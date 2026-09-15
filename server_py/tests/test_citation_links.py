"""P1.6 (bucket B14) — a provision URL no tool returned must never reach the answer.

The failure this pins is not a broken link. `.../asp/2000/1/section/21` resolves
whether or not the research ever retrieved section 21, so a manufactured
provision URL reads to a lawyer as a verified citation and no link-checker can
tell the difference. P1.4 stopped the *prompt* asking for it; these tests pin the
*code* that makes it impossible.

Two halves, tested in order:
  * `provision_url_block` — the cause. Summarisation keeps the section numbers
    and drops every URL, which is what leaves the model reconstructing one.
  * `enforce_provision_links` — the guarantee, at the seam where the answer is
    assembled.

Note the warning this suite was written under (SESSION_LOG Session 4):
`test_bad_link_*` stayed green for three sessions while its detector was wrong on
every real input, because it was built from synthetic labels no real corpus
produces. So the fixtures here use the **real** shape `_slim_section_results`
emits and the **real** URL spellings the two LEX endpoints return, including the
`/id/` form that only one of them uses.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.agent_core import run_worker_agent
from src.agent.provider_factory import set_request_provider_config
from src.utils.citation_links import (
    PROVISION_FOOTNOTE,
    PROVISION_MARKER,
    act_base_url,
    enforce_provision_links,
    harvest_legislation_urls,
    is_provision_url,
    normalise_leg_url,
    provision_url_block,
)

ACT = "http://www.legislation.gov.uk/asp/2000/1"
S21 = "http://www.legislation.gov.uk/id/asp/2000/1/section/21"
S22 = "http://www.legislation.gov.uk/id/asp/2000/1/section/22"


# ---------------------------------------------------------------------------
# URL identity — the four spellings of one resource
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spelling", [
    "http://www.legislation.gov.uk/asp/2000/1/section/21",
    "https://www.legislation.gov.uk/asp/2000/1/section/21",
    "http://legislation.gov.uk/asp/2000/1/section/21",
    "https://www.legislation.gov.uk/id/asp/2000/1/section/21",
    "https://www.legislation.gov.uk/id/asp/2000/1/section/21/",
    "https://www.legislation.gov.uk/asp/2000/1/section/21#para2",
])
def test_one_resource_has_one_key(spelling):
    """LEX returns `http://` and the `/id/` form; models emit `https://` without
    it. Treating those as different URLs would report a correctly-copied link as
    manufactured — the instrument failing, not the product."""
    assert normalise_leg_url(spelling) == "legislation.gov.uk/asp/2000/1/section/21"


def test_non_legislation_hosts_have_no_key():
    assert normalise_leg_url("https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671") == ""
    assert normalise_leg_url("https://www.parliament.scot/x/section/3") == ""
    assert normalise_leg_url("") == ""


def test_provision_urls_are_distinguished_from_act_urls():
    assert is_provision_url(S21) is True
    assert is_provision_url(ACT) is False
    assert act_base_url(S21) == "legislation.gov.uk/asp/2000/1"
    assert act_base_url(ACT) == ""


# ---------------------------------------------------------------------------
# The cause: summarisation eats the URLs, so they are handed back after it
# ---------------------------------------------------------------------------

SLIMMED_SECTIONS = json.dumps({
    "results": [
        {"legislation_id": "asp/2000/1", "provision_type": "section",
         "number": 21, "title": "Accounts", "url": S21, "text": "..."},
        {"legislation_id": "asp/2000/1", "provision_type": "section",
         "number": 22, "title": "Audit", "url": S22, "text": "..."},
    ],
    "returned": 2,
})


def test_provision_block_lists_the_urls_the_retrieval_returned():
    block = provision_url_block(SLIMMED_SECTIONS)
    assert S21 in block and S22 in block
    assert "section 21" in block and "section 22" in block
    # It must tell the model what to do with them, or it is just more context.
    assert "verbatim" in block.lower()


def test_provision_block_survives_the_phase_2_nudge_tail():
    """`run_worker_tool` appends the nudge after the JSON, so a plain
    `json.loads` raises "Extra data" on exactly the successful calls."""
    with_nudge = SLIMMED_SECTIONS + "\n\n[NEXT STEP: Call search_legislation_sections...]"
    assert S21 in provision_url_block(with_nudge)


@pytest.mark.parametrize("payload", [
    "not json at all",
    json.dumps({"results": []}),
    json.dumps({"results": [{"legislation_id": "asp/2000/1", "url": ACT}]}),  # Act only
    json.dumps({"error": "boom"}),
])
def test_provision_block_is_empty_when_there_is_nothing_to_hand_back(payload):
    """Appended unconditionally by the caller, so "nothing to say" must be ""."""
    assert provision_url_block(payload) == ""


def test_harvest_is_key_agnostic_and_recursive():
    """The two LEX endpoints spell the identifier `uri`, `id` and `url`. A
    harvest keyed on one of them would under-count and manufacture false
    positives downstream."""
    payload = json.dumps({
        "results": [{"uri": S21}, {"id": S22}, {"nested": {"url": ACT}}],
        "junk": [1, None, "no url here"],
    })
    assert harvest_legislation_urls(payload) == {
        normalise_leg_url(S21), normalise_leg_url(S22), normalise_leg_url(ACT),
    }


def test_harvest_of_unparseable_output_contributes_nothing():
    """Fail-soft: a harvest error must never raise into a research run."""
    assert harvest_legislation_urls("<html>503</html>") == set()
    assert harvest_legislation_urls(None) == set()


# ---------------------------------------------------------------------------
# The guarantee: enforcement at the answer seam
# ---------------------------------------------------------------------------

def test_a_retrieved_provision_link_is_left_alone_however_it_is_spelled():
    text = f"See [PFA Act 2000 - s.21](https://www.legislation.gov.uk/asp/2000/1/section/21)."
    out, demoted, unlinked = enforce_provision_links(text, {S21})
    assert out == text
    assert (demoted, unlinked) == (0, 0)


def test_an_unretrieved_provision_falls_back_to_the_act_when_the_act_was_retrieved():
    """The honest case. With only the Act in hand, linking the Act is CORRECT —
    what is wrong is the label reading as a verified provision citation. A
    strip-only fix would trade a bad link for a bad claim."""
    text = f"Under [PFA Act 2000 - s.21]({S21}) the accounts must be sent."
    out, demoted, unlinked = enforce_provision_links(text, {ACT})
    assert (demoted, unlinked) == (1, 0)
    assert S21 not in out
    assert "asp/2000/1" in out                    # still linked, to the Act
    assert f"s.21 {PROVISION_MARKER}" in out      # and marked
    assert PROVISION_FOOTNOTE in out


def test_an_unretrieved_provision_with_no_act_either_loses_its_link():
    """`CITATION PROTOCOL -> VALIDATION` already says "cite it in bold text
    rather than guessing a URL". This is enforcement making that true."""
    text = f"Under [PFA Act 2000 - s.21]({S21}) the accounts must be sent."
    out, demoted, unlinked = enforce_provision_links(text, set())
    assert (demoted, unlinked) == (0, 1)
    assert "](" not in out
    assert f"**PFA Act 2000 - s.21 {PROVISION_MARKER}**" in out
    assert PROVISION_FOOTNOTE in out


def test_the_disclosure_claims_only_what_is_known():
    """Invariant 1: a disclosure must be TRUE. We know no tool returned a URL for
    this citation. We do NOT know the provision went unread — a whole-Act
    `get_legislation_text` carries one URL for the Act and none for its sections —
    so the footnote must not say "not retrieved"."""
    assert "not retrieved" not in PROVISION_FOOTNOTE.lower()
    assert "url" in PROVISION_FOOTNOTE.lower()


def test_act_level_links_and_other_hosts_are_not_touched():
    """Scope discipline: a label naming a section against an Act-level URL is
    `bad_links`' question, and case law has its own identifier discipline."""
    text = (
        f"[PFA Act 2000 - s.21]({ACT}) and "
        "[R (Coulthard) v SSEFRA [2025] EWCA Civ 1671]"
        "(https://caselaw.nationalarchives.gov.uk/ewca/civ/2025/1671) and "
        "[Official Report](https://www.parliament.scot/x/section/3)"
    )
    out, demoted, unlinked = enforce_provision_links(text, set())
    assert out == text
    assert (demoted, unlinked) == (0, 0)


def test_the_footnote_appears_once_however_many_links_are_rewritten():
    text = f"[a - s.21]({S21}) [b - s.22]({S22}) [c - s.21 again]({S21})"
    out, demoted, unlinked = enforce_provision_links(text, {ACT})
    assert demoted == 3
    assert out.count(PROVISION_FOOTNOTE) == 1


def test_enforcement_is_idempotent():
    """It runs at the worker seam and again at the answer seam — a Manager that
    passes the report through verbatim must not have it marked twice."""
    text = f"Under [PFA Act 2000 - s.21]({S21})."
    once, _, _ = enforce_provision_links(text, {ACT})
    twice, demoted, unlinked = enforce_provision_links(once, {ACT})
    assert twice == once
    assert (demoted, unlinked) == (0, 0)


def test_no_retrieved_set_is_a_no_op():
    """Fail-soft: a caller that threads nothing keeps the previous behaviour
    exactly, rather than having every provision link stripped."""
    text = f"Under [PFA Act 2000 - s.21]({S21})."
    out, demoted, unlinked = enforce_provision_links(text, None)
    assert out == text
    assert (demoted, unlinked) == (0, 0)


# ---------------------------------------------------------------------------
# End-to-end through the worker: the row's stated acceptance
# ---------------------------------------------------------------------------

@pytest.fixture
def _worker_config():
    set_request_provider_config({
        "_research_mode": "legislation_only",
        "_tool_memo_enabled": False,
        "_local_prompt_cache_enabled": False,
    })
    yield
    set_request_provider_config({})


def _chat_loop_that_cites(report: str, tool_call: bool):
    """Stub chat_loop: optionally runs one tool call, then returns `report`."""
    calls = []

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        calls.append(messages)
        if tool_call and len(calls) == 1:
            await tool_executor(
                "search_legislation_sections",
                {"legislation_id": "asp/2000/1", "query": "accounts"},
            )
        return {"content": report}

    chat_loop.calls = calls
    return chat_loop


_REPORT = (
    "1. **Summary Answer (BLUF):** Accounts must be sent to the Auditor General.\n"
    f"2. **Detailed Analysis:** Under [PFA Act 2000 - s.21]({S21}) they must.\n"
    "3. **Jurisdiction & Status:** Scotland.\n"
    f"4. **References:**\n   - [PFA Act 2000 - s.21]({S21})\n"
)


def test_a_provision_url_a_tool_returned_reaches_the_answer(_worker_config):
    chat_loop = _chat_loop_that_cites(_REPORT, tool_call=True)
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=SLIMMED_SECTIONS),
    ):
        result = asyncio.run(run_worker_agent(
            chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        ))
    assert result["content"] == _REPORT


def test_a_provision_url_no_tool_returned_does_not(_worker_config):
    """The row's acceptance, stated as a unit test. Same report, same model
    behaviour — the only difference is that the research never retrieved s.21."""
    chat_loop = _chat_loop_that_cites(_REPORT, tool_call=True)
    act_only = json.dumps({"results": [
        {"legislation_id": "asp/2000/1", "title": "PFA Act 2000", "url": ACT},
    ]})
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=act_only),
    ):
        result = asyncio.run(run_worker_agent(
            chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        ))
    assert S21 not in result["content"]
    assert PROVISION_FOOTNOTE in result["content"]
    # Demoted, not deleted: the Act was retrieved, so linking it is correct.
    assert "asp/2000/1" in result["content"]


def test_the_retrieved_set_spans_the_whole_request_not_one_delegation(_worker_config):
    """A provision retrieved by delegation 1 is legitimately cited by
    delegation 2's report. A per-delegation set would flag that as manufactured —
    and Deep Research runs one worker per plan step."""
    shared: set = set()
    harvest_legislation_urls(SLIMMED_SECTIONS, into=shared)

    chat_loop = _chat_loop_that_cites(_REPORT, tool_call=False)
    result = asyncio.run(run_worker_agent(
        chat_loop, lambda *a, **k: None, "q", "test-model", None, 0,
        retrieved_urls=shared,
    ))
    assert result["content"] == _REPORT


@pytest.mark.asyncio
async def test_a_summarised_retrieval_still_hands_the_urls_to_the_model(_worker_config):
    """Half A, in situ. This is the mechanism the whole row turns on: a 32K
    section retrieval summarises to prose that names the sections and carries no
    URL at all (measured: 70% of section searches are summarised), which is what
    leaves the model rebuilding a link from the Act's base URI. The block is
    appended AFTER summarisation for the same reason the Phase-2 nudge is — the
    summariser cannot discard what it never saw."""
    from src.agent.agent_shared import run_worker_tool

    async def _noop_chunk(*a, **k):
        return None

    async def _fake_summarise(text, query, model, **kwargs):
        # A faithful stand-in for the real thing: section numbers kept, every
        # URL gone.
        return "Section 21 requires accounts. Section 22 provides for audit.", False

    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=SLIMMED_SECTIONS),
    ), patch(
        "src.agent.agent_shared.get_request_provider_config",
        return_value={"_research_mode": "legislation_only",
                      "_local_prompt_cache_enabled": False},
    ), patch(
        "src.agent.provider_factory.get_summarise_threshold", return_value=100
    ), patch(
        "src.agent.agent_shared.summarise_for_query", new=_fake_summarise
    ):
        retrieved: set = set()
        out = await run_worker_tool(
            "search_legislation_sections",
            {"legislation_id": "asp/2000/1", "query": "accounts"},
            "accounts", _noop_chunk, "test-model",
            retrieved_urls=retrieved,
        )

    assert "Section 21 requires accounts" in out      # the summary survived
    assert S21 in out and S22 in out                  # and so did the URLs
    # And provenance is recorded from the RAW result, not from what the model saw.
    assert normalise_leg_url(S21) in retrieved
