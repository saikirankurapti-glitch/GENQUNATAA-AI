from fastapi import FastAPI

app = FastAPI(
    title="GenQuantaa AI API",
    version="0.1.0",
    description="Backend API for the GenQuantaa AI copilot.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "genquantaa-api"}
