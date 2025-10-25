"""OAuth 2.0 авторизация для amoCRM."""
import asyncio

import httpx
from loguru import logger

from app.core.cache import redis_client
from app.core.config import get_settings
from app.integrations.amocrm.models import AmoCRMTokens


class AmoCRMAuthManager:
    """Менеджер OAuth авторизации amoCRM."""

    REDIS_KEY = "amocrm:tokens"
    TOKEN_TTL = 86400  # 24 часа

    def __init__(self) -> None:
        self.settings = get_settings()
        self._lock = asyncio.Lock()
        self._base_url = f"https://{self.settings.amocrm_subdomain}.amocrm.ru"

    async def get_access_token(self) -> str:
        """Получает валидный access token (из кеша или обновляет)."""
        async with self._lock:
            # Пробуем получить из Redis
            cached = await self._get_cached_tokens()

            if cached and not cached.is_expired():
                logger.debug("Используем cached amoCRM токен")
                return cached.access_token

            # Токен истёк или отсутствует
            if cached and cached.refresh_token:
                logger.info("amoCRM токен истёк, обновляем через refresh_token")
                tokens = await self._refresh_tokens(cached.refresh_token)
            else:
                logger.warning("amoCRM токенов нет в кеше, требуется первичная авторизация")
                raise ValueError(
                    "Требуется первичная OAuth авторизация. "
                    f"Перейдите: {self._base_url}/oauth?client_id={self.settings.amocrm_client_id}&"
                    f"redirect_uri={self.settings.amocrm_redirect_uri}&response_type=code"
                )

            # Сохраняем в Redis
            await self._cache_tokens(tokens)

            return tokens.access_token

    async def exchange_code_for_tokens(self, code: str) -> AmoCRMTokens:
        """Обменивает authorization code на токены (первичная авторизация)."""
        logger.info("Обмен authorization code на токены")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/oauth2/access_token",
                json={
                    "client_id": self.settings.amocrm_client_id,
                    "client_secret": self.settings.amocrm_client_secret.get_secret_value(),
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.amocrm_redirect_uri,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        tokens = AmoCRMTokens(**data)
        await self._cache_tokens(tokens)

        logger.info("✅ amoCRM токены получены и сохранены")
        return tokens

    async def _refresh_tokens(self, refresh_token: str) -> AmoCRMTokens:
        """Обновляет токены через refresh_token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/oauth2/access_token",
                json={
                    "client_id": self.settings.amocrm_client_id,
                    "client_secret": self.settings.amocrm_client_secret.get_secret_value(),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "redirect_uri": self.settings.amocrm_redirect_uri,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info("✅ amoCRM токены обновлены")
        return AmoCRMTokens(**data)

    async def _get_cached_tokens(self) -> AmoCRMTokens | None:
        """Получает токены из Redis."""
        data = await redis_client.get(self.REDIS_KEY)
        if not data:
            return None

        import json

        tokens_dict = json.loads(data)
        return AmoCRMTokens(**tokens_dict)

    async def _cache_tokens(self, tokens: AmoCRMTokens) -> None:
        """Сохраняет токены в Redis."""
        import json

        await redis_client.setex(
            self.REDIS_KEY,
            self.TOKEN_TTL,
            json.dumps(tokens.model_dump(mode="json")),
        )
        logger.debug("amoCRM токены сохранены в Redis (TTL: %d сек)", self.TOKEN_TTL)


# Глобальный инстанс
auth_manager = AmoCRMAuthManager()
