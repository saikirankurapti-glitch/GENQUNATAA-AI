from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .auth import current_user
from .db import get_db
from .db_models import InterviewQuestion, MessageRecord, SessionNote, SessionRecord, UserRecord
from .intelligence import interview_intelligence
from .models import ChatRequest, ChatResponse, Session, SessionCreate
from .rag import retriever

router = APIRouter(prefix="/api/v1")
ai = GeminiService()


def to_session(record: SessionRecord) -> Session:
    return Session(id=record.id, title=record.title, mode=record.mode, created_at=record.created_at)


async def owned_session(db: AsyncSession, session_id: UUID, user: UserRecord) -> SessionRecord:
    record = await db.scalar(select(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == user.id))
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.post("/sessions", response_model=Session)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> Session:
    record = SessionRecord(user_id=user.id, title=payload.title, mode=payload.mode)
    db.add(record)
    await db.commit(); await db.refresh(record)
    return to_session(record)


@router.get("/sessions", response_model=list[Session])
async def list_sessions(db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> list[Session]:
    result = await db.execute(select(SessionRecord).where(SessionRecord.user_id == user.id).order_by(SessionRecord.created_at.desc()).limit(50))
    return [to_session(item) for item in result.scalars().all()]


@router.get("/sessions/analytics")
async def session_analytics(db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    sessions = (await db.execute(select(SessionRecord).where(SessionRecord.user_id == user.id).order_by(SessionRecord.created_at.desc()).limit(100))).scalars().all()
    rows = []
    for session in sessions:
        questions = await db.scalar(select(func.count(InterviewQuestion.id)).where(InterviewQuestion.session_id == session.id))
        notes = await db.scalar(select(func.count(SessionNote.id)).where(SessionNote.session_id == session.id))
        confidence = await db.scalar(select(func.avg(InterviewQuestion.confidence)).where(InterviewQuestion.session_id == session.id))
        rows.append({"id": str(session.id), "title": session.title, "mode": session.mode, "created_at": session.created_at.isoformat() if session.created_at else None, "question_count": int(questions or 0), "note_count": int(notes or 0), "average_confidence": round(float(confidence or 0), 3)})
    active = [r["average_confidence"] for r in rows if r["question_count"]]
    modes: dict[str, int] = {}
    for row in rows: modes[row["mode"]] = modes.get(row["mode"], 0) + 1
    return {"total_sessions": len(rows), "total_questions": sum(r["question_count"] for r in rows), "total_notes": sum(r["note_count"] for r in rows), "average_confidence": round(sum(active) / len(active), 3) if active else 0, "mode_counts": modes, "sessions": rows}


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> Session:
    return to_session(await owned_session(db, session_id, user))


@router.get("/sessions/{session_id}/analytics")
async def session_detail_analytics(session_id: UUID, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    record = await owned_session(db, session_id, user)
    questions = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.session_id == record.id).order_by(InterviewQuestion.created_at.desc()))).scalars().all()
    notes = (await db.execute(select(SessionNote).where(SessionNote.session_id == record.id).order_by(SessionNote.created_at.desc()))).scalars().all()
    values = [float(q.confidence or 0) for q in questions]
    return {"session": to_session(record).model_dump(mode="json"), "question_count": len(questions), "note_count": len(notes), "average_confidence": round(sum(values) / len(values), 3) if values else 0, "high_confidence_questions": sum(1 for value in values if value >= 0.7), "questions": [interview_intelligence.serialize_question(q) for q in questions], "notes": [{"id": str(n.id), "type": n.note_type, "content": n.content, "created_at": n.created_at.isoformat() if n.created_at else None} for n in notes]}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> ChatResponse:
    session_id = payload.session_id
    if session_id is None:
        session = SessionRecord(user_id=user.id); db.add(session); await db.flush(); session_id = session.id
    else:
        await owned_session(db, session_id, user)
    retrieved = await retriever.retrieve(db, payload.message, limit=5, user_id=user.id)
    retrieved_context = "\n\n".join(f"Source: {item['filename']}\n{item['content']}" for item in retrieved)
    context_parts = [part for part in [payload.context, retrieved_context] if part]
    try: answer = await ai.generate(payload.message, "\n\n".join(context_parts) or None)
    except RuntimeError as exc:
        await db.rollback(); raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.add(MessageRecord(session_id=session_id, role="user", content=payload.message)); db.add(MessageRecord(session_id=session_id, role="assistant", content=answer)); await db.commit()
    return ChatResponse(session_id=session_id, answer=answer, model=ai.model)


@router.post("/visual/analyze")
async def analyze_visual(file: UploadFile, user: UserRecord = Depends(current_user)) -> dict:
    allowed = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed: raise HTTPException(status_code=415, detail="Only PNG, JPEG, and WebP screenshots are supported")
    image = await file.read()
    if not image: raise HTTPException(status_code=400, detail="Screenshot is empty")
    if len(image) > 5 * 1024 * 1024: raise HTTPException(status_code=413, detail="Screenshot exceeds the 5 MB limit")
    try: analysis = await ai.analyze_visual(image, file.content_type)
    except RuntimeError as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"filename": file.filename, "mime_type": file.content_type, "analysis": analysis, "image_persisted": False}


@router.post("/sessions/{session_id}/questions/analyze")
async def analyze_question(session_id: UUID, payload: dict, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    await owned_session(db, session_id, user)
    transcript = str(payload.get("transcript", "")).strip()
    if not transcript: raise HTTPException(status_code=400, detail="transcript is required")
    try: return await interview_intelligence.analyze_question(db, session_id, transcript, user_id=user.id)
    except Exception as exc: await db.rollback(); raise HTTPException(status_code=502, detail=f"Interview analysis failed: {exc}") from exc


@router.get("/sessions/{session_id}/questions")
async def list_questions(session_id: UUID, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> list[dict]:
    await owned_session(db, session_id, user)
    result = await db.execute(select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.created_at.desc()))
    return [interview_intelligence.serialize_question(item) for item in result.scalars().all()]


@router.post("/sessions/{session_id}/notes")
async def add_note(session_id: UUID, payload: dict, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    await owned_session(db, session_id, user)
    content = str(payload.get("content", "")).strip()
    if not content: raise HTTPException(status_code=400, detail="content is required")
    await interview_intelligence.add_note(db, session_id, content, str(payload.get("note_type", "insight")))
    return {"status": "saved", "session_id": str(session_id)}


@router.get("/sessions/{session_id}/notes")
async def list_notes(session_id: UUID, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> list[dict]:
    await owned_session(db, session_id, user)
    result = await db.execute(select(SessionNote).where(SessionNote.session_id == session_id).order_by(SessionNote.created_at.desc()))
    return [{"id": str(item.id), "note_type": item.note_type, "content": item.content, "created_at": item.created_at.isoformat() if item.created_at else None} for item in result.scalars().all()]


@router.get("/sessions/{session_id}/summary")
async def session_summary(session_id: UUID, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict:
    await owned_session(db, session_id, user)
    try: return await interview_intelligence.summarize(db, session_id)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=502, detail=f"Session summary failed: {exc}") from exc
