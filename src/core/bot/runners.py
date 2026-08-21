import asyncio
import logging

from telegram.ext import Application

from config import settings
from core.bot.discord.client import ElementalBot

logger = logging.getLogger(__name__)


async def run_telegram_bot(tg_app: Application) -> None:
    """Обертка для асинхронного запуска Telegram бота."""
    logger.info("Telegram бот инициализируется...")
    async with tg_app:
        await tg_app.start()
        updater = tg_app.updater
        if updater is not None:
            await updater.start_polling()
        try:
            # Удерживаем задачу активной, пока не будет отменен весь Event Loop
            await asyncio.Event().wait()
        finally:
            logger.info("Остановка Telegram бота...")
            if updater is not None:
                await updater.stop()
            await tg_app.stop()


async def run_discord_bot(discord_client: ElementalBot) -> None:
    """Обертка для асинхронного запуска Discord бота."""
    logger.info("Discord бот инициализируется...")
    token = settings.discord_token.get_secret_value()
    try:
        await discord_client.start(token)
    finally:
        logger.info("Остановка Discord бота...")
        await discord_client.close()
