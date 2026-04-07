from typing import Literal, TypedDict

# Типы ролей для LLM
Role = Literal["system", "user", "assistant"]


class MessageParam(TypedDict):
    role: Role
    content: str
