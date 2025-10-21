"""Настройки приложения на основе pydantic-settings."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import load_environment


load_environment()


class Settings(BaseSettings):
    """Глобальные настройки приложения."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Supabase / PostgreSQL
    supabase_url: str
    supabase_key: SecretStr
    supabase_service_key: SecretStr
    database_url: str

    # Redis
    upstash_redis_url: str

    # LLM
    llm_provider: Literal["openai", "anthropic", "openrouter"] = "openai"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # Avito
    avito_client_id: str
    avito_client_secret: SecretStr
    avito_user_id: str

    # Telegram
    telegram_bot_token: SecretStr
    telegram_webhook_url: str

    # amoCRM
    amocrm_domain: str
    amocrm_access_token: SecretStr

    # Google Calendar
    google_calendar_credentials: str

    # ЮKassa
    yookassa_shop_id: str
    yookassa_secret_key: SecretStr

    # Безопасность и логирование
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    environment: Literal[
        "development",
        "staging",
        "production",
    ] = "development"
    log_level: str = "INFO"
    sentry_dsn: str | None = None

    # CORS
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Прочие настройки
    documents_path: str = "/var/data/documents"
    rate_limit_per_minute: int = 60
    rate_limit_window_seconds: int = 60
    session_ttl_days: int = 30
    max_concurrent_users: int = 100

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> list[str]:
        """Преобразует строку в список источников."""
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
            return [item for item in items if item]
        if isinstance(value, list):
            return value
        return ["*"]



settings = Settings()  # type: ignore[call-arg]
