import os

import discord
import tiktoken
from aiohttp import web
from dotenv import load_dotenv

from core.discord.guards import is_messageable
from core.integrations.openrouter import OpenRouterClient
from core.types.llm import MessageParam

load_dotenv()

MAX_TOKENS = 10000

encoding = tiktoken.get_encoding("o200k_base")


class ElementalBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, activity=discord.CustomActivity(name="Исследование"))

        # Зависимость теперь ссылается на наш собственный адаптер, а не на чужой SDK
        self.llm_client: OpenRouterClient | None = None

    async def setup_hook(self) -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY не задан в окружении")

        self.llm_client = OpenRouterClient(api_key=api_key)

        # 2. Запуск вахтера (Web Server)
        self.loop.create_task(start_web_server())


bot = ElementalBot()


# --- 1. Асинхронный вахтер ---
async def health_check(request: web.Request) -> web.Response:
    # Инспектор от Hugging Face придет сюда
    return web.Response(text="Bot is alive.")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Строго 0.0.0.0 и порт 7860
    site = web.TCPSite(runner, "0.0.0.0", 7860)
    await site.start()
    print("Веб-сервер поднят в асинхронном контуре на 7860.")


@bot.event
async def on_ready() -> None:
    print(f"{bot.user} на связи. Жду приказов.")


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

    # [КРИСТАЛЛ ТИПИЗАЦИИ]: Применяем наш кастомный Type Guard.
    # Mypy теперь на 100% уверен, что channel имеет тип Messageable,
    # и больше не будет подчёркивать вызов `.history()` красным.
    if not is_messageable(channel):
        return

    # --- 2. ПОДГОТОВКА КОНТЕКСТА ---

    current_model = "openai/gpt-4o-mini"

    user_request = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not user_request:
        user_request = "Проанализируй переписку выше:"

    system_prompt = "Ты — суровый инженер. Обращайся ко мне на ты. Отвечай коротко и по делу, как мужик. Взвешивай плюсы и минусы."
    base_prompt_text = f"{user_request}\n\n--- КОНТЕКСТ ИЗ ЧАТА ---\n"

    base_tokens = len(encoding.encode(system_prompt + base_prompt_text))
    available_tokens_for_log = MAX_TOKENS - base_tokens

    messages_to_process: list[str] = []
    current_log_tokens = 0
    message_count = 0

    async with channel.typing():
        # --- 3. ИЗВЛЕЧЕНИЕ ИСТОРИИ ---

        # Ошибок типов больше нет.
        async for msg in channel.history(limit=500, before=message):
            msg_line = f"{msg.author.name}: {msg.content}\n"
            msg_tokens = len(encoding.encode(msg_line))

            if current_log_tokens + msg_tokens > available_tokens_for_log:
                break

            messages_to_process.append(msg_line)
            current_log_tokens += msg_tokens
            message_count += 1

        messages_to_process.reverse()
        context = "".join(messages_to_process)
        final_prompt = base_prompt_text + context

        # --- 4. ЗАПРОС К LLM ---

        try:
            # Вызываем наш чистый интерфейс
            messages: list[MessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt},
            ]

            response = await bot.llm_client.create_completion(
                model=current_model,
                messages=messages,
                temperature=0.3,
            )

            # --- 5. ОБРАБОТКА ОТВЕТА ---

            usage = response.usage
            usage_info = f"Tokens: {usage.prompt_tokens}+{usage.completion_tokens}" if usage else "N/A"

            debug_info = f"**[{current_model} | Msgs: {message_count} | {usage_info}]**"

            bot_answer = "..."
            if response.choices and response.choices[0].message.content:
                bot_answer = response.choices[0].message.content

            full_response = f"{debug_info}\n\n{bot_answer}"

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

        except Exception as e:
            await message.reply(f"**[Error]** Архитектурный сбой: {e}")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN не задан в окружении")
    bot.run(token)
