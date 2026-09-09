from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_ALLOWED = {"application/pdf", "text/plain", "text/markdown"}

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, str | int]:
    if file.content_type not in _ALLOWED:
        return {"status":"rejected", "reason":"Supported types: PDF, TXT, Markdown"}
    data = await file.read()
    return {"status":"accepted", "filename":file.filename or "document", "bytes":len(data)}
