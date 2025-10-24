"""Векторный поиск по документам базы знаний."""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

        async with session_factory() as session:
            # Используем литеральную подстановку для embedding (f-string),
            # так как параметры не работают с большими векторами в pgvector
            # NOTE: Не используем ORDER BY с той же операцией <=> -
            # это ломает запрос с литеральными строками
            # Увеличиваем выборку кандидатов, затем переупорядочиваем по ключевым словам
            candidates_limit = max(50, limit * 50)
            sql_query = f"""
                SELECT id,
                       title,
                       content,
                       embedding <=> '{embedding_str}'::vector AS distance
                FROM documents
                LIMIT {candidates_limit}
            """

            result = await session.execute(text(sql_query))
            all_rows = result.fetchall()

            # Ре-ранжирование: повышаем приоритет документов
            # с вхождениями терминов запроса
            query_terms = [t for t in query.lower().split() if len(t) >= 4]

            def keyword_score(title: str, content: str) -> int:
                title_l = title.lower() if title else ""
                content_l = content.lower() if content else ""
                score = 0
                for term in query_terms:
                    if term in title_l:
                        score += 2
                    if term in content_l:
                        score += 1
                return score

            # Сортируем по (минус счёт по ключевым словам, distance)
            sorted_rows = sorted(
                all_rows,
                key=lambda r: (
                    -keyword_score(r[1], r[2]),
                    float(r[3]),
                ),
            )

            rows = sorted_rows[:limit]

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
