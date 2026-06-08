# AILA — Claude Code Context

## What This Project Is
AILA (AI Legal Assistant) is an AI-powered legal research assistant for a **UK government organisation**. Users are qualified lawyers querying UK legislation and case law. The system uses a Manager-Worker agent architecture — the Manager handles conversation, the Worker performs deep research via the LEX API.

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
Current feature branch: **`feature/multi-bot-federation`** — merge to `main` when testing is complete. `main` is the branch the server pulls from.

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

### Parliamentary Research Worker Optimisations
When `research_mode == "parliamentary_records"` (set via `RESEARCH_MODE` env var for the parliament bot), the Worker uses `PARLIAMENT_TOOLS` instead of `WORKER_TOOLS`. Key design decisions:

- **Parliament tool set** — `search_hansard`, `get_hansard_debate`, `get_member_info`, `search_bills`, `search_scottish_parliament`. Wired via `get_worker_tools("parliamentary_records")` in `tools.py`.
- **TWFY API limitation** — `getHansard` does **not** support date range filtering. The `date_from`/`date_to` schema params are accepted but not forwarded to the API (they are silently ignored by the endpoint). Results are always ordered by date (most recent first), regardless of any date constraints. The model is informed of this in the system prompt.
- **Search budget** — `run_worker_agent` creates `search_budget = {"remaining": 2}` for `parliamentary_records` mode and passes it to every `run_worker_tool` call. When the budget hits 0, `run_worker_tool` returns a hard-stop JSON message instead of calling the API, forcing the model to proceed to Phase 2. Without this cap, weaker models loop on `search_hansard` indefinitely (10–15 calls) because TWFY returns recent debates by date rather than by relevance, so results often look irrelevant to the query.
- **Debate title extraction** — `_slim_hansard_results` extracts debate titles from `speech.parent.body` (not `speech.debate`, which is always empty). The `parent.body` field is HTML so it is run through `_strip_html` (which calls `html.unescape`).
- **`debate_type` hint** — The slimmed result includes a `debate_type` field (`"lords"`, `"wrans"`, `"wms"`, or `"debates"`) detected from `speech.listurl`. The model passes this when calling `get_hansard_debate`, ensuring the correct TWFY endpoint is used (`getLords`, `getWrans`, or `getDebates`).
- **Phase 2 nudge** — After each `search_hansard` result, a `[MANDATORY NEXT STEP — DO NOT call search_hansard again...]` instruction listing the returned gids and their `debate_type` values is appended to the tool result. This reinforces the search budget stop.
- **TWFY API key** — Set via `TWFY_API_KEY` env var (free key from theyworkforyou.com/api/key). Required for `search_hansard`, `get_hansard_debate`, and `search_scottish_parliament`. If missing, those tools return a clear error.

### Federation System
Multiple specialised bots (each a separate FastAPI process + DB) can consult each other via `POST /api/consult`. The calling Manager agent gets a `consult_peer` tool injected alongside `delegate_research` — but only when at least one enabled peer is registered. With zero peers, behaviour is identical to today.

Key design decisions:
- **`peer_bots` DB table** — stores peer registry; managed via Admin Portal → Federation tab or `POST/PUT/DELETE /api/peers`
- **`bot_config.json`** — each bot has an identity file (`bot_id`, `name`, `tagline`, `logo_path`) and an optional `peer_registry_seed` list loaded on startup (insert-or-ignore by `peer_id`). Path set via `BOT_CONFIG_PATH` env var.
- **`get_manager_tools(peer_descriptions)`** in `tools.py` — builds the manager tool list dynamically. Returns the same list as the old hardcoded `MANAGER_TOOLS` when `peer_descriptions` is empty; appends `consult_peer` when peers exist.
- **Depth limit** — `ConsultRequest.depth` is incremented by the caller. Any request arriving with `depth >= 2` gets HTTP 422 immediately — prevents A→B→C cascade loops.
- **`api_key` is write-only** — stored in `peer_bots.api_key`; never returned by any API response (treat like a password).
- **`/api/consult` is synchronous JSON** (not SSE) — the calling Manager blocks until the full peer answer is returned before synthesising its response.
- **Identity endpoints** — `GET /api/bot-info` (no auth) returns `bot_id`, `name`, `tagline`; `GET /api/bot/logo` streams the logo file. Frontend fetches these on mount and uses them for dynamic branding.
- **Local dev** — see `deployment/LOCAL_SETUP.md` for running multiple bots on one machine. `deployment/local/` is gitignored (holds per-machine `active_bots.txt` and `shared.env`).
- **Parliament bot DB** — `lexchat_parliament` (set in `bots/parliament/.env`). `start_federation_dev.ps1` creates this DB automatically. The script loads `bots/parliament/.env` first, then overrides `BOT_ID` and `BOT_CONFIG_PATH` with absolute paths so the relative path in the `.env` file doesn't win.
- **`BOT_CONFIG_PATH` note** — uvicorn runs from `server_py/`, so `os.path.abspath(path)` resolves relative paths relative to `server_py/`. The federation dev script sets this to an absolute path to avoid the ambiguity.

### External API Dependencies

All external APIs called at query time. URLs must be reachable from the deployment target.

| API | Base URL | Used by | Auth | Notes |
|---|---|---|---|---|
| LEX API | `https://lex.lab.i.ai.gov.uk` | Legislation bot | None (internal) | POST endpoints: `/legislation/search`, `/legislation/section/search`, `/legislation/text` |
| National Archives case law | `https://caselaw.nationalarchives.gov.uk/atom.xml` | Legislation bot (case law mode) | None | GET with `query`, `court`, `date_from`, `date_to` params; returns Atom XML |
| TheyWorkForYou (TWFY) | `https://www.theyworkforyou.com/api` | Parliament bot | `TWFY_API_KEY` | Endpoints: `getHansard`, `getDebates`, `getLords`, `getWrans`, `getSP`, `getMSPInfo` |
| Parliament Members API | `https://members-api.parliament.uk/api/Members/Search` | Parliament bot | None | `get_member_info` for Commons (`House=1`) and Lords (`House=2`) |
| Parliament Bills API | `https://bills-api.parliament.uk/api/v1/Bills` | Parliament bot | None | `search_bills` for UK Westminster |
| Scottish Parliament Bills | `https://data.parliament.scot/api/bills` | Parliament bot | None | `search_bills` for Scotland; full list fetched, filtered client-side (no server-side search param) |
| OpenRouter | `https://openrouter.ai/api/v1` | Both (optional) | `OPENROUTER_API_KEY` | Only when OpenRouter is set as active provider in Admin Portal |

To verify all endpoints are reachable from a deployment target, run `server_py/test_apis.ps1` (reads `TWFY_API_KEY` from `.env`; TWFY tests skip gracefully if the key is absent).

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
| `BOT_ID` | This bot's identifier (used by `/api/bot-info` fallback) | `legislation_bot` |
| `BOT_CONFIG_PATH` | Path to `bot_config.json`; resolved relative to CWD (uvicorn runs from `server_py/`) | *(blank — identity not loaded)* |
| `RESEARCH_MODE` | Override research mode for this bot instance; set to `parliamentary_records` for the parliament bot | *(blank — uses frontend value)* |
| `TWFY_API_KEY` | TheyWorkForYou API key for Hansard/parliamentary tools; free at theyworkforyou.com/api/key | *(blank)* |

All `.env` values are startup defaults only. Provider-specific settings (base URL, API key, model, temperature, concurrency) can be overridden at runtime via Admin Portal → Developer tab and are persisted in the DB.

## Deployment Workflow
The **only** way to deploy to the target server is via GitHub — the target does a `git pull` from `origin/main`. There is no direct file transfer or zip-based deployment.

1. Make changes to `client/src/`
2. Build: `npm run build` (in `client/`)
3. Commit **including** `client/dist/` (force-add — it is gitignored): `git add -f client/dist/`
4. Push to `origin main`
5. On the target: `git pull`, then restart with `stop_native.cmd` and `start_native.cmd`

Always commit and push together in the same step — uncommitted or unpushed changes are invisible to the target.

## Start / Stop
| Action | Script |
|---|---|
| Start | `deployment\start_native.cmd` |
| Stop | `deployment\stop_native.cmd` |

Start script launches PostgreSQL, then Ollama, then the FastAPI backend. Stop script kills uvicorn, Ollama, and the PostgreSQL Windows service.

## Frontend Design System

The full token/component reference lives at `client/src/design-system.md`. **Read it before writing any new frontend UI.** Key rules:

- Use design token classes — never raw Tailwind palette values (`text-blue-600`, `bg-zinc-800`, `text-gray-500`, etc.)
- **`bg-brand` ≠ `bg-accent`** — `bg-brand` is for primary CTA button backgrounds; `bg-accent` is for focus rings, active indicators, and selected states only. Mixing these up is the most common mistake.
- `bg-brand-navy` / `hover:bg-brand-navy-dark` are **old non-token classes** that no longer exist — replace with `bg-brand` / `hover:bg-brand-hover`.
- Token-backed classes (`text-ink-*`, `bg-paper`, `bg-brand`, etc.) switch for dark mode automatically — no `dark:` variants needed for colour.
- All button labels, inputs, and UI chrome use `font-ui`; legal content uses `font-serif`.

### Button quick-reference

| Variant | Key classes |
|---|---|
| Primary | `bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed` |
| Secondary | `bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:ring-2 focus-visible:ring-accent` |
| Danger | `bg-danger text-white font-ui text-sm font-medium rounded-md px-4 py-2 hover:opacity-90 focus-visible:ring-2 focus-visible:ring-danger` |
| Icon | `size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-accent` |
| Filter pill (active) | `bg-accent text-white border-transparent rounded-full px-3 py-1 font-ui text-xs` |
| Filter pill (inactive) | `border border-ink-200 text-ink-600 rounded-full px-3 py-1 font-ui text-xs hover:bg-ink-50` |

## Key Files
| File | Purpose |
|---|---|
| `client/src/App.jsx` | Main frontend app — chat UI, favicon swap, dynamic model fetch, dynamic bot branding, post-login notice gate |
| `client/src/components/DataSensitivityNotice.jsx` | Post-login splash screen — data sensitivity warning shown on every login session |
| `client/src/design-system.md` | Design token reference — colours, typography, button/component patterns |
| `client/src/pages/AdminPortal.jsx` | Admin portal including Developer tab (provider config) and Federation tab (peer registry CRUD) |
| `client/src/pages/Settings.jsx` | Account settings page — change password form |
| `server_py/src/config.py` | `MODEL_LIST`, `OPENROUTER_MODEL_LIST`, system prompts, app settings; `bot_id`/`bot_config_path` |
| `server_py/src/agent/tools.py` | LEX API tool schemas, `_slim_search_results`, parliament tools (`PARLIAMENT_TOOLS`, `execute_parliament_tool`, `_slim_hansard_results`), `get_manager_tools(peer_descriptions)`, `get_worker_tools(research_mode)` |
| `server_py/src/agent/agent_shared.py` | Shared worker tool execution pipeline; `run_worker_tool` (includes `search_budget` enforcement for parliamentary mode) |
| `server_py/src/agent/ollama_client.py` | Ollama agent implementation (chat_loop, worker, summarisation, federation) |
| `server_py/src/agent/openrouter_client.py` | OpenRouter agent implementation (OpenAI-compatible, federation) |
| `server_py/src/agent/provider_factory.py` | Provider resolution, ContextVar config, queue/semaphore caches; `get_summarise_model()` |
| `server_py/src/agent/federation_client.py` | `load_peer_registry`, `build_peer_descriptions`, `consult_peer`; `ConsultRequest`/`ConsultResponse` |
| `server_py/src/routers/ai.py` | `/api/models` and `/api/chat` endpoints |
| `server_py/src/routers/developer.py` | Developer-only endpoints including provider config GET/POST and `GET /developer/activity-log` |
| `server_py/src/routers/identity.py` | `GET /api/bot-info`, `GET /api/bot/logo` — no auth required |
| `server_py/src/routers/federation.py` | `POST /api/consult` — receives peer consultation requests |
| `server_py/src/routers/peers.py` | Admin CRUD for peer registry — `api_key` never returned |
| `server_py/src/models.py` | SQLAlchemy models — includes `AppSetting`, `Chat.provider`, `Message.model/provider`, `ActivityLog`, `PeerBot` |
| `client/src/components/ActivityLogModal.jsx` | Admin activity log modal — unified feed of logins, queries, feedback, surveys, errors; auto-refreshes every 10 min |
| `bots/legislation/bot_config.json` | Legislation bot identity + peer seed (default/template bot config) |
| `bots/parliament/bot_config.json` | Parliament bot identity; `research_mode: "parliamentary_records"` under `agent` key |
| `bots/parliament/.env` | Parliament bot env overrides — `RESEARCH_MODE`, `TWFY_API_KEY`, `DATABASE_URL` (`lexchat_parliament`), `PORT=8001` |
| `shared/scripts/new_bot.ps1` | Provision a new bot from the legislation template |
| `shared/scripts/register_peer.ps1` | Register a peer bot via the admin API |
| `deployment/LOCAL_SETUP.md` | Multi-bot local dev workflow |
| `deployment/NATIVE_DEPLOYMENT.md` | Full deployment reference |

## Admin Portal — Developer Tab
Available to the `admin` user only. Contains:
- **LLM Provider panel** — configure both providers (base URL, API key, model, temperature, max concurrent requests, max concurrent summarisations); separate Save Settings and Set as Active buttons
- **Activity Log** — unified feed of user logins, queries submitted, feedback ratings, survey responses, and service health errors; filterable by time range; auto-refreshes every 10 minutes; powered by `GET /developer/activity-log`
- **Synthetic Data Generation** — seed 100 test users with 6 months of chat history
- **Danger Zone** — wipe all data except the admin account

## Admin Portal — Federation Tab
Available to the `admin` user only. Contains:
- **Peer table** — lists all registered peers with name, peer_id, base URL, description, API key indicator, and enable/disable toggle
- **Delete** — removes a peer from the registry immediately
- **Add Peer form** — `peer_id`, `name`, `base_url`, `api_key` (password field, write-only), `description`, `enabled` checkbox
- API key is **never displayed** after save — `has_api_key: true/false` indicator only

## Activity Log
- DB table: `activity_log` (columns: `id`, `event_type`, `username`, `description`, `created_at`); index on `created_at`
- Model: `ActivityLog` in `server_py/src/models.py`
- Currently only `LOGIN` events are written explicitly (in `auth.py` on successful login); `QUERY`, `FEEDBACK`, `SURVEY`, and `ERROR` events are synthesised at query time via UNION ALL from `messages`, `product_feedback`, and `service_health_logs`
- Endpoint: `GET /developer/activity-log?days=7&limit=500` — admin only; `days=all` disables the date filter
- Frontend: `ActivityLogModal.jsx` opened from the Developer tab

## Post-Login Splash Screen
- Shown on every login session, before the main app renders
- Warns users not to enter information above OFFICIAL-SENSITIVE, personal data, privileged communications, ongoing proceedings, information under confidence, or commercially sensitive data
- Explains that queries are processed by third-party LLM services outside the organisation's secure network
- User must click "I understand — proceed to AILA" to dismiss; cannot be bypassed
- State (`noticeAcknowledged`) resets to `false` on logout, ensuring the notice reappears on the next login
- Component: `client/src/components/DataSensitivityNotice.jsx`

## Favicon Behaviour
- On mount: attempts `GET /api/bot/logo` — if the file exists, swaps favicon to it; falls back to `/favicon.svg` silently
- While AI is generating: swaps to animated canvas spinner driven by `requestAnimationFrame`
- On load complete: reverts to `/favicon.svg` (or bot logo on next mount)
- Logic is in two `useEffect`s in `App.jsx` — one watching `loading`, one running once on mount

## Bot Identity & Branding
- `GET /api/bot-info` (no auth) — returns `bot_id`, `name`, `tagline` from `bot_config.json` loaded at startup
- `App.jsx` fetches bot info on mount: sets `document.title` and `botInfo` state; all "AILA" labels in the UI use `{botInfo.name}` (default `'AILA'` if the request fails)
- `GET /api/bot/logo` — streams `bot_identity.logo_path`; 404 if not configured or file missing
- `BOT_CONFIG_PATH` env var → path to `bot_config.json` relative to repo root; if unset, identity is not loaded and defaults apply
