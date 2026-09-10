from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .auth import current_user
from .db import get_db
from .db_models import Document, ResumeProfile, UserRecord

router = APIRouter(prefix="/api/v1/preparation", tags=["preparation"])

class PreparationPlanner:
    def __init__(self) -> None:
        self.ai = GeminiService()

    async def build(self, db: AsyncSession, user: UserRecord, target_role: str, job_description: str, available_minutes: int) -> dict[str, Any]:
        profile = await db.scalar(select(ResumeProfile).join(Document, ResumeProfile.document_id == Document.id).where(Document.user_id == user.id).order_by(ResumeProfile.id.desc()))
        skills = profile.skills if profile else "unknown"
        prompt = f'''You are GenQuantaa's personalized interview preparation planner.
Target role: {target_role}
Candidate skills: {skills}
Job description: {job_description}
Available preparation time: {available_minutes} minutes
Create an executable preparation plan. Prioritize high-impact gaps and realistic interview practice. Never invent candidate experience. Return ONLY JSON with keys: readiness_score (0-1), total_minutes (integer), sessions (array objects with day, topic, objective, activities array, minutes integer, priority high|medium|low), drills (array strings), mock_interview_plan (array strings), final_checklist (array strings), top_risks (array strings).'''
        fallback = {"readiness_score": 0.5, "total_minutes": available_minutes, "sessions": [{"day": 1, "topic": "Core role fundamentals", "objective": "Close the highest-impact knowledge gaps", "activities": ["Review fundamentals", "Practice concise explanations"], "minutes": min(60, available_minutes), "priority": "high"}], "drills": ["Explain one production scenario in 2 minutes", "Solve one role-specific troubleshooting problem"], "mock_interview_plan": ["Run an adaptive technical interview", "Review weak answers and retry"], "final_checklist": ["Resume claims are defensible", "Prepare project metrics", "Review common trade-offs"], "top_risks": ["Job-specific gaps need validation"]}
        result = fallback
        if self.ai.api_key:
            from google import genai
            from google.genai import types
            try:
                response = await genai.Client(api_key=self.ai.api_key).aio.models.generate_content(model=self.ai.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
                parsed = json.loads(response.text or "{}")
                if isinstance(parsed, dict): result = {**fallback, **parsed}
            except Exception:
                result = fallback
        result["target_role"] = target_role
        result["candidate_skills"] = skills
        result["available_minutes"] = available_minutes
        return result

planner = PreparationPlanner()

@router.post("/plan")
async def plan(payload: dict[str, Any], db: AsyncSession = Depends(get_db), user: UserRecord = Depends(current_user)) -> dict[str, Any]:
    role = str(payload.get("target_role", "Data Engineer")).strip() or "Data Engineer"
    jd = str(payload.get("job_description", "")).strip()
    try:
        minutes = int(payload.get("available_minutes", 180))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="available_minutes must be an integer") from None
    if not jd: raise HTTPException(status_code=400, detail="job_description is required")
    if len(jd) > 30000: raise HTTPException(status_code=400, detail="job_description is too long")
    if minutes < 30 or minutes > 10080: raise HTTPException(status_code=400, detail="available_minutes must be between 30 and 10080")
    return await planner.build(db, user, role, jd, minutes)
