from typing import Literal, TypedDict

# Типы ролей для LLM
Role = Literal["system", "user", "assistant"]


class MessageParam(TypedDict):
    role: Role
    content: str


class CompletionResult(TypedDict):
    content: str
    thoughts: str
    prompt_tokens: int
    completion_tokens: int
