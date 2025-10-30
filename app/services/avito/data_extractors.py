"""Извлечение данных из сообщений клиента."""
from __future__ import annotations

import json
import re
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.settings import settings
from app.models.conversation import ExtractionResult
from app.services.avito.prompt_loader import PromptLoader


class BaseExtractor:
    """Базовый класс для экстракторов."""

    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        api_key = (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else None
        )
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)

        self.prompt_loader = PromptLoader(
            settings.prompts_dir or "app/services/avito/prompts"
        )


class NameExtractor(BaseExtractor):
    """Извлекает имя клиента из текста."""

    async def extract(self, message: str) -> ExtractionResult:
        """Извлечь имя из сообщения."""
        if not self.client:
            return ExtractionResult(
                value=None,
                confidence=0.0,
                reasoning="OpenAI недоступен",
            )

        try:
            system, user = self.prompt_loader.get_prompt(
                "extraction.poml",
                "extract_name",
                message=message,
            )

            response = await self.client.chat.completions.create(
                model=settings.openai_extraction_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content or "{}"
            data = json.loads(result_text)

            return ExtractionResult(
                value=data.get("name"),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка извлечения имени: {exc}")
            return ExtractionResult(
                value=None,
                confidence=0.0,
                reasoning=f"Ошибка: {str(exc)}",
            )


class PhoneExtractor(BaseExtractor):
    """Извлекает телефон из текста."""

    PHONE_PATTERNS = [
        r"\+7\s*[\(]?\d{3}[\)]?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        r"8\s*[\(]?\d{3}[\)]?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        r"7\s*[\(]?\d{3}[\)]?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        r"\d{10}",
    ]

    async def extract(self, message: str) -> ExtractionResult:
        """Извлечь телефон из сообщения."""
        phone = self._extract_with_regex(message)

        if phone:
            return ExtractionResult(
                value=phone,
                confidence=0.9,
                reasoning="Найден через regex",
            )

        return ExtractionResult(
            value=None,
            confidence=0.0,
            reasoning="Телефон не найден",
        )

    def _extract_with_regex(self, text: str) -> Optional[str]:
        """Извлечь телефон через regex."""
        for pattern in self.PHONE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0)
                digits = re.sub(r"\D", "", phone)

                if len(digits) == 10:
                    return f"+7{digits}"
                if len(digits) == 11:
                    if digits[0] == "8":
                        return f"+7{digits[1:]}"
                    if digits[0] == "7":
                        return f"+{digits}"

                return f"+{digits}"

        return None


class NeedExtractor(BaseExtractor):
    """Извлекает потребность (боль) клиента."""

    async def extract(
        self,
        conversation_history: str,
        user_message: str,
    ) -> ExtractionResult:
        """Определить потребность клиента."""
        if not self.client:
            return ExtractionResult(
                value=None,
                confidence=0.0,
                reasoning="OpenAI недоступен",
            )

        try:
            system, user = self.prompt_loader.get_prompt(
                "extraction.poml",
                "extract_need",
                conversation_history=conversation_history,
                user_message=user_message,
            )

            response = await self.client.chat.completions.create(
                model=settings.openai_extraction_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content or "{}"
            data = json.loads(result_text)

            pain = data.get("pain_point")
            product = data.get("product_interest")

            value = None
            if pain:
                value = json.dumps(
                    {
                        "pain_point": pain,
                        "product_interest": product,
                    }
                )

            return ExtractionResult(
                value=value,
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ошибка извлечения потребности: {exc}")
            return ExtractionResult(
                value=None,
                confidence=0.0,
                reasoning=f"Ошибка: {str(exc)}",
            )
