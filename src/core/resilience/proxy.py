import logging
from collections.abc import Iterable

import tenacity

from core.integrations.base_provider import BaseLLMProvider
from core.resilience.policy import RetryPolicy
from core.types.llm import CompletionResult, MessageParam

logger = logging.getLogger(__name__)


class RetryingLLMProvider(BaseLLMProvider):
    """Прокси-провайдер, оборачивающий любой BaseLLMProvider

    и применяющий промышленную политику повторных попыток через tenacity.
    """

    def __init__(self, provider: BaseLLMProvider, policy: RetryPolicy | None = None) -> None:
        self.provider = provider
        self.policy = policy or RetryPolicy()

    async def create_completion(
        self,
        messages: Iterable[MessageParam],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> CompletionResult:
        retryer = tenacity.AsyncRetrying(
            retry=tenacity.retry_if_exception(self.policy.is_retriable),
            stop=tenacity.stop_after_attempt(self.policy.max_retries),
            wait=tenacity.wait_exponential(multiplier=self.policy.base_delay),
            reraise=True,
        )

        async for attempt in retryer:
            with attempt:
                result = await self.provider.create_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                )
                return result

        raise RuntimeError("Превышено максимальное число попыток вызова LLM")
