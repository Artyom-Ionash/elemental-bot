import asyncio
import logging
import traceback
from collections.abc import Iterable

from google import genai
from google.genai import errors, types

from core.integrations.base_llm import BaseLLMClient
from core.types.llm import CompletionResult, MessageParam

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3.1-flash-lite-preview"

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:

        target_model = model or self.model_name
        contents = [types.Content(role="user" if msg["role"] == "user" else "model", parts=[types.Part.from_text(text=msg["content"])]) for msg in messages if msg["role"] != "system"]

        system_instruction = next((m["content"] for m in messages if m["role"] == "system"), None)

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_level=types.ThinkingLevel.HIGH),
            tools=[
                # Платные (https://ai.google.dev/gemini-api/docs/google-search):
                # types.Tool(google_search=types.GoogleSearch()),
                # types.Tool(google_search_retrieval=types.GoogleSearchRetrieval()),
            ],
        )

        # Преодоление ошибки 503

        max_retries = 4
        base_delay = 2
        response: types.GenerateContentResponse | None = None

        for attempt in range(max_retries):
            try:
                # Избегаем предупреждения "partially unknown" на уровне вызова SDK с помощью точечного игнорирования.
                # При этом возвращаемый тип response остается полностью и строго типизированным.
                response = await self.client.aio.models.generate_content(  # type: ignore[reportUnknownMemberType]
                    model=target_model,
                    contents=contents,
                    config=config,
                )
                break  # Пробили стену, выходим из цикла
            except errors.APIError as e:
                logger.error(
                    "API Error | Status: %s | Error: %s",
                    str(e.code),
                    str(e),
                )
                raise RuntimeError(f"Контур управления не ответил: {e}") from e
            except Exception as e:
                error_str = str(e)
                # Добавляем обрывы связи и тайм-ауты в список того, что нужно терпеть
                retriable_errors = ["503", "Server disconnected", "TimeoutError", "ClientConnectorError"]

                if any(err in error_str for err in retriable_errors):
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2**attempt)
                        logger.warning("Сбой на линии (%s). Ждем %s сек. Попытка %s/%s", type(e).__name__, sleep_time, attempt + 1, max_retries)
                        await asyncio.sleep(sleep_time)
                        continue

                # Системная или сетевая ошибка общего характера
                logger.error("System/Network Error: %s\n%s", e, traceback.format_exc())
                raise RuntimeError(f"Контур управления не ответил: {e}") from e

        if response is None:
            raise RuntimeError("Контур управления вернул пустой ответ")

        # Парсинг
        thought_text = ""
        answer_text = ""

        # Безопасный парсинг, чтобы не словить IndexError, если ответ пустой
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, "thought", False):
                    thought_text += part.text or ""
                else:
                    answer_text += part.text or ""

        p_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) if response.usage_metadata else 0
        c_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) if response.usage_metadata else 0

        return {
            "content": answer_text,
            "thoughts": thought_text,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
        }
