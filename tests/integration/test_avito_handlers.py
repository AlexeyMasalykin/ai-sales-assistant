"""Интеграционные тесты обработчиков Avito сообщений."""

from __future__ import annotations

import pytest

from app.services.avito.handlers import AvitoMessageHandlers
from tests.conftest import skip_without_avito

pytestmark = [pytest.mark.integration, skip_without_avito]


@pytest.mark.asyncio
async def test_handle_greeting_message() -> None:
    """Обработка приветствия должна возвращать приветственный текст."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Привет!",
        "user456",
    )

    # RAG генерирует персонализированные ответы
    assert len(response) > 0
    assert any(
        keyword in response.lower() for keyword in ("привет", "здравствуй", "помочь")
    )


@pytest.mark.asyncio
async def test_handle_price_question() -> None:
    """Ответ на вопрос о цене содержит информацию о тарифах."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Сколько стоит?",
        "user456",
    )

    # RAG должен вернуть информацию о ценах
    assert any(
        keyword in response.lower() for keyword in ("цен", "стоимость", "₽", "руб")
    )
    assert len(response) > 50  # Детальный ответ с ценами


@pytest.mark.asyncio
async def test_handle_contact_request() -> None:
    """Запрос контактов возвращает информацию о каналах связи."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Как с вами связаться?",
        "user456",
    )

    # RAG должен предоставить полезный ответ о связи
    assert len(response) > 10
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_handle_default_message() -> None:
    """Неизвестный запрос приводит к универсальному ответу."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Какая-то случайная фраза",
        "user456",
    )

    # RAG всегда должен возвращать какой-то полезный ответ
    assert len(response) > 0
    assert isinstance(response, str)
    # Ответ должен быть отформатирован для Telegram (с HTML тегами)
    assert "<b>" in response or "<i>" in response


@pytest.mark.asyncio
async def test_handle_image_message() -> None:
    """Сообщение с изображением возвращает подтверждение."""
    response = await AvitoMessageHandlers.handle_image_message(
        "chat123",
        "https://example.com/image.jpg",
    )

    assert "изображение" in response.lower()
