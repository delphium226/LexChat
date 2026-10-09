"""P3.20: Scottish case law from the Scottish Courts and Tribunals Service.

The National Archives' Find Case Law holds no decision of the Court of
Session, the Sheriff Appeal Court, the Sheriff Courts or the High Court of
Justiciary. With `scts_caselaw_enabled` on, `search_case_law` also searches
SCTS's published judgments and returns them as a second list
(`scottish_results`, counts in `scottish`); `get_case_law_text` reads an SCTS
judgment PDF; and every text that says the Court of Session is absent from the
databases searched is swapped for one that is true, still naming what SCTS
does not hold. With it off, nothing changes (the dry run over every stored
input in `notes/batch12_C.md` is byte-identical to the base).

What this file pins, by seam:

1. the query (every term required, the fallback form, negations dropped);
2. the citation helpers (filename and text) and the slimmer (dedupe, dates);
3. the search: request shape, the any-term fallback, the per-request cap, fail-soft;
4. the judgment text: the host allowlist, the PDF read off the event loop, the guards;
5. the executor: both lists, either half failing, the gate, the text routing;
6. the Worker's notes and the sources rail;
7. the footer: keyed on this turn's records, byte-identical without them,
   screened against every detector;
8. the prompts and tool descriptions: swapped only when on, every site;
9. caching: both tools stay in CACHEABLE_TOOLS, the drafting override holds;
10. the grader, `replay_report scts`, both ways.

Synthetic names and URLs only ("Widget Co v Example Ltd", `2017csih99`).
No network: every HTTP call is an `httpx.MockTransport`.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src import prompts as P  # noqa: E402
from src.agent import agent_shared  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import executor, schemas, scts  # noqa: E402
from src.config import settings  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402

_RealAsyncClient = httpx.AsyncClient
# `net` stubs asyncio.sleep (the retry helper's backoff) module-wide; the
# concurrency test needs a sleep that really yields.
_real_sleep = asyncio.sleep

SEARCH_URL = scts.SCTS_SEARCH_URL
PDF_URL = "https://www.scotcourts.gov.uk/media/abc/2017csih99-widget-co-v-example-ltd.pdf"
PDF_URL_OLD = "https://www.scotcourts.gov.uk/media/def/p1901_02-gizmo-v-widget.pdf"
FCL_URL = "https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/1"


def _row(link="/media/abc/2017csih99-widget-co-v-example-ltd.pdf", title="Widget Co v Example Ltd",
         court="Court of Session", additional="2017-05-04T00:00:00Z", date="2017-05-10T00:00:00Z"):
    return {"title": title, "documentLink": link, "date": date, "court": [court],
            "sheriffdom": [], "judges": ["Lord Example"], "additionalDate": additional,
            "tags": [], "searchType": "Index"}


def _body(rows, total=None):
    return {"results": rows,
            "pagination": {"count": {"total": len(rows) if total is None else total,
                                     "start": 1, "end": len(rows)},
                           "page": {"current": 1, "total": 1, "limit": 10}}}


def _pdf(lines) -> bytes:
    """A minimal one-page PDF whose text is `lines` (pdfplumber reads it)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    ops = "BT /F1 11 Tf 14 TL 72 720 Td " + " ".join(f"({esc(x)}) Tj T*" for x in lines) + " ET"
    stream = ops.encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "scts_caselaw_enabled", True)
    set_request_provider_config({"_provider": "test", "_research_mode": "legislation_and_case_law"})
    yield
    set_request_provider_config({})


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(settings, "scts_caselaw_enabled", False)
    set_request_provider_config({"_provider": "test", "_research_mode": "legislation_and_case_law"})
    yield
    set_request_provider_config({})


@pytest.fixture
def net(monkeypatch):
    """Every httpx.AsyncClient goes through a MockTransport. `net.routes` maps
    (method, host) to a list of responses served in order (the last repeats);
    `net.seen` records every request."""
    seen, routes = [], {}

    def handler(request):
        seen.append(request)
        key = (request.method, request.url.host)
        script = routes.get(key)
        if not script:
            raise AssertionError(f"unexpected request {key} {request.url}")
        item = script.pop(0) if len(script) > 1 else script[0]
        if isinstance(item, Exception):
            raise item
        return item

    def make(*args, **kwargs):
        kwargs.pop("verify", None)
        return _RealAsyncClient(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make)

    async def no_sleep(d):
        return None
    monkeypatch.setattr(executor.asyncio, "sleep", no_sleep)

    class N:
        pass
    n = N()
    n.seen, n.routes = seen, routes
    n.client = make
    return n


def _sent(req):
    return json.loads(req.content.decode("utf-8"))


_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:tna="https://caselaw.nationalarchives.gov.uk">
  <entry>
    <title>Gizmo Ltd v Widget plc</title>
    <link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/1"/>
    <published>1901-01-15T00:00:00Z</published>
    <tna:identifier slug="ewhc/ch/1901/1" type="ukncn">[1901] EWHC 1 (Ch)</tna:identifier>
  </entry>
</feed>"""


# ---------------------------------------------------------------------------
# 1. The query
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,required,any_term", [
    ('"widget duty" gizmo', '+"widget duty" +gizmo', '"widget duty" gizmo'),
    ("widget gizmo", "+widget +gizmo", "widget gizmo"),
    # an OR run is one term with alternatives
    ('"widget duty" OR "gizmo duty" Example', '+("widget duty" | "gizmo duty") +Example',
     '("widget duty" | "gizmo duty") Example'),
    # AND is not an operator in SCTS: dropped
    ("widget AND gizmo", "+widget +gizmo", "widget gizmo"),
    # a negation is DROPPED, never sent and never made required
    ("widget -gizmo", "+widget", ""),
    ('widget -"gizmo duty" Example', "+widget +Example", "widget Example"),
    ("widget NOT gizmo Example", "+widget +Example", "widget Example"),
    # inner punctuation: one phrase
    ("regulation 3(2)(a)", '+regulation +"3 2 a"', 'regulation "3 2 a"'),
    ("non-disclosure widget", '+"non-disclosure" +widget', '"non-disclosure" widget'),
    # square brackets cleaned (a citation searched as words)
    ('"[1901] CSIH 9"', '+"1901 CSIH 9"', ""),
    # an unbalanced quote (no stored query had one) degrades to words; no stray quote is sent
    ('"widget duty gizmo', "+widget +duty +gizmo", "widget duty gizmo"),
    ('"widget" "duty', '+"widget" +duty', '"widget" duty'),
    # a single term has no different any-term form: no fallback
    ("widget", "+widget", ""),
    ("", "", ""),
    ('"" OR', "", ""),
    ("AND NOT", "", ""),
])
def test_the_query_forms(query, required, any_term):
    assert scts.scts_query_forms(query) == (required, any_term)


def test_no_form_ever_carries_a_minus_or_a_bare_and():
    for q in ("a -b", 'a -"b c"', "a AND b", "-a b", "a - b"):
        req, anyf = scts.scts_query_forms(q)
        for form in (req, anyf):
            assert " -" not in f" {form}" and " AND " not in f" {form} "


# ---------------------------------------------------------------------------
# 2. Citations and the slimmer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("link,ncn", [
    ("/media/a/2017csih99-widget.pdf", "[2017] CSIH 99"),
    ("/media/a/2017csoh9.pdf", "[2017] CSOH 9"),
    ("/media/a/2026hcjac4-widget.pdf", "[2026] HCJAC 4"),
    ("/media/a/2026sacciv63-widget.pdf", "[2026] SAC (Civ) 63"),
    ("/media/a/2026saccrim7-widget.pdf", "[2026] SAC (Crim) 7"),
    ("/media/a/2025scgla002-widget.pdf", "[2025] SC GLA 2"),
    ("/media/a/2026ut59-widget.pdf", "[2026] UT 59"),
    ("/media/a/p1901_02-widget.pdf", None),            # an old court reference
    ("/media/a/2019scotland-widget.pdf", None),        # a year then a word, no number
    ("/media/a/widget-2017csih99.pdf", None),          # not at the start
    ("/media/a/2017csih99x-widget.pdf", None),         # the number must end there
    ("", None),
])
def test_citation_from_the_filename(link, ncn):
    assert scts.ncn_from_filename(link) == ncn


def test_citation_from_the_text_is_read_from_the_opening_only():
    assert scts.ncn_from_text("OPINION\n[2017] CSIH 99\nWidget") == "[2017] CSIH 99"
    assert scts.ncn_from_text("[2026] SAC (Civ) 63 widget") == "[2026] SAC (Civ) 63"
    assert scts.ncn_from_text("x [2025] SC GLA 2 y") == "[2025] SC GLA 2"
    assert scts.ncn_from_text("no citation here") is None
    # a citation cited deep in the judgment is another case's, not this one's
    assert scts.ncn_from_text("x" * 4100 + " [2001] CSIH 1") is None


def test_the_slimmer_dedupes_dates_and_keeps_citations_out_of_dates():
    rows = scts.slim_scts_results(_body([
        _row(),
        _row(),                                            # a repeated row (354 rows, 352 judgments)
        _row(link="/media/def/p1901_02-gizmo-v-widget.pdf", title="Gizmo v Widget [2099] CSIH 1",
             additional="2012-01-13T00:00:00Z", date="2015-03-01T00:00:00Z"),
        {"title": "no link"},                              # no documentLink: dropped
        "not a row",
    ]))
    assert [r["url"] for r in rows] == [PDF_URL, PDF_URL_OLD]
    first, second = rows
    assert first == {"title": "Widget Co v Example Ltd", "court": "Court of Session",
                     "judges": ["Lord Example"], "decision_date": "2017-05-04",
                     "published": "2017-05-10", "ncn": "[2017] CSIH 99", "url": PDF_URL}
    # the decision date is additionalDate, never a year read from a citation
    assert second["decision_date"] == "2012-01-13" and second["published"] == "2015-03-01"
    # a citation-like string in a TITLE is not the judgment's citation
    assert second["ncn"] is None
    assert set(first) == {"title", "court", "judges", "decision_date", "published", "ncn", "url"}


def test_the_slimmer_survives_odd_bodies():
    for body in (None, {}, {"results": None}, {"results": "x"}, [], "x"):
        assert scts.slim_scts_results(body) == []


# ---------------------------------------------------------------------------
# 3. The search
# ---------------------------------------------------------------------------

async def _search(net, q, dates=None):
    async with net.client() as c:
        return await scts.search_scts(q, dates, c)


async def test_the_request_carries_required_terms_the_date_window_and_the_page(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    out = await _search(net, '"widget duty" gizmo', {"from": "2012-01-01", "to": "2012-12-31"})
    assert len(net.seen) == 1
    body = _sent(net.seen[0])
    assert body == {"query": '+"widget duty" +gizmo',
                    "filters": [{"field": "AdditionalDate", "value": "2012-01-01|2012-12-31"}],
                    "page": 1, "limit": scts.SCTS_PAGE_SIZE, "indexType": "Judgments", "category": ""}
    assert str(net.seen[0].url) == SEARCH_URL
    assert out["block"]["status"] == "ok" and out["block"]["match"] == "all"
    assert out["block"]["dates"] == {"from": "2012-01-01", "to": "2012-12-31"}
    assert [r["url"] for r in out["results"]] == [PDF_URL]


async def test_an_open_ended_window_and_no_window(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    await _search(net, "widget gizmo", {"from": "2016-01-01", "to": None})
    await _search(net, "widget gizmo", None)
    assert _sent(net.seen[0])["filters"] == [{"field": "AdditionalDate", "value": "2016-01-01|"}]
    assert _sent(net.seen[1])["filters"] == []


async def test_zero_with_every_term_falls_back_once_to_any_term(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [
        httpx.Response(200, json=_body([])),
        httpx.Response(200, json=_body([_row()] * 10, total=12712)),
    ]
    out = await _search(net, '"widget duty" gizmo')
    assert [_sent(r)["query"] for r in net.seen] == ['+"widget duty" +gizmo', '"widget duty" gizmo']
    assert out["block"]["match"] == "any" and out["block"]["query_sent"] == '"widget duty" gizmo'
    assert out["block"]["shown"] == 1        # ten rows of one judgment, deduped
    assert out["block"]["total"] == 12712


async def test_no_fallback_for_a_single_term_or_when_every_term_matched(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([]))]
    out = await _search(net, "widget")
    assert len(net.seen) == 1 and out["block"]["status"] == "ok" and out["block"]["shown"] == 0
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    await _search(net, "widget gizmo")
    assert len(net.seen) == 2


async def test_a_short_page_counts_distinct_judgments_not_repeated_rows(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [
        httpx.Response(200, json=_body([_row(), _row()], total=2))]
    out = await _search(net, "widget gizmo")
    assert out["block"]["shown"] == 1 and out["block"]["total"] == 1
    # a full page keeps the server's total
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body(
        [_row(link=f"/media/x/2017csih{i}-w.pdf") for i in range(10)], total=354))]
    out = await _search(net, "widget gizmo")
    assert out["block"]["shown"] == 10 and out["block"]["total"] == 354


async def test_an_error_is_an_error_and_never_raises(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(400, json={"x": 1})]
    out = await _search(net, "widget gizmo")
    assert out["block"]["status"] == "error" and out["results"] == []
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, text="not json")]
    assert (await _search(net, "widget gizmo"))["block"]["status"] == "error"
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [ValueError("boom")]
    assert (await _search(net, "widget gizmo"))["block"]["status"] == "error"


async def test_a_failed_fallback_leaves_the_all_terms_zero(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [
        httpx.Response(200, json=_body([])), httpx.Response(400, json={})]
    out = await _search(net, "widget gizmo")
    assert out["block"]["status"] == "ok" and out["block"]["match"] == "all"
    assert out["block"]["shown"] == 0


async def test_nothing_to_search_makes_no_call(on, net):
    out = await _search(net, "AND -widget")
    assert out["block"]["status"] == "not_searched" and net.seen == []


async def test_the_per_request_cap(on, net):
    state = scts.request_state()
    state["search_calls"] = scts.SCTS_MAX_SEARCH_CALLS
    out = await _search(net, "widget gizmo")
    assert out["block"]["status"] == "capped" and out["block"]["cap"] == scts.SCTS_MAX_SEARCH_CALLS
    assert net.seen == []
    # one call left: the all-terms search runs, its fallback does not
    state["search_calls"] = scts.SCTS_MAX_SEARCH_CALLS - 1
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([]))]
    out = await _search(net, "widget gizmo")
    assert len(net.seen) == 1 and out["block"]["status"] == "ok" and out["block"]["shown"] == 0


def test_the_request_state_lives_on_the_request_config():
    cfg = {"_provider": "test"}
    set_request_provider_config(cfg)
    try:
        s1 = scts.request_state()
        s1["search_calls"] = 3
        assert scts.request_state() is s1 and cfg["_scts_state"] is s1
    finally:
        set_request_provider_config({})
    # without a request config: a fresh state each time, and the shared
    # default is never written to
    a, b = scts.request_state(), scts.request_state()
    a["search_calls"] = 9
    assert b["search_calls"] == 0
    from src.agent.provider_factory import get_request_provider_config
    assert "_scts_state" not in get_request_provider_config()


async def test_the_concurrency_limit_holds_across_requests(on, net, monkeypatch):
    live, peak = {"n": 0}, {"n": 0}
    real = executor._request_with_retry

    async def slow(client, method, url, **kw):
        live["n"] += 1
        peak["n"] = max(peak["n"], live["n"])
        await _real_sleep(0.01)
        live["n"] -= 1
        return await real(client, method, url, **kw)

    monkeypatch.setattr(executor, "_request_with_retry", slow)
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    await asyncio.gather(*[_search(net, "widget gizmo") for _ in range(6)])
    # the calls did overlap, up to the limit and never past it
    assert peak["n"] == scts.SCTS_CONCURRENCY == 2 and len(net.seen) == 6


async def test_anything_unexpected_inside_the_search_is_an_error_not_a_raise(on, net, monkeypatch):
    def boom(body):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(scts, "slim_scts_results", boom)
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    out = await _search(net, "widget gizmo")
    assert out == {"results": [], "block": {**out["block"], "status": "error"}}


async def test_titles_are_kept_for_the_text_fetch(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    await _search(net, "widget gizmo")
    assert scts.request_state()["titles"][PDF_URL] == {
        "title": "Widget Co v Example Ltd", "court": "Court of Session", "decision_date": "2017-05-04"}


# ---------------------------------------------------------------------------
# 4. The judgment text
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,ok", [
    (PDF_URL, True),
    ("https://www.scotcourts.gov.uk/media/abc/X.PDF", True),
    ("http://www.scotcourts.gov.uk/media/abc/x.pdf", False),      # https only
    ("https://www.scotcourts.gov.uk/media/abc/x.html", False),    # a PDF only
    ("https://www.scotcourts.gov.uk/media/abc/x.pdf?x=1", False), # no query string
    ("https://scotcourts.gov.uk.example/media/x.pdf", False),     # the host exactly
    ("https://www.scotcourts.gov.uk.example.org/media/x.pdf", False),
    ("https://evil-www.scotcourts.gov.uk/media/x.pdf", False),
    ("https://api.pa.web.scotcourts.gov.uk/media/x.pdf", False),
    (FCL_URL, False),
    ("", False),
    (None, False),
])
def test_the_scottish_text_route_host_allowlist(url, ok):
    assert scts.is_scts_judgment_url(url) is ok


def test_the_pdf_is_read_with_pdfplumber():
    text = scts._pdf_text(_pdf(["OPINION OF THE COURT", "[2017] CSIH 99", "Widget Co v Example Ltd"]))
    assert "[2017] CSIH 99" in text and "Widget Co v Example Ltd" in text


async def _fetch(net, url=PDF_URL):
    async with net.client() as c:
        return await scts.fetch_scts_judgment(url, c)


async def test_the_text_fetch_reads_the_pdf_off_the_event_loop(on, net, monkeypatch):
    calls = []
    real = asyncio.to_thread

    async def spy(fn, *a, **k):
        calls.append(fn)
        return await real(fn, *a, **k)

    monkeypatch.setattr(scts.asyncio, "to_thread", spy)
    scts.request_state()["titles"][PDF_URL] = {"title": "Widget Co v Example Ltd",
                                              "court": "Court of Session", "decision_date": "2017-05-04"}
    net.routes[("GET", "www.scotcourts.gov.uk")] = [
        httpx.Response(200, content=_pdf(["OPINION", "[2017] CSIH 98", "The reclaiming motion is refused."]))]
    out = await _fetch(net)
    assert calls == [scts._pdf_text]
    assert out["url"] == PDF_URL and out["title"] == "Widget Co v Example Ltd"
    assert out["court"] == "Court of Session" and out["decision_date"] == "2017-05-04"
    # the filename's citation wins over one the text prints (a judgment can
    # print its own citation wrongly; the filename agrees with the URL)
    assert out["ncn"] == "[2017] CSIH 99"
    assert "reclaiming motion is refused" in out["text"]
    assert net.seen[0].headers["accept"] == "application/pdf"


async def test_a_descriptive_filename_takes_the_citation_from_the_text(on, net):
    net.routes[("GET", "www.scotcourts.gov.uk")] = [
        httpx.Response(200, content=_pdf(["OPINION", "[2017] CSIH 98"]))]
    out = await _fetch(net, PDF_URL_OLD)
    assert out["ncn"] == "[2017] CSIH 98" and out["title"] == ""
    net.routes[("GET", "www.scotcourts.gov.uk")] = [httpx.Response(200, content=_pdf(["No citation"]))]
    out = await _fetch(net, PDF_URL_OLD)
    assert out["ncn"] == ""


@pytest.mark.parametrize("response,expect", [
    (httpx.Response(404, content=b"%PDF"), "HTTP 404"),
    (httpx.Response(200, content=b"<html>not a pdf</html>"), "did not return a PDF"),
    (httpx.Response(200, content=b"%PDF-1.4 broken"), "Could not read"),
])
async def test_a_bad_fetch_is_an_error_result(on, net, response, expect):
    net.routes[("GET", "www.scotcourts.gov.uk")] = [response]
    out = await _fetch(net)
    assert out["text"] == "" and expect in out["error"] and out["url"] == PDF_URL


async def test_an_empty_text_and_a_too_large_pdf_are_errors(on, net, monkeypatch):
    net.routes[("GET", "www.scotcourts.gov.uk")] = [httpx.Response(200, content=_pdf([]))]
    out = await _fetch(net)
    assert "No text" in out["error"]
    monkeypatch.setattr(scts, "SCTS_PDF_MAX_BYTES", 10)
    net.routes[("GET", "www.scotcourts.gov.uk")] = [httpx.Response(200, content=_pdf(["x"]))]
    out = await _fetch(net)
    assert "too large" in out["error"]


async def test_the_text_cap_makes_no_call(on, net):
    scts.request_state()["pdf_calls"] = scts.SCTS_MAX_PDF_CALLS
    out = await _fetch(net)
    assert net.seen == [] and out["text"] == "" and "limit" in out["error"]


async def test_real_fetches_count_toward_the_text_cap(on, net):
    """The counter, not a seeded value: SCTS_MAX_PDF_CALLS real fetches, then
    the next is refused with no call made."""
    net.routes[("GET", "www.scotcourts.gov.uk")] = [httpx.Response(200, content=_pdf(["[2017] CSIH 99"]))]
    for _ in range(scts.SCTS_MAX_PDF_CALLS):
        assert not (await _fetch(net)).get("error")
    assert len(net.seen) == scts.SCTS_MAX_PDF_CALLS
    out = await _fetch(net)
    assert "limit" in out["error"] and len(net.seen) == scts.SCTS_MAX_PDF_CALLS
    assert scts.request_state()["pdf_calls"] == scts.SCTS_MAX_PDF_CALLS


async def test_real_searches_count_toward_the_search_cap(on, net):
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([_row()]))]
    for _ in range(scts.SCTS_MAX_SEARCH_CALLS):
        assert (await _search(net, "widget"))["block"]["status"] == "ok"
    assert len(net.seen) == scts.SCTS_MAX_SEARCH_CALLS
    out = await _search(net, "widget")
    assert out["block"]["status"] == "capped" and len(net.seen) == scts.SCTS_MAX_SEARCH_CALLS
    # a fallback is a call too: it counts toward the same cap
    scts.request_state()["search_calls"] = 0
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body([]))]
    await _search(net, "widget gizmo")
    assert scts.request_state()["search_calls"] == 2


async def test_a_reported_total_below_the_rows_shown_is_raised_to_them(on, net):
    """A body whose `total` is below the rows it carries (an inconsistent
    count) never reports fewer judgments than were shown."""
    rows = [_row(link=f"/media/x/2017csih{i}-w.pdf") for i in range(15)]
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json=_body(rows, total=11))]
    out = await _search(net, "widget gizmo")
    assert out["block"]["shown"] == 15 and out["block"]["total"] == 15
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [httpx.Response(200, json={
        "results": [_row()], "pagination": {}})]
    out = await _search(net, "widget gizmo")
    assert out["block"]["shown"] == 1 and out["block"]["total"] == 1


# ---------------------------------------------------------------------------
# 5. The executor
# ---------------------------------------------------------------------------

def _routes_both(net, fcl=None, scot=None):
    net.routes[("GET", "caselaw.nationalarchives.gov.uk")] = [
        fcl if fcl is not None else httpx.Response(200, text=_FEED)]
    net.routes[("POST", "api.pa.web.scotcourts.gov.uk")] = [
        scot if scot is not None else httpx.Response(200, json=_body([_row()]))]


async def test_setting_off_searches_find_case_law_alone_and_the_shape_is_unchanged(off, net):
    _routes_both(net)
    out = json.loads(await executor.execute_worker_tool("search_case_law", {"query": "widget"}))
    assert {r.url.host for r in net.seen} == {"caselaw.nationalarchives.gov.uk"}
    assert set(out) == {"results", "shown", "total", "total_exact", "total_min", "total_max", "query"}


async def test_setting_on_returns_both_lists(on, net):
    _routes_both(net)
    out = json.loads(await executor.execute_worker_tool(
        "search_case_law", {"query": "widget gizmo", "court": "ewhc/ch", "date_from": "1900-01-01"}))
    assert sorted(r.url.host for r in net.seen) == ["api.pa.web.scotcourts.gov.uk",
                                                  "caselaw.nationalarchives.gov.uk"]
    assert out["results"][0]["url"] == FCL_URL and out["shown"] == 1
    assert out["scottish_results"][0]["url"] == PDF_URL
    assert out["scottish"]["status"] == "ok"
    sent = _sent(next(r for r in net.seen if r.method == "POST"))
    # the court code is Find Case Law's: never sent to SCTS; the dates are
    assert "court" not in json.dumps(sent).lower().replace("court of session", "")
    assert sent["filters"] == [{"field": "AdditionalDate", "value": "1900-01-01|"}]


async def test_the_research_type_gates_the_search(net, monkeypatch):
    monkeypatch.setattr(settings, "scts_caselaw_enabled", True)
    set_request_provider_config({"_provider": "t", "_research_mode": "legislation_only"})
    try:
        _routes_both(net)
        out = json.loads(await executor.execute_worker_tool("search_case_law", {"query": "widget"}))
        assert "scottish" not in out
    finally:
        set_request_provider_config({})


async def test_find_case_law_failing_leaves_the_scottish_list(on, net):
    _routes_both(net, fcl=httpx.Response(500, text="down"))
    out = json.loads(await executor.execute_worker_tool("search_case_law", {"query": "widget gizmo"}))
    assert out["error"].startswith("The Find Case Law search failed (HTTP 500)")
    assert out["results"] == [] and out["scottish"]["status"] == "ok"
    assert out["scottish_results"][0]["url"] == PDF_URL


async def test_an_invalid_court_code_keeps_its_message_beside_the_scottish_list(on, net):
    _routes_both(net, fcl=httpx.Response(400, text="bad court"))
    out = json.loads(await executor.execute_worker_tool(
        "search_case_law", {"query": "widget gizmo", "court": "csoh"}))
    assert out["error"].startswith("Invalid court filter 'csoh'")
    assert out["scottish"]["status"] == "ok"


async def test_scts_failing_leaves_find_case_law_unchanged(on, net):
    _routes_both(net, scot=httpx.Response(400, json={}))
    out = json.loads(await executor.execute_worker_tool("search_case_law", {"query": "widget gizmo"}))
    assert out["results"][0]["url"] == FCL_URL and "error" not in out
    assert out["scottish"]["status"] == "error" and out["scottish_results"] == []


async def test_a_bad_date_is_refused_before_either_call(on, net):
    out = json.loads(await executor.execute_worker_tool(
        "search_case_law", {"query": "widget", "date_from": "last year"}))
    assert out["error"] and net.seen == [] and "scottish" not in out


async def test_the_text_route_by_host(on, net):
    net.routes[("GET", "www.scotcourts.gov.uk")] = [httpx.Response(200, content=_pdf(["[2017] CSIH 99"]))]
    out = json.loads(await executor.execute_worker_tool("get_case_law_text", {"url": PDF_URL}))
    assert out["ncn"] == "[2017] CSIH 99" and [r.url.host for r in net.seen] == ["www.scotcourts.gov.uk"]
    # anything that is not Find Case Law or an SCTS PDF: refused, no call
    for url in ("https://example.org/judgment", "https://www.scotcourts.gov.uk/media/x.html",
                "http://www.scotcourts.gov.uk/media/x.pdf"):
        out = json.loads(await executor.execute_worker_tool("get_case_law_text", {"url": url}))
        assert out == {"error": executor.GET_CASE_LAW_TEXT_REFUSAL, "url": url, "text": ""}
    assert len(net.seen) == 1


async def test_setting_off_refuses_an_scts_url_and_keeps_find_case_law(off, net):
    out = json.loads(await executor.execute_worker_tool("get_case_law_text", {"url": PDF_URL}))
    assert out["error"] == executor.GET_CASE_LAW_TEXT_REFUSAL and net.seen == []
    akn = ('<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><judgment>'
           '<p>Dismissed.</p></judgment></akomaNtoso>')
    net.routes[("GET", "caselaw.nationalarchives.gov.uk")] = [httpx.Response(200, text=akn)]
    out = json.loads(await executor.execute_worker_tool("get_case_law_text", {"url": FCL_URL}))
    assert "Dismissed." in out["text"] and str(net.seen[0].url) == FCL_URL + "/data.xml"
    # a missing url is the error it always was
    assert await executor.execute_worker_tool("get_case_law_text", {}) == "Error executing tool: 'url'"


# ---------------------------------------------------------------------------
# 6. The Worker's notes and the sources rail
# ---------------------------------------------------------------------------

def _result(fcl_rows=1, scot_rows=1, status="ok", match="all", total=None, error=None):
    d = {"results": [{"title": "Gizmo Ltd v Widget plc", "ncn": "[1901] EWHC 1 (Ch)",
                      "court": "ewhc/ch", "date": "1901-01-15", "url": FCL_URL}] * fcl_rows,
         "shown": fcl_rows, "total": fcl_rows, "total_exact": True,
         "total_min": fcl_rows, "total_max": fcl_rows, "query": "q"}
    if error:
        d["error"] = error
    rows = scts.slim_scts_results(_body([_row(link=f"/media/x/2017csih{i}-w.pdf") for i in range(scot_rows)]))
    d["scottish_results"] = rows
    d["scottish"] = {"status": status, "shown": len(rows), "total": total or len(rows),
                     "total_exact": True, "match": match if status == "ok" else None}
    return json.dumps(d)


def test_both_lists_get_their_notes_and_one_imperative_last():
    note = agent_shared._case_law_note_with_scottish({"query": "widget gizmo"}, _result(1, 2))
    blocks = note.strip().split("\n\n")
    assert blocks[0].startswith("[SEARCH SCOPE — all 1 judgment(s) in Find Case Law")
    assert blocks[1].startswith("[SEARCH SCOPE — all 2 judgment(s) in the Scottish Courts")
    assert blocks[-1].startswith("[MANDATORY NEXT STEP")
    assert note.count("[MANDATORY NEXT STEP") == 1
    assert FCL_URL in blocks[-1] and "/media/x/2017csih0-w.pdf" in blocks[-1]
    assert "decided 2017-05-04" in blocks[-1]


def test_the_stop_rule_only_when_both_lists_are_empty():
    both_zero = agent_shared._case_law_note_with_scottish({"query": "w g"}, _result(0, 0))
    assert ss.CASE_LAW_BOTH_ZERO_STOP in both_zero and "[MANDATORY" not in both_zero
    assert ss.FCL_ZERO_NOTE_WITH_SCTS in both_zero and ss.SCTS_ZERO_NOTE in both_zero
    one = agent_shared._case_law_note_with_scottish({"query": "w g"}, _result(0, 2))
    assert ss.CASE_LAW_BOTH_ZERO_STOP not in one and ss.FCL_ZERO_NOTE_WITH_SCTS in one
    assert "[MANDATORY" in one
    # SCTS errored and Find Case Law empty: no stop rule (a search did not run)
    err = agent_shared._case_law_note_with_scottish({"query": "w g"}, _result(0, 0, status="error"))
    assert ss.CASE_LAW_BOTH_ZERO_STOP not in err and "returned an error" in err
    # Find Case Law errored: no zero note claims it returned 0
    fe = agent_shared._case_law_note_with_scottish({"query": "w g"}, _result(0, 1, error="x"))
    assert ss.FCL_ZERO_NOTE_WITH_SCTS not in fe and "[MANDATORY" in fe


@pytest.mark.parametrize("kw,expect", [
    ({"status": "ok", "scot_rows": 10, "total": 354}, "the first 10 of 354 judgments"),
    ({"status": "ok", "scot_rows": 3, "match": "any", "total": 12712},
     "that contain any of the terms of \"widget gizmo\", listed most relevant first: a query "
     "requiring every term returned 0"),
    ({"status": "ok", "scot_rows": 3, "total": 3}, "all 3 judgment(s)"),
    ({"status": "error", "scot_rows": 0}, "returned an error"),
    ({"status": "capped", "scot_rows": 0}, "had no part in this search"),
    ({"status": "not_searched", "scot_rows": 0}, "holds no word to look up"),
])
def test_each_class_of_the_scottish_note(kw, expect):
    note = ss.scottish_search_note({"query": "widget gizmo"}, _result(**kw))
    assert expect in note
    assert note.strip().startswith("[SEARCH SCOPE —") and note.strip().endswith("]")


def test_the_scottish_note_holds_no_square_bracket_and_quotes_the_query_once():
    note = ss.scottish_search_note({"query": "[1901] CSIH 9"}, _result())
    inner = note.strip()[1:-1]
    assert "[" not in inner and "]" not in inner and '"(1901) CSIH 9"' in note
    quoted = ss.scottish_search_note({"query": '"widget duty" gizmo'}, _result())
    assert 'every term of "widget duty" gizmo,' in quoted and '""' not in quoted
    empty = ss.scottish_search_note({"query": ""}, _result(status="error", scot_rows=0))
    assert "the query the query" not in empty and " for " not in empty
    empty_ok = ss.scottish_search_note({"query": ""}, _result())
    assert "every term of the query, listed" in empty_ok
    assert ss.strip_scope_blocks("Answer. " + note.strip() + " More.")[0] == "Answer.  More."


def test_without_a_scottish_block_there_is_no_scottish_note():
    assert ss.scottish_search_note({"query": "w"}, {"results": []}) == ""
    assert not agent_shared._has_scottish_list(json.dumps({"results": []}))
    assert agent_shared._has_scottish_list(_result())


def test_the_rail_gets_the_scottish_judgments_with_their_decision_dates():
    acc = []
    agent_shared._extract_sources_from_tool("search_case_law", {"query": "w"}, _result(1, 2), acc)
    assert [s["url"] for s in acc] == [FCL_URL, "https://www.scotcourts.gov.uk/media/x/2017csih0-w.pdf",
                                       "https://www.scotcourts.gov.uk/media/x/2017csih1-w.pdf"]
    assert acc[1] == {"kind": "Case", "title": "Widget Co v Example Ltd", "sub": "[2017] CSIH 0",
                      "meta": "Court of Session, 2017-05-04", "cite": "[2017] CSIH 0",
                      "url": "https://www.scotcourts.gov.uk/media/x/2017csih0-w.pdf"}


async def test_the_worker_tool_path_uses_the_scottish_notes(on):
    from unittest.mock import AsyncMock, patch

    async def chunk(*a, **k):
        return None
    with patch("src.agent.agent_shared.execute_worker_tool", new=AsyncMock(return_value=_result(1, 1))):
        log = []
        out = await agent_shared.run_worker_tool("search_case_law", {"query": "widget gizmo"},
                                                 "brief", chunk, "m", search_log=log)
    assert "the Scottish Courts and Tribunals Service's published judgments" in out
    assert log == [{"tool": "search_case_law", "query": "widget gizmo", "shown": 1, "ok": True,
                    "scts": "ok", "scts_shown": 1}]


# ---------------------------------------------------------------------------
# 7. The footer
# ---------------------------------------------------------------------------

def _cl(q="widget", ok=True, scts_status=None):
    r = {"tool": "search_case_law", "query": q, "shown": 3, "ok": ok}
    if scts_status is not None:
        r.update(scts=scts_status, scts_shown=1)
    return r


def test_a_record_without_the_scottish_list_is_what_it_was():
    log = []
    ss.record_case_law_search(log, "search_case_law", {"query": "w"},
                              json.dumps({"results": [], "query": "w"}))
    assert log == [{"tool": "search_case_law", "query": "w", "shown": 0, "ok": True}]


@pytest.mark.parametrize("status", ["ok", "error", "capped", "not_searched"])
def test_a_record_with_the_scottish_list_carries_its_status(status):
    log = []
    ss.record_case_law_search(log, "search_case_law", {"query": "w"}, _result(status=status))
    assert log[0]["scts"] == status


def test_no_scts_record_gives_todays_footer_byte_for_byte():
    for recs in ([_cl()], [_cl(ok=False)], [_cl(scts_status="capped")],
                 [_cl(scts_status="not_searched")]):
        plain = [{k: v for k, v in r.items() if k not in ("scts", "scts_shown")} for r in recs]
        assert ss.case_law_scope_footer(recs) == ss.case_law_scope_footer(plain)
        assert ss.CASE_LAW_COVERAGE_SENTENCE in ss.case_law_scope_footer(recs)


def test_an_ok_scts_search_swaps_the_coverage_sentence():
    for recs in ([_cl(scts_status="ok")], [_cl(), _cl("gizmo", scts_status="ok")]):
        line = ss.case_law_scope_footer(recs)
        assert ss.CASE_LAW_COVERAGE_SENTENCE not in line and rr.CASE_LAW_CODE not in line
        assert ss.SCTS_COVERAGE_BOTH_SENTENCE in line and ss.SCTS_ABSENCE_SENTENCE in line
        assert ss.CASE_LAW_DOCTRINE_SENTENCE in line
        # still says what SCTS does not hold
        assert "Northern Ireland" in line and "not every Sheriff Court decision" in line
        assert "almost none in criminal cases" in line


def test_find_case_law_errored_and_scts_ran():
    line = ss.case_law_scope_footer([_cl(ok=False, scts_status="ok")])
    assert ss.SCTS_COVERAGE_ONLY_SENTENCE in line and ss.SCTS_FCL_ERRORED_SENTENCE in line
    assert ss.CASE_LAW_DOCTRINE_SENTENCE not in line and rr.CASE_LAW_CODE not in line
    assert "not decisions of the UK Supreme Court" in line


def test_scts_errored_keeps_todays_sentence_and_says_so():
    line = ss.case_law_scope_footer([_cl(scts_status="error")])
    assert ss.CASE_LAW_COVERAGE_SENTENCE in line and ss.SCTS_ERRORED_SENTENCE in line
    assert line.index(ss.CASE_LAW_COVERAGE_SENTENCE) < line.index(ss.SCTS_ERRORED_SENTENCE)
    assert line.endswith(ss.CASE_LAW_DOCTRINE_SENTENCE + "*")


@pytest.mark.parametrize("recs", [
    [_cl(scts_status="ok")], [_cl("a"), _cl("b", scts_status="ok"), _cl("c")],
    [_cl(ok=False, scts_status="ok")], [_cl(scts_status="error")],
    [_cl(ok=False, scts_status="error")],
])
def test_every_variant_is_one_stripped_line_and_trips_no_detector(recs):
    for line in (ss.case_law_scope_footer(recs),
                 ss.answer_scope_footer([{"tool": "search_legislation", "query": "Widget Act 1901",
                                          "legislation_id": "", "shown": 5, "matched": 9}] + recs,
                                        {"_jurisdiction": "scotland"})):
        answer = "The answer." + line
        assert rr._without_footer(answer) == "The answer."
        assert ss.strip_answer_footer(answer) == "The answer."
        assert answer.count("*Search scope:") == 1
        assert rr.caselaw_gap_statements(answer)
    body = ss.case_law_scope_footer(recs)
    for det in (rr.NEG_ASSERTED, rr.NOT_FOUND, rr.NEG_BLAMED_USER, rr.IN_FORCE_CLAIM,
                rr.HALT_PARAPHRASE, rr.HALT_AS_TIMEOUT, rr.HALT_LITERAL, rr.SCHED_LIMIT,
                rr.OPENER_VOCAB):
        assert not det.search(body), det.pattern[:60]
    # As P2.4's test does: the opening "were searched for "…"" names the terms
    # by design, so `NEG_LIMITS` and `NEG_TERMS` are read from the coverage
    # sentence on.
    start = min(body.index(s) for s in (ss.CASE_LAW_COVERAGE_SENTENCE, ss.SCTS_COVERAGE_BOTH_SENTENCE,
                                         ss.SCTS_COVERAGE_ONLY_SENTENCE) if s in body)
    for det in (rr.NEG_LIMITS, rr.NEG_TERMS):
        assert not det.search(body[start:]), det.pattern[:60]
    assert rr.derivation_claims(body)[0] == []
    assert not any(rr._currency_asserted(s) for s in rr._sentences(body))


def test_the_grader_is_coupled_to_the_product_sentences():
    assert ss.SCTS_COVERAGE_BOTH_SENTENCE.startswith(rr.SCTS_CODE_BOTH)
    assert ss.SCTS_COVERAGE_ONLY_SENTENCE.startswith(rr.SCTS_CODE_ONLY)


# ---------------------------------------------------------------------------
# 8. The prompts and the tool descriptions
# ---------------------------------------------------------------------------

_SOURCES = {
    0: P.WORKER_SYSTEM_PROMPT_CASE_LAW, 1: P.WORKER_SYSTEM_PROMPT_CASE_LAW,
    2: P.WORKER_SYSTEM_PROMPT_CASE_LAW, 3: P.WORKER_SYSTEM_PROMPT_CASE_LAW,
    4: P.WORKER_SYSTEM_PROMPT_HYBRID, 5: P.WORKER_SYSTEM_PROMPT_HYBRID,
    6: P.WORKER_SYSTEM_PROMPT_CONVERSATIONAL, 7: P._JURISDICTION_EXTENT_NOTES["scotland"],
}


def test_every_old_text_occurs_once_where_it_was_taken_from():
    for i, (old, _new) in enumerate(P.SCTS_PROMPT_WORDING):
        if i in _SOURCES:
            assert _SOURCES[i].count(old) == 1, i
    assert P._SYNTHESIS_SOURCES["case_law_only"][0].count(P.SCTS_PROMPT_WORDING[8][0]) == 1
    assert P._SYNTHESIS_SOURCES["legislation_and_case_law"][0].count(P.SCTS_PROMPT_WORDING[8][0]) == 1
    assert len(P.SCTS_PROMPT_WORDING) == 9


def test_off_every_prompt_is_unchanged(off):
    for mode in ("case_law_only", "legislation_and_case_law", "legislation_only"):
        for text in (P.WORKER_SYSTEM_PROMPT_CASE_LAW, P.WORKER_SYSTEM_PROMPT_HYBRID,
                     P.WORKER_SYSTEM_PROMPT_CONVERSATIONAL):
            assert P.apply_scts_wording(text, mode) is text
        assert schemas.get_worker_tools(mode) == schemas._worker_tools_for(mode)
    assert schemas.get_worker_tools("case_law_only") is schemas.CASE_LAW_TOOLS


@pytest.mark.parametrize("mode,chat", [
    ("case_law_only", "research"), ("legislation_and_case_law", "research"),
    ("case_law_only", "conversational"), ("legislation_and_case_law", "conversational"),
])
def test_on_the_case_law_prompts_carry_the_scts_wording(on, mode, chat):
    cfg = {"_chat_mode": chat, "_research_mode": mode, "_jurisdiction": "scotland"}
    prompt = P.get_worker_system_prompt(mode, cfg)
    for old, new in P.SCTS_PROMPT_WORDING:
        assert old not in prompt or old in new
    assert "scottish_results" in prompt
    assert "holds NO decisions of the Court of Session" not in prompt
    assert "Note that the case law database holds no decisions" not in prompt
    if chat == "research":
        assert "Northern Ireland" in prompt
        assert "do not present a decision of a court outside Scotland as stating Scots law" in prompt


def test_on_a_legislation_only_prompt_is_unchanged(on):
    cfg = {"_chat_mode": "research", "_research_mode": "legislation_only", "_jurisdiction": "scotland"}
    assert P.apply_scts_wording(P.WORKER_SYSTEM_PROMPT, "legislation_only") is P.WORKER_SYSTEM_PROMPT
    assert "Note that the case law database holds no decisions" in P.build_filter_constraint_block(cfg)


def test_on_the_synthesis_names_both_databases(on):
    for mode in ("case_law_only", "legislation_and_case_law"):
        assert "Scottish Courts and Tribunals Service" in P.get_deep_research_synthesis_prompt(mode)
    assert "Scottish Courts" not in P.get_deep_research_synthesis_prompt("legislation_only")


def test_on_the_tools_are_copies_with_the_scts_descriptions(on):
    tools = schemas.get_worker_tools("legislation_and_case_law")
    by = {t["function"]["name"]: t["function"] for t in tools}
    assert by["search_case_law"]["description"] == schemas.SCTS_SEARCH_CASE_LAW_DESCRIPTION
    assert by["search_case_law"]["parameters"]["properties"]["court"]["description"].startswith(
        schemas.SCTS_COURT_ARG_PREFIX)
    assert by["get_case_law_text"]["description"] == schemas.SCTS_GET_CASE_LAW_TEXT_DESCRIPTION
    # the module's objects are untouched
    assert "Scottish Courts" not in schemas.CASE_LAW_TOOLS[0]["function"]["description"]
    assert not schemas.CASE_LAW_TOOLS[0]["function"]["parameters"]["properties"]["court"][
        "description"].startswith(schemas.SCTS_COURT_ARG_PREFIX)
    # the legislation tools are the same objects
    assert by["search_legislation"] is next(
        t["function"] for t in schemas.WORKER_TOOLS if t["function"]["name"] == "search_legislation")


def test_the_gate():
    assert settings.__class__.model_fields["scts_caselaw_enabled"].default is False


def test_the_gate_reads_the_setting_and_the_research_type(monkeypatch):
    monkeypatch.setattr(settings, "scts_caselaw_enabled", False)
    assert not scts.scts_enabled() and not scts.scts_enabled("case_law_only")
    monkeypatch.setattr(settings, "scts_caselaw_enabled", True)
    assert scts.scts_enabled() and scts.scts_enabled("case_law_only")
    assert scts.scts_enabled("legislation_and_case_law")
    for mode in ("legislation_only", "parliamentary_records", "drafting", ""):
        assert not scts.scts_enabled(mode)


# ---------------------------------------------------------------------------
# 9. Caching
# ---------------------------------------------------------------------------

def test_both_tools_stay_cacheable_and_the_drafting_override_holds():
    from src.routers.agent_request import ChatRequest, build_request_config
    from src.services.local_prompt_cache import CACHEABLE_TOOLS
    # SCTS content is Crown copyright under the Open Government Licence: public.
    assert {"search_case_law", "get_case_law_text"} <= CACHEABLE_TOOLS
    body = ChatRequest(messages=[{"role": "user", "content": "x"}], model="m",
                       research_mode="drafting")
    cfg = build_request_config(body, {}, "openrouter", {"local_prompt_cache_enabled": True},
                               chat_mode="research")
    assert cfg["_local_prompt_cache_enabled"] is False


# ---------------------------------------------------------------------------
# 10. The grader: `replay_report scts`
# ---------------------------------------------------------------------------

def _turn(n, answer, scts_status="ok", returned=(PDF_URL,), fetched=()):
    tools = []
    if scts_status is not None:
        tools.append({"name": "search_case_law", "raw_result": json.dumps({
            "results": [], "scottish": {"status": scts_status},
            "scottish_results": [{"url": u} for u in returned]})})
    for u in fetched:
        tools.append({"name": "get_case_law_text", "raw_result": json.dumps({"url": u, "text": "t"})})
    return {"turn": n, "chat_mode": "research", "answer": answer,
            "audit": {"delegations": [{"tools": tools}]}}


def _doc(*turns):
    return {"session_id": "9999", "rep": 1, "turns": list(turns)}


def test_the_grader_verdicts_both_ways():
    new = ss.case_law_scope_footer([_cl(scts_status="ok")])
    old = ss.case_law_scope_footer([_cl()])
    cite = f"[Widget Co v Example Ltd]({PDF_URL})"
    other_url = "https://www.scotcourts.gov.uk/media/zzz/2001csoh1-g.pdf"
    other = f"[Gizmo v Widget]({other_url})"
    rows = rr.scts_rows(_doc(
        _turn(1, "A. " + cite + new),                                  # clean
        _turn(2, "A. " + cite + old),                                  # the old sentence: FAIL
        _turn(3, "A." + new, scts_status=None, returned=()),           # new sentence, no SCTS
        _turn(4, "A. " + other + new),                                 # a link no search returned
        _turn(5, "A." + new),                                          # ok search, nothing cited
        _turn(6, "A. " + other + new, returned=(), fetched=(other_url,)),  # fetched counts
        _turn(7, "A." + old, scts_status="error", returned=()),        # SCTS errored: old is right
    ))
    got = [(r["turn"], rr.scts_verdicts(r, require_cite=True), r["cited"]) for r in rows]
    assert got == [
        (1, [], 1),
        (2, ["OLD_SENTENCE"], 1),
        (3, ["MISATTRIBUTED"], 0),
        (4, ["UNRETURNED", "UNCITED"], 0),
        (5, ["UNCITED"], 0),
        (6, [], 1),
        (7, [], 0),
    ]
    # without --require-cite, an uncited turn is not a finding
    assert rr.scts_verdicts(rows[4]) == []


def test_the_grader_counts_non_uksc_find_case_law_links_for_the_hand_read():
    answer = ("See [Gizmo](https://caselaw.nationalarchives.gov.uk/ewhc/ch/1901/1) and "
              "[Widget v Gizmo](https://caselaw.nationalarchives.gov.uk/uksc/1901/2)."
              + ss.case_law_scope_footer([_cl(scts_status="ok")]))
    assert rr.scts_rows(_doc(_turn(1, answer)))[0]["fcl_non_uksc"] == 1


def test_the_subcommand_exits(tmp_path, capsys):
    clean, dirty, none = tmp_path / "clean", tmp_path / "dirty", tmp_path / "none"
    for d in (clean, dirty, none):
        d.mkdir()
    new = ss.case_law_scope_footer([_cl(scts_status="ok")])
    old = ss.case_law_scope_footer([_cl()])
    cite = f"[Widget Co v Example Ltd]({PDF_URL})"
    (clean / "9999_rep1.json").write_text(json.dumps(_doc(_turn(1, "A. " + cite + new))), encoding="utf-8")
    (dirty / "9999_rep1.json").write_text(json.dumps(_doc(_turn(1, "A. " + cite + old))), encoding="utf-8")
    (none / "9999_rep1.json").write_text(json.dumps(_doc(_turn(1, "A." + old, scts_status=None))),
                                         encoding="utf-8")
    assert rr.main(["--dir", str(clean), "scts", "--require-cite"]) == 0
    assert rr.main(["--dir", str(dirty), "scts"]) == 1
    assert "OLD_SENTENCE  1" in capsys.readouterr().out
    assert rr.main(["--dir", str(none), "scts"]) == 1
    assert "No turn ran an ok SCTS search" in capsys.readouterr().out
