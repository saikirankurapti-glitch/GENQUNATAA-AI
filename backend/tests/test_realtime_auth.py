import asyncio
import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_realtime_auth.db"
os.environ["AUTH_SECRET"] = "test-realtime-secret"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.db_models import SessionRecord, UserRecord
from app.main import app
from app.realtime import _owned_session


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": email.split("@", 1)[0]},
    )
    assert response.status_code == 201


def test_realtime_rejects_unauthenticated_socket() -> None:
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/api/v1/realtime/ws"):
                raise AssertionError("unauthenticated websocket was accepted")
        except Exception as exc:
            assert "403" in str(exc) or "1008" in str(exc)


def test_realtime_session_ownership_is_enforced() -> None:
    async def scenario() -> None:
        await init_db()
        async with SessionLocal() as db:
            first = UserRecord(email=f"first-{uuid4()}@example.com", name="first", password_hash="test")
            second = UserRecord(email=f"second-{uuid4()}@example.com", name="second", password_hash="test")
            db.add_all([first, second])
            await db.commit()
            await db.refresh(first)
            await db.refresh(second)

            record = SessionRecord(title="private live", mode="live", user_id=first.id)
            db.add(record)
            await db.commit()
            await db.refresh(record)
            session_id = record.id
            first_id = first.id
            second_id = second.id

        assert await _owned_session(session_id, first_id) is True
        assert await _owned_session(session_id, second_id) is False

    asyncio.run(scenario())
