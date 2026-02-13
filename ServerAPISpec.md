# Server API Specification

## Overview
This document outlines the API endpoints for the LexChat server. The server uses **FastAPI (Python)** and communicates with a PostgreSQL database.

**Base URL**: `/api` (implicitly relative to the server root)

### Interactive Documentation
The API provides auto-generated interactive documentation, accessible when running locally with the backend port exposed:
*   **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Authentication
Authentication is handled via JWT (JSON Web Tokens).
*   **Method**: Bearer Token in `Authorization` header OR `token` cookie.
*   **Header Format**: `Authorization: Bearer <token>`
*   **Middleware**: `authenticateToken` validates the token. `isAdmin` restricts access to users with `role: 'admin'`.

---

## 1. Authentication & Session (`/api/auth`)

### Login
*   **Endpoint**: `POST /api/auth/login`
*   **Public**: Yes
*   **Body**:
    ```json
    {
      "username": "string",
      "password": "string",
      "rememberMe": "boolean (optional)"
    }
    ```
*   **Response**: `200 OK`
    ```json
    {
      "token": "jwt_token_string",
      "user": {
        "id": "integer",
        "username": "string",
        "role": "string",
        "dark_mode": "boolean"
      }
    }
    ```
    *Note: Also sets an HTTP-only `token` cookie.*

### Logout
*   **Endpoint**: `POST /api/auth/logout`
*   **Public**: Yes
*   **Response**: `200 OK`
    ```json
    { "message": "Logged out successfully" }
    ```
    *Note: Clears the `token` cookie.*

### Get Current User
*   **Endpoint**: `GET /api/auth/me`
*   **Auth Required**: Yes
*   **Response**: `200 OK`
    ```json
    {
      "user": {
        "id": "integer",
        "username": "string",
        "role": "string",
        "dark_mode": "boolean"
      }
    }
    ```

### Request Password Reset
*   **Endpoint**: `POST /api/auth/reset-password-request`
*   **Public**: Yes
*   **Body**: `{"username": "string"}`
*   **Response**: `200 OK`
    ```json
    { "message": "If user exists, a password reset email has been sent." }
    ```

### Change Password
*   **Endpoint**: `POST /api/auth/change-password`
*   **Auth Required**: Yes
*   **Body**:
    ```json
    {
      "currentPassword": "string",
      "newPassword": "string"
    }
    ```
*   **Response**: `200 OK` `{"message": "Password updated successfully"}`

### Update Preferences
*   **Endpoint**: `PUT /api/auth/preferences`
*   **Auth Required**: Yes
*   **Body**: `{"dark_mode": "boolean"}`
*   **Response**: `200 OK` `{"message": "Preferences updated"}`

---

## 2. Chat Management (`/api/chats`)

**All endpoints require Authentication.**

### List Chats
*   **Endpoint**: `GET /api/chats`
*   **Response**: `200 OK` - Array of chat objects.
    ```json
    [
      {
        "id": "integer",
        "user_id": "integer",
        "title": "string",
        "model": "string",
        "created_at": "timestamp"
      }
    ]
    ```

### Create Chat
*   **Endpoint**: `POST /api/chats`
*   **Body**:
    ```json
    {
      "title": "string (optional)",
      "model": "string"
    }
    ```
*   **Response**: `200 OK` - The created chat object.

### Update Chat (Title)
*   **Endpoint**: `PUT /api/chats/:id`
*   **Body**: `{"title": "string"}`
*   **Response**: `200 OK` - The updated chat object.

### Delete Chat
*   **Endpoint**: `DELETE /api/chats/:id`
*   **Response**: `200 OK` `{"message": "Chat deleted"}`

### Get Messages
*   **Endpoint**: `GET /api/chats/:id/messages`
*   **Response**: `200 OK` - Array of message objects.
    ```json
    [
      {
        "id": "integer",
        "chat_id": "integer",
        "role": "string (user/assistant)",
        "content": "string",
        "rating": "integer (nullable)",
        "feedback_comment": "string (nullable)",
        "created_at": "timestamp"
      }
    ]
    ```

### Add Message
*   **Endpoint**: `POST /api/chats/:id/messages`
*   **Body**:
    ```json
    {
      "role": "string",
      "content": "string"
    }
    ```
*   **Response**: `200 OK` - The created message object.

### Rate Message
*   **Endpoint**: `PUT /api/chats/messages/:id/rating`
*   **Body**:
    ```json
    {
      "rating": "integer (1-5)",
      "comment": "string (optional)"
    }
    ```
*   **Response**: `200 OK` - The updated message object.

---

## 3. User Administration (`/api/users`)

**Require Authentication + Admin Role.**

### List Users
*   **Endpoint**: `GET /api/users`
*   **Response**: `200 OK` - Array of user objects.

### Create User
*   **Endpoint**: `POST /api/users`
*   **Body**:
    ```json
    {
      "username": "string",
      "password": "string",
      "role": "string (user/admin)",
      "email": "string"
    }
    ```
*   **Response**: `201 Created` - The created user object.

### Update User
*   **Endpoint**: `PUT /api/users/:id`
*   **Body**: User fields to update (username, role, email, password).
*   **Response**: `200 OK` - The updated user object.

### Delete User
*   **Endpoint**: `DELETE /api/users/:id`
*   **Response**: `200 OK` `{"message": "User deleted"}`

---

## 4. Learning & Feedback (`/api/learning`)

**Require Authentication + Admin Role.**

### Get Feedback
*   **Endpoint**: `GET /api/learning/feedback`
*   **Description**: Retrieves recent messages that have user ratings/comments.
*   **Response**: `200 OK` - Array of feedback objects.

### Get Stats
*   **Endpoint**: `GET /api/learning/stats`
*   **Query Params**: `days` (string, e.g., '30' or 'all').
*   **Description**: Aggregate ratings by day and model.
*   **Response**: `200 OK` - Array of stats objects.

### Test Retrieval
*   **Endpoint**: `POST /api/learning/test`
*   **Body**: `{"query": "string"}`
*   **Response**: `200 OK` - RAG retrieval results.

---

## 5. Developer Tools (`/api/developer`)

**(Ideally should be restricted, but code is currently public/available if defined)**

### Seed Data
*   **Endpoint**: `POST /api/developer/seed`
*   **Description**: Generates synthetic users and chat history.
*   **Response**: `200 OK` `{"success": true, "stats": {...}}`

### Reset Database
*   **Endpoint**: `POST /api/developer/reset`
*   **Description**: Deletes all data except the 'admin' user.
*   **Response**: `200 OK`

---

## 6. Statistics (`/api/stats`)

**Require Authentication + Admin Role.**

### Get Usage Stats
*   **Endpoint**: `GET /api/stats/usage`
*   **Query Params**: `days` (string, e.g., '30' or 'all').
*   **Response**: `200 OK`
    ```json
    {
      "kpi": { "users": int, "chats": int, "messages": int, "activeUsers": int },
      "activity": [...],
      "models": [...],
      "topUsers": [...]
    }
    ```

---

## 7. Model & Chat Operations (Root Level)

### List Models
*   **Endpoint**: `GET /api/models`
*   **Public**: Yes
*   **Response**: `200 OK` - List of available LLM models.

### Chat Stream
*   **Endpoint**: `POST /api/chat`
*   **Public**: Yes
*   **Body**:
    ```json
    {
      "messages": [{"role": "user", "content": "..."}],
      "model": "string",
      "num_ctx": "integer (optional)",
      "deep_research": "boolean (optional)"
    }
    ```
*   **Response**: `200 OK` (Streamed SSE)
    *   Events: `data: { "type": "token", "content": "..." }`, `data: { "type": "result", "message": "..." }`

---

## 8. System Health (`/api/health`)

### Health Check
*   **Endpoint**: `GET /api/health`
*   **Public**: Yes
*   **Response**: `200 OK`
    ```json

---

## 9. System-to-System Chat (`/api/system`)

### System Chat
*   **Endpoint**: `POST /api/system/chat`
*   **Description**: A chat endpoint tailored for machine-to-machine communication. It relays all LLM events including detailed tool calls and results, allowing the connecting system to "see" the agent's thought process and actions.
*   **Public**: Yes (currently, similar to `/api/chat`)
*   **Body**:
    ```json
    {
      "messages": [{"role": "user", "content": "..."}],
      "model": "string",
      "num_ctx": "integer (optional)"
    }
    ```
*   **Response**: `200 OK` (Streamed SSE)
    *   **Events**:
        *   `data: { "type": "token", "content": "..." }` - Standard token stream.
        *   `data: { "type": "tool_call", "tool_calls": [...] }` - Emitted when the model decides to call a tool. Contains the full tool call payload (name, arguments).
        *   `data: { "type": "tool_start", "tool": "..." }` - Emitted when a tool execution begins.
        *   `data: { "type": "tool_end", "tool": "...", "result": "..." }` - Emitted when a tool execution finishes.
        *   `data: { "type": "tool_result", "tool": "...", "result": "..." }` - Emitted with the final output of the tool call (e.g. the research report).
        *   `data: { "type": "result", "message": "..." }` - Final assistant response.
