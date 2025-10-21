"""Обработчики различных типов сообщений Avito."""

from __future__ import annotations

from loguru import logger


class AvitoMessageHandlers:
    """Базовые обработчики входящих сообщений Avito."""

    @staticmethod
    async def handle_text_message(chat_id: str, text: str, author_id: str) -> str:
        """Обрабатывает текстовое сообщение и возвращает ответ."""
        logger.info(
            "Avito: текстовое сообщение в чате %s от %s: %s",
            chat_id,
            author_id,
            text[:80],
        )
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
