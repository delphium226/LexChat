"""Unit tests for the National Archives case law parsers.

Pure functions over Atom (search results) and LegalDocML/AKN (judgment text) XML,
so no network or DB is needed. Fixtures are inlined as small representative
snippets (unlike the large gz caption fixture in test_caption_match.py, these
inputs are tiny and clearer read in-place).
"""

from src.agent.tools.caselaw import (
    _extract_judgment_text,
    _parse_case_law_atom,
    detect_appellate_decisions,
)


# Mirrors the real National Archives feed: the neutral citation is the TEXT of a
# <uk:identifier type="ukncn"> element (there are several identifier elements, only one
# is the ukncn) on the bare host namespace, and its slug attribute carries the court
# path. There is NO <uk:ncn>/<uk:court> element — an earlier fixture invented those,
# which is why the parser bug (reading a non-existent element) went unnoticed.
_ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:uk="https://caselaw.nationalarchives.gov.uk">
  <title>Search results</title>
  <entry>
    <title>R (on the application of Miller) v The Prime Minister</title>
    <link rel="alternate" href="https://caselaw.nationalarchives.gov.uk/uksc/2019/41"/>
    <id>https://caselaw.nationalarchives.gov.uk/uksc/2019/41</id>
    <published>2019-09-24T00:00:00Z</published>
    <uk:identifier slug="uksc/2019/41" type="ukncn">[2019] UKSC 41</uk:identifier>
    <uk:identifier slug="tna.abcd1234" type="fclid">abcd1234</uk:identifier>
  </entry>
  <entry>
    <title>Fixture Two v Example</title>
    <id>https://caselaw.nationalarchives.gov.uk/ewca/civ/2020/1</id>
    <link href="https://caselaw.nationalarchives.gov.uk/ewca/civ/2020/1"/>
    <published>2020-01-15T09:30:00Z</published>
    <uk:identifier slug="ewca/civ/2020/1" type="ukncn">[2020] EWCA Civ 1</uk:identifier>
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
    assert first["ncn"] == "[2019] UKSC 41"  # text of the ukncn identifier
    assert first["court"] == "uksc"  # court path from the ukncn slug (year/number stripped)
    assert first["date"] == "2019-09-24"  # published truncated to the date
    assert first["url"] == "https://caselaw.nationalarchives.gov.uk/uksc/2019/41"
    assert entries[1]["court"] == "ewca/civ"  # multi-segment court path preserved


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


# --- detect_appellate_decisions -------------------------------------------------

def _r(title, ncn, court, url):
    return {"title": title, "ncn": ncn, "court": court, "url": url}


def test_detect_appeal_flags_higher_court_of_same_case():
    # The L31 Coulthard scenario: first-instance EWHC and its EWCA appeal both present.
    results = [
        _r("R (Coulthard) v Secretary of State for Environment, Food and Rural Affairs",
           "[2024] EWHC 3252 (Admin)", "EWHC-Administrative", "https://x/ewhc/admin/2024/3252"),
        _r("Coulthard v Secretary of State for Environment, Food and Rural Affairs",
           "[2025] EWCA Civ 1671", "EWCA-Civil", "https://x/ewca/civ/2025/1671"),
    ]
    appeals = detect_appellate_decisions(results)
    assert [a["ncn"] for a in appeals] == ["[2025] EWCA Civ 1671"]


def test_detect_appeal_returns_empty_when_only_first_instance_present():
    results = [
        _r("R (Coulthard) v Secretary of State for Environment, Food and Rural Affairs",
           "[2024] EWHC 3252 (Admin)", "EWHC-Administrative", "https://x/ewhc/admin/2024/3252"),
    ]
    assert detect_appellate_decisions(results) == []


def test_detect_appeal_ignores_unrelated_cases_sharing_only_boilerplate():
    # Two different cases, both against a "Secretary of State" — the shared words are
    # stopwords, so no distinctive token links them: no false appeal flag.
    results = [
        _r("R (Aardvark) v Secretary of State for the Home Department",
           "[2024] EWHC 100 (Admin)", "EWHC-Administrative", "https://x/ewhc/1"),
        _r("R (Zebra) v Secretary of State for the Home Department",
           "[2025] EWCA Civ 200", "EWCA-Civil", "https://x/ewca/2"),
    ]
    assert detect_appellate_decisions(results) == []


def test_detect_appeal_ignores_same_level_pair():
    # Same distinctive party but both at the High Court — no appellate result to flag.
    results = [
        _r("Brightwater Ltd v Someone", "[2024] EWHC 1 (Ch)", "EWHC-Chancery", "https://x/1"),
        _r("Brightwater Ltd v Someone Else", "[2024] EWHC 2 (Ch)", "EWHC-Chancery", "https://x/2"),
    ]
    assert detect_appellate_decisions(results) == []


def test_detect_appeal_uksc_over_ewca():
    results = [
        _r("Miller v The Prime Minister", "[2019] EWCA Civ 500", "EWCA-Civil", "https://x/ewca"),
        _r("R (Miller) v The Prime Minister", "[2019] UKSC 41", "UKSC", "https://x/uksc"),
    ]
    appeals = detect_appellate_decisions(results)
    assert [a["ncn"] for a in appeals] == ["[2019] UKSC 41"]


def test_detect_appeal_ranks_court_from_url_when_ncn_and_court_blank():
    # Live National Archives Atom feeds do NOT populate <uk:ncn>/<uk:court>, so the
    # court level is only in the URL path. Rank derivation must use the URL, or A2
    # never fires on real search results (regression: it silently returned []).
    results = [
        _r("Sophie Coulthard & Anor, R (on the application of) v Secretary of State "
           "for the Environment, Food and Rural Affairs",
           "", "", "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2024/3252"),
        _r("Sophie Coulthard & Anor, R (on the application of) v Secretary of State "
           "for the Environment, Food and Rural Affairs",
           "", "", "https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671"),
    ]
    appeals = detect_appellate_decisions(results)
    assert [a["url"] for a in appeals] == [
        "https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671"
    ]


def test_detect_appeal_skips_results_without_url():
    results = [
        _r("Coulthard v SSEFRA", "[2024] EWHC 3252 (Admin)", "EWHC", "https://x/ewhc"),
        {"title": "Coulthard v SSEFRA", "ncn": "[2025] EWCA Civ 1671", "court": "EWCA", "url": ""},
    ]
    assert detect_appellate_decisions(results) == []
