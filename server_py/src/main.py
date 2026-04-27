import logging
import os
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import auth, users, chats, ai, learning, stats, developer, system, health, feedback, matters
from .services.health_service import background_health_loop
from .utils.logger import setup_logging

# Initialise structured logging before anything else
setup_logging()

logger = logging.getLogger("app")
http_logger = logging.getLogger("http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    health_task = asyncio.create_task(background_health_loop(60))
    logger.info(f"[Main] Server running on http://{settings.host}:{settings.port}")
    yield
    # Shutdown
    health_task.cancel()


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
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    log = http_logger.warning if response.status_code >= 400 else http_logger.info
    log(f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms")
    return response


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
