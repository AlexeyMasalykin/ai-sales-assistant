"""Бизнес-логика создания лидов из диалогов."""
from loguru import logger

from app.integrations.amocrm.client import amocrm_client
from app.integrations.amocrm.models import LeadCreateRequest, LeadCreateResponse


class AmoCRMService:
    """Сервис для работы с amoCRM лидами."""

    @staticmethod
    async def create_lead_from_conversation(
        request: LeadCreateRequest,
        user_id: str | int | None = None,
    ) -> LeadCreateResponse:
        """
        Создаёт лид и контакт в amoCRM из данных диалога.

        Workflow:
        1. Создать контакт (если есть phone/email)
        2. Создать лид с привязкой к контакту
        3. Добавить примечание с историей диалога
        4. Добавить кастомные поля (источник, продукт)
        """
        logger.info(
            "Создание лида для '%s' (источник: %s, создатель: %s)",
            request.user_name,
            request.source,
            user_id or "service",
        )

        contact_id = None

        # Шаг 1: Создать контакт (если есть данные)
        if request.phone or request.email:
            try:
                contact_id = await amocrm_client.create_contact(
                    name=request.user_name,
                    phone=request.phone,
                    email=request.email,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Ошибка создания контакта: %s", str(exc))
                # Продолжаем без контакта

        # Шаг 2: Подготовить кастомные поля
        custom_fields = []

        # Источник лида
        source_map = {
            "telegram": "Telegram Bot",
            "avito": "Avito Messenger",
            "web": "Веб-чат",
        }
        custom_fields.append(
            {
                "field_id": 949903,
                "values": [{"value": source_map.get(request.source, "Неизвестно")}],
            }
        )

        # Продукт (если указан)
        if request.product_interest:
            custom_fields.append(
                {
                    "field_id": 949899,
                    "values": [{"value": request.product_interest}],
                }
            )

        # Шаг 3: Создать лид
        lead_name = f"Заявка от {request.user_name}"
        if request.product_interest:
            lead_name += f" ({request.product_interest})"

        try:
            lead_id = await amocrm_client.create_lead(
                name=lead_name,
                price=request.budget,
                contact_id=contact_id,
                custom_fields=custom_fields,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка создания лида: %s", str(exc))
            return LeadCreateResponse(
                lead_id=0,
                contact_id=contact_id,
                success=False,
                message=f"Ошибка создания лида: {str(exc)}",
            )

        # Шаг 4: Добавить примечание с историей диалога
        if request.conversation_history:
            try:
                await amocrm_client.add_note(
                    entity_id=lead_id,
                    entity_type="leads",
                    text=f"История диалога:\n\n{request.conversation_history}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Не удалось добавить примечание: %s", str(exc))
                # Не критично

        logger.info("✅ Лид создан: lead_id=%d, contact_id=%s", lead_id, contact_id)

        return LeadCreateResponse(
            lead_id=lead_id,
            contact_id=contact_id,
            success=True,
            message="Лид успешно создан в amoCRM",
        )


# Глобальный инстанс
amocrm_service = AmoCRMService()
