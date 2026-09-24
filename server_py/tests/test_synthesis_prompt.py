"""FIX_PLAN P4.7 (absorbing docs/TODO.md D17): the Deep Research synthesis
prompt, built per research type.

It used to be one constant for every type. Its model gap sentence was
"No reported case law was found on X", and the synthesis was told only the
plan's free-text scope note, so a 'Legislation only' report was scripted to
present a source it never searched as searched and empty. Its section list
was the legislation Worker's, so a Holyrood or Westminster report was told to
write a territorial-extent and in-force section (D17 item 2).

These tests are the row's deterministic half, and the only evidence for
D17 item 2: the replay harness replays the legislation bot's export and has
never run the parliament bot, so no stored payload exists for it.
"""

import pytest

from src import prompts
from src.agent import agent_core
from src.agent.agent_core import build_synthesis_messages, run_deep_research
from src.agent.provider_factory import set_request_provider_config
from src.prompts import REPORT_SECTIONS, get_deep_research_synthesis_prompt as synth

TYPES = sorted(REPORT_SECTIONS)
PARLIAMENTARY = ("parliamentary_records", "westminster_records")
LEGISLATION_BEARING = ("legislation_only", "legislation_and_case_law")


def test_every_research_type_has_a_prompt():
    assert set(TYPES) == {"legislation_only", "case_law_only", "legislation_and_case_law",
                          "parliamentary_records", "westminster_records"}


# --- the section list is the type's, from the one definition ---------------


def test_the_reformat_check_and_the_synthesis_read_one_definition():
    assert agent_core._REPORT_SECTIONS is REPORT_SECTIONS


@pytest.mark.parametrize("rm", TYPES)
def test_the_prompt_asks_for_the_types_own_sections_in_order(rm):
    p = synth(rm)
    positions = [p.index(f"{i}. **{name}:**")
                 for i, name in enumerate(REPORT_SECTIONS[rm], 1)]
    assert positions == sorted(positions)
    assert f"{len(REPORT_SECTIONS[rm]) + 1}. **" not in p


@pytest.mark.parametrize("rm", PARLIAMENTARY)
def test_a_parliamentary_report_has_no_extent_or_in_force_section(rm):
    """D17 item 2: the Holyrood and Westminster reports were told to write a
    territorial-extent and in-force section."""
    p = synth(rm)
    assert "Jurisdiction & Status" not in p
    assert "Territorial extent" not in p
    assert "Do NOT omit this section" not in p
    assert "Summary (BLUF)" in p


def test_the_legislation_sections_are_unchanged():
    p = synth("legislation_only")
    for name in ("Summary Answer (BLUF)", "Detailed Analysis", "Jurisdiction & Status",
                 "References"):
        assert f"**{name}:**" in p
    assert "Do NOT omit this section" in p


# --- Invariant 1: what every type must keep ---------------------------------


@pytest.mark.parametrize("rm", TYPES)
def test_every_type_keeps_citation_preservation_and_the_pinpoint_rule(rm):
    """P3.1: the synthesis rewrote every subsection label to the bare section."""
    p = synth(rm)
    assert "CITATION PRESERVATION" in p
    assert "A pinpoint stays a pinpoint" in p
    assert "Never shorten it to s.12." in p


@pytest.mark.parametrize("rm", TYPES)
def test_every_type_keeps_p25s_currency_rules(rm):
    """In Jurisdiction & Status where the type has that section, as a rule
    otherwise: a report on debates or judgments can still say an Act is in
    force."""
    p = synth(rm)
    assert "attributes to a retrieved change record" in p
    assert "not verified" in p
    assert "Never write that all cited legislation is in force" in p
    if rm in LEGISLATION_BEARING:
        assert "**Jurisdiction & Status:** Territorial extent" in p
    else:
        assert "- IN-FORCE STATUS:" in p


@pytest.mark.parametrize("rm", TYPES)
def test_every_type_keeps_links_as_links(rm):
    """Found on the seam (Session 26): with the first per-type wording, one
    payload (6408) wrote its references as bare URLs in 2 of 4 draws, against
    0 of 4 before."""
    assert "never turn a link into a bare URL or into plain text" in synth(rm)


@pytest.mark.parametrize("rm", TYPES)
def test_every_type_carries_the_deep_research_fingerprint(rm):
    """`replay_set` reads '**Key findings' as the Deep Research marker, and the
    P0.5 mode evidence rests on it. The label is named as a label because the
    first per-type wording lost it on a hybrid payload in 2 of 4 draws."""
    p = synth(rm)
    assert "**Key findings**" in p
    assert "under that bold label" in p


# --- the gap wording ---------------------------------------------------------


@pytest.mark.parametrize("rm", TYPES)
def test_no_type_scripts_a_case_law_negative(rm):
    p = synth(rm)
    assert "No reported case law was found" not in p
    assert "no reported case law" not in p.lower()


@pytest.mark.parametrize("rm", TYPES)
def test_every_type_describes_a_gap_by_what_happened(rm):
    """Thomas's wording: excluded is not searched, failed did not complete, and
    only a completed search finds nothing, only in what it searched."""
    p = synth(rm)
    assert "NOT SEARCHED" in p
    assert "DID NOT COMPLETE" in p
    assert "Only a completed search can find nothing, and only in the sources it searched" in p
    assert "retrieved in this research do" in p   # the type's gap sentence


@pytest.mark.parametrize("rm,unsearched", [
    ("legislation_only", "case law"),
    ("case_law_only", "the text of legislation"),
    ("parliamentary_records", "case law"),
    ("westminster_records", "case law"),
])
def test_the_prompt_names_what_the_type_did_not_search(rm, unsearched):
    p = synth(rm)
    line = next(ln for ln in p.splitlines() if ln.startswith("It did NOT search"))
    assert unsearched in line


def test_the_hybrid_prompt_claims_nothing_unsearched():
    p = synth("legislation_and_case_law")
    assert "did NOT search" not in p
    assert "court judgments" in p and "UK legislation" in p


# --- fall-through and the old name -------------------------------------------


@pytest.mark.parametrize("rm", ["drafting", "", "no_such_type"])
def test_an_unknown_type_falls_through_to_legislation_only(rm):
    """As `_REPORT_SECTIONS.get(..., legislation_only)` does. 'drafting' has no
    Worker on this branch."""
    assert synth(rm) == synth("legislation_only")


def test_the_old_constant_is_the_legislation_prompt():
    assert prompts.DEEP_RESEARCH_SYNTHESIS_PROMPT == synth("legislation_only")


# --- the research type reaches the synthesis call ----------------------------


@pytest.mark.parametrize("rm", TYPES)
def test_the_builder_uses_the_research_type_it_is_given(rm):
    msgs = build_synthesis_messages("q", {"scope_note": "s"},
                                    [{"title": "t", "detail": "d", "content": "c"}],
                                    research_mode=rm)
    assert msgs[0] == {"role": "system", "content": synth(rm)}


def test_the_builder_defaults_to_legislation_only():
    msgs = build_synthesis_messages("q", {}, [{"title": "t", "detail": "d", "content": "c"}])
    assert msgs[0]["content"] == synth("legislation_only")


@pytest.mark.asyncio
@pytest.mark.parametrize("rm", ["parliamentary_records", "legislation_and_case_law"])
async def test_run_deep_research_hands_the_requests_type_to_the_synthesis(rm):
    set_request_provider_config({"_provider": "ollama", "_chat_mode": "deep_research",
                                 "_research_mode": rm, "model": "m"})
    captured = {}

    async def worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        return {"content": "Finding.", "sources": []}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        captured["system"] = messages[0]["content"]
        return {"role": "assistant", "content": "Report."}

    try:
        await run_deep_research(
            chat_loop, worker,
            {"scope_note": "s", "steps": [{"id": 1, "title": "t", "detail": "d"}]},
            [{"role": "user", "content": "q"}], "m", None, None, 0)
    finally:
        set_request_provider_config({})
    assert captured["system"] == synth(rm)
