import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user
from ..models import PeerBot

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/peers", tags=["Peers"])


class PeerCreate(BaseModel):
    peer_id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    description: str
    enabled: bool = True


class PeerUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # omit or None = keep existing
    description: Optional[str] = None
    enabled: Optional[bool] = None


def _safe(peer: PeerBot) -> dict:
    """Serialise a PeerBot without ever returning the api_key."""
    return {
        "id": peer.id,
        "peer_id": peer.peer_id,
        "name": peer.name,
        "base_url": peer.base_url,
        "has_api_key": bool(peer.api_key),
        "description": peer.description,
        "enabled": peer.enabled,
        "created_at": peer.created_at.isoformat(),
    }


@router.get("")
async def list_peers(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_admin_user),
):
    result = await db.execute(select(PeerBot).order_by(PeerBot.created_at))
    return [_safe(p) for p in result.scalars().all()]


@router.post("", status_code=201)
async def create_peer(
    body: PeerCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_admin_user),
):
    existing = await db.execute(select(PeerBot).where(PeerBot.peer_id == body.peer_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"peer_id '{body.peer_id}' already exists")
    peer = PeerBot(
        peer_id=body.peer_id,
        name=body.name,
        base_url=body.base_url,
        api_key=body.api_key or None,
        description=body.description,
        enabled=body.enabled,
    )
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    logger.info(f"[Peers] Created peer {peer.peer_id}")
    return _safe(peer)


@router.put("/{peer_id}")
async def update_peer(
    peer_id: str,
    body: PeerUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_admin_user),
):
    result = await db.execute(select(PeerBot).where(PeerBot.peer_id == peer_id))
    peer = result.scalar_one_or_none()
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    if body.name is not None:
        peer.name = body.name
    if body.base_url is not None:
        peer.base_url = body.base_url
    if body.api_key is not None:
        peer.api_key = body.api_key
    if body.description is not None:
        peer.description = body.description
    if body.enabled is not None:
        peer.enabled = body.enabled

    await db.commit()
    await db.refresh(peer)
    logger.info(f"[Peers] Updated peer {peer.peer_id}")
    return _safe(peer)


@router.delete("/{peer_id}", status_code=204)
async def delete_peer(
    peer_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_admin_user),
):
    result = await db.execute(select(PeerBot).where(PeerBot.peer_id == peer_id))
    peer = result.scalar_one_or_none()
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    await db.delete(peer)
    await db.commit()
    logger.info(f"[Peers] Deleted peer {peer_id}")
