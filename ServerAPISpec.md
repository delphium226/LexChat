# LexChat — Server API Specification

**Base URL**: `/api`

Interactive docs (local dev only):
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Authentication

JWT-based. Token delivered via HTTP-only cookie on login, or passed as `Authorization: Bearer <token>` header.

All protected endpoints return `401` if unauthenticated, `403` if authenticated but insufficient role.

---

## 1. Auth (`/api/auth`)

### POST `/api/auth/login` — Public
```json
// Request
{ "username": "string", "password": "string", "rememberMe": false }

// Response 200
{
  "token": "jwt_string",
  "user": { "id": 1, "username": "string", "role": "user|admin", "dark_mode": false, "research_mode": "legislation_only" }
}
```
Also sets an HTTP-only `token` cookie.

### POST `/api/auth/logout` — Public
Clears the `token` cookie. Returns `{ "message": "Logged out successfully" }`.

### GET `/api/auth/me` — Auth required
Returns current user object (same shape as login response `user`).

### POST `/api/auth/reset-password-request` — Public
```json
// Request
{ "username": "string" }
// Response 200 — always 200 regardless of whether user exists (prevents enumeration)
{ "message": "If that username exists, a reset has been initiated." }
```

### POST `/api/auth/change-password` — Auth required
```json
// Request
{ "currentPassword": "string", "newPassword": "string" }
// Response 200
{ "message": "Password updated successfully" }
```

### PUT `/api/auth/preferences` — Auth required
```json
// Request (all fields optional)
{ "dark_mode": true, "research_mode": "legislation_only|case_law|combined" }
// Response 200
{ "message": "Preferences updated" }
```

---

## 2. Chats (`/api/chats`) — Auth required

### GET `/api/chats`
Returns array of chat objects ordered by `created_at DESC`.
```json
[{
  "id": 1, "user_id": 1, "title": "string", "model": "string",
  "provider": "ollama|openrouter", "matter_id": null, "created_at": "ISO8601"
}]
```

### POST `/api/chats`
```json
// Request
{ "title": "string (optional)", "model": "string", "provider": "string (optional)" }
// Response 200 — created chat object
```

### PUT `/api/chats/{id}`
```json
// Request
{ "title": "string" }
// Response 200 — updated chat object
```

### DELETE `/api/chats/{id}`
Returns `{ "message": "Chat deleted" }`.

### GET `/api/chats/{id}/messages`
Returns array of message objects ordered by `created_at ASC`.
```json
[{
  "id": 1, "chat_id": 1, "role": "user|assistant",
  "content": "string", "model": "string|null", "provider": "string|null",
  "rating": null, "feedback_comment": null, "cost_usd": null,
  "created_at": "ISO8601"
}]
```

### POST `/api/chats/{id}/messages`
```json
// Request
{ "role": "user|assistant", "content": "string", "model": "string|null", "provider": "string|null", "cost_usd": 0.0012 }
// Response 200 — created message object
```

### PUT `/api/chats/messages/{id}/rating` — Auth required
```json
// Request
{ "rating": 4, "comment": "string (optional)" }
// Response 200 — updated message object
```

---

## 3. AI (`/api`)

### GET `/api/models` — Public
Returns the active provider's model list with `active: true` on the configured default model.
```json
[{ "name": "mistral-large-3:675b-cloud", "label": "Mistral Large 3", "active": true }]
```

### POST `/api/chat` — Public (auth not enforced at API level; conversation filtering is client-side)
SSE streaming endpoint. Each event is `data: {...}\n\n`.
```json
// Request
{
  "messages": [{ "role": "user", "content": "..." }],
  "model": "string",
  "num_ctx": 262144,
  "research_mode": "legislation_only|case_law|combined"
}
```

SSE event types:
| Type | Shape | Description |
|---|---|---|
| `token` | `{ "type": "token", "content": "..." }` | Streamed token from Manager |
| `status` | `{ "type": "status", "message": "..." }` | Agent status update (e.g. "Research Agent starting...") |
| `tool_start` | `{ "type": "tool_start", "tool": "..." }` | Tool execution beginning |
| `tool_end` | `{ "type": "tool_end", "tool": "...", "result": "..." }` | Tool execution complete |
| `timing` | `{ "type": "timing", ... }` | Request performance breakdown |
| `result` | `{ "type": "result", "message": { "role": "assistant", "content": "...", "model": "...", "provider": "...", "cost_usd": 0.002 } }` | Final response |
| `error` | `{ "type": "error", "error": "..." }` | Error occurred |

---

## 4. System Chat (`/api/system`) — Public

### POST `/api/system/chat`
Machine-to-machine variant of `/api/chat`. Relays all internal SSE events including tool calls and API call start/end events. Same request shape as `/api/chat`. Additional event types:
- `tool_call` — model's tool call payload
- `api_call_start` / `api_call_end` — LEX API request/response details

---

## 5. Users (`/api/users`) — Admin only

### GET `/api/users`
Returns array of all users.

### POST `/api/users`
```json
{ "username": "string", "password": "string", "role": "user|admin", "email": "string (optional)" }
```

### PUT `/api/users/{id}`
Partial update — any combination of `username`, `role`, `email`, `password`.

### DELETE `/api/users/{id}`
Returns `{ "message": "User deleted" }`.

---

## 6. Learning & Feedback (`/api/learning`) — Admin only

### GET `/api/learning/feedback`
Returns recent messages with user ratings and comments.

### GET `/api/learning/stats`
Query param: `days` (integer or `"all"`). Returns aggregate ratings by day and model.

### POST `/api/learning/test`
```json
// Request
{ "query": "string" }
// Response — RAG retrieval results: examples and critiques matched to the query
```

---

## 7. Statistics (`/api/stats`) — Admin only

### GET `/api/stats/usage`
Query param: `days` (integer). Returns KPIs, daily activity, model breakdown, top users.
```json
{
  "kpi": { "users": 12, "chats": 340, "messages": 2100, "activeUsers": 8 },
  "activity": [...],
  "models": [...],
  "topUsers": [...]
}
```

### GET `/api/stats/performance`
Query param: `days`. Returns request timing breakdowns (queue wait, LLM ms, LEX API ms, total ms).

### GET `/api/stats/cost`
Query param: `days`. Returns per-day cost totals and per-model cost breakdown from `Message.cost_usd`.

---

## 8. Developer Tools (`/api/developer`) — Admin only

### GET `/api/developer/provider-config`
Returns current settings for both providers:
```json
{
  "active_provider": "ollama",
  "ollama": { "base_url": "...", "api_key": "...", "model": "...", "summarisation_model": "...", "temperature": 0.3, "max_concurrent_requests": 2, "max_summarise_concurrency": 1 },
  "openrouter": { ... }
}
```

### POST `/api/developer/provider-config`
```json
{ "provider": "ollama|openrouter", "config": { ...same fields... } }
```

### POST `/api/developer/active-provider`
```json
{ "active_provider": "ollama|openrouter" }
```

### GET `/api/developer/openrouter-models`
Returns the curated OpenRouter model list from `config.py`.

### POST `/api/developer/seed`
Generates ~100 synthetic users with 6 months of chat history. Returns `{ "success": true, "stats": { ... } }`.

### POST `/api/developer/reset`
Deletes all data except the `admin` user. Irreversible.

### POST `/api/developer/clear-usage`
Deletes all `RequestTiming` rows.

### POST `/api/developer/clear-performance`
Deletes performance-related data.

---

## 9. Health (`/api/health`)

### GET `/api/health` — Public
Simple liveness check. Returns `{ "status": "healthy" }`.

### GET `/api/health/status` — Auth required
Returns the latest health check result for each monitored service (Ollama, LEX API, PostgreSQL).
```json
[{ "service_name": "ollama", "is_healthy": true, "latency_ms": 230, "error_message": null, "checked_at": "ISO8601" }]
```

### GET `/api/health/history` — Auth required
Query params: `service` (string), `limit` (integer, default 100). Returns historical health check log for a service.

### POST `/api/health/trigger` — Admin only
Triggers an immediate health check cycle for all services.

---

## 10. Product Feedback (`/api/feedback`)

### POST `/api/feedback` — Auth required
```json
{ "message": "string" }
```

### GET `/api/feedback` — Admin only
Returns all product feedback messages with user info.
