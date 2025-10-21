"""Middleware для ограничения частоты запросов."""

from __future__ import annotations

from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Ограничивает количество запросов в заданное окно времени."""

    def __init__(
        self,
        app,
        *,
        limit: int,
        window_seconds: int,
        exempt_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self.exempt_paths = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next):
        """Применяет проверку лимита перед выполнением запроса."""
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        redis_key = f"rate:{client_ip}"
        try:
            current = await redis_client.incr(redis_key)
            if current == 1:
                await redis_client.expire(redis_key, self.window_seconds)
        except Exception as exc:
            logger.warning("Сбой rate limiting, пропуск: {}", exc)
            return await call_next(request)

        if current > self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Превышен лимит запросов."},
            )

        return await call_next(request)
