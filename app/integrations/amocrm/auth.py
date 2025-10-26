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
        logger.info("🔄 Обмен authorization code на токены")
        logger.debug("Code (первые 30 символов): %s...", code[:30])

        token_url = f"{self._base_url}/oauth2/access_token"
        payload = {
            "client_id": self.settings.amocrm_client_id,
            "client_secret": self.settings.amocrm_client_secret.get_secret_value(),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.amocrm_redirect_uri,
        }

        logger.debug("Token URL: %s", token_url)
        logger.debug("Redirect URI: %s", self.settings.amocrm_redirect_uri)
        logger.debug("Client ID: %s", self.settings.amocrm_client_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    json=payload,
                    timeout=30.0,
                )

                logger.info("amoCRM token response status: %s", response.status_code)

                if response.status_code != 200:
                    logger.error("❌ Ошибка получения токенов: %s", response.status_code)
                    logger.error("Response body: %s", response.text[:500])
                    response.raise_for_status()

                data = response.json()
                logger.debug("Response data keys: %s", list(data.keys()))

            tokens = AmoCRMTokens(**data)
            logger.info("✅ Токены успешно распарсены")
            logger.debug("Access token длина: %s", len(tokens.access_token))
            logger.debug("Refresh token длина: %s", len(tokens.refresh_token) if tokens.refresh_token else 0)
            logger.debug("Expires in: %s секунд", tokens.expires_in)

            await self._cache_tokens(tokens)

            logger.info("✅ amoCRM токены получены и сохранены в Redis")
            return tokens

        except httpx.HTTPStatusError as exc:
            logger.error("❌ HTTP ошибка при обмене code на токены: %s", exc)
            logger.error("Response: %s", exc.response.text[:500])
            raise
        except Exception as exc:
            logger.error("❌ Неожиданная ошибка при обмене code на токены: %s", exc)
            logger.exception(exc)
            raise

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
