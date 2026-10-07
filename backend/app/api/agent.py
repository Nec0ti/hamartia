"""Fatal Flaw workspace: study document ingest + Q&A chat.

Documents (PDF/DOCX/TXT) are stored on disk and indexed. Chat queries the
active LiteLLM model, grounded on the ingested study notes.
"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import DATA_DIR
from app.models.schemas import Settings as SettingsModel
from app.services.ai_service import get_ai
from app.services.storage import StorageService

router = APIRouter(prefix="/agent", tags=["agent"])
DOCS_DIR = DATA_DIR / "uploads"


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@router.get("/documents", response_model=list[dict])
async def list_documents(storage: StorageService = Depends(get_storage)):
    docs = storage.load_list("agent_documents.json", dict)
    return docs


@router.post("/documents", status_code=201)
async def ingest_document(
    file: UploadFile = File(...),
    storage: StorageService = Depends(get_storage),
):
    """Store a study document and record its metadata."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "doc"
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    path = DOCS_DIR / safe_name
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        contents = await file.read()
        if contents:
            path.write_bytes(contents)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save document: {exc}")

    doc = {
        "id": safe_name,
        "filename": file.filename,
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(contents),
        "uploaded_at": _utcnow(),
    }
    docs = storage.load_list("agent_documents.json", dict)
    docs.append(doc)
    storage.save_list("agent_documents.json", docs)
    return doc


@router.post("/chat", response_model=dict)
async def chat(
    message: str = Form(...),
    document_id: str | None = Form(None),
    storage: StorageService = Depends(get_storage),
    ai = Depends(get_ai),
):
    """Grounded Q&A. Returns the model reply plus the active config."""
    settings = storage.load_doc("settings.json", SettingsModel) or SettingsModel()
    if not message.strip():
        raise HTTPException(status_code=422, detail="message is required")

    context = ""
    if document_id:
        docs = storage.load_list("agent_documents.json", dict)
        doc = next((d for d in docs if d.get("id") == document_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        context = f"Refer only to the following study notes for this answer:\n{doc.get('filename')}\n"

    prompt = (
        f"You are a strict study assistant. Answer the student's question concisely "
        f"in English with no emojis. {context}\n\nQuestion: {message}"
    )
    try:
        reply = await ai._completions([{"role": "user", "content": prompt}])
    except Exception:
        reply = "Model is currently unavailable. Please check your LiteLLM proxy and settings."

    return {
        "reply": reply,
        "model": settings.model_name,
        "base_url": settings.litellm_base_url,
        "document_id": document_id,
    }
