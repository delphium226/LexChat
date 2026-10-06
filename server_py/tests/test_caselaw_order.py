"""P3.22: case-law results by relevance, not newest first.

`search_case_law` sent no `order`, and the National Archives feed's default is
`-date`, so every case-law search returned the 50 NEWEST matches and the
Phase-2 nudge's "most relevant" first three were the three newest. The fix is
two params that must travel together: `order=relevance` (the advanced search's
own sort, NOT in the published spec) and `per_page=50` (ANY explicit `order`
resets the page size to 10 without it: the 10-row trap). These tests pin both,
each failing alone; pin that court and dates are sent exactly as before; and
pin that the window note says the order the params ask for, with none of its
three old order statements left (newest first, "most recent", "an older
judgment").

Fixtures are synthetic ("Widget Co v Example Ltd", 1901); no network: an
`httpx.MockTransport` records each request.
"""
import json
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from src.agent.provider_factory import set_request_provider_config
from src.agent.tools import executor
from src.agent.tools.caselaw import (
    CASE_LAW_ORDER_PARAMS,
    CASE_LAW_PAGE_SIZE,
    case_law_count,
)
from src.utils.search_scope import CASE_LAW_RESULT_ORDER, case_law_search_note

_RealAsyncClient = httpx.AsyncClient
_BASE = "https://caselaw.nationalarchives.gov.uk/atom.xml?query=widget"


def _entry(i: int, year: int) -> str:
    return (
        "<entry>"
        f"<title>Widget Co v Example Ltd {i}</title>"
        f'<link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/{year}/{i}"/>'
        f"<published>{year}-01-15T00:00:00Z</published>"
        f'<tna:identifier slug="ewhc/ch/{year}/{i}" type="ukncn">[{year}] EWHC {i} (Ch)</tna:identifier>'
        "</entry>"
    )


def _feed(rows, last=None) -> str:
    links = f'<link href="{_BASE}&amp;page=1" rel="first"/>'
    if last is not None:
        links += f'<link href="{_BASE}&amp;page={last}" rel="last"/>'
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:tna="https://caselaw.nationalarchives.gov.uk">'
        f"<title>t</title>{links}"
        + "".join(_entry(i, y) for i, y in rows)
        + "</feed>"
    )


@pytest.fixture
def requests_seen(monkeypatch):
    """Serve a short feed and record every request the executor makes."""
    seen = []

    def make(*a, **kw):
        kw.pop("verify", None)

        def handler(req):
            seen.append(req)
            return httpx.Response(200, text=_feed([(1, 1901), (2, 1900)], last=1))

        return _RealAsyncClient(*a, transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", make)
    set_request_provider_config({})
    yield seen
    set_request_provider_config({})


def _params(req) -> dict:
    q = parse_qs(urlparse(str(req.url)).query)
    assert all(len(v) == 1 for v in q.values()), q   # no param sent twice
    return {k: v[0] for k, v in q.items()}


async def _search(args, cfg=None, on_chunk=None):
    set_request_provider_config(cfg or {})
    return json.loads(await executor.execute_worker_tool(
        "search_case_law", args, on_chunk=on_chunk))


# --- the params ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_search_asks_for_relevance_with_a_full_page(requests_seen):
    """Both params, each failing alone: without `order` the feed lists newest
    first; with `order` and no `per_page` it returns 10 rows, not 50."""
    await _search({"query": "widget"})
    assert len(requests_seen) == 1
    p = _params(requests_seen[0])
    assert p.get("order") == "relevance"
    assert p.get("per_page") == "50"
    assert p == {"query": "widget", "order": "relevance", "per_page": "50"}


@pytest.mark.asyncio
async def test_court_and_dates_are_sent_exactly_as_before(requests_seen):
    """The order params are added; nothing P3.9 or P4.4 sends is changed."""
    await _search({"query": "widget", "court": "ewhc/ch",
                   "date_from": "1900-01-01", "date_to": "1901-12-31"})
    p = _params(requests_seen[0])
    assert p == {
        "query": "widget", "court": "ewhc/ch",
        "from_date_0": "1", "from_date_1": "1", "from_date_2": "1900",
        "to_date_0": "31", "to_date_1": "12", "to_date_2": "1901",
        "order": "relevance", "per_page": "50",
    }


@pytest.mark.asyncio
async def test_a_refused_window_still_sends_nothing(requests_seen):
    out = await _search({"query": "widget", "date_from": "1902-01-01",
                         "date_to": "1901-01-01"})
    assert requests_seen == [] and out["error"]


@pytest.mark.asyncio
async def test_the_audit_event_records_the_params_sent(requests_seen):
    """`api_call_start` carries the payload the audit trace stores as the
    call's request, so a harness can see the order a search ran under."""
    events = []

    async def on_chunk(ev):
        events.append(ev)

    await _search({"query": "widget"}, on_chunk=on_chunk)
    start = [e for e in events if e.get("type") == "api_call_start"]
    assert len(start) == 1
    assert start[0]["payload"]["order"] == "relevance"
    assert start[0]["payload"]["per_page"] == "50"


@pytest.mark.asyncio
async def test_the_feed_order_is_kept_in_the_result(monkeypatch):
    """The executor hands the model the rows in the order the feed listed them
    (relevance), never re-sorted by date: an older row first stays first."""
    rows = [(3, 1899), (1, 1901), (2, 1900)]

    def make(*a, **kw):
        kw.pop("verify", None)
        return _RealAsyncClient(*a, transport=httpx.MockTransport(
            lambda req: httpx.Response(200, text=_feed(rows, last=1))), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", make)
    set_request_provider_config({})
    out = await _search({"query": "widget"})
    assert [r["date"][:4] for r in out["results"]] == ["1899", "1901", "1900"]


def test_the_order_params_are_the_pair_and_the_page_size_is_fifty():
    assert CASE_LAW_ORDER_PARAMS == {"order": "relevance", "per_page": "50"}
    assert CASE_LAW_PAGE_SIZE == 50
    assert CASE_LAW_ORDER_PARAMS["per_page"] == str(CASE_LAW_PAGE_SIZE)


def test_a_full_relevance_page_is_counted_as_before():
    """`last` counts at ten a page under either order (batch 8 C: 52 of 52
    full pages kept the same link), so the count reads it unchanged."""
    feed = _feed([(i, 1901) for i in range(1, 51)], last=520)
    assert case_law_count(feed, 50) == {"shown": 50, "total": 5200, "total_exact": False,
                                        "total_min": 5191, "total_max": 5200}


# --- the note says the order the params ask for --------------------------------

def _data(n, last=None):
    rows = [(i, 1901) for i in range(1, n + 1)]
    return {"results": [{"url": f"u{i}"} for i in range(n)],
            **case_law_count(_feed(rows, last=last), n)}


def test_the_order_statement_names_relevance_not_date():
    assert CASE_LAW_ORDER_PARAMS["order"] == "relevance"
    assert CASE_LAW_RESULT_ORDER.startswith("most relevant first")
    assert "relevance" in CASE_LAW_RESULT_ORDER
    for old in ("newest", "recent", "by date rather than by relevance", "ranked"):
        assert old not in CASE_LAW_RESULT_ORDER


def test_all_three_order_statements_are_flipped_on_every_branch():
    notes = {
        "about": case_law_search_note({"query": "widget"}, _data(50, last=520)),
        "all": case_law_search_note({"query": "widget"}, _data(7, last=1)),
        "no figure": case_law_search_note({"query": "widget"}, _data(50)),
    }
    for name, note in notes.items():
        assert note, name
        assert "listed most relevant first, by relevance to the search words" in note, name
        for old in ("newest first", "most recent", "older", "by date rather than by relevance"):
            assert old not in note, (name, old)
    assert "the first 50 of about 5,200 judgments" in notes["about"]
    assert "the first 50 judgments" in notes["no figure"]
    for name in ("about", "no figure"):
        assert "Another judgment that matches can sit outside these 50" in notes[name]
    assert "outside these" not in notes["all"]


# --- the Phase-2 nudge names the first three as listed --------------------------

@pytest.mark.asyncio
async def test_the_nudge_names_the_first_three_in_the_feed_order():
    """"The 1-3 most relevant cases below" is true now because the nudge lists
    `results[:3]` as the feed ordered them; it must not re-sort them."""
    from src.agent.agent_shared import run_worker_tool

    rows = [{"url": f"https://caselaw.nationalarchives.gov.uk/ewhc/ch/{y}/{i}",
             "title": f"Widget Co v Example Ltd {i}", "ncn": f"({y}) EWHC {i} (Ch)",
             "date": f"{y}-01-15"} for i, y in ((3, 1899), (1, 1901), (2, 1900), (4, 1902))]
    raw = {"results": rows, "shown": 4, "total": 4, "total_exact": True,
           "total_min": 4, "total_max": 4, "query": "widget"}

    async def chunk(*a, **k):
        return None

    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps(raw))):
        out = await run_worker_tool("search_case_law", {"query": "widget"},
                                    "brief", chunk, "test-model")
    nudge = out[out.index("MANDATORY NEXT STEP"):]
    listed = [line.split('"')[1] for line in nudge.splitlines() if line.strip().startswith("- url:")]
    assert listed == [r["url"] for r in rows[:3]]
    assert "most relevant first" in out[:out.index("MANDATORY NEXT STEP")]
