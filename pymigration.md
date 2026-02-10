# LexChat: Node.js Express → FastAPI Migration Plan

## Overview

Migrate the LexChat backend from Node.js/Express (`server/`) to Python/FastAPI (`server_py/`). The goal is feature-parity with the existing server while leveraging Python's async ecosystem and improving maintainability.

**Current progress: ~25-30%** — project scaffolding, basic auth framework, Ollama streaming, Docker, and test scaffolding are in place. The core (database persistence, full agent system, 14 of 22 endpoints) remains to be built.

---

## Migration Phases

### Phase 1: Database Foundation

The single biggest blocker. Nothing persists until ORM models and schema init exist.

#### 1.1 — Define SQLAlchemy ORM Models

**File:** `server_py/src/models.py` (new)

Create async-compatible SQLAlchemy models matching the existing Postgres schema in `server/src/db.js`:

```
Table: users
├── id           SERIAL PRIMARY KEY
├── username     VARCHAR(255) UNIQUE NOT NULL
├── password_hash VARCHAR(255) NOT NULL
├── email        VARCHAR(255) UNIQUE (nullable)
├── role         VARCHAR(50) DEFAULT 'user'
├── dark_mode    BOOLEAN DEFAULT FALSE
└── created_at   TIMESTAMP DEFAULT now()

Table: chats
├── id           SERIAL PRIMARY KEY
├── user_id      INTEGER FK → users(id) ON DELETE CASCADE
├── title        TEXT
├── model        VARCHAR(255)
└── created_at   TIMESTAMP DEFAULT now()

Table: messages
├── id               SERIAL PRIMARY KEY
├── chat_id          INTEGER FK → chats(id) ON DELETE CASCADE
├── role             VARCHAR(50) NOT NULL ('user' | 'assistant')
├── content          TEXT NOT NULL
├── rating           INTEGER CHECK (1-5), nullable
├── feedback_comment TEXT, nullable
└── created_at       TIMESTAMP DEFAULT now()
```

- Use `sqlalchemy.orm.DeclarativeBase` with `Mapped` type annotations.
- Define relationships: `User.chats`, `Chat.messages`, `Chat.user`.
- Import `Base` into `database.py`.

#### 1.2 — Schema Initialisation on Startup

**File:** `server_py/src/database.py` (edit)

Add an `init_db()` async function that:
1. Calls `Base.metadata.create_all(engine)` to create tables if not present.
2. Seeds the default admin user (username=`admin`, bcrypt-hashed password=`admin`, role=`admin`) if no admin exists.
3. Is called from a FastAPI `@app.on_event("startup")` (or `lifespan`) handler in `main.py`.

This mirrors `initializeDB()` in `server/src/db.js:12-69`.

#### 1.3 — Add Alembic (optional, recommended)

**New files:** `server_py/alembic/`, `server_py/alembic.ini`

- `pip install alembic` (add to `requirements.txt`).
- Configure async Alembic with the same `DATABASE_URL`.
- Generate initial migration from ORM models.
- This enables future schema changes without manual ALTER TABLE.

**Test gate:** Start the app against a fresh Postgres container. Verify tables are created and admin user is seeded.

---

### Phase 2: Wire Real Database Into Existing Routes

Replace all mock/in-memory data with actual database queries. Each sub-task below targets one router file.

#### 2.1 — Auth Routes (`routers/auth.py`)

**Source of truth:** `server/src/routes/authRoutes.js`

Replace the hardcoded `testuser`/`admin` credentials with real DB lookups:

| Endpoint | Current State | Action |
|---|---|---|
| `POST /login` | Hardcoded credentials | Query `users` table, `bcrypt.verify` password, return JWT + user object including `dark_mode` |
| `POST /logout` | Done | No change needed |
| `GET /me` | Returns token claims only | Query `users` table by `req.user.id`, return `{id, username, role, dark_mode}` |

- Inject `db: AsyncSession = Depends(get_db)` into each endpoint.
- Use `passlib.hash.bcrypt` (already in requirements) for password verification.

#### 2.2 — Chat Routes (`routers/chats.py`)

**Source of truth:** `server/src/routes/chatRoutes.js`

Replace `MOCK_CHATS` / `MOCK_MESSAGES` globals with database CRUD:

| Endpoint | Action |
|---|---|
| `GET /` | `SELECT * FROM chats WHERE user_id = :uid ORDER BY created_at DESC` |
| `POST /` | `INSERT INTO chats (user_id, title, model) ...` |
| `GET /:id/messages` | Verify ownership, `SELECT * FROM messages WHERE chat_id = :id ORDER BY created_at ASC` |
| `POST /:id/messages` | Verify ownership, `INSERT INTO messages (chat_id, role, content) ...` |

- Remove all `MOCK_*` globals.
- Add ownership verification (user_id check) on all per-chat endpoints.

#### 2.3 — User Routes (`routers/users.py`)

**Source of truth:** `server/src/routes/userRoutes.js`

Replace mock data with real queries:

| Endpoint | Action |
|---|---|
| `GET /` | `SELECT id, username, email, role, created_at FROM users ORDER BY id` |
| `POST /` | Hash password with bcrypt, INSERT, handle unique constraint (23505) |

- Hash passwords with `passlib.hash.bcrypt.hash()`.
- Handle duplicate username/email with proper 400 response.

**Test gate:** Run full CRUD cycle through each router against real Postgres. Verify data survives restarts.

---

### Phase 3: Missing Auth & User Endpoints

Port the 5 endpoints that don't exist yet in the FastAPI server.

#### 3.1 — Password Reset Request

**File:** `routers/auth.py`
**Source:** `authRoutes.js:46-66`

- `POST /api/auth/reset-password-request`
- Body: `{username}`
- Look up user email, call email service (Phase 6), always return `200` with generic message.

#### 3.2 — Change Password

**File:** `routers/auth.py`
**Source:** `authRoutes.js:68-89`

- `POST /api/auth/change-password`
- Auth required.
- Verify `currentPassword` against DB hash, then update with new bcrypt hash.

#### 3.3 — Update Preferences

**File:** `routers/auth.py`
**Source:** `authRoutes.js:106-115`

- `PUT /api/auth/preferences`
- Auth required.
- Body: `{dark_mode: bool}`
- Update `users.dark_mode` for current user.

#### 3.4 — Update User (Admin)

**File:** `routers/users.py`
**Source:** `userRoutes.js:76-109`

- `PUT /api/users/:id`
- Admin required.
- Update username, role, email, and optionally password.
- Handle unique constraint violations.

#### 3.5 — Delete User (Admin)

**File:** `routers/users.py`
**Source:** `userRoutes.js:54-74`

- `DELETE /api/users/:id`
- Admin required.
- Prevent deleting self or the `admin` account.
- Cascade deletes chats and messages.

---

### Phase 4: Missing Chat & Feedback Endpoints

#### 4.1 — Update Chat Title

**File:** `routers/chats.py`
**Source:** `chatRoutes.js:38-55`

- `PUT /api/chats/:id`
- Auth required, verify ownership.
- Update title.

#### 4.2 — Delete Chat

**File:** `routers/chats.py`
**Source:** `chatRoutes.js:58-71`

- `DELETE /api/chats/:id`
- Auth required, verify ownership.
- Messages cascade-delete via FK.

#### 4.3 — Rate Message

**File:** `routers/chats.py`
**Source:** `chatRoutes.js:113-138`

- `PUT /api/chats/messages/:id/rating`
- Auth required.
- Verify ownership via JOIN with chats.
- Body: `{rating: 1-5, comment?: str}`
- Validate rating range.

---

### Phase 5: Agent System (Core Intelligence)

This is the most complex phase. The current `ollama_client.py` only does basic streaming. The Node.js server has a full Manager/Worker agent architecture with tool calling.

#### 5.1 — Configuration: System Prompts & Models

**File:** `server_py/src/config.py` (edit)

Add settings that mirror `server/src/config.js`:

- `lex_api_url` (default: `https://lex.lab.i.ai.gov.uk/`)
- `default_context` (default: `131072`)
- `models` list with `name` and `contextLengthKB`
- `manager_system_prompt` — copy verbatim from `config.js:25-42`
- `worker_system_prompt` — copy verbatim from `config.js:44-70`
- `email_user`, `email_pass`

#### 5.2 — Tool Definitions

**File:** `server_py/src/agent/tools.py` (new)

Port from `server/src/agent/tools.js`:

- `MANAGER_TOOLS` — list of Ollama tool-call JSON schemas:
  - `delegate_research(query: str)`
- `WORKER_TOOLS` — list of Ollama tool-call JSON schemas:
  - `search_legislation(query: str, year_from?: int, year_to?: int)`
  - `get_legislation_text(legislation_id: str)`
  - `search_caselaw(query: str, year_from?: int, year_to?: int)`

#### 5.3 — Tool Execution (LEX API Client)

**File:** `server_py/src/agent/tools.py` (same file)

Port `executeWorkerTool()` from `tools.js:101-141`:

- Use `httpx.AsyncClient` (already in requirements).
- `search_legislation` → `POST {LEX_API_URL}/legislation/search`
- `get_legislation_text` → `POST {LEX_API_URL}/legislation/text`
- `search_caselaw` → `POST {LEX_API_URL}/caselaw/search`
- Return JSON-stringified results. Handle and log errors.

#### 5.4 — Generic Chat Loop (ReAct Loop)

**File:** `server_py/src/agent/ollama_client.py` (rewrite)

Port `chatLoop()` from `ollama.js:100-196`:

```python
async def chat_loop(
    messages: list,
    model: str,
    signal: asyncio.Event,   # cancellation
    num_ctx: int,
    tools: list,
    tool_executor: Callable,  # async (name, args) -> str
    on_chunk: Callable | None  # async (event_dict) -> None
) -> dict:
```

Logic:
1. Build payload: `{model, messages, tools, stream: True, options: {num_ctx}}`.
2. POST to Ollama `/api/chat` with streaming.
3. Parse JSONL lines, accumulate `content` and `tool_calls`.
4. Stream tokens via `on_chunk({type: "token", content})`.
5. If tool calls present: execute each via `tool_executor`, append `{role: "tool", content, name}` to messages, recurse.
6. Return final `{role: "assistant", content}`.

#### 5.5 — Worker Agent

**File:** `server_py/src/agent/ollama_client.py` (same file)

Port `runWorkerAgent()` from `ollama.js:21-38`:

- Fresh context with worker system prompt.
- Uses `WORKER_TOOLS` and `execute_worker_tool`.
- Suppresses token streaming (passes `on_chunk=None`).
- Reports tool start/end to parent's `on_chunk`.

#### 5.6 — Manager Agent (Main Chat Entry Point)

**File:** `server_py/src/agent/ollama_client.py` (same file)

Port `processUserRequest()` from `ollama.js:45-93`:

- Injects manager system prompt.
- Injects learning context (Phase 5.8).
- Uses `MANAGER_TOOLS`.
- `delegate_research` tool executor calls `run_worker_agent()`.
- Streams tokens to client.

#### 5.7 — Deep Research Agent

**File:** `server_py/src/agent/deep_research.py` (new)

Port from `server/src/agent/deepResearch.js`:

- Combine worker tools + `search_web` tool.
- Use the deep research system prompt (copy from `deepResearch.js:38-50`).
- Reuse `chat_loop()` with the expanded toolset.

#### 5.8 — Web Search

**File:** `server_py/src/agent/web_search.py` (new)

Port from `server/src/agent/webSearch.js`:

- The Node.js version uses `google-sr` (Google scraper).
- Python equivalent: use `googlesearch-python` or `httpx` + scraping.
- Add to `requirements.txt`.
- Function: `async def search_web(query: str) -> str` — returns formatted top 5 results.

#### 5.9 — Learning / RAG System

**File:** `server_py/src/agent/learning.py` (new)

Port from `server/src/agent/learning.js`:

- `extract_keywords(text)` — remove stop words, join with ` | ` for tsquery.
- `async get_relevant_examples(user_query, db_session)` — execute the two PostgreSQL full-text-search CTEs (positive examples rated >= 4, critiques rated <= 3 with comment). Return `{examples, critiques}`.
- `format_learning_context(learning_data)` — format into system prompt injection string.

Inject `db: AsyncSession` dependency. Use `session.execute(text(...))` for raw SQL.

#### 5.10 — Update AI Router

**File:** `server_py/src/routers/ai.py` (edit)

Update `POST /api/chat` to:
1. Use the new `process_user_request()` (manager agent) for standard chat.
2. Use `chat_with_deep_research()` when `deep_research=True`.
3. Integrate request queue (Phase 7.1).
4. Add AbortController-equivalent (`asyncio.Event`) for client disconnect.
5. Stream tool status events alongside tokens.
6. Add 2-minute timeout warning SSE event.
7. Handle `ECONNREFUSED` → friendly Ollama-down message.

Update `GET /api/models` to return the configured model list with context lengths (matching `listModels()` in `ollama.js:198-203`).

**Test gate:** Send a chat request through the full Manager → Worker → LEX API pipeline. Verify tool calling, delegation, and SSE streaming work end-to-end.

---

### Phase 6: Admin & Analytics Endpoints

#### 6.1 — Learning Routes

**File:** `server_py/src/routers/learning.py` (new)

**Source:** `server/src/routes/learningRoutes.js`

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/learning/feedback` | Admin | Join messages+chats+users, return rated messages (limit 100) |
| `GET /api/learning/stats` | Admin | Aggregate avg_rating + count by date and model, filterable by `?days=30\|all` |
| `POST /api/learning/test` | Admin | Call `get_relevant_examples(query)`, return raw results |

Register in `main.py`.

#### 6.2 — Stats Routes

**File:** `server_py/src/routers/stats.py` (new)

**Source:** `server/src/routes/statsRoutes.js`

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/stats/usage` | Admin | Returns `{kpi, activity, models, topUsers}` filtered by `?days=30\|all` |

KPIs: total users, total chats, total messages, active users.
Activity: daily chat counts.
Models: chat count per model.
Top Users: top 5 by message count.

Register in `main.py`.

#### 6.3 — Developer Routes

**File:** `server_py/src/routers/developer.py` (new)

**Source:** `server/src/routes/developerRoutes.js`

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/developer/seed` | None | Generate 100 synthetic users + 6 months of chat history with ratings |
| `POST /api/developer/reset` | None | Delete all messages, chats, and non-admin users |

- Python equivalent of `@faker-js/faker` → `pip install faker` (add to `requirements.txt`).
- Port the seeding logic: 100 users, weekly activity loop, 30% activity chance, legal topics, weighted ratings.

Register in `main.py`.

---

### Phase 7: Infrastructure & Services

#### 7.1 — Request Queue

**File:** `server_py/src/utils/queue.py` (new)

Port `RequestQueue` from `server/src/utils/queue.js`:

- Use `asyncio.Semaphore` for concurrency control.
- `async enqueue(task_factory, on_waiting)` — queue with position notification callback.
- `get_stats()` — returns `{active, queued, concurrency}`.
- Wire into `POST /api/chat` in `ai.py`.

#### 7.2 — Structured Logging

**File:** `server_py/src/utils/logger.py` (new)

Port from `server/src/utils/logger.js` (Winston):

- Use Python `logging` module with `logging.handlers.TimedRotatingFileHandler`.
- Create three loggers:
  - `app` — general app logs → `logs/app-YYYY-MM-DD.log`
  - `agent` — AI/tool activity → `logs/agent-YYYY-MM-DD.log`
  - `http` — request/response → `logs/http-YYYY-MM-DD.log`
- Add HTTP logging middleware to FastAPI (use `@app.middleware("http")`).
- Format: `YYYY-MM-DD HH:mm:ss [LEVEL] message`.

#### 7.3 — Email Service

**File:** `server_py/src/services/email_service.py` (new)

Port from `server/src/services/emailService.js` (Nodemailer):

- Use `aiosmtplib` + `email.mime` (add `aiosmtplib` to `requirements.txt`).
- Or simpler: use `smtplib` (stdlib) in a thread executor.
- `async send_welcome_email(to, username, password)` — HTML welcome email.
- `async send_password_reset_email(to, username, token)` — HTML reset email.
- Skip silently if `EMAIL_USER` / `EMAIL_PASS` not configured.
- Gmail SMTP config.

---

### Phase 8: Tests

#### 8.1 — Fix Existing Tests

- `test_auth.py` — Remove soft assertions (accepting 200 OR 401). Use proper test DB setup.
- `test_users.py` — Add admin auth fixture, test real CRUD.
- `test_agent_stream.py` — Mock Ollama responses, test SSE format.

#### 8.2 — Add Test Infrastructure

**File:** `tests/conftest.py` (edit)

- Create a test database (or use SQLite async for fast tests).
- Add fixtures:
  - `db_session` — async test DB session with rollback.
  - `admin_token` — JWT for admin user.
  - `user_token` — JWT for regular user.
  - `seeded_data` — pre-populated users, chats, messages.

Add `pytest-asyncio`, `httpx` (for `AsyncClient`) to `requirements.txt` (httpx already present).

#### 8.3 — New Test Files

| Test File | Covers |
|---|---|
| `test_auth.py` | Login (valid/invalid), logout, /me, change-password, preferences |
| `test_users.py` | Admin CRUD, permission checks, unique constraints, delete protection |
| `test_chats.py` | Full lifecycle: create chat → add messages → rate → update title → delete |
| `test_learning.py` | Feedback listing, stats aggregation, RAG test endpoint |
| `test_stats.py` | Usage KPIs with date filtering |
| `test_developer.py` | Seed + reset operations |
| `test_agent.py` | Mock Ollama, verify tool-calling loop, manager→worker delegation |
| `test_queue.py` | Concurrency limiting, position notifications |

---

### Phase 9: Configuration & Security Hardening

#### 9.1 — Config Alignment

Update `config.py` with all settings from the Node.js `config.js`:

| Setting | Current | Add |
|---|---|---|
| `lex_api_url` | Missing | `https://lex.lab.i.ai.gov.uk/` |
| `default_context` | Missing | `131072` |
| `models` | Missing | List of `{name, contextLengthKB}` |
| `email_user` | Missing | From `.env` |
| `email_pass` | Missing | From `.env` |
| `db_max_connections` | Missing | Default `20` |

#### 9.2 — Security Fixes

- CORS: Restrict origins in production (currently `*`).
- JWT secret: Ensure `.env` override is mandatory in production (fail-fast if default).
- Cookie `secure=True` when `NODE_ENV=production` equivalent.
- Add input validation (Pydantic models enforce this naturally).
- Ensure no raw SQL injection vectors in stats/learning queries that interpolate `days`.

#### 9.3 — Requirements.txt Update

Add all new dependencies:

```
alembic
faker
aiosmtplib
googlesearch-python  # or alternative for web search
pytest-asyncio
```

---

### Phase 10: Docker & Deployment

#### 10.1 — Dockerfile Review

The current `server_py/Dockerfile` already has a working multi-stage build. Verify:
- Python dependencies include all new packages.
- `logs/` directory is created.
- `.env` is not baked into the image.

#### 10.2 — docker-compose.yml

Already configured to use `server_py/Dockerfile`. Verify:
- `LEX_API_URL` is passed as env var.
- `EMAIL_USER`, `EMAIL_PASS` env vars are mapped.
- Volume mount for `logs/` if persistent logging is needed.

#### 10.3 — Smoke Test

Full integration test via Docker:
1. `docker-compose up --build`
2. Verify DB tables are created and admin user seeded.
3. Login as admin via `/api/auth/login`.
4. Create a chat, send a message, verify SSE streaming.
5. Check `/api/stats/usage` returns data.
6. Run `/api/developer/seed`, then verify data.

---

## Execution Order & Dependencies

```
Phase 1 (DB Foundation)
  ├── 1.1 ORM Models
  ├── 1.2 Schema Init
  └── 1.3 Alembic (optional)
      │
Phase 2 (Wire DB into existing routes)
  ├── 2.1 Auth → DB
  ├── 2.2 Chats → DB
  └── 2.3 Users → DB
      │
Phase 3 (Missing auth/user endpoints)      ← can parallel with Phase 4
  ├── 3.1 Password reset request
  ├── 3.2 Change password
  ├── 3.3 Update preferences
  ├── 3.4 Update user
  └── 3.5 Delete user
      │
Phase 4 (Missing chat endpoints)           ← can parallel with Phase 3
  ├── 4.1 Update chat title
  ├── 4.2 Delete chat
  └── 4.3 Rate message
      │
Phase 5 (Agent system)                     ← largest phase, depends on Phase 1
  ├── 5.1 Config: prompts & models
  ├── 5.2 Tool definitions
  ├── 5.3 Tool execution (LEX API)
  ├── 5.4 Chat loop (ReAct)
  ├── 5.5 Worker agent
  ├── 5.6 Manager agent
  ├── 5.7 Deep research agent
  ├── 5.8 Web search
  ├── 5.9 Learning/RAG
  └── 5.10 Update AI router
      │
Phase 6 (Admin endpoints)                  ← depends on Phase 1
  ├── 6.1 Learning routes
  ├── 6.2 Stats routes
  └── 6.3 Developer routes
      │
Phase 7 (Infrastructure)                   ← can parallel with Phases 3-6
  ├── 7.1 Request queue
  ├── 7.2 Structured logging
  └── 7.3 Email service
      │
Phase 8 (Tests)                            ← ongoing, but full suite after Phases 1-7
      │
Phase 9 (Config & security)                ← after all features complete
      │
Phase 10 (Docker & deployment)             ← final validation
```

---

## Endpoint Checklist

| # | Method | Endpoint | Express | FastAPI | Phase |
|---|--------|----------|---------|---------|-------|
| 1 | POST | `/api/auth/login` | Done | Mock → DB | 2.1 |
| 2 | POST | `/api/auth/logout` | Done | Done | — |
| 3 | GET | `/api/auth/me` | Done | Claims → DB | 2.1 |
| 4 | POST | `/api/auth/reset-password-request` | Done | Missing | 3.1 |
| 5 | POST | `/api/auth/change-password` | Done | Missing | 3.2 |
| 6 | PUT | `/api/auth/preferences` | Done | Missing | 3.3 |
| 7 | GET | `/api/users` | Done | Mock → DB | 2.3 |
| 8 | POST | `/api/users` | Done | Mock → DB | 2.3 |
| 9 | PUT | `/api/users/:id` | Done | Missing | 3.4 |
| 10 | DELETE | `/api/users/:id` | Done | Missing | 3.5 |
| 11 | GET | `/api/chats` | Done | Mock → DB | 2.2 |
| 12 | POST | `/api/chats` | Done | Mock → DB | 2.2 |
| 13 | PUT | `/api/chats/:id` | Done | Missing | 4.1 |
| 14 | DELETE | `/api/chats/:id` | Done | Missing | 4.2 |
| 15 | GET | `/api/chats/:id/messages` | Done | Mock → DB | 2.2 |
| 16 | POST | `/api/chats/:id/messages` | Done | Mock → DB | 2.2 |
| 17 | PUT | `/api/chats/messages/:id/rating` | Done | Missing | 4.3 |
| 18 | GET | `/api/learning/feedback` | Done | Missing | 6.1 |
| 19 | GET | `/api/learning/stats` | Done | Missing | 6.1 |
| 20 | POST | `/api/learning/test` | Done | Missing | 6.1 |
| 21 | POST | `/api/developer/seed` | Done | Missing | 6.3 |
| 22 | POST | `/api/developer/reset` | Done | Missing | 6.3 |
| 23 | GET | `/api/stats/usage` | Done | Missing | 6.2 |
| 24 | GET | `/api/models` | Done | Basic → Full | 5.10 |
| 25 | POST | `/api/chat` | Done | Basic → Full | 5.10 |
| 26 | GET | `/health` | N/A | Done | — |

**Legend:** Done = complete, Mock → DB = exists but needs real DB, Missing = not yet created, Basic → Full = partial implementation needs expansion.

---

## Key File Map (Target State)

```
server_py/
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── alembic/
│   └── versions/
├── src/
│   ├── __init__.py
│   ├── main.py                  # App factory, lifespan, router registration
│   ├── config.py                # All settings (Pydantic)
│   ├── database.py              # Engine, session, init_db()
│   ├── models.py                # SQLAlchemy ORM: User, Chat, Message
│   ├── dependencies.py          # JWT auth, get_current_user, get_admin_user
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── ollama_client.py     # chat_loop, run_worker, process_user_request, list_models
│   │   ├── tools.py             # Tool schemas + execute_worker_tool (LEX API)
│   │   ├── deep_research.py     # Deep research agent
│   │   ├── web_search.py        # Google web search
│   │   └── learning.py          # RAG: get_relevant_examples, format_learning_context
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # 6 endpoints
│   │   ├── users.py             # 4 endpoints
│   │   ├── chats.py             # 7 endpoints
│   │   ├── ai.py                # 2 endpoints (models + chat)
│   │   ├── learning.py          # 3 endpoints
│   │   ├── stats.py             # 1 endpoint
│   │   └── developer.py         # 2 endpoints
│   ├── services/
│   │   └── email_service.py     # Welcome + reset emails
│   └── utils/
│       ├── queue.py             # RequestQueue (asyncio.Semaphore)
│       └── logger.py            # Structured logging (app, agent, http)
└── tests/
    ├── conftest.py              # Fixtures: client, db, tokens, seeded data
    ├── test_auth.py
    ├── test_users.py
    ├── test_chats.py
    ├── test_learning.py
    ├── test_stats.py
    ├── test_developer.py
    ├── test_agent.py
    └── test_queue.py
```
