from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db import get_db
from .db_models import InterviewQuestion, SessionRecord
from .rag import retriever

router = APIRouter(prefix="/api/v1/coding", tags=["coding"])
ai = GeminiService()


@router.post("/analyze")
async def analyze_code(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    session_id = payload.get("session_id")
    code = str(payload.get("code", "")).strip()
    question = str(payload.get("question", "")).strip()
    language = str(payload.get("language", "auto")).strip() or "auto"
    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    if len(code) > 30000:
        raise HTTPException(status_code=400, detail="code exceeds 30000 characters")

    if session_id:
        try:
            sid = UUID(str(session_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid session_id") from exc
        if not await db.get(SessionRecord, sid):
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = SessionRecord(title="Coding interview", mode="coding")
        db.add(session)
        await db.flush()
        sid = session.id

    query = question or code[:2000]
    retrieved = await retriever.retrieve(db, query, limit=4)
    context = "\n\n".join(f"Source: {item['filename']}\n{item['content']}" for item in retrieved)
    prompt = f"""Analyze this coding interview problem and code as a senior software engineer.
Return ONLY valid JSON with keys: language, problem, approach, solution, optimized_solution, complexity, edge_cases, explanation, interview_tips.
Use concise but complete content. Preserve the candidate's language when possible. Do not invent requirements.

Language: {language}
Problem/question: {question or '(not provided)'}
Code:
```text
{code}
```
Relevant candidate/knowledge context:
{context or '(none)'}
"""
    try:
        raw = await ai.generate(prompt)
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    parsed: dict
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        parsed = {
            "language": language,
            "problem": question,
            "approach": raw,
            "solution": "",
            "optimized_solution": "",
            "complexity": "",
            "edge_cases": [],
            "explanation": raw,
            "interview_tips": [],
        }

    record = InterviewQuestion(
        session_id=sid,
        transcript=question or code,
        question_type="coding",
        answer=parsed.get("solution") or parsed.get("explanation") or raw,
        key_points=json.dumps(parsed.get("interview_tips", [])),
        confidence=1.0 if parsed.get("solution") else 0.5,
        follow_up=parsed.get("optimized_solution", ""),
        sources=json.dumps([item["filename"] for item in retrieved]),
    )
    db.add(record)
    await db.commit()
    return {"session_id": str(sid), "question_id": str(record.id), **parsed, "sources": retrieved}


@router.get("/sessions/{session_id}")
async def coding_history(session_id: UUID, db: AsyncSession = Depends(get_db)) -> list[dict]:
    if not await db.get(SessionRecord, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = await db.execute(
        select(InterviewQuestion)
        .where(InterviewQuestion.session_id == session_id, InterviewQuestion.question_type == "coding")
        .order_by(InterviewQuestion.created_at.desc())
    )
    return [
        {
            "id": str(item.id),
            "transcript": item.transcript,
            "answer": item.answer,
            "key_points": json.loads(item.key_points or "[]"),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in result.scalars().all()
    ]
