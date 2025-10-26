"""Обработчики различных типов сообщений Avito."""

from __future__ import annotations

from loguru import logger


class AvitoMessageHandlers:
    """Базовые обработчики входящих сообщений Avito."""

    @staticmethod
    async def handle_text_message(chat_id: str, text: str, author_id: str) -> str:
        """Обрабатывает текстовое сообщение и генерирует ответ через RAG."""
        logger.info(
            "Avito: текстовое сообщение в чате %s от %s: %s",
            chat_id,
            author_id,
            text[:80],
        )

        from app.services.avito.lead_service import avito_lead_service

        amocrm_history = await avito_lead_service.get_conversation_history_from_amocrm(
            chat_id
        )
        if amocrm_history:
            logger.info(
                "📚 Загружена Avito история из amoCRM для chat_id=%s (%s символов)",
                chat_id,
                len(amocrm_history),
            )

        lead_result = None

        if avito_lead_service.should_create_lead(text):
            logger.info("🎯 Обнаружен триггер Avito лида в чате %s", chat_id)
            product_interest = avito_lead_service.extract_product_from_text(text)
            user_name = f"Avito User {author_id[:8]}"

            lead_result = await avito_lead_service.create_lead_from_conversation(
                chat_id=chat_id,
                user_name=user_name,
                product_interest=product_interest,
                conversation_context=(
                    (f"История из amoCRM:\n{amocrm_history}\n\n" if amocrm_history else "")
                    + text
                )[:500],
            )

            if lead_result and lead_result.success:
                logger.info("✅ Автоматический Avito лид создан: lead_id=%s", lead_result.lead_id)

        answer: str

        try:
            from app.services.rag.answer import answer_generator

            if answer_generator.client is None:
                logger.debug(
                    "Avito: RAG недоступен (клиент LLM отсутствует), используем fallback."
                )
                answer = AvitoMessageHandlers._get_fallback_response(text)
            else:
                # Используем generate_answer_with_context для передачи истории отдельно
                user_name = f"Avito User {author_id[:8]}"
                generated_answer = await answer_generator.generate_answer_with_context(
                    question=text,  # Чистый вопрос без истории
                    user_name=user_name,
                    context=None,  # У Avito пока нет сохраненного контекста сессии
                    amocrm_history=amocrm_history if amocrm_history else None,
                )
                if not generated_answer or generated_answer.strip() == "":
                    logger.warning(
                        "RAG не вернул ответ для чата %s, используем fallback", chat_id
                    )
                    answer = AvitoMessageHandlers._get_fallback_response(text)
                else:
                    answer = generated_answer
                    logger.info(
                        "RAG ответ сгенерирован для чата %s (длина: %s)",
                        chat_id,
                        len(answer),
                    )

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации ответа через RAG для чата %s: %s", chat_id, exc)
            answer = AvitoMessageHandlers._get_fallback_response(text)

        if lead_result and lead_result.success and lead_result.lead_id:
            await avito_lead_service.save_conversation_to_amocrm(
                lead_id=lead_result.lead_id,
                user_message=text,
                bot_response=answer,
                qualification=None,
            )

        return answer

    @staticmethod
    def _get_fallback_response(text: str) -> str:
        """Возвращает базовый ответ, если RAG недоступен."""
        text_lower = text.lower()

        if any(word in text_lower for word in ("привет", "здравствуйте", "добрый")):
            return (
                "Здравствуйте! 👋\n\n"
                "Я — ИИ-ассистент по автоматизации бизнеса.\n\n"
                "У нас есть:\n"
                "🤖 ИИ-Менеджер — автоматизация CRM\n"
                "⚖️ ИИ-Юрист — анализ документов\n"
                "📊 ИИ-Аналитик — обработка данных\n\n"
                "Расскажите, какая задача стоит перед вами?"
            )

        if any(
            word in text_lower for word in ("цена", "стоимость", "сколько", "тариф")
        ):
            return (
                "💰 Стоимость зависит от задач и объёма внедрения:\n\n"
                "📦 Старт — от 50 000 ₽\n"
                "🚀 Оптимум — от 150 000 ₽\n"
                "⭐ Enterprise — индивидуально\n\n"
                "Опишите вашу ситуацию, и я подготовлю расчёт!"
            )

        if any(
            word in text_lower
            for word in (
                "контакт",
                "связь",
                "связаться",
                "телефон",
                "email",
                "telegram",
            )
        ):
            return (
                "📞 С нами можно связаться так:\n\n"
                "Telegram: @your_bot\n"
                "Email: sales@example.com\n"
                "Телефон: +7 (XXX) XXX-XX-XX\n\n"
                "Можем продолжить общение и здесь, если удобно!"
            )

        return (
            "Спасибо за сообщение! 🙏\n\n"
            "Я передал его специалисту — он ответит в ближайшее время.\n"
            "Если хотите, задайте дополнительные вопросы прямо сейчас!"
        )

    @staticmethod
    async def handle_image_message(chat_id: str, image_url: str) -> str:
        """Реагирует на сообщение с изображением."""
        logger.info("Avito: получено изображение в чате %s (%s).", chat_id, image_url)
        return (
            "Спасибо за изображение! 📷\n\n"
            "Мы изучим его и вернёмся с ответом в ближайшее время."
        )
