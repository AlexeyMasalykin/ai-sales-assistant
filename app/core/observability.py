"""Инструменты наблюдаемости приложения."""

from __future__ import annotations

from loguru import logger
import sentry_sdk

from app.core.settings import settings


def configure_sentry() -> None:
    """Подключает Sentry при наличии DSN."""
    if not settings.sentry_dsn:
        logger.debug("Sentry не активирован: отсутствует DSN.")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
    )
    logger.info("Sentry успешно инициализирован.")
