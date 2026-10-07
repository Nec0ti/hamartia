"""Cosmos gamification endpoints.

Mistake tags seed planetary nodes, which live inside `cosmos.json` alongside
the unlocked-sectors list (see the Phase 1 seed). Assaulting a node wagers XP:
success clears it and awards reward XP; failure refunds the wager and applies a
small penalty. Sectors are hidden (fog-of-war) until explicitly unlocked.
"""

import math
import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import COSMOS_SECTORS, DATA_DIR
from app.models.schemas import CosmosData, CosmosNode, UserStats
from app.services.storage import StorageService

router = APIRouter(prefix="/cosmos", tags=["cosmos"])


def get_storage():
    """Dependency returning the shared JSON storage service."""
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


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
    cosmos.user_xp = user.total_xp
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

    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    nodes = cosmos.nodes
    existing = next((n for n in nodes if n.subject == subject and n.tag == tag), None)
    if existing:
        existing.error_count += 1
        storage.save_doc("cosmos.json", cosmos)
        return existing

    error_xp = 100
    is_boss = False
    # Subjects with many repeated failures become Boss planets.
    if payload.get("error_count", 0) >= 5:
        error_xp = 500
        is_boss = True

    node = CosmosNode(
        id=f"node_{_utcnow().replace(':', '')}",
        name=f"{subject.replace(' ', '')}",
        subject=subject,
        tag=tag,
        error_count=payload.get("error_count", 0),
        error_xp=error_xp,
        reward_xp=error_xp * 2 + 50,
        sector=payload.get("sector", "sector_0"),
        is_boss=is_boss,
        x=_warp_pos(len(nodes), len(nodes) + 1)[0],
        y=_warp_pos(len(nodes), len(nodes) + 1)[1],
        radius=20 if is_boss else 12,
    )
    nodes.append(node)
    storage.save_doc("cosmos.json", cosmos)
    return node


@router.get("/nodes", response_model=list[CosmosNode])
async def list_nodes(storage: StorageService = Depends(get_storage)):
    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    return cosmos.nodes


@router.post("/nodes/{node_id}/assault", response_model=CosmosNode)
async def assault_node(
    node_id: str,
    storage: StorageService = Depends(get_storage),
):
    """Wager XP to cleanse a node. Success clears it and awards reward XP."""
    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    nodes = list(cosmos.nodes)
    target = next((n for n in nodes if n.id == node_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Node not found")

    user = storage.load_doc("user.json", UserStats) or UserStats()
    wager = target.error_xp

    # Roll success. Boss nodes are harder to cleanse.
    difficulty = 0.70 if target.is_boss else 0.75
    success = random.random() < difficulty

    if not success:
        # Failure: refund partial, apply a 10% penalty on the wager.
        user.total_xp = max(0, user.total_xp - int(wager * 0.10))
        storage.save_doc("user.json", user)
        return target

    # Success: remove node, award reward XP.
    reward = target.reward_xp
    cosmos.nodes = [n for n in nodes if n.id != node_id]
    storage.save_doc("cosmos.json", cosmos)
    user.total_xp = user.total_xp + reward
    storage.save_doc("user.json", user)
    return CosmosNode.model_validate_json(target.model_dump_json()).copy(update={"cleansed": True})


@router.post("/sectors/{sector}", status_code=201)
async def unlock_sector(
    sector: str,
    storage: StorageService = Depends(get_storage),
):
    """Reveal a new sector on the fog-of-war map."""
    if sector not in COSMOS_SECTORS:
        raise HTTPException(status_code=422, detail=f"Unknown sector. Allowed: {', '.join(COSMOS_SECTORS)}")
    cosmos = storage.load_doc("cosmos.json", CosmosData) or CosmosData()
    if sector in cosmos.unlocked_sectors:
        return cosmos
    cosmos.unlocked_sectors.append(sector)
    storage.save_doc("cosmos.json", cosmos)
    return cosmos
