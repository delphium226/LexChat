"""P3.5 (bucket B3) — the relationship, retrieved rather than forbidden.

P2.3 forbade the unverified *made under* claim. This row is the other four
fifths of B3 and it runs the opposite way: commencement, amendment, repeal and
revocation **are** retrievable via `/amendment/search`, so the fix is a tool.

**Invariant 1 cuts both ways here, and that is what most of this file pins.**
P2.3's risk was over-claiming from nothing; P3.5's is over-claiming from
something. Three properties of the raw feed make a naive pass-through assert
things that are not true, and every one of them is a test below:

  * **35% of rows are http/https duplicates of one relation** — `asp/2025/2`
    returns 71 rows for 36 relations. A tool that counts rows says "15
    provisions commenced" where the truth is 8.
  * **`type_of_effect` is sometimes null** — labelled `"not stated"`, never
    dropped, and never described as a commencement.
  * **Commencement is frequently self-referential** — 28 of `asp/2025/2`'s 36
    relations are the Act commencing its own sections under s. 27, which is not
    commencement by regulation and is the literal question 6409 asked.

The live numbers quoted throughout are reproducible with
`python -m tools.lex_probe --commencement`.
"""

import json

import pytest

from src.agent.agent_shared import _worker_tool_key_arg
from src.agent.tools.lex import _provision_sort_key, _slim_amendment_results
from src.agent.tools.schemas import WORKER_TOOLS, get_worker_tools
from src.services.local_prompt_cache import CACHEABLE_TOOLS
from src.utils.search_scope import (
    amendment_search_note,
    answer_scope_footer,
    record_relations,
    strip_scope_blocks,
    worker_scope_block,
)
from src.utils.stopwatch import TimingCollector

TOOL = "get_legislation_changes"


def _row(changed="asp/2025/2", changed_prov="s. 9",
         affecting="ssi/2025/119", affecting_prov="reg. 2 sch.",
         effect="coming into force", scheme="http"):
    """One `/amendment/search` row, in the exact shape the API returns.

    `scheme` exists because the feed emits the same relation twice, once under
    each scheme, and the API's own `id` embeds it — so the twins are not equal
    by id and a dedupe keyed on it removes nothing.
    """
    base = f"{scheme}://www.legislation.gov.uk/id"
    return {
        "changed_legislation": changed,
        "changed_year": 2025,
        "changed_number": changed.split("/")[-1],
        "changed_url": f"{base}/{changed}",
        "changed_provision": changed_prov,
        "changed_provision_url": (
            f"{base}/{changed}/section/{changed_prov.split('. ')[-1]}"
            if changed_prov else None
        ),
        "affecting_legislation": affecting,
        "affecting_year": 2025,
        "affecting_number": affecting.split("/")[-1],
        "affecting_url": f"{base}/{affecting}",
        "affecting_provision": affecting_prov,
        "affecting_provision_url": f"{base}/{affecting}/regulation/2",
        "type_of_effect": effect,
        "id": f"changed-{base}/{changed}-prov-{changed_prov}-affecting-"
              f"{base}/{affecting}-prov-{affecting_prov}-type-{effect}",
        "ai_explanation": None,
        "ai_explanation_model": None,
        "ai_explanation_timestamp": None,
    }


# --- the slimmer ---------------------------------------------------------------

def test_the_response_is_a_bare_list_and_that_is_the_shape_it_arrives_in():
    """`/amendment/search` returns a top-level JSON array, not `{results: []}`.

    The same trap `_slim_section_results` already carries, and it is worth a
    test of its own: reading `.get("results")` off a list raises, and a slimmer
    that raises is a retrieval that goes missing.
    """
    out = _slim_amendment_results([_row()], "asp/2025/2", "to")
    assert out["relations"] == 1
    assert out["related"][0]["legislation_id"] == "ssi/2025/119"


def test_an_object_wrapped_response_is_handled_too():
    out = _slim_amendment_results({"results": [_row()]}, "asp/2025/2", "to")
    assert out["relations"] == 1


@pytest.mark.parametrize("payload", [None, "", 17, {"error": "boom"}])
def test_an_unexpected_shape_passes_through_untouched(payload):
    """A slimmer must never be the reason a retrieval goes missing."""
    assert _slim_amendment_results(payload, "asp/2025/2", "to") == payload


def test_http_and_https_twins_collapse_to_one_relation():
    """**The correction the handover into this row did not have.**

    `asp/2025/2` returns 71 rows for 36 relations; `asp/2018/9` 956 for 484.
    Measured over 6,738 rows on eight instruments: 35% duplicates, concentrated
    in the Scottish material. Counting rows would report roughly double, and
    "15 provisions commenced by SSI" would be 8.
    """
    rows = [_row(scheme="http"), _row(scheme="https")]
    out = _slim_amendment_results(rows, "asp/2025/2", "to")
    assert out["rows_returned"] == 2
    assert out["relations"] == 1
    assert out["duplicate_rows_collapsed"] == 1
    assert out["related"][0]["changed_provisions"] == ["s. 9"]


def test_the_surviving_url_is_https():
    """One spelling reaches the model, and it is the one the site serves."""
    out = _slim_amendment_results([_row(scheme="http")], "asp/2025/2", "to")
    assert out["related"][0]["url"].startswith("https://")


def test_a_null_effect_type_is_labelled_not_dropped():
    """19% of sampled rows carry no `type_of_effect`.

    Dropping them would make the tool the reason a real relation went missing;
    rendering them as a commencement would assert something the record does not
    say. So they are kept under an explicit label, and the block (tested below)
    forbids describing them as any particular kind of change.
    """
    out = _slim_amendment_results(
        [_row(effect=None), _row(changed_prov="s. 10", effect="coming into force")],
        "asp/2025/2", "to")
    assert out["effects"]["not stated"] == 1
    assert any(g["type_of_effect"] == "not stated" for g in out["related"])


def test_self_referential_commencement_is_separated_from_commencement_by_regulation():
    """28 of `asp/2025/2`'s 36 relations are the Act commencing itself under s. 27.

    6409 asked which sections had been commenced **by regulation**. A tool that
    does not separate the two answers that question wrongly in the direction
    that looks most convincing.
    """
    rows = [
        _row(changed_prov="s. 9", affecting="ssi/2025/119"),
        _row(changed_prov="s. 28", affecting="asp/2025/2", affecting_prov="s. 27(1)"),
        _row(changed_prov="s. 6", affecting="asp/2025/2", affecting_prov="s. 27(2)"),
    ]
    out = _slim_amendment_results(rows, "asp/2025/2", "to")
    assert out["by_other_legislation"] == 1
    assert out["by_this_legislation_itself"] == 2
    # And the instrument that actually commenced something is listed first.
    assert out["related"][0]["legislation_id"] == "ssi/2025/119"
    assert out["related"][0]["self"] is False
    assert out["related"][-1]["self"] is True


def test_direction_by_flips_the_grouping_side_only():
    """`changed_provision` is always what changed; `affecting_provision` always what did it.

    Only the grouping side moves, which is what lets one shape serve both
    directions — and getting it backwards would silently invert every answer.
    """
    row = _row(changed="asp/2018/9", changed_prov="s. 95",
               affecting="asp/2025/2", affecting_prov="s. 4")
    out = _slim_amendment_results([row], "asp/2025/2", "by")
    assert out["related"][0]["legislation_id"] == "asp/2018/9"
    assert out["related"][0]["changed_provisions"] == ["s. 95"]
    assert out["related"][0]["effected_by"] == ["s. 4"]
    assert "made BY asp/2025/2" in out["relations_are"]


def test_provisions_come_back_in_natural_order():
    """s. 2 before s. 10. The API returns them in no useful order, and a lawyer
    reading "s. 9, s. 21, s. 20, s. 17" cannot see what is commenced."""
    rows = [_row(changed_prov=p) for p in ("s. 21", "s. 2", "s. 10", "s. 9")]
    out = _slim_amendment_results(rows, "asp/2025/2", "to")
    assert out["related"][0]["changed_provisions"] == ["s. 2", "s. 9", "s. 10", "s. 21"]


def test_provision_sort_handles_schedule_paragraphs():
    """Numerals compare numerically within a series, and sections come before
    schedules — which is the order legislation itself is printed in, and falls
    out of comparing the text run ("s. " < "sch. ") before the digits."""
    labels = ["Sch. 6 para. 10", "Sch. 6 para. 2", "s. 10", "s. 2"]
    assert sorted(labels, key=_provision_sort_key) == [
        "s. 2", "s. 10", "Sch. 6 para. 2", "Sch. 6 para. 10"]


def test_a_long_provision_list_is_capped_and_says_how_many_it_dropped():
    from src.agent.tools import lex
    rows = [_row(changed_prov=f"s. {i}") for i in range(1, lex._MAX_CHANGED_PROVISIONS + 6)]
    out = _slim_amendment_results(rows, "asp/2025/2", "to")
    g = out["related"][0]
    assert len(g["changed_provisions"]) == lex._MAX_CHANGED_PROVISIONS
    assert g["changed_provisions_not_listed"] == 5
    # The count is of the whole group, not of what was listed.
    assert g["count"] == lex._MAX_CHANGED_PROVISIONS + 5


def test_a_long_instrument_list_is_capped_and_says_how_many_it_dropped():
    from src.agent.tools import lex
    n = lex._MAX_RELATED_INSTRUMENTS + 3
    rows = [_row(affecting=f"ssi/2020/{i}") for i in range(n)]
    out = _slim_amendment_results(rows, "asp/2025/2", "to")
    assert out["related_instruments"] == n
    assert len(out["related"]) == lex._MAX_RELATED_INSTRUMENTS
    assert out["related_instruments_not_listed"] == 3


# --- the tool-result block -----------------------------------------------------

def _slim(rows, lid="asp/2025/2", direction="to", complete=True):
    out = _slim_amendment_results(rows, lid, direction)
    out["window_complete"] = complete
    if not complete:
        out["window_size"] = 2000
    return json.dumps(out)


def test_the_block_permits_the_relation_and_forbids_the_two_things_it_lacks():
    note = amendment_search_note(
        {"legislation_id": "asp/2025/2"},
        _slim([_row(), _row(changed_prov="s. 20")]))
    assert "CHANGE RECORD" in note
    assert "you MAY state a relation listed here" in note
    # A relation row carries no date and no enabling power. Both are claims a
    # retrieved relation invites and neither is in the data.
    assert "no DATE on any relation" in note
    assert "made-under relation" in note


def test_the_block_names_the_self_referential_split():
    rows = [
        _row(changed_prov="s. 9", affecting="ssi/2025/119"),
        _row(changed_prov="s. 28", affecting="asp/2025/2", affecting_prov="s. 27(1)"),
    ]
    note = amendment_search_note({"legislation_id": "asp/2025/2"}, _slim(rows))
    assert "1 of them are marked `self: true`" in note
    assert "NOT commencement by regulation" in note


def test_the_block_names_the_unstated_effect_rows():
    note = amendment_search_note({"legislation_id": "asp/2025/2"},
                                 _slim([_row(effect=None)]))
    assert "not stated" in note
    assert "Do not describe those as a commencement" in note


def test_an_empty_change_record_is_an_honest_negative_not_a_finding():
    """Invariant 1. 113 of the 272 legislation_ids the replay corpus touched have
    no recorded relation at all, so this branch is common — and the difference
    between "nothing is recorded" and "nothing happened" is the whole of B5."""
    note = amendment_search_note({"legislation_id": "ukpga/1962/47"}, _slim([]))
    assert "no commencement, amendment, repeal or revocation relation is recorded" in note
    assert "NOT proof" in note
    assert "you MAY state" not in note


def test_a_truncated_window_says_so():
    """P1.3's lesson. `size` truncates silently and the API reports no total, so
    a cap-bound list must never be presented as exhaustive."""
    note = amendment_search_note(
        {"legislation_id": "ukpga/2010/15"},
        _slim([_row(affecting=f"ssi/2020/{i}") for i in range(3)], complete=False))
    assert "TRUNCATED at 2000 rows" in note
    assert "not be present" not in note
    assert "NOT complete" in note


@pytest.mark.parametrize("data", ["", "not json", json.dumps({"error": "boom"}), None])
def test_a_failed_retrieval_produces_no_block(data):
    assert amendment_search_note({"legislation_id": "asp/2025/2"}, data) == ""


def test_the_block_never_reaches_the_lawyer():
    """The strip had to be widened for this block, and forgetting that is a live
    defect: P2.3's `[ENABLING POWER]` block was not matched by `_TOOL_BLOCK`
    until the test that caught it was written."""
    note = amendment_search_note({"legislation_id": "asp/2025/2"}, _slim([_row()]))
    out, n = strip_scope_blocks("Here is the answer." + note)
    assert n == 1
    assert out == "Here is the answer."
    assert "CHANGE RECORD" not in out


# --- the record, the report block and the footer -------------------------------

def _record(rows, lid="asp/2025/2", complete=True):
    log = []
    record_relations(log, TOOL, {"legislation_id": lid}, _slim(rows, lid, complete=complete))
    return log


def test_the_record_carries_the_instruments_the_relation_names():
    log = _record([_row(), _row(changed_prov="s. 18", affecting="ssi/2025/377")])
    assert log[0]["tool"] == "change_record"
    assert log[0]["others"] == ["ssi/2025/119", "ssi/2025/377"]
    assert log[0]["by_other"] == 2


def test_a_self_referential_only_record_names_no_other_instrument():
    log = _record([_row(affecting="asp/2025/2", affecting_prov="s. 27(1)")])
    assert log[0]["others"] == []
    assert log[0]["by_other"] == 0


@pytest.mark.parametrize("data", [None, "", "{", [], {"x": 1}, 17])
def test_recording_never_raises_on_anything(data):
    log = []
    record_relations(log, TOOL, {"legislation_id": "asp/2025/2"}, data)
    record_relations(None, TOOL, {}, data)
    record_relations(log, "search_legislation", {}, data)


def test_the_report_block_carries_the_relation_to_the_agent_that_writes_the_answer():
    """The Manager holding a `delegate_research` result, and the Deep Research
    synthesis holding a step's findings, never see a tool result — and they are
    the agents that write "no commencement regulations have been made"."""
    log = _record([_row()])
    log.append({"tool": "search_legislation", "query": "Care Reform",
                "legislation_id": "", "shown": 5, "matched": 141})
    block = worker_scope_block(log, {})
    assert "Change record" in block
    assert "ssi/2025/119" in block
    assert "you MAY state those" in block


def test_the_report_block_says_when_the_change_record_was_empty():
    log = _record([], lid="asp/2025/9")
    log.append({"tool": "search_legislation", "query": "Care Reform",
                "legislation_id": "", "shown": 5, "matched": 141})
    block = worker_scope_block(log, {})
    assert "NO relation is recorded for asp/2025/9" in block
    assert "NOT as a finding that no commencement" in block


def test_a_step_that_consulted_no_change_record_says_nothing_about_one():
    """Gated for the same reason `_enabling_limb` is: a sentence about a thing
    that cannot arise is noise, and noise is what gets a block ignored."""
    log = [{"tool": "search_legislation", "query": "q", "legislation_id": "",
            "shown": 5, "matched": 10}]
    assert "Change record" not in worker_scope_block(log, {})


def test_the_footer_tells_the_lawyer_where_the_relation_came_from():
    log = _record([_row()])
    log.append({"tool": "search_legislation", "query": "Care Reform",
                "legislation_id": "", "shown": 5, "matched": 141})
    footer = answer_scope_footer(log, {})
    assert "recorded changes for asp/2025/2" in footer
    assert "carry no dates" in footer


def test_the_footer_distinguishes_an_empty_record_from_an_absent_change():
    log = _record([], lid="asp/2025/9")
    log.append({"tool": "search_legislation", "query": "Care Reform",
                "legislation_id": "", "shown": 5, "matched": 141})
    footer = answer_scope_footer(log, {})
    assert "list nothing in the direction consulted" in footer
    assert "weaker statement than the change never having been made" in footer


def test_a_turn_that_consulted_no_change_record_gets_no_clause():
    log = [{"tool": "search_legislation", "query": "q", "legislation_id": "",
            "shown": 5, "matched": 10}]
    assert "recorded changes" not in answer_scope_footer(log, {})


def test_the_footer_clause_trips_no_detector():
    """**P2.2's footer corrupted P2.2's own denominator, and P2.3's first two
    drafts tripped both detectors in turn.** This clause contains the words
    "commencement", "amendment" and "nothing", so it is checked against every
    detector that reads these answers — including the one added for this row.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.utils.search_scope import _relations_footer_clause
    from tools.replay_report import (NEG_ASSERTED, _CMC_DENIED, _without_footer,
                                     derivation_claims)

    for rows, lid in (([_row()], "asp/2025/2"), ([], "asp/2025/9")):
        log = _record(rows, lid=lid)
        clause = _relations_footer_clause(log)
        assert clause
        assert not NEG_ASSERTED.search(clause)
        assert not _CMC_DENIED.search(clause)
        assert derivation_claims(clause)[0] == []

    # And the whole footer is stripped before either detector sees an answer.
    log = _record([_row()])
    log.append({"tool": "search_legislation", "query": "Care Reform",
                "legislation_id": "", "shown": 5, "matched": 141})
    answer = "The Act was commenced in part." + answer_scope_footer(log, {})
    assert _without_footer(answer).strip() == "The Act was commenced in part."


# --- wiring: efficiency, cache, tool set, prompts -------------------------------

def test_the_two_directions_are_not_a_redundant_refetch():
    """`legislation_id` alone would make "what commenced this" and "what this
    commences" the same call. On the legislation profile `max_redundant_tool_calls`
    is 0, so that would write an EFFICIENCY breach for correct behaviour."""
    to = _worker_tool_key_arg({"legislation_id": "asp/2025/2", "direction": "to"})
    by = _worker_tool_key_arg({"legislation_id": "asp/2025/2", "direction": "by"})
    assert to != by

    tc = TimingCollector("r")
    tc.record_worker_tool(TOOL, to)
    tc.record_worker_tool(TOOL, by)
    assert tc.redundant_tool_calls == 0
    tc.record_worker_tool(TOOL, to)
    assert tc.redundant_tool_calls == 1


def test_the_other_tools_key_on_the_legislation_id_exactly_as_before():
    assert _worker_tool_key_arg({"legislation_id": "asp/2025/2"}) == "asp/2025/2"
    assert _worker_tool_key_arg({"meeting_id": "1", "iob_id": "2"}) == "1:2"


def test_the_change_record_is_counted_but_deliberately_unclassified_by_phase():
    """A change record is neither a discovery search nor primary text.

    Classifying it Phase 2 would raise `phase2_retrieval_calls` without raising
    `sources_kept` — the legislation profile's fan-out denominator — so a correct
    relationship lookup would push requests toward the `fanout_ratio` breach and
    move every efficiency number published in Waves 0-2. The work stays visible
    in `worker_tool_calls`; only the phase split abstains. Same treatment, and
    same reasoning, as `get_member_info`.
    """
    tc = TimingCollector("r")
    tc.record_worker_tool(TOOL, "asp/2025/2:to")
    assert tc.worker_tool_calls == 1
    assert tc.phase1_search_calls == 0
    assert tc.phase2_retrieval_calls == 0
    assert tc.distinct_legislation_ids_retrieved == 0


def test_the_change_record_may_enter_the_shared_cache_and_drafting_guidance_may_not():
    """The allowlist exists to force a deliberate call. `/amendment/search` takes
    a legislation_id and a direction and returns published statutory data — no
    user content on either side."""
    assert TOOL in CACHEABLE_TOOLS
    assert "search_drafting_guidance" not in CACHEABLE_TOOLS


def test_the_tool_is_offered_in_every_mode_that_has_the_legislation_tools():
    names = {t["function"]["name"] for t in WORKER_TOOLS}
    assert TOOL in names
    for mode in ("legislation_only", "legislation_and_case_law"):
        assert TOOL in {t["function"]["name"] for t in get_worker_tools(mode)}
    for mode in ("case_law_only", "parliamentary_records", "westminster_records"):
        assert TOOL not in {t["function"]["name"] for t in get_worker_tools(mode)}


def test_the_direction_argument_is_an_enum_the_model_cannot_invent():
    schema = next(t for t in WORKER_TOOLS if t["function"]["name"] == TOOL)
    props = schema["function"]["parameters"]["properties"]
    assert props["direction"]["enum"] == ["to", "by"]
    assert schema["function"]["parameters"]["required"] == ["legislation_id"]


def test_every_legislation_worker_prompt_carries_the_routing_rule():
    """Three prompts, and the case-law one deliberately not — it has no
    legislation tools, so the rule would be an instruction about a tool the
    model does not hold. Verified against the prompts themselves rather than by
    grepping, for the reason the suggestions rules are."""
    from src.prompts import (WORKER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT_CASE_LAW,
                             WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
                             WORKER_SYSTEM_PROMPT_HYBRID)
    for p in (WORKER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT_HYBRID,
              WORKER_SYSTEM_PROMPT_CONVERSATIONAL):
        assert TOOL in p
        assert "NEVER write that no commencement regulations have been made" in p
        # P2.3's rule is still there and still separate.
        assert "ENABLING POWER" in p
    assert TOOL not in WORKER_SYSTEM_PROMPT_CASE_LAW


def test_both_search_blocks_route_a_relationship_question_to_the_tool():
    """The seam where the false negative actually forms. 6409 turn 5 concluded
    "no commencement regulations have been made yet" after five searches and one
    section search; 6410 turn 1 concluded it from the Act's own s. 39."""
    from src.utils.search_scope import legislation_search_note, section_search_note
    search = legislation_search_note(
        {"query": "Care Reform"},
        {"results": [{"legislation_id": "asp/2025/9"}], "returned": 1,
         "total": 141, "total_matched": 141}, {})
    section = section_search_note(
        {"query": "commencement", "legislation_id": "asp/2025/9"},
        {"results": [{"legislation_id": "asp/2025/9"}], "returned": 1})
    for note in (search, section):
        assert TOOL in note
        assert "do NOT conclude anything about them from these rows" in note


# --- the acceptance detector ---------------------------------------------------

def test_the_detector_reads_the_measured_false_negative():
    from tools.replay_report import commencement_verdict
    verdict, named, denials = commencement_verdict(
        "6410", "No commencement regulations have been made yet for the "
                "Care Reform (Scotland) Act 2025.")
    assert verdict == "false"
    assert named == [] and len(denials) == 1


def test_the_detector_does_not_grade_a_true_statement_about_provisions_as_a_defect():
    """Twenty of `asp/2025/2`'s twenty-eight sections really are uncommenced.

    Counting "the remaining provisions have not yet been brought into force" as
    a defect would push the model to hedge a correct statement — the regression
    Invariant 1 exists to prevent, and exactly how P2.2's first `NEG_ASSERTED`
    failed at 100%.
    """
    from tools.replay_report import commencement_verdict
    for true_sentence in (
        "The remaining provisions have not yet been brought into force.",
        "Sections 24 to 28 came into force on the day after Royal Assent.",
        "The remaining provisions come into force on a day appointed by the "
        "Scottish Ministers by regulations.",
    ):
        assert commencement_verdict("6409", true_sentence)[0] == "silent"


def test_the_detector_credits_a_named_commencing_instrument_in_any_spelling():
    from tools.replay_report import commencement_verdict
    for spelling in ("ssi/2025/119", "SSI 2025/119", "S.S.I. 2025/119",
                     "the Commencement No. 1 Regulations 2025 (SSI 2025/119)"):
        verdict, named, _ = commencement_verdict(
            "6409", f"Sections 2, 9 and 17 were commenced by {spelling}.")
        assert verdict == "correct", spelling
        assert named == ["ssi/2025/119"]


def test_a_halt_attributed_negative_is_neither_a_pass_nor_the_defect():
    """P2.1 owns that failure. Booking it here would let this row take credit
    for a fix it did not make — and 6409 turn 6 is exactly that answer."""
    from tools.replay_report import commencement_verdict
    verdict, _, _ = commencement_verdict(
        "6409", "No commencement regulations were found, as the research "
                "process was halted prior to completion.")
    assert verdict == "limited"


def test_the_attribution_excuse_does_not_survive_actually_holding_the_record():
    """If the turn called the tool and the record named a commencing instrument,
    a denial is a plain defect however politely it is hedged."""
    from tools.replay_report import commencement_verdict
    verdict, _, _ = commencement_verdict(
        "6409", "No commencement regulations were found, as the research "
                "process was halted prior to completion.",
        consulted_others=["ssi/2025/119"])
    assert verdict == "false"


def test_a_session_with_no_verified_ground_truth_is_never_graded():
    from tools.replay_report import commencement_verdict
    assert commencement_verdict(
        "9999", "No commencement regulations have been made yet.")[0] == "silent"


# --- the fetch: past the cap, or say so ----------------------------------------

def _amendment_client(monkeypatch, sizes_to_rows):
    """Stub `_request_with_retry` and record the `size` each call asked for.

    Stubbed at the retry helper rather than at the transport because the branch
    under test makes TWO requests and the assertion is about the second one
    happening (or not), which is easier to read as a list of sizes than as a
    transport script.
    """
    import httpx

    from src.agent.tools import executor

    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        size = kwargs["json"]["size"]
        asked.append(size)
        return httpx.Response(200, json=sizes_to_rows(size),
                              request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def _run(args):
    import asyncio

    from src.agent.tools.executor import execute_worker_tool
    return json.loads(asyncio.run(execute_worker_tool(TOOL, args)))


def test_a_complete_record_is_fetched_once(monkeypatch):
    asked = _amendment_client(monkeypatch, lambda size: [_row()])
    out = _run({"legislation_id": "asp/2025/2", "direction": "to"})
    assert asked == [2000]
    assert out["window_complete"] is True
    assert "window_size" not in out


def test_a_cap_bound_record_is_refetched_past_the_cap(monkeypatch):
    """**P1.3's defect, not repeated.** `size` truncates silently and the
    response carries no count field of any kind, so exactly `size` rows can only
    mean the cap bound. Measured over the legislation_ids the replay corpus
    touched, 13 (4.8%) exceed 2,000 and every one of them completes at the
    escalated size."""
    from src.agent.tools import executor

    def rows(size):
        return [_row(changed_prov=f"s. {i}") for i in range(min(size, 3000))]

    asked = _amendment_client(monkeypatch, rows)
    out = _run({"legislation_id": "ukpga/2010/15"})
    assert asked == [executor._AMENDMENT_FETCH_SIZE,
                     executor._AMENDMENT_ESCALATED_SIZE]
    assert out["window_complete"] is True
    assert out["relations"] == 3000


def test_a_second_bind_is_reported_rather_than_chased(monkeypatch):
    """Never observed live — the largest instrument in the corpus is 13,681 rows
    — but a window that cannot be closed must be stated, not hidden, and the
    block says so to the model."""
    from src.agent.tools import executor

    asked = _amendment_client(
        monkeypatch, lambda size: [_row(changed_prov=f"s. {i}") for i in range(size)])
    out = _run({"legislation_id": "ukpga/1988/1"})
    assert asked == [executor._AMENDMENT_FETCH_SIZE,
                     executor._AMENDMENT_ESCALATED_SIZE]
    assert out["window_complete"] is False
    assert out["window_size"] == executor._AMENDMENT_ESCALATED_SIZE
    assert "TRUNCATED" in amendment_search_note({"legislation_id": "ukpga/1988/1"},
                                                json.dumps(out))


def test_the_direction_argument_maps_onto_the_api_flag(monkeypatch):
    import httpx

    from src.agent.tools import executor

    seen = []

    async def fake(client, method, url, *, name="", **kwargs):
        seen.append(kwargs["json"])
        return httpx.Response(200, json=[], request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    _run({"legislation_id": "asp/2025/2", "direction": "by"})
    assert seen[0]["search_amended"] is False
    seen.clear()
    _run({"legislation_id": "asp/2025/2", "direction": "to"})
    assert seen[0]["search_amended"] is True


def test_an_unrecognised_direction_falls_back_to_the_common_one_and_says_which(monkeypatch):
    """Erroring would spend a tool-call round to tell the model something the
    enum already told it. The fallback is the direction that answers the common
    question, and the result states in plain words which direction it is — so a
    model that meant the other one can see that it did not get it."""
    _amendment_client(monkeypatch, lambda size: [_row()])
    out = _run({"legislation_id": "asp/2025/2", "direction": "sideways"})
    assert out["direction"] == "to"
    assert "made TO asp/2025/2" in out["relations_are"]


# --- the References rail --------------------------------------------------------

def _sources(rows, lid="asp/2025/2"):
    from src.agent.agent_shared import _extract_sources_from_tool
    acc = []
    _extract_sources_from_tool(TOOL, {"legislation_id": lid}, _slim(rows, lid), acc)
    return acc


def test_a_commencing_instrument_can_reach_the_references_rail():
    acc = _sources([_row(), _row(changed_prov="s. 18", affecting="ssi/2025/377")])
    assert [s["_lid"] for s in acc] == ["ssi/2025/119", "ssi/2025/377"]
    assert acc[0]["url"] == "https://www.legislation.gov.uk/id/ssi/2025/119"


def test_a_related_instrument_carries_no_excerpt_so_only_cited_ones_survive():
    """`_source_is_used` keeps a source unconditionally when it has an excerpt.

    The change record establishes that this instrument commenced something; it
    does not mean its text was read. An excerpt here would pin every related
    instrument into the rail whether or not the answer cited it — overstating
    the research and inflating `sources_kept`, the legislation profile's fan-out
    denominator.
    """
    from src.agent.agent_core import _source_is_used
    acc = _sources([_row()])
    assert not acc[0].get("excerpt")
    assert _source_is_used(acc[0], "Sections 2 and 9 were commenced by ssi/2025/119.")
    assert not _source_is_used(acc[0], "The Act is partly in force.")


def test_the_act_commencing_itself_is_not_offered_as_a_separate_source():
    acc = _sources([_row(affecting="asp/2025/2", affecting_prov="s. 27(1)")])
    assert acc == []


def test_the_subject_acts_own_url_comes_from_the_feed():
    """P1.6 demotes an unverified provision link to the Act only when the Act's
    URL was returned by a tool, so the subject's own URL has to be in the
    result — and it is the feed's, never composed."""
    out = _slim_amendment_results([_row(scheme="http")], "asp/2025/2", "to")
    assert out["url"] == "https://www.legislation.gov.uk/id/asp/2025/2"


def test_a_denial_of_the_REMAINDER_is_the_right_answer_not_the_defect():
    """**Found by the acceptance run, and correcting it did not move a
    before-column number.**

    6410 rep 2 turn 2 answered *"SSI 2025/388 … Based on the recorded changes to
    the Act, no further commencement regulations have been found"* — true,
    sourced, and exactly the answer this row exists to produce: the change
    record holds precisely one commencing instrument. Grading it as the defect
    would punish the fix.
    """
    from tools.replay_report import commencement_verdict
    for sentence in (
        "SSI 2025/388 has been made. Based on the recorded changes to the Act, "
        "no further commencement regulations have been found.",
        "SSI 2025/388 commenced several sections. No subsequent commencement "
        "regulations have been recorded for the Act.",
    ):
        assert commencement_verdict("6410", sentence)[0] == "correct"


def test_a_qualifier_attached_to_the_WRONG_NOUN_is_still_a_flat_denial():
    """The exclusion is scoped to the noun phrase, and this is why.

    `wave2_p22` 6409 rep 3 turn 6 says *"no commencement regulations bringing
    FURTHER sections into force were identified"* — "further" attaches to
    *sections*, and the sentence denies that any commencing regulation was
    found. A bare `\bfurther\b` anywhere in the sentence would have dropped it,
    moving a BEFORE-column number to make the after-column look better.
    """
    from tools.replay_report import commencement_verdict
    verdict, _, denials = commencement_verdict(
        "6409",
        "Sections 24 to 28 came into force automatically the day after Royal "
        "Assent, but no commencement regulations bringing further sections into "
        "force were identified in the completed portion of this research.")
    assert verdict == "false"
    assert len(denials) == 1


def test_a_remainder_denial_naming_nothing_is_still_graded():
    """A remainder is only a remainder of something. An answer that denies
    "further" instruments while naming none has not delivered the relation."""
    from tools.replay_report import commencement_verdict
    assert commencement_verdict(
        "6410", "No further commencement regulations have been made.")[0] == "false"
