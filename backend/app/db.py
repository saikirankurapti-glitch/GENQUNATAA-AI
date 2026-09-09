from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from .db_models import (
        Document,
        DocumentChunk,
        InterviewQuestion,
        MessageRecord,
        ResumeProfile,
        SessionNote,
        SessionRecord,
    )  # noqa: F401

    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            # Safe for existing deployments created before native pgvector support.
            await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_vector vector(768)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_hnsw ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)"))
