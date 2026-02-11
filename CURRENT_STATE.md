# LexChat - Current State

## Last Updated: 2026-02-10

## Active Configuration
- **Backend**: FastAPI (Python) at `server_py/`
- **Frontend**: React (Vite) at `client/` served via Nginx
- **Database**: PostgreSQL 15 via Docker
- **AI**: Ollama with Manager/Worker agent architecture
- **Deployment**: Docker Compose (Split containers: `frontend` + `backend`)

## Migration Status: COMPLETE (Phases 1-10)

All 10 phases of the Express → FastAPI migration have been implemented:

1. **Database Foundation** — SQLAlchemy ORM models (`models.py`), schema init on startup (`database.py`), admin user seeding
2. **Real DB in routes** — Auth, chats, users all use async SQLAlchemy sessions
3. **Missing auth endpoints** — Password reset, change password, preferences
4. **Missing chat endpoints** — Update title, delete chat, rate message
5. **Agent system** — Full Manager/Worker with tool calling, LEX API client, deep research, web search, RAG learning
6. **Admin endpoints** — Learning feedback/stats, usage stats, developer seed/reset
7. **Infrastructure** — Request queue, structured logging (app/agent/http), email service
8. **Tests** — Async test suite with proper fixtures (conftest, auth, users, chats, agent)
9. **Config & security** — All settings in Pydantic, system prompts, model list
10. **Docker** — Dockerfile reviewed, logs dir created, docker-compose verified

## All 25 Endpoints Implemented

| Group | Count | Endpoints |
|---|---|---|
| Auth | 6 | login, logout, /me, reset-password-request, change-password, preferences |
| Users | 4 | list, create, update, delete |
| Chats | 7 | list, create, update, delete, messages (list/add), rate message |
| AI | 2 | models, chat (SSE streaming) |
| Learning | 3 | feedback, stats, test retrieval |
| Stats | 1 | usage |
| Developer | 2 | seed, reset |
| Health | 1 | /health |

## Key Files Created/Modified

### New files:
- `nginx.conf` — Nginx configuration for frontend/proxy
- `client/Dockerfile` — Frontend Dockerfile
- `server_py/src/models.py` — User, Chat, Message ORM models
- `server_py/src/agent/tools.py` — LEX API tool definitions + execution
- `server_py/src/agent/deep_research.py` — Deep research agent
- `server_py/src/agent/web_search.py` — Google web search
- `server_py/src/agent/learning.py` — RAG system (keyword extraction, feedback retrieval)
- `server_py/src/routers/learning.py` — Admin learning/feedback routes
- `server_py/src/routers/stats.py` — Admin usage statistics
- `server_py/src/routers/developer.py` — Seed/reset endpoints
- `server_py/src/utils/queue.py` — Async request queue
- `server_py/src/utils/logger.py` — Structured logging setup
- `server_py/src/services/email_service.py` — Gmail SMTP email service

### Modified files:
- `server_py/src/config.py` — Full settings + system prompts + model list
- `server_py/src/database.py` — init_db() with schema creation + admin seeding
- `server_py/src/main.py` — Lifespan, logging middleware, all routers registered
- `server_py/src/dependencies.py` — No changes needed (already correct)
- `server_py/src/routers/auth.py` — Real DB auth, all 6 endpoints
- `server_py/src/routers/users.py` — Real DB CRUD, all 4 endpoints
- `server_py/src/routers/chats.py` — Real DB CRUD, all 7 endpoints
- `server_py/src/routers/ai.py` — Full agent system with SSE streaming
- `server_py/src/agent/ollama_client.py` — Chat loop, worker, manager, learning injection
- `server_py/requirements.txt` — Added faker, pytest-asyncio, sqlalchemy[asyncio], python-dotenv
- `server_py/Dockerfile` — Added logs directory creation

## How to Run
```bash
# Docker (recommended)
docker-compose up --build

# Local dev
cd server_py
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```
