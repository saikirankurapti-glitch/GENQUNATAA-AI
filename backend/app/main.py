from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .coding import router as coding_router
from .config import get_settings
from .db import init_db
from .documents import router as documents_router
from .realtime import router as realtime_router
from .resume import router as resume_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="GenQuantaa AI API", version="0.7.0", description="Backend API for the GenQuantaa AI copilot.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(coding_router)
app.include_router(realtime_router)
app.include_router(documents_router)
app.include_router(resume_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "genquantaa-api", "database": "configured", "rag": "enabled", "coding": "enabled"}
