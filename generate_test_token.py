"""Генерация тестового JWT токена."""
from datetime import timedelta
from app.core.security import create_access_token

# Создаём токен для тестового пользователя
token = create_access_token(
    subject="test_user_123",  # ID пользователя
    expires_delta=timedelta(days=30),  # Токен на 30 дней
    extra_claims={
        "id": 1,  # user_id для логирования
        "email": "test@example.com",
        "role": "admin"
    }
)

print("=" * 60)
print("ТЕСТОВЫЙ JWT ТОКЕН:")
print("=" * 60)
print(token)
print("=" * 60)
print("\nИспользуй этот токен для тестирования:")
print(f"Authorization: Bearer {token}")
print("=" * 60)
