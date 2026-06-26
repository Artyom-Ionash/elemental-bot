import io
import logging
import traceback

import discord
import tiktoken
from aiohttp import web

from config import settings
from core.discord.guards import is_messageable
from core.integrations.gemini import GeminiClient
from core.types.llm import MessageParam

logger = logging.getLogger(__name__)

encoding = tiktoken.get_encoding("o200k_base")


class ElementalBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, activity=discord.CustomActivity(name="Исследование"))

        self.llm_client: GeminiClient | None = None

    async def setup_hook(self) -> None:
        log_channel_id = settings.discord_log_channel_id

        # Проверяем, какой провайдер должен быть инициализирован
        is_openrouter = "/" in settings.default_model

        if is_openrouter:
            # Предупреждаем о временном ограничении интеграции (технический долг)
            raise NotImplementedError("Интеграция OpenRouter в единый интерфейс (BaseLLM) находится в процессе разработки. Пожалуйста, используйте нативную модель Gemini.")

        # Статический анализатор (mypy) требует гарантии, что ключ не None.
        # Благодаря валидатору в Settings мы уверены в этом в рантайме.
        assert settings.gemini_api_key is not None
        self.llm_client = GeminiClient(api_key=settings.gemini_api_key.get_secret_value())

        # Запуск веб-сервера
        self.loop.create_task(start_web_server())

        # Инициализация централизованного логгера
        from core.discord.logger import setup_logging

        setup_logging(self, log_channel_id)

        logger.info("Система инициализирована. База на месте.")


bot = ElementalBot()


# --- 1. Асинхронный вахтер ---
async def health_check(request: web.Request) -> web.Response:
    # Инспектор от Hugging Face или Render придет сюда
    return web.Response(text="Bot is alive. Running on Gemini.")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()

    # Поддержка динамического порта из конфигурации Pydantic
    port = settings.port

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Веб-сервер поднят в асинхронном контуре на порту %d.", port)


@bot.event
async def on_ready() -> None:
    logger.info("%s на связи. Жду приказов.", bot.user)


@bot.event
async def on_message(message: discord.Message) -> None:
    """
    Обработчик сообщений со строгим Type Narrowing (Defense in Depth).
    """
    # --- 1. TYPE GUARDS & EARLY EXITS ---

    if bot.user is None or bot.llm_client is None:
        return

    if message.author == bot.user:
        return

    if not bot.user.mentioned_in(message):
        return

    channel = message.channel

    if not is_messageable(channel):
        return

    # --- 2. ПОДГОТОВКА КОНТЕКСТА ---

    current_model = settings.default_model

    # Вычищаем упоминание бота из запроса
    user_request = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    # Запоминаем автора и текст, чтобы вставить их в самый конец
    current_message_block = f"{message.author.name}: {user_request}\n"

    if not user_request:
        user_request = "Проанализируй переписку выше:"

    system_prompt = settings.system_prompt

    messages_to_process: list[str] = []
    current_log_tokens = 0
    message_count = 0

    async with channel.typing():
        # --- 3. ИЗВЛЕЧЕНИЕ ИСТОРИИ ---
        # Выгребаем историю ДО этого сообщения
        async for msg in channel.history(limit=500, before=message):
            msg_line = f"{msg.author.name}: {msg.content}\n"
            msg_tokens = len(encoding.encode(msg_line))

            if current_log_tokens + msg_tokens > settings.max_tokens - 1000:  # Запас на промпт
                break

            messages_to_process.append(msg_line)
            current_log_tokens += msg_tokens
            message_count += 1

        messages_to_process.reverse()
        # Собираем лог
        context = "".join(messages_to_process)

        # Сборка финального промпта: История + актуальное сообщение в самом конце
        final_prompt = f"--- ИСТОРИЯ ЧАТА ---\n{context}\n--- АКТУАЛЬНЫЙ ЗАПРОС ---\n{current_message_block}"

        # --- 4. ЗАПРОС К LLM ---

        try:
            messages: list[MessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt},
            ]

            # ИНСПЕКЦИОННЫЙ ЛЮК (DEBUG MODE)
            if settings.debug:
                log_channel_id = settings.discord_log_channel_id
                log_channel = bot.get_channel(log_channel_id)
                if is_messageable(log_channel):
                    # Собираем слепок того, что уйдёт в модель
                    debug_dump = f"# SYSTEM PROMPT\n{system_prompt}\n\n# FINAL PROMPT\n{final_prompt}"
                    # Конвертируем строку в байты, чтобы Дискорд схавал как файл
                    file_bytes = io.BytesIO(debug_dump.encode("utf-8"))
                    discord_file = discord.File(fp=file_bytes, filename="context_dump.md")

                    await log_channel.send("🛠 **[DEBUG]** Слепок контекста перед отправкой в LLM:", file=discord_file)

            # Принимаем унифицированный словарь от Gemini
            response_data = await bot.llm_client.create_completion(
                model=current_model,
                messages=messages,
                temperature=1.0,
            )

            # --- 5. ОБРАБОТКА ОТВЕТА ---

            p_tokens = response_data.get("prompt_tokens", 0)
            c_tokens = response_data.get("completion_tokens", 0)
            usage_info = f"Tokens: {p_tokens}+{c_tokens}"

            # Дебаговая информация улетает в консоль в чистом виде
            logger.debug("[%s | Msgs: %d | %s]", current_model, message_count, usage_info)

            full_response = response_data.get("content", "...")

            # --- 6. ДОСТАВКА ---

            if len(full_response) <= 2000:
                await message.reply(full_response)
            else:
                for i in range(0, len(full_response), 1900):
                    part = full_response[i : i + 1900]
                    if i == 0:
                        await message.reply(part)
                    else:
                        await channel.send(part)

        except Exception:
            # Снимаем полный слепок аварии
            error_tb = traceback.format_exc()

            # 1. Отправляем полный лог в админский канал (через твой DiscordHandler)
            logger.error(f"Критический сбой при обработке сообщения!\nПользователь: {message.author}\nОшибка:\n{error_tb}")

            # 2. Юзеру отдаем спокойную заглушку, чтоб не пугать кишками кода
            try:
                await message.reply("⚙️ **Система словила перегруз.** Датчики зафиксировали сбой, логи ушли инженеру. Попробуй ещё раз через пару минут.")
            except discord.errors.Forbidden:
                pass  # Если даже ответить не можем - просто глотаем


if __name__ == "__main__":
    # Чтение токена через безопасный метод SecretStr
    token = settings.discord_token.get_secret_value()
    bot.run(token)
