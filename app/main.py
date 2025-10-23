"""Точка входа FastAPI приложения."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app import __version__
from app.api import register_routes
from app.core.cache import close_redis, verify_redis
from app.core.config import load_environment
from app.core.database import (
    apply_migrations,
    close_engine,
    verify_database,
)
from app.core.dependencies import authorize_request
from app.core.logging import configure_logging
from app.core.observability import configure_sentry
from app.core.rate_limiter import RateLimitMiddleware
from app.core.settings import settings
from app.services.avito.sync import sync_manager
from app.services.avito.webhook import webhook_handler
from app.services.telegram.bot import telegram_bot
from app.services.rag.loader import document_loader


UNPROTECTED_PATHS = {
    "/",
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/webhooks/avito/messages",
    "/api/v1/webhooks/telegram",
}

# Паттерны для веб-чата (проверяются отдельно)
CHAT_PATH_PATTERNS = [
    "/api/v1/chat/sessions",
    "/api/v1/chat/messages",
    "/api/v1/chat/ws/",
]

# Паттерны для веб-чата (проверяются отдельно)
CHAT_PATH_PATTERNS = [
    "/api/v1/chat/sessions",
    "/api/v1/chat/messages",
    "/api/v1/chat/ws/",
]

# Паттерны для веб-чата (проверяются отдельно)
CHAT_PATH_PATTERNS = [
    "/api/v1/chat/sessions",
    "/api/v1/chat/messages",
    "/api/v1/chat/ws/",
]


load_environment()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом приложения."""
    configure_logging()
    configure_sentry()
    await bootstrap_runtime()
    try:
        yield
    finally:
        await shutdown_runtime()


def setup_middlewares(app: FastAPI) -> None:
    """Регистрирует middleware для приложения."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # В production указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        limit=settings.rate_limit_per_minute,
        window_seconds=settings.rate_limit_window_seconds,
        exempt_paths=UNPROTECTED_PATHS,
    )

    @app.middleware("http")
    async def enforce_jwt(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Проверяет JWT для защищённых эндпоинтов."""
        if request.url.path in UNPROTECTED_PATHS or any(
            request.url.path.startswith(pattern) for pattern in CHAT_PATH_PATTERNS
        ):
            return await call_next(request)
        try:
            await authorize_request(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        return await call_next(request)


def register_exception_handlers(app: FastAPI) -> None:
    """Настраивает обработчики ошибок FastAPI."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Обрабатывает ошибки валидации запросов."""
        logger.warning(
            "Ошибка валидации для пути {}: {}",
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "message": "Ошибки проверки данных запроса.",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Обрабатывает неожиданные исключения."""
        logger.exception(
            "Необработанное исключение для пути {}",
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера."},
        )


def create_application() -> FastAPI:
    """Создаёт и настраивает экземпляр FastAPI."""
    app = FastAPI(
        title="Интеллектуальный ассистент продаж ИИ-услуг",
        version=__version__,
        description="Сервис автоматизации продаж ИИ-услуг.",
        lifespan=lifespan,
    )

    setup_middlewares(app)
    register_exception_handlers(app)
    register_routes(app)

    @app.get("/", tags=["health"])
    async def root() -> dict[str, str]:
        """Возвращает статус сервиса."""
        return {
            "status": "ok",
            "message": "Ассистент продаж готов к работе.",
        }

    return app


app = create_application()


async def bootstrap_runtime() -> None:
    """Готовит внешние сервисы к работе."""
    await apply_migrations()
    await verify_database()
    await verify_redis()
    await webhook_handler.start_processing()
    if settings.avito_sync_enabled:
        await sync_manager.start_sync(
            interval_minutes=settings.avito_sync_interval_minutes
        )
    await telegram_bot.start()
    # При необходимости загрузить документы базы знаний:
    # await document_loader.load_all_documents()


async def shutdown_runtime() -> None:
    """Закрывает соединения при остановке приложения."""
    await webhook_handler.stop_processing()
    await sync_manager.stop_sync()
    await telegram_bot.stop()
    await close_redis()
    await close_engine()
