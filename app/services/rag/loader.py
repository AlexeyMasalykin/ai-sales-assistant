"""Загрузчик документов в базу данных."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from sqlalchemy import text

from app.core.database import engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.services.rag.embeddings import embeddings_service


class DocumentLoader:
    """Загрузчик документов в векторную БД"""

    def __init__(self) -> None:
        self.docs_path = Path("documents/knowledge_base")
        self.async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    async def load_all_documents(self) -> dict:
        """Загружает все документы из папки"""
        logger.info("Начало загрузки документов базы знаний.")

        stats = {"total": 0, "loaded": 0, "failed": 0}

        if not self.docs_path.exists():
            logger.error(f"Папка {self.docs_path} не найдена")
            return stats

        # Находим все .md файлы
        md_files = list(self.docs_path.glob("*.md"))
        stats["total"] = len(md_files)

        logger.info(f"Найдено {len(md_files)} документов для загрузки.")

        for file_path in md_files:
            try:
                await self.load_document(file_path)
                stats["loaded"] += 1
                logger.info(f"✅ Загружен: {file_path.name}")
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"❌ Ошибка загрузки {file_path.name}: {e}")

        logger.info(
            f"Загрузка завершена: {stats['loaded']} успешно, "
            f"{stats['failed']} с ошибками."
        )

        return stats

    async def load_document(self, file_path: Path) -> None:
        """Загружает один документ"""
        # Читаем содержимое
        content = file_path.read_text(encoding="utf-8")
        title = file_path.stem.replace("_", " ").title()

        # Генерируем embedding
        embedding = await embeddings_service.generate_embedding(content)

        # Преобразуем в PostgreSQL array format: [1.0, 2.0, 3.0]
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Сохраняем в БД
        async with self.async_session() as session:
            query = text(
                """
                INSERT INTO documents (title, content, embedding, metadata)
                VALUES (:title, :content, CAST(:embedding AS vector), :metadata)
                ON CONFLICT (title) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
            """
            )

            await session.execute(
                query,
                {
                    "title": title,
                    "content": content,
                    "embedding": embedding_str,
                    "metadata": json.dumps({"source": str(file_path)}),
                },
            )

            await session.commit()

    async def clear_documents(self) -> None:
        """Очищает таблицу documents"""
        async with self.async_session() as session:
            await session.execute(text("TRUNCATE TABLE documents"))
            await session.commit()
            logger.info("Таблица documents очищена")


# Singleton
document_loader = DocumentLoader()
