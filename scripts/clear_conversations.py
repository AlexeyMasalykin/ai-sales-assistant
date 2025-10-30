#!/usr/bin/env python3
"""
Скрипт для очистки истории диалогов Avito из Redis.

Удаляет:
- avito:conversation:* - история диалогов
- avito:contact_id:* - кэш контактов

НЕ удаляет:
- amocrm:tokens - OAuth токены amoCRM
- telegram:* - данные Telegram
- Другие данные

Использование:
    python scripts/clear_conversations.py
    # или в Docker:
    docker-compose exec -T app python scripts/clear_conversations.py
"""

import asyncio
import sys

from loguru import logger

from app.core.redis_client import get_redis_client


async def clear_conversations():
    """Очистить историю диалогов Avito из Redis."""
    redis = await get_redis_client()
    
    logger.info("="*70)
    logger.info("🧹 ОЧИСТКА ИСТОРИИ ДИАЛОГОВ AVITO")
    logger.info("="*70)
    
    patterns_to_delete = [
        "avito:conversation:*",
        "avito:contact_id:*",
    ]
    
    total_deleted = 0
    details = {}
    
    for pattern in patterns_to_delete:
        logger.info(f"\n🔍 Поиск ключей: {pattern}")
        
        cursor = 0
        keys_batch = []
        
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            keys_batch.extend(keys)
            
            if cursor == 0:
                break
        
        if keys_batch:
            logger.info(f"✅ Найдено {len(keys_batch)} ключей")
            
            # Показываем примеры (первые 5)
            if len(keys_batch) <= 5:
                for key in keys_batch:
                    logger.info(f"   - {key}")
            else:
                for key in keys_batch[:3]:
                    logger.info(f"   - {key}")
                logger.info(f"   ... и еще {len(keys_batch) - 3} ключей")
            
            # Удаляем
            for key in keys_batch:
                await redis.delete(key)
                total_deleted += 1
            
            details[pattern] = len(keys_batch)
            logger.info(f"✅ Удалено {len(keys_batch)} ключей по паттерну {pattern}")
        else:
            logger.info(f"ℹ️  Ключей не найдено по паттерну {pattern}")
            details[pattern] = 0
    
    logger.info("")
    logger.info("="*70)
    logger.info(f"🎉 ОЧИСТКА ЗАВЕРШЕНА")
    logger.info("="*70)
    logger.info(f"Всего удалено: {total_deleted} ключей")
    
    for pattern, count in details.items():
        logger.info(f"  {pattern}: {count} ключей")
    
    # Проверяем, что токены amoCRM остались
    logger.info("")
    amocrm_tokens = await redis.get("amocrm:tokens")
    if amocrm_tokens:
        logger.info("✅ Токены amoCRM сохранены (авторизация не затронута)")
    else:
        logger.warning("⚠️  Токены amoCRM не найдены (возможно, еще не было авторизации)")
    
    logger.info("="*70)
    logger.info("✅ Готово! Теперь можно начать новый диалог.")
    logger.info("="*70)


async def main():
    """Главная функция."""
    try:
        await clear_conversations()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"❌ Ошибка: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

