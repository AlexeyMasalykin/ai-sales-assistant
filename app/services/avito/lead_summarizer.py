"""Генерация саммари диалога и рекомендаций для менеджера."""
from __future__ import annotations

from loguru import logger
from openai import AsyncOpenAI

from app.core.settings import settings
from app.models.conversation import ConversationContext
from app.services.avito.prompt_loader import PromptLoader


class LeadSummarizer:
    """Генерирует саммари и рекомендации."""

    def __init__(self):
        self.client: AsyncOpenAI | None = None
        api_key = (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else None
        )
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)

        self.prompt_loader = PromptLoader(
            settings.prompts_dir or "app/services/avito/prompts"
        )

    async def generate_summary(self, context: ConversationContext) -> str:
        """Генерировать саммари диалога."""
        if not self.client:
            return self._fallback_summary(context)

        try:
            system, user = self.prompt_loader.get_prompt(
                "summarization.poml",
                "conversation_summary",
                conversation_history=context.get_history_text(),
                user_name=context.user_name or "",
                phone=context.phone or "",
                email=context.email or "",
                pain_point=context.pain_point or "",
                product_interest=context.product_interest or "",
            )

            response = await self.client.chat.completions.create(
                model=settings.openai_summarization_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

            return (
                response.choices[0].message.content
                or self._fallback_summary(context)
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка генерации саммари: {exc}")
            return self._fallback_summary(context)

    async def generate_recommendations(self, context: ConversationContext) -> str:
        """Генерировать рекомендации менеджеру."""
        if not self.client:
            return self._fallback_recommendations(context)

        try:
            system, user = self.prompt_loader.get_prompt(
                "summarization.poml",
                "manager_recommendations",
                user_name=context.user_name or "",
                pain_point=context.pain_point or "",
                product_interest=context.product_interest or "",
                conversation_history=context.get_history_text(),
                lead_temperature="Тёплый",
            )

            response = await self.client.chat.completions.create(
                model=settings.openai_summarization_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

            return (
                response.choices[0].message.content
                or self._fallback_recommendations(context)
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка генерации рекомендаций: {exc}")
            return self._fallback_recommendations(context)

    def _fallback_summary(self, context: ConversationContext) -> str:
        """Fallback саммари."""
        return f"""
САММАРИ ДИАЛОГА

👤 Клиент: {context.user_name or "Не указано"}
📞 Телефон: {context.phone or "Не указан"}

🎯 ОСНОВНАЯ БОЛЬ:
{context.pain_point or "Не выявлена"}

💡 ИНТЕРЕС К ПРОДУКТУ:
{context.product_interest or "Не определён"}

🌡️ ТЕМПЕРАТУРА ЛИДА: Тёплый
Клиент оставил контакты, готов к диалогу.
"""

    def _fallback_recommendations(self, context: ConversationContext) -> str:
        """Fallback рекомендации."""
        return f"""
РЕКОМЕНДАЦИИ МЕНЕДЖЕРУ

🎯 ГЛАВНЫЙ ФОКУС ЗВОНКА:
Обсудить проблему: {context.pain_point or "не выявлена"}

💬 OPENING:
"Добрый день, {context.user_name}! Вы оставили заявку на {context.product_interest or 'автоматизацию'}.
Удобно сейчас поговорить?"

🚀 СЛЕДУЮЩИЕ ШАГИ:
- Запланировать демонстрацию
- Отправить презентацию
"""


lead_summarizer = LeadSummarizer()
