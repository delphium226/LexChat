"""End-of-session feedback (the pre-pilot form) — POST/GET /api/feedback/session.

Every field is optional by design, so the interesting cases are the ones that
are present and out of range: both rating scales are 1-5 and the closed
questions are enums, which would otherwise reach the DB as free-form values
and quietly corrupt the admin aggregates.
"""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from src.models import SessionFeedback, User
from src.routers.feedback import (
    PREPILOT_END,
    PREPILOT_START,
    PREPILOT_TIMEFRAME,
    _clean_filters,
    _timeframe_bounds,
)

URL = "/api/feedback/session"

FULL_PAYLOAD = {
    "message_count": 6,
    "manual_time_hours": 4.0,
    "time_saved_hours": 2.5,
    "verification_hours": 0.5,
    "session_continuity": "one_go",
    "found_right_law": "partially",
    "found_right_law_notes": "  Missed the 2016 amendment.  ",
    "right_jurisdiction": "no",
    "right_jurisdiction_notes": "Answered on England and Wales, not Scotland.",
    "references_accurate": "partially",
    "references_notes": "Could not verify the case citation.",
    "refers_incorrectly": "yes",
    "refers_incorrectly_notes": "",
    "confidence": 5,  # top of the scale — proves 5 is in range, not just 1-4
    "ease_of_use": 4,
    "ease_of_use_reason": "Clear, but the filters took a moment to find.",
    "other_comments": "More case law coverage.",
}


@pytest.mark.asyncio
async def test_submit_requires_auth(client: AsyncClient):
    response = await client.post(URL, json={"confidence": 3})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_full_payload(client: AsyncClient, seed_user: User, user_token: str, db_session):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(URL, json=FULL_PAYLOAD, headers=headers)
    assert response.status_code == 201
    assert response.json() == {"status": "ok"}

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.user_id == seed_user.id
    assert row.manual_time_hours == 4.0
    assert row.session_continuity == "one_go"
    assert row.found_right_law == "partially"
    assert row.right_jurisdiction == "no"
    # 7a's polarity is inverted — 'yes' means the assistant DID get something
    # wrong. Stored verbatim; the reading of it lives in the admin tab.
    assert row.refers_incorrectly == "yes"
    assert row.confidence == 5
    assert row.ease_of_use == 4
    # Free text is trimmed, and blank text is stored as NULL rather than ''
    assert row.found_right_law_notes == "Missed the 2016 amendment."
    assert row.refers_incorrectly_notes is None


@pytest.mark.asyncio
async def test_submit_empty_payload_is_allowed(client: AsyncClient, user_token: str, db_session):
    """The form is entirely optional; the client blocks a blank submit, not the API."""
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(URL, json={}, headers=headers)
    assert response.status_code == 201
    assert len((await db_session.execute(select(SessionFeedback))).scalars().all()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"confidence": 6},
        {"confidence": 0},
        {"ease_of_use": 6},
        {"ease_of_use": 0},
        {"manual_time_hours": -1},
        {"time_saved_hours": -0.5},
        {"verification_hours": -2},
        {"message_count": -1},
        {"session_continuity": "sort of"},
        {"found_right_law": "maybe"},
        {"right_jurisdiction": "maybe"},
        # All four accuracy questions are yes/partially/no since the users revised
        # them; 'unsure' was 6a's old third option and is no longer accepted.
        {"references_accurate": "unsure"},
        {"refers_incorrectly": "unsure"},
    ],
)
@pytest.mark.asyncio
async def test_submit_rejects_out_of_range(client: AsyncClient, user_token: str, payload):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(URL, json=payload, headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_id_must_belong_to_the_caller(client: AsyncClient, user_token: str, db_session):
    """An unknown or someone else's chat_id is dropped, not stored and not an error."""
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(URL, json={"chat_id": 999999, "confidence": 2}, headers=headers)
    assert response.status_code == 201

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.chat_id is None


@pytest.mark.asyncio
async def test_chat_id_is_kept_for_the_owner(client: AsyncClient, user_token: str, db_session):
    headers = {"Authorization": f"Bearer {user_token}"}
    chat = await client.post("/api/chats/", json={"model": "mistral", "title": "Test"}, headers=headers)
    chat_id = chat.json()["id"]

    response = await client.post(URL, json={"chat_id": chat_id, "confidence": 4}, headers=headers)
    assert response.status_code == 201

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.chat_id == chat_id


@pytest.mark.asyncio
async def test_get_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(URL, headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_compliance_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(f"{URL}/compliance", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_compliance_counts_threads_against_responses(
    client: AsyncClient, seed_user: User, user_token: str, admin_token: str, db_session
):
    """The chase list: two threads worked in, one response, so one thread is missing feedback."""
    idle = User(
        username="idlelawyer",
        password_hash="x",
        role="user",
        email="idle@test.com",
    )
    db_session.add(idle)
    await db_session.commit()

    user_headers = {"Authorization": f"Bearer {user_token}"}
    for title in ("Thread one", "Thread two"):
        chat = await client.post("/api/chats/", json={"model": "mistral", "title": title}, headers=user_headers)
        await client.post(
            f"/api/chats/{chat.json()['id']}/messages",
            json={"role": "user", "content": "Question"},
            headers=user_headers,
        )
    await client.post(URL, json={"confidence": 4}, headers=user_headers)

    response = await client.get(f"{URL}/compliance", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()

    row = next(u for u in body["users"] if u["user_id"] == seed_user.id)
    assert row["threads"] == 2
    assert row["queries"] == 2
    assert row["responses"] == 1
    assert row["last_active"] is not None
    assert row["last_feedback"] is not None

    # A user who has done nothing must appear with zeros rather than be dropped
    # — never having logged in at all is exactly what the roster should surface.
    idle_row = next(u for u in body["users"] if u["username"] == "idlelawyer")
    assert idle_row["threads"] == 0
    assert idle_row["responses"] == 0
    assert idle_row["last_feedback"] is None

    # ...but the operator account is filtered out entirely, not shown as idle.
    assert "admin" not in {u["username"] for u in body["users"]}

    assert body["totals"]["active_users"] == 1
    assert body["totals"]["responding_users"] == 1
    assert body["totals"]["threads"] == 2
    assert body["totals"]["responses"] == 1


@pytest.mark.asyncio
async def test_resubmission_is_a_correction_not_a_second_response(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """Two forms on one thread: the latest is reported, the first is retained.

    Nothing stops a lawyer pressing "Finished session" twice, and counting both
    would give them double weight in the accuracy shares and the confidence
    averages.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat = await client.post("/api/chats/", json={"model": "mistral", "title": "T"}, headers=user_headers)
    chat_id = chat.json()["id"]
    await client.post(URL, json={"chat_id": chat_id, "confidence": 2}, headers=user_headers)
    await client.post(URL, json={"chat_id": chat_id, "confidence": 5}, headers=user_headers)

    rows = (await client.get(URL, headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert len(rows) == 1
    assert rows[0]["confidence"] == 5

    # Superseded, not deleted — the audit record survives in the table.
    stored = (await db_session.execute(select(SessionFeedback))).scalars().all()
    assert sorted(r.confidence for r in stored) == [2, 5]


@pytest.mark.asyncio
async def test_forms_without_a_thread_are_never_deduplicated(
    client: AsyncClient, user_token: str, admin_token: str
):
    """There is no thread to supersede them against, so each one stands."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    await client.post(URL, json={"confidence": 3}, headers=user_headers)
    await client.post(URL, json={"confidence": 4}, headers=user_headers)

    rows = (await client.get(URL, headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert sorted(r["confidence"] for r in rows) == [3, 4]


@pytest.mark.asyncio
async def test_compliance_chases_on_threads_covered_not_form_count(
    client: AsyncClient, seed_user: User, user_token: str, admin_token: str
):
    """Three forms on one of three threads leaves two threads to chase.

    Counting forms reported this lawyer as fully up to date, and let the
    coverage percentage exceed 100%.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_ids = []
    for title in ("One", "Two", "Three"):
        chat = await client.post("/api/chats/", json={"model": "mistral", "title": title}, headers=user_headers)
        chat_ids.append(chat.json()["id"])
        await client.post(
            f"/api/chats/{chat_ids[-1]}/messages",
            json={"role": "user", "content": "Question"},
            headers=user_headers,
        )
    for _ in range(3):
        await client.post(URL, json={"chat_id": chat_ids[0], "confidence": 4}, headers=user_headers)

    body = (await client.get(f"{URL}/compliance", headers={"Authorization": f"Bearer {admin_token}"})).json()
    row = next(u for u in body["users"] if u["user_id"] == seed_user.id)
    assert row["threads"] == 3
    assert row["responses"] == 3
    assert row["threads_covered"] == 1

    assert body["totals"]["threads"] == 3
    assert body["totals"]["threads_covered"] == 1
    assert body["totals"]["threads_covered"] <= body["totals"]["threads"]


@pytest.mark.asyncio
async def test_a_form_with_no_thread_covers_nothing(
    client: AsyncClient, seed_user: User, user_token: str, admin_token: str
):
    """It is a response, but it closes no gap — the thread is still unreviewed.

    The two counts are meant to disagree here: the lawyer has engaged with the
    form (so they count as responding), but none of their threads is reviewed
    (so the gap stays open and they stay on the chase list).
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat = await client.post("/api/chats/", json={"model": "mistral", "title": "T"}, headers=user_headers)
    await client.post(
        f"/api/chats/{chat.json()['id']}/messages",
        json={"role": "user", "content": "Question"},
        headers=user_headers,
    )
    await client.post(URL, json={"confidence": 4}, headers=user_headers)

    body = (await client.get(f"{URL}/compliance", headers={"Authorization": f"Bearer {admin_token}"})).json()
    row = next(u for u in body["users"] if u["user_id"] == seed_user.id)
    assert row["responses"] == 1
    assert row["threads_covered"] == 0
    assert body["totals"]["responding_users"] == 1
    assert body["totals"]["threads_covered"] == 0


@pytest.mark.asyncio
async def test_compliance_flags_a_user_who_never_responds(
    client: AsyncClient, seed_user: User, user_token: str, admin_token: str
):
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat = await client.post("/api/chats/", json={"model": "mistral", "title": "T"}, headers=user_headers)
    await client.post(
        f"/api/chats/{chat.json()['id']}/messages",
        json={"role": "user", "content": "Question"},
        headers=user_headers,
    )

    body = (await client.get(f"{URL}/compliance", headers={"Authorization": f"Bearer {admin_token}"})).json()
    row = next(u for u in body["users"] if u["user_id"] == seed_user.id)
    assert row["threads"] == 1
    assert row["responses"] == 0
    assert row["last_feedback"] is None
    assert body["totals"]["responding_users"] == 0


@pytest.mark.asyncio
async def test_compliance_accepts_all_timeframe(client: AsyncClient, admin_token: str):
    response = await client.get(f"{URL}/compliance?days=all", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["days"] == "all"


# --- Filter snapshot ------------------------------------------------------
#
# The panel's state at submit time, so an answer like 5c (right jurisdiction)
# can be read against what the jurisdiction filter was actually set to. Stored
# through an allowlist, because it is client-supplied JSON landing in a column
# an admin reads and exports.

FILTERS = {
    "research_mode": "legislation_only",
    "chat_mode": "research",
    "jurisdiction": "scotland",
    "date_from": "1990",
    "date_to": "2026",
    "court": "",
    "legislation_type": "ukpga",
    "current_only": True,
    "record_type": None,
    "sessions": [6, 7],
    "house": None,
}


@pytest.mark.asyncio
async def test_filters_are_stored_and_returned(client: AsyncClient, user_token: str, admin_token: str, db_session):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(URL, json={**FULL_PAYLOAD, "filters": FILTERS}, headers=headers)
    assert response.status_code == 201

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.filters["jurisdiction"] == "scotland"
    assert row.filters["sessions"] == [6, 7]
    assert row.filters["current_only"] is True
    # Nulls and blanks are absent, not stored as None/'' — "unset" is one state.
    assert "record_type" not in row.filters
    assert "court" not in row.filters

    rows = (await client.get(URL, headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert rows[0]["filters"]["legislation_type"] == "ukpga"


@pytest.mark.asyncio
async def test_a_form_without_filters_still_submits(client: AsyncClient, user_token: str, db_session):
    """The column is additive — omitting it must behave exactly as before."""
    headers = {"Authorization": f"Bearer {user_token}"}
    assert (await client.post(URL, json={"confidence": 3}, headers=headers)).status_code == 201
    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.filters is None


@pytest.mark.asyncio
async def test_junk_filters_do_not_cost_the_lawyer_their_feedback(
    client: AsyncClient, user_token: str, db_session
):
    """A malformed snapshot is dropped, not rejected — the answers still land.

    Rejecting would throw away five minutes of typing over a field nobody
    filled in by hand.
    """
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.post(
        URL, json={"confidence": 4, "filters": {"nonsense": "x", "sessions": "seven"}}, headers=headers
    )
    assert response.status_code == 201

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.confidence == 4
    assert row.filters is None


def test_clean_filters_enforces_the_shape():
    assert _clean_filters(None) is None
    assert _clean_filters({}) is None
    assert _clean_filters("scotland") is None
    # Unknown keys are dropped rather than stored.
    assert _clean_filters({"jurisdiction": "wales", "evil": "x"}) == {"jurisdiction": "wales"}
    # False is a real answer ("current in force only" switched off), so it must
    # survive a check that a truthiness test would swallow.
    assert _clean_filters({"current_only": False}) == {"current_only": False}
    assert _clean_filters({"current_only": "no"}) is None
    # bool subclasses int in Python, so [True] must not become a session number.
    assert _clean_filters({"sessions": [7, True, "6", None]}) == {"sessions": [7]}
    assert _clean_filters({"sessions": []}) is None
    # Oversized strings are truncated rather than rejected.
    assert len(_clean_filters({"court": "x" * 500})["court"]) == 100


# --- Pre-pilot timeframe --------------------------------------------------
#
# Nothing here may depend on "today" falling inside the pre-pilot: the window is
# a fixed range in August 2026 and these tests must still pass in 2027. Every
# timestamp is therefore set explicitly rather than inherited from utcnow().

# 11 Aug 2026 00:00 and 19 Aug 2026 23:59:59.999999 UK time, expressed in the
# naive UTC the rows are stored in. August is BST, so both shift back an hour.
PREPILOT_FIRST_UTC = datetime(2026, 8, 10, 23, 0, 0)
PREPILOT_LAST_UTC = datetime(2026, 8, 19, 22, 59, 59, 999999)


def test_timeframe_bounds_resolves_each_selector():
    assert _timeframe_bounds("all") == (None, None)
    assert _timeframe_bounds(PREPILOT_TIMEFRAME) == (PREPILOT_FIRST_UTC, PREPILOT_LAST_UTC)

    # The trailing windows keep no upper bound, so they behave exactly as they
    # did before the pre-pilot option was added.
    start, end = _timeframe_bounds("30")
    assert end is None
    assert abs((datetime.utcnow() - timedelta(days=30)) - start) < timedelta(seconds=5)

    # An unrecognised value still falls back to 30 days rather than erroring.
    assert _timeframe_bounds("nonsense")[0] is not None
    assert _timeframe_bounds("nonsense")[1] is None


def test_prepilot_dates_are_the_agreed_run():
    assert (PREPILOT_START.isoformat(), PREPILOT_END.isoformat()) == ("2026-08-11", "2026-08-19")


@pytest.mark.asyncio
async def test_prepilot_window_includes_both_end_days_in_uk_time(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """Inclusive of the 11th and the 19th, as UK calendar days.

    The boundary cases are an hour either side of midnight BST: stored naively
    in UTC, the first moment of the 11th is 10 Aug 23:00 and the last moment of
    the 19th is 19 Aug 22:59, so a UTC-naive reading would drop an hour of the
    opening day and admit an hour of the 20th.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    # confidence doubles as an identifier: 1/4 inside, 2/3 outside.
    stamps = {
        1: PREPILOT_FIRST_UTC,                                  # 11 Aug 00:00 BST
        2: PREPILOT_FIRST_UTC - timedelta(minutes=1),           # 10 Aug 23:59 BST
        3: PREPILOT_LAST_UTC + timedelta(minutes=1),            # 20 Aug 00:00 BST
        4: PREPILOT_LAST_UTC - timedelta(minutes=1),            # 19 Aug 23:58 BST
    }
    for confidence, stamp in stamps.items():
        await client.post(URL, json={"confidence": confidence}, headers=user_headers)
        await db_session.execute(
            text("UPDATE session_feedback SET created_at = :t WHERE confidence = :c"),
            {"t": stamp, "c": confidence},
        )
    await db_session.commit()

    rows = (
        await client.get(
            f"{URL}?days={PREPILOT_TIMEFRAME}", headers={"Authorization": f"Bearer {admin_token}"}
        )
    ).json()
    assert sorted(r["confidence"] for r in rows) == [1, 4]


@pytest.mark.asyncio
async def test_prepilot_window_bounds_durations_and_compliance(
    client: AsyncClient, seed_user: User, user_token: str, admin_token: str, db_session
):
    """All three endpoints honour the closed upper bound, not just the list."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    inside = await _thread_with_messages(client, user_headers, "During")
    outside = await _thread_with_messages(client, user_headers, "After")
    for chat_id in (inside, outside):
        await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    # Anchor each thread whole — messages, form and press together — so the one
    # outside differs only in when it happened.
    for chat_id, anchor in ((inside, datetime(2026, 8, 15, 10, 0)), (outside, datetime(2026, 9, 15, 10, 0))):
        await db_session.execute(
            text("UPDATE messages SET created_at = :t WHERE chat_id = :c"), {"t": anchor, "c": chat_id}
        )
        await db_session.execute(
            text("UPDATE session_feedback SET created_at = :t2, finished_at = :t2 WHERE chat_id = :c"),
            {"t2": anchor + timedelta(minutes=30), "c": chat_id},
        )
    await db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    durations = (await client.get(f"{URL}/durations?days={PREPILOT_TIMEFRAME}", headers=headers)).json()
    assert [s["chat_id"] for s in durations["sessions"]] == [inside]
    assert durations["summary"]["median_seconds"] == 30 * 60

    compliance = (await client.get(f"{URL}/compliance?days={PREPILOT_TIMEFRAME}", headers=headers)).json()
    row = next(u for u in compliance["users"] if u["user_id"] == seed_user.id)
    assert row["threads"] == 1
    assert row["responses"] == 1
    assert row["threads_covered"] == 1


# --- Session length -------------------------------------------------------


async def _thread_with_messages(client: AsyncClient, headers: dict, title: str, roles=("user", "assistant")):
    chat = await client.post("/api/chats/", json={"model": "mistral", "title": title}, headers=headers)
    chat_id = chat.json()["id"]
    for role in roles:
        await client.post(
            f"/api/chats/{chat_id}/messages", json={"role": role, "content": "x"}, headers=headers
        )
    return chat_id


@pytest.mark.asyncio
async def test_durations_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duration_uses_last_response_when_the_press_was_not_timed(
    client: AsyncClient, user_token: str, admin_token: str
):
    """A form with no `finished_seconds_ago` still counts, measured to the last
    answer — the session was reported on, only its end was never timed."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Untimed")
    await client.post(URL, json={"chat_id": chat_id}, headers=user_headers)

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    session = next(s for s in body["sessions"] if s["chat_id"] == chat_id)
    assert session["end_signal"] == "last_response"
    assert session["duration_seconds"] >= 0
    assert body["summary"]["inferred"] == 1
    assert body["summary"]["closed_properly"] == 0


@pytest.mark.asyncio
async def test_thread_without_feedback_is_not_measured(
    client: AsyncClient, user_token: str, admin_token: str
):
    """An abandoned thread has an end signal (the last answer) but no form. It
    is excluded so the medians describe only sessions a lawyer reported on."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    abandoned = await _thread_with_messages(client, user_headers, "Abandoned")
    reported = await _thread_with_messages(client, user_headers, "Reported")
    await client.post(URL, json={"chat_id": reported, "finished_seconds_ago": 0}, headers=user_headers)

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    measured = [s["chat_id"] for s in body["sessions"]]
    assert abandoned not in measured
    assert measured == [reported]
    assert body["summary"]["sessions"] == 1


@pytest.mark.asyncio
async def test_admin_own_sessions_are_excluded_from_stats(
    client: AsyncClient, user_token: str, admin_token: str
):
    """The operator account's threads are smoke tests, not legal research, so
    they are dropped from all three reads the tab makes — including the chase
    list, where there is nobody to chase about a smoke test."""
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_chat = await _thread_with_messages(client, admin_headers, "Smoke test")
    user_chat = await _thread_with_messages(client, user_headers, "Real research")
    for headers, chat_id in ((admin_headers, admin_chat), (user_headers, user_chat)):
        await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=headers)

    rows = (await client.get(URL, headers=admin_headers)).json()
    assert [r["chat_id"] for r in rows] == [user_chat]

    durations = (await client.get(f"{URL}/durations", headers=admin_headers)).json()
    assert [s["chat_id"] for s in durations["sessions"]] == [user_chat]

    compliance = (await client.get(f"{URL}/compliance", headers=admin_headers)).json()
    assert "admin" not in {u["username"] for u in compliance["users"]}
    # The admin thread must leave the coverage denominator too, not just the row.
    assert compliance["totals"]["threads"] == 1
    assert compliance["totals"]["active_users"] == 1


@pytest.mark.asyncio
async def test_finished_button_takes_precedence_over_last_response(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """The explicit "I am done" beats the inferred end, even though it is later."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Closed properly")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    assert row.finished_at is not None

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    session = next(s for s in body["sessions"] if s["chat_id"] == chat_id)
    assert session["end_signal"] == "finished_button"
    assert session["ended_at"] == row.finished_at.isoformat()
    assert body["summary"]["closed_properly"] == 1


@pytest.mark.asyncio
async def test_finished_seconds_ago_is_subtracted_from_server_now(
    client: AsyncClient, user_token: str, db_session
):
    """The delta is resolved against the server clock, so the stored end is the
    button press and not the (later) moment the filled-in form arrived."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    before = datetime.utcnow()
    await client.post(URL, json={"finished_seconds_ago": 600}, headers=user_headers)

    row = (await db_session.execute(select(SessionFeedback))).scalars().one()
    delta = (before - row.finished_at).total_seconds()
    assert 595 <= delta <= 605
    assert row.finished_at < row.created_at


@pytest.mark.parametrize("value", [-1, 2 * 60 * 60 + 1])
@pytest.mark.asyncio
async def test_finished_seconds_ago_rejects_implausible_values(client: AsyncClient, user_token: str, value):
    response = await client.post(
        URL, json={"finished_seconds_ago": value}, headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_thread_with_no_answer_is_not_measurable(client: AsyncClient, user_token: str, admin_token: str):
    """A question asked but never answered, and never closed, has no end signal.

    The form is submitted (without a timed press) so this isolates the missing
    end signal rather than passing for want of feedback.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Unanswered", roles=("user",))
    await client.post(URL, json={"chat_id": chat_id}, headers=user_headers)

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert all(s["chat_id"] != chat_id for s in body["sessions"])


@pytest.mark.asyncio
async def test_long_session_is_capped_not_dropped(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """A thread picked up the next day is credited at the cap, and still counted.

    Capping rather than excluding is the point: the row survives, so the
    session-length population stays the same as the accuracy charts', and the
    reported duration is a floor rather than a deletion.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Resumed next day")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    # Backdate the thread's first question by 30h, leaving the end where it is.
    await db_session.execute(
        text("UPDATE messages SET created_at = created_at - INTERVAL '30 hours' WHERE chat_id = :c"),
        {"c": chat_id},
    )
    await db_session.commit()

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    cap = body["cap_seconds"]
    session = next(s for s in body["sessions"] if s["chat_id"] == chat_id)
    assert session["capped"] is True
    assert session["duration_seconds"] == cap
    assert session["elapsed_seconds"] > cap

    # The cap must not leak into the headline totals...
    assert body["summary"]["sessions"] == 1
    assert body["summary"]["total_seconds"] == cap
    # ...and the uncapped block must still report the truth, so the assumption
    # behind the cap can be checked from the tab without database access.
    assert body["uncapped"]["capped_sessions"] == 1
    assert body["uncapped"]["longest_seconds"] > cap
    assert body["uncapped"]["total_seconds"] > body["summary"]["total_seconds"]


@pytest.mark.asyncio
async def test_short_session_is_untouched_by_the_cap(
    client: AsyncClient, user_token: str, admin_token: str
):
    """The common case must be byte-for-byte what it was before the cap."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Quick question")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    session = next(s for s in body["sessions"] if s["chat_id"] == chat_id)
    assert session["capped"] is False
    assert session["duration_seconds"] == session["elapsed_seconds"]
    assert body["uncapped"]["capped_sessions"] == 0
    assert body["uncapped"]["median_seconds"] == body["summary"]["median_seconds"]


@pytest.mark.asyncio
async def test_timeframe_follows_the_form_not_the_thread_start(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """An old thread fed back on today is measured; the window tracks the form.

    Filtering on the thread's first question put session length on a clock that
    matched neither the accuracy charts nor the chase list, so a long-running
    thread appeared in both of those and in neither the medians nor the
    histogram.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Long running")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    # Thread began well outside a 7-day window; the form arrived just now.
    await db_session.execute(
        text("UPDATE messages SET created_at = created_at - INTERVAL '20 days' WHERE chat_id = :c"),
        {"c": chat_id},
    )
    await db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    body = (await client.get(f"{URL}/durations?days=7", headers=headers)).json()
    assert [s["chat_id"] for s in body["sessions"]] == [chat_id]

    # ...and the two endpoints agree on the population, which is the point.
    rows = (await client.get(f"{URL}?days=7", headers=headers)).json()
    assert len(rows) == body["summary"]["sessions"]


@pytest.mark.asyncio
async def test_a_form_outside_the_window_is_not_measured(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """The converse: an old form on an old thread stays out of a short window."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Ancient")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    for table in ("messages", "session_feedback"):
        await db_session.execute(
            text(f"UPDATE {table} SET created_at = created_at - INTERVAL '20 days' WHERE chat_id = :c"),
            {"c": chat_id},
        )
    await db_session.commit()

    body = (
        await client.get(f"{URL}/durations?days=7", headers={"Authorization": f"Bearer {admin_token}"})
    ).json()
    assert body["summary"]["sessions"] == 0


@pytest.mark.asyncio
async def test_impossible_finish_time_falls_back_instead_of_dropping(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """`finished_at` is client-derived, so it can land before the thread began.

    That is a bad browser value, not a short session. It used to drop the row
    outright even where the last answer would have measured it; now the value
    is discarded, the inference is used, and the event is counted.
    """
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Duff timer")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    await db_session.execute(
        text("UPDATE session_feedback SET finished_at = finished_at - INTERVAL '1 hour' WHERE chat_id = :c"),
        {"c": chat_id},
    )
    await db_session.commit()

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    session = next(s for s in body["sessions"] if s["chat_id"] == chat_id)
    assert session["end_signal"] == "last_response"
    assert session["duration_seconds"] >= 0
    assert body["quality"]["implausible_finish"] == 1
    assert body["quality"]["recovered_by_fallback"] == 1
    assert body["quality"]["no_end_signal"] == 0


@pytest.mark.asyncio
async def test_impossible_finish_with_no_answer_is_counted_not_silent(
    client: AsyncClient, user_token: str, admin_token: str, db_session
):
    """With nothing to fall back on it is still dropped — but no longer silently."""
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Unanswered", roles=("user",))
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    await db_session.execute(
        text("UPDATE session_feedback SET finished_at = finished_at - INTERVAL '1 hour' WHERE chat_id = :c"),
        {"c": chat_id},
    )
    await db_session.commit()

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert body["summary"]["sessions"] == 0
    assert body["quality"]["implausible_finish"] == 1
    assert body["quality"]["recovered_by_fallback"] == 0
    assert body["quality"]["no_end_signal"] == 1


@pytest.mark.asyncio
async def test_quality_block_is_clean_for_ordinary_traffic(
    client: AsyncClient, user_token: str, admin_token: str
):
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat_id = await _thread_with_messages(client, user_headers, "Normal")
    await client.post(URL, json={"chat_id": chat_id, "finished_seconds_ago": 0}, headers=user_headers)

    body = (await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert body["quality"] == {
        "implausible_finish": 0,
        "recovered_by_fallback": 0,
        "no_end_signal": 0,
    }


@pytest.mark.asyncio
async def test_durations_summary_splits_by_continuity(client: AsyncClient, user_token: str, admin_token: str):
    user_headers = {"Authorization": f"Bearer {user_token}"}
    one_go = await _thread_with_messages(client, user_headers, "One go")
    broken = await _thread_with_messages(client, user_headers, "With breaks")
    await client.post(
        URL, json={"chat_id": one_go, "session_continuity": "one_go", "finished_seconds_ago": 0}, headers=user_headers
    )
    await client.post(
        URL,
        json={"chat_id": broken, "session_continuity": "not_one_go", "finished_seconds_ago": 0},
        headers=user_headers,
    )

    summary = (
        await client.get(f"{URL}/durations", headers={"Authorization": f"Bearer {admin_token}"})
    ).json()["summary"]
    assert summary["sessions"] == 2
    assert summary["one_go_sessions"] == 1
    assert summary["not_one_go_sessions"] == 1
    assert summary["median_one_go"] is not None
    assert summary["median_not_one_go"] is not None


@pytest.mark.asyncio
async def test_get_returns_rows_with_username_and_chat_title(
    client: AsyncClient, user_token: str, admin_token: str
):
    user_headers = {"Authorization": f"Bearer {user_token}"}
    chat = await client.post(
        "/api/chats/", json={"model": "mistral", "title": "Compulsory purchase"}, headers=user_headers
    )
    await client.post(
        URL, json={**FULL_PAYLOAD, "chat_id": chat.json()["id"]}, headers=user_headers
    )

    response = await client.get(URL, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["chat_title"] == "Compulsory purchase"
    assert rows[0]["confidence"] == 5
    assert rows[0]["username"]
