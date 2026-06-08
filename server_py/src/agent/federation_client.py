import logging

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PeerBot

logger = logging.getLogger("agent")


# -----------------------------------------------------------------------
# Pydantic schemas (shared with /api/consult router)
# -----------------------------------------------------------------------

class ConsultRequest(BaseModel):
    question: str
    depth: int = 0


class ConsultResponse(BaseModel):
    answer: str
    bot_id: str
    bot_name: str


# -----------------------------------------------------------------------
# Registry helpers
# -----------------------------------------------------------------------

async def load_peer_registry(db: AsyncSession) -> list[PeerBot]:
    result = await db.execute(select(PeerBot).where(PeerBot.enabled == True))
    return list(result.scalars().all())


def build_peer_descriptions(peers: list[PeerBot]) -> str:
    if not peers:
        return ""
    lines = []
    for p in peers:
        lines.append(f"- peer_id={p.peer_id!r}: {p.name} — {p.description}")
    return "\n".join(lines)


# -----------------------------------------------------------------------
# Remote consult call
# -----------------------------------------------------------------------

async def consult_peer(peer: PeerBot, question: str, depth: int) -> str:
    """POST /api/consult on the peer bot and return its answer string."""
    headers = {"Content-Type": "application/json"}
    if peer.api_key:
        headers["Authorization"] = f"Bearer {peer.api_key}"

    payload = ConsultRequest(question=question, depth=depth).model_dump()

    try:
        async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
            resp = await client.post(
                f"{peer.base_url.rstrip('/')}/api/consult",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("answer", "")
    except httpx.HTTPStatusError as e:
        logger.error(f"[Federation] Peer {peer.peer_id} returned HTTP {e.response.status_code}")
        raise
    except Exception as e:
        logger.error(f"[Federation] Failed to consult peer {peer.peer_id}: {e}")
        raise
