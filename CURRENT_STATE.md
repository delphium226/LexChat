# LexChat — Current State

## Last Updated: 2026-04-26

## Active Configuration

- **Deployment**: Native Windows (no Docker, no WSL) — primary target is Windows Server 2022
- **Frontend**: React 19 + Vite, pre-built to `client/dist/`, served as static files by FastAPI
- **Backend**: Python 3.11 + FastAPI + uvicorn at `server_py/`
- **Database**: PostgreSQL 15 — credentials `lexuser`/`lexpassword`/`lexchat`
- **LLM**: Ollama (cloud-routed proxy) **or** OpenRouter — switchable at runtime, no restart needed
- **Active branch**: `feature/reskin` (UI reskin + provider system); main branch is `main`

## Provider System

Two LLM providers supported, configured per-provider in the `AppSetting` DB table:

| Key | Description |
|---|---|
| `active_provider` | `"ollama"` or `"openrouter"` |
| `provider.ollama` | JSON blob: base_url, api_key, model, summarisation_model, temperature, max_concurrent_requests, max_summarise_concurrency |
| `provider.openrouter` | Same shape |

A `ContextVar` in `provider_factory.py` carries the resolved config through the entire async call chain without changing function signatures. Per-provider `RequestQueue` and summarisation `asyncio.Semaphore` are cached by `(provider, concurrency)` and recreated automatically if settings change.

## All Implemented Endpoints

### Auth (`/api/auth`) — 7 endpoints
| Method | Path | Auth |
|---|---|---|
| POST | `/login` | Public |
| POST | `/logout` | Public |
| GET | `/me` | Required |
| POST | `/reset-password-request` | Public |
| POST | `/change-password` | Required |
| PUT | `/preferences` | Required |

### Chats (`/api/chats`) — 7 endpoints
| Method | Path |
|---|---|
| GET | `/api/chats` |
| POST | `/api/chats` |
| PUT | `/api/chats/{id}` |
| DELETE | `/api/chats/{id}` |
| GET | `/api/chats/{id}/messages` |
| POST | `/api/chats/{id}/messages` |
| PUT | `/api/chats/messages/{id}/rating` |

### AI (`/api`) — 2 endpoints
| Method | Path | Notes |
|---|---|---|
| GET | `/api/models` | Returns active provider's model list with `active` flag |
| POST | `/api/chat` | SSE streaming; supports `deep_research` and `research_mode` |

### Users (`/api/users`) — 4 endpoints (admin only)
CRUD: list, create, update, delete

### Learning (`/api/learning`) — 3 endpoints (admin only)
Feedback list, stats, test retrieval

### Stats (`/api/stats`) — 3 endpoints (admin only)
| Method | Path |
|---|---|
| GET | `/api/stats/usage` |
| GET | `/api/stats/performance` |
| GET | `/api/stats/cost` |

### Developer (`/api/developer`) — 7 endpoints (admin only)
| Method | Path |
|---|---|
| GET | `/api/developer/provider-config` |
| POST | `/api/developer/provider-config` |
| POST | `/api/developer/active-provider` |
| GET | `/api/developer/openrouter-models` |
| POST | `/api/developer/seed` |
| POST | `/api/developer/reset` |
| POST | `/api/developer/clear-usage` |
| POST | `/api/developer/clear-performance` |

### Health (`/api/health`) — 3 endpoints
| Method | Path |
|---|---|
| GET | `/api/health/status` |
| GET | `/api/health/history` |
| POST | `/api/health/trigger` |

### Feedback (`/api/feedback`) — 2 endpoints
| Method | Path |
|---|---|
| POST | `/api/feedback` |
| GET | `/api/feedback` (admin only) |

### System (`/api/system`) — 1 endpoint
Machine-to-machine chat with full tool call SSE events

### Health check — 1 endpoint
`GET /api/health` — public

**Total: ~42 endpoints**

## Database Models

| Model | Table | Key fields |
|---|---|---|
| `User` | `users` | id, username, password_hash, email, role, dark_mode, research_mode |
| `Chat` | `chats` | id, user_id, title, model, provider, created_at |
| `Message` | `messages` | id, chat_id, role, content, model, provider, rating, feedback_comment, cost_usd |
| `AppSetting` | `app_settings` | key (PK), value (JSON text) |
| `RequestTiming` | `request_timings` | per-request performance breakdown |
| `ProductFeedback` | `product_feedback` | user product feedback messages |
| `ServiceHealthStatus` | `service_health_logs` | per-service health check results |

## Key Source Files

| File | Purpose |
|---|---|
| `client/src/App.jsx` | Main chat UI — sidebar, composer, sources rail wiring, model fetch |
| `client/src/components/SourcesRail.jsx` | Citation panel — rendered alongside chat, populated from agent response |
| `client/src/components/LexMark.jsx` | LexChat logo/wordmark component |
| `client/src/components/ChatMessage.jsx` | Message rendering — markdown, citation links, message toolbar |
| `client/src/pages/AdminPortal.jsx` | Full admin dashboard including Developer/Cost/Health tabs |
| `client/src/index.css` | CSS custom properties design system (CSS vars for colours, fonts, spacing) |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar config, queue/semaphore caches |
| `server_py/src/agent/agent_shared.py` | Shared worker tool execution pipeline (used by both provider clients) |
| `server_py/src/agent/ollama_client.py` | Ollama agent: chat_loop, worker, manager, summarisation |
| `server_py/src/agent/openrouter_client.py` | OpenRouter agent: OpenAI-compatible implementation |
| `server_py/src/agent/tools.py` | LEX API tool schemas, `_slim_search_results`, `execute_worker_tool` |
| `server_py/src/agent/summarisation.py` | Shared summarisation pipeline |
| `server_py/src/config.py` | MODEL_LIST, OPENROUTER_MODEL_LIST, system prompts, app settings |
| `server_py/src/models.py` | SQLAlchemy ORM models |
| `server_py/src/database.py` | `init_db()` — schema creation, migrations, admin seeding |
| `server_py/src/main.py` | FastAPI app, lifespan, routers, static file serving |

## Admin Portal Tabs

| Tab | Content |
|---|---|
| Users | CRUD user management |
| Usage | Query volume, token consumption, active users — time-filtered graphs |
| Performance | Request timing breakdown (queue wait, LLM, LEX API) |
| Cost | Per-query USD cost from OpenRouter usage; running totals |
| Learning | User feedback table + RAG retrieval playground |
| Health | Live service health (Ollama, LEX API, PostgreSQL) with history graphs |
| Developer | Provider config, synthetic data seed, danger zone reset |

## Deployment Workflow

The only way to deploy to the target server is via GitHub:

1. Make changes to `client/src/`
2. Build: `npm run build` (in `client/`)
3. Commit including `client/dist/` (force-add — gitignored): `git add -f client/dist/`
4. Push to `origin feature/reskin` (or `main` for production)
5. On target: `git pull`, then restart with `stop_native.cmd` / `start_native.cmd`
