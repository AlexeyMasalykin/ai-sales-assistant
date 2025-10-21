"""Подключение к PostgreSQL и управление миграциями."""

from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Создаёт асинхронную сессию SQLAlchemy."""
    async with session_factory() as session:
        yield session


async def verify_database() -> None:
    """Проверяет соединение с базой данных."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def close_engine() -> None:
    """Закрывает соединения с базой данных."""
    await engine.dispose()


async def apply_migrations() -> None:
    """Запускает alembic миграции."""
    try:
        process = await asyncio.create_subprocess_exec(
            "alembic",
            "upgrade",
            "head",
            stdout=PIPE,
            stderr=PIPE,
        )
    except FileNotFoundError:
        logger.warning("Утилита alembic не найдена, миграции пропущены.")
        return
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode().strip() or stdout.decode().strip()
        logger.error("Ошибка применения миграций: {}", message)
        raise RuntimeError(message)
    logger.info("Миграции применены успешно.")
