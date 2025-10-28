"""Настройки приложения на основе pydantic-settings."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import load_environment


load_environment()


class Settings(BaseSettings):
    """Глобальные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Supabase / PostgreSQL
    supabase_url: str = "postgresql://test"
    supabase_key: SecretStr = SecretStr("test_key")
    supabase_service_key: SecretStr = SecretStr("test_service_key")
    database_url: str = "postgresql+asyncpg://test/test"

    # Redis
    upstash_redis_url: str = "redis://localhost:6379"

    # LLM
    llm_provider: Literal["openai", "anthropic", "openrouter"] = "openai"
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API ключ для LLM квалификации лидов",
    )
    openai_model: str = Field(
        description="Модель OpenAI, используемая для генерации ответов/документов",
    )
    openai_conversation_model: str = Field(
        description="Модель OpenAI для генерации ответов в Avito диалоге",
    )
    openai_extraction_model: str = Field(
        description="Модель OpenAI для извлечения данных из сообщений",
    )
    openai_summarization_model: str = Field(
        description="Модель OpenAI для генерации саммари",
    )
    anthropic_api_key: SecretStr | None = None

    # Avito
    avito_client_id: str = "test"
    avito_client_secret: SecretStr = SecretStr("test")
    avito_user_id: str = "test"
    avito_api_base_url: str = "https://api.avito.ru"
    avito_token_ttl: int = 86_400
    avito_token_refresh_before: int = 3_600
    avito_auto_reply_enabled: bool = True
    avito_max_queue_size: int = 1_000
    avito_processing_workers: int = 3
    avito_response_delay_seconds: int = 2
    avito_cache_ttl_seconds: int = 3_600
    avito_sync_interval_minutes: int = 60
    avito_sync_enabled: bool = True
    avito_conversation_enabled: bool = Field(
        default=False,
        description="Включена ли FSM система прогрева лидов в Avito",
    )
    avito_conversation_ttl: int = Field(
        default=604_800,
        description="TTL хранения контекста диалога в секундах",
    )

    # Telegram
    telegram_bot_token: SecretStr = SecretStr("test")
    telegram_webhook_url: str = "https://test"
    telegram_bot_service_token: str = Field(
        default="",
        description="JWT токен для Telegram бота (TTL: 1 год)",
    )
    avito_bot_service_token: str = Field(
        default="",
        description="JWT токен для Avito бота (TTL: 1 год)",
    )

    # amoCRM
    amocrm_subdomain: str = Field(default="", description="amoCRM subdomain")
    amocrm_client_id: str = Field(default="", description="amoCRM Client ID")
    amocrm_client_secret: SecretStr = Field(default="", description="amoCRM Client Secret")
    amocrm_redirect_uri: str = Field(
        default="https://smmassistant.online/api/v1/amocrm/callback",
        description="amoCRM OAuth redirect URI",
    )

    # Google Calendar
    google_calendar_credentials: str = "{}"

    # ЮKassa
    yookassa_shop_id: str = "test"
    yookassa_secret_key: SecretStr = SecretStr("test")

    # Безопасность и логирование
    jwt_secret_key: SecretStr = SecretStr("dev-secret-key")
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
    prompts_dir: str | None = Field(
        default=None,
        description="Каталог с .poml промптами",
    )
    name_extraction_threshold: float = Field(default=0.7)
    phone_extraction_threshold: float = Field(default=0.8)
    need_extraction_threshold: float = Field(default=0.6)

    # PDF генерация
    max_pdf_size_mb: int = Field(default=10)
    pdf_output_dir: str = Field(default="data/documents")
    api_base_url: str = Field(
        default="https://smmassistant.online",
        description="Базовый URL API для внутренних запросов",
    )
    telegram_lead_cache_ttl: int = Field(
        default=86_400,
        description="TTL кэша созданных Telegram лидов (секунды)",
    )
    avito_lead_cache_ttl: int = Field(
        default=86_400,
        description="TTL кэша созданных Avito лидов (секунды)",
    )

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


settings = Settings()
