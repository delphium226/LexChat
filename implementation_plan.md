# Implementation Plan: Split Architecture with FastAPI Backend

## Goal
Transition the current Node.js backend to a Python **FastAPI** architecture.
The backend will become a robust API server (`server_py`) supporting the existing React frontend (`client`).

**Architecture Shift**:
- **Current**: React (Client) <-> Node/Express (Monolith API + Static Serving) <-> Postgres & Ollama
- **Target**: React (Client) <-> **FastAPI** (Pure API) <-> Postgres & Ollama

## User Review Required
> [!IMPORTANT]
> **breaking-change**: The backend port will change from **3000** to **8000**.
> - I will update `client/vite.config.js` to proxy to 8000.
> - I will update `docker-compose.yml` to map port 8000.
> - **Action Required**: You may need to rebuild your docker containers.

## TDD Strategy
We will follow a strict **Red-Green-Refactor** cycle for migrating the backend. Since the API contract is already defined (by the existing Node.js app), we can write precise tests asserting that contract before writing the Python code.

**Cycle per Module**:
1.  **Red**: Create `test_<module>.py` defining the requests and expected JSON responses (based on current Node.js behavior). Run and confirm failure.
2.  **Green**: Implement the minimal FastAPI code (Routers/Schemas) to make the test pass.
3.  **Refactor**: Optimize and clean up implementation.

## Proposed Changes

### 1. Foundation
- **[NEW] `server_py/requirements.txt`**: Define dependencies (`fastapi`, `pytest`, `httpx`, `asyncpg`, etc.).
- **[NEW] `server_py/src/main.py`**: Minimal invalid app skeleton.
- **[NEW] `server_py/src/config.py`**: Settings management.
- **[NEW] `server_py/tests/conftest.py`**: Setup `TestClient` and temporary/mocked DB fixtures.

### 2. Authentication (TDD)
- **[NEW] `server_py/tests/test_auth.py`**:
    - `test_login_success`: POST /api/auth/login -> 200, returns token + user, sets cookie.
    - `test_login_failure`: Invalid creds -> 401.
    - `test_me_endpoint`: GET /api/auth/me With Token -> 200, matches user.
- **[NEW] `server_py/src/routers/auth.py` & `dependencies.py`**: Implement login logic, JWT issuing, and dependency injection to pass tests.

### 3. Database & Users (TDD)
- **[NEW] `server_py/tests/test_users.py`**:
    - `test_create_user`: POST /api/users -> 201.
    - `test_list_users`: GET /api/users (Admin) -> 200 list.
- **[NEW] `server_py/src/database.py`**: Implement `AsyncSession`, `initializeDB` (schema creation).
- **[NEW] `server_py/src/routers/users.py`**: Implement CRUD logic.

### 4. Chat Management (TDD)
- **[NEW] `server_py/tests/test_chats.py`**:
    - `test_create_chat`: POST /api/chats -> 200.
    - `test_get_history`: GET /api/chats/:id/messages -> 200 list.
- **[NEW] `server_py/src/routers/chats.py`**: Implement chat persistence logic.

### 5. AI Agent & Streaming (TDD)
- **[NEW] `server_py/tests/test_agent_stream.py`**:
    - `test_chat_stream`: POST /api/chat -> 200 (Stream).
        - *Mock*: Mock the `ollama.client` to yield chunks.
        - *Assert*: Response is `text/event-stream` and contains expected `data: {...}` chunks.
- **[NEW] `server_py/src/agent/`**:
    - Implement `ollama_client.py` with streaming support.
    - Implement `queue_manager.py` for concurrency control.
    - Connect to `routers/ai_routes.py`.

### 6. Infrastructure
- **[MODIFY] `docker-compose.yml`**: Switch service to Python.
- **[MODIFY] `client/vite.config.js`**: Update proxy port to 8000.

## Verification Plan

### Automated Tests (`server_py/tests/`)
- `test_auth.py`: Verify login returns valid JWT.
- `test_chat_flow.py`: Mock Ollama and verify SSE stream basics.

### Manual Verification
1.  **Auth**: UI Login/Logout works. Protected routes reject missing cookies.
2.  **Legacy Data**: Old chats from Postgres are visible (schema is identical).
3.  **Chat Stream**:
    - Send message.
    - Verify "queue position" updates show up.
    - Verify partial token streaming works.
    - Verify tool use (if triggered) shows in logs/UI.
