"""Unit tests for Deep Research mode: planner (Phase A) and executor (Phase B).

All tests stub the provider chat_loop / run_worker_agent — no LLM or network.
"""
import asyncio

import pytest

from src.agent.agent_core import (
    _build_step_brief,
    _normalise_plan_args,
    draft_research_plan,
    run_deep_research,
)
from src.agent.provider_factory import set_request_provider_config


@pytest.fixture(autouse=True)
def _provider_config():
    """Minimal request config so _get_cfg() resolves inside agent_core."""
    set_request_provider_config({
        "_provider": "ollama",
        "_chat_mode": "deep_research",
        "_research_mode": "legislation_only",
        "model": "test-model",
    })
    yield
    set_request_provider_config({})


# ---------------------------------------------------------------------------
# _normalise_plan_args
# ---------------------------------------------------------------------------

def test_normalise_plan_args_happy_path():
    plan, err = _normalise_plan_args({
        "scope_note": "Covers X.",
        "steps": [
            {"title": "Find the Act", "detail": "Identify the governing Act."},
            {"title": "Check s.42", "detail": "Commencement and amendments."},
        ],
    })
    assert err is None
    assert plan["scope_note"] == "Covers X."
    assert [s["id"] for s in plan["steps"]] == [1, 2]
    assert plan["steps"][0]["title"] == "Find the Act"


def test_normalise_plan_args_json_string_steps():
    """Weaker models double-encode the steps array as a JSON string."""
    plan, err = _normalise_plan_args({
        "scope_note": "",
        "steps": '[{"title": "Find the Act", "detail": "d"}]',
    })
    assert err is None
    assert len(plan["steps"]) == 1


def test_normalise_plan_args_rejects_empty_and_garbage():
    _, err = _normalise_plan_args({"steps": []})
    assert err and "no usable steps" in err

    _, err = _normalise_plan_args({"steps": "not json"})
    assert err and "must be an array" in err

    _, err = _normalise_plan_args({"steps": [{"detail": "no title"}, "junk"]})
    assert err and "no usable steps" in err


def test_normalise_plan_args_caps_steps_at_eight():
    plan, err = _normalise_plan_args({
        "steps": [{"title": f"Step {i}", "detail": "d"} for i in range(12)],
    })
    assert err is None
    assert len(plan["steps"]) == 8


# ---------------------------------------------------------------------------
# draft_research_plan (Phase A)
# ---------------------------------------------------------------------------

def _make_chat_loop_calling(tool_name, tool_args):
    """Return a stub chat_loop that invokes the given planner tool once."""
    calls = []

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        calls.append({"messages": messages, "tools": tools})
        await tool_executor(tool_name, tool_args)
        return {"role": "assistant", "content": "Done"}

    chat_loop.calls = calls
    return chat_loop


@pytest.mark.asyncio
async def test_draft_research_plan_returns_plan():
    chat_loop = _make_chat_loop_calling("submit_research_plan", {
        "scope_note": "Compulsory purchase in E&W.",
        "steps": [
            {"title": "Identify the governing Acts", "detail": "Primary legislation."},
            {"title": "Compensation provisions", "detail": "Assessment rules."},
        ],
    })
    result = await draft_research_plan(
        chat_loop,
        [{"role": "user", "content": "Explain compulsory purchase"}],
        "test-model", None, 0,
    )
    assert "plan" in result
    assert len(result["plan"]["steps"]) == 2
    assert result["plan"]["steps"][0]["id"] == 1
    # Planner runs with exactly the two planner tools
    tool_names = {t["function"]["name"] for t in chat_loop.calls[0]["tools"]}
    assert tool_names == {"submit_research_plan", "request_clarification"}
    # System prompt injected as first message
    assert chat_loop.calls[0]["messages"][0]["role"] == "system"
    assert "Research Planner" in chat_loop.calls[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_draft_research_plan_clarification_path():
    chat_loop = _make_chat_loop_calling(
        "request_clarification", {"question": "Which Act do you mean?"}
    )
    result = await draft_research_plan(
        chat_loop, [{"role": "user", "content": "What does the Act say?"}],
        "test-model", None, 0,
    )
    assert result == {"needs_clarification": True, "question": "Which Act do you mean?"}


@pytest.mark.asyncio
async def test_draft_research_plan_retries_when_no_tool_called():
    """First call answers in prose; retry must nudge and succeed."""
    attempt = {"n": 0}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        attempt["n"] += 1
        if attempt["n"] == 1:
            return {"role": "assistant", "content": "Here is my plan in prose..."}
        assert any("MUST call" in str(m.get("content")) for m in messages if m["role"] == "user")
        await tool_executor("submit_research_plan", {
            "scope_note": "", "steps": [{"title": "T", "detail": "D"}],
        })
        return {"role": "assistant", "content": "Done"}

    result = await draft_research_plan(
        chat_loop, [{"role": "user", "content": "q"}], "test-model", None, 0,
    )
    assert attempt["n"] == 2
    assert "plan" in result


@pytest.mark.asyncio
async def test_draft_research_plan_error_when_both_attempts_fail():
    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        return {"role": "assistant", "content": "prose only"}

    result = await draft_research_plan(
        chat_loop, [{"role": "user", "content": "q"}], "test-model", None, 0,
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# run_deep_research (Phase B)
# ---------------------------------------------------------------------------

APPROVED_PLAN = {
    "scope_note": "Covers procedure and compensation.",
    "steps": [
        {"id": 1, "title": "Procedure", "detail": "CPO confirmation procedure."},
        {"id": 2, "title": "Compensation", "detail": "Assessment of compensation."},
    ],
}


def _make_worker_stub(results):
    """Stub run_worker_agent_fn returning canned results in order."""
    briefs = []

    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None):
        briefs.append(query)
        return results[len(briefs) - 1]

    run_worker.briefs = briefs
    return run_worker


def _make_synthesis_chat_loop(content="Integrated report."):
    captured = {}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        captured["messages"] = messages
        captured["tools"] = tools
        return {"role": "assistant", "content": content}

    chat_loop.captured = captured
    return chat_loop


@pytest.mark.asyncio
async def test_run_deep_research_step_loop_and_dedup():
    shared_source = {"title": "Act A", "url": "http://x/act-a"}
    worker = _make_worker_stub([
        {"content": "Finding one.", "sources": [shared_source, {"title": "Act B", "url": "http://x/act-b"}]},
        {"content": "Finding two.", "sources": [dict(shared_source)]},  # duplicate across steps
    ])
    chat_loop = _make_synthesis_chat_loop()
    events = []

    def on_chunk(data):
        events.append(data)

    result = await run_deep_research(
        chat_loop, worker, APPROVED_PLAN,
        [{"role": "user", "content": "Explain CPOs"}],
        "test-model", on_chunk, None, 0,
    )

    # One worker run per approved step, each brief self-contained
    assert len(worker.briefs) == 2
    assert "CPO confirmation procedure" in worker.briefs[0]
    assert "Explain CPOs" in worker.briefs[0]           # original question included
    assert "Covers procedure and compensation" in worker.briefs[0]  # scope note included

    # Sources deduped across steps and renumbered
    assert [s["url"] for s in result["sources"]] == ["http://x/act-a", "http://x/act-b"]
    assert [s["n"] for s in result["sources"]] == [1, 2]

    # Synthesis got both step findings and ran tool-free
    synthesis_user = chat_loop.captured["messages"][1]["content"]
    assert "Finding one." in synthesis_user and "Finding two." in synthesis_user
    assert chat_loop.captured["tools"] == []
    assert result["content"] == "Integrated report."

    # Per-step progress events
    starts = [e for e in events if e["type"] == "tool_start"]
    ends = [e for e in events if e["type"] == "tool_end"]
    assert len(starts) == 2 and len(ends) == 2
    assert starts[0]["tool"] == "Research Agent — Step 1: Procedure"


@pytest.mark.asyncio
async def test_run_deep_research_records_delegations():
    from src.utils.stopwatch import TimingCollector
    timing = TimingCollector("testreq1")
    worker = _make_worker_stub([
        {"content": "f1", "sources": []},
        {"content": "f2", "sources": []},
    ])
    await run_deep_research(
        chat_loop_fn=_make_synthesis_chat_loop(),
        run_worker_agent_fn=worker,
        approved_plan=APPROVED_PLAN,
        messages=[{"role": "user", "content": "q"}],
        model="test-model", on_chunk=None, cancel_event=None, num_ctx=0,
        timing_collector=timing,
    )
    assert timing.manager_delegations == 2


@pytest.mark.asyncio
async def test_run_deep_research_respects_cancel_between_steps():
    cancel_event = asyncio.Event()

    async def run_worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None):
        cancel_event.set()  # client disconnects during step 1
        return {"content": "f1", "sources": []}

    with pytest.raises(asyncio.CancelledError):
        await run_deep_research(
            _make_synthesis_chat_loop(), run_worker, APPROVED_PLAN,
            [{"role": "user", "content": "q"}],
            "test-model", None, cancel_event, 0,
        )


def test_build_step_brief_without_scope_or_query():
    brief = _build_step_brief({"title": "T", "detail": "D"}, {}, "")
    assert brief == "RESEARCH TASK: T\n\nD"


# ---------------------------------------------------------------------------
# POST /api/research/plan endpoint
# ---------------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402

PLAN_BODY = {
    "messages": [{"role": "user", "content": "Explain compulsory purchase"}],
    "model": "test-model",
}


@pytest.mark.asyncio
async def test_plan_endpoint_requires_auth(client):
    response = await client.post("/api/research/plan", json=PLAN_BODY)
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
@patch("src.agent.ollama_client.draft_research_plan")
async def test_plan_endpoint_returns_plan(mock_draft, client, auth_headers):
    mock_draft.return_value = {
        "plan": {"scope_note": "s", "steps": [{"id": 1, "title": "T", "detail": "D"}]}
    }
    response = await client.post("/api/research/plan", json=PLAN_BODY, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan"]["steps"][0]["title"] == "T"
    mock_draft.assert_called_once()


@pytest.mark.asyncio
@patch("src.agent.ollama_client.draft_research_plan")
async def test_plan_endpoint_clarification(mock_draft, client, auth_headers):
    mock_draft.return_value = {"needs_clarification": True, "question": "Which Act?"}
    response = await client.post("/api/research/plan", json=PLAN_BODY, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"needs_clarification": True, "question": "Which Act?"}


@pytest.mark.asyncio
@patch("src.agent.ollama_client.draft_research_plan")
async def test_plan_endpoint_planner_error_maps_to_502(mock_draft, client, auth_headers):
    mock_draft.return_value = {"error": "The planner did not produce a research plan."}
    response = await client.post("/api/research/plan", json=PLAN_BODY, headers=auth_headers)
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_plan_endpoint_missing_fields(client, auth_headers):
    response = await client.post(
        "/api/research/plan", json={"messages": [], "model": ""}, headers=auth_headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/chat execution wiring + efficiency carve-out + persistence
# ---------------------------------------------------------------------------

def test_efficiency_breaches_skipped_for_deep_research():
    from src.config import evaluate_efficiency_breaches

    metrics = {
        "manager_delegations": 5,       # would breach max_delegations=1
        "phase2_retrieval_calls": 12,   # would breach fan-out
        "sources_kept": 2,
        "redundant_tool_calls": 0,
        "chat_mode": "deep_research",
    }
    assert evaluate_efficiency_breaches(metrics) == []
    # Same metrics in standard research mode DO breach
    metrics["chat_mode"] = "research"
    assert evaluate_efficiency_breaches(metrics) != []


def _parse_sse_events(text):
    import json
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            events.append(json.loads(block[6:]))
    return events


CHAT_EXEC_BODY = {
    "messages": [{"role": "user", "content": "Explain CPOs"}],
    "model": "test-model",
    "chat_mode": "deep_research",
    "deep_research_plan": {
        "scope_note": "s",
        "steps": [{"id": 1, "title": "T", "detail": "D"}],
    },
}


@pytest.mark.asyncio
@patch("src.agent.ollama_client.run_deep_research")
async def test_chat_endpoint_dispatches_deep_research(mock_run, client, auth_headers):
    mock_run.return_value = {"role": "assistant", "content": "Report.", "sources": []}
    response = await client.post("/api/chat", json=CHAT_EXEC_BODY, headers=auth_headers)
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    result = next(e for e in events if e["type"] == "result")
    assert result["message"]["content"] == "Report."
    mock_run.assert_called_once()
    # First positional arg is the approved plan dict
    plan_arg = mock_run.call_args.args[0]
    assert plan_arg["steps"][0]["title"] == "T"


@pytest.mark.asyncio
@patch("src.agent.ollama_client.process_user_request")
async def test_chat_endpoint_deep_research_without_plan_errors(mock_process, client, auth_headers):
    body = {**CHAT_EXEC_BODY}
    body.pop("deep_research_plan")
    response = await client.post("/api/chat", json=body, headers=auth_headers)
    events = _parse_sse_events(response.text)
    assert any(e["type"] == "error" for e in events)
    mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_chat_endpoint_rejects_oversized_plan(client, auth_headers):
    body = {
        **CHAT_EXEC_BODY,
        "deep_research_plan": {
            "scope_note": "s",
            "steps": [{"title": f"S{i}", "detail": "d"} for i in range(9)],
        },
    }
    response = await client.post("/api/chat", json=body, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_message_research_plan_persistence(client, user_token):
    """The approved plan round-trips through message create/list (audit trail)."""
    headers = {"Authorization": f"Bearer {user_token}"}
    chat = (await client.post(
        "/api/chats", json={"title": "DR", "model": "test-model"}, headers=headers
    )).json()
    plan = {"scope_note": "s", "steps": [{"id": 1, "title": "T", "detail": "D"}]}

    created = (await client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"role": "assistant", "content": "Report.", "research_plan": plan},
        headers=headers,
    )).json()
    assert created["research_plan"] == plan

    listed = (await client.get(f"/api/chats/{chat['id']}/messages", headers=headers)).json()
    assert listed[0]["research_plan"] == plan
