import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_coding_isolation.db"
os.environ["AUTH_SECRET"] = "test-coding-isolation-secret"

from fastapi.testclient import TestClient

from app.main import app


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": email.split("@", 1)[0]},
    )
    assert response.status_code == 201


def test_coding_sessions_are_isolated_between_users() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "coding-first@example.com")
        register(second, "coding-second@example.com")

        first_result = first.post(
            "/api/v1/coding/analyze",
            json={"code": "print('first')", "question": "Write a Python hello world program", "language": "python"},
        )
        assert first_result.status_code in {200, 502}

        if first_result.status_code == 502:
            # Gemini is optional in CI; ownership can still be verified by creating a session via the sessions API.
            created = first.post("/api/v1/sessions", json={"title": "Coding", "mode": "coding"})
            assert created.status_code == 200
            session_id = created.json()["id"]
        else:
            session_id = first_result.json()["session_id"]

        assert first.get(f"/api/v1/coding/sessions/{session_id}").status_code == 200
        assert second.get(f"/api/v1/coding/sessions/{session_id}").status_code == 404
        assert first.post(
            "/api/v1/coding/analyze",
            json={"session_id": session_id, "code": "print('second')", "question": "Use Python", "language": "python"},
        ).status_code in {200, 502}
