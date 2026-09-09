from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user
from .db import get_db
from .db_models import AuditLogRecord, UserRecord
from .rbac import require_roles

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


async def record_audit(
    db: AsyncSession,
    request: Request,
    action: str,
    actor_user_id: UUID | None = None,
    resource_type: str = "",
    resource_id: str = "",
    details: dict | None = None,
) -> None:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",", 1)[0].strip() if forwarded else (request.client.host if request.client else "")
    db.add(AuditLogRecord(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip[:64],
        user_agent=request.headers.get("user-agent", "")[:1000],
        created_at=datetime.now(timezone.utc),
    ))


class AuditLogOut(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    details: dict
    ip_address: str
    user_agent: str
    created_at: datetime


@router.get("/logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = 100,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    user: UserRecord = Depends(require_roles("admin", "cto", "manager")),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogOut]:
    limit = max(1, min(limit, 500))
    query = select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc()).limit(limit)
    if user.role == "manager":
        query = query.where(AuditLogRecord.actor_user_id == user.id)
    elif actor_user_id:
        query = query.where(AuditLogRecord.actor_user_id == actor_user_id)
    if action:
        query = query.where(AuditLogRecord.action == action)
    rows = (await db.scalars(query)).all()
    return [AuditLogOut(
        id=row.id,
        actor_user_id=row.actor_user_id,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        details=row.details or {},
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        created_at=row.created_at,
    ) for row in rows]


@router.get("/me", response_model=list[AuditLogOut])
async def my_audit_logs(
    limit: int = 100,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogOut]:
    limit = max(1, min(limit, 500))
    rows = (await db.scalars(
        select(AuditLogRecord)
        .where(AuditLogRecord.actor_user_id == user.id)
        .order_by(AuditLogRecord.created_at.desc())
        .limit(limit)
    )).all()
    return [AuditLogOut(
        id=row.id, actor_user_id=row.actor_user_id, action=row.action,
        resource_type=row.resource_type, resource_id=row.resource_id,
        details=row.details or {}, ip_address=row.ip_address,
        user_agent=row.user_agent, created_at=row.created_at,
    ) for row in rows]
