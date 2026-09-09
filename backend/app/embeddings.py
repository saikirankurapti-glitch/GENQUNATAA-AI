from __future__ import annotations

import json
from math import sqrt
from typing import Sequence

from .config import get_settings


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_embedding_model
        self.dimensions = settings.gemini_embedding_dimensions

    async def embed(self, text: str) -> list[float]:
        if not self.api_key:
            return []
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        result = await client.aio.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
        )
        if not result.embeddings:
            return []
        return list(result.embeddings[0].values or [])


def serialize_embedding(values: Sequence[float]) -> str:
    return json.dumps(list(values), separators=(",", ":"))


def deserialize_embedding(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [float(item) for item in parsed]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
