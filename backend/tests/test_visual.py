import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["AUTH_SECRET"] = "test-visual-secret"

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str) -> None:
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "name": "Visual Test"})
    assert registered.status_code == 201


def test_visual_rejects_non_image():
    with TestClient(app) as client:
        _login(client, "visual-non-image@example.com")
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415


def test_visual_rejects_empty_image():
    with TestClient(app) as client:
        _login(client, "visual-empty-image@example.com")
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("screen.png", b"", "image/png")},
        )
        assert response.status_code == 400
