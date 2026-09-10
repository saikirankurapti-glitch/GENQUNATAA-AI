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
from .db_models import Document, ResumeProfile, SessionRecord, UserRecord

router = APIRouter(prefix="/api/v1/role-intelligence", tags=["role-intelligence"])

class RoleIntelligenceEngine:
    def __init__(self) -> None:
        self.ai = GeminiService()

    async def analyze(self, db: AsyncSession, user: UserRecord, target_role: str, job_description: str) -> dict[str, Any]:
        profile = await db.scalar(select(ResumeProfile).join(Document, ResumeProfile.document_id == Document.id).where(Document.user_id == user.id).order_by(ResumeProfile.id.desc()))
        skills = profile.skills if profile else "unknown"
        prompt = f'''You are GenQuantaa Role Intelligence. Build a practical interview strategy from a candidate profile and job description.
Target role: {target_role}
Candidate skills: {skills}
Job description: {job_description}
Return ONLY JSON. Do not invent candidate experience.
Keys:
role_summary:string,
skill_gap_matrix:array of objects with skill, importance (high|medium|low), candidate_level (strong|partial|missing), gap, evidence,
priority_topics:array of strings,
interview_roadmap:array of objects with stage, objective, topics (array), question_weight (0-1), recommended_questions (array),
preparation_plan:array of objects with topic, action, priority (high|medium|low), estimated_minutes (integer),
likely_question_types:array of strings,
readiness_score:0-1,
risks:array of strings,
strengths:array of strings'''
        fallback = {"role_summary": f"Interview strategy for {target_role}", "skill_gap_matrix": [{"skill": "Core role fundamentals", "importance": "high", "candidate_level": "partial", "gap": "Validate depth with practical questions", "evidence": skills}], "priority_topics": ["fundamentals", "implementation", "troubleshooting", "system design"], "interview_roadmap": [{"stage": "Fundamentals", "objective": "Validate core knowledge", "topics": ["fundamentals"], "question_weight": 0.25, "recommended_questions": []}, {"stage": "Implementation", "objective": "Test hands-on depth", "topics": ["implementation", "debugging"], "question_weight": 0.35, "recommended_questions": []}, {"stage": "Architecture", "objective": "Evaluate design trade-offs", "topics": ["system design"], "question_weight": 0.25, "recommended_questions": []}, {"stage": "Behavioral", "objective": "Evaluate ownership and communication", "topics": ["projects", "incidents"], "question_weight": 0.15, "recommended_questions": []}], "preparation_plan": [{"topic": "Role fundamentals", "action": "Practice concise explanations and production examples", "priority": "high", "estimated_minutes": 45}], "likely_question_types": ["technical", "system_design", "project", "behavioral"], "readiness_score": 0.5, "risks": ["Job-description-specific gaps require review"], "strengths": [skills]}
        result = fallback
        if self.ai.api_key:
            from google import genai
            from google.genai import types
            try:
                response = await genai.Client(api_key=self.ai.api_key).aio.models.generate_content(model=self.ai.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
                parsed = json.loads(response.text or "{}")
                if isinstance(parsed, dict): result = {**fallback, **parsed}
            except (json.JSONDecodeError, Exception):
                result = fallback
        result["target_role"] = target_role
        result["candidate_skills"] = skills
        return result

engine = RoleIntelligenceEngine()

@router.post("/analyze")
async def analyze(payload: dict[str, Any], db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict[str, Any]:
    target_role = str(payload.get("target_role", "Data Engineer")).strip() or "Data Engineer"
    job_description = str(payload.get("job_description", "")).strip()
    if not job_description: raise HTTPException(status_code=400, detail="job_description is required")
    if len(job_description) > 30000: raise HTTPException(status_code=400, detail="job_description is too long")
    return await engine.analyze(db, user, target_role, job_description)

@router.post("/sessions/{session_id}/strategy")
async def session_strategy(session_id: UUID, payload: dict[str, Any], db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict[str, Any]:
    session = await db.scalar(select(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == user.id))
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    job_description = str(payload.get("job_description", "")).strip()
    if not job_description: raise HTTPException(status_code=400, detail="job_description is required")
    return await engine.analyze(db, user, str(payload.get("target_role", "Data Engineer")).strip() or "Data Engineer", job_description)
