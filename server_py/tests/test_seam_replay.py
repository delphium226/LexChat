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
    assert built[0]["content"] == agent_core.DEEP_RESEARCH_SYNTHESIS_PROMPT


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


def test_without_fix_strips_the_block_and_swaps_the_prompt(run_file, monkeypatch):
    monkeypatch.setattr(sr, "_prompt_constant_at",
                        lambda rev, name: f"OLD {name} @ {rev}")
    doc, turn = sr.load_turn(run_file, 1)
    msgs = sr.synthesis_messages(doc, turn, without_fix=True, rev="abc1234")
    assert msgs[0]["content"] == "OLD DEEP_RESEARCH_SYNTHESIS_PROMPT @ abc1234"
    assert "PINPOINTS TO KEEP" not in msgs[1]["content"]
    # Everything else is untouched: the findings and the halt note survive.
    assert "s.57(3)(a)" in msgs[1]["content"]
    assert "STEP FINDINGS" in msgs[1]["content"]


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


def test_the_prompt_reader_finds_a_real_constant():
    """Reads `prompts.py` at a revision with a regex; pinned against HEAD so a
    change to how the constants are written is caught here."""
    text = sr._prompt_constant_at("HEAD", "DEEP_RESEARCH_SYNTHESIS_PROMPT")
    assert "CITATION PRESERVATION" in text
    with pytest.raises(SystemExit):
        sr._prompt_constant_at("HEAD", "NO_SUCH_PROMPT_CONSTANT")


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
