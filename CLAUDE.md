# LexChat — Claude Code Context

## What This Project Is
LexChat is an AI-powered legal research assistant for a **UK government legal department**. Users are qualified lawyers querying UK legislation and case law. The system uses a Manager-Worker agent architecture — the Manager handles conversation, the Worker performs deep research via the LEX API.

## Tech Stack
- **Frontend**: React 19 + Vite + Tailwind CSS (`client/`)
- **Backend**: Python 3.11 + FastAPI + uvicorn (`server_py/`)
- **Database**: PostgreSQL 15 (`lexuser`/`lexpassword`/`lexchat`)
- **AI Engine**: Ollama (proxies to Ollama-hosted cloud models) **or** OpenRouter — switchable at runtime via Admin Portal
- **Model**: Configured per-provider in Admin Portal → Developer tab; defaults to `mistral-large-3:675b-cloud` (Ollama)

## Deployment Target
- **OS**: Windows Server 2022, **internet-restricted** (outbound access limited to whitelisted addresses only — not fully air-gapped)
- **No Docker, no WSL** — everything runs natively
- **HTTPS on port 443** using organisational certificates at `deployment/certs/lexchat.crt` and `deployment/certs/lexchat.key`
- PostgreSQL runs as a Windows service; Ollama and uvicorn are started by the launch scripts
- OpenRouter requires outbound internet to `openrouter.ai` — works on the target if that address is whitelisted

## Active Branch
All deployment work happens on **`experiment/native-deployment`**. Main branch is `main`.

## Key Architectural Decisions

### LLM Provider System
- Two providers supported: **Ollama** (Ollama-hosted cloud models, accessed via the local Ollama process as a proxy) and **OpenRouter** (internet, OpenAI-compatible API)
- Active provider and all per-provider settings are stored in the `AppSetting` DB table — no restart required to switch
- Per-provider settings: `base_url`, `api_key`, `model`, `summarisation_model`, `temperature`, `max_concurrent_requests`, `max_summarise_concurrency`
- Settings stored as JSON blobs: `AppSetting(key="provider.ollama")` and `AppSetting(key="provider.openrouter")`
- `.env` values are startup defaults/fallbacks; DB overrides at request time
- A `ContextVar` in `provider_factory.py` carries the resolved config through the entire async call chain (chat_loop, worker agent, summarisation) without changing function signatures
- Per-provider `RequestQueue` and summarisation `asyncio.Semaphore` cached by `(provider, concurrency)` — recreated automatically if settings change
- `deep_research.py` routes `chat_loop` through `get_active_chat_loop()` so deep research also uses the correct provider

### Model Selection
- Model is no longer hardcoded in the frontend — `App.jsx` calls `GET /api/models` on load
- `/api/models` returns the active provider's model list with `active: true` marking the configured default
- `FIXED_MODEL` constant has been removed from `App.jsx`
- Curated model lists in `config.py`: `MODEL_LIST` (Ollama) and `OPENROUTER_MODEL_LIST` (OpenRouter)

### Provenance
- `Chat.model` and `Chat.provider` — set at chat creation (frontend state at time of first message)
- `Message.model` and `Message.provider` — set on every **assistant** message from the backend result; authoritative record of what was actually used at inference time

### Worker Agent Optimisations
The Worker's research pipeline has been tuned to minimise unnecessary LLM calls and summarisation overhead. Key decisions:

- **`search_legislation` response slimming** — `_slim_search_results` in `tools.py` strips the API response to `legislation_id`, `title`, `url`, `status`, `year`, and `extent` only. The `description` field is intentionally excluded — it is verbose and redundant once Phase 2 retrieves actual section text. This keeps Phase 1 results under the summarisation threshold (~1–2K per result vs 10–16K with description), eliminating Phase 1 summarisation entirely.
- **One call per `legislation_id` in Phase 2** — The Worker system prompt instructs the model to make exactly one `search_legislation_sections` call per `legislation_id`, combining all aspects into a single query (e.g. `"procedure, confirmation, compensation, definition of acquiring authority"`). This prevents duplicate calls to the same Act, which were previously the dominant source of unnecessary summarisation.
- **Dual-model support** — Each provider can be configured with a separate `summarisation_model` (Admin Portal → Developer tab). If set, this model is used exclusively for document summarisation; the main `model` is used for all Manager and Worker agent calls. If blank, both roles use the same model. Recommended: on OpenRouter, set `summarisation_model` to `google/gemini-2.0-flash` for fast, cheap summarisation while keeping a capable model for reasoning.
- **Summarisation concurrency** — Controlled per-provider via `max_summarise_concurrency` in the Admin Portal. Ollama should be set to **1** — concurrent calls to the Ollama cloud endpoint cause HTTP 500 errors. OpenRouter can handle **5+** without errors and processes summaries in parallel significantly faster. The right value depends on the model and endpoint capacity.
- **Model quality is the dominant variable** — A capable instruction-following model (e.g. Gemini Flash on OpenRouter) will correctly batch Phase 2 calls, use combined queries, and complete an 8-Act research query in ~90 seconds. A weaker model (e.g. free-tier Nemotron) ignores batching instructions, makes sequential single calls with duplicate `legislation_id`s, and produces bloated context — with the same infrastructure but ~10× worse performance.
- **Phase 2 nudge** — After each `search_legislation` result is processed, a `[NEXT STEP: Call search_legislation_sections...]` instruction with extracted `legislation_id`s is appended to the tool result. This ensures the model proceeds to Phase 2 even if the system prompt instruction is not followed precisely.

### Other
- Python deps are installed **globally** (no venv) on the target — the offline installer uses `pip install` directly
- The frontend is **pre-built on the dev machine** and committed including `client/dist/` — the target has no Node.js
- The backend serves the pre-built `client/dist` as static files

## Dev Machine Setup
- Portable Node.js v22.15.0 lives at `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`
- Add to PATH before running npm: `export PATH="/c/Users/rhett/node_portable/node-v22.15.0-win-x64:$PATH"`
- Use bash (Git Bash) for shell commands — not PowerShell or cmd — as the Claude Code shell
- To run `.cmd` scripts from bash: `cmd //c "C:\Projects\LexChat\deployment\start_native.cmd"`
- Locally there are no SSL certs, so the app runs on **HTTP port 8000** (not HTTPS 443)
- The start script emits harmless `find` errors (bash/cmd `find` mismatch) — PostgreSQL still starts correctly
- PostgreSQL credentials are the same locally and on the target: `lexuser`/`lexpassword`/`lexchat`

## Environment Variables (server_py/.env)
| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_API_KEY` | Bearer token for cloud-routed Ollama | *(blank)* |
| `OPENROUTER_API_KEY` | OpenRouter API key | *(blank)* |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://lexuser:lexpassword@localhost:5432/lexchat` |
| `JWT_SECRET` | Auth token signing key | `dev_secret_key_change_me` |

All `.env` values are startup defaults only. Provider-specific settings (base URL, API key, model, temperature, concurrency) can be overridden at runtime via Admin Portal → Developer tab and are persisted in the DB.

## Deployment Workflow
The **only** way to deploy to the target server is via GitHub — the target does a `git pull` from `origin/experiment/native-deployment`. There is no direct file transfer or zip-based deployment.

1. Make changes to `client/src/`
2. Build: `npm run build` (in `client/`)
3. Commit **including** `client/dist/` (force-add — it is gitignored): `git add -f client/dist/`
4. Push to `origin experiment/native-deployment`
5. On the target: `git pull`, then restart with `stop_native.cmd` and `start_native.cmd`

Always commit and push together in the same step — uncommitted or unpushed changes are invisible to the target.

## Start / Stop
| Action | Script |
|---|---|
| Start | `deployment\start_native.cmd` |
| Stop | `deployment\stop_native.cmd` |

Start script launches PostgreSQL, then Ollama, then the FastAPI backend. Stop script kills uvicorn, Ollama, and the PostgreSQL Windows service.

## Key Files
| File | Purpose |
|---|---|
| `client/src/App.jsx` | Main frontend app — chat UI, favicon swap, dynamic model fetch |
| `client/src/pages/AdminPortal.jsx` | Admin portal including Developer tab with provider config panel |
| `server_py/src/config.py` | `MODEL_LIST`, `OPENROUTER_MODEL_LIST`, system prompts, app settings |
| `server_py/src/agent/tools.py` | LEX API tool schemas, `_slim_search_results`, `execute_worker_tool` |
| `server_py/src/agent/agent_shared.py` | Shared worker tool execution pipeline (used by both provider clients) |
| `server_py/src/agent/ollama_client.py` | Ollama agent implementation (chat_loop, worker, summarisation) |
| `server_py/src/agent/openrouter_client.py` | OpenRouter agent implementation (OpenAI-compatible) |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar config, queue/semaphore caches; `get_summarise_model()` |
| `server_py/src/routers/ai.py` | `/api/models` and `/api/chat` endpoints |
| `server_py/src/routers/developer.py` | Developer-only endpoints including provider config GET/POST |
| `server_py/src/models.py` | SQLAlchemy models — includes `AppSetting`, `Chat.provider`, `Message.model/provider` |
| `deployment/NATIVE_DEPLOYMENT.md` | Full deployment reference |

## Admin Portal — Developer Tab
Available to the `admin` user only. Contains:
- **LLM Provider panel** — configure both providers (base URL, API key, model, temperature, max concurrent requests, max concurrent summarisations); separate Save Settings and Set as Active buttons
- **Synthetic Data Generation** — seed 100 test users with 6 months of chat history
- **Danger Zone** — wipe all data except the admin account

## Favicon Behaviour
- Static: `client/public/favicon.png` (first frame of spinner GIF)
- While AI is generating: swaps to animated canvas spinner driven by `requestAnimationFrame`
- Logic is in a `useEffect` watching the `loading` state in `App.jsx`
