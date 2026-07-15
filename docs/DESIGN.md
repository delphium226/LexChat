# Low-Level Design Document

## 1. Database Schema (PostgreSQL)

The three tables below are the **core** conversational schema. The full schema (defined in
`server_py/src/models.py`) also includes `app_settings` (runtime provider config), `activity_log`,
`peer_bots` (federation registry), `product_feedback`, `service_health_logs`, `matters` /
`matter_notes`, `documents`, `request_timings`, and the parliament-bot FTS tables
`sp_committee_items` / `sp_plenary_items` / `sp_video_captions`. See `ARCHITECTURE.md` for the
entity overview.

### `users`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique user identifier |
| `username` | VARCHAR(255) | UNIQUE, NOT NULL | Login username |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| `email` | VARCHAR(255) | UNIQUE | Contact email |
| `role` | VARCHAR(50) | DEFAULT 'user' | 'admin' or 'user' |
| `dark_mode` | BOOLEAN | DEFAULT FALSE | UI preference |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Account creation time |

### `chats`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique chat identifier |
| `user_id` | INTEGER | FK -> users(id) | Owner of the chat |
| `title` | TEXT | | Chat title (auto-generated or user set) |
| `model` | VARCHAR(255) | | LLM model selected at chat creation |
| `provider` | VARCHAR(50) | | LLM provider at chat creation (`ollama`/`openrouter`) |
| `matter_id` | INTEGER | FK -> matters(id), NULL | Optional owning matter (workspace) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Chat creation time |

### `messages`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique message identifier |
| `chat_id` | INTEGER | FK -> chats(id) | Parent chat |
| `role` | VARCHAR(50) | NOT NULL | 'user' or 'assistant' |
| `content` | TEXT | NOT NULL | The message text |
| `model` | VARCHAR(255) | | Model actually used at inference time (assistant messages) |
| `provider` | VARCHAR(50) | | Provider actually used at inference time (assistant messages) |
| `cost_usd` | NUMERIC | | Estimated inference cost for the message |
| `rating` | INTEGER | CHECK (1-5) | User feedback score |
| `feedback_comment`| TEXT | | User feedback text |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Timestamp |

---

## 2. API Specification (REST)

> This is a high-level sketch. **`docs/api/ServerAPISpec.md` is the authoritative, up-to-date
> endpoint reference** (auth rules, request/response shapes, and the newer federation, peers,
> identity, matters, documents, and activity-log endpoints).

All API routes (except `/api/auth/login`, `/api/health`, and the identity endpoints) require a
valid JWT — supplied as an HTTP-only cookie on login or an `Authorization: Bearer <token>` header.

### Auth (`/api/auth`)
-   `POST /login`: Authenticate and receive JWT (also sets an HTTP-only cookie).
-   `POST /logout`, `GET /me`, `POST /change-password`, `PUT /preferences`.
-   There is **no public signup** — the seeded `admin` account creates users via the Admin Portal.

### Chats (`/api/chats`)
-   `GET /`: List all chats for current user.
-   `POST /`: Create a new chat session.
-   `PUT /:id`: Rename a chat.
-   `DELETE /:id`: Delete a chat.

### Messages (`/api/chats/:id/messages`)
-   `GET /`: Get full history of a chat.
-   `POST /`: Send a user message.
    -   **Logic**: This triggers the Agent pipeline. The response will be the Assistant's reply.
-   `PUT /:msgId/rating`: Submit feedback (1-5 stars) and comment.

### Learning & Admin (`/api/learning`)
-   **Auth**: Requires `role = 'admin'`.
-   `GET /feedback`: List recent rated messages.
-   `GET /stats`: Aggregated performance metrics (ratings over time).
-   `POST /test`: Test the RAG retrieval logic for a given query.

---

## 3. Agent Architecture (Server-Side)

The backend implements a **Manager-Worker** pattern to handle complex queries.

### 3.1 Manager Agent
-   **System Prompt**: Defined in `server_py/src/config.py` (`MANAGER_SYSTEM_PROMPT`).
-   **Tools**:
    -   `delegate_research(query)`: Hand off legal queries to the Worker. The `query` parameter must be a self-contained research brief including Act names, years, jurisdiction constraints, and any relevant conversational context — the Worker has no access to conversation history.
-   **Flow**:
    1.  Receives user message.
    2.  Injects relevant RAG feedback from prior rated interactions (learning loop).
    3.  Triages: general conversation (answer directly) vs. legal query (delegate).
    4.  If delegating: formulates a context-enriched research brief and calls `delegate_research`.
    5.  Presents the Worker's findings verbatim, preserving all citations.

### 3.2 Worker Agent
-   **System Prompt**: Defined in `server_py/src/config.py` (`WORKER_SYSTEM_PROMPT`). Strict citation and source-grounding rules; ephemeral context (no conversation history).
-   **Tools** (defined in the `server_py/src/agent/tools/` package — `schemas.py`, `lex.py`, `parliament.py`, `caselaw.py`, `executor.py`). The legislation toolset is:
    -   `search_legislation(query, year_from?, year_to?)`: Search UK Acts and SIs by title or keyword. Returns metadata and short excerpts; does **not** download full text.
    -   `search_legislation_sections(query, legislation_id)`: Search for specific sections within a known Act. **Preferred over `get_legislation_text`** for targeted questions — avoids downloading the entire Act.
    -   `get_legislation_text(legislation_id)`: Retrieve the full text of an Act. Fallback only — used when section search returns insufficient results, or when the full structure of an Act is required.
-   **Flow**:
    1.  Receives the research brief from the Manager (isolated context — no chat history).
    2.  Calls `search_legislation` to identify candidate Acts and obtain `legislation_id`s.
    3.  Calls `search_legislation_sections` scoped to each relevant Act to retrieve matching provisions directly.
    4.  Falls back to `get_legislation_text` only if section search yields nothing useful.
    5.  Iterates with alternative search terms if results are sparse.
    6.  Returns a structured, cited markdown answer (BLUF → Analysis → Jurisdiction → References).

### 3.3 Learning Loop (RAG)
-   **Ingest**: When a user rates a message (4-5 stars), it becomes a "Positive Example".
-   **Critique**: When a user rates a message (1-3 stars) + Comment, it becomes a "Negative Constraint".
-   **Retrieval**: On each new message, the system embeds the query and searches `messages` table for semantically similar past feedback.

---

## 4. Frontend Architecture (React)

### Directory Structure
-   `src/components/`: Reusable UI (Button, Input, Modal).
-   `src/pages/`:
    -   `ChatPage`: Main interface. Sidebar (List Chats), Main Area (Message List).
    -   `AdminDashboard`: Protected route. Graphs and tables.
    -   `LoginPage` / `SignupPage`.
-   `src/services/api.js`: Central Axios instance with Interceptors for JWT handling.
-   `src/context/AuthContext.jsx`: Provides `user` state and `login/logout` methods app-wide.

### Key Libraries
-   **State**: React `useState`, `useContext`.
-   **Routing**: `react-router-dom`.
-   **Styling**: `tailwindcss`.
-   **Markdown**: `react-markdown` + `remark-gfm` (for tables/citations).
-   **Charts**: `recharts` (for Admin visuals).

---

## 5. Deployment Architecture

The application is deployed **natively on Windows Server 2022 — no Docker, no WSL, no nginx.**
Everything runs as native processes/services. See `docs/deployment/NATIVE_DEPLOYMENT.md` for the
full guide and `ARCHITECTURE.md` for the deployment view.

### 5.1 Processes / services
1.  **FastAPI backend (uvicorn)** — the single application entry point. Serves the pre-built React
    frontend (`client/dist/`) as static files **and** the `/api` backend from one process. Listens
    on **HTTPS port 443** in production (organisational TLS certs in `deployment/certs/`); HTTP
    port 8000 in local dev.
2.  **PostgreSQL 15** — runs as a Windows service; listens on `localhost:5432` only.
3.  **Ollama** — local inference process/proxy on `localhost:11434`; forwards `:cloud`-tagged models
    to remote inference providers. Only used when Ollama is the active provider (OpenRouter calls
    `openrouter.ai` directly).

The frontend is **pre-built on the dev machine and committed** (`client/dist/`); the target server
needs no Node.js. Start/stop is scripted via `deployment/start_native.cmd` /
`deployment/stop_native.cmd` (PostgreSQL → Ollama → uvicorn).

### 5.2 Traffic flow
1.  **User request** → HTTPS port 443 → **uvicorn**.
2.  **Static asset** → uvicorn serves the file from `client/dist/`.
3.  **API request (`/api/*`)** → handled in-process by FastAPI, which queries PostgreSQL and the
    active LLM provider (Ollama or OpenRouter) plus external research APIs (LEX, National Archives,
    Scottish Parliament sources).

### 5.3 Multi-bot & updates
Each bot is an **independent uvicorn process** with its own database and port, differentiated by
configuration (`bots/<id>/`), not forked code; bots can consult each other via federation
(`POST /api/consult`). Updates are delivered by `git pull` from `origin/main` (there is no
zip/file-transfer deployment).
