"""Интеграционные тесты FSM диалога."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.conversation import ConversationState
from app.services.avito.conversation_manager import AvitoConversationManager


def create_mock_openai_client():
    """Создает мок OpenAI клиента для тестов."""
    call_count = {"count": 0}

    async def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        system_content = messages[0].get("content", "") if messages else ""
        user_content = messages[1].get("content", "") if len(messages) > 1 else ""

        mock_message = MagicMock()

        # Extraction запросы (JSON response)
        if "эксперт по извлечению" in system_content.lower():
            if "имён" in system_content.lower():
                if "Иван" in user_content:
                    mock_message.content = (
                        '{"name": "Иван", "confidence": 0.95, "reasoning": "Явное указание имени"}'
                    )
                else:
                    mock_message.content = (
                        '{"name": null, "confidence": 0.0, "reasoning": "Имени нет"}'
                    )
            elif "болей и потребностей" in system_content.lower():
                if "CRM" in user_content or "crm" in user_content.lower():
                    mock_message.content = '{"pain_point": "Менеджеры тратят 2 часа в день на CRM", "product_interest": "AI Manager", "confidence": 0.9, "reasoning": "Чёткая проблема с CRM"}'
                else:
                    mock_message.content = (
                        '{"pain_point": null, "product_interest": null, "confidence": 0.0, "reasoning": "Боль не выявлена"}'
                    )
        # Conversation запросы (обычный текст)
        else:
            call_count["count"] += 1
            if call_count["count"] == 1:
                mock_message.content = (
                    "Здравствуйте! 👋 Я AI-ассистент. Как мне к вам обращаться?"
                )
            elif call_count["count"] == 2:
                mock_message.content = "Приятно познакомиться, Иван! 😊 Расскажите, какие задачи хотите решить?"
            elif call_count["count"] == 3:
                mock_message.content = "Понимаю вас, Иван. Ручная работа с CRM — это серьёзная проблема. Чтобы подготовить индивидуальное предложение, оставьте, пожалуйста, ваш телефон."
            else:
                mock_message.content = "Спасибо, Иван! ✅ Я передал вашу заявку специалисту — он свяжется с вами в течение часа."

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    return MagicMock(return_value=mock_client)


@pytest.mark.asyncio
async def test_full_conversation_flow(fake_redis):
    """Тест полного цикла прогрева лида."""
    mock_async_openai = create_mock_openai_client()

    with patch("openai.AsyncOpenAI", mock_async_openai):
    manager = AvitoConversationManager()
    chat_id = "test_chat_integration"

        # Шаг 1: Приветствие
    response1 = await manager.handle_message(
        chat_id,
        "Здравствуйте, интересует автоматизация",
    )
    assert "обращаться" in response1.lower()

    context = await manager.get_context(chat_id)
    assert context.state == ConversationState.GREETING

        # Шаг 2: Имя
    response2 = await manager.handle_message(chat_id, "Меня зовут Иван")
    assert "иван" in response2.lower()

    context = await manager.get_context(chat_id)
    assert context.state == ConversationState.NAME_COLLECTED
    assert context.user_name == "Иван"

        # Шаг 3: Потребность
    response3 = await manager.handle_message(
        chat_id,
        "Менеджеры тратят 2 часа в день на CRM",
    )

    context = await manager.get_context(chat_id)
    assert context.state == ConversationState.NEED_IDENTIFIED
    assert context.pain_point is not None

        # Шаг 4: Телефон
    response4 = await manager.handle_message(chat_id, "+7 999 123-45-67")
    assert "передал" in response4.lower() or "специалист" in response4.lower()

    context = await manager.get_context(chat_id)
    assert context.state == ConversationState.QUALIFIED
    assert context.phone == "+79991234567"

        # Очистка
        await fake_redis.delete(f"avito:conversation:{chat_id}")
