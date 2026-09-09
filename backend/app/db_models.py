from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .db import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - dependency is installed in production/CI
    Vector = None


settings = get_settings()
# Keep SQLite test/dev databases compatible while using a real pgvector column on PostgreSQL.
EmbeddingVectorType = Vector(settings.gemini_embedding_dimensions) if Vector and settings.database_url.startswith("postgresql") else JSON


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), default="Untitled session")
    mode: Mapped[str] = mapped_column(String(50), default="copilot")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    messages: Mapped[list[MessageRecord]] = relationship("MessageRecord", cascade="all, delete-orphan")
    questions: Mapped[list[InterviewQuestion]] = relationship("InterviewQuestion", cascade="all, delete-orphan")
    notes: Mapped[list[SessionNote]] = relationship("SessionNote", cascade="all, delete-orphan")


class MessageRecord(Base):
    __tablename__ = "messages"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list[DocumentChunk]] = relationship("DocumentChunk", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    # Legacy JSON embedding retained for backwards compatibility during migration.
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Native pgvector representation used by PostgreSQL semantic search.
    embedding_vector: Mapped[list[float] | None] = mapped_column(EmbeddingVectorType, nullable=True)


class ResumeProfile(Base):
    __tablename__ = "resume_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    skills: Mapped[str] = mapped_column(Text, default="")
    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    transcript: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(50), default="general")
    answer: Mapped[str] = mapped_column(Text)
    key_points: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    follow_up: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionNote(Base):
    __tablename__ = "session_notes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    note_type: Mapped[str] = mapped_column(String(50), default="insight")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
