"""P3.24 — the negative and continuing commencement-claim detector.

`replay_report negcurrency` reads every sentence that says a provision is not
yet commenced, partially in force, no longer in force or remains in force, and
grades it against what the conversation retrieved: SUPPORTED, UNSUPPORTED (read
from an absence, or contradicted) or UNCLEAR. P2.5's `_currency_asserted`
deliberately does not see the negative shape, because a true negative exists;
so this detector must keep the true one (Invariant 1) while catching the one
read from an empty or absent change record.

Every fixture is synthetic ("Widget (Scotland) Act 1901", `asp/1901/1`); no
session text, search term or instrument from the pre-pilot is used.
"""

import io
import json
from contextlib import redirect_stdout

from tools.replay_report import (
    _currency_asserted,
    cmd_negcurrency,
    negcurrency_claim,
    negcurrency_provisions,
    negcurrency_turn,
)

ACT = "asp/1901/1"
ACT_TITLE = "Widget (Scotland) Act 1901"
REGS = "ssi/1901/7"          # a commencing instrument
ORDER = "ssi/1901/3"
ORDER_TITLE = "Widget Order 1901"
OTHER = "uksi/1899/2"
OTHER_TITLE = "Gadget Regulations 1899"


def _tool(name, raw, args=None):
    return {"name": name, "args": args or {}, "raw_result": json.dumps(raw)}


def _search(*rows):
    return _tool("search_legislation", {"results": [
        {"legislation_id": lid, "title": title} for lid, title in rows]})


def _group(lid, effect, provisions, self_rel=False, not_listed=0):
    g = {"legislation_id": lid, "self": self_rel, "type_of_effect": effect,
         "count": len(provisions), "changed_provisions": list(provisions)}
    if not_listed:
        g["changed_provisions_not_listed"] = not_listed
        g["count"] += not_listed
    return g


def _changes(lid, groups, direction="to", complete=True):
    effects = {}
    for g in groups:
        effects[g["type_of_effect"]] = effects.get(g["type_of_effect"], 0) + g["count"]
    cif = effects.get("coming into force", 0)
    rep = sum(v for k, v in effects.items()
              if any(t in k.lower() for t in ("repeal", "revok", "revoc")))
    return _tool("get_legislation_changes", {
        "legislation_id": lid, "direction": direction, "relations": sum(effects.values()),
        "effects": effects, "provisions_commenced": cif,
        "commencement_orders_of_amendments": 0,
        "repeal_or_revocation_relations": rep, "related": groups,
        "window_complete": complete,
    }, {"legislation_id": lid, "direction": direction})


def _turn(answer, *tools, turn=1):
    return {"turn": turn, "question": "q", "answer": answer,
            "audit": {"delegations": [{"tools": list(tools)}]}}


def _one(answer, *tools, earlier=None):
    claims, _ = negcurrency_turn(_turn(answer, *tools), earlier)
    assert len(claims) == 1, claims
    return claims[0]


# --- the claim vocabulary and its guards ------------------------------------

def test_the_shape_p25_cannot_see_is_a_claim_here():
    """The row's premise, pinned: P2.5's grader skips the negative by design,
    and this detector is what reads it."""
    s = "Section 5: Not yet commenced."
    assert not _currency_asserted(s)
    assert negcurrency_claim(s) == ("not_yet", None)


def test_each_kind_is_recognised():
    assert negcurrency_claim("Sections 2 to 4 have not yet been brought into force.")[0] == "not_yet"
    assert negcurrency_claim("The Widget (Scotland) Act 1901 is partially in force.")[0] == "partial"
    assert negcurrency_claim("The Widget Order 1901 is no longer in force.")[0] == "no_longer"
    assert negcurrency_claim("In Scotland this requirement no longer applies.")[0] == "no_longer"
    assert negcurrency_claim("Section 9 is not in force.")[0] == "not_in_force"
    assert negcurrency_claim("The prohibition in section 3 remains in force.")[0] == "continuing"
    assert negcurrency_claim("The Act remains on the statute book.")[0] == "continuing"


def test_non_claims_are_dropped_with_a_reason():
    assert negcurrency_claim("Is section 5 not yet in force?") == ("not_yet", "question")
    assert negcurrency_claim(
        'Section 1 provides that the Act "shall continue in force until Parliament '
        'otherwise determines".') == ("continuing", "quoted")
    assert negcurrency_claim(
        "To establish whether section 5 remains in force, consult the record.") == (
        "continuing", "conditional")
    assert negcurrency_claim("Section 5 may not yet be in force.") == ("not_yet", "hedged")
    # "likely" leans on the absence as hard as the bare form, so it is graded.
    assert negcurrency_claim(
        "No commencement regulations were found, so section 5 is likely not yet "
        "in force.") == ("not_yet", None)
    # A statement about the record is not a claim about the law.
    assert negcurrency_claim("The remaining sections are not yet recorded as commenced.") == (
        None, None)


def test_the_disclaimer_is_read_on_its_own_clause():
    """A claim in one clause is not dropped because the next one disclaims."""
    s = ("The record lists repeals, establishing that some provisions are no longer "
         "in force, but it does not establish the in-force status of the Act as a whole.")
    assert negcurrency_claim(s) == ("no_longer", None)


def test_provisions_are_parsed_to_the_records_base_form():
    assert negcurrency_provisions("All other sections (1, 3–5, and 9) are not yet in force.") == [
        "s. 1", "s. 3", "s. 4", "s. 5", "s. 9"]
    # Authority is not the subject; a title's year is not a provision.
    assert negcurrency_provisions(
        "Anything not covered by section 39(1) remains uncommenced.") == []
    assert negcurrency_provisions(
        "The Gadget Regulations 1899 were revoked by SI 1901/3, reg. 2(c).") == []


# --- verdicts ---------------------------------------------------------------

def test_a_negative_with_no_change_record_is_unsupported():
    s, kind, verdict, why = _one(
        "Sections 2 to 4 of the Widget (Scotland) Act 1901 have not yet been commenced.",
        _search((ACT, ACT_TITLE)))
    assert (kind, verdict) == ("not_yet", "UNSUPPORTED")
    assert "absence" in why


def test_an_empty_change_record_does_not_support_a_negative():
    """The era gap: a record with no commencement relation at all says nothing
    about whether a provision commenced."""
    _, _, verdict, why = _one(
        "Section 4 has not yet been commenced.",
        _changes(ACT, [_group(REGS, "repealed", ["s. 7"])]))
    assert verdict == "UNSUPPORTED"
    assert "no commencement relation" in why


def test_the_true_negative_is_kept():
    """Invariant 1: a record that commences some provisions by another
    instrument, listed in full, and not this one, shows it uncommenced."""
    _, _, verdict, _ = _one(
        "Sections 3 and 4 are not yet in force.",
        _changes(ACT, [_group(REGS, "coming into force", ["s. 1", "s. 2"])]))
    assert verdict == "SUPPORTED"


def test_a_negative_the_record_contradicts_is_unsupported():
    _, _, verdict, why = _one(
        "Section 2 is not yet in force.",
        _changes(ACT, [_group(REGS, "coming into force", ["s. 1", "s. 2"])]))
    assert verdict == "UNSUPPORTED"
    assert "as commenced" in why


def test_a_self_referential_relation_is_not_a_commencement():
    """The Act's own commencement section lists every provision it governs,
    including those it leaves to regulations, so it neither supports nor
    contradicts."""
    _, _, verdict, why = _one(
        "Section 4 is not yet in force.",
        _changes(ACT, [_group(ACT, "coming into force", ["s. 1", "s. 2", "s. 3", "s. 4"],
                              self_rel=True)]))
    assert verdict == "UNCLEAR"
    assert "instrument's own" in why


def test_a_truncated_record_cannot_show_a_provision_absent():
    _, _, verdict, _ = _one(
        "Section 99 is not yet in force.",
        _changes(ACT, [_group(REGS, "coming into force", ["s. 1"], not_listed=70)]))
    assert verdict == "UNCLEAR"


def test_denying_the_whole_instrument_against_a_record_of_commencements():
    _, _, verdict, why = _one(
        "The Widget (Scotland) Act 1901 is not yet in force.",
        _search((ACT, ACT_TITLE)),
        _changes(ACT, [_group(REGS, "coming into force", ["s. 1"])]))
    assert verdict == "UNSUPPORTED"
    assert "whole instrument" in why


def test_partial_is_never_read_as_denying_the_provisions_it_names():
    _, kind, verdict, _ = _one(
        "It is partially in force, with sections 1 and 2 brought into force by regulations.",
        _changes(ACT, [_group(REGS, "coming into force", ["s. 1", "s. 2"])]))
    assert (kind, verdict) == ("partial", "SUPPORTED")


def test_a_commencement_provision_names_the_mechanism_not_its_use():
    section = _tool("search_legislation_sections", [{
        "legislation_id": ACT, "number": "9", "title": "Commencement",
        "text": "The other provisions of this Act come into force on such day as the "
                "Scottish Ministers may by regulations appoint."}])
    _, _, verdict, _ = _one("The rest of the Act is not yet in force.", section)
    assert verdict == "UNSUPPORTED"
    dated = _tool("search_legislation_sections", [{
        "legislation_id": ACT, "number": "9", "title": "Commencement",
        "text": "This Act comes into force on 1 April 2999."}])
    _, _, verdict, _ = _one("The rest of the Act is not yet in force.", dated)
    assert verdict == "UNCLEAR"


def test_an_abbreviated_revocation_counts_as_a_removal():
    """The feed writes "rev (saving)" and "omitted", which the slimmer's own
    count does not include; the group itself is in the result the model read."""
    _, _, verdict, _ = _one(
        "The Widget Order 1901 is no longer in force.",
        _search((ORDER, ORDER_TITLE)),
        _changes(ORDER, [_group(REGS, "rev (saving)", ["Instrument"])]))
    assert verdict == "SUPPORTED"


def test_an_unrelated_instruments_removal_supports_nothing():
    """Read off every record in the turn, another instrument's revocation once
    'supported' a sentence about a different one."""
    tools = (_search((ORDER, ORDER_TITLE), (OTHER, OTHER_TITLE)),
             _changes(ORDER, []),
             _changes(OTHER, [_group(REGS, "revoked", ["Regulations"])]))
    _, _, verdict, _ = _one("The Widget Order 1901 is no longer in force.", *tools)
    assert verdict != "SUPPORTED"
    # Naming nothing, the sentence is read against every record, and the
    # other instrument's whole revocation still does not support it.
    _, _, verdict, _ = _one("In Scotland this requirement no longer applies.", *tools)
    assert verdict != "SUPPORTED"


def test_this_instrument_is_named_by_the_sentences_before_it():
    answer = ("*   **Widget Order 1901:** extends to Scotland.\n"
              "The index title marks this instrument as revoked, so it is no longer in force.")
    claims, _ = negcurrency_turn(_turn(
        answer, _tool("search_legislation", {"results": [
            {"legislation_id": ORDER, "title": ORDER_TITLE + " (revoked)"}]})))
    assert [c[2] for c in claims] == ["SUPPORTED"]


def test_remains_in_force_needs_a_record():
    _, _, verdict, _ = _one("The prohibition in section 3 remains in force.",
                            _search((ACT, ACT_TITLE)))
    assert verdict == "UNSUPPORTED"
    _, _, verdict, _ = _one(
        "The Widget Order 1901 remains in force.",
        _search((ORDER, ORDER_TITLE)),
        _changes(ORDER, [_group(REGS, "revoked", ["Order"])]))
    assert verdict == "UNSUPPORTED"


def test_on_the_statute_book_is_supported_by_a_complete_record_of_removals():
    _, _, verdict, _ = _one(
        "The Widget (Scotland) Act 1901 remains on the statute book.",
        _search((ACT, ACT_TITLE)),
        _changes(ACT, [_group(REGS, "repealed", ["s. 7"])]))
    assert verdict == "SUPPORTED"


def test_a_follow_up_rests_on_the_earlier_turns_retrieval():
    from tools.replay_report import negcurrency_evidence
    first = _turn("Sections 1 and 2 were commenced by regulations.",
                  _changes(ACT, [_group(REGS, "coming into force", ["s. 1", "s. 2"])]))
    earlier = negcurrency_evidence(first)
    _, _, verdict, why = _one("As noted, it is partially in force.", earlier=earlier)
    assert verdict == "SUPPORTED"
    assert "earlier turn" in why
    _, _, verdict, _ = _one("As noted, it is partially in force.")
    assert verdict == "UNSUPPORTED"


def test_the_command_counts_per_directory(tmp_path):
    root = tmp_path / "replay"
    for name, answer in (("dir_a", "Section 4 has not yet been commenced."),
                         ("dir_b", "Nothing about currency here.")):
        d = root / name
        d.mkdir(parents=True)
        (d / "9001_rep1.json").write_text(json.dumps({
            "session_id": "9001", "rep": 1,
            "turns": [_turn(answer, _search((ACT, ACT_TITLE)))]}), encoding="utf-8")

    class Args:
        dir = str(root)
        all = True
        sessions = None
        drops = False
        verbose = False

    out = io.StringIO()
    with redirect_stdout(out):
        assert cmd_negcurrency(Args) == 0
    text = out.getvalue()
    assert "dir_a" in text and "dir_b" not in text
    assert "turns with an UNSUPPORTED claim: 1 of 2 answered" in text
