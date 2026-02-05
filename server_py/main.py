import logging
import os
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings

from database import db
from routes import auth, chats, agent, users, developer, stats, learning

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lexchat")



app = FastAPI(title="LexChat API", version="1.0.0")

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(agent.router)
app.include_router(users.router)
app.include_router(developer.router)
app.include_router(stats.router)
app.include_router(learning.router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for now, matching Node
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request duration (simple version)
    response = await call_next(request)
    return response

# Routes Placeholders
@app.get("/api/models")
async def list_models():
    # Matching Node.js config
    return [
        {"name": "deepseek-v3.2:cloud"},
        {"name": "mistral-large-3:675b-cloud"}, 
        {"name": "kimi-k2-thinking:cloud"}
    ]

# Serve Static Files (SPA Support)
# We will point to the client build directory
# Serve Static Files (SPA Support)
# We will point to the client build directory
# Search paths: 
# 1. ../client/dist (Local dev relative to server_py)
# 2. /app/client/dist (Docker standard convention)
possible_paths = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../client/dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "client/dist")),
    "/app/client/dist"
]

CLIENT_BUILD_DIR = None
for path in possible_paths:
    if os.path.exists(path):
        CLIENT_BUILD_DIR = path
        break

if CLIENT_BUILD_DIR:
    logger.info(f"Serving static files from: {CLIENT_BUILD_DIR}")
    app.mount("/", StaticFiles(directory=CLIENT_BUILD_DIR, html=True), name="static")
else:
    logger.warning("Client build directory not found. Static files will not be served.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
