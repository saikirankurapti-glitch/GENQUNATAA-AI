from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db_models import InterviewQuestion, MessageRecord
from .rag import retriever


class VisualCopilotFusion:
    """Generate a grounded interview answer using transcript + explicit visual context."""

    def __init__(self) -> None:
        self.ai = GeminiService()
        self.answer_modes = {"concise", "detailed", "star", "technical"}

    async def analyze(
        self,
        db: AsyncSession,
        session_id: UUID,
        transcript: str,
        visual_context: dict[str, Any] | None,
        detection_confidence: float = 1.0,
        detection_reason: str = "manual",
        answer_mode: str = "concise",
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        mode = answer_mode if answer_mode in self.answer_modes else "concise"
        retrieved = await retriever.retrieve(db, transcript, limit=6, user_id=user_id)
        source_details = [
            {
                "filename": str(item.get("filename", "Unknown source")),
                "score": round(float(item.get("score", 0)), 3),
                "snippet": str(item.get("content", ""))[:180].replace("\n", " "),
            }
            for item in retrieved
        ]
        allowed_sources = [item["filename"] for item in source_details]
        knowledge = "\n\n".join(
            f"Source ID: {i + 1}\nFilename: {item['filename']}\n{item['content']}"
            for i, item in enumerate(retrieved)
        ) or "No resume or knowledge-base context matched."

        visual = visual_context or {}
        visual_text = str(visual.get("visible_text", ""))[:12000]
        visual_code = str(visual.get("code", ""))[:16000]
        visual_question = str(visual.get("question", ""))[:4000]
        visual_actionable = str(visual.get("actionable_context", ""))[:8000]
        visual_type = str(visual.get("context_type", "unknown"))
        visual_confidence = max(0.0, min(1.0, float(visual.get("confidence", 0))))

        mode_instruction = {
            "concise": "Answer in 3-5 spoken sentences. Prioritize clarity and speed.",
            "detailed": "Answer in 6-10 spoken sentences with implementation detail.",
            "star": "For behavioral/project questions use Situation, Task, Action, Result. For technical questions use a structured practical explanation.",
            "technical": "Give a technically deep answer with architecture, implementation choices, trade-offs, and complexity where relevant.",
        }[mode]
        prompt = f"""You are GenQuantaa AI's multimodal interview intelligence engine.
Use the interviewer transcript as the primary question signal and the explicit visual context as supporting evidence.
{mode_instruction}
Never invent candidate experience or unreadable visual content. If visual text/code is incomplete, say so instead of guessing.
Prefer the visible coding/problem statement when it directly clarifies the question. Use resume/knowledge sources for candidate-specific claims.

Return ONLY valid JSON with keys:
question_type: one of technical, behavioral, system_design, coding, project, general
answer: candidate-ready spoken answer
key_points: array of 3 to 6 short points
confidence: number 0 to 1
follow_up: one likely follow-up question
sources: array of filenames used, only from supplied filenames
visual_context_used: boolean

Answer mode: {mode}
Interviewer question:
{transcript}

Visual context type: {visual_type}
Visual confidence: {visual_confidence:.3f}
Visual detected question:
{visual_question or '(none)'}
Visual visible text:
{visual_text or '(none)'}
Visual code:
{visual_code or '(none)'}
Visual actionable context:
{visual_actionable or '(none)'}

Resume/knowledge context:
{knowledge}
"""
        if self.ai.api_key:
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
                            "visual_context_used": {"type": "BOOLEAN"},
                        },
                        "required": ["question_type", "answer", "key_points", "confidence", "follow_up", "sources", "visual_context_used"],
                    },
                ),
            )
            try:
                result = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                result = {"question_type": "general", "answer": response.text or "I could not generate an answer.", "key_points": [], "confidence": 0.5, "follow_up": "", "sources": [], "visual_context_used": bool(visual_context)}
        else:
            result = {"question_type": "general", "answer": "AI is not configured. Add GEMINI_API_KEY to generate the multimodal interview answer.", "key_points": [], "confidence": 0.0, "follow_up": "", "sources": [], "visual_context_used": False}

        model_confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        retrieval_strength = max((float(item.get("score", 0)) for item in retrieved), default=0.0)
        retrieval_strength = max(0.0, min(1.0, retrieval_strength))
        detection = max(0.0, min(1.0, detection_confidence))
        grounded = model_confidence * 0.60 + retrieval_strength * 0.15 + detection * 0.10 + visual_confidence * 0.15
        if not visual_context:
            grounded = model_confidence * 0.70 + retrieval_strength * 0.20 + detection * 0.10
        if not retrieved and not visual_context:
            grounded = min(model_confidence, max(0.25, detection * 0.70))

        requested = {str(x).strip() for x in result.get("sources", []) if str(x).strip()}
        sources = [name for name in allowed_sources if name in requested]
        if requested and not sources:
            sources = allowed_sources[:3]
        answer = str(result.get("answer", "")).strip()
        record = InterviewQuestion(
            session_id=session_id,
            transcript=transcript,
            question_type=str(result.get("question_type", "general")),
            answer=answer,
            key_points=json.dumps(result.get("key_points", [])),
            confidence=round(grounded, 4),
            follow_up=str(result.get("follow_up", "")),
            sources=json.dumps(sources),
        )
        db.add(record)
        db.add(MessageRecord(session_id=session_id, role="interviewer", content=transcript))
        db.add(MessageRecord(session_id=session_id, role="assistant", content=answer))
        await db.commit()
        await db.refresh(record)
        return {
            "id": str(record.id),
            "session_id": str(session_id),
            "transcript": transcript,
            "question_type": record.question_type,
            "answer": answer,
            "key_points": result.get("key_points", []),
            "confidence": record.confidence,
            "confidence_label": "High" if grounded >= 0.80 else "Medium" if grounded >= 0.60 else "Low",
            "detection_confidence": round(detection, 3),
            "detection_reason": detection_reason,
            "retrieval_strength": round(retrieval_strength, 3),
            "follow_up": record.follow_up,
            "sources": sources,
            "source_details": source_details,
            "answer_mode": mode,
            "visual_context_used": bool(result.get("visual_context_used", bool(visual_context))),
            "visual_context_type": visual_type,
            "visual_confidence": round(visual_confidence, 3),
        }


visual_copilot_fusion = VisualCopilotFusion()
