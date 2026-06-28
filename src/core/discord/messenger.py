import io
import logging
import traceback

import discord
import tiktoken

from config import settings
from core.discord.guards import is_messageable
from core.integrations.gemini import GeminiClient
from core.types.llm import MessageParam

logger = logging.getLogger(__name__)
encoding = tiktoken.get_encoding("o200k_base")


class Messenger:
    """
    Инкапсулирует жизненный цикл обработки сообщения:
    от извлечения истории до доставки ответа пользователю.
    """

    def __init__(self, bot: discord.Client, llm_client: GeminiClient) -> None:
        self.bot = bot
        self.llm_client = llm_client

    async def handle(self, message: discord.Message) -> None:
        # --- ПОДГОТОВКА КОНТЕКСТА ---
        current_model = settings.default_model
        assert self.bot.user is not None

        user_request = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
        current_message_block = f"{message.author.name}: {user_request}\n"

        if not user_request:
            user_request = "Проанализируй переписку выше:"

        system_prompt = settings.system_prompt
        messages_to_process: list[str] = []
        current_log_tokens = 0
        message_count = 0

        channel = message.channel
        async with channel.typing():
            # --- ИЗВЛЕЧЕНИЕ ИСТОРИИ ---
            async for msg in channel.history(limit=500, before=message):
                msg_line = f"{msg.author.name}: {msg.content}\n"
                msg_tokens = len(encoding.encode(msg_line))

                if current_log_tokens + msg_tokens > settings.max_tokens - 1000:
                    break

                messages_to_process.append(msg_line)
                current_log_tokens += msg_tokens
                message_count += 1

            messages_to_process.reverse()
            context = "".join(messages_to_process)
            final_prompt = f"--- ИСТОРИЯ ЧАТА ---\n{context}\n--- АКТУАЛЬНЫЙ ЗАПРОС ---\n{current_message_block}"

            # --- ЗАПРОС К LLM ---
            try:
                messages: list[MessageParam] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_prompt},
                ]

                # DEBUG MODE
                if settings.debug:
                    log_channel_id = settings.discord_log_channel_id
                    log_channel = self.bot.get_channel(log_channel_id)
                    if is_messageable(log_channel):
                        debug_dump = f"# SYSTEM PROMPT\n{system_prompt}\n# FINAL PROMPT\n{final_prompt}"
                        file_bytes = io.BytesIO(debug_dump.encode("utf-8"))
                        discord_file = discord.File(fp=file_bytes, filename="context_dump.md")
                        await log_channel.send("🛠 **[DEBUG]** Слепок контекста перед отправкой в LLM:", file=discord_file)

                response_data = await self.llm_client.create_completion(
                    model=current_model,
                    messages=messages,
                    temperature=1.0,
                )

                # --- ОБРАБОТКА ОТВЕТА ---
                p_tokens = response_data.get("prompt_tokens", 0)
                c_tokens = response_data.get("completion_tokens", 0)
                usage_info = f"Tokens: {p_tokens}+{c_tokens}"
                logger.debug("[%s | Msgs: %d | %s]", current_model, message_count, usage_info)

                full_response = response_data.get("content", "...")

                # --- ДОСТАВКА ---
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
                error_tb = traceback.format_exc()
                logger.error(f"Критический сбой при обработке сообщения!\nПользователь: {message.author}\nОшибка:\n{error_tb}")

                try:
                    await message.reply("⚙️ **Система словила перегруз.** Датчики зафиксировали сбой, логи ушли инженеру. Попробуй ещё раз через пару минут.")
                except discord.errors.Forbidden:
                    pass
