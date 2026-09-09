import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_rbac.db"
os.environ["AUTH_SECRET"] = "test-rbac-secret"
os.environ["APP_ENV"] = "development"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.db_models import UserRecord
from app.main import app


def register(client: TestClient, email: str) -> None:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "name": email.split("@")[0]})
    assert response.status_code == 201


def set_role(email: str, role: str) -> None:
    async def update_role() -> None:
        async with SessionLocal() as db:
            user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
            assert user is not None
            user.role = role
            await db.commit()
    asyncio.run(update_role())


def test_rbac_denies_team_member_and_allows_admin() -> None:
    member_email = "rbac-member@example.com"
    admin_email = "rbac-admin@example.com"
    with TestClient(app) as member, TestClient(app) as admin:
        register(member, member_email)
        register(admin, admin_email)
        set_role(admin_email, "admin")
        assert member.get("/api/v1/rbac/users").status_code == 403
        assert admin.get("/api/v1/rbac/users").status_code == 200


def test_admin_can_change_role_but_cannot_change_self() -> None:
    admin_email = "rbac-owner@example.com"
    target_email = "rbac-target@example.com"
    with TestClient(app) as admin, TestClient(app) as target:
        register(admin, admin_email)
        register(target, target_email)
        set_role(admin_email, "admin")
        users = admin.get("/api/v1/rbac/users").json()
        target_user = next(x for x in users if x["email"] == target_email)
        changed = admin.patch(f"/api/v1/rbac/users/{target_user['id']}/role", json={"role": "manager"})
        assert changed.status_code == 200
        assert changed.json()["role"] == "manager"
        owner = next(x for x in users if x["email"] == admin_email)
        assert admin.patch(f"/api/v1/rbac/users/{owner['id']}/role", json={"role": "team_member"}).status_code == 400
        assert target.get("/api/v1/rbac/roles").json()["role"] == "manager"


def test_feature_matrix() -> None:
    cases = [
        ("team_member", {"admin": False, "pricing": False, "manager": False, "security": True}),
        ("manager", {"admin": False, "pricing": False, "manager": True, "security": True}),
        ("cto", {"admin": True, "pricing": True, "manager": True, "security": True}),
        ("admin", {"admin": True, "pricing": True, "manager": True, "security": True}),
    ]
    for index, (role, expected) in enumerate(cases):
        email = f"rbac-matrix-{index}@example.com"
        with TestClient(app) as client:
            register(client, email)
            set_role(email, role)
            data = client.get("/api/v1/rbac/roles").json()
            assert data["role"] == role
            assert data["features"] == expected
