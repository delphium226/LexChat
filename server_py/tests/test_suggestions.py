"""Unit tests for the `<suggestions>` block parser (utils/suggestions.py) and
the prompt wiring that produces and suppresses the block."""

import pytest

from src.prompts import (
    CONSULTED_PEER_BLOCK,
    NO_CHIPS_SUGGESTION_RULES,
    get_manager_system_prompt,
    get_planner_system_prompt,
)
from src.utils.suggestions import (
    MAX_SUGGESTIONS,
    diagnose_suggestions,
    extract_suggestions,
)


def test_no_block_returns_content_unchanged():
    content = "Section 33 creates the offence.\n\nWhat would you like next?"
    assert extract_suggestions(content) == (content, [])


def test_empty_content():
    assert extract_suggestions("") == ("", [])
    assert extract_suggestions(None) == ("", [])


def test_well_formed_block():
    content = (
        "Section 33 creates the offence.\n\n"
        "<suggestions>\n"
        "What penalties apply under section 33?\n"
        "Has section 33 been considered in case law?\n"
        "</suggestions>"
    )
    clean, items = extract_suggestions(content)
    assert clean == "Section 33 creates the offence."
    assert items == [
        "What penalties apply under section 33?",
        "Has section 33 been considered in case law?",
    ]


def test_bulleted_and_numbered_lines_are_stripped():
    content = (
        "Answer.\n<suggestions>\n"
        "- What penalties apply?\n"
        "* Which court decided it?\n"
        "1. Is it still in force?\n"
        "2) Does it extend to Scotland?\n"
        "</suggestions>"
    )
    _, items = extract_suggestions(content)
    assert items == [
        "What penalties apply?",
        "Which court decided it?",
        "Is it still in force?",
        "Does it extend to Scotland?",
    ]


def test_surrounding_quotes_are_stripped():
    content = '<suggestions>\n"What penalties apply?"\n</suggestions>'
    _, items = extract_suggestions(content)
    assert items == ["What penalties apply?"]


def test_duplicate_lines_deduped_case_insensitively():
    content = (
        "Answer.\n<suggestions>\n"
        "What penalties apply?\n"
        "what PENALTIES apply?\n"
        "Is it in force?\n"
        "</suggestions>"
    )
    _, items = extract_suggestions(content)
    assert items == ["What penalties apply?", "Is it in force?"]


def test_more_than_four_items_capped():
    lines = "\n".join(f"Question number {i}?" for i in range(1, 8))
    clean, items = extract_suggestions(f"Answer.\n<suggestions>\n{lines}\n</suggestions>")
    assert clean == "Answer."
    assert len(items) == MAX_SUGGESTIONS
    assert items[0] == "Question number 1?"


def test_over_long_item_is_dropped_not_truncated():
    long_line = "Why " + ("x" * 200) + "?"
    content = f"Answer.\n<suggestions>\n{long_line}\nShort one?\n</suggestions>"
    _, items = extract_suggestions(content)
    assert items == ["Short one?"]


def test_unterminated_tag_is_stripped_and_parsed():
    content = "Answer body.\n\n<suggestions>\nWhat penalties apply?\nIs it in force?"
    clean, items = extract_suggestions(content)
    assert clean == "Answer body."
    assert items == ["What penalties apply?", "Is it in force?"]


def test_unterminated_tag_alone_leaves_clean_content():
    clean, items = extract_suggestions("Answer body.\n\n<suggestions>")
    assert clean == "Answer body."
    assert items == []


def test_tag_echoed_twice_last_block_wins():
    content = (
        "Here is what I would suggest:\n"
        "<suggestions>\nStale question?\n</suggestions>\n\n"
        "The real answer.\n\n"
        "<suggestions>\nFresh question?\n</suggestions>"
    )
    clean, items = extract_suggestions(content)
    assert items == ["Fresh question?"]
    # Only the last block is removed; the earlier echo is left in the prose,
    # which is a prompt-quality issue rather than something to guess at here.
    assert clean.endswith("The real answer.")


def test_empty_block_yields_no_items_but_strips_markup():
    clean, items = extract_suggestions("Answer.\n<suggestions>\n\n</suggestions>")
    assert clean == "Answer."
    assert items == []


def test_case_insensitive_tag():
    clean, items = extract_suggestions("Answer.\n<SUGGESTIONS>\nWhat next?\n</Suggestions>")
    assert clean == "Answer."
    assert items == ["What next?"]


# ---------------------------------------------------------------------------
# Prompt wiring
# ---------------------------------------------------------------------------

# Every branch of get_manager_system_prompt's dispatch, so a new bot type or a
# refactor to a single return cannot silently lose either half of the wiring.
_MANAGER_PROMPT_CASES = [
    ("legislation_only", {}),                                   # research mode
    ("legislation_and_case_law", {}),
    ("legislation_only", {"_chat_mode": "conversational"}),     # conversational
    ("parliamentary_records", {}),                              # early return
    ("westminster_records", {}),                                # early return
    ("drafting", {}),                                           # early return
]


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_every_manager_prompt_asks_for_a_suggestions_block(mode, cfg):
    prompt = get_manager_system_prompt(mode, cfg or None)
    assert "<suggestions>" in prompt
    assert "</suggestions>" in prompt


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_consulted_block_appended_on_every_return_path(mode, cfg):
    assert CONSULTED_PEER_BLOCK not in get_manager_system_prompt(mode, cfg or None)
    consulted = get_manager_system_prompt(mode, {**cfg, "_consulted": True})
    assert CONSULTED_PEER_BLOCK in consulted
    # It must be last, so it overrides the follow-up instruction above it.
    assert consulted.rstrip().endswith(CONSULTED_PEER_BLOCK)


# --- suggested_questions_enabled flag ---------------------------------------
# The flag SUBSTITUTES the chips rules out of the prompt rather than appending an
# override after them. These tests exist to keep it that way: an override-style
# implementation would leave the <suggestions> instruction in the prompt and rely
# on the model obeying a later contradiction.

@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_flag_off_removes_every_trace_of_the_chips_instruction(mode, cfg):
    off = get_manager_system_prompt(mode, {**cfg, "_suggested_questions_enabled": False})
    assert "<suggestions>" not in off
    assert "</suggestions>" not in off
    # The chips-specific rationale must go too, not just the tag.
    assert "clickable buttons" not in off


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_flag_off_still_asks_for_a_follow_up_and_for_options(mode, cfg):
    """Deleting the rules outright would lose the instruction to offer options at
    all, leaving a clarifying question the user cannot answer."""
    off = get_manager_system_prompt(mode, {**cfg, "_suggested_questions_enabled": False})
    assert NO_CHIPS_SUGGESTION_RULES in off
    assert "FOLLOW-UP QUESTIONS:" in off
    assert "CLARIFYING QUESTIONS" in off
    # The no-speculation guardrail survives the swap — chips made a hallucinated
    # option one click away, but a written-out wrong option is still wrong.
    assert "have not retrieved via a tool" in off


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_flag_absent_or_true_leaves_prompt_unchanged(mode, cfg):
    """Absent key behaves as ON, so an old saved features JSON is a no-op."""
    baseline = get_manager_system_prompt(mode, cfg or None)
    assert get_manager_system_prompt(mode, {**cfg, "_suggested_questions_enabled": True}) == baseline
    assert "<suggestions>" in baseline


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_consulted_block_still_appended_when_flag_is_off(mode, cfg):
    """The two are independent: a consulted peer with chips off must get both the
    swapped rules and the consulted override."""
    prompt = get_manager_system_prompt(
        mode, {**cfg, "_consulted": True, "_suggested_questions_enabled": False}
    )
    assert CONSULTED_PEER_BLOCK in prompt
    assert "<suggestions>" not in prompt.replace(CONSULTED_PEER_BLOCK, "")


# ---------------------------------------------------------------------------
# Mode dispatch completeness (S1 — drafting bot)
# ---------------------------------------------------------------------------
# Every mode dispatch in the codebase is a lookup-with-legislation-fallback or an
# if/elif chain ending in the legislation branch. That makes adding a mode safe
# for the existing bots — and makes a MISSED KEY FAIL SILENTLY, as the new bot
# quietly runs with legislation prompts, legislation tools and legislation
# efficiency thresholds. Nothing raises and nothing looks wrong in the logs.
#
# So each case below asserts BOTH halves: that "drafting" resolves to the
# drafting object, AND that it is not the legislation fallback. Asserting only
# the first half would pass on a missed key wherever the fallback happens to
# satisfy the same assertion.

def test_dispatch_efficiency_profile(monkeypatch):
    """config.py — EFFICIENCY_PROFILES / get_efficiency_profile()."""
    from src import config

    monkeypatch.setattr(config.settings, "research_mode", "drafting")
    profile = config.get_efficiency_profile()
    assert profile is config.EFFICIENCY_PROFILES["drafting"]
    assert profile is not config.EFFICIENCY_PROFILES["legislation"]


def test_dispatch_worker_tools():
    """tools/schemas.py — get_worker_tools()."""
    from src.agent.tools.schemas import DRAFTING_TOOLS, WORKER_TOOLS, get_worker_tools

    tools = get_worker_tools("drafting")
    # Identity, not contents: DRAFTING_TOOLS starts as a copy of WORKER_TOOLS, so
    # an equality check here would pass even if the branch were missing entirely.
    assert tools is DRAFTING_TOOLS
    assert tools is not WORKER_TOOLS


def test_dispatch_worker_system_prompt():
    """prompts.py — get_worker_system_prompt()."""
    from src.prompts import (
        DRAFTING_WORKER_SYSTEM_PROMPT,
        WORKER_SYSTEM_PROMPT,
        get_worker_system_prompt,
    )

    prompt = get_worker_system_prompt("drafting")
    assert DRAFTING_WORKER_SYSTEM_PROMPT in prompt
    assert WORKER_SYSTEM_PROMPT not in prompt


def test_dispatch_worker_system_prompt_ignores_conversational_chat_mode():
    """Like the parliament/Westminster bots, the drafting worker keeps its own
    prompt in conversational mode — the generic conversational worker prompt is
    legislation-shaped."""
    from src.prompts import (
        DRAFTING_WORKER_SYSTEM_PROMPT,
        WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
        get_worker_system_prompt,
    )

    prompt = get_worker_system_prompt("drafting", {"_chat_mode": "conversational"})
    assert DRAFTING_WORKER_SYSTEM_PROMPT in prompt
    assert WORKER_SYSTEM_PROMPT_CONVERSATIONAL not in prompt


def test_dispatch_manager_system_prompt():
    """prompts.py — get_manager_system_prompt()'s early-return branch."""
    from src.prompts import _DRAFTING_BODY, _MANAGER_BODY, get_manager_system_prompt

    prompt = get_manager_system_prompt("drafting")
    assert _DRAFTING_BODY in prompt
    assert _MANAGER_BODY not in prompt


def test_dispatch_filter_constraint_block():
    """prompts.py — _filter_constraint_block_for_mode().

    The drafting bot exposes no research filters, so its block is empty. The cfg
    below produces a non-empty block on the legislation path, which is what makes
    the empty result evidence of the branch rather than of an empty cfg.
    """
    from src.prompts import _filter_constraint_block_for_mode

    cfg = {"_jurisdiction": "scotland", "_current_only": True}
    assert _filter_constraint_block_for_mode("legislation_only", cfg) != ""
    assert _filter_constraint_block_for_mode("drafting", cfg) == ""


def test_dispatch_report_sections():
    """agent_core.py — _REPORT_SECTIONS."""
    from src.agent.agent_core import _REPORT_SECTIONS

    assert "drafting" in _REPORT_SECTIONS
    assert _REPORT_SECTIONS["drafting"] != _REPORT_SECTIONS["legislation_only"]
    # The list is what _report_needs_reformat grades against and what the
    # reformat retry is told to aim at, so it must match the worker prompt's
    # OUTPUT STRUCTURE labels.
    from src.prompts import DRAFTING_WORKER_SYSTEM_PROMPT

    for section in _REPORT_SECTIONS["drafting"]:
        assert section in DRAFTING_WORKER_SYSTEM_PROMPT


def test_dispatch_planner_mode_note():
    """prompts.py — _PLANNER_MODE_NOTES."""
    from src.prompts import _PLANNER_MODE_NOTES, get_planner_system_prompt

    prompt = get_planner_system_prompt("drafting")
    assert _PLANNER_MODE_NOTES["drafting"] in prompt
    assert _PLANNER_MODE_NOTES["legislation_only"] not in prompt


def test_drafting_guidance_tool_is_not_yet_present():
    """S1 is scaffolding: the guidance tool arrives in S3. Pinned so a later
    session cannot mistake the placeholder tool set for a finished one — and as
    the counterpart to test_drafting_security's CACHEABLE_TOOLS assertion."""
    from src.agent.tools.schemas import get_worker_tools

    names = {t["function"]["name"] for t in get_worker_tools("drafting")}
    assert "search_drafting_guidance" not in names


@pytest.mark.parametrize("mode", ["legislation_only", "case_law_only", "parliamentary_records"])
def test_planner_options_rule_swapped_not_overridden(mode):
    on = get_planner_system_prompt(mode, {})
    off = get_planner_system_prompt(mode, {"_suggested_questions_enabled": False})
    assert "`options`" in on
    assert "`options`" not in off
    # The template slot must always be filled, on either path.
    assert "{options_rule}" not in on and "{options_rule}" not in off


# --- diagnose_suggestions: the prompt-adherence floor ------------------------
# These do not change a reply; they exist so a drifting model is greppable in
# the logs instead of surfacing in front of a user first.

_TRANSPORT_BODY = (
    '"Tell me about transport" is a very broad topic. To help me find the most '
    "relevant Scottish Parliament proceedings, could you please narrow down your "
    "request?\n\nFor example, are you looking for:\n"
    "- Recent plenary debates on transport policy?\n"
    "- Evidence sessions from the Net Zero, Energy and Transport Committee?\n"
    "- Statements from the Cabinet Secretary for Transport?"
)


def test_clarification_without_options_is_flagged():
    issues = diagnose_suggestions(
        "Which Act do you mean?", [], has_sources=False
    )
    assert len(issues) == 1
    assert "nothing to click" in issues[0]


def test_clarification_with_options_duplicated_in_body_is_flagged():
    # The regression actually seen: options as prose bullets AND as chips.
    issues = diagnose_suggestions(
        _TRANSPORT_BODY, ["Plenary debates?", "Committee evidence?"],
        has_sources=False,
    )
    assert len(issues) == 1
    assert "duplicated" in issues[0]


def test_clean_clarification_is_not_flagged():
    issues = diagnose_suggestions(
        "Could you narrow that down?",
        ["Plenary debates?", "Committee evidence?"],
        has_sources=False,
    )
    assert issues == []


def test_researched_answer_without_a_block_is_flagged():
    issues = diagnose_suggestions(
        "Section 33 creates the offence.", [], has_sources=True
    )
    assert len(issues) == 1
    assert "without a <suggestions> block" in issues[0]


def test_healthy_researched_answer_is_not_flagged():
    issues = diagnose_suggestions(
        "Section 33 creates the offence.", ["What are the penalties?"],
        has_sources=True,
    )
    assert issues == []


def test_researched_answer_with_bullets_is_not_mistaken_for_a_clarification():
    # A real report is full of bullets; it must not trip the duplication check.
    body = "Findings:\n- s.1 imposes the duty\n- s.2 defines the employer\n- s.33 penalises breach"
    assert diagnose_suggestions(body, ["Next?"], has_sources=True) == []


def test_empty_content_is_never_flagged():
    assert diagnose_suggestions("", [], has_sources=False) == []
    assert diagnose_suggestions(None, [], has_sources=False) == []
