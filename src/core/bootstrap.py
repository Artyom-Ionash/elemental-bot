from config import settings
from core.integrations.base_provider import BaseLLMProvider
from core.integrations.factory import create_llm_provider
from lib.context_builder import ContextBuilder
from lib.token_calculator import TokenCalculator


def init_common() -> tuple[BaseLLMProvider, TokenCalculator, ContextBuilder]:
    """Инициализирует общие компоненты для предотвращения дублирования соединений."""
    llm_client = create_llm_provider(settings)
    token_calculator = TokenCalculator()
    context_builder = ContextBuilder(token_calculator=token_calculator, max_tokens=settings.max_tokens)
    return llm_client, token_calculator, context_builder
