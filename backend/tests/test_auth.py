import asyncio
import hashlib
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_auth.db"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "development"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.db_models import AuthSessionRecord, UserRecord
from app.main import app


def test_register_login_me_logout() -> None:
    with TestClient(app) as client:
        email = "auth-test@example.com"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "name": "Auth Test"})
        assert registered.status_code == 201
        assert registered.json()["email"] == email

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Auth Test"

        logged_out = client.post("/api/v1/auth/logout")
        assert logged_out.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401

        logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
        assert logged_in.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200


def test_duplicate_registration_rejected() -> None:
    with TestClient(app) as client:
        email = "duplicate-test@example.com"
        assert client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"}).status_code == 201
        assert client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"}).status_code == 409


def test_password_is_stored_as_argon2_hash() -> None:
    email = "argon2-test@example.com"
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"})
        assert response.status_code == 201

    async def read_hash() -> str:
        async with SessionLocal() as db:
            user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
            assert user is not None
            return user.password_hash

    password_hash = asyncio.run(read_hash())
    assert password_hash.startswith("$argon2")
    assert "StrongPass123" not in password_hash


def test_logout_revokes_server_side_session() -> None:
    email = "revoke-test@example.com"
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"})
        assert response.status_code == 201
        token = client.cookies.get("genquantaa_session")
        assert token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        assert client.post("/api/v1/auth/logout").status_code == 200

    async def read_session() -> AuthSessionRecord | None:
        async with SessionLocal() as db:
            return await db.scalar(select(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash))

    session = asyncio.run(read_session())
    assert session is not None
    assert session.revoked_at is not None


def test_old_cookie_is_rejected_after_logout() -> None:
    with TestClient(app) as client:
        email = "cookie-revoke-test@example.com"
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"})
        assert response.status_code == 201
        token = client.cookies.get("genquantaa_session")
        assert token

        assert client.post("/api/v1/auth/logout").status_code == 200
        client.cookies.set("genquantaa_session", token)
        assert client.get("/api/v1/auth/me").status_code == 401


def test_sessions_are_user_scoped_and_mark_current_session() -> None:
    with TestClient(app, headers={"User-Agent": "Mozilla/5.0 Chrome/140.0 Windows NT 10.0"}) as first:
        assert first.post("/api/v1/auth/register", json={"email": "sessions-a@example.com", "password": "StrongPass123"}).status_code == 201
        # A second login creates a distinct active session for the same user.
        assert first.post("/api/v1/auth/login", json={"email": "sessions-a@example.com", "password": "StrongPass123"}).status_code == 200
        sessions = first.get("/api/v1/auth/sessions")
        assert sessions.status_code == 200
        rows = sessions.json()
        assert len(rows) == 2
        assert sum(row["current"] for row in rows) == 1
        assert all(row["device"] == "Chrome · Windows" for row in rows)

        with TestClient(app) as second:
            assert second.post("/api/v1/auth/register", json={"email": "sessions-b@example.com", "password": "StrongPass123"}).status_code == 201
            other = second.get("/api/v1/auth/sessions")
            assert other.status_code == 200
            assert len(other.json()) == 1
            assert all(row["id"] not in {item["id"] for item in rows} for row in other.json())


def test_revoke_individual_session_and_revoke_all() -> None:
    with TestClient(app) as client:
        email = "session-revoke-api@example.com"
        assert client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"}).status_code == 201
        first_token = client.cookies.get("genquantaa_session")
        assert first_token

        assert client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).status_code == 200
        rows = client.get("/api/v1/auth/sessions").json()
        assert len(rows) == 2
        old_session_id = next(row["id"] for row in rows if not row["current"])

        revoked = client.delete(f"/api/v1/auth/sessions/{old_session_id}")
        assert revoked.status_code == 200
        assert revoked.json()["current"] is False
        remaining = client.get("/api/v1/auth/sessions")
        assert remaining.status_code == 200
        assert len(remaining.json()) == 1
        assert remaining.json()[0]["current"] is True

        # Restore the first token to prove the individually revoked session is rejected.
        client.cookies.set("genquantaa_session", first_token)
        assert client.get("/api/v1/auth/me").status_code == 401

        # The current login is still valid through the current token.
        current_token = rows[0]["id"]
        assert current_token
        # Re-authenticate to obtain a fresh current session before testing revoke-all.
        client.cookies.clear()
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).status_code == 200
        all_revoked = client.post("/api/v1/auth/sessions/revoke-all")
        assert all_revoked.status_code == 200
        assert all_revoked.json()["revoked_count"] >= 1
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.get("/api/v1/auth/sessions").status_code == 401
