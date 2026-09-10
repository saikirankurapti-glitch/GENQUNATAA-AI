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
        AuditLogRecord, AuthSessionRecord, Document, DocumentChunk, InterviewQuestion,
        MessageRecord, ResumeProfile, SessionNote, SessionRecord, UserRecord,
    )  # noqa: F401

    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role varchar(30) NOT NULL DEFAULT 'team_member'"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users(role)"))
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
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs(actor_user_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS difficulty varchar(30) NOT NULL DEFAULT 'medium'"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS answer_quality double precision NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS missing_concepts text NOT NULL DEFAULT '[]'"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS ideal_answer text NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS coaching_feedback text NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS predicted_follow_ups text NOT NULL DEFAULT '[]'"))
            for statement in (
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS candidate_answer text NOT NULL DEFAULT ''",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS candidate_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS correctness_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS relevance_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS completeness_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS structure_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS technical_depth_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS communication_score double precision NOT NULL DEFAULT 0",
                "ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS evaluation_feedback text NOT NULL DEFAULT ''",
            ):
                await conn.execute(text(statement))
        elif conn.dialect.name == "sqlite":
            columns = {str(row[1]) for row in (await conn.execute(text("PRAGMA table_info(interview_questions)"))).fetchall()}
            additions = {
                "candidate_answer": "TEXT NOT NULL DEFAULT ''",
                "candidate_score": "REAL NOT NULL DEFAULT 0",
                "correctness_score": "REAL NOT NULL DEFAULT 0",
                "relevance_score": "REAL NOT NULL DEFAULT 0",
                "completeness_score": "REAL NOT NULL DEFAULT 0",
                "structure_score": "REAL NOT NULL DEFAULT 0",
                "technical_depth_score": "REAL NOT NULL DEFAULT 0",
                "communication_score": "REAL NOT NULL DEFAULT 0",
                "evaluation_feedback": "TEXT NOT NULL DEFAULT ''",
            }
            for name, definition in additions.items():
                if name not in columns:
                    await conn.execute(text(f"ALTER TABLE interview_questions ADD COLUMN {name} {definition}"))
