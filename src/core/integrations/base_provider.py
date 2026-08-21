from abc import ABC, abstractmethod
from collections.abc import Iterable

from core.types.llm import CompletionResult, MessageParam


class BaseLLMProvider(ABC):
    """Унифицированный контракт для всех LLM-провайдеров.

    Любая реализация обязана возвращать нормализованный ``CompletionResult``,
    чтобы верхние слои (messenger) не зависели от конкретного SDK.
    """

    @abstractmethod
    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:
        """Генерирует ответ модели и возвращает его в универсальном виде."""
        raise NotImplementedError
