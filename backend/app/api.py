from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db import get_db
from .db_models import InterviewQuestion, MessageRecord, SessionNote, SessionRecord
from .intelligence import interview_intelligence
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
    retrieved_context = "\n\n".join(f"Source: {item['filename']}\n{item['content']}" for item in retrieved)
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


@router.post("/sessions/{session_id}/questions/analyze")
async def analyze_question(session_id: UUID, payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    if not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    transcript = str(payload.get("transcript", "")).strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript is required")
    try:
        return await interview_intelligence.analyze_question(db, session_id, transcript)
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Interview analysis failed: {exc}") from exc


@router.get("/sessions/{session_id}/questions")
async def list_questions(session_id: UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    if not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = await db.execute(select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.created_at.desc()))
    return [interview_intelligence.serialize_question(item) for item in result.scalars().all()]


@router.post("/sessions/{session_id}/notes")
async def add_note(session_id: UUID, payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    if not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    content = str(payload.get("content", "")).strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    note_type = str(payload.get("note_type", "insight"))
    await interview_intelligence.add_note(db, session_id, content, note_type)
    return {"status": "saved", "session_id": str(session_id)}


@router.get("/sessions/{session_id}/notes")
async def list_notes(session_id: UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    if not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = await db.execute(select(SessionNote).where(SessionNote.session_id == session_id).order_by(SessionNote.created_at.desc()))
    return [{"id": str(item.id), "note_type": item.note_type, "content": item.content, "created_at": item.created_at.isoformat() if item.created_at else None} for item in result.scalars().all()]


@router.get("/sessions/{session_id}/summary")
async def session_summary(session_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await interview_intelligence.summarize(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Session summary failed: {exc}") from exc
