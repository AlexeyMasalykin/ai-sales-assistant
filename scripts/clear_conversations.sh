#!/bin/bash
# Скрипт для очистки истории диалогов Avito из Redis
# Сохраняет токены amoCRM и другие важные данные

cd "$(dirname "$0")/.." || exit

echo "======================================================================"
echo "🧹 ОЧИСТКА ИСТОРИИ ДИАЛОГОВ AVITO"
echo "======================================================================"
echo ""
echo "Что будет удалено:"
echo "  ❌ avito:conversation:* - история диалогов"
echo "  ❌ avito:contact_id:* - кэш контактов"
echo ""
echo "Что НЕ будет удалено:"
echo "  ✅ amocrm:tokens - OAuth токены amoCRM"
echo "  ✅ telegram:* - данные Telegram"
echo "  ✅ Другие данные"
echo ""
echo "======================================================================"
echo ""

read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Отменено"
    exit 1
fi

echo ""
echo "🔄 Запуск очистки..."
echo ""

docker-compose exec -T app python << 'EOF'
import asyncio
from app.core.redis_client import get_redis_client

async def clear_redis():
    redis = await get_redis_client()
    
    patterns_to_delete = [
        "avito:conversation:*",
        "avito:contact_id:*",
    ]
    
    total_deleted = 0
    
    for pattern in patterns_to_delete:
        print(f"🔍 Поиск: {pattern}")
        
        cursor = 0
        keys_batch = []
        
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            keys_batch.extend(keys)
            if cursor == 0:
                break
        
        if keys_batch:
            print(f"   ✅ Найдено: {len(keys_batch)} ключей")
            
            for key in keys_batch:
                await redis.delete(key)
                total_deleted += 1
                if len(keys_batch) <= 10:
                    print(f"      - {key}")
        else:
            print(f"   ℹ️  Ключей не найдено")
    
    print(f"\n{'='*60}")
    print(f"🎉 Очистка завершена! Удалено: {total_deleted} ключей")
    
    # Проверяем токены amoCRM
    amocrm_tokens = await redis.get("amocrm:tokens")
    if amocrm_tokens:
        print("✅ Токены amoCRM сохранены")
    else:
        print("⚠️  Токены amoCRM не найдены (возможно не было авторизации)")
    
    print(f"{'='*60}")

asyncio.run(clear_redis())
EOF

echo ""
echo "✅ Готово! Теперь можно начать новый диалог с чистой историей."

