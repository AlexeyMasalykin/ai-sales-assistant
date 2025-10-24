"""Векторный (и резервный) поиск по документам базы знаний."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import text

from app.core.database import session_factory
from app.services.rag.embeddings import embeddings_service


class DocumentSearch:
    """Выполняет поиск документов по запросу пользователя."""

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Возвращает релевантные документы для указанного запроса."""
        logger.info("RAG поиск документов: '%s' (limit=%s)", query[:50], limit)

        if embeddings_service.client is None:
            logger.debug("Используется оффлайн-поиск документов (без embeddings).")
            return self._fallback_search(query, limit)

        query_embedding = await embeddings_service.generate_embedding(query)

        embedding_str = "[" + ",".join(f"{x:.8g}" for x in query_embedding) + "]"

        async with session_factory() as session:
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
                "similarity": 1.0 - float(row[3]),
            }
            for row in rows
        ]

        logger.info("Найдено %s релевантных документов.", len(documents))
        return documents

    def _fallback_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        documents = _load_local_documents()
        if not documents:
            return []

        query_terms = [term.lower() for term in query.split() if len(term) >= 3]
        scored: list[tuple[int, dict[str, Any]]] = []

        for doc in documents:
            title = doc["title"].lower()
            content = doc["content"].lower()
            score = 0
            for term in query_terms:
                if term in title:
                    score += 3
                if term in content:
                    score += 1
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            top_docs = [item[1] for item in scored[:limit]]
        else:
            top_docs = documents[:limit]

        logger.info(
            "Найдено %s документов локальным поиском.",
            len(top_docs),
        )
        return top_docs


@lru_cache(maxsize=1)
def _load_local_documents() -> list[dict[str, Any]]:
    base_path = Path("documents/knowledge_base")
    documents: list[dict[str, Any]] = []
    if not base_path.exists():
        logger.warning("Папка %s с документами не найдена.", base_path)
        return documents

    for path in sorted(base_path.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            logger.error("Не удалось прочитать %s: %s", path, exc)
            continue
        documents.append(
            {
                "id": path.stem,
                "title": path.stem.replace("_", " ").title(),
                "content": content,
                "similarity": 0.5,
            }
        )

    return documents


document_search = DocumentSearch()
