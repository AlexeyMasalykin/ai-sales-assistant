---
description: "Задачи реализации ассистента продаж ИИ-услуг"
---

# Задачи: Интеллектуальный ассистент продаж ИИ-услуг

**Входные артефакты**: `specs/001-ai-sales-assistant/spec.md`, `specs/001-ai-sales-assistant/plan.md`
**Тесты**: указываются в соответствующих историях при необходимости
**Группировка**: задачи объединены по пользовательским историям для независимой реализации и тестирования

## Формат: `[ID] [P?] [Story] Описание`
- **[P]** — задача может выполняться параллельно
- **[Story]** — код истории (INF, US1, US2, US3, US4, US5)
- Описание содержит конкретные пути файлов и ожидаемые артефакты

---

## Фаза 0: Подготовка инфраструктуры (Story: INF, приоритет P0)

- [ ] T001 [INF] Создать каркас приложения FastAPI с файлами `app/main.py`, `app/api/__init__.py`, `app/core/__init__.py`, `app/services/__init__.py`
- [ ] T002 [P] [INF] Настроить контейнеризацию: подготовить `Dockerfile`, `docker-compose.yml`, `nginx/nginx.conf`, `deploy/hetzner-compose.yml`
- [ ] T003 [P] [INF] Сформировать конфигурацию окружения: шаблон `.env.example`, модуль `app/core/config.py`, класс настроек `app/core/settings.py`
- [ ] T004 [INF] Настроить CI/CD пайплайн (GitHub Actions/GitLab CI) в `.github/workflows/ci.yml` для запуска `pytest` и проверок линтера
- [ ] T005 [P] [INF] Подготовить schemata БД: базовая миграция в `migrations/versions/0001_initial.py`, конфигурация Alembic в `alembic.ini`

---

## Фаза 1: Фундаментальные сервисы (Story: INF, приоритет P0)

- [ ] T006 [INF] Реализовать точку входа API: создать `app/main.py` с инициализацией FastAPI, подключением роутеров, middleware CORS и rate limiting
- [ ] T007 [P] [INF] Настроить JWT-аутентификацию: модуль `app/core/security.py`, зависимости `app/core/dependencies.py`, модели токена в `app/models/security.py`
- [ ] T008 [INF] Внедрить логирование через Loguru: конфигурация в `app/core/logging.py`, интеграция с Sentry в `app/core/observability.py`
- [ ] T009 [P] [INF] Реализовать хранилища: подключение PostgreSQL (`app/core/database.py`) и Redis (`app/core/cache.py`) с асинхронными клиентами
- [ ] T010 [INF] Добавить health-check эндпоинты `/health`, `/ready` в `app/api/routes/health.py` и зарегистрировать их в `app/api/__init__.py`

---

## Фаза 2: Пользовательская история US1 — Автоматизация Avito (приоритет P1)

**Цель**: принимать лиды из Avito, вести диалог, обновлять объявления, пересылать обращения в CRM
**Независимая проверка**: прогон интеграционного теста webhooks Avito, подтверждение создания лида с тегом `avito-lead`

- [ ] T011 [US1] Реализовать клиент Avito API в `app/services/avito/client.py` с поддержкой OAuth и обновления токенов
- [ ] T012 [P] [US1] Создать обработчики webhooks Avito в `app/api/routes/avito.py`, включая валидацию подписи
- [ ] T013 [US1] Настроить автоответы и маршрутизацию сообщений Avito → Telegram в `app/services/avito/handlers.py`
- [ ] T014 [P] [US1] Добавить обновление объявлений и расписание синхронизации в `app/services/avito/sync.py`
- [ ] T015 [US1] Написать интеграционный тест webhooks Avito `tests/integration/test_avito_webhook.py` с mock API

---

## Фаза 3: Пользовательская история US2 — Диалоговый ассистент Telegram и сайт (приоритет P1)

**Цель**: обеспечить диалог по Telegram Bot API и чат-виджету сайта с сохранением контекста
**Независимая проверка**: успешные сценарии приветствия, сбора брифа и передачи контекста в Redis

- [ ] T016 [US2] Реализовать Telegram webhook эндпоинт `app/api/routes/telegram.py` с проверкой подписи и JWT
- [ ] T017 [P] [US2] Создать бот-логика: модуль `app/services/telegram/bot.py` (FSM, inline-кнопки, обработка команд)
- [ ] T018 [US2] Реализовать веб-канал: эндпоинты чат-виджета в `app/api/routes/chat.py`, websocket-обработчик в `app/services/web/chat_session.py`
- [ ] T019 [P] [US2] Встроить хранение контекста в Redis через `app/services/session/store.py` с TTL 30 дней
- [ ] T020 [US2] Добавить интеграционный тест Telegram webhook `tests/integration/test_telegram_webhook.py`

---

## Фаза 4: Пользовательская история US3 — RAG, расчёт стоимости и документы (приоритет P1)

**Цель**: предоставлять точные ответы из базы знаний, рассчитывать пакеты и генерировать PDF документы
**Независимая проверка**: unit-тест расчёта стоимости, генерация валидного PDF < 10 МБ, корректные ответы RAG

- [ ] T021 [US3] Настроить пайплайн RAG: модуль `app/services/rag/indexer.py` для pgvector, `app/services/rag/retriever.py` для поиска
- [ ] T022 [P] [US3] Реализовать менеджер LLM провайдеров `app/services/llm/router.py` с fallback GPT-4o-mini → Claude 3.5
- [ ] T023 [US3] Создать сервис расчёта стоимости `app/services/pricing/calculator.py` и конфигурацию коэффициентов в `app/core/pricing_rules.py`
- [ ] T024 [P] [US3] Добавить шаблоны Jinja2 `templates/commercial_offer.html`, `templates/contract.html`, `templates/invoice.html`
- [ ] T025 [US3] Реализовать генерацию PDF через WeasyPrint `app/services/pdf/generator.py` с ограничением `MAX_PDF_SIZE_MB`
- [ ] T026 [P] [US3] Написать unit-тесты расчёта стоимости `tests/unit/test_pricing_calculator.py`
- [ ] T027 [US3] Создать тест генерации PDF `tests/unit/test_pdf_generator.py` с проверкой размера и структуры
- [ ] T028 [US3] Реализовать RAG unit-тесты `tests/unit/test_rag_retriever.py` с использованием фикстур в `tests/fixtures/knowledge_base/`

---

## Фаза 5: Пользовательская история US4 — Интеграция CRM, календаря и оплаты (приоритет P2)

**Цель**: автоматизировать создание лидов, бронирование консультаций и приём платежей
**Независимая проверка**: интеграционный тест `tests/integration/test_sales_pipeline.py` с моками amoCRM, Google Calendar и ЮKassa

- [ ] T029 [US4] Реализовать модуль amoCRM `app/integrations/amocrm/client.py` и сервис создания лида `app/services/crm/amocrm_service.py`
- [ ] T030 [P] [US4] Настроить интеграцию с Google Calendar `app/integrations/google_calendar/client.py`, обработку слотов в `app/services/calendar/scheduler.py`
- [ ] T031 [US4] Внедрить ЮKassa клиент `app/integrations/yookassa/client.py` и сервис генерации ссылок `app/services/payments/yookassa_service.py`
- [ ] T032 [P] [US4] Добавить Email уведомления `app/integrations/email/smtp_client.py`, шаблоны писем в `templates/email/`
- [ ] T033 [US4] Создать интеграционный тест сквозного сценария `tests/integration/test_sales_pipeline.py`

---

## Фаза 6: Пользовательская история US5 — Безопасность, мониторинг и эксплуатация (приоритет P1)

**Цель**: обеспечить соответствие требованиям безопасности, наблюдаемость и устойчивость
**Независимая проверка**: отчёт о прохождении чек-листа безопасности и успешный запуск наблюдаемости

- [ ] T034 [US5] Реализовать шифрование AES-256 для персональных данных в `app/core/crypto.py`, интегрировать в модели `app/models/user.py`, `app/models/lead.py`
- [ ] T035 [P] [US5] Настроить валидацию подписей webhooks (Avito, Telegram, ЮKassa) в `app/core/signature.py` и применить в соответствующих маршрутах
- [ ] T036 [US5] Добавить мониторинг Sentry/Prometheus в `app/core/observability.py`, настроить алерты в `deploy/monitoring/`
- [ ] T037 [P] [US5] Реализовать механизм повторов с экспоненциальной задержкой `app/services/common/retry_policy.py` и подключить к внешним интеграциям
- [ ] T038 [US5] Подготовить документацию по реагированию на инциденты `docs/runbooks/incident-response.md` и чек-лист запуска `docs/runbooks/release-checklist.md`

---

## Фаза 7: Финализация и полировка (глобальные задачи)

- [ ] T039 [P] [INF] Актуализировать `README.md` и `docs/architecture.md` на русском языке
- [ ] T040 [INF] Провести нагрузочные тесты `tests/performance/locustfile.py`, зафиксировать результаты в `docs/reports/performance.md`
- [ ] T041 [P] [INF] Выполнить итоговой аудит безопасности, задокументировать выводы в `docs/reports/security-audit.md`

---

## Зависимости и порядок выполнения
- Фазы 0–1 (Story INF) блокируют все пользовательские истории
- US1, US2, US3 стартуют после завершения фундамента и могут выполняться параллельно при условии синхронизации команд
- US4 зависит от завершения US1–US3 (данные лидов, слоты и документы)
- US5 частично требует готовности интеграций для тестирования подписей и мониторинга
- Финальная фаза выполняется после закрытия критических задач всех историй

---

Документ обновляется по мере прогресса, изменения отмечаются в истории коммитов.
