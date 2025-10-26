"""Модели CRM для внутренних сервисов."""
from __future__ import annotations

from app.integrations.amocrm.models import (
    LeadCreateRequest as AmoLeadCreateRequest,
    LeadCreateResponse,
)


class LeadCreateRequest(AmoLeadCreateRequest):
    """Переиспользуемая модель запроса создания лида."""

    pipeline_id: int | None = None
    status_id: int | None = None


class LeadCreateResult(LeadCreateResponse):
    """Результат создания лида в amoCRM."""
