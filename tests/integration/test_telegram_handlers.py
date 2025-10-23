"""Тесты Telegram обработчиков команд."""

import pytest
from unittest.mock import AsyncMock

from app.services.telegram.handlers import TelegramHandlers


@pytest.mark.asyncio
async def test_handle_start_command() -> None:
    """Тест команды /start"""
    response = await TelegramHandlers.handle_start(12345, "TestUser")

    assert "Привет, TestUser" in response
    assert "/help" in response
    assert "/services" in response


@pytest.mark.asyncio
async def test_handle_help_command() -> None:
    """Тест команды /help"""
    response = await TelegramHandlers.handle_help(12345)

    assert "/start" in response
    assert "/services" in response
    assert "/price" in response


@pytest.mark.asyncio
async def test_handle_services_command() -> None:
    """Тест команды /services"""
    response = await TelegramHandlers.handle_services(12345)

    assert "услуги" in response.lower() or "AI" in response


@pytest.mark.asyncio
async def test_handle_price_command() -> None:
    """Тест команды /price"""
    response = await TelegramHandlers.handle_price(12345)

    assert "стоимость" in response.lower() or "₽" in response


@pytest.mark.asyncio
async def test_handle_contact_command() -> None:
    """Тест команды /contact"""
    response = await TelegramHandlers.handle_contact(12345, "TestUser")

    assert "связаться" in response.lower()
    assert "TestUser" in response


@pytest.mark.asyncio
async def test_handle_cases_command() -> None:
    """Тест команды /cases"""
    response = await TelegramHandlers.handle_cases(12345)

    assert "кейс" in response.lower()


@pytest.mark.asyncio
async def test_handle_unknown_command() -> None:
    """Тест неизвестной команды"""
    response = await TelegramHandlers.handle_unknown_command(12345, "/unknown")

    assert "не распознана" in response.lower()
    assert "/help" in response


@pytest.mark.asyncio
async def test_handle_generate_price() -> None:
    """Тест генерации прайс-листа"""
    response = await TelegramHandlers.handle_generate_price(12345, "TestUser")

    assert len(response) > 50
    assert "TestUser" in response or "прайс" in response.lower()


@pytest.mark.asyncio
async def test_handle_generate_proposal() -> None:
    """Тест генерации КП"""
    response = await TelegramHandlers.handle_generate_proposal(
        12345,
        "TestUser",
        "ООО Тест",
        "AI автоматизация",
    )

    assert len(response) > 50
    assert "коммерческое предложение" in response.lower() or "КП" in response


@pytest.mark.asyncio
async def test_handle_text_message_with_rag(
    mock_redis: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Тест текстового сообщения через RAG"""
    mock_answer = AsyncMock(return_value="<b>TestUser</b>, мы предлагаем услуги AI.")
    monkeypatch.setattr(
        "app.services.rag.answer.answer_generator.generate_answer_with_context",
        mock_answer,
    )

    response = await TelegramHandlers.handle_text_message(
        12345,
        "Какие у вас услуги?",
        "TestUser",
    )

    assert response == "<b>TestUser</b>, мы предлагаем услуги AI."
    mock_answer.assert_awaited_once()
