"""Tests for the /api/system/chat request parity fix and the audit trace.

Two distinct regressions are covered:

1. **Field parity.** `/api/system/chat` used to declare its own three-field
   request model, so `chat_mode`, `research_mode` and every filter were
   silently dropped — an eval harness could only ever exercise
   `legislation_only` / `research`. Parity is now structural (the model
   subclasses `ChatRequest`), and these tests pin it so it cannot regress.

2. **The audit trace.** The structure a consumer needs (which tool ran inside
   which delegation, raw vs post-summarisation result, which API calls each
   tool made) must come from the call graph, not from parsing UI labels out of
   the SSE stream.

All tests stub the provider chat_loop / tool executors — no LLM, no network.
"""
import asyncio
import json

import pytest

from src.agent.agent_core import run_deep_research, run_worker_agent
from src.agent.provider_factory import set_request_provider_config
from src.routers.agent_request import (
    ChatRequest,
    ResearchPlanRequest,
    build_request_config,
    resolve_research_mode,
)
from src.routers.system import SystemChatRequest
from src.utils.audit_trace import AuditCollector, set_audit_collector


@pytest.fixture(autouse=True)
def _clean_context():
    set_request_provider_config({
        "_provider": "ollama",
        "_chat_mode": "research",
        "_research_mode": "legislation_only",
        "model": "test-model",
    })
    yield
    set_request_provider_config({})
    set_audit_collector(None)


# ---------------------------------------------------------------------------
# 1. Request field parity
# ---------------------------------------------------------------------------

def test_system_chat_accepts_every_chat_field():
    """The original bug: /api/system/chat dropped chat_mode and research_mode.

    Parity is asserted against ChatRequest itself rather than a hardcoded list,
    so a field added to /api/chat and forgotten here fails this test.
    """
    missing = set(ChatRequest.model_fields) - set(SystemChatRequest.model_fields)
    assert missing == set(), f"/api/system/chat is missing {missing}"


def test_system_chat_request_round_trips_mode_fields():
    body = SystemChatRequest(
        messages=[{"role": "user", "content": "q"}],
        model="m",
        chat_mode="conversational",
        research_mode="case_law_only",
    )
    assert body.chat_mode == "conversational"
    assert body.research_mode == "case_law_only"


def test_research_plan_request_shares_the_filter_set():
    """The planner needs the same filters as execution, or the drafted plan is
    scoped differently from the run that executes it."""
    shared = set(ChatRequest.model_fields) - {"chat_mode", "deep_research_plan"}
    assert shared <= set(ResearchPlanRequest.model_fields)


@pytest.mark.parametrize("mode", [
    "legislation_only", "case_law_only", "legislation_and_case_law",
    "parliamentary_records", "westminster_records",
])
def test_build_request_config_carries_research_mode(mode):
    body = SystemChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m", research_mode=mode,
    )
    cfg = build_request_config(body, {}, "ollama", {}, chat_mode="research")
    assert cfg["_research_mode"] == mode


@pytest.mark.parametrize("mode", ["research", "conversational", "deep_research"])
def test_build_request_config_carries_chat_mode(mode):
    body = SystemChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m", chat_mode=mode,
    )
    cfg = build_request_config(body, {}, "ollama", {}, chat_mode=mode)
    assert cfg["_chat_mode"] == mode


def test_env_research_mode_overrides_the_body():
    """A parliament-bot process must not be talked into legislation mode by a
    request body — its DB, tools and crawler are all mode-specific."""
    from src.config import settings
    original = settings.research_mode
    try:
        settings.research_mode = "parliamentary_records"
        body = SystemChatRequest(
            messages=[{"role": "user", "content": "q"}], model="m",
            research_mode="legislation_only",
        )
        assert resolve_research_mode(body) == "parliamentary_records"
    finally:
        settings.research_mode = original


def test_record_type_routes_by_mode():
    """The Holyrood and Westminster record-type vocabularies are disjoint, so a
    value must only reach the filter for the bot's own mode."""
    holyrood = SystemChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m",
        research_mode="parliamentary_records", record_type="committee",
    )
    cfg = build_request_config(holyrood, {}, "ollama", {}, chat_mode="research")
    assert cfg["_pt_record_type"] == "committee"
    assert cfg["_wm_record_type"] is None

    westminster = SystemChatRequest(
        messages=[{"role": "user", "content": "q"}], model="m",
        research_mode="westminster_records", record_type="commons_debates",
    )
    cfg = build_request_config(westminster, {}, "ollama", {}, chat_mode="research")
    assert cfg["_wm_record_type"] == "commons_debates"
    assert cfg["_pt_record_type"] is None


def test_deep_research_leaves_cache_key_query_empty():
    """Deep Research keys the local cache on each step's approved plan text;
    setting the raw user question here would collide unrelated steps."""
    body = SystemChatRequest(
        messages=[{"role": "user", "content": "the question"}], model="m",
        chat_mode="deep_research",
    )
    cfg = build_request_config(body, {}, "ollama", {}, chat_mode="deep_research")
    assert cfg["_cache_key_query"] == ""

    cfg = build_request_config(body, {}, "ollama", {}, chat_mode="research")
    assert cfg["_cache_key_query"] == "the question"


def test_build_request_config_is_identical_for_all_three_bodies():
    """One builder, one key set — the drift that caused the original bug."""
    kwargs = dict(
        messages=[{"role": "user", "content": "q"}], model="m",
        research_mode="case_law_only", jurisdiction="scotland", court="UKSC",
    )
    chat = build_request_config(ChatRequest(**kwargs), {}, "ollama", {}, chat_mode="research")
    system = build_request_config(SystemChatRequest(**kwargs), {}, "ollama", {}, chat_mode="research")
    plan = build_request_config(ResearchPlanRequest(**kwargs), {}, "ollama", {}, chat_mode="research")
    assert chat.keys() == system.keys() == plan.keys()
    assert chat == system == plan


# ---------------------------------------------------------------------------
# 2. Audit trace
# ---------------------------------------------------------------------------

def _chat_loop_calling_tools(tool_calls, final_content="THE REPORT"):
    """Fake provider chat_loop that invokes `tool_calls` then returns a report."""
    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        for name, args in tool_calls:
            await executor(name, args)
        return {"content": final_content, "sources": []}
    return chat_loop


async def _noop_summarise(*a, **kw):
    return ""


@pytest.mark.asyncio
async def test_audit_records_delegation_and_tools(monkeypatch):
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return json.dumps({"results": [{"title": "An Act"}]})

    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)

    await run_worker_agent(
        _chat_loop_calling_tools([("search_legislation", {"query": "housing"})]),
        _noop_summarise, "the brief", "test-model", None, 0,
    )

    assert len(audit.delegations) == 1
    d = audit.delegations[0]
    assert d["brief"] == "the brief"
    assert d["report"] == "THE REPORT"
    assert d["error"] is None
    assert [t["name"] for t in d["tools"]] == ["search_legislation"]
    assert d["tools"][0]["args"] == {"query": "housing"}
    assert "An Act" in d["tools"][0]["raw_result"]


@pytest.mark.asyncio
async def test_audit_captures_api_calls_inside_the_owning_tool(monkeypatch):
    """API-call nesting must come from the call graph, not event ordering."""
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        if on_chunk:
            await on_chunk({
                "type": "api_call_start", "id": "c1",
                "url": "https://lex.example/search", "method": "POST",
                "payload": {"query": "housing"},
            })
            await on_chunk({
                "type": "api_call_end", "id": "c1",
                "url": "https://lex.example/search", "status": 200,
                "response": {"results": [{"title": "An Act"}]}, "elapsed_ms": 12,
            })
        return json.dumps({"results": []})

    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)

    await run_worker_agent(
        _chat_loop_calling_tools([
            ("search_legislation", {"query": "a"}),
            ("search_legislation_sections", {"legislation_id": "ukpga/1985/68"}),
        ]),
        _noop_summarise, "brief", "test-model", None, 0,
    )

    tools = audit.delegations[0]["tools"]
    assert len(tools) == 2
    for t in tools:
        assert len(t["api_calls"]) == 1
        call = t["api_calls"][0]
        assert call["url"] == "https://lex.example/search"
        assert call["method"] == "POST"
        assert call["request"] == {"query": "housing"}
        assert call["status"] == 200
        assert call["response"]["results"][0]["title"] == "An Act"
        assert call["elapsed_ms"] == 12


@pytest.mark.asyncio
async def test_audit_records_raw_and_final_separately(monkeypatch):
    """The point of raw_result: distinguishing a bad summary from a bad
    retrieval, which the SSE stream alone cannot express."""
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    big = json.dumps({"text": "x" * 400_000})

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return big

    async def fake_summarise(text, query, model, **kw):
        return ("SHORT SUMMARY", False)

    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query", fake_summarise)
    monkeypatch.setattr(
        "src.agent.provider_factory.get_summarise_threshold", lambda: 1000
    )

    await run_worker_agent(
        _chat_loop_calling_tools([("get_legislation_text", {"legislation_id": "x"})]),
        _noop_summarise, "brief", "test-model", None, 0,
    )

    tool = audit.delegations[0]["tools"][0]
    assert tool["summarised"] is True
    assert tool["raw_result"] == big
    assert "SHORT SUMMARY" in tool["final_result"]
    assert tool["local_cache_hit"] is False


@pytest.mark.asyncio
async def test_audit_marks_memo_hits(monkeypatch):
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    calls = []

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        calls.append(name)
        return json.dumps({"results": []})

    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)

    await run_worker_agent(
        _chat_loop_calling_tools([
            ("search_legislation", {"query": "same"}),
            ("search_legislation", {"query": "same"}),
        ]),
        _noop_summarise, "brief", "test-model", None, 0,
        tool_memo={},
    )

    tools = audit.delegations[0]["tools"]
    assert len(calls) == 1, "second identical call should be served from the memo"
    assert tools[0]["memo_hit"] is False
    assert tools[1]["memo_hit"] is True


@pytest.mark.asyncio
async def test_audit_records_deep_research_step_metadata():
    """Deep Research emits 'Research Agent — Step N: title' as a display label;
    the trace carries step and title as real fields instead."""
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None):
        # The real run_worker_agent opens the delegation; emulate that here so
        # the test exercises the metadata hand-off rather than the whole worker.
        rec = audit.start_delegation(query)
        audit.end_delegation(rec, report="findings")
        return {"content": "findings", "sources": []}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        return {"content": "INTEGRATED REPORT", "sources": []}

    plan = {
        "scope_note": "scope",
        "steps": [
            {"id": 1, "title": "Find the Act", "detail": "d1"},
            {"id": 2, "title": "Check s.42", "detail": "d2"},
        ],
    }
    await run_deep_research(
        synthesis, worker, plan, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )

    assert len(audit.delegations) == 2
    assert [d["step"] for d in audit.delegations] == [1, 2]
    assert [d["title"] for d in audit.delegations] == ["Find the Act", "Check s.42"]
    assert all(d["kind"] == "deep_research_step" for d in audit.delegations)


@pytest.mark.asyncio
async def test_audit_closes_delegation_on_worker_failure():
    """A trace that just stops mid-delegation is indistinguishable from a hang."""
    audit = AuditCollector("req123")
    set_audit_collector(audit)

    async def failing_chat_loop(*a, **kw):
        raise RuntimeError("provider exploded")

    with pytest.raises(RuntimeError):
        await run_worker_agent(
            failing_chat_loop, _noop_summarise, "brief", "test-model", None, 0,
        )

    assert len(audit.delegations) == 1
    assert audit.delegations[0]["error"] is not None
    assert audit.delegations[0]["duration_s"] is not None


@pytest.mark.asyncio
async def test_no_collector_means_no_overhead_and_no_behaviour_change(monkeypatch):
    """/api/chat sets no collector — the recording sites must be inert."""
    set_audit_collector(None)

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return json.dumps({"results": []})

    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)

    result = await run_worker_agent(
        _chat_loop_calling_tools([("search_legislation", {"query": "a"})]),
        _noop_summarise, "brief", "test-model", None, 0,
    )
    assert result["content"] == "THE REPORT"


def test_audit_event_shape():
    audit = AuditCollector("req123")
    audit.record_final({"content": "the answer", "sources": [{"n": 1, "url": "u"}]})
    event = audit.to_event(
        config={
            "_chat_mode": "research", "_research_mode": "case_law_only",
            "_provider": "openrouter", "model": "m", "_court": "UKSC",
        },
        timings={"total_ms": 1234},
    )
    assert event["type"] == "audit"
    assert event["schema_version"] == 1
    assert event["request_id"] == "req123"
    assert event["chat_mode"] == "research"
    assert event["research_mode"] == "case_law_only"
    assert event["filters"]["court"] == "UKSC"
    assert event["answer"] == "the answer"
    assert event["sources"] == [{"n": 1, "url": "u"}]
    assert event["timings"]["total_ms"] == 1234
    # Must survive json.dumps — it goes down an SSE stream.
    assert json.loads(json.dumps(event))["request_id"] == "req123"


def test_audit_field_truncation_is_marked():
    audit = AuditCollector("req123", max_field_chars=10)
    rec = audit.start_delegation("x" * 100)
    assert "truncated 90 chars" in rec["brief"]


def test_audit_collector_never_raises():
    """A broken trace is acceptable; a broken research run is not."""
    audit = AuditCollector("req123")
    audit.end_delegation(None, report="ignored")
    audit.end_tool(None, raw_result="ignored")
    audit.record_final(None)
    audit.record_final("not a dict")
    assert audit.to_event(config={})["type"] == "audit"


# ---------------------------------------------------------------------------
# 3. End-to-end through the endpoint (agent mocked, real SSE)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_system_chat_emits_audit_event_on_the_wire(client, auth_headers, monkeypatch):
    """The trace has to survive JSON-serialisation and reach the stream."""
    from src.utils.audit_trace import get_audit_collector

    async def fake_process(messages, model, on_chunk, cancel_event, num_ctx,
                           db_session=None, emit_tool_details=False, timing_collector=None):
        # Emulate one delegation's worth of work against the live collector.
        audit = get_audit_collector()
        assert audit is not None, "collector must reach the agent call chain"
        rec = audit.start_delegation("the brief")
        tool = audit.start_tool(rec, "search_legislation", {"query": "housing"})
        audit.end_tool(tool, raw_result="RAW", final_result="FINAL")
        audit.end_delegation(rec, report="THE REPORT")
        return {"role": "assistant", "content": "the answer"}

    monkeypatch.setattr("src.agent.ollama_client.process_user_request", fake_process)

    response = await client.post(
        "/api/system/chat",
        json={
            "messages": [{"role": "user", "content": "q"}],
            "model": "mistral",
            "chat_mode": "research",
            "research_mode": "case_law_only",
            "court": "UKSC",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    audit_events = [e for e in events if e.get("type") == "audit"]
    assert len(audit_events) == 1
    ev = audit_events[0]

    # The fields the old endpoint silently dropped.
    assert ev["research_mode"] == "case_law_only"
    assert ev["chat_mode"] == "research"
    assert ev["filters"]["court"] == "UKSC"

    assert ev["answer"] == "the answer"
    assert len(ev["delegations"]) == 1
    d = ev["delegations"][0]
    assert d["brief"] == "the brief"
    assert d["report"] == "THE REPORT"
    assert [t["name"] for t in d["tools"]] == ["search_legislation"]
    assert d["tools"][0]["raw_result"] == "RAW"
    assert d["tools"][0]["final_result"] == "FINAL"

    # audit must precede result, so a consumer stopping at `result` still saw it.
    types = [e.get("type") for e in events]
    assert types.index("audit") < types.index("result")


@pytest.mark.asyncio
async def test_system_chat_rejects_deep_research_without_a_plan(client, auth_headers):
    """Previously this fell through and ran a normal research request; a harness
    checking status codes would have recorded it as a Deep Research run."""
    response = await client.post(
        "/api/system/chat",
        json={
            "messages": [{"role": "user", "content": "q"}],
            "model": "mistral",
            "chat_mode": "deep_research",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "deep_research_plan" in response.json()["detail"]


@pytest.mark.asyncio
async def test_system_chat_audit_can_be_disabled(client, auth_headers, monkeypatch):
    async def fake_process(messages, model, on_chunk, cancel_event, num_ctx,
                           db_session=None, emit_tool_details=False, timing_collector=None):
        return {"role": "assistant", "content": "the answer"}

    monkeypatch.setattr("src.agent.ollama_client.process_user_request", fake_process)

    response = await client.post(
        "/api/system/chat",
        json={
            "messages": [{"role": "user", "content": "q"}],
            "model": "mistral",
            "audit": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert '"type": "audit"' not in response.text
