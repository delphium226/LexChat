# LexChat — AI Legal Research Assistant

A locally-hosted AI assistant for UK government legal departments. Powered by a Manager-Worker agent architecture that queries the LEX API for authoritative UK legislation and case law.

## Key Features

- **Manager-Worker Agent Architecture** — the Manager handles conversation and delegates complex queries to a Worker Agent that performs multi-phase legislation research via the LEX API
- **Dual LLM Provider Support** — switch between Ollama (cloud-routed local proxy) and OpenRouter at runtime via the Admin Portal; no restart required
- **Sources Rail** — per-response citation panel listing legislation and case law with excerpts and direct legislation.gov.uk links
- **Deep Research mode** — iterative multi-Act research with parallel tool calls, section-level retrieval, and automatic summarisation of large results
- **Admin Portal** — user management, usage analytics, performance stats, per-query cost tracking, provider/model configuration, and service health monitoring
- **Self-improvement loop** — user ratings (1–5 stars) and comments are stored and injected as few-shot examples or warnings for similar future queries (RAG)
- **Dark mode** — persisted per user

## Architecture

### Frontend (`client/`)
- React 19 + Vite + Tailwind CSS
- Pre-built and served as static files by the FastAPI backend (no separate Node.js server at runtime)
- Key components: `App.jsx` (main chat UI), `SourcesRail.jsx` (citations panel), `LexMark.jsx` (wordmark/spinner), `ChatMessage.jsx` (markdown + citation rendering), `AdminPortal.jsx` (admin dashboard)

### Backend (`server_py/`)
- Python 3.11 + FastAPI + uvicorn
- PostgreSQL 15 for persistence
- Async throughout (SQLAlchemy asyncpg, httpx, asyncio)
- Agent pipeline: `provider_factory.py` → `ollama_client.py` or `openrouter_client.py` → `agent_shared.py` → `tools.py` (LEX API)

### LLM Providers
| Provider | How it works |
|---|---|
| **Ollama** | Local Ollama process acts as a proxy to cloud-hosted models (e.g. `mistral-large-3:675b-cloud`). Models are identified by `:cloud` suffix. |
| **OpenRouter** | Direct HTTPS to `openrouter.ai` via an OpenAI-compatible API. Requires outbound internet to `openrouter.ai`. |

Active provider and all per-provider settings (base URL, API key, model, temperature, concurrency) are stored in the database and configurable at runtime via Admin Portal → Developer tab.

## Deployment

The application runs natively on **Windows Server 2022** (no Docker, no WSL). The frontend is pre-built on the dev machine and committed to the repository; the target server requires only Python and PostgreSQL.

See [deployment/NATIVE_DEPLOYMENT.md](deployment/NATIVE_DEPLOYMENT.md) for full deployment instructions (air-gapped installation and the git-pull update workflow), and [deployment/README.md](deployment/README.md) for an index of every deployment script.

### Quick start

Install on the target using the offline bundle (see the air-gapped section of NATIVE_DEPLOYMENT.md), then start:
```cmd
deployment\start_native.cmd
```

Application is served over **HTTPS on port 443**.

## Local Development Setup

### Prerequisites
- Python 3.11
- PostgreSQL 15 (`lexuser` / `lexpassword` / `lexchat`)
- Ollama running locally, or an OpenRouter API key
- Node.js v22 (a portable install is fine — `deployment/install_node.ps1` sets one up; dev-machine specifics live in `CLAUDE.md`)

### Run the backend

```bash
cd server_py
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

The backend runs on `http://localhost:8000` and serves the pre-built frontend from `client/dist/`.

### Build the frontend (after source changes)

```bash
# Ensure Node.js v22 is on PATH (see CLAUDE.md for the dev-machine portable install)
cd client
npm install
npm run build
```

Force-add the built dist before committing (it is gitignored):

```bash
git add -f client/dist/
```

### Environment variables (`server_py/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://lexuser:lexpassword@localhost:5432/lexchat` |
| `JWT_SECRET` | Auth token signing key | `dev_secret_key_change_me` |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Bearer token for cloud-routed Ollama | *(blank)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(blank)* |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |

All `.env` values are startup defaults only. Provider settings can be overridden at runtime via the Admin Portal and are persisted in the database.

## Default Admin Credentials

On first run, the database is seeded with:
- **Username**: `admin`
- **Password**: `admin`

Change this immediately in production via Admin Portal → Users.

## API Documentation

When running locally, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

See [ServerAPISpec.md](ServerAPISpec.md) for the full endpoint reference.
