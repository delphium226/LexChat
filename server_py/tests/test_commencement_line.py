"""P3.24 (bucket B3): the per-instrument commencement line in the report block.

Thomas's retest of `v2026.09.3` (30 September 2026, `glm-5.2:cloud`) listed
provisions as "Not yet commenced" where the research found only that no
commencement was recorded. A change record that lists no commencement is not
evidence that none was made. The lever decided by the user (2026-10-05) is a
line in `_currency_limb`, one per instrument whose change record the step
consulted, computed from the record:

* commencement relations made by ANOTHER instrument, all listed: a provision
  not among them may be called "not recorded as commenced" (the true negative
  Invariant 1 keeps stateable);
* such relations, not all listed: only the listed ones may be stated;
* only the instrument's own commencement provision acting on itself (batch 6
  B's F3), none at all, or a count with no list: neither, from that record;
* a record of the changes it makes to OTHER legislation: nothing about its own;

and, for an instrument whose record was not consulted, neither. Plus one
sentence beside `_IN_FORCE_RULE` (`_COMMENCEMENT_RECORD_RULE`).

Synthetic instruments only ("Widget" Acts of 1901).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.tools.lex import _slim_amendment_results
from src.utils.search_scope import (
    _currency_limb,
    record_currency,
    record_relations,
    record_search,
    worker_scope_block,
)

_ACT = "asp/1901/1"
_ORDER = "ssi/1901/3"


def _row(changed_prov, affecting, effect, changed=_ACT, affecting_prov="reg. 2"):
    """One `/amendment/search` relation, as both scheme twins (as the feed sends)."""
    return [{
        "changed_legislation": changed, "changed_provision": changed_prov,
        "changed_url": f"{scheme}://www.legislation.gov.uk/id/{changed}",
        "affecting_legislation": affecting, "affecting_provision": affecting_prov,
        "affecting_url": f"{scheme}://www.legislation.gov.uk/id/{affecting}",
        "type_of_effect": effect, "id": f"{scheme}-{changed_prov}-{affecting}-{effect}",
    } for scheme in ("http", "https")]


def _rows(*specs, changed=_ACT):
    out = []
    for prov, affecting, effect in specs:
        out += _row(prov, affecting, effect, changed=changed)
    return out


def _log(*records, search=True):
    """A step's record as `run_worker_tool` builds it: a search, then P3.5's and
    P2.5's recorders on each change-record call (slimmed by the product)."""
    log = []
    if search:
        record_search(log, "search_legislation", {"query": "widgets"},
                      {"results": [], "total": 0})
    for lid, rows, direction in records:
        slim = _slim_amendment_results(rows, lid, direction)
        args = {"legislation_id": lid, "direction": direction}
        record_relations(log, "get_legislation_changes", args, slim)
        record_currency(log, "get_legislation_changes", args, slim)
    return log


def _currency_entry(log):
    rows = [e for e in log if e.get("tool") == "currency" and e.get("kind") == "relations"]
    assert len(rows) == 1
    return rows[0]


# --- the recorder ----------------------------------------------------------

def test_the_recorder_counts_commencements_by_another_instrument_apart_from_self():
    """The field the line needs, recorded from the RAW (pre-summarisation)
    result. `provisions_commenced` counts the instrument's own relations too
    (F3), so it cannot be what the line reads."""
    rows = _rows(("s. 1", _ORDER, "coming into force"),
                 ("s. 2", _ORDER, "coming into force"),
                 ("s. 3", _ACT, "coming into force"),
                 ("s. 4", _ACT, "coming into force"),
                 ("s. 5", _ACT, "coming into force"),
                 ("s. 6", "asp/1901/9", "words substituted"))
    e = _currency_entry(_log((_ACT, rows, "to")))
    assert e["commenced"] == 5                  # P2.5's count, unchanged
    assert e["commenced_by_other"] == 2
    assert e["commenced_self"] == 3
    assert e["commenced_listed_in_full"] is True
    assert e["direction"] == "to"


def test_the_recorder_marks_a_cut_list_as_not_listed_in_full():
    """61 provisions commenced by one order: the slimmer lists 60 and counts
    the rest (`changes_not_listed`), so a provision not shown may be among
    them."""
    rows = _rows(*[(f"s. {i}", _ORDER, "coming into force") for i in range(1, 62)])
    e = _currency_entry(_log((_ACT, rows, "to")))
    assert e["commenced_by_other"] == 61
    assert e["commenced_listed_in_full"] is False


def test_the_recorder_reads_the_older_stored_shape_too():
    """Stored results predate P3.19's `changes`; a rebuild over them must read
    their cut marker and, before P2.5, derive the total from `effects`."""
    old = {"legislation_id": _ACT, "direction": "to", "relations": 3,
           "effects": {"coming into force": 3},
           "related": [{"legislation_id": _ORDER, "self": False,
                        "type_of_effect": "coming into force", "count": 3,
                        "changed_provisions": ["s. 1"],
                        "changed_provisions_not_listed": 2}]}
    log = []
    record_currency(log, "get_legislation_changes", {"legislation_id": _ACT}, old)
    e = _currency_entry(log)
    assert e["commenced_by_other"] == 3 and e["commenced_listed_in_full"] is False
    old["related"][0].pop("changed_provisions_not_listed")
    log = []
    record_currency(log, "get_legislation_changes", {"legislation_id": _ACT}, old)
    assert _currency_entry(log)["commenced_listed_in_full"] is True


def test_groups_beyond_the_instrument_cap_leave_the_list_incomplete():
    """A record whose commencement groups were cut at `_MAX_RELATED_INSTRUMENTS`
    holds more commencement relations than it lists."""
    d = {"legislation_id": _ACT, "direction": "to", "relations": 9,
         "provisions_commenced": 9, "related": [
             {"legislation_id": _ORDER, "self": False,
              "type_of_effect": "coming into force", "count": 4}]}
    log = []
    record_currency(log, "get_legislation_changes", {"legislation_id": _ACT}, d)
    e = _currency_entry(log)
    assert e["commenced_by_other"] == 4 and e["commenced_listed_in_full"] is False


# --- the line's cases --------------------------------------------------------

def test_commencement_by_another_instrument_permits_not_recorded_as_commenced():
    """Invariant 1: the true negative stays stateable, with its source."""
    limb = _currency_limb(_log((_ACT, _rows(("s. 1", _ORDER, "coming into force"),
                                            ("s. 2", _ORDER, "coming into force")), "to")))
    assert (f"{_ACT}: 2 commencement relation(s) made by another instrument, all "
            "listed") in limb
    assert "may be called not recorded as commenced, citing this record" in limb
    # P2.5's sentence is gone: it was the one that counted self relations.
    assert "WERE retrieved" not in limb


def test_a_cut_list_permits_only_what_it_lists():
    rows = _rows(*[(f"s. {i}", _ORDER, "coming into force") for i in range(1, 62)])
    limb = _currency_limb(_log((_ACT, rows, "to")))
    assert f"{_ACT}: commencement relations made by another instrument are recorded, " \
           "but not all are listed" in limb
    assert "so do not state whether it has been commenced" in limb
    assert "not recorded as commenced" not in limb


def test_only_self_referential_relations_permit_neither():
    """Batch 6 B's F3. An Act's commencement section listed against every
    provision it governs is not evidence that any of them has commenced;
    P2.5's limb said "Commencement relations WERE retrieved" of it."""
    rows = _rows(("s. 1", _ACT, "coming into force"), ("s. 7", _ACT, "coming into force"))
    limb = _currency_limb(_log((_ACT, rows, "to")))
    assert f"{_ACT}: the only commencement relations recorded are its own " \
           "commencement provision acting on itself" in limb
    assert "do not state from this record whether any of its provisions has been " \
           "commenced" in limb
    assert "not recorded as commenced" not in limb
    assert "WERE retrieved" not in limb


@pytest.mark.parametrize("rows", [
    [],                                                              # an empty record
    _rows(("s. 2", "asp/1901/9", "words substituted")),              # amendments only
    _rows(("specified amended provision(s)", "ssi/1901/5", "Commencement Order")),
], ids=["empty record", "amendments only", "commencement orders of amendments only"])
def test_a_record_with_no_commencement_relation_permits_neither(rows):
    limb = _currency_limb(_log((_ACT, rows, "to")))
    assert f"{_ACT}: the record lists neither a commencement by another instrument " \
           "nor one of its own: do not state from it whether any of its provisions " \
           "has been commenced." in limb


def test_a_count_with_no_listed_group_permits_neither():
    d = {"legislation_id": _ACT, "direction": "to", "relations": 4,
         "provisions_commenced": 4, "related": []}
    log = []
    record_currency(log, "get_legislation_changes", {"legislation_id": _ACT}, d)
    limb = _currency_limb(log)
    assert f"{_ACT}: the record counts 4 commencement relation(s) but does not list " \
           "them" in limb


def test_no_change_record_consulted_permits_neither():
    """The not-consulted case: a step that searched and consulted no record."""
    limb = _currency_limb(_log())
    assert "Commencement: this step consulted no change record, so do not state " \
           "whether any provision of any instrument has been commenced." in limb


def test_every_other_instrument_is_named_as_not_consulted():
    limb = _currency_limb(_log((_ACT, [], "to")))
    assert "For any instrument not named here, this step consulted no change " \
           "record: do not state whether its provisions have been commenced." in limb


def test_a_record_of_changes_made_to_other_legislation_says_nothing_of_its_own():
    """Under "by", the order's relations commence the Act's provisions, not the
    order's own; the line says so and permits the former."""
    rows = _rows(("s. 1", _ORDER, "coming into force"))
    limb = _currency_limb(_log((_ORDER, rows, "by")))
    assert f"{_ORDER}: only the changes it makes to other legislation were " \
           "consulted. A provision of other legislation it lists as commenced may " \
           "be stated as commenced by it." in limb
    assert f"The record does not show whether any provision of {_ORDER} itself has " \
           "been commenced." in limb


def test_both_directions_on_one_instrument_keep_both_facts():
    rows_by = _rows(("s. 1", _ORDER, "coming into force"))
    limb = _currency_limb(_log((_ORDER, [], "to"), (_ORDER, rows_by, "by")))
    assert f"{_ORDER}: the record lists neither a commencement" in limb
    assert "Its changes to other legislation were also consulted" in limb
    assert limb.count(f"- {_ORDER}:") == 1


def test_one_line_per_instrument_and_the_best_call_wins():
    """A memo hit records the same instrument twice; it gets one line, and a
    record that shows commencement is not overwritten by a call that showed
    none."""
    full = _rows(("s. 1", _ORDER, "coming into force"))
    limb = _currency_limb(_log((_ACT, full, "to"), (_ACT, [], "to"),
                               ("asp/1901/2", [], "to")))
    assert limb.count(f"- {_ACT}:") == 1
    assert f"{_ACT}: 1 commencement relation(s) made by another instrument" in limb
    assert "- asp/1901/2: the record lists neither" in limb


def test_instruments_beyond_the_cap_share_one_line_that_permits_neither():
    from src.utils.search_scope import _MAX_COMMENCEMENT_LINES
    lids = [f"asp/1901/{100 + i}" for i in range(_MAX_COMMENCEMENT_LINES + 2)]
    limb = _currency_limb(_log(*[(lid, [], "to") for lid in lids]))
    assert limb.count(": the record lists neither") == _MAX_COMMENCEMENT_LINES
    assert f"- {lids[-2]}, {lids[-1]}: records consulted but not described here" in limb


def test_the_line_reaches_the_report_block():
    """The agent that writes the answer reads `worker_scope_block`."""
    block = worker_scope_block(_log((_ACT, _rows(("s. 1", _ACT, "coming into force")),
                                     "to")), {})
    assert "acting on itself" in block
    assert block.rstrip().endswith("[/SEARCH SCOPE]")


# --- the prompt sentence -----------------------------------------------------

def test_the_prompt_sentence_is_in_exactly_the_three_prompts_with_the_rule():
    from src import prompts
    sentence = prompts._COMMENCEMENT_RECORD_RULE
    rule_head = "IN-FORCE STATUS (whether legislation is current law):"
    carriers = {name for name, v in vars(prompts).items()
                if isinstance(v, str) and sentence in v
                and name not in ("_COMMENCEMENT_RECORD_RULE", "_IN_FORCE_RULE")}
    with_rule = {name for name, v in vars(prompts).items()
                 if isinstance(v, str) and rule_head in v
                 and name not in ("_COMMENCEMENT_RECORD_RULE", "_IN_FORCE_RULE")}
    assert carriers == {"WORKER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT_HYBRID",
                        "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"}
    assert carriers == with_rule
    assert sentence in prompts._IN_FORCE_RULE
    # Beside the bullets it qualifies: after (a)-(d) and `Commencement Order`.
    rule = prompts._IN_FORCE_RULE
    assert rule.index("`Commencement Order` is NOT (a)") < rule.index(sentence) \
        < rule.index("If you DID call `get_legislation_changes`")
    assert sentence.startswith("- (a) counts only a relation made by ANOTHER instrument")


# --- the grader P3.24's acceptance is read with --------------------------------

def _graded(answer, rows, lid=_ACT, direction="to"):
    import json
    from tools.replay_report import negcurrency_turn
    slim = _slim_amendment_results(rows, lid, direction)
    turn = {"answer": answer, "audit": {"delegations": [{"tools": [{
        "name": "get_legislation_changes",
        "args": {"legislation_id": lid, "direction": direction},
        "raw_result": json.dumps(slim)}]}]}}
    return negcurrency_turn(turn)[0]


def test_negcurrency_reads_the_change_record_in_p319_shape():
    """`replay_report negcurrency` read only the pre-P3.19 `changed_provisions`,
    so on a record in P3.19's `changes` shape it saw no provision at all and
    graded a negative the record CONTRADICTS as SUPPORTED. `wave4_b7_p324` is
    the first directory in that shape."""
    rows = _rows(("s. 1", _ORDER, "coming into force"),
                 ("s. 2", _ORDER, "coming into force"))
    (claim,) = _graded("Section 1 of the Widget Act 1901 is not yet in force.", rows)
    assert claim[2] == "UNSUPPORTED"
    assert "lists s. 1 as commenced" in claim[3]
    # The true negative stays SUPPORTED (Invariant 1).
    (claim,) = _graded("Section 5 of the Widget Act 1901 is not yet in force.", rows)
    assert claim[2] == "SUPPORTED"


def test_negcurrency_reads_the_p319_cut_marker():
    """`changes_not_listed` is P3.19's cut marker: a provision not shown may be
    in the part left out, so the negative is UNCLEAR, not SUPPORTED."""
    rows = _rows(*[(f"s. {i}", _ORDER, "coming into force") for i in range(1, 62)])
    (claim,) = _graded("Section 99 of the Widget Act 1901 is not yet in force.", rows)
    assert claim[2] == "UNCLEAR"


# --- the Worker-facing block on the change record (extension, user decision) ---

def _worker_note(rows, lid=_ACT, direction="to"):
    from src.utils.search_scope import amendment_search_note
    slim = _slim_amendment_results(rows, lid, direction)
    return amendment_search_note({"legislation_id": lid, "direction": direction}, slim)


_P25_SENTENCE = "those ARE its own commencement and you may state them"


def test_the_worker_block_permits_relations_by_another_instrument():
    note = _worker_note(_rows(("s. 1", _ORDER, "coming into force"),
                              ("s. 2", _ORDER, "coming into force")))
    assert " 2 `coming into force` relation(s) were made by another instrument and " \
           "name a provision of this legislation: you may state each of those " \
           "provisions as commenced, citing the instrument against it." in note
    assert "They are all listed here, so a provision of this legislation not among " \
           "them may be called not recorded as commenced" in note
    assert _P25_SENTENCE not in note
    assert "self: true` relation" not in note


def test_the_worker_block_says_when_the_list_is_cut():
    rows = _rows(*[(f"s. {i}", _ORDER, "coming into force") for i in range(1, 62)])
    note = _worker_note(rows)
    assert "The commencement relations are not all listed here, so a provision " \
           "not listed may be in the part not shown: do not state whether it has " \
           "been commenced." in note
    assert "not recorded as commenced" not in note


def test_the_worker_block_does_not_read_self_relations_as_commencement():
    """F3 at the Worker's own seam. For an Act the self relation is its
    commencement section; for an SI it is usually the regulation fixing its own
    commencement day, which is why the Worker is sent to that provision for the
    date."""
    for lid in (_ACT, _ORDER):
        rows = _rows(("s. 1", lid, "coming into force"), ("s. 7", lid, "coming into force"),
                     changed=lid)
        note = _worker_note(rows, lid=lid)
        assert " 2 `coming into force` relation(s) are marked `self: true`: this " \
               "legislation's own commencement provision acting on itself, which says " \
               "how its provisions come into force, not whether they have. Read that " \
               "provision itself for any date it fixes, and do not state from these " \
               "relations alone whether a provision has been commenced." in note
        assert _P25_SENTENCE not in note
        assert "made by another instrument" not in note


def test_the_worker_block_splits_a_mixed_record():
    rows = _rows(("s. 1", _ORDER, "coming into force"),
                 ("s. 2", _ACT, "coming into force"), ("s. 3", _ACT, "coming into force"))
    note = _worker_note(rows)
    assert " 1 `coming into force` relation(s) were made by another instrument" in note
    assert " 2 `coming into force` relation(s) are marked `self: true`" in note


def test_the_worker_block_with_a_count_and_no_listed_group():
    from src.utils.search_scope import amendment_search_note
    d = {"legislation_id": _ACT, "direction": "to", "relations": 5,
         "provisions_commenced": 5, "related": [], "window_complete": True}
    note = amendment_search_note({"legislation_id": _ACT}, d)
    assert " 5 relation(s) are `coming into force`, but their groups are not listed " \
           "here" in note


def test_the_worker_block_under_by_speaks_of_other_legislation():
    note = _worker_note(_rows(("s. 1", _ORDER, "coming into force")),
                        lid=_ORDER, direction="by")
    assert "this legislation commencing provisions of the legislation named " \
           "against each" in note
    assert "they do not show whether this legislation's own provisions have been " \
           "commenced" in note
    assert _P25_SENTENCE not in note


def test_the_worker_block_keeps_the_honest_failure_branch():
    """Invariant 1: a record with no `coming into force` relation still says
    the commencement is not recorded here, never that it was not made."""
    for rows in ([], _rows(("s. 2", "asp/1901/9", "words substituted"))):
        note = _worker_note(rows)
        if rows:
            assert "NO relation here is a `coming into force` relation for this " \
                   "legislation" in note
            assert "do not conclude it was never commenced" in note
        assert "made by another instrument" not in note
        assert "self: true` relation" not in note
