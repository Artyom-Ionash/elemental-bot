from collections.abc import Iterable
from typing import Any

import aiohttp

from core.types.llm import MessageParam


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        # 1. Резервируем место под постоянную трубу
        self._session: aiohttp.ClientSession | None = None

    # 2. Ленивая инициализация сессии с ЖЕСТКИМ ТАЙМАУТОМ
    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Если Гугл тупит дольше 15 секунд — рубим нахер, чтоб не вешать бота
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

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

        # 3. Берем нашу ПОСТОЯННУЮ трубу, а не создаем новую
        session = self._get_session()

        try:
            async with session.post(url, json=payload) as resp:
                if not resp.ok:
                    error_text = await resp.text()
                    raise RuntimeError(f"Gemini API Error [{resp.status}]: {error_text}")

                data = await resp.json()

                try:
                    text_response = data["candidates"][0]["content"]["parts"][0]["text"]
                    usage = data.get("usageMetadata", {})
                    return {"content": text_response, "prompt_tokens": usage.get("promptTokenCount", 0), "completion_tokens": usage.get("candidatesTokenCount", 0)}
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"Ошибка парсинга ответа: {data}") from e

        except TimeoutError:
            raise RuntimeError("Таймаут: Гугл не ответил за 15 секунд. Завод стоит.")

    # 4. Не забываем глушить мотор при выходе
    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
