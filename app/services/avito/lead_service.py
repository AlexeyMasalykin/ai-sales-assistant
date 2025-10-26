"""Сервис для создания лидов из Avito диалогов."""
from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from app.core.redis_client import get_redis_client
from app.core.settings import settings
from app.models.crm import LeadCreateResult


class AvitoLeadService:
    """Сервис для создания лидов в amoCRM из Avito."""

    CONTACT_CACHE_TTL = 86400 * 30  # 30 дней

    def __init__(self) -> None:
        self.api_base_url = settings.api_base_url or "https://smmassistant.online"
        self.service_token = settings.avito_bot_service_token
        self.lead_cache_ttl = settings.avito_lead_cache_ttl

    async def _get_lead_cache_key(self, chat_id: str) -> str:
        """Генерирует ключ кэша для лида Avito чата."""
        return f"avito:lead_created:{chat_id}"

    async def _is_lead_already_created(
        self,
        chat_id: str,
    ) -> tuple[bool, int | None, int | None]:
        """Проверяет, был ли уже создан лид для этого Avito чата."""
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
                    "⚠️  Лид для Avito chat_id=%s уже существует: lead_id=%s, status_id=%s",
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
            logger.error("Ошибка проверки кэша Avito лида: %s", exc)
            return False, None, None

    async def _cache_created_lead(
        self,
        chat_id: str,
        lead_id: int,
        status_id: int,
        contact_id: int | None = None,
    ) -> None:
        """Сохраняет информацию о созданном лиде в Redis."""
        redis = await get_redis_client()
        cache_key = await self._get_lead_cache_key(chat_id)

        try:
            cache_payload = {"lead_id": lead_id, "status_id": status_id}
            if contact_id:
                cache_payload["contact_id"] = contact_id

            cache_data = json.dumps(cache_payload)
            await redis.setex(cache_key, self.lead_cache_ttl, cache_data)
            logger.info(
                "✅ Avito лид %s закэширован для chat_id=%s (status_id=%s, TTL: %sh)",
                lead_id,
                chat_id,
                status_id,
                self.lead_cache_ttl // 3600,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка кэширования Avito лида: %s", exc)
            return

        if contact_id:
            await self._cache_contact_id(chat_id=chat_id, contact_id=contact_id)

    async def _cache_contact_id(
        self,
        chat_id: str,
        contact_id: int | str | None,
    ) -> None:
        """Кэширует contact_id для ускоренной загрузки истории Avito диалогов."""
        if not contact_id:
            return

        try:
            redis = await get_redis_client()
            contact_cache_key = f"avito:contact_id:{chat_id}"
            await redis.setex(contact_cache_key, self.CONTACT_CACHE_TTL, str(contact_id))
            logger.info(
                "✅ Avito contact_id %s закэширован для chat_id=%s",
                contact_id,
                chat_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка кэширования Avito contact_id: %s", exc)

    async def save_conversation_to_amocrm(
        self,
        lead_id: int,
        user_message: str,
        bot_response: str | None = None,
        qualification: Any | None = None,
    ) -> bool:
        """Сохраняет историю переписки в amoCRM."""
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
                logger.info("✅ История Avito сохранена в amoCRM для лида %s", lead_id)
            else:
                logger.warning(
                    "⚠️ Не удалось сохранить Avito историю в amoCRM для лида %s",
                    lead_id,
                )

            return success

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка сохранения Avito истории в amoCRM: %s", exc)
            return False

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
        """
        Создаёт новый лид или обновляет существующий диалог из Avito.

        Шаги:
        1. Квалифицируем диалог
        2. Ищем контакт в amoCRM
        3. Если контакт найден — ищем активные лиды и двигаем статус
        4. Если лидов нет — создаём новый
        """
        if not self.service_token:
            logger.error("Сервисный токен Avito бота не настроен. Лид не создан.")
            return None

        from app.integrations.amocrm.client import get_amocrm_client
        from app.services.crm.lead_qualifier import lead_qualifier

        search_phone = phone or f"avito_user_{chat_id[:8]}"
        last_message = conversation_context.split("\n")[-1] if conversation_context else ""

        logger.info(
            "Обработка Avito лида для %s (chat_id=%s, phone=%s)",
            user_name,
            chat_id,
            search_phone,
        )

        qualification = await lead_qualifier.qualify_lead(
            conversation_history=conversation_context,
            user_message=conversation_context,
            source="avito",
        )
        logger.info(
            "📊 Avito квалификация: stage=%s, temp=%s, confidence=%.2f",
            qualification.stage,
            qualification.temperature,
            qualification.confidence,
        )
        logger.debug("Reasoning: %s", qualification.reasoning)

        amocrm_client = await get_amocrm_client()
        contact_id = await amocrm_client.find_contact_by_phone(search_phone)

        if contact_id:
            logger.info("✅ Avito контакт найден: contact_id=%s", contact_id)
            await self._cache_contact_id(chat_id=chat_id, contact_id=contact_id)

            leads = await amocrm_client.find_leads_by_contact(
                contact_id=contact_id,
                pipeline_id=lead_qualifier.PIPELINE_ID,
            )

            if leads:
                existing_lead = leads[0]
                lead_id = existing_lead["id"]
                current_status_id = existing_lead["status_id"]

                logger.info(
                    "✅ Найден активный Avito лид: lead_id=%s, status_id=%s",
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
                            "✅ Avito лид %s перемещён в статус %s (status_id=%s)",
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
                        logger.error(
                            "❌ Не удалось обновить Avito лид %s", lead_id
                        )

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
                    "⏸️  Avito лид %s остаётся в текущем статусе (status_id=%s)",
                    lead_id,
                    current_status_id,
                )
                return LeadCreateResult(
                    lead_id=lead_id,
                    contact_id=contact_id,
                    success=True,
                    message="Лид актуален, статус не изменён",
                )

        logger.info(
            "Создание нового Avito лида для %s (контакт не найден)", user_name
        )

        lead_data = {
            "user_name": user_name,
            "phone": search_phone,
            "email": email,
            "source": "avito",
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
                result_contact_id = result.get("contact_id")

                logger.info(
                    "✅ Avito лид создан: lead_id=%s, contact_id=%s, stage=%s",
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
                if result_contact_id:
                    await self._cache_contact_id(
                        chat_id=chat_id,
                        contact_id=result_contact_id,
                    )
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

    async def get_conversation_history_from_amocrm(self, chat_id: str) -> str:
        """Возвращает историю переписки из amoCRM."""
        from app.integrations.amocrm.client import get_amocrm_client
        from app.services.crm.lead_qualifier import lead_qualifier

        try:
            redis = await get_redis_client()
            contact_cache_key = f"avito:contact_id:{chat_id}"
            cached_contact_id = await redis.get(contact_cache_key)

            amocrm_client = await get_amocrm_client()
            contact_id: int | None = None

            if cached_contact_id:
                if isinstance(cached_contact_id, bytes):
                    cached_contact_id = cached_contact_id.decode()
                try:
                    contact_id = int(cached_contact_id)
                    logger.info(
                        "✅ Avito contact_id %s получен из кэша для chat_id=%s",
                        contact_id,
                        chat_id,
                    )
                except ValueError:
                    logger.warning("⚠️ Некорректный Avito contact_id в кэше: %s", cached_contact_id)

            if not contact_id:
                search_phone = f"avito_user_{chat_id[:8]}"
                contact_id = await amocrm_client.find_contact_by_phone(search_phone)

                if contact_id:
                    await redis.setex(
                        contact_cache_key,
                        self.CONTACT_CACHE_TTL,
                        str(contact_id),
                    )
                    logger.info(
                        "✅ Avito contact_id %s найден через API и закэширован",
                        contact_id,
                    )

            if not contact_id:
                logger.debug("Avito контакт для chat_id=%s не найден", chat_id)
                return ""

            leads = await amocrm_client.find_leads_by_contact(
                contact_id=contact_id,
                pipeline_id=lead_qualifier.PIPELINE_ID,
            )

            if not leads:
                logger.debug("Avito лиды для contact_id=%s не найдены", contact_id)
                return ""

            lead_id = leads[0]["id"]
            notes = await amocrm_client.get_lead_notes(lead_id=lead_id, limit=10)

            if not notes:
                logger.debug("Avito заметки для лида %s не найдены", lead_id)
                return ""

            logger.info("📝 Загружено %s Avito заметок из amoCRM", len(notes))

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
                else:
                    skipped_notes += 1

            if skipped_notes > 0:
                logger.info("⚠️ Пропущено %s Avito заметок без маркеров диалога", skipped_notes)

            history = "\n\n".join(history_parts)

            logger.info(
                "✅ Сформирована Avito история для chat_id=%s: %s сообщений, %s символов",
                chat_id,
                len(history_parts),
                len(history),
            )

            if history_parts:
                logger.debug("Avito первое сообщение: %s", history_parts[0][:150])
            else:
                logger.warning("⚠️ Avito история пустая после парсинга!")

            return history

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка загрузки Avito истории из amoCRM: %s", exc)
            return ""

    def should_create_lead(self, text: str) -> bool:
        """Определяет, содержит ли сообщение триггеры для создания лида."""
        text_lower = text.lower()

        hot_triggers = [
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
