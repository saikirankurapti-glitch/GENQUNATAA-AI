from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal, get_db
from .db_models import UserRecord

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_SESSION_COOKIE = "genquantaa_session"
_SESSION_TTL = timedelta(days=7)
_SECRET = os.getenv("AUTH_SECRET", "development-only-change-me")


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = sha256(salt + password.encode()).hexdigest()
    return f"{salt.hex()}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected = stored.split("$", 1)
        actual = sha256(bytes.fromhex(salt_hex) + password.encode()).hexdigest()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token(user_id: UUID, expires: datetime) -> str:
    payload = f"{user_id}:{int(expires.timestamp())}"
    signature = hmac.new(_SECRET.encode(), payload.encode(), "sha256").hexdigest()
    return f"{payload}:{signature}"


def _decode(token: str) -> tuple[UUID, datetime] | None:
    try:
        user_text, expiry_text, signature = token.split(":", 2)
        payload = f"{user_text}:{expiry_text}"
        expected = hmac.new(_SECRET.encode(), payload.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        expiry = datetime.fromtimestamp(int(expiry_text), tz=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            return None
        return UUID(user_text), expiry
    except (ValueError, TypeError):
        return None


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


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserRecord:
    token = request.cookies.get(_SESSION_COOKIE)
    decoded = _decode(token) if token else None
    if not decoded:
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id, _ = decoded
    user = await db.get(UserRecord, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


async def websocket_user(websocket: WebSocket) -> UserRecord | None:
    token = websocket.cookies.get(_SESSION_COOKIE)
    decoded = _decode(token) if token else None
    if not decoded:
        return None
    user_id, _ = decoded
    async with SessionLocal() as db:
        user = await db.get(UserRecord, user_id)
        if not user or not user.is_active:
            return None
        return user


def public_user(user: UserRecord) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)


def set_session(response: Response, user_id: UUID) -> None:
    expires = datetime.now(timezone.utc) + _SESSION_TTL
    response.set_cookie(
        _SESSION_COOKIE,
        _token(user_id, expires),
        max_age=int(_SESSION_TTL.total_seconds()),
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    email = str(payload.email).lower().strip()
    if await db.scalar(select(UserRecord).where(UserRecord.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = UserRecord(email=email, name=payload.name.strip() or email.split("@", 1)[0], password_hash=_hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    set_session(response, user.id)
    return public_user(user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> UserOut:
    email = str(payload.email).lower().strip()
    user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
    if not user or not user.is_active or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    set_session(response, user.id)
    return public_user(user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(_SESSION_COOKIE, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user: UserRecord = Depends(current_user)) -> UserOut:
    return public_user(user)
