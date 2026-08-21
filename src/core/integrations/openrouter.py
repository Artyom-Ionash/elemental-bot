from collections.abc import Iterable

from openai import AsyncOpenAI

from core.integrations.base_provider import BaseLLMProvider
from core.types.llm import CompletionResult, MessageParam


class OpenRouterProvider(BaseLLMProvider):
    """Адаптер OpenRouter поверх OpenAI-совместимого API.

    Нормализует ответ SDK к универсальному контракту ``CompletionResult``.
    """

    def __init__(self, api_key: str, default_model: str = "openai/gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.default_model = default_model

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:
        target_model = model or self.default_model

        # Приводим к типу, который ожидает SDK (структура совпадает с нашим MessageParam)
        completion = await self._client.chat.completions.create(
            model=target_model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )

        choice = completion.choices[0] if completion.choices else None

        content = ""
        if choice is not None and choice.message.content is not None:
            content = choice.message.content

        # Некоторые reasoning-модели отдают цепочку рассуждений в отдельном поле
        reasoning = getattr(choice.message, "reasoning_content", None) if choice is not None else None
        thoughts = reasoning if isinstance(reasoning, str) else ""

        usage = completion.usage
        prompt_tokens = usage.prompt_tokens if usage is not None else 0
        completion_tokens = usage.completion_tokens if usage is not None else 0

        return {
            "content": content,
            "thoughts": thoughts,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
