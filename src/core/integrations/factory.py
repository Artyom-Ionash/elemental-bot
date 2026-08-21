from config import Settings
from core.integrations.base_provider import BaseLLMProvider
from core.integrations.gemini import GeminiProvider
from core.integrations.openrouter import OpenRouterProvider


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    """Создаёт LLM-провайдера на основе выбранной модели (``default_model``).

    OpenRouter-модели задаются форматом ``провайдер/модель`` (например, ``openai/gpt-4o-mini``),
    нативные модели Gemini — без слэша. Выбор провайдера симметричен валидации в ``config.py``.
    """
    if "/" in settings.default_model:
        if settings.openrouter_api_key is None:
            raise ValueError("Выбрана модель OpenRouter, но OPENROUTER_API_KEY не задан в окружении.")
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key.get_secret_value(),
            default_model=settings.default_model,
        )

    if settings.gemini_api_key is None:
        raise ValueError("Выбрана нативная модель Gemini, но GEMINI_API_KEY не задан в окружении.")
    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        default_model=settings.default_model,
    )
