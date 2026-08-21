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
    bot_discord = setup_discord_client(llm_client=llm_client, context_builder=context_builder)

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
