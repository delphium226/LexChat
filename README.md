# AILA — AI Legal Research Assistants

A locally-hosted, multi-bot AI research platform for UK government legal departments. Users are qualified lawyers; every answer is grounded in retrieved primary sources with citations.

The product name is **AILA (AI Legal Assistant)**; the repository and its directories are still named *LexChat* for historical reasons.

> **One codebase, many bots.** There is a single backend (`server_py/`) and a single frontend (`client/`). Each bot is the *same* `uvicorn src.main:app` process differentiated by **configuration, not forked code** — its own identity, database, port, research toolset and system prompts. Bots can consult each other over **federation**.

## The bot fleet

| Bot | Identity | `RESEARCH_MODE` | Research sources | Database | Port (dev) | Status |
|---|---|---|---|---|---|---|
| **Legislation** | AILA | `legislation_only` (also `case_law_only`, `legislation_and_case_law`) | LEX API (UK legislation) + National Archives case law | `lexchat` | 8000 | Live |
| **Parliament (Holyrood)** | ParliChat | `parliamentary_records` | Scottish Parliament plenary & committee Official Report (locally crawled FTS), SP Bills, TheyWorkForYou, SP TV video | `lexchat_parliament` | 8001 | Live |
| **Westminster** | HansardChat | `westminster_records` | UK Parliament Hansard API, Members API, Bills API | `lexchat_westminster` | 8002 | Live |
| **Drafting** | — | `drafting` | Drafting guidance corpus + legislation precedent | — | — | In build on `feature/drafting-bot` ([BUILD_PLAN](docs/drafting/BUILD_PLAN.md)) |

Each bot's config lives in `bots/<id>/` — a `bot_config.json` (identity, logo, brand colour, optional peer-registry seed) and a `.env` (its own `DATABASE_URL`, `PORT`, `RESEARCH_MODE`, feature flags). Provision a new bot by copying `bots/legislation/` as a template (`shared/scripts/new_bot.ps1`); see [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) for running several bots on one machine.

## Key Features

### Shared platform — every bot gets these
- **Manager-Worker agent architecture** — the Manager handles conversation, triage and clarification; it delegates a self-contained research brief to a Worker that performs multi-phase retrieval against that bot's sources. The Worker has no chat history, so the brief must stand alone.
- **Federation** — with at least one enabled peer registered, the Manager gains a `consult_peer` tool and can ask a sibling bot (legislation ↔ parliament ↔ Westminster) via `POST /api/consult`. With zero peers the tool is simply absent and behaviour is unchanged.
- **Deep Research mode** — an opt-in plan-first mode: the bot drafts an **editable research plan**, the lawyer adds/removes/reorders/edits steps, and on approval the plan is executed step by step in code (one Worker run per step) and composed into an integrated report. The approved plan is persisted on the assistant message as an audit artefact.
- **Dual LLM provider support** — switch between Ollama (local process proxying cloud-hosted models) and OpenRouter at runtime via the Admin Portal; per-provider settings live in the database, no restart required. A separate cheaper `summarisation_model` can be configured per provider.
- **Sources rail** — per-response citation panel with excerpts and direct links to the authoritative source (legislation.gov.uk, the National Archives, parliament.scot, hansard.parliament.uk).
- **Suggested question chips** — the Manager's follow-up questions and clarification options are rendered as one-click buttons rather than prose.
- **Matters** — a workspace that groups chats, documents and notes for a piece of work.
- **Document upload** — attach PDFs/DOCX to a chat; extracted text is injected as context.
- **Research filters** — scope a query by source type, date range, record type and (Holyrood) parliamentary session; filters are enforced in code on the Worker's tools, not left to the prompt.
- **Caching stack** — provider prompt caching, a per-request tool memo, and a cross-user local cache of document summaries. All additive, fail-soft, and individually switchable.
- **Self-improvement loop** — user ratings (1–5 stars) and comments are stored and injected into later prompts as gold-standard examples or warnings for similar queries.
- **Admin Portal** — users, usage/performance/cost analytics, per-bot **Efficiency** measurement, **Cache** stats, **Data Coverage**, learning monitor, service health, user & session feedback, provider/model configuration, feature flags, federation peer registry, and a scoped **restore** from the nightly database backup.
- **Evaluation endpoint** — `/api/system/chat` mirrors `/api/chat` for the external eval harness and emits a structured `audit` trace (delegations → tools → API calls, with pre- and post-summarisation text).

### Per-bot capabilities
- **Legislation bot** — Act/SI discovery, section-level retrieval (preferred over whole-Act download), full-text fallback, and case-law retrieval from the National Archives with appellate-decision detection (it nudges the Worker toward the higher-court decision).
- **Parliament bot (Holyrood)** — Scotland-only. Full-text search and verbatim retrieval of plenary and committee transcripts from a locally crawled Postgres FTS corpus (Sessions 6–7 backfilled, incremental daily delta), MSP lookup, Holyrood bill search, and opt-in **SP TV video deep links** that turn an Official Report citation into a timestamped video link.
- **Westminster bot** — Commons, Lords, Westminster Hall and Public Bill Committee proceedings via the live Hansard API (search → verbatim contributions), plus MP/Lords member lookup and UK bill search. No local crawl: retrieval is full-text from the API.

## Documents

All project documentation lives under [`docs/`](docs/). `CLAUDE.md` (agent/contributor context) and this `README.md` remain at the repository root.

| Document | Purpose |
|---|---|
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | Plain-English overview of the assistants and their features — for non-technical readers and new users |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture reference — context, container, multi-bot, agent-pipeline, Deep Research, caching, federation, data-model, measurement and deployment views (with Mermaid diagrams) |
| [docs/SPECIFICATION.md](docs/SPECIFICATION.md) | Product specification — executive summary, Manager-Worker agent system, features, deployment, roadmap |
| [docs/DESIGN.md](docs/DESIGN.md) | Low-level design — database schema, agent flow, frontend structure |
| [docs/NETWORK_AND_DEPENDENCIES.md](docs/NETWORK_AND_DEPENDENCIES.md) | Network access & dependency reference for firewall/proxy allowlisting (installation + runtime endpoints and ports) |
| [docs/TODO.md](docs/TODO.md) | Canonical project todo list — deferred work and open chores |
| [docs/CONCURRENT_RUNS_DURABILITY.md](docs/CONCURRENT_RUNS_DURABILITY.md) | Server-side run durability — deferred design (concurrent runs are in-tab only) |
| **API** | |
| [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) | Server REST/SSE API reference — every `/api` endpoint, request/response shapes, auth |
| [docs/api/AUDIT_TRACE.md](docs/api/AUDIT_TRACE.md) | `/api/system/chat` eval endpoint and the `audit` SSE trace (harness handover spec) |
| [docs/api/LexAPISpec.md](docs/api/LexAPISpec.md) | External LEX API specification (UK legislation search/section/text endpoints) |
| **Deployment & operations** | |
| [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) | Native Windows Server 2022 deployment guide — offline install + git-pull updates |
| [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md) | Local multi-bot (federation) development setup |
| [docs/deployment/BACKUP_RUNBOOK.md](docs/deployment/BACKUP_RUNBOOK.md) | Nightly backup + scoped-restore operating procedure |
| [docs/deployment/README.md](docs/deployment/README.md) | Index of every script in the `deployment/` directory |
| [docs/BACKUP_RESTORE_PLAN.md](docs/BACKUP_RESTORE_PLAN.md) | Backup & scoped-restore design (D14) |
| **Frontend** | |
| [docs/frontend/design-system.md](docs/frontend/design-system.md) | Design-token & component reference — read before writing new UI |
| [docs/frontend/README.md](docs/frontend/README.md) | React + Vite client template notes |
| **Modes & features** | |
| [docs/deep-research/IMPLEMENTATION_PLAN.md](docs/deep-research/IMPLEMENTATION_PLAN.md) | Deep Research (plan → approve → execute) build spec |
| [docs/LOCAL_PROMPT_CACHE_PLAN.md](docs/LOCAL_PROMPT_CACHE_PLAN.md) | Cross-user local summary cache design (D7) |
| [docs/CACHE_REVIEW_FIXES_PLAN.md](docs/CACHE_REVIEW_FIXES_PLAN.md) | Cache review fixes (D8) — key-query source, cross-user safety, hygiene |
| [docs/CACHE_ADMIN_UI_PLAN.md](docs/CACHE_ADMIN_UI_PLAN.md) | Feature flags + Admin Portal Cache tab (D6) |
| [docs/LOGGING_IMPROVEMENTS_PLAN.md](docs/LOGGING_IMPROVEMENTS_PLAN.md) | Logging & log-redaction plan (PII at INFO vs DEBUG) |
| [docs/LOGGING_PR_D_PLAN.md](docs/LOGGING_PR_D_PLAN.md) | Logging PR D — remaining log work |
| [docs/drafting/BUILD_PLAN.md](docs/drafting/BUILD_PLAN.md) | Drafting bot — build spec and session ledger (in build) |
| [docs/drafting/SESSION_LOG.md](docs/drafting/SESSION_LOG.md) | Drafting bot — what each build session actually did |
| **Parliament bots** | |
| [docs/parliament/PARLIAMENTARY_DATA.md](docs/parliament/PARLIAMENTARY_DATA.md) | Scottish Parliament data model — sessions, transcript hierarchy, availability matrix |
| [docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md](docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md) | Semantic (embedding) retrieval plan — **deferred / NO-GO** |
| [docs/parliament/VIDEO_DEEPLINK_PLAN.md](docs/parliament/VIDEO_DEEPLINK_PLAN.md) | SP TV video deep-link implementation brief (plenary v1) |
| [docs/parliament/VIDEO_COMMITTEE_SPIKE.md](docs/parliament/VIDEO_COMMITTEE_SPIKE.md) | SP TV video deep-links v2 — committee spike brief |
| [docs/parliament/WESTMINSTER_VIDEO_SPIKE_PLAN.md](docs/parliament/WESTMINSTER_VIDEO_SPIKE_PLAN.md) | parliamentlive.tv deep-link feasibility spike |
| [docs/parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md](docs/parliament/WESTMINSTER_VIDEO_IMPLEMENTATION_PLAN.md) | parliamentlive.tv deep-link implementation plan (not built) |
| **Evaluation** | |
| [docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md](docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md) | Golden-question eval set for the legislation bot (DRAFT) |
| [docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md](docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md) | Golden-question eval set for the parliament bot (DRAFT) |
| **Planning & releases** | |
| [docs/planning/EFFICIENCY_PER_BOT_PLAN.md](docs/planning/EFFICIENCY_PER_BOT_PLAN.md) | Per-bot efficiency measurement plan (shipped) |
| [docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md](docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md) | Per-request efficiency profiles follow-up (scoped) |
| [docs/planning/CANADA_BOT_FEASIBILITY.md](docs/planning/CANADA_BOT_FEASIBILITY.md) | Feasibility: a Canadian jurisdiction bot |
| [docs/planning/SOUTH_AFRICA_BOT_FEASIBILITY.md](docs/planning/SOUTH_AFRICA_BOT_FEASIBILITY.md) | Feasibility: a South African jurisdiction bot |
| [docs/planning/agent_performance_analysis.md](docs/planning/agent_performance_analysis.md) | Prompt for generating comparative agent performance tables from logs |
| [docs/releases/2026-07-legislation-bot.md](docs/releases/2026-07-legislation-bot.md) | Release notes — legislation bot |
| [docs/releases/2026-07-parliament-bot.md](docs/releases/2026-07-parliament-bot.md) | Release notes — parliament bot |

## Architecture

### Frontend (`client/`)
- React 19 + Vite + Tailwind CSS
- Pre-built and served as static files by the FastAPI backend (no separate Node.js server at runtime)
- Branding is **dynamic** — the client fetches `GET /api/bot-info` and `GET /api/bot/logo` on mount, so the same bundle renders as any bot in the fleet
- Key components: `App.jsx` (chat UI + SSE consumer), `SourcesRail.jsx` (citations), `DeepResearchPlan.jsx` (editable plan card), `SuggestedQuestions.jsx` (chips), `ResearchFiltersModal.jsx`, `ChatMessage.jsx` (markdown + citations), `AdminPortal.jsx` + `pages/admin/*` (per-tab panels)

### Backend (`server_py/`)
- Python 3.11 + FastAPI + uvicorn
- PostgreSQL 15 for persistence (one database per bot)
- Async throughout (SQLAlchemy asyncpg, httpx, asyncio)
- Agent pipeline: `routers/agent_request.py` (shared request models + config) → `provider_factory.py` → `ollama_client.py` / `openrouter_client.py` → `agent_core.py` + `agent_shared.py` → `agent/tools/` package (`lex`, `caselaw`, `parliament`, `westminster`, `executor`)
- Services: `parliament_crawler.py` (Holyrood corpus), `sptv_client.py` + `caption_match.py` (video deep links), `local_prompt_cache.py`, `backup_restore.py`, `health_service.py`

### LLM Providers
| Provider | How it works |
|---|---|
| **Ollama** | Local Ollama process acts as a proxy to cloud-hosted models (e.g. `mistral-large-3:675b-cloud`). Models are identified by a `:cloud` suffix. |
| **OpenRouter** | Direct HTTPS to `openrouter.ai` via an OpenAI-compatible API. Requires outbound internet to `openrouter.ai`. |

Active provider and all per-provider settings (base URL, API key, model, summarisation model, temperature, concurrency) are stored in the database and configurable at runtime via Admin Portal → Developer tab. `.env` values are startup defaults only.

### How one codebase behaves as different bots

**Shared (common code):** the entire backend and frontend — agent pipeline (`agent/`), tools, routers, DB models, and the React app. No bot has its own copy.

**Bot-specific (config, not code):** each bot has a directory under `bots/<id>/` holding only config:
- `bot_config.json` — identity (`bot_id`, `name`, `tagline`, `logo_path`, `brand_color`) plus an optional `peer_registry_seed`. Loaded at startup via the `BOT_CONFIG_PATH` env var; drives dynamic branding through `GET /api/bot-info` and `GET /api/bot/logo`.
- `.env` — per-bot overrides: its own `DATABASE_URL` (**separate database per bot**), `PORT`, `RESEARCH_MODE`, feature flags, and any API keys.

Behaviour is then switched at runtime:
- `RESEARCH_MODE` (env) → `research_mode` selects the Worker's toolset (`tools/schemas.py::get_worker_tools`) **and** the matching Manager/Worker system prompts. Modes: `legislation_only`, `case_law_only`, `legislation_and_case_law`, `parliamentary_records`, `westminster_records`.
- The same mode also selects the bot's **efficiency profile** (`config.py::EFFICIENCY_PROFILES`) — the breach rules and dashboard bands the Admin Portal grades that bot against, since a legislation query and a transcript retrieval have different healthy shapes.
- Each bot is an **independent process** with its own DB and port, and can consult siblings via federation (`POST /api/consult`). The peer registry is per-bot (`peer_bots` table / Admin Portal → Federation tab).

For the full picture — diagrams of the request lifecycle, Deep Research, the caching stack, the parliament data pipeline and the deployment topology — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Deployment

The application runs natively on **Windows Server 2022** (no Docker, no WSL, no nginx). The frontend is pre-built on the dev machine and committed to the repository; the target server requires only Python and PostgreSQL. The target is *internet-restricted* — every external host used by the deployed bots must be whitelisted (see [docs/NETWORK_AND_DEPENDENCIES.md](docs/NETWORK_AND_DEPENDENCIES.md)).

See [docs/deployment/NATIVE_DEPLOYMENT.md](docs/deployment/NATIVE_DEPLOYMENT.md) for full deployment instructions (offline installation and the git-pull update workflow), and [docs/deployment/README.md](docs/deployment/README.md) for an index of every deployment script.

### Quick start

Install on the target using the offline bundle (see the offline-install section of NATIVE_DEPLOYMENT.md), then start:
```cmd
deployment\start_native.cmd
```

The application is served over **HTTPS on port 443**.

Backups are a scheduled nightly `pg_dump -Fc` per database (`deployment/backup_databases.ps1`, GFS retention), verified by a full `pg_restore -f NUL` read; restore is done scope-by-scope from the Admin Portal → Developer tab. See [docs/deployment/BACKUP_RUNBOOK.md](docs/deployment/BACKUP_RUNBOOK.md).

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

The backend runs on `http://localhost:8000` (HTTP locally — there are no TLS certs on a dev machine) and serves the pre-built frontend from `client/dist/`.

To run more than one bot locally (and exercise federation), use `deployment/start_federation_dev.ps1` — see [docs/deployment/LOCAL_SETUP.md](docs/deployment/LOCAL_SETUP.md).

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

### Environment variables (`server_py/.env`, or `bots/<id>/.env` per bot)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (one database per bot) | `postgresql://lexuser:lexpassword@localhost:5432/lexchat` |
| `PORT` | Listening port for this bot process | `8000` |
| `JWT_SECRET` | Auth token signing key | `dev_secret_key_change_me` |
| `BOT_ID` | Bot identity key | `legislation_bot` |
| `BOT_CONFIG_PATH` | Path to this bot's `bot_config.json` (relative paths resolve from `server_py/`) | *(blank)* |
| `RESEARCH_MODE` | Fixes this bot's research domain; overrides the per-request value | *(blank → legislation)* |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Bearer token for cloud-routed Ollama | *(blank)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(blank)* |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `LEX_API_URL` | LEX legislation API base URL | `https://lex.lab.i.ai.gov.uk/` |
| `TWFY_API_KEY` | TheyWorkForYou key — required by the parliament bot for SP plenary/written-answer search and MSP lookup | *(blank)* |
| `ENABLE_VIDEO_DEEPLINKS` | Opt-in SP TV video deep links (parliament bot) | `false` |
| `ENABLE_WESTMINSTER_VIDEO_DEEPLINKS` | Reserved for parliamentlive.tv deep links (not implemented) | `false` |
| `BACKUP_ROOT` | Where the nightly dumps are written/read — must match the scheduled task's `-BackupRoot` | `C:\LexChatBackups` |
| `PG_BIN` | PostgreSQL `bin` directory (`pg_dump`/`pg_restore`); auto-detected when blank | *(blank)* |
| `LOG_LEVEL` | Log level. **User content and PII are redacted at INFO and appear in full only at DEBUG** — do not set DEBUG on a bot handling sensitive material | `INFO` |
| `EMAIL_USER` / `EMAIL_PASS` | Gmail SMTP credentials for password-reset email (optional) | *(blank)* |

All `.env` values are startup defaults only. Provider settings and feature flags can be overridden at runtime via the Admin Portal and are persisted in the database.

> **Do not add settings to `server_py/.env.native`** — `start_native.cmd` copies it over `.env` on every start, so it is the live config on the target and carries per-machine edits. Tracked changes to it cause merge conflicts on `git pull`.

## Default Admin Credentials

On first run, the database is seeded with:
- **Username**: `admin`
- **Password**: `admin`

Change this immediately in production via Admin Portal → Users.

## API Documentation

When running locally, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

See [docs/api/ServerAPISpec.md](docs/api/ServerAPISpec.md) for the full endpoint reference, and [docs/api/AUDIT_TRACE.md](docs/api/AUDIT_TRACE.md) for the machine-to-machine `/api/system/chat` variant used by the eval harness.
