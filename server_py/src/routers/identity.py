import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from ..config import settings

router = APIRouter(tags=["Identity"])


@router.get("/api/bot-info")
async def bot_info():
    from ..main import bot_identity
    result = {
        "bot_id": bot_identity.get("bot_id", settings.bot_id),
        "name": bot_identity.get("name", "AILA"),
        "tagline": bot_identity.get("tagline", "AI Legal Assistant"),
    }
    if brand_color := bot_identity.get("brand_color"):
        result["brand_color"] = brand_color
    if logo_emoji := bot_identity.get("logo_emoji"):
        result["logo_emoji"] = logo_emoji
    return result


@router.get("/api/bot/logo")
async def bot_logo():
    from ..main import bot_identity
    logo_path = bot_identity.get("logo_path", "")
    if not logo_path:
        return JSONResponse({"detail": "No logo configured"}, status_code=404)
    abs_path = os.path.abspath(logo_path)
    if not os.path.isfile(abs_path):
        return JSONResponse({"detail": "Logo file not found"}, status_code=404)
    return FileResponse(abs_path)
