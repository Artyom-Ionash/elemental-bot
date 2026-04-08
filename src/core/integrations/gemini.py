from collections.abc import Iterable
from typing import Any

# Официальная библиотека от Гугла
from google import genai
from google.genai import types

from core.types.llm import MessageParam


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        # Официальный клиент "из коробки"
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

        # РЕЖИМ ПЕРЕГРУЗКИ: Делаем петлю на случай, если Гугл шлёт нас лесом
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )

                # Если дошли сюда — всё хорошо, выходим из петли
                break

            except Exception as e:
                # Проверяем, есть ли статус ошибки (иногда это APIError, иногда сетевая)
                # Если это последняя попытка — проваливаемся дальше
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Система не смогла восстановиться после {max_retries} попыток: {e}")

                # Если ошибка транзитная (временная) — ждем
                wait_time = 2**attempt  # 1, 2, 4 секунды (экспоненциальная задержка)
                print(f"[DEBUG] Отбой связи. Ждем {wait_time} сек... (Попытка {attempt + 1})")
                await asyncio.sleep(wait_time)

        # Парсинг (здесь логика остается та же)
        thought_text = ""
        answer_text = ""
        for part in response.candidates[0].content.parts:
            if part.thought:
                thought_text += part.text or ""
            else:
                answer_text += part.text or ""

        return {"content": answer_text, "thoughts": thought_text, "prompt_tokens": response.usage_metadata.prompt_token_count, "completion_tokens": response.usage_metadata.candidates_token_count}
