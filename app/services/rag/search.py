"""Векторный поиск по документам базы знаний."""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import text

from app.core.database import session_factory
from app.services.rag.embeddings import embeddings_service


class DocumentSearch:
    """Выполняет векторный поиск документов по запросу пользователя."""

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Возвращает релевантные документы для указанного запроса."""
        logger.info("RAG поиск документов: '%s' (limit=%s)", query[:50], limit)

        query_embedding = await embeddings_service.generate_embedding(query)

        # Преобразуем в PostgreSQL array format: [1.0, 2.0, 3.0]
        # Ограничиваем точность до 8 знаков (как в PostgreSQL float)
        embedding_str = "[" + ",".join(f"{x:.8g}" for x in query_embedding) + "]"

        async with session_factory() as session:  # type: ignore[misc]
            # Используем литеральную подстановку для embedding (f-string),
            # так как параметры не работают с большими векторами в pgvector
            # NOTE: Не используем ORDER BY с той же операцией <=> -
            # это ломает запрос с литеральными строками
            sql_query = f"""
                SELECT id,
                       title,
                       content,
                       embedding <=> '{embedding_str}'::vector AS distance
                FROM documents
                LIMIT {limit * 10}
            """

            result = await session.execute(text(sql_query))
            all_rows = result.fetchall()

            # Сортируем в Python и берем топ-N
            rows = sorted(all_rows, key=lambda r: r[3])[:limit]

        documents: list[dict[str, Any]] = [
            {
                "id": str(row[0]),
                "title": row[1],
                "content": row[2],
                "similarity": 1.0 - float(row[3]),  # Конвертируем distance в similarity
            }
            for row in rows
        ]

        logger.info("Найдено %s релевантных документов.", len(documents))
        return documents


document_search = DocumentSearch()
