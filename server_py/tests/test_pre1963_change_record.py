"""P3.49: an empty change record for an instrument made before 1963.

LEX's `/amendment/search` holds no relation with a pre-1963 instrument on either
side (probed 2026-10-13, Session 47; 171 of 171 stored calls on a pre-1963 id
empty). So for such an instrument "no change is recorded" is not a negative of
any strength, and Thomas's Q8 (6341) relied on ss.38 and 39 of the Shops Act
1950, repealed, with no warning. Four code texts say so: the Worker's
change-record block, the Manager's limb, P3.24's per-instrument line and the
lawyer's footer. Each is tested here through the product's own recorders, and
each modern-instrument case is pinned unchanged.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.tools.lex import _slim_amendment_results
from src.utils.search_scope import (
    CHANGE_RECORD_FIRST_YEAR,
    _currency_limb,
    _relations_footer_clause,
    _relations_limb,
    amendment_search_note,
    answer_scope_footer,
    before_change_record,
    record_currency,
    record_relations,
    record_search,
    worker_scope_block,
)

SHOPS_1950 = "ukpga/Geo6/14/28"
MODERN = "asp/2001/7"


def _row(changed, affecting, effect="repealed"):
    return {
        "changed_legislation": changed, "changed_provision": "s. 3",
        "changed_url": f"http://www.legislation.gov.uk/id/{changed}",
        "affecting_legislation": affecting, "affecting_provision": "s. 9",
        "affecting_url": f"http://www.legislation.gov.uk/id/{affecting}",
        "type_of_effect": effect,
    }


def _slim(lid, rows=()):
    return _slim_amendment_results(list(rows), lid, "to")


def _log(*records):
    """A turn's record as `run_worker_tool` builds it on each change-record call."""
    log = []
    for lid, rows in records:
        slim = _slim(lid, rows)
        args = {"legislation_id": lid}
        record_relations(log, "get_legislation_changes", args, slim)
        record_currency(log, "get_legislation_changes", args, slim)
    return log


def _searched():
    log = []
    record_search(log, "search_legislation", {"query": "shop"},
                  {"results": [], "total": 0})
    return log


# --- which ids --------------------------------------------------------------

@pytest.mark.parametrize("lid", [
    SHOPS_1950, "ukpga/Vict/49-50/55", "ukpga/1-2Geo5/54", "ukpga/52-53Vict/52",
    "ukpga/Eliz2/10-11/46", "ukpga/1950/28", "ukpga/1962/46", "uksi/1961/1580",
    "aosp/1690/4", "ukpga/1934/42",
])
def test_pre_1963_ids(lid):
    assert before_change_record(lid)


@pytest.mark.parametrize("lid", [
    "ukpga/1963/41", "uksi/1966/94", "asp/2000/4", "ssi/2025/388",
    "eur/1958/1", "", None, "10 & 11 Geo. 5. c. 58", "Shops Act 1950",
])
def test_not_pre_1963_ids(lid):
    assert not before_change_record(lid)


def test_the_cut_off_is_1963():
    assert CHANGE_RECORD_FIRST_YEAR == 1963


# --- 1. the Worker's change-record block -------------------------------------

def test_block_for_an_empty_pre_1963_record_says_no_record_is_held():
    note = amendment_search_note({"legislation_id": SHOPS_1950}, _slim(SHOPS_1950))
    assert "holds no change record at all for legislation made before 1963" in note
    assert f"whether {SHOPS_1950} or any of its provisions has been amended, " \
           "repealed or revoked is NOT known" in note
    assert "Do not write that no change is recorded" in note
    assert ("whether that provision has since been amended or repealed could not "
            "be checked in this index") in note
    # Not the modern branch's wording, and not the text index's coverage
    # sentence, whose "rather than by date" would contradict it.
    assert "relation is recorded for" not in note
    assert "rather than by date" not in note


def test_block_for_an_empty_modern_record_is_unchanged():
    note = amendment_search_note({"legislation_id": MODERN}, _slim(MODERN))
    assert "relation is recorded for asp/2001/7 in this direction" in note
    assert "before 1963" not in note


def test_block_for_a_pre_1963_record_with_rows_is_the_ordinary_one():
    """Gated on the record being empty: if LEX adds the data, the wording retires."""
    note = amendment_search_note(
        {"legislation_id": SHOPS_1950},
        _slim(SHOPS_1950, [_row(SHOPS_1950, "ukpga/1994/20")]))
    assert "recorded relation(s) for ukpga/Geo6/14/28" in note
    assert "before 1963" not in note


# --- 2. the Manager's limb ---------------------------------------------------

def test_limb_names_the_pre_1963_instrument_and_drops_the_no_relation_line():
    limb = _relations_limb(_log((SHOPS_1950, [])))
    assert f"{SHOPS_1950} was made before 1963" in limb
    assert "says nothing about whether it has been amended, repealed or revoked" in limb
    assert "Do not report it as no change being recorded" in limb
    assert ("whether that provision has since been amended or repealed could not "
            "be checked here") in limb
    assert "NO relation is recorded" not in limb


def test_limb_keeps_the_two_cases_apart():
    limb = _relations_limb(_log((SHOPS_1950, []), (MODERN, [])))
    assert f"NO relation is recorded for {MODERN}." in limb
    assert f"{SHOPS_1950} was made before 1963" in limb
    assert f"NO relation is recorded for {SHOPS_1950}" not in limb


def test_limb_for_two_pre_1963_instruments_is_plural():
    limb = _relations_limb(_log((SHOPS_1950, []), ("ukpga/1950/28", [])))
    assert f"{SHOPS_1950}, ukpga/1950/28 were made before 1963" in limb
    assert "whether they have been amended" in limb


def test_limb_for_a_modern_empty_record_is_unchanged():
    limb = _relations_limb(_log((MODERN, [])))
    assert "NO relation is recorded for asp/2001/7" in limb
    assert "before 1963" not in limb


def test_limb_reaches_the_worker_scope_block():
    log = _searched() + _log((SHOPS_1950, []))
    assert f"{SHOPS_1950} was made before 1963" in worker_scope_block(log)


# --- 3. P3.24's per-instrument line ------------------------------------------

def test_commencement_line_for_an_empty_pre_1963_record():
    limb = _currency_limb(_log((SHOPS_1950, [])))
    assert (f"- {SHOPS_1950}: made before 1963, for which the index holds no change "
            "record: do not state from it whether any of its provisions has been "
            "commenced, amended, repealed or revoked.") in limb
    assert f"{SHOPS_1950}: the record lists neither" not in limb


def test_commencement_line_for_a_modern_empty_record_is_unchanged():
    limb = _currency_limb(_log((MODERN, [])))
    assert f"- {MODERN}: the record lists neither a commencement" in limb


def test_commencement_line_for_a_pre_1963_record_with_rows_is_the_ordinary_one():
    limb = _currency_limb(_log((SHOPS_1950, [_row(SHOPS_1950, "ukpga/1994/20")])))
    assert f"{SHOPS_1950}: the record lists neither" in limb
    assert "made before 1963" not in limb


# --- 4. the lawyer's footer --------------------------------------------------

def test_footer_for_a_pre_1963_record_alone():
    clause = _relations_footer_clause(_log((SHOPS_1950, [])))
    assert clause == (
        " The index used holds no record of changes to legislation made before "
        f"1963 ({SHOPS_1950}), so whether it has been amended or repealed since is "
        "not known from this research; check the revised text on "
        "legislation.gov.uk before relying on it."
    )


def test_footer_mixed_keeps_the_consulted_lead_and_adds_the_clause():
    clause = _relations_footer_clause(_log((MODERN, []), (SHOPS_1950, []),
                                           ("ukpga/1950/28", [])))
    assert clause.startswith(" Commencement and amendment relations above come from")
    assert "An empty change record means the change is not recorded" in clause
    assert clause.endswith(
        f"before 1963 ({SHOPS_1950}, ukpga/1950/28), so whether they have been "
        "amended or repealed since is not known from this research; check the "
        "revised text on legislation.gov.uk before relying on them.")


def test_footer_names_every_pre_1963_instrument_up_to_eight_then_counts():
    """The acceptance's rep 2: six pre-1963 records, and a cap of three left
    out the Shops Act 1950, the Act the question was about."""
    six = ["ukpga/1-2Geo5/54", "ukpga/1934/42", "ukpga/1912/3", SHOPS_1950,
           "ukpga/1951/38", "uksi/1960/2014"]
    clause = _relations_footer_clause(_log(*[(lid, []) for lid in six]))
    assert f"({', '.join(six)})" in clause
    ten = [f"ukpga/19{40 + i}/{i + 1}" for i in range(10)]
    clause = _relations_footer_clause(_log(*[(lid, []) for lid in ten]))
    assert f"({', '.join(ten[:8])} and 2 more)" in clause


def test_footer_for_a_modern_empty_record_is_unchanged():
    clause = _relations_footer_clause(_log((MODERN, [])))
    assert "before 1963" not in clause
    assert "An empty change record means the change is not recorded" in clause


def test_footer_reaches_the_answer():
    log = _searched() + _log((SHOPS_1950, []))
    footer = answer_scope_footer(log, {})
    assert "holds no record of changes to legislation made before 1963" in footer


# --- the new texts trip no detector that reads these answers -----------------

def test_new_texts_trip_no_detector():
    from tools.replay_report import (
        IN_FORCE_CLAIM, NEG_ASSERTED, _CMC_CONTEXT, _CMC_DENIED, _CUR_DISCLOSED,
        _currency_asserted, _sentences, derivation_claims, negcurrency_claim,
    )
    log = _log((SHOPS_1950, []), ("ukpga/1950/28", []))
    footer_clause = _relations_footer_clause(_log((SHOPS_1950, [])))
    texts = {
        "footer": footer_clause,
        "footer plural": _relations_footer_clause(log),
        # A Worker can echo the block, and a Manager the limb and the line.
        "block": amendment_search_note({"legislation_id": SHOPS_1950}, _slim(SHOPS_1950)),
        "limb": _relations_limb(log),
        "line": _currency_limb(_log((SHOPS_1950, []))),
    }
    for name, text in texts.items():
        assert "before 1963" in text, name
        new = text[text.index("before 1963") - 120:]
        assert not NEG_ASSERTED.search(new), name
        assert derivation_claims(new)[0] == [], name
        for s in _sentences(new):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), (name, s)
            assert not _currency_asserted(s), (name, s)
            assert negcurrency_claim(s)[0] is None, (name, s)
    for clause in (texts["footer"], texts["footer plural"]):
        assert not IN_FORCE_CLAIM.search(clause)
        assert not _CUR_DISCLOSED.search(clause)
