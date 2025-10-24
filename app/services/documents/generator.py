"""Генератор документов на основе GPT и шаблонов."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.settings import settings
from app.core.pricing_rules import get_all_tariffs, ProductType
from app.services.documents.templates import template_manager
from app.services.rag.search import document_search
from app.services.pdf.generator import pdf_generator


def clean_html_from_markdown(html: str) -> str:
    """
    Удаляет markdown обёртки из HTML, если GPT их добавил.

    GPT иногда возвращает HTML в markdown блоках:
    ```html
    <html>...</html>
    ```

    Эта функция очищает такие обёртки.
    """
    html = html.strip()

    # Удаляем открывающий блок
    if html.startswith("```html"):
        html = html[7:]
    elif html.startswith("```"):
        html = html[3:]

    # Удаляем закрывающий блок
    if html.endswith("```"):
        html = html[:-3]

    return html.strip()


class DocumentGenerator:
    """Генератор документов с помощью GPT"""

    def __init__(self) -> None:
        self.client: Optional[AsyncOpenAI]
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

        if not self.client:
            logger.debug("Используется оффлайн генерация прайс-листа.")
            return self._generate_price_list_fallback(client_name, services)

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
            html = clean_html_from_markdown(response.choices[0].message.content or "")
            logger.info("Прайс-лист сгенерирован (%s символов)", len(html))
            return html
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации прайс-листа: %s", exc)
            return "<p>Ошибка генерации документа</p>"

    async def generate_commercial_proposal(self, client_data: Dict) -> str:
        """Генерирует коммерческое предложение"""
        client_name = client_data.get("name", "клиента")
        logger.info("Генерация КП для %s", client_name)

        if not self.client:
            logger.debug("Оффлайн генерация коммерческого предложения.")
            return self._generate_commercial_proposal_fallback(client_data)

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

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты - эксперт по созданию продающих "
                            "коммерческих предложений."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=3000,
            )
            html = clean_html_from_markdown(response.choices[0].message.content or "")
            logger.info("КП сгенерировано (%s символов)", len(html))
            return html
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации КП: %s", exc)
            return "<p>Ошибка генерации документа</p>"

    async def generate_contract_draft(self, client_data: Dict) -> str:
        """Генерирует черновик договора"""
        logger.info("Генерация черновика договора для %s", client_data.get("name"))

        if not self.client:
            logger.debug("Оффлайн генерация черновика договора.")
            return self._generate_contract_fallback(client_data)

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
            html = clean_html_from_markdown(response.choices[0].message.content or "")
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

    # --- Fallback helpers -------------------------------------------------

    def _generate_price_list_fallback(
        self,
        client_name: str,
        services: Optional[List[str]] = None,
    ) -> str:
        products = {
            "ai-manager": ProductType.AI_MANAGER,
            "ai-analyst": ProductType.AI_ANALYST,
            "ai-lawyer": ProductType.AI_LAWYER,
        }

        normalized = [service.lower() for service in services or []]
        selected: List[ProductType]
        if normalized:
            selected = [
                product
                for key, product in products.items()
                if any(key in value for value in normalized)
            ]
            if not selected:
                selected = list(products.values())
        else:
            selected = list(products.values())

        all_tariffs = get_all_tariffs()
        rows: List[str] = []
        for product in selected:
            for tariff in all_tariffs.get(product, []):
                price = (
                    "По запросу"
                    if tariff.is_enterprise
                    else f"{tariff.price_monthly:,}".replace(",", " ") + " ₽/мес"
                )
                features = ", ".join(tariff.features)
                rows.append(
                    "<tr>"
                    f"<td>{tariff.name}</td>"
                    f"<td>{product.value}</td>"
                    f"<td>{price}</td>"
                    f"<td>{features}</td>"
                    "</tr>"
                )

        if not rows:
            rows.append(
                "<tr><td>Индивидуально</td><td>Комплексное решение</td><td>По запросу</td><td>Подбор под задачи клиента</td></tr>"
            )

        rows_html = "".join(rows)
        return (
            "<html><head><meta charset='UTF-8'><title>Прайс-лист</title>"
            "<style>body{font-family:Arial,sans-serif;padding:24px;}h1{color:#2c3e50;}"
            "table{width:100%;border-collapse:collapse;margin-top:16px;}"
            "th,td{border:1px solid #e0e0e0;padding:10px;text-align:left;}"
            "th{background:#f5f5f5;}</style></head><body>"
            f"<h1>Персональный прайс-лист для {client_name}</h1>"
            "<p>Это ориентировочный расчёт. Финальная стоимость зависит от объёма внедрения и требуемых интеграций.</p>"
            "<table><tr><th>Тариф</th><th>Продукт</th><th>Стоимость</th><th>Основные функции</th></tr>"
            f"{rows_html}</table>"
            "<p><strong>Дополнительные услуги:</strong> внедрение от 80 000 ₽, интеграция с CRM от 30 000 ₽, обучение от 15 000 ₽ в день.</p>"
            "<p>Напишите, какие задачи стоят перед вами — подготовим детальный расчёт и график внедрения.</p>"
            "</body></html>"
        )

    def _generate_commercial_proposal_fallback(self, client_data: Dict) -> str:
        context = {
            "company_name": client_data.get("company", "вашей компании"),
            "date": date.today().isoformat(),
            "manager_name": "Алексей Смирнов",
            "service_name": client_data.get("services", "AI-решения"),
            "service_description": (
                "Мы предлагаем комплексное внедрение ассистентов, аналитику продаж и"
                " автоматизацию документооборота под задачи вашего бизнеса."
            ),
            "price_items": [
                {
                    "name": "AI-Manager Бизнес",
                    "quantity": "12 мес",
                    "price": "150 000",
                    "total": "1 800 000",
                },
                {
                    "name": "Внедрение и обучение",
                    "quantity": "1",
                    "price": "120 000",
                    "total": "120 000",
                },
            ],
            "total_price": "1 920 000",
        }
        return template_manager.render_template(
            "commercial_proposal_template.html",
            context,
        )

    def _generate_contract_fallback(self, client_data: Dict) -> str:
        context = {
            "contract_number": "0001",
            "contract_date": date.today().strftime("%d.%m.%Y"),
            "executor_representative": "Генеральный директор Петров П.П.",
            "customer_company": client_data.get("name", "ООО Клиент"),
            "customer_inn": client_data.get("inn", "1234567890"),
            "customer_representative": "Директор Сидоров С.С.",
            "customer_authority": "Устава",
            "products": [
                {
                    "name": client_data.get("services", "AI-решения"),
                    "tariff": "Корпоративный",
                    "period": client_data.get("timeline", "12 месяцев"),
                    "price": client_data.get("price", "500000"),
                }
            ],
            "services": [],
            "discounts": False,
            "total_discount": "0",
            "total_price": client_data.get("price", "500000"),
            "implementation_period": client_data.get("timeline", "3 месяца"),
            "contract_end_date": "31.12." + date.today().strftime("%Y"),
            "customer_address": client_data.get("address", "Москва, ул. Пример"),
            "generation_date": date.today().strftime("%d.%m.%Y"),
        }
        return template_manager.render_template("contract_template.html", context)

    async def generate_price_list_pdf(
        self, client_name: str, services: Optional[list[str]] = None
    ) -> tuple[bytes, Optional[str]]:
        """
        Генерирует прайс-лист в формате PDF.

        Returns:
            Кортеж (PDF в байтах, путь к сохранённому файлу)
        """
        html = await self.generate_price_list(client_name, services)
        pdf_bytes, file_path = pdf_generator.generate_with_template(
            html, "price_list", client_name, save_to_disk=True
        )
        return pdf_bytes, str(file_path) if file_path else None

    async def generate_commercial_proposal_pdf(
        self, client_data: Dict
    ) -> tuple[bytes, Optional[str]]:
        """
        Генерирует коммерческое предложение в формате PDF.

        Returns:
            Кортеж (PDF в байтах, путь к сохранённому файлу)
        """
        html = await self.generate_commercial_proposal(client_data)
        client_name = client_data.get("name", "client")
        pdf_bytes, file_path = pdf_generator.generate_with_template(
            html, "commercial_proposal", client_name, save_to_disk=True
        )
        return pdf_bytes, str(file_path) if file_path else None

    async def generate_contract_draft_pdf(
        self, client_data: Dict
    ) -> tuple[bytes, Optional[str]]:
        """
        Генерирует черновик договора в формате PDF.

        Returns:
            Кортеж (PDF в байтах, путь к сохранённому файлу)
        """
        html = await self.generate_contract_draft(client_data)
        client_name = client_data.get("name", "client")
        pdf_bytes, file_path = pdf_generator.generate_with_template(
            html, "contract", client_name, save_to_disk=True
        )
        return pdf_bytes, str(file_path) if file_path else None


# Singleton
document_generator = DocumentGenerator()
