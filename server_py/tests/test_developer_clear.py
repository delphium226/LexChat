"""Tests for the scoped Danger Zone clear (GET /data-counts, POST /clear-data).

These replace three overlapping clear endpoints that could not, between them,
produce a clean slate before a pilot. What is pinned here:

  * admin-only, via the router-level dependency (a non-admin must get 403);
  * the typed confirmation is enforced SERVER-side, not just in the UI;
  * scoping — clearing one domain leaves the others untouched;
  * the fixed execution order, so `chats` + `feedback` in one request can never
    leave orphan session_feedback rows behind (chat_id is ON DELETE SET NULL);
  * users / app_settings / peer_bots survive a full pilot reset;
  * the removed /reset and /seed foot-guns stay removed.
"""
import pytest
from sqlalchemy import func, select

from src.models import (
    ActivityLog,
    AppSetting,
    Chat,
    LocalPromptCache,
    Message,
    PeerBot,
    ProductFeedback,
    RequestTiming,
    ServiceHealthStatus,
    SessionFeedback,
    User,
)

pytestmark = pytest.mark.asyncio

ALL_SCOPES = ["chats", "performance", "feedback", "activity", "health", "cache"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


async def _count(db, model) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar() or 0)


async def _seed_everything(db, user):
    """One row in every table a scope touches, plus the config rows that must survive."""
    chat = Chat(user_id=user.id, title="t", model="m", provider="ollama")
    db.add(chat)
    await db.commit()
    await db.refresh(chat)

    db.add(Message(chat_id=chat.id, role="user", content="q"))
    db.add(Message(
        chat_id=chat.id, role="assistant", content="a",
        rating=4, feedback_comment="helpful",
    ))
    db.add(RequestTiming(request_id="req0001", total_ms=100.0))
    db.add(ProductFeedback(user_id=user.id, message="survey"))
    db.add(SessionFeedback(user_id=user.id, chat_id=chat.id, message_count=2))
    db.add(ActivityLog(event_type="LOGIN", username=user.username))
    db.add(ServiceHealthStatus(service_name="lex", is_healthy=True))
    db.add(LocalPromptCache(
        content_hash="c" * 64, query_hash="q" * 64,
        query_text="query", summary="summary",
    ))
    # Must NOT be deleted by any scope.
    db.add(AppSetting(key="features", value='{"tool_memo_enabled": true}'))
    db.add(PeerBot(
        peer_id="parliament_bot", name="Parliament",
        base_url="http://x", description="Holyrood records",
    ))
    await db.commit()
    return chat


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

async def test_data_counts_requires_admin(client, user_token):
    r = await client.get("/api/developer/data-counts", headers=_hdr(user_token))
    assert r.status_code == 403


async def test_clear_data_requires_admin(client, user_token, db_session, seed_user):
    await _seed_everything(db_session, seed_user)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ALL_SCOPES, "confirm": "DELETE"},
        headers=_hdr(user_token),
    )
    assert r.status_code == 403
    assert await _count(db_session, Chat) == 1


# --------------------------------------------------------------------------- #
# Counts
# --------------------------------------------------------------------------- #

async def test_data_counts_empty(client, admin_token):
    r = await client.get("/api/developer/data-counts", headers=_hdr(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert set(body["counts"]) == set(ALL_SCOPES)
    assert all(v == 0 for v in body["counts"].values())
    assert set(body["scopes"]) == set(ALL_SCOPES)


async def test_data_counts_reports_rows_and_cascade(client, admin_token, db_session, seed_admin):
    await _seed_everything(db_session, seed_admin)
    body = (await client.get("/api/developer/data-counts", headers=_hdr(admin_token))).json()

    assert body["counts"]["chats"] == 1
    assert body["counts"]["performance"] == 1
    # 1 survey + 1 session + 1 rated message
    assert body["counts"]["feedback"] == 3
    assert body["counts"]["activity"] == 1
    assert body["counts"]["health"] == 1
    assert body["counts"]["cache"] == 1
    # The cascade is disclosed, not discovered afterwards.
    assert body["details"]["chats"]["messages"] == 2
    assert "documents" in body["details"]["chats"]


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("confirm", ["", "delete", "DELETE ", "yes"])
async def test_wrong_confirmation_deletes_nothing(
    client, admin_token, db_session, seed_admin, confirm
):
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ALL_SCOPES, "confirm": confirm},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400
    assert await _count(db_session, Chat) == 1
    assert await _count(db_session, RequestTiming) == 1


async def test_unknown_scope_rejected(client, admin_token, db_session, seed_admin):
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ["chats", "users"], "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400
    assert "users" in r.json()["detail"]
    assert await _count(db_session, Chat) == 1


async def test_empty_scope_list_rejected(client, admin_token):
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": [], "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Clearing
# --------------------------------------------------------------------------- #

async def test_pilot_reset_clears_all_metrics_and_preserves_config(
    client, admin_token, db_session, seed_admin
):
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ALL_SCOPES, "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    assert set(r.json()["deleted"]) == set(ALL_SCOPES)

    for model in (
        Chat, Message, RequestTiming, ProductFeedback,
        SessionFeedback, ActivityLog, ServiceHealthStatus, LocalPromptCache,
    ):
        assert await _count(db_session, model) == 0, model.__name__

    # Config and accounts survive.
    assert await _count(db_session, User) == 1
    assert await _count(db_session, AppSetting) == 1
    assert await _count(db_session, PeerBot) == 1


async def test_scope_is_respected(client, admin_token, db_session, seed_admin):
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ["performance"], "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == {"performance": 1}
    assert await _count(db_session, RequestTiming) == 0
    assert await _count(db_session, Chat) == 1
    assert await _count(db_session, Message) == 2
    assert await _count(db_session, ActivityLog) == 1


@pytest.mark.parametrize("scopes", [["chats", "feedback"], ["feedback", "chats"]])
async def test_chats_and_feedback_leave_no_orphans_in_either_order(
    client, admin_token, db_session, seed_admin, scopes
):
    """session_feedback.chat_id is SET NULL, so tick order must not change the outcome."""
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": scopes, "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    assert await _count(db_session, SessionFeedback) == 0
    assert await _count(db_session, Chat) == 0
    assert await _count(db_session, Message) == 0


async def test_feedback_scope_nulls_message_ratings(client, admin_token, db_session, seed_admin):
    await _seed_everything(db_session, seed_admin)
    r = await client.post(
        "/api/developer/clear-data",
        json={"scopes": ["feedback"], "confirm": "DELETE"},
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    rated = (await db_session.execute(
        select(func.count()).select_from(Message).where(Message.rating.isnot(None))
    )).scalar()
    assert rated == 0
    # The messages themselves stay — only the ratings were cleared.
    assert await _count(db_session, Message) == 2


# --------------------------------------------------------------------------- #
# Removed foot-guns
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", ["/api/developer/reset", "/api/developer/seed"])
async def test_removed_endpoints_are_gone(client, admin_token, path):
    r = await client.post(path, headers=_hdr(admin_token))
    # 405 rather than 404: the SPA catch-all still answers the path for GET.
    assert r.status_code in (404, 405)
