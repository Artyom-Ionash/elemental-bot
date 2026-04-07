from collections.abc import Iterable

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from core.types.llm import MessageParam


class OpenRouterClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    async def create_completion(
        self,
        messages: Iterable[MessageParam],  # Наш внутренний контракт
        model: str = "openai/gpt-4o-mini",
        temperature: float = 0.9,
    ) -> ChatCompletion:
        # Приводим к типу, который ожидает SDK (cast к Any, так как структура совпадает)
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
