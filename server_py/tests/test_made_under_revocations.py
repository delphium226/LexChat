"""FIX_PLAN P3.33 at its seams: the made-under list says which instruments legislation.gov.uk
records as revoked, and nothing says any instrument is in force.

Pins: the snapshot row (the flag and the day checked), the tool result (a line per listed
instrument; counts over EVERY instrument found, so a cut list still counts the whole), the
CURRENCY block the Worker reads (permits a recorded revocation, forbids "in force" and a future
revocation stated as done; removed from what the lawyer reads), the Manager's limb and the
lawyer's footer clause, each screened against every detector that reads answers.
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
TODAY = "1906-06-01"
WHOLE = {"state": "wholly", "whole": [{"type": "revoked", "by": "ssi/1903/9", "date_source": "feed",
                                       "dates": [{"date": "1903-04-01", "qualification": "wholly in force"}]}]}
LATER = {"state": "wholly", "whole": [{"type": "revoked", "by": "ssi/1905/9", "date_source": "feed",
                                       "dates": [{"date": "1907-01-01", "qualification": "wholly in force"}]}]}
UNDATED = {"state": "wholly", "whole": [{"type": "rev", "by": "ssi/1902/9"}]}
PART = {"state": "partly", "partial": {"count": 3, "by": ["ssi/1904/2"], "by_count": 1}}


def _rows(flags, checked="1906-05-01"):
    return [(f"ssi/1901/{i}", f"The Widget Regulations 1901 No. {i}", "Widget (Scotland) Act 1901",
             "asp/1901/1", "power", json.dumps(f) if f else None, checked)
            for i, f in enumerate(flags, 1)]


def _result(flags, checked="1906-05-01"):
    return store.build_result("Widget (Scotland) Act 1901", "95", "section/95",
                              _rows(flags, checked), [], COV, today=TODAY)


# --- the snapshot row -------------------------------------------------------

def test_snapshot_row_carries_the_flag_and_the_day_checked():
    from datetime import date
    inst, _ = store._rows_for({"id": "ssi/1901/1", "title": "T", "revocation": WHOLE,
                               "revocation_checked": "1906-05-01"})
    assert json.loads(inst["revocation"]) == WHOLE
    assert inst["revocation_checked"] == date(1906, 5, 1)   # asyncpg wants a date, not a string
    inst, _ = store._rows_for({"id": "ssi/1901/2", "title": "T"})
    assert inst["revocation"] is None and inst["revocation_checked"] is None


# --- the tool result --------------------------------------------------------

def test_each_listed_instrument_says_what_is_recorded():
    d = _result([WHOLE, LATER, UNDATED, PART, None])
    lines = [i["revocation"] for i in d["instruments"]]
    assert lines == [
        "recorded as revoked in whole by ssi/1903/9, with effect from 1903-04-01",
        "recorded as revoked in whole by ssi/1905/9, with effect from 1907-01-01, a date still to come",
        'recorded as revoked in whole by ssi/1902/9, no date recorded (the record\'s words: "rev")',
        "recorded as revoked in part: 3 provisions revoked or omitted, by ssi/1904/2",
        "no revocation recorded",
    ]
    rv = d["revocations"]
    assert (rv["revoked"], rv["revoked_later"], rv["revoked_undated"], rv["partly"], rv["none"]) == (1, 1, 1, 1, 1)
    assert rv["checked"] == "1906-05-01"


def test_counts_cover_every_instrument_found_when_the_list_is_cut():
    d = _result([WHOLE] * (mu.MAX_LISTED + 5) + [None] * 3)
    assert len(d["instruments"]) == mu.MAX_LISTED and d["count"] == mu.MAX_LISTED + 8
    assert d["revocations"]["revoked"] == mu.MAX_LISTED + 5 and d["revocations"]["none"] == 3
    # still bounded (the result is never summarised)
    assert len(json.dumps(d)) < 16_000


def test_a_record_loaded_before_the_check_reads_as_not_checked():
    rows = [(f"ssi/1901/{i}", "T", "Widget (Scotland) Act 1901", None, "power") for i in (1, 2)]
    d = store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV, today=TODAY)
    assert [i["revocation"] for i in d["instruments"]] == ["not checked", "not checked"]
    assert d["revocations"]["unchecked"] == 2 and d["revocations"]["checked"] is None
    assert mu.revocation_note(d) == ""          # nothing checked, nothing said


# --- the block the Worker reads ----------------------------------------------

def test_the_currency_block_permits_a_recorded_revocation_and_forbids_in_force():
    note = mu.made_under_note(json.dumps(_result([WHOLE, LATER, UNDATED, PART, None])))
    assert "[ENABLING POWER" in note and "[CURRENCY — revocations as recorded on legislation.gov.uk" in note
    block = note[note.index("[CURRENCY"):]
    assert ("of the 5 instruments, 3 recorded as revoked in whole (1 with no date recorded; 1 with "
            "effect from a date still to come), 1 as revoked in part; for the other 1 no revocation "
            "is recorded") in block
    assert "You MAY state a recorded revocation" in block
    assert "do not say the instrument has been revoked" in block
    assert "NOT evidence that an instrument is in force" in block
    assert "never that it is in force, current or still has effect" in block
    assert block.count("[") == 1 and block.count("]") == 1      # strippable whole


def test_the_block_says_when_the_counts_cover_more_than_the_list():
    note = mu.made_under_note(json.dumps(_result([WHOLE] * (mu.MAX_LISTED + 2))))
    assert f"Only the {mu.MAX_LISTED} listed instruments carry a line; the counts cover all " \
           f"{mu.MAX_LISTED + 2}." in note


def test_the_block_never_reaches_the_lawyer():
    note = mu.made_under_note(json.dumps(_result([WHOLE, None])))
    text, n = ss.strip_scope_blocks("The answer." + note)
    assert text.strip() == "The answer." and n >= 2


def test_unchecked_instruments_are_named_as_such():
    rows = _rows([WHOLE, None]) + [("ssi/1905/7", "T", "Widget (Scotland) Act 1901", None, "power", None, None)]
    d = store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV, today=TODAY)
    assert "1 instrument was added to the record after the check and not checked" in mu.revocation_note(d)


# --- the Manager's limb and the lawyer's footer ------------------------------

def _log(flags):
    log = []
    ss.record_made_under(log, json.dumps(_result(flags)))
    return log


def test_the_limb_counts_and_carries_the_rule():
    limb = ss._made_under_limb(_log([WHOLE, LATER, PART, None]))
    assert ("4 instrument(s) whose own preamble names section 95 of the Widget (Scotland) Act 1901, "
            "of which legislation.gov.uk records 2 as revoked in whole (1 from a date still to come), "
            "1 as revoked in part (checked 1906-05-01)") in limb
    assert limb.endswith("A revocation is stated only as legislation.gov.uk records it; no revocation "
                         "recorded does not mean in force.")


def test_the_footer_names_the_day_checked():
    clause = ss._made_under_footer_clause(_log([WHOLE, None]))
    assert clause.endswith("Revocations of those instruments are as recorded on legislation.gov.uk on "
                           "1906-05-01; where none is recorded, that is not confirmation that an "
                           "instrument still has effect.")


def test_without_a_check_the_limb_and_footer_are_unchanged():
    rows = [(f"ssi/1901/{i}", "T", "Widget (Scotland) Act 1901", None, "power") for i in (1, 2)]
    log = []
    ss.record_made_under(log, json.dumps(store.build_result(
        "Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV)))
    assert "revoked" not in ss._made_under_limb(log)
    assert "Revocations" not in ss._made_under_footer_clause(log)


# --- every detector that reads answers ---------------------------------------

def _texts():
    d = _result([WHOLE, LATER, UNDATED, PART, None])
    note = mu.made_under_note(json.dumps(d))
    log = _log([WHOLE, LATER, PART, None])
    return {
        "block": note[note.index("[CURRENCY"):],
        "limb": ss._made_under_limb(log),
        "footer": ss._made_under_footer_clause(log),
        **{f"line{i}": x["revocation"] for i, x in enumerate(d["instruments"])},
    }


@pytest.mark.parametrize("name", ["limb", "footer", "line0", "line1", "line2", "line3", "line4"])
def test_no_detector_trips_on_text_a_lawyer_or_the_manager_can_read(name):
    """The footer reaches the lawyer; the limb and the lines can be echoed into an answer. None
    may be read by a grader as an in-force claim, a negative commencement or currency claim, a
    derivation, a not-found, or a halt."""
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED, NEG_BLAMED_INDEX,
        NEG_BLAMED_USER, NOT_FOUND, _CMC_CONTEXT, _CMC_DENIED, _currency_asserted, _sentences,
        derivation_claims, negcurrency_claim,
    )
    text = _texts()[name]
    assert text
    for rx in (NEG_ASSERTED, NEG_BLAMED_INDEX, NEG_BLAMED_USER, NOT_FOUND, HALT_LITERAL,
               HALT_PARAPHRASE, HALT_AS_TIMEOUT):
        assert not rx.search(text), (name, rx.pattern[:60])
    assert derivation_claims(text)[0] == []
    for s in _sentences(text):
        assert not _currency_asserted(s), s
        assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
        assert negcurrency_claim(s)[0] is None, s
    if name != "limb":
        assert not IN_FORCE_CLAIM.search(text), name


# --- the graders read the record ---------------------------------------------

def test_each_listed_instrument_carries_a_status_code():
    d = _result([WHOLE, LATER, UNDATED, PART, None])
    assert [i["revocation_status"] for i in d["instruments"]] == [
        "revoked", "revoked_later", "revoked_undated", "partly", "none"]
    rows = [("ssi/1901/1", "T", "Widget (Scotland) Act 1901", None, "power")]
    d = store.build_result("Widget (Scotland) Act 1901", "95", "section/95", rows, [], COV, today=TODAY)
    assert d["instruments"][0]["revocation_status"] == "unchecked"


def _negcurrency(answer, flags):
    from tools.replay_report import negcurrency_turn
    turn = {"turn": 1, "question": "q", "answer": answer, "audit": {"delegations": [{"tools": [
        {"name": "find_instruments_made_under", "args": {},
         "raw_result": json.dumps(_result(flags))}]}]}}
    claims, _ = negcurrency_turn(turn, None)
    assert len(claims) == 1, claims
    return claims[0][2]


def test_negcurrency_counts_a_recorded_whole_revocation_as_evidence():
    s = "SSI 1901/1 is no longer in force: it was revoked by SSI 1903/9."
    assert _negcurrency(s, [WHOLE]) == "SUPPORTED"
    assert _negcurrency(s, [None]) == "UNSUPPORTED"          # nothing recorded
    assert _negcurrency(s, [LATER]) == "UNSUPPORTED"         # dated after the day it ran
    assert _negcurrency(s, [PART]) == "UNSUPPORTED"          # only a partial removal
    assert _negcurrency("SSI 1901/1 remains in force.", [WHOLE]) == "UNSUPPORTED"


def test_madeunder_grade_reads_revocations_against_the_hand_checked_set():
    from tools import madeunder_grade as g
    body = ("- [SSI 2022/217](https://www.legislation.gov.uk/ssi/2022/217): revoked by "
            "[SSI 2024/311](https://www.legislation.gov.uk/ssi/2024/311) from 21 March 2025.\n"
            "- SSI 2021/73 is revoked in part (reg. 13).\n"
            "- The (Consequential Amendment, Revocation and Saving Provision) Regulations 2024 "
            "(SSI 2024/311) were made under section 95.\n"
            "- SSI 2025/100 has been revoked.\n"
            "- SSI 2020/99 remains in force.")
    r = g.revocation_grade(body, g.named_ids(body))
    assert r["whole_correct"] == ["ssi/2022/217"]
    assert r["part_correct"] == ["ssi/2021/73"]
    assert r["whole_wrong"] == ["ssi/2025/100"]                 # not recorded as revoked
    assert "ssi/2024/311" not in r["whole_wrong"]               # the revoker, and a title
    assert r["whole_missed"] == [] and len(r["in_force"]) == 1
    r = g.revocation_grade("SSI 2022/217 was made under section 95.", {"ssi/2022/217"})
    assert r["whole_missed"] == ["ssi/2022/217"]


def test_each_instrument_takes_its_feeds_check_date_from_the_manifest():
    recs = store.prepare_snapshot(
        [{"id": "ssi/1901/1"}, {"id": "uksi/1901/2"}, {"id": "uksi/1902/3"}],
        {"harvested_at": "1906-01-01", "revocations": {"checked": {"ssi": "1906-05-01",
                                                                    "uksi/1901": "1906-05-02"}}})
    assert [r["revocation_checked"] for r in recs] == ["1906-05-01", "1906-05-02", None]
    assert all(r["source"] == "snapshot" for r in recs)
    # a manifest from before P3.33: nothing checked
    assert store.prepare_snapshot([{"id": "ssi/1901/1"}], {})[0]["revocation_checked"] is None


def test_the_limb_says_nothing_of_revocation_without_a_check_date():
    assert ss._revocation_limb({"revoked": 3, "checked": None}) == ""
    assert ss._revocation_limb(None) == ""


def test_a_cut_list_leads_with_instruments_not_revoked_in_whole():
    flags = [WHOLE] * 30 + [None] * 15 + [LATER, PART]       # 47 found; ssi/1901/1-30 revoked
    d = _result(flags)
    ids = [i["legislation_id"] for i in d["instruments"]]
    assert len(ids) == mu.MAX_LISTED and d["listed_order"] == "not_wholly_revoked_first"
    # the 17 not revoked in whole (15 none, 1 from a date still to come, 1 in part) come first
    assert ids[:17] == [f"ssi/1901/{i}" for i in range(31, 48)]
    assert all(i["revocation_status"] == "revoked" for i in d["instruments"][17:])
    assert "The list leads with the instruments not recorded as revoked in whole, oldest first." \
        in mu.made_under_note(json.dumps(d))


def test_a_list_that_is_not_cut_keeps_its_order():
    d = _result([WHOLE, None, PART])
    assert [i["legislation_id"] for i in d["instruments"]] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3"]
    assert d["listed_order"] == "oldest_first"
    assert "The list leads" not in mu.made_under_note(json.dumps(d))


def test_madeunder_grade_reads_specific_provisions_as_partial():
    from tools import madeunder_grade as g
    body = ("*   Specific provisions within **SSI 2021/73**, **SSI 2021/174**, and **SSI 2022/54** have "
            "been revoked or omitted by subsequent legislation (e.g., SSI 2021/249, SSI 2025/336).")
    r = g.revocation_grade(body, g.named_ids(body))
    assert r["whole_wrong"] == [] and r["part_correct"] == ["ssi/2021/174", "ssi/2021/73", "ssi/2022/54"]


def test_the_block_asks_for_each_revocation_against_its_instrument():
    note = mu.made_under_note(json.dumps(_result([WHOLE, PART, None])))
    assert ("When you list or name any of these instruments, say against each one the record shows "
            "revoked, in whole or in part, what its line says.") in note


def test_a_turn_that_consulted_only_the_record_gets_its_clause_in_the_footer():
    """wave4_p333 6383 t3 (and wave4_p331's): the lookup-only branch had no made-under clause,
    and a turn with the record alone got no footer at all."""
    log = _log([WHOLE, None])
    footer = ss.lookup_scope_footer(log, [])
    assert footer.strip().startswith("*Search scope: no ranked search of the legislation index was run")
    assert "The record of enabling powers consulted here covers" in footer
    assert "Revocations of those instruments are as recorded on legislation.gov.uk on 1906-05-01" in footer


def test_no_detector_trips_on_the_lookup_only_footer():
    from tools.replay_report import (
        IN_FORCE_CLAIM, NEG_ASSERTED, NOT_FOUND, _CMC_CONTEXT, _CMC_DENIED, _currency_asserted,
        _sentences, derivation_claims, negcurrency_claim,
    )
    footer = ss.lookup_scope_footer(_log([WHOLE, None]), [])
    assert not NEG_ASSERTED.search(footer) and not NOT_FOUND.search(footer)
    assert not IN_FORCE_CLAIM.search(footer) and derivation_claims(footer)[0] == []
    for s in _sentences(footer):
        assert not _currency_asserted(s), s
        assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
        assert negcurrency_claim(s)[0] is None, s
