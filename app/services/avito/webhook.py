"""Обработка событий Avito Messenger."""

from __future__ import annotations

import asyncio
from asyncio import Task
from typing import Any

from loguru import logger

from app.core.settings import settings
from app.services.avito.client import AvitoAPIClient
from app.services.avito.handlers import AvitoMessageHandlers
from app.services.avito.exceptions import AvitoAPIError, AvitoRateLimitError


class AvitoWebhookHandler:
    """Управляет приёмом, очередь и автоответами Avito."""

    def __init__(self, client: AvitoAPIClient | None = None) -> None:
        self.client = client or AvitoAPIClient()
        self.message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=settings.avito_max_queue_size,
        )
        self._workers: list[Task[Any]] = []
        self._stop_event = asyncio.Event()

    async def validate_signature(
        self,
        payload: dict[str, Any],
        signature: str | None,
    ) -> bool:
        """Проверяет подпись webhook (заглушка)."""
        # TODO: добавить фактическую проверку подписи Avito.
        if signature is None:
            logger.debug("Подпись webhook Avito отсутствует.")
        return True

    async def add_to_queue(self, webhook_data: dict[str, Any]) -> None:
        """Ставит входящее событие в очередь обработки."""
        try:
            self.message_queue.put_nowait(webhook_data)
            logger.info(
                "Событие Avito добавлено в очередь (текущий размер: %s).",
                self.message_queue.qsize(),
            )
        except asyncio.QueueFull:
            logger.error("Очередь обработки Avito переполнена, событие отброшено.")

    async def start_processing(self) -> None:
        """Запускает фоновых воркеров обработки сообщений."""
        if self._workers:
            logger.debug("Обработка Avito уже активна.")
            return
        self._stop_event.clear()
        for idx in range(settings.avito_processing_workers):
            task = asyncio.create_task(
                self._worker_loop(idx),
                name=f"avito-worker-{idx}",
            )
            self._workers.append(task)
        logger.info("Запущено %s воркеров Avito.", len(self._workers))

    async def stop_processing(self) -> None:
        """Останавливает фоновые воркеры обработки."""
        if not self._workers:
            return
        self._stop_event.set()
        for task in self._workers:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Воркер %s остановлен.", task.get_name())
        self._workers.clear()
        logger.info("Обработка очереди Avito остановлена.")

    async def _worker_loop(self, worker_id: int) -> None:
        """Бесконечный цикл обработки сообщений из очереди."""
        logger.debug("Старт воркера Avito #%s.", worker_id)
        while not self._stop_event.is_set():
            try:
                payload = await self.message_queue.get()
            except asyncio.CancelledError:
                break
            try:
                await self._handle_message(payload)
            except Exception as exc:  # noqa: BLE001
                logger.error("Ошибка обработки события Avito: {}", exc)
            finally:
                self.message_queue.task_done()
        logger.debug("Воркер Avito #%s завершён.", worker_id)

    async def _handle_message(self, webhook_data: dict[str, Any]) -> None:
        """Определяет тип события и выполняет соответствующий обработчик."""
        event_type = webhook_data.get("event_type", "")
        payload = webhook_data.get("payload") or webhook_data
        logger.debug("Обработка события Avito типа %s.", event_type)

        if event_type == "message.new":
            message = payload.get("message") or {}
            await self._handle_new_message(message)
        elif event_type == "message.read":
            logger.info("Avito: сообщение отмечено как прочитанное: {}", payload)
        elif event_type:
            logger.debug("Avito: необработанный тип события %s.", event_type)
        else:
            logger.warning("Avito: событие без типа: {}", webhook_data)

    async def _handle_new_message(self, message_data: dict[str, Any]) -> None:
        """Обрабатывает новое входящее сообщение."""
        chat_id = message_data.get("chat_id")
        author_id = (message_data.get("author_id") or "").strip()
        message_type = message_data.get("type", "text")
        text = (message_data.get("text") or "").strip()

        logger.info(
            "Avito: новое сообщение chat_id=%s author_id=%s type=%s",
            chat_id,
            author_id,
            message_type,
        )
        logger.debug("Avito: содержимое сообщения %s", message_data)

        if not chat_id:
            logger.error("Avito: сообщение без chat_id пропущено.")
            return

        response: str | None = None
        if message_type == "text" and text:
            response = await self._generate_response(text, chat_id)
        elif message_type == "image":
            response = await AvitoMessageHandlers.handle_image_message(
                chat_id,
                str(message_data.get("image_url", "")),
            )
        else:
            logger.debug("Avito: тип сообщения %s не поддерживается автоответом.", message_type)

        if settings.avito_auto_reply_enabled and response:
            await self._send_with_retry(chat_id, response)
        else:
            logger.info("Avito: автоответ отключён или не требуется для чата %s.", chat_id)

    async def _generate_response(self, message_text: str, chat_id: str) -> str:
        """Генерирует ответ по тексту сообщения."""
        logger.debug("Avito: генерация ответа для чата %s.", chat_id)
        response = await AvitoMessageHandlers.handle_text_message(
            chat_id=chat_id,
            text=message_text,
            author_id="avito-user",
        )
        return response

    async def _send_with_retry(self, chat_id: str, text: str) -> None:
        """Отправляет автоответ с повторными попытками."""
        for attempt in range(3):
            try:
                if settings.avito_response_delay_seconds > 0:
                    await asyncio.sleep(settings.avito_response_delay_seconds)
                await self.client.send_message(chat_id, text)
                logger.info("Avito: отправлен автоответ в чат %s.", chat_id)
                return
            except AvitoRateLimitError as exc:
                wait_time = exc.retry_after or max(1, 2**attempt)
                logger.warning(
                    "Avito: rate limit при отправке сообщения, повтор через %s секунд.",
                    wait_time,
                )
                await asyncio.sleep(wait_time)
            except AvitoAPIError as exc:
                logger.warning(
                    "Avito: ошибка API при отправке (попытка %s): %s",
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(2**attempt)
            except Exception as exc:  # noqa: BLE001
                logger.error("Avito: критическая ошибка отправки сообщения: %s", exc)
                await asyncio.sleep(2**attempt)
        logger.error("Avito: не удалось отправить сообщение в чат %s после 3 попыток.", chat_id)

    async def register_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Регистрирует webhook URL в Avito."""
        logger.info("Avito: регистрация webhook для %s.", webhook_url)
        return await self.client.register_webhook(webhook_url)

    async def get_webhook_status(self) -> dict[str, Any]:
        """Возвращает текущий статус webhook подписки."""
        logger.debug("Avito: запрос статуса webhook.")
        return await self.client.get_webhook_status()

    async def unregister_webhook(self) -> dict[str, Any]:
        """Удаляет активную подписку Avito webhook."""
        logger.info("Avito: удаление webhook подписки.")
        return await self.client.unregister_webhook()


webhook_handler = AvitoWebhookHandler()
