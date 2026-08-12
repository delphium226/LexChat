"""End-of-session feedback (the pre-pilot form) — POST/GET /api/feedback/session.

Every field is optional by design, so the interesting cases are the ones that
are present and out of range: both rating scales are 1-5 and the closed
questions are enums, which would otherwise reach the DB as free-form values
and quietly corrupt the admin aggregates.
"""
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from src.models import SessionFeedback, User

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
