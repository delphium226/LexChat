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


# --- P3.29: the appeal detector links one litigation, not one shared word ------
#
# Over every stored result set and batch 8 C's re-run, 211 of the 317 distinct
# appeals the old rule flagged were unrelated cases sharing one word (a place,
# "county", "holdings", a first name). Real titles from those sets.

_TNA = "https://caselaw.nationalarchives.gov.uk/"


def _d(title, path, date):
    """A feed row as the live parser returns it: ncn/court blank, court in the URL."""
    return {"title": title, "ncn": "", "court": "", "url": _TNA + path, "date": date}


def _flagged(results):
    return [a["url"].replace(_TNA, "") for a in detect_appellate_decisions(results)]


def test_p329_genuine_appeal_with_dates_is_kept():
    results = [
        _d("Sophie Coulthard & Anor, R (on the application of) v Secretary of State for the "
           "Environment, Food and Rural Affairs", "ewhc/admin/2024/3252", "2024-12-17"),
        _d("Sophie Coulthard & Anor, R (on the application of) v Secretary of State for the "
           "Environment, Food and Rural Affairs", "ewca/civ/2025/1671", "2025-12-19"),
    ]
    assert _flagged(results) == ["ewca/civ/2025/1671"]


def test_p329_shared_place_word_is_not_a_link():
    # "borough" and "county" are the vocabulary of party names, not a party.
    results = [
        _d("Cheshire East Borough Council v Secretary of State for Communities and Local "
           "Government", "ewhc/admin/2015/410", "2015-02-25"),
        _d("Wigan Borough Council v Scullindale Global Ltd & Ors", "ewhc/ch/2021/779", "2021-04-01"),
        _d("Kay & Ors v London Borough of Lambeth & Anor", "ewca/civ/2017/926", "2017-07-20"),
        _d("Hampshire County Council v Secretary of State for Environment, Food and Rural "
           "Affairs", "ewhc/admin/2020/959", "2020-04-23"),
        _d("Powys County Council v Price & Anor", "ewca/civ/2021/1133", "2021-07-27"),
    ]
    assert _flagged(results) == []


def test_p329_two_shared_local_government_words_are_not_a_link():
    # "London" and "Borough" are two shared words, and an anonymised claimant
    # ("AAM") has no name word to differ on: only the vocabulary list stops it.
    results = [
        _d("AAM, R (on the application of) v London Borough of Bromley", "ewhc/admin/2025/1565",
           "2025-06-23"),
        _d("Haneen Abdelrahman v The Mayor and Burgesses of the London Borough of Islington",
           "ewca/civ/2025/1038", "2025-07-31"),
    ]
    assert _flagged(results) == []


def test_p329_lower_judgment_decided_after_the_appeal_is_not_its_appeal():
    # The same parties at two levels, but the "judgment under appeal" is later.
    results = [
        _d("Kanwarjit Singh Juj v John Lewis Partnership Plc", "ewca/civ/2023/1507", "2023-12-21"),
        _d("Kanwarjit Singh Juj v John Lewis Partnership Plc", "ewhc/kb/2024/2418", "2024-09-30"),
    ]
    assert _flagged(results) == []
    results[1]["date"] = "2022-09-30"
    assert _flagged(results) == ["ewca/civ/2023/1507"]


def test_p329_appeal_more_than_six_years_on_is_not_linked():
    results = [
        _d("Barclay & Ors, R (on the application of) v Secretary of State for Justice & Ors",
           "ewca/civ/2016/1319", "2016-12-02"),
        _d("Barclay & Anor, R (on the application of) v Secretary of State for Justice & Ors",
           "ewhc/admin/2008/1183", "2008-05-09"),
    ]
    assert _flagged(results) == []
    results[1]["date"] = "2011-05-09"
    assert _flagged(results) == ["ewca/civ/2016/1319"]


def test_p329_missing_date_is_not_refused_on_the_date():
    results = [
        _d("Jones v Cleanthi", "ewhc/qb/2005/2646", ""),
        _d("Jones v Cleanthi", "ewca/civ/2006/1712", "2006-12-12"),
    ]
    assert _flagged(results) == ["ewca/civ/2006/1712"]


def test_p329_one_shared_surname_needs_the_other_party_to_agree():
    # Berezovsky v Hine is not the appeal of Berezovsky v Abramovich ...
    results = [
        _d("Berezovsky v Abramovich", "ewhc/comm/2011/1143", "2011-05-06"),
        _d("Berezovsky v Hine & Ors", "ewca/civ/2011/1089", "2011-10-07"),
    ]
    assert _flagged(results) == []
    # ... but SSWP v Payne is the appeal of Payne v SSWP (the parties swapped).
    results = [
        _d("Payne & Anor, R (on the application of) v Secretary of State for Work and Pensions",
           "ewhc/admin/2010/2162", "2010-07-26"),
        _d("Secretary of State for Work & Pensions v Payne & Anor", "ewca/civ/2010/1431",
           "2010-12-14"),
    ]
    assert _flagged(results) == ["ewca/civ/2010/1431"]


def test_p329_first_name_is_not_a_link():
    results = [
        _d("Paul Birch v Paula Brookfield & Ors", "ewhc/comm/2025/732", "2025-03-27"),
        _d("Paul Morgan Evans & Anor v Swansea Building Society", "ewca/civ/2026/978",
           "2026-07-28"),
    ]
    assert _flagged(results) == []


def test_p329_two_shared_words_with_the_other_party_named_differently():
    results = [
        _d("Dan Cornel Nistor & Anor v Union of Shop, Distributive and Allied Workers (USDAW)",
           "ewhc/kb/2024/1165", "2024-05-16"),
        _d("Tesco Stores Ltd v Union of Shop, Distributive and Allied Workers and others",
           "uksc/2024/28", "2024-09-12"),
    ]
    assert _flagged(results) == []
    results.append(_d("THE UNION OF SHOP, DISTRIBUTIVE AND ALLIED WORKERS v TESCO STORES "
                      "LIMITED", "ewhc/qb/2022/201", "2022-02-03"))
    assert _flagged(results) == ["uksc/2024/28"]


def test_p329_valuation_officer_name_against_different_ratepayers():
    # A valuation officer's name is in unrelated appeals against the same office ...
    results = [
        _d("Michael Stanuszek v Dawn Bunyan (Listing Officer)", "ewhc/admin/2025/255",
           "2025-02-07"),
        _d("Dawn Bunyan (Valuation Officer) v Fridays Limited", "ewca/civ/2025/666",
           "2025-05-22"),
    ]
    assert _flagged(results) == []
    # ... and the ratepayer, with the officer on the other side, still links.
    results = [
        _d("S & J Monk v Keith Newbigin (VO)", "ukut/lc/2014/14", "2014-02-26"),
        _d("Newbigin (Valuation Officer) v S J & J Monk (a firm)", "ewca/civ/2015/78",
           "2015-02-13"),
    ]
    assert _flagged(results) == ["ewca/civ/2015/78"]


def test_p329_criminal_division_and_privy_council_are_never_flagged():
    results = [
        _d("Prospect v Andrew Evans", "ewhc/kb/2025/499", "2025-03-10"),
        _d("Andrew Evans v R", "ewca/crim/2025/1150", "2025-09-05"),
        _d("Bank of Scotland v Hussain & Anor", "ewhc/ch/2022/2812", "2022-11-05"),
        _d("Hussain v Bank of Scotland (Jersey)", "ukpc/2023/12", "2023-03-22"),
    ]
    assert _flagged(results) == []


def test_p329_same_two_parties_with_generic_names_link():
    results = [
        _d("British Telecommunications Plc, R (on the application of) v Her Majesty's Treasury",
           "ewhc/admin/2018/3251", "2018-11-28"),
        _d("British Telecommunications PLC, R (On the Application Of) v Treasury",
           "ewca/civ/2020/1", "2020-01-21"),
    ]
    assert _flagged(results) == ["ewca/civ/2020/1"]


def test_p329_two_letter_initials_against_one_department_are_not_a_link():
    results = [
        _d("AM, R (on the application of) v Secretary of State for the Home Department",
           "ewhc/admin/2022/2591", "2022-10-14"),
        _d("R (on the application of AM (Belarus)) v Secretary of State for the Home Department",
           "uksc/2024/13", "2024-04-24"),
    ]
    assert _flagged(results) == []


def test_p329_frequent_surname_in_the_set_still_links():
    # The old rule dropped a word in more than three results, so a litigant with
    # several judgments in one set ("Evans") was never linked.
    results = [
        _d("Evans v First Secretary of State & Anor", "ewhc/admin/2003/2169", "2003-09-08"),
        _d("Evans v Barclays Bank Plc", "ewhc/ch/2020/1", "2020-01-01"),
        _d("Avon Estates Ltd v Evans & Anor", "ewhc/ch/2013/1635", "2013-06-13"),
        _d("Stuart William Evans & Ors v JNP Group", "ewhc/comm/2026/2175", "2026-08-14"),
        _d("Evans v First Secretary of State & Ors", "ewca/civ/2003/1523", "2003-11-05"),
    ]
    assert _flagged(results) == ["ewca/civ/2003/1523"]
