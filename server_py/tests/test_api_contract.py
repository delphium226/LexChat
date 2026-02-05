import pytest
import httpx
from datetime import datetime

BASE_URL = "http://localhost:80/api" # Node.js (Docker Port 80)
# BASE_URL = "http://localhost:8000/api" # Python (FastAPI default)

@pytest.fixture
def api_client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)

@pytest.fixture
def auth_header(api_client):
    """Authenticate and return headers"""
    # Create or ensure admin user exists (or just login if we assume seed data)
    # For now, let's try to login as admin/admin which is the default seed
    try:
        response = api_client.post("/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        if response.status_code == 200:
            token = response.json()["token"]
            return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass
    return None

def test_public_models_endpoint(api_client):
    response = api_client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check structure if possible, but list is enough for now

def test_login_success(api_client):
    response = api_client.post("/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["username"] == "admin"
    assert "role" in data["user"]

def test_login_failure(api_client):
    response = api_client.post("/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_get_me_authenticated(api_client, auth_header):
    if not auth_header:
        pytest.skip("Authentication failed, skipping authenticated test")
    
    response = api_client.get("/auth/me", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["username"] == "admin"

def test_get_me_unauthenticated(api_client):
    response = api_client.get("/auth/me")
    assert response.status_code in [401, 403] 

def test_list_chats(api_client, auth_header):
    if not auth_header:
        pytest.skip("Auth failed")
    response = api_client.get("/chats", headers=auth_header)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_chat(api_client, auth_header):
    if not auth_header:
        pytest.skip("Auth failed")
    payload = {"model": "llama3"}
    response = api_client.post("/chats", json=payload, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "llama3"
    assert "id" in data
    return data["id"]

def test_chat_lifecycle(api_client, auth_header):
    if not auth_header:
        pytest.skip("Auth failed")
    
    # 1. Create Chat
    chat_id = test_create_chat(api_client, auth_header)
    
    # 2. Add Message
    msg_payload = {"role": "user", "content": "Hello"}
    resp = api_client.post(f"/chats/{chat_id}/messages", json=msg_payload, headers=auth_header)
    assert resp.status_code == 200
    
    # 3. Get Messages
    resp = api_client.get(f"/chats/{chat_id}/messages", headers=auth_header)
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) >= 1
    assert msgs[-1]["content"] == "Hello"
    
    # 4. Update Chat Title
    new_title = "Updated Title"
    resp = api_client.put(f"/chats/{chat_id}", json={"title": new_title}, headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["title"] == new_title
    
    # 5. Delete Chat
    resp = api_client.delete(f"/chats/{chat_id}", headers=auth_header)
    assert resp.status_code == 200

def test_admin_users_endpoint(api_client, auth_header):
    # admin/admin should be admin role
    if not auth_header:
        pytest.skip("Auth failed")
        
    response = api_client.get("/users", headers=auth_header)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
