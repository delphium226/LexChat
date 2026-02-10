import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import auth, users, chats, ai, learning, stats, developer
from .utils.logger import setup_logging

# Initialise structured logging before anything else
setup_logging()

logger = logging.getLogger("app")
http_logger = logging.getLogger("http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info(f"Server running on http://{settings.host}:{settings.port}")
    yield
    # Shutdown


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
    http_logger.info(
        f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms"
    )
    return response


# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(ai.router)
app.include_router(learning.router)
app.include_router(stats.router)
app.include_router(developer.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}



