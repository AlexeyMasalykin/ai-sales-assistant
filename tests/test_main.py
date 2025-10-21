"""Базовые тесты для проверки работы приложения."""

import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# noqa: E402 - импорты после настройки путей
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_root_endpoint() -> None:
    """Тест корневого endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "message" in data
