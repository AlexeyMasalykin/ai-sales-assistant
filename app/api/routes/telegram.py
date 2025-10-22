"""Маршруты webhook для Telegram Bot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from app.services.telegram.bot import telegram_bot
from app.services.telegram.handlers import TelegramHandlers


router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])


@router.post("", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request) -> dict[str, bool]:
    """Принимает webhook от Telegram Bot API."""
    try:
        data: dict[str, Any] = await request.json()
    except ValueError as exc:
        logger.error("Telegram: некорректный JSON webhook: {}", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    message = data.get("message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        logger.warning("Telegram: сообщение без chat_id: {}", message)
        return {"ok": True}

    user_info = message.get("from", {})
    user_name = user_info.get("first_name") or user_info.get("username") or "Друг"

    text = message.get("text")
    if text:
        if text == "/start":
            response = await TelegramHandlers.handle_start(chat_id, user_name)
        elif text == "/help":
            response = await TelegramHandlers.handle_help(chat_id)
        elif text == "/services":
            response = await TelegramHandlers.handle_services(chat_id)
        elif text == "/price":
            response = await TelegramHandlers.handle_price(chat_id)
        else:
            response = await TelegramHandlers.handle_text_message(
                chat_id,
                text,
                user_name,
            )

        await telegram_bot.send_message(chat_id, response)

    return {"ok": True}
