from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db_models import InterviewQuestion, MessageRecord, SessionNote, SessionRecord
from .profile_intelligence import build_profile_context
from .rag import retriever


class InterviewIntelligence:
    ANSWER_MODES = {"concise", "detailed", "star", "technical"}
    QUESTION_TYPES = {"technical", "behavioral", "system_design", "coding", "project", "general"}
    DIFFICULTIES = {"easy", "medium", "hard", "expert"}

    def __init__(self) -> None:
        self.ai = GeminiService()

    @staticmethod
    def looks_like_question(text: str) -> bool:
        value = text.strip().lower()
        if not value or len(value) < 8:
            return False
        if "?" in value:
            return True
        return value.startswith(("what ", "why ", "how ", "when ", "where ", "which ", "who ", "can you ", "could you ", "would you ", "tell me ", "explain ", "describe ", "compare ", "difference between ", "have you ", "do you ", "did you ", "walk me through "))

    @staticmethod
    def _source_details(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"filename": str(item.get("filename", "Unknown source")), "score": round(float(item.get("score", 0.0)), 3), "snippet": str(item.get("content", ""))[:180].replace("\n", " ")} for item in retrieved]

    @staticmethod
    def _list(value: Any, limit: int = 8) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(x).strip() for x in value if str(x).strip()][:limit]

    async def analyze_question(self, db: AsyncSession, session_id: UUID, transcript: str, detection_confidence: float = 1.0, detection_reason: str = "manual", answer_mode: str = "concise", user_id: UUID | None = None) -> dict[str, Any]:
        answer_mode = answer_mode if answer_mode in self.ANSWER_MODES else "concise"
        retrieved = await retriever.retrieve(db, transcript, limit=6, user_id=user_id)
        profile = await build_profile_context(db, user_id) if user_id else None
        source_details = self._source_details(retrieved)
        allowed_sources = [item["filename"] for item in source_details]
        context = "\n\n".join(f"Source ID: {index + 1}\nFilename: {item['filename']}\n{item['content']}" for index, item in enumerate(retrieved)) or "No resume or knowledge-base context matched."
        profile_context = "No authenticated resume profile available."
        if profile:
            profile_context = f"Candidate name: {profile.get('name') or 'Not provided'}\nCandidate skills: {', '.join(profile.get('skills', []))}\nExperience years: {profile.get('experience_years') or 'Not provided'}\nResume source: {profile.get('profile_source', 'resume')}\nResume evidence:\n{profile.get('resume_text', '')[:12000]}"
        mode_instruction = {"concise":"Answer in 3-5 spoken sentences. Prioritize clarity and speed.","detailed":"Answer in 6-10 spoken sentences with enough implementation detail for a strong interview response.","star":"For behavioral/project questions use Situation, Task, Action, Result structure. For technical questions, use a similarly structured practical explanation.","technical":"Give a technically deep answer with architecture, implementation choices, trade-offs, and complexity where relevant."}[answer_mode]
        prompt = f"""You are GenQuantaa AI's Interview Question Intelligence 2.0 engine.
Analyze the interviewer's question and produce a candidate-ready answer plus structured coaching intelligence.
{mode_instruction}
Use the candidate profile and supplied resume/knowledge context when relevant. Never invent candidate experience.
For experience/behavioral/project questions, prefer concrete evidence from the candidate profile. For generic technical questions, answer accurately even when the resume is not relevant.
Difficulty means the interview complexity required to answer well. answer_quality is the quality of the GENERATED answer against correctness, relevance, completeness, clarity and interview usefulness, from 0 to 1. Do not claim it is a measured candidate score.
missing_concepts should contain the most important concepts a strong answer should cover but the generated answer does not adequately cover.
ideal_answer should be a stronger reference answer, not a copy of the generated answer.
coaching_feedback should give 2-4 actionable improvements for a candidate.
predicted_follow_ups should contain 2-4 likely interviewer follow-up questions.
Source attribution MUST use only the supplied filenames. If a source was not used, omit it.
Confidence should reflect answer correctness AND how strongly the supplied context supports it.

Return ONLY valid JSON with these keys:
question_type: one of technical, behavioral, system_design, coding, project, general
difficulty: one of easy, medium, hard, expert
answer: a spoken answer in first person where appropriate
answer_quality: number from 0 to 1
key_points: array of 3 to 6 short points
missing_concepts: array of 0 to 6 concepts
ideal_answer: concise strong reference answer
coaching_feedback: actionable coaching feedback
predicted_follow_ups: array of 2 to 4 likely questions
confidence: number from 0 to 1
follow_up: one primary likely follow-up question
sources: array of source filenames used, selected ONLY from the supplied filenames

Answer mode: {answer_mode}
Question:
{transcript}

Candidate profile:
{profile_context}

Retrieved knowledge context:
{context}
"""
        fallback = {"question_type":"general","difficulty":"medium","answer":"AI is not configured. Add GEMINI_API_KEY to generate the interview answer.","answer_quality":0.0,"key_points":[],"missing_concepts":[],"ideal_answer":"","coaching_feedback":"Configure Gemini to enable interview intelligence.","predicted_follow_ups":[],"confidence":0.0,"follow_up":"","sources":[]}
        result: dict[str, Any] = fallback
        if self.ai.api_key:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.ai.api_key)
            response = await client.aio.models.generate_content(model=self.ai.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type":"OBJECT","properties":{"question_type":{"type":"STRING"},"difficulty":{"type":"STRING"},"answer":{"type":"STRING"},"answer_quality":{"type":"NUMBER"},"key_points":{"type":"ARRAY","items":{"type":"STRING"}},"missing_concepts":{"type":"ARRAY","items":{"type":"STRING"}},"ideal_answer":{"type":"STRING"},"coaching_feedback":{"type":"STRING"},"predicted_follow_ups":{"type":"ARRAY","items":{"type":"STRING"}},"confidence":{"type":"NUMBER"},"follow_up":{"type":"STRING"},"sources":{"type":"ARRAY","items":{"type":"STRING"}}},"required":["question_type","difficulty","answer","answer_quality","key_points","missing_concepts","ideal_answer","coaching_feedback","predicted_follow_ups","confidence","follow_up","sources"]}))
            try:
                result = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                result = {**fallback, "answer": response.text or fallback["answer"], "confidence": 0.5}

        question_type = str(result.get("question_type", "general")) if str(result.get("question_type", "general")) in self.QUESTION_TYPES else "general"
        difficulty = str(result.get("difficulty", "medium")).lower() if str(result.get("difficulty", "medium")).lower() in self.DIFFICULTIES else "medium"
        model_confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        answer_quality = max(0.0, min(1.0, float(result.get("answer_quality", model_confidence))))
        retrieval_strength = max(0.0, min(1.0, max((float(item.get("score", 0.0)) for item in retrieved), default=0.0)))
        profile_strength = 0.15 if profile else 0.0
        grounded_confidence = (model_confidence * 0.65) + (retrieval_strength * 0.15) + (max(0.0, min(1.0, detection_confidence)) * 0.10) + profile_strength
        if not retrieved and not profile:
            grounded_confidence = min(model_confidence, max(0.25, detection_confidence * 0.70))
        answer = str(result.get("answer", "")).strip()
        key_points = self._list(result.get("key_points"))
        missing_concepts = self._list(result.get("missing_concepts"))
        predicted_follow_ups = self._list(result.get("predicted_follow_ups"), 4)
        ideal_answer = str(result.get("ideal_answer", "")).strip()
        coaching_feedback = str(result.get("coaching_feedback", "")).strip()
        requested_sources = {str(item).strip() for item in result.get("sources", []) if str(item).strip()} if isinstance(result.get("sources"), list) else set()
        sources = [filename for filename in allowed_sources if filename in requested_sources]
        if requested_sources and not sources:
            sources = allowed_sources[:3]
        record = InterviewQuestion(session_id=session_id, transcript=transcript, question_type=question_type, difficulty=difficulty, answer=answer, answer_quality=round(answer_quality, 4), key_points=json.dumps(key_points), missing_concepts=json.dumps(missing_concepts), ideal_answer=ideal_answer, coaching_feedback=coaching_feedback, predicted_follow_ups=json.dumps(predicted_follow_ups), confidence=round(grounded_confidence, 4), follow_up=str(result.get("follow_up", "")), sources=json.dumps(sources))
        db.add(record)
        db.add(MessageRecord(session_id=session_id, role="interviewer", content=transcript))
        db.add(MessageRecord(session_id=session_id, role="assistant", content=answer))
        await db.commit()
        await db.refresh(record)
        payload = self.serialize_question(record)
        payload.update({"answer_mode":answer_mode,"detection_confidence":round(max(0.0,min(1.0,detection_confidence)),3),"detection_reason":detection_reason,"retrieval_strength":round(retrieval_strength,3),"profile_context_used":bool(profile),"confidence_label":self.confidence_label(grounded_confidence),"source_details":source_details})
        return payload

    @staticmethod
    def confidence_label(value: float) -> str:
        if value >= 0.80: return "High"
        if value >= 0.60: return "Medium"
        return "Low"

    async def add_note(self, db: AsyncSession, session_id: UUID, content: str, note_type: str = "insight") -> None:
        if content.strip():
            db.add(SessionNote(session_id=session_id, note_type=note_type, content=content.strip()))
            await db.commit()

    async def summarize(self, db: AsyncSession, session_id: UUID) -> dict[str, Any]:
        session = await db.get(SessionRecord, session_id)
        if not session: raise ValueError("Session not found")
        questions = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.created_at))).scalars().all()
        notes = (await db.execute(select(SessionNote).where(SessionNote.session_id == session_id).order_by(SessionNote.created_at))).scalars().all()
        transcript = "\n".join(f"Q: {q.transcript}\nA: {q.answer}\nQuality: {q.answer_quality}\nMissing: {q.missing_concepts}" for q in questions)
        note_text = "\n".join(n.content for n in notes)
        prompt = f"Summarize this interview session in JSON with keys summary, strengths, gaps, next_steps, score. Use the per-question quality and missing concepts to identify patterns. Keep it concise.\n{transcript}\nNotes:\n{note_text}"
        summary = {"summary":"No interview questions recorded yet.","strengths":[],"gaps":[],"next_steps":[],"score":0}
        if self.ai.api_key and questions:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.ai.api_key)
            response = await client.aio.models.generate_content(model=self.ai.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type":"OBJECT","properties":{"summary":{"type":"STRING"},"strengths":{"type":"ARRAY","items":{"type":"STRING"}},"gaps":{"type":"ARRAY","items":{"type":"STRING"}},"next_steps":{"type":"ARRAY","items":{"type":"STRING"}},"score":{"type":"NUMBER"}},"required":["summary","strengths","gaps","next_steps","score"]}))
            try: summary = json.loads(response.text or "{}")
            except json.JSONDecodeError: summary["summary"] = response.text or summary["summary"]
        return {"session_id":str(session_id),"question_count":len(questions),"notes_count":len(notes),**summary}

    @staticmethod
    def serialize_question(record: InterviewQuestion) -> dict[str, Any]:
        def parse(value: str) -> list[Any]:
            try: return json.loads(value or "[]")
            except (TypeError, json.JSONDecodeError): return []
        return {"id":str(record.id),"session_id":str(record.session_id),"transcript":record.transcript,"question_type":record.question_type,"difficulty":record.difficulty,"answer":record.answer,"answer_quality":record.answer_quality,"key_points":parse(record.key_points),"missing_concepts":parse(record.missing_concepts),"ideal_answer":record.ideal_answer,"coaching_feedback":record.coaching_feedback,"predicted_follow_ups":parse(record.predicted_follow_ups),"confidence":record.confidence,"follow_up":record.follow_up,"sources":parse(record.sources),"created_at":record.created_at.isoformat() if record.created_at else None}


interview_intelligence = InterviewIntelligence()
