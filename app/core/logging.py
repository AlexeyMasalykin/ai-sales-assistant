"""Настройка структурированного логирования с помощью Loguru."""

from __future__ import annotations

import logging
import sys

from types import FrameType

from loguru import logger

from app.core.settings import settings


class InterceptHandler(logging.Handler):
    """Перенаправляет стандартные логи в Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Переопределяет обработку записей логов."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def configure_logging() -> None:
    """Инициализирует JSON-логирование для приложения."""
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        serialize=True,
        backtrace=True,
        diagnose=False,
    )
    reset_standard_handlers()


def reset_standard_handlers() -> None:
    """Перенастраивает стандартный модуль logging."""
    intercept = InterceptHandler()
    logging.basicConfig(handlers=[intercept], level=0)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging_logger = logging.getLogger(name)
        logging_logger.handlers = [intercept]
        logging_logger.propagate = False
