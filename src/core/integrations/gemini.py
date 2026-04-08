import asyncio  # <--- Добавили для паузы
import logging
from collections.abc import Iterable
from typing import Any

import aiohttp

from core.types.llm import MessageParam

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str = "gemini-3.1-flash-lite-preview",
        temperature: float = 0.3,
    ) -> dict[str, Any]:

        contents = []
        system_instruction = None

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"

        # --- НАСТРОЙКИ АМОРТИЗАТОРА ---
        max_retries = 3
        base_delay = 2  # Секунды

        async with aiohttp.ClientSession() as session:
            for attempt in range(max_retries):
                async with session.post(url, json=payload) as resp:
                    # Если база перегружена (503) или слишком много запросов (429)
                    if resp.status in (503, 429):
                        if attempt < max_retries - 1:
                            # Увеличиваем задержку: 2 сек, 4 сек, 8 сек...
                            sleep_time = base_delay * (2**attempt)
                            logger.info("[Gemini] Сервер шлёт нахер (%s). Ждём %s сек. Попытка %d/%d...", resp.status, sleep_time, attempt + 1, max_retries)
                            await asyncio.sleep(sleep_time)
                            continue  # Пробуем еще раз
                        else:
                            # Если исчерпали попытки — падаем с честной ошибкой
                            error_text = await resp.text()
                            raise RuntimeError(f"Gemini API сдох окончательно [{resp.status}]: {error_text}")

                    # Если ошибка другая (например 400 Bad Request) - падаем сразу
                    if not resp.ok:
                        error_text = await resp.text()
                        raise RuntimeError(f"Gemini API Error [{resp.status}]: {error_text}")

                    # Если всё чётко (200 OK) — выходим из цикла
                    data = await resp.json()
                    break

            # Парсим ответ
            try:
                text_response = data["candidates"][0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata", {})

                return {"content": text_response, "prompt_tokens": usage.get("promptTokenCount", 0), "completion_tokens": usage.get("candidatesTokenCount", 0)}
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Ошибка парсинга ответа Gemini: {data}") from e
