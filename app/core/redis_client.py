"""Асинхронный помощник для доступа к Redis клиенту."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.cache import get_redis_client as _sync_get_redis_client


async def get_redis_client() -> Redis:
    """Возвращает Redis клиент (совместимо с async/await)."""
    return _sync_get_redis_client()
