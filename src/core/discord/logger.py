import io
import logging

import discord


class DiscordHandler(logging.Handler):
    def __init__(self, bot: discord.Client, channel_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        # ЖЕСТКАЯ ФИЛЬТРАЦИЯ
        if record.levelno < self.level:
            return

        # Проверяем, передал ли инженер данные для файла через параметр 'extra'
        file_content = getattr(record, "file_content", None)
        file_name = getattr(record, "file_name", "dump.md")

        if file_content:
            # Упаковываем строку в байты и создаем discord.File прямо здесь
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            discord_file = discord.File(fp=file_bytes, filename=file_name)
            msg = f"🛠 **[{record.levelname}]** {record.name}: {record.getMessage()}"
            self.bot.loop.create_task(self.send_file(discord_file, msg))
        else:
            # Обычный текстовый лог (JSON для читаемости админом)
            level = record.levelname
            module = record.name
            msg = record.getMessage()
            message = f"[`{level}`]\t**{module}**\n```log\n{msg}\n```"
            self.bot.loop.create_task(self.send_log(message))

    async def send_log(self, message: str) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            if len(message) <= 1900:
                # Если ответ компактный — шлем текстом, не грузим систему
                await channel.send(message)
            else:
                # Если портянка большая — упаковываем в файл
                # Использование BytesIO позволяет создать файл в памяти, не мусоря на диске
                file_bytes = io.BytesIO(message.encode("utf-8"))
                discord_file = discord.File(fp=file_bytes, filename="response.md")

                # Добавляем короткий заголовок, чтобы было ясно, что внутри
                await channel.send("Журнал слишком длинный, держи файлом:", file=discord_file)

    async def send_file(self, file: discord.File, content: str) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(content=content, file=file)


def setup_logging(bot: discord.Client, log_channel_id: int) -> None:
    logging.getLogger("discord").propagate = False

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Root видит всё

    # 1. Консоль: INFO и выше (нам не надо видеть каждое шевеление отладки)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # 2. Дискорд: ТОЛЬКО ОШИБКИ (ERROR и CRITICAL)
    discord_handler = DiscordHandler(bot, log_channel_id)
    discord_handler.setLevel(logging.ERROR)  # ЗДЕСЬ ЖЕСТКИЙ ЗАМОР
    root_logger.addHandler(discord_handler)
