"""Telegram Bot клиент."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.core.settings import settings


class TelegramBot:
    """Клиент Telegram Bot API с поддержкой webhook."""

    def __init__(self) -> None:
        self.token = settings.telegram_bot_token.get_secret_value()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.webhook_url = settings.telegram_webhook_url
        self.client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Создаёт HTTP клиент и устанавливает webhook."""
        if self.client is not None:
            logger.debug("Telegram Bot уже запущен.")
            return

        self.client = httpx.AsyncClient(timeout=30.0)
        await self.set_webhook(f"{self.webhook_url}/api/v1/webhooks/telegram")
        await self.set_bot_commands()
        logger.info("Telegram Bot запущен.")

    async def stop(self) -> None:
        """Закрывает HTTP клиент и освобождает ресурсы."""
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info("Telegram Bot остановлен.")

    async def set_webhook(self, url: str) -> dict[str, Any]:
        """Устанавливает webhook URL в Telegram."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/setWebhook",
                json={"url": url},
            )
            result = response.json()

        if result.get("ok"):
            logger.info("Webhook Telegram установлен: %s", url)
        else:
            logger.error("Ошибка установки webhook Telegram: %s", result)
        return result

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """Отправляет сообщение в чат Telegram."""
        if not self.client:
            raise RuntimeError("Telegram Bot не запущен.")

        try:
            response = await self.client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            result = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка при отправке сообщения Telegram: {}", exc)
            raise

        if result.get("ok"):
            logger.debug("Сообщение отправлено в чат %s.", chat_id)
        else:
            logger.error("Telegram вернул ошибку при отправке: %s", result)
        return result

    async def set_bot_commands(self) -> None:
        """Устанавливает меню команд бота."""
        if not self.client:
            return

        commands = [
            {"command": "start", "description": "🚀 Начать работу"},
            {"command": "help", "description": "❓ Помощь"},
            {"command": "services", "description": "📋 Наши услуги"},
            {"command": "price", "description": "💰 Узнать стоимость"},
            {"command": "price_list", "description": "📄 Скачать прайс"},
            {"command": "proposal", "description": "📝 Заказать КП"},
            {"command": "contact", "description": "📞 Связаться с менеджером"},
            {"command": "cases", "description": "🏆 Наши кейсы"},
        ]

        try:
            response = await self.client.post(
                f"{self.base_url}/setMyCommands", json={"commands": commands}
            )
            data = response.json()
            if data.get("ok"):
                logger.info("Меню команд установлено")
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка установки меню: %s", exc)


# Singleton экземпляр
telegram_bot = TelegramBot()
