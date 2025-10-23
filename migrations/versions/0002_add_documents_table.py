"""Добавляет таблицу documents для RAG системы с уникальным индексом."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Идентификаторы миграции
revision = "0002_add_documents_table"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создает таблицу documents и включает расширение pgvector."""
    # Включаем расширение pgvector для векторных операций
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Создаем таблицу documents (если её еще нет)
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(500) NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Добавляем уникальное ограничение на title (если еще нет)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'documents_title_unique'
            ) THEN
                ALTER TABLE documents 
                ADD CONSTRAINT documents_title_unique UNIQUE (title);
            END IF;
        END $$;
    """)
    
    # Создаем индекс для векторного поиска
    op.execute("""
        CREATE INDEX IF NOT EXISTS documents_embedding_idx 
        ON documents 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    
    # Создаем индекс для поиска по title
    op.execute("""
        CREATE INDEX IF NOT EXISTS documents_title_idx 
        ON documents (title);
    """)


def downgrade() -> None:
    """Удаляет таблицу documents."""
    op.execute("DROP TABLE IF EXISTS documents;")

