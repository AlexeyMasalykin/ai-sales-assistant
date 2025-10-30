"""Тесты Redis контекста для Telegram."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.telegram.handlers import TelegramHandlers
from app.services.web.chat_session import session_manager
from tests.conftest import skip_without_telegram

pytestmark = [pytest.mark.integration, skip_without_telegram]


def _setup_in_memory_redis(mock_redis: AsyncMock) -> None:
    """Настраивает in-memory поведение Redis моков для тестов."""
    string_storage: dict[str, str] = {}
    list_storage: dict[str, list[str]] = {}

    async def get(key: str) -> str | None:
        return string_storage.get(key)

    async def set_value(key: str, value: str) -> bool:
        string_storage[key] = value
        return True

    async def setex(key: str, ttl: int, value: str) -> bool:
        string_storage[key] = value
        return True

    async def expire(key: str, ttl: int) -> bool:
        return True

    async def rpush(key: str, value: str) -> int:
        list_storage.setdefault(key, []).append(value)
        return len(list_storage[key])

    async def lrange(key: str, start: int, end: int) -> list[str]:
        items = list_storage.get(key, [])
        size = len(items)
        if size == 0:
            return []

        if start < 0:
            start = max(0, size + start)
        if end < 0:
            end = size + end
        end = min(end, size - 1)
        if start > end:
            return []
        return items[start : end + 1]

    mock_redis.get.side_effect = get
    mock_redis.set.side_effect = set_value
    mock_redis.setex.side_effect = setex
    mock_redis.expire.side_effect = expire
    mock_redis.rpush.side_effect = rpush
    mock_redis.lrange.side_effect = lrange


@pytest.mark.asyncio
async def test_telegram_session_creation(mock_redis: AsyncMock) -> None:
    """Тест создания Telegram сессии."""
    _setup_in_memory_redis(mock_redis)

    session_id = await session_manager.get_or_create_telegram_session(12345, "TestUser")

    assert session_id

    session = await session_manager.get_session(session_id)
    assert session is not None
    assert session["user_name"] == "TestUser"
    assert session["metadata"]["channel"] == "telegram"
    assert session["metadata"]["chat_id"] == 12345


@pytest.mark.asyncio
async def test_telegram_message_with_context(
    mock_redis: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет сохранение контекста и генерацию ответа."""
    _setup_in_memory_redis(mock_redis)

    responses = ["Ответ 1", "Ответ 2"]
    mock_answer = AsyncMock(side_effect=responses)
    monkeypatch.setattr(
        "app.services.rag.answer.answer_generator.generate_answer_with_context",
        mock_answer,
    )

    first = await TelegramHandlers.handle_text_message(
        12345,
        "Привет, расскажи про услуги",
        "TestUser",
    )
    second = await TelegramHandlers.handle_text_message(
        12345,
        "А сколько это стоит?",
        "TestUser",
    )

    assert first == "Ответ 1"
    assert second == "Ответ 2"
    assert mock_answer.await_count == 2


@pytest.mark.asyncio
async def test_context_retrieval(mock_redis: AsyncMock) -> None:
    """Тест получения контекста для LLM."""
    _setup_in_memory_redis(mock_redis)

    session_id = await session_manager.create_session("TestUser")

    await session_manager.add_message(session_id, "user", "Сообщение 1")
    await session_manager.add_message(session_id, "assistant", "Ответ 1")
    await session_manager.add_message(session_id, "user", "Сообщение 2")

    context = await session_manager.get_context_for_llm(session_id, limit=10)

    assert len(context) == 3
    assert context[0]["role"] == "user"
    assert context[0]["content"] == "Сообщение 1"
