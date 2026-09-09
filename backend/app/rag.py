from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import Document, DocumentChunk
from .embeddings import EmbeddingService, cosine_similarity, deserialize_embedding


class Retriever:
    def __init__(self) -> None:
        self.embeddings = EmbeddingService()

    async def retrieve(self, db: AsyncSession, query: str, limit: int = 5) -> list[dict[str, str | float]]:
        limit = max(1, min(limit, 20))
        query_vector: list[float] = []
        if self.embeddings.api_key:
            try:
                query_vector = await self.embeddings.embed(query)
            except Exception:
                query_vector = []

        if query_vector and db.bind is not None and db.bind.dialect.name == "postgresql":
            distance = DocumentChunk.embedding_vector.cosine_distance(query_vector)
            result = await db.execute(
                select(DocumentChunk, Document.filename, distance.label("distance"))
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.embedding_vector.is_not(None))
                .order_by(distance)
                .limit(limit)
            )
            return [
                {"content": chunk.content, "filename": filename, "score": round(max(0.0, 1.0 - float(distance_value)), 4)}
                for chunk, filename, distance_value in result.all()
            ]

        result = await db.execute(select(DocumentChunk, Document.filename).join(Document, Document.id == DocumentChunk.document_id))
        rows = result.all()
        if not rows:
            return []

        scored: list[tuple[float, DocumentChunk, str]] = []
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        for chunk, filename in rows:
            vector = deserialize_embedding(chunk.embedding)
            semantic = cosine_similarity(query_vector, vector) if query_vector and vector else 0.0
            lexical = sum(chunk.content.lower().count(term) for term in query_terms)
            score = semantic + min(lexical * 0.02, 0.25)
            if score > 0:
                scored.append((score, chunk, filename))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [{"content": chunk.content, "filename": filename, "score": round(score, 4)} for score, chunk, filename in scored[:limit]]


retriever = Retriever()
