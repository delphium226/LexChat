"""P3.1 (B10): the provision at the depth the lawyer asked for.

Measured before building (`wave3_p31_pre`, n=3 at HEAD, and every stored
replay of 6396/6365/6348): **every provision the three acceptance sessions
needed was retrieved with all its subsections, in every run.** Depth was lost
after retrieval, at three seams, and each had a prompt telling it to:

* the Worker's write-up: every legislation Worker prompt showed a WHOLE-section
  citation example (`[... - s.110](.../section/110)`) and the quick-lookup
  Worker was told to cite "Act + section";
* the Deep Research synthesis, which flattened the steps' pinpoints (6365 at
  HEAD: s.57 at 4 of 20 references in the step reports, 0 of 10 in the report);
* the chat-mode Manager's rewrite, which dropped 6396's provision entirely.

So the fix is at those three seams (user decision, Session 16), and these
tests pin it, together with the two decisions taken alongside it: the ranked
sections array is NOT used (it ranks against the title search), and the
section search now sends `size`, the parameter the endpoint reads.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src import prompts  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.agent.tools.executor import execute_worker_tool  # noqa: E402
from src.agent.tools.lex import _slim_search_results  # noqa: E402
from src.utils.citation_links import PROVISION_MARKER, enforce_provision_links  # noqa: E402
from src.utils.discovery_budget import SECTION_SEARCH_ROUNDS  # noqa: E402

_LEG_WORKERS = {
    "research": prompts.WORKER_SYSTEM_PROMPT,
    "hybrid": prompts.WORKER_SYSTEM_PROMPT_HYBRID,
    "quick-lookup": prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
}

# A citation example whose label stops at a whole section: "- s.110](" or
# "Under s.7 of the [". The shape all three prompts taught before P3.1.
_WHOLE_SECTION_EXAMPLE = re.compile(r"- s\.\d+\]\(|\bUnder s\.\d+ of the \[")
_PINPOINT_EXAMPLE = re.compile(r"s\.\d+\(\d+\)")


# ---------------------------------------------------------------------------
# Seam 1: the Worker's write-up
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(_LEG_WORKERS))
def test_no_legislation_worker_teaches_a_whole_section_citation(name):
    prompt = _LEG_WORKERS[name]
    assert not _WHOLE_SECTION_EXAMPLE.search(prompt)
    assert _PINPOINT_EXAMPLE.search(prompt)
    assert "Act + section," not in prompt


@pytest.mark.parametrize("name", ["research", "hybrid"])
def test_the_research_workers_say_the_link_stays_the_returned_url(name):
    """A pinpoint label on the section URL the tool returned: never a URL built
    for a subsection, which P1.6 would demote as never retrieved."""
    flat = " ".join(_LEG_WORKERS[name].split()).lower()
    assert "never build a url for a subsection" in flat
    assert "sch 2 para 3(1)" in flat


# The provisions the P3.1 acceptance grades (`replay_report.DEPTH_TRUTH`). An
# example in a prompt that names one of them would let a model copying the
# example's FORMAT land on the graded provision by accident, which would
# contaminate the acceptance. Caught at build, before any sweep: the first
# draft of these prompts used "Sch 1 para 1(2)" and "s.21(2)" as examples.
_GRADED = ("Sch 1 para 1(2)", "s.21(2)", "s.22(5)", "s.57(3)", "s.45(1)", "s.36(2)")


@pytest.mark.parametrize("prompt", [
    prompts.WORKER_SYSTEM_PROMPT, prompts.WORKER_SYSTEM_PROMPT_HYBRID,
    prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL, prompts.DEEP_RESEARCH_SYNTHESIS_PROMPT,
    prompts.MANAGER_SYSTEM_PROMPT_CONVERSATIONAL, prompts.MANAGER_SYSTEM_PROMPT,
])
def test_no_prompt_example_names_a_provision_the_acceptance_grades(prompt):
    for p in _GRADED:
        assert p not in prompt


@pytest.mark.parametrize("name", ["research", "hybrid"])
def test_the_research_workers_ask_for_the_whole_provision(name):
    """6348: the Worker had s.36(2) in hand and described s.36(1) only."""
    assert "what each of its subsections provides" in _LEG_WORKERS[name]


def test_the_quick_lookup_worker_asks_for_the_subsection_in_place():
    """Edited in place, not appended as a block: P2.4's A/B measured an
    appended block changing this Worker's output format and costing links."""
    prompt = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    assert "Act + the subsection or paragraph that states the point" in prompt
    assert 'Under s.7(2) of the [Acquisition of Land Act 1981](URL)' in prompt
    assert "PINPOINT" not in prompt
    # Quick lookup keeps its one-call phrasing; the code cap still applies.
    assert "One call per `legislation_id`" in prompt


# ---------------------------------------------------------------------------
# The one-call rule, relaxed to the number the code enforces
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["research", "hybrid"])
def test_the_one_call_rule_is_relaxed_to_the_enforced_number(name):
    prompt = _LEG_WORKERS[name]
    assert "exactly ONE call per" not in prompt
    assert "more than once for the same `legislation_id`" not in prompt
    assert f"at most {SECTION_SEARCH_ROUNDS} times" in prompt
    assert "refused" in prompt


def test_phase_4_no_longer_contradicts_the_cap():
    assert (f"within the limit of {SECTION_SEARCH_ROUNDS} section searches per "
            "`legislation_id`") in prompts.WORKER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Seams 2 and 3: the two agents that rewrite a Worker's findings
# ---------------------------------------------------------------------------

def test_the_deep_research_synthesis_keeps_a_pinpoint():
    p = prompts.DEEP_RESEARCH_SYNTHESIS_PROMPT
    assert "A pinpoint stays a pinpoint" in p
    assert "Never shorten it to s.12." in p


@pytest.mark.parametrize("chips", [True, False])
def test_the_chat_manager_keeps_the_provision_in_both_chip_variants(chips):
    p = prompts.get_manager_system_prompt(
        "legislation_only",
        {"_chat_mode": "conversational", "_suggested_questions_enabled": chips})
    assert "never reduce a provision to the instrument's name alone" in p


def test_the_research_manager_is_unchanged():
    """It passes the report through verbatim, and 6348's depth was lost in the
    Worker's report, not in the pass-through."""
    assert "never reduce a provision" not in prompts.MANAGER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# What a pinpoint label must not trip: P1.6's enforcement and the B14 check
# ---------------------------------------------------------------------------

S57 = "http://www.legislation.gov.uk/asp/2002/3/section/57"
ACT = "http://www.legislation.gov.uk/asp/2002/3"


def test_a_pinpoint_label_on_a_retrieved_section_url_is_left_alone():
    text = f"Interim reports run to 30 September ([WI(S)A 2002 - s.57(3)(a)]({S57}))."
    assert enforce_provision_links(text, {S57}) == (text, 0, 0)


def test_a_pinpoint_label_on_an_unretrieved_url_is_still_demoted():
    text = f"Interim reports run to 30 September ([WI(S)A 2002 - s.57(3)(a)]({S57}))."
    out, demoted, _ = enforce_provision_links(text, {ACT})
    assert demoted == 1 and S57 not in out
    assert f"s.57(3)(a) {PROVISION_MARKER}" in out


@pytest.mark.parametrize("label,url", [
    ("WI(S)A 2002 - s.57(3)(a)", S57),
    ("Cattle Identification (Scotland) Regulations 2007 - Sch. 1, para. 1(2)",
     "http://www.legislation.gov.uk/id/ssi/2007/174/schedule/1"),
    ("Sch 1 para 1(2)", "http://www.legislation.gov.uk/id/ssi/2007/174/schedule/1"),
    ("reg. 4(3)", "http://www.legislation.gov.uk/id/ssi/2007/174/regulation/4"),
])
def test_a_pinpoint_label_is_not_a_wrong_granularity_link(label, url):
    doc = {"session_id": "6365", "rep": 1,
           "turns": [{"turn": 1, "answer": f"See [{label}]({url}).", "audit": {}}]}
    assert rr.analyse_run(doc).bad_links == []


# ---------------------------------------------------------------------------
# Decision: the ranked sections array stays dropped, and dropping it is safe
# ---------------------------------------------------------------------------

_ROW = {"uri": "http://www.legislation.gov.uk/id/asp/2002/13",
        "title": "Freedom of Information (Scotland) Act 2002",
        "status": "revised", "year": 2002, "extent": ["Scotland"]}


@pytest.mark.parametrize("sections", [
    [{"number": "70", "provision_type": "section", "score": 1.0},
     {"number": "", "provision_type": "section", "score": 0.95}],
    None, "junk", [None, 3, {"number": None}], [],
])
def test_the_ranked_array_is_never_carried_and_never_breaks_the_slimmer(sections):
    """Decided at Session 16: for FOISA the title search ranks ss.70, 76 and 3
    and omits s.36, so carrying it would steer Phase 2 away from the answer."""
    row = dict(_ROW, sections=sections)
    out = _slim_search_results({"results": [row], "total": 141})
    assert out == _slim_search_results({"results": [dict(_ROW)], "total": 141})
    assert "sections" not in json.dumps(out)


# ---------------------------------------------------------------------------
# `size`, not `limit`
# ---------------------------------------------------------------------------

def test_the_section_search_sends_size_the_parameter_the_endpoint_reads(monkeypatch):
    """`/legislation/section/search` reads `size` (verified live 2026-09-18:
    `limit=3` returns 10 rows, `size=3` returns 3). `limit` was ignored."""
    sent = []

    async def fake(client, method, url, *, name="", **kwargs):
        sent.append((url, kwargs["json"]))
        return httpx.Response(200, json=[], request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    asyncio.run(execute_worker_tool("search_legislation_sections",
                                    {"legislation_id": "asp/2002/13", "query": "s36"}))
    ((url, payload),) = sent
    assert url.endswith("/legislation/section/search")
    assert payload == {"query": "s36", "legislation_id": "asp/2002/13", "size": 10}
