"""Модуль авторизации для работы с Avito API."""

from __future__ import annotations

import asyncio
import httpx
from loguru import logger
from typing import Any, Dict, cast

from app.core.cache import get_redis_client
from app.core.settings import settings
from app.services.avito.exceptions import AvitoAPITimeoutError, AvitoAuthError


class AvitoAuthManager:
    """Управляет получением и кэшированием access token Avito."""

    def __init__(self) -> None:
        self.cache_key = "avito:access_token"
        self._client_id = settings.avito_client_id
        self._client_secret = settings.avito_client_secret.get_secret_value()
        self.token_url = f"{settings.avito_api_base_url}/token"
        self.token_ttl = settings.avito_token_ttl
        self.refresh_before = settings.avito_token_refresh_before
        self._lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        """Возвращает валидный access token.

        Returns:
            Строка с access token Avito.
        """
        async with self._lock:
            cached = await self._get_cached_token()
            if cached:
                return cached
            return await self._request_new_token()

    async def invalidate_token(self) -> None:
        """Удаляет кэшированный токен.

        Returns:
            None.
        """
        await get_redis_client().delete(self.cache_key)
        logger.debug("Access token Avito удалён из кэша.")

    async def _get_cached_token(self) -> str | None:
        """Возвращает токен из Redis, если он ещё валиден.

        Returns:
            Строка токена или None, если требуется обновление.
        """
        token: str | None = await get_redis_client().get(self.cache_key)
        if not token:
            return None

        ttl = await get_redis_client().ttl(self.cache_key)
        if ttl == -2:
            return None
        if ttl != -1 and ttl < self.refresh_before:
            logger.debug(
                "Токен Avito истекает через {} секунд, требуется обновление.",
                ttl,
            )
            return None
        logger.debug(
            "Используется токен Avito из кэша (TTL: {} секунд).",
            ttl,
        )
        return token

    async def _request_new_token(self) -> str:
        """Запрашивает новый токен у Avito API.

        Returns:
            Строка с новым access token.
        """
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        logger.info("Запрос нового access token Avito.")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
        except httpx.TimeoutException as exc:
            logger.error("Таймаут запроса токена Avito: {}", exc)
            raise AvitoAPITimeoutError(
                "Истекло время ожидания ответа от Avito."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Сетевая ошибка при запросе токена Avito: {}", exc)
            raise AvitoAuthError("Ошибка сети при запросе токена Avito.") from exc

        if response.status_code in (401, 403):
            logger.error(
                "Ошибка авторизации Avito: статус {}, тело {}",
                response.status_code,
                response.text,
            )
            raise AvitoAuthError(
                "Не удалось авторизоваться в Avito API.",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            logger.error(
                "Неожиданная ошибка Avito при получении токена: {} - {}",
                response.status_code,
                response.text,
            )
            raise AvitoAuthError(
                "Сервис Avito вернул ошибку при запросе токена.",
                status_code=response.status_code,
            )

        try:
            data = cast(Dict[str, Any], response.json())
        except ValueError as exc:
            logger.error("Неверный JSON в ответе Avito при получении токена: {}", exc)
            raise AvitoAuthError("Avito вернул некорректный JSON.") from exc
        token_raw = data.get("access_token")
        if not isinstance(token_raw, str) or not token_raw:
            logger.error("Ответ Avito не содержит access_token: {}", data)
            raise AvitoAuthError("Отсутствует access_token в ответе Avito.")

        token = token_raw
        try:
            expires_in = int(data.get("expires_in", self.token_ttl))
        except (TypeError, ValueError):
            expires_in = self.token_ttl

        await self._cache_token(token, expires_in)
        logger.debug(
            "Новый токен Avito успешно получен (TTL: {} секунд).",
            expires_in,
        )
        return token

    async def _cache_token(self, token: str, expires_in: int) -> None:
        """Сохраняет токен в Redis с ограничением по времени.

        Args:
            token: Значение access token.
            expires_in: Срок действия токена в секундах.
        """
        ttl = max(1, min(expires_in, self.token_ttl))
        await get_redis_client().set(self.cache_key, token, ex=ttl)
        logger.debug("Токен Avito сохранён в Redis с TTL {} секунд.", ttl)
