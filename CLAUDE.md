# LexChat — Claude Code Context

## What This Project Is
LexChat is an AI-powered legal research assistant for a **UK government legal department**. Users are qualified lawyers querying UK legislation and case law. The system uses a Manager-Worker agent architecture — the Manager handles conversation, the Worker performs deep research via the LEX API.

## Tech Stack
- **Frontend**: React 19 + Vite + Tailwind CSS (`client/`)
- **Backend**: Python 3.11 + FastAPI + uvicorn (`server_py/`)
- **Database**: PostgreSQL 15 (`lexuser`/`lexpassword`/`lexchat`)
- **AI Engine**: Ollama (cloud-routed models) **or** OpenRouter — switchable at runtime via Admin Portal
- **Model**: Configured per-provider in Admin Portal → Developer tab; defaults to `mistral-large-3:675b-cloud` (Ollama)

## Deployment Target
- **OS**: Windows Server 2022, **air-gapped** (no internet access)
- **No Docker, no WSL** — everything runs natively
- **HTTPS on port 443** using organisational certificates at `deployment/certs/lexchat.crt` and `deployment/certs/lexchat.key`
- PostgreSQL runs as a Windows service; Ollama and uvicorn are started by the launch scripts
- OpenRouter requires internet — only usable on the dev machine or a non-air-gapped deployment

## Active Branch
All deployment work happens on **`experiment/native-deployment`**. Main branch is `main`.

## Key Architectural Decisions

### LLM Provider System
- Two providers supported: **Ollama** (local/cloud-routed) and **OpenRouter** (internet, OpenAI-compatible API)
- Active provider and all per-provider settings are stored in the `AppSetting` DB table — no restart required to switch
- Per-provider settings: `base_url`, `api_key`, `model`, `temperature`, `max_concurrent_requests`, `max_summarise_concurrency`
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
| `server_py/src/agent/ollama_client.py` | Ollama agent implementation (chat_loop, worker, summarisation) |
| `server_py/src/agent/openrouter_client.py` | OpenRouter agent implementation (OpenAI-compatible) |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar config, queue/semaphore caches |
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
