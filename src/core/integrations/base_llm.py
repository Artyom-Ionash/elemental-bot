from abc import ABC, abstractmethod
from collections.abc import Iterable

from core.types.llm import CompletionResult, MessageParam


class BaseLLMClient(ABC):
    @abstractmethod
    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:
        pass
