import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_profile_intelligence.db"
os.environ["AUTH_SECRET"] = "test-profile-intelligence-secret"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from app.main import app


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": email.split("@", 1)[0]},
    )
    assert response.status_code == 201


def test_profile_context_is_user_scoped() -> None:
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "profile-first@example.com")
        register(second, "profile-second@example.com")

        uploaded = first.post(
            "/api/v1/resume/upload",
            files={
                "file": (
                    "first-resume.txt",
                    b"First Candidate\nfirst@example.com\n5 years Python Azure Databricks SQL",
                    "text/plain",
                )
            },
        )
        assert uploaded.status_code == 200
        assert first.get("/api/v1/profile/context").status_code == 200
        assert first.get("/api/v1/profile/context").json()["name"] == "First Candidate"
        assert second.get("/api/v1/profile/context").status_code == 404
        assert second.get("/api/v1/profile/analysis").status_code == 200
        assert second.get("/api/v1/profile/analysis").json() is None


def test_profile_analysis_without_ai_uses_deterministic_fallback() -> None:
    with TestClient(app) as client:
        register(client, "fallback-profile@example.com")
        uploaded = client.post(
            "/api/v1/resume/upload",
            files={
                "file": (
                    "fallback.txt",
                    b"Fallback Candidate\nfallback@example.com\n4 years Python SQL Azure",
                    "text/plain",
                )
            },
        )
        assert uploaded.status_code == 200
        response = client.get("/api/v1/profile/analysis")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Fallback Candidate"
        assert "python" in body["skills"]
        assert body["core_strengths"]
