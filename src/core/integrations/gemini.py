import asyncio
import logging
import traceback
from collections.abc import Iterable
from typing import Any

from google import genai
from google.genai import types

from core.types.llm import MessageParam

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3.1-flash-lite-preview"

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:

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

        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
                break  # Пробили стену, выходим из цикла
            except Exception as e:
                error_str = str(e)
                # [ОБНОВЛЕНИЕ]: Добавляем обрывы связи и тайм-ауты в список того, что нужно терпеть
                retriable_errors = ["503", "Server disconnected", "TimeoutError", "ClientConnectorError"]

                if any(err in error_str for err in retriable_errors):
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2**attempt)
                        logger.warning("Сбой на линии (%s). Ждем %s сек. Попытка %s/%s", type(e).__name__, sleep_time, attempt + 1, max_retries)
                        await asyncio.sleep(sleep_time)
                        continue

                # Если ошибка другая (например, кривой токен) или попытки кончились — падаем
                if hasattr(e, "response") and e.response:  # type: ignore
                    resp = e.response  # type: ignore
                    logger.error(
                        "API Error | Status: %s | Request-ID: %s | Error: %s",
                        getattr(resp, "status_code", "Unknown"),
                        resp.headers.get("x-goog-request-id", "N/A") if hasattr(resp, "headers") else "N/A",
                        e,
                    )
                else:
                    logger.error("System/Network Error: %s\n%s", e, traceback.format_exc())

                raise RuntimeError(f"Контур управления не ответил: {e}")

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

        return {"content": answer_text, "thoughts": thought_text, "prompt_tokens": p_tokens, "completion_tokens": c_tokens}
