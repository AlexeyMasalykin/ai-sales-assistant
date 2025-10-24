# 🪝 Avito Webhook: Настройка и интеграция

**Дата:** 24 октября 2025  
**Статус:** ✅ Настроен и работает

---

## 🎯 Выполнено

### 1. ✅ Webhook зарегистрирован в Avito
- **URL:** `https://smmassistant.online/api/v1/webhooks/avito/messages`
- **Версия:** v3
- **Статус:** Активен

### 2. ✅ Обработчик webhook настроен
**Файл:** `app/api/routes/avito.py` (строка 26)

**Endpoint:** `POST /api/v1/webhooks/avito/messages`

**Функциональность:**
- Принимает входящие события от Avito
- Валидирует подпись (X-Avito-Signature)
- Добавляет события в очередь обработки
- Возвращает статус 200 OK

### 3. ✅ Интеграция с RAG системой
**Файл:** `app/services/avito/handlers.py`

**Изменения:**
- `handle_text_message()` теперь использует RAG для генерации ответов
- Добавлен fallback на статические ответы при ошибках RAG
- Логирование всех этапов обработки

**Пример работы:**
```python
# Входящее сообщение от клиента
message = "Какие продукты вы предлагаете?"

# RAG генерирует ответ на основе базы знаний
answer = await answer_engine.generate_answer(message)

# Ответ отправляется клиенту в Avito
await client.send_message(chat_id, answer)
```

### 4. ✅ Исправлен метод unregister_webhook
**Файл:** `app/services/avito/webhook.py`

**Изменения:**
- Добавлен параметр `webhook_url` (опциональный)
- Автоматическое получение URL из текущей подписки
- Обработка случаев, когда URL не найден

---

## 🔄 Как это работает

```mermaid
graph LR
    A[Клиент в Avito] -->|Отправляет сообщение| B[Avito Messenger]
    B -->|POST webhook| C[/api/v1/webhooks/avito/messages]
    C -->|Добавляет в очередь| D[Message Queue]
    D -->|Worker обрабатывает| E[AvitoWebhookHandler]
    E -->|Запрос к RAG| F[RAG Engine]
    F -->|Поиск в базе знаний| G[PostgreSQL + pgvector]
    G -->|Релевантные документы| F
    F -->|Генерация ответа| H[OpenAI API]
    H -->|Ответ| E
    E -->|Отправка| I[Avito Messenger API]
    I -->|Доставка| A
```

### Детальный процесс:

1. **Клиент отправляет сообщение** в чате Avito
2. **Avito отправляет webhook** на наш endpoint
3. **FastAPI принимает webhook** и валидирует подпись
4. **Сообщение добавляется в очередь** (asyncio.Queue)
5. **Worker берёт сообщение** из очереди
6. **Handler вызывает RAG систему**:
   - Поиск релевантных документов в векторной БД
   - Генерация ответа через OpenAI
7. **Ответ отправляется клиенту** через Avito API
8. **Клиент получает ответ** в реальном времени

---

## 📊 Настройки из .env

```env
# Авито API
AVITO_CLIENT_ID=3YrB26STF-FoBME_mN_1
AVITO_CLIENT_SECRET=...
AVITO_USER_ID=7738787

# Автоответы
AVITO_AUTO_REPLY_ENABLED=true
AVITO_RESPONSE_DELAY_SECONDS=2

# Очередь обработки
AVITO_MAX_QUEUE_SIZE=1000
AVITO_PROCESSING_WORKERS=3
```

---

## 🧪 Тестирование

### Проверка webhook статуса:
```python
from app.services.avito.client import AvitoAPIClient

client = AvitoAPIClient()
status = await client.get_webhook_status()
# {'subscriptions': [{'url': '...', 'version': '3'}]}
```

### Отправка тестового сообщения:
```python
await client.send_message(
    chat_id="u2i-M1ttp84ZUMlWRq6ZjnLSaw",
    text="Тестовое сообщение"
)
```

### Проверка RAG интеграции:
```python
from app.services.rag.answer import answer_engine

answer = await answer_engine.generate_answer("Какие продукты вы предлагаете?")
# Вернёт информацию из базы знаний
```

---

## 🔧 Обслуживание

### Перерегистрация webhook:
```bash
POST /api/v1/avito/webhook/register
{
  "webhook_url": "https://smmassistant.online/api/v1/webhooks/avito/messages"
}
```

### Проверка статуса:
```bash
GET /api/v1/avito/webhook/status
```

### Удаление webhook:
```bash
DELETE /api/v1/avito/webhook/unregister
```

---

## 📝 Обновлённые файлы

1. **app/services/avito/client.py**
   - Обновлены endpoints (v1, v2, v3)
   - Добавлен параметр `user_id` во все методы

2. **app/services/avito/webhook.py**
   - Исправлен метод `unregister_webhook`
   - Добавлена автоматическая подстановка URL

3. **app/services/avito/handlers.py**
   - Интеграция с RAG системой
   - Fallback на статические ответы
   - Улучшенное логирование

4. **app/api/routes/avito.py**
   - Endpoint для приёма webhook (уже был)
   - CRUD операции для управления подписками

---

## ✅ Статус интеграции

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| **Webhook URL** | ✅ Зарегистрирован | v3, активен |
| **Endpoint** | ✅ Работает | `/webhooks/avito/messages` |
| **Авторизация** | ✅ OK | OAuth2 client_credentials |
| **messenger:read** | ✅ OK | Получение чатов |
| **messenger:write** | ✅ OK | Отправка сообщений |
| **RAG интеграция** | ✅ OK | `answer_engine.generate_answer()` |
| **Fallback** | ✅ OK | Статические ответы при ошибках |
| **Queue processing** | ✅ OK | 3 воркера, очередь 1000 |
| **Auto-reply** | ✅ Enabled | Задержка 2 сек |

---

## 🎉 Готово к работе!

Система полностью настроена и готова к обработке входящих сообщений от клиентов в Avito Messenger с использованием RAG системы для генерации умных ответов на основе базы знаний.

**Следующие шаги:**
1. Мониторинг логов для отслеживания работы
2. Анализ качества ответов RAG
3. Настройка метрик и алертов (если нужно)

