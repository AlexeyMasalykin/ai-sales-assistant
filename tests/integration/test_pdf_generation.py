"""Интеграционные тесты генерации PDF документов."""

from pathlib import Path

import pytest

from app.services.documents.generator import document_generator


@pytest.mark.asyncio
async def test_generate_price_list_pdf() -> None:
    """Тест генерации прайс-листа в PDF."""
    client_name = "ООО Тестовая компания"
    services = ["AI Ассистент", "Автоматизация CRM"]

    pdf_bytes, file_path = await document_generator.generate_price_list_pdf(
        client_name, services
    )

    # Проверяем PDF
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    # Проверяем размер (должен быть меньше 10 МБ)
    size_mb = len(pdf_bytes) / (1024 * 1024)
    assert size_mb < 10

    # Проверяем файл
    if file_path:
        assert Path(file_path).exists()
        assert "price_list" in file_path
        assert Path(file_path).suffix == ".pdf"


@pytest.mark.asyncio
async def test_generate_commercial_proposal_pdf() -> None:
    """Тест генерации коммерческого предложения в PDF."""
    client_data = {
        "name": "Иван Петров",
        "company": "ООО Инновации",
        "services": "AI автоматизация",
        "budget": "500 000 - 1 000 000 ₽",
        "notes": "Требуется интеграция с CRM",
    }

    pdf_bytes, file_path = await document_generator.generate_commercial_proposal_pdf(
        client_data
    )

    # Проверяем PDF
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    # Проверяем размер
    size_mb = len(pdf_bytes) / (1024 * 1024)
    assert size_mb < 10

    # Проверяем файл
    if file_path:
        assert Path(file_path).exists()
        assert "commercial_proposal" in file_path


@pytest.mark.asyncio
async def test_generate_contract_draft_pdf() -> None:
    """Тест генерации договора в PDF."""
    client_data = {
        "name": "ООО Клиент",
        "inn": "1234567890",
        "services": "Разработка AI-ассистента",
        "price": "750 000",
        "timeline": "3 месяца",
    }

    pdf_bytes, file_path = await document_generator.generate_contract_draft_pdf(
        client_data
    )

    # Проверяем PDF
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    # Проверяем размер
    size_mb = len(pdf_bytes) / (1024 * 1024)
    assert size_mb < 10

    # Проверяем файл
    if file_path:
        assert Path(file_path).exists()
        assert "contract" in file_path


@pytest.mark.asyncio
async def test_pdf_generation_all_documents() -> None:
    """Тест генерации всех типов документов."""
    client_data = {
        "name": "Полный тест",
        "company": "ООО Тестирование",
        "services": "Комплексная автоматизация",
        "budget": "1 000 000 ₽",
        "inn": "9876543210",
        "price": "1 000 000",
        "timeline": "6 месяцев",
    }

    # Генерируем все документы
    price_list_pdf, _ = await document_generator.generate_price_list_pdf(
        client_data["name"]
    )
    proposal_pdf, _ = await document_generator.generate_commercial_proposal_pdf(
        client_data
    )
    contract_pdf, _ = await document_generator.generate_contract_draft_pdf(client_data)

    # Проверяем, что все PDF валидны
    for pdf_bytes in [price_list_pdf, proposal_pdf, contract_pdf]:
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF-")

        # Проверяем размер
        size_mb = len(pdf_bytes) / (1024 * 1024)
        assert size_mb < 10


@pytest.mark.asyncio
async def test_pdf_with_special_characters_in_name() -> None:
    """Тест генерации PDF с специальными символами в имени клиента."""
    client_data = {
        "name": 'ООО "Компания & Ко" / Филиал №1',
        "company": "Тест",
        "services": "AI",
    }

    pdf_bytes, file_path = await document_generator.generate_commercial_proposal_pdf(
        client_data
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0

    # Файл должен быть создан с корректным именем (без недопустимых символов)
    if file_path:
        assert Path(file_path).exists()
        # Недопустимые символы должны быть удалены
        assert "/" not in Path(file_path).name
        assert "&" not in Path(file_path).name


@pytest.mark.asyncio
async def test_pdf_size_validation() -> None:
    """Тест валидации размера PDF."""
    client_name = "Тест размера"

    pdf_bytes, _ = await document_generator.generate_price_list_pdf(client_name)

    # Проверяем, что PDF не превышает максимальный размер
    size_mb = len(pdf_bytes) / (1024 * 1024)
    assert size_mb < 10

    # Проверяем, что PDF имеет разумный размер (не пустой)
    assert size_mb > 0.001  # Более 1 КБ
