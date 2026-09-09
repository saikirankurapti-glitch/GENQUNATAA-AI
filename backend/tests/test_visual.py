import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from fastapi.testclient import TestClient

from app.main import app


def test_visual_rejects_non_image():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415


def test_visual_rejects_empty_image():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/visual/analyze",
            files={"file": ("screen.png", b"", "image/png")},
        )
        assert response.status_code == 400
