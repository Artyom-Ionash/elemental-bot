from typing import Any, TypeGuard

import discord


def is_messageable(obj: Any) -> TypeGuard[discord.abc.Messageable]:
    """
    Универсальный Type Guard для Discord.
    Если возвращает True, mypy гарантирует, что у объекта есть методы .send() и .history().
    Аналог `value is Type` из TypeScript.
    """
    return isinstance(obj, discord.abc.Messageable)
