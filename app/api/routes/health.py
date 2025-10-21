"""Эндпоинты проверки состояния сервиса."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.cache import verify_redis
from app.core.database import verify_database


router = APIRouter(tags=["health"])


@router.get("/health", summary="Быстрая проверка доступности")
async def health() -> dict[str, str]:
    """Возвращает краткий статус приложения."""
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Расширенная проверка готовности",
    response_class=JSONResponse,
)
async def ready() -> JSONResponse:
    """Проверяет готовность внутренних сервисов."""
    services: dict[str, dict[str, str]] = {}
    overall_status = status.HTTP_200_OK

    try:
        await verify_database()
        services["postgres"] = {"status": "ok"}
    except Exception as exc:
        logger.error("База данных недоступна: {}", exc)
        services["postgres"] = {"status": "error", "detail": str(exc)}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        await verify_redis()
        services["redis"] = {"status": "ok"}
    except Exception as exc:
        logger.error("Redis недоступен: {}", exc)
        services["redis"] = {"status": "error", "detail": str(exc)}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    services["external"] = {
        "status": "pending",
        "detail": "Интеграции будут проверяться позже.",
    }

    return JSONResponse(
        status_code=overall_status,
        content={
            "status": "ok" if overall_status == status.HTTP_200_OK else "error",
            "services": services,
        },
    )
