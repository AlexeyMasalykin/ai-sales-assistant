"""Маршруты для работы с Avito Messenger API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.core.dependencies import get_current_user
from app.models.avito import WebhookRegistrationRequest, WebhookStatusResponse
from app.services.avito.exceptions import AvitoAPIError, AvitoRateLimitError
from app.services.avito.webhook import webhook_handler


router = APIRouter(tags=["avito"])


@router.post("/webhooks/avito/messages", status_code=status.HTTP_200_OK)
async def receive_avito_webhook(request: Request) -> dict[str, str]:
    """Принимает webhook от Avito и ставит в очередь на обработку."""
    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        logger.error("Avito webhook: некорректный JSON: {}", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    event_type = payload.get("event_type", "unknown")
    logger.info("Получен webhook от Avito: %s", event_type)
    logger.debug("Avito webhook payload: {}", payload)

    signature = request.headers.get("X-Avito-Signature")
    is_valid = await webhook_handler.validate_signature(payload, signature)
    if not is_valid:
        logger.warning("Webhook Avito отклонён: подпись недействительна.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    await webhook_handler.add_to_queue(payload)
    return {"status": "ok"}


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
        result = await webhook_handler.register_webhook(request.webhook_url)
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
        result = await webhook_handler.get_webhook_status()
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
        result = await webhook_handler.unregister_webhook()
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
