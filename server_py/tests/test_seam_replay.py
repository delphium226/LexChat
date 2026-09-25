"""`tools/seam_replay.py`: one composition seam, rebuilt from a stored run file.

The point of the tool is that iterating on a prompt or composition change costs
one model call instead of a session replay (measured on the fixtures it was
built against: $0.03 for the Worker seam against $0.55 for a 6348 replay;
$0.11 for the Deep Research synthesis against $0.61-0.79 for the turn). That
only holds if the payload it builds is the one the product sends, so the tests
below pin:

1. it uses `agent_core.build_synthesis_messages`, the product's own builder,
   rather than a copy that would drift;
2. the fixture is read the way `run_deep_research` assembled it (plan steps
   paired with their delegation's report; halted steps carried);
3. the Worker seam replays the RECORDED tool results, excluding any call a
   budget refused, and forces a tool-free composition;
4. `--without-fix` really removes the fix (the pinpoint block, and the prompt
   at the older revision), which is what makes an A/B an A/B;
5. `--dry-run` never calls a model.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.seam_replay as sr  # noqa: E402
from src.agent import agent_core  # noqa: E402

S57 = "http://www.legislation.gov.uk/asp/2002/3/section/57"
S21 = "http://www.legislation.gov.uk/asp/2000/1/section/21"


def _run_doc(**over):
    """A run file the shape `replay.py` writes, with one Deep Research turn."""
    doc = {
        "session_id": "6365",
        "rep": 1,
        "filters": {"research_mode": "legislation_only", "jurisdiction": "scotland",
                    "year_to": 2026},
        "filter_snapshot_chat_mode": "deep_research",
        "turns": [{
            "turn": 1,
            "question": "Scottish Water's reporting timeline?",
            "chat_mode": "deep_research",
            "answer": "Integrated report.",
            "plan": {"scope_note": "Legislation only.", "steps": [
                {"id": 1, "title": "Accounts", "detail": "Find the duties."},
                {"id": 2, "title": "Audit", "detail": "Find the deadlines."},
            ]},
            "audit": {"delegations": [
                {"step": 1, "brief": "Accounts duties",
                 "report": f"Accounts ([WI(S)A 2002 - s.57(3)(a)]({S57})).",
                 "tools": [
                     {"name": "search_legislation", "args": {"query": "water"},
                      "final_result": '{"results": []}'},
                     {"name": "search_legislation_sections",
                      "args": {"legislation_id": "asp/2002/3", "query": "accounts"},
                      "final_result": "Section 57 text."},
                 ]},
                {"step": 2, "brief": "Audit deadlines",
                 "report": f"Six months ([PFA(S)A 2000 - s.21(2)]({S21})).",
                 "halted": {"reason": "step_cap", "limit": 20, "steps": 20},
                 "tools": [{"name": "search_legislation_sections",
                            "args": {"legislation_id": "asp/2000/1", "query": "audit"},
                            "final_result": "Section 21 text."},
                           {"name": "search_legislation", "args": {"query": "late"},
                            "budget_blocked": True,
                            "final_result": '{"searched": false}'}]},
            ]},
        }],
    }
    doc.update(over)
    return doc


@pytest.fixture
def run_file(tmp_path):
    p = tmp_path / "6365_rep1.json"
    p.write_text(json.dumps(_run_doc()), encoding="utf-8")
    return p


# --- 1 + 2. the fixture, and the product's own builder ----------------------


def test_the_turn_is_found_and_a_missing_one_is_an_error(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    assert doc["session_id"] == "6365" and turn["turn"] == 1
    with pytest.raises(SystemExit):
        sr.load_turn(run_file, 7)


def test_step_findings_pair_the_plan_with_its_delegations(run_file):
    _doc, turn = sr.load_turn(run_file, 1)
    findings = sr.step_findings_from(turn)
    assert [f["title"] for f in findings] == ["Accounts", "Audit"]
    assert [f["detail"] for f in findings] == ["Find the duties.", "Find the deadlines."]
    assert "s.57(3)(a)" in findings[0]["content"]
    # A step whose delegation is missing contributes an empty finding, not a crash.
    turn["audit"]["delegations"] = [turn["audit"]["delegations"][1]]
    assert sr.step_findings_from(turn)[0]["content"] == ""


def test_halted_steps_are_carried(run_file):
    _doc, turn = sr.load_turn(run_file, 1)
    (halt,) = sr.halts_from(turn)
    assert (halt["step"], halt["scope"], halt["reason"]) == (2, "step", "step_cap")


def test_the_synthesis_payload_is_the_products_own(run_file):
    """If this drifts, the tool measures something the product never sends."""
    doc, turn = sr.load_turn(run_file, 1)
    built = sr.synthesis_messages(doc, turn)
    expected = agent_core.build_synthesis_messages(
        turn["question"], turn["plan"], sr.step_findings_from(turn),
        sr.halts_from(turn), 2)
    assert built == expected
    body = built[1]["content"]
    assert "PINPOINTS TO KEEP" in body                 # P3.1
    assert f"- {S57}: s.57(3)(a)" in body
    assert "step 2 of 2" in body or "incomplete" in body.lower()   # P2.1/P2.2
    assert built[0]["content"] == agent_core.get_deep_research_synthesis_prompt(
        "legislation_only")


@pytest.mark.parametrize("research_mode", [
    "legislation_and_case_law", "parliamentary_records"])
def test_the_synthesis_payload_carries_the_turns_research_type(run_file, research_mode):
    """P4.7: the product builds the synthesis prompt per research type, so the
    seam must pass the stored turn's type, or it replays the wrong prompt."""
    doc, turn = sr.load_turn(run_file, 1)
    turn["research_mode"] = research_mode
    built = sr.synthesis_messages(doc, turn)
    assert built[0]["content"] == agent_core.get_deep_research_synthesis_prompt(research_mode)


def test_an_old_run_file_takes_the_type_the_audit_recorded(run_file):
    """A run file written before turns carried a type: the audit trace's."""
    doc, turn = sr.load_turn(run_file, 1)
    doc["filters"]["research_mode"] = None
    turn["audit"]["research_mode"] = "legislation_and_case_law"
    assert sr._cfg_for(doc, turn)["_research_mode"] == "legislation_and_case_law"


def test_a_turn_with_no_step_findings_is_refused(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    for dg in turn["audit"]["delegations"]:
        dg["report"] = ""
    with pytest.raises(SystemExit):
        sr.synthesis_messages(doc, turn)


# --- 3. the Worker seam -----------------------------------------------------


def test_the_worker_seam_replays_the_recorded_results_and_forces_composition(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    msgs = sr.worker_messages(doc, turn, delegation=1)
    assert [m["role"] for m in msgs] == [
        "system", "user", "assistant", "tool", "tool", "user"]
    assert msgs[1]["content"] == "Accounts duties"
    ids = [c["id"] for c in msgs[2]["tool_calls"]]
    assert ids == [m["tool_call_id"] for m in msgs if m["role"] == "tool"]
    assert msgs[4]["content"] == "Section 57 text."
    assert "Compose your report" in msgs[-1]["content"]


def test_a_refused_call_is_not_replayed_as_a_retrieval(run_file):
    """A budget-blocked call returned no results; feeding its stop message back
    as a tool result would invent a retrieval the run never made."""
    doc, turn = sr.load_turn(run_file, 1)
    msgs = sr.worker_messages(doc, turn, delegation=2)
    assert [m["content"] for m in msgs if m["role"] == "tool"] == ["Section 21 text."]


def test_the_worker_seam_needs_a_delegation_with_tools(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    turn["audit"]["delegations"] = []
    with pytest.raises(SystemExit):
        sr.worker_messages(doc, turn)


def test_the_recorded_filters_reach_the_prompt(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    cfg = sr._cfg_for(doc, turn)
    assert cfg["_research_mode"] == "legislation_only"
    assert cfg["_jurisdiction"] == "scotland" and cfg["_year_to"] == 2026
    assert cfg["_chat_mode"] == "deep_research"


# --- 4. --without-fix really removes the fix --------------------------------


def _fake_rev(monkeypatch, agent_core_text: str, prompts_text: str = "OLD = 1"):
    """`_file_at` for a made-up revision: its agent_core.py and prompts.py."""
    def _file_at(rev, path):
        return agent_core_text if path.endswith("agent_core.py") else prompts_text
    monkeypatch.setattr(sr, "_file_at", _file_at)
    monkeypatch.setattr(sr, "_prompt_constant_at",
                        lambda rev, name: f"OLD {name} @ {rev}")


def test_without_fix_before_p31_strips_the_block_and_swaps_the_prompt(run_file, monkeypatch):
    _fake_rev(monkeypatch, "def build_synthesis_messages(): pass")
    doc, turn = sr.load_turn(run_file, 1)
    msgs = sr.synthesis_messages(doc, turn, without_fix=True, rev="abc1234")
    assert msgs[0]["content"] == "OLD DEEP_RESEARCH_SYNTHESIS_PROMPT @ abc1234"
    assert "PINPOINTS TO KEEP" not in msgs[1]["content"]
    # Everything else is untouched: the findings and the halt note survive.
    assert "s.57(3)(a)" in msgs[1]["content"]
    assert "STEP FINDINGS" in msgs[1]["content"]


def test_without_fix_after_p31_keeps_the_block_and_changes_only_the_prompt(
        run_file, monkeypatch):
    """P4.7: the block used to be stripped whatever `--rev` was, so a
    before-side at a post-P3.1 commit differed from the after-side in the
    prompt AND the block. Now the user message is byte-identical."""
    _fake_rev(monkeypatch, "x += pinpoint_block([f['content'] for f in s])")
    doc, turn = sr.load_turn(run_file, 1)
    live = sr.synthesis_messages(doc, turn)
    old = sr.synthesis_messages(doc, turn, without_fix=True, rev="abc1234")
    assert old[1] == live[1]
    assert "PINPOINTS TO KEEP" in old[1]["content"]
    assert old[0]["content"] == "OLD DEEP_RESEARCH_SYNTHESIS_PROMPT @ abc1234"


@pytest.mark.parametrize("research_mode", [
    "legislation_only", "legislation_and_case_law", "parliamentary_records"])
def test_without_fix_at_a_per_type_revision_builds_that_types_prompt(
        run_file, monkeypatch, research_mode):
    """From P4.7 the prompt is built per research type, which a regex cannot
    read back; the revision's own builder is run for the turn's type."""
    _fake_rev(monkeypatch, "pinpoint_block(",
              "def get_deep_research_synthesis_prompt(research_mode):\n"
              "    return 'OLD BUILT FOR ' + research_mode\n")
    doc, turn = sr.load_turn(run_file, 1)
    turn["research_mode"] = research_mode
    msgs = sr.synthesis_messages(doc, turn, without_fix=True, rev="abc1234")
    assert msgs[0]["content"] == f"OLD BUILT FOR {research_mode}"


def test_the_pinpoint_block_is_read_off_real_revisions():
    """Pinned against git: the default rev predates P3.1's block, HEAD has it.
    (Fails in a copy that is not a git checkout, like the two readers below.)"""
    assert sr.rev_has_pinpoint_block(sr.PRE_P31_REV) is False
    assert sr.rev_has_pinpoint_block("HEAD") is True


def test_without_fix_swaps_the_right_worker_prompt(run_file, monkeypatch):
    seen = []
    monkeypatch.setattr(sr, "_prompt_constant_at",
                        lambda rev, name: seen.append(name) or "OLD WORKER")
    doc, turn = sr.load_turn(run_file, 1)
    sr.worker_messages(doc, turn, without_fix=True)
    assert seen == ["WORKER_SYSTEM_PROMPT"]          # not the conversational one
    turn["chat_mode"] = "conversational"
    sr.worker_messages(doc, turn, without_fix=True)
    assert seen[-1] == "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"


@pytest.mark.parametrize("research_mode,chat_mode,name", [
    ("legislation_only", "research", "WORKER_SYSTEM_PROMPT"),
    ("case_law_only", "research", "WORKER_SYSTEM_PROMPT_CASE_LAW"),
    ("legislation_and_case_law", "research", "WORKER_SYSTEM_PROMPT_HYBRID"),
    ("case_law_only", "conversational", "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"),
    ("legislation_only", "deep_research", "WORKER_SYSTEM_PROMPT"),
])
def test_without_fix_swaps_the_constant_of_the_turns_research_type(
        run_file, monkeypatch, research_mode, chat_mode, name):
    """P4.6: the A/B side must be the Worker the turn actually ran. Before, a
    case-law-only or hybrid turn got `WORKER_SYSTEM_PROMPT` swapped in, which
    is the wrong Worker and carries the wrong scripted lines."""
    seen = []
    monkeypatch.setattr(sr, "_prompt_constant_at",
                        lambda rev, n: seen.append(n) or "OLD WORKER")
    doc, turn = sr.load_turn(run_file, 1)
    turn["research_mode"], turn["chat_mode"] = research_mode, chat_mode
    sr.worker_messages(doc, turn, without_fix=True)
    assert seen == [name]


def test_without_fix_replaces_only_the_literal(run_file, monkeypatch):
    """The without side keeps the date line, the rules appended to the literal
    and the filter block, so the A/B differs in the literal alone."""
    monkeypatch.setattr(sr, "_prompt_constant_at", lambda rev, n: "OLD WORKER LITERAL")
    doc, turn = sr.load_turn(run_file, 1)
    turn["research_mode"], turn["chat_mode"] = "legislation_only", "research"
    live = sr.worker_messages(doc, turn)[0]["content"]
    old = sr.worker_messages(doc, turn, without_fix=True)[0]["content"]
    assert "OLD WORKER LITERAL" in old
    assert sr._prompt_constant_in_tree("WORKER_SYSTEM_PROMPT") not in old
    for kept in ("Today's date is", "IN-FORCE STATUS", "NOT HELD IS NOT A WRONG CITATION"):
        assert kept in live and kept in old
    # Only the literal differs.
    lit = sr._prompt_constant_in_tree("WORKER_SYSTEM_PROMPT")
    assert old == live.replace(lit, "OLD WORKER LITERAL", 1)


def test_the_prompt_reader_finds_a_real_constant():
    """Reads `prompts.py` at a revision with a regex; pinned against HEAD so a
    change to how the constants are written is caught here."""
    # A constant that is still one literal. The synthesis prompt stopped being
    # one at P4.7, so it is read at the commit before (`9cacde8`) below.
    text = sr._prompt_constant_at("HEAD", "WORKER_SYSTEM_PROMPT")
    assert "OUTPUT STRUCTURE" in text
    with pytest.raises(SystemExit):
        sr._prompt_constant_at("HEAD", "NO_SUCH_PROMPT_CONSTANT")


def test_the_synthesis_prompt_before_p47_is_the_one_literal():
    """At the commit P4.7's acceptance was booked on, the synthesis prompt is
    the single constant, whatever the research type. (Needs git.)"""
    old = sr._synthesis_prompt_at("9cacde8", "parliamentary_records")
    assert "No reported case law was found on X" in old
    assert "Jurisdiction & Status" in old
    assert old == sr._synthesis_prompt_at("9cacde8", "legislation_only")


# --- 5. the command ---------------------------------------------------------


def test_dry_run_builds_the_payload_and_calls_no_model(run_file, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("--dry-run must not call the model")

    monkeypatch.setattr(sr, "run_seam", boom)
    monkeypatch.setattr(sr, "_provider_cfg", boom)
    assert sr.main(["synthesis", "--run", str(run_file), "--turn", "1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "session=6365 turn=1" in out and "current code" in out
    assert "pinpoint block: present" in out


def test_the_grader_is_only_applied_where_there_is_a_ground_truth():
    assert sr._grade("6365", "Under s.57(3)(a) …").startswith(("DELIVERED", "PARTIAL",
                                                              "SHALLOW", "MISSED"))
    assert sr._grade("9999", "anything") == ""


# --- 6. --from-raw: the summarised-path blocks rebuilt through the product ---
#
# P3.11. The seam replays `final_result`, so a block the product builds in
# `run_worker_tool` from the RAW result (P1.6's URLs, P3.11's outline) is in a
# fixture only if it existed when the run was recorded. `--from-raw` rebuilds
# those blocks through `agent_shared.summarised_result_blocks`, the product's
# own builder, and leaves the recorded summary and the per-tool notes alone.

from src.agent.agent_shared import summarised_result_blocks  # noqa: E402
from src.utils.citation_links import provision_url_block  # noqa: E402

_S36 = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
_RAW_S36 = json.dumps({"results": [{
    "legislation_id": "asp/2002/13", "number": 36, "provision_type": "section",
    "title": "Confidentiality", "url": _S36,
    "text": ("Section 36) **Confidentiality**\n\n"
             "1) Information in respect of which a claim to confidentiality of "
             "communications could be maintained in legal proceedings is exempt "
             "information. \n"
             "2) Information is exempt information if— \n"
             "\ta) it was obtained by a Scottish public authority from another "
             "person; and \n\tb) its disclosure would be a breach of confidence. "),
}], "returned": 1})
_SCOPE = "\n\n[SEARCH SCOPE — 1 provision(s) of asp/2002/13, ranked by relevance to \"x\".]"


def _summarised_tool(with_url_block=True, with_scope=True, summarised=True):
    final = "Summary: s.36(1) only."
    if with_url_block:
        final += provision_url_block(_RAW_S36)
    if with_scope:
        final += _SCOPE
    return {"name": "search_legislation_sections",
            "args": {"legislation_id": "asp/2002/13", "query": "x"},
            "raw_result": _RAW_S36, "final_result": final, "summarised": summarised}


def _tool_contents(msgs):
    return [m["content"] for m in msgs if m["role"] == "tool"]


def test_from_raw_rebuilds_the_blocks_where_the_product_puts_them(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    turn["audit"]["delegations"][0]["tools"][1] = _summarised_tool()
    recorded = _tool_contents(sr.worker_messages(doc, turn, delegation=1))[1]
    rebuilt = _tool_contents(sr.worker_messages(doc, turn, delegation=1, from_raw=True))[1]
    assert "[SECTION OUTLINE" not in recorded                  # the before-column
    assert rebuilt.startswith("Summary: s.36(1) only.")        # the summary is kept
    assert rebuilt.endswith(_SCOPE)                            # and so is the note
    assert rebuilt.index("[CITATION URLS") < rebuilt.index("[SECTION OUTLINE") < rebuilt.index("[SEARCH SCOPE")
    assert rebuilt.count("[CITATION URLS") == 1
    assert "(2) Information is exempt information if" in rebuilt
    # Through the product's own builder, not a copy of it.
    assert summarised_result_blocks("search_legislation_sections", _RAW_S36) in rebuilt


def test_from_raw_leaves_an_unsummarised_result_alone(run_file):
    """The product appends these blocks on the summarised path only."""
    doc, turn = sr.load_turn(run_file, 1)
    turn["audit"]["delegations"][0]["tools"][1] = _summarised_tool(
        with_url_block=False, summarised=False)
    before = _tool_contents(sr.worker_messages(doc, turn, delegation=1))
    after = _tool_contents(sr.worker_messages(doc, turn, delegation=1, from_raw=True))
    assert after == before


def test_from_raw_on_a_fixture_recorded_before_the_url_block(run_file):
    """No recorded block to replace: both blocks go in front of the scope note,
    which is where the product puts them."""
    doc, turn = sr.load_turn(run_file, 1)
    turn["audit"]["delegations"][0]["tools"][1] = _summarised_tool(with_url_block=False)
    rebuilt = _tool_contents(sr.worker_messages(doc, turn, delegation=1, from_raw=True))[1]
    assert rebuilt.startswith("Summary: s.36(1) only.")
    assert rebuilt.index("[CITATION URLS") < rebuilt.index("[SECTION OUTLINE") < rebuilt.index("[SEARCH SCOPE")
    assert rebuilt.endswith(_SCOPE)


def test_from_raw_with_no_scope_note_appends(run_file):
    doc, turn = sr.load_turn(run_file, 1)
    turn["audit"]["delegations"][0]["tools"][1] = _summarised_tool(
        with_url_block=False, with_scope=False)
    rebuilt = _tool_contents(sr.worker_messages(doc, turn, delegation=1, from_raw=True))[1]
    assert rebuilt.startswith("Summary: s.36(1) only.")
    assert rebuilt.rstrip().endswith("[/SECTION OUTLINE]")


def test_from_raw_is_a_no_op_when_the_product_would_add_nothing(run_file):
    """A raw result with nothing to hand back (no provision rows) is returned
    exactly as recorded, so the option never invents a block."""
    doc, turn = sr.load_turn(run_file, 1)
    t = _summarised_tool()
    t["raw_result"] = json.dumps({"results": []})
    t["final_result"] = "Summary." + _SCOPE
    turn["audit"]["delegations"][0]["tools"][1] = t
    rebuilt = _tool_contents(sr.worker_messages(doc, turn, delegation=1, from_raw=True))[1]
    assert rebuilt == "Summary." + _SCOPE


def test_dry_run_reports_the_outline_count(run_file, monkeypatch, capsys):
    doc = _run_doc()
    doc["turns"][0]["audit"]["delegations"][0]["tools"][1] = _summarised_tool()
    run_file.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(sr, "run_seam", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    assert sr.main(["worker", "--run", str(run_file), "--turn", "1", "--dry-run"]) == 0
    assert "results: 2, with a subsection outline: 0  (as recorded)" in capsys.readouterr().out
    assert sr.main(["worker", "--run", str(run_file), "--turn", "1", "--dry-run",
                    "--from-raw"]) == 0
    assert "results: 2, with a subsection outline: 1  (rebuilt from raw)" in capsys.readouterr().out

# --- 7. the Manager seam (P3.13) ---------------------------------------------
#
# The conversational Manager composing the worker report into the answer: the
# conversation so far, each recorded delegation as the `delegate_research`
# call it was and the result `manager_tool_executor` returns, then a tool-free
# call. Pinned against the product's own builders, like the other two seams.

FOISA36 = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
CONV_REPORT = (f"Under [s.36(1)]({FOISA36}), information is exempt (while s.36(2) "
               "exempts information obtained from another person).\n\n"
               "[SEARCH SCOPE — what this research step actually did]\nx\n[/SEARCH SCOPE]")


def _conv_doc():
    return {
        "session_id": "6348", "rep": 1,
        "filters": {"research_mode": "legislation_only"},
        "runtime_state": {"model": "m", "suggested_questions_enabled": True},
        "turns": [
            {"turn": 1, "question": "Q1", "chat_mode": "conversational",
             "answer": "A1", "audit": {"delegations": [
                 {"step": None, "brief": "brief one", "report": CONV_REPORT}]}},
            {"turn": 2, "question": "Q2", "chat_mode": "conversational",
             "answer": "A2", "audit": {"delegations": [
                 {"step": None, "brief": "brief two", "report": CONV_REPORT},
                 {"step": 3, "brief": "a Deep Research step", "report": "not mine"}]}},
            {"turn": 3, "question": "Q3", "chat_mode": "conversational",
             "answer": "A3", "audit": {"delegations": []}},
        ],
    }


def test_the_manager_payload_is_built_by_the_product():
    from src.prompts import get_manager_system_prompt
    doc = _conv_doc()
    msgs = sr.manager_messages(doc, doc["turns"][0])
    cfg = sr.manager_cfg(doc, doc["turns"][0], [{"role": "user", "content": "Q1"}])
    assert msgs[0] == {"role": "system",
                       "content": get_manager_system_prompt("legislation_only", cfg)}
    assert msgs[1] == {"role": "user", "content": "Q1"}
    call = msgs[2]["tool_calls"][0]["function"]
    assert call["name"] == "delegate_research"
    assert json.loads(call["arguments"]) == {"query": "brief one"}
    # The tool result is `worker_result_for_manager`'s, sibling link included.
    assert msgs[3]["content"] == agent_core.worker_result_for_manager(CONV_REPORT, cfg)
    assert f"[s.36(2)]({FOISA36})" in msgs[3]["content"]


def test_the_conversational_prompt_is_the_one_the_target_runs():
    """`research_mode_enabled` was OFF on the target and is pinned OFF for a
    replay (P4.1); a run file recorded before it was a pinned flag must not
    silently get the app's default, which is ON."""
    from src.prompts import RESEARCH_MODE_HINT_OFF
    doc = _conv_doc()
    system = sr.manager_messages(doc, doc["turns"][0])[0]["content"]
    assert "CURRENT MODE: Chat" in system
    assert RESEARCH_MODE_HINT_OFF in system


def test_a_later_turn_carries_the_history_and_skips_deep_research_steps():
    doc = _conv_doc()
    msgs = sr.manager_messages(doc, doc["turns"][1])
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user", "assistant", "tool"]
    assert msgs[1]["content"] == "Q1" and msgs[2]["content"] == "A1"
    assert msgs[3]["content"].endswith("Q2")
    # The client's mode stamps are not provider fields.
    assert all("chat_mode" not in m and "research_mode" not in m for m in msgs)
    assert "not mine" not in json.dumps(msgs)


def test_a_turn_with_no_delegation_is_refused():
    doc = _conv_doc()
    with pytest.raises(SystemExit):
        sr.manager_messages(doc, doc["turns"][2])


def test_manager_without_fix_hands_over_the_bare_report_and_the_old_body(monkeypatch):
    monkeypatch.setattr(sr, "_prompt_constant_at",
                        lambda rev, name: f"OLD {name} @ {rev}")
    doc = _conv_doc()
    msgs = sr.manager_messages(doc, doc["turns"][0], without_fix=True, rev="abc1234")
    assert msgs[3]["content"] == f"[Research Agent Result]\n{CONV_REPORT}"
    assert "OLD _MANAGER_CONV_BODY @ abc1234" in msgs[0]["content"]
    assert "CITATION PRESERVATION" not in msgs[0]["content"]


def test_the_manager_body_reader_finds_the_constant():
    text = sr._prompt_constant_at("HEAD", "_MANAGER_CONV_BODY")
    assert "CURRENT MODE: Chat" in text


@pytest.mark.parametrize("flags,offered", [([], True), (["--no-tools"], False)])
def test_the_manager_is_offered_its_tools_unless_told_not_to(tmp_path, monkeypatch,
                                                            flags, offered):
    """Tool-free, the seam delivered a payload the live Manager flattened
    (`wave3_p313` rep 1 turn 1, 3 of 3 draws); offered the tools the live
    call carries, it reproduced the miss in 3 of 3."""
    p = tmp_path / "6348_rep1.json"
    p.write_text(json.dumps(_conv_doc()), encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_seam(messages, cfg, tools=None):
        seen["tools"] = tools
        return "Answer.", 0.0, "m"

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_seam", fake_seam)
    assert sr.main(["manager", "--run", str(p), "--turn", "1", *flags]) == 0
    names = [t["function"]["name"] for t in (seen["tools"] or [])]
    assert ("delegate_research" in names) is offered


# --- P3.15: manager --first-round ------------------------------------------------

def _p315_doc():
    """p37_6409-shaped: export turn 9 looks SSI 2025/377 up (not held), and
    export turn 11 is answered from history."""
    look = {"name": "lookup_legislation", "args": {},
            "raw_result": json.dumps({"legislation_id": "ssi/2025/377",
                                      "status": "not_held", "routed_by_code": True})}
    return {
        "session_id": "p37_6409", "rep": 1,
        "script": {"base": "6409", "turns": [{"from_turn": 9}, {"from_turn": 11}]},
        "filters": {"research_mode": "legislation_only"},
        "runtime_state": {"model": "m"},
        "turns": [
            {"turn": 1, "question": "Q9", "chat_mode": "conversational",
             "answer": "SSI 2025/377 is not held in this index.",
             "audit": {"delegations": [{"step": None, "brief": "Find SSI 2025/377",
                                        "report": "r", "tools": [look]}]}},
            {"turn": 2, "question": "Q11", "chat_mode": "conversational",
             "answer": "A", "audit": {"delegations": []}},
        ],
    }


def test_the_manager_head_is_the_first_round_of_a_from_history_turn():
    doc = _p315_doc()
    msgs, cfg = sr.manager_head(doc, doc["turns"][1])
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"].endswith("Q11")
    # the composition seam still refuses a turn with nothing to compose from,
    # and starts with the same head
    with pytest.raises(SystemExit):
        sr.manager_messages(doc, doc["turns"][1])
    head, _ = sr.manager_head(doc, doc["turns"][0])
    assert sr.manager_messages(doc, doc["turns"][0])[:2] == sr._strip_stamps(head)
    # --date pins the Manager prompt's date line and changes nothing else
    pinned, _ = sr.manager_head(doc, doc["turns"][1], on_date=sr.date(2026, 9, 24))
    assert "Today's date is 24 September 2026." in pinned[0]["content"]
    assert pinned[0]["content"].replace(
        "Today's date is 24 September 2026.",
        sr.worker_date_line(sr.date.today()), 1) == msgs[0]["content"]
    assert pinned[1:] == msgs[1:]


@pytest.mark.parametrize("answer,verdict", [
    ("The text of SSI 2025/377 is not available here.", "FAIL"),
    ("This index does not hold SSI 2025/377 itself.", "PASS"),
])
def test_a_manager_first_round_answer_is_graded_by_lookup(tmp_path, monkeypatch, capsys,
                                                         answer, verdict):
    p = tmp_path / "p37_6409_rep1.json"
    p.write_text(json.dumps(_p315_doc()), encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_first(messages, cfg, tools):
        seen["tools"] = [t["function"]["name"] for t in tools]
        seen["roles"] = [m["role"] for m in messages]
        return answer, [], 0.01, "m"

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_first_round", fake_first)
    assert sr.main(["manager", "--run", str(p), "--turn", "2", "--first-round"]) == 0
    out = capsys.readouterr().out
    assert "delegate_research" in seen["tools"]
    assert seen["roles"][-1] == "user"
    assert "ANSWERED FROM HISTORY" in out
    assert f"lookup: ssi/2025/377 {verdict}" in out


def test_a_manager_first_round_delegation_prints_the_numbers_its_brief_names(
        tmp_path, monkeypatch, capsys):
    p = tmp_path / "p37_6409_rep1.json"
    p.write_text(json.dumps(_p315_doc()), encoding="utf-8")

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_first(messages, cfg, tools):
        return "", [("delegate_research",
                     json.dumps({"query": "Commencement of 2025 asp 2 by SSI 2025/377"}))], 0.01, "m"

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_first_round", fake_first)
    assert sr.main(["manager", "--run", str(p), "--turn", "1", "--first-round"]) == 0
    out = capsys.readouterr().out
    assert "its first brief named 2025/377" in out
    assert "DELEGATED: delegate_research" in out
    assert "brief names: 2025 asp 2, 2025/377" in out


# --- P4.5: --apply-lost -------------------------------------------------------

_SCOPE_ONLY = (
    "\n\n[SEARCH SCOPE — what this research step actually did]\n"
    "Searched the legislation index 1 time(s) for: \"x\".\n[/SEARCH SCOPE]"
)


def _lost_doc():
    """A Deep Research turn whose step 1 reply was lost (6375 r3 t2's shape:
    report "") and whose step 2 report is its scope block alone (6374 r3
    t4's shape)."""
    doc = _run_doc()
    dgs = doc["turns"][0]["audit"]["delegations"]
    dgs[0]["report"] = ""
    dgs[1].pop("halted")
    dgs[1]["report"] = _SCOPE_ONLY
    return doc


def test_the_recorded_payload_is_the_before_side():
    doc = _lost_doc()
    body = sr.synthesis_messages(doc, doc["turns"][0])[1]["content"]
    assert "[Research Incomplete" not in body and "LOST STEPS" not in body


def test_apply_lost_labels_each_lost_report_ahead_of_what_was_recorded():
    from src.utils.research_halt import LOST_REPORT_TAG
    doc = _lost_doc()
    turn = doc["turns"][0]
    findings = sr.step_findings_from(turn, apply_lost=True)
    assert all(f["content"].startswith(LOST_REPORT_TAG) for f in findings)
    assert findings[1]["content"].endswith(_SCOPE_ONLY)  # the record kept, after
    assert [x["step"] for x in sr.lost_from(turn, apply_lost=True)] == [1, 2]
    body = sr.synthesis_messages(doc, turn, apply_lost=True)[1]["content"]
    assert "LOST STEPS" in body


def test_a_halted_or_answered_step_is_never_relabelled(run_file):
    _doc, turn = sr.load_turn(run_file, 1)
    assert not any(sr.is_lost_shaped(d) for d in turn["audit"]["delegations"])
    assert sr.lost_from(turn, apply_lost=True) == []


def test_a_step_recorded_as_lost_is_read_without_the_flag():
    doc = _lost_doc()
    turn = doc["turns"][0]
    turn["audit"]["delegations"][0]["lost"] = {"reason": "empty_completion",
                                               "sources_retrieved": 4}
    (x,) = [x for x in sr.lost_from(turn) if x["step"] == 1]
    assert x["sources_retrieved"] == 4


def test_the_manager_seam_hands_over_the_labelled_report(tmp_path, monkeypatch):
    from src.utils.research_halt import LOST_REPORT_TAG
    doc = _conv_doc()
    doc["turns"][0]["audit"]["delegations"][0]["report"] = _SCOPE_ONLY
    msgs = sr.manager_messages(doc, doc["turns"][0], apply_lost=True)
    tool = [m for m in msgs if m.get("role") == "tool"][0]["content"]
    assert tool.startswith("[Research Agent Result]\n" + LOST_REPORT_TAG)
    before = sr.manager_messages(doc, doc["turns"][0])
    assert LOST_REPORT_TAG not in [m for m in before if m.get("role") == "tool"][0]["content"]

    # The draw goes through the answer seam: one lost delegation that nothing
    # made good, so the lawyer notice is prepended.
    p = tmp_path / "6348_rep1.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "out"

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_seam(messages, cfg, tools=None):
        return "Nothing was found.", 0.0, "m"

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_seam", fake_seam)
    assert sr.main(["manager", "--run", str(p), "--turn", "1", "--apply-lost",
                    "--out", str(out)]) == 0
    text = (out / "6348_t1_manager_lost_rep1.md").read_text(encoding="utf-8")
    assert text.startswith("> **⚠ This answer is incomplete.**")


def test_apply_lost_is_not_a_worker_seam_option(run_file):
    with pytest.raises(SystemExit):
        sr.main(["worker", "--run", str(run_file), "--turn", "1", "--apply-lost",
                 "--dry-run"])


# ---------------------------------------------------------------------------
# --as-sent (P4.10): a Worker call rebuilt as chat_loop sent it
# ---------------------------------------------------------------------------
#
# Checked on the stored (a) calls before any draw: the regrouped rounds equal
# every call's recorded react_turn, and both wave3_p313 payloads rebuild to
# exactly the recorded sent_chars (41,906 and 25,277).

def _t(name, start, dur, result="r"):
    return {"name": name, "args": {"q": name}, "final_result": result,
            "started_at": start, "duration_s": dur}


def test_parallel_tools_share_a_round_and_a_later_start_opens_one():
    tools = [_t("a", 9.4, 0.7), _t("b", 13.2, 4.9), _t("c", 13.21, 1.0),
             _t("d", 25.8, 0.0),   # a memo hit: zero duration
             _t("e", 25.81, 0.4),  # started with d, after d "ended"
             _t("f", 31.2, 0.4)]
    rounds = sr.tool_rounds(tools)
    assert [[t["name"] for t in r] for r in rounds] == [["a"], ["b", "c"],
                                                       ["d", "e"], ["f"]]


def _as_sent_doc():
    return {"session_id": "6348", "rep": 2,
            "filters": {"research_mode": "legislation_only"},
            "turns": [{"turn": 1, "question": "Q", "chat_mode": "conversational",
                       "audit": {"empty_completions": [
                           {"sent_chars": 1, "react_turn": 2, "attempt": 1}],
                           "delegations": [{"brief": "the brief", "tools": [
                               _t("search_legislation", 5.0, 1.0, "R1"),
                               _t("search_legislation_sections", 9.0, 2.0, "R2"),
                               _t("get_legislation_changes", 9.1, 1.0, "R3")]}]}}]}


def test_the_as_sent_payload_is_rounds_not_a_compose_message():
    doc = _as_sent_doc()
    msgs = sr.worker_as_sent_messages(doc, doc["turns"][0])
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool",
                                         "assistant", "tool", "tool"]
    assert msgs[1]["content"] == "the brief"
    assert [c["function"]["name"] for c in msgs[4]["tool_calls"]] == [
        "search_legislation_sections", "get_legislation_changes"]
    # the ids pair each call with its result
    assert [m["tool_call_id"] for m in msgs[5:]] == [
        c["id"] for c in msgs[4]["tool_calls"]]
    # no closing "compose" message: the call that reasoned to nothing had none
    assert msgs[-1]["role"] == "tool"
    # sent_chars counts content the way chat_loop does
    assert sr.sent_chars(msgs) == len(msgs[0]["content"]) + len("the brief") + 6
    # cut at a round
    assert len(sr.worker_as_sent_messages(doc, doc["turns"][0], upto_round=1)) == 4


def test_an_as_sent_draw_offers_the_workers_tools_and_prints_the_outcome(
        tmp_path, monkeypatch, capsys):
    p = tmp_path / "6348_rep2.json"
    p.write_text(json.dumps(_as_sent_doc()), encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_run(messages, cfg, tools, extra=None):
        seen.update(tools=[t["function"]["name"] for t in tools], extra=extra)
        return {"content_chars": 0, "tool_calls": [], "finish_reason": "stop",
                "native_finish_reason": "STOP", "reasoning_chars": 60000,
                "completion_tokens": 62912, "reasoning_tokens": 62900,
                "cost": 0.77, "stream_error": None, "seconds": 350.0}

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_as_sent", fake_run)
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--reasoning-effort", "low", "--max-tokens", "16000"]) == 0
    assert "search_legislation" in seen["tools"]
    assert seen["extra"] == {"reasoning": {"effort": "low"}, "max_tokens": 16000}
    out = capsys.readouterr().out
    assert "recorded empty-completion call: sent_chars 1, react_turn 2" in out
    assert "rep1: empty (a)" in out and "$0.7700" in out
    assert "links:" not in out  # nothing to grade on an empty draw


def test_an_answered_as_sent_draw_is_graded_and_written(tmp_path, monkeypatch, capsys):
    p = tmp_path / "6348_rep2.json"
    p.write_text(json.dumps(_as_sent_doc()), encoding="utf-8")

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_run(messages, cfg, tools, extra=None):
        return {"content_chars": 60, "content": f"See [s.36(1)]({FOISA36}).",
                "tool_calls": [], "finish_reason": "stop", "native_finish_reason": "STOP",
                "reasoning_chars": 0, "completion_tokens": 200, "reasoning_tokens": 0,
                "cost": 0.01, "stream_error": None, "seconds": 4.0}

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_as_sent", fake_run)
    out_dir = tmp_path / "out"
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--reasoning-effort", "low", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "rep1: answered" in out and "links: 1" in out
    assert (out_dir / "6348_t1_d1_as_sent_effort-low_rep1.md").read_text(
        encoding="utf-8").startswith("See [s.36(1)]")


def test_as_sent_outcomes():
    base = {"content_chars": 0, "tool_calls": [], "finish_reason": "stop",
            "reasoning_chars": 0, "completion_tokens": None, "stream_error": None}
    assert sr.as_sent_outcome({**base, "content_chars": 5}) == "answered"
    assert sr.as_sent_outcome({**base, "tool_calls": ["x"]}) == "tool call"
    assert sr.as_sent_outcome({**base, "completion_tokens": 62912}) == "empty (a)"
    assert sr.as_sent_outcome(base) == "empty (c)"
    # P4.10, Session 29: a capped runaway ended in a lone newline. The product
    # (`is_empty_completion`) calls that empty; so must the seam.
    assert sr.as_sent_outcome({**base, "content": "\n", "content_chars": 1,
                               "completion_tokens": 30719}) == "empty (a)"
    assert sr.as_sent_outcome({**base, "content": " \n", "content_chars": 2,
                               "tool_calls": ["x"]}) == "tool call"
    assert sr.as_sent_outcome({**base, "content": "Yes.", "content_chars": 4}) == "answered"


def test_lever_flags_need_as_sent(run_file):
    with pytest.raises(SystemExit):
        sr.main(["worker", "--run", str(run_file), "--turn", "1",
                 "--max-tokens", "100", "--dry-run"])
    with pytest.raises(SystemExit):
        sr.main(["worker", "--run", str(run_file), "--turn", "1",
                 "--date", "recorded", "--dry-run"])
    # worker --first-round does not pin the date line, so it refuses the flag
    # rather than silently drawing today's (Session 29)
    with pytest.raises(SystemExit):
        sr.main(["worker", "--run", str(run_file), "--turn", "1", "--first-round",
                 "--date", "recorded", "--dry-run"])


def test_as_sent_date_resolves_recorded_and_iso():
    doc = {"started_at": "2026-09-23T08:12:08+00:00"}
    assert sr.as_sent_date(None, doc) is None
    assert sr.as_sent_date("recorded", doc) == sr.date(2026, 9, 23)
    assert sr.as_sent_date("2026-09-24", doc) == sr.date(2026, 9, 24)
    with pytest.raises(SystemExit):
        sr.as_sent_date("recorded", {})
    with pytest.raises(SystemExit):
        sr.as_sent_date("24/09/2026", doc)


def test_the_as_sent_payload_carries_the_pinned_date_line():
    # P4.10, Session 29: the date line alone decided whether a stored (a)
    # payload ran away, so the faithful payload is the one with its own date.
    doc = _as_sent_doc()
    today = sr.worker_as_sent_messages(doc, doc["turns"][0])
    pinned = sr.worker_as_sent_messages(doc, doc["turns"][0],
                                        on_date=sr.date(2026, 9, 23))
    assert today[0]["content"].startswith(sr.worker_date_line(sr.date.today()))
    assert pinned[0]["content"].startswith("Today's date is 23 September 2026.")
    # only the date line differs
    assert pinned[0]["content"].replace(
        "Today's date is 23 September 2026.",
        sr.worker_date_line(sr.date.today()), 1) == today[0]["content"]
    assert pinned[1:] == today[1:]


def test_an_as_sent_draw_with_a_date_prints_and_names_it(tmp_path, monkeypatch, capsys):
    p = tmp_path / "6348_rep2.json"
    p.write_text(json.dumps({**_as_sent_doc(), "started_at": "2026-09-23T08:12:08+00:00"}),
                 encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_run(messages, cfg, tools, extra=None):
        seen["system"] = messages[0]["content"]
        return {"content_chars": 1, "content": "\n", "tool_calls": [],
                "finish_reason": "stop", "native_finish_reason": "STOP",
                "reasoning_chars": 37310, "completion_tokens": 30719,
                "reasoning_tokens": 30718, "cost": 0.38, "stream_error": None,
                "seconds": 163.0}

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_as_sent", fake_run)
    out_dir = tmp_path / "out"
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--max-tokens", "32000", "--date", "recorded",
                    "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert seen["system"].startswith("Today's date is 23 September 2026.")
    assert "date line: 23 September 2026 (pinned by --date)" in out
    # a lone newline is empty, and an empty reply is not graded
    assert "rep1: empty (a)" in out and "links:" not in out
    assert (out_dir / "6348_t1_d1_as_sent_max-32000_date-2026-09-23_rep1.md").exists()


# ---------------------------------------------------------------------------
# --at-rev (P4.11): the Worker prompt and tools as the recorded head built them
# ---------------------------------------------------------------------------
#
# Checked before any draw: today's code rebuilt 1 of 7 stored (b) Worker
# payloads to their recorded sent_chars; the recorded head's own builder
# rebuilt all 7, and the two P4.10 payloads.

_OLD_PROMPTS = (
    "from datetime import date\n"
    "def get_worker_system_prompt(rm, cfg):\n"
    "    return (f\"Today's date is {date.today().strftime('%d %B %Y')}.\\n\"\n"
    "            f\"OLD WORKER PROMPT {rm}\")\n"
)
_OLD_SCHEMAS = (
    "def get_worker_tools(rm):\n"
    "    return [{'type': 'function', 'function': {'name': 'old_tool_' + rm,\n"
    "             'description': '', 'parameters': {'type': 'object'}}}]\n"
)


def _fake_file_at(seen):
    def fake(rev, path):
        seen.append((rev, path))
        return {"server_py/src/prompts.py": _OLD_PROMPTS,
                "server_py/src/agent/tools/schemas.py": _OLD_SCHEMAS}.get(path, "")
    return fake


def test_at_rev_resolves_recorded_to_the_runs_git_head():
    doc = {"runtime_state": {"git_head": "2d9ae11"}}
    assert sr.as_sent_rev(None, doc) is None
    assert sr.as_sent_rev("recorded", doc) == "2d9ae11"
    assert sr.as_sent_rev("8006db9", doc) == "8006db9"
    with pytest.raises(SystemExit):
        sr.as_sent_rev("recorded", {"runtime_state": {}})


def test_the_as_sent_payload_at_a_rev_uses_that_revs_worker_prompt(monkeypatch):
    seen = []
    monkeypatch.setattr(sr, "_file_at", _fake_file_at(seen))
    doc = _as_sent_doc()
    now = sr.worker_as_sent_messages(doc, doc["turns"][0], on_date=sr.date(2026, 9, 18))
    old = sr.worker_as_sent_messages(doc, doc["turns"][0], on_date=sr.date(2026, 9, 18),
                                     at_rev="2d9ae11")
    # the rev's own builder, with the pinned date line
    assert old[0]["content"] == ("Today's date is 18 September 2026.\n"
                                 "OLD WORKER PROMPT legislation_only")
    assert ("2d9ae11", "server_py/src/prompts.py") in seen
    # only the system prompt is the rev's: the brief and the rounds are recorded
    assert old[1:] == now[1:]


def test_an_as_sent_draw_at_the_recorded_rev_offers_that_revs_tools(
        tmp_path, monkeypatch, capsys):
    seen_files = []
    monkeypatch.setattr(sr, "_file_at", _fake_file_at(seen_files))
    p = tmp_path / "6385_rep1.json"
    p.write_text(json.dumps({**_as_sent_doc(), "started_at": "2026-09-18T12:56:23+00:00",
                             "runtime_state": {"git_head": "2d9ae11"}}),
                 encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_run(messages, cfg, tools, extra=None):
        seen.update(system=messages[0]["content"],
                    tools=[t["function"]["name"] for t in tools])
        return {"content_chars": 0, "content": "", "tool_calls": [],
                "finish_reason": "error", "native_finish_reason": None,
                "reasoning_chars": 560, "completion_tokens": 140,
                "reasoning_tokens": 139, "cost": 0.0,
                "stream_error": "Upstream idle timeout exceeded", "seconds": 130.0}

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_as_sent", fake_run)
    out_dir = tmp_path / "out"
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--date", "recorded", "--at-rev", "recorded",
                    "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert seen["system"].endswith("OLD WORKER PROMPT legislation_only")
    assert seen["tools"] == ["old_tool_legislation_only"]
    assert ("2d9ae11", "server_py/src/agent/tools/schemas.py") in seen_files
    assert "code: 2d9ae11 (--at-rev); tools offered: old_tool_legislation_only" in out
    assert "rep1: empty (b)" in out
    assert (out_dir / "6348_t1_d1_as_sent_date-2026-09-18_rev-2d9ae11_rep1.md").exists()


def test_the_working_tree_draw_names_its_code_and_tools(tmp_path, capsys):
    p = tmp_path / "6348_rep2.json"
    p.write_text(json.dumps(_as_sent_doc()), encoding="utf-8")
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "code: the working tree; tools offered: search_legislation" in out


def test_at_rev_is_an_as_sent_option_only(run_file):
    # refused rather than ignored, on every path that does not honour it
    for argv in (["worker", "--at-rev", "recorded"],
                 ["worker", "--first-round", "--at-rev", "recorded"],
                 ["manager", "--first-round", "--at-rev", "recorded"],
                 ["manager", "--at-rev", "recorded"]):
        with pytest.raises(SystemExit):
            sr.main([argv[0], "--run", str(run_file), "--turn", "1", *argv[1:],
                     "--dry-run"])


# ---------------------------------------------------------------------------
# --provider (P4.11): one OpenRouter upstream, and which one served the draw
# ---------------------------------------------------------------------------

def test_an_as_sent_draw_on_a_provider_routes_it_and_prints_who_served(
        tmp_path, monkeypatch, capsys):
    p = tmp_path / "6348_rep2.json"
    p.write_text(json.dumps(_as_sent_doc()), encoding="utf-8")
    seen = {}

    async def fake_cfg(extra):
        return {"model": "m", **extra}

    async def fake_run(messages, cfg, tools, extra=None):
        seen["extra"] = extra
        return {"content_chars": 3, "content": "Yes", "tool_calls": [],
                "finish_reason": "stop", "native_finish_reason": "STOP",
                "reasoning_chars": 0, "completion_tokens": 20, "reasoning_tokens": 0,
                "cost": 0.001, "stream_error": None, "seconds": 3.0,
                "provider": "Google AI Studio"}

    monkeypatch.setattr(sr, "_provider_cfg", fake_cfg)
    monkeypatch.setattr(sr, "run_as_sent", fake_run)
    out_dir = tmp_path / "out"
    assert sr.main(["worker", "--run", str(p), "--turn", "1", "--as-sent",
                    "--provider", "google-ai-studio", "--out", str(out_dir)]) == 0
    assert seen["extra"] == {"provider": {"order": ["google-ai-studio"],
                                          "allow_fallbacks": False}}
    out = capsys.readouterr().out
    assert "provider=Google AI Studio" in out
    assert '"allow_fallbacks": false' in out  # the lever line names the route
    assert (out_dir / "6348_t1_d1_as_sent_provider-google-ai-studio_rep1.md").exists()


def test_run_as_sent_reads_the_serving_provider_off_the_stream(monkeypatch):
    chunks = [
        {"provider": "Google", "choices": [{"delta": {"reasoning": "hm"}}]},
        {"provider": "Google", "choices": [{"delta": {"content": "Yes"},
                                            "finish_reason": "stop"}],
         "usage": {"completion_tokens": 5, "cost": 0.001}},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for c in chunks:
                yield "data: " + json.dumps(c)
            yield "data: [DONE]"

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, json=None, headers=None):
            FakeClient.payload = json
            return FakeStream()

    import asyncio

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    msgs = [{"role": "user", "content": "q"}]
    r = asyncio.run(sr.run_as_sent(msgs, {"model": "m", "api_key": "k"}, [],
                                   {"provider": {"order": ["google-vertex"],
                                                 "allow_fallbacks": False}}))
    assert r["provider"] == "Google" and r["content"] == "Yes"
    assert FakeClient.payload["provider"] == {"order": ["google-vertex"],
                                              "allow_fallbacks": False}


def test_provider_is_an_as_sent_option_only(run_file):
    for argv in (["worker", "--provider", "google-ai-studio"],
                 ["worker", "--first-round", "--provider", "google-ai-studio"],
                 ["manager", "--first-round", "--provider", "google-ai-studio"]):
        with pytest.raises(SystemExit):
            sr.main([argv[0], "--run", str(run_file), "--turn", "1", *argv[1:],
                     "--dry-run"])
