"""Обработчики команд и сообщений Telegram."""

from __future__ import annotations

from loguru import logger

from app.services.rag.answer import answer_generator


class TelegramHandlers:
    """Командные обработчики Telegram бота."""

    @staticmethod
    async def handle_start(chat_id: int, user_name: str) -> str:
        """Обрабатывает команду /start."""
        logger.info(
            "Telegram: команда /start от %s (chat_id=%s)",
            user_name,
            chat_id,
        )
        return (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            "Я — ИИ-ассистент по автоматизации бизнеса.\n\n"
            "<b>Что я умею:</b>\n"
            "• Консультировать по нашим услугам\n"
            "• Рассчитать стоимость проекта\n"
            "• Подобрать решение под ваши задачи\n"
            "• Ответить на вопросы об автоматизации\n\n"
            "<b>Команды:</b>\n"
            "/help — список команд\n"
            "/services — наши услуги\n"
            "/price — узнать стоимость\n\n"
            "Задавайте вопросы — я отвечу!"
        )

    @staticmethod
    async def handle_help(chat_id: int) -> str:
        """Обрабатывает команду /help."""
        logger.info("Telegram: команда /help от chat_id=%s", chat_id)
        return (
            "📋 <b>Доступные команды:</b>\n\n"
            "/start — приветствие и информация\n"
            "/help — эта справка\n"
            "/services — список наших услуг\n"
            "/price — узнать стоимость\n"
            "/contact — связаться с менеджером\n\n"
            "Или просто напишите ваш вопрос!"
        )

    @staticmethod
    async def handle_services(chat_id: int) -> str:
        """Обрабатывает команду /services."""
        logger.info("Telegram: команда /services от chat_id=%s", chat_id)
        return (
            "🚀 <b>Наши услуги:</b>\n\n"
            "<b>1. ИИ-Менеджер</b>\n"
            "Автоматизация общения с клиентами через ИИ\n"
            "• Avito, Telegram, WhatsApp\n"
            "• Квалификация лидов\n"
            "• От 50,000 ₽\n\n"
            "<b>2. ИИ-Аналитик</b>\n"
            "Анализ данных и прогнозирование\n"
            "• Отчёты по продажам\n"
            "• Прогноз спроса\n"
            "• От 80,000 ₽\n\n"
            "<b>3. ИИ-Документовед</b>\n"
            "Генерация документов\n"
            "• Договоры, КП\n"
            "• Автоматизация документооборота\n"
            "• От 60,000 ₽\n\n"
            "Напишите какая услуга интересует — расскажу подробнее!"
        )

    @staticmethod
    async def handle_price(chat_id: int) -> str:
        """Обрабатывает команду /price."""
        logger.info("Telegram: команда /price от chat_id=%s", chat_id)
        return (
            "💰 <b>Стоимость услуг:</b>\n\n"
            "📦 <b>Старт</b> — от 50,000 ₽\n"
            "• Базовая автоматизация\n"
            "• 1 канал (Avito/Telegram)\n"
            "• Техподдержка 1 месяц\n\n"
            "🚀 <b>Оптимум</b> — от 150,000 ₽\n"
            "• Полная автоматизация\n"
            "• 3 канала\n"
            "• RAG система\n"
            "• Техподдержка 3 месяца\n\n"
            "⭐ <b>Enterprise</b> — индивидуально\n"
            "• Кастомные решения\n"
            "• Интеграции с любыми системами\n"
            "• Приоритетная поддержка\n\n"
            "Расскажите о ваших задачах — подберу оптимальное решение!"
        )

    @staticmethod
    async def handle_text_message(
        chat_id: int,
        text: str,
        user_name: str,
    ) -> str:
        """Обрабатывает текстовые сообщения с помощью RAG."""
        logger.info(
            "Telegram: сообщение от %s (chat_id=%s): %s",
            user_name,
            chat_id,
            text[:50],
        )
        return await answer_generator.generate_answer(text, user_name)
