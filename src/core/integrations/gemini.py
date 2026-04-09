import logging
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
        )

        try:
            # SDK сам делает retry внутри. Если сдох — вернет исключение.
            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            # Пытаемся вытянуть детали, если это API-ошибка
            if hasattr(e, "response"):
                # Официальный SDK прокидывает response объект
                resp = e.response
                logger.error("API Error | Status: %s | Request-ID: %s | Error: %s", resp.status_code if hasattr(resp, "status_code") else "Unknown", resp.headers.get("x-goog-request-id", "N/A"), e)
            else:
                # Если это не API-ошибка, а твой косяк в логике или сеть
                logger.error("System/Network Error: %s\n%s", e, traceback.format_exc())

            raise RuntimeError(f"Контур управления не ответил: {e}")

        # Парсинг
        thought_text = ""
        answer_text = ""
        for part in response.candidates[0].content.parts:
            if part.thought:
                thought_text += part.text or ""
            else:
                answer_text += part.text or ""

        return {"content": answer_text, "thoughts": thought_text, "prompt_tokens": response.usage_metadata.prompt_token_count, "completion_tokens": response.usage_metadata.candidates_token_count}
