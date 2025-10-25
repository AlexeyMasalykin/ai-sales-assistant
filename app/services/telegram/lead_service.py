"""Сервис для создания лидов из Telegram диалогов."""
from __future__ import annotations

from datetime import timedelta

import httpx
from loguru import logger

from app.core.redis_client import get_redis_client
from app.core.settings import settings
from app.models.crm import LeadCreateRequest, LeadCreateResult


class TelegramLeadService:
    """Сервис для создания лидов в amoCRM из Telegram."""

    def __init__(self) -> None:
        self.api_base_url = settings.api_base_url or "https://smmassistant.online"
        self.service_token = settings.telegram_bot_service_token
        self.lead_cache_ttl = settings.telegram_lead_cache_ttl

    async def _get_lead_cache_key(self, chat_id: int) -> str:
        """Генерирует ключ кэша для лида пользователя."""
        return f"telegram:lead_created:{chat_id}"

    async def _is_lead_already_created(self, chat_id: int) -> tuple[bool, int | None]:
        """Проверяет, был ли уже создан лид для пользователя."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            cached_lead_id = await redis.get(cache_key)
            if cached_lead_id:
                logger.info(
                    "⚠️  Лид для chat_id=%s уже существует: lead_id=%s",
                    chat_id,
                    cached_lead_id,
                )
                return True, int(cached_lead_id)
            return False, None
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка проверки кэша лида: %s", exc)
            return False, None

    async def _cache_created_lead(self, chat_id: int, lead_id: int) -> None:
        """Сохраняет информацию о созданном лиде в Redis."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            await redis.setex(cache_key, self.lead_cache_ttl, str(lead_id))
            ttl_hours = timedelta(seconds=self.lead_cache_ttl)
            logger.info(
                "✅ Лид %s закэширован для chat_id=%s (TTL: %s)",
                lead_id,
                chat_id,
                ttl_hours,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка кэширования лида: %s", exc)

    async def create_lead_from_conversation(
        self,
        chat_id: int,
        user_name: str,
        phone: str | None = None,
        email: str | None = None,
        product_interest: str | None = None,
        budget: int | None = None,
        conversation_context: str = "",
    ) -> LeadCreateResult | None:
        """
        Создаёт лид в amoCRM из данных Telegram диалога.

        Args:
            chat_id: ID чата Telegram
            user_name: Имя пользователя
            phone: Телефон (если извлечён из диалога)
            email: Email (если извлечён из диалога)
            product_interest: Интерес к продукту (AI Manager/AI Lawyer/AI Analyst)
            budget: Примерный бюджет (если упоминался)
            conversation_context: Краткая история диалога

        Returns:
            Результат создания лида или None при ошибке
        """
        if not self.service_token:
            logger.error("Сервисный токен Telegram бота не настроен. Лид не создан.")
            return None

        lead_exists, existing_lead_id = await self._is_lead_already_created(chat_id)
        if lead_exists and existing_lead_id:
            logger.info(
                "⏭️  Пропускаем создание лида для %s (chat_id=%s). Лид уже существует: %s",
                user_name,
                chat_id,
                existing_lead_id,
            )
            return LeadCreateResult(
                lead_id=existing_lead_id,
                contact_id=0,
                success=True,
                message="Лид уже был создан ранее",
            )

        logger.info(
            "Создание лида для Telegram пользователя %s (chat_id=%s)",
            user_name,
            chat_id,
        )

        lead_request = LeadCreateRequest(
            user_name=user_name,
            phone=phone or f"telegram_user_{chat_id}",
            email=email,
            source="telegram",
            product_interest=product_interest or "Консультация",
            budget=budget,
            conversation_history=conversation_context[:500],
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/v1/amocrm/leads",
                    headers={
                        "Authorization": f"Bearer {self.service_token}",
                        "Content-Type": "application/json",
                    },
                    json=lead_request.model_dump(exclude_none=True),
                )

            if response.status_code == 200:
                result = response.json()
                lead_id = result.get("lead_id")
                logger.info(
                    "✅ Лид создан: lead_id=%s, contact_id=%s",
                    lead_id,
                    result.get("contact_id"),
                )
                if lead_id:
                    await self._cache_created_lead(chat_id, int(lead_id))
                return LeadCreateResult(**result)

            logger.error(
                "Ошибка создания лида: %s - %s",
                response.status_code,
                response.text,
            )
            return None

        except Exception as exc:  # noqa: BLE001
            logger.error("Исключение при создании лида: %s", exc)
            return None

    def should_create_lead(self, text: str) -> bool:
        """
        Определяет, содержит ли сообщение триггеры для создания лида.

        Args:
            text: Текст сообщения

        Returns:
            True если нужно создать лид
        """
        text_lower = text.lower()
        trigger_phrases = [
            "оставить заявку",
            "оставьте заявку",
            "хочу заказать",
            "хочу купить",
            "свяжитесь со мной",
            "позвоните мне",
            "жду звонка",
            "готов купить",
            "заказать",
            "купить",
            "оформить заказ",
            "создать заявку",
            "связаться",
            "оставлю заявку",
        ]

        return any(phrase in text_lower for phrase in trigger_phrases)

    def extract_product_from_context(self, context: list[dict]) -> str | None:
        """
        Извлекает упоминание продукта из контекста диалога.

        Args:
            context: История сообщений

        Returns:
            Название продукта или None
        """
        products = {
            "ии-менеджер": "AI Manager",
            "ai manager": "AI Manager",
            "менеджер": "AI Manager",
            "ии-юрист": "AI Lawyer",
            "ai lawyer": "AI Lawyer",
            "юрист": "AI Lawyer",
            "ии-аналитик": "AI Analyst",
            "ai analyst": "AI Analyst",
            "аналитик": "AI Analyst",
            "автоматизация": "AI Manager",
            "crm": "AI Manager",
        }

        full_context = " ".join(msg.get("content", "").lower() for msg in context)

        for key, product in products.items():
            if key in full_context:
                return product

        return None


telegram_lead_service = TelegramLeadService()
