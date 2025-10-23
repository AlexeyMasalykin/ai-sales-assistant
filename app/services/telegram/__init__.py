"""Telegram Bot сервис."""

from app.services.telegram.bot import TelegramBot, telegram_bot
from app.services.telegram.handlers import TelegramHandlers

__all__ = ["TelegramBot", "telegram_bot", "TelegramHandlers"]
