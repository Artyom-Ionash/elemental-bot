import discord

from config import settings
from lib.token_calculator import TokenCalculator


class ContextBuilder:
    def __init__(self, token_calculator: TokenCalculator, max_tokens: int | None = None) -> None:
        self.token_calculator = token_calculator
        self._max_tokens = max_tokens

    @property
    def max_tokens(self) -> int:
        return settings.max_tokens if self._max_tokens is None else self._max_tokens

    async def build_context(self, channel: discord.abc.Messageable, before_message: discord.Message, limit: int = 500) -> tuple[str, int]:
        messages_to_process: list[str] = []
        current_log_tokens = 0
        message_count = 0

        async for msg in channel.history(limit=limit, before=before_message):
            msg_line = f"{msg.author.name}: {msg.content}\n"
            msg_tokens = self.token_calculator.count_tokens(msg_line)

            if current_log_tokens + msg_tokens > self.max_tokens - 1000:
                break

            messages_to_process.append(msg_line)
            current_log_tokens += msg_tokens
            message_count += 1

        messages_to_process.reverse()
        context = "".join(messages_to_process)
        return context, message_count
