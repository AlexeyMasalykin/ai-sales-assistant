"""Модели для диалоговой системы Avito."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Состояния FSM диалога."""

    START = "start"
    GREETING = "greeting"
    NAME_COLLECTED = "name_collected"
    NEED_IDENTIFIED = "need_identified"
    PHONE_COLLECTED = "phone_collected"
    QUALIFIED = "qualified"


class MessageRole(str, Enum):
    """Роль автора сообщения."""

    USER = "user"
    BOT = "bot"


class ConversationMessage(BaseModel):
    """Сообщение в диалоге."""

    timestamp: datetime
    role: MessageRole
    text: str


class ExtractionAttempts(BaseModel):
    """Счётчик попыток извлечения данных."""

    name: int = 0
    phone: int = 0
    need: int = 0


class ConversationMetadata(BaseModel):
    """Метаданные диалога."""

    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    extraction_attempts: ExtractionAttempts = Field(default_factory=ExtractionAttempts)


class ConversationContext(BaseModel):
    """Полный контекст диалога."""

    chat_id: str
    state: ConversationState = ConversationState.START
    user_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    pain_point: Optional[str] = None
    product_interest: Optional[str] = None
    messages: list[ConversationMessage] = Field(default_factory=list)
    metadata: ConversationMetadata

    def add_message(self, role: MessageRole, text: str) -> None:
        """Добавить сообщение в историю."""
        self.messages.append(
            ConversationMessage(timestamp=datetime.utcnow(), role=role, text=text)
        )
        self.metadata.message_count += 1
        self.metadata.updated_at = datetime.utcnow()

    def get_history_text(self, last_n: Optional[int] = None) -> str:
        """Получить историю в текстовом формате."""
        messages = self.messages[-last_n:] if last_n else self.messages
        return "\n".join(
            f"{'Клиент' if msg.role == MessageRole.USER else 'Бот'}: {msg.text}"
            for msg in messages
        )

    def has_required_data(self) -> bool:
        """Проверка, все ли обязательные данные собраны."""
        return all([self.user_name, self.phone, self.pain_point])


class ExtractionResult(BaseModel):
    """Результат извлечения данных."""

    value: Optional[str]
    confidence: float
    reasoning: str
