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

## Documents

All project documentation lives under [`docs/`](docs/). `CLAUDE.md` (agent/contributor context) and this `README.md` remain at the repository root.

| Document | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture reference — context, container, agent-pipeline, federation, data-model, and deployment views (with Mermaid diagrams) |
| [docs/SPECIFICATION.md](docs/SPECIFICATION.md) | Product specification — executive summary, Manager-Worker agent system, features, deployment, roadmap |
| [docs/DESIGN.md](docs/DESIGN.md) | Low-level design — database schema, agent flow, frontend structure |
| [docs/NETWORK_AND_DEPENDENCIES.md](docs/NETWORK_AND_DEPENDENCIES.md) | Network access & dependency reference for firewall/proxy allowlisting (installation + runtime endpoints and ports) |
| [docs/TODO.md](docs/TODO.md) | Canonical project todo list — deferred work and open chores |
| **API** | |
| [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) | Server REST/SSE API reference — every `/api` endpoint, request/response shapes, auth |
| [docs/api/LexAPISpec.md](docs/api/LexAPISpec.md) | External LEX API specification (UK legislation search/section/text endpoints) |
| **Deployment** | |
| [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) | Native Windows Server 2022 deployment guide — air-gapped install + git-pull updates |
| [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) | Local multi-bot (federation) development setup |
| [docs/deployment/README.md](docs/deployment/README.md) | Index of every script in the `deployment/` directory |
| **Frontend** | |
| [docs/frontend/design-system.md](docs/frontend/design-system.md) | Design-token & component reference — read before writing new UI |
| [docs/frontend/README.md](docs/frontend/README.md) | React + Vite client template notes |
| **Parliament bot** | |
| [docs/parliament/PARLIAMENTARY_DATA.md](docs/parliament/PARLIAMENTARY_DATA.md) | Scottish Parliament data model — sessions, transcript hierarchy, availability matrix |
| [docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md](docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md) | Semantic (embedding) retrieval plan — **deferred / NO-GO** |
| [docs/parliament/VIDEO_DEEPLINK_PLAN.md](docs/parliament/VIDEO_DEEPLINK_PLAN.md) | SP TV video deep-link implementation brief (plenary v1) |
| [docs/parliament/VIDEO_COMMITTEE_SPIKE.md](docs/parliament/VIDEO_COMMITTEE_SPIKE.md) | SP TV video deep-links v2 — committee spike brief |
| **Evaluation** | |
| [docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md](docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md) | Golden-question eval set for the legislation bot (DRAFT) |
| [docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md](docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md) | Golden-question eval set for the parliament bot (DRAFT) |
| **Planning** | |
| [docs/planning/EFFICIENCY_PER_BOT_PLAN.md](docs/planning/EFFICIENCY_PER_BOT_PLAN.md) | Per-bot efficiency measurement plan (shipped) |
| [docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md](docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md) | Per-request efficiency profiles follow-up (scoped) |
| [docs/planning/agent_performance_analysis.md](docs/planning/agent_performance_analysis.md) | Prompt for generating comparative agent performance tables from logs |

## Architecture

### Frontend (`client/`)
- React 19 + Vite + Tailwind CSS
- Pre-built and served as static files by the FastAPI backend (no separate Node.js server at runtime)
- Key components: `App.jsx` (main chat UI), `SourcesRail.jsx` (citations panel), `LexMark.jsx` (wordmark/spinner), `ChatMessage.jsx` (markdown + citation rendering), `AdminPortal.jsx` (admin dashboard)

### Backend (`server_py/`)
- Python 3.11 + FastAPI + uvicorn
- PostgreSQL 15 for persistence
- Async throughout (SQLAlchemy asyncpg, httpx, asyncio)
- Agent pipeline: `provider_factory.py` → `ollama_client.py` or `openrouter_client.py` → `agent_shared.py` → `agent/tools/` package (LEX API, case law, Scottish Parliament)

### LLM Providers
| Provider | How it works |
|---|---|
| **Ollama** | Local Ollama process acts as a proxy to cloud-hosted models (e.g. `mistral-large-3:675b-cloud`). Models are identified by `:cloud` suffix. |
| **OpenRouter** | Direct HTTPS to `openrouter.ai` via an OpenAI-compatible API. Requires outbound internet to `openrouter.ai`. |

Active provider and all per-provider settings (base URL, API key, model, temperature, concurrency) are stored in the database and configurable at runtime via Admin Portal → Developer tab.

### Architecture: one codebase, many bots

There is **one** backend codebase (`server_py/`). Every bot — the legislation assistant, the Scottish Parliament bot, and any future bot — runs the *same* `uvicorn src.main:app`; they are differentiated by **configuration, not forked code**.

**Shared (common code):** the entire backend and frontend — agent pipeline (`agent/`), tools, routers, DB models, and the React app. No bot has its own copy.

**Bot-specific (config, not code):** each bot has a directory under `bots/<id>/` holding only config:
- `bot_config.json` — identity (`bot_id`, `name`, `tagline`, `logo_path`) plus an optional `peer_registry_seed`. Loaded at startup via the `BOT_CONFIG_PATH` env var; drives dynamic branding through `GET /api/bot-info` and `GET /api/bot/logo`.
- `.env` — per-bot overrides: its own `DATABASE_URL` (**separate database per bot**), `PORT`, `RESEARCH_MODE`, and any API keys.

**How one codebase behaves as different bots** — behaviour is switched at runtime by config:
- `RESEARCH_MODE` (env) → `research_mode` selects the Worker's toolset (`tools/schemas.py::get_worker_tools`) and system prompt: `legislation_only`, `case_law_only`, `legislation_and_case_law`, or `parliamentary_records`.
- Each bot is an **independent process** with its own DB and port, and can consult siblings via **federation** (`POST /api/consult`; the Manager gains a `consult_peer` tool when peers are registered). The peer registry is per-bot (`peer_bots` table / Admin Portal → Federation tab).

| Bot | `research_mode` | Database | Port (dev) | Worker toolset |
|---|---|---|---|---|
| Legislation (default) | `legislation_only` (+ case law) | `lexchat` | 8000 | LEX API legislation & National Archives case law |
| Parliament | `parliamentary_records` | `lexchat_parliament` | 8001 | Scottish Parliament (plenary, committee, bills, MSPs) |

Provision a new bot by copying `bots/legislation/` as a template (`shared/scripts/new_bot.ps1`). See [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) for running several bots locally.

## Deployment

The application runs natively on **Windows Server 2022** (no Docker, no WSL). The frontend is pre-built on the dev machine and committed to the repository; the target server requires only Python and PostgreSQL.

See [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) for full deployment instructions (air-gapped installation and the git-pull update workflow), and [docs/deployment/README.md](docs/deployment/README.md) for an index of every deployment script.

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

See [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) for the full endpoint reference.
