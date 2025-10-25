"""HTTP клиент для amoCRM API."""
import asyncio
from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings
from app.integrations.amocrm.auth import auth_manager
from app.integrations.amocrm.models import (
    AmoCRMContact,
    AmoCRMLead,
    AmoCRMNote,
)


class AmoCRMAPIError(Exception):
    """Базовая ошибка amoCRM API."""

    pass


class AmoCRMRateLimitError(AmoCRMAPIError):
    """Ошибка превышения лимита запросов."""

    pass


class AmoCRMClient:
    """Клиент для работы с amoCRM API."""

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # секунды

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = f"https://{self.settings.amocrm_subdomain}.amocrm.ru/api/v4"

    async def create_lead(
        self,
        name: str,
        price: int | None = None,
        contact_id: int | None = None,
        pipeline_id: int | None = None,
        responsible_user_id: int | None = None,
        custom_fields: list[dict] | None = None,
    ) -> int:
        """Создаёт лид в amoCRM."""
        logger.info("Создание лида '%s' (цена: %s)", name, price)

        payload = {
            "name": name,
        }

        if price is not None:
            payload["price"] = price

        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id

        if responsible_user_id is not None:
            payload["responsible_user_id"] = responsible_user_id

        if custom_fields:
            payload["custom_fields_values"] = custom_fields

        if contact_id:
            payload["_embedded"] = {"contacts": [{"id": contact_id}]}
            
        import json
        logger.info(f"=== PAYLOAD ДЛЯ AMOCRM ===")
        logger.info(f"Full payload: {json.dumps([payload], indent=2, ensure_ascii=False)}")
        logger.info(f"custom_fields_values: {payload.get('custom_fields_values')}")
        logger.info(f"=========================")

        response = await self._request("POST", "/leads", json=[payload])

        lead_id = response["_embedded"]["leads"][0]["id"]
        logger.info("✅ Лид создан: ID=%d", lead_id)

        return lead_id

    async def create_contact(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        custom_fields: list[dict] | None = None,
    ) -> int:
        """Создаёт контакт в amoCRM."""
        logger.info("Создание контакта '%s'", name)

        payload = {
            "name": name,
        }

        custom_fields_values = custom_fields or []

        if phone:
            custom_fields_values.append(
                {
                    "field_code": "PHONE",
                    "values": [{"value": phone}],  # Убрали enum_code
                }
            )

        if email:
            custom_fields_values.append(
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email}],  # Убрали enum_code
                }
            )

        if custom_fields_values:
            payload["custom_fields_values"] = custom_fields_values

        response = await self._request("POST", "/contacts", json=[payload])

        contact_id = response["_embedded"]["contacts"][0]["id"]
        logger.info("✅ Контакт создан: ID=%d", contact_id)

        return contact_id

    async def add_note(
        self,
        entity_id: int,
        entity_type: str,
        text: str,
    ) -> int:
        """Добавляет примечание к сущности."""
        logger.debug("Добавление примечания к %s ID=%d", entity_type, entity_id)

        payload = {
            "entity_id": entity_id,
            "note_type": "common",
            "params": {"text": text},
        }

        response = await self._request(
            "POST",
            f"/{entity_type}/{entity_id}/notes",
            json=[payload],
        )

        note_id = response["_embedded"]["notes"][0]["id"]
        logger.debug("✅ Примечание добавлено: ID=%d", note_id)

        return note_id

    async def get_lead(self, lead_id: int) -> dict:
        """Получает лид по ID."""
        logger.debug("Получение лида ID=%d", lead_id)
        return await self._request("GET", f"/leads/{lead_id}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Any | None = None,
        params: dict | None = None,
        retry: int = 0,
    ) -> dict:
        """Выполняет HTTP запрос с обработкой ошибок и retry."""
        token = await auth_manager.get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                    timeout=30.0,
                )

            # 401 - токен истёк, пробуем обновить
            if response.status_code == 401 and retry < 1:
                logger.warning("amoCRM 401: токен истёк, пробуем обновить")
                # Инвалидируем кеш токенов
                from app.core.cache import redis_client

                await redis_client.delete("amocrm:tokens")
                return await self._request(method, endpoint, json, params, retry + 1)

            # 429 - rate limit
            if response.status_code == 429:
                if retry < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY * (2**retry)  # exponential backoff
                    logger.warning(
                        "amoCRM rate limit, ждём %.1f сек (попытка %d/%d)",
                        delay,
                        retry + 1,
                        self.MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    return await self._request(method, endpoint, json, params, retry + 1)
                else:
                    raise AmoCRMRateLimitError("Превышен лимит запросов к amoCRM")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as exc:
            logger.error("amoCRM API ошибка %d: %s", exc.response.status_code, exc.response.text)
            raise AmoCRMAPIError(f"HTTP {exc.response.status_code}: {exc.response.text}")

        except httpx.RequestError as exc:
            logger.error("amoCRM запрос провалился: %s", str(exc))
            if retry < self.MAX_RETRIES:
                delay = self.RETRY_DELAY * (2**retry)
                logger.info("Повтор через %.1f сек", delay)
                await asyncio.sleep(delay)
                return await self._request(method, endpoint, json, params, retry + 1)
            raise AmoCRMAPIError(f"Request error: {str(exc)}")


# Глобальный инстанс
amocrm_client = AmoCRMClient()
