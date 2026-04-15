# Low-Level Design Document

## 1. Database Schema (PostgreSQL)

The application uses a relational database with three primary tables.

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
| `model` | VARCHAR(255) | | LLM model used for the chat |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Chat creation time |

### `messages`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | SERIAL | PRIMARY KEY | Unique message identifier |
| `chat_id` | INTEGER | FK -> chats(id) | Parent chat |
| `role` | VARCHAR(50) | NOT NULL | 'user' or 'assistant' |
| `content` | TEXT | NOT NULL | The message text |
| `rating` | INTEGER | CHECK (1-5) | User feedback score |
| `feedback_comment`| TEXT | | User feedback text |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Timestamp |

---

## 2. API Specification (REST)

All API routes (except `/auth`) require a valid JWT in the `Authorization` header (`Bearer <token>`).

### Auth (`/auth`)
-   `POST /signup`: Register a new user.
-   `POST /login`: Authenticate and receive JWT.

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
-   **Tools** (defined in `server_py/src/agent/tools.py`):
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

The application is deployed as a set of Docker containers orchestrated by Docker Compose.

### 5.1 Services
1.  **Frontend (`lexchat-frontend`)**:
    -   **Base Image**: `nginx:alpine`
    -   **Role**: Serves the static React application build (`/usr/share/nginx/html`) and proxies API requests.
    -   **Configuration**: `nginx.conf` defines routing rules.
    -   **Port**: Exposed on host port 80.

2.  **Backend (`lexchat-backend`)**:
    -   **Base Image**: `python:3.11-slim`
    -   **Role**: Hosts the FastAPI application.
    -   **Port**: Exposed on host port 8000 (for direct API access/Swagger UI).
    -   **Dependencies**: Connects to `db` and `ollama`.

3.  **Database (`lexchat-db`)**:
    -   **Image**: `postgres:15`
    -   **Role**: Persistent data storage.

4.  **AI Inference (`lexchat-ollama`)**:
    -   **Image**: `ollama/ollama`
    -   **Role**: Local LLM inference engine.

### 5.2 Traffic Flow
1.  **User Request** -> Host Port 80 -> **Nginx (Frontend)**.
2.  **Static Asset** -> Nginx serves file from local volume.
3.  **API Request (`/api/*`)** -> Nginx proxies to `http://backend:8000`.
4.  **Backend Processing** -> FastAPI handles request, queries DB/Ollama.
