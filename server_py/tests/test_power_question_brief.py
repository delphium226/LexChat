"""FIX_PLAN P3.51, Fix 2 (Session 52; wording approved by the user for a
single-step test): the power-question line in the conversational Manager's
"WHEN USING delegate_research IN CHAT MODE" guidance.

Q16 (6354) asks what mechanisms would lessen a single local authority's duty to
accommodate the homeless; 9 of 12 stored briefs since P3.51's block asked for
the DUTY, and a duty-worded section search of the 1987 Act rarely returns the
s.33 family (`evidence/seam/s52/brief/`). The line asks for the power instead.
It is in the conversational Manager prompt and in no other prompt, and it names
no instrument (P3.13: a Manager prompt clause once moved a first brief to the
wrong Act).
"""
import re

import pytest

from src import prompts
from src.agent.tools.schemas import get_manager_tools, get_planner_tools, get_worker_tools

LINE = (
    "- When the user asks what power, provision or mechanism would let someone do "
    "something (enable, allow, change, lessen or suspend a requirement), write the brief "
    "as a search for that power, in the user's own words: ask for provisions that give a "
    "power to do it or to change the rule, not for the duty, scheme or body the power "
    "would act on."
)
# A distinctive fragment, so a reworded or partial copy anywhere else is caught too.
FRAGMENT = "not for the duty, scheme or body the power"

RESEARCH_TYPES = ("legislation_only", "case_law_only", "legislation_and_case_law")
BOT_MODES = ("parliamentary_records", "westminster_records")
FLAGS = (
    {},
    {"_suggested_questions_enabled": False},
    {"_research_mode_enabled": False},
    {"_research_mode_enabled": True},
    {"_suggested_questions_enabled": False, "_research_mode_enabled": False},
    {"_consulted": True},
)


def _cfg(chat_mode, extra):
    cfg = dict(extra)
    if chat_mode:
        cfg["_chat_mode"] = chat_mode
    return cfg or None


def test_the_line_sits_in_the_delegate_research_guidance():
    body = prompts._MANAGER_CONV_BODY
    assert body.count(LINE) == 1
    start = body.index("WHEN USING delegate_research IN CHAT MODE:\n")
    end = body.index("\n\nTONE:", start)
    section = body[start:end]
    bullets = [b for b in section.split("\n") if b.startswith("- ")]
    assert bullets == [
        bullets[0], "- Include any Act names, SI numbers, or context from earlier in the "
                    "conversation.", LINE]
    assert bullets[0].startswith("- Write a tightly scoped brief.")


def test_the_line_names_no_instrument():
    # P3.13's lesson: nothing the Manager could copy into a brief as an Act.
    assert not re.search(r"\b(?:Act|Order|Regulations|SSI|SI)\b|\d", LINE)


@pytest.mark.parametrize("research_mode", RESEARCH_TYPES)
@pytest.mark.parametrize("extra", FLAGS)
def test_in_the_conversational_manager_prompt(research_mode, extra):
    prompt = prompts.get_manager_system_prompt(research_mode, _cfg("conversational", extra))
    assert prompt.count(LINE) == 1


@pytest.mark.parametrize("research_mode", RESEARCH_TYPES + BOT_MODES)
@pytest.mark.parametrize("chat_mode", (None, "research", "deep_research", "conversational"))
@pytest.mark.parametrize("extra", FLAGS)
def test_in_no_other_prompt(research_mode, chat_mode, extra):
    cfg = _cfg(chat_mode, extra)
    texts = [
        prompts.get_worker_system_prompt(research_mode, cfg),
        prompts.get_planner_system_prompt(research_mode, cfg),
        prompts.get_deep_research_synthesis_prompt(research_mode),
    ]
    if not (chat_mode == "conversational" and research_mode in RESEARCH_TYPES):
        texts.append(prompts.get_manager_system_prompt(research_mode, cfg))
    for text in texts:
        assert FRAGMENT not in text


def test_in_no_tool_description():
    tools = [get_manager_tools(""), get_manager_tools("- parliament_bot: Holyrood"),
             get_planner_tools()]
    for rm in RESEARCH_TYPES + BOT_MODES:
        for cm in (None, "research", "deep_research", "conversational"):
            tools.append(get_worker_tools(rm, cm))
    for t in tools:
        assert FRAGMENT not in repr(t)


def test_only_the_conversational_body_carries_it():
    # Every module-level string in prompts.py: the body and the constant built from it.
    carriers = sorted(k for k, v in vars(prompts).items()
                      if isinstance(v, str) and FRAGMENT in v)
    assert carriers == ["MANAGER_SYSTEM_PROMPT_CONVERSATIONAL", "_MANAGER_CONV_BODY"]


def test_the_default_jurisdiction_section_is_untouched():
    # The research Manager and planner read the JURISDICTION section out of the
    # same body; the new line is after it, so their copies cannot move.
    assert FRAGMENT not in prompts.DEFAULT_JURISDICTION_SECTION
    assert FRAGMENT not in prompts.PLANNER_JURISDICTION_SECTION
