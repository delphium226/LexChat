"""Response-shape test for POST /api/learning/test.

Locks the {"examples": [...], "critiques": [...]} retrieval shape so the
newly-added response_model can't drop the row columns coming out of the
full-text-search SQL.
"""
import pytest

from src.models import Chat, Message

pytestmark = pytest.mark.asyncio


async def test_learning_test_empty(client, admin_token):
    # A query of only stop/short words yields no keywords → empty lists.
    r = await client.post(
        "/api/learning/test",
        json={"query": "the a of"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"examples", "critiques"}
    assert body["examples"] == [] and body["critiques"] == []


async def test_learning_test_seeded(client, admin_token, db_session, seed_admin):
    chat = Chat(user_id=seed_admin.id, title="t", model="m", provider="ollama")
    db_session.add(chat)
    await db_session.commit()
    await db_session.refresh(chat)
    # user question then a highly-rated assistant answer → a positive example
    db_session.add(Message(chat_id=chat.id, role="user", content="compulsory purchase compensation procedure"))
    db_session.add(Message(chat_id=chat.id, role="assistant", content="the answer", rating=5))
    await db_session.commit()

    r = await client.post(
        "/api/learning/test",
        json={"query": "compulsory purchase compensation"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"examples", "critiques"}
    assert len(body["examples"]) == 1
    assert set(body["examples"][0]) == {
        "chat_id", "question_time", "question", "answer", "rating", "feedback_comment",
    }
