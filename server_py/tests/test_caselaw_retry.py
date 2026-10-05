"""P4.19: case-law calls go through the retry helper, as LEX calls do.

The National Archives publishes a limit of 1,000 requests per rolling five
minutes per IP address, answered with HTTP 429, and the target is one IP for
every user, every Worker and every Deep Research step. `search_case_law` and
`_fetch_judgment_text` used to call `client.get` directly, so a 429 reached
`raise_for_status()` and the retrieval was dropped. They now go through
`_request_with_retry` (A5a), which honours `Retry-After` and backs off on
429/502/503/504.

**On timeouts and transport errors (the question batch 5 C put on the row).**
The helper also retries a timeout or a transport error up to three times, which
neither call did before. That is kept, deliberately, and pinned below: over the
1,149 stored `search_case_law` API calls and 564 `get_case_law_text` calls
(every replay directory), the only failures were 3 DNS transport errors, which
is exactly what a retry is for, and no call reached the 15 s timeout (max 13.1
s, p99 2.9 s). The cost of retrying a real timeout is bounded: four attempts at
15 s plus 3.5 s of backoff. The 15 s per-request timeout is itself pinned, so the
executor's 30 s client default cannot replace it silently.

asyncio.sleep is stubbed (the recorded delays are asserted) and the HTTP layer
is an `httpx.MockTransport`: no network.
"""
import json

import httpx
import pytest

from src.agent.tools import caselaw, executor

_RealAsyncClient = httpx.AsyncClient

_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:tna="https://caselaw.nationalarchives.gov.uk">
  <title>Search results</title>
  <entry>
    <title>Widget Co v Example Ltd</title>
    <link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewca/civ/1901/1"/>
    <published>1901-01-15T00:00:00Z</published>
    <tna:identifier slug="ewca/civ/1901/1" type="ukncn">[1901] EWCA Civ 1</tna:identifier>
  </entry>
</feed>
"""

_AKN = """<?xml version="1.0" encoding="utf-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
            xmlns:uk="https://caselaw.nationalarchives.gov.uk/akn">
  <judgment>
    <header><FRBRname value="Widget Co v Example Ltd"/><uk:cite>[1901] EWCA Civ 1</uk:cite></header>
    <judgmentBody><p>The appeal is dismissed.</p></judgmentBody>
  </judgment>
</akomaNtoso>
"""

_JUDGMENT_URL = "https://caselaw.nationalarchives.gov.uk/ewca/civ/1901/1"


@pytest.fixture
def sleeps(monkeypatch):
    delays = []

    async def fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(executor.asyncio, "sleep", fake_sleep)
    return delays


@pytest.fixture
def transport(monkeypatch):
    """Route every `httpx.AsyncClient` the executor or caselaw opens through a
    scripted MockTransport. Returns the list of requests seen; set
    `transport.script` to the responses (or exceptions) to serve in order."""
    seen = []
    state = {"script": [], "i": 0}

    def handler(request):
        seen.append(request)
        i = min(state["i"], len(state["script"]) - 1)
        state["i"] += 1
        item = state["script"][i]
        if isinstance(item, type) and issubclass(item, Exception):
            raise item("scripted", request=request)
        return item

    def make(*args, **kwargs):
        kwargs.pop("verify", None)
        return _RealAsyncClient(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make)

    class T:
        requests = seen

        @property
        def script(self):
            return state["script"]

        @script.setter
        def script(self, value):
            state["script"] = list(value)
            state["i"] = 0

    return T()


async def _search(args=None):
    return await executor.execute_worker_tool(
        "search_case_law", args or {"query": "widget"}
    )


# --- search_case_law ---------------------------------------------------------

@pytest.mark.asyncio
async def test_search_retries_a_429_then_returns_the_results(transport, sleeps):
    transport.script = [
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(200, text=_FEED),
    ]
    out = json.loads(await _search())
    assert len(transport.requests) == 2
    assert sleeps == [2.0]                      # Retry-After honoured
    assert [r["url"] for r in out["results"]] == [_JUDGMENT_URL]


@pytest.mark.asyncio
async def test_search_retries_a_transient_503(transport, sleeps):
    transport.script = [httpx.Response(503), httpx.Response(200, text=_FEED)]
    out = json.loads(await _search())
    assert len(out["results"]) == 1
    assert len(sleeps) == 1


@pytest.mark.asyncio
async def test_search_400_returns_at_once_unretried(transport, sleeps):
    """An invalid court code: the existing error, immediately, one request."""
    transport.script = [httpx.Response(400, text="not one of the available choices")]
    out = json.loads(await _search({"query": "widget", "court": "csoh"}))
    assert len(transport.requests) == 1
    assert sleeps == []
    assert out["results"] == [] and "Invalid court filter 'csoh'" in out["error"]


@pytest.mark.asyncio
async def test_search_retries_a_timeout_and_keeps_its_15s_timeout(transport, sleeps):
    """Wanted (see the module docstring): a timeout or transport error is
    retried like a 429, and the per-request timeout stays 15 s."""
    transport.script = [httpx.ConnectTimeout, httpx.Response(200, text=_FEED)]
    out = json.loads(await _search())
    assert len(out["results"]) == 1
    assert len(transport.requests) == 2 and len(sleeps) == 1
    for r in transport.requests:
        assert r.extensions["timeout"]["read"] == 15.0


@pytest.mark.asyncio
async def test_search_persistent_429_is_still_an_error_after_the_retries(transport, sleeps):
    transport.script = [httpx.Response(429)]
    out = await _search()
    assert out.startswith("Error executing tool")
    assert len(transport.requests) == executor._MAX_RETRIES + 1


# --- get_case_law_text / _fetch_judgment_text ---------------------------------

@pytest.mark.asyncio
async def test_judgment_fetch_retries_a_429_through_the_executor(transport, sleeps):
    transport.script = [
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(200, text=_AKN),
    ]
    out = json.loads(await executor.execute_worker_tool(
        "get_case_law_text", {"url": _JUDGMENT_URL}))
    assert "error" not in out
    assert "The appeal is dismissed." in out["text"]
    assert out["ncn"] == "[1901] EWCA Civ 1"
    assert sleeps == [1.0]
    assert [str(r.url) for r in transport.requests] == [_JUDGMENT_URL + "/data.xml"] * 2
    for r in transport.requests:
        assert r.extensions["timeout"]["read"] == 15.0


@pytest.mark.asyncio
async def test_judgment_fetch_without_a_client_opens_its_own_and_retries(transport, sleeps):
    transport.script = [httpx.Response(502), httpx.Response(200, text=_AKN)]
    out = await caselaw._fetch_judgment_text(_JUDGMENT_URL)
    assert "The appeal is dismissed." in out["text"]
    assert len(transport.requests) == 2 and len(sleeps) == 1


@pytest.mark.asyncio
async def test_judgment_fetch_404_is_not_retried(transport, sleeps):
    transport.script = [httpx.Response(404)]
    out = json.loads(await executor.execute_worker_tool(
        "get_case_law_text", {"url": _JUDGMENT_URL}))
    assert out["error"] == "HTTP 404 fetching judgment"
    assert len(transport.requests) == 1 and sleeps == []
