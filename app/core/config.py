"""Утилиты конфигурации приложения."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_environment(env_file: Optional[str] = None) -> None:
    """Загружает переменные окружения из файла `.env`."""
    if env_file:
        load_dotenv(dotenv_path=env_file, override=False)
        return

    default_path = Path(".env")
    if default_path.exists():
        load_dotenv(dotenv_path=default_path, override=False)
