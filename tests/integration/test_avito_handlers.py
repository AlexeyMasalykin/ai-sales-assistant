"""Интеграционные тесты обработчиков Avito сообщений."""

from __future__ import annotations

import pytest

from app.services.avito.handlers import AvitoMessageHandlers


@pytest.mark.asyncio
async def test_handle_greeting_message() -> None:
    """Обработка приветствия должна возвращать приветственный текст."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Привет!",
        "user456",
    )

    assert "Здравствуйте" in response
    assert "ИИ-ассистент" in response


@pytest.mark.asyncio
async def test_handle_price_question() -> None:
    """Ответ на вопрос о цене содержит информацию о тарифах."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Сколько стоит?",
        "user456",
    )

    assert "Стоимость" in response or "стоимость" in response.lower()
    assert "₽" in response


@pytest.mark.asyncio
async def test_handle_contact_request() -> None:
    """Запрос контактов возвращает информацию о каналах связи."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Как с вами связаться?",
        "user456",
    )

    assert any(keyword in response for keyword in ("Telegram", "Email", "Телефон"))


@pytest.mark.asyncio
async def test_handle_default_message() -> None:
    """Неизвестный запрос приводит к универсальному ответу."""
    response = await AvitoMessageHandlers.handle_text_message(
        "chat123",
        "Какая-то случайная фраза",
        "user456",
    )

    assert len(response) > 0
    assert "Спасибо" in response or "специалист" in response.lower()


@pytest.mark.asyncio
async def test_handle_image_message() -> None:
    """Сообщение с изображением возвращает подтверждение."""
    response = await AvitoMessageHandlers.handle_image_message(
        "chat123",
        "https://example.com/image.jpg",
    )

    assert "изображение" in response.lower()
