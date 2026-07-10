"""Unit tests for the National Archives case law parsers.

Pure functions over Atom (search results) and LegalDocML/AKN (judgment text) XML,
so no network or DB is needed. Fixtures are inlined as small representative
snippets (unlike the large gz caption fixture in test_caption_match.py, these
inputs are tiny and clearer read in-place).
"""

from src.agent.tools.caselaw import _extract_judgment_text, _parse_case_law_atom


_ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:uk="https://caselaw.nationalarchives.gov.uk/terms/v1">
  <title>Search results</title>
  <entry>
    <title>R (on the application of Miller) v The Prime Minister</title>
    <link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/uksc/2019/41"/>
    <id>https://caselaw.nationalarchives.gov.uk/uksc/2019/41</id>
    <published>2019-09-24T00:00:00Z</published>
    <uk:ncn>[2019] UKSC 41</uk:ncn>
    <uk:court>UKSC</uk:court>
  </entry>
  <entry>
    <title>Fixture Two v Example</title>
    <id>https://caselaw.nationalarchives.gov.uk/ewca/civ/2020/1</id>
    <link href="https://caselaw.nationalarchives.gov.uk/ewca/civ/2020/1"/>
    <published>2020-01-15T09:30:00Z</published>
    <uk:ncn>[2020] EWCA Civ 1</uk:ncn>
    <uk:court>EWCA-Civil</uk:court>
  </entry>
</feed>
"""

_AKN_JUDGMENT = """<?xml version="1.0" encoding="utf-8"?>
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">
  <judgment>
    <header><FRBRname value="[2019] UKSC 41"/></header>
    <judgmentBody>
      <p>The appeal is <b>allowed</b>.</p>
      <p>Costs are awarded to the appellant.</p>
    </judgmentBody>
  </judgment>
</akomaNtoso>
"""


def test_atom_parses_entries_with_all_fields():
    entries = _parse_case_law_atom(_ATOM_FEED)
    assert len(entries) == 2
    first = entries[0]
    assert first["title"] == "R (on the application of Miller) v The Prime Minister"
    assert first["ncn"] == "[2019] UKSC 41"
    assert first["court"] == "UKSC"
    assert first["date"] == "2019-09-24"  # published truncated to the date
    assert first["url"] == "https://caselaw.nationalarchives.gov.uk/uksc/2019/41"


def test_atom_falls_back_to_plain_link_when_no_alternate():
    # Second entry has no rel="alternate" link — parser falls back to the first <link>.
    entries = _parse_case_law_atom(_ATOM_FEED)
    assert entries[1]["url"] == "https://caselaw.nationalarchives.gov.uk/ewca/civ/2020/1"


def test_atom_malformed_returns_empty():
    assert _parse_case_law_atom("<feed><entry>unclosed") == []
    assert _parse_case_law_atom("") == []


def test_atom_empty_feed_returns_empty():
    empty = '<feed xmlns="http://www.w3.org/2005/Atom"><title>none</title></feed>'
    assert _parse_case_law_atom(empty) == []


def test_extract_judgment_text_collects_text_and_tail():
    text = _extract_judgment_text(_AKN_JUDGMENT)
    assert "The appeal is" in text
    assert "allowed" in text  # nested <b> element text is collected
    assert "." in text  # the tail after </b> is collected
    assert "Costs are awarded to the appellant." in text


def test_extract_judgment_text_malformed_returns_empty():
    assert _extract_judgment_text("<akn><p>unclosed") == ""
    assert _extract_judgment_text("") == ""
