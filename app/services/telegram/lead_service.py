"""Сервис для создания лидов из Telegram диалогов."""
from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from app.core.redis_client import get_redis_client
from app.core.settings import settings
from app.models.crm import LeadCreateResult


class TelegramLeadService:
    """Сервис для создания лидов в amoCRM из Telegram."""

    def __init__(self) -> None:
        self.api_base_url = settings.api_base_url or "https://smmassistant.online"
        self.service_token = settings.telegram_bot_service_token
        self.lead_cache_ttl = settings.telegram_lead_cache_ttl

    async def _get_lead_cache_key(self, chat_id: int) -> str:
        """Генерирует ключ кэша для лида пользователя."""
        return f"telegram:lead_created:{chat_id}"

    async def _is_lead_already_created(
        self,
        chat_id: int,
    ) -> tuple[bool, int | None, int | None]:
        """Проверяет, был ли уже создан лид для пользователя."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode()
                data = json.loads(cached_data)
                lead_id = data.get("lead_id")
                status_id = data.get("status_id")

                logger.info(
                    "⚠️  Лид для chat_id=%s уже существует: lead_id=%s, status_id=%s",
                    chat_id,
                    lead_id,
                    status_id,
                )
                return (
                    True,
                    int(lead_id) if lead_id is not None else None,
                    int(status_id) if status_id is not None else None,
                )
            return False, None, None
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка проверки кэша лида: %s", exc)
            return False, None, None

    async def _cache_created_lead(
        self,
        chat_id: int,
        lead_id: int,
        status_id: int,
    ) -> None:
        """Сохраняет информацию о созданном лиде в Redis."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            cache_data = json.dumps({"lead_id": lead_id, "status_id": status_id})
            await redis.setex(cache_key, self.lead_cache_ttl, cache_data)
            ttl_hours = max(1, self.lead_cache_ttl // 3600)
            logger.info(
                "✅ Лид %s закэширован для chat_id=%s "
                "(status_id=%s, TTL: %sч)",
                lead_id,
                chat_id,
                status_id,
                ttl_hours,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка кэширования лида: %s", exc)

    async def save_conversation_to_amocrm(
        self,
        lead_id: int,
        user_message: str,
        bot_response: str | None = None,
        qualification: Any | None = None,
    ) -> bool:
        """
        Сохраняет историю диалога в заметках amoCRM.

        Args:
            lead_id: ID лида
            user_message: последнее сообщение пользователя
            bot_response: ответ бота (опционально)
            qualification: данные квалификации (опционально)
        """
        from app.integrations.amocrm.client import get_amocrm_client

        try:
            amocrm_client = await get_amocrm_client()

            note_parts = [f"👤 Пользователь: {user_message}"]

            if qualification:
                note_parts.append(
                    f"\n📊 Квалификация: {qualification.stage} "
                    f"({qualification.temperature}, confidence: {qualification.confidence:.2f})"
                )
                if getattr(qualification, "reasoning", None):
                    note_parts.append(f"💭 Reasoning: {qualification.reasoning}")

            if bot_response:
                short_response = (
                    f"{bot_response[:300]}..." if len(bot_response) > 300 else bot_response
                )
                note_parts.append(f"\n🤖 Ответ бота: {short_response}")

            note_text = "\n".join(note_parts)

            success = await amocrm_client.add_note(
                entity_id=lead_id,
                entity_type="leads",
                note_type="common",
                text=note_text,
            )

            if success:
                logger.info("✅ История сохранена в amoCRM для лида %s", lead_id)
            else:
                logger.warning("⚠️ Не удалось сохранить историю в амоCRM для лида %s", lead_id)

            return success

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка сохранения истории в amoCRM: %s", exc)
            return False

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
        Создаёт новый лид или обновляет существующий.

        Логика:
        1. Квалифицируем диалог через OpenAI
        2. Ищем контакт по телефону в amoCRM
        3. Если контакт найден → ищем активные лиды
        4. Если лид найден → обновляем статус (если нужно)
        5. Если лида нет → создаём новый через API
        """
        if not self.service_token:
            logger.error("Сервисный токен не настроен.")
            return None

        from app.integrations.amocrm.client import get_amocrm_client
        from app.services.crm.lead_qualifier import lead_qualifier

        search_phone = phone or f"telegram_user_{chat_id}"
        last_message = conversation_context.split("\n")[-1] if conversation_context else ""

        logger.info(
            "Обработка лида для %s (chat_id=%s, phone=%s)",
            user_name,
            chat_id,
            search_phone,
        )

        qualification = await lead_qualifier.qualify_lead(
            conversation_history=conversation_context,
            user_message=conversation_context.split("\n")[-1]
            if conversation_context
            else "",
            source="telegram",
        )

        logger.info(
            "📊 Квалификация: stage=%s, temp=%s, confidence=%.2f",
            qualification.stage,
            qualification.temperature,
            qualification.confidence,
        )
        logger.debug("Reasoning: %s", qualification.reasoning)

        amocrm_client = await get_amocrm_client()
        contact_id = await amocrm_client.find_contact_by_phone(search_phone)

        if contact_id:
            logger.info("✅ Контакт найден: contact_id=%s", contact_id)
            leads = await amocrm_client.find_leads_by_contact(
                contact_id=contact_id,
                pipeline_id=lead_qualifier.PIPELINE_ID,
            )

            if leads:
                existing_lead = leads[0]
                lead_id = existing_lead["id"]
                current_status_id = existing_lead["status_id"]

                logger.info(
                    "✅ Найден активный лид: lead_id=%s, status_id=%s",
                    lead_id,
                    current_status_id,
                )

                should_update = lead_qualifier.should_update_stage(
                    current_status_id=current_status_id,
                    new_status_id=qualification.status_id,
                )

                if should_update:
                    success = await amocrm_client.update_lead_status(
                        lead_id=lead_id,
                        status_id=qualification.status_id,
                        pipeline_id=lead_qualifier.PIPELINE_ID,
                    )

                    if success:
                        logger.info(
                            "✅ Лид %s перемещён в статус %s (status_id=%s)",
                            lead_id,
                            qualification.stage,
                            qualification.status_id,
                        )
                        await self.save_conversation_to_amocrm(
                            lead_id=lead_id,
                            user_message=last_message,
                            bot_response=None,
                            qualification=qualification,
                        )
                    else:
                        logger.error("❌ Не удалось обновить статус лида %s", lead_id)

                    return LeadCreateResult(
                        lead_id=lead_id,
                        contact_id=contact_id,
                        success=success,
                        message=(
                            f"Лид обновлён: {qualification.stage}"
                            if success
                            else "Ошибка обновления"
                        ),
                    )

                logger.info(
                    "⏸️  Лид %s остаётся в текущем статусе (status_id=%s)",
                    lead_id,
                    current_status_id,
                )
                return LeadCreateResult(
                    lead_id=lead_id,
                    contact_id=contact_id,
                    success=True,
                    message="Лид актуален, статус не изменён",
                )

        logger.info("Создание нового лида для %s (контакт не найден)", user_name)

        lead_data = {
            "user_name": user_name,
            "phone": search_phone,
            "email": email,
            "source": "telegram",
            "product_interest": product_interest or "Консультация",
            "budget": budget,
            "conversation_history": conversation_context[:500],
            "pipeline_id": lead_qualifier.PIPELINE_ID,
            "status_id": qualification.status_id,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/v1/amocrm/leads",
                    headers={
                        "Authorization": f"Bearer {self.service_token}",
                        "Content-Type": "application/json",
                    },
                    json=lead_data,
                )

            if response.status_code == 200:
                result = response.json()
                lead_id = result.get("lead_id")

                logger.info(
                    "✅ Новый лид создан: lead_id=%s, contact_id=%s, stage=%s",
                    lead_id,
                    result.get("contact_id"),
                    qualification.stage,
                )

                if lead_id:
                    await self.save_conversation_to_amocrm(
                        lead_id=int(lead_id),
                        user_message=last_message,
                        bot_response=None,
                        qualification=qualification,
                    )
                return LeadCreateResult(**result)

            logger.error(
                "❌ Ошибка создания лида: %s - %s",
                response.status_code,
                response.text,
            )
            return None

        except Exception as exc:  # noqa: BLE001
            logger.error("❌ Исключение при создании лида: %s", exc)
            return None

    async def get_conversation_history_from_amocrm(self, chat_id: int) -> str:
        """Загружает историю диалога из amoCRM (только из CRM, без Redis)."""
        from app.integrations.amocrm.client import get_amocrm_client
        from app.services.crm.lead_qualifier import lead_qualifier

        try:
            amocrm_client = await get_amocrm_client()
            search_phone = f"telegram_user_{chat_id}"

            contact_id = await amocrm_client.find_contact_by_phone(search_phone)

            if not contact_id:
                logger.debug(f"Контакт для chat_id={chat_id} не найден в amoCRM")
                return ""

            logger.info(f"✅ Контакт {contact_id} найден для chat_id={chat_id}")

            leads = await amocrm_client.find_leads_by_contact(
                contact_id=contact_id,
                pipeline_id=lead_qualifier.PIPELINE_ID,
            )

            if not leads:
                logger.debug(f"Лиды для contact_id={contact_id} не найдены")
                return ""

            lead_id = leads[0]["id"]
            logger.info(f"✅ Найден лид {lead_id} для загрузки истории")

            notes = await amocrm_client.get_lead_notes(lead_id=lead_id, limit=10)

            if not notes:
                logger.debug(f"Заметки для лида {lead_id} не найдены")
                return ""

            logger.info(f"📝 Загружено {len(notes)} заметок из amoCRM")

            notes_sorted = sorted(notes, key=lambda item: item.get("created_at", 0))
            history_parts: list[str] = []
            skipped_notes = 0

            for note in notes_sorted:
                text = note.get("text", "")

                # Проверяем наличие маркеров диалога (с эмодзи и без)
                if (
                    "Пользователь:" in text
                    or "👤 Пользователь:" in text
                    or "Ответ бота:" in text
                    or "🤖 Ответ бота:" in text
                    or "История диалога:" in text
                ):
                    clean_text = text.strip()
                    clean_text = clean_text.replace("История диалога:", "").strip()

                    # Убираем блоки квалификации и reasoning
                    if "Квалификация:" in clean_text or "📊 Квалификация:" in clean_text:
                        clean_text = clean_text.split("Квалификация:")[0].strip()
                        clean_text = clean_text.split("📊 Квалификация:")[0].strip()

                    if "Reasoning:" in clean_text or "💭 Reasoning:" in clean_text:
                        clean_text = clean_text.split("Reasoning:")[0].strip()
                        clean_text = clean_text.split("💭 Reasoning:")[0].strip()

                    # Нормализуем маркеры (убираем эмодзи, приводим к единому формату)
                    clean_text = clean_text.replace("👤 Пользователь:", "Клиент:")
                    clean_text = clean_text.replace("Пользователь:", "Клиент:")
                    clean_text = clean_text.replace("🤖 Ответ бота:", "Бот:")
                    clean_text = clean_text.replace("Ответ бота:", "Бот:")

                    if clean_text.strip():
                        history_parts.append(clean_text.strip())
                        logger.debug(f"✅ Заметка добавлена: {clean_text[:80]}...")
                else:
                    skipped_notes += 1
                    logger.debug(
                        f"⚠️ Заметка пропущена (нет маркеров диалога): {text[:80]}..."
                    )

            if skipped_notes:
                logger.info(f"⚠️ Пропущено {skipped_notes} заметок без маркеров диалога")

            history = "\n\n".join(history_parts)

            logger.info(
                f"✅ Сформирована история: {len(history_parts)} сообщений, {len(history)} символов"
            )

            if history_parts:
                logger.debug(f"Первое сообщение: {history_parts[0][:150]}")

            return history

        except Exception as exc:
            logger.error(f"Ошибка загрузки истории из amoCRM: {exc}")
            return ""

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
            "согласен",
            "согласна",
            "подписать договор",
            "когда подпишем",
            "готов подписать",
            "оплатить",
            "счёт",
            "реквизиты",
            "договор готов"
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
