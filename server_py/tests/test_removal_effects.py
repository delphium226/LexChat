"""FIX_PLAN P3.28 — the change record's removals, classified by effect type.

The change record counted a relation as a repeal when its effect held "repeal",
"revok" or "revoc", and said of each that the named provision "is no longer in
force". Batch 12 G read every effect type in both vocabularies (2,063 LEX types,
713 legislation.gov.uk feed types) and found it wrong both ways: it missed
"omitted", "removed", "deleted", "ceases to have effect" and "rev (saving)"
(3,422 relations), so a record whose whole-provision removals were all
"omitted" was handed over as holding none, and 12 answer sentences then denied a
removal the record held; and it over-claimed "no longer in force" of "words
repealed" (the provision stays) and "repealed (prosp.)" (not yet in effect), and
counted "power to repeal conferred" at all.

Every fixture here is synthetic (`ssi/1901/3`, "Widget Order 1901"); the effect
strings are legislation.gov.uk's public vocabulary.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.tools.lex import _slim_amendment_results
from src.utils import search_scope as ss
from src.utils.removal_effects import (
    LEGACY_KEY,
    PROVISION,
    PROVISION_IN_PART,
    PROVISION_KEY,
    QUALIFIED,
    QUALIFIED_KEY,
    WORDS_ONLY,
    WORDS_ONLY_KEY,
    classify_removal,
    counts_from_effects,
    removal_counts,
)

SUBJECT = "ssi/1901/3"


# ---------------------------------------------------------------------------
# the classifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("effect", [
    "repealed", "repeal", "revoked", "omitted", "removed", "deleted",
    "ceases to have effect", "cease to have effect", "ceased to have effect",
    "rev (saving)", "rev. (saving)", "Form omitted", "repealed (saving)",
    "repealed (1.1.1996)", "omitted by virtue of S.I. 1901/7, reg. 7(10)(a) (as substituted)",
])
def test_a_whole_provision_removal_is_a_provision_removal(effect):
    """Each family the product missed ("omitted" is the largest: 1,469 LEX
    relations), and the ones it counted, with a date or a saving that does not
    qualify the removal."""
    assert classify_removal(effect) == (PROVISION, "")


@pytest.mark.parametrize("effect", [
    "repealed in part", "revoked in part & amended (15.1.2000)", "rev in pt (2.8.2005)",
    "repealed In pt. & amended",
])
def test_part_of_a_provision_removed_is_its_own_class(effect):
    assert classify_removal(effect) == (PROVISION_IN_PART, "")


@pytest.mark.parametrize("effect", [
    "words omitted", "word omitted", "words repealed", "word repealed",
    "words revoked", "entry repealed", "entries omitted", "words removed",
    "words deleted", "words and comma omitted",
])
def test_words_or_entries_removed_only_is_text_amended(effect):
    """The provision stays; its text is amended. "words repealed" was counted as
    a repeal before P3.28 (540 relations over the stored records)."""
    assert classify_removal(effect) == (WORDS_ONLY, "")


@pytest.mark.parametrize("effect,qualifier", [
    ("repealed (prosp.)", "prospective"),
    ("repealed in part (pt.prosp.)", "prospective"),
    ("omitted (temp.)", "temporary"),
    ("words repealed (temp.)", "temporary"),
    ("omitted (cond.)", "conditional"),
    ("words omitted (cond.)", "conditional"),
    ("omitted for specified purposes", "for specified purposes"),
    ("repealed (S)", "for part of the United Kingdom only"),
    ("repealed (EW)", "for part of the United Kingdom only"),
    ("repealed in part (S)", "for part of the United Kingdom only"),
    ("repealed (1.4.1995) (S)", "for part of the United Kingdom only"),
    ("revoked (E.W.)", "for part of the United Kingdom only"),
    ("repealed (N.I.)", "for part of the United Kingdom only"),
])
def test_a_qualified_removal_carries_its_qualifier(effect, qualifier):
    """A qualifier wins over "in part" and "words": "repealed in part (S)" is a
    removal for Scotland only before it is a part removal."""
    assert classify_removal(effect) == (QUALIFIED, qualifier)


def test_a_lower_case_bracket_is_not_a_territory():
    """The territory codes are capitals; "(s)" is a plural, "(a)" a paragraph."""
    assert classify_removal("word(s) repealed")[0] == WORDS_ONLY
    assert classify_removal("omitted by S.I. 1901/7, reg. 2(s)") == (PROVISION, "")


@pytest.mark.parametrize("effect", [
    "power to repeal conferred", "power to amend or revoke conferred",
    "repeal of earlier affecting provision 1901 asp 7, sch. 6 para. 3",
    "revocation of earlier commencing SSI 1901/239",
    "omitted in earlier amending provision S.I. 1901/748, reg. 27",
    "words omitted in earlier amending provision 1901 c. 22, s. 5(8) (cond.)",
    "saving for expiry of 1901 c. 7, s. 1 (repealed)",
    "expiry of earlier affecting provision 1901 c. 7, Sch. 1 (omitted)",
    "functions cease to be exercisable concurrently",
    "coming into force", "Commencement Order", "words substituted", "inserted",
    "modified", "applied (with modifications)", "disapplied", "not stated", None, "",
])
def test_nothing_else_is_a_removal_of_the_subject(effect):
    """The product's four false positives, and the not-the-subject types a naive
    "omit" or "expiry" widening would catch (batch 12 G: 14 + 65 LEX types)."""
    assert classify_removal(effect) == (None, "")


def test_counts_from_an_effect_histogram():
    eff = {"repealed": 3, "repealed in part": 2, "omitted": 1, "words omitted": 4,
           "repealed (prosp.)": 1, "power to repeal conferred": 5,
           "coming into force": 9, "odd": "x"}
    assert counts_from_effects(eff) == {PROVISION_KEY: 6, WORDS_ONLY_KEY: 4,
                                        QUALIFIED_KEY: 1}
    assert counts_from_effects(None) == {PROVISION_KEY: 0, WORDS_ONLY_KEY: 0,
                                         QUALIFIED_KEY: 0}


def test_removal_counts_prefers_the_slimmer_then_the_histogram_then_the_old_count():
    slim = {PROVISION_KEY: 1, WORDS_ONLY_KEY: 2, QUALIFIED_KEY: 3,
            "effects": {"repealed": 9}, LEGACY_KEY: 7}
    assert removal_counts(slim) == {PROVISION_KEY: 1, WORDS_ONLY_KEY: 2, QUALIFIED_KEY: 3}
    # a result stored before P3.28: its histogram, classified now, never the
    # old count (which held "words repealed" and missed "omitted")
    stored = {"effects": {"omitted": 2, "words repealed": 4}, LEGACY_KEY: 4}
    assert removal_counts(stored) == {PROVISION_KEY: 2, WORDS_ONLY_KEY: 4, QUALIFIED_KEY: 0}
    # a partial set of the new keys is not the slimmer's: read the histogram
    part = {PROVISION_KEY: 5, "effects": {"omitted": 2}}
    assert removal_counts(part)[PROVISION_KEY] == 2
    # no histogram at all: the old count, as provision removals
    assert removal_counts({LEGACY_KEY: 3}) == {PROVISION_KEY: 3, WORDS_ONLY_KEY: 0,
                                               QUALIFIED_KEY: 0}
    for odd in (None, "x", [], {LEGACY_KEY: "3"}, {"effects": "x"}):
        assert removal_counts(odd)[PROVISION_KEY] == 0


def test_removal_counts_never_raises():
    class Boom(dict):
        def get(self, *a, **k):
            raise RuntimeError("boom")
    assert removal_counts(Boom()) == {PROVISION_KEY: 0, WORDS_ONLY_KEY: 0, QUALIFIED_KEY: 0}


# ---------------------------------------------------------------------------
# the slimmer
# ---------------------------------------------------------------------------

def _rows(*specs, subject=SUBJECT):
    out = []
    for prov, affecting, effect in specs:
        for scheme in ("http", "https"):
            out.append({
                "changed_legislation": subject, "changed_provision": prov,
                "changed_url": f"{scheme}://www.legislation.gov.uk/id/{subject}",
                "affecting_legislation": affecting, "affecting_provision": "art. 2",
                "affecting_url": f"{scheme}://www.legislation.gov.uk/id/{affecting}",
                "type_of_effect": effect,
            })
    return out


def _slim():
    return _slim_amendment_results(_rows(
        ("reg. 1", "ssi/1901/4", "omitted"),
        ("reg. 2", "ssi/1901/4", "repealed in part"),
        ("reg. 3", "ssi/1901/5", "words repealed"),
        ("reg. 4", "ssi/1901/5", "repealed (prosp.)"),
        ("reg. 5", "ssi/1901/6", "power to repeal conferred"),
        ("reg. 6", "ssi/1901/6", "words substituted"),
    ), SUBJECT, "to")


def test_the_slimmer_counts_removals_by_class():
    slim = _slim()
    assert (slim[PROVISION_KEY], slim[WORDS_ONLY_KEY], slim[QUALIFIED_KEY]) == (2, 1, 1)
    # the old count is not written beside the new ones: two counts of
    # "repeals" disagreeing in one result would be read by the Worker
    assert LEGACY_KEY not in slim
    assert slim["relations"] == 6, "the http/https twins must still collapse"


def test_each_removal_group_is_marked_with_its_class_and_only_those():
    groups = {g["type_of_effect"]: g for g in _slim()["related"]}
    assert groups["omitted"]["removal"] == PROVISION
    assert groups["repealed in part"]["removal"] == PROVISION_IN_PART
    assert groups["words repealed"]["removal"] == WORDS_ONLY
    assert groups["repealed (prosp.)"]["removal"] == QUALIFIED
    assert groups["repealed (prosp.)"]["qualifier"] == "prospective"
    for effect in ("omitted", "repealed in part", "words repealed"):
        assert "qualifier" not in groups[effect]
    for effect in ("power to repeal conferred", "words substituted"):
        assert "removal" not in groups[effect] and "qualifier" not in groups[effect]


def test_one_group_per_effect_still_counts_every_relation():
    """The group is created once and its count still runs (the slimmer's own
    pattern, rebuilt round the class key)."""
    slim = _slim_amendment_results(_rows(
        ("reg. 1", "ssi/1901/4", "omitted"), ("reg. 2", "ssi/1901/4", "omitted")),
        SUBJECT, "to")
    assert len(slim["related"]) == 1
    assert slim["related"][0]["count"] == 2
    assert slim["related"][0]["removal"] == PROVISION


# ---------------------------------------------------------------------------
# the Worker's change-record block (`_relation_removal_bits`)
# ---------------------------------------------------------------------------

W_WHOLE = ("relation(s) remove a provision, wholly or in part (their groups are marked "
           "`removal: provision` or `removal: provision_in_part`): those establish that the "
           "named provision, or the part of it removed, is no longer in force, and you may "
           "state them the same way.")
W_WORDS = ("relation(s) remove words or entries only (marked `removal: words_only`): each "
           "amends the text of the named provision, which stays, so state it as the text "
           "amended, never as a provision removed.")
W_QUAL = ("relation(s) remove something with a qualification in their effect (marked "
          "`removal: qualified`, with a `qualifier`: prospective, temporary, conditional, "
          "for specified purposes, or for part of the United Kingdom only): state each only "
          "with its qualification, never as a provision removed outright.")


def _rec(effects, lid=SUBJECT, direction="to"):
    return {"legislation_id": lid, "direction": direction,
            "relations": sum(effects.values()), "effects": effects, "related": [],
            "window_complete": True, "provisions_commenced": 0,
            "commencement_orders_of_amendments": 0}


def test_each_class_gets_its_own_sentence_and_only_when_present():
    full = ss._relation_removal_bits(_rec({"omitted": 2, "words omitted": 3,
                                           "omitted (temp.)": 1}))
    assert f" 2 {W_WHOLE}" in full and f" 3 {W_WORDS}" in full and f" 1 {W_QUAL}" in full
    assert full.endswith(" The record gives no date for these removals either.")
    words = ss._relation_removal_bits(_rec({"words repealed": 4}))
    assert words == f" 4 {W_WORDS} The record gives no date for these removals either."
    qual = ss._relation_removal_bits(_rec({"repealed (prosp.)": 1}))
    assert qual == f" 1 {W_QUAL} The record gives no date for these removals either."
    whole = ss._relation_removal_bits(_rec({"repealed in part": 1}))
    assert whole == f" 1 {W_WHOLE} The record gives no date for these removals either."
    assert ss._relation_removal_bits(_rec({"words substituted": 2})) == ""
    assert ss._relation_removal_bits(_rec({"power to repeal conferred": 2})) == ""


def test_words_repealed_is_no_longer_said_to_take_a_provision_out_of_force():
    """The over-claim: before P3.28, "words repealed" fell under "those establish
    that the named provision is no longer in force"."""
    note = ss.amendment_search_note({"legislation_id": SUBJECT},
                                    json.dumps(_rec({"words repealed": 4})))
    assert "no longer in force" not in note.replace(
        "it CANNOT establish that this legislation is in force as a whole", "")
    assert "state it as the text amended" in note


def test_an_omitted_provision_is_handed_over_as_removed():
    """The false negative: an "omitted" whole provision counted 0 before, so
    the Worker read the record as holding no repeal."""
    note = ss.amendment_search_note({"legislation_id": SUBJECT},
                                    json.dumps(_rec({"omitted": 3})))
    assert f" 3 {W_WHOLE}" in note


def test_a_stored_pre_p328_result_rebuilds_through_its_histogram():
    """`seam_replay --from-raw` rebuilds a stored result's blocks with current
    code: the old count says 4 repeals, the histogram says 2 omitted provisions
    and 4 words repealed."""
    stored = _rec({"omitted": 2, "words repealed": 4})
    stored[LEGACY_KEY] = 4
    bits = ss._relation_removal_bits(stored)
    assert f" 2 {W_WHOLE}" in bits and f" 4 {W_WORDS}" in bits


# ---------------------------------------------------------------------------
# the Manager's limb and the lawyer's footer
# ---------------------------------------------------------------------------

def _log(*recs):
    log = []
    for r in recs:
        ss.record_currency(log, "get_legislation_changes",
                           {"legislation_id": r["legislation_id"]}, r)
    return log


def test_the_currency_log_carries_the_three_classes():
    (e,) = _log(_rec({"omitted": 2, "words omitted": 3, "repealed (S)": 1}))
    assert (e["repeals"], e["words_only_removals"], e["qualified_removals"]) == (2, 3, 1)


M_WHOLE = ("Relations removing a provision wholly or in part (repealed, revoked, omitted or "
           "ceasing to have effect, for example) were retrieved for")
M_WORDS = "Relations removing words or entries only were retrieved for"
M_QUAL = "Removals with a qualification in their effect"


def test_the_manager_limb_names_each_class_for_its_own_instruments():
    limb = ss._currency_limb(_log(
        _rec({"omitted": 1}, lid="ssi/1901/3"),
        _rec({"words omitted": 1}, lid="ssi/1901/4"),
        _rec({"repealed (prosp.)": 1}, lid="ssi/1901/5"),
        _rec({"words omitted": 1}, lid="ssi/1901/4"),
        _rec({"repealed (prosp.)": 1}, lid="ssi/1901/5"),
    ))
    assert f" {M_WHOLE} ssi/1901/3 — a statement that those provisions, or the parts " \
           "removed, are no longer in force is supported, again without a date." in limb
    assert (f" {M_WORDS} ssi/1901/4: each amends the text of the provision it names, which "
            "stays, so state it as the text amended, never as a provision removed.") in limb
    assert (f" {M_QUAL} (prospective, temporary, conditional, for specified purposes, or "
            "for part of the United Kingdom only) were retrieved for ssi/1901/5: state each "
            "only with its qualification, never as a provision removed outright.") in limb
    # each list names only its own instruments, once
    assert limb.count("ssi/1901/4") == limb.count(f"{M_WORDS} ssi/1901/4") + \
        limb.count("- ssi/1901/4:")
    assert limb.count("ssi/1901/5") == limb.count(f"were retrieved for ssi/1901/5:") +         limb.count("- ssi/1901/5:")


def test_the_manager_limb_lists_at_most_six_per_class():
    recs = [_rec({"words omitted": 1}, lid=f"ssi/1901/{10 + i}") for i in range(8)]
    limb = ss._currency_limb(_log(*recs))
    line = limb[limb.index(M_WORDS):]
    line = line[:line.index(":")]
    assert "ssi/1901/15" in line and "ssi/1901/16" not in line
    recs = [_rec({"omitted (temp.)": 1}, lid=f"ssi/1901/{30 + i}") for i in range(8)]
    limb = ss._currency_limb(_log(*recs))
    line = limb[limb.index(M_QUAL):]
    line = line[line.index("retrieved for"):]
    line = line[:line.index(":")]
    assert "ssi/1901/35" in line and "ssi/1901/36" not in line


def test_a_record_with_no_removal_of_a_provision_is_not_listed_as_one():
    limb = ss._currency_limb(_log(_rec({"words repealed": 2, "power to repeal conferred": 1})))
    assert M_WHOLE not in limb and M_WORDS in limb


def test_the_footer_counts_any_removal_as_a_checked_change():
    """P4.18's sentence says the record lists "neither a commencement nor a
    repeal": false of a record whose only removals are "words omitted", and true
    of one whose only "repeal" is a power conferred."""
    words = ss._currency_footer_clause(_log(_rec({"words omitted": 2})))
    assert "neither a commencement nor a repeal" not in words
    assert "what was checked is the recorded changes for ssi/1901/3" in words
    qual = ss._currency_footer_clause(_log(_rec({"omitted (temp.)": 2})))
    assert "what was checked is the recorded changes for ssi/1901/3" in qual
    conferred = ss._currency_footer_clause(_log(_rec({"power to repeal conferred": 2})))
    assert "neither a commencement nor a repeal" in conferred
    omitted = ss._currency_footer_clause(_log(_rec({"omitted": 1})))
    assert "what was checked is the recorded changes for ssi/1901/3" in omitted


# ---------------------------------------------------------------------------
# every new sentence against every detector that reads answers
# ---------------------------------------------------------------------------

def _detectors():
    from tools import replay_report as rr
    return rr


def _trips(text):
    rr = _detectors()
    out = []
    for name in ("NEG_ASSERTED", "NOT_FOUND", "IN_FORCE_CLAIM", "_CUR_DISCLOSED",
                 "NEG_TERMS", "NEG_LIMITS", "NEG_BLAMED_INDEX", "NEG_BLAMED_USER",
                 "HALT_LITERAL", "HALT_PARAPHRASE", "HALT_AS_TIMEOUT", "OPENER_VOCAB"):
        if getattr(rr, name).search(text):
            out.append(name)
    if rr.derivation_claims(text)[0]:
        out.append("derivation")
    if rr._without_footer(text) != text.strip():
        out.append("footer strip")
    for s in rr._sentences(text):
        if rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s):
            out.append("CMC_DENIED")
        if rr._currency_asserted(s):
            out.append("currency_asserted")
        if rr.negcurrency_claim(s)[0] is not None:
            out.append("negcurrency:" + rr.negcurrency_claim(s)[0])
    return out


OLD_WORKER = (" 3 relation(s) are repeals or revocations: those establish that the named "
              "provision is no longer in force, and you may state them the same way.")
OLD_MANAGER = (" Repeal or revocation relations were retrieved for ssi/1901/3 — a statement "
               "that those provisions are no longer in force is supported, again without a "
               "date.")


def test_the_new_sentences_trip_nothing_the_old_one_did_not():
    """The words-only and qualified sentences trip no detector at all. The
    provision sentence permits "no longer in force", so `negcurrency` reads it
    as that claim, exactly as it read P2.5's sentence it replaces, and nothing
    else."""
    for text in (f" 3 {W_WORDS}", f" 2 {W_QUAL}",
                 " The record gives no date for these removals either.",
                 " The record gives no date for these removals.",
                 ss._currency_limb(_log(_rec({"words omitted": 1})))
                 [ss._currency_limb(_log(_rec({"words omitted": 1}))).index(M_WORDS) - 1:]
                 .split(" So in the Jurisdiction")[0],
                 ss._currency_limb(_log(_rec({"omitted (temp.)": 1})))
                 [ss._currency_limb(_log(_rec({"omitted (temp.)": 1}))).index(M_QUAL) - 1:]
                 .split(" So in the Jurisdiction")[0]):
        assert _trips(text) == [], text
    assert _trips(f" 3 {W_WHOLE}") == _trips(OLD_WORKER) == ["negcurrency:no_longer"]
    limb = ss._currency_limb(_log(_rec({"omitted": 1})))
    whole = limb[limb.index(M_WHOLE) - 1:].split(" So in the Jurisdiction")[0]
    assert _trips(whole) == _trips(OLD_MANAGER) == ["negcurrency:no_longer"]
