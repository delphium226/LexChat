import pytest
from httpx import AsyncClient

from src.models import User


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_user: User):
    response = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "testuser"
    assert data["user"]["role"] == "user"
    assert "dark_mode" in data["user"]


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, seed_user: User, user_token: str):
    response = await client.post(
        "/api/auth/change-password",
        json={"currentPassword": "testpassword", "newPassword": "newpass123"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, seed_user: User, user_token: str):
    response = await client.post(
        "/api/auth/change-password",
        json={"currentPassword": "wrongpassword", "newPassword": "newpass123"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, seed_user: User, user_token: str):
    response = await client.put(
        "/api/auth/preferences",
        json={"dark_mode": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200

    # Verify it persisted
    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert me.json()["user"]["dark_mode"] is True


@pytest.mark.asyncio
async def test_reset_password_request(client: AsyncClient, seed_user: User):
    response = await client.post(
        "/api/auth/reset-password-request",
        json={"username": "testuser"},
    )
    assert response.status_code == 200
    # Always returns generic message
    assert "password reset email" in response.json()["message"].lower()
