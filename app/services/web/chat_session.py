"""Менеджер сессий диалогов (веб + Telegram)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Awaitable, Dict, List, Optional, cast

from loguru import logger

from app.core.cache import get_redis_client


class ChatSessionManager:
    """Управляет данными сессий диалогов в Redis для всех каналов."""

    def __init__(self) -> None:
        self.session_ttl = 60 * 60 * 24 * 30  # 30 дней
        self.session_prefix = "chat:session:"
        self.messages_prefix = "chat:messages:"
        self.telegram_prefix = "telegram:chat:"

    async def create_session(
        self,
        user_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Создаёт новую сессию чата."""
        session_id = str(uuid.uuid4())

        session_data: Dict[str, Any] = {
            "session_id": session_id,
            "user_name": user_name or "Гость",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "message_count": 0,
        }

        key = f"{self.session_prefix}{session_id}"
        await get_redis_client().setex(
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

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получает данные сессии."""
        key = f"{self.session_prefix}{session_id}"
        data = await get_redis_client().get(key)

        if data is None:
            logger.warning("Сессия {} не найдена", session_id)
            return None

        try:
            session = cast(Dict[str, Any], json.loads(data))
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            logger.error("Ошибка чтения данных сессии %s: %s", session_id, exc)
            return None

        return session

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """Добавляет сообщение в историю сессии."""
        message: Dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        key = f"{self.messages_prefix}{session_id}"
        redis_client = get_redis_client()
        await cast(Awaitable[int], redis_client.rpush(key, json.dumps(message)))
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

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Получает историю сообщений сессии."""
        key = f"{self.messages_prefix}{session_id}"
        redis_client = get_redis_client()
        raw_messages = await cast(
            Awaitable[List[str]],
            redis_client.lrange(key, -limit, -1),
        )

        messages: List[Dict[str, Any]] = []
        for raw_message in raw_messages:
            try:
                parsed = cast(Dict[str, Any], json.loads(raw_message))
            except (TypeError, ValueError) as exc:  # noqa: BLE001
                logger.warning(
                    "Сообщение чата %s пропущено из-за ошибки парсинга: %s",
                    session_id,
                    exc,
                )
                continue
            messages.append(parsed)

        logger.debug("Получено {} сообщений для сессии {}", len(messages), session_id)

        return messages

    async def extend_session(self, session_id: str) -> None:
        """Продлевает TTL сессии и истории сообщений."""
        session_key = f"{self.session_prefix}{session_id}"
        messages_key = f"{self.messages_prefix}{session_id}"

        redis_client = get_redis_client()
        await redis_client.expire(session_key, self.session_ttl)
        await redis_client.expire(messages_key, self.session_ttl)

        logger.debug("TTL сессии {} продлён", session_id)

    async def get_or_create_telegram_session(
        self,
        chat_id: int,
        user_name: str,
    ) -> str:
        """Получает или создаёт сессию для Telegram чата."""
        session_key = f"{self.telegram_prefix}{chat_id}"
        redis_client = get_redis_client()
        stored_session_id = await redis_client.get(session_key)

        if isinstance(stored_session_id, str) and stored_session_id:
            session_id = stored_session_id
            await self.extend_session(session_id)
            await redis_client.expire(session_key, self.session_ttl)
            logger.debug(
                "Продлена Telegram сессия {} для chat_id={}", session_id, chat_id
            )
            return session_id

        session_id = await self.create_session(
            user_name=user_name,
            metadata={"channel": "telegram", "chat_id": chat_id},
        )

        await redis_client.setex(
            session_key,
            self.session_ttl,
            session_id,
        )

        logger.info("Создана Telegram сессия {} для chat_id={}", session_id, chat_id)

        return session_id

    async def get_context_for_llm(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Получает сообщения в формате OpenAI для LLM."""
        messages = await self.get_messages(session_id, limit)

        context: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            context.append({"role": role, "content": content})

        logger.debug(
            "Сформирован контекст для LLM ({} сообщений) по сессии {}",
            len(context),
            session_id,
        )

        return context


session_manager = ChatSessionManager()
