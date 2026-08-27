import asyncio
import logging

from config import settings
from core.bootstrap import init_common
from core.bot.discord.client import setup_discord_client
from core.bot.runners import run_discord_bot, run_telegram_bot
from core.bot.telegram.client import setup_telegram_client
from core.http.server import start_web_server

logger = logging.getLogger(__name__)


async def main() -> None:
    # 1. Инициализация общих AI/ML зависимостей
    llm_client, token_calculator, context_builder = init_common()

    # 2. Настройка Telegram бота
    assert settings.telegram_token is not None
    telegram_bot = setup_telegram_client(
        token=settings.telegram_token.get_secret_value(),
        llm_client=llm_client,
        token_calculator=token_calculator,
        max_tokens=settings.max_tokens,
        system_prompt=settings.system_prompt,
    )

    # 3. Настройка Discord бота
    assert settings.discord_token is not None
    discord_bot = setup_discord_client(
        token=settings.discord_token.get_secret_value(),
        llm_client=llm_client,
        context_builder=context_builder,
    )

    # 4. Конкурентный запуск веб-сервера, Telegram и Discord ботов в одном контуре
    logger.info("Запуск веб-сервера, Telegram и Discord ботов в параллельном режиме...")
    try:
        await asyncio.gather(
            start_web_server(),
            run_telegram_bot(telegram_bot),
            run_discord_bot(discord_bot),
        )
    except asyncio.CancelledError:
        logger.info("Задачи остановлены.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение завершило работу по сигналу пользователя.")
