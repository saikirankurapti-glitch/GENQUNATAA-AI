from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionBoundary:
    text: str
    confidence: float
    reason: str


class QuestionBoundaryDetector:
    """Turns finalized live-transcription fragments into interview-question boundaries."""

    QUESTION_STARTERS = (
        "what ", "why ", "how ", "when ", "where ", "which ", "who ",
        "can you ", "could you ", "would you ", "will you ", "have you ",
        "has your ", "do you ", "did you ", "are you ", "were you ",
        "tell me ", "explain ", "describe ", "compare ", "walk me through ",
        "difference between ", "what's ", "what is ", "what are ",
    )
    MIN_LENGTH = 10
    MAX_LENGTH = 700

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._last_emitted = ""

    def add(self, text: str) -> None:
        value = self._clean(text)
        if value:
            self._parts.append(value)

    def flush(self) -> QuestionBoundary | None:
        value = self._clean(" ".join(self._parts))
        self._parts.clear()
        if not value:
            return None

        question = self._extract_question(value)
        if not question:
            return None
        normalized = self._normalize_for_compare(question.text)
        if normalized == self._last_emitted:
            return None
        self._last_emitted = normalized
        return question

    def reset(self) -> None:
        self._parts.clear()
        self._last_emitted = ""

    def _extract_question(self, text: str) -> QuestionBoundary | None:
        candidates = [self._clean(part) for part in re.split(r"(?<=[?.!])\s+", text)]
        candidates = [part for part in candidates if len(part) >= self.MIN_LENGTH]
        if not candidates:
            return None

        explicit = [part for part in candidates if "?" in part]
        if explicit:
            selected = explicit[-1]
            return QuestionBoundary(selected[: self.MAX_LENGTH], 0.98, "explicit_question_mark")

        for candidate in reversed(candidates):
            lower = candidate.lower()
            if lower.startswith(self.QUESTION_STARTERS):
                return QuestionBoundary(candidate[: self.MAX_LENGTH], 0.90, "interrogative_starter")

        # Interviewers sometimes omit punctuation in speech. Prefer a bounded
        # sentence that contains an interrogative phrase over generating an answer
        # for ordinary interviewer commentary.
        lower = text.lower()
        if any(token in lower for token in ("can you", "could you", "would you", "tell me", "explain", "describe")):
            return QuestionBoundary(text[: self.MAX_LENGTH], 0.76, "spoken_interrogative_phrase")
        return None

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize_for_compare(value: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", value.lower()).strip()
