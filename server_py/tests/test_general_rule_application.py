"""FIX_PLAN P3.17 (B11): a general rule is retrieved by its application
provision, not only by its definition.

Measured on the stored sweeps before this phase existed: when the brief asked
what a word means in an instrument, the quick-lookup Worker searched only that
instrument, found the word undefined and wrote its report, so no general
interpretation legislation was ever retrieved on the first turn. Where such
legislation WAS retrieved, a section search for the defined word returned its
definitions schedule and never the section saying which instruments it applies
to, and every such report said the wrong legislation applied; a section search
for "application" returned the application section every time.

PHASE 2c is a prompt lever (the row offered code or prompt; the seam has no
deterministic trigger for "the word is undefined" that code could act on, see
the batch note). These tests pin its shape: present in the quick-lookup Worker
for every research type that reaches it, conditional, generic (it names no
instrument, so it cannot steer a brief to one), absent from the research
Workers and from every Manager prompt (the first-delegation drift guard).
"""

import re

import pytest

from src import prompts
from src.prompts import get_manager_system_prompt, get_worker_system_prompt

CONV = {"_chat_mode": "conversational"}
RESEARCH_TYPES = ("legislation_only", "legislation_and_case_law", "case_law_only")


def _phase(text: str) -> str:
    """The PHASE 2c block of a Worker prompt ('' when absent)."""
    m = re.search(r"PHASE 2c\b.*?(?=\n\nSYNTHESISE IMMEDIATELY:)", text, re.S)
    return m.group(0) if m else ""


@pytest.mark.parametrize("rm", RESEARCH_TYPES)
def test_the_quick_lookup_worker_asks_for_the_application_provision(rm):
    phase = _phase(get_worker_system_prompt(rm, {**CONV, "_research_mode": rm}))
    assert phase, "PHASE 2c missing from the quick-lookup Worker"
    assert "APPLICATION provision" in phase
    assert 'query "application"' in phase
    assert "`search_legislation_sections`" in phase


def test_a_definition_alone_is_not_evidence_that_it_applies():
    phase = _phase(prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL)
    assert "does not show that the definition applies here" in phase
    # The three outcomes: covered, excluded, not checked.
    assert "only if the application provision you retrieved covers it" in phase
    assert "If that provision excludes the instrument" in phase
    assert "whether it applies was not checked" in phase


def test_the_phase_is_conditional():
    phase = _phase(prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL)
    head = phase.split("\n", 1)[0]
    assert "(only when the brief asks what a word or phrase means" in head


def test_the_phase_names_no_instrument():
    """Which general legislation applies is for the retrieval to show; a name
    in the prompt would be training knowledge and could move a brief."""
    phase = _phase(prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL)
    assert phase
    assert not re.search(r"\b(1[89]|20)\d\d\b", phase), "a year names an instrument"
    assert not re.search(r"\b[A-Z][a-z]+ (Act|Order|Regulations|Rules)\b", phase), "a title"
    for word in ("asp/", "uksi/", "ukpga/", "ssi/"):
        assert word not in phase, word


def test_the_synthesis_step_waits_for_it():
    w = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    assert "After Phase 2 (and 2b or 2c where they apply), write your answer." in w
    assert w.index("PHASE 2b") < w.index("PHASE 2c") < w.index("SYNTHESISE IMMEDIATELY:")


@pytest.mark.parametrize("rm", RESEARCH_TYPES)
@pytest.mark.parametrize("cm", ("research", "deep_research"))
def test_the_research_workers_are_unchanged(rm, cm):
    assert "PHASE 2c" not in get_worker_system_prompt(rm, {"_chat_mode": cm, "_research_mode": rm})


@pytest.mark.parametrize("rm", RESEARCH_TYPES)
@pytest.mark.parametrize("cm", ("conversational", "research", "deep_research"))
@pytest.mark.parametrize("chips", (True, False))
def test_no_manager_prompt_carries_it(rm, cm, chips):
    """The Manager writes the first delegation brief; its prompt must not move."""
    cfg = {"_chat_mode": cm, "_research_mode": rm, "_suggested_questions_enabled": chips}
    text = get_manager_system_prompt(rm, cfg)
    assert "PHASE 2c" not in text
    assert "APPLICATION provision" not in text
