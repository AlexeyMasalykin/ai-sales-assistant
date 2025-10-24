"""HTTP-клиент для работы с Avito API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Literal, Union, cast

import httpx
from loguru import logger

from app.core.settings import settings
from app.services.avito.auth import AvitoAuthManager
from app.services.avito.exceptions import (
    AvitoAPIError,
    AvitoAPITimeoutError,
    AvitoAuthError,
    AvitoRateLimitError,
)

JSONDict = Dict[str, Any]
JSONList = List[Any]
JSONResponse = Union[JSONDict, JSONList]


class AvitoAPIClient:
    """Клиент Avito API с обработкой авторизации и ошибок."""

    def __init__(self, auth_manager: AvitoAuthManager | None = None) -> None:
        self.auth_manager = auth_manager or AvitoAuthManager()
        self.base_url = settings.avito_api_base_url
        self.timeout = httpx.Timeout(30.0)
        self._max_attempts = 3

    async def send_message(
        self, chat_id: str, text: str, user_id: str | None = None
    ) -> dict[str, Any]:
        """Отправляет текстовое сообщение в чат Avito.

        Args:
            chat_id: Идентификатор чата Avito.
            text: Текст сообщения (максимум 1000 символов).
            user_id: ID пользователя. Если не указан, берется из settings.

        Returns:
            Ответ Avito API с данными отправленного сообщения.
        """
        from app.core.settings import settings

        uid = user_id or settings.avito_user_id
        payload = {
            "type": "text",
            "message": {"text": text},
        }
        endpoint = f"/messenger/v1/accounts/{uid}/chats/{chat_id}/messages"
        response = await self._request("POST", endpoint, json=payload)
        return self._ensure_dict(response)

    async def upload_image(self, file_path: str) -> dict[str, Any]:
        """Загружает изображение в Avito Messenger.

        Args:
            file_path: Путь к файлу изображения.

        Returns:
            Данные об успешно загруженном файле.
        """
        path = Path(file_path)
        if not path.is_file():
            raise AvitoAPIError(f"Файл не найден: {file_path}")
        with path.open("rb") as file_obj:
            files = {"file": (path.name, file_obj, "image/jpeg")}
            response = await self._request(
                "POST",
                "/messenger/v3/upload_image",
                files=files,
            )
        return self._ensure_dict(response)

    async def get_chats(
        self, limit: int = 50, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Возвращает список чатов Avito.

        Args:
            limit: Максимальное количество чатов в ответе (max 100).
            user_id: ID пользователя. Если не указан, берется из settings.

        Returns:
            Список чатов Avito.
        """
        from app.core.settings import settings

        uid = user_id or settings.avito_user_id
        endpoint = f"/messenger/v2/accounts/{uid}/chats"
        response = await self._request(
            "GET",
            endpoint,
            params={"limit": min(limit, 100)},
        )
        return self._extract_dict_list(response, "chats")

    async def get_chat_messages(
        self, chat_id: str, limit: int = 100, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Возвращает сообщения указанного чата.

        Args:
            chat_id: Идентификатор чата Avito.
            limit: Максимальное количество сообщений (max 100).
            user_id: ID пользователя. Если не указан, берется из settings.

        Returns:
            Список сообщений чата.
        """
        from app.core.settings import settings

        uid = user_id or settings.avito_user_id
        endpoint = f"/messenger/v3/accounts/{uid}/chats/{chat_id}/messages/"
        response = await self._request(
            "GET",
            endpoint,
            params={"limit": min(limit, 100)},
        )
        return self._extract_dict_list(response, "messages")

    async def get_items(self) -> list[dict[str, Any]]:
        """Возвращает список объявлений пользователя.

        Returns:
            Список объявлений.
        """
        response = await self._request("GET", "/core/v1/items")
        payload = self._ensure_dict(response)
        items_raw = payload.get("items", [])
        if not isinstance(items_raw, list):
            return []
        return [item for item in items_raw if isinstance(item, dict)]

    async def get_item_stats(self, item_id: str) -> dict[str, Any]:
        """Получает статистику по объявлению.

        Args:
            item_id: Идентификатор объявления.

        Returns:
            Статистика просмотров и контактов.
        """
        response = await self._request(
            "GET",
            f"/core/v1/items/{item_id}/stats",
        )
        return self._ensure_dict(response)

    async def register_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Регистрирует webhook URL в Avito Messenger (v3).

        Args:
            webhook_url: Публичный HTTPS URL для приёма событий.

        Returns:
            Ответ Avito API о регистрации.
        """
        payload = {"url": webhook_url}
        response = await self._request(
            "POST",
            "/messenger/v3/webhook",
            json=payload,
        )
        return self._ensure_dict(response)

    async def get_webhook_status(self) -> dict[str, Any]:
        """Возвращает информацию о текущих подписках webhook (v1)."""
        response = await self._request(
            "POST",
            "/messenger/v1/subscriptions",
        )
        return self._ensure_dict(response)

    async def unregister_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Удаляет текущую подписку webhook (v1).

        Args:
            webhook_url: URL для отписки.
        """
        payload = {"url": webhook_url}
        response = await self._request(
            "POST",
            "/messenger/v1/webhook/unsubscribe",
            json=payload,
        )
        return self._ensure_dict(response)

    async def _request(
        self,
        method: Literal["GET", "POST", "DELETE", "PATCH", "PUT"],
        endpoint: str,
        **kwargs: Any,
    ) -> JSONResponse:
        """Выполняет HTTP-запрос к Avito с повторными попытками.

        Args:
            method: HTTP-метод запроса.
            endpoint: Путь относительно базового URL Avito.
            **kwargs: Дополнительные аргументы httpx.

        Returns:
            Ответ Avito API, преобразованный в словарь.

        Raises:
            AvitoAPIError: При ошибках Avito API или исчерпании попыток.
        """
        for attempt in range(self._max_attempts):
            token = await self.auth_manager.get_access_token()
            headers = kwargs.pop("headers", {})
            headers.setdefault("Authorization", f"Bearer {token}")
            headers.setdefault("Accept", "application/json")

            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                ) as client:
                    response = await client.request(
                        method,
                        endpoint,
                        headers=headers,
                        **kwargs,
                    )
            except httpx.TimeoutException as exc:
                logger.warning("Таймаут запроса Avito: {}", exc)
                if attempt == self._max_attempts - 1:
                    raise AvitoAPITimeoutError(
                        "Превышено время ожидания ответа Avito.",
                    ) from exc
                await asyncio.sleep(2**attempt)
                continue
            except httpx.RequestError as exc:
                logger.error("Сетевая ошибка Avito: {}", exc)
                raise AvitoAPIError("Сетевая ошибка при обращении к Avito.") from exc

            if response.status_code == 401:
                logger.warning(
                    "Получен статус 401 от Avito, обновление токена.",
                )
                await self.auth_manager.invalidate_token()
                if attempt == self._max_attempts - 1:
                    raise AvitoAuthError("Авторизация Avito отклонена.", 401)
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = max(1, 2**attempt)
                if retry_after and retry_after.isdigit():
                    wait_time = max(wait_time, int(retry_after))
                logger.warning(
                    "Достигнут rate limit Avito, повтор через {} секунд.",
                    wait_time,
                )
                if attempt == self._max_attempts - 1:
                    raise AvitoRateLimitError(wait_time)
                await asyncio.sleep(wait_time)
                continue

            if response.status_code >= 400:
                logger.error(
                    "Ошибка Avito API {}: {}",
                    response.status_code,
                    response.text,
                )
                raise AvitoAPIError(
                    f"Avito API вернул код {response.status_code}.",
                )

            logger.debug(
                "Успешный запрос Avito {} {} (статус {}).",
                method,
                endpoint,
                response.status_code,
            )
            if not response.content:
                return {}
            try:
                return cast(JSONResponse, response.json())
            except ValueError as exc:
                logger.error("Некорректный JSON в ответе Avito: {}", exc)
                raise AvitoAPIError("Некорректный формат ответа Avito API.") from exc

        raise AvitoAPIError("Превышено число попыток запроса к Avito API.")

    @staticmethod
    def _ensure_dict(data: JSONResponse) -> JSONDict:
        if isinstance(data, dict):
            return data
        raise AvitoAPIError("Avito API вернул неожиданный формат ответа.")

    @staticmethod
    def _extract_dict_list(
        data: JSONResponse,
        key: str | None = None,
    ) -> List[JSONDict]:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and key:
            raw_value = data.get(key, [])
            items = raw_value if isinstance(raw_value, list) else []
        else:
            items = []

        return [item for item in items if isinstance(item, dict)]
