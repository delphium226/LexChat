"""FIX_PLAN P3.13 (B10): the conversational Manager drops a sibling subsection
its own Worker had written.

6348's lawyer: the answer *"did not initially elaborate on the full provision,
only referring to s36(1) and not s36(2)"*. After P3.11 the quick-lookup Worker
states s.36(2) in 3 of 3 turn-1 reports, and the conversational Manager
deleted it from 2 of those 3 answers. Every time, the sibling was the one
provision in the report written without a link — both subsections share the
section's URL — and the Manager's CITATION PRESERVATION rule protects each
provision "with its link".

Measured over every replayed run before building (Session 22, 35
directories): when the conversational answer kept one subsection of a section,
it kept a sibling it had been handed as a link 58 times in 60 and one handed
as plain text 70 in 104. So the fix has two halves, and these tests pin both:

1. **Code** (`link_sibling_pinpoints`, called by `worker_result_for_manager`):
   the sibling is linked to the section URL the same paragraph already
   carries, so it reaches the Manager as a citation. Never builds a URL; never
   links a pinpoint to a different instrument's section (Invariant 1: a real
   page for the wrong Act reads as a verified citation).
2. **A clause** in the existing CITATION PRESERVATION bullet, because the
   Manager also edits the sibling out as off-topic ("legal advice privilege"
   is s.36(1)), linked or not: on the seam, the link alone recovered 1 of the
   3 flattened payloads, the clause alone 2, both together 3, with links up
   (12 -> 15 over five payloads).
"""

import pytest

from src import prompts
from src.agent.agent_core import worker_result_for_manager
from src.utils.citation_links import link_sibling_pinpoints

S36 = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
S50 = "http://www.legislation.gov.uk/id/asp/2002/13/section/50"
DPA36 = "http://www.legislation.gov.uk/ukpga/2018/12/section/36"
RETRIEVED = {S36, S50}

# The three shapes the Worker wrote the sibling in, verbatim from the run files
# (wave3_p311_conv reps 1 and 2, wave0_conv_6348 rep 3).
PARENTHETICAL = (
    f"Under [s.36(1) of the Freedom of Information (Scotland) Act 2002]({S36}), "
    "information is exempt from disclosure if a claim to confidentiality of "
    "communications could be maintained in legal proceedings (while s.36(2) "
    "exempts information obtained from another person where disclosure would "
    "constitute an actionable breach of confidence)."
)
SENTENCE = (
    f"Under [s.36(1) of the Freedom of Information (Scotland) Act 2002]({S36}), "
    "information is exempt if a claim to confidentiality of communications "
    "could be maintained. A related exemption in s.36(2) applies to "
    "information obtained from another person."
)
REMAINDER = (
    f"Under [s.36(1)]({S36}) of the Freedom of Information (Scotland) Act 2002, "
    "information is exempt if a claim to confidentiality of communications "
    "could be maintained. The remainder of the section, s.36(2), provides a "
    "separate exemption for information obtained from a third party."
)


@pytest.mark.parametrize("report", [PARENTHETICAL, SENTENCE, REMAINDER])
def test_the_sibling_is_linked_to_the_section_the_report_already_links(report):
    out, n = link_sibling_pinpoints(report, RETRIEVED)
    assert n == 1
    assert f"[s.36(2)]({S36})" in out
    # Nothing else changed.
    assert out.replace(f"[s.36(2)]({S36})", "s.36(2)") == report


def test_it_is_idempotent():
    once, _ = link_sibling_pinpoints(PARENTHETICAL, RETRIEVED)
    twice, n = link_sibling_pinpoints(once, RETRIEVED)
    assert twice == once and n == 0


def test_a_bare_section_is_not_a_sibling():
    text = f"Under [s.36(1)]({S36}), information is exempt; see also s.36 generally."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_it_never_builds_a_url():
    """s.50(5) with no s.50 link in the paragraph stays plain text, even though
    the report holds a FOISA link and s.50's URL is predictable."""
    text = f"Under [s.36(1)]({S36}), information is exempt. And s.50(5) protects advice."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_the_link_must_be_in_the_same_paragraph():
    text = f"Under [s.36(1)]({S36}), information is exempt.\n\nSeparately, s.36(2) covers confidences."
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_two_urls_for_the_section_is_ambiguous_and_left_alone():
    text = (f"[FOISA s.36(1)]({S36}) and [DPA 2018 s.36(1)]({DPA36}) differ; "
            "s.36(2) is narrower.")
    assert link_sibling_pinpoints(text, RETRIEVED | {DPA36}) == (text, 0)


def test_a_pinpoint_of_another_named_instrument_is_not_given_this_ones_url():
    """The one wrong link the first draft made over the corpus (`wave2_p25`,
    6341): a list of Use Classes Orders, where the 1963 Order's s.2(2) was
    handed the 1950 Order's s.2 URL."""
    s2 = "http://www.legislation.gov.uk/id/si/1950/1131/section/2"
    text = (f"* [The Town and Country Planning (Use Classes) Order 1950 - s. 2]({s2})\n"
            "* **The Town and Country Planning (Use Classes) Order 1963 - s. 2(2)**")
    assert link_sibling_pinpoints(text, {s2}) == (text, 0)


def test_a_pinpoint_that_names_its_own_act_after_it_is_left_alone():
    text = (f"Under [s.36(1) of FOISA]({S36}), information is exempt, and "
            "s.36(2) of the Data Protection Act 2018 is different.")
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_a_title_written_straight_after_the_link_names_the_same_act():
    """"[s.36(1)](...) of the Freedom of Information (Scotland) Act 2002" —
    the plain title is the link's own Act, so it does not block the sibling
    (the REMAINDER shape above relies on this)."""
    out, n = link_sibling_pinpoints(REMAINDER, RETRIEVED)
    assert n == 1


def test_a_plain_title_between_link_and_pinpoint_blocks_it():
    text = (f"Under [s.36(1)]({S36}), information is exempt. The Data Protection "
            "Act 2018 also has rules, and s.36(2) is narrower.")
    assert link_sibling_pinpoints(text, RETRIEVED) == (text, 0)


def test_an_unretrieved_url_is_never_propagated():
    assert link_sibling_pinpoints(PARENTHETICAL, {S50}) == (PARENTHETICAL, 0)


def test_the_search_scope_block_is_never_touched():
    report = PARENTHETICAL + (
        "\n\n[SEARCH SCOPE — what this research step actually did]\n"
        f"Searched within [s.36(1)]({S36}); s.36(2) was in the results.\n[/SEARCH SCOPE]")
    out, n = link_sibling_pinpoints(report, RETRIEVED)
    assert n == 1
    assert out.split("\n\n[SEARCH SCOPE")[1] == report.split("\n\n[SEARCH SCOPE")[1]


def test_regulations_and_articles_are_linked_by_their_own_segment():
    reg = "http://www.legislation.gov.uk/id/uksi/2004/3391/regulation/12"
    text = f"[Regulation 12(4)(e)]({reg}) covers internal communications; regulation 12(8) defines them."
    out, n = link_sibling_pinpoints(text, {reg})
    assert n == 1 and f"[regulation 12(8)]({reg})" in out
    # A section pinpoint is never given a regulation URL.
    text = f"[Regulation 12(4)]({reg}) applies, and s.12(8) is elsewhere."
    assert link_sibling_pinpoints(text, {reg}) == (text, 0)


def test_a_schedule_url_is_never_a_section_url():
    sch = "http://www.legislation.gov.uk/id/asp/2002/13/schedule/1"
    text = f"[Schedule 1]({sch}) lists authorities; s.1(2) is general."
    assert link_sibling_pinpoints(text, {sch}) == (text, 0)


def test_it_is_fail_soft_on_nothing():
    assert link_sibling_pinpoints("", RETRIEVED) == ("", 0)
    assert link_sibling_pinpoints(None, RETRIEVED) == (None, 0)


# --- the seam: only the conversational Manager is handed the linked report ---


def test_the_conversational_manager_gets_the_linked_report():
    out = worker_result_for_manager(PARENTHETICAL, {"_chat_mode": "conversational"}, RETRIEVED)
    assert out.startswith("[Research Agent Result]\n")
    assert f"[s.36(2)]({S36})" in out


@pytest.mark.parametrize("mode", ["research", "deep_research", None])
def test_every_other_manager_gets_the_report_unchanged(mode):
    """The research Manager passes the report through (it kept 441 of 441
    pinpoints over the corpus, linked or not), so nothing it shows the lawyer
    changes."""
    out = worker_result_for_manager(PARENTHETICAL, {"_chat_mode": mode}, RETRIEVED)
    assert out == f"[Research Agent Result]\n{PARENTHETICAL}"


@pytest.fixture
def _conversational_cfg():
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_chat_mode": "conversational", "model": "test-model",
        "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


async def test_process_user_request_hands_the_manager_the_linked_report(_conversational_cfg):
    """Wired at the one place the Manager receives a worker report."""
    from src.agent.agent_core import process_user_request

    async def worker(query, model, cancel_event, num_ctx, on_chunk, **kw):
        # The real worker harvests every URL its tools returned into this set.
        kw["retrieved_urls"].update(RETRIEVED)
        return {"content": PARENTHETICAL, "sources": [], "searches": []}

    seen = {}

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        seen["result"] = await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "Answer."}

    await process_user_request(manager, worker, [{"role": "user", "content": "q"}],
                               "test-model", None, None, 0)
    assert f"[s.36(2)]({S36})" in seen["result"]


# --- the clause, and P2.4's constraint on how it may be added -----------------


def test_the_conversational_manager_keeps_what_the_worker_says_of_the_siblings():
    body = prompts._MANAGER_CONV_BODY
    rules = body.split("CRITICAL RULES:")[1].split("YOUR APPROACH:")[0]
    bullet = [ln for ln in rules.splitlines() if ln.startswith("- CITATION PRESERVATION")]
    assert len(bullet) == 1
    assert ("where the Worker says what a cited section's other subsections "
            "provide, keep that line too") in bullet[0]
    # A clause of the existing bullet, not a new one: P2.4 measured that more
    # structure in the conversational prompts moves output to bullets and costs
    # case-law links. Four CRITICAL RULES, as before.
    assert len([ln for ln in rules.splitlines() if ln.startswith("- ")]) == 4


def test_the_research_manager_is_unchanged():
    assert "other subsections provide" not in prompts._MANAGER_BODY
