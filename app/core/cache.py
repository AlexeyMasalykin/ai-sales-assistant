"""Клиент Redis для кеша и сессий."""

from __future__ import annotations

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
        await redis_client.ping()
    except Exception as exc:
        logger.error("Redis недоступен: {}", exc)
        raise


async def close_redis() -> None:
    """Закрывает подключение к Redis."""
    try:
        await redis_client.aclose()
    except Exception as exc:
        logger.warning("Ошибка закрытия Redis: {}", exc)
