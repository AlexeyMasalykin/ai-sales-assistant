"""Точка входа FastAPI приложения."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__


def create_application() -> FastAPI:
    """Создаёт и настраивает экземпляр FastAPI."""
    app = FastAPI(
        title="Интеллектуальный ассистент продаж ИИ-услуг",
        version=__version__,
        description="Сервис автоматизации продаж ИИ-услуг"
                    "с интеграциями и LLM",
    )

    # TODO: Заменить заглушку списка доменов на значения
    #       из конфигурации.
    allowed_origins: list[str] = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["health"])
    async def root() -> dict[str, str]:
        """Возвращает статус сервиса."""
        return {"status": "ok", "message": "Ассистент продаж готов к работе."}

    return app


app = create_application()
