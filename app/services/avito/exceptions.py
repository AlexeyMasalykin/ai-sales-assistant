"""Исключения для работы с Avito API."""

from __future__ import annotations


class AvitoAPIError(Exception):
    """Базовое исключение Avito API."""


class AvitoAuthError(AvitoAPIError):
    """Ошибка авторизации."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class AvitoRateLimitError(AvitoAPIError):
    """Превышен rate limit."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class AvitoAPITimeoutError(AvitoAPIError):
    """Таймаут запроса."""
