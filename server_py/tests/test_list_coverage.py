"""FIX_PLAN P3.53: a question about which of a listed set has a property.

6383 t1 asks which of the 37 instruments made under s.95 contain '£'; the
quick-lookup Worker searched 2-8 of them and the answer sampled, read as
complete, or said the rest were "highly likely" to contain it. Pins: the gate
(a made-under list of 5 or more, section searches with one query over 3 or
more of its instruments), the Worker's scope-block line in both branches, the
Deep Research note (computed over every step, absent from each step's block),
the footer sentence, the made-under block's note, byte-identical output when
the gate does not fire, the strip, and every detector that reads answers.
Synthetic ids ("Widget (Scotland) Act 1901", `ssi/1901/N`).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import made_under_store as store  # noqa: E402
from src.utils import made_under as mu  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402

COV = store.coverage({"label": "Scottish statutory instruments made from 1901 to 1905",
                      "harvested_at": "1906-01-01"}, None, 0)


def _found(n):
    rows = [(f"ssi/1901/{i}", f"The Widget Regulations 1901 No. {i}",
             "Widget (Scotland) Act 1901", "asp/1901/1", "power") for i in range(1, n + 1)]
    return store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV)


def _log(n=10, searched=(1, 2, 3, 4), query="£"):
    log = []
    ss.record_made_under(log, json.dumps(_found(n)))
    for i in searched:
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"ssi/1901/{i}", "query": query},
                         {"results": [{"url": "x"}]})
    return log


def _without_ids(log):
    """The log as P3.53's gate cannot read it: the output before this row."""
    out = [dict(e) for e in log]
    for e in out:
        e.pop("ids", None)
    return out


# --- the gate -----------------------------------------------------------------

def test_fires_on_a_list_of_five_searched_three_times_with_one_query():
    cov = ss.list_coverage(_log(5, (1, 2, 3)))
    assert cov == {"N": 5, "M": 3, "query": "£", "unsearched": ["ssi/1901/4", "ssi/1901/5"]}


@pytest.mark.parametrize("n,searched", [(4, (1, 2, 3, 4)), (10, (1, 2)), (10, ())])
def test_does_not_fire_below_the_gate(n, searched):
    assert ss.list_coverage(_log(n, searched)) is None


def test_different_queries_are_not_pooled():
    log = _log(10, (1, 2))
    ss.record_search(log, "search_legislation_sections",
                     {"legislation_id": "ssi/1901/3", "query": "penalty"}, {"results": []})
    assert ss.list_coverage(log) is None


def test_quotes_case_and_spacing_do_not_split_one_query():
    log = _log(10, (1,), query="'£'")
    for i, q in ((2, '"£"'), (3, " £ ")):
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"ssi/1901/{i}", "query": q}, {"results": []})
    assert ss.list_coverage(log)["M"] == 3


def test_searches_outside_the_list_do_not_count():
    log = _log(10, (1, 2))
    ss.record_search(log, "search_legislation_sections",
                     {"legislation_id": "ssi/1999/1", "query": "£"}, {"results": []})
    assert ss.list_coverage(log) is None


def test_a_section_family_entry_is_not_a_list():
    """P3.51's entries are `made_under` entries too, but no list the Worker was handed."""
    log = [{"tool": "made_under", "source": mu.SECTION_FAMILY_SOURCE, "status": "found",
            "named": [(f"ssi/1901/{i}", "T") for i in range(1, 10)]}]
    for i in (1, 2, 3):
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"ssi/1901/{i}", "query": "£"}, {"results": []})
    assert ss.list_coverage(log) is None


def test_full_urls_match_bare_ids():
    log = _log(6, ())
    for i in (1, 2, 3):
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"https://www.legislation.gov.uk/id/ssi/1901/{i}",
                          "query": "£"}, {"results": []})
    assert ss.list_coverage(log)["M"] == 3


# --- the Worker's scope block --------------------------------------------------

def test_some_not_searched():
    block = ss.worker_scope_block(_log(10, (1, 2, 3, 4)), {})
    assert ("List coverage: the made-under record listed 10 instruments, and this step searched "
            '4 of them for "£". The other 6 were NOT searched for it (ssi/1901/5, ssi/1901/6, '
            "ssi/1901/7, ssi/1901/8, ssi/1901/9, ssi/1901/10). If the answer says which of the "
            'listed instruments contain or match "£", it MUST say that 6 of the 10 were not '
            "checked, and say nothing of what those 6 contain.") in block


def test_all_searched():
    block = ss.worker_scope_block(_log(6, range(1, 7)), {})
    assert ("List coverage: the made-under record listed 6 instruments, and this step searched "
            'every one of them for "£". If the answer names those in which it was found, it MUST '
            'also say that the other listed instruments were searched and "£" was not found in '
            "the text returned.") in block


def test_the_unsearched_ids_are_capped():
    block = ss.worker_scope_block(_log(37, (1, 2, 3)), {})
    assert "The other 34 were NOT searched for it (ssi/1901/4, " in block
    assert "ssi/1901/11 and 26 more)" in block


@pytest.mark.parametrize("n,searched", [(4, (1, 2, 3, 4)), (10, (1, 2)), (10, ())])
def test_byte_identical_when_the_gate_does_not_fire(n, searched):
    log = _log(n, searched)
    assert ss.worker_scope_block(log, {}) == ss.worker_scope_block(_without_ids(log), {})
    assert "List coverage" not in ss.worker_scope_block(log, {})
    for f in (ss.answer_scope_footer, ss.section_scope_footer):
        assert f(log) == f(_without_ids(log))


def test_the_line_never_reaches_the_lawyer():
    report = "The answer." + ss.worker_scope_block(_log(10, (1, 2, 3)), {})
    text, n = ss.strip_scope_blocks(report)
    assert text.strip() == "The answer." and n >= 1


# --- Deep Research --------------------------------------------------------------

def test_deep_research_steps_carry_no_line():
    """A step may search what an earlier step listed (6382, wave5_p17: step 1 searched all 37,
    step 2 the 19 found): a per-step line would tell the synthesis 18 were not searched."""
    block = ss.worker_scope_block(_log(10, (1, 2, 3)), {"_chat_mode": "deep_research"})
    assert "List coverage" not in block


def test_the_synthesis_gets_one_note_over_every_step():
    step1 = _log(10, range(1, 11))
    step2 = _log(10, (1, 2, 3))
    note = ss.list_coverage_note(step1 + step2)
    assert note.startswith("\n\n[SEARCH SCOPE — list coverage, across every step: the made-under "
                           "record listed 10 instruments, and this research searched every one "
                           'of them for "£".')
    assert note.count("[") == 1 and note.count("]") == 1
    text, n = ss.strip_scope_blocks("The report." + note)
    assert text.strip() == "The report." and n == 1
    assert ss.list_coverage_note(_log(10, (1, 2))) == ""


def test_build_synthesis_messages_carries_the_note_only_when_given_the_searches():
    from src.agent.agent_core import build_synthesis_messages
    findings = [{"title": "t", "detail": "d", "content": "c"}]
    before = build_synthesis_messages("q", {}, findings, [], 1)
    assert build_synthesis_messages("q", {}, findings, [], 1, searches=[]) == before
    after = build_synthesis_messages("q", {}, findings, [], 1, searches=_log(10, (1, 2, 3)))
    assert after[1]["content"] == before[1]["content"] + ss.list_coverage_note(_log(10, (1, 2, 3)))


# --- the footer ------------------------------------------------------------------

def test_the_footer_says_how_many_were_not_checked():
    footer = ss.section_scope_footer(_log(37, (1, 2, 3, 4)))
    assert (' Of the 37 instruments the made-under record lists, 4 were searched for "£"; the '
            "other 33 were not checked.") in footer
    assert footer.count("\n") == 2          # still one line after the blank one


def test_the_footer_is_silent_when_every_one_was_searched():
    log = _log(6, range(1, 7))
    assert ss.section_scope_footer(log) == ss.section_scope_footer(_without_ids(log))


def test_the_footer_sentence_trips_no_detector():
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED,
        NEG_BLAMED_INDEX, NEG_BLAMED_USER, NOT_FOUND, _without_footer, derivation_claims,
    )
    text = ss._list_coverage_footer(_log(37, (1, 2, 3, 4)))
    assert text
    for rx in (NEG_ASSERTED, NEG_BLAMED_INDEX, NEG_BLAMED_USER, NOT_FOUND, HALT_LITERAL,
               HALT_PARAPHRASE, HALT_AS_TIMEOUT, IN_FORCE_CLAIM):
        assert not rx.search(text), rx.pattern[:60]
    assert derivation_claims(text)[0] == []
    answer = "The answer." + ss.section_scope_footer(_log(37, (1, 2, 3, 4)))
    assert _without_footer(answer).strip() == "The answer."


# --- the made-under block's note -------------------------------------------------

def test_the_block_asks_for_each_or_says_which_not():
    note = mu.made_under_note(json.dumps(_found(5)))
    assert (" 5 listed; if the question asks which of them have a property, search each or "
            "say which you did not.") in note
    assert note.count("[") == 1 and note.count("]") == 1


def test_the_block_is_unchanged_below_five():
    assert "have a property" not in mu.made_under_note(json.dumps(_found(4)))


# --- the grader -------------------------------------------------------------------

def _turn(n, searched, answer):
    tools = [{"name": "find_instruments_made_under", "args": {}, "raw_result": json.dumps(_found(n))}]
    tools += [{"name": "search_legislation_sections",
               "args": {"legislation_id": f"ssi/1901/{i}", "query": "£"}} for i in searched]
    return {"turn": 1, "answer": answer, "audit": {"delegations": [{"tools": tools}]}}


def test_listcov_grades_both_branches():
    from tools.replay_report import listcov_turn
    assert listcov_turn(_turn(10, (1, 2), "x")) is None
    assert listcov_turn(_turn(10, (1, 2, 3), "Three contain it."))["verdict"] == "FAIL"
    assert listcov_turn(_turn(10, (1, 2, 3), "Three contain it; the other 7 were not checked."
                              ))["verdict"] == "PASS"
    assert listcov_turn(_turn(10, (1, 2, 3), "Three contain it; the other 7 were not checked. "
                              "The rest are highly likely to contain it."))["verdict"] == "FAIL"
    assert listcov_turn(_turn(5, range(1, 6), "SSI 1901/1 contains it."))["verdict"] == "FAIL"
    assert listcov_turn(_turn(5, range(1, 6), "SSI 1901/1 contains it. The remaining 4 were "
                              "searched and do not contain it."))["verdict"] == "PASS"
