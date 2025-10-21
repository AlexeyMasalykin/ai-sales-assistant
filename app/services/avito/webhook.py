"""Обработчики webhook-событий Avito."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.services.avito.client import AvitoAPIClient


WEBHOOK_QUEUE: asyncio.Queue[dict[str, Any]] = asyncio.Queue()


class AvitoWebhookHandler:
    """Управляет приёмом и обработкой событий Avito webhook."""

    def __init__(self, client: AvitoAPIClient | None = None) -> None:
        self.client = client or AvitoAPIClient()

    async def validate_signature(
        self,
        payload: dict[str, Any],
        signature: str | None,
    ) -> bool:
        """Проверяет подпись webhook.

        Args:
            payload: Данные события в виде словаря.
            signature: Подпись запроса от Avito.

        Returns:
            Всегда True (заглушка до интеграции фактической проверки).
        """
        # TODO: реализовать проверку подписи после уточнения схемы Avito.
        if signature is None:
            logger.debug("Подпись webhook не предоставлена Avito.")
        return True

    async def process_message(self, webhook_data: dict[str, Any]) -> None:
        """Помещает входящее сообщение в очередь на дальнейшую обработку.

        Args:
            webhook_data: Данные события Avito.
        """
        await WEBHOOK_QUEUE.put(webhook_data)
        logger.info(
            "Входящее событие Avito добавлено в очередь, текущий размер: {}.",
            WEBHOOK_QUEUE.qsize(),
        )

    async def register_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Регистрирует webhook URL в Avito.

        Args:
            webhook_url: Публичный адрес приёма сообщений.

        Returns:
            Ответ Avito API.
        """
        logger.info("Регистрация webhook Avito для URL %s.", webhook_url)
        return await self.client.register_webhook(webhook_url)

    async def get_webhook_status(self) -> dict[str, Any]:
        """Возвращает сведения о текущих подписках webhook."""
        logger.debug("Запрос статуса webhook Avito.")
        return await self.client.get_webhook_status()

    async def unregister_webhook(self) -> dict[str, Any]:
        """Удаляет активную подписку webhook в Avito."""
        logger.info("Удаление webhook подписки Avito.")
        return await self.client.unregister_webhook()
