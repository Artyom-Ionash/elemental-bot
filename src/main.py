import asyncio
import logging

import discord
from telegram.ext import Application, MessageHandler, filters

from config import settings
from core.discord.guards import is_messageable
from core.discord.messenger import Messenger
from core.http.server import start_web_server
from core.integrations.gemini import GeminiClient
from core.telegram.messenger import TelegramMessenger
from lib.context_builder import ContextBuilder
from lib.token_calculator import TokenCalculator

logger = logging.getLogger(__name__)


# --- Инициализация общих компонентов ---
def init_common() -> tuple[GeminiClient, TokenCalculator, ContextBuilder]:
    """Инициализирует общие компоненты для предотвращения дублирования соединений."""
    assert settings.gemini_api_key is not None
    llm_client = GeminiClient(api_key=settings.gemini_api_key.get_secret_value())
    token_calculator = TokenCalculator()
    context_builder = ContextBuilder(token_calculator=token_calculator, max_tokens=settings.max_tokens)
    return llm_client, token_calculator, context_builder


# --- Класс Discord Бота ---
class ElementalBot(discord.Client):
    def __init__(self, llm_client: GeminiClient, context_builder: ContextBuilder) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, activity=discord.CustomActivity(name="Исследование"))

        # Передача зависимостей извне
        self.llm_client = llm_client
        self.context_builder = context_builder
        self.messenger: Messenger | None = None

    async def setup_hook(self) -> None:
        # Сборка обработчика сообщений с внедренными зависимостями
        self.messenger = Messenger(bot=self, llm_client=self.llm_client, context_builder=self.context_builder)


bot_discord: ElementalBot | None = None


# --- Обертка для асинхронного запуска Telegram ---
async def run_telegram_bot(tg_app: Application) -> None:
    logger.info("Telegram бот инициализируется...")
    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling()
        try:
            # Удерживаем задачу активной, пока не будет отменен весь Event Loop
            await asyncio.Event().wait()
        finally:
            logger.info("Остановка Telegram бота...")
            await tg_app.updater.stop()
            await tg_app.stop()


# --- Обертка для асинхронного запуска Discord ---
async def run_discord_bot(discord_client: ElementalBot) -> None:
    logger.info("Discord бот инициализируется...")
    token = settings.discord_token.get_secret_value()
    try:
        await discord_client.start(token)
    finally:
        logger.info("Остановка Discord бота...")
        await discord_client.close()


# --- Единая точка входа ---
async def main() -> None:
    global bot_discord

    # 1. Запуск общего асинхронного веб-сервера
    await start_web_server()

    # 2. Инициализация общих AI/ML зависимостей
    llm_client, token_calculator, context_builder = init_common()

    # 3. Настройка Telegram бот-приложения
    telegram_messenger = TelegramMessenger(
        llm_client=llm_client,
        token_calculator=token_calculator,
        max_tokens=settings.max_tokens,
        system_prompt=settings.system_prompt,
    )

    assert settings.telegram_token is not None
    tg_app = Application.builder().token(settings.telegram_token.get_secret_value()).build()
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_messenger.handle))

    # 4. Настройка Discord клиента
    bot_discord = ElementalBot(llm_client=llm_client, context_builder=context_builder)

    # Регистрируем события Discord на созданный экземпляр
    @bot_discord.event
    async def on_ready() -> None:
        logger.info("%s на связи. Жду приказов.", bot_discord.user)

    @bot_discord.event
    async def on_message(message: discord.Message) -> None:
        if bot_discord is None or bot_discord.messenger is None:
            return
        if message.author == bot_discord.user:
            return
        if not bot_discord.user.mentioned_in(message):
            return

        channel = message.channel
        if not is_messageable(channel):
            return

        await bot_discord.messenger.handle(message)

    # 5. Конкурентный запуск обеих платформ в одном потоке
    logger.info("Запуск Telegram и Discord ботов в параллельном режиме...")
    try:
        await asyncio.gather(
            run_telegram_bot(tg_app),
            run_discord_bot(bot_discord),
        )
    except asyncio.CancelledError:
        logger.info("Задачи ботов остановлены.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение завершило работу по сигналу пользователя.")
