"""Интеграционные тесты webhook Avito."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Возвращает TestClient с заглушенными зависимостями старта/остановки."""

    async def noop() -> None:
        return None

    monkeypatch.setattr("app.main.bootstrap_runtime", noop)
    monkeypatch.setattr("app.main.shutdown_runtime", noop)

    with TestClient(app) as client:
        yield client


def test_webhook_endpoint_receives_message(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient
) -> None:
    """Webhook принимает сообщение и отвечает OK."""
    validate_mock = AsyncMock(return_value=True)
    queue_mock = AsyncMock()
    monkeypatch.setattr(
        "app.api.routes.avito.webhook_handler.validate_signature", validate_mock
    )
    monkeypatch.setattr("app.api.routes.avito.webhook_handler.add_to_queue", queue_mock)

    payload = {
        "event_type": "message.new",
        "payload": {
            "chat_id": "test_chat_123",
            "message": {
                "id": "msg_456",
                "text": "Привет!",
                "author_id": "user_789",
                "created_at": "2025-10-21T12:00:00Z",
            },
        },
    }

    response = test_client.post("/api/v1/webhooks/avito/messages", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    validate_mock.assert_awaited()
    queue_mock.assert_awaited_with(payload)


def test_webhook_endpoint_fast_response(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient
) -> None:
    """Ответ на webhook возвращается быстрее одной секунды."""
    monkeypatch.setattr(
        "app.api.routes.avito.webhook_handler.validate_signature",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.api.routes.avito.webhook_handler.add_to_queue",
        AsyncMock(),
    )

    payload = {"event_type": "test"}

    start = time.time()
    response = test_client.post("/api/v1/webhooks/avito/messages", json=payload)
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 1.0


def test_webhook_signature_validation(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient
) -> None:
    """Неверная подпись приводит к отказу 403."""
    monkeypatch.setattr(
        "app.api.routes.avito.webhook_handler.validate_signature",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.api.routes.avito.webhook_handler.add_to_queue",
        AsyncMock(),
    )

    response = test_client.post(
        "/api/v1/webhooks/avito/messages", json={"event_type": "test"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid signature"
