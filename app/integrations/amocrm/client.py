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
        status_id: int | None = None,
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

        if status_id is not None:
            payload["status_id"] = status_id

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

    async def update_lead_status(
        self,
        lead_id: int,
        status_id: int,
        pipeline_id: int | None = None,
    ) -> bool:
        """
        Обновляет статус лида в amoCRM.

        Args:
            lead_id: ID лида
            status_id: Новый статус
            pipeline_id: ID воронки (опционально)
        """
        logger.info("Обновление статуса лида %s → status_id=%s", lead_id, status_id)

        payload = {
            "id": lead_id,
            "status_id": status_id,
        }

        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id

        try:
            response = await self._request("PATCH", "/leads", json=[payload])

            if response and "_embedded" in response:
                logger.info("✅ Статус лида %s обновлён → %s", lead_id, status_id)
                return True

            logger.error("Неожиданный ответ при обновлении лида: %s", response)
            return False

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка обновления статуса лида %s: %s", lead_id, exc)
            return False

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
        entity_type: str = "leads",
        note_type: str = "common",
        text: str = "",
    ) -> bool:
        """
        Добавляет примечание к сущности.

        Args:
            entity_id: ID лида/контакта
            entity_type: "leads" или "contacts"
            note_type: тип заметки (обычно "common")
            text: текст заметки
        """
        logger.info("Добавление заметки к %s/%s", entity_type, entity_id)

        payload = {
            "entity_id": entity_id,
            "note_type": note_type,
            "params": {"text": text},
        }

        try:
            response = await self._request(
                "POST",
                f"/{entity_type}/notes",
                json=[payload],
            )
            if response and "_embedded" in response:
                logger.info("✅ Заметка добавлена к %s/%s", entity_type, entity_id)
                return True

            logger.error("Неожиданный ответ при добавлении заметки: %s", response)
            return False

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка добавления заметки: %s", exc)
            return False

    async def get_lead(self, lead_id: int) -> dict:
        """Получает лид по ID."""
        logger.debug("Получение лида ID=%d", lead_id)
        return await self._request("GET", f"/leads/{lead_id}")

    async def find_contact_by_phone(self, phone: str) -> int | None:
        """
        Ищет контакт по номеру телефона через поле custom_fields_values.

        Args:
            phone: Номер телефона (например: telegram_user_477811332)

        Returns:
            ID контакта или None
        """
        try:
            logger.info(f"Поиск контакта по телефону: {phone}")

            response = await self._request(
                "GET",
                "/contacts",
                params={"query": phone, "limit": 10},
            )

            # После получения response
            logger.debug(f"API ответ: {response}")

            contacts = response.get("_embedded", {}).get("contacts") if response else None

            # Добавь
            logger.info(f"📊 Получено контактов от API: {len(contacts) if contacts else 0}")

            if contacts:
                for contact in contacts:
                    custom_fields = contact.get("custom_fields_values", [])

                    for field in custom_fields:
                        if field.get("field_code") == "PHONE":
                            values = field.get("values", [])

                            for value in values:
                                if phone in value.get("value", ""):
                                    contact_id = contact["id"]
                                    logger.info(f"✅ Контакт найден: contact_id={contact_id}")
                                    return contact_id

            logger.info(f"Контакт с телефоном {phone} не найден")
            return None

        except Exception as exc:
            logger.error(f"Ошибка поиска контакта: {exc}")
            return None

    async def get_contact_from_lead(self, lead_id: int) -> int | None:
        """
        Получает ID контакта из лида.

        Args:
            lead_id: ID лида

        Returns:
            ID контакта или None
        """
        try:
            lead = await self.get_lead(lead_id)

            if lead and "_embedded" in lead and "contacts" in lead["_embedded"]:
                contacts = lead["_embedded"]["contacts"]
                if contacts:
                    contact_id = contacts[0]["id"]
                    logger.info(f"✅ Контакт {contact_id} получен из лида {lead_id}")
                    return contact_id

            logger.warning(f"Контакт не найден в лиде {lead_id}")
            return None

        except Exception as exc:
            logger.error(f"Ошибка получения контакта из лида: {exc}")
            return None

    async def find_leads_by_contact(
        self,
        contact_id: int,
        pipeline_id: int | None = None,
    ) -> list[dict]:
        """
        Находит активные лиды, привязанные к контакту.

        Args:
            contact_id: ID контакта
            pipeline_id: Фильтр по воронке (опционально)
        """
        try:
            logger.info("Поиск лидов для контакта: %s", contact_id)

            params: dict[str, int] | dict[str, int | None] = {"filter[contacts]": contact_id}
            if pipeline_id:
                params["filter[pipeline_id]"] = pipeline_id

            response = await self._request("GET", "/leads", params=params)

            leads = response.get("_embedded", {}).get("leads") if response else None
            if leads:
                active_leads = [
                    {
                        "id": lead["id"],
                        "status_id": lead["status_id"],
                        "pipeline_id": lead["pipeline_id"],
                        "name": lead.get("name", ""),
                    }
                    for lead in leads
                    if lead.get("status_id") not in [142, 143]
                ]
                logger.info("✅ Найдено %s активных лидов", len(active_leads))
                return active_leads

            logger.info("Лиды для контакта %s не найдены", contact_id)
            return []

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка поиска лидов: %s", exc)
            return []

    async def get_lead_notes(
        self,
        lead_id: int,
        limit: int = 20,
    ) -> list[dict]:
        """
        Получает заметки лида.

        Args:
            lead_id: ID лида
            limit: максимальное число заметок
        """
        try:
            logger.info("Загрузка заметок для лида %s", lead_id)

            response = await self._request(
                "GET",
                f"/leads/{lead_id}/notes",
                params={"limit": limit},
            )

            notes = response.get("_embedded", {}).get("notes") if response else None
            if not notes:
                logger.info("Заметки для лида %s не найдены", lead_id)
                return []

            result: list[dict] = []
            for note in notes:
                if note.get("note_type") == "common":
                    result.append(
                        {
                            "id": note.get("id"),
                            "text": note.get("params", {}).get("text", ""),
                            "created_at": note.get("created_at", 0),
                        }
                    )

            logger.info("✅ Загружено %s заметок для лида %s", len(result), lead_id)
            return result

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка загрузки заметок: %s", exc)
            return []

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


async def get_amocrm_client() -> AmoCRMClient:
    """Возвращает глобальный инстанс amoCRM клиента."""
    return amocrm_client
