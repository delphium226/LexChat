import logging

from fastapi import APIRouter, Depends, HTTPException

from ..agent.federation_client import ConsultRequest, ConsultResponse
from ..bot_state import get_bot_identity
from ..agent.provider_factory import (
    get_active_provider,
    get_process_user_request,
    get_provider_config,
    set_request_provider_config,
)
from ..config import settings
from ..database import async_session_maker
from ..dependencies import get_current_user

logger = logging.getLogger("app")

router = APIRouter(tags=["Federation"])


@router.post("/api/consult", response_model=ConsultResponse)
async def consult(body: ConsultRequest, user: dict = Depends(get_current_user)):
    """Receive a consultation request from a peer bot and return a full answer.

    depth >= 2 is rejected to prevent A→B→C cascade loops.
    """
    if body.depth >= 2:
        raise HTTPException(status_code=422, detail="Depth limit exceeded — no cascading federation")

    bot_identity = get_bot_identity()

    async with async_session_maker() as db:
        active_provider = await get_active_provider(db)
        provider_config = await get_provider_config(db, active_provider)
        process_user_request = await get_process_user_request(db)

    set_request_provider_config({
        **provider_config,
        "_provider": active_provider,
        # Respect this bot's own research mode (e.g. the parliament bot sets
        # RESEARCH_MODE=parliamentary_records) — a consulted peer must answer
        # with its specialised toolset, not the legislation default.
        "_research_mode": settings.research_mode or "legislation_only",
    })

    resolved_model = provider_config.get("model") or settings.bot_id

    messages = [{"role": "user", "content": body.question}]

    async with async_session_maker() as db_session:
        result = await process_user_request(
            messages=messages,
            model=resolved_model,
            on_chunk=None,
            cancel_event=None,
            num_ctx=None,
            db_session=db_session,
            # Carry the consultation depth into the manager so any onward
            # consult_peer call sends depth+1 and the depth>=2 check actually
            # stops A->B->C cascades (previously reset to 0 here).
            depth=body.depth,
        )

    answer = result.get("content", "")
    bot_id = bot_identity.get("bot_id", settings.bot_id)
    bot_name = bot_identity.get("name", "AILA")

    logger.info(f"[Federation] Answered consult from {user['username']} (depth={body.depth})")

    return ConsultResponse(answer=answer, bot_id=bot_id, bot_name=bot_name)
