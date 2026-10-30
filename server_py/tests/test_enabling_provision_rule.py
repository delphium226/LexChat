"""FIX_PLAN P3.52 fix B (Session 52, draft): the ENABLING PROVISION bullet in the
quick-lookup Worker prompt's OUTPUT section, and nowhere else."""
from __future__ import annotations

import pytest

from src import prompts
from src.prompts import (get_deep_research_synthesis_prompt, get_manager_system_prompt,
                         get_planner_system_prompt, get_worker_system_prompt)

RULE = prompts._ENABLING_PROVISION_LEAD
MODES = ["legislation_only", "legislation_and_case_law", "case_law_only",
         "parliamentary_records", "westminster_records"]


def test_the_quick_lookup_worker_carries_it_once_at_the_end_of_the_citation_bullet():
    p = get_worker_system_prompt("legislation_only", {"_chat_mode": "conversational"})
    assert p.count(RULE) == 1
    output = p.split("OUTPUT:")[1].split("CITATION FORMAT:")[0]
    bullets = [ln for ln in output.splitlines() if ln.startswith("- ")]
    assert len(bullets) == 4                      # P2.4's format invariant
    assert bullets[1].startswith("- Include the relevant citation")
    assert bullets[1].endswith("the 2-5 sentences above. " + RULE)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("chat", [None, "research", "deep_research"])
def test_no_other_worker_prompt_carries_it(mode, chat):
    cfg = {"_chat_mode": chat} if chat else None
    assert "which provision enables or empowers" not in get_worker_system_prompt(mode, cfg)


@pytest.mark.parametrize("mode", MODES)
def test_the_parliamentary_conversational_workers_and_the_other_agents_do_not(mode):
    if mode in ("parliamentary_records", "westminster_records"):
        assert "which provision enables or empowers" not in get_worker_system_prompt(
            mode, {"_chat_mode": "conversational"})
    for chat in (None, "research", "deep_research", "conversational"):
        cfg = {"_chat_mode": chat} if chat else None
        assert "which provision enables or empowers" not in get_manager_system_prompt(mode, cfg)
    assert "which provision enables or empowers" not in get_planner_system_prompt(mode)
    assert "which provision enables or empowers" not in get_deep_research_synthesis_prompt(mode)


def test_the_rule_is_sentences_not_a_bullet_and_names_no_scenario():
    assert RULE.startswith("Where the brief asks which provision enables or empowers ")
    assert "\n" not in RULE
    low = RULE.lower()
    for word in ("bus", "fare", "transport", "lawyer"):
        assert word not in low
