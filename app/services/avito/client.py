"""HTTP-клиент для работы с Avito API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

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


class AvitoAPIClient:
    """Клиент Avito API с обработкой авторизации и ошибок."""

    def __init__(self, auth_manager: AvitoAuthManager | None = None) -> None:
        self.auth_manager = auth_manager or AvitoAuthManager()
        self.base_url = settings.avito_api_base_url
        self.timeout = httpx.Timeout(30.0)
        self._max_attempts = 3

    async def send_message(self, chat_id: str, text: str) -> dict[str, Any]:
        """Отправляет текстовое сообщение в чат Avito.

        Args:
            chat_id: Идентификатор чата Avito.
            text: Текст сообщения.

        Returns:
            Ответ Avito API с данными отправленного сообщения.
        """
        payload = {
            "chat_id": chat_id,
            "message": {"type": "text", "text": text},
        }
        return await self._request("POST", "/messenger/v3/send", json=payload)

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
            return await self._request(
                "POST",
                "/messenger/v3/upload_image",
                files=files,
            )

    async def get_chats(self, limit: int = 50) -> list[dict[str, Any]]:
        """Возвращает список чатов Avito.

        Args:
            limit: Максимальное количество чатов в ответе.

        Returns:
            Список чатов Avito.
        """
        response = await self._request(
            "GET",
            "/messenger/v3/chats",
            params={"limit": limit},
        )
        return response.get("chats", [])

    async def get_chat_messages(self, chat_id: str) -> list[dict[str, Any]]:
        """Возвращает сообщения указанного чата.

        Args:
            chat_id: Идентификатор чата Avito.

        Returns:
            Список сообщений чата.
        """
        response = await self._request(
            "GET",
            f"/messenger/v3/chats/{chat_id}/messages",
        )
        return response.get("messages", [])

    async def get_items(self) -> list[dict[str, Any]]:
        """Возвращает список объявлений пользователя.

        Returns:
            Список объявлений.
        """
        response = await self._request("GET", "/core/v1/items")
        return response.get("items", [])

    async def get_item_stats(self, item_id: str) -> dict[str, Any]:
        """Получает статистику по объявлению.

        Args:
            item_id: Идентификатор объявления.

        Returns:
            Статистика просмотров и контактов.
        """
        return await self._request(
            "GET",
            f"/core/v1/items/{item_id}/stats",
        )

    async def _request(
        self,
        method: Literal["GET", "POST", "DELETE", "PATCH", "PUT"],
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
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
                return response.json()
            except ValueError as exc:
                logger.error("Некорректный JSON в ответе Avito: {}", exc)
                raise AvitoAPIError("Некорректный формат ответа Avito API.") from exc

        raise AvitoAPIError("Превышено число попыток запроса к Avito API.")
