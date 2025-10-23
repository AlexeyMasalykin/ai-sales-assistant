"""Генератор документов на основе GPT и шаблонов."""

from __future__ import annotations

from typing import Dict, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.settings import settings
from app.services.documents.templates import template_manager
from app.services.rag.search import document_search


class DocumentGenerator:
    """Генератор документов с помощью GPT"""

    def __init__(self) -> None:
        api_key = settings.openai_api_key
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key.get_secret_value())
        else:
            self.client = None
            logger.warning("OpenAI API key не настроен")

        self.model = "gpt-4o-mini"

    async def generate_price_list(
        self, client_name: str, services: Optional[list[str]] = None
    ) -> str:
        """Генерирует прайс-лист для клиента"""
        logger.info("Генерация прайс-листа для %s", client_name)

        try:
            pricing_docs = await document_search.search(
                "стоимость услуг прайс", limit=2
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка поиска ценовых документов: %s", exc)
            pricing_docs = []

        pricing_info = "\n\n".join(
            [doc["content"] for doc in pricing_docs if "content" in doc]
        )

        prompt = f"""Создай персонализированный прайс-лист для клиента "{client_name}".

ИНФОРМАЦИЯ О ЦЕНАХ:
{pricing_info}

ТРЕБОВАНИЯ:
- Формат: HTML с таблицей
- Включи только релевантные услуги
- Добавь персональное обращение к клиенту
- Укажи сроки действия цен
- Стиль: профессиональный, лаконичный

УСЛУГИ ДЛЯ ВКЛЮЧЕНИЯ: {services if services else "все основные"}

Верни только HTML код без markdown разметки."""

        if not self.client:
            logger.warning("OpenAI клиент не инициализирован, возвращаем stub HTML")
            return "<p>Сервис временно недоступен</p>"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - эксперт по созданию коммерческих документов.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            html = (response.choices[0].message.content or "").strip()
            logger.info("Прайс-лист сгенерирован (%s символов)", len(html))
            return html
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации прайс-листа: %s", exc)
            return "<p>Ошибка генерации документа</p>"

    async def generate_commercial_proposal(self, client_data: Dict) -> str:
        """Генерирует коммерческое предложение"""
        client_name = client_data.get("name", "клиента")
        logger.info("Генерация КП для %s", client_name)

        query = f"услуги {client_data.get('services', 'автоматизация')} кейсы"
        try:
            docs = await document_search.search(query, limit=3)
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка поиска документов для КП: %s", exc)
            docs = []

        context = "\n\n".join(
            [
                f"**{doc.get('title', 'Документ')}**\n{doc.get('content', '')}"
                for doc in docs
                if doc.get("content")
            ],
        )

        prompt = f"""Создай коммерческое предложение для клиента.

ДАННЫЕ КЛИЕНТА:
- Имя: {client_data.get('name', 'Уважаемый клиент')}
- Компания: {client_data.get('company', 'не указана')}
- Интересующие услуги: {client_data.get('services', 'AI автоматизация')}
- Бюджет: {client_data.get('budget', 'не указан')}
- Дополнительно: {client_data.get('notes', '')}

ИНФОРМАЦИЯ О НАШИХ УСЛУГАХ:
{context}

СТРУКТУРА КП:
1. Приветствие и обращение
2. Описание решения под задачи клиента
3. Этапы реализации
4. Стоимость и сроки
5. Кейсы и результаты
6. Призыв к действию

ТРЕБОВАНИЯ:
- Формат: HTML
- Стиль: профессиональный, убедительный
- Длина: 800-1200 слов
- Персонализация под клиента
- Конкретные цифры и сроки

Верни только HTML код."""

        if not self.client:
            logger.warning("OpenAI клиент не инициализирован, возвращаем stub HTML")
            return "<p>Сервис временно недоступен</p>"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - эксперт по созданию продающих коммерческих предложений.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=3000,
            )
            html = (response.choices[0].message.content or "").strip()
            logger.info("КП сгенерировано (%s символов)", len(html))
            return html
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации КП: %s", exc)
            return "<p>Ошибка генерации документа</p>"

    async def generate_contract_draft(self, client_data: Dict) -> str:
        """Генерирует черновик договора"""
        logger.info("Генерация черновика договора для %s", client_data.get("name"))

        prompt = f"""Создай черновик договора на оказание услуг по автоматизации.

ДАННЫЕ:
- Заказчик: {client_data.get('name', 'ООО "Клиент"')}
- ИНН: {client_data.get('inn', '___________')}
- Услуги: {client_data.get('services', 'AI автоматизация')}
- Стоимость: {client_data.get('price', '__________')} руб.
- Срок: {client_data.get('timeline', '___ месяцев')}

ТРЕБОВАНИЯ:
- Стандартная структура договора
- Предмет договора
- Права и обязанности сторон
- Стоимость и порядок оплаты
- Сроки
- Ответственность
- Заключительные положения

Формат: HTML, юридически корректный язык.
Верни только HTML код."""

        if not self.client:
            logger.warning("OpenAI клиент не инициализирован, возвращаем stub HTML")
            return "<p>Сервис временно недоступен</p>"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - юрист, специализирующийся на IT-договорах.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            html = (response.choices[0].message.content or "").strip()
            logger.info("Черновик договора сгенерирован (%s символов)", len(html))
            return html
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации договора: %s", exc)
            return "<p>Ошибка генерации документа</p>"

    async def render_from_template(self, template_name: str, context: Dict) -> str:
        """Рендерит документ по готовому шаблону."""
        logger.info("Рендер документа из шаблона %s", template_name)
        try:
            return template_manager.render_template(template_name, context)
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка рендеринга шаблона %s: %s", template_name, exc)
            return "<p>Ошибка генерации документа</p>"


# Singleton
document_generator = DocumentGenerator()
