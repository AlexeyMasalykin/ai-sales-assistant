"""Синхронизация объявлений и статистики Avito."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from app.core.cache import redis_client
from app.core.settings import settings
from app.services.avito.client import AvitoAPIClient
from app.services.avito.exceptions import AvitoAPIError, AvitoRateLimitError


class AvitoSyncManager:
    """Менеджер синхронизации объявлений Avito."""

    def __init__(self) -> None:
        self.client = AvitoAPIClient()
        self.is_running = False
        self.sync_task: Optional[asyncio.Task[Any]] = None
        self._lock = asyncio.Lock()

    async def start_sync(self, interval_minutes: Optional[int] = None) -> None:
        """Запускает периодическую синхронизацию объявлений.

        Args:
            interval_minutes: Интервал синхронизации в минутах.
        """
        async with self._lock:
            if self.is_running:
                logger.warning("Синхронизация Avito уже запущена.")
                return

            if interval_minutes is None:
                interval_minutes = settings.avito_sync_interval_minutes

            self.is_running = True
            logger.info(
                "Старт синхронизации Avito (интервал: %s мин).",
                interval_minutes,
            )

            self.sync_task = asyncio.create_task(
                self._sync_loop(interval_minutes),
                name="avito-sync",
            )

    async def stop_sync(self) -> None:
        """Останавливает синхронизацию объявлений."""
        async with self._lock:
            if not self.is_running:
                return

            self.is_running = False
            if self.sync_task:
                self.sync_task.cancel()
                try:
                    await self.sync_task
                except asyncio.CancelledError:
                    logger.debug("Задача синхронизации Avito отменена.")
                finally:
                    self.sync_task = None

            logger.info("Синхронизация Avito остановлена.")

    async def _sync_loop(self, interval_minutes: int) -> None:
        """Периодический цикл синхронизации объявлений."""
        try:
            while self.is_running:
                await self.sync_all_items()
                await asyncio.sleep(max(1, interval_minutes) * 60)
        except asyncio.CancelledError:
            logger.debug("Цикл синхронизации Avito завершён (отмена).")
        except Exception as exc:  # noqa: BLE001
            logger.error("Критическая ошибка цикла синхронизации Avito: {}", exc)
            await asyncio.sleep(60)

    async def sync_all_items(self) -> dict[str, Any]:
        """Синхронизирует все объявления и сохраняет статистику.

        Returns:
            Сводная статистика синхронизации.
        """
        logger.info("Начало синхронизации объявлений Avito.")
        stats: dict[str, Any] = {
            "total_items": 0,
            "synced": 0,
            "failed": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            items = await self.client.get_items()
            stats["total_items"] = len(items)
        except AvitoAPIError as exc:
            logger.error("Не удалось получить список объявлений Avito: {}", exc)
            raise

        for item in items:
            item_id = item.get("id")
            if not item_id:
                logger.warning("Пропущено объявление без ID: {}", item)
                continue
            try:
                await self._sync_single_item(item_id)
                stats["synced"] += 1
            except AvitoRateLimitError as exc:
                stats["failed"] += 1
                retry_after = exc.retry_after or 60
                logger.warning(
                    "Превышен лимит Avito при синхронизации %s. Повтор через %s секунд.",
                    item_id,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
            except AvitoAPIError as exc:
                stats["failed"] += 1
                logger.warning("Ошибка Avito при синхронизации %s: %s", item_id, exc)
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                logger.warning("Неожиданная ошибка синхронизации %s: %s", item_id, exc)

        logger.info(
            "Синхронизация завершена: %s успешно, %s с ошибками.",
            stats["synced"],
            stats["failed"],
        )
        await redis_client.set(
            "avito:last_sync_stats",
            json.dumps(stats),
            ex=settings.avito_cache_ttl_seconds,
        )
        return stats

    async def _sync_single_item(self, item_id: str) -> None:
        """Синхронизирует статистику одного объявления."""
        logger.debug("Сбор статистики Avito для объявления %s.", item_id)
        stats = await self.client.get_item_stats(item_id)
        cache_key = f"avito:item:{item_id}"
        await redis_client.setex(
            cache_key,
            settings.avito_cache_ttl_seconds,
            json.dumps(stats),
        )

    async def get_item_statistics(self, item_id: str) -> dict[str, Any]:
        """Возвращает статистику объявления из кэша либо Avito API."""
        cache_key = f"avito:item:{item_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug("Статистика объявления %s получена из кэша.", item_id)
            try:
                data = json.loads(cached)
            except json.JSONDecodeError:
                data = cached
            return {"cached": True, "data": data}

        logger.info("Получение свежей статистики Avito для %s.", item_id)
        stats = await self.client.get_item_stats(item_id)
        await redis_client.setex(
            cache_key,
            settings.avito_cache_ttl_seconds,
            json.dumps(stats),
        )
        return {"cached": False, "data": stats}

    async def apply_vas_service(self, item_id: str, service_code: str) -> dict[str, Any]:
        """Применяет VAS-услугу к объявлению (заглушка)."""
        logger.info("Применение VAS '%s' к объявлению %s.", service_code, item_id)
        result = {
            "item_id": item_id,
            "service": service_code,
            "status": "applied",
            "timestamp": datetime.utcnow().isoformat(),
        }
        # TODO: заменить на реальный вызов Avito API, когда он появится в клиенте.
        return result


sync_manager = AvitoSyncManager()
