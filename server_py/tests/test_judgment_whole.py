"""P3.50: a judgment reaches the Worker whole up to its own cap.

Rex v Evans [2025] EWCA Crim 1150 is 28,746 characters. At the 8,000-character
fallback threshold it was summarised in all 21 stored turns that fetched it,
and the summary dropped [43], the paragraph that makes "actual duties at the
material time, not the formal designation" the case's central point, 21 times
in 21. `get_case_law_text` now passes whole up to `CASE_LAW_WHOLE_CHARS`
whatever the model's threshold; the context budget still applies, and so does
the chat loops' last-resort cap, which reads the same per-tool threshold
(`cap_tool_result`), or a whole judgment would be cut off there instead.

The loop tests run the REAL loops against a mocked transport (the harness
from `test_halt_writeup.py`).
"""
from __future__ import annotations

import json

import httpx
import pytest

from src.agent import agent_shared, ollama_client, openrouter_client, provider_factory
from src.agent.agent_shared import run_worker_tool
from src.agent.provider_factory import (
    cap_tool_result,
    get_tool_result_threshold,
    set_request_provider_config,
)
from src.agent.summarisation import CASE_LAW_WHOLE_CHARS, WHOLE_TEXT_TOOLS

EVANS = 28_746
MARK = "\n\n[Content truncated — result exceeded context limit]"


@pytest.fixture
def _cfg():
    # No context length resolvable: the 8,000-character fallback, as in every
    # stored replay.
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_research_mode": "case_law_only",
                                 "_local_prompt_cache_enabled": False})
    yield
    set_request_provider_config({})


# --- 1. the threshold and the cap ---------------------------------------------


def test_a_judgment_has_its_own_threshold_at_the_fallback(_cfg):
    assert provider_factory.get_summarise_threshold() == 8_000
    assert WHOLE_TEXT_TOOLS == {"get_case_law_text"}
    assert get_tool_result_threshold("get_case_law_text") == CASE_LAW_WHOLE_CHARS == 60_000
    for other in ("search_case_law", "search_legislation_sections", "get_legislation_text"):
        assert get_tool_result_threshold(other) == 8_000


def test_a_higher_model_threshold_is_never_lowered(monkeypatch):
    monkeypatch.setattr(provider_factory, "get_summarise_threshold", lambda: 200_000)
    assert get_tool_result_threshold("get_case_law_text") == 200_000
    assert get_tool_result_threshold("search_case_law") == 200_000


class _Timer:
    def __init__(self):
        self.n = 0

    def record_truncation(self):
        self.n += 1


def test_the_last_resort_cap_is_per_tool(_cfg):
    t = _Timer()
    assert cap_tool_result("get_case_law_text", "x" * EVANS, t) == "x" * EVANS
    assert cap_tool_result("search_case_law", "x" * EVANS, t) == "x" * 12_000 + MARK
    assert cap_tool_result("get_case_law_text", "x" * 70_000, t) == "x" * 64_000 + MARK
    assert cap_tool_result("search_case_law", "x" * 12_000, t) == "x" * 12_000
    assert t.n == 2
    assert cap_tool_result("search_case_law", "x" * 20_000) == "x" * 12_000 + MARK   # no timer


# --- 2. run_worker_tool's decision ---------------------------------------------


@pytest.fixture
def _pipeline(monkeypatch, _cfg):
    state = {"summarised": [], "payload": ""}

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return state["payload"]

    async def fake_summarise(text, query, model, **kw):
        state["summarised"].append(len(text))
        return f"[summary of {len(text)} chars]", False

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    return state


async def _fetch(state, payload, budget=None):
    state["payload"] = payload
    return await run_worker_tool("get_case_law_text", {"url": "https://caselaw.nationalarchives.gov.uk/ewca/crim/2025/1150"},
                                 "Summarise Rex v Evans", chunk_fn=None, summarise_model="m",
                                 context_budget=budget)


@pytest.mark.asyncio
async def test_evans_is_handed_over_whole(_pipeline):
    text = json.dumps({"title": "Evans", "text": "a" * (EVANS - 40)})
    out = await _fetch(_pipeline, text, {"used": 0, "limit": 250_000})
    assert _pipeline["summarised"] == []
    assert out.startswith(text)


@pytest.mark.asyncio
async def test_a_judgment_over_its_cap_is_summarised(_pipeline):
    await _fetch(_pipeline, "x" * (CASE_LAW_WHOLE_CHARS + 1))
    assert _pipeline["summarised"] == [CASE_LAW_WHOLE_CHARS + 1]


@pytest.mark.asyncio
async def test_the_context_budget_still_applies_to_a_judgment(_pipeline):
    await _fetch(_pipeline, "x" * EVANS, {"used": 230_000, "limit": 250_000})
    assert _pipeline["summarised"] == [EVANS]


# --- 3. the real chat loops do not cut it off ----------------------------------

_TOOLS = [{"type": "function", "function": {
    "name": n, "description": "d",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
}} for n in ("get_case_law_text", "search_case_law")]


def _sse(*chunks: str) -> str:
    return "".join(f"data: {c}\n\n" for c in chunks) + "data: [DONE]\n\n"


def _or_tool_call(name: str) -> str:
    return _sse(json.dumps({"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": "call_1", "function": {"name": name, "arguments": "{}"}}]}}]}))


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


async def _executor(name, args):
    return "x" * EVANS


def _tool_message(payload):
    return next(m for m in payload["messages"] if m.get("role") == "tool")["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,expected", [
    ("get_case_law_text", "x" * EVANS),
    ("search_case_law", "x" * 12_000 + MARK),
])
async def test_the_openrouter_loop_caps_per_tool(_cfg, _mock_http, tool, expected):
    seen = _mock_http([_or_tool_call(tool), _or_text("Report.")])
    await openrouter_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test/model", None, 0, _TOOLS, _executor, None, max_turns=3)
    assert _tool_message(seen[1]) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,expected", [
    ("get_case_law_text", "x" * EVANS),
    ("search_case_law", "x" * 12_000 + MARK),
])
async def test_the_ollama_loop_caps_per_tool(_cfg, _mock_http, tool, expected):
    seen = _mock_http([_ollama_tool_call(tool), _ollama_text("Report.")])
    await ollama_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test-model", None, 0, _TOOLS, _executor, None, max_turns=3)
    assert _tool_message(seen[1]) == expected
