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
-   **System Prompt**: Defined in `config.js`.
-   **Tools**:
    -   `delegate_research(query)`: Hand off legal queries to the Worker.
-   **Flow**:
    1.  Receives User Message.
    2.  Checks "Memory" (RAG) for similar past Q&A.
    3.  Decides: Answer directly (chat) OR Delegate (research).
    4.  If Delegate: Calls `delegate_research`.
    5.  Formats final response.

### 3.2 Worker Agent
-   **System Prompt**: Strict legal citation rules.
-   **Tools**:
    -   `lex_api_search`: Semantic search on legislation/case law.
    -   `web_search`: Google search for broader context.
    -   `read_url`: Scrape content for reading.
-   **Flow**:
    1.  Receives query from Manager.
    2.  Loops: Plan -> Search -> Read -> Analyze.
    3.  Returns: Cited, markdown answer.

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
