"""Регистрация FastAPI роутеров приложения."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.avito import router as avito_router
from app.api.routes.health import router as health_router


def register_routes(application: FastAPI) -> None:
    """Подключает все API-модули к FastAPI приложению."""
    application.include_router(health_router)
    application.include_router(
        avito_router,
        prefix="/api/v1",
    )
