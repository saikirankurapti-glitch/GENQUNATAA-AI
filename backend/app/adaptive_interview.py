from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .auth import current_user
from .db import get_db
from .db_models import Document, InterviewQuestion, ResumeProfile, SessionRecord, UserRecord

router = APIRouter(prefix="/api/v1/adaptive", tags=["adaptive-interview"])

class AdaptiveInterviewer:
    DIFFICULTIES = ("easy", "medium", "hard", "expert")
    QUESTION_TYPES = ("technical", "behavioral", "system_design", "coding", "project", "general")

    def __init__(self) -> None:
        self.ai = GeminiService()

    async def next_question(self, db: AsyncSession, session: SessionRecord, user: UserRecord, target_role: str = "Data Engineer", focus: str = "adaptive") -> dict[str, Any]:
        questions = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.session_id == session.id).order_by(InterviewQuestion.created_at))).scalars().all()
        profile = (await db.execute(select(ResumeProfile).join(Document, ResumeProfile.document_id == Document.id).where(Document.user_id == user.id).order_by(ResumeProfile.id.desc()).limit(1))).scalar_one_or_none()
        history = [{"question": q.transcript, "type": q.question_type, "difficulty": q.difficulty, "candidate_score": q.candidate_score, "missing": q.missing_concepts} for q in questions[-10:]]
        prompt = f"""You are GenQuantaa's adaptive interviewer engine. Select the NEXT interview question based on demonstrated candidate performance, not a fixed sequence.
Target role: {target_role}
Focus preference: {focus}
Candidate profile skills: {profile.skills if profile else 'unknown'}
Previous questions and evaluation results: {json.dumps(history)}

Rules:
- If the last answer was weak (especially below 0.60), ask a targeted remediation/probing question or reduce difficulty one level.
- If strong (especially above 0.80), increase difficulty or probe a deeper trade-off.
- Avoid repeating the same question or concept unless deliberately testing remediation.
- Progress naturally across fundamentals, implementation, troubleshooting, architecture and behavioral/project areas.
- Use resume evidence when available, but never invent candidate experience.
- Return ONLY JSON.
Keys: question, question_type (technical|behavioral|system_design|coding|project|general), difficulty (easy|medium|hard|expert), focus_area, rationale, expected_concepts (array), follow_up_strategy.
"""
        fallback = {"question": "Walk me through a production data pipeline you have worked on and one reliability improvement you would make.", "question_type": "project", "difficulty": "medium", "focus_area": "project depth", "rationale": "Establish a practical baseline before adapting difficulty.", "expected_concepts": ["architecture", "reliability", "trade-offs"], "follow_up_strategy": "Probe one implementation decision and its failure mode."}
        result = fallback
        if self.ai.api_key:
            from google import genai
            from google.genai import types
            response = await genai.Client(api_key=self.ai.api_key).aio.models.generate_content(model=self.ai.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type":"OBJECT","properties":{"question":{"type":"STRING"},"question_type":{"type":"STRING"},"difficulty":{"type":"STRING"},"focus_area":{"type":"STRING"},"rationale":{"type":"STRING"},"expected_concepts":{"type":"ARRAY","items":{"type":"STRING"}},"follow_up_strategy":{"type":"STRING"}},"required":["question","question_type","difficulty","focus_area","rationale","expected_concepts","follow_up_strategy"]}))
            try: result = json.loads(response.text or "{}")
            except json.JSONDecodeError: pass
        if result.get("difficulty") not in self.DIFFICULTIES: result["difficulty"] = "medium"
        if result.get("question_type") not in self.QUESTION_TYPES: result["question_type"] = "general"
        return {"session_id": str(session.id), "sequence": len(questions) + 1, "adaptive": bool(questions), **result}

engine = AdaptiveInterviewer()

@router.post("/sessions/{session_id}/next")
async def next_question(session_id: UUID, payload: dict[str, Any] | None = None, db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict[str, Any]:
    session = await db.scalar(select(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == user.id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    payload = payload or {}
    return await engine.next_question(db, session, user, str(payload.get("target_role", "Data Engineer")), str(payload.get("focus", "adaptive")))
