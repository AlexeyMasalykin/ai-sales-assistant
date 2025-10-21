"""Утилиты конфигурации приложения."""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Загружаем .env ПЕРЕД импортом Settings
load_dotenv(override=True)

class Settings(BaseSettings):
    """Настройки приложения."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Avito API (приоритет для текущей фазы)
    AVITO_CLIENT_ID: str
    AVITO_CLIENT_SECRET: str
    AVITO_USER_ID: str
    AVITO_API_BASE_URL: str = "https://api.avito.ru"
    AVITO_TOKEN_TTL: int = 86400
    AVITO_TOKEN_REFRESH_BEFORE: int = 3600
    
    # Database
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None
    
    # Redis
    UPSTASH_REDIS_URL: Optional[str] = None
    
    # LLM
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # JWT
    JWT_SECRET_KEY: Optional[str] = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    
    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

# Создаём глобальный экземпляр настроек
settings = Settings()

def load_environment(env_file: Optional[str] = None) -> None:
    """Загружает переменные окружения из файла `.env`."""
    if env_file:
        load_dotenv(dotenv_path=env_file, override=True)
        return
    default_path = Path(".env")
    if default_path.exists():
        load_dotenv(dotenv_path=default_path, override=True)
