import logging

from discord.ext import commands


class DiscordHandler(logging.Handler):
    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        # Вот здесь магия: getMessage() заменяет %s на реальные значения
        formatted_message = record.getMessage()

        # Теперь отправляем уже "чистый" текст
        self.bot.loop.create_task(self.send_log(record, formatted_message))

    async def send_log(self, record: logging.LogRecord, message: str) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            # Тут вставляем отформатированное сообщение
            await channel.send(f"**[{record.levelname}]** {message}")


# В setup_hook бота добавь:
# handler = DiscordHandler(self, 1234567890) # ID твоего канала
# logging.getLogger('discord').addHandler(handler)
