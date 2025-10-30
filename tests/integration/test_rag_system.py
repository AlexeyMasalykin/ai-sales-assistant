"""Тесты RAG системы."""

import pytest

from app.services.rag.answer import answer_generator
from app.services.rag.search import document_search

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_document_search_pricing(load_knowledge_base) -> None:
    """Тест поиска информации о ценах"""
    results = await document_search.search("стоимость цена", limit=2)

    assert len(results) > 0
    assert results[0]["similarity"] > 0.2
    assert "title" in results[0]
    assert "content" in results[0]


@pytest.mark.asyncio
async def test_document_search_services(load_knowledge_base) -> None:
    """Тест поиска услуг"""
    results = await document_search.search("услуги автоматизация", limit=2)

    assert len(results) > 0
    assert results[0]["similarity"] > 0.2
    # Проверяем, что в контенте есть информация об услугах/сервисах
    contents = " ".join([r["content"].lower() for r in results])
    assert "ai-manager" in contents or "crm" in contents or "автоматиз" in contents


@pytest.mark.asyncio
async def test_document_search_cases(load_knowledge_base) -> None:
    """Тест поиска кейсов"""
    results = await document_search.search("кейсы проекты", limit=2)

    assert len(results) > 0
    titles = [r["title"].lower() for r in results]
    assert any("case" in t for t in titles)


@pytest.mark.asyncio
async def test_answer_generation(load_knowledge_base) -> None:
    """Тест генерации ответа через RAG"""
    answer = await answer_generator.generate_answer(
        "Сколько стоит автоматизация?", "TestUser"
    )

    assert len(answer) > 50
    assert "TestUser" in answer or "₽" in answer
    assert "<b>" in answer or "<i>" in answer


@pytest.mark.asyncio
async def test_answer_generation_services(load_knowledge_base) -> None:
    """Тест вопроса об услугах"""
    answer = await answer_generator.generate_answer("Какие у вас услуги?", "TestUser")

    assert len(answer) > 50
    assert "услуг" in answer.lower() or "AI" in answer or "ИИ" in answer


@pytest.mark.asyncio
async def test_answer_generation_no_results(load_knowledge_base) -> None:
    """Тест когда документы не найдены"""
    answer = await answer_generator.generate_answer(
        "random xyz123 gibberish", "TestUser"
    )

    assert len(answer) > 0
    assert "извините" in answer.lower() or "TestUser" in answer
