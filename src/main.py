import asyncio
import logging

from telegram.ext import Application, MessageHandler, filters

from config import settings
from core.bootstrap import init_common
from core.bot.discord.client import setup_discord_client
from core.bot.runners import run_discord_bot, run_telegram_bot
from core.bot.telegram.messenger import TelegramMessenger
from core.http.server import start_web_server

logger = logging.getLogger(__name__)


async def main() -> None:
    # 1. Инициализация общих AI/ML зависимостей
    llm_client, token_calculator, context_builder = init_common()

    # 2. Настройка Telegram бот-приложения
    telegram_messenger = TelegramMessenger(
        llm_client=llm_client,
        token_calculator=token_calculator,
        max_tokens=settings.max_tokens,
        system_prompt=settings.system_prompt,
    )

    assert settings.telegram_token is not None
    tg_app = Application.builder().token(settings.telegram_token.get_secret_value()).build()
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_messenger.handle))

    # 3. Настройка Discord клиента
    bot_discord = setup_discord_client(llm_client=llm_client, context_builder=context_builder)

    # 4. Конкурентный запуск веб-сервера, Telegram и Discord ботов в одном контуре
    logger.info("Запуск веб-сервера, Telegram и Discord ботов в параллельном режиме...")
    try:
        await asyncio.gather(
            start_web_server(),
            run_telegram_bot(tg_app),
            run_discord_bot(bot_discord),
        )
    except asyncio.CancelledError:
        logger.info("Задачи остановлены.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение завершило работу по сигналу пользователя.")
