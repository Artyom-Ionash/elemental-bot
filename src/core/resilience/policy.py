import logging

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Политика повторных попыток для LLM-провайдеров.

    Определяет максимальное число попыток, базовую задержку и условия,
    при которых ошибку следует считать временной (ретраибельной).
    """

    def __init__(self, max_retries: int = 4, base_delay: float = 2.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay

    def is_retriable(self, exception: BaseException) -> bool:
        """Проверяет, является ли исключение временным сетевым или серверным сбоем."""
        error_str = str(exception)

        status_code = getattr(exception, "status_code", None) or getattr(exception, "code", None)
        if status_code in (503, 502, 504, 429):
            return True

        retriable_keywords = [
            "503",
            "502",
            "504",
            "429",
            "Server disconnected",
            "TimeoutError",
            "ClientConnectorError",
            "APITimeoutError",
            "APIConnectionError",
            "Timeout",
            "Connection reset",
        ]
        return any(keyword in error_str for keyword in retriable_keywords)
