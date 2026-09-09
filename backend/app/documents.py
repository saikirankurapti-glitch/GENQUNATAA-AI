from __future__ import annotations

import io
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user
from .db import get_db
from .db_models import Document, DocumentChunk, UserRecord
from .embeddings import EmbeddingService, serialize_embedding
from .rag import retriever

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
_ALLOWED = {"application/pdf", "text/plain", "text/markdown"}
_MAX_BYTES = 10 * 1024 * 1024
_CHUNK_SIZE = 1200
_embeddings = EmbeddingService()


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    characters: int
    chunks: int


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


def extract_text(data: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def chunk_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [normalized[i:i + _CHUNK_SIZE] for i in range(0, len(normalized), _CHUNK_SIZE) if normalized[i:i + _CHUNK_SIZE]]


@router.post("/upload", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> DocumentOut:
    if file.content_type not in _ALLOWED:
        raise HTTPException(status_code=415, detail="Supported types: PDF, TXT, Markdown")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit")
    text = extract_text(data, file.content_type or "text/plain")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in document")

    chunks = chunk_text(text)
    document = Document(user_id=user.id, filename=file.filename or "document", content_type=file.content_type, content=text)
    db.add(document)
    await db.flush()
    for index, chunk in enumerate(chunks):
        vector = None
        if _embeddings.api_key:
            try:
                vector = await _embeddings.embed(chunk)
            except Exception:
                vector = None
        db.add(DocumentChunk(document_id=document.id, chunk_index=index, content=chunk, embedding=serialize_embedding(vector) if vector else None, embedding_vector=vector or None))
    await db.commit()
    await db.refresh(document)
    return DocumentOut(id=document.id, filename=document.filename, content_type=document.content_type, characters=len(text), chunks=len(chunks))


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> list[DocumentOut]:
    statement = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.user_id == user.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(statement)
    return [
        DocumentOut(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            characters=len(document.content),
            chunks=chunk_count,
        )
        for document, chunk_count in result.all()
    ]


@router.post("/search")
async def search_documents(payload: SearchRequest, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    limit = max(1, min(payload.limit, 20))
    results = await retriever.retrieve(db, payload.query, limit=limit, user_id=user.id)
    return {"query": payload.query, "results": results}
