"""Веб-чат API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from app.services.rag.answer import answer_generator
from app.services.web.chat_session import session_manager

router = APIRouter(prefix="/chat", tags=["chat"])


class SessionCreate(BaseModel):
    user_name: str | None = None
    metadata: dict | None = None


class SessionResponse(BaseModel):
    session_id: str
    user_name: str


class MessageSend(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(data: SessionCreate) -> SessionResponse:
    """Создаёт новую сессию чата."""
    session_id = await session_manager.create_session(
        user_name=data.user_name,
        metadata=data.metadata,
    )

    session = await session_manager.get_session(session_id)
    if not session:
        logger.error("Не удалось получить созданную сессию {}", session_id)
        raise HTTPException(status_code=500, detail="Failed to create session")

    return SessionResponse(
        session_id=session_id,
        user_name=session["user_name"],
    )


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 50) -> dict:
    """Получает историю сообщений."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await session_manager.get_messages(session_id, limit)

    return {
        "session_id": session_id,
        "messages": messages,
        "total": len(messages),
    }


@router.post("/messages")
async def send_message(data: MessageSend) -> dict:
    """Отправляет сообщение и получает ответ."""
    session = await session_manager.get_session(data.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session_manager.add_message(
        data.session_id,
        "user",
        data.message,
    )

    answer = await answer_generator.generate_answer(
        data.message,
        session["user_name"],
    )

    await session_manager.add_message(
        data.session_id,
        "assistant",
        answer,
    )

    await session_manager.extend_session(data.session_id)

    return {
        "message": answer,
        "session_id": data.session_id,
    }


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket для real-time чата."""
    await websocket.accept()

    logger.info("WebSocket подключен для сессии {}", session_id)

    session = await session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message")

            if not message:
                continue

            logger.debug(
                "WS сообщение от {}: {}",
                session_id,
                message[:50],
            )

            await session_manager.add_message(session_id, "user", message)

            answer = await answer_generator.generate_answer(
                message,
                session["user_name"],
            )

            await session_manager.add_message(session_id, "assistant", answer)

            await websocket.send_json(
                {
                    "role": "assistant",
                    "content": answer,
                },
            )

            await session_manager.extend_session(session_id)

    except WebSocketDisconnect:
        logger.info("WebSocket отключен для сессии {}", session_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка WebSocket для {}: {}", session_id, exc)
        await websocket.close()
