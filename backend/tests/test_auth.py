import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_auth.db"
os.environ["AUTH_SECRET"] = "test-secret"

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
