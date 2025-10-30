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
        5. Если получили телефон - создать лид и сгенерировать подтверждение
        6. Иначе - сгенерировать обычный ответ
        7. Сохранить контекст в Redis
        8. Вернуть ответ
        """
        context = await self.get_context(chat_id)
        context.add_message(MessageRole.USER, message)
        
        # Запоминаем старое состояние
        old_state = context.state
        
        await self._try_extract_data(context, message)
        await self._update_state(context)
        
        # Если только что получили телефон - создаем лид и даем специальный ответ
        if old_state != ConversationState.PHONE_COLLECTED and context.state == ConversationState.PHONE_COLLECTED:
            # Запускаем создание лида в фоне (не ждем)
            import asyncio
            asyncio.create_task(self._create_lead(context))
            
            context.state = ConversationState.QUALIFIED
            
            # Специальный ответ-подтверждение (отправляется сразу!)
            bot_response = (
                f"Спасибо, {context.user_name}! ✅\n\n"
                f"Я передал вашу заявку специалисту по {context.product_interest or 'автоматизации'} — "
                f"он свяжется с вами в течение часа.\n\n"
                f"Если у вас есть вопросы, я могу ответить прямо сейчас! 😊"
            )
        else:
            # Обычный ответ
            bot_response = await self._generate_response(context, message)
        
        context.add_message(MessageRole.BOT, bot_response)
        await self.save_context(context)

        return bot_response

    async def _try_extract_data(
        self,
        context: ConversationContext,
        message: str,
    ) -> None:
        """Попытаться извлечь данные из сообщения (параллельно для скорости)."""
        import asyncio
        import time
        
        # Собираем задачи для параллельного выполнения
        tasks = []
        skipped = []
        
        if not context.user_name:
            tasks.append(("name", self.name_extractor.extract(message)))
        else:
            skipped.append("name")

        if not context.phone:
            tasks.append(("phone", self.phone_extractor.extract(message)))
        else:
            skipped.append("phone")

        if not context.pain_point:
            history = context.get_history_text(last_n=5)
            tasks.append(("need", self.need_extractor.extract(history, message)))
        else:
            skipped.append("need")
        
        # Логируем пропущенные извлечения для оптимизации
        if skipped:
            logger.info(
                "Avito: пропущены извлечения для %s: %s (уже есть)",
                context.chat_id,
                ", ".join(skipped)
            )
        
        # Выполняем все запросы параллельно
        if tasks:
            task_types = [t[0] for t in tasks]
            task_coroutines = [t[1] for t in tasks]
            
            logger.info(
                "Avito: запуск %d параллельных извлечений для %s: %s",
                len(task_types),
                context.chat_id,
                ", ".join(task_types)
            )
            start_time = time.time()
            results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            elapsed = time.time() - start_time
            logger.info(
                "Avito: параллельные извлечения завершены за %.2f сек",
                elapsed
            )
            
            # Обрабатываем результаты
            for task_type, result in zip(task_types, results):
                if isinstance(result, Exception):
                    logger.error(f"Ошибка извлечения {task_type}: {result}")
                    continue
                
                if task_type == "name":
                    if result.value and result.confidence >= settings.name_extraction_threshold:
                        context.user_name = result.value
                        logger.info(
                            "Avito: имя извлечено для %s: %s (confidence: %.2f)",
                            context.chat_id,
                            result.value,
                            result.confidence,
                        )
                
                elif task_type == "phone":
                    if result.value and result.confidence >= settings.phone_extraction_threshold:
                        context.phone = result.value
                        logger.info(
                            "Avito: телефон извлечён для %s: %s",
                            context.chat_id,
                            result.value,
                        )
                
                elif task_type == "need":
                    if (
                        result.value
                        and result.confidence >= settings.need_extraction_threshold
            ):
                        data = json.loads(result.value)
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
            # Гибкий переход: если есть потребность - можно перейти к NEED_IDENTIFIED даже без имени
            if context.pain_point:
                context.state = ConversationState.NEED_IDENTIFIED
                logger.info(
                    "Avito: переход GREETING -> NEED_IDENTIFIED (потребность определена без имени)"
                )
            elif context.user_name:
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
        import time
        
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

            logger.info(
                "Avito: генерация ответа для %s (state=%s, prompt=%s)",
                context.chat_id,
                context.state.value,
                prompt_key
            )
            start_time = time.time()

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
            )

            elapsed = time.time() - start_time
            logger.info(
                "Avito: ответ сгенерирован за %.2f сек (модель: %s)",
                elapsed,
                settings.openai_conversation_model
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
        """Генерировать ответ через промпт qualified с RAG контекстом."""
        try:
            from app.services.rag.search import document_search
            from openai import AsyncOpenAI

            # Ищем релевантные документы через RAG (limit=1 для скорости, кэш ускоряет)
            documents = await document_search.search(user_message, limit=1)
            rag_context = "\n\n".join(
                f"📄 {doc['title']}:\n{doc['content'][:300]}"
                for doc in documents
            ) if documents else "Информация не найдена в базе знаний."

            # Используем промпт qualified из conversation.poml
            api_key = (
                settings.openai_api_key.get_secret_value()
                if settings.openai_api_key
                else None
            )
            if not api_key:
                return "Спасибо за вопрос! Специалист ответит вам в ближайшее время."

            client = AsyncOpenAI(api_key=api_key)

            system, user = self.prompt_loader.get_prompt(
                "conversation.poml",
                "qualified",
                user_name=context.user_name or "Клиент",
                phone=context.phone or "",
                product_interest=context.product_interest or "",
                user_message=user_message,
                rag_context=rag_context,
            )

            response = await client.chat.completions.create(
                model=settings.openai_conversation_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

            return response.choices[0].message.content or "Извините, произошла ошибка"

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка генерации qualified ответа: {exc}")
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

