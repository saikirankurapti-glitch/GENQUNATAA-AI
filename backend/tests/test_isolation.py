import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_isolation.db"
os.environ["AUTH_SECRET"] = "test-isolation-secret"

from fastapi.testclient import TestClient

from app.main import app


def register(client: TestClient, email: str) -> None:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": email.split("@", 1)[0]})
    assert response.status_code == 201


def test_sessions_are_isolated_between_users() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "first@example.com")
        register(second, "second@example.com")
        first_session = first.post("/api/v1/sessions", json={"title": "First", "mode": "copilot"})
        second_session = second.post("/api/v1/sessions", json={"title": "Second", "mode": "copilot"})
        assert first_session.status_code == 200
        assert second_session.status_code == 200
        first_id = first_session.json()["id"]
        second_id = second_session.json()["id"]
        assert first.get(f"/api/v1/sessions/{first_id}").status_code == 200
        assert second.get(f"/api/v1/sessions/{second_id}").status_code == 200
        assert first.get(f"/api/v1/sessions/{second_id}").status_code == 404
        assert second.get(f"/api/v1/sessions/{first_id}").status_code == 404


def test_documents_are_isolated_between_users() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "docs-first@example.com")
        register(second, "docs-second@example.com")
        uploaded = first.post("/api/v1/documents/upload", files={"file": ("private.txt", b"private first user content", "text/plain")})
        assert uploaded.status_code == 200
        first_docs = first.get("/api/v1/documents")
        second_docs = second.get("/api/v1/documents")
        assert first_docs.status_code == 200
        assert second_docs.status_code == 200
        assert [item["filename"] for item in first_docs.json()] == ["private.txt"]
        assert second_docs.json() == []
