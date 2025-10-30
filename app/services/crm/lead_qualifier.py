"""Умная квалификация лидов через OpenAI GPT."""
from __future__ import annotations

import json
from typing import Literal

from loguru import logger
from openai import AsyncOpenAI

from app.core.settings import settings

LeadStage = Literal[
    "first_contact",  # Первичный контакт
    "negotiation",  # Переговоры
    "decision",  # Принимают решение
    "contract",  # Согласование договора
]

LeadTemperature = Literal["cold", "warm", "hot"]


class LeadQualificationResult:
    """Результат квалификации лида."""

    def __init__(
        self,
        stage: LeadStage,
        temperature: LeadTemperature,
        confidence: float,
        reasoning: str,
        status_id: int,
    ):
        self.stage = stage
        self.temperature = temperature
        self.confidence = confidence
        self.reasoning = reasoning
        self.status_id = status_id


class LeadQualifier:
    """Сервис для квалификации лидов через OpenAI GPT."""

    STAGE_TO_STATUS = {
        "first_contact": 80984178,
        "negotiation": 80984182,
        "decision": 80984186,
        "contract": 80984190,
    }

    STAGE_ORDER = {
        "first_contact": 1,
        "negotiation": 2,
        "decision": 3,
        "contract": 4,
    }

    PIPELINE_ID = 10230522

    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        api_key = (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else None
        )
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            logger.warning("OpenAI API key не настроен. LLM квалификация недоступна.")

    async def qualify_lead(
        self,
        conversation_history: str,
        user_message: str,
        source: str = "unknown",
    ) -> LeadQualificationResult:
        """Квалифицирует лид на основе диалога."""
        if not self.client:
            logger.warning("OpenAI недоступен, используем fallback квалификацию")
            return self._fallback_qualification(user_message)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            conversation_history,
            user_message,
            source,
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content or "{}"
            return self._parse_llm_response(result_text)

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка OpenAI квалификации: {exc}")
            return self._fallback_qualification(user_message)

    def _build_system_prompt(self) -> str:
        """Создаёт system prompt для OpenAI."""
        return """Ты — эксперт по квалификации лидов в B2B продажах AI-решений.

Твоя задача — анализировать диалоги с потенциальными клиентами и определять:
1. Этап воронки продаж
2. Температуру лида (готовность к покупке)

ЭТАПЫ ВОРОНКИ:
- **first_contact**: Первое обращение, общие вопросы, изучение продукта
- **negotiation**: Обсуждение деталей, вопросы о функционале, цене, сроках
- **decision**: Готовность купить, запрос КП, уточнение условий, сравнение вариантов
- **contract**: Обсуждение договора, согласование сроков, готовность к оплате

ТЕМПЕРАТУРА ЛИДА:
- **cold**: Только изучает, много вопросов, нет готовности покупать
- **warm**: Заинтересован, уточняет детали, может купить в будущем
- **hot**: Готов купить сейчас, просит КП/договор, обсуждает оплату

ФОРМАТ ОТВЕТА (строго JSON):
{
  "stage": "first_contact|negotiation|decision|contract",
  "temperature": "cold|warm|hot",
  "confidence": 0.0-1.0,
  "reasoning": "краткое объяснение (1-2 предложения)"
}

ПРИМЕРЫ:

Входные данные:
Сообщение: "Здравствуйте, расскажите про AI Manager"

Ответ:
{
  "stage": "first_contact",
  "temperature": "cold",
  "confidence": 0.9,
  "reasoning": "Первичный запрос информации, нет признаков готовности к покупке"
}

---

Входные данные:
Сообщение: "Сколько стоит внедрение для компании на 50 человек?"

Ответ:
{
  "stage": "negotiation",
  "temperature": "warm",
  "confidence": 0.85,
  "reasoning": "Конкретный вопрос о цене под свои параметры, есть интерес"
}

---

Входные данные:
Сообщение: "Хочу купить AI Manager, отправьте КП и договор"

Ответ:
{
  "stage": "decision",
  "temperature": "hot",
  "confidence": 0.95,
  "reasoning": "Явное намерение купить, запрос документов для оформления"
}

---

Входные данные:
Сообщение: "Согласны на ваши условия, когда можем подписать договор?"

Ответ:
{
  "stage": "contract",
  "temperature": "hot",
  "confidence": 0.98,
  "reasoning": "Согласие на условия, готовность к подписанию"
}

Всегда отвечай только валидным JSON в указанном формате."""

    def _build_user_prompt(
        self,
        conversation_history: str,
        user_message: str,
        source: str,
    ) -> str:
        """Создаёт user prompt."""
        return f"""Проанализируй диалог и определи этап воронки и температуру лида.

КОНТЕКСТ:
Источник: {source}

История диалога:
{conversation_history}

Последнее сообщение клиента:
{user_message}

Верни JSON с квалификацией лида."""

    def _parse_llm_response(self, response_text: str) -> LeadQualificationResult:
        """Парсит ответ OpenAI."""
        try:
            data = json.loads(response_text)

            stage = data.get("stage", "first_contact")
            temperature = data.get("temperature", "cold")
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            if stage not in self.STAGE_TO_STATUS:
                logger.warning("Неизвестный stage '%s', используем first_contact", stage)
                stage = "first_contact"

            status_id = self.STAGE_TO_STATUS[stage]

            logger.info(
                "✅ OpenAI квалификация: stage=%s, temp=%s, confidence=%.2f",
                stage,
                temperature,
                confidence,
            )
            logger.debug("Reasoning: %s", reasoning)

            return LeadQualificationResult(
                stage=stage,
                temperature=temperature,
                confidence=confidence,
                reasoning=reasoning,
                status_id=status_id,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка парсинга OpenAI ответа: %s", exc)
            logger.debug("Ответ OpenAI: %s", response_text)
            return self._fallback_qualification("")

    def _fallback_qualification(self, user_message: str) -> LeadQualificationResult:
        """Простая квалификация без LLM (fallback).
        
        ВАЖНО: fallback используется только при ошибках GPT.
        По умолчанию всегда возвращаем first_contact для безопасности.
        """
        text_lower = user_message.lower()

        # Только очень явные триггеры для продвинутых стадий
        very_hot_triggers = [
            "хочу купить",
            "готов купить",
            "отправьте кп",
            "отправьте счет",
            "готовы подписать",
        ]

        warm_triggers = [
            "сколько стоит",
            "какая цена",
            "какая стоимость",
        ]

        # Очень явные триггеры решения
        if any(trigger in text_lower for trigger in very_hot_triggers):
            return LeadQualificationResult(
                stage="decision",
                temperature="hot",
                confidence=0.6,
                reasoning="Явное намерение купить (fallback)",
                status_id=self.STAGE_TO_STATUS["decision"],
            )

        # Вопросы о цене
        if any(trigger in text_lower for trigger in warm_triggers):
            return LeadQualificationResult(
                stage="negotiation",
                temperature="warm",
                confidence=0.5,
                reasoning="Вопросы о цене (fallback)",
                status_id=self.STAGE_TO_STATUS["negotiation"],
            )

        # DEFAULT: всегда first_contact для безопасности
        return LeadQualificationResult(
            stage="first_contact",
            temperature="warm",
            confidence=0.5,
            reasoning="Первичное обращение (fallback)",
            status_id=self.STAGE_TO_STATUS["first_contact"],
        )

    @classmethod
    def should_update_stage(
        cls,
        current_status_id: int,
        new_status_id: int,
    ) -> bool:
        """
        Определяет, нужно ли двигать лид вперёд по воронке.

        Лид может переходить только на более поздние этапы.
        """
        status_to_stage = {status: stage for stage, status in cls.STAGE_TO_STATUS.items()}

        current_stage = status_to_stage.get(current_status_id)
        new_stage = status_to_stage.get(new_status_id)

        if not current_stage or not new_stage:
            logger.warning(
                "Неизвестный status_id: current=%s, new=%s",
                current_status_id,
                new_status_id,
            )
            return False

        current_order = cls.STAGE_ORDER.get(current_stage, 0)
        new_order = cls.STAGE_ORDER.get(new_stage, 0)

        should_update = new_order > current_order

        if should_update:
            logger.info(
                "📈 Прогресс: %s (%s) → %s (%s)",
                current_stage,
                current_order,
                new_stage,
                new_order,
            )
        else:
            logger.debug(
                "⏸️  Статус не изменился или откат: %s → %s",
                current_stage,
                new_stage,
            )

        return should_update


lead_qualifier = LeadQualifier()
