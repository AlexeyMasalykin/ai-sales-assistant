"""Менеджер сессий веб-чата."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from loguru import logger

from app.core.cache import redis_client


class ChatSessionManager:
    """Управляет данными сессий веб-чата в Redis."""

    def __init__(self) -> None:
        self.session_ttl = 60 * 60 * 24 * 30  # 30 дней
        self.session_prefix = "chat:session:"
        self.messages_prefix = "chat:messages:"

    async def create_session(
        self,
        user_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Создаёт новую сессию чата."""
        session_id = str(uuid.uuid4())

        session_data = {
            "session_id": session_id,
            "user_name": user_name or "Гость",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "message_count": 0,
        }

        key = f"{self.session_prefix}{session_id}"
        await redis_client.setex(
            key,
            self.session_ttl,
            json.dumps(session_data),
        )

        logger.info(
            "Создана сессия {} для пользователя {}",
            session_id,
            session_data["user_name"],
        )

        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Получает данные сессии."""
        key = f"{self.session_prefix}{session_id}"
        data = await redis_client.get(key)

        if not data:
            logger.warning("Сессия {} не найдена", session_id)
            return None

        return json.loads(data)

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """Добавляет сообщение в историю сессии."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        key = f"{self.messages_prefix}{session_id}"
        await redis_client.rpush(key, json.dumps(message))
        await redis_client.expire(key, self.session_ttl)

        session = await self.get_session(session_id)
        if session:
            session["message_count"] += 1
            session_key = f"{self.session_prefix}{session_id}"
            await redis_client.setex(
                session_key,
                self.session_ttl,
                json.dumps(session),
            )

        logger.debug("Добавлено сообщение в сессию {}", session_id)

    async def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        """Получает историю сообщений сессии."""
        key = f"{self.messages_prefix}{session_id}"
        messages_json = await redis_client.lrange(key, -limit, -1)

        messages = [json.loads(msg) for msg in messages_json]

        logger.debug("Получено {} сообщений для сессии {}", len(messages), session_id)

        return messages

    async def extend_session(self, session_id: str) -> None:
        """Продлевает TTL сессии и истории сообщений."""
        session_key = f"{self.session_prefix}{session_id}"
        messages_key = f"{self.messages_prefix}{session_id}"

        await redis_client.expire(session_key, self.session_ttl)
        await redis_client.expire(messages_key, self.session_ttl)

        logger.debug("TTL сессии {} продлён", session_id)


session_manager = ChatSessionManager()
