from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .ai import GeminiService
from .db_models import InterviewQuestion


class CandidateAnswerEvaluator:
    DIMENSIONS = ("correctness_score", "relevance_score", "completeness_score", "structure_score", "technical_depth_score", "communication_score")

    def __init__(self) -> None:
        self.ai = GeminiService()

    @staticmethod
    def _score(value: Any) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 4)
        except (TypeError, ValueError):
            return 0.0

    async def evaluate(self, db: AsyncSession, question: InterviewQuestion, candidate_answer: str) -> dict[str, Any]:
        answer = candidate_answer.strip()
        if not answer:
            raise ValueError("candidate_answer is required")
        prompt = f"""You are GenQuantaa AI's candidate answer evaluator.
Evaluate the candidate's ACTUAL answer to the interview question. Do not grade the AI-generated answer.
Score each dimension from 0 to 1: correctness, relevance, completeness, structure, technical_depth, communication.
Technical depth should be judged relative to the question; for non-technical questions, use the dimension for depth of reasoning/evidence.
Do not penalize a candidate for claims that cannot be verified from the supplied context, but flag unsupported experience claims when they are clearly inconsistent with context.
Give concise, actionable feedback and identify missing concepts or evidence.

Return ONLY JSON:
correctness_score: number 0-1
relevance_score: number 0-1
completeness_score: number 0-1
structure_score: number 0-1
technical_depth_score: number 0-1
communication_score: number 0-1
candidate_score: weighted overall score 0-1
evaluation_feedback: concise actionable feedback
missing_concepts: array of up to 6 missing concepts/evidence

Question type: {question.question_type}
Difficulty: {question.difficulty}
Question:
{question.transcript}

Reference/ideal answer:
{question.ideal_answer}

Previously identified key points:
{question.key_points}

Candidate's actual answer:
{answer}
"""
        fallback = {name: 0.0 for name in self.DIMENSIONS}
        fallback.update({"candidate_score": 0.0, "evaluation_feedback": "Gemini is not configured. Add GEMINI_API_KEY to evaluate the candidate answer.", "missing_concepts": []})
        result: dict[str, Any] = fallback
        if self.ai.api_key:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.ai.api_key)
            response = await client.aio.models.generate_content(
                model=self.ai.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={"type":"OBJECT","properties":{
                        "correctness_score":{"type":"NUMBER"},"relevance_score":{"type":"NUMBER"},"completeness_score":{"type":"NUMBER"},"structure_score":{"type":"NUMBER"},"technical_depth_score":{"type":"NUMBER"},"communication_score":{"type":"NUMBER"},"candidate_score":{"type":"NUMBER"},"evaluation_feedback":{"type":"STRING"},"missing_concepts":{"type":"ARRAY","items":{"type":"STRING"}}},
                        "required":[*self.DIMENSIONS,"candidate_score","evaluation_feedback","missing_concepts"]},
                ),
            )
            try:
                result = json.loads(response.text or "{}")
            except json.JSONDecodeError:
                result = {**fallback, "evaluation_feedback": response.text or fallback["evaluation_feedback"]}

        scores = {name: self._score(result.get(name)) for name in self.DIMENSIONS}
        weighted = sum(scores.values()) / len(scores)
        model_score = self._score(result.get("candidate_score", weighted))
        # Keep the overall score bounded while preventing an arbitrary model score from ignoring dimensions.
        overall = round((weighted * 0.75) + (model_score * 0.25), 4)
        missing = result.get("missing_concepts", [])
        missing = [str(x).strip() for x in missing if str(x).strip()][:6] if isinstance(missing, list) else []
        question.candidate_answer = answer
        question.candidate_score = overall
        for name, value in scores.items():
            setattr(question, name, value)
        question.evaluation_feedback = str(result.get("evaluation_feedback", "")).strip()
        question.missing_concepts = json.dumps(missing)
        await db.commit()
        await db.refresh(question)
        return {
            "question_id": str(question.id),
            "candidate_answer": question.candidate_answer,
            "candidate_score": question.candidate_score,
            "correctness_score": question.correctness_score,
            "relevance_score": question.relevance_score,
            "completeness_score": question.completeness_score,
            "structure_score": question.structure_score,
            "technical_depth_score": question.technical_depth_score,
            "communication_score": question.communication_score,
            "evaluation_feedback": question.evaluation_feedback,
            "missing_concepts": missing,
        }


evaluator = CandidateAnswerEvaluator()
