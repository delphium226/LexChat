"""P4.20: the legal professional's footer names ONE list of change records.

P3.5's clause (`_relations_footer_clause`) named the first three change records
consulted, in the order consulted; P2.5's (`_currency_footer_clause`) named,
sorted, the first three that held a commencement or repeal; P2.5's dated branch
named a third list and P3.49's a fourth. On one line they could disagree, and
the reader could not tell which records were checked: 109 of 423 stored footers
carrying both named different instruments, 36 more differed only in order
(Thomas, 23 and 30 September; `evidence/seam/thomas_s37/thomas_census2.py`).

Now P3.5's clause names the list once, in the order consulted, up to 8 then a
count; a property some but not all of the records hold is marked against each
record that holds it, and the other clauses point into the list.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.tools.lex import _slim_amendment_results  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402
from src.utils.search_scope import (  # noqa: E402
    _currency_footer_clause,
    _relations_footer_clause,
    answer_scope_footer,
    carried_scope_footer,
    record_currency,
    record_relations,
    record_search,
    section_scope_footer,
)

ID = re.compile(r"\b[a-z]{2,6}/[A-Za-z0-9-]+(?:/[A-Za-z0-9-]+)+")
SOURCED = "(lists a commencement or repeal)"
DATED = "(dates added for commencements)"
BOTH = "(lists a commencement or repeal; dates added for commencements)"
OLD = "(made before 1963)"


def _rec(log, lid, *, relations=0, by_other=0, commenced=0, repeals=0, words=0,
         qualified=0, dated=0, later=0, complete=True):
    """One change-record call as the two recorders write it (shape pinned by
    `test_the_helper_writes_what_the_recorders_write`)."""
    extra = {"later": later} if later else {}
    log.append({"tool": "change_record", "legislation_id": lid, "direction": "to",
                "relations": relations, "by_other": by_other, "others": [],
                "complete": complete, "dated": dated, **extra})
    log.append({"tool": "currency", "kind": "relations", "legislation_id": lid,
                "direction": "to", "relations": relations, "commenced": commenced, "orders": 0,
                "repeals": repeals, "words_only_removals": words,
                "qualified_removals": qualified, "commenced_by_other": commenced,
                "commenced_self": 0, "commenced_listed_in_full": True,
                "dated": dated, **extra})
    return log


def _sourced(log, lid, **kw):
    return _rec(log, lid, relations=4, by_other=4, commenced=4, **kw)


def _empty(log, lid):
    return _rec(log, lid)


def _row(effect, changed="ssi/2001/1", affecting="ssi/2001/9"):
    return [{
        "changed_legislation": changed, "changed_provision": "reg. 2",
        "changed_url": f"{scheme}://www.legislation.gov.uk/id/{changed}",
        "affecting_legislation": affecting, "affecting_provision": "reg. 3",
        "affecting_url": f"{scheme}://www.legislation.gov.uk/id/{affecting}",
        "type_of_effect": effect, "id": f"{scheme}-{effect}",
    } for scheme in ("http", "https")]


def _consulted(*records):
    """Through the product's own recorders, as `run_worker_tool` calls them."""
    log = []
    for lid, rows in records:
        slim = _slim_amendment_results(rows, lid, "to")
        record_relations(log, "get_legislation_changes", {"legislation_id": lid}, slim)
        record_currency(log, "get_legislation_changes", {"legislation_id": lid}, slim)
    return log


def _lists(text):
    """Every change-record list a footer has ever named, by its introducer."""
    out = []
    for rx in (r"recorded changes for (.+?), which this research consulted directly",
               r"what was checked is the recorded changes for (.+?), which name",
               r"for the commencements of (.+?) made by another instrument",
               r"made before 1963 \((.+?)\), so whether"):
        for m in re.finditer(rx, text):
            out.append(tuple(ID.findall(m.group(1))))
    return [x for x in out if x]


def _clauses(log):
    return _relations_footer_clause(log) + _currency_footer_clause(log)


def test_the_helper_writes_what_the_recorders_write():
    log = _consulted(("ssi/2001/1", _row("coming into force")))
    mine = _sourced([], "ssi/2001/1")
    for want, got in zip(log, mine):
        assert set(want) == set(got), (want, got)


# --- the defect --------------------------------------------------------------

def test_the_footer_names_one_list_where_it_named_two():
    """Thomas's case: the records consulted, and a subset that held a
    commencement or repeal, named twice in two orders."""
    log = _consulted(("ssi/2019/4", []),
                     ("asp/2025/2", _row("coming into force", changed="asp/2025/2")),
                     ("asp/2018/9", _row("repealed", changed="asp/2018/9")))
    clauses = _clauses(log)
    assert _lists(clauses) == [("ssi/2019/4", "asp/2025/2", "asp/2018/9")]
    for lid in ("ssi/2019/4", "asp/2025/2", "asp/2018/9"):
        assert clauses.count(lid) == 1, lid
    assert (f"recorded changes for ssi/2019/4, asp/2025/2 {SOURCED}, asp/2018/9 "
            f"{SOURCED}, which this research consulted directly") in clauses
    cur = _currency_footer_clause(log)
    assert ("what was checked is the recorded changes marked above as listing a "
            "commencement or repeal, which name the instruments involved provision "
            "by provision but carry no dates.") in cur
    assert not ID.search(cur)


def test_one_record_carries_no_mark_and_is_named_once():
    log = _consulted(("asp/2025/2", _row("coming into force", changed="asp/2025/2")))
    assert _clauses(log).count("asp/2025/2") == 1
    assert "(lists" not in _clauses(log)
    assert ("; what was checked is those recorded changes, which name the instruments "
            "involved provision by provision but carry no dates.") in _currency_footer_clause(log)


def test_all_records_sourced_need_no_mark():
    log = _sourced(_sourced([], "asp/2025/2"), "asp/2018/9")
    assert "recorded changes for asp/2025/2, asp/2018/9, which" in _relations_footer_clause(log)
    assert "what was checked is those recorded changes" in _currency_footer_clause(log)


def test_the_list_keeps_the_order_consulted_not_sorted():
    log = _sourced(_empty([], "ssi/2024/9"), "asp/2001/1")
    assert f"for ssi/2024/9, asp/2001/1 {SOURCED}, which" in _relations_footer_clause(log)


def test_no_mark_where_no_record_holds_a_commencement_or_repeal():
    log = _empty(_empty([], "ssi/2001/1"), "ssi/2001/2")
    rel, cur = _relations_footer_clause(log), _currency_footer_clause(log)
    assert "for ssi/2001/1, ssi/2001/2, which" in rel and "(" not in rel.split("which")[0]
    # P4.18's sentence, unchanged.
    assert cur.endswith("; the recorded changes consulted list neither a commencement "
                        "nor a repeal, so they do not answer that question either.")


# --- more than three, more than eight ------------------------------------------

def test_a_record_holding_a_commencement_past_the_third_is_named():
    """The old lead cut at three, so a sourced fourth record was named only in
    P2.5's second list. It is now in the one list, marked."""
    log = []
    for i in range(1, 4):
        _empty(log, f"ssi/2020/{i}")
    _sourced(log, "asp/2020/4")
    rel = _relations_footer_clause(log)
    assert f"ssi/2020/3, asp/2020/4 {SOURCED}, which" in rel


def test_past_eight_the_rest_are_counted_with_their_marks():
    log = []
    for i in range(1, 12):
        if i in (2, 10, 11):
            _sourced(log, f"ssi/2020/{i}")
        else:
            _empty(log, f"ssi/2020/{i}")
    rel = _relations_footer_clause(log)
    assert ("ssi/2020/8 and 3 more (2 of them listing a commencement or repeal), "
            "which this research consulted directly") in rel
    assert "ssi/2020/9" not in rel
    assert f"ssi/2020/2 {SOURCED}" in rel


def test_past_eight_all_sourced_is_a_plain_count():
    log = []
    for i in range(1, 11):
        _sourced(log, f"ssi/2020/{i}")
    rel = _relations_footer_clause(log)
    assert "ssi/2020/8 and 2 more, which this research" in rel
    assert "those recorded changes" in _currency_footer_clause(log)


# --- the dated branch (P3.21) and the still-to-come phrase (P3.54) -------------

def test_one_dated_record_points_at_its_own_commencements():
    log = _sourced([], "asp/2025/2", dated=2)
    cur = _currency_footer_clause(log)
    assert cur == (
        " Whether legislation is in force is not something this index reports; what "
        "was checked is those recorded changes, which name the instruments involved "
        "provision by provision, and, for their commencements made by another "
        "instrument, the date legislation.gov.uk's Changes to Legislation record "
        "gives for each. Neither is a check of whether a provision has since been "
        "amended or repealed.")
    assert _clauses(log).count("asp/2025/2") == 1


def test_some_dated_records_are_marked_and_pointed_at():
    log = _empty(_sourced(_sourced([], "asp/2025/2", dated=2), "asp/2018/9"), "ssi/2019/4")
    rel, cur = _relations_footer_clause(log), _currency_footer_clause(log)
    assert f"for asp/2025/2 {BOTH}, asp/2018/9 {SOURCED}, ssi/2019/4, which" in rel
    assert ("what was checked is the recorded changes marked above as listing a "
            "commencement or repeal, which name the instruments involved provision by "
            "provision, and, for the commencements made by another instrument in those "
            "marked above as having dates added for commencements, the date") in cur
    assert _lists(rel + cur) == [("asp/2025/2", "asp/2018/9", "ssi/2019/4")]


def test_every_sourced_record_dated_marks_only_the_sourced():
    log = _empty(_sourced([], "asp/2025/2", dated=1), "ssi/2019/4")
    rel = _relations_footer_clause(log)
    assert f"asp/2025/2 {BOTH}, ssi/2019/4, which" in rel


def test_the_still_to_come_phrase_is_kept():
    log = _sourced([], "ssi/2026/274", dated=1, later=1)
    rel = _relations_footer_clause(log)
    assert ("or, for a date after today, when it is due to come into force, "
            "not whether it has been amended or repealed since") in rel
    assert rel.count("ssi/2026/274") == 1


# --- P3.49, made before 1963 ----------------------------------------------------

def test_pre_1963_alone_is_its_own_one_list_unchanged():
    log = _empty(_empty([], "ukpga/1950/28"), "ukpga/Geo6/14/28")
    assert _relations_footer_clause(log) == (
        " The index used holds no record of changes to legislation made before 1963 "
        "(ukpga/1950/28, ukpga/Geo6/14/28), so whether they have been amended or "
        "repealed since is not known from this research; check the revised text on "
        "legislation.gov.uk before relying on them.")


def test_pre_1963_beside_a_modern_record_is_marked_not_listed_again():
    log = _empty(_empty(_sourced([], "asp/2025/2"), "ukpga/1950/28"), "ukpga/Geo6/14/28")
    rel = _relations_footer_clause(log)
    assert (f"for asp/2025/2 {SOURCED}, ukpga/1950/28 {OLD}, ukpga/Geo6/14/28 {OLD}, "
            "which this research consulted directly") in rel
    assert rel.endswith(
        " The index used holds no record of changes to legislation made before 1963, "
        "so whether those marked above as made before 1963 have been amended or "
        "repealed since is not known from this research; check the revised text on "
        "legislation.gov.uk before relying on them.")
    assert len(_lists(rel + _currency_footer_clause(log))) == 1


def test_pre_1963_past_the_cap_is_counted():
    log = []
    for i in range(1, 9):
        _sourced(log, f"asp/2020/{i}")
    _empty(log, "ukpga/1950/28")
    rel = _relations_footer_clause(log)
    assert "and 1 more (1 of them made before 1963)" in rel
    assert "the one marked above as made before 1963 has" in rel


# --- P3.28's removal classes ----------------------------------------------------

@pytest.mark.parametrize("kw", [{"repeals": 1}, {"words": 2}, {"qualified": 1}],
                         ids=["provision", "words only", "qualified"])
def test_every_removal_class_is_marked_as_listing_a_repeal(kw):
    log = _empty(_rec([], "asp/2025/2", relations=2, by_other=2, **kw), "ssi/2001/1")
    assert f"asp/2025/2 {SOURCED}, ssi/2001/1, which" in _relations_footer_clause(log)
    assert "neither a commencement nor a repeal" not in _currency_footer_clause(log)


def test_a_power_conferred_is_not_marked():
    log = _consulted(("asp/2025/2", _row("power to repeal conferred", changed="asp/2025/2")),
                     ("ssi/2001/1", []))
    assert "(lists" not in _relations_footer_clause(log)
    assert "neither a commencement nor a repeal" in _currency_footer_clause(log)


# --- no change-record entry: the currency clause names its own (fallback) -------

def test_without_a_change_record_entry_the_currency_clause_names_its_list():
    log = [{"tool": "currency", "kind": "relations", "legislation_id": "ssi/1901/3",
            "commenced": 1, "repeals": 0, "dated": 0}]
    assert _relations_footer_clause(log) == ""
    assert ("what was checked is the recorded changes for ssi/1901/3, which name the "
            "instruments involved") in _currency_footer_clause(log)


def test_without_a_change_record_entry_dated_records_are_marked_not_listed_again():
    log = [{"tool": "currency", "kind": "relations", "legislation_id": lid,
            "commenced": 1, "repeals": 0, "dated": d}
           for lid, d in (("ssi/1901/3", 1), ("ssi/1901/4", 0))]
    cur = _currency_footer_clause(log)
    assert f"recorded changes for ssi/1901/3 {DATED}, ssi/1901/4, which" in cur
    assert "in those marked as having dates added for commencements" in cur
    assert len(_lists(cur)) == 1


# --- at every footer that carries the clauses -------------------------------------

def _mixed_log():
    log = []
    _sourced(log, "asp/2025/2", dated=2)
    _empty(log, "ssi/2019/4")
    _rec(log, "asp/2018/9", relations=2, by_other=2, repeals=2)
    _empty(log, "ukpga/1950/28")
    for i in range(1, 7):
        (_sourced if i % 2 else _empty)(log, f"ssi/2021/{i}")
    return log


def test_every_footer_line_names_one_list():
    log = _mixed_log()
    searched = list(log)
    record_search(searched, "search_legislation", {"query": "widget licence"},
                  {"results": [], "total": 0})
    fresh = answer_scope_footer(searched, {})
    history = [{"role": "user", "content": "q"},
               {"role": "assistant", "content": "A." + answer_scope_footer(searched[-1:], {})}]
    carried = carried_scope_footer(history, log)
    sections = list(log)
    record_search(sections, "search_legislation_sections",
                  {"legislation_id": "asp/2025/2", "query": "licence"},
                  {"results": [{"title": "s. 1"}], "total": 1})
    section = section_scope_footer(sections)
    for line in (fresh, carried, section):
        assert "which this research consulted directly" in line, line
        assert len(_lists(line)) == 1, line
        clause_part = line[line.index(" Commencement and amendment"):]
        clause_part = clause_part[:clause_part.index("Neither is a check")]
        for lid in ("asp/2025/2", "ssi/2019/4", "asp/2018/9", "ukpga/1950/28"):
            assert clause_part.count(lid) == 1, (lid, line)


def test_the_constants_say_what_the_clauses_point_at():
    """The mark and the phrase pointing at it are one constant each, so a mark
    reworded cannot leave a clause pointing at a mark the list no longer has."""
    assert set(ss._MARK_AS) == {ss._MARK_SOURCED, ss._MARK_DATED, ss._MARK_OLD}
    log = _mixed_log()
    rel, cur = _relations_footer_clause(log), _currency_footer_clause(log)
    for mark in (ss._MARK_SOURCED, ss._MARK_DATED, ss._MARK_OLD):
        assert f"({mark}" in rel or f"; {mark})" in rel, mark
    assert f"marked above as {ss._MARK_AS[ss._MARK_SOURCED]}" in cur
    assert f"marked above as {ss._MARK_AS[ss._MARK_DATED]}" in cur
    assert f"marked above as {ss._MARK_AS[ss._MARK_OLD]}" in rel


def test_a_record_only_the_currency_entry_carries_is_in_the_one_list():
    """No stored turn has one, but a change-record result whose relation count
    was not an int writes a currency entry and no change-record entry. Its id
    joins the one list, so the currency clause never points at a mark the list
    lacks, nor names a second list."""
    log = _empty([], "ssi/2001/1")
    log.append({"tool": "currency", "kind": "relations", "legislation_id": "asp/2001/2",
                "commenced": 2, "repeals": 0, "dated": 0})
    clauses = _clauses(log)
    assert f"for ssi/2001/1, asp/2001/2 {SOURCED}, which" in clauses
    assert _lists(clauses) == [("ssi/2001/1", "asp/2001/2")]
