"""Обработчики команд и сообщений Telegram."""

from __future__ import annotations

from typing import Dict, Optional

from loguru import logger

from app.services.documents.generator import document_generator
from app.services.rag.answer import answer_generator


class TelegramHandlers:
    """Командные обработчики Telegram бота."""

    @staticmethod
    async def handle_start(chat_id: int, user_name: str) -> str:
        """Обрабатывает команду /start."""
        logger.info("Telegram: команда /start от %s (chat_id=%s)", user_name, chat_id)
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
            "/price — узнать стоимость\n"
            "/price_list — персональный прайс\n"
            "/proposal — коммерческое предложение\n\n"
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
            "/price_list — персональный прайс\n"
            "/proposal — коммерческое предложение\n"
            "/contact — связаться с менеджером\n"
            "/cases — наши кейсы\n\n"
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
    async def handle_generate_price(chat_id: int, user_name: str) -> str:
        """Обработчик команды /price_list."""
        logger.info("Генерация прайс-листа для %s (chat_id=%s)", user_name, chat_id)

        html = await document_generator.generate_price_list(client_name=user_name, services=None)

        text = html.replace("<table>", "\n").replace("</table>", "\n")
        text = text.replace("<tr>", "").replace("</tr>", "\n")
        text = text.replace("<td>", " ").replace("</td>", " | ")

        return f"<b>Персональный прайс-лист</b>\n\n{text[:1000]}\n\n💾 Полную версию вышлю файлом."

    @staticmethod
    async def handle_generate_proposal(
        chat_id: int,
        user_name: str,
        company: str = "",
        services: str = "",
    ) -> str:
        """Обработчик команды /proposal."""
        logger.info("Генерация КП для %s (chat_id=%s)", user_name, chat_id)

        client_data: Dict[str, Optional[str]] = {
            "name": user_name,
            "company": company,
            "services": services or "AI автоматизация",
        }

        html = await document_generator.generate_commercial_proposal(client_data)

        return (
            "<b>✅ Коммерческое предложение готово!</b>\n\n"
            f"Создано персональное КП для {company or 'вашей компании'}.\n\n"
            f"📄 Объём: ~{len(html)} символов\n"
            "💾 Отправлю полную версию файлом.\n\n"
            "Хотите обсудить детали? Напишите мне!"
        )

    @staticmethod
    async def handle_contact(chat_id: int, user_name: str) -> str:
        """Обработчик команды /contact."""
        logger.info("Запрос контактов от %s (chat_id=%s)", user_name, chat_id)

        return (
            "📞 <b>Связаться с нами</b>\n\n"
            "<b>Менеджер:</b> Алексей\n"
            "<b>Telegram:</b> @your_manager_username\n"
            "<b>Email:</b> sales@yourcompany.com\n"
            "<b>Телефон:</b> +7 (XXX) XXX-XX-XX\n\n"
            "<b>Или напишите ваш вопрос прямо здесь</b> — "
            "я передам менеджеру, и он свяжется с вами в течение часа!\n\n"
            f"{user_name}, чем могу помочь? 😊"
        )

    @staticmethod
    async def handle_cases(chat_id: int) -> str:
        """Обработчик команды /cases."""
        logger.info("Запрос кейсов от чата %s", chat_id)

        try:
            from app.services.rag.search import document_search  # noqa: WPS433 (local import for async context)

            docs = await document_search.search("кейсы внедрения проекты", limit=1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка поиска кейсов: %s", exc)
            docs = []

        if docs:
            cases_content = docs[0].get("content", "")
            return (
                "🏆 <b>Наши успешные кейсы</b>\n\n"
                f"{cases_content[:800]}...\n\n"
                "Хотите узнать подробнее о любом кейсе?\n"
                "Напишите мне вопрос!"
            )

        return (
            "🏆 <b>Наши кейсы</b>\n\n"
            "У нас есть множество успешных внедрений!\n"
            'Напишите "расскажи про кейсы" и я дам подробную информацию.'
        )

    @staticmethod
    async def handle_unknown_command(chat_id: int, command: str) -> str:
        """Обработчик неизвестных команд."""
        logger.warning("Неизвестная команда: %s от чата %s", command, chat_id)

        return (
            f"❓ Команда <code>{command}</code> не распознана.\n\n"
            "<b>Доступные команды:</b>\n"
            "/help — список всех команд\n"
            "/services — наши услуги\n"
            "/price — узнать стоимость\n"
            "/contact — связаться с менеджером\n\n"
            "Или просто напишите ваш вопрос!"
        )

    @staticmethod
    async def handle_text_message(chat_id: int, text: str, user_name: str) -> str:
        """Обрабатывает текстовые сообщения с помощью RAG."""
        logger.info("Telegram: сообщение от %s (chat_id=%s): %s", user_name, chat_id, text[:50])
        return await answer_generator.generate_answer(text, user_name)
