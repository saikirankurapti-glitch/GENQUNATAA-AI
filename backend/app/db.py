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
        AuthSessionRecord, Document, DocumentChunk, InterviewQuestion, MessageRecord,
        ResumeProfile, SessionNote, SessionRecord, UserRecord,
    )  # noqa: F401

    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_vector vector(768)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_hnsw ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)"))
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id) ON DELETE CASCADE"))
            await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id) ON DELETE CASCADE"))
            await conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS user_agent varchar(1000) NOT NULL DEFAULT ''"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions(user_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions(user_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires_at ON auth_sessions(expires_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_sessions_revoked_at ON auth_sessions(revoked_at)"))
