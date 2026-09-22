import pytest
from httpx import AsyncClient

from src.models import User


@pytest.mark.asyncio
async def test_list_chats_unauthorized(client: AsyncClient):
    response = await client.get("/api/chats/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_lifecycle(client: AsyncClient, seed_user: User, user_token: str):
    headers = {"Authorization": f"Bearer {user_token}"}

    # List chats (empty)
    response = await client.get("/api/chats/", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    # Create chat
    response = await client.post(
        "/api/chats/",
        json={"model": "mistral", "title": "Test Chat"},
        headers=headers,
    )
    assert response.status_code == 200
    chat = response.json()
    assert chat["model"] == "mistral"
    assert chat["title"] == "Test Chat"
    chat_id = chat["id"]

    # Get messages (empty)
    response = await client.get(f"/api/chats/{chat_id}/messages", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    # Add message
    response = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"role": "user", "content": "Hello"},
        headers=headers,
    )
    assert response.status_code == 200
    msg = response.json()
    assert msg["content"] == "Hello"
    assert msg["role"] == "user"

    # Get messages (one)
    response = await client.get(f"/api/chats/{chat_id}/messages", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Update chat title
    response = await client.put(
        f"/api/chats/{chat_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

    # Delete chat
    response = await client.delete(f"/api/chats/{chat_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Chat deleted"

    # Verify deleted
    response = await client.get(f"/api/chats/{chat_id}/messages", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rate_message(client: AsyncClient, seed_user: User, user_token: str):
    headers = {"Authorization": f"Bearer {user_token}"}

    # Create chat and message
    chat_resp = await client.post(
        "/api/chats/",
        json={"model": "mistral"},
        headers=headers,
    )
    chat_id = chat_resp.json()["id"]

    msg_resp = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"role": "assistant", "content": "Here is the law..."},
        headers=headers,
    )
    msg_id = msg_resp.json()["id"]

    # Rate message
    response = await client.put(
        f"/api/chats/messages/{msg_id}/rating",
        json={"rating": 5, "comment": "Great answer"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rating"] == 5
    assert data["feedback_comment"] == "Great answer"


@pytest.mark.asyncio
async def test_message_modes_round_trip(client: AsyncClient, seed_user: User, user_token: str):
    """P4.1 (B7): the modes an assistant message ran under are persisted and
    come back on every read, so the next turn's history can carry them and
    the backend can see a change. NULL where the client did not stamp them."""
    headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = (await client.post("/api/chats/", json={"model": "m"}, headers=headers)).json()["id"]

    stamped = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"role": "assistant", "content": "Covers legislation only.",
              "research_mode": "legislation_only", "chat_mode": "conversational"},
        headers=headers,
    )
    assert stamped.status_code == 200
    assert stamped.json()["research_mode"] == "legislation_only"
    assert stamped.json()["chat_mode"] == "conversational"
    unstamped = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"role": "user", "content": "I have changed it"},
        headers=headers,
    )
    assert unstamped.json()["research_mode"] is None

    rows = (await client.get(f"/api/chats/{chat_id}/messages", headers=headers)).json()
    assert [(r["research_mode"], r["chat_mode"]) for r in rows] == [
        ("legislation_only", "conversational"), (None, None),
    ]
    # Rating a message returns the full row, stamps included.
    rated = await client.put(
        f"/api/chats/messages/{rows[0]['id']}/rating",
        json={"rating": 4}, headers=headers,
    )
    assert rated.json()["research_mode"] == "legislation_only"
    assert rated.json()["chat_mode"] == "conversational"


@pytest.mark.asyncio
async def test_rate_message_invalid_rating(client: AsyncClient, seed_user: User, user_token: str):
    headers = {"Authorization": f"Bearer {user_token}"}

    chat_resp = await client.post(
        "/api/chats/",
        json={"model": "mistral"},
        headers=headers,
    )
    chat_id = chat_resp.json()["id"]

    msg_resp = await client.post(
        f"/api/chats/{chat_id}/messages",
        json={"role": "assistant", "content": "Response"},
        headers=headers,
    )
    msg_id = msg_resp.json()["id"]

    # Invalid rating
    response = await client.put(
        f"/api/chats/messages/{msg_id}/rating",
        json={"rating": 6},
        headers=headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_not_found(client: AsyncClient, seed_user: User, user_token: str):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.get("/api/chats/99999/messages", headers=headers)
    assert response.status_code == 404
