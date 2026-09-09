from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user
from .config import get_settings
from .db import get_db
from .db_models import UserRecord

Role = Literal["admin", "cto", "manager", "team_member"]
ROLES: tuple[str, ...] = ("admin", "cto", "manager", "team_member")
ROLE_RANK = {"team_member": 10, "manager": 20, "cto": 30, "admin": 40}
FEATURE_ROLES: dict[str, set[str]] = {
    "admin": {"admin", "cto"},
    "pricing": {"admin", "cto"},
    "manager": {"admin", "cto", "manager"},
    "security": {"admin", "cto", "manager", "team_member"},
}

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])
settings = get_settings()


class RoleUpdate(BaseModel):
    role: Role


class AdminUserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool


def has_feature_access(role: str, feature: str) -> bool:
    return role in FEATURE_ROLES.get(feature, {"admin", "cto", "manager", "team_member"})


def require_roles(*roles: str):
    async def dependency(user: UserRecord = Depends(current_user)) -> UserRecord:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency


def _bootstrap_role(email: str) -> str | None:
    normalized = email.lower().strip()
    if normalized in settings.bootstrap_admin_email_list:
        return "admin"
    if normalized in settings.bootstrap_cto_email_list:
        return "cto"
    return None


async def apply_bootstrap_role(user: UserRecord) -> None:
    role = _bootstrap_role(user.email)
    if role and user.role != role:
        user.role = role


@router.get("/roles")
async def roles(user: UserRecord = Depends(current_user)) -> dict[str, object]:
    return {"role": user.role, "roles": list(ROLES), "features": {key: has_feature_access(user.role, key) for key in FEATURE_ROLES}}


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(user: UserRecord = Depends(require_roles("admin", "cto")), db: AsyncSession = Depends(get_db)) -> list[AdminUserOut]:
    users = (await db.scalars(select(UserRecord).order_by(UserRecord.created_at.asc()))).all()
    return [AdminUserOut(id=x.id, email=x.email, name=x.name, role=x.role, is_active=x.is_active) for x in users]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
async def update_role(user_id: UUID, payload: RoleUpdate, actor: UserRecord = Depends(require_roles("admin", "cto")), db: AsyncSession = Depends(get_db)) -> AdminUserOut:
    target = await db.get(UserRecord, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    if actor.role == "cto" and payload.role in {"admin", "cto"}:
        raise HTTPException(status_code=403, detail="CTO can manage manager and team-member roles only")
    if actor.role == "cto" and ROLE_RANK.get(target.role, 0) > ROLE_RANK["manager"]:
        raise HTTPException(status_code=403, detail="CTO cannot change an admin or CTO")
    target.role = payload.role
    await db.commit()
    await db.refresh(target)
    return AdminUserOut(id=target.id, email=target.email, name=target.name, role=target.role, is_active=target.is_active)


@router.get("/team", response_model=list[AdminUserOut])
async def team_users(user: UserRecord = Depends(require_roles("admin", "cto", "manager")), db: AsyncSession = Depends(get_db)) -> list[AdminUserOut]:
    users = (await db.scalars(select(UserRecord).where(UserRecord.role.in_(["manager", "team_member"])).order_by(UserRecord.created_at.asc()))).all()
    return [AdminUserOut(id=x.id, email=x.email, name=x.name, role=x.role, is_active=x.is_active) for x in users]
