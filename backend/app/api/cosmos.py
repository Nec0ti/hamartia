"""Cosmos progress endpoints. Mutations update the single cosmos document.

The legacy random XP assault is retired until it can be tied to a verifiable
study outcome and a single-file reward rule.
"""

import math
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import COSMOS_SECTORS, DATA_DIR
from app.core.progression import progression_summary
from app.models.schemas import CosmosData, CosmosNode, Exam, UserStats
from app.services.storage import StorageService

router = APIRouter(prefix="/cosmos", tags=["cosmos"])


def get_storage():
    """Dependency returning the shared JSON storage service."""
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def _warp_pos(index: int, total: int, width: float = 1000.0, height: float = 700.0) -> tuple:
    """Spread nodes across the canvas using a spiral-ish layout."""
    angle = 2 * math.pi * index / max(total, 1)
    radius = 120 + index * 90
    x = width / 2 + radius * math.cos(angle)
    y = height / 2 + radius * math.sin(angle)
    return (x, y)


@router.get("", response_model=CosmosData)
async def get_cosmos(storage: StorageService = Depends(get_storage)):
    """Return the full cosmos state, projecting the user's current XP onto it."""
    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    user = storage.load_doc("user.json", UserStats) or UserStats()
    # Read-only projection so the frontend can gate assaultability by XP.
    exams = storage.load_list("exams.json", Exam)
    cosmos.user_xp = progression_summary(exams, bonus_xp=user.total_xp)["total_xp"]
    return cosmos


@router.post("/nodes", status_code=201)
async def create_node(
    payload: dict,
    storage: StorageService = Depends(get_storage),
):
    """Seed a node from a subject + mistake tag. Escalates high-error subjects
    into Boss nodes automatically. Re-creating an identical node increments its
    error count instead of adding a duplicate."""
    subject = (payload.get("subject") or "").strip()
    tag = payload.get("tag", "[Knowledge Gap]")
    if not subject:
        raise HTTPException(status_code=422, detail="subject is required")

    result = []

    def upsert(cosmos):
        existing = next((n for n in cosmos.nodes if n.subject == subject and n.tag == tag), None)
        if existing:
            existing.error_count += 1
            result.append(existing)
            return True

        error_xp = 500 if payload.get("error_count", 0) >= 5 else 100
        is_boss = error_xp == 500
        node = CosmosNode(
            id=f"node_{uuid4().hex}",
            name=subject.replace(" ", ""),
            subject=subject,
            tag=tag,
            error_count=payload.get("error_count", 0),
            error_xp=error_xp,
            reward_xp=error_xp * 2 + 50,
            sector=payload.get("sector", "sector_0"),
            is_boss=is_boss,
            x=_warp_pos(len(cosmos.nodes), len(cosmos.nodes) + 1)[0],
            y=_warp_pos(len(cosmos.nodes), len(cosmos.nodes) + 1)[1],
            radius=20 if is_boss else 12,
        )
        cosmos.nodes.append(node)
        result.append(node)
        return True

    storage.update_doc("cosmos.json", CosmosData, upsert)
    return result[0]


@router.get("/nodes", response_model=list[CosmosNode])
async def list_nodes(storage: StorageService = Depends(get_storage)):
    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    return cosmos.nodes


@router.post("/nodes/{node_id}/assault", status_code=410)
async def assault_node(node_id: str):
    """Disabled until a user-verifiable, single-file reward rule exists."""
    raise HTTPException(status_code=410, detail="Cosmos rewards are disabled pending a safe study-completion rule")


@router.post("/sectors/{sector}", status_code=201)
async def unlock_sector(
    sector: str,
    storage: StorageService = Depends(get_storage),
):
    """Reveal a new sector on the fog-of-war map."""
    if sector not in COSMOS_SECTORS:
        raise HTTPException(status_code=422, detail=f"Unknown sector. Allowed: {', '.join(COSMOS_SECTORS)}")
    result = []

    def unlock(cosmos):
        if sector in cosmos.unlocked_sectors:
            result.append(cosmos)
            return False
        cosmos.unlocked_sectors.append(sector)
        result.append(cosmos)
        return True

    storage.update_doc("cosmos.json", CosmosData, unlock)
    return result[0]
