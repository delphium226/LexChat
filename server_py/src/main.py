import json
import logging
import os
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .bot_state import set_bot_identity
from .config import settings
from .database import init_db, async_session_maker
from .routers import auth, users, chats, ai, learning, stats, developer, system, health, feedback, matters, documents
from .routers import identity, federation, peers, research
from .services.health_service import background_health_loop
from .services.parliament_crawler import (
    background_crawl_loop,
    background_plenary_crawl_loop,
    backfill_captions,
    backfill_committee_captions,
    backfill_plenary,
    backfill_sessions,
)
from .utils.logger import setup_logging

# Initialise structured logging before anything else
setup_logging(bot_id=settings.bot_id)

logger = logging.getLogger("app")
http_logger = logging.getLogger("http")


async def _load_bot_config() -> None:
    """Load bot_config.json and seed peer_bots table (insert-or-ignore by peer_id)."""
    path = settings.bot_config_path
    if not path:
        return
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        logger.warning(f"[BotConfig] bot_config_path set but file not found: {abs_path}")
        return
    try:
        with open(abs_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        logger.error(f"[BotConfig] Failed to parse {abs_path}: {e}")
        return

    bot_identity = cfg.get("bot_identity", {})
    set_bot_identity(bot_identity)
    logger.info(f"[BotConfig] Loaded identity: {bot_identity.get('name', '?')} ({bot_identity.get('bot_id', '?')})")

    seeds = cfg.get("peer_registry_seed", [])
    if not seeds:
        return

    from sqlalchemy import text as sa_text
    async with async_session_maker() as session:
        for peer in seeds:
            pid = peer.get("peer_id", "")
            if not pid:
                continue
            await session.execute(
                sa_text(
                    "INSERT INTO peer_bots (peer_id, name, base_url, api_key, description, enabled) "
                    "VALUES (:peer_id, :name, :base_url, :api_key, :description, TRUE) "
                    "ON CONFLICT (peer_id) DO NOTHING"
                ),
                {
                    "peer_id": pid,
                    "name": peer.get("name", pid),
                    "base_url": peer.get("base_url", ""),
                    "api_key": peer.get("api_key") or None,
                    "description": peer.get("description", ""),
                },
            )
        await session.commit()
    logger.info(f"[BotConfig] Seeded {len(seeds)} peer(s) (insert-or-ignore).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.jwt_secret in ("dev_secret_key_change_me", "production_secret_key_change_me"):
        logger.warning(
            "[Security] JWT_SECRET is set to a well-known default value. "
            "Set a unique JWT_SECRET in server_py/.env (or .env.native) before "
            "exposing this server to users."
        )
    await init_db()
    await _load_bot_config()
    health_task = asyncio.create_task(background_health_loop(300))

    # SP committee crawler: one-shot backfill on first run, then daily rolling crawl.
    # Only starts when the parliament bot research mode is active so the legislation
    # bot doesn't crawl unnecessarily.
    from .config import settings as _s
    crawl_tasks = []
    if _s.research_mode == "parliamentary_records":
        # Committee then plenary backfill, sequentially, so the two one-shot
        # backfills don't hammer the SP origin concurrently. The daily plenary
        # loop is self-staggered (see background_plenary_crawl_loop).
        async def _backfill_all():
            await backfill_sessions()
            await backfill_plenary()
            # Video captions last — staggered after plenary so the two one-shot
            # backfills don't hit the SP origin concurrently. No-op when the
            # ENABLE_VIDEO_DEEPLINKS flag is off (checked inside the backfills).
            await backfill_captions()
            # Committee captions after plenary captions (same origin) — resolves each
            # committee event by name via the SP TV archive.
            await backfill_committee_captions()

        crawl_tasks = [
            asyncio.create_task(_backfill_all()),
            asyncio.create_task(background_crawl_loop(86400)),
            asyncio.create_task(background_plenary_crawl_loop(86400)),
        ]

    logger.info(f"[Main] Server running on http://{settings.host}:{settings.port}")
    yield
    # Shutdown
    health_task.cancel()
    for t in crawl_tasks:
        t.cancel()


app = FastAPI(
    title="LexChat API",
    description="FastAPI Backend for LexChat",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Configuration
origins = ["*"]  # Restricted in Phase 9 for production

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTTP request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    status = 500  # default if call_next raises before returning a response
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # try/finally so an unhandled exception in call_next is still logged
        # (and timed) rather than skipping the access line entirely.
        duration_ms = int((time.time() - start) * 1000)
        if status >= 500:
            log = http_logger.error
        elif status >= 400:
            log = http_logger.warning
        else:
            log = http_logger.info
        log(f"{request.method} {request.url.path} {status} {duration_ms}ms")


# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(ai.router)
app.include_router(learning.router)
app.include_router(stats.router)
app.include_router(developer.router)
app.include_router(system.router)
app.include_router(health.router)
app.include_router(feedback.router)
app.include_router(matters.router)
app.include_router(documents.router)
app.include_router(identity.router)
app.include_router(federation.router)
app.include_router(peers.router)
app.include_router(research.router)


import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# ... earlier imports remain ...

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

# Serve Frontend static files if the directory exists
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "client", "dist"))

if os.path.isdir(frontend_dist):
    # Serve assets like JS/CSS directly
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Catch-all route to serve React index.html for unknown paths (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Prevent catching /api routes
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
            
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Fall back to index.html for SPA
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    logger.warning(f"[Main] Frontend static directory not found at {frontend_dist}. UI will not be available.")
