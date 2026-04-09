import json
import logging

import discord


class DiscordHandler(logging.Handler):
    def __init__(self, bot: discord.Client, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        # Структурируем лог в JSON для парсинга
        log_entry = {"level": record.levelname, "module": record.name, "msg": record.getMessage()}
        message = f"```json\n{json.dumps(log_entry, indent=2, ensure_ascii=False)}\n```"
        self.bot.loop.create_task(self.send_log(message))

    async def send_log(self, message: str) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(message)


def setup_logging(bot: discord.Client, log_channel_id: int) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(console_handler)

    # Хендлер для Дискорда
    discord_handler = DiscordHandler(bot, log_channel_id)
    discord_handler.setLevel(logging.ERROR)  # В Дискорд только ошибки!
    root_logger.addHandler(discord_handler)
