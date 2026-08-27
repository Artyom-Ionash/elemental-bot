import logging

import discord

from core.bot.discord.guards import is_messageable
from core.bot.discord.messenger import Messenger
from core.integrations.base_provider import BaseLLMProvider
from lib.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class DiscordBot(discord.Client):
    """Инкапсулирует клиент и обработчики Discord-бота."""

    def __init__(self, token: str, llm_client: BaseLLMProvider, context_builder: ContextBuilder) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, activity=discord.CustomActivity(name="Исследование"))

        self.token = token
        self.llm_client = llm_client
        self.context_builder = context_builder
        self.messenger: Messenger | None = None

    async def setup_hook(self) -> None:
        # Сборка обработчика сообщений с внедренными зависимостями
        self.messenger = Messenger(bot=self, llm_client=self.llm_client, context_builder=self.context_builder)

    async def start_bot(self) -> None:
        """Запуск Discord клиента с инкапсулированным токеном."""
        await self.start(self.token)

    async def stop_bot(self) -> None:
        """Остановка Discord клиента."""
        await self.close()


def setup_discord_client(token: str, llm_client: BaseLLMProvider, context_builder: ContextBuilder) -> DiscordBot:
    """Создает и настраивает экземпляр DiscordBot вместе с обработчиками событий."""
    bot_discord = DiscordBot(token=token, llm_client=llm_client, context_builder=context_builder)

    @bot_discord.event
    async def on_ready() -> None:
        logger.info("%s на связи. Жду приказов.", bot_discord.user)

    @bot_discord.event
    async def on_message(message: discord.Message) -> None:
        if bot_discord.messenger is None:
            return
        if message.author == bot_discord.user:
            return
        if not bot_discord.user or not bot_discord.user.mentioned_in(message):
            return

        channel = message.channel
        if not is_messageable(channel):
            return

        await bot_discord.messenger.handle(message)

    return bot_discord
