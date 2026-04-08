# LexChat — Claude Code Context

## What This Project Is
LexChat is an AI-powered legal research assistant for a **UK government legal department**. Users are qualified lawyers querying UK legislation and case law. The system uses a Manager-Worker agent architecture — the Manager handles conversation, the Worker performs deep research via the LEX API.

## Tech Stack
- **Frontend**: React 19 + Vite + Tailwind CSS (`client/`)
- **Backend**: Python 3.11 + FastAPI + uvicorn (`server_py/`)
- **Database**: PostgreSQL 15 (`lexuser`/`lexpassword`/`lexchat`)
- **AI Engine**: Ollama (cloud-routed models)
- **Model**: Locked to `mistral-large-3:675b-cloud` (256KB context) — no model selector in UI

## Deployment Target
- **OS**: Windows Server 2022, **air-gapped** (no internet access)
- **No Docker, no WSL** — everything runs natively
- **HTTPS on port 443** using organisational certificates at `deployment/certs/lexchat.crt` and `deployment/certs/lexchat.key`
- PostgreSQL runs as a Windows service; Ollama and uvicorn are started by the launch scripts

## Active Branch
All deployment work happens on **`experiment/native-deployment`**. Main branch is `main`.

## Key Architectural Decisions
- Model is hardcoded in `client/src/App.jsx` (`FIXED_MODEL = 'mistral-large-3:675b-cloud'`) and in `server_py/src/config.py` (`MODEL_LIST`)
- Python deps are installed **globally** (no venv) on the target — the offline installer uses `pip install` directly
- The frontend is **pre-built on the dev machine** and transferred as a zip — the target has no Node.js
- The backend serves the pre-built `client/dist` as static files

## Dev Machine Setup
- Portable Node.js v22.15.0 lives at `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`
- Add to PATH before running npm: `export PATH="/c/Users/rhett/node_portable/node-v22.15.0-win-x64:$PATH"`
- Use bash (Git Bash) for shell commands — not PowerShell or cmd — as the Claude Code shell

## Frontend Update Workflow (Air-Gapped)
1. Make changes to `client/src/`
2. Build: `npm run build` (in `client/`)
3. Package: `deployment\package_frontend_update.ps1` → produces `frontend_update.zip`
4. Transfer zip to target server repo root
5. Apply: `deployment\apply_frontend_update.ps1` on target
6. Restart: `stop_native.cmd` then `start_native_offline.cmd`

## Start / Stop
| Action | Script |
|---|---|
| Start (air-gapped) | `deployment\start_native_offline.cmd` |
| Start (internet) | `deployment\start_native.cmd` |
| Stop (both) | `deployment\stop_native.cmd` |

Start scripts launch **Ollama first**, then the FastAPI backend. Stop script kills uvicorn, Ollama, and the PostgreSQL Windows service.

## Key Files
| File | Purpose |
|---|---|
| `client/src/App.jsx` | Main frontend app — chat UI, favicon swap, fixed model |
| `server_py/src/config.py` | Model list, system prompts, app settings |
| `server_py/src/agent/ollama_client.py` | Agent logic, Ollama communication |
| `server_py/src/routers/ai.py` | `/api/models` and `/api/chat` endpoints |
| `deployment/NATIVE_DEPLOYMENT.md` | Full deployment reference |

## Favicon Behaviour
- Static: `client/public/favicon.png` (first frame of spinner GIF)
- While AI is generating: swaps to `client/public/favicon-loading.gif` (animated spinner)
- Logic is in a `useEffect` watching the `loading` state in `App.jsx`
