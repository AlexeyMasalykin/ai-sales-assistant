"""Интеграционные тесты синхронизации Avito."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.avito.sync import AvitoSyncManager


@pytest.mark.asyncio
async def test_sync_manager_start_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет запуск и остановку фоновой синхронизации."""
    manager = AvitoSyncManager()
    monkeypatch.setattr(manager, "sync_all_items", AsyncMock(return_value={}))

    await manager.start_sync(interval_minutes=1)
    await asyncio.sleep(0)

    assert manager.is_running is True
    assert manager.sync_task is not None

    await manager.stop_sync()
    assert manager.is_running is False
    assert manager.sync_task is None


@pytest.mark.asyncio
async def test_sync_all_items(mock_redis: AsyncMock) -> None:
    """Успешная синхронизация объявлений сохраняет данные в кэш."""

    async def get_items() -> list[dict[str, str]]:
        return [
            {"id": "item1", "title": "Test 1"},
            {"id": "item2", "title": "Test 2"},
        ]

    async def get_item_stats(_: str) -> dict[str, int]:
        return {"views": 100, "contacts": 5}

    manager = AvitoSyncManager()
    manager.client = SimpleNamespace(  # type: ignore[assignment]
        get_items=get_items,
        get_item_stats=get_item_stats,
    )

    stats = await manager.sync_all_items()

    assert stats["total_items"] == 2
    assert stats["synced"] == 2
    mock_redis.setex.assert_awaited()


@pytest.mark.asyncio
async def test_get_item_statistics_caching(mock_redis: AsyncMock) -> None:
    """Статистика возвращается из кэша при наличии данных."""
    cached_payload = {"views": 10, "contacts": 2}
    mock_redis.get.return_value = json.dumps(cached_payload)

    manager = AvitoSyncManager()
    result = await manager.get_item_statistics("cached-item")

    assert result["cached"] is True
    assert result["data"]["views"] == cached_payload["views"]


@pytest.mark.asyncio
async def test_get_item_statistics_fetch(mock_redis: AsyncMock) -> None:
    """При отсутствии кэша данные запрашиваются из API."""
    mock_redis.get.return_value = None

    manager = AvitoSyncManager()
    manager.client = SimpleNamespace(  # type: ignore[assignment]
        get_item_stats=AsyncMock(return_value={"views": 42, "contacts": 1}),
    )

    result = await manager.get_item_statistics("fresh-item")

    assert result["cached"] is False
    assert result["data"]["views"] == 42
    mock_redis.setex.assert_awaited()


@pytest.mark.asyncio
async def test_apply_vas_service() -> None:
    """Применение VAS услуги возвращает заглушку с нужными полями."""
    manager = AvitoSyncManager()
    result = await manager.apply_vas_service("item123", "highlight")

    assert result["status"] == "applied"
    assert result["item_id"] == "item123"
    assert result["service"] == "highlight"
