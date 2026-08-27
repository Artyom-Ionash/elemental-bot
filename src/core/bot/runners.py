import asyncio
import logging

from core.bot.discord.client import DiscordBot
from core.bot.telegram.client import TelegramBot

logger = logging.getLogger(__name__)


async def run_telegram_bot(telegram_bot: TelegramBot) -> None:
    """Обертка для асинхронного запуска Telegram бота."""
    logger.info("Telegram бот инициализируется...")
    try:
        await telegram_bot.start()
        await asyncio.Event().wait()
    finally:
        logger.info("Остановка Telegram бота...")
        await telegram_bot.stop()


async def run_discord_bot(discord_bot: DiscordBot) -> None:
    """Обертка для асинхронного запуска Discord бота."""
    logger.info("Discord бот инициализируется...")
    try:
        await discord_bot.start_bot()
    finally:
        logger.info("Остановка Discord бота...")
        await discord_bot.stop_bot()
