"""Генерация сервисных токенов для ботов."""
from datetime import timedelta
import sys
import os

# Добавляем корневую директорию в path для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import create_access_token


def generate_service_token(service_name: str, days: int = 365) -> str:
    """
    Генерирует долгоживущий JWT токен для сервиса.

    Args:
        service_name: Название сервиса (telegram_bot, avito_bot)
        days: Срок действия токена в днях (по умолчанию 365)

    Returns:
        JWT токен в виде строки
    """
    return create_access_token(
        subject=f"service:{service_name}",
        expires_delta=timedelta(days=days),
        extra_claims={
            "type": "service",
            "service": service_name,
            "permissions": ["create_lead", "update_lead", "read_lead"]
        }
    )


def main():
    """Генерирует токены для всех ботов."""
    print("=" * 70)
    print("ГЕНЕРАЦИЯ СЕРВИСНЫХ JWT ТОКЕНОВ ДЛЯ БОТОВ")
    print("=" * 70)
    print(f"TTL: 365 дней (1 год)")
    print(f"Дата генерации: {timedelta()}")
    print("=" * 70)

    # Telegram Bot
    telegram_token = generate_service_token("telegram_bot")
    print(f"\n📱 Telegram Bot Service Token:")
    print(f"TELEGRAM_BOT_SERVICE_TOKEN={telegram_token}")

    # Avito Bot
    avito_token = generate_service_token("avito_bot")
    print(f"\n🏪 Avito Bot Service Token:")
    print(f"AVITO_BOT_SERVICE_TOKEN={avito_token}")

    print("\n" + "=" * 70)
    print("ИНСТРУКЦИЯ:")
    print("=" * 70)
    print("1. Скопируй токены выше")
    print("2. Добавь их в .env файл:")
    print("   nano .env")
    print("3. Перезапусти приложение:")
    print("   docker-compose restart app")
    print("4. Сохрани токены в безопасном месте (password manager)")
    print("=" * 70)
    print("\n⚠️  ВАЖНО: Эти токены дают полный доступ к API создания лидов!")
    print("   Не коммить в Git, не публиковать, хранить в .env")
    print("=" * 70)


if __name__ == "__main__":
    main()
