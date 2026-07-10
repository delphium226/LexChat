"""Unit tests for the Scottish Parliament Official Report HTML parsers.

Pure functions over listing/meeting/transcript HTML, so no network or DB is
needed. Fixtures are inlined as small representative snippets that reproduce the
markup shapes the regexes target (the `<p id="orscontributions_...">` speech
structure, `meeting=ID&iob=ID` agenda links, and committee-vs-plenary slugs).
"""

from src.agent.tools.parliament import (
    _parse_sp_listing_meetings,
    _parse_sp_meeting_page,
    _parse_sp_plenary_meetings,
    _parse_sp_plenary_transcript,
    _strip_html,
)


# --- _strip_html ---

def test_strip_html_removes_tags_and_unescapes_entities():
    out = _strip_html("<p>Hello &amp; <b>world</b></p>")
    assert "<" not in out and ">" not in out
    assert "&amp;" not in out and "&" in out
    assert "Hello" in out and "world" in out


def test_strip_html_handles_none_and_empty():
    assert _strip_html(None) == ""
    assert _strip_html("") == ""


# --- listing parsers (committee vs plenary) ---

_LISTING = """
<ul>
  <li><a href="/chamber-and-committees/official-report/search-what-was-said-in-parliament/education-children-and-young-people-committee-03-06-2026?meeting=16000">Education Cttee</a></li>
  <li><a href="/chamber-and-committees/official-report/search-what-was-said-in-parliament/meeting-of-parliament-02-06-2026?meeting=16001">Meeting of Parliament</a></li>
</ul>
"""


def test_listing_committee_parser_excludes_plenary():
    meetings = _parse_sp_listing_meetings(_LISTING)
    assert len(meetings) == 1
    m = meetings[0]
    assert m["meeting_id"] == "16000"
    assert m["slug"] == "education-children-and-young-people-committee-03-06-2026"
    assert m["committee_code"] == "education-children-and-young-people-committee"
    assert m["date"] == "2026-06-03"


def test_listing_plenary_parser_includes_only_plenary():
    meetings = _parse_sp_plenary_meetings(_LISTING)
    assert len(meetings) == 1
    m = meetings[0]
    assert m["meeting_id"] == "16001"
    assert m["committee_code"] == "MOP"
    assert m["committee_name"] == "Meeting of Parliament"
    assert m["date"] == "2026-06-02"


def test_listing_deduplicates_repeated_links():
    doubled = _LISTING + _LISTING
    assert len(_parse_sp_listing_meetings(doubled)) == 1


# --- _parse_sp_meeting_page ---

_MEETING_PAGE = """
<html><head><title>Education Committee | Scottish Parliament</title></head>
<body>
  <h1>Education, Children and Young People Committee [Draft], Meeting date: 3 June 2026</h1>
  <a href="/official-report/search-what-was-said-in-parliament/edu-03-06-2026?meeting=16000&amp;iob=5001">Subordinate Legislation</a>
  <a href="/official-report/search-what-was-said-in-parliament/edu-03-06-2026?meeting=16000&amp;iob=5002">Evidence Session</a>
</body></html>
"""


def test_meeting_page_extracts_clean_committee_name():
    out = _parse_sp_meeting_page(_MEETING_PAGE, "edu-03-06-2026", "16000")
    # [Draft] and the trailing "Meeting date:" clause are stripped
    assert out["committee_name"] == "Education, Children and Young People Committee"


def test_meeting_page_extracts_agenda_items_with_iob():
    out = _parse_sp_meeting_page(_MEETING_PAGE, "edu-03-06-2026", "16000")
    items = out["agenda_items"]
    assert [i["iob_id"] for i in items] == ["5001", "5002"]
    assert items[0]["title"] == "Subordinate Legislation"
    assert items[0]["url"].endswith("?meeting=16000&iob=5001")


# --- _parse_sp_plenary_transcript ---

_TRANSCRIPT = """
<html><head><title>Meeting of the Parliament | Scottish Parliament</title></head>
<body><main>
  <h2 class="h3">First Item</h2>
  <p id="orscontributions_1"><a href="/msps/1/alpha-msp">Alpha MSP</a>:</p>
  <p>Thank you, Presiding Officer. This is the first point.</p>
  <p>14:05</p>
  <p>And this is the second point.</p>
  <h2 class="h3">Second Item</h2>
  <p id="orscontributions_2"><a href="/msps/2/beta-msp">Beta MSP (Minister)</a>:</p>
  <p>I am grateful to the member for that question.</p>
</main></body></html>
"""


def test_transcript_parses_attributed_speeches():
    out = _parse_sp_plenary_transcript(_TRANSCRIPT, "http://example/x")
    assert out["page_title"] == "Meeting of the Parliament"
    assert out["total_speeches"] == 2
    first, second = out["speeches"]
    assert first["speaker"] == "Alpha MSP"
    # multiple body paragraphs joined; the bare "14:05" timestamp paragraph is dropped
    assert "first point" in first["text"] and "second point" in first["text"]
    assert "14:05" not in first["text"]
    assert second["speaker"] == "Beta MSP (Minister)"


def test_transcript_scopes_to_agenda_item():
    # Scoping to "First Item" cuts the transcript at the next <h2 class="h3">,
    # so only Alpha's contribution remains.
    out = _parse_sp_plenary_transcript(_TRANSCRIPT, "http://example/x", agenda_title="First Item")
    assert out["total_speeches"] == 1
    assert out["speeches"][0]["speaker"] == "Alpha MSP"


def test_transcript_no_contributions_returns_empty_list():
    out = _parse_sp_plenary_transcript("<main><p>Nothing here</p></main>", "http://example/x")
    assert out["speeches"] == []
    assert out["total_speeches"] == 0
