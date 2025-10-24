"""Сервис генерации векторных представлений через OpenAI."""

from __future__ import annotations


from loguru import logger
from openai import AsyncOpenAI
from typing import Optional

from app.core.settings import settings


class EmbeddingsService:
    """Сервис генерации embeddings с использованием OpenAI API."""

    def __init__(self) -> None:
        self.client: Optional[AsyncOpenAI]
        api_key = settings.openai_api_key
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key.get_secret_value(), timeout=90.0)
        else:
            self.client = None
            logger.warning("OpenAI API key не настроен — embeddings недоступны.")

        self.model = "text-embedding-3-small"
        self.dimensions = 1_536

    async def generate_embedding(self, text: str) -> list[float]:
        """Возвращает embedding для указанного текста."""
        if not self.client:
            raise RuntimeError("OpenAI клиент не инициализирован.")

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка генерации embedding: {}", exc)
            raise

        embedding = list(response.data[0].embedding)
        logger.debug(
            "Получен embedding длиной %s для текста из %s символов.",
            len(embedding),
            len(text),
        )
        return embedding

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Генерирует embeddings для списка текстов одной загрузкой."""
        if not self.client:
            raise RuntimeError("OpenAI клиент не инициализирован.")

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка batch генерации embeddings: {}", exc)
            raise

        embeddings = [list(item.embedding) for item in response.data]
        logger.info("Создано %s embeddings.", len(embeddings))
        return embeddings


embeddings_service = EmbeddingsService()
