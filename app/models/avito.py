"""Pydantic-модели для взаимодействия с Avito."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AvitoWebhookMessage(BaseModel):
    """Входящее сообщение от Avito."""

    chat_id: str = Field(..., description="Идентификатор чата Avito.")
    message_id: str = Field(..., alias="id", description="Идентификатор сообщения.")
    text: Optional[str] = Field(default=None, description="Текст сообщения, если есть.")
    author_id: str = Field(..., description="Идентификатор автора сообщения.")
    created_at: str = Field(..., description="Время создания сообщения в формате ISO 8601.")
    message_type: Optional[str] = Field(
        default=None,
        alias="type",
        description="Тип сообщения (text, image, voice и т.д.).",
    )
    attachments: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Список вложений сообщения.",
    )


class AvitoWebhookPayload(BaseModel):
    """Полный payload, приходящий с Avito webhook."""

    event_type: str = Field(..., description="Тип события Avito, например message.new.")
    payload: Optional[dict[str, Any]] = Field(
        default=None,
        description="Исходный объект payload от Avito.",
    )
    message: Optional[AvitoWebhookMessage] = Field(
        default=None,
        description="Извлечённое сообщение, если доступно в payload.",
    )
    raw: Optional[dict[str, Any]] = Field(
        default=None,
        description="Оригинальные данные, если требуется сохранить исходный вид.",
    )


class WebhookRegistrationRequest(BaseModel):
    """Запрос на регистрацию webhook."""

    webhook_url: str = Field(..., description="Публичный HTTPS URL для webhook Avito.")


class WebhookStatusResponse(BaseModel):
    """Ответ о статусе зарегистрированного webhook."""

    is_registered: bool = Field(..., description="Признак наличия активной подписки.")
    webhook_url: Optional[str] = Field(
        default=None,
        description="Текущий URL webhook, если зарегистрирован.",
    )
    raw: Optional[dict[str, Any]] = Field(
        default=None,
        description="Сырые данные ответа Avito для отладки.",
    )


class AvitoVASRequest(BaseModel):
    """Запрос на применение VAS-услуги."""

    service_code: str = Field(
        ...,
        description="Код услуги Avito (например, highlight).",
    )


class AvitoSyncOptions(BaseModel):
    """Параметры запуска синхронизации."""

    interval_minutes: int = Field(
        default=60,
        ge=1,
        le=24 * 60,
        description="Интервал в минутах между синхронизациями.",
    )
