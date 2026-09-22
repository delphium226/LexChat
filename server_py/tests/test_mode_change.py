"""FIX_PLAN P4.1 (bucket B7, the research-mode dead-end).

Three bugs and one review action, each pinned here:

(a) ANCHORING — the model repeats its own earlier refusal, still in the
    history, over a system prompt that already carries the new mode. Fixed in
    code: `utils/mode_change.py` reads the modes the client stamps on the
    previous assistant message and, when they differ from this request's,
    prefixes a marker onto the user's turn (`process_user_request` and the
    Deep Research planner).
(b) THE WRONG CONTROL NAME — four prompt sites named two different controls
    between them ("switch to Research mode"; "'Legislation & Case Law' mode
    via the mode selector"). Every deflection now takes the control's name
    from one constant, and the conversational Manager's pointer to Research
    mode is substituted out when that mode is not offered.
(c) INVENTED UI — "typically located at the top or side of your screen".
    The prompts forbid describing the interface; the tests forbid the prompts
    naming anything the UI does not have.
Action 9 (Thomas's review) — a suggestion chip only sends text, so an offer to
    change a mode is dropped from the chips by code.
"""

import pytest

from src import prompts
from src.agent.agent_core import draft_research_plan, process_user_request
from src.agent.provider_factory import set_request_provider_config
from src.prompts import (
    CASE_LAW_OUT_OF_SCOPE_RULE,
    RESEARCH_MODE_HINT_OFF,
    RESEARCH_MODE_HINT_ON,
    get_manager_system_prompt,
    get_planner_system_prompt,
    get_worker_system_prompt,
)
from src.utils.audit_trace import AuditCollector, set_audit_collector
from src.utils.mode_change import (
    CHAT_MODE_CONTROL,
    RESEARCH_TYPE_CONTROL,
    apply_mode_change_marker,
    is_mode_switch_offer,
    mode_change_for,
    mode_change_marker,
    previous_modes,
)
from src.utils.suggestions import extract_suggestions

# What the UI actually calls the two controls (Sidebar.jsx, App.jsx,
# ResearchFiltersModal.jsx). A prompt may name these and nothing else.
UI_RESEARCH_TYPE_LABELS = ("Legislation only", "Case law only", "Legislation & case law")

# Wording the pre-pilot and `wave0_conv` showed reaching lawyers, none of which
# names a control the product has.
FORBIDDEN_PHRASES = (
    "mode selector",
    "'Legislation & Case Law' mode",
    "Legislation & Case Law mode",
    "top or side",
    "start a new chat session",
    "direct the user to switch mode",
)


def _history(prev_rm="legislation_only", prev_cm="conversational", stamp=True):
    assistant = {"role": "assistant", "content": "This session covers legislation only."}
    if stamp:
        assistant["research_mode"] = prev_rm
        assistant["chat_mode"] = prev_cm
    return [
        {"role": "user", "content": "Summarise Rex v Evans (Graham) [2025] EWCA."},
        assistant,
        {"role": "user", "content": "I have changed the mode, please proceed"},
    ]


# ---------------------------------------------------------------------------
# (a) the marker
# ---------------------------------------------------------------------------

def test_previous_modes_reads_the_last_assistant_message_only():
    msgs = [
        {"role": "assistant", "content": "old", "research_mode": "case_law_only", "chat_mode": "research"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "new", "research_mode": "legislation_only", "chat_mode": "conversational"},
        {"role": "user", "content": "q2"},
    ]
    assert previous_modes(msgs) == {"research_mode": "legislation_only", "chat_mode": "conversational"}


def test_unstamped_history_is_not_a_change():
    """A history without stamped modes (older rows, a consulted peer's single
    message, a harness that does not stamp) must read as unknown, never as a
    change — that is exactly today's behaviour."""
    cfg = {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}
    assert mode_change_for(_history(stamp=False), cfg) is None
    assert mode_change_for([{"role": "user", "content": "q"}], cfg) is None
    assert mode_change_for([], cfg) is None
    assert mode_change_for(None, cfg) is None
    # A stamped value that is not a string is ignored, not compared.
    bad = _history()
    bad[1]["research_mode"] = {"weird": True}
    bad[1]["chat_mode"] = 3
    assert mode_change_for(bad, cfg) is None


def test_same_modes_is_not_a_change():
    cfg = {"_research_mode": "legislation_only", "_chat_mode": "conversational"}
    assert mode_change_for(_history(), cfg) is None


def test_research_type_change_is_detected_with_both_values():
    cfg = {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}
    change = mode_change_for(_history(), cfg)
    assert change == {
        "research_mode": {"from": "legislation_only", "to": "legislation_and_case_law"},
        "chat_mode": None,
    }


def test_chat_mode_change_is_detected():
    cfg = {"_research_mode": "legislation_only", "_chat_mode": "research"}
    change = mode_change_for(_history(), cfg)
    assert change["chat_mode"] == {"from": "conversational", "to": "research"}
    assert change["research_mode"] is None


def test_deep_research_reverting_to_conversational_is_silent():
    """The frontend reverts to conversational after every Deep Research turn
    (it is one-shot), so that transition is not the user switching anything."""
    cfg = {"_research_mode": "legislation_only", "_chat_mode": "conversational"}
    assert mode_change_for(_history(prev_cm="deep_research"), cfg) is None
    # ...but the other direction IS a change the user made.
    cfg = {"_research_mode": "legislation_only", "_chat_mode": "deep_research"}
    assert mode_change_for(_history(), cfg)["chat_mode"]["to"] == "deep_research"


def test_marker_names_the_ui_labels_and_the_consequence():
    text = mode_change_marker({
        "research_mode": {"from": "legislation_only", "to": "legislation_and_case_law"},
        "chat_mode": None,
    })
    assert text.startswith("[SYSTEM NOTICE")
    assert text.endswith("]")
    assert '"Legislation & case law"' in text
    assert '"Legislation only"' in text
    assert "case law can now be searched" in text.lower()
    assert "do not tell the user the setting has not changed" in text
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text


def test_marker_is_prefixed_onto_the_last_user_turn_only():
    cfg = {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}
    msgs = _history()
    out, change = apply_mode_change_marker(msgs, cfg)
    assert change is not None
    assert out is not msgs                      # a new list...
    assert msgs[-1]["content"] == "I have changed the mode, please proceed"  # ...the input untouched
    assert out[-1]["content"].startswith("[SYSTEM NOTICE")
    assert out[-1]["content"].endswith("I have changed the mode, please proceed")
    assert out[:-1] == msgs[:-1]                # nothing else moved
    # Idempotent: applying it again does not stack a second marker.
    again, _ = apply_mode_change_marker(out, cfg)
    assert again[-1]["content"].count("[SYSTEM NOTICE") == 1


def test_no_change_returns_the_same_list_object():
    cfg = {"_research_mode": "legislation_only", "_chat_mode": "conversational"}
    msgs = _history()
    out, change = apply_mode_change_marker(msgs, cfg)
    assert out is msgs and change is None


def test_no_user_turn_means_no_marker():
    cfg = {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}
    msgs = [{"role": "assistant", "content": "x", "research_mode": "legislation_only"}]
    out, change = apply_mode_change_marker(msgs, cfg)
    assert out is msgs and change is None


# ---------------------------------------------------------------------------
# (a) through the two seams that read the history
# ---------------------------------------------------------------------------

class _Capture:
    def __init__(self):
        self.messages = None

    async def manager(self, messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        self.messages = list(messages)
        return {"role": "assistant", "content": "Proceeding with the case summary."}

    async def planner(self, messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, emit_tool_details=False,
                      timing_collector=None):
        if self.messages is None:  # the first call; the retry appends a nudge
            self.messages = list(messages)
        return {"role": "assistant", "content": "prose only"}


async def _manager_turn(messages, cfg, audit=None):
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_tool_memo_enabled": False, **cfg})
    set_audit_collector(audit)
    cap = _Capture()

    async def worker(*a, **kw):  # never reached: the fake manager does not delegate
        raise AssertionError("no delegation expected")

    try:
        final = await process_user_request(cap.manager, worker, messages,
                                           "test-model", None, None, 0)
    finally:
        set_request_provider_config({})
        set_audit_collector(None)
    return cap, final


@pytest.mark.asyncio
async def test_the_manager_sees_the_marker_and_the_result_echoes_the_modes():
    """6346, turn 3: the lawyer says she changed it, and this time she had."""
    audit = AuditCollector("req-p41")
    cap, final = await _manager_turn(
        _history(), {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}, audit,
    )
    last_user = [m for m in cap.messages if m["role"] == "user"][-1]
    assert last_user["content"].startswith("[SYSTEM NOTICE")
    assert "I have changed the mode, please proceed" in last_user["content"]
    # The refusal itself stays in the history — the marker supersedes it, it
    # does not rewrite the record.
    assert any(m["role"] == "assistant" and "legislation only" in m["content"] for m in cap.messages)
    # The reply is stamped so the NEXT turn's history carries it back.
    assert final["research_mode"] == "legislation_and_case_law"
    assert final["chat_mode"] == "conversational"
    # And the trace says a marker went in (schema v5).
    event = audit.to_event(config={"_research_mode": "legislation_and_case_law"})
    assert event["mode_change"] == {
        "research_mode": {"from": "legislation_only", "to": "legislation_and_case_law"},
        "chat_mode": None,
    }


@pytest.mark.asyncio
async def test_an_unstamped_history_gets_no_marker_and_a_null_trace():
    audit = AuditCollector("req-p41b")
    cap, final = await _manager_turn(
        _history(stamp=False), {"_research_mode": "legislation_and_case_law", "_chat_mode": "conversational"}, audit,
    )
    last_user = [m for m in cap.messages if m["role"] == "user"][-1]
    assert last_user["content"] == "I have changed the mode, please proceed"
    assert final["research_mode"] == "legislation_and_case_law"
    assert audit.to_event(config={})["mode_change"] is None


@pytest.mark.asyncio
async def test_the_planner_reads_the_same_marker():
    """6346 turn 4 asked for Deep Research and the planner handed the refusal
    back as a clarification. Same history, same seam."""
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_research_mode": "legislation_and_case_law",
                                 "_chat_mode": "deep_research"})
    cap = _Capture()
    try:
        await draft_research_plan(cap.planner, _history(), "test-model", None, 0)
    finally:
        set_request_provider_config({})
    last_user = [m for m in cap.messages if m["role"] == "user"][-1]
    assert last_user["content"].startswith("[SYSTEM NOTICE")
    assert '"Legislation & case law"' in last_user["content"]


# ---------------------------------------------------------------------------
# (b) and (c): what the prompts may say
# ---------------------------------------------------------------------------

# Every dispatch branch of get_manager_system_prompt (test_suggestions.py's
# pattern), so no branch can keep an old deflection.
_MANAGER_CASES = [
    ("legislation_only", {}),
    ("legislation_only", {"_chat_mode": "conversational"}),
    ("legislation_and_case_law", {}),
    ("legislation_and_case_law", {"_chat_mode": "conversational"}),
    ("case_law_only", {}),
    ("case_law_only", {"_chat_mode": "conversational"}),
    ("parliamentary_records", {}),
    ("westminster_records", {}),
]


@pytest.mark.parametrize("mode,cfg", _MANAGER_CASES)
def test_no_manager_prompt_names_a_control_the_ui_does_not_have(mode, cfg):
    text = get_manager_system_prompt(mode, cfg or None)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, phrase
    # "Research mode" may be named only as the sidebar control, or in the
    # explicit prohibition on offering it as the route to case law.
    for line in text.splitlines():
        if "Research mode" in line:
            assert (
                CHAT_MODE_CONTROL in line
                or "do not tell them to switch to Research mode" in line
                or line.strip() == RESEARCH_MODE_HINT_OFF
            ), line


@pytest.mark.parametrize("cfg", [{}, {"_chat_mode": "conversational"}])
def test_legislation_only_deflection_names_the_filter_in_both_chat_modes(cfg):
    """The research-mode Manager used to get a one-line 'direct the user to
    switch mode' and no note at all; the conversational one named a control
    that does not exist. Both now carry the one rule."""
    text = get_manager_system_prompt("legislation_only", cfg or None)
    assert "CURRENT RESEARCH TYPE: Legislation only." in text
    assert CASE_LAW_OUT_OF_SCOPE_RULE in text
    assert RESEARCH_TYPE_CONTROL in text
    assert "'Legislation & case law'" in text
    assert "next message in this same conversation" in text
    assert "never tell them to start a new chat" in text


def test_the_rule_itself_uses_only_ui_labels():
    for label in ("'Legislation only'", "'Legislation & case law'"):
        assert label in CASE_LAW_OUT_OF_SCOPE_RULE
    assert "Filters button" in RESEARCH_TYPE_CONTROL
    assert "Research type" in RESEARCH_TYPE_CONTROL
    assert "Mode menu" in CHAT_MODE_CONTROL
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in CASE_LAW_OUT_OF_SCOPE_RULE


def test_case_law_only_is_not_called_a_mode_either():
    text = get_manager_system_prompt("case_law_only", {"_chat_mode": "conversational"})
    assert "CURRENT RESEARCH TYPE: Case law only." in text
    assert "Case Law Only mode" not in text
    assert RESEARCH_TYPE_CONTROL in text


def test_research_mode_hint_is_substituted_out_when_the_mode_is_not_offered():
    """The Research chat mode was OFF for the whole pre-pilot; 'switch to
    Research mode' told lawyers to use a control they did not have. Same
    substitute-not-override design as the chips flag."""
    on = get_manager_system_prompt("legislation_only", {"_chat_mode": "conversational"})
    assert RESEARCH_MODE_HINT_ON in on
    assert RESEARCH_MODE_HINT_OFF not in on
    absent = get_manager_system_prompt("legislation_only", {"_chat_mode": "conversational",
                                                            "_research_mode_enabled": True})
    assert absent == on
    off = get_manager_system_prompt("legislation_only", {"_chat_mode": "conversational",
                                                         "_research_mode_enabled": False})
    assert RESEARCH_MODE_HINT_OFF in off
    assert RESEARCH_MODE_HINT_ON not in off
    assert "Research mode is available" not in off
    # The rest of the prompt is byte-identical either way.
    assert off.replace(RESEARCH_MODE_HINT_OFF, RESEARCH_MODE_HINT_ON) == on


def test_the_hint_says_research_mode_is_not_the_route_to_case_law():
    assert CHAT_MODE_CONTROL in RESEARCH_MODE_HINT_ON
    assert "never offer it as the way to reach case law" in RESEARCH_MODE_HINT_ON


def test_the_research_manager_defers_to_the_note():
    text = prompts.MANAGER_SYSTEM_PROMPT
    assert "CURRENT RESEARCH TYPE note above" in text
    assert "do not improvise a different instruction" in text


def test_the_chat_worker_no_longer_sends_users_to_research_mode():
    """The Worker's 'suggest the user switch to Research mode' is where 6343's
    wording came from. Still exactly four OUTPUT bullets (P2.4's format
    invariant, pinned separately in test_case_law_gap.py)."""
    text = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    assert "Research mode" not in text
    output = text.split("OUTPUT:")[1].split("CITATION FORMAT:")[0]
    assert "do not suggest changing a mode, research type or setting" in output
    assert len([ln for ln in output.splitlines() if ln.startswith("- ")]) == 4
    # The filter block is not the seam either: the built prompt carries no
    # control name.
    built = get_worker_system_prompt("legislation_only", {"_chat_mode": "conversational"})
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in built


@pytest.mark.parametrize("mode", ["legislation_only", "case_law_only", "legislation_and_case_law"])
def test_the_planner_names_the_filter_not_a_mode(mode):
    text = get_planner_system_prompt(mode, {"_chat_mode": "deep_research"})
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text
    assert "CURRENT RESEARCH TYPE:" in text
    if mode == "legislation_only":
        assert RESEARCH_TYPE_CONTROL in text
        assert "current setting is the one stated here" in text


@pytest.mark.parametrize("block", [
    prompts._MANAGER_CHIPS, prompts._MANAGER_CONV_CHIPS,
    prompts._PARLIAMENT_CHIPS, prompts._WESTMINSTER_CHIPS,
])
def test_every_chips_block_forbids_offering_a_mode_switch(block):
    assert "Never offer a change of mode, research type or filter as a suggestion" in block


# ---------------------------------------------------------------------------
# Action 9: the chip that could not switch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,offer", [
    ("Switch to Research mode", True),                          # 6407 turn 2, verbatim
    ("Switch to Research mode.", True),
    ("Change the research type to Legislation & case law", True),
    ("Could you enable case law in the filters?", True),
    ("Please turn on Research mode for a fuller search", True),
    ("Use the Filters button to include case law", True),
    ("What penalties apply under section 33?", False),
    ("Does this provision extend to Scotland?", False),
    ("What did the court decide on the mode of trial?", False),  # "mode" alone is not an offer
    ("How is 'switch' defined in the Electricity Act 1989?", False),
])
def test_is_mode_switch_offer(text, offer):
    assert is_mode_switch_offer(text) is offer


def test_mode_switch_offers_are_dropped_from_the_chips():
    content = (
        "This session covers legislation only.\n"
        "<suggestions>\n"
        "Switch to Research mode\n"
        "What does s.1 of the Act provide?\n"
        "Change the research type to include case law\n"
        "Does the Act extend to Scotland?\n"
        "</suggestions>"
    )
    clean, items = extract_suggestions(content)
    assert clean == "This session covers legislation only."
    assert items == ["What does s.1 of the Act provide?", "Does the Act extend to Scotland?"]


def test_a_block_of_only_mode_switch_offers_yields_no_chips():
    clean, items = extract_suggestions("Answer.\n<suggestions>\nSwitch to Research mode\n</suggestions>")
    assert clean == "Answer."
    assert items == []
