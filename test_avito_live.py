# test_avito_live.py
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.services.avito.auth import AvitoAuthManager
from app.services.avito.client import AvitoAPIClient

async def test_auth():
    """Тест OAuth авторизации"""
    print("=" * 50)
    print("🔐 Тест 1: OAuth 2.0 авторизация")
    print("=" * 50)
    
    try:
        auth = AvitoAuthManager()
        
        # Первый запрос
        print("\n1️⃣ Запрашиваем токен (первый раз)...")
        token1 = await auth.get_access_token()
        print(f"✅ Токен получен: {token1[:30]}...")
        print(f"   Длина токена: {len(token1)} символов")
        
        # Второй запрос (из кэша)
        print("\n2️⃣ Запрашиваем токен повторно (из кэша)...")
        token2 = await auth.get_access_token()
        print(f"✅ Токен получен: {token2[:30]}...")
        
        # Проверка кэширования
        if token1 == token2:
            print("\n✅ УСПЕХ! Кэширование работает!")
            return True
        else:
            print("\n❌ ОШИБКА! Токены разные (кэш не работает)")
            return False
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_client():
    """Тест AvitoAPIClient"""
    print("\n" + "=" * 50)
    print("🤖 Тест 2: AvitoAPIClient")
    print("=" * 50)
    
    try:
        client = AvitoAPIClient()
        
        print("\n3️⃣ Проверяем инициализацию клиента...")
        print(f"✅ Клиент создан: {client.__class__.__name__}")
        print(f"   Base URL: {client.base_url if hasattr(client, 'base_url') else 'N/A'}")
        
        # Пока не делаем реальные запросы к API
        print("\n⚠️  Реальные запросы к Messenger/Items API делаем после T012")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("\n" + "🚀" * 25)
    print("ТЕСТИРОВАНИЕ AVITO API CLIENT (T011)")
    print("🚀" * 25)
    
    # Тест 1: OAuth
    result1 = await test_auth()
    
    # Тест 2: Client
    result2 = await test_client()
    
    # Итоги
    print("\n" + "=" * 50)
    print("📊 ИТОГИ:")
    print("=" * 50)
    print(f"  OAuth 2.0:        {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"  AvitoAPIClient:   {'✅ PASS' if result2 else '❌ FAIL'}")
    print("=" * 50)
    
    if result1 and result2:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! T011 ГОТОВ!")
        return 0
    else:
        print("\n⚠️  ЕСТЬ ОШИБКИ. НУЖНЫ ИСПРАВЛЕНИЯ.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
