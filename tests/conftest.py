"""Pytest configuration."""

import os
import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# После настройки sys.path импортируем остальные модули
import pytest  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

from app.core.database import close_engine  # noqa: E402


# ========== Проверка секретов ==========

def has_avito_secrets() -> bool:
    """Проверяет наличие Avito API секретов."""
    return bool(
        os.getenv("AVITO_CLIENT_ID") and os.getenv("AVITO_CLIENT_SECRET")
    )


def has_telegram_secrets() -> bool:
    """Проверяет наличие Telegram Bot токена."""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN"))


# ========== Маркеры для pytest ==========

skip_without_avito = pytest.mark.skipif(
    not has_avito_secrets(),
    reason="Avito secrets not configured. Set AVITO_CLIENT_ID and AVITO_CLIENT_SECRET",
)

skip_without_telegram = pytest.mark.skipif(
    not has_telegram_secrets(),
    reason="Telegram secrets not configured. Set TELEGRAM_BOT_TOKEN",
)

# Флаг, указывающий, загружены ли документы в БД
_documents_loaded = False


@pytest.fixture(autouse=True)
async def _dispose_sqlalchemy_engine_after_test():
    """Автоматически сбрасывает пул соединений SQLAlchemy после каждого теста.

    Это предотвращает переиспользование соединений между разными event loop
    (pytest-asyncio создаёт новый loop на каждый тест при scope=function),
    что устраняет ошибку asyncpg: 'Future attached to a different loop'.
    """
    yield
    try:
        await close_engine()
    except Exception:
        # В тестах игнорируем ошибки закрытия, чтобы не фейлить сьют
        pass


@pytest.fixture()
async def mock_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Асинхронный мок Redis-клиента, подменяющий app.core.cache.redis_client."""
    mock = AsyncMock()
    # Часто используемые методы: get/set/setex/ttl/incr/expire/ping
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=0)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.ping = AsyncMock(return_value=True)
    mock.rpush = AsyncMock(return_value=0)
    mock.lrange = AsyncMock(return_value=[])

    monkeypatch.setattr("app.core.cache.redis_client", mock)
    # chat_session импортирует redis_client из app.core.cache, патчить не нужно
    return mock


@pytest.fixture()
async def fake_redis(monkeypatch: pytest.MonkeyPatch):
    """Использует fakeredis - полнофункциональную in-memory имитацию Redis."""
    import fakeredis.aioredis
    
    # Создаем fake Redis клиент
    fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    # Подменяем глобальный redis_client
    monkeypatch.setattr("app.core.cache.redis_client", fake_client)
    
    yield fake_client
    
    # Очистка после теста
    await fake_client.flushall()
    await fake_client.aclose()


@pytest.fixture(scope="function")
async def load_knowledge_base():
    """Загружает документы базы знаний перед RAG тестами."""
    global _documents_loaded

    # Загружаем документы только один раз за весь прогон тестов
    if not _documents_loaded:
        try:
            from app.services.rag.loader import document_loader
            from loguru import logger

            logger.info("Загрузка документов базы знаний для тестов...")
            stats = await document_loader.load_all_documents()
            logger.info(f"Загружено документов: {stats}")
            _documents_loaded = True
        except Exception as e:
            from loguru import logger

            logger.error(f"Ошибка загрузки документов: {e}")
            # Не фейлим тест, если документы не загрузились
            pass

    yield
