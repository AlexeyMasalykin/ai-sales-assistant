"""Интеграционные тесты OAuth 2.0 для Avito."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.services.avito.auth import AvitoAuthManager
from app.services.avito.exceptions import AvitoAuthError

@pytest.mark.asyncio
async def test_get_access_token_success(mock_redis):
    """Получение нового access token при отсутствии кэша."""
    mock_redis.get.return_value = None
    
    mock_response = MagicMock()  # НЕ AsyncMock!
    mock_response.status_code = 200
    mock_response.json.return_value = {  # sync метод
        "access_token": "test_token_123",
        "expires_in": 86_400,
        "token_type": "Bearer",
    }
    
    with patch("app.services.avito.auth.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response,
        )
        
        auth = AvitoAuthManager()
        token = await auth.get_access_token()
    
    assert token == "test_token_123"
    mock_redis.set.assert_awaited_with("avito:access_token", "test_token_123", ex=86_400)

@pytest.mark.asyncio
async def test_token_caching(mock_redis):
    """Использование токена из Redis при достаточном TTL."""
    mock_redis.get.return_value = "cached_token"
    mock_redis.ttl.return_value = 7_200
    
    auth = AvitoAuthManager()
    token = await auth.get_access_token()
    
    assert token == "cached_token"

@pytest.mark.asyncio
async def test_token_refresh_before_expiry(mock_redis):
    """Обновление токена за час до истечения."""
    mock_redis.get.return_value = "old_token"
    mock_redis.ttl.return_value = 200  # < 3600
    
    mock_response = MagicMock()  # НЕ AsyncMock!
    mock_response.status_code = 200
    mock_response.json.return_value = {  # sync метод
        "access_token": "new_token_456",
        "expires_in": 86_400,
        "token_type": "Bearer",
    }
    
    with patch("app.services.avito.auth.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response,
        )
        
        auth = AvitoAuthManager()
        token = await auth.get_access_token()
    
    assert token == "new_token_456"

@pytest.mark.asyncio
async def test_auth_error_401():
    """Обработка ошибки 401 от Avito."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    
    with patch("app.services.avito.auth.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response,
        )
        with patch("app.services.avito.auth.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            
            auth = AvitoAuthManager()
            
            with pytest.raises(AvitoAuthError):
                await auth.get_access_token()
