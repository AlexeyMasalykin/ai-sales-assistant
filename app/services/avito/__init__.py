"""Пакет интеграции с Avito API."""

from .auth import AvitoAuthManager
from .client import AvitoAPIClient

__all__ = ["AvitoAuthManager", "AvitoAPIClient"]
