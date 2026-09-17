"""P2.2 (bucket B5) — no bare negatives.

The row states the acceptance as *"6409 and 6367 name their search terms and
active filters in the negative answer"*, and **Invariant 1 applies with force**:
the test is that the negative is EXPLAINED, not that it becomes a positive.
Honest failure is the most-praised behaviour in the corpus and a fix that raises
the answer rate by lowering the evidence bar is a regression even if the row goes
green. Nothing below asserts that anything was found.

**What this file pins that the row did not anticipate.** The row is written
against the missing `else:` on `if id_pairs:` — `search_legislation` is the only
search tool with no zero-result nudge. That is fixed here and is tested, but it
is not where B5 lives. Measured over the Wave 1 replay directory:

  * zero-result `search_legislation` calls: **4 of 790**;
  * `search_legislation` calls that were windowed (5 rows shown of N matched):
    **783 of 783**, median N = 141, p90 185, max 220;
  * turns asserting a negative: **17**, of which **0** followed an empty search.

So a fix confined to the empty branch would have moved none of the seventeen and
could still have gone green on a loose detector. The scope block therefore goes
on **both** branches, and `test_the_window_note_fires_on_a_productive_search` is
the one that matters — it is the branch 783 of 790 calls take.
"""

import json
import re

import pytest

from src.agent.agent_core import run_deep_research, run_worker_agent
from src.agent.provider_factory import set_request_provider_config
from src.utils.research_halt import halt_worker_report
from src.utils.search_scope import (
    LEX_COVERAGE_SENTENCE,
    answer_scope_footer,
    enabling_power_note,
    incomplete_steps_note,
    legislation_search_note,
    record_enabling_power,
    record_search,
    section_search_note,
    strip_scope_blocks,
    worker_scope_block,
)

HALT = {"reason": "step_cap", "limit": 20, "steps": 20}


def _search_result(shown=5, matched=141, removed=0):
    """A slimmed `search_legislation` response in its post-P1.3 shape."""
    return {
        "results": [
            {"legislation_id": f"asp/2018/{i}", "title": f"Act {i}",
             "url": f"http://www.legislation.gov.uk/id/asp/2018/{i}",
             "status": "revised", "year": 2018, "extent": ["Scotland"]}
            for i in range(shown)
        ],
        "returned": shown,
        "total": matched,
        "total_matched": matched,
        "removed_by_filters": removed,
    }


# ---------------------------------------------------------------------------
# The window — the branch 783 of 790 searches take
# ---------------------------------------------------------------------------

def test_the_window_note_fires_on_a_productive_search():
    """Seven of the seventeen measured negatives are one sentence — *"no
    commencement regulations have been made"* (6409 x5, 6410 x2) — drawn from the
    top 5 of a median 141 ranked matches. The model was never told that is what
    it was looking at."""
    note = legislation_search_note(
        {"query": "commencement regulations Social Security Scotland 2025"},
        _search_result(shown=5, matched=141),
    )
    assert "top 5 of 141 candidates ranked by relevance" in note
    assert "commencement regulations Social Security Scotland 2025" in note
    assert "cannot establish" in note
    assert "Do NOT state that anything does not exist" in note


def test_the_note_does_not_claim_a_window_that_is_not_there():
    """If the API matched no more than it showed, there is no window and saying
    there is one would be its own falsehood."""
    note = legislation_search_note({"query": "q"}, _search_result(shown=3, matched=3))
    assert "3 result(s)" in note
    assert "candidates ranked" not in note


def test_the_total_is_labelled_a_ranking_depth_not_a_count_of_hits():
    """LEX ranks the whole corpus against the wording: *"zzqx nonexistent statute
    about interplanetary haggis"* returns **185 matches** live. A model told "5 of
    185" and not told what the 185 is has every reason to go hunting for the other
    180 — which is the discovery loop P2.7 exists to stop, so the note must not
    create the incentive it is meant to remove."""
    note = legislation_search_note({"query": "q"}, _search_result(matched=185))
    assert "ranking depth" in note
    assert "NOT a count of relevant instruments" in note
    assert "do not go looking for the rest" in note


def test_the_active_filters_are_named_verbatim():
    """The row's acceptance in one line: a negative must say what limits it was
    reached under. The filters live on the request config and the year window is
    the intersection of the user's and the model's own arguments."""
    note = legislation_search_note(
        {"query": "q", "year_from": 2019},
        _search_result(),
        {"_jurisdiction": "scotland", "_legislation_type": "secondary",
         "_year_from": 2015, "_year_to": 2026},
    )
    assert "jurisdiction=scotland" in note
    assert "legislation_type=secondary" in note
    # max(2015, 2019) — executor.py intersects, so 2019 is the window that ran.
    assert "years 2019-2026" in note


def test_no_filters_says_none_rather_than_going_quiet():
    note = legislation_search_note({"query": "q"}, _search_result())
    assert "Filters in force: none." in note


def test_rows_the_filters_removed_are_counted():
    note = legislation_search_note({"query": "q"}, _search_result(removed=12))
    assert "12 row(s) on this page were removed by those filters" in note


# ---------------------------------------------------------------------------
# The empty branch — the row's own mechanical half
# ---------------------------------------------------------------------------

def test_the_zero_result_branch_exists_at_all():
    """`search_legislation` was the only search tool with no zero-result nudge:
    case law, Scottish Parliament and Hansard all have one and the legislation
    branch fired only `if id_pairs:`."""
    note = legislation_search_note(
        {"query": "salmon fishing byelaws"},
        {"results": [], "returned": 0, "total": 0, "total_matched": 0},
    )
    assert "returned 0 results" in note
    assert "salmon fishing byelaws" in note


def test_the_empty_branch_caps_searching_rather_than_licensing_it():
    """Deliberately unlike the case-law and Hansard nudges, which say "you may
    retry once". P2.7 measured the legislation Worker looping on discovery — 26%
    redundant calls on the turns that hit the step cap against a 15% base rate —
    so this branch says stop, not try again."""
    note = legislation_search_note({"query": "q"}, {"results": [], "returned": 0})
    assert "stop" in note.lower()
    assert "retry" not in note.lower()


def test_the_empty_branch_reports_the_counts_when_it_has_them():
    note = legislation_search_note(
        {"query": "q"},
        {"results": [], "returned": 0, "total_matched": 97, "removed_by_filters": 20},
        {"_jurisdiction": "scotland"},
    )
    assert "the index reported 97 match(es)" in note
    assert "20 retrieved row(s) were removed by the filters" in note
    assert "jurisdiction=scotland" in note


# ---------------------------------------------------------------------------
# Coverage — "the index does not hold it" is not "it does not exist"
# ---------------------------------------------------------------------------

def test_both_branches_carry_the_coverage_sentence():
    """The limb that turns a true-sounding negative false. Verified live
    2026-09-15: ssi/2025/377 and ssi/2026/170 are both 404 in LEX, and both were
    cited correctly by the lawyer who asked (6409, 6373)."""
    for data in (_search_result(), {"results": [], "returned": 0}):
        assert LEX_COVERAGE_SENTENCE in legislation_search_note({"query": "q"}, data)


def test_the_coverage_sentence_never_says_none_of_a_series_is_held():
    """P5.3 recorded "UK SI 2026 ~0% held" from a 20-point lookup sample. A
    `/legislation/search` cross-check returns 27 distinct `uksi/2026/*`
    instruments, all 12 spot-checked resolving on lookup; a 60-point census puts
    it at ~2%. "Under 5%" is true; "none" would not be, and a lawyer told "none"
    would stop looking."""
    s = LEX_COVERAGE_SENTENCE.lower()
    assert "under 10%" in s
    # The claim to exclude is "0% of the series is held" — not the characters
    # "0%", which "under 10%" legitimately contains. (That substring collision
    # failed this test the moment the bound widened from 5% to 10%.)
    assert not re.search(r"(?<![1-9])0%", s)
    assert "none of" not in s
    assert "2026" in s and "sampled" in s          # dated, because it will move
    assert "not evidence of absence in law" in s


def test_the_coverage_figures_are_bounds_not_the_last_sample():
    """**Caught by re-running the probe, one day after the figure shipped.** The
    string first said "under 5%", written from a single 60-point sample of SSI
    2026 that returned 1/60. The next day the same command returned 5/60 — 8%,
    falsifying a claim already sitting in a string a government lawyer reads.
    That is ordinary noise at n=60, so a product claim has to be true across the
    spread, not equal to the last draw. Hedging words are load-bearing here."""
    s = LEX_COVERAGE_SENTENCE.lower()
    assert "roughly" in s and "under" in s
    # No bare equality claim about a sampled rate.
    for exact in ("exactly", "precisely", "is 85%", "is 2%", "is 8%"):
        assert exact not in s


def test_the_search_terms_requirement_is_bounded():
    """6409 turns 6 and 7 ran 17 and 25 searches. "Give the exact search terms
    used" invites all 25 into the answer, turning a disclosure into a log and
    burying the finding — the full list is in the audit trace, not the answer."""
    note = legislation_search_note({"query": "q"}, _search_result())
    assert "two or three most specific" in note
    assert "not every query you ran" in note


def test_the_no_filters_case_must_be_stated_not_skipped():
    """The commonest case is no filters at all, where silence is
    indistinguishable from not having checked."""
    note = legislation_search_note({"query": "q"}, _search_result())
    assert "or say plainly that none were applied" in note


def test_the_miss_is_attributed_to_the_search_not_to_the_lawyer():
    """6373: AILA questioned FrankieH's citation of SSI 2026/170 — *"could you
    confirm the year or the SI number?"* — when the citation was right and the
    index was short. 6409 did the same three times over SSI 2025/377."""
    note = legislation_search_note({"query": "q"}, _search_result())
    assert "never to the user's citation" in note


def test_speculation_about_the_cause_is_forbidden_everywhere():
    """6335 turn 7 invented *"the database is having difficulty parsing the
    Schedule B1 structure"*; 6340 invented a broad enabling power. The same
    prohibition P2.1 carries, at the seam where the negative is formed."""
    for note in (
        legislation_search_note({"query": "q"}, _search_result()),
        legislation_search_note({"query": "q"}, {"results": [], "returned": 0}),
        section_search_note({"query": "q", "legislation_id": "asp/2018/9"},
                            {"results": [], "returned": 0}),
    ):
        assert "speculate" in note


# ---------------------------------------------------------------------------
# Section search — the second source of bare negatives
# ---------------------------------------------------------------------------

def test_the_section_note_says_the_ranked_ten_are_not_the_act():
    """6335 turn 7 reported a targeted search "returned no results" when it had
    returned results — paragraphs 42-44 simply were not in the ranked ten."""
    note = section_search_note(
        {"query": "paragraphs 42, 43, 44", "legislation_id": "ukpga/1986/45"},
        {"results": [{"number": 1}, {"number": 2}], "returned": 2},
    )
    assert "2 provision(s) of ukpga/1986/45" in note
    assert "NOT the full contents" in note
    assert "may still be in it" in note


def test_the_section_note_distinguishes_absent_from_not_surfaced():
    note = section_search_note(
        {"query": "preamble", "legislation_id": "ssi/2025/119"},
        {"results": [], "returned": 0},
    )
    assert "0 provisions of ssi/2025/119" in note
    assert "did not surface one" in note
    assert "NOT that the instrument lacks such a provision" in note


def test_a_section_note_grants_no_new_retry_licence():
    for data in ({"results": [], "returned": 0}, {"results": [{"n": 1}], "returned": 1}):
        assert "retry" not in section_search_note({"legislation_id": "x"}, data).lower()


# ---------------------------------------------------------------------------
# Robustness — a diagnostic must never be the reason a retrieval goes missing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("data", [
    None, "", "not json", [], {"error": "LEX API error: 500"}, {"unexpected": 1},
])
def test_unparseable_or_errored_results_produce_no_note(data):
    """Invariant 5 — additive and fail-soft. An error payload gets no lecture
    about ranked search, and nothing here may raise on a shape we have not seen."""
    assert legislation_search_note({"query": "q"}, data) in ("", None) or isinstance(
        legislation_search_note({"query": "q"}, data), str
    )
    assert section_search_note({"query": "q"}, data) == "" or isinstance(
        section_search_note({"query": "q"}, data), str
    )


def test_an_error_payload_is_left_alone():
    err = {"error": "LEX API error: 500"}
    assert legislation_search_note({"query": "q"}, err) == ""
    assert section_search_note({"query": "q"}, err) == ""


def test_the_note_survives_a_result_that_already_carries_a_nudge():
    """By the time anything re-reads a tool result it may already have a block
    appended — a plain `json.loads` raises "Extra data" on exactly the calls that
    succeeded, which is the trap `replay_report._json_or_none` documents."""
    payload = json.dumps(_search_result()) + "\n\n[NEXT STEP: ...]"
    assert "top 5 of 141 candidates" in legislation_search_note({"query": "q"}, payload)


def test_a_long_query_is_capped_not_dropped():
    note = legislation_search_note({"query": "x" * 5000}, _search_result())
    assert "x" * 200 in note
    assert len(note) < 2000


# ---------------------------------------------------------------------------
# The wiring — the block must reach the model, not just exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_block_is_appended_to_what_the_worker_actually_receives(monkeypatch):
    """P1.6's lesson applied forward: *a fix can be invisible to the thing that
    grades it*. The nudges are appended **after** summarisation deliberately (the
    summariser cannot eat what it never saw), so this asserts on the string
    `run_worker_tool` returns, not on the note builder."""
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_jurisdiction": "scotland", "model": "test-model",
    })
    try:
        async def fake_exec(name, args, on_chunk=None, timing_collector=None):
            return json.dumps(_search_result())

        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        out = await agent_shared.run_worker_tool(
            "search_legislation", {"query": "commencement"}, "q", None, "m",
        )
        assert "[SEARCH SCOPE" in out
        assert "jurisdiction=scotland" in out
        # The Phase-2 imperative stays last on a productive search: it is the
        # instruction that drives retrieval, and recency is why it works.
        assert out.index("[SEARCH SCOPE") < out.index("[NEXT STEP")
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_section_search_gets_one_too(monkeypatch):
    from src.agent import agent_shared

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        async def fake_exec(name, args, on_chunk=None, timing_collector=None):
            return json.dumps({"results": [], "returned": 0})

        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        out = await agent_shared.run_worker_tool(
            "search_legislation_sections",
            {"query": "preamble", "legislation_id": "ssi/2025/119"}, "q", None, "m",
        )
        assert "[SEARCH SCOPE" in out
        assert "ssi/2025/119" in out
    finally:
        set_request_provider_config({})


# ---------------------------------------------------------------------------
# A negative reached under a halted step (the half P2.1 narrows but cannot close)
# ---------------------------------------------------------------------------

def test_the_synthesis_is_told_which_steps_did_not_establish_anything():
    """6382 rep 2 of P2.1's acceptance sweep: steps 2 and 3 halted and the report
    still opened *"no SSIs ... were found that contain the '£' symbol"* — the two
    steps that would have established that are the two that stopped."""
    note = incomplete_steps_note(
        [{**HALT, "step": 2, "title": "Search SSIs"},
         {**HALT, "step": 3, "title": "Check text"}],
        steps_total=4,
    )
    assert "step 2 (Search SSIs)" in note and "step 3 (Check text)" in note
    assert "(2 of 4 steps)" in note
    assert "MUST NOT write, in the BLUF or anywhere else" in note
    assert "does not exist, was not made, or could not be found" in note


def test_the_instruction_still_demands_a_full_answer_from_the_completed_steps():
    """Invariant 1 in the other direction: this must not become a licence to
    refuse. The steps that finished are still answerable."""
    note = incomplete_steps_note([{**HALT, "step": 1, "title": "A"}])
    assert "Answer fully from the steps that DID complete" in note


def test_no_halted_step_means_no_instruction():
    assert incomplete_steps_note([]) == ""
    # A Manager-scope halt carries no step number; it is disclosed by P2.1's
    # notice and has no synthesis to instruct.
    assert incomplete_steps_note([{**HALT, "scope": "manager"}]) == ""


@pytest.mark.asyncio
async def test_the_synthesis_payload_carries_it_end_to_end():
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })
    seen = {}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        seen["user"] = messages[-1]["content"]
        return {"content": "INTEGRATED REPORT"}

    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        halted = "Step 2" in query
        return {
            "content": halt_worker_report(HALT) if halted else "findings",
            "sources": [],
            **({"halted": dict(HALT)} if halted else {}),
        }

    plan = {"scope_note": "scope",
            "steps": [{"id": i, "title": f"Step {i} title", "detail": "d"}
                      for i in (1, 2, 3)]}
    try:
        await run_deep_research(
            synthesis, worker, plan, [{"role": "user", "content": "q"}],
            "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})
    assert "INCOMPLETE STEPS" in seen["user"]
    assert "step 2 (Step 2 title)" in seen["user"]
    # It has to come after the findings it qualifies, or it qualifies nothing.
    assert seen["user"].index("STEP FINDINGS") < seen["user"].index("INCOMPLETE STEPS")


@pytest.mark.asyncio
async def test_a_clean_deep_research_payload_is_unchanged():
    """No false positives: a plan whose steps all completed must produce exactly
    the payload it produced before this row."""
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })
    seen = {}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        seen["user"] = messages[-1]["content"]
        return {"content": "INTEGRATED REPORT"}

    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        return {"content": "findings", "sources": []}

    try:
        await run_deep_research(
            synthesis, worker,
            {"scope_note": "s", "steps": [{"id": 1, "title": "T", "detail": "d"}]},
            [{"role": "user", "content": "q"}], "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})
    assert "INCOMPLETE STEPS" not in seen["user"]
    assert seen["user"].rstrip().endswith("findings")


# ---------------------------------------------------------------------------
# The seam the first acceptance run found open
# ---------------------------------------------------------------------------
#
# 6367 rep 1 carried the tool-result block in the Worker's context 27 times and
# still produced *"No Statutory Instruments were found prescribing …"* with no
# terms and no filters, and in the body *"A search up to 2026 CONFIRMS that no
# Statutory Instruments prescribe …"*. Three of its four worker reports carried
# no scope language at all. The Worker sees tool results; the Manager sees only
# the report, and the synthesis only the step findings — so the agent that
# writes the negative had never seen a scope block.


def _log(n_searches=2, n_sections=1):
    log = [{"tool": "search_legislation", "query": f"query {i}", "shown": 5,
            "matched": 141 + i} for i in range(n_searches)]
    log += [{"tool": "search_legislation_sections", "query": "s 5",
             "legislation_id": "asp/2002/3", "shown": 10, "matched": None}
            for _ in range(n_sections)]
    return log


def test_the_worker_report_block_states_the_terms_the_filters_and_the_rule():
    block = worker_scope_block(_log(), {"_jurisdiction": "scotland", "_year_to": 2026})
    assert "Searched the legislation index 2 time(s)" in block
    assert '"query 0"' in block and '"query 1"' in block
    assert "asp/2002/3" in block
    assert "jurisdiction=scotland, years any-2026" in block
    assert "NONE of this can establish that something does not exist" in block
    assert 'Do not say a search "confirms" an absence' in block
    assert LEX_COVERAGE_SENTENCE in block


def test_the_query_list_is_capped_so_the_footer_cannot_bury_the_report():
    """6409 turn 7 ran 25 searches. A footer that prints all of them is a
    transcript, and the full list is already in the audit trace."""
    block = worker_scope_block(_log(n_searches=30, n_sections=0))
    assert "and 18 more" in block
    assert block.count('"query ') == 12


def test_no_searches_means_no_block():
    """A worker that searched for nothing has nothing to disclose, and an empty
    footer on every conversational turn would be noise."""
    assert worker_scope_block([]) == ""
    assert worker_scope_block(None) == ""


def test_record_search_never_raises_on_a_shape_it_has_not_seen():
    log = []
    for data in (None, "", "not json", [], {"weird": True}, {"results": "no"}):
        record_search(log, "search_legislation", {"query": "q"}, data)
    assert len(log) == 6
    record_search(None, "search_legislation", {"query": "q"}, {})  # no log: no-op


def test_the_block_never_reaches_the_lawyer():
    """It is addressed to an agent — "NONE of this can establish…" is an
    instruction, not prose for a government lawyer — and in research mode the
    Manager is told to pass the Worker's report through verbatim."""
    body = "1. **Summary Answer (BLUF):** The Act applies.\n2. **References:** x"
    out, n = strip_scope_blocks(body + worker_scope_block(_log()))
    assert n == 1
    assert out == body.strip()
    assert "SEARCH SCOPE" not in out


def test_the_strip_also_removes_a_tool_result_block():
    """Belt and braces, like the halt-marker strip: a tool-result block should
    never reach an answer, and if one does it must not render."""
    tool_block = legislation_search_note({"query": "q"}, _search_result())
    out, n = strip_scope_blocks("The answer." + tool_block)
    assert n == 1 and "SEARCH SCOPE" not in out


def test_the_strip_leaves_an_ordinary_answer_byte_identical():
    body = "A complete answer with no problems at all."
    assert strip_scope_blocks(body) == (body, 0)


def test_a_quoted_tool_block_cannot_swallow_the_answer():
    """The severe failure mode, and the reason the worker pattern requires the
    words "research step". The strip runs on the Manager's ANSWER. If a model
    quoted a tool-result block mid-answer — not asked for, not prevented — a
    worker pattern matching any `[SEARCH SCOPE …]` opener would start there and
    run lazily to the report's closing marker at the end, deleting the whole
    answer body in between. Low probability, total loss."""
    tool_block = legislation_search_note({"query": "q"}, _search_result())
    answer = (
        "1. **Summary Answer (BLUF):** The Act applies in Scotland.\n\n"
        "The tool told me:" + tool_block + "\n\n"
        "2. **Detailed Analysis:** Section 5 imposes the duty.\n"
        "3. **References:** legislation.gov.uk\n"
    ) + worker_scope_block(_log())
    out, n = strip_scope_blocks(answer)
    assert n == 2
    assert "SEARCH SCOPE" not in out
    # Everything the model actually wrote survives.
    assert "The Act applies in Scotland" in out
    assert "Section 5 imposes the duty" in out
    assert "References" in out


@pytest.mark.asyncio
async def test_the_block_lands_on_the_report_the_manager_reads(monkeypatch):
    """End to end through `run_worker_agent`: the facts must be ON the report,
    because that is all the Manager and the Deep Research synthesis ever see."""
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_jurisdiction": "scotland", "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        return json.dumps(_search_result())

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        await executor("search_legislation", {"query": "commencement regulations"})
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** No commencement regulations were found.\n"
            "2. **Detailed Analysis:** None.\n3. **Jurisdiction & Status:** Scotland.\n"
            "4. **References:** None found.")}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        result = await run_worker_agent(
            chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        )
    finally:
        set_request_provider_config({})

    report = result["content"]
    assert "[SEARCH SCOPE" in report
    assert '"commencement regulations"' in report
    assert "jurisdiction=scotland" in report
    # The model's own text is untouched — the block is appended, never a rewrite.
    assert strip_scope_blocks(report)[0].startswith("1. **Summary Answer (BLUF):**")


@pytest.mark.asyncio
async def test_the_block_does_not_mark_a_source_as_cited(monkeypatch):
    """Order matters. `_source_is_used` matches a source on its bare
    `legislation_id`, and the block names the instruments that were
    section-searched. Appending before source filtering would let our own footer
    vouch for a source the model never mentioned — a diagnostic corrupting the
    measurement of a different bucket (P4.3's unused-source rate)."""
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        return json.dumps(_search_result(shown=1))

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        await executor("search_legislation_sections",
                       {"query": "s 5", "legislation_id": "asp/2018/0"})
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Nothing on point was located.\n"
            "2. **References:** None found.")}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        result = await run_worker_agent(
            chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        )
    finally:
        set_request_provider_config({})

    # The block names asp/2018/0; the model's prose does not. Stripping the block
    # must leave no trace of it, which is what keeps the source filter honest.
    assert "asp/2018/0" in result["content"]
    assert "asp/2018/0" not in strip_scope_blocks(result["content"])[0]


# ---------------------------------------------------------------------------
# The code-emitted footer — the escalation the acceptance forced
# ---------------------------------------------------------------------------
#
# Carrying the facts to the agent that writes the answer moved compliance from
# **0% to 52%** over the acceptance replay (n=3 on 6409 and 6367, 23 turns
# asserting a negative). 48% of negatives still told a lawyer something was not
# found without saying what had been looked for. Invariant 2: where a row offers
# a choice between "tell the model to" and "make it so", take the second.


def test_the_footer_states_the_terms_the_filters_and_the_limit():
    footer = answer_scope_footer(
        [{"tool": "search_legislation", "query": "commencement regulations 2025"},
         {"tool": "search_legislation", "query": "social security scotland"}],
        {"_jurisdiction": "scotland"},
    )
    assert '"commencement regulations 2025"' in footer
    assert '"social security scotland"' in footer
    assert "filters in force: jurisdiction = scotland" in footer
    assert "ranked search" in footer
    assert "not found in this index" in footer
    assert "not the same as being absent from the law" in footer


def test_the_footer_says_so_when_no_filter_was_applied():
    """Silence about filters is indistinguishable from not having checked, and
    "no filter narrowed it" is the commonest true answer."""
    footer = answer_scope_footer([{"tool": "search_legislation", "query": "q"}])
    assert "no jurisdiction, type or date filter narrowed it" in footer


def test_an_inert_year_bound_is_not_reported_as_a_constraint():
    """Caught in the first footer sweep. 6409 and 6367 both ran with
    `year_to = 2026`, which excluded nothing in September 2026, and the footer
    said *"filters in force: years any-2026"* — a constraint that did not
    constrain. An overstated limit invites a lawyer to re-run a search that was
    never narrowed, wasting the time this row exists to protect."""
    inert = answer_scope_footer(
        [{"tool": "search_legislation", "query": "q"}], {"_year_to": 2026})
    assert "no jurisdiction, type or date filter narrowed it" in inert
    assert "2026" not in inert.split("This is a ranked search")[0]
    # A bound that really is in the past is still reported.
    past = answer_scope_footer(
        [{"tool": "search_legislation", "query": "q"}], {"_year_to": 2010})
    assert "years up to 2010" in past


def test_the_model_quoting_its_own_query_does_not_double_the_quotes():
    """Also from the first footer sweep: the model routinely quotes its query,
    and wrapping that again rendered `""Water Industry Commission""`. The same
    query with and without the model's quotes is one query, not two."""
    footer = answer_scope_footer([
        {"tool": "search_legislation", "query": '"Water Industry Commission"'},
        {"tool": "search_legislation", "query": "Water Industry Commission"},
        {"tool": "search_legislation", "query": "WICS annual report"},
    ])
    assert '""' not in footer
    assert '"Water Industry Commission", "WICS annual report"' in footer
    assert "further quer" not in footer      # three entries, two distinct queries


def test_the_footer_lists_two_queries_and_counts_the_rest():
    """6409 turn 7 ran 25 searches. A footer that lists all of them is a
    transcript; the audit trace already holds the full list."""
    footer = answer_scope_footer(
        [{"tool": "search_legislation", "query": f"q{i}"} for i in range(9)])
    assert '"q0"' in footer and '"q1"' in footer and '"q2"' not in footer
    assert "7 further queries not listed" in footer


def test_a_turn_that_ran_no_legislation_search_gets_no_footer():
    """A purely conversational reply, or a case-law-only turn, is untouched —
    the footer describes a legislation search and there was none."""
    assert answer_scope_footer([]) == ""
    assert answer_scope_footer(None) == ""
    assert answer_scope_footer([{"tool": "search_case_law", "query": "q"}]) == ""
    assert answer_scope_footer([{"tool": "search_legislation", "query": ""}]) == ""


def test_the_footer_satisfies_the_acceptance_conditions_by_construction():
    """Stated plainly because it makes the mechanical acceptance circular: after
    this change the three conditions are met by code on every researched answer,
    so the number that still measures the *model* is the one graded with the
    footer removed. `replay_report negatives` reports both."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import tools.replay_report as rr

    answer = "No commencement regulations were found." + answer_scope_footer(
        [{"tool": "search_legislation", "query": "commencement regulations 2025"}])
    assert rr.NEG_ASSERTED.search(answer)
    assert rr._names_search_terms(answer)
    assert rr.NEG_LIMITS.search(answer)
    assert rr.NEG_BLAMED_INDEX.search(answer)
    assert not rr.NEG_BLAMED_USER.search(answer)


@pytest.mark.asyncio
async def test_the_footer_reaches_the_answer_and_sits_after_the_sources(monkeypatch):
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        return json.dumps(_search_result())

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None):
        await executor("search_legislation", {"query": "commencement regulations"})
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Nothing found.\n"
            "2. **References:** None found.")}

    async def worker(*a, **kw):
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0,
        )

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "No commencement regulations exist."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        final = await process_user_request(
            manager, worker, [{"role": "user", "content": "q"}],
            "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})

    assert "*Search scope:" in final["content"]
    assert '"commencement regulations"' in final["content"]
    # The agent-facing block never renders; only the lawyer-facing line does.
    assert "SEARCH SCOPE" not in final["content"]
    # And it is last, so nothing reads a query string as part of the answer body.
    assert final["content"].rstrip().endswith("absent from the law.*")


# ---------------------------------------------------------------------------
# P2.3 (B3b) — an enabling power may be asserted only where it was retrieved
# ---------------------------------------------------------------------------
#
# The hazard this whole section is written against: **citing a provision is not
# asserting a derivation.** "Under section 91 of the Act, Ministers must
# consult" is correct legal writing about retrieved text; "SSI 2018/273 was made
# under section 91" is the B3 claim. A fix — or a test — that cannot tell them
# apart pushes the model to hedge findings it actually retrieved, which is the
# regression Invariant 1 exists to prevent.

# The two real preambles the replay corpus ever returned, both from 6340 rep 1's
# `get_legislation_text` calls. Pinned as fixtures rather than invented, because
# the whole permitted branch rests on this text existing in this field.
_REAL_RECITAL = (
    "In exercise of the powers conferred upon me by sections 75(c) and 144(5) "
    "of the Education (Scotland) Act 1962(a) and of all other powers enabling "
    "me in that behalf, I hereby make the following regulations:-"
)
_NOT_A_RECITAL = (
    "These Regulations bring sections 31 and 36 and schedules 5 and 10 of the "
    "Social Security (Scotland) Act 2018 into force on 8 October 2020."
)


def _text_result(description="", full_text="Section 1) Citation and commencement"):
    """A `/legislation/text` response in its real shape.

    `{legislation, full_text}` — NOT `text`. The nested `legislation.text` key is
    empty for everything, including fully held Acts (P5.1's correction), and the
    preamble arrives in `legislation.description`.
    """
    return {
        "legislation": {
            "legislation_id": "uksi/1979/766",
            "title": "The ... Regulations 1979",
            "description": description,
            "text": "",
        },
        "full_text": full_text,
    }


def test_a_retrieved_preamble_permits_the_claim_and_hands_back_the_words():
    note = enabling_power_note({"legislation_id": "uksi/1979/766"},
                               _text_result(description=_REAL_RECITAL))
    assert "ENABLING POWER" in note
    assert "DOES state" in note
    assert "sections 75(c) and 144(5)" in note      # the words, not a paraphrase
    assert "You MAY state the enabling power" in note


def test_a_record_without_a_preamble_forbids_the_claim():
    note = enabling_power_note({"legislation_id": "ssi/2020/295"},
                               _text_result(description=_NOT_A_RECITAL))
    assert "does NOT state" in note
    assert "Do NOT write" in note
    # And it must say what to do instead — Invariant 1: the honest negative is
    # the right answer, not silence.
    assert "could not be verified" in note


def test_the_recital_is_found_in_full_text_when_the_description_lacks_it():
    """1 of the 103 instruments sampled live carried it only there.

    A rule that missed a real recital would forbid a claim the material
    supports, which is the failing direction nobody would notice."""
    note = enabling_power_note(
        {"legislation_id": "uksi/1966/1171"},
        _text_result(description="",
                     full_text="Her Majesty, by virtue and in exercise of the "
                               "powers in that behalf conferred by the Foreign "
                               "Jurisdiction Act 1890(a) ..."))
    assert "DOES state" in note


def test_primary_legislation_gets_no_block_at_all():
    """An Act has no enabling power of its own, so the block cannot apply.

    Noise in a block is what gets the block ignored."""
    for lid in ("asp/2018/9", "ukpga/1962/47", "anaw/2014/4"):
        assert enabling_power_note({"legislation_id": lid},
                                   _text_result(description=_REAL_RECITAL)) == ""


@pytest.mark.parametrize("data", [{}, {"error": "boom"}, "not json", None])
def test_a_failed_retrieval_produces_no_block(data):
    assert enabling_power_note({"legislation_id": "ssi/2020/295"}, data) == ""


def test_the_search_block_names_adjacency_only_where_an_si_is_in_the_rows():
    """6340's mechanism exactly: three SIs that merely ranked highly for an
    Act's title were reported as made under it."""
    acts_only = legislation_search_note({"query": "q"}, _search_result())
    assert "made under" not in acts_only

    with_si = _search_result()
    with_si["results"][0]["legislation_id"] = "ssi/2018/273"
    note = legislation_search_note({"query": "q"}, with_si)
    assert "NO relationship data" in note
    assert "has NOT thereby been shown to be made under" in note


def test_a_section_search_of_an_instrument_says_it_cannot_establish_the_power():
    """The route the Worker actually uses for instruments — and the preamble is
    not a ranked provision, so it can never appear here."""
    si = section_search_note({"legislation_id": "ssi/2018/273", "query": "q"},
                             {"results": [{"provision": "reg 1"}], "returned": 1})
    assert "cannot tell you what this instrument was made under" in si
    act = section_search_note({"legislation_id": "asp/2018/9", "query": "q"},
                              {"results": [{"provision": "s 95"}], "returned": 1})
    assert "made under" not in act


# --- the worker-report seam: the Manager never sees a tool result -------------

def _log_with(*pairs):
    log = [{"tool": "search_legislation", "query": "q", "legislation_id": "",
            "shown": 5, "matched": 141}]
    for lid, stated in pairs:
        record_enabling_power(
            log, "get_legislation_text", {"legislation_id": lid},
            _text_result(description=_REAL_RECITAL if stated else _NOT_A_RECITAL))
    return log


def test_the_report_block_forbids_the_claim_when_nothing_was_retrieved():
    block = worker_scope_block(_log_with(("ssi/2018/273", False),
                                         ("ssi/2019/269", False)), {})
    assert "Enabling power: NOT retrieved for any of the 2 instrument(s)" in block
    assert "Ranking near an Act in a keyword search is not evidence" in block


def test_the_report_block_names_the_instruments_it_may_be_claimed_for():
    block = worker_scope_block(_log_with(("uksi/1979/766", True),
                                         ("ssi/2018/273", False)), {})
    assert "retrieved for 1 of 2 instrument(s)" in block
    assert "uksi/1979/766" in block
    assert "For EVERY other instrument" in block


def test_a_step_that_touched_no_instrument_says_nothing_about_enabling_power():
    """No derivation claim can arise, so the sentence would be noise."""
    log = [{"tool": "search_legislation", "query": "q", "legislation_id": "",
            "shown": 5, "matched": 141}]
    assert "Enabling power" not in worker_scope_block(log, {})


def test_primary_legislation_is_not_recorded_at_all():
    log = []
    record_enabling_power(log, "get_legislation_text",
                          {"legislation_id": "asp/2018/9"},
                          _text_result(description=_REAL_RECITAL))
    assert log == []


def test_recording_never_raises_on_anything():
    """Invariant 5 — a diagnostic must never be the reason a retrieval fails."""
    for args, data in (({"legislation_id": None}, None),
                       ({}, "not json"),
                       ({"legislation_id": "ssi/2020/1"}, object())):
        record_enabling_power([], "get_legislation_text", args, data)
    record_enabling_power(None, "get_legislation_text", {"legislation_id": "ssi/1/1"}, {})


# --- the lawyer-facing seam ---------------------------------------------------

def _footer(*pairs):
    return answer_scope_footer(_log_with(*pairs), {})


def test_a_section_search_records_the_instrument_but_never_states_a_power():
    """The preamble is not a ranked provision, so this route can only ever
    establish that the instrument was looked at.

    It is nonetheless the route that matters: over the replay corpus the Worker
    called `search_legislation_sections` 628 times against 32
    `get_legislation_text` calls, so recording only the latter would leave the
    report block and the footer silent on almost every turn where a derivation
    claim can arise."""
    log = []
    record_enabling_power(log, "search_legislation_sections",
                          {"legislation_id": "ssi/2018/273"},
                          {"results": [{"provision": "reg 1"}], "returned": 1})
    assert log == [{"tool": "enabling_power", "legislation_id": "ssi/2018/273",
                    "stated": False}]
    # And a tool that touches no single instrument records nothing.
    log2 = []
    record_enabling_power(log2, "search_legislation", {"query": "q"}, {"results": []})
    assert log2 == []


def test_the_footer_says_the_derivation_is_unverified_when_it_is():
    line = _footer(("ssi/2018/273", False))
    assert "does not record which enabling power" in line
    assert "unverified" in line


def test_the_footer_names_the_instrument_where_the_preamble_gave_it():
    line = _footer(("uksi/1979/766", True))
    assert "uksi/1979/766" in line
    assert "for anything else mentioned above the derivation is unverified" in line
    assert "applied only to" in line


def test_a_turn_that_retrieved_no_instrument_gets_no_enabling_clause():
    """Gated on a STRUCTURAL fact, not on a prose detector deciding whether the
    answer contains a derivation claim. A prose detector in the product fails
    silently — an unrecognised phrasing means no disclosure and no signal."""
    log = [{"tool": "search_legislation", "query": "commencement", "shown": 5,
            "matched": 141}]
    line = answer_scope_footer(log, {})
    assert line and "enabling power" not in line


def test_footer_trips_no_detector():
    """**P2.2's twelfth instrument error, pre-empted.**

    P2.2's own footer said "anything reported above as not found was not found
    in this index", which trips `NEG_ASSERTED` — so selecting the denominator on
    the full answer enrolled every researched turn and crushed the model column
    from 52% to 14%. A product change corrupting the instrument measuring it.

    This clause uses the words "made under" and "enabling power", so it is
    checked against BOTH detectors that read these answers.

    Graded on the CLAUSE, not on the whole footer: P2.2's half of the footer
    trips `NEG_ASSERTED` by design and by record, which is exactly why
    `_without_footer` exists. The first assertion is that the strip covers the
    lengthened footer; the rest are that this row adds no new trip of its own.

    **P2.5's clause is checked here too**, which makes this four rows' worth,
    and it is the one with the most exposure: it contains the words "in force"
    and is read by a detector built to find exactly those. Its own
    both-directions validation is in `test_in_force_status.py`; this is the
    cross-check against the three detectors the other rows own.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.utils.search_scope import (
        _currency_footer_clause, _enabling_footer_clause, record_currency,
    )
    from tools.replay_report import NEG_ASSERTED, derivation_claims, _without_footer

    for pair in (("ssi/2018/273", False), ("uksi/1979/766", True)):
        answer = "The Act commenced on 1 April 2025." + _footer(pair)
        # The footer is stripped whole, so neither detector ever sees it.
        assert _without_footer(answer).strip() == "The Act commenced on 1 April 2025."
        clause = _enabling_footer_clause(_log_with(pair))
        assert clause
        assert not NEG_ASSERTED.search(clause)
        assert derivation_claims(clause)[0] == []

    # P2.5, both branches of its clause.
    empty_log = []
    record_currency(empty_log, "search_legislation", {}, {"results": [
        {"legislation_id": "ukpga/1967/81",
         "title": "Companies Act 1967 (repealed)"}]})
    sourced_log = []
    record_currency(sourced_log, "get_legislation_changes",
                    {"legislation_id": "asp/2025/2"},
                    {"legislation_id": "asp/2025/2", "provisions_commenced": 8,
                     "commencement_orders_of_amendments": 0,
                     "repeal_or_revocation_relations": 0})
    for log in (empty_log, sourced_log):
        clause = _currency_footer_clause(log)
        assert clause
        assert not NEG_ASSERTED.search(clause)
        assert derivation_claims(clause)[0] == []


def test_the_enabling_block_is_stripped_before_a_lawyer_sees_it():
    """The block is an instruction to an agent. In research mode the Manager is
    told to pass a Worker's report through verbatim, so without an
    unconditional strip the bookkeeping renders on screen."""
    note = enabling_power_note({"legislation_id": "uksi/1979/766"},
                               _text_result(description=_REAL_RECITAL))
    out, n = strip_scope_blocks("Here is the answer." + note)
    assert n == 1
    assert out == "Here is the answer."
    assert "ENABLING POWER" not in out


def test_a_recital_containing_brackets_still_strips_cleanly():
    r"""The strip matches `\[ENABLING POWER[^\[\]]*\]`, so a bracket inside the
    quoted preamble would end the match early and leave agent-facing text in
    front of a lawyer. The quote is rewritten to keep it balanced."""
    note = enabling_power_note(
        {"legislation_id": "uksi/1979/766"},
        _text_result(description="In exercise of the powers conferred by "
                                 "section 75 [as amended] of the 1962 Act"))
    out, n = strip_scope_blocks("Answer." + note)
    assert n == 1 and out == "Answer."


# --- the wiring: the block must reach the model, the clause must reach the page

@pytest.mark.asyncio
async def test_the_enabling_block_reaches_what_the_worker_actually_receives(monkeypatch):
    """Asserted on the string `run_worker_tool` returns, not on the builder.

    It is computed from the RAW result and appended AFTER summarisation for the
    same reason `provision_url_block` is: the preamble lives in
    `legislation.description`, a large instrument gets summarised, and the
    summariser drops it. Compute it downstream and the evidence has gone.
    """
    from src.agent import agent_shared

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        async def fake_exec(name, args, on_chunk=None, timing_collector=None):
            return json.dumps(_text_result(description=_REAL_RECITAL))

        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        out = await agent_shared.run_worker_tool(
            "get_legislation_text", {"legislation_id": "uksi/1979/766"}, "q", None, "m",
        )
        assert "[ENABLING POWER" in out
        assert "sections 75(c) and 144(5)" in out
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_an_instrument_with_no_preamble_gets_the_prohibition(monkeypatch):
    from src.agent import agent_shared

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})
    try:
        async def fake_exec(name, args, on_chunk=None, timing_collector=None):
            return json.dumps(_text_result(description=_NOT_A_RECITAL))

        monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
        out = await agent_shared.run_worker_tool(
            "get_legislation_text", {"legislation_id": "ssi/2020/295"}, "q", None, "m",
        )
        assert "does NOT state" in out
        assert "could not be verified" in out
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_whole_seam_end_to_end(monkeypatch):
    """Worker retrieves an instrument with no preamble; the Manager's answer
    carries the lawyer-facing clause and none of the agent-facing bookkeeping.

    This is the seam P2.2's first acceptance run found open: the Worker sees
    tool results, the Manager sees only the report, so a fix at the tool
    boundary never reaches the agent that writes the claim.
    """
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({"_provider": "openrouter", "model": "test-model"})

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        if name == "search_legislation":
            return json.dumps(_search_result())
        return json.dumps(_text_result(description=_NOT_A_RECITAL))

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None):
        await executor("search_legislation", {"query": "social security"})
        await executor("get_legislation_text", {"legislation_id": "ssi/2018/273"})
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** SSI 2018/273 was made under s.95.\n"
            "2. **References:** ssi/2018/273")}

    async def worker(*a, **kw):
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0,
        )

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        report = await tool_executor("delegate_research", {"query": "q"})
        # The Manager passes the Worker's report through, as it is told to in
        # research mode — so whatever the report carries must be stripped here.
        return {"role": "assistant", "content": report}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        final = await process_user_request(
            manager, worker, [{"role": "user", "content": "q"}],
            "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})

    content = final["content"]
    # The lawyer gets the disclosure …
    assert "the derivation is unverified" in content or "is unverified" in content
    # … and none of the agent-facing blocks.
    assert "ENABLING POWER" not in content
    assert "SEARCH SCOPE" not in content
    assert "Enabling power: NOT retrieved" not in content


def test_the_footer_never_renders_an_unbalanced_quote():
    """Found by P2.3's acceptance sweep, in front of a lawyer.

    `.strip('"')` removes only the OUTER quotes, so the model's own
    field-syntax query rendered as `"Education (Scotland) Act 1962" 117"` —
    unbalanced, and reading as two searches where there was one. Phrase-search
    quoting is deliberately dropped: this line is provenance prose and the exact
    queries live in the audit trace.
    """
    log = [{"tool": "search_legislation",
            "query": '"Education (Scotland) Act 1962" 117', "shown": 5,
            "matched": 141},
           {"tool": "search_legislation",
            "query": '"Social Security (Scotland) Act 2018" "95" "£"',
            "shown": 5, "matched": 141}]
    line = answer_scope_footer(log, {})
    quoted = line[line.index("searched for"):line.index("; ")]
    assert quoted.count('"') % 2 == 0, quoted
    assert '""' not in line
    assert "Education (Scotland) Act 1962 117" in line


# --- the footer the model copies back (P2.2 defect, found during P3.5) ---------

def test_an_echoed_footer_is_removed_before_a_fresh_one_is_appended():
    """**Found live in P3.5's smoke run, and it is P2.2's defect.**

    The footer is prose addressed to the lawyer, so `strip_scope_blocks` leaves
    it alone — correctly. It then travels into the next turn's conversation
    history, the model reproduces it verbatim at the end of its answer, and the
    code appends its own. The lawyer reads the same disclosure twice, which is
    how a disclosure stops being read. Visible in `wave2_p22_final` as well as
    in the P3.5 smoke run, so it predates this row.
    """
    from src.utils.search_scope import strip_answer_footer

    log = [{"tool": "search_legislation", "query": "Care Reform", "shown": 5,
            "matched": 141, "legislation_id": ""}]
    footer = answer_scope_footer(log, {})
    answer = "Yes, SSI 2025/388 has been made." + footer
    assert strip_answer_footer(answer) == "Yes, SSI 2025/388 has been made."
    # Two of them, which is what actually reached the screen.
    assert strip_answer_footer(answer + footer) == "Yes, SSI 2025/388 has been made."
    # And appending after the strip leaves exactly one.
    assert (strip_answer_footer(answer) + footer).count("*Search scope:") == 1


def test_the_strip_leaves_an_answer_without_a_footer_alone():
    from src.utils.search_scope import strip_answer_footer

    for text in ("", "A plain answer.", "An answer with *emphasis* in it.",
                 "A line.\n\n*Not a search scope line at all.*"):
        assert strip_answer_footer(text) == (text.rstrip() if text else text)


def test_the_strip_cannot_eat_answer_text_that_follows_a_copied_footer():
    """A dot-all run from the first `*Search scope:` to the end of the string
    would delete whatever came after it. Matched line by line instead, because
    the footer is a single line and the risk is not worth the brevity."""
    from src.utils.search_scope import strip_answer_footer

    log = [{"tool": "search_legislation", "query": "q", "shown": 1,
            "matched": 2, "legislation_id": ""}]
    text = "Answer." + answer_scope_footer(log, {}) + "\n\nA later paragraph."
    assert strip_answer_footer(text) == text


# ---------------------------------------------------------------------------
# P2.9 (B5) — a memo-served search must still enter its own run's record
# ---------------------------------------------------------------------------
#
# `search_log` is per-WORKER-RUN; the tool memo is per-REQUEST. So when a Deep
# Research step repeats a search an earlier step already made, the second step
# was served from the memo and that query never entered its own record — absent
# from `worker_scope_block` (what the agent writing the negative is told was
# searched) and from `answer_scope_footer` (what the lawyer is told).
#
# Measured before the fix with `replay_report scoperecord`, over the six replay
# directories that have a scope block: 277 of 1,189 `search_legislation` calls
# (23%) missing, in 86 of 259 worker runs (33%), 11 of which recorded no search
# at all; and `issued - recorded == memo hits` **exactly, per run, with no
# exceptions across all six** — which is what identifies the memo as the sole
# cause rather than one cause among several.

from unittest.mock import AsyncMock, patch  # noqa: E402

from src.agent.agent_shared import run_worker_tool  # noqa: E402

_SEARCH_ARGS = {"query": "Scotland Act 1998"}


async def _p29_chunk(*a, **k):
    return None


def _p29_call(tool_memo, search_log, name="search_legislation", args=None):
    return run_worker_tool(
        name, dict(args if args is not None else _SEARCH_ARGS), "brief",
        _p29_chunk, "test-model",
        tool_memo=tool_memo,
        search_log=search_log,
    )


@pytest.mark.asyncio
async def test_a_memo_served_search_lands_in_the_reusing_runs_record():
    """The row's acceptance. Two worker runs in one request, each with its own
    per-run log; the second is served from the shared memo and must still
    record the query as its own."""
    memo = {}
    log_step1, log_step2 = [], []
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=json.dumps(_search_result())),
    ) as mock_exec:
        await _p29_call(memo, log_step1)
        await _p29_call(memo, log_step2)

    assert mock_exec.await_count == 1                      # still served from memo
    searches = [e for e in log_step2 if e["tool"] == "search_legislation"]
    assert len(searches) == 1
    assert searches[0]["query"] == "Scotland Act 1998"
    # And the counts come off the stored RAW result, not a placeholder.
    assert searches[0]["shown"] == 5
    assert searches[0]["matched"] == 141


@pytest.mark.asyncio
async def test_the_block_no_longer_demands_terms_it_has_withheld():
    """6374 rep 1 turn 2 is the measured case, and it is worse than a short
    count. That step's ONLY search was a memo hit, so its block carried no
    "Searched the legislation index" line at all — while still instructing the
    agent that a negative "MUST quote the search terms above". There were none
    above. The disclosure contradicted itself."""
    memo = {}
    log_step1, log_step2 = [], []
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=json.dumps(_search_result())),
    ):
        await _p29_call(memo, log_step1)
        await _p29_call(memo, log_step2)

    block = worker_scope_block(log_step2)
    assert "MUST quote the search terms above" in block
    assert "Searched the legislation index 1 time(s)" in block
    assert '"Scotland Act 1998"' in block


@pytest.mark.asyncio
async def test_a_memo_hit_on_a_non_search_tool_records_no_search():
    """`record_search` does not self-gate on the tool name — both call sites on
    the non-memo path do it, and so must this one. Without the gate every
    memoised retrieval would be logged as a search of the index, inflating the
    very count this row exists to correct."""
    memo = {}
    log1, log2 = [], []
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=json.dumps({"legislation": {}, "full_text": "x"})),
    ):
        args = {"legislation_id": "ukpga/1998/46"}
        await _p29_call(memo, log1, name="get_legislation_text", args=args)
        await _p29_call(memo, log2, name="get_legislation_text", args=args)

    assert [e for e in log2 if e["tool"] == "search_legislation"] == []
    assert worker_scope_block(log2).count("Searched the legislation index") == 0


@pytest.mark.asyncio
async def test_section_searches_are_recorded_on_the_memo_path_too():
    """The non-memo path records both search tools; parity means both here."""
    memo = {}
    log1, log2 = [], []
    sections = json.dumps({"title": "t", "url": "u", "sections": []})
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=sections),
    ):
        args = {"legislation_id": "ukpga/1998/46", "query": "commencement"}
        await _p29_call(memo, log1, name="search_legislation_sections", args=args)
        await _p29_call(memo, log2, name="search_legislation_sections", args=args)

    secs = [e for e in log2 if e["tool"] == "search_legislation_sections"]
    assert len(secs) == 1
    assert secs[0]["legislation_id"] == "ukpga/1998/46"
    assert "ukpga/1998/46" in worker_scope_block(log2)


@pytest.mark.asyncio
async def test_a_run_with_no_memo_is_unchanged():
    """The non-memo path must record exactly once, not twice — the fix adds a
    third `record_search` call site and a double-count would overstate the
    footer in the opposite direction."""
    log = []
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=json.dumps(_search_result())),
    ):
        await _p29_call(None, log)
    assert len([e for e in log if e["tool"] == "search_legislation"]) == 1


# ---------------------------------------------------------------------------
# P2.8 (B5), with P2.10 folded in: a negative carried forward from an earlier turn
# ---------------------------------------------------------------------------
#
# `answer_scope_footer` is per TURN. A follow-up the Manager answers from the
# history runs no search, so it got no footer, even when it restated an earlier
# turn's negative. Measured with `NEG_ASSERTED` over the ten replay
# directories: four turns (`wave2_p22_final/6409 r1 t11`, `r3 t4`;
# `wave2_p25/6341 r2 t2`, `r3 t2`). They are the only `queries = 0` FAIL rows
# that `replay_report negatives` prints.

from src.utils.search_scope import (  # noqa: E402
    _earlier_footers,
    _lawyer_filters_phrase,
    carried_scope_footer,
    strip_answer_footer,
)

_P28_LOG = [
    {"tool": "search_legislation", "query": "SSI 2025/377", "legislation_id": "",
     "shown": 5, "matched": 141},
    {"tool": "search_legislation", "legislation_id": "", "shown": 5, "matched": 141,
     "query": "Social Security (Amendment) (Scotland) Act 2025 (Commencement No. 2) "
              "Regulations 2025"},
    {"tool": "search_legislation", "query": "commencement regulations",
     "legislation_id": "", "shown": 5, "matched": 141},
]
_P28_NEGATIVE = "SSI 2025/377 is not currently available in the legislation database."


def _p28_search(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


def _p28_history(*footers, answer=_P28_NEGATIVE):
    """A conversation whose assistant turns end in the given footers, followed
    by the user's next question."""
    msgs = []
    for i, footer in enumerate(footers):
        msgs.append({"role": "user", "content": f"question {i}"})
        msgs.append({"role": "assistant", "content": answer + footer})
    msgs.append({"role": "user", "content": "follow-up"})
    return msgs


def _p28_rr():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import tools.replay_report as rr
    return rr


def test_a_reply_that_searched_nothing_restates_the_earlier_scope():
    """The row's acceptance, deterministically. 6341 rep 2 turn 2 wrote *"the
    initial search already checked the available database and found no case
    law results"* and got nothing beside it."""
    fresh = answer_scope_footer(_P28_LOG, {"_jurisdiction": "scotland"})
    line = carried_scope_footer(_p28_history(fresh), [])
    assert line.startswith("\n\n*Search scope: ")
    assert line.endswith("*")
    assert "\n" not in line.strip()
    assert "no search of the legislation index was run for this reply" in line
    assert "Earlier in this conversation it was searched for" in line
    assert '"SSI 2025/377"' in line
    assert "(1 further query not listed)" in line
    assert "filters in force: jurisdiction = scotland" in line
    assert "ranked search" in line
    assert "not the same as being absent from the law" in line


def test_the_carried_line_never_describes_a_search_this_reply_ran():
    """The row's hard constraint: no turn may carry a scope statement describing
    a search it did not run. So the line says first that this reply searched
    nothing, labels every term as earlier, and claims no dependency.

    **Hazard 1, `wave1/6341 r1 t8`.** That turn answered "what is a stub" from
    training knowledge. The gate is structural, so this line fires there too.
    It is not a false attribution, because the line does not say the reply drew
    on those searches. It tells the lawyer that nothing was looked up for this
    answer, which is true and worth knowing. The not-found clause is scoped to
    "those searches", so a negative the model produced from memory gains no
    index authority from it."""
    line = carried_scope_footer(
        _p28_history(answer_scope_footer(_P28_LOG, {})), [])
    before_terms = line.split('"')[0]
    assert "no search of the legislation index was run for this reply" in before_terms
    assert "Earlier in this conversation" in before_terms
    for claim in ("based on", "rests on", "relies on", "drawn from",
                  "was searched for this reply", "this reply searched"):
        assert claim not in line
    assert "a result reported as not found in those searches" in line


@pytest.mark.parametrize("messages", [
    None,
    [],
    [{"role": "user", "content": "q"}],
    [{"role": "user", "content": "q"},
     {"role": "assistant", "content": "A plain answer with no footer."},
     {"role": "user", "content": "q2"}],
])
def test_no_searched_turn_in_the_history_means_no_carried_line(messages):
    assert carried_scope_footer(messages, []) == ""


def test_a_footer_outside_an_assistant_reply_is_not_read_as_a_search():
    """A lawyer pasting an old answer into their own message has not run a
    search in this conversation."""
    fresh = answer_scope_footer(_P28_LOG, {})
    for role in ("user", "system", "tool"):
        messages = [{"role": role, "content": "You said: x" + fresh},
                    {"role": "user", "content": "and?"}]
        assert carried_scope_footer(messages, []) == ""


@pytest.mark.parametrize("tool", ["search_legislation", "search_legislation_sections"])
def test_a_turn_that_searched_gets_no_carried_line(tool):
    """A turn that ran a search is P2.2's, and the fresh footer is unchanged.
    **Both** search tools count. A turn that searched only within an instrument
    gets no fresh footer, but "no search was run for this reply" would be false
    there, so it stays silent."""
    fresh = answer_scope_footer(_P28_LOG, {})
    searched = [{"tool": tool, "query": "q", "legislation_id": "asp/2025/2"}]
    assert carried_scope_footer(_p28_history(fresh), searched) == ""


def test_the_next_turn_neither_stacks_nor_chains():
    """Turn 1 searched, turns 2 and 3 did not. Turn 3's history holds turn 1's
    fresh footer AND turn 2's carried line. A carried line is never read as a
    search, so turn 3 restates turn 1 exactly once and nothing compounds."""
    fresh = answer_scope_footer(_P28_LOG, {})
    turn2 = carried_scope_footer(_p28_history(fresh), [])
    turn3 = carried_scope_footer(_p28_history(fresh, turn2), [])
    assert turn2
    assert turn3 == turn2
    assert turn3.count("*Search scope:") == 1
    # The model copying turn 2's line back is removed before turn 3's goes on.
    echoed = "As noted earlier, it was not found." + turn2
    assert strip_answer_footer(echoed) == "As noted earlier, it was not found."
    assert (strip_answer_footer(echoed) + turn3).count("*Search scope:") == 1
    # A carried line with no fresh footer behind it is not a source of searches.
    assert carried_scope_footer(_p28_history(turn2), []) == ""


@pytest.mark.parametrize("log,cfg", [
    (_p28_search("q"), {}),
    (_P28_LOG, {"_jurisdiction": "scotland", "_legislation_type": "ssi",
                "_year_from": 2020}),
    (_p28_search(*[f"q{i}" for i in range(9)]), {"_year_to": 2010}),
    (_p28_search('"Education (Scotland) Act 1962" 117'), {}),
    (_log_with(("ssi/2018/273", False)), {}),
])
def test_every_fresh_footer_shape_is_read_back_exactly(log, cfg):
    """`_FRESH_FOOTER` is coupled to `answer_scope_footer`'s f-string. If the
    wording changes and this fails, fix the parse. In production a parse miss
    fails silent (no carried line), so this test is the only place a miss
    shows up."""
    fresh = answer_scope_footer(log, cfg)
    parsed = _earlier_footers(_p28_history(fresh))
    assert len(parsed) == 1
    got = parsed[0]
    head = fresh[: fresh.index("; ")]
    assert got["terms"] == re.findall(r'"([^"]*)"', head)
    assert got["terms"]
    m = re.search(r"\((\d+) further quer", head)
    assert got["rest"] == (int(m.group(1)) if m else 0)
    assert got["filters"] == _lawyer_filters_phrase(cfg)


def test_several_earlier_searches_are_combined_newest_first():
    older = answer_scope_footer(_p28_search("older search"), {"_jurisdiction": "scotland"})
    newer = answer_scope_footer(_p28_search("newer search", "Older Search"), {})
    line = carried_scope_footer(_p28_history(older, newer), [])
    assert line.index('"newer search"') < line.index('"Older Search"')
    assert line.count('"') == 4                  # deduped across turns
    assert "further quer" not in line
    # Different filters on different replies are not merged into one claim.
    assert "the filters differed between those replies" in line

    # Same filters on every reply: stated inline. Every query is listed, so the
    # count is exact.
    third = answer_scope_footer(_p28_search("a third search"), {})
    line = carried_scope_footer(_p28_history(newer, third), [])
    assert "no jurisdiction, type or date filter narrowed it" in line
    assert "(1 further query not listed)" in line

    # An unlisted query on one reply may repeat a listed one on another, so no
    # number is invented.
    many = answer_scope_footer(_p28_search(*[f"q{i}" for i in range(4)]), {})
    line = carried_scope_footer(_p28_history(older, many), [])
    assert "(further queries not listed)" in line
    assert not re.search(r"\(\d+ further", line)


def test_the_carried_line_trips_no_detector_on_the_models_prose():
    """**Hazard 2, which is P2.2's Session 6 trap.** The line says "not found",
    so any shape `_without_footer` does not strip would enrol a purely positive
    turn as a negative and corrupt the number grading this row. It keeps the
    footer's shape, and this test asserts that the strip removes it whole."""
    rr = _p28_rr()
    from tools.replay_report import derivation_claims

    line = carried_scope_footer(
        _p28_history(answer_scope_footer(_P28_LOG, {})), [])
    positive = "Yes. SSI 2025/119 brought sections 2 and 9 into force."
    answer = positive + line
    assert rr._without_footer(answer) == positive
    assert not rr.NEG_ASSERTED.search(rr._without_footer(answer))
    assert derivation_claims(line)[0] == []
    assert not rr.IN_FORCE_CLAIM.search(line)
    assert not rr.HALT_PARAPHRASE.search(line)
    assert not rr.HALT_AS_TIMEOUT.search(line)
    assert not rr.NEG_BLAMED_USER.search(line)
    assert answer.count("*Search scope:") == 1


def test_a_restated_negative_is_qualified_by_construction():
    """What `replay_report negatives` grades, on 6341 rep 2 turn 2's own
    sentence. The turn is still enrolled, because enrolment reads the model's
    words. It now passes on the whole answer. It is not made to look like a
    positive: under Invariant 1 the negative stays."""
    rr = _p28_rr()
    fresh = answer_scope_footer(_p28_search("sale of goods case law"), {})
    restated = ("The initial search already checked the available database "
                "and found no case law results.")
    answer = restated + carried_scope_footer(_p28_history(fresh), [])
    bare = rr._without_footer(answer)
    assert bare == restated
    assert rr.NEG_ASSERTED.search(bare)
    assert rr._names_search_terms(answer)
    assert rr.NEG_BLAMED_INDEX.search(answer)
    assert rr.NEG_LIMITS.search(answer)
    assert not rr.NEG_BLAMED_USER.search(answer)


def test_a_retrieval_only_turn_keeps_its_own_clauses():
    """A turn that retrieved an instrument's text without searching gets no
    fresh footer, so P2.3's derivation clause never reached the lawyer. The
    carried line appends this turn's own clauses. They are gated on this turn's
    records, so they are true by construction."""
    fresh = answer_scope_footer(_P28_LOG, {})
    entries = [e for e in _log_with(("ssi/2018/273", False))
               if e["tool"] != "search_legislation"]
    line = carried_scope_footer(_p28_history(fresh), entries)
    assert "no search of the legislation index was run for this reply" in line
    assert "derivation given above is unverified" in line
    assert line.endswith("*")
    assert "\n" not in line.strip()


@pytest.mark.parametrize("messages,searches", [
    ([{"role": "assistant", "content": None}], []),
    ([{"role": "assistant", "content": [{"type": "text", "text": "x"}]}], []),
    (["not a dict", 3, None], []),
    (_p28_history(answer_scope_footer(_P28_LOG, {})), [None]),
    # The model-written variant P2.2's final sweep actually stored
    # (`wave2_p22_final/6409 r1 t2`), from before P3.5 stripped echoes.
    ([{"role": "assistant", "content": (
        "Answer.\n\n*Search scope: the legislation index was searched for the "
        "terms above with no jurisdiction or type filters applied (year range "
        "up to 2026).*")}], []),
])
def test_unreadable_history_is_silent_and_never_raises(messages, searches):
    assert carried_scope_footer(messages, searches) == ""


# --- P2.8 through the Manager seam ------------------------------------------

async def _p28_turn(monkeypatch, messages, manager, worker=None):
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        return json.dumps(_search_result())

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None):
        await executor("search_legislation", {"query": "this turn's own search"})
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Found.\n"
            "2. **References:** None.")}

    async def searching_worker(*a, **kw):
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0,
        )

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        return await process_user_request(
            manager, worker or searching_worker, messages,
            "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})


def _answers_from_history(text):
    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        return {"role": "assistant", "content": text}
    return manager


@pytest.mark.asyncio
async def test_a_follow_up_answered_from_history_reaches_the_lawyer_qualified(monkeypatch):
    """6409 rep 1 turn 11, end to end: no delegation, an earlier negative
    restated, and the qualification now sits beside it."""
    restated = ("As noted in the previous search, SSI 2025/377 is not currently "
                "available in the legislation database.")
    history = _p28_history(answer_scope_footer(_P28_LOG, {}))
    final = await _p28_turn(monkeypatch, history, _answers_from_history(restated))
    assert final["content"].startswith(restated)
    assert "no search of the legislation index was run for this reply" in final["content"]
    assert '"SSI 2025/377"' in final["content"]
    assert final["content"].count("*Search scope:") == 1
    assert final["content"].rstrip().endswith("absent from the law.*")


@pytest.mark.asyncio
async def test_a_first_turn_that_searched_nothing_is_untouched(monkeypatch):
    text = "Could you tell me which instrument you mean?"
    final = await _p28_turn(
        monkeypatch, [{"role": "user", "content": "q"}], _answers_from_history(text))
    assert final["content"] == text


@pytest.mark.asyncio
async def test_a_turn_that_searched_gets_only_its_own_footer(monkeypatch):
    """The earlier carried line is in the history and the model copies it back.
    This turn searched, so the lawyer gets this turn's fresh footer, exactly
    once, and nothing carried."""
    fresh = answer_scope_footer(_P28_LOG, {})
    carried = carried_scope_footer(_p28_history(fresh), [])
    history = _p28_history(fresh, carried)

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "It has been made." + carried}

    final = await _p28_turn(monkeypatch, history, manager)
    assert final["content"].count("*Search scope:") == 1
    assert '"this turn\'s own search"' not in final["content"]    # quotes are stripped
    assert '"this turn s own search"' in final["content"]
    assert "no search of the legislation index was run" not in final["content"]


@pytest.mark.asyncio
async def test_a_failed_delegation_carries_nothing(monkeypatch):
    """The worker raised, so its search record went with it. "No search was run
    for this reply" might be false, and the line stays silent."""
    async def failing_worker(*a, **kw):
        raise RuntimeError("provider stalled")

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "The research could not be completed."}

    history = _p28_history(answer_scope_footer(_P28_LOG, {}))
    final = await _p28_turn(monkeypatch, history, manager, worker=failing_worker)
    assert final["content"] == "The research could not be completed."


@pytest.mark.asyncio
async def test_a_peer_consult_carries_nothing(monkeypatch):
    """A consulted peer searches with its own tools, which this turn's record
    does not see."""
    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        await tool_executor("consult_peer", {"peer_id": "parliament_bot",
                                             "question": "q"})
        return {"role": "assistant", "content": "The Parliament Bot found no records."}

    history = _p28_history(answer_scope_footer(_P28_LOG, {}))
    final = await _p28_turn(monkeypatch, history, manager)
    assert final["content"] == "The Parliament Bot found no records."
