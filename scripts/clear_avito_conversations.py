#!/usr/bin/env python3
"""Скрипт для очистки истории диалогов Avito из Redis.

Удаляет:
- avito:conversation:* - история диалогов
- avito:contact_id:* - кэш контактов

НЕ удаляет:
- amocrm:tokens - OAuth токены amoCRM
- telegram:* - данные Telegram
"""

import asyncio

from loguru import logger

from app.core.redis_client import get_redis_client


async def clear_avito_conversations():
    """Очистить историю диалогов Avito из Redis."""
    redis = await get_redis_client()
    
    # Паттерны для удаления
    patterns_to_delete = [
        "avito:conversation:*",
        "avito:contact_id:*",
    ]
    
    total_deleted = 0
    
    for pattern in patterns_to_delete:
        logger.info(f"🔍 Поиск ключей по паттерну: {pattern}")
        
        # Получаем все ключи по паттерну
        cursor = 0
        keys_batch = []
        
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            keys_batch.extend(keys)
            
            if cursor == 0:
                break
        
        if keys_batch:
            logger.info(f"✅ Найдено {len(keys_batch)} ключей")
            
            # Удаляем батчами
            for key in keys_batch:
                await redis.delete(key)
                total_deleted += 1
            
            logger.info(f"✅ Удалено {len(keys_batch)} ключей по паттерну {pattern}")
        else:
            logger.info(f"ℹ️  Ключей не найдено по паттерну {pattern}")
    
    logger.info(f"\n🎉 Очистка завершена! Всего удалено ключей: {total_deleted}")
    
    # Проверяем, что токены amoCRM остались
    amocrm_tokens = await redis.get("amocrm:tokens")
    if amocrm_tokens:
        logger.info("✅ Токены amoCRM сохранены (авторизация не затронута)")
    else:
        logger.warning("⚠️  Токены amoCRM не найдены (возможно, еще не было авторизации)")


async def main():
    """Главная функция."""
    logger.info("="*60)
    logger.info("🧹 ОЧИСТКА ИСТОРИИ ДИАЛОГОВ AVITO")
    logger.info("="*60)
    logger.info("")
    
    await clear_avito_conversations()
    
    logger.info("")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())

