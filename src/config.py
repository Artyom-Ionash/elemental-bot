from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_token: SecretStr
    discord_log_channel_id: int
    telegram_token: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    telegram_admin_id: int | None = None

    # Настройки работы бота
    port: int = Field(default=7860, ge=1, le=65535)
    debug: bool = False
    default_model: str = "gemini-3.1-flash-lite-preview"
    max_tokens: int = 10000

    system_prompt: str = "Ты — пацан, звать тебя Стихиал, ведёшь себя непринуждённо. Обычно отвечаешь коротко, изредка — абзацем.\n"

    @model_validator(mode="after")
    def validate_provider_keys(self) -> Self:
        """
        Проверяет наличие необходимого API-ключа в зависимости от выбранной модели.
        Обеспечивает симметрию конфигураций и защищает бота от падения при запросах.
        """
        # Модели OpenRouter обычно имеют формат 'провайдер/модель' (например, 'openai/gpt-4o-mini')
        is_openrouter_model = "/" in self.default_model

        if is_openrouter_model:
            if not self.openrouter_api_key:
                raise ValueError(f"Выбрана модель OpenRouter '{self.default_model}', но OPENROUTER_API_KEY не задан в окружении.")
        else:
            if not self.gemini_api_key:
                raise ValueError(f"Выбрана нативная модель Gemini '{self.default_model}', но GEMINI_API_KEY не задан в окружении.")

        return self


# Создаем глобальный синглтон настроек
settings = Settings()  # type: ignore[call-arg]
