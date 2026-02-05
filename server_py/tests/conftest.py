import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import db

@pytest.fixture
def mock_db(monkeypatch):
    """Mock the database object methods on the singleton instance"""
    # We must patch the methods on the existing 'db' instance because other modules
    # have already imported it (singleton pattern).
    
    # Create mocks
    mock_connect = AsyncMock()
    mock_disconnect = AsyncMock()
    mock_fetch_all = AsyncMock(return_value=[])
    mock_fetch_one = AsyncMock(return_value=None)
    mock_execute = AsyncMock(return_value=None)
    
    # Apply patches to the 'db' instance
    monkeypatch.setattr(db, "connect", mock_connect)
    monkeypatch.setattr(db, "disconnect", mock_disconnect)
    monkeypatch.setattr(db, "fetch_all", mock_fetch_all)
    monkeypatch.setattr(db, "fetch_one", mock_fetch_one)
    monkeypatch.setattr(db, "execute", mock_execute)
    
    # Return a container object to allow tests to configure return values
    # We can just return 'db' itself, but better to return a simple holder 
    # that exposes the mocks for assertion.
    class MockDB:
        connect = mock_connect
        disconnect = mock_disconnect
        fetch_all = mock_fetch_all
        fetch_one = mock_fetch_one
        execute = mock_execute
        
    return MockDB()

@pytest.fixture
async def client(mock_db): # Request mock_db to ensure it's patched
    """Async client for testing"""
    # Override startup/shutdown to avoid real DB connection logic if any
    app.dependency_overrides = {}
    
    # Transport for in-process ASGI
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
