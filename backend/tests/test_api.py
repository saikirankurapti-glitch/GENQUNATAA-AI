import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient) -> None:
    email = "session-api-test@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "name": "Session Test"})
    if registered.status_code == 409:
        logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
        assert logged_in.status_code == 200
    else:
        assert registered.status_code == 201


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_and_get_session() -> None:
    with TestClient(app) as client:
        _login(client)
        created = client.post("/api/v1/sessions", json={"title": "Interview", "mode": "copilot"})
        assert created.status_code == 200
        session_id = created.json()["id"]

        fetched = client.get(f"/api/v1/sessions/{session_id}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Interview"
