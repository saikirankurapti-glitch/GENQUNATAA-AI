import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient) -> None:
    email = "visual-api-test@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "name": "Visual Test"})
    if registered.status_code == 409:
        logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
        assert logged_in.status_code == 200
    else:
        assert registered.status_code == 201


def test_visual_rejects_non_image():
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415


def test_visual_rejects_empty_image():
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("screen.png", b"", "image/png")},
        )
        assert response.status_code == 400
