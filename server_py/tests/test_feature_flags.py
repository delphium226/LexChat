"""Feature-flag endpoint tests (D6): cache toggles alongside matters_enabled.

Backward compatibility is the point — an old saved `features` JSON and an old
client POST body (matters_enabled only) must both keep working, with the new
cache flags defaulting to True.
"""
import json

import pytest

from src.models import AppSetting

FEATURES_URL = "/api/developer/features"


@pytest.mark.asyncio
async def test_get_features_defaults(client, auth_headers):
    response = await client.get(FEATURES_URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "matters_enabled": True,
        "prompt_caching_enabled": True,
        "tool_memo_enabled": True,
        "local_prompt_cache_enabled": True,
    }


@pytest.mark.asyncio
async def test_get_features_merges_old_saved_json(client, auth_headers, db_session):
    """A features row saved before the cache flags existed still reports them ON."""
    db_session.add(AppSetting(key="features", value=json.dumps({"matters_enabled": False})))
    await db_session.commit()

    response = await client.get(FEATURES_URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "matters_enabled": False,
        "prompt_caching_enabled": True,
        "tool_memo_enabled": True,
        "local_prompt_cache_enabled": True,
    }


@pytest.mark.asyncio
async def test_save_features_round_trips_new_keys(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    body = {
        "matters_enabled": True,
        "prompt_caching_enabled": False,
        "tool_memo_enabled": False,
        "local_prompt_cache_enabled": False,
    }
    response = await client.post(FEATURES_URL, json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["features"] == body

    response = await client.get(FEATURES_URL, headers=headers)
    assert response.json() == body


@pytest.mark.asyncio
async def test_save_features_accepts_old_client_body(client, admin_token):
    """An old client POSTing only matters_enabled must not 422 — new flags default ON."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post(FEATURES_URL, json={"matters_enabled": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["features"] == {
        "matters_enabled": False,
        "prompt_caching_enabled": True,
        "tool_memo_enabled": True,
        "local_prompt_cache_enabled": True,
    }


@pytest.mark.asyncio
async def test_save_features_requires_admin(client, user_token):
    response = await client.post(
        FEATURES_URL,
        json={"matters_enabled": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
