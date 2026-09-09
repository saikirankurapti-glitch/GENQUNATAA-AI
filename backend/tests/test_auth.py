import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_auth.db"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "development"

from fastapi.testclient import TestClient

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
    with TestClient(app) as client:
        email = "argon2-test@example.com"
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123"})
        assert response.status_code == 201

        from sqlalchemy import select
        from app.db import SessionLocal
        from app.db_models import UserRecord

        import asyncio

        async def read_hash() -> str:
            async with SessionLocal() as db:
                user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
                assert user is not None
                return user.password_hash

        password_hash = asyncio.run(read_hash())
        assert password_hash.startswith("$argon2")
        assert "StrongPass123" not in password_hash
