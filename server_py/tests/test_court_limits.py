"""FIX_PLAN P3.50, fix A1 (Session 52): the court's own limit on its decision,
found by code in a judgment's text (`utils/court_limits.py`) and carried to the
Worker (a block on the `get_case_law_text` result), the Deep Research synthesis
(a block beside P3.1's pinpoints) and the answer seam (an "Also in" note)."""
from __future__ import annotations

import asyncio
import json

import pytest

from src.agent import agent_core, agent_shared
from src.agent.provider_factory import set_request_provider_config
from src.utils import court_limits as cl
from src.utils.search_scope import strip_scope_blocks

URL = "https://caselaw.nationalarchives.gov.uk/ewca/crim/2025/1150"
P43 = ("We should emphasise that in reaching our decision that the first ground of appeal "
       "should be rejected, our focus was necessarily on the admitted duties and "
       "responsibilities of the appellant on the night in question.  It is possible that the "
       "application of the three-part test to other OSGs employed in prisons, with different "
       "roles at different times, would yield a different result.")
P43_NORM = " ".join(P43.split())
TEXT = (
    "Neutral Citation Number:\n[2025] EWCA Crim 1150\nApproved Judgment\n"
    "1.\nThe appellant was an operational support grade.\n"
    "42.\nAlthough it is not necessary to our decision, we would add that the judge could "
    "properly have directed the jury that the appellant was a public officer.\n"
    "43.\n" + P43 + "\n"
    "44.\nAs to the second ground of appeal, the admitted fact was that checks were missed.\n"
)


def _raw(text=TEXT, **extra):
    return json.dumps({"url": URL, "title": "Graham Andrew Evans v R",
                       "ncn": "[2025] EWCA Crim 1150", "text": text, **extra})


# --- the detector -------------------------------------------------------------

def test_the_evans_limit_is_found_with_its_paragraph_verbatim():
    assert cl.find_limits(TEXT) == [{"para": "43", "kind": 0, "passage": P43_NORM}]


def test_a_judgment_with_no_limit_yields_nothing():
    assert cl.find_limits("1.\nThe appeal is dismissed.\n2.\nWe so order.\n") == []
    assert cl.find_limits("") == []


@pytest.mark.parametrize("para", [
    # quoted from another judgment, opened in the paragraph
    '“Nothing in this judgment is intended to decide the wider point.” That was obiter.',
    # a quotation running on from the paragraph above (closes more than it opens)
    'Nothing in this judgment should be construed as approval of the ruling.” '
    'The issue does not arise.',
    # attributed to another judge in the same sentence
    'As Etherton LJ said, nothing in this judgment should be taken as approving it.',
    # a concessive clause widening, not limiting, the decision
    'We note that, while our focus has been on section 1, the same reading applies to section 2.',
])
def test_quoted_attributed_and_widening_passages_are_skipped(para):
    assert cl.find_limits(f"10.\n{para}\n11.\nEnd.\n") == []


def test_a_law_report_year_is_never_a_paragraph_number():
    text = ("60.\nI express no view, one way or the other, about whether the argument is right "
            "(see Dutton\n[2000] 1 QB 133). It is difficult.\n61.\nNext.\n")
    got = cl.find_limits(text)
    assert got and got[0]["para"] == "60" and "[2000] 1 QB 133" in got[0]["passage"]


def test_the_best_ranked_passages_are_kept_and_returned_in_order():
    text = ("5.\nWe express no view as to whether the lease took effect.\n"
            "6.\nWe do not decide whether the second point is right.\n"
            "9.\nOur decision is confined to the facts of this case.\n")
    got = cl.find_limits(text)
    assert [(g["para"], g["kind"]) for g in got] == [("5", 2), ("9", 0)]


def test_a_heading_the_paragraph_runs_into_is_left_out():
    text = ("125.\nNothing in this judgement should be read as indicating any view on the "
            "planning merits of the scheme.\nCosts\n126.\nCosts follow the event.\n")
    assert cl.find_limits(text)[0]["passage"].endswith("of the scheme.")


def test_a_next_sentence_that_runs_on_past_a_line_break_is_left_out():
    filler = "The tribunal heard evidence over many days. " * 30
    text = (f"7.\n{filler}Nothing in this judgment is intended to fetter the tribunal's discretion."
            " In accordance with Jafri v Lincoln College\n[2014] EWCA Civ 449 it was\n"
            "8.\nEnd.\n")
    assert cl.find_limits(text)[0]["passage"] == (
        "Nothing in this judgment is intended to fetter the tribunal's discretion.")


def test_a_long_paragraph_gives_the_sentence_and_the_next():
    filler = "The tribunal heard evidence over many days. " * 30
    text = (f"7.\n{filler}Nothing in this judgment is intended to fetter the tribunal's discretion."
            f" The weight is for the tribunal. {filler}\n8.\nEnd.\n")
    passage = cl.find_limits(text)[0]["passage"]
    assert passage == ("Nothing in this judgment is intended to fetter the tribunal's discretion. "
                       "The weight is for the tribunal.")


# --- the Worker's block -------------------------------------------------------

def test_the_note_is_gated_on_the_tool_and_on_a_passage():
    assert cl.court_limit_note("search_case_law", _raw()) == ""
    assert cl.court_limit_note("get_case_law_text", _raw("1.\nDismissed.\n")) == ""
    assert cl.court_limit_note("get_case_law_text", json.dumps({"error": "x", "text": ""})) == ""
    assert cl.court_limit_note("get_case_law_text", "not json") == ""


def test_the_note_quotes_the_passage_and_states_the_rule():
    note = cl.court_limit_note("get_case_law_text", _raw())
    assert note.startswith(f"\n\n[{cl.COURT_LIMIT_HEAD} — ")
    assert "Judgment: Graham Andrew Evans v R, [2025] EWCA Crim 1150" in note
    assert f'Paragraph 43 (the court confines its decision): "{P43_NORM}"' in note
    assert "cite paragraph 43" in note and "do not state the holding as a rule" in note
    assert note.endswith(f"[/{cl.COURT_LIMIT_HEAD}]")


@pytest.mark.parametrize("ncn", ["[2025] EWCA Crim 1150", "[2009] EWHC 1811 (Admin)", ""])
def test_the_note_reads_back_to_what_the_detector_found(ncn):
    raw = json.dumps({"url": URL, "title": "A v B", "ncn": ncn, "text": TEXT})
    assert cl.limits_in_text("x" + cl.court_limit_note("get_case_law_text", raw) + "y") == \
        cl.court_limits_from_result(raw)


def test_an_echoed_block_is_stripped_and_nothing_else_moves():
    note = cl.court_limit_note("get_case_law_text", _raw())
    body = "The court held X.\n\nSee [43]."
    assert strip_scope_blocks(body + note)[0] == body
    assert strip_scope_blocks(body) == (body, 0)


# --- the synthesis block --------------------------------------------------------

LIMS = cl.court_limits_from_result(_raw())


def test_the_block_is_given_for_a_judgment_a_step_names():
    block = cl.court_limits_block(LIMS, ["Step 1 read R v Evans [2025] EWCA Crim 1150."])
    assert f"[{cl.COURT_LIMIT_HEAD}S — " in block and P43_NORM in block
    assert cl.court_limits_block(LIMS, ["Step 1 read nothing relevant."]) == ""
    assert cl.court_limits_block([], ["R v Evans"]) == ""


def _findings(content):
    return [{"title": "Step", "detail": "", "content": content}]


def test_the_synthesis_payload_carries_it_and_is_unchanged_without_it():
    f = _findings(f"Evans ([2025] EWCA Crim 1150)({URL}) held X.")
    without = agent_core.build_synthesis_messages("q", {}, f, [], 1, research_mode="case_law_only")
    none = agent_core.build_synthesis_messages("q", {}, f, [], 1, research_mode="case_law_only",
                                               court_limits=[])
    withb = agent_core.build_synthesis_messages("q", {}, f, [], 1, research_mode="case_law_only",
                                                court_limits=LIMS)
    assert without == none
    assert P43_NORM in withb[1]["content"]
    assert withb[1]["content"].replace(cl.court_limits_block(LIMS, [f[0]["content"]]), "") == \
        without[1]["content"]


# --- the answer seam ------------------------------------------------------------

ANSWER = ("In *Rex v Evans (Graham)* [2025] EWCA Crim 1150 the court held that an OSG is a "
          "public officer.\n\nThe second ground failed.")


def test_the_limit_goes_back_after_the_paragraph_that_names_the_judgment():
    out, n = cl.restore_court_limits(ANSWER, LIMS)
    assert n == 1
    first, rest = out.split("\n\n", 1)
    assert rest.startswith('Also in Graham Andrew Evans v R [2025] EWCA Crim 1150, at [43], '
                           f'the court limited its own decision: "{P43_NORM}"')
    assert out.endswith("The second ground failed.")


@pytest.mark.parametrize("answer", [
    ANSWER + " See [43].",
    ANSWER + " The court said its focus was on the admitted duties and responsibilities of "
             "the appellant on the night in question.",
    "The court held that an OSG is a public officer.",   # does not name the judgment
    "",
])
def test_nothing_is_added_where_the_answer_carries_it_or_never_names_it(answer):
    assert cl.restore_court_limits(answer, LIMS) == (answer, 0)


def test_the_restore_is_idempotent_and_a_note_is_not_a_naming():
    once, _ = cl.restore_court_limits(ANSWER, LIMS)
    assert cl.restore_court_limits(once, LIMS) == (once, 0)
    only_note = "Intro.\n\nAlso in s.3: R v Evans [2025] EWCA Crim 1150 is cited."
    assert cl.restore_court_limits(only_note, LIMS) == (only_note, 0)


@pytest.mark.parametrize("kind", [1, 2])
def test_only_a_confinement_is_restored(kind):
    other = [{**LIMS[0], "kind": kind}]
    assert cl.restore_court_limits(ANSWER, other) == (ANSWER, 0)


def test_the_note_quotes_the_matched_sentence_and_the_next_within_450():
    long_tail = " ".join(["The tribunal heard further evidence on the point."] * 12)
    passage = ("Nothing in this judgment is intended to fetter the tribunal's discretion. "
               "The weight is for the tribunal. " + long_tail)
    assert cl.restore_excerpt(passage) == (
        "Nothing in this judgment is intended to fetter the tribunal's discretion. "
        "The weight is for the tribunal.")
    lead = "The background is long. " * 10
    got = cl.restore_excerpt(lead + "Our decision is confined to the facts of this case. "
                             + "Then " + "x" * 460 + ".")
    assert got == "Our decision is confined to the facts of this case."
    huge = "Our decision is confined to the facts of this case, " + "and so on " * 60 + "."
    cut = cl.restore_excerpt(huge)
    assert cut.endswith(" ...") and len(cut) <= cl.MAX_RESTORE_CHARS + 4
    assert cl.restore_excerpt(P43_NORM) == P43_NORM          # Evans: both sentences, 402 chars


def test_at_most_two_notes():
    many = [{**LIMS[0], "url": f"{URL}{i}", "ncn": f"[2025] EWCA Crim 115{i}", "title": "X v R"}
            for i in range(4)]
    answer = " ".join(f"[2025] EWCA Crim 115{i} held Y." for i in range(4))
    assert cl.restore_court_limits(answer, many)[1] == cl.MAX_RESTORES


def test_a_failure_returns_the_answer_unchanged(monkeypatch):
    monkeypatch.setattr(cl, "_names_judgment", lambda *a: 1 / 0)
    assert cl.restore_court_limits(ANSWER, LIMS) == (ANSWER, 0)


# --- wiring -----------------------------------------------------------------------

def _run_tool(monkeypatch, name, raw, memo=None):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "case_law_only",
                                 "model": "m"})

    async def fake_exec(n, args, on_chunk=None, timing_collector=None, worker_call=False):
        return raw

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    return asyncio.run(agent_shared.run_worker_tool(
        name, {"url": URL}, "brief", lambda *a, **k: None, "m", search_log=[], tool_memo=memo))


def test_the_judgment_result_carries_the_block_and_a_memo_hit_too(monkeypatch):
    memo = {}
    out = _run_tool(monkeypatch, "get_case_law_text", _raw(), memo)
    assert out.startswith(_raw()) and out[len(_raw()):] == cl.court_limit_note(
        "get_case_law_text", _raw())
    assert _run_tool(monkeypatch, "get_case_law_text", _raw(), memo) == out
    set_request_provider_config({})


def test_a_judgment_with_no_limit_is_returned_unchanged(monkeypatch):
    raw = _raw("1.\nDismissed.\n")
    assert _run_tool(monkeypatch, "get_case_law_text", raw) == raw
    set_request_provider_config({})


@pytest.fixture
def _cfg():
    def set_(chat_mode, research_mode="case_law_only"):
        set_request_provider_config({
            "_provider": "openrouter", "_research_mode": research_mode,
            "_chat_mode": chat_mode, "model": "test-model", "_tool_memo_enabled": False})
    yield set_
    set_request_provider_config({})


def _manager(answer):
    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}
    return manager


async def _worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
    return {"content": "Report on R v Evans [2025] EWCA Crim 1150.", "sources": [],
            "searches": [], "court_limits": LIMS}


@pytest.mark.asyncio
async def test_the_conversational_answer_gets_the_limit_back(_cfg):
    from src.agent.agent_core import process_user_request
    _cfg("conversational")
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert "Also in Graham Andrew Evans v R [2025] EWCA Crim 1150, at [43]" in final["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("chat, mode", [("research", "case_law_only"),
                                        ("conversational", "parliamentary_records")])
async def test_research_mode_and_the_parliamentary_bots_are_left_alone(_cfg, chat, mode):
    from src.agent.agent_core import process_user_request
    _cfg(chat, mode)
    final = await process_user_request(_manager(ANSWER), _worker,
                                       [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert "the court limited its own decision" not in final["content"]


@pytest.mark.asyncio
async def test_deep_research_hands_the_synthesis_the_block_and_restores(_cfg):
    _cfg("deep_research")
    seen = {}

    async def synth(messages, model, cancel_event, num_ctx, tools, executor, on_chunk=None, **kw):
        seen["payload"] = messages[1]["content"]
        return {"role": "assistant", "content": ANSWER}

    async def step_worker(brief, model, cancel_event, num_ctx, on_chunk, **kw):
        return {"content": "Step on R v Evans [2025] EWCA Crim 1150.", "sources": [],
                "searches": [], "court_limits": LIMS}

    final = await agent_core.run_deep_research(
        synth, step_worker, {"steps": [{"title": "Read", "detail": "d"}]},
        [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    assert f"[{cl.COURT_LIMIT_HEAD}S — " in seen["payload"]
    assert "Also in Graham Andrew Evans v R [2025] EWCA Crim 1150, at [43]" in final["content"]


def test_run_worker_agent_reads_the_limits_back_from_its_tool_results(monkeypatch):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "case_law_only",
                                 "model": "m", "_chat_mode": "research"})

    async def fake_exec(n, args, on_chunk=None, timing_collector=None, worker_call=False):
        return _raw()

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)

    async def loop(messages, model, cancel_event, num_ctx, tools, executor, on_chunk=None, **kw):
        await executor("get_case_law_text", {"url": URL})
        return {"role": "assistant", "content": "Report."}

    async def chunk(*a, **k):
        return ""

    result = asyncio.run(agent_core.run_worker_agent(loop, chunk, "brief", "m", None, 0))
    assert result["court_limits"] == LIMS
    set_request_provider_config({})


def test_the_answer_note_quotes_the_excerpt_not_the_whole_passage():
    tail = " ".join(["The tribunal heard further evidence on the point."] * 12)
    lim = {**LIMS[0], "passage": "Our decision is confined to the facts of this case. "
                                 "Nothing else follows. " + tail}
    out, n = cl.restore_court_limits(ANSWER, [lim])
    assert n == 1
    assert out.count('decision: "Our decision is confined to the facts of this case. '
                     'Nothing else follows."') == 1
    assert "further evidence" not in out
