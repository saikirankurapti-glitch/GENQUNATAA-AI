from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db_models import InterviewQuestion, MessageRecord, SessionNote, SessionRecord
from .rag import retriever


class InterviewIntelligence:
    def __init__(self) -> None:
        self.ai = GeminiService()

    @staticmethod
    def looks_like_question(text: str) -> bool:
        value = text.strip().lower()
        if not value or len(value) < 8:
            return False
        if "?" in value:
            return True
        starters = (
            "what ", "why ", "how ", "when ", "where ", "which ", "who ",
            "can you ", "could you ", "would you ", "tell me ", "explain ",
            "describe ", "compare ", "difference between ", "have you ",
            "do you ", "did you ", "walk me through ",
        )
        return value.startswith(starters)

    async def analyze_question(self, db: AsyncSession, session_id: UUID, transcript: str) -> dict[str, Any]:
        retrieved = await retriever.retrieve(db, transcript, limit=6)
        context = "\n\n".join(
            f"Source: {item['filename']}\n{item['content']}" for item in retrieved
        ) or "No resume or knowledge-base context matched."

        prompt = f"""You are GenQuantaa AI's interview intelligence engine.
Analyze the interviewer's question and produce a concise candidate-ready answer.
Use the supplied resume/knowledge context when relevant. Never invent candidate experience.

Return ONLY valid JSON with these keys:
question_type: one of technical, behavioral, system_design, coding, project, general
answer: a concise spoken answer in first person where appropriate
key_points: array of 3 to 6 short points
confidence: number from 0 to 1
follow_up: one likely follow-up question
sources: array of source filenames used

Question:
{transcript}

Context:
{context}
"""
        result: dict[str, Any]
        if not self.ai.api_key:
            result = {
                "question_type": "general",
                "answer": "AI is not configured. Add GEMINI_API_KEY to generate the interview answer.",
                "key_points": [],
                "confidence": 0.0,
                "follow_up": "",
                "sources": [],
            }
        else:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.ai.api_key)
            response = await client.aio.models.generate_content(
                model=self.ai.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "question_type": {"type": "STRING"},
                            "answer": {"type": "STRING"},
                            "key_points": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "confidence": {"type": "NUMBER"},
                            "follow_up": {"type": "STRING"},
                            "sources": {"type": "ARRAY", "items": {"type": "STRING"}},
                        },
                        "required": ["question_type", "answer", "key_points", "confidence", "follow_up", "sources"],
                    },
                ),
            )
            try:
                result = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                result = {
                    "question_type": "general",
                    "answer": response.text or "I could not generate an answer.",
                    "key_points": [],
                    "confidence": 0.5,
                    "follow_up": "",
                    "sources": [item["filename"] for item in retrieved],
                }

        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        answer = str(result.get("answer", "")).strip()
        record = InterviewQuestion(
            session_id=session_id,
            transcript=transcript,
            question_type=str(result.get("question_type", "general")),
            answer=answer,
            key_points=json.dumps(result.get("key_points", [])),
            confidence=confidence,
            follow_up=str(result.get("follow_up", "")),
            sources=json.dumps(result.get("sources", [item["filename"] for item in retrieved])),
        )
        db.add(record)
        db.add(MessageRecord(session_id=session_id, role="interviewer", content=transcript))
        db.add(MessageRecord(session_id=session_id, role="assistant", content=answer))
        await db.commit()
        await db.refresh(record)
        return self.serialize_question(record)

    async def add_note(self, db: AsyncSession, session_id: UUID, content: str, note_type: str = "insight") -> None:
        if content.strip():
            db.add(SessionNote(session_id=session_id, note_type=note_type, content=content.strip()))
            await db.commit()

    async def summarize(self, db: AsyncSession, session_id: UUID) -> dict[str, Any]:
        session = await db.get(SessionRecord, session_id)
        if not session:
            raise ValueError("Session not found")
        questions = (await db.execute(
            select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.created_at)
        )).scalars().all()
        notes = (await db.execute(
            select(SessionNote).where(SessionNote.session_id == session_id).order_by(SessionNote.created_at)
        )).scalars().all()
        transcript = "\n".join(f"Q: {q.transcript}\nA: {q.answer}" for q in questions)
        note_text = "\n".join(n.content for n in notes)
        prompt = f"Summarize this interview session in JSON with keys summary, strengths, gaps, next_steps, score. Keep it concise.\n{transcript}\nNotes:\n{note_text}"
        summary = {"summary": "No interview questions recorded yet.", "strengths": [], "gaps": [], "next_steps": [], "score": 0}
        if self.ai.api_key and questions:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.ai.api_key)
            response = await client.aio.models.generate_content(
                model=self.ai.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "summary": {"type": "STRING"},
                            "strengths": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "gaps": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "next_steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "score": {"type": "NUMBER"},
                        },
                        "required": ["summary", "strengths", "gaps", "next_steps", "score"],
                    },
                ),
            )
            try:
                summary = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                summary["summary"] = response.text or summary["summary"]
        return {"session_id": str(session_id), "question_count": len(questions), "notes_count": len(notes), **summary}

    @staticmethod
    def serialize_question(record: InterviewQuestion) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "session_id": str(record.session_id),
            "transcript": record.transcript,
            "question_type": record.question_type,
            "answer": record.answer,
            "key_points": json.loads(record.key_points or "[]"),
            "confidence": record.confidence,
            "follow_up": record.follow_up,
            "sources": json.loads(record.sources or "[]"),
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }


interview_intelligence = InterviewIntelligence()
