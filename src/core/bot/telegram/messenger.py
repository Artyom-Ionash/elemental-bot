import asyncio
import logging
from collections import defaultdict
from typing import Any

from telegram import Update
from telegram.ext import CallbackContext

from config import settings
from core.integrations.base_provider import BaseLLMProvider
from lib.token_calculator import TokenCalculator

logger = logging.getLogger(__name__)
from lib.ticket_router import TicketRouter


class TelegramMessenger:
    """
    Обработчик сообщений для Telegram.
    Ведёт локальную историю чатов, строит контекст с ограничением по токенам,
    отправляет запрос в LLM и возвращает ответ.
    """

    def __init__(
        self,
        llm_client: BaseLLMProvider,
        token_calculator: TokenCalculator,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.token_calculator = token_calculator
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt

        # Храним историю для каждого чата: chat_id -> list of messages
        # Каждое сообщение: {"author": str, "content": str, "timestamp": float}
        self.history: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self.router = TicketRouter()

        # Лимит на количество хранимых сообщений (для предотвращения переполнения)
        self.max_history_size = 200

    @property
    def max_tokens(self) -> int:
        return settings.max_tokens if self._max_tokens is None else self._max_tokens

    @property
    def system_prompt(self) -> str:
        return settings.system_prompt if self._system_prompt is None else self._system_prompt

    async def handle(self, update: Update, context: CallbackContext) -> None:
        if not update.message or not update.message.text:
            return

        user_request = update.message.text.strip()
        chat_id = update.message.chat_id
        user_name = update.message.from_user.username or "Caller"

        # --- ФАЗА 1: FAST PATH (Маршрутизация без LLM) ---
        route_result = self.router.route(user_request)  # Предполагается, что self.router = TicketRouter() в __init__

        if route_result["action"] == "dispatch_police":
            await update.message.reply_text("🚨 **[СИСТЕМА: ВЫЗОВ ПЕРЕДАН В ПОЛИЦИЮ]**\nНаряд выехал. Оставайтесь в безопасном месте.")
            return
        elif route_result["action"] == "dispatch_ambulance":
            await update.message.reply_text("🚑 **[СИСТЕМА: ВЫЗОВ ПЕРЕДАН В СКОРУЮ ПОМОЩЬ]**\nБригада в пути. Не перемещайте пострадавшего, если нет прямой угрозы.")
            return
        elif route_result["action"] == "dispatch_fire":
            await update.message.reply_text("🔥 **[СИСТЕМА: ВЫЗОВ ПЕРЕДАН В МЧС/ПОЖАРНУЮ]**\nРасчет выехал. Срочно покиньте помещение, не используйте лифт.")
            return
        elif route_result["action"] == "auto_reply":
            await update.message.reply_text(f"ℹ️ **[СИСТЕМА: АВТОМАТИЧЕСКИЙ ОТВЕТ]**\n{route_result['reply_text']}")
            return

        # --- ФАЗА 2: SLOW PATH (LLM Triage / Выяснение обстоятельств) ---
        # Сюда доходим, только если action == "llm_triage"

        # Строим контекст из истории чата (ваш существующий метод)
        self._add_message(chat_id, user_name, user_request)
        context_text, msg_count = self._build_context(chat_id)

        final_prompt = f"--- ИСТОРИЯ ЧАТА ---\n{context_text}\n--- АКТУАЛЬНЫЙ ОТВЕТ АБОНЕНТА ---\n{user_name}: {user_request}"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": final_prompt},
        ]

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

            response_data = await self.llm_client.create_completion(messages=messages, temperature=0.3)
            full_response = response_data.get("content", "...")

            # Обратите внимание: тут мы НЕ добавляем заголовки.
            # Выводим чистый текст диспетчера, как просили.
            await update.message.reply_text(full_response)

            self._add_message(chat_id, "Dispatcher", full_response)

        except Exception:
            # Fallback на случай падения LLM или таймаута
            await update.message.reply_text("⚠️ **[СИСТЕМА: СБОЙ СВЯЗИ]**\nВаш запрос переведен на ручного диспетчера. Ожидайте ответа.")

    def _add_message(self, chat_id: int, author: str, content: str) -> None:
        """Добавляет сообщение в историю чата, обрезая при превышении лимита."""
        hist = self.history[chat_id]
        hist.append({"author": author, "content": content, "timestamp": asyncio.get_event_loop().time()})
        if len(hist) > self.max_history_size:
            hist.pop(0)

    def _build_context(self, chat_id: int) -> tuple[str, int]:
        """
        Строит текстовый контекст из истории, обрезая по токенам.
        Возвращает (контекст_строка, количество_сообщений).
        """
        hist = self.history.get(chat_id, [])
        # Идём с конца (новые сообщения важнее)
        messages_to_use = []
        current_tokens = 0
        count = 0

        # Резервируем место под системный промпт и запрос (примерно 1000 токенов)
        token_budget = self.max_tokens - 1000
        if token_budget <= 0:
            return "", 0

        for msg in reversed(hist):
            line = f"{msg['author']}: {msg['content']}\n"
            tokens = self.token_calculator.count_tokens(line)
            if current_tokens + tokens > token_budget:
                break
            messages_to_use.append(line)
            current_tokens += tokens
            count += 1

        # Возвращаем в хронологическом порядке
        messages_to_use.reverse()
        return "".join(messages_to_use), count
