"""FIX_PLAN P3.38 — the text of an instrument the index lacks, read from legislation.gov.uk.

When a lookup says an instrument is not held or held without text, or a text
read comes back empty or "Legislation not found", code reads the instrument
from legislation.gov.uk through LEX's `GET /legislation/proxy/<encoded path>`
(`agent/tools/published_text.py`; live, memoised per request, bounded,
fail-soft) and hands it to the Worker in a code-written block
(`utils/published_text.py`), with the Manager's limb and the lawyer's footer
clause saying where it came from.

Every id, title and provision here is synthetic ("The Widget Order 1901",
`ssi/1901/3`). No test reaches the network: `conftest.py` refuses the read's
client by default, and the tests below serve synthetic documents through
`_client`.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch
from urllib.parse import unquote

import httpx
import pytest

from src.agent.provider_factory import set_request_provider_config
from src.agent.tools import published_text as reader
from src.utils import published_text as pt

LID = "ssi/1901/3"
LEG = "http://www.legislation.gov.uk"
NS = ('xmlns="http://www.legislation.gov.uk/namespaces/legislation" '
      'xmlns:ukm="http://www.legislation.gov.uk/namespaces/metadata" '
      'xmlns:dc="http://purl.org/dc/elements/1.1/"')


# ---------------------------------------------------------------------------
# synthetic documents
# ---------------------------------------------------------------------------

def _doc(lid=LID, version="made", body=True, schedule=True, pdf=True,
         preamble="The Scottish Ministers make the following Order in exercise of the "
                  "powers conferred by section 9 of the Widget (Scotland) Act 1901"):
    uri = f"{LEG}/{lid}" + (f"/{version}" if version != "current" else "")
    meta = (f"<ukm:Metadata><dc:title>The Widget Order 1901</dc:title>"
            + (f'<ukm:Alternatives><ukm:Alternative URI="{LEG}/{lid}/pdfs/x.pdf"/>'
               "</ukm:Alternatives>" if pdf else "")
            + "<dc:description>Not body text.</dc:description></ukm:Metadata>")
    if not body:
        return f'<Legislation {NS} DocumentURI="{uri}">{meta}</Legislation>'
    sched = ("<Schedules><Schedule DocumentURI=\"" + f"{LEG}/{lid}/schedule/made\">"
             "<Number>SCHEDULE</Number><TitleBlock><Title>Widget fees</Title></TitleBlock>"
             "<ScheduleBody><P1 DocumentURI=\"" + f"{LEG}/{lid}/schedule/paragraph/1/made\">"
             "<Pnumber>1</Pnumber><P1para><Text>The fee is five shillings.</Text></P1para>"
             "</P1></ScheduleBody></Schedule></Schedules>") if schedule else ""
    return (
        f'<Legislation {NS} DocumentURI="{uri}">{meta}<Secondary>'
        "<SecondaryPrelims><Number>1901 No. 3</Number><Title>The Widget Order 1901</Title>"
        f"<SecondaryPreamble><EnactingText><Para><Text>{preamble}"
        '<FootnoteRef Ref="f1"/>.</Text></Para></EnactingText></SecondaryPreamble>'
        "</SecondaryPrelims>"
        f'<Body><P1group><Title>Citation</Title><P1 DocumentURI="{LEG}/{lid}/article/1/made">'
        "<Pnumber>1</Pnumber><P1para><P2><Pnumber>1</Pnumber><P2para>"
        "<Text>This Order may be cited as the Widget Order 1901.</Text></P2para></P2>"
        "<P2><Pnumber>2</Pnumber><P2para><Text>In this Order—</Text>"
        "<UnorderedList><ListItem><Para><Text>“widget” means a widget.</Text></Para>"
        "</ListItem></UnorderedList></P2para></P2></P1para></P1></P1group>"
        "<Commentaries><Commentary><Para><Text>EDITORIAL NOTE</Text></Para></Commentary>"
        "</Commentaries></Body>"
        f"{sched}</Secondary>"
        '<Footnotes><Footnote id="f1"><FootnoteText><Para><Text>1901 asp 1</Text></Para>'
        "</FootnoteText></Footnote></Footnotes></Legislation>"
    )


class _Server:
    """Serves the read's proxy GETs from a dict path -> (status, body) or an
    exception, and records each path asked."""

    def __init__(self, pages=None, delay=0.0):
        self.pages = pages or {}
        self.delay = delay
        self.asked = []

    async def handler(self, request):
        url = str(request.url)
        assert "/legislation/proxy/" in url
        segment = url.split("/legislation/proxy/", 1)[1]
        assert "/" not in segment  # one encoded segment
        path = unquote(segment)
        self.asked.append(path)
        if self.delay:
            await asyncio.sleep(self.delay)
        got = self.pages.get(path)
        if got is None:
            return httpx.Response(404, json={"detail": f"Legislation not found: {path}"})
        if isinstance(got, Exception):
            raise got
        status, body = got
        return httpx.Response(status, text=body)

    def install(self, monkeypatch):
        monkeypatch.setattr(
            reader, "_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(self.handler)))
        return self


def _read(lid=LID, cfg=True):
    async def go():
        set_request_provider_config({"_test": True} if cfg else {})
        return await reader.read_published_text(lid)
    return asyncio.run(go())


# ---------------------------------------------------------------------------
# the trigger
# ---------------------------------------------------------------------------

def _lookup(status, lid=LID):
    return json.dumps({"tool": "lookup_legislation", "legislation_id": lid,
                       "label": pt.label_for(lid), "status": status})


@pytest.mark.parametrize("status,kind", [
    ("not_held", pt.KIND_NOT_HELD), ("held_without_text", pt.KIND_NO_TEXT),
])
def test_a_not_held_or_text_less_lookup_triggers_a_read(status, kind):
    assert pt.trigger("lookup_legislation", {}, _lookup(status)) == (LID, kind)
    # with a block appended after the JSON (a result that has been through the seam)
    assert pt.trigger("lookup_legislation", {}, _lookup(status) + "\n\n[X]") == (LID, kind)


@pytest.mark.parametrize("status", ["held", "lookup_failed", "invalid"])
def test_a_held_or_undecided_lookup_triggers_nothing(status):
    assert pt.trigger("lookup_legislation", {}, _lookup(status)) is None


@pytest.mark.parametrize("body", ["", "   ", "No text content available for this legislation."])
def test_an_empty_text_read_triggers_a_read(body):
    raw = json.dumps({"legislation": {"title": "x"}, "full_text": body})
    assert pt.trigger("get_legislation_text", {"legislation_id": LID}, raw) == (
        LID, pt.KIND_NO_TEXT)


def test_a_text_read_with_text_or_an_error_triggers_nothing():
    args = {"legislation_id": LID}
    assert pt.trigger("get_legislation_text", args, json.dumps(
        {"legislation": {}, "full_text": "1. This Order may be cited."})) is None
    assert pt.trigger("get_legislation_text", args, json.dumps(
        {"error": "x", "full_text": ""})) is None
    assert pt.trigger("get_legislation_text", args,
                      'Error executing tool: {"detail":"Internal Server Error"}') is None
    assert pt.trigger("get_legislation_text", args, "not json") is None


def test_a_text_read_the_index_answered_not_found_triggers_a_read():
    raw = 'Error executing tool: {"detail":"Legislation not found: ssi 1901 No. 3"}'
    assert pt.trigger("get_legislation_text", {"legislation_id": LID}, raw) == (
        LID, pt.KIND_READ_NOT_FOUND)
    # the regnal form LEX's own search returns, which its text endpoint 404s on
    assert pt.trigger("get_legislation_text", {"legislation_id": "ukpga/Vict/1-2/99"},
                      raw) == ("ukpga/Vict/1-2/99", pt.KIND_READ_NOT_FOUND)


def test_other_tools_and_unreadable_ids_trigger_nothing():
    assert pt.trigger("search_legislation_sections", {"legislation_id": LID}, "[]") is None
    assert pt.trigger("get_legislation_text", {"legislation_id": "eur/1901/3"},
                      json.dumps({"full_text": ""})) is None
    assert pt.trigger("lookup_legislation", {}, _lookup("not_held", "zz/1901/3")) is None


@pytest.mark.parametrize("value,want", [
    ("ssi/1901/3", "ssi/1901/3"),
    ("SSI/1901/3", "ssi/1901/3"),
    ("http://www.legislation.gov.uk/id/ssi/1901/3", "ssi/1901/3"),
    ("https://legislation.gov.uk/ssi/1901/3/", "ssi/1901/3"),
    ("ukpga/Vict/1-2/99", "ukpga/Vict/1-2/99"),
    ("ukpga/Geo5/1/9", "ukpga/Geo5/1/9"),
    ("eur/1901/3", ""), ("ssi/1901", ""), ("ssi/1901/3/section/1", ""), ("", ""),
    ("../ssi/1901/3", ""),
])
def test_ids_are_normalised_or_refused(value, want):
    assert pt.normalise_id(value) == want


def test_an_instrument_is_read_as_made_and_an_act_as_enacted_then_current():
    assert pt.routes(LID) == [f"{LID}/made/data.xml", f"{LID}/data.xml"]
    assert pt.routes("asp/1901/1") == ["asp/1901/1/enacted/data.xml", "asp/1901/1/data.xml"]
    assert pt.routes("eur/1901/1") == []


# ---------------------------------------------------------------------------
# the CLML renderer
# ---------------------------------------------------------------------------

def test_the_renderer_gives_numbered_provisions_schedules_and_footnotes():
    p = pt.parse_published(_doc())
    assert p["title"] == "The Widget Order 1901" and p["version"] == "made"
    assert p["url"] == f"https://www.legislation.gov.uk/{LID}/made"
    lines = p["text"].split("\n")
    assert "1. (1) This Order may be cited as the Widget Order 1901." in lines
    assert "(2) In this Order—" in lines
    assert "- “widget” means a widget." in lines
    assert "SCHEDULE" in lines and "1. The fee is five shillings." in lines
    assert lines[-2:] == ["Footnotes:", "(1) 1901 asp 1"]
    assert "(footnote 1)" in p["text"]
    # metadata and editorial commentaries are not the instrument's words
    assert "Not body text" not in p["text"] and "EDITORIAL NOTE" not in p["text"]
    assert p["has_schedules"] is True
    assert p["provision_urls"] == [f"https://www.legislation.gov.uk/{LID}/article/1/made",
                                   f"https://www.legislation.gov.uk/{LID}/schedule/made",
                                   f"https://www.legislation.gov.uk/{LID}/schedule/paragraph/1/made"]
    assert p["preamble"].startswith("The Scottish Ministers make the following Order")


def test_the_version_is_the_documents_own_and_a_schedule_is_seen_only_when_there():
    assert pt.parse_published(_doc(version="enacted"))["version"] == "enacted"
    assert pt.parse_published(_doc(version="current"))["version"] == "current"
    assert pt.parse_published(_doc(schedule=False))["has_schedules"] is False


def test_a_document_with_no_body_is_no_text_and_names_its_scan():
    p = pt.parse_published(_doc(body=False))
    assert p["text"] == "" and p["pdf"] == f"https://www.legislation.gov.uk/{LID}/pdfs/x.pdf"
    assert pt.parse_published(_doc(body=False, pdf=False))["pdf"] == ""


@pytest.mark.parametrize("page", [
    "", "<html><body>502</body></html>", "not xml",
    '{"detail":"Legislation not found"}',
    '<?xml version="1.0"?><!DOCTYPE Legislation [<!ENTITY x "y">]><Legislation/>',
    '<feed xmlns="http://www.w3.org/2005/Atom"/>',
])
def test_a_page_that_is_not_a_legislation_document_is_never_read_as_one(page):
    with pytest.raises(ValueError):
        pt.parse_published(page)


# ---------------------------------------------------------------------------
# the read
# ---------------------------------------------------------------------------

def test_the_made_version_is_read_through_the_proxy_in_one_call(monkeypatch):
    srv = _Server({f"{LID}/made/data.xml": (200, _doc())}).install(monkeypatch)
    got = _read()
    assert got["status"] == pt.OK and got["version"] == "made"
    assert "This Order may be cited" in got["text"]
    assert srv.asked == [f"{LID}/made/data.xml"]


def test_a_version_legislation_gov_uk_lacks_falls_back_to_the_current_one(monkeypatch):
    srv = _Server({f"{LID}/data.xml": (200, _doc(version="current"))}).install(monkeypatch)
    got = _read()
    assert got["status"] == pt.OK and got["version"] == "current"
    assert srv.asked == [f"{LID}/made/data.xml", f"{LID}/data.xml"]


def test_the_proxys_wrapped_upstream_400_is_absence_too(monkeypatch):
    wrapped = json.dumps({"detail": "External API error: Client error '400 Bad Request' "
                                    "for url 'https://www.legislation.gov.uk/x'"})
    _Server({f"{LID}/made/data.xml": (502, wrapped),
             f"{LID}/data.xml": (502, wrapped)}).install(monkeypatch)
    assert _read()["status"] == pt.NOT_PUBLISHED


def test_no_document_on_either_route_is_not_published(monkeypatch):
    srv = _Server({}).install(monkeypatch)
    assert _read()["status"] == pt.NOT_PUBLISHED
    assert len(srv.asked) == 2


@pytest.mark.parametrize("status,body", [
    (404, '{"detail":"Not Found"}'),            # a route moved: never absence
    (502, '{"detail":"External API error: Server error \'500 Internal\' for url x"}'),
    (502, "Bad gateway '404 '"),                # a 404 code not in the proxy's own error
    (500, "boom"),
])
def test_any_other_error_is_a_failed_read_not_absence(monkeypatch, status, body):
    srv = _Server({f"{LID}/made/data.xml": (status, body)}).install(monkeypatch)
    got = _read()
    assert got["status"] == pt.FAILED and got["reason"] == f"http_{status}"
    assert len(srv.asked) == 1


def test_no_reply_and_a_transport_error_are_failed_reads(monkeypatch):
    _Server({f"{LID}/made/data.xml": httpx.ReadTimeout("slow")}).install(monkeypatch)
    assert _read() == {"status": pt.FAILED, "reason": "no_reply"}
    _Server({f"{LID}/made/data.xml": httpx.ConnectError("down")}).install(monkeypatch)
    assert _read() == {"status": pt.FAILED, "reason": "error"}


def test_a_body_over_the_byte_cap_is_not_read(monkeypatch):
    monkeypatch.setattr(reader, "MAX_BYTES", 100)
    _Server({f"{LID}/made/data.xml": (200, _doc())}).install(monkeypatch)
    assert _read() == {"status": pt.FAILED, "reason": "too_large"}


def test_a_200_that_is_not_a_document_is_a_failed_read(monkeypatch):
    _Server({f"{LID}/made/data.xml": (200, "<html>maintenance</html>")}).install(monkeypatch)
    assert _read() == {"status": pt.FAILED, "reason": "unreadable"}


def test_a_scan_only_instrument_is_pdf_only_and_not_read_twice(monkeypatch):
    srv = _Server({f"{LID}/made/data.xml": (200, _doc(body=False)),
                   f"{LID}/data.xml": (200, _doc())}).install(monkeypatch)
    got = _read()
    assert got["status"] == pt.PDF_ONLY and got["pdf"].endswith("/pdfs/x.pdf")
    assert srv.asked == [f"{LID}/made/data.xml"]


def test_a_bodiless_page_with_no_scan_moves_on_to_the_next_route(monkeypatch):
    srv = _Server({f"{LID}/made/data.xml": (200, _doc(body=False, pdf=False)),
                   f"{LID}/data.xml": (200, _doc(version="current"))}).install(monkeypatch)
    assert _read()["status"] == pt.OK and len(srv.asked) == 2


def test_an_id_this_route_does_not_read_makes_no_call(monkeypatch):
    srv = _Server({}).install(monkeypatch)
    assert _read("eur/1901/3") == {"status": pt.UNSUPPORTED}
    assert srv.asked == []


def test_one_request_reads_an_instrument_once_however_often_it_asks(monkeypatch):
    srv = _Server({f"{LID}/made/data.xml": (200, _doc())}, delay=0.05).install(monkeypatch)

    async def go():
        set_request_provider_config({"_test": True})
        a, b = await asyncio.gather(reader.read_published_text(LID),
                                    reader.read_published_text(LID))
        c = await reader.read_published_text(LID)
        return a, b, c
    a, b, c = asyncio.run(go())
    assert a["status"] == b["status"] == c["status"] == pt.OK
    assert srv.asked == [f"{LID}/made/data.xml"]


def test_without_a_request_config_each_read_is_its_own(monkeypatch):
    srv = _Server({f"{LID}/made/data.xml": (200, _doc())}).install(monkeypatch)
    _read(cfg=False)
    _read(cfg=False)
    assert len(srv.asked) == 2


def test_a_request_reads_at_most_the_cap_and_says_so(monkeypatch):
    monkeypatch.setattr(reader, "MAX_READS_PER_REQUEST", 2)
    pages = {f"ssi/1901/{n}/made/data.xml": (200, _doc(f"ssi/1901/{n}")) for n in (1, 2, 3)}
    srv = _Server(pages).install(monkeypatch)

    async def go():
        set_request_provider_config({"_test": True})
        out = [await reader.read_published_text(f"ssi/1901/{n}") for n in (1, 2, 3)]
        out.append(await reader.read_published_text("ssi/1901/1"))  # memoised: no new read
        return out
    one, two, three, again = asyncio.run(go())
    assert one["status"] == two["status"] == again["status"] == pt.OK
    assert three == {"status": pt.LIMIT, "limit": 2}
    assert len(srv.asked) == 2


# ---------------------------------------------------------------------------
# the wording
# ---------------------------------------------------------------------------

def _ok(version="made", sched=True):
    return {"status": pt.OK, "version": version, "title": "The Widget Order 1901",
            "has_schedules": sched, "url": f"https://www.legislation.gov.uk/{LID}/{version}"}


def test_the_block_says_where_the_text_came_from_and_carries_it():
    b = pt.published_block(LID, pt.KIND_NOT_HELD, _ok(), "whole", "1. Text.", 1234)
    assert b.startswith("\n\n[PROVISION FETCHED BY CODE — this index lacks SSI 1901/3 "
                        "(The Widget Order 1901), so code read its text from legislation.gov.uk")
    assert "the version as made with its schedules, 1,234 characters. Check that its title " \
           "is the instrument the question is about before relying on it. Below is the " \
           "whole" in b
    assert f"cite it as https://www.legislation.gov.uk/{LID}/made" in b
    assert "because the index lacks it" in b
    assert b.endswith("]\n1. Text.\n[/PROVISION FETCHED BY CODE]")
    b2 = pt.published_block(LID, pt.KIND_NO_TEXT, _ok("current", False), "summary", "S.", 9)
    assert "this index holds the record of SSI 1901/3 (The Widget Order 1901) but none of its text" in b2
    assert "current version (it publishes no version as made or enacted of it) (it has no " \
           "schedule)" in b2
    assert "below is a summary of that retrieved text" in b2
    assert pt.has_published_text(b) and pt.has_published_text(b2)


def test_the_block_never_matches_a_handed_schedule_paragraph():
    from src.utils.paragraph_restore import handed_paragraphs
    body = "Section 1) **Widgets**\n1) text"
    b = pt.published_block(LID, pt.KIND_NOT_HELD, _ok(), "whole", body, 10)
    assert handed_paragraphs(b) == []


@pytest.mark.parametrize("outcome,phrase", [
    ({"status": pt.NOT_PUBLISHED}, "returned no document under ssi/1901/3 either"),
    ({"status": pt.PDF_ONLY, "pdf": "https://x/y.pdf"}, "only as a scanned PDF (https://x/y.pdf)"),
    ({"status": pt.FAILED, "reason": "no_reply"}, "did not complete (no reply)"),
    ({"status": pt.FAILED, "reason": "http_500"}, "did not complete (the read did not complete)"),
    ({"status": pt.LIMIT, "limit": 8}, "already read 8 instruments from there"),
    ({"status": pt.EARLIER}, "earlier in this research"),
])
def test_every_no_text_outcome_is_one_line(outcome, phrase):
    line = pt.published_line(LID, pt.KIND_NOT_HELD, outcome)
    assert line.startswith("\n\n[PROVISION FETCHED BY CODE — this index lacks SSI 1901/3")
    assert line.endswith("]") and line.count("]") == 1 and line.count("[") == 1
    assert phrase in line
    assert not pt.has_published_text(line)
    assert pt.blocks_in("x" + line).strip() == line.strip()


def test_an_unsupported_outcome_says_nothing():
    assert pt.published_line(LID, pt.KIND_NOT_HELD, {"status": pt.UNSUPPORTED}) == ""


def test_blocks_in_finds_only_this_rows_blocks_in_order():
    from src.utils.schedule_units import FETCHED_CLOSE, FETCHED_OPEN
    b = pt.published_block(LID, pt.KIND_NOT_HELD, _ok(), "whole", "1. T.", 5)
    line = pt.published_line("ssi/1901/4", pt.KIND_NO_TEXT, {"status": pt.NOT_PUBLISHED})
    p312 = f"\n\n{FETCHED_OPEN}the index holds Schedule 2 of ssi/1901/3 as one provision.]\nx\n{FETCHED_CLOSE}"
    got = pt.blocks_in('{"tool": "lookup_legislation"}' + b + p312 + line)
    assert got == b + line
    assert pt.blocks_in(None) == "" and pt.blocks_in("no blocks") == ""


def test_the_record_drives_the_managers_limb_and_the_lawyers_footer():
    log = []
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.OK, "version": "made"})
    pt.record_published(log, "ssi/1901/4", pt.KIND_NO_TEXT, {"status": pt.FAILED})
    pt.record_published(log, "ssi/1901/5", pt.KIND_NO_TEXT, {"status": pt.UNSUPPORTED})
    assert [e["status"] for e in log] == [pt.OK, pt.FAILED]
    limb = pt.published_limb(log)
    assert "Read from legislation.gov.uk by code, because the index lacks the text: " \
           "SSI 1901/3 (the version as made)." in limb
    assert "Asked legislation.gov.uk for the text, and none was read: SSI 1901/4." in limb
    assert pt.published_footer_clause(log) == (
        " The text of SSI 1901/3 (as made) was read from legislation.gov.uk.")
    assert pt.published_limb([]) == "" and pt.published_footer_clause([]) == ""
    # a failed read gets no footer clause
    assert pt.published_footer_clause(log[1:]) == ""


def test_a_read_after_a_failed_one_wins_in_the_limb():
    log = []
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.FAILED})
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.OK, "version": "made"})
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.EARLIER})
    limb = pt.published_limb(log)
    assert "SSI 1901/3 (the version as made)" in limb and "none was read" not in limb
    assert pt.handed_in_run(log, LID) and not pt.handed_in_run(log, "ssi/1901/4")
    assert pt.published_footer_clause(log).count("SSI 1901/3") == 1


def test_the_footer_names_each_version():
    log = [{"tool": pt.PUBLISHED_ENTRY, "legislation_id": f"ssi/1901/{n}",
            "label": f"SSI 1901/{n}", "status": pt.OK, "version": v}
           for n, v in ((1, "made"), (2, "enacted"), (3, "current"))]
    assert pt.published_footer_clause(log) == (
        " The text of SSI 1901/1 (as made), SSI 1901/2 (as enacted) and SSI 1901/3 "
        "(its current version) was read from legislation.gov.uk.")


# ---------------------------------------------------------------------------
# the seam: run_worker_tool
# ---------------------------------------------------------------------------

async def _chunk(*a, **k):
    return None


def _run(name, args, raw, monkeypatch, pages=None, search_log=None, memo=None,
         urls=None, budget=None, cfg=None):
    """One `run_worker_tool` call with the executor stubbed to `raw` and the
    read served from `pages`."""
    from src.agent.agent_shared import run_worker_tool
    srv = _Server(pages or {}).install(monkeypatch)

    async def go():
        set_request_provider_config(cfg if cfg is not None else {"_test": True})
        with patch("src.agent.agent_shared.execute_worker_tool",
                   new=AsyncMock(return_value=raw)):
            return await run_worker_tool(name, dict(args), "is a widget fee set?", _chunk,
                                         "test-model", search_log=search_log,
                                         tool_memo=memo, retrieved_urls=urls,
                                         context_budget=budget)
    return asyncio.run(go()), srv


def test_a_not_held_lookup_hands_the_worker_the_text(monkeypatch):
    log, urls = [], set()
    out, srv = _run("lookup_legislation", {"legislation_id": LID}, _lookup("not_held"),
                    monkeypatch, {f"{LID}/made/data.xml": (200, _doc())}, log, urls=urls)
    assert out.startswith(_lookup("not_held"))
    assert "this index lacks SSI 1901/3 (The Widget Order 1901), so code read" in out
    assert "1. (1) This Order may be cited as the Widget Order 1901." in out
    assert [e["status"] for e in log if e["tool"] == pt.PUBLISHED_ENTRY] == [pt.OK]
    # P2.3 with P3.38: the preamble read states the power
    assert "[ENABLING POWER — legislation.gov.uk's text of ssi/1901/3, read by code DOES " \
           "state what ssi/1901/3 was made" in out
    assert {"tool": "enabling_power", "legislation_id": LID, "stated": True,
            "source": "legislation_gov_uk"} in log
    # the provisions it carries may be cited, with or without the version
    assert "legislation.gov.uk/ssi/1901/3/article/1/made" in urls
    assert "legislation.gov.uk/ssi/1901/3/article/1" in urls
    assert "legislation.gov.uk/ssi/1901/3/made" in urls


def test_a_preamble_without_a_recital_permits_nothing(monkeypatch):
    log = []
    doc = _doc(preamble="The Scottish Ministers make the following Order")
    out, _ = _run("lookup_legislation", {"legislation_id": LID}, _lookup("not_held"),
                  monkeypatch, {f"{LID}/made/data.xml": (200, doc)}, log)
    assert "[ENABLING POWER" not in out
    assert not [e for e in log if e["tool"] == "enabling_power"]


def test_an_act_never_gets_the_instrument_recital_block(monkeypatch):
    lid = "asp/1901/1"
    out, _ = _run("lookup_legislation", {}, _lookup("not_held", lid), monkeypatch,
                  {f"{lid}/enacted/data.xml": (200, _doc(lid, "enacted"))})
    assert "so code read its text" in out and "[ENABLING POWER" not in out


def test_an_empty_text_read_hands_the_worker_the_text(monkeypatch):
    raw = json.dumps({"legislation": {"title": "The Widget Order 1901"},
                      "full_text": "No text content available for this legislation."})
    log = []
    out, _ = _run("get_legislation_text", {"legislation_id": LID}, raw, monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, log)
    assert "this index holds the record of SSI 1901/3 (The Widget Order 1901) but none of its text" in out
    assert "This Order may be cited" in out
    # the permitting block replaced P2.3's forbidding one
    assert "does NOT state what" not in out and "DOES state what ssi/1901/3" in out


def test_a_not_found_text_read_says_its_text_follows(monkeypatch):
    raw = 'Error executing tool: {"detail":"Legislation not found: ssi 1901 No. 3"}'
    out, _ = _run("get_legislation_text", {"legislation_id": LID}, raw, monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, [])
    assert "Say plainly that this index does not hold it, and that its text below was " \
           "read from legislation.gov.uk instead." in out
    assert "its contents could not be checked here" not in out
    assert out.index("[SEARCH SCOPE — not held") < out.index("so code read its text")
    # said as what the read returned: the index may hold the record under
    # another form of the id (the regnal 404)
    assert "this index's text read gave no text for SSI 1901/3 (The Widget Order 1901) under that id, so code" in out
    assert "because the index's text read gave none." in out
    assert "this index lacks" not in out


def test_a_failed_read_leaves_the_not_held_note_as_it_was(monkeypatch):
    raw = 'Error executing tool: {"detail":"Legislation not found: ssi 1901 No. 3"}'
    log = []
    out, _ = _run("get_legislation_text", {"legislation_id": LID}, raw, monkeypatch, {
        f"{LID}/made/data.xml": (500, "boom")}, log)
    assert "its contents could not be checked here" in out
    assert "did not complete (the read did not complete)" in out
    assert [e["status"] for e in log if e["tool"] == pt.PUBLISHED_ENTRY] == [pt.FAILED]


def test_a_held_lookup_reads_nothing(monkeypatch):
    out, srv = _run("lookup_legislation", {}, _lookup("held"), monkeypatch,
                    {f"{LID}/made/data.xml": (200, _doc())}, [])
    assert srv.asked == [] and "PROVISION FETCHED" not in out


def test_a_text_longer_than_the_threshold_is_summarised_without_the_shared_cache(monkeypatch):
    summary = AsyncMock(return_value=("A summary of the Widget Order.", False))
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query", summary)
    monkeypatch.setattr("src.agent.provider_factory.get_summarise_threshold", lambda: 50)

    async def _never(*a, **k):
        raise AssertionError("the legislation.gov.uk text must never reach the shared cache")
    from src.services import local_prompt_cache as lpc
    monkeypatch.setattr(lpc, "lookup", _never)
    monkeypatch.setattr(lpc, "store", _never)
    out, _ = _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, [])
    assert "below is a summary of that retrieved text" in out
    assert "A summary of the Widget Order.\n[/PROVISION FETCHED BY CODE]" in out
    assert "This Order may be cited" not in out
    assert summary.await_args.args[1] == "is a widget fee set?"


def test_a_summary_longer_than_the_threshold_is_cut_to_it(monkeypatch):
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query",
                        AsyncMock(return_value=("S" * 500, False)))
    monkeypatch.setattr("src.agent.provider_factory.get_summarise_threshold", lambda: 60)
    out, _ = _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, [])
    assert "S" * 60 + "\n[/PROVISION FETCHED BY CODE]" in out and "S" * 61 not in out


def test_a_text_that_would_overrun_the_context_budget_is_summarised(monkeypatch):
    summary = AsyncMock(return_value=("Short.", False))
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query", summary)
    # room for the lookup result itself, not for the text after it
    budget = {"used": 0, "limit": len(_lookup("not_held")) + 50}
    out, _ = _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, [], budget=budget)
    assert summary.await_count == 1 and "below is a summary" in out


def test_a_text_within_the_threshold_and_budget_goes_whole(monkeypatch):
    summary = AsyncMock(return_value=("Short.", False))
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query", summary)
    out, _ = _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch,
                  {f"{LID}/made/data.xml": (200, _doc())}, [],
                  budget={"used": 0, "limit": 250_000})
    assert summary.await_count == 0 and "Below is the whole of it." in out


def test_a_second_trigger_in_one_run_points_back(monkeypatch):
    log = []
    _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch,
         {f"{LID}/made/data.xml": (200, _doc())}, log)
    raw = 'Error executing tool: {"detail":"Legislation not found: ssi 1901 No. 3"}'
    out, srv = _run("get_legislation_text", {"legislation_id": LID}, raw, monkeypatch,
                    {f"{LID}/made/data.xml": (200, _doc())}, log)
    assert srv.asked == []
    assert "code read its text from legislation.gov.uk earlier in this research" in out
    assert "its text was read from legislation.gov.uk earlier in this research" in out
    assert "This Order may be cited" not in out


def test_a_memo_hit_records_the_read_for_the_reusing_step(monkeypatch):
    memo, first, second = {}, [], []
    out1, srv = _run("lookup_legislation", {"legislation_id": LID}, _lookup("not_held"),
                     monkeypatch, {f"{LID}/made/data.xml": (200, _doc())}, first, memo=memo)
    out2, srv2 = _run("lookup_legislation", {"legislation_id": LID}, _lookup("not_held"),
                      monkeypatch, {f"{LID}/made/data.xml": (200, _doc())}, second, memo=memo)
    assert out1 == out2 and srv2.asked == []
    pub = [e for e in second if e["tool"] in (pt.PUBLISHED_ENTRY, "enabling_power")]
    assert [e["tool"] for e in pub] == [pt.PUBLISHED_ENTRY, "enabling_power"]


def test_a_failure_inside_the_route_leaves_the_result_as_it_was(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr("src.agent.agent_shared.published_text_route", _boom)
    out, _ = _run("lookup_legislation", {}, _lookup("not_held"), monkeypatch, {}, [])
    assert out == _lookup("not_held")


# ---------------------------------------------------------------------------
# the brief, the quick-lookup suffix, the Manager's block and the footer
# ---------------------------------------------------------------------------

def _final(status, lid=LID, with_text=True):
    got = _lookup(status, lid)
    if with_text:
        return got + pt.published_block(lid, pt.KIND_NOT_HELD if status == "not_held"
                                        else pt.KIND_NO_TEXT, _ok(), "whole", "1. Text.", 8)
    return got + pt.published_line(lid, pt.KIND_NOT_HELD, {"status": pt.FAILED})


def test_the_routed_brief_carries_the_text_after_its_block():
    from src.utils.instrument_lookup import routed_lookup_block

    finals = {LID: _final("not_held"), "ssi/1901/4": _final("held_without_text", "ssi/1901/4"),
              "ssi/1901/5": _final("not_held", "ssi/1901/5", with_text=False)}

    async def run_tool(name, args):
        return finals[f"{args['legislation_type']}/{args['year']}/{args['number']}"]
    brief = "Check SSI 1901/3, SSI 1901/4 and SSI 1901/5."
    block = asyncio.run(routed_lookup_block(brief, ["lookup_legislation"], run_tool))
    head, _, rest = block.partition("]\n\n[PROVISION FETCHED BY CODE")
    assert head.startswith("\n\n[SEARCH SCOPE — instrument lookup")
    assert "SSI 1901/3: NOT HELD." in head and "and that text follows this block" in head
    assert "SSI 1901/4 (" not in head  # the lookup result here carries no title
    assert "SSI 1901/4: HELD WITHOUT TEXT." in head
    # a failed read: the sentence as it was, and the failure line after the block
    assert "SSI 1901/5: NOT HELD. The index has no record of it under that type, year and " \
           "number, so a search for its title or number will not find it and its text " \
           "cannot be read here." in head
    assert block.count("[/PROVISION FETCHED BY CODE]") == 2
    assert block.rstrip().endswith("did not complete (the read did not complete), so its text "
                                   "could not be checked here. That says nothing about the "
                                   "instrument.]")


def test_the_brief_is_unchanged_without_a_read():
    from src.utils.instrument_lookup import lookup_brief_block
    for status in ("not_held", "held_without_text", "held"):
        plain = lookup_brief_block([_lookup(status)])
        assert "legislation.gov.uk instead" not in plain


def test_the_quick_lookup_suffix_carries_the_text():
    from src.utils.instrument_lookup import section_search_lookup

    async def run_tool(name, args):
        return _final("held_without_text")
    suffix = asyncio.run(section_search_lookup(
        "search_legislation_sections", {"legislation_id": LID}, set(), run_tool))
    assert "so code read its text from legislation.gov.uk" in suffix
    assert suffix.rstrip().endswith("[/PROVISION FETCHED BY CODE]")


def test_the_managers_block_and_the_footer_say_where_the_text_came_from():
    from src.utils.search_scope import (
        LOOKUP_ENTRY, answer_scope_footer, lookup_scope_footer, worker_scope_block,
    )
    log = [{"tool": LOOKUP_ENTRY, "legislation_id": LID, "label": "SSI 1901/3",
            "status": "not_held"}]
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.OK, "version": "made"})
    block = worker_scope_block(log, {})
    assert "Read from legislation.gov.uk by code, because the index lacks the text: " \
           "SSI 1901/3 (the version as made)." in block
    assert block.index("Looked up by number") < block.index("Read from legislation.gov.uk")
    footer = lookup_scope_footer(log)
    assert "SSI 1901/3 was looked up by its number and is not held in this index" in footer
    assert footer.rstrip("*").endswith(
        "The text of SSI 1901/3 (as made) was read from legislation.gov.uk.")
    searched = log + [{"tool": "search_legislation", "query": "widget", "shown": 5,
                       "matched": 9}]
    assert "The text of SSI 1901/3 (as made) was read from legislation.gov.uk." in \
        answer_scope_footer(searched, {})


def test_a_read_with_no_lookup_still_reaches_the_footer():
    from src.utils.search_scope import lookup_scope_footer
    log = []
    pt.record_published(log, LID, pt.KIND_NO_TEXT, {"status": pt.OK, "version": "made"})
    assert "The text of SSI 1901/3 (as made) was read from legislation.gov.uk." in \
        lookup_scope_footer(log)


def test_an_earlier_footer_still_parses_back_with_the_clause_after_it():
    from src.utils.search_scope import LOOKUP_ENTRY, _earlier_lookups, lookup_scope_footer
    log = [{"tool": LOOKUP_ENTRY, "legislation_id": LID, "label": "SSI 1901/3",
            "status": "not_held"}]
    pt.record_published(log, LID, pt.KIND_NOT_HELD, {"status": pt.OK, "version": "made"})
    msgs = [{"role": "assistant", "content": "Answer." + lookup_scope_footer(log)}]
    got = _earlier_lookups(msgs)
    assert [(e["label"], e["status"]) for e in got] == [("SSI 1901/3", "not_held")]
