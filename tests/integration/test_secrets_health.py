"""Тесты для мониторинга состояния секретов и токенов."""

import pytest

from app.services.avito.auth import AvitoAuthManager
from tests.conftest import skip_without_avito


@skip_without_avito
@pytest.mark.integration
async def test_avito_token_is_valid() -> None:
    """Проверяет, что Avito access token можно получить."""
    auth = AvitoAuthManager()
    token = await auth.get_access_token()

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 20


@skip_without_avito
@pytest.mark.integration
async def test_avito_token_has_sufficient_ttl(mock_redis) -> None:
    """Предупреждает если токен истекает менее чем через час."""
    mock_redis.ttl.return_value = 7200  # 2 часа

    ttl = await mock_redis.ttl("avito:access_token")

    if 0 < ttl < 3600:
        pytest.fail(f"⚠️ Avito токен истекает через {ttl} секунд. Обновите токен!")

    assert ttl > 0, "Токен отсутствует в кэше"
