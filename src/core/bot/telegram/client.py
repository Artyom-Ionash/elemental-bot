import logging

from telegram.ext import Application, MessageHandler, filters

from core.bot.telegram.messenger import TelegramMessenger
from core.integrations.base_provider import BaseLLMProvider
from lib.token_calculator import TokenCalculator

logger = logging.getLogger(__name__)


class TelegramBot:
    """Инкапсулирует приложение и обработчики Telegram-бота."""

    def __init__(
        self,
        token: str,
        llm_client: BaseLLMProvider,
        token_calculator: TokenCalculator,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.token = token
        self.messenger = TelegramMessenger(
            llm_client=llm_client,
            token_calculator=token_calculator,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        self.app = Application.builder().token(token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.messenger.handle))

    async def start(self) -> None:
        """Инициализация и запуск опроса Telegram бота."""
        await self.app.initialize()
        await self.app.start()
        if self.app.updater is not None:
            await self.app.updater.start_polling()

    async def stop(self) -> None:
        """Остановка и завершение работы Telegram бота."""
        if self.app.updater is not None:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()


def setup_telegram_client(
    token: str,
    llm_client: BaseLLMProvider,
    token_calculator: TokenCalculator,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
) -> TelegramBot:
    """Создает и настраивает экземпляр TelegramBot."""
    return TelegramBot(
        token=token,
        llm_client=llm_client,
        token_calculator=token_calculator,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
    )
