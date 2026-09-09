from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = "Untitled session"
    mode: str = "copilot"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionCreate(BaseModel):
    title: str = "Untitled session"
    mode: str = "copilot"


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=12000)
    context: str | None = Field(default=None, max_length=30000)


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    model: str
