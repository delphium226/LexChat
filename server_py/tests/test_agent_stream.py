import pytest
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


@pytest.mark.asyncio
@patch("src.agent.ollama_client.process_user_request")
async def test_chat_endpoint_with_mock(mock_process, client: AsyncClient):
    """Test /api/chat endpoint with mocked agent to avoid Ollama dependency."""
    mock_process.return_value = {
        "role": "assistant",
        "content": "This is a mocked response.",
    }

    response = await client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "mistral",
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_chat_endpoint_missing_fields(client: AsyncClient):
    """Test /api/chat returns error for missing required fields."""
    response = await client.post(
        "/api/chat",
        json={"messages": [], "model": ""},
    )
    # Should still return 200 with SSE error or 422 validation error
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_models_endpoint(client: AsyncClient):
    """Test /api/models returns model list."""
    response = await client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]
    assert "context_length" in data[0]
