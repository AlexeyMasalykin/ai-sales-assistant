"""Тесты генерации документов."""

import pytest

from app.services.documents.generator import document_generator


@pytest.mark.asyncio
async def test_generate_price_list() -> None:
    """Тест генерации прайс-листа"""
    html = await document_generator.generate_price_list(
        client_name="TestClient",
        services=["AI-Manager", "AI-Analyst"],
    )

    assert len(html) > 100
    assert "TestClient" in html
    assert "<" in html and ">" in html


@pytest.mark.asyncio
async def test_generate_commercial_proposal() -> None:
    """Тест генерации КП"""
    client_data = {
        "name": "Иван Петров",
        "company": "ООО Тест",
        "services": "AI автоматизация",
        "budget": "200000",
    }

    html = await document_generator.generate_commercial_proposal(client_data)

    assert len(html) > 500
    assert "Иван" in html or "ООО Тест" in html
    assert "<" in html and ">" in html


@pytest.mark.asyncio
async def test_generate_contract_draft() -> None:
    """Тест генерации черновика договора"""
    client_data = {
        "name": "ООО Клиент",
        "inn": "1234567890",
        "services": "Разработка ИИ-решений",
        "price": "500000",
        "timeline": "3 месяца",
    }

    html = await document_generator.generate_contract_draft(client_data)

    assert len(html) > 500
    assert "ООО Клиент" in html or "1234567890" in html
    assert "договор" in html.lower()
    assert "<" in html and ">" in html


@pytest.mark.asyncio
async def test_generate_price_list_minimal() -> None:
    """Тест генерации прайса с минимальными данными"""
    html = await document_generator.generate_price_list(client_name="Test")

    assert len(html) > 100
    assert "Test" in html
