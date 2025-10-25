"""Зависимости FastAPI для проверки авторизации."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from loguru import logger

from app.core.security import decode_token
from app.models.security import TokenPayload


bearer_scheme = HTTPBearer(auto_error=False)


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    """Извлекает и проверяет токен из заголовка Authorization."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется заголовок авторизации.",
        )
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Поддерживается только схема Bearer.",
        )
    return decode_token(credentials.credentials)


async def get_current_user(
    payload: TokenPayload = Depends(get_token_payload),
) -> TokenPayload:
    """
    Возвращает полезную нагрузку текущего пользователя.

    Поддерживает:
    - Обычные пользовательские токены (sub: user_id)
    - Сервисные токены (sub: service:service_name)
    """
    if isinstance(payload.sub, str) and payload.sub.startswith("service:"):
        logger.debug(f"Аутентифицирован сервис: {payload.sub}")
        return payload

    return payload


def get_service_name(payload: TokenPayload) -> str | None:
    """
    Извлекает имя сервиса из токена.

    Returns:
        Имя сервиса (telegram_bot, avito_bot) или None если не сервисный токен
    """
    if isinstance(payload.sub, str) and payload.sub.startswith("service:"):
        return payload.sub.replace("service:", "")
    return None


async def authorize_request(request: Request) -> TokenPayload:
    """Проверяет токен в запросе (используется в middleware)."""
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация.",
        )
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный формат заголовка Authorization.",
        )
    logger.debug("Проверка токена для пути {}", request.url.path)
    return decode_token(token)
