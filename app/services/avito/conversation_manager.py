"""Управление FSM диалога и контекстом."""
from __future__ import annotations

import json
from datetime import datetime

from loguru import logger

from app.core.redis_client import get_redis_client
from app.core.settings import settings
from app.models.conversation import (
    ConversationContext,
    ConversationMetadata,
    ConversationState,
    MessageRole,
)
from app.services.avito.data_extractors import (
    NameExtractor,
    NeedExtractor,
    PhoneExtractor,
)
from app.services.avito.lead_summarizer import LeadSummarizer
from app.services.avito.prompt_loader import PromptLoader


class AvitoConversationManager:
    """Управляет FSM диалога и контекстом."""

    def __init__(self):
        self.name_extractor = NameExtractor()
        self.phone_extractor = PhoneExtractor()
        self.need_extractor = NeedExtractor()
        self.summarizer = LeadSummarizer()
        self.prompt_loader = PromptLoader(
            settings.prompts_dir or "app/services/avito/prompts"
        )
        self.context_ttl = settings.avito_conversation_ttl

    async def handle_message(self, chat_id: str, message: str) -> str:
        """
        Главная точка входа для обработки сообщения.

        Логика:
        1. Загрузить контекст из Redis
        2. Попытаться извлечь данные (имя, телефон, боль)
        3. Обновить контекст
        4. Определить текущее состояние FSM
        5. Сгенерировать ответ в зависимости от состояния
        6. Сохранить контекст в Redis
        7. Вернуть ответ
        """
        context = await self.get_context(chat_id)
        context.add_message(MessageRole.USER, message)
        await self._try_extract_data(context, message)
        await self._update_state(context)
        bot_response = await self._generate_response(context, message)
        context.add_message(MessageRole.BOT, bot_response)
        await self.save_context(context)

        if context.state == ConversationState.PHONE_COLLECTED:
            await self._create_lead(context)
            context.state = ConversationState.QUALIFIED
            await self.save_context(context)

        return bot_response

    async def _try_extract_data(
        self,
        context: ConversationContext,
        message: str,
    ) -> None:
        """Попытаться извлечь данные из сообщения."""
        if not context.user_name:
            name_result = await self.name_extractor.extract(message)
            if name_result.value and name_result.confidence >= settings.name_extraction_threshold:
                context.user_name = name_result.value
                logger.info(
                    "Avito: имя извлечено для %s: %s (confidence: %.2f)",
                    context.chat_id,
                    name_result.value,
                    name_result.confidence,
                )

        if not context.phone:
            phone_result = await self.phone_extractor.extract(message)
            if phone_result.value and phone_result.confidence >= settings.phone_extraction_threshold:
                context.phone = phone_result.value
                logger.info(
                    "Avito: телефон извлечён для %s: %s",
                    context.chat_id,
                    phone_result.value,
                )

        if not context.pain_point:
            history = context.get_history_text(last_n=5)
            need_result = await self.need_extractor.extract(history, message)

            if (
                need_result.value
                and need_result.confidence >= settings.need_extraction_threshold
            ):
                data = json.loads(need_result.value)
                context.pain_point = data.get("pain_point")
                context.product_interest = data.get("product_interest")
                logger.info(
                    "Avito: потребность определена для %s: %s",
                    context.chat_id,
                    context.pain_point,
                )

    async def _update_state(self, context: ConversationContext) -> None:
        """Обновить состояние FSM на основе собранных данных."""
        if context.state == ConversationState.START:
            context.state = ConversationState.GREETING
        elif context.state == ConversationState.GREETING:
            if context.user_name:
                context.state = ConversationState.NAME_COLLECTED
        elif context.state == ConversationState.NAME_COLLECTED:
            if context.pain_point:
                context.state = ConversationState.NEED_IDENTIFIED
        elif context.state == ConversationState.NEED_IDENTIFIED:
            if context.phone:
                context.state = ConversationState.PHONE_COLLECTED

    async def _generate_response(
        self,
        context: ConversationContext,
        user_message: str,
    ) -> str:
        """Сгенерировать ответ в зависимости от состояния."""
        if context.state == ConversationState.QUALIFIED:
            return await self._generate_qualified_response(context, user_message)

        prompt_key = self._get_prompt_key_for_state(context.state)

        try:
            from openai import AsyncOpenAI

            api_key = (
                settings.openai_api_key.get_secret_value()
                if settings.openai_api_key
                else None
            )
            if not api_key:
                logger.warning("OpenAI API ключ не задан, используется fallback")
                return self._get_fallback_response(context.state, user_message)

            client = AsyncOpenAI(api_key=api_key)

            system, user = self.prompt_loader.get_prompt(
                "conversation.poml",
                prompt_key,
                user_name=context.user_name or "",
                user_message=user_message,
                conversation_history=context.get_history_text(),
                pain_point=context.pain_point or "",
                product_interest=context.product_interest or "",
            )

            response = await client.chat.completions.create(
                model=settings.openai_conversation_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.7,
            )

            return response.choices[0].message.content or "Извините, произошла ошибка"

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка генерации ответа: {exc}")
            return self._get_fallback_response(context.state, user_message)

    def _get_prompt_key_for_state(self, state: ConversationState) -> str:
        """Получить ключ промпта для состояния."""
        mapping = {
            ConversationState.GREETING: "greeting",
            ConversationState.NAME_COLLECTED: "name_collected",
            ConversationState.NEED_IDENTIFIED: "need_identified",
            ConversationState.PHONE_COLLECTED: "qualified",
        }
        return mapping.get(state, "greeting")

    async def _generate_qualified_response(
        self,
        context: ConversationContext,
        user_message: str,
    ) -> str:
        """Генерировать ответ через RAG с персонализацией."""
        try:
            from app.services.rag.answer import answer_generator
            from app.services.avito.lead_service import avito_lead_service

            amocrm_history = (
                await avito_lead_service.get_conversation_history_from_amocrm(
                    context.chat_id
                )
            )

            answer = await answer_generator.generate_answer_with_context(
                question=user_message,
                user_name=context.user_name or "Клиент",
                context=None,
                amocrm_history=amocrm_history,
                platform="avito",
            )

            if context.user_name and not answer.startswith(context.user_name):
                answer = f"{context.user_name}, {answer}"

            return answer

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка RAG ответа: {exc}")
            return "Спасибо за вопрос! Специалист ответит вам в ближайшее время."

    def _get_fallback_response(
        self,
        state: ConversationState,
        message: str,  # noqa: ARG002 - для совместимости
    ) -> str:
        """Fallback ответы если GPT недоступен."""
        if state == ConversationState.GREETING:
            return (
                "Здравствуйте! 👋\n"
                "Я — AI-ассистент по автоматизации бизнеса.\n"
                "Как я могу к вам обращаться?"
            )
        if state == ConversationState.NAME_COLLECTED:
            return (
                "Расскажите, пожалуйста, о вашей ситуации:\n"
                "- Какие задачи хотите решить?\n"
                "- Что сейчас занимает больше всего времени?"
            )
        if state == ConversationState.NEED_IDENTIFIED:
            return (
                "Понимаю вашу ситуацию.\n"
                "Чтобы подготовить индивидуальное предложение, "
                "оставьте, пожалуйста, ваш номер телефона."
            )

        return "Спасибо за сообщение!"

    async def _create_lead(self, context: ConversationContext) -> None:
        """Создать лид в amoCRM с саммари и рекомендациями."""
        try:
            from app.services.avito.lead_service import avito_lead_service

            summary = await self.summarizer.generate_summary(context)
            recommendations = await self.summarizer.generate_recommendations(context)
            conversation_text = context.get_history_text()

            await avito_lead_service.create_lead_from_conversation(
                chat_id=context.chat_id,
                user_name=context.user_name or "Клиент Avito",
                phone=context.phone,
                email=context.email,
                product_interest=context.product_interest,
                pain_point=context.pain_point,
                conversation_context=(
                    f"{conversation_text}\n\n{summary}\n\n{recommendations}"
                ),
            )

            logger.info("✅ Лид создан для Avito чата %s", context.chat_id)

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка создания лида: {exc}")

    async def get_context(self, chat_id: str) -> ConversationContext:
        """Загрузить контекст из Redis."""
        redis = await get_redis_client()
        cache_key = f"avito:conversation:{chat_id}"
        cached = await redis.get(cache_key)

        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode()
            data = json.loads(cached)
            return ConversationContext(**data)

        return ConversationContext(
            chat_id=chat_id,
            state=ConversationState.START,
            metadata=ConversationMetadata(
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        )

    async def save_context(self, context: ConversationContext) -> None:
        """Сохранить контекст в Redis."""
        redis = await get_redis_client()
        cache_key = f"avito:conversation:{context.chat_id}"
        data = context.model_dump_json()
        await redis.setex(cache_key, self.context_ttl, data)


conversation_manager = AvitoConversationManager()
