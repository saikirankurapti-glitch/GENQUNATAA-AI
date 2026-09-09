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
