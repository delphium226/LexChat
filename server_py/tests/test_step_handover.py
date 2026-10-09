"""P3.10: a Deep Research step that works on an earlier step's list is handed it.

`run_deep_research` runs each approved step as an isolated Worker. Before this,
a later step told to "check the identified Orders" was never given them and
re-derived the list with its own searches; measured after P3.8, every such step
did (12 of 12), and 5 of 12 worked on a different list. Now `_build_step_brief`
adds one code-written line naming the instruments the earlier steps' report
BODIES cite, to every step after the first (batch 12 B: a wording gate missed a
step that worked on the list), and P3.7's routed lookups do not read that line.

Every instrument here is synthetic.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import (  # noqa: E402
    _build_step_brief,
    run_deep_research,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.utils import step_handover as SH  # noqa: E402
from src.utils.instrument_lookup import extract_instrument_citations  # noqa: E402
from src.utils.search_scope import worker_scope_block  # noqa: E402

LINK = "[{t}](https://www.legislation.gov.uk/{i})"
DEPENDENT = {"title": "Check the status of the identified Orders",
             "detail": "Check the amendment and revocation status of the identified Orders."}
INDEPENDENT = {"title": "Find the parent Act", "detail": "Identify the Widget Act 1901."}
PLAN = {"scope_note": "Widget Orders made under the Widget Act 1901.",
        "steps": [INDEPENDENT, DEPENDENT]}
QUESTION = "Which Widget Orders are in force?"


def _scope_block(*ids):
    """The block `run_worker_agent` appends to every report, built by the
    product's own builder (a section search per id)."""
    log = [{"tool": "search_legislation_sections", "query": "widgets",
            "legislation_id": i, "shown": 1, "matched": 1} for i in ids]
    return worker_scope_block(log)


STEP1_REPORT = (
    "## Findings\n"
    f"- {LINK.format(t='The Widget Order 1901', i='uksi/1901/4/article/2')}\n"
    "- The Widget (Scotland) Regulations, SSI 1902/30, make the same provision.\n"
    f"- {LINK.format(t='The Widget Order 1901', i='uksi/1901/4')} again.\n"
    + _scope_block("uksi/1909/99")
)


# --- which steps get the line -----------------------------------------------
#
# Every step after the first whose earlier reports cite an instrument, whatever
# its wording (user decision, 2026-10-09). The wording gate this replaces
# missed "Review the retrieved secondary legislation ..." in the acceptance
# replay, and that step dropped an instrument.

@pytest.mark.parametrize("title, detail", [
    # Forms the old gate recognised.
    ("Review the SSIs", "Review the full text of the SSIs identified in the previous step"),
    ("Check status", "Check the amendment status of the identified Widget Administration "
                     "(Offices) Orders"),
    # The form it missed (`wave4_b11_sweep`): works on the list, names no
    # "identified" and no step.
    ("Compile the list of constituent bodies",
     "Review the retrieved secondary legislation to extract and compile a list of the bodies."),
    # A step that does not work on the list at all; the line is conditional.
    ("Find the penalties", "Identify the penalty provisions in the Widget Act 1901."),
    # A provision-dependent step (batch 10 D's other shape).
    ("Extract deadlines", "Extract the deadlines from the identified provisions in both Acts"),
    # No detail at all.
    ("Widgets", None),
])
def test_every_later_step_gets_the_line_whatever_its_wording(title, detail):
    step = {"title": title, "detail": detail}
    brief = _build_step_brief(step, PLAN, QUESTION, [STEP1_REPORT])
    parts = brief.split("\n\n")
    assert parts[-2] == SH.handover_line([STEP1_REPORT])
    assert parts[-1].startswith("CONTEXT: This task is one step")
    # Without it, the brief is exactly what it was before P3.10.
    assert brief.replace("\n\n" + parts[-2], "") == _build_step_brief(step, PLAN, QUESTION)


# --- what the line names --------------------------------------------------------

def test_the_ids_are_read_from_the_report_body_not_its_scope_block():
    """The scope block names an instrument the model never listed (here, one it
    section-searched); the line must not hand it on."""
    assert "uksi/1909/99" in STEP1_REPORT
    assert SH.handed_on_ids([STEP1_REPORT]) == ["uksi/1901/4", "ssi/1902/30"]


def test_both_citation_forms_are_read_each_once_in_order():
    """A link's id form and the citation a lawyer writes ("SSI 1902/30"); the
    same instrument twice, and across two reports, once; first appearance
    first, report by report."""
    second = "Also S.I. 1903/7 and " + LINK.format(t="x", i="ssi/1902/30") + "."
    assert SH.handed_on_ids([STEP1_REPORT, second]) == [
        "uksi/1901/4", "ssi/1902/30", "uksi/1903/7"]


def test_forms_no_stored_run_holds():
    """Input forms the 148 stored steps 2+ do not contain (batch 11 E's dry
    run): a lost step (its label, then the scope block), a halted step whose
    write-up round produced partial findings, and an echoed instrument-lookup
    block. None stored was lost; the four halted ones were all written up."""
    from src.utils.instrument_lookup import lookup_brief_block
    from src.utils.research_halt import halt_worker_report, lost_worker_report

    lost = lost_worker_report(3) + _scope_block("uksi/1909/99")
    assert SH.handed_on_ids([lost]) == []
    halted = halt_worker_report({"limit": 20}, sources_retrieved=2,
                                writeup="## Findings\n- SSI 1902/30 applies.") + _scope_block()
    assert SH.handed_on_ids([halted]) == ["ssi/1902/30"]
    echoed = "## Findings\nWidgets.\n" + lookup_brief_block(['{"tool": "lookup_legislation", '
                                                             '"status": "not_held", "legislation_id": '
                                                             '"ssi/1908/8", "label": "SSI 1908/8"}'])
    assert "ssi/1908/8" in echoed
    assert SH.handed_on_ids([echoed]) == []


def test_no_instrument_means_no_line():
    assert SH.handover_line(["## Findings\nNothing was cited."]) == ""
    assert SH.handover_line([]) == ""
    assert SH.handover_line(["", None]) == ""


def test_the_line_names_every_id_up_to_the_cap_and_counts_the_rest():
    def report(n):
        return " ".join(LINK.format(t="x", i=f"uksi/19{10 + k:02d}/{k + 1}") for k in range(n))

    at = SH.handover_line([report(SH.MAX_HANDED_ON_IDS)])
    assert f"uksi/19{9 + SH.MAX_HANDED_ON_IDS}/{SH.MAX_HANDED_ON_IDS}." in at
    assert "more" not in at.split(". Where")[0]
    past = SH.handover_line([report(SH.MAX_HANDED_ON_IDS + 3)])
    assert f"uksi/19{9 + SH.MAX_HANDED_ON_IDS}/{SH.MAX_HANDED_ON_IDS} and 3 more." in past
    assert f"uksi/19{10 + SH.MAX_HANDED_ON_IDS}/" not in past
    # One past the cap: the boundary (an off-by-one would drop "and 1 more" and
    # silently lose the one id; batch 12 integrator's mutant M4).
    one_past = SH.handover_line([report(SH.MAX_HANDED_ON_IDS + 1)])
    assert f"uksi/19{9 + SH.MAX_HANDED_ON_IDS}/{SH.MAX_HANDED_ON_IDS} and 1 more." in one_past
    assert SH.MAX_HANDED_ON_IDS >= 10   # the largest stored list (batch 11 E's dry run)


def test_the_line_wording():
    """The wording put to the user (batch 11 E). Conditional, so a step that
    does not work on an earlier list is not widened, and it never says "search
    for", which reads to a grader as a negative naming its search."""
    assert SH.handover_line([STEP1_REPORT]) == (
        "EARLIER STEPS' INSTRUMENTS: the reports of the earlier steps of this plan cite "
        "these instruments, by legislation_id: uksi/1901/4, ssi/1902/30. Where this task "
        "works on instruments an earlier step identified, they are among these: work on "
        "each one of the kind the task names, by its legislation_id, rather than finding "
        "the list again. Look further only if the task asks for more than the earlier "
        "steps reported."
    )


# --- the brief ------------------------------------------------------------------

def test_a_dependent_step_gets_the_line_before_the_context_sentence():
    brief = _build_step_brief(DEPENDENT, PLAN, QUESTION, [STEP1_REPORT])
    parts = brief.split("\n\n")
    assert parts[-1].startswith("CONTEXT: This task is one step")
    assert parts[-2] == SH.handover_line([STEP1_REPORT])
    # Without it, the brief is exactly what it was before P3.10.
    assert brief.replace("\n\n" + parts[-2], "") == _build_step_brief(DEPENDENT, PLAN, QUESTION)


def test_the_first_step_and_a_step_whose_earlier_reports_cite_nothing_are_unchanged():
    for step in (DEPENDENT, INDEPENDENT):
        first = _build_step_brief(step, PLAN, QUESTION)
        assert SH.HANDOVER_LABEL not in first
        # No earlier reports (the first step): no line.
        assert _build_step_brief(step, PLAN, QUESTION, []) == first
        assert _build_step_brief(step, PLAN, QUESTION, None) == first
        # Earlier reports citing nothing (a lost step, a case-law-only step):
        # no line, not an empty paragraph.
        assert _build_step_brief(step, PLAN, QUESTION, ["Nothing cited.", ""]) == first


def test_a_case_law_report_hands_on_only_the_legislation_it_links():
    """No stored Deep Research turn ran case law only (batch 12 B's dry run), so
    this form is synthetic. A judgment's link and neutral citation are not
    instruments; a legislation.gov.uk link inside a case-law report is."""
    judgments = ("## Key Cases\n- [Widget Co v Example Ltd [1901] UKSC 4]"
                 "(https://caselaw.nationalarchives.gov.uk/uksc/1901/4)\n")
    assert _build_step_brief(INDEPENDENT, PLAN, QUESTION, [judgments]) == \
        _build_step_brief(INDEPENDENT, PLAN, QUESTION)
    with_act = judgments + "- Applying " + LINK.format(t="s.2", i="ukpga/1901/7/section/2") + "\n"
    assert "by legislation_id: ukpga/1901/7." in _build_step_brief(
        INDEPENDENT, PLAN, QUESTION, [with_act])


def test_a_failure_reading_the_reports_leaves_the_brief_as_it_was(monkeypatch):
    """Fail-soft (Invariant 5): every step 2+ now goes through the line, so an
    error reading the earlier reports must cost the line and nothing else."""
    def broken(reports):
        raise ValueError("unreadable report")

    monkeypatch.setattr(SH, "handed_on_ids", broken)
    assert SH.handover_line([STEP1_REPORT]) == ""
    assert _build_step_brief(INDEPENDENT, PLAN, QUESTION, [STEP1_REPORT]) == \
        _build_step_brief(INDEPENDENT, PLAN, QUESTION)


def test_a_step_with_no_question_still_gets_the_line_last():
    """No CONTEXT sentence (no user question): the line closes the brief."""
    brief = _build_step_brief(INDEPENDENT, PLAN, "", [STEP1_REPORT])
    assert brief.split("\n\n")[-1] == SH.handover_line([STEP1_REPORT])
    assert "CONTEXT:" not in brief


@pytest.fixture
def _dr_cfg():
    set_request_provider_config({"_provider": "ollama", "_chat_mode": "deep_research",
                                 "_research_mode": "legislation_only", "model": "m"})
    yield
    set_request_provider_config({})


@pytest.mark.asyncio
async def test_run_deep_research_hands_step_two_the_list_step_one_reported(_dr_cfg):
    briefs = []

    async def worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        briefs.append(query)
        return {"content": STEP1_REPORT if len(briefs) == 1 else "Step two.", "sources": []}

    async def synthesis(messages, *a, **k):
        return {"role": "assistant", "content": "Report."}

    await run_deep_research(synthesis, worker, PLAN, [{"role": "user", "content": QUESTION}],
                            "m", None, None, 0)
    assert SH.HANDOVER_LABEL not in briefs[0]
    assert "by legislation_id: uksi/1901/4, ssi/1902/30." in briefs[1]
    assert "uksi/1909/99" not in briefs[1]


@pytest.mark.asyncio
async def test_run_deep_research_hands_every_later_step_what_all_earlier_steps_cite(_dr_cfg):
    """Steps 2 and 3 are worded as independent tasks; both get the line. Step 3's
    names step 1's instruments and then step 2's, each once."""
    briefs = []
    reports = [STEP1_REPORT,
               "## Findings\n- " + LINK.format(t="The Widget Rules 1903", i="ssi/1903/12") + "\n"
               "- SSI 1902/30 again.\n" + _scope_block("ssi/1909/98"),
               "Step three."]
    plan = {"scope_note": "Widgets.", "steps": [
        INDEPENDENT,
        {"title": "Find the Widget Rules", "detail": "Identify rules made under the Widget Act 1901."},
        {"title": "Find the penalties", "detail": "Identify the penalty provisions."},
    ]}

    async def worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        briefs.append(query)
        return {"content": reports[len(briefs) - 1], "sources": []}

    async def synthesis(messages, *a, **k):
        return {"role": "assistant", "content": "Report."}

    await run_deep_research(synthesis, worker, plan, [{"role": "user", "content": QUESTION}],
                            "m", None, None, 0)
    assert len(briefs) == 3
    assert SH.HANDOVER_LABEL not in briefs[0]
    assert "by legislation_id: uksi/1901/4, ssi/1902/30. Where" in briefs[1]
    assert "by legislation_id: uksi/1901/4, ssi/1902/30, ssi/1903/12. Where" in briefs[2]
    assert "1909/9" not in briefs[1] + briefs[2]


# --- P3.7: the line is not looked up ----------------------------------------------

def test_the_line_is_invisible_to_the_lookup_extractor():
    brief = _build_step_brief(DEPENDENT, PLAN, QUESTION, [STEP1_REPORT])
    assert extract_instrument_citations(brief)        # the line does name ids
    assert extract_instrument_citations(SH.without_handover_line(brief)) == []
    # Only a line the label opens is taken out: the label quoted inside other
    # text (the question is quoted into the CONTEXT paragraph) is left alone.
    quoted = f'CONTEXT: "{SH.HANDOVER_LABEL} SSI 1902/30"'
    assert SH.without_handover_line(quoted) == quoted


def test_the_worker_looks_up_the_steps_own_instrument_but_not_the_lines(monkeypatch):
    """Through the product's own routing (`run_worker_agent`): the instrument the
    step's text names is looked up; the line's are not."""
    set_request_provider_config({"_provider": "openrouter",
                                 "_research_mode": "legislation_only", "model": "m"})
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        body = kwargs.get("json") or {}
        asked.append("{legislation_type}/{year}/{number}".format(**body)
                     if "legislation_type" in body else body.get("legislation_id"))
        return httpx.Response(404, json={"detail": "Legislation not found"},
                              request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    step = dict(DEPENDENT, detail=DEPENDENT["detail"] + " Start with SSI 1905/5.")
    brief = _build_step_brief(step, PLAN, QUESTION, [STEP1_REPORT])
    assert "uksi/1901/4" in brief

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None,
                   **kw):
        return {"role": "assistant", "content": "Report."}

    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, brief, "m", None, 0))
    assert asked == ["ssi/1905/5"]
