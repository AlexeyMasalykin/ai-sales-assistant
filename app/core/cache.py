"""Клиент Redis для кеша и сессий."""

from __future__ import annotations

import inspect
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from app.core.settings import settings


redis_client: Redis = Redis.from_url(
    settings.upstash_redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def verify_redis() -> None:
    """Проверяет доступность Redis."""
    try:
        ping_response: Any = redis_client.ping()
        if inspect.isawaitable(ping_response):
            ping_raw = await ping_response
        else:
            ping_raw = ping_response
        result = bool(ping_raw)
        if not result:
            raise RuntimeError("Redis ping вернул отрицательный результат.")
    except Exception as exc:
        logger.error("Redis недоступен: {}", exc)
        raise


async def close_redis() -> None:
    """Закрывает подключение к Redis."""
    try:
        await redis_client.close()
    except Exception as exc:
        logger.warning("Ошибка закрытия Redis: {}", exc)
