"""Интеграционные тесты amoCRM клиента."""
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.amocrm.models import LeadCreateRequest
from app.services.crm.amocrm_service import amocrm_service

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_create_lead_from_conversation():
    """Тест создания лида из диалога."""

    # Mock amoCRM API
    with patch("app.integrations.amocrm.client.amocrm_client.create_contact") as mock_contact, patch(
        "app.integrations.amocrm.client.amocrm_client.create_lead"
    ) as mock_lead, patch("app.integrations.amocrm.client.amocrm_client.add_note") as mock_note:
        mock_contact.return_value = 12345
        mock_lead.return_value = 67890
        mock_note.return_value = 11111

        request = LeadCreateRequest(
            user_name="Иван Петров",
            phone="+79991234567",
            email="ivan@example.com",
            source="telegram",
            product_interest="AI Manager",
            budget=150000,
            conversation_history="История диалога...",
        )

        result = await amocrm_service.create_lead_from_conversation(request)

        assert result.success is True
        assert result.lead_id == 67890
        assert result.contact_id == 12345

        # Проверяем вызовы
        mock_contact.assert_called_once()
        mock_lead.assert_called_once()
        mock_note.assert_called_once()


@pytest.mark.asyncio
async def test_create_lead_without_contact():
    """Тест создания лида без контакта."""

    with patch("app.integrations.amocrm.client.amocrm_client.create_lead") as mock_lead:
        mock_lead.return_value = 67890

        request = LeadCreateRequest(
            user_name="Аноним",
            source="web",
            product_interest="AI Analyst",
        )

        result = await amocrm_service.create_lead_from_conversation(request)

        assert result.success is True
        assert result.lead_id == 67890
        assert result.contact_id is None
