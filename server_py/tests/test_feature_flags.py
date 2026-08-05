"""Feature-flag endpoint tests (D6): cache toggles alongside matters_enabled.

Backward compatibility is the point — an old saved `features` JSON and an old
client POST body (matters_enabled only) must both keep working, with the new
cache flags defaulting to True.

The two feedback flags are the exception to "everything defaults ON": the
weekly survey and the end-of-session pre-pilot form ask different things and
are not meant to run at once, so both default OFF and are switched on per
deployment.
"""
import json

import pytest

from src.models import AppSetting

FEATURES_URL = "/api/developer/features"

DEFAULTS = {
    "matters_enabled": True,
    "prompt_caching_enabled": True,
    "tool_memo_enabled": True,
    "local_prompt_cache_enabled": True,
    "research_mode_enabled": True,
    "deep_research_mode_enabled": True,
    "drafting_mode_enabled": True,
    "suggested_questions_enabled": True,
    "weekly_survey_enabled": False,
    "session_feedback_enabled": False,
}


@pytest.mark.asyncio
async def test_get_features_defaults(client, auth_headers):
    response = await client.get(FEATURES_URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == DEFAULTS


@pytest.mark.asyncio
async def test_get_features_merges_old_saved_json(client, auth_headers, db_session):
    """A features row saved before the newer flags existed still reports their defaults."""
    db_session.add(AppSetting(key="features", value=json.dumps({"matters_enabled": False})))
    await db_session.commit()

    response = await client.get(FEATURES_URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {**DEFAULTS, "matters_enabled": False}


@pytest.mark.asyncio
async def test_save_features_round_trips_new_keys(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Every flag inverted from its default, so the round trip proves both
    # directions (ON→OFF for the mode flags, OFF→ON for the feedback flags).
    body = {flag: not value for flag, value in DEFAULTS.items()}
    response = await client.post(FEATURES_URL, json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["features"] == body

    response = await client.get(FEATURES_URL, headers=headers)
    assert response.json() == body


@pytest.mark.asyncio
async def test_save_features_accepts_old_client_body(client, admin_token):
    """An old client POSTing only matters_enabled must not 422 — the rest take their defaults."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.post(FEATURES_URL, json={"matters_enabled": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["features"] == {**DEFAULTS, "matters_enabled": False}


@pytest.mark.asyncio
async def test_save_features_requires_admin(client, user_token):
    response = await client.post(
        FEATURES_URL,
        json={"matters_enabled": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
