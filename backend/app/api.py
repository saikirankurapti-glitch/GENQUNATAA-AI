from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db import get_db
from .db_models import MessageRecord, SessionRecord
from .models import ChatRequest, ChatResponse, Session, SessionCreate
from .rag import retriever

router = APIRouter(prefix="/api/v1")
ai = GeminiService()


def to_session(record: SessionRecord) -> Session:
    return Session(id=record.id, title=record.title, mode=record.mode, created_at=record.created_at)


@router.post("/sessions", response_model=Session)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)) -> Session:
    record = SessionRecord(title=payload.title, mode=payload.mode)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return to_session(record)


@router.get("/sessions", response_model=list[Session])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[Session]:
    result = await db.execute(select(SessionRecord).order_by(SessionRecord.created_at.desc()).limit(50))
    return [to_session(item) for item in result.scalars().all()]


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> Session:
    record = await db.get(SessionRecord, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return to_session(record)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    session_id = payload.session_id
    if session_id is None:
        session = SessionRecord()
        db.add(session)
        await db.flush()
        session_id = session.id
    elif not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    retrieved = await retriever.retrieve(db, payload.message, limit=5)
    retrieved_context = "\n\n".join(
        f"Source: {item['filename']}\n{item['content']}" for item in retrieved
    )
    context_parts = [part for part in [payload.context, retrieved_context] if part]
    context = "\n\n".join(context_parts) or None

    try:
        answer = await ai.generate(payload.message, context)
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.add(MessageRecord(session_id=session_id, role="user", content=payload.message))
    db.add(MessageRecord(session_id=session_id, role="assistant", content=answer))
    await db.commit()
    return ChatResponse(session_id=session_id, answer=answer, model=ai.model)
