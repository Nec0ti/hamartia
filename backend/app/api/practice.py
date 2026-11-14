"""CRUD and summaries for completed subject/topic practice sets."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession, PracticeSessionCreate
from app.services.storage import StorageService

router = APIRouter(prefix="/practice", tags=["practice"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}") from exc


@router.get("", response_model=list[PracticeSession])
async def list_sessions(storage: StorageService = Depends(get_storage)):
    return storage.load_list("practice_sessions.json", PracticeSession)


@router.get("/insights", response_model=list[dict])
async def practice_insights(storage: StorageService = Depends(get_storage)):
    return practice_topic_summaries(storage.load_list("practice_sessions.json", PracticeSession))


@router.post("", status_code=201, response_model=PracticeSession)
async def create_session(payload: PracticeSessionCreate, storage: StorageService = Depends(get_storage)):
    session = PracticeSession(
        id=f"practice_{uuid4().hex}",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **payload.model_dump(),
    )
    storage.append_list("practice_sessions.json", session, PracticeSession)
    return session


@router.put("/{session_id}", response_model=PracticeSession)
async def update_session(
    session_id: str,
    payload: PracticeSessionCreate,
    storage: StorageService = Depends(get_storage),
):
    updated = []

    def replace(sessions):
        for index, session in enumerate(sessions):
            if session.id == session_id:
                sessions[index] = PracticeSession(
                    id=session.id, created_at=session.created_at, **payload.model_dump(),
                )
                updated.append(sessions[index])
                return True
        return False

    if not storage.update_list("practice_sessions.json", PracticeSession, replace):
        raise HTTPException(status_code=404, detail="Practice set not found")
    return updated[0]


@router.delete("/{session_id}")
async def delete_session(session_id: str, storage: StorageService = Depends(get_storage)):
    def remove(sessions):
        remaining = [item for item in sessions if item.id != session_id]
        if len(remaining) == len(sessions):
            return False
        sessions[:] = remaining
        return True

    if not storage.update_list("practice_sessions.json", PracticeSession, remove):
        raise HTTPException(status_code=404, detail="Practice set not found")
    return {"deleted": session_id}
