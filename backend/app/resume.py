from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user
from .db import get_db
from .db_models import Document, DocumentChunk, ResumeProfile, UserRecord
from .documents import _MAX_BYTES, _ALLOWED, chunk_text, extract_text
from .embeddings import EmbeddingService, serialize_embedding

router = APIRouter(prefix="/api/v1/resume", tags=["resume"])
embedding_service = EmbeddingService()


class ResumeOut(BaseModel):
    id: UUID
    filename: str
    name: str | None
    email: str | None
    skills: list[str]
    experience_years: float | None


KNOWN_SKILLS = {"python", "sql", "azure", "azure data factory", "azure databricks", "databricks", "adls", "azure data lake", "spark", "pyspark", "aws", "gcp", "snowflake", "dbt", "airflow", "kafka", "java", "scala", "terraform", "docker", "kubernetes", "git", "power bi", "machine learning", "tensorflow", "pandas", "numpy"}


def parse_resume(text: str) -> tuple[str | None, str | None, list[str], float | None]:
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = next((line for line in lines[:8] if 2 <= len(line.split()) <= 4 and not re.search(r"[@:]|resume|curriculum vitae", line, re.I)), None)
    lower = text.lower()
    skills = sorted(skill for skill in KNOWN_SKILLS if skill in lower)
    years = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", lower)]
    return name, email_match.group(0) if email_match else None, skills, max(years) if years else None


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> ResumeOut:
    if file.content_type not in _ALLOWED:
        raise HTTPException(status_code=415, detail="Supported resume types: PDF, TXT, Markdown")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Resume exceeds the 10 MB limit")
    text = extract_text(data, file.content_type or "text/plain")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in resume")
    name, email, skills, years = parse_resume(text)
    document = Document(user_id=user.id, filename=file.filename or "resume", content_type=file.content_type, content=text)
    db.add(document)
    await db.flush()
    db.add(ResumeProfile(document_id=document.id, name=name, email=email, skills=", ".join(skills), experience_years=years))
    for index, chunk in enumerate(chunk_text(text)):
        vector = []
        if embedding_service.api_key:
            try: vector = await embedding_service.embed(chunk)
            except Exception: vector = []
        db.add(DocumentChunk(document_id=document.id, chunk_index=index, content=chunk, embedding=serialize_embedding(vector) if vector else None, embedding_vector=vector or None))
    await db.commit()
    return ResumeOut(id=document.id, filename=document.filename, name=name, email=email, skills=skills, experience_years=years)


@router.get("/latest", response_model=ResumeOut | None)
async def latest_resume(db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> ResumeOut | None:
    result = await db.execute(select(ResumeProfile, Document).join(Document, Document.id == ResumeProfile.document_id).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(1))
    row = result.first()
    if not row: return None
    profile, document = row
    return ResumeOut(id=document.id, filename=document.filename, name=profile.name, email=profile.email, skills=[s.strip() for s in profile.skills.split(",") if s.strip()], experience_years=profile.experience_years)
