from uuid import UUID

from fastapi import APIRouter, HTTPException

from .ai import GeminiService
from .models import ChatRequest, ChatResponse, Session, SessionCreate

router = APIRouter(prefix="/api/v1")
_sessions: dict[UUID, Session] = {}
ai = GeminiService()


@router.post("/sessions", response_model=Session)
async def create_session(payload: SessionCreate) -> Session:
    session = Session(title=payload.title, mode=payload.mode)
    _sessions[session.id] = session
    return session


@router.get("/sessions", response_model=list[Session])
async def list_sessions() -> list[Session]:
    return list(_sessions.values())


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: UUID) -> Session:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    session_id = payload.session_id
    if session_id is None:
        session = Session()
        _sessions[session.id] = session
        session_id = session.id
    elif session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        answer = await ai.generate(payload.message, payload.context)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(session_id=session_id, answer=answer, model=ai.model)
