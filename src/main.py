import logging

import discord

from config import settings
from core.discord.guards import is_messageable
from core.discord.logger import setup_logging
from core.discord.messenger import Messenger
from core.http.server import start_web_server
from core.integrations.gemini import GeminiClient

logger = logging.getLogger(__name__)


class ElementalBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, activity=discord.CustomActivity(name="Исследование"))

        # Зависимости
        self.messenger: Messenger | None = None

    async def setup_hook(self) -> None:
        log_channel_id = settings.discord_log_channel_id

        # 1. Инициализация LLM
        assert settings.gemini_api_key is not None
        llm_client = GeminiClient(api_key=settings.gemini_api_key.get_secret_value())

        # 2. Сборка обработчика сообщений
        self.messenger = Messenger(bot=self, llm_client=llm_client)

        # 3. Запуск фоновых задач (Веб-сервер)
        self.loop.create_task(start_web_server())

        # 4. Инициализация логгера
        setup_logging(self, log_channel_id)
        logger.info("Система инициализирована. База на месте.")


bot = ElementalBot()


@bot.event
async def on_ready() -> None:
    logger.info("%s на связи. Жду приказов.", bot.user)


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Тонкая прокладка. Занимается ТОЛЬКО маршрутизацией и строгим Type Narrowing.
    """
    # --- 1. TYPE GUARDS & EARLY EXITS ---
    if bot.user is None or bot.messenger is None:
        return
    if message.author == bot.user:
        return
    if not bot.user.mentioned_in(message):
        return

    channel = message.channel
    if not is_messageable(channel):
        return

    # --- 2. ДЕЛЕГИРОВАНИЕ БИЗНЕС-ЛОГИКИ ---
    await bot.messenger.handle(message)


if __name__ == "__main__":
    token = settings.discord_token.get_secret_value()
    bot.run(token)
