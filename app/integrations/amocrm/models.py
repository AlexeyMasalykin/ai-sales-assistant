"""Pydantic модели для amoCRM API."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AmoCRMTokens(BaseModel):
    """OAuth токены amoCRM."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    created_at: datetime = Field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """Проверяет истёк ли токен (с запасом 1 час)."""
        age = (datetime.now() - self.created_at).total_seconds()
        return age >= (self.expires_in - 3600)


class AmoCRMCustomField(BaseModel):
    """Кастомное поле amoCRM."""

    field_id: int
    values: list[dict]


class AmoCRMContact(BaseModel):
    """Контакт amoCRM."""

    name: str
    first_name: str | None = None
    last_name: str | None = None
    custom_fields_values: list[AmoCRMCustomField] | None = None


class AmoCRMLead(BaseModel):
    """Лид amoCRM."""

    name: str
    price: int | None = None
    pipeline_id: int | None = None
    status_id: int | None = None
    responsible_user_id: int | None = None
    custom_fields_values: list[AmoCRMCustomField] | None = None
    _embedded: dict | None = None


class AmoCRMNote(BaseModel):
    """Примечание к лиду."""

    entity_id: int
    entity_type: Literal["leads", "contacts", "companies"]
    note_type: Literal["common"] = "common"
    params: dict


class LeadCreateRequest(BaseModel):
    """Запрос на создание лида из диалога."""

    user_name: str
    phone: str | None = None
    email: str | None = None
    source: Literal["telegram", "avito", "web"] = "telegram"
    product_interest: str | None = None  # AI Manager/Lawyer/Analyst
    budget: int | None = None
    conversation_history: str | None = None
    pipeline_id: int | None = None
    status_id: int | None = None
    metadata: dict | None = None


class LeadCreateResponse(BaseModel):
    """Ответ на создание лида."""

    lead_id: int
    contact_id: int | None = None
    success: bool
    message: str
