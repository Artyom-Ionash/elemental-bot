import asyncio
import logging
import traceback

import discord

from features.discord_bot.client import DiscordBot
from features.telegram_bot.client import TelegramBot

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
    except discord.errors.HTTPException as e:
        error_tb = traceback.format_exc()
        retry_after = getattr(e, "retry_after", None)
        headers = getattr(e.response, "headers", None) if hasattr(e, "response") else None
        if retry_after is None and headers:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
        text_content = getattr(e, "text", None)

        logger.error(f"Discord HTTPException при запуске (Status: {getattr(e, 'status', 'unknown')}, retry_after: {retry_after}, text: {text_content}):\nОшибка:\n{error_tb}")
    except Exception:
        error_tb = traceback.format_exc()
        logger.error(f"Критический сбой при запуске Discord бота:\n{error_tb}")
    finally:
        logger.info("Остановка Discord бота...")
        await discord_bot.stop_bot()
