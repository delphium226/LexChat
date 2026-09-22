"""P4.1 (B7): the harness half — a per-turn research type, scripted sessions,
the stamped history, and the `deadend` grader.

The harness used to send ONE `research_mode` per session (`replay.py::_filters`
takes the Session), so no replay could ever show bug (a): a lawyer changing
the research type mid-session. The row's acceptance is a scripted
"refusal, mode change, same question", which needs the type per TURN — the
same shape P0.5 gave chat mode.
"""

import json
import sys
from dataclasses import fields
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay as rp  # noqa: E402
import replay_report as rr  # noqa: E402
import replay_set as rs  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "scripts"


def _turn(i, question, chat_mode="conversational", got_reply=True):
    return rs.Turn(index=i, question=question, chat_mode=chat_mode,
                   chat_mode_source="conversational_marker", got_reply=got_reply,
                   recorded_answer_chars=100, recorded_answer_shape="conversational",
                   research_mode="legislation_only", research_mode_source="default")


def _base(session_id="6346"):
    return rs.Session(
        session_id=session_id, user="u", thread="t", verdict="FAIL", primary="B7",
        turns=[_turn(1, "Summarise the case."), _turn(2, "I will change it."),
               _turn(3, "I have changed the mode, please proceed")],
        jurisdiction=None,
    )


# ---------------------------------------------------------------------------
# per-turn research type
# ---------------------------------------------------------------------------

def test_turn_carries_a_research_mode_and_its_source():
    names = {f.name for f in fields(rs.Turn)}
    assert {"research_mode", "research_mode_source"} <= names
    names = {f.name for f in fields(rp.TurnResult)}
    assert {"research_mode", "research_mode_source", "mode_change"} <= names


def test_the_export_stamps_every_turn_with_the_session_value_and_where_it_came_from(tmp_path):
    """Until P0.6 the twelve blank sessions still get the default — but it is
    now labelled `default` per turn, so the run file says so."""
    csv = tmp_path / "export.csv"
    cls = tmp_path / "classification.json"
    head = ["Session ID", "Message #", "Message role", "Message content",
            "Filter: Chat mode", "Filter: Research mode", "Session mode"]
    rows = [
        ["1", "1", "user", "q", "", "", ""],
        ["1", "2", "assistant", "a", "", "", ""],
        ["2", "1", "user", "q", "conversational", "legislation_and_case_law", ""],
        ["2", "2", "assistant", "a", "conversational", "legislation_and_case_law", ""],
    ]
    import csv as _csv
    with csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)
    cls.write_text(json.dumps({"1": {"verdict": "FAIL"}, "2": {"verdict": "DEFECT"}}), encoding="utf-8")
    sessions = {s.session_id: s for s in rs.load_sessions(str(csv), str(cls))}
    t1 = sessions["1"].turns[0]
    assert (t1.research_mode, t1.research_mode_source) == (rs.DEFAULT_RESEARCH_MODE, "default")
    t2 = sessions["2"].turns[0]
    assert (t2.research_mode, t2.research_mode_source) == ("legislation_and_case_law", "snapshot")


# ---------------------------------------------------------------------------
# scripted sessions
# ---------------------------------------------------------------------------

def test_scripted_session_takes_text_by_index_and_the_type_per_turn():
    script = {"session_id": "p41_x", "base": "6346", "verdict": "FAIL", "primary": "B7",
              "turns": [{"from_turn": 1, "research_mode": "legislation_only"},
                        {"from_turn": 3, "research_mode": "legislation_and_case_law"},
                        {"from_turn": 1, "research_mode": "legislation_and_case_law"}]}
    s = rs.scripted_session(script, [_base()])
    assert s.session_id == "p41_x" and s.verdict == "FAIL" and s.primary == "B7"
    assert [t.question for t in s.turns] == [
        "Summarise the case.", "I have changed the mode, please proceed", "Summarise the case."]
    assert [t.research_mode for t in s.turns] == [
        "legislation_only", "legislation_and_case_law", "legislation_and_case_law"]
    assert {t.research_mode_source for t in s.turns} == {"script"}
    assert {t.chat_mode_source for t in s.turns} == {"script"}
    assert [t.index for t in s.turns] == [1, 2, 3]
    assert [t.chat_mode for t in s.turns] == ["conversational"] * 3  # the base turn's
    assert s.script is script
    assert s.research_mode == "legislation_only"  # the first turn's, for `filters`


def test_scripted_turn_may_override_chat_mode_or_give_literal_harness_text():
    script = {"session_id": "p41_y", "base": "6346",
              "turns": [{"from_turn": 1, "research_mode": "legislation_only"},
                        {"question": "Switch to Research mode", "research_mode": "legislation_only"},
                        {"from_turn": 1, "research_mode": "legislation_only", "chat_mode": "research"}]}
    s = rs.scripted_session(script, [_base()])
    assert s.turns[1].question == "Switch to Research mode" and s.turns[1].got_reply is False
    assert s.turns[2].chat_mode == "research"


def test_scripted_session_refuses_a_bad_base_or_turn():
    with pytest.raises(SystemExit):
        rs.scripted_session({"session_id": "p", "base": "9999",
                             "turns": [{"from_turn": 1, "research_mode": "legislation_only"}]}, [_base()])
    with pytest.raises(SystemExit):
        rs.scripted_session({"session_id": "p", "base": "6346",
                             "turns": [{"from_turn": 9, "research_mode": "legislation_only"}]}, [_base()])


def test_load_script_validates(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"session_id": "p", "base": "6346",
                             "turns": [{"from_turn": 1, "research_mode": "nonsense"}]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        rs.load_script(p)
    p.write_text(json.dumps({"session_id": "p", "base": "6346", "turns": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        rs.load_script(p)
    p.write_text(json.dumps({"session_id": "p", "base": "6346",
                             "turns": [{"from_turn": 1, "research_mode": "legislation_only"}]}), encoding="utf-8")
    assert rs.load_script(p)["base"] == "6346"


def test_the_committed_scripts_hold_no_question_text():
    """The lawyers' verbatim questions are never committed (FIX_PLAN, Data
    handling). A script may only point at the export by turn index, or carry
    harness text of its own."""
    paths = sorted(SCRIPTS.glob("*.json"))
    assert paths, "no scripts committed"
    for p in paths:
        script = rs.load_script(p)
        for t in script["turns"]:
            assert "from_turn" in t and "question" not in t, f"{p.name}: literal question text"
        assert script["base"] in ("6343", "6346")
        # A mode change is the point: at least one turn differs from the first.
        modes = [t["research_mode"] for t in script["turns"]]
        assert modes[0] == "legislation_only" and "legislation_and_case_law" in modes[1:]


# ---------------------------------------------------------------------------
# the request and the stamped history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_turn_research_mode_is_sent_and_the_answer_is_stamped():
    """The harness sends the TURN's research type (not the session snapshot)
    and stamps its own answer the way the client stamps a saved message —
    which is the only reason the product can see the change on turn 2."""
    script = {"session_id": "p41_z", "base": "6346",
              "turns": [{"from_turn": 1, "research_mode": "legislation_only"},
                        {"from_turn": 3, "research_mode": "legislation_and_case_law"}]}
    s = rs.scripted_session(script, [_base()])
    seen = []

    class FakeClient:
        def _filters(self, sess):
            return {"research_mode": sess.research_mode, "jurisdiction": None}

        async def chat(self, messages, sess, chat_mode, plan, research_mode=None):
            seen.append({"messages": [dict(m) for m in messages],
                         "research_mode": research_mode, "chat_mode": chat_mode})
            tr = rp.TurnResult(turn=0, question=messages[-1]["content"], answer=f"A{len(seen)}")
            tr.audit = {"mode_change": (
                {"research_mode": {"from": "legislation_only", "to": research_mode}, "chat_mode": None}
                if len(seen) == 2 else None)}
            return tr

    rec = await rp.replay_session(FakeClient(), s, 1, {"git_head": "test"})
    assert [c["research_mode"] for c in seen] == ["legislation_only", "legislation_and_case_law"]
    # Turn 2's history carries turn 1's answer stamped with the mode it ran under.
    hist = seen[1]["messages"]
    assert hist[1]["role"] == "assistant"
    assert hist[1]["research_mode"] == "legislation_only"
    assert hist[1]["chat_mode"] == "conversational"
    # The run file records the per-turn type, its source and the product's view.
    turns = rec["turns"]
    assert [t["research_mode"] for t in turns] == ["legislation_only", "legislation_and_case_law"]
    assert {t["research_mode_source"] for t in turns} == {"script"}
    assert turns[0]["mode_change"] is None
    assert turns[1]["mode_change"]["research_mode"]["to"] == "legislation_and_case_law"
    assert rec["script"] is script
    assert rec["filters"]["research_mode"] == "legislation_only"


def test_research_mode_enabled_is_pinned_off_like_the_pre_pilot():
    assert rp.PINNED_FEATURES["research_mode_enabled"] is False
    assert rp.PINNED_FEATURES["local_prompt_cache_enabled"] is False


# ---------------------------------------------------------------------------
# the grader
# ---------------------------------------------------------------------------

def _doc(*turns, session="p41_6346", rep=1):
    return {"session_id": session, "rep": rep, "filters": {"research_mode": "legislation_only"},
            "turns": [
                {"turn": i + 1, "answer": a, "research_mode": rm, "chat_mode": "conversational",
                 "mode_change": mc, "audit": {"delegations": [{}] * d}}
                for i, (a, rm, mc, d) in enumerate(turns)
            ]}


REFUSAL = ("This session is currently set to cover legislation only. To get a summary "
           "please switch to 'Legislation & Case Law' mode using the mode selector.")
STILL = ("It appears this session is still restricted to legislation only. You may need "
         "to start a new chat session with the 'Legislation & Case Law' mode enabled.")
GOOD_DEFLECTION = ("The research type is currently set to 'Legislation only', so case law "
                   "was not searched. You can change it to 'Legislation & case law' using "
                   "the Filters button above the message box (Research filters > Research "
                   "type); the change applies to your next message in this conversation.")
ANSWERED = "In *Rex v Evans (Graham)* [2025] EWCA Crim 1150 the Court of Appeal held that..."
CHANGE = {"research_mode": {"from": "legislation_only", "to": "legislation_and_case_law"}, "chat_mode": None}


@pytest.mark.parametrize("text,switch,wrong,ui,old", [
    (REFUSAL, True, True, False, True),
    (STILL, True, True, False, True),
    ("You can switch to Research mode using the mode selector or toggle in your "
     "application interface, typically located at the top or side of the chat window.",
     True, True, True, False),
    (GOOD_DEFLECTION, False, False, False, True),   # it names the old scope: fine on an unchanged turn
    (ANSWERED, False, False, False, False),
    ("I do not have the tools to search for or summarise case law.", False, False, False, True),
    ("Under s.7(2) the acquiring authority may...", False, False, False, False),
])
def test_the_four_regexes(text, switch, wrong, ui, old):
    assert bool(rr.DEADEND_SWITCH.search(text)) is switch
    assert bool(rr.DEADEND_WRONG_CONTROL.search(text)) is wrong
    assert bool(rr.DEADEND_INVENTED_UI.search(text)) is ui
    assert bool(rr.DEADEND_OLD_MODE.search(text)) is old


def test_rows_mark_the_change_against_the_previous_answered_turn():
    doc = _doc((REFUSAL, "legislation_only", None, 0),
               ("", "legislation_only", None, 0),                 # blank reply, no answer
               (ANSWERED, "legislation_and_case_law", CHANGE, 1))
    rows = rr.deadend_rows(doc)
    assert [r["changed"] for r in rows] == [False, False, True]
    assert [r["marker"] for r in rows] == [False, False, True]
    assert rows[2]["delegations"] == 1
    assert rows[0]["wrong_control"] and rows[0]["switch"]


def test_the_before_column_shape_is_a_finding_and_the_fixed_shape_is_clean():
    """The pre-fix product on the scripted sequence: refusal, then the same
    refusal after the change (bug (a)) — and every refusal names the wrong
    control (bug (b))."""
    before = _doc((REFUSAL, "legislation_only", None, 0),
                  (STILL, "legislation_and_case_law", None, 0),
                  (STILL, "legislation_and_case_law", None, 0))
    findings = rr.deadend_findings(rr.deadend_rows(before))
    assert any("no mode-change marker" in f for f in findings)
    assert sum("bug a" in f for f in findings) == 2
    assert sum("bug b" in f for f in findings) == 3

    after = _doc((GOOD_DEFLECTION, "legislation_only", None, 0),
                 (ANSWERED, "legislation_and_case_law", CHANGE, 1),
                 (ANSWERED, "legislation_and_case_law", None, 1))
    assert rr.deadend_findings(rr.deadend_rows(after)) == []


def test_a_change_the_product_did_not_see_is_a_finding_even_if_the_answer_is_fine():
    doc = _doc((GOOD_DEFLECTION, "legislation_only", None, 0),
               (ANSWERED, "legislation_and_case_law", None, 1))
    findings = rr.deadend_findings(rr.deadend_rows(doc))
    assert findings == ["p41_6346 r1 t2: research type changed and no mode-change marker was injected"]


def test_invented_ui_is_a_finding_on_any_turn():
    doc = _doc(("The control is typically located at the top or side of your screen.",
                "legislation_only", None, 0))
    assert any("bug c" in f for f in rr.deadend_findings(rr.deadend_rows(doc)))


def test_counts_are_over_answered_turns_at_rep_1():
    rows = rr.deadend_rows(_doc((REFUSAL, "legislation_only", None, 0),
                                ("", "legislation_only", None, 0),
                                (ANSWERED, "legislation_and_case_law", CHANGE, 1)))
    c = rr._deadend_counts(rows)
    assert c == {"answered": 2, "switch": 1, "wrong_control": 1, "invented_ui": 0,
                 "old_mode": 1, "changed": 1, "changed_clean": 1, "marker": 1}


def test_deadend_exits_one_on_a_finding_and_zero_when_clean(tmp_path, capsys):
    d = tmp_path / "dir"
    d.mkdir()
    (d / "p41_6346_rep1.json").write_text(json.dumps(_doc(
        (REFUSAL, "legislation_only", None, 0),
        (STILL, "legislation_and_case_law", None, 0))), encoding="utf-8")
    assert rr.main(["--dir", str(d), "deadend"]) == 1
    out = capsys.readouterr().out
    assert "FINDINGS" in out and "bug a" in out and "switch/restart 2" in out
    (d / "p41_6346_rep1.json").write_text(json.dumps(_doc(
        (GOOD_DEFLECTION, "legislation_only", None, 0),
        (ANSWERED, "legislation_and_case_law", CHANGE, 1))), encoding="utf-8")
    assert rr.main(["--dir", str(d), "deadend", "--before", str(d)]) == 0
    out = capsys.readouterr().out
    assert "no findings" in out and "--before" in out


# ---------------------------------------------------------------------------
# the planner-clarification mode source (found while building this row)
# ---------------------------------------------------------------------------

def _export(tmp_path, rows):
    import csv as _csv
    csv = tmp_path / "export.csv"
    cls = tmp_path / "classification.json"
    head = ["Session ID", "Message #", "Message role", "Message content", "Message model",
            "Filter: Chat mode", "Filter: Research mode", "Session mode"]
    with csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(head)
        w.writerows(rows)
    ids = {r[0] for r in rows}
    cls.write_text(json.dumps({i: {"verdict": "FAIL"} for i in ids}), encoding="utf-8")
    return str(csv), str(cls)


def test_a_blank_model_answer_is_a_planner_clarification_and_its_neighbours_stay_in_deep_research(tmp_path):
    """6346's shape: three planner clarifications (no model, no report
    headings), then two turns with no reply. The shape marker read the three
    as conversational; the client saves a clarification with no model and
    every other assistant message with one, so the blank IS the planner."""
    csv, cls = _export(tmp_path, [
        ["6346", "1", "user", "q1", "", "", "", ""],
        ["6346", "2", "assistant", "The current research mode is set to 'Legislation Only'.", "", "", "", ""],
        ["6346", "3", "user", "q2", "", "", "", ""],
        ["6346", "4", "assistant", "Please confirm once you have changed it.", "", "", "", ""],
        ["6346", "5", "user", "q3", "", "", "", ""],
        ["6346", "6", "assistant", "The system still restricts my searches.", "", "", "", ""],
        ["6346", "7", "user", "q4", "", "", "", ""],
        ["6346", "8", "user", "q5", "", "", "", ""],
    ])
    s = rs.load_sessions(csv, cls)[0]
    assert [(t.chat_mode, t.chat_mode_source) for t in s.turns] == [
        ("deep_research", "planner_marker")] * 3 + [("deep_research", "neighbour")] * 2
    assert s.deep_research_turns == [1, 2, 3, 4, 5]
    # The exporter derives `Session mode` from `messages.research_plan`, which
    # a clarification never writes — so a blank Session mode here is agreement,
    # not a disagreement to report.
    assert rs.reconciliation_report([s]) == {
        "marker_but_not_session_mode": [], "session_mode_but_no_marker": [],
        "session_mode_blank_with_marker": []}


def test_an_answer_with_a_model_is_never_read_as_the_planner(tmp_path):
    csv, cls = _export(tmp_path, [
        ["1", "1", "user", "q1", "", "", "", ""],
        ["1", "2", "assistant", "The Act provides...", "google/gemini-3.1-pro-preview", "", "", ""],
        ["1", "3", "user", "q2", "", "", "", ""],
    ])
    s = rs.load_sessions(csv, cls)[0]
    assert [(t.chat_mode, t.chat_mode_source) for t in s.turns] == [
        ("conversational", "conversational_marker"), ("conversational", "neighbour")]


def test_a_completed_report_still_outranks_the_planner_read(tmp_path):
    """A Deep Research report row also has a model; the DR marker decides it
    first either way."""
    csv, cls = _export(tmp_path, [
        ["1", "1", "user", "q1", "", "", "", "deep_research"],
        ["1", "2", "assistant", "**Key findings**\n- x", "", "", "", "deep_research"],
    ])
    s = rs.load_sessions(csv, cls)[0]
    assert (s.turns[0].chat_mode, s.turns[0].chat_mode_source) == ("deep_research", "dr_marker")


@pytest.mark.asyncio
async def test_a_deep_research_turn_takes_the_change_from_the_planner_json():
    """The plan endpoint emits no audit event, so on a Deep Research turn the
    harness reads `mode_change` off the planner's JSON — for a clarification
    (no chat call at all) and for a drafted plan (whose execution call may
    report it too)."""
    script = {"session_id": "p41_dr", "base": "6346",
              "turns": [{"from_turn": 1, "research_mode": "legislation_only", "chat_mode": "deep_research"},
                        {"from_turn": 3, "research_mode": "legislation_and_case_law", "chat_mode": "deep_research"},
                        {"from_turn": 1, "research_mode": "legislation_and_case_law", "chat_mode": "deep_research"}]}
    s = rs.scripted_session(script, [_base()])
    change = {"research_mode": {"from": "legislation_only", "to": "legislation_and_case_law"}, "chat_mode": None}
    calls = []

    class FakeClient:
        def _filters(self, sess):
            return {"research_mode": sess.research_mode}

        async def draft_plan(self, messages, sess, research_mode=None):
            calls.append(("plan", research_mode, [dict(m) for m in messages]))
            if len(calls) == 1:
                return {"needs_clarification": True, "question": "Which?", "mode_change": None}
            if len(calls) == 2:
                return {"needs_clarification": True, "question": "Still which?", "mode_change": change}
            return {"plan": {"scope_note": "", "steps": [{"id": 1, "title": "t", "detail": ""}]},
                    "mode_change": None}

        async def chat(self, messages, sess, chat_mode, plan, research_mode=None):
            calls.append(("chat", research_mode, [dict(m) for m in messages]))
            tr = rp.TurnResult(turn=0, question=messages[-1]["content"], answer="Report.")
            tr.audit = {"mode_change": None}
            return tr

    rec = await rp.replay_session(FakeClient(), s, 1, {"git_head": "test"})
    turns = rec["turns"]
    assert [t["status"] for t in turns] == ["needs_clarification", "needs_clarification", "ok"]
    assert turns[0]["mode_change"] is None
    assert turns[1]["mode_change"] == change          # from the planner's JSON
    assert turns[2]["mode_change"] is None
    # The clarification appended to the history is stamped like any reply.
    hist = calls[1][2]
    assert hist[1]["role"] == "assistant" and hist[1]["chat_mode"] == "deep_research"
    assert hist[1]["research_mode"] == "legislation_only"
    assert [c[1] for c in calls] == ["legislation_only", "legislation_and_case_law",
                                     "legislation_and_case_law", "legislation_and_case_law"]
