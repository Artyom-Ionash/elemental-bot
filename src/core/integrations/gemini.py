import logging
from collections.abc import Iterable

from google import genai
from google.genai import errors, types

from core.integrations.base_provider import BaseLLMProvider
from core.types.llm import CompletionResult, MessageParam

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Нативный провайдер Gemini.

    Фокусируется исключительно на маппинге API, авторизации и сериализации данных.
    Логика повторных попыток (Retry) вынесена в прокси-слой ``RetryingLLMProvider``.
    """

    def __init__(self, api_key: str, default_model: str = "gemini-flash-lite-latest") -> None:
        self.client = genai.Client(api_key=api_key)
        self.default_model = default_model

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:

        target_model = model or self.default_model
        contents = [
            types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[types.Part.from_text(text=msg["content"])],
            )
            for msg in messages
            if msg["role"] != "system"
        ]

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

        try:
            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
        except errors.APIError as e:
            logger.error(
                "API Error | Status: %s | Error: %s",
                str(e.code),
                str(e),
            )
            raise RuntimeError(f"Контур управления не ответил: {e}") from e
        except Exception as e:
            logger.error("System/Network Error: %s", e)
            raise

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
