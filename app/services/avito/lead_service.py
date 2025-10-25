"""Сервис для создания лидов из Avito диалогов."""
from __future__ import annotations

import httpx
from loguru import logger

from app.core.redis_client import get_redis_client
from app.core.settings import settings
from app.models.crm import LeadCreateRequest, LeadCreateResult


class AvitoLeadService:
    """Сервис для создания лидов в amoCRM из Avito."""

    def __init__(self) -> None:
        self.api_base_url = settings.api_base_url or "https://smmassistant.online"
        self.service_token = settings.avito_bot_service_token
        self.lead_cache_ttl = settings.avito_lead_cache_ttl

    async def _get_lead_cache_key(self, chat_id: str) -> str:
        """Генерирует ключ кэша для лида Avito чата."""
        return f"avito:lead_created:{chat_id}"

    async def _is_lead_already_created(self, chat_id: str) -> tuple[bool, int | None]:
        """Проверяет, был ли уже создан лид для этого Avito чата."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            cached_lead_id = await redis.get(cache_key)
            if cached_lead_id:
                logger.info(
                    "⚠️  Лид для Avito chat_id=%s уже существует: lead_id=%s",
                    chat_id,
                    cached_lead_id,
                )
                return True, int(cached_lead_id)
            return False, None
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка проверки кэша Avito лида: %s", exc)
            return False, None

    async def _cache_created_lead(self, chat_id: str, lead_id: int) -> None:
        """Сохраняет информацию о созданном лиде в Redis."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            await redis.setex(cache_key, self.lead_cache_ttl, str(lead_id))
            logger.info(
                "✅ Avito лид %s закэширован для chat_id=%s (TTL: %sh)",
                lead_id,
                chat_id,
                self.lead_cache_ttl // 3600,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка кэширования Avito лида: %s", exc)

    async def create_lead_from_conversation(
        self,
        chat_id: str,
        user_name: str,
        phone: str | None = None,
        email: str | None = None,
        product_interest: str | None = None,
        budget: int | None = None,
        conversation_context: str = "",
    ) -> LeadCreateResult | None:
        """Создаёт лид в amoCRM из данных Avito диалога."""
        if not self.service_token:
            logger.error("Сервисный токен Avito бота не настроен. Лид не создан.")
            return None

        lead_exists, existing_lead_id = await self._is_lead_already_created(chat_id)
        if lead_exists and existing_lead_id:
            logger.info(
                "⏭️  Пропускаем создание Avito лида для %s (chat_id=%s). Лид уже существует: %s",
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
            "Создание лида для Avito пользователя %s (chat_id=%s)",
            user_name,
            chat_id,
        )

        lead_request = LeadCreateRequest(
            user_name=user_name,
            phone=phone or f"avito_user_{chat_id[:8]}",
            email=email,
            source="avito",
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
                    "✅ Avito лид создан: lead_id=%s, contact_id=%s",
                    lead_id,
                    result.get("contact_id"),
                )
                if lead_id:
                    await self._cache_created_lead(chat_id, int(lead_id))
                return LeadCreateResult(**result)

            logger.error(
                "Ошибка создания Avito лида: %s - %s",
                response.status_code,
                response.text,
            )
            return None

        except Exception as exc:  # noqa: BLE001
            logger.error("Исключение при создании Avito лида: %s", exc)
            return None

    def should_create_lead(self, text: str) -> bool:
        """Определяет, содержит ли сообщение триггеры для создания лида."""
        text_lower = text.lower()

        hot_triggers = [
            "хочу купить",
            "готов купить",
            "хочу заказать",
            "готов заказать",
            "оформить заказ",
            "оставить заявку",
            "оставьте заявку",
            "свяжитесь со мной",
            "позвоните мне",
            "жду звонка",
            "нужна консультация",
            "записаться на консультацию",
        ]
        price_triggers = ["сколько стоит", "цена", "стоимость"]
        readiness_triggers = ["беру", "покупаю", "заказываю", "согласен"]

        has_hot_trigger = any(phrase in text_lower for phrase in hot_triggers)
        has_price = any(phrase in text_lower for phrase in price_triggers)
        has_readiness = any(phrase in text_lower for phrase in readiness_triggers)

        return has_hot_trigger or (has_price and has_readiness)

    def extract_product_from_text(self, text: str) -> str | None:
        """Извлекает упоминание продукта из текста."""
        text_lower = text.lower()
        products = {
            "ии-менеджер": "AI Manager",
            "ai manager": "AI Manager",
            "менеджер": "AI Manager",
            "автоматизация crm": "AI Manager",
            "ии-юрист": "AI Lawyer",
            "ai lawyer": "AI Lawyer",
            "юрист": "AI Lawyer",
            "юридическ": "AI Lawyer",
            "ии-аналитик": "AI Analyst",
            "ai analyst": "AI Analyst",
            "аналитик": "AI Analyst",
            "анализ данных": "AI Analyst",
            "автоматизация": "AI Manager",
        }

        for key, product in products.items():
            if key in text_lower:
                return product

        return None


avito_lead_service = AvitoLeadService()
