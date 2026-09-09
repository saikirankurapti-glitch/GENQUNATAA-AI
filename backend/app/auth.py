from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import os
import secrets
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import SessionLocal, get_db
from .db_models import AuthSessionRecord, UserRecord

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_SESSION_COOKIE = "genquantaa_session"
_SESSION_TTL = timedelta(days=7)
_SECRET = os.getenv("AUTH_SECRET", "development-only-change-me")
_PASSWORD_HASHER = PasswordHasher()
_SETTINGS = get_settings()


def _hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def _verify_password(password: str, stored: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError, TypeError):
        return False


def _needs_password_rehash(stored: str) -> bool:
    try:
        return _PASSWORD_HASHER.check_needs_rehash(stored)
    except (InvalidHashError, ValueError, TypeError):
        return False


def _token(user_id: UUID, expires: datetime, secret: str | None = None) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}:{int(expires.timestamp())}:{nonce}"
    signature = hmac.new((secret or _SECRET).encode(), payload.encode(), "sha256").hexdigest()
    return f"{payload}:{signature}"


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _decode(token: str) -> tuple[UUID, datetime] | None:
    try:
        user_text, expiry_text, nonce, signature = token.split(":", 3)
        payload = f"{user_text}:{expiry_text}:{nonce}"
        expected = hmac.new(_SECRET.encode(), payload.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        expiry = datetime.fromtimestamp(int(expiry_text), tz=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            return None
        return UUID(user_text), expiry
    except (ValueError, TypeError):
        return None


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _session_for_token(db: AsyncSession, token: str) -> tuple[AuthSessionRecord, UserRecord] | None:
    decoded = _decode(token)
    if not decoded:
        return None
    session = await db.scalar(select(AuthSessionRecord).where(AuthSessionRecord.token_hash == _token_hash(token)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at is not None or (_utc(session.expires_at) or now) <= now:
        return None
    user = await db.get(UserRecord, session.user_id)
    if not user or not user.is_active:
        return None
    session.last_seen_at = now
    return session, user


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str


class AuthSessionOut(BaseModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    current: bool
    device: str


def _device_from_user_agent(user_agent: str | None) -> str:
    value = (user_agent or "").lower()
    if "edg/" in value or "edge/" in value:
        browser = "Edge"
    elif "chrome/" in value and "edg/" not in value:
        browser = "Chrome"
    elif "firefox/" in value:
        browser = "Firefox"
    elif "safari/" in value and "chrome/" not in value:
        browser = "Safari"
    else:
        browser = "Browser"
    if "iphone" in value:
        platform = "iPhone"
    elif "ipad" in value:
        platform = "iPad"
    elif "android" in value:
        platform = "Android"
    elif "windows" in value:
        platform = "Windows"
    elif "mac os" in value or "macintosh" in value:
        platform = "macOS"
    elif "linux" in value:
        platform = "Linux"
    else:
        platform = "Unknown device"
    return f"{browser} · {platform}"


def _configured_role(email: str) -> str:
    normalized = email.lower().strip()
    if normalized in _SETTINGS.bootstrap_admin_email_list:
        return "admin"
    if normalized in _SETTINGS.bootstrap_cto_email_list:
        return "cto"
    return "team_member"


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserRecord:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    authenticated = await _session_for_token(db, token)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    _, user = authenticated
    await db.commit()
    return user


async def websocket_user(websocket: WebSocket) -> UserRecord | None:
    token = websocket.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    async with SessionLocal() as db:
        authenticated = await _session_for_token(db, token)
        if not authenticated:
            return None
        _, user = authenticated
        await db.commit()
        return user


def public_user(user: UserRecord) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)


def set_session(response: Response, user_id: UUID, db: AsyncSession, user_agent: str | None = None) -> None:
    expires = datetime.now(timezone.utc) + _SESSION_TTL
    token = _token(user_id, expires)
    db.add(AuthSessionRecord(user_id=user_id, token_hash=_token_hash(token), expires_at=expires, user_agent=(user_agent or "")[:1000]))
    response.set_cookie(_SESSION_COOKIE, token, max_age=int(_SESSION_TTL.total_seconds()), httponly=True, secure=os.getenv("APP_ENV", "development").lower() in {"production", "prod"}, samesite="lax", path="/")


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    email = str(payload.email).lower().strip()
    if await db.scalar(select(UserRecord).where(UserRecord.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = UserRecord(email=email, name=payload.name.strip() or email.split("@", 1)[0], password_hash=_hash_password(payload.password), role=_configured_role(email))
    db.add(user)
    await db.flush()
    set_session(response, user.id, db, request.headers.get("user-agent"))
    await db.commit()
    await db.refresh(user)
    return public_user(user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    email = str(payload.email).lower().strip()
    user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
    if not user or not user.is_active or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if _needs_password_rehash(user.password_hash):
        user.password_hash = _hash_password(payload.password)
    configured_role = _configured_role(email)
    if configured_role != "team_member" and user.role != configured_role:
        user.role = configured_role
    user.last_login_at = datetime.now(timezone.utc)
    set_session(response, user.id, db, request.headers.get("user-agent"))
    await db.commit()
    return public_user(user)


@router.get("/sessions", response_model=list[AuthSessionOut])
async def list_sessions(request: Request, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[AuthSessionOut]:
    token = request.cookies.get(_SESSION_COOKIE)
    current_hash = _token_hash(token) if token else None
    now = datetime.now(timezone.utc)
    sessions = (await db.scalars(select(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id, AuthSessionRecord.revoked_at.is_(None)).order_by(AuthSessionRecord.created_at.desc()))).all()
    active = [x for x in sessions if (_utc(x.expires_at) or now) > now]
    return [AuthSessionOut(id=x.id, created_at=_utc(x.created_at) or now, last_seen_at=_utc(x.last_seen_at), expires_at=_utc(x.expires_at) or now, current=x.token_hash == current_hash, device=_device_from_user_agent(x.user_agent)) for x in active]


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: UUID, request: Request, response: Response, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict[str, bool | str]:
    token = request.cookies.get(_SESSION_COOKIE)
    current_hash = _token_hash(token) if token else None
    session = await db.scalar(select(AuthSessionRecord).where(AuthSessionRecord.id == session_id, AuthSessionRecord.user_id == user.id, AuthSessionRecord.revoked_at.is_(None)))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    is_current = session.token_hash == current_hash
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    if is_current:
        response.delete_cookie(_SESSION_COOKIE, path="/")
    return {"status": "revoked", "current": is_current}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(request: Request, response: Response, user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict[str, int | str]:
    result = await db.execute(update(AuthSessionRecord).where(AuthSessionRecord.user_id == user.id, AuthSessionRecord.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()
    response.delete_cookie(_SESSION_COOKIE, path="/")
    return {"status": "all_sessions_revoked", "revoked_count": result.rowcount or 0}


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        await db.execute(update(AuthSessionRecord).where(AuthSessionRecord.token_hash == _token_hash(token), AuthSessionRecord.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
        await db.commit()
    response.delete_cookie(_SESSION_COOKIE, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user: UserRecord = Depends(current_user)) -> UserOut:
    return public_user(user)
