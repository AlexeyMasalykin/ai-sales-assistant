"""Общие фикстуры для интеграционных тестов Avito."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_redis():
    """Возвращает замоканный Redis клиент."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=3_600)
    redis.delete = AsyncMock(return_value=True)
    redis.expire = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    redis.aclose = AsyncMock(return_value=True)
    return redis


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch: pytest.MonkeyPatch, mock_redis: AsyncMock):
    """Патчит Redis клиент во всех релевантных модулях."""
    monkeypatch.setattr("app.core.cache.redis_client", mock_redis)
    monkeypatch.setattr("app.services.avito.auth.redis_client", mock_redis)
    monkeypatch.setattr("app.services.avito.sync.redis_client", mock_redis)
    yield mock_redis


@pytest.fixture
def mock_avito_api():
    """Возвращает замоканный Avito API клиент."""
    api = AsyncMock()
    api.send_message = AsyncMock(return_value={"status": "sent"})
    api.get_items = AsyncMock(return_value=[])
    api.get_item_stats = AsyncMock(return_value={"views": 0, "contacts": 0})
    return api


@pytest.fixture
def sample_webhook_payload() -> dict[str, object]:
    """Пример payload от Avito webhook."""
    return {
        "event_type": "message.new",
        "payload": {
            "chat_id": "test_chat",
            "message": {
                "id": "msg_id",
                "text": "Test message",
                "author_id": "user_id",
                "created_at": "2025-10-21T12:00:00Z",
            },
        },
    }
