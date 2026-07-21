from typing import Any, TypeGuard

import discord


def is_messageable(obj: Any) -> TypeGuard[discord.abc.Messageable]:
    """
    Универсальный Type Guard для Discord.
    Проверяет, что объект существует (не None) и поддерживает отправку сообщений.

    Если возвращает True, статический анализатор гарантирует, что у объекта
    есть методы .send() и .history().
    """
    return isinstance(obj, discord.abc.Messageable)
