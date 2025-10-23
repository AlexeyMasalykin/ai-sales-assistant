ЗАДАЧА T019: Redis хранение контекста диалогов

⚠️ ВАЖНО: НЕ ТРОГАЙ .env ФАЙЛ!

КОНТЕКСТ:
- T016-T018 завершены ✅
- ChatSessionManager уже есть для веб-чата
- Telegram Bot НЕ использует Redis для контекста
- Нужно унифицировать хранение

ЦЕЛЬ T019:
Создать единую систему хранения контекста диалогов в Redis для Telegram и веб-чата

ПРОБЛЕМА СЕЙЧАС:
- Веб-чат использует ChatSessionManager
- Telegram хранит контекст... нигде (каждое сообщение независимо)
- Нет общего интерфейса

РЕШЕНИЕ:
Расширить ChatSessionManager для поддержки обоих каналов

ОБНОВИТЬ ФАЙЛЫ:

1. app/services/web/chat_session.py (ОБНОВИТЬ)
   Добавить поддержку Telegram:
```python
   class ChatSessionManager:
       """Менеджер сессий для всех каналов (веб-чат + Telegram)"""
       
       def __init__(self):
           self.session_ttl = 60 * 60 * 24 * 30  # 30 дней
           self.session_prefix = "chat:session:"
           self.messages_prefix = "chat:messages:"
           self.telegram_prefix = "telegram:chat:"  # НОВОЕ
       
       async def get_or_create_telegram_session(
           self,
           chat_id: int,
           user_name: str
       ) -> str:
           """Получает или создаёт сессию для Telegram чата"""
           # Проверяем есть ли активная сессия
           session_key = f"{self.telegram_prefix}{chat_id}"
           session_id = await redis_client.get(session_key)
           
           if session_id:
               # Продлеваем TTL
               await self.extend_session(session_id)
               return session_id
           
           # Создаём новую сессию
           session_id = await self.create_session(
               user_name=user_name,
               metadata={"channel": "telegram", "chat_id": chat_id}
           )
           
           # Сохраняем маппинг chat_id -> session_id
           await redis_client.setex(
               session_key,
               self.session_ttl,
               session_id
           )
           
           logger.info(f"Создана Telegram сессия {session_id} для chat_id={chat_id}")
           
           return session_id
       
       async def get_context_for_llm(
           self,
           session_id: str,
           limit: int = 10
       ) -> list[dict]:
           """Получает контекст для LLM в формате OpenAI"""
           messages = await self.get_messages(session_id, limit)
           
           # Конвертируем в формат OpenAI
           context = []
           for msg in messages:
               context.append({
                   "role": msg["role"],
                   "content": msg["content"]
               })
           
           return context
```

2. app/services/telegram/handlers.py (ОБНОВИТЬ)
   Интегрировать с ChatSessionManager:
```python
   from app.services.web.chat_session import session_manager
   
   class TelegramHandlers:
       
       @staticmethod
       async def handle_text_message(
           chat_id: int,
           text: str,
           user_name: str
       ) -> str:
           """Обрабатывает текстовое сообщение с контекстом"""
           logger.info(
               "Telegram: сообщение от %s (chat_id=%s): %s",
               user_name,
               chat_id,
               text[:50]
           )
           
           # Получаем или создаём сессию
           session_id = await session_manager.get_or_create_telegram_session(
               chat_id,
               user_name
           )
           
           # Сохраняем сообщение пользователя
           await session_manager.add_message(session_id, "user", text)
           
           # Получаем контекст последних N сообщений
           context = await session_manager.get_context_for_llm(session_id, limit=5)
           
           # Генерируем ответ с контекстом
           answer = await answer_generator.generate_answer_with_context(
               text,
               user_name,
               context
           )
           
           # Сохраняем ответ
           await session_manager.add_message(session_id, "assistant", answer)
           
           return answer
```

3. app/services/rag/answer.py (ОБНОВИТЬ)
   Добавить метод с контекстом:
```python
   class AnswerGenerator:
       
       async def generate_answer_with_context(
           self,
           question: str,
           user_name: str,
           context: list[dict] | None = None
       ) -> str:
           """Генерирует ответ с учётом контекста диалога"""
           logger.info(
               "Генерация ответа с контекстом для '%s' (история: %d сообщений)",
               question,
               len(context) if context else 0
           )
           
           # RAG поиск документов
           documents = await document_search.search(question, limit=3)
           
           # Формируем контекст из документов
           knowledge_context = "\n\n".join([
               f"Документ: {doc['title']}\n{doc['content'][:500]}"
               for doc in documents
           ])
           
           # Строим промпт с историей
           messages = []
           
           # Системный промпт
           messages.append({
               "role": "system",
               "content": f"""Ты — AI Sales Assistant компании, специализирующейся на AI-решениях.
               
Контекст из базы знаний:
{knowledge_context}

ВАЖНО:
- Отвечай кратко и по делу
- Обращайся к клиенту по имени: {user_name}
- Используй HTML теги: <b>, <i>, <a>
- Если не знаешь — предложи связаться с менеджером
- Сохраняй контекст предыдущих сообщений"""
           })
           
           # Добавляем историю диалога
           if context:
               messages.extend(context)
           
           # Добавляем текущий вопрос
           messages.append({
               "role": "user",
               "content": question
           })
           
           # Генерируем ответ
           response = await openai_client.chat.completions.create(
               model="gpt-4o-mini",
               messages=messages,
               max_tokens=500,
               temperature=0.7
           )
           
           answer = response.choices[0].message.content.strip()
           
           # Гарантируем HTML теги
           if "<b>" not in answer and "<i>" not in answer:
               answer = f"<b>{user_name}</b>, {answer}"
           
           logger.info("Ответ с контекстом сгенерирован (%d символов)", len(answer))
           
           return answer
```

4. tests/integration/test_telegram_context.py (НОВЫЙ)
   Тесты контекста:
```python
   """Тесты Redis контекста для Telegram."""
   import pytest
   from app.services.web.chat_session import session_manager
   from app.services.telegram.handlers import TelegramHandlers
   
   @pytest.mark.asyncio
   async def test_telegram_session_creation():
       """Тест создания Telegram сессии"""
       session_id = await session_manager.get_or_create_telegram_session(
           12345,
           "TestUser"
       )
       
       assert session_id is not None
       assert len(session_id) > 0
       
       # Проверяем что сессия существует
       session = await session_manager.get_session(session_id)
       assert session is not None
       assert session["user_name"] == "TestUser"
       assert session["metadata"]["channel"] == "telegram"
   
   @pytest.mark.asyncio
   async def test_telegram_message_with_context():
       """Тест сохранения контекста"""
       chat_id = 12345
       
       # Первое сообщение
       response1 = await TelegramHandlers.handle_text_message(
           chat_id,
           "Привет, расскажи про ваши услуги",
           "TestUser"
       )
       
       assert len(response1) > 0
       
       # Второе сообщение (должно помнить контекст)
       response2 = await TelegramHandlers.handle_text_message(
           chat_id,
           "А сколько это стоит?",
           "TestUser"
       )
       
       assert len(response2) > 0
       # Ответ должен быть релевантен услугам из первого сообщения
   
   @pytest.mark.asyncio
   async def test_context_retrieval():
       """Тест получения контекста для LLM"""
       session_id = await session_manager.create_session("TestUser")
       
       # Добавляем несколько сообщений
       await session_manager.add_message(session_id, "user", "Сообщение 1")
       await session_manager.add_message(session_id, "assistant", "Ответ 1")
       await session_manager.add_message(session_id, "user", "Сообщение 2")
       
       # Получаем контекст
       context = await session_manager.get_context_for_llm(session_id, limit=10)
       
       assert len(context) == 3
       assert context[0]["role"] == "user"
       assert context[0]["content"] == "Сообщение 1"
```

ТРЕБОВАНИЯ:
- TTL = 30 дней для всех сессий
- Единый интерфейс для веб-чата и Telegram
- Контекст последних N сообщений
- Маппинг chat_id -> session_id для Telegram
- Автосоздание сессий
- Продление TTL при активности
- Формат OpenAI для LLM

ЛОГИРОВАНИЕ:
- INFO: создание сессий, контекст
- DEBUG: добавление сообщений
- ERROR: ошибки Redis

⚠️ КРИТИЧНО:
- НЕ ИЗМЕНЯЙ .env ФАЙЛ!
- Используй существующий redis_client
- TTL = 2592000 секунд (30 дней)
- Все методы async
- Типизация везде
