import tiktoken


class TokenCalculator:
    def __init__(self, encoding_name: str = "o200k_base") -> None:
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
