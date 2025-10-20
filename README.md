# Интеллектуальный ассистент продаж ИИ-услуг

## Обзор
Проект реализует систему ассистента продаж, основанную на FastAPI, с интеграцией LLM, RAG и внешних сервисов (Avito, Telegram, amoCRM, Google Calendar, ЮKassa). Документация и спецификации доступны в каталоге `specs/`.

## Быстрый старт (разработка)
1. Установите зависимости:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
3. Запустите локальные сервисы:
   ```bash
   docker-compose up -d
   ```
4. Выполните миграции БД:
   ```bash
   alembic upgrade head
   ```
5. Запустите приложение:
   ```bash
   uvicorn app.main:app --reload
   ```

## Запуск в контейнерах (prod/staging)
```bash
docker compose -f docker-compose.yml -f deploy/hetzner-compose.yml up -d
```

## Тестирование и проверки
```bash
pytest
black --check .
flake8
mypy app
```

## Структура проекта
- `app/` — исходный код FastAPI
- `specs/` — спецификации и планы
- `migrations/` — миграции Alembic
- `deploy/` — конфигурации для развёртывания
- `nginx/` — настройки reverse proxy
- `.github/workflows/` — CI/CD пайплайны

## Требования
- Python 3.11+
- Docker и Docker Compose
- PostgreSQL и Redis (рекомендуется использовать готовые контейнеры из `docker-compose.yml`)

## Поддержка
Все вопросы, предложения и инциденты фиксируйте в системе трекинга задач или через ответственного менеджера проекта.
