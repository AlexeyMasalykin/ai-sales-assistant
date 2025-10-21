"""Pydantic-модели для безопасности."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    """Данные, закодированные в JWT токене."""

    sub: str = Field(..., description="Идентификатор субъекта.")
    exp: int = Field(..., description="Метка истечения токена (UNIX).")
    iat: int | None = Field(
        default=None,
        description="Метка выпуска токена (UNIX).",
    )


class AccessToken(BaseModel):
    """Ответ с токеном доступа."""

    access_token: str
    token_type: str = "bearer"
