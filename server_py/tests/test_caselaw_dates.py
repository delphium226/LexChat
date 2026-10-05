"""P3.9: the case-law date filter applies.

`search_case_law` sent `date_from`/`date_to` to the National Archives feed,
which ignores both: a 2025-only window returned the same 50 results as no
window, so the model's dates and the lawyer's date range (intersected into the
same params) both silently did nothing. The feed honours the advanced search's
day/month/year form, `from_date_0/1/2` and `to_date_0/1/2`, which is NOT in its
published spec. These tests pin the params built, the intersection, and the
refusal of an impossible or malformed window (no request is made). The live
half of the acceptance is `python -m tools.lex_probe --caselaw`.

No network: an `httpx.MockTransport` records each request.
"""
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from src.agent.provider_factory import set_request_provider_config
from src.agent.tools import executor
from src.agent.tools.caselaw import case_law_date_window
from src.utils.search_scope import case_law_search_note

_RealAsyncClient = httpx.AsyncClient

_FEED = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:tna="https://caselaw.nationalarchives.gov.uk"><title>t</title>'
    '<link href="https://caselaw.nationalarchives.gov.uk/atom.xml?query=widget&amp;page=1" rel="last"/>'
    "<entry><title>Widget Co v Example Ltd</title>"
    '<link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/1"/>'
    "<published>1901-06-01T00:00:00Z</published></entry></feed>"
)


@pytest.fixture
def requests_seen(monkeypatch):
    seen = []

    def make(*a, **kw):
        kw.pop("verify", None)

        def handler(req):
            seen.append(req)
            return httpx.Response(200, text=_FEED)

        return _RealAsyncClient(*a, transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(httpx, "AsyncClient", make)
    set_request_provider_config({})
    yield seen
    set_request_provider_config({})


def _params(req) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}


async def _search(args, cfg=None):
    set_request_provider_config(cfg or {})
    return json.loads(await executor.execute_worker_tool("search_case_law", args))


@pytest.mark.asyncio
async def test_model_dates_are_sent_in_the_form_the_feed_honours(requests_seen):
    out = await _search({"query": "widget", "date_from": "1901-01-01",
                         "date_to": "1901-12-31"})
    p = _params(requests_seen[0])
    assert {k: p[k] for k in p if "date" in k} == {
        "from_date_0": "1", "from_date_1": "1", "from_date_2": "1901",
        "to_date_0": "31", "to_date_1": "12", "to_date_2": "1901",
    }
    # The ignored names are not sent any more.
    assert "date_from" not in p and "date_to" not in p
    assert out["dates"] == {"from": "1901-01-01", "to": "1901-12-31"}


@pytest.mark.asyncio
async def test_an_undated_search_sends_no_date_and_reports_none(requests_seen):
    out = await _search({"query": "widget"})
    assert not [k for k in _params(requests_seen[0]) if "date" in k]
    assert "dates" not in out


@pytest.mark.asyncio
async def test_the_lawyers_dates_intersect_with_the_models(requests_seen):
    await _search({"query": "widget", "date_from": "1899-03-01", "date_to": "1902-12-31"},
                  {"_date_from": "1900-01-01", "_date_to": "1901-12-31"})
    p = _params(requests_seen[0])
    assert (p["from_date_2"], p["from_date_1"], p["from_date_0"]) == ("1900", "1", "1")
    assert (p["to_date_2"], p["to_date_1"], p["to_date_0"]) == ("1901", "12", "31")


@pytest.mark.asyncio
async def test_the_lawyers_dates_alone_still_apply(requests_seen):
    await _search({"query": "widget"}, {"_date_from": "1900-01-01"})
    p = _params(requests_seen[0])
    assert p["from_date_2"] == "1900" and "to_date_2" not in p


@pytest.mark.asyncio
async def test_a_start_after_the_end_is_refused_without_a_request(requests_seen):
    out = await _search({"query": "widget", "date_from": "1902-01-01",
                         "date_to": "1901-01-01"})
    assert requests_seen == []
    assert out["results"] == [] and out["shown"] == 0
    assert "The date window is empty" in out["error"]
    assert "lawyer" not in out["error"]


@pytest.mark.asyncio
async def test_a_window_emptied_by_the_intersection_is_refused_and_says_why(requests_seen):
    out = await _search({"query": "widget", "date_from": "1899-01-01",
                         "date_to": "1899-12-31"},
                        {"_date_from": "1901-01-01", "_date_to": "1901-12-31"})
    assert requests_seen == []
    assert "from 1901-01-01 to 1899-12-31" in out["error"]
    assert "dates the lawyer set" in out["error"]


@pytest.mark.asyncio
async def test_a_malformed_date_is_refused_without_a_request(requests_seen):
    out = await _search({"query": "widget", "date_from": "01/01/1901"})
    assert requests_seen == []
    assert "YYYY-MM-DD" in out["error"]
    out = await _search({"query": "widget", "date_to": "1901-02-30"})
    assert requests_seen == [] and out["error"]


def test_a_year_or_month_is_widened_to_its_whole_span():
    w = case_law_date_window({"date_from": "1900", "date_to": "1901-02"}, {})
    assert w["error"] is None
    assert w["dates"] == {"from": "1900-01-01", "to": "1901-02-28"}
    assert (w["params"]["to_date_0"], w["params"]["to_date_1"]) == ("28", "2")


def test_the_window_note_names_the_dates_it_ran_under():
    data = {"results": [{"url": "u"}], "shown": 1, "total": 1, "total_exact": True,
            "total_min": 1, "total_max": 1,
            "dates": {"from": "1900-01-01", "to": "1901-12-31"}}
    note = case_law_search_note({"query": "widget", "court": "ewhc/ch"}, data)
    assert "(court: ewhc/ch; dated 1900-01-01 to 1901-12-31)" in note
    data["dates"] = {"from": "1900-01-01", "to": None}
    assert "(dated from 1900-01-01)" in case_law_search_note({"query": "w"}, data)
    data["dates"] = {"from": None, "to": "1901-12-31"}
    assert "(dated up to 1901-12-31)" in case_law_search_note({"query": "w"}, data)


def test_new_text_trips_no_detector():
    """The refusal messages and the dated window note reach the model, which can
    echo them; screened against every answer detector, as P3.23's note is."""
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
    texts = [
        case_law_date_window({"date_from": "1902-01-01", "date_to": "1901-01-01"}, {})["error"],
        case_law_date_window({"date_from": "1899-01-01", "date_to": "1899-12-31"},
                             {"_date_from": "1901-01-01"})["error"],
        case_law_date_window({"date_from": "soon"}, {})["error"],
    ]
    data = {"results": [{"url": "u"}] * 50, "shown": 50, "total": 5200,
            "total_exact": False, "total_min": 5191, "total_max": 5200}
    for dates in ({"from": "1900-01-01", "to": "1901-12-31"},
                  {"from": "1900-01-01", "to": None}, {"from": None, "to": "1901-12-31"}):
        texts.append(case_law_search_note({"query": "widget"}, {**data, "dates": dates}))
    for text in texts:
        assert text
        for rx in (NEG_ASSERTED, NOT_FOUND, NEG_BLAMED_INDEX, NEG_BLAMED_USER,
                   NEG_LIMITS, NEG_TERMS, HALT_PARAPHRASE, HALT_AS_TIMEOUT,
                   IN_FORCE_CLAIM, OPENER_VOCAB, SCOTS_CASELAW_GAP, _CUR_DISCLOSED):
            assert not rx.search(text), (rx.pattern[:40], text)
        assert derivation_claims(text)[0] == []
        for s in _sentences(text):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
            assert not _currency_asserted(s), s
            assert negcurrency_claim(s)[0] is None, s
