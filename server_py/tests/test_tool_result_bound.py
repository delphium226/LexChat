"""P1.8: no code-written text is cut off a Worker's tool result.

The chat loops' last-resort cap (`cap_tool_result`) cut every tool result at the
per-tool threshold plus 4,000 characters, and so cut the code-written blocks
`run_worker_tool` appends after the tool's own output: over every stored replay,
310 Worker results at the 8,000-character fallback threshold, and every cut fell
in code text (the [CURRENCY] block of every made-under list over 12,000
characters, whole; P3.51's section families; P3.12's PROVISION FETCHED BY CODE;
the section SEARCH SCOPE note), none in the tool's own output
(`docs/prepilot-fixes/evidence/seam/s52/p18/`).

Now `run_worker_tool` bounds the tool's OWN output (`cap_tool_body`) before any
code text is appended, the Worker's loop skips the last-resort cap
(`results_bounded`), the made-under list has its own bound (P3.34's pattern), and
`delegate_research` (a model-written report with a code scope block at its end)
is not cut at the Manager. The loop tests run the REAL loops against a mocked
transport (the harness from `test_judgment_whole.py`).
"""
from __future__ import annotations

import json

import httpx
import pytest

from src.agent import agent_core, agent_shared, ollama_client, openrouter_client, provider_factory
from src.agent.agent_shared import run_worker_tool
from src.agent.provider_factory import (
    BODY_CUT_MARKER,
    cap_tool_body,
    cap_tool_result,
    get_tool_result_threshold,
    set_request_provider_config,
)
from src.services import made_under_store as store
from src.utils import made_under as mu
from src.utils.made_under import MADE_UNDER_TOOL, MADE_UNDER_WHOLE_CHARS

OLD_MARK = "\n\n[Content truncated — result exceeded context limit]"
SECTIONS = "search_legislation_sections"


@pytest.fixture
def _cfg():
    # No context length resolvable: the 8,000-character fallback, as in every
    # stored replay (and on the target in the pre-pilot).
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_chat_mode": "research",
                                 "_research_mode": "legislation_only",
                                 "_tool_memo_enabled": False,
                                 "_local_prompt_cache_enabled": False})
    yield
    set_request_provider_config({})


class _Timer:
    def __init__(self):
        self.n = 0

    def record_truncation(self):
        self.n += 1


# --- 1. the bound on the tool's own output -------------------------------------


def test_a_body_within_the_limit_is_returned_unchanged(_cfg):
    body = "x" * 12_000
    t = _Timer()
    assert cap_tool_body(SECTIONS, body, t) is body
    assert t.n == 0


def test_a_body_over_the_limit_is_cut_and_says_the_notes_after_it_are_whole(_cfg):
    t = _Timer()
    out = cap_tool_body(SECTIONS, "x" * 12_001, t)
    assert out == "x" * 12_000 + BODY_CUT_MARKER
    assert t.n == 1
    assert "this tool's own result" in BODY_CUT_MARKER
    assert "notes after this line are complete" in BODY_CUT_MARKER
    # Lower-case after the bracket: never read as a code-written block header.
    assert BODY_CUT_MARKER.startswith("\n\n[Content truncated")


def test_the_body_bound_is_per_tool(_cfg):
    assert cap_tool_body("get_case_law_text", "x" * 64_000) == "x" * 64_000
    assert cap_tool_body("get_case_law_text", "x" * 64_001) == "x" * 64_000 + BODY_CUT_MARKER


# --- 2. the made-under list has its own bound ----------------------------------


def test_the_made_under_list_has_its_own_threshold(_cfg, monkeypatch):
    assert provider_factory.get_summarise_threshold() == 8_000
    assert get_tool_result_threshold(MADE_UNDER_TOOL) == MADE_UNDER_WHOLE_CHARS == 30_000
    body = "x" * 20_000
    assert cap_tool_body(MADE_UNDER_TOOL, body) is body
    monkeypatch.setattr(provider_factory, "get_summarise_threshold", lambda: 200_000)
    assert get_tool_result_threshold(MADE_UNDER_TOOL) == 200_000


COV = store.coverage({"label": "Scottish statutory instruments made from 1901 to 1905",
                      "harvested_at": "1906-01-01"}, None, 0)
PART = {"state": "partly", "partial": {"count": 3, "by": ["ssi/1904/2"], "by_count": 1}}


def _long_list(n=60):
    rows = [(f"ssi/1901/{i}", "The Widget (Scotland) Regulations 1901 (Amendment) " * 6,
             "Widget (Scotland) Act 1901", "asp/1901/1", "as applied by", json.dumps(PART),
             "1906-05-01") for i in range(1, n + 1)]
    return store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV,
                              today="1906-06-01")


def test_a_list_of_the_longest_rows_is_within_its_bound():
    """Titles are cut at 110 characters and the list at `MAX_LISTED`, so the
    JSON is bounded by construction; 40 of the longest rows stay well inside it."""
    d = _long_list()
    assert len(d["instruments"]) == mu.MAX_LISTED == 40
    body = json.dumps(d, ensure_ascii=False)
    assert 12_000 < len(body) < MADE_UNDER_WHOLE_CHARS


# --- 3. the Manager's report is not cut ----------------------------------------


def test_a_worker_report_reaches_the_manager_whole(_cfg):
    report = "[Research Agent Result]\n" + "r" * 30_000 + "\n\n[SEARCH SCOPE — what this research step]"
    assert cap_tool_result("delegate_research", report) == report


def test_any_other_tool_keeps_the_last_resort_cap(_cfg):
    assert cap_tool_result("consult_peer", "x" * 20_000) == "x" * 12_000 + OLD_MARK
    assert cap_tool_result(SECTIONS, "x" * 20_000) == "x" * 12_000 + OLD_MARK


# --- 4. run_worker_tool: the notes after the body are never cut ----------------


@pytest.fixture
def _pipeline(monkeypatch, _cfg):
    state = {"payload": "", "summarised": []}

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return state["payload"]

    async def fake_summarise(text, query, model, **kw):
        state["summarised"].append(len(text))
        return "s" * 7_999, False

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    return state


NOTE = "\n\n[NOTE — " + "n" * 6_000 + "]"


@pytest.mark.asyncio
async def test_a_summary_and_its_notes_come_back_whole(_pipeline):
    _pipeline["payload"] = "p" * 30_000
    out = await run_worker_tool(SECTIONS, {"legislation_id": "asp/1901/1", "query": "q"},
                                "q", chunk_fn=None, summarise_model="m", result_suffix=NOTE)
    assert _pipeline["summarised"] == [30_000]
    assert out.startswith("s" * 7_999)
    assert out.endswith(NOTE)
    assert len(out) > 12_000 and "Content truncated" not in out
    # What the chat loop's cap did to the same string before P1.8:
    assert NOTE not in cap_tool_result(SECTIONS, out)


@pytest.mark.asyncio
async def test_an_unsummarised_body_over_its_bound_is_cut_and_its_notes_kept(_pipeline):
    _pipeline["payload"] = "x" * 40_000
    out = await run_worker_tool(MADE_UNDER_TOOL, {"act": "A", "section": "1"},
                                "q", chunk_fn=None, summarise_model="m", result_suffix=NOTE)
    assert _pipeline["summarised"] == []          # the list is never summarised
    assert out == "x" * 34_000 + BODY_CUT_MARKER + NOTE


# --- 5. the real chat loops ----------------------------------------------------

_TOOLS = [{"type": "function", "function": {
    "name": n, "description": "d",
    "parameters": {"type": "object", "properties": {"act": {"type": "string"}}},
}} for n in (SECTIONS, MADE_UNDER_TOOL)]


def _sse(*chunks: str) -> str:
    return "".join(f"data: {c}\n\n" for c in chunks) + "data: [DONE]\n\n"


def _or_tool_call(name: str, args: str = "{}") -> str:
    return _sse(json.dumps({"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": "call_1", "function": {"name": name, "arguments": args}}]}}]}))


def _or_text(text: str) -> str:
    return _sse(json.dumps({"choices": [{"delta": {"content": text}}]}))


def _ollama_tool_call(name: str) -> str:
    return json.dumps({"message": {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": name, "arguments": {}}}]}, "done": True}) + "\n"


def _ollama_text(text: str) -> str:
    return json.dumps({"message": {"role": "assistant", "content": text}, "done": True}) + "\n"


@pytest.fixture
def _mock_http(monkeypatch):
    real = httpx.AsyncClient

    def install(responses):
        seen, state = [], {"i": 0}

        def handler(request):
            seen.append(json.loads(request.content))
            i = min(state["i"], len(responses) - 1)
            state["i"] += 1
            return httpx.Response(200, text=responses[i])

        def factory(*args, **kwargs):
            kwargs.pop("verify", None)
            kwargs.pop("proxy", None)
            return real(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return seen

    return install


BIG = "y" * 9_000 + NOTE   # a bounded body and its notes: 15,000+ characters


async def _executor(name, args):
    return BIG


def _tool_messages(payload):
    return [m["content"] for m in payload["messages"] if m.get("role") == "tool"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bounded,expected", [(True, BIG), (False, BIG[:12_000] + OLD_MARK)])
async def test_the_openrouter_loop_leaves_a_bounded_result_whole(_cfg, _mock_http, bounded, expected):
    seen = _mock_http([_or_tool_call(SECTIONS), _or_tool_call(SECTIONS), _or_text("Report.")])
    await openrouter_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test/model", None, 0, _TOOLS, _executor, None, max_turns=5,
        results_bounded=bounded)
    # The second round's payload carries both rounds' results: forwarded
    # through the recursion.
    assert _tool_messages(seen[2]) == [expected, expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("bounded,expected", [(True, BIG), (False, BIG[:12_000] + OLD_MARK)])
async def test_the_ollama_loop_leaves_a_bounded_result_whole(_cfg, _mock_http, bounded, expected):
    seen = _mock_http([_ollama_tool_call(SECTIONS), _ollama_tool_call(SECTIONS),
                       _ollama_text("Report.")])
    await ollama_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test-model", None, 0, _TOOLS, _executor, None, max_turns=5,
        results_bounded=bounded)
    assert _tool_messages(seen[2]) == [expected, expected]


# --- 6. end to end: a made-under list reaches the Worker with its CURRENCY block


@pytest.mark.asyncio
async def test_the_worker_is_handed_the_whole_currency_block(_cfg, _mock_http, monkeypatch):
    """The shape of every stored made-under cut: a list over 12,000 characters
    whose closing [CURRENCY] block the chat loop cut off whole. Here the Worker
    run is real (`agent_core.run_worker_agent`, the OpenRouter loop, the real
    `run_worker_tool` and `made_under_note`); only the record and the transport
    are not."""
    body = json.dumps(_long_list(), ensure_ascii=False)

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        assert name == MADE_UNDER_TOOL
        return body

    async def no_summarise(*a, **kw):
        raise AssertionError("the made-under list is never summarised")

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", no_summarise)
    seen = _mock_http([_or_tool_call(MADE_UNDER_TOOL, json.dumps({"act": "Widget (Scotland) Act 1901",
                                                                  "section": "95"})),
                       _or_text("## Findings\nReport.")])
    await agent_core.run_worker_agent(openrouter_client.chat_loop, no_summarise,
                                      "What was made under s.95?", "test/model", None, 0)
    handed = _tool_messages(seen[1])
    assert len(handed) == 1
    note = mu.made_under_note(body)
    assert "[CURRENCY — revocations as recorded on legislation.gov.uk" in note
    assert handed[0] == body + note
    assert len(handed[0]) > 12_000 and "Content truncated" not in handed[0]


@pytest.mark.asyncio
async def test_the_worker_is_handed_a_summarised_search_with_its_whole_scope_note(
        _cfg, _mock_http, monkeypatch):
    """The shape of the 235 stored section-search cuts: a summary within the
    threshold, then code blocks that take the result past 12,000 characters.
    The Worker run is real; the scope note is lengthened to stand for the
    blocks after it (P3.51's families, P3.12's fetched unit)."""
    raw = json.dumps({"results": [{"legislation_id": "asp/1901/1", "number": str(i),
                                   "text": "t" * 400} for i in range(25)]})
    scope = "\n\n[SEARCH SCOPE — " + "n" * 6_000 + "]"

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return raw

    async def fake_summarise(text, query, model, **kw):
        return "s" * 7_999, False

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    monkeypatch.setattr(agent_shared, "section_search_note", lambda args, data: scope)
    seen = _mock_http([_or_tool_call(SECTIONS, json.dumps({"legislation_id": "asp/1901/1",
                                                           "query": "widgets"})),
                       _or_text("## Findings\nReport.")])
    await agent_core.run_worker_agent(openrouter_client.chat_loop, fake_summarise,
                                      "Widgets?", "test/model", None, 0)
    handed = _tool_messages(seen[1])
    assert len(handed) == 1
    assert handed[0].startswith("s" * 7_999)
    assert scope in handed[0]
    assert len(handed[0]) > 12_000 and "Content truncated" not in handed[0]
