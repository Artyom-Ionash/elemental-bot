import logging

from discord.ext import commands


class DiscordHandler(logging.Handler):
    def __init__(self, bot: commands.Bot, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        # Получаем форматированное сообщение (включая INFO, ERROR, WARNING)
        message = self.format(record)

        # Экранируем символы, чтобы не сломать Markdown Дискорда
        message = message.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")

        # Отправляем в очередь
        self.bot.loop.create_task(self.send_log(record.levelname, message))

    async def send_log(self, level: str, message: str) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            # Делаем лог красивым и читаемым
            color = "🔴" if level in ["ERROR", "CRITICAL"] else "🟡" if level == "WARNING" else "🟢"
            await channel.send(f"{color} **[{level}]** `{message[:1900]}`")
