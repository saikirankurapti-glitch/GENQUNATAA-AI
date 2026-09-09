from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_session() -> None:
    created = client.post("/api/v1/sessions", json={"title": "Interview", "mode": "copilot"})
    assert created.status_code == 200
    session_id = created.json()["id"]

    fetched = client.get(f"/api/v1/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Interview"
