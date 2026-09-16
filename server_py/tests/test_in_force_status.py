"""P2.5 (bucket B4) — stop asserting in-force status.

Pairs with P1.2, which removed the `current_only` filter and the two places it
asserted currency. The re-baseline showed that did **not** clear the bucket:
in-force claims went 27 -> 30 on the old instrument, because three prompt sites
still told the Worker to state currency and "Jurisdiction & Status" is a
mandatory report section.

**The model was not inventing a source — it was quoting the only field that
looked like one.** Measured over the replay corpus:

  * `status` vocabulary across **15,160** model-visible search rows (every
    row in all seven replay directories, printed by `lex_probe --inforce`):
    `final` 60.3%, `revised` 38.8%, **`stub` 0.9%** — three values, not the two
    the plan recorded, and not one of them says anything about currency;
  * of `wave1`'s 65 in-force assertion sentences, **48 cite a text version as
    the evidence** — "is currently in force (revised)", "Status: Revised (In
    force)".

**Three things this file pins that the row did not anticipate, all measured:**

1. **The old `IN_FORCE_CLAIM` detector undercounts by 30%.** It requires
   "is/are/remains/currently in force" and so catches none of the bare Status
   bullets that are the purest form of the defect — `In force (revised).`
   (6341 x3, 6384 x6, 6389 x3), `Status: Revised (In force).` (6406 x4).
   Properly counted, `wave1` is **43 turns / 65 assertions**, not 30 / 34. The
   old pattern is left byte-identical so the published series stays comparable.

2. **`Commencement Order` is not a commencement of the subject**, and P3.5 left
   that trap open. `ukpga/1998/46` — 6411's Act — has **zero `coming into
   force` relations and 29 `Commencement Order` ones**, each a commencement
   order for an *amendment* made to it by another Act. Across 1,355 such
   relations the `changed_provision` is one of eight placeholder values and
   never a provision. Merged, the fix for 6411's unsourced answer would have
   been a differently-sourced wrong one.

3. **The date is not in the relation.** 552 of 89,465 relations embed one in
   `type_of_effect` (0.6%) and **zero** of the 19,031 `coming into force` rows
   do, so P3.5's "no date on any relation" stands where it matters and the
   second hop is still required. Equally, a repeal marker in the title carries a
   date on only **8 of the 258** rows that have one — a flag, not a date route.

Nothing here asserts that anything was found. Invariant 1 applies in the
**inverse** direction for this row: the risk is suppressing a currency statement
the material now supports, which is why `test_a_retrieved_commencement_is_still_permitted`
and the `sourced` column of `replay_report currency` exist.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import _REPORT_SECTIONS
from src.agent.agent_shared import _extract_sources_inner
from src.agent.tools.lex import (
    _effect_is_commencement_of_subject,
    _effect_is_commencement_order,
    _effect_is_repeal,
    _slim_amendment_results,
    _slim_search_results,
)
from src.prompts import (
    DEEP_RESEARCH_SYNTHESIS_PROMPT,
    WORKER_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
    WORKER_SYSTEM_PROMPT_HYBRID,
)
from src.utils.search_scope import (
    _currency_footer_clause,
    _currency_limb,
    amendment_search_note,
    currency_note,
    legislation_search_note,
    record_currency,
    strip_scope_blocks,
)


def _api_search(*titles, status="revised"):
    """A raw `/legislation/search` response, pre-slimming."""
    return {
        "results": [
            {"uri": f"http://www.legislation.gov.uk/id/{lid}", "title": title,
             "status": status, "year": 2020, "extent": ["Scotland"]}
            for lid, title in titles
        ],
        "total": 141,
    }


def _rows(*specs):
    """`/amendment/search` rows. Each spec is (changed_provision, affecting, effect)."""
    out = []
    for prov, affecting, effect in specs:
        for scheme in ("http", "https"):  # the http/https twins, as the feed sends them
            out.append({
                "changed_legislation": "ukpga/1998/46",
                "changed_provision": prov,
                "changed_url": f"{scheme}://www.legislation.gov.uk/id/ukpga/1998/46",
                "affecting_legislation": affecting,
                "affecting_provision": "art. 2",
                "affecting_url": f"{scheme}://www.legislation.gov.uk/id/{affecting}",
                "type_of_effect": effect,
                "id": f"{scheme}-{prov}-{affecting}-{effect}",
            })
    return out


# ---------------------------------------------------------------------------
# The misread field — removed as an affordance, not argued with
# ---------------------------------------------------------------------------

def test_the_status_field_no_longer_reaches_the_model_under_that_name():
    """`status: "revised"` is what produced *"is currently in force (revised)"*
    on 48 of `wave1`'s 65 assertion sentences. The value is kept — it is true
    and a model may legitimately say the revised text is held — under a key that
    cannot be read as currency."""
    slim = _slim_search_results(_api_search(("asp/2018/9", "An Act")))
    row = slim["results"][0]
    assert row["text_version"] == "revised"
    assert "status" not in row, "the key the model misread must be gone"


@pytest.mark.parametrize("value", ["final", "revised", "stub"])
def test_the_whole_measured_vocabulary_survives_the_rename(value):
    """Three values, not two. `stub` is 0.9% of 15,160 rows and the plan and
    `test_current_only_removed`'s docstring both said the vocabulary was
    `final`/`revised` only — pinned here so a fourth value is visible rather
    than silently renamed to nothing."""
    slim = _slim_search_results(_api_search(("asp/2018/9", "An Act"), status=value))
    assert slim["results"][0]["text_version"] == value


def test_the_sources_rail_still_shows_what_it_showed_before():
    """The rename is confined to the model's view. `extract_sources` reads the
    new key, so the lawyer-facing rail (`year · meta · extent`) is unchanged —
    a silent empty badge would be a UI regression smuggled in by a backend fix."""
    acc = []
    slim = _slim_search_results(_api_search(("asp/2018/9", "An Act")))
    _extract_sources_inner("search_legislation", {}, slim, acc)
    assert acc and acc[0]["meta"] == "revised"


def test_a_pre_p25_result_still_populates_the_rail():
    """A memoised or replayed result written before the rename carries `status`.
    The fallback is why a cache hit does not blank the badge."""
    acc = []
    old_shape = {"results": [{"legislation_id": "asp/2018/9", "title": "An Act",
                              "url": "u", "status": "final", "year": 2018,
                              "extent": []}]}
    _extract_sources_inner("search_legislation", {}, old_shape, acc)
    assert acc[0]["meta"] == "final"


def test_the_search_block_says_what_the_text_version_is_not():
    """Unconditional on the productive branch, like every other limb of this
    block: a detector deciding whether *this* search is about currency would
    have to read the model's intent before the model has formed it."""
    slim = _slim_search_results(_api_search(("asp/2018/9", "An Act")))
    note = legislation_search_note({"query": "q"}, slim, {})
    assert "text_version" in note
    assert "NOT evidence" in note
    assert "get_legislation_changes" in note


# ---------------------------------------------------------------------------
# The title marker — a real signal, and an asymmetric one
# ---------------------------------------------------------------------------

def test_a_repeal_marker_in_the_title_is_surfaced_and_may_be_relied_on():
    """1.7% of rows (258 of 15,160, 43 distinct titles). Rare, and the one
    direction a lawyer must not miss.

    ~~2.0%, 256 of 12,640, 42 titles~~ was written from five of the seven
    replay directories before `lex_probe --inforce` walked all seven. Same
    lesson as Session 7's and Session 8's retractions: the figure behind the
    command wins over the figure behind the one-off script."""
    slim = _slim_search_results(_api_search(
        ("ukpga/1967/81", "Companies Act 1967 (repealed)"),
        ("asp/2018/9", "Social Security (Scotland) Act 2018"),
    ))
    note = currency_note({}, slim)
    assert "ukpga/1967/81" in note
    assert "repealed" in note
    assert "MAY rely on it" in note
    # And the other row is not thereby said to be in force.
    assert "asp/2018/9" not in note
    assert "absence of a marker" in note


def test_the_marker_carries_a_date_only_where_the_title_does():
    """8 of the 258 corpus rows with a marker carry a date after the keyword.
    So the date travels when it is there and is never invented when it is not."""
    dated = currency_note({}, _slim_search_results(
        _api_search(("ukpga/1964/82", "Education Act 1964 (repealed 1.11.1996)"))))
    assert "1.11.1996" in dated
    bare = currency_note({}, _slim_search_results(
        _api_search(("ukpga/1967/81", "Companies Act 1967 (repealed)"))))
    assert "date of repeal is not established" in bare


def test_no_marker_means_no_block_at_all():
    """98% of searches. A currency block on every page would be noise, and the
    standing warning already rides on the search block."""
    slim = _slim_search_results(_api_search(("asp/2018/9", "An Act")))
    assert currency_note({}, slim) == ""


def test_an_act_named_repeals_is_not_read_as_repealed():
    """Anchored to the opening parenthesis. "Statute Law (Repeals) Act 1998" is
    a title, not a status."""
    slim = _slim_search_results(_api_search(
        ("ukpga/1998/43", "Statute Law (Repeals) Act 1998")))
    assert currency_note({}, slim) == ""


# ---------------------------------------------------------------------------
# `Commencement Order` — the trap P3.5 left open
# ---------------------------------------------------------------------------

def test_the_two_commencement_effects_are_not_the_same_relation():
    assert _effect_is_commencement_of_subject("coming into force")
    assert not _effect_is_commencement_of_subject("Commencement Order")
    assert _effect_is_commencement_order("Commencement Order")
    assert not _effect_is_commencement_order("coming into force")


@pytest.mark.parametrize("effect", [
    "repealed", "words repealed", "word repealed", "repealed in part", "repeal",
    "entry repealed", "revoked", "repealed (1.1.1996)",
])
def test_the_repeal_family_is_matched_on_the_token_not_a_fixed_set(effect):
    """2,912 distinct effect strings over the sample and the repeal family spans
    at least eight spellings. A fixed set would silently miss the tail, and
    missing a repeal is the direction this row exists to stop."""
    assert _effect_is_repeal(effect)


@pytest.mark.parametrize("effect", [
    "coming into force", "Commencement Order", "words substituted", "inserted",
    "modified", None, "",
])
def test_nothing_else_is_read_as_a_repeal(effect):
    assert not _effect_is_repeal(effect)


def test_a_commencement_order_row_is_flagged_as_not_commencing_the_subject():
    """`ukpga/1998/46`'s real shape. The placeholder provision is the tell: the
    row is a commencement order for an amendment made by another Act, and
    `ssi/2001/81` — the Adults with Incapacity (Scotland) Act 2000
    (Commencement No. 1) Order 2001 — appears against `ukpga/1963/41` for
    exactly that reason."""
    slim = _slim_amendment_results(
        _rows(("specified amended provision(s)", "uksi/2001/566", "Commencement Order"),
              ("C/O", "ssi/2001/81", "Commencement Order")),
        "ukpga/1998/46", "to")
    assert slim["provisions_commenced"] == 0
    assert slim["commencement_orders_of_amendments"] == 2
    for g in slim["related"]:
        assert g["commences_this_legislation"] is False


def test_a_real_commencement_is_counted_as_one_and_carries_no_false_flag():
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2025/119", "coming into force"),
              ("s. 20", "ssi/2025/119", "coming into force")),
        "ukpga/1998/46", "to")
    assert slim["provisions_commenced"] == 2
    assert slim["commencement_orders_of_amendments"] == 0
    # Absent rather than True: the key is emitted only to deny, so a group
    # without it is not thereby asserted to commence anything.
    assert "commences_this_legislation" not in slim["related"][0]


def test_the_three_counts_are_separated_where_an_act_carries_all_of_them():
    """`asp/2000/4` has both classes — 35 real and 14 placeholder — so the split
    is not academic."""
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2001/81", "coming into force"),
              ("specified amended provision(s)", "uksi/2001/566", "Commencement Order"),
              ("s. 86", "ukpga/2011/1", "repealed"),
              ("s. 2(3)", "ukpga/2016/11", "words inserted")),
        "ukpga/1998/46", "to")
    assert slim["provisions_commenced"] == 1
    assert slim["commencement_orders_of_amendments"] == 1
    assert slim["repeal_or_revocation_relations"] == 1
    assert slim["relations"] == 4, "the http/https twins must still collapse"


def test_a_commencement_order_group_never_displaces_a_real_relation():
    """`ukpga/1998/46` has 29 of them at one row each against 857 relations, and
    `_MAX_RELATED_INSTRUMENTS` is 40. Sorted to the back with the
    self-referential groups: neither is an answer to "what commenced this"."""
    slim = _slim_amendment_results(
        _rows(("specified amended provision(s)", "uksi/2001/566", "Commencement Order"),
              ("specified amended provision(s)", "uksi/2004/829", "Commencement Order"),
              ("s. 9", "ssi/2025/119", "coming into force")),
        "ukpga/1998/46", "to")
    assert slim["related"][0]["legislation_id"] == "ssi/2025/119"


def test_the_block_forbids_naming_a_commencement_order_as_the_commencement():
    slim = _slim_amendment_results(
        _rows(("specified amended provision(s)", "uksi/2001/566", "Commencement Order")),
        "ukpga/1998/46", "to")
    note = amendment_search_note({"legislation_id": "ukpga/1998/46"}, slim)
    assert "are NOT" in note and "commencement order for" in note
    assert "Do NOT name any of those instruments" in note
    # And the empty-commencement branch fires alongside it, so the model is not
    # left to infer that a placeholder row filled the gap.
    assert "NO relation here is a `coming into force` relation" in note


def test_a_retrieved_commencement_is_still_permitted():
    """**The suppression check, and this row's real risk.** P3.5 made these
    retrievable; a fix that forbade the claim outright would drive the defect to
    zero by driving the sourced answer there too. Invariant 1, read backwards."""
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2025/119", "coming into force")), "asp/2025/2", "to")
    note = amendment_search_note({"legislation_id": "asp/2025/2"}, slim)
    assert "you may state them" in note
    assert "citing the instrument" in note


def test_the_whole_act_claim_is_forbidden_whatever_the_record_shows():
    for rows in (_rows(("s. 9", "ssi/2025/119", "coming into force")),
                 _rows(("specified amended provision(s)", "uksi/2001/566",
                        "Commencement Order")),
                 _rows(("s. 86", "ukpga/2011/1", "repealed"))):
        note = amendment_search_note(
            {"legislation_id": "x"}, _slim_amendment_results(rows, "x", "to"))
        assert "CANNOT establish that this legislation is in force as a whole" in note


# ---------------------------------------------------------------------------
# The report block — the one limb that speaks when it found nothing
# ---------------------------------------------------------------------------

def _log_from(*calls):
    log = []
    for name, args, data in calls:
        record_currency(log, name, args, data)
    return log


def test_the_limb_speaks_on_a_step_that_established_nothing():
    """The opposite gate from `_enabling_limb` and `_relations_limb`, and
    deliberate: a step that established nothing about currency is exactly the
    step whose report says *"all cited legislation is currently in force"*. The
    Manager writing that sentence has seen no tool result at all."""
    limb = _currency_limb([{"tool": "search_legislation", "query": "q",
                            "shown": 5, "matched": 141, "legislation_id": ""}])
    assert limb
    assert "could not be verified" in limb
    assert "NOTHING in this step establishes" in limb


def test_the_limb_names_what_was_retrieved_when_something_was():
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2025/119", "coming into force")), "asp/2025/2", "to")
    log = _log_from(("get_legislation_changes", {"legislation_id": "asp/2025/2"}, slim))
    log.append({"tool": "search_legislation", "query": "q", "shown": 5,
                "matched": 9, "legislation_id": ""})
    limb = _currency_limb(log)
    assert "Commencement relations WERE retrieved for asp/2025/2" in limb
    assert "carry no dates" in limb


def test_the_limb_carries_the_valid_date_as_a_text_version_date():
    """The honest substitute, available on the 18% of turns that reach Phase 3.
    A substitution rather than a silence is what keeps this fix on the right
    side of Invariant 1 — but it must never be offered as an in-force date."""
    text = {"legislation": {"id": "ukpga/1998/46", "valid_date": "2026-03-11",
                            "title": "Scotland Act 1998"}, "full_text": "..."}
    log = _log_from(("get_legislation_text", {"legislation_id": "ukpga/1998/46"}, text))
    limb = _currency_limb(log)
    assert "up to date to: ukpga/1998/46 to 2026-03-11" in limb
    assert "not an in-force date" in limb


def test_a_malformed_valid_date_is_dropped_rather_than_repeated():
    for bad in ("", None, "March 2026", "2026", "2026-3-1x"):
        log = _log_from(("get_legislation_text", {"legislation_id": "x"},
                         {"legislation": {"valid_date": bad}}))
        assert log == []


def test_a_step_that_touched_no_legislation_gets_no_limb():
    assert _currency_limb([]) == ""
    assert _currency_limb([{"tool": "search_case_law"}]) == ""


@pytest.mark.parametrize("data", [None, "", "not json", [], {"error": "boom"}, 7])
def test_record_currency_never_raises_on_a_shape_it_has_not_seen(data):
    """Invariant 5. A diagnostic must never be the reason a retrieval fails."""
    log = []
    for name in ("search_legislation", "get_legislation_changes",
                 "get_legislation_text", "search_case_law"):
        record_currency(log, name, {}, data)
    record_currency(None, "search_legislation", {}, data)


# ---------------------------------------------------------------------------
# The lawyer-facing clause, and the strip
# ---------------------------------------------------------------------------

def test_the_footer_clause_says_no_currency_check_was_run_when_none_was():
    """The thing 42 of 62 pre-pilot sessions could not have known, because the
    UI pill was telling them the opposite."""
    log = _log_from(("search_legislation", {},
                     _slim_search_results(_api_search(
                         ("ukpga/1967/81", "Companies Act 1967 (repealed)")))))
    clause = _currency_footer_clause(log)
    assert "not something this index reports" in clause
    assert "no change record was consulted" in clause
    assert "ukpga/1967/81" in clause


def test_the_footer_clause_says_what_was_checked_when_something_was():
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2025/119", "coming into force")), "asp/2025/2", "to")
    clause = _currency_footer_clause(
        _log_from(("get_legislation_changes", {"legislation_id": "asp/2025/2"}, slim)))
    assert "recorded changes for asp/2025/2" in clause
    assert "carry no dates" in clause


def test_a_turn_with_no_currency_evidence_gets_no_clause():
    """Gated on a structural fact, like every other clause on this footer. A
    prose detector in the product fails silently."""
    assert _currency_footer_clause([]) == ""
    assert _currency_footer_clause([{"tool": "search_legislation"}]) == ""


def test_the_currency_block_is_stripped_before_a_lawyer_sees_it():
    """`[CURRENCY …]` is an instruction to an agent, and in research mode the
    Manager is told to pass a Worker's report through verbatim. P2.3 shipped
    `[ENABLING POWER …]` with the strip un-widened and found it live; the test
    is written first here for that reason."""
    note = currency_note({}, _slim_search_results(
        _api_search(("ukpga/1967/81", "Companies Act 1967 (repealed)"))))
    assert note
    out, n = strip_scope_blocks("Here is the answer." + note)
    assert n == 1
    assert out == "Here is the answer."
    assert "CURRENCY" not in out


# ---------------------------------------------------------------------------
# The prompts — what the Status line may say, not whether it exists
# ---------------------------------------------------------------------------

def test_the_mandatory_section_survives():
    """**The obvious fix is a trap.** Telling the model to omit
    "Jurisdiction & Status" makes `_report_needs_reformat` judge the report
    malformed and spends an A4 reformat call re-adding the heading — which the
    model then fills with the same conflation. The heading stays; the permitted
    content changes."""
    assert "Jurisdiction & Status" in _REPORT_SECTIONS["legislation_only"]
    assert "Jurisdiction & Status" in _REPORT_SECTIONS["legislation_and_case_law"]
    for prompt in (WORKER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT_HYBRID,
                   DEEP_RESEARCH_SYNTHESIS_PROMPT):
        assert "Jurisdiction & Status" in prompt
        assert "Do NOT omit this section" in prompt


@pytest.mark.parametrize("name", ["WORKER_SYSTEM_PROMPT",
                                  "WORKER_SYSTEM_PROMPT_HYBRID",
                                  "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"])
def test_all_three_legislation_worker_prompts_carry_the_rule(name):
    """**Including the conversational one, and that is load-bearing.** It
    carried no in-force instruction at all — and `get_worker_system_prompt`
    returns it whenever `_chat_mode == "conversational"`, which is the mode
    session 6411 ran in when it answered *"Yes, the Scotland Act 1998 is in
    force"* and named a commencement order it had not retrieved. The site with
    no instruction was the site with the defect."""
    import src.prompts as P
    prompt = getattr(P, name)
    assert "IN-FORCE STATUS (whether legislation is current law)" in prompt
    assert "NEVER write a blanket currency claim" in prompt
    assert "`Commencement Order` is NOT" in prompt


def test_the_rule_does_not_forbid_a_sourced_statement():
    """P3.5 routes the Worker to `get_legislation_changes` for exactly these
    questions. A flat prohibition would fight it and suppress answers that are
    now properly sourced."""
    for prompt in (WORKER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT_HYBRID,
                   WORKER_SYSTEM_PROMPT_CONVERSATIONAL):
        assert "What you MAY state, citing the source" in prompt
        assert "get_legislation_changes" in prompt


def test_the_synthesis_prompt_governs_the_agent_that_never_sees_a_tool_result():
    """The DR synthesis holds step findings only, so it is told what a finding
    has to attribute before it may repeat a currency claim."""
    assert "attributes to a retrieved change record" in DEEP_RESEARCH_SYNTHESIS_PROMPT
    assert "not verified" in DEEP_RESEARCH_SYNTHESIS_PROMPT
    assert "Never write that all cited legislation is in force" \
        in DEEP_RESEARCH_SYNTHESIS_PROMPT


def test_the_case_law_prompt_is_deliberately_untouched():
    """`WORKER_SYSTEM_PROMPT_CASE_LAW` has a "Jurisdiction & Currency" section,
    but its currency is whether a judgment remains good law and it has no
    legislation tools. Recorded rather than left to look like an omission."""
    from src.prompts import WORKER_SYSTEM_PROMPT_CASE_LAW
    assert "IN-FORCE STATUS (whether legislation is current law)" \
        not in WORKER_SYSTEM_PROMPT_CASE_LAW
    assert "Jurisdiction & Currency" in WORKER_SYSTEM_PROMPT_CASE_LAW


# ---------------------------------------------------------------------------
# The instrument, validated in both directions on real corpus sentences
# ---------------------------------------------------------------------------
#
# Every MUST_ASSERT string below is an affirmative in-force assertion read by
# hand out of all 86 `in force` sentences in `wave1`; every MUST_NOT is a shape
# that has to stay uncounted. **On this work the measuring instrument has been
# wrong seventeen times across eight sessions and seven published numbers were
# retracted**, so a new detector is pinned in both directions before it is used.

MUST_ASSERT = [
    "*   **Status:** In force (revised).",
    "*   **Status:** The Climate Change (Scotland) Act 2009 is currently in force (revised).",
    "uk/ukpga/1986/45) applies to the United Kingdom and is currently in force (revised status).",
    "Status: Revised (In Force).",
    "*   All referenced legislation is currently in force.",
    "In force.",
    "In force (revised).",
    "In force (Stub/Revised).",
    "The relevant Acts are currently in force.",
    "26 of the 2015 Act) and is currently in force.",
    "*   **Status:** Revised (In force)",
    "(Status: In force / Revised)",
    "*   **Status:** The Social Security (Scotland) Act 2018 is on the statute book (Revised / In force).",
    "uk/id/ukpga/Eliz2/5-6/31) remains in force.",
    'The instrument is currently in force and its status is "revised".',
    "All retrieved SSIs and the UKSI are currently in force, with statuses recorded as either final or revised.",
    "Yes, the Scotland Act 1998 is in force.",
    "*   **In-Force Status:** All identified legislation is enacted and currently in force, with commencement dates ranging from 2013 to exit day.",
    "The identified Orders in Council are also in force (final/revised status).",
]

MUST_NOT = [
    # statutory text being quoted — the conditional use. 6335 t4 quotes
    # s. 252(2)(b) of the Insolvency Act 1986, and the old `IN_FORCE_CLAIM`
    # counts it.
    'Section 252(2)(b) mandates that while an interim order is in force, "no other '
    'proceedings, and no execution or other legal process, may be commenced".',
    "Regarding commencement, **Section 99** dictates that while certain administrative "
    "sections came into force the day after Royal Assent, **Section 85** comes into "
    "force on a day appointed.",
    "An order in force at the relevant time would have applied.",
    # negatives and qualified partials — the answer this row WANTS
    "The Care Reform (Scotland) Act 2025 is only partially in force.",
    "As of 15 September 2026, no commencement orders have been made, so the majority "
    "of the Act is not yet in force.",
    "The remaining sections of the Act are not yet recorded as having been commenced.",
    "Section 38 is no longer in force, having been repealed by SSI 2014/486.",
    # commencement dates — graded in their own column, not as assertions
    "The remaining provisions come into force on a day appointed by the Scottish "
    "Ministers by regulations.",
    "Section 95 came into force the day after Royal Assent (under Section 99(1)).",
    "The core reporting and accounting duties were brought into force on 1 July 2005.",
    "Sections 2, 9, 17, 20, 21, 22, and 23 were brought into force by SSI 2025/119.",
    "The revised text held shows that section 9 came into force on 10 May 2025.",
]


def _asserts(sentence: str) -> bool:
    from tools.replay_report import (
        _CUR_ASSERT, _CUR_FROM_VERSION, _CUR_NEGATED, _CUR_SUBORDINATE,
    )
    return bool(
        (_CUR_ASSERT.search(sentence)
         and not _CUR_NEGATED.search(sentence)
         and not _CUR_SUBORDINATE.search(sentence))
        or _CUR_FROM_VERSION.search(sentence)
    )


@pytest.mark.parametrize("sentence", MUST_ASSERT)
def test_the_detector_catches_every_assertion_in_the_corpus(sentence):
    assert _asserts(sentence)


@pytest.mark.parametrize("sentence", MUST_NOT)
def test_the_detector_counts_nothing_it_should_not(sentence):
    assert not _asserts(sentence)


def test_the_detector_does_not_read_the_products_own_new_wording():
    """The failure this work keeps repeating: P2.2's footer tripped
    `NEG_ASSERTED` and corrupted its own denominator; P2.3's first two drafts
    tripped two detectors. Every sentence this row emits into an answer is
    checked against the detector that reads it."""
    slim = _slim_amendment_results(
        _rows(("s. 9", "ssi/2025/119", "coming into force")), "asp/2025/2", "to")
    log = _log_from(("get_legislation_changes", {"legislation_id": "asp/2025/2"}, slim))
    for clause in (_currency_footer_clause(log),
                   _currency_footer_clause(_log_from(
                       ("search_legislation", {}, _slim_search_results(_api_search(
                           ("ukpga/1967/81", "Companies Act 1967 (repealed)")))))),
                   "in-force status was not verified — the legislation index does not "
                   "report it, and no commencement or repeal record was retrieved for "
                   "this instrument."):
        assert clause
        for sentence in re.split(r"(?<=[.!?])\s+", clause):
            assert not _asserts(sentence), sentence


def test_the_old_detector_is_left_byte_identical():
    """It produced the published 27 -> 30 series. Widening it would move a
    number already in `BASELINE.md`, which is the trap Session 8 recorded — so
    the new instrument sits alongside it and `cmd_currency` prints both. The old
    one is blind to the bare Status bullet, which is why `wave1` reads 43 turns
    on the new instrument and 30 on the old."""
    from tools.replay_report import IN_FORCE_CLAIM
    assert IN_FORCE_CLAIM.pattern == (
        r"\b(?:is|are|remains?|currently) (?:still )?in force"
        r"|\bin force (?:as (?:at|of)|on)\b|\bcurrently in force\b"
    )
    assert not IN_FORCE_CLAIM.search("*   **Status:** In force (revised).")
    assert _asserts("*   **Status:** In force (revised).")
