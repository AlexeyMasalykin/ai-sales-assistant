"""Маршруты для работы с Avito Messenger API."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from loguru import logger

from app.core.dependencies import get_current_user
from app.models.avito import (
    AvitoWebhookPayload,
    WebhookRegistrationRequest,
    WebhookStatusResponse,
)
from app.services.avito.exceptions import AvitoAPIError, AvitoRateLimitError
from app.services.avito.webhook import AvitoWebhookHandler


router = APIRouter(tags=["avito"])
_handler = AvitoWebhookHandler()


async def _process_webhook_async(data: dict[str, Any]) -> None:
    """Фоновая обработка события Avito webhook."""
    try:
        await _handler.process_message(data)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка обработки webhook Avito: {}", exc)


@router.post("/webhooks/avito/messages", status_code=status.HTTP_200_OK)
async def receive_avito_message(
    payload: AvitoWebhookPayload,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict[str, str]:
    """Принимает входящие сообщения от Avito и добавляет их в очередь.

    Args:
        payload: Данные webhook, переданные Avito.
        x_signature: Подпись запроса (если предоставляется Avito).

    Returns:
        Подтверждение приёма сообщения.
    """
    payload_dict = payload.model_dump(by_alias=True, exclude_none=True)
    logger.debug("Получен webhook Avito: {}", payload_dict)

    is_valid = await _handler.validate_signature(payload_dict, x_signature)
    if not is_valid:
        logger.warning("Webhook Avito отклонён из-за недействительной подписи.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    logger.info("Получено событие Avito типа {}", payload.event_type)
    asyncio.create_task(_process_webhook_async(payload_dict))
    return {"status": "accepted"}


@router.post(
    "/avito/webhook/register",
    status_code=status.HTTP_200_OK,
)
async def register_avito_webhook(
    request: WebhookRegistrationRequest,
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """Регистрирует URL webhook в Avito Messenger."""
    try:
        result = await _handler.register_webhook(request.webhook_url)
    except AvitoRateLimitError as exc:
        logger.warning("Превышен лимит Avito при регистрации webhook: {}", exc.retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Avito rate limit, попробуйте позже.",
        ) from exc
    except AvitoAPIError as exc:
        logger.error("Ошибка Avito при регистрации webhook: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    logger.info(
        "Webhook Avito успешно зарегистрирован для {} пользователем {}",
        request.webhook_url,
        getattr(current_user, "sub", "unknown"),
    )
    return result


@router.get(
    "/avito/webhook/status",
    response_model=WebhookStatusResponse,
)
async def get_avito_webhook_status(
    current_user=Depends(get_current_user),
) -> WebhookStatusResponse:
    """Возвращает статус текущей подписки Avito webhook."""
    try:
        result = await _handler.get_webhook_status()
    except AvitoAPIError as exc:
        logger.error("Не удалось получить статус Avito webhook: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    subscriptions = result.get("subscriptions") or []
    is_registered = bool(subscriptions)
    webhook_url = None
    if subscriptions:
        webhook_url = subscriptions[0].get("url")

    logger.debug(
        "Статус webhook Avito: зарегистрирован={}, url={} (запрос от {})",
        is_registered,
        webhook_url,
        getattr(current_user, "sub", "unknown"),
    )

    return WebhookStatusResponse(
        is_registered=is_registered,
        webhook_url=webhook_url,
        raw=result,
    )


@router.delete(
    "/avito/webhook/unregister",
    status_code=status.HTTP_200_OK,
)
async def unregister_avito_webhook(
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """Удаляет активную подписку Avito webhook."""
    try:
        result = await _handler.unregister_webhook()
    except AvitoAPIError as exc:
        logger.error("Ошибка Avito при удалении webhook: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    logger.info(
        "Webhook Avito успешно удалён пользователем {}",
        getattr(current_user, "sub", "unknown"),
    )
    return result
