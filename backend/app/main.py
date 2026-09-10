from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .adaptive_interview import router as adaptive_router
from .api import router
from .audit import router as audit_router
from .auth import router as auth_router
from .coding import router as coding_router
from .config import get_settings
from .db import init_db
from .documents import router as documents_router
from .preparation_planner import router as preparation_router
from .profile_intelligence import router as profile_intelligence_router
from .question_bank import router as question_bank_router
from .rbac import router as rbac_router
from .realtime import router as realtime_router
from .resume import router as resume_router
from .role_intelligence import router as role_intelligence_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="GenQuantaa AI API", version="0.9.6", description="Backend API for the GenQuantaa AI copilot.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(audit_router)
app.include_router(router)
app.include_router(coding_router)
app.include_router(question_bank_router)
app.include_router(realtime_router)
app.include_router(adaptive_router)
app.include_router(role_intelligence_router)
app.include_router(preparation_router)
app.include_router(documents_router)
app.include_router(resume_router)
app.include_router(profile_intelligence_router)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "genquantaa-api", "database": "configured", "rag": "enabled", "coding": "enabled", "question_bank": "enabled", "auth": "enabled", "rbac": "enabled", "audit": "enabled", "profile_intelligence": "enabled", "adaptive_interviewer": "enabled", "role_intelligence": "enabled", "preparation_planner": "enabled"}
