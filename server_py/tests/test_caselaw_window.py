"""P3.23: tell the model how many case-law results there were, not how many it
was shown.

`search_case_law` returned `"total": len(entries)`, never more than the 50-row
page, so `total: 50` read as "every match seen" when the feed held thousands.
The real figure is in the feed's `<link rel="last">`, and it is counted at TEN
judgments a page whatever page size was asked for (measured live 2026-10-05,
batch 7 D: one query gives `last` page 520 with 50 rows a page; paging finds
5,193; page 520 at `per_page=10` holds 3). So:

* `caselaw.case_law_count` reports `shown` and the matching total apart
  (`total`, `total_exact`, `total_min`, `total_max`);
* `search_scope.case_law_search_note` states the window in P2.2's form,
  naming today's order (newest first; P3.22 flips it);
* the zero-result note and the Phase-2 nudge in `agent_shared` stay keyed on
  the SHOWN count, since `total` is now an estimate.

Fixtures are synthetic ("Widget Co v Example Ltd"); no network.
"""
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.agent.tools import executor
from src.agent.tools.caselaw import (
    CASE_LAW_PAGE_SIZE,
    _parse_case_law_last_page,
    case_law_count,
)
from src.utils.search_scope import (
    CASE_LAW_RESULT_ORDER,
    case_law_search_note,
    strip_scope_blocks,
)

_RealAsyncClient = httpx.AsyncClient
_BASE = "https://caselaw.nationalarchives.gov.uk/atom.xml?query=widget"


def _entry(i: int) -> str:
    return (
        "<entry>"
        f"<title>Widget Co v Example Ltd {i}</title>"
        f'<link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/{i}"/>'
        "<published>1901-01-15T00:00:00Z</published>"
        f'<tna:identifier slug="ewhc/ch/1901/{i}" type="ukncn">[1901] EWHC {i} (Ch)</tna:identifier>'
        "</entry>"
    )


def _feed(n: int, last=None) -> str:
    links = f'<link href="{_BASE}&amp;page=1" rel="first"/>'
    if last is not None:
        links += f'<link href="{_BASE}&amp;page={last}" rel="last"/>'
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:tna="https://caselaw.nationalarchives.gov.uk">'
        f"<title>Latest documents</title>{links}"
        + "".join(_entry(i) for i in range(1, n + 1))
        + "</feed>"
    )


# --- the parser ---------------------------------------------------------------

def test_last_page_is_read_from_the_link():
    assert _parse_case_law_last_page(_feed(50, last=520)) == 520
    assert _parse_case_law_last_page(_feed(0, last=0)) == 0
    assert _parse_case_law_last_page(_feed(50)) is None
    assert _parse_case_law_last_page("not xml") is None


def test_a_full_page_reports_the_total_from_the_last_link_at_ten_a_page():
    c = case_law_count(_feed(50, last=520), 50)
    assert c == {"shown": 50, "total": 5200, "total_exact": False,
                 "total_min": 5191, "total_max": 5200}


def test_a_page_that_is_not_full_is_the_whole_set_whatever_last_says():
    """The "empty last page" case: 19 rows with `last` page 2 (seen live on a
    dated query). Read at 50 a page that link said up to 100; the page not
    being full says 19 exactly."""
    c = case_law_count(_feed(19, last=2), 19)
    assert c == {"shown": 19, "total": 19, "total_exact": True,
                 "total_min": 19, "total_max": 19}


def test_no_last_link_on_a_full_page_is_reported_as_unknown_not_as_complete():
    c = case_law_count(_feed(50), 50)
    assert c["shown"] == 50 and c["total"] == 50
    assert c["total_exact"] is False and c["total_max"] is None


def test_zero_results():
    assert case_law_count(_feed(0, last=0), 0)["total"] == 0


def test_a_full_page_whose_link_fits_in_it_is_exact():
    c = case_law_count(_feed(50, last=5), 50)
    assert c["total"] == 50 and c["total_exact"] is True


# --- the executor -------------------------------------------------------------

@pytest.fixture
def serve(monkeypatch):
    def install(body):
        def make(*a, **kw):
            kw.pop("verify", None)
            return _RealAsyncClient(*a, transport=httpx.MockTransport(
                lambda req: httpx.Response(200, text=body)), **kw)
        monkeypatch.setattr(httpx, "AsyncClient", make)
    return install


@pytest.mark.asyncio
async def test_the_tool_reports_shown_and_total_apart(serve):
    serve(_feed(CASE_LAW_PAGE_SIZE, last=520))
    out = json.loads(await executor.execute_worker_tool(
        "search_case_law", {"query": "widget"}))
    assert len(out["results"]) == 50
    assert out["shown"] == 50
    assert out["total"] == 5200           # was 50: the defect
    assert (out["total_min"], out["total_max"]) == (5191, 5200)
    assert out["total_exact"] is False


@pytest.mark.asyncio
async def test_the_tool_reports_a_short_page_as_exact(serve):
    serve(_feed(7, last=1))
    out = json.loads(await executor.execute_worker_tool(
        "search_case_law", {"query": "widget"}))
    assert out["shown"] == out["total"] == 7 and out["total_exact"] is True


# --- the window note ------------------------------------------------------------

def _data(n, last=None):
    return {"results": [{"url": f"u{i}"} for i in range(n)],
            **case_law_count(_feed(n, last=last), n)}


def test_window_note_states_shown_of_about_total_and_the_order():
    note = case_law_search_note({"query": "widget"}, _data(50, last=520))
    assert "the 50 most recent of about 5,200 judgments" in note
    assert "between 5,191 and 5,200" in note
    assert '"widget"' in note
    assert CASE_LAW_RESULT_ORDER in note and "newest first" in note


def test_window_note_names_the_court_when_one_was_set():
    note = case_law_search_note({"query": "widget", "court": "ewhc/ch"},
                                _data(50, last=520))
    assert "(court: ewhc/ch)" in note


def test_window_note_on_a_complete_set_says_all():
    note = case_law_search_note({"query": "widget"}, _data(7, last=1))
    assert "all 7 judgment(s)" in note and "newest first" in note
    assert "most recent of" not in note


def test_window_note_without_a_figure_does_not_invent_one():
    note = case_law_search_note({"query": "widget"}, _data(50))
    assert "no figure for how many match in all" in note
    assert "about" not in note


def test_window_note_is_silent_on_zero_results_and_errors():
    assert case_law_search_note({"query": "widget"}, _data(0, last=0)) == ""
    assert case_law_search_note({"query": "widget"},
                                {"error": "x", "results": [], "total": 0}) == ""


def test_window_note_is_stripped_if_a_worker_echoes_it():
    for data in (_data(50, last=520), _data(7, last=1), _data(50)):
        note = case_law_search_note({"query": "widget"}, data)
        out, n = strip_scope_blocks("The answer." + note)
        assert n == 1 and out == "The answer."


def test_window_note_trips_no_detector():
    """Any text the product writes into a block the model can echo is read by
    every grader (batch 6 lesson). Screened on every branch, per sentence where
    the detector is per sentence."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED,
        NEG_BLAMED_INDEX, NEG_BLAMED_USER, NEG_LIMITS, NEG_TERMS, NOT_FOUND,
        OPENER_VOCAB, SCOTS_CASELAW_GAP, _CMC_CONTEXT, _CMC_DENIED,
        _CUR_DISCLOSED, _currency_asserted, _sentences, derivation_claims,
        negcurrency_claim,
    )
    notes = [
        case_law_search_note({"query": "widget", "court": "ewhc/ch"}, _data(50, last=520)),
        case_law_search_note({"query": "widget"}, _data(7, last=1)),
        case_law_search_note({"query": "widget"}, _data(50)),
        case_law_search_note({}, _data(50, last=520)),
    ]
    for note in notes:
        assert note
        for rx in (NEG_ASSERTED, NOT_FOUND, NEG_BLAMED_INDEX, NEG_BLAMED_USER,
                   NEG_LIMITS, NEG_TERMS, HALT_PARAPHRASE, HALT_AS_TIMEOUT,
                   IN_FORCE_CLAIM, OPENER_VOCAB, SCOTS_CASELAW_GAP, _CUR_DISCLOSED):
            assert not rx.search(note), (rx.pattern[:40], note)
        assert derivation_claims(note)[0] == []
        for s in _sentences(note):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
            assert not _currency_asserted(s), s
            assert negcurrency_claim(s)[0] is None, s


# --- agent_shared: keyed on the shown count ------------------------------------

async def _run(raw: dict) -> str:
    from src.agent.agent_shared import run_worker_tool

    async def chunk(*a, **k):
        return None

    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps(raw))):
        return await run_worker_tool("search_case_law", {"query": "widget"},
                                     "brief", chunk, "test-model")


@pytest.mark.asyncio
async def test_zero_shown_gets_the_zero_note_even_when_total_is_not_zero():
    """`total` is an estimate now; a page with nothing on it is a zero-result
    search whatever the estimate says, and must not get the Phase-2 nudge (which
    would list no judgments to fetch)."""
    raw = {"results": [], "shown": 0, "total": 10, "total_exact": False,
           "total_min": 1, "total_max": 10, "query": "widget"}
    out = await _run(raw)
    assert "This search returned 0 results" in out
    assert "MANDATORY NEXT STEP" not in out


@pytest.mark.asyncio
async def test_a_shown_page_gets_the_window_then_the_nudge():
    raw = {"results": [{"url": "https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/1",
                        "title": "Widget Co v Example Ltd", "ncn": "[1901] EWHC 1 (Ch)"}],
           "shown": 1, "total": 1, "total_exact": True, "total_min": 1,
           "total_max": 1, "query": "widget"}
    out = await _run(raw)
    assert "[SEARCH SCOPE — all 1 judgment(s)" in out
    assert out.index("[SEARCH SCOPE") < out.index("MANDATORY NEXT STEP")
    assert out.rstrip().endswith("]")
