from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .auth import current_user
from .db import get_db
from .db_models import Document, ResumeProfile, UserRecord

router = APIRouter(prefix="/api/v1/profile", tags=["profile-intelligence"])
ai = GeminiService()


class ProfileAnalysis(BaseModel):
    resume_id: UUID
    filename: str
    name: str | None
    email: str | None
    experience_years: float | None
    skills: list[str]
    headline: str
    summary: str
    core_strengths: list[str]
    projects: list[str]
    likely_roles: list[str]
    interview_topics: list[str]
    evidence: list[str]


def _base_profile(profile: ResumeProfile, document: Document) -> dict[str, Any]:
    return {
        "resume_id": document.id,
        "filename": document.filename,
        "name": profile.name,
        "email": profile.email,
        "experience_years": profile.experience_years,
        "skills": [s.strip() for s in profile.skills.split(",") if s.strip()],
    }


async def build_profile_context(db: AsyncSession, user_id: UUID) -> dict[str, Any] | None:
    result = await db.execute(
        select(ResumeProfile, Document)
        .join(Document, Document.id == ResumeProfile.document_id)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    profile, document = row
    base = _base_profile(profile, document)
    return {
        **base,
        "resume_text": document.content[:24000],
        "profile_source": document.filename,
    }


@router.get("/analysis", response_model=ProfileAnalysis | None)
async def analyze_profile(
    db: AsyncSession = Depends(get_db),
    user: UserRecord = Depends(current_user),
) -> ProfileAnalysis | None:
    context = await build_profile_context(db, user.id)
    if not context:
        return None

    fallback = {
        **{k: context[k] for k in ("resume_id", "filename", "name", "email", "experience_years", "skills")},
        "headline": f"{context['name'] or 'Candidate'} with {context['experience_years'] or 'relevant'} years of experience",
        "summary": "",
        "core_strengths": context["skills"][:8],
        "projects": [],
        "likely_roles": [],
        "interview_topics": context["skills"][:10],
        "evidence": [],
    }
    if not ai.api_key:
        return ProfileAnalysis(**fallback)

    prompt = f"""You are GenQuantaa's resume intelligence engine. Build a factual candidate profile from the supplied resume.
Never invent employers, projects, technologies, metrics, certifications, education, or experience. Use only evidence in the resume.
Return ONLY valid JSON with keys: headline, summary, core_strengths, projects, likely_roles, interview_topics, evidence.
headline: concise professional positioning statement.
summary: 2-4 sentence candidate summary.
core_strengths: 4-8 specific strengths supported by the resume.
projects: up to 8 concise project/initiative descriptions grounded in the resume.
likely_roles: up to 6 roles that fit the demonstrated experience.
interview_topics: up to 12 topics an interviewer is likely to ask about.
evidence: up to 8 short resume-grounded facts useful for answering interview questions.

Parsed name: {context['name']}
Parsed skills: {', '.join(context['skills'])}
Parsed experience years: {context['experience_years']}
Resume:
{context['resume_text']}
"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=ai.api_key)
        response = await client.aio.models.generate_content(
            model=ai.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "headline": {"type": "STRING"},
                        "summary": {"type": "STRING"},
                        "core_strengths": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "projects": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "likely_roles": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "interview_topics": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "evidence": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["headline", "summary", "core_strengths", "projects", "likely_roles", "interview_topics", "evidence"],
                },
            ),
        )
        result = json.loads(response.text or "{}")
    except Exception:
        result = {}

    for key in ("core_strengths", "projects", "likely_roles", "interview_topics", "evidence"):
        if not isinstance(result.get(key), list):
            result[key] = fallback[key]
    for key in ("headline", "summary"):
        if not isinstance(result.get(key), str):
            result[key] = fallback[key]
    return ProfileAnalysis(**{**fallback, **result})


@router.get("/context")
async def profile_context(
    db: AsyncSession = Depends(get_db),
    user: UserRecord = Depends(current_user),
) -> dict[str, Any]:
    context = await build_profile_context(db, user.id)
    if not context:
        raise HTTPException(status_code=404, detail="No resume profile found")
    context.pop("resume_text", None)
    return context
