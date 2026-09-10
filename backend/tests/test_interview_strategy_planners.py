import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_interview_strategy_planners.db"
os.environ["AUTH_SECRET"] = "test-interview-strategy-secret"
os.environ["APP_ENV"] = "development"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from app.main import app


def register(client: TestClient, email: str) -> None:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": email.split("@")[0]})
    assert response.status_code == 201


def upload_resume(client: TestClient, name: str, skills: str) -> None:
    response = client.post("/api/v1/resume/upload", files={"file": ("resume.txt", f"{name}\n{name}@example.com\n5 years {skills}".encode(), "text/plain")})
    assert response.status_code == 200


def test_role_intelligence_uses_only_current_users_resume() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "strategy-first@example.com")
        register(second, "strategy-second@example.com")
        upload_resume(first, "First Candidate", "Python Azure Databricks SQL")
        first_result = first.post("/api/v1/role-intelligence/analyze", json={"target_role": "Azure Data Engineer", "job_description": "Build Azure data pipelines with Python and SQL."})
        second_result = second.post("/api/v1/role-intelligence/analyze", json={"target_role": "Azure Data Engineer", "job_description": "Build Azure data pipelines with Python and SQL."})
        assert first_result.status_code == 200
        assert second_result.status_code == 200
        assert "python" in first_result.json()["candidate_skills"].lower()
        assert second_result.json()["candidate_skills"] == "unknown"


def test_preparation_planner_fallback_and_validation() -> None:
    with TestClient(app) as client:
        register(client, "planner@example.com")
        upload_resume(client, "Planner Candidate", "Python SQL Azure")
        response = client.post("/api/v1/preparation/plan", json={"target_role": "Data Engineer", "job_description": "Build ETL pipelines.", "available_minutes": 180})
        assert response.status_code == 200
        body = response.json()
        assert body["target_role"] == "Data Engineer"
        assert body["candidate_skills"] != "unknown"
        assert body["available_minutes"] == 180
        assert body["sessions"]
        invalid = client.post("/api/v1/preparation/plan", json={"job_description": "Build ETL pipelines.", "available_minutes": "abc"})
        assert invalid.status_code == 400
        assert "integer" in invalid.json()["detail"]


def test_strategy_endpoints_require_authentication() -> None:
    with TestClient(app) as client:
        assert client.post("/api/v1/role-intelligence/analyze", json={"job_description": "x"}).status_code == 401
        assert client.post("/api/v1/preparation/plan", json={"job_description": "x", "available_minutes": 60}).status_code == 401
