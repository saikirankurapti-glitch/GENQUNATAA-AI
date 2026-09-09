from __future__ import annotations

from typing import Any

from .config import get_settings


class GeminiService:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    async def generate(self, message: str, context: str | None = None) -> str:
        if not self.api_key:
            return (
                "Gemini is not configured yet. Set GEMINI_API_KEY in your .env file "
                "to enable live AI answers."
            )

        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You are GenQuantaa AI, a concise real-time interview and coding copilot. "
                "Answer the user's question directly. If context is provided, use it as "
                "supporting evidence and do not invent facts.\n\n"
                f"Context:\n{context or '(none)'}\n\n"
                f"User question:\n{message}"
            )
            response: Any = await client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return response.text or "I could not generate an answer."
        except Exception as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

    async def analyze_visual(self, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        """Analyze one explicitly user-selected screenshot without persisting the image."""
        if not self.api_key:
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY in your .env file.")

        try:
            from google import genai
            from google.genai import types
            import json

            client = genai.Client(api_key=self.api_key)
            prompt = """
You are GenQuantaa AI's visual interview and coding-context analyzer.
Analyze only what is visibly legible in the supplied screenshot. Do not invent hidden,
blurred, cropped, or unreadable content. Return strict JSON with these fields:
summary, visible_text, code, language, context_type, question, confidence, actionable_context.
context_type must be one of coding_problem, interview_question, architecture_diagram, sql,
technical_ui, general, unknown. Return null for language/question when absent.
For diagrams, describe visible components and relationships. For code, preserve readable line
structure and never fabricate missing lines. If text is too small to read, omit it rather than guessing.
"""
            response: Any = await client.aio.models.generate_content(
                model=self.model,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "summary": {"type": "STRING"},
                            "visible_text": {"type": "STRING"},
                            "code": {"type": "STRING"},
                            "language": {"type": "STRING", "nullable": True},
                            "context_type": {"type": "STRING"},
                            "question": {"type": "STRING", "nullable": True},
                            "confidence": {"type": "NUMBER"},
                            "actionable_context": {"type": "STRING"},
                        },
                        "required": ["summary", "visible_text", "code", "language", "context_type", "question", "confidence", "actionable_context"],
                    },
                ),
            )
            result = json.loads(response.text or "{}")
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0))))
            allowed = {"coding_problem", "interview_question", "architecture_diagram", "sql", "technical_ui", "general", "unknown"}
            return {
                "summary": str(result.get("summary", "")),
                "visible_text": str(result.get("visible_text", "")),
                "code": str(result.get("code", "")),
                "language": result.get("language"),
                "context_type": result.get("context_type") if result.get("context_type") in allowed else "unknown",
                "question": result.get("question"),
                "confidence": round(confidence, 3),
                "actionable_context": str(result.get("actionable_context", "")),
            }
        except Exception as exc:
            raise RuntimeError(f"Visual analysis failed: {exc}") from exc
