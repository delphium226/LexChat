"""P3.11 (B10 residual): one subsection cited without its siblings.

6348's lawyer: the answer *"did not initially elaborate on the full provision,
only referring to s36(1) and not s36(2)"*. P3.1's prompt rule moved that from
0 of 3 to 1 of 3. Measured over every stored 6348 run before this was built,
the section search returns s.36 with both subsections every time and the
summariser keeps s.36(2) in 1 of 11 summaries - the Worker cannot say what a
subsection provides when it was never shown it. So the fix is P1.6's pattern:
a code-built block appended AFTER summarisation, from the RAW result.

What this file pins:

1. the outline: every numbered subsection of a retrieved provision, with its
   opening words and its paragraphs folded in, labelled from the URL segment;
2. what it deliberately leaves out: Schedules (P3.12), single-body provisions,
   rows with no provision URL, old-form rows;
3. its bounds, and that it is empty when it has nothing to say;
4. the wiring: on the summarised path only, after P1.6's URL block and before
   P2.2's scope note; a local-cache hit and a memo hit still carry it; a
   whole-Act retrieval does not get one;
5. it is stripped from an answer whole, and a stray header with it;
6. its static text trips no detector and names no graded provision;
7. `summarised_result_blocks` is one definition the seam tool shares.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent.agent_shared import run_worker_tool, summarised_result_blocks  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.services import local_prompt_cache as lpc  # noqa: E402
from src.utils.citation_links import provision_url_block  # noqa: E402
from src.utils.search_scope import strip_scope_blocks  # noqa: E402
from src.utils.section_outline import (  # noqa: E402
    MAX_BLOCK_CHARS,
    MAX_SUBSECTION_CHARS,
    MAX_SUBSECTIONS_PER_PROVISION,
    OUTLINE_BLOCK_CLOSE,
    OUTLINE_BLOCK_OPEN,
    OUTLINE_HEADER,
    subsection_outline,
)

FOISA = "asp/2002/13"
ACT = "http://www.legislation.gov.uk/asp/2002/13"
S36 = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
S30 = "http://www.legislation.gov.uk/id/asp/2002/13/section/30"
S15 = "http://www.legislation.gov.uk/id/asp/2002/13/section/15"

# The real shape `_slim_section_results` emits (SESSION_LOG Session 4's warning:
# a fixture no real corpus produces proves nothing). These are the rows the
# 6348 fixture carries, verbatim, with LEX's own line and tab structure.
S36_TEXT = (
    "Section 36) **Confidentiality**\n\n"
    "1) Information in respect of which a claim to confidentiality of "
    "communications could be maintained in legal proceedings is exempt "
    "information. \n"
    "2) Information is exempt information if— \n"
    "\ta) it was obtained by a Scottish public authority from another person "
    "(including another such authority); and \n"
    "\tb) its disclosure by the authority so obtaining it to the public "
    "(otherwise than under this Act) would constitute a breach of confidence "
    "actionable by that person or any other person. "
)
S30_TEXT = (
    "Section 30) **Prejudice to effective conduct of public affairs**\n"
    "Information is exempt information if its disclosure under this Act— \n"
    "\ta) would, or would be likely to, prejudice substantially the maintenance "
    "of the convention of the collective responsibility of the Scottish "
    "Ministers; \n"
    "\tb) would, or would be likely to, inhibit substantially— \n"
    "\t\ti) the free and frank provision of advice; or \n"
    "\t\tii) the free and frank exchange of views for the purposes of "
    "deliberation; or \n"
    "\tc) would otherwise prejudice substantially, or be likely to prejudice "
    "substantially, the effective conduct of public affairs"
)
S15_TEXT = (
    "Section 15) **Duty to provide advice and assistance**\n\n"
    "1) A Scottish public authority must, so far as it is reasonable to expect "
    "it to do so, provide advice and assistance to a person who proposes to "
    "make, or has made, a request for information to it. \n"
    "2) A Scottish public authority which, in relation to the provision of "
    "advice or assistance in any case, conforms with the code of practice "
    "issued under section 60 is, as respects that case, to be taken to comply "
    "with the duty imposed by subsection (1). "
)


def _row(number, url, text, ptype="section", title="", legislation_id=FOISA):
    return {"legislation_id": legislation_id, "number": number,
            "provision_type": ptype, "text": text, "title": title, "url": url}


def _raw(*rows):
    return json.dumps({"results": list(rows), "returned": len(rows)})


ROW_36 = _row(36, S36, S36_TEXT, title="Confidentiality")
ROW_30 = _row(30, S30, S30_TEXT, title="Prejudice to effective conduct of public affairs")
ROW_15 = _row(15, S15, S15_TEXT, title="Duty to provide advice and assistance")
RAW_6348 = _raw(ROW_36, ROW_30, ROW_15)


# ---------------------------------------------------------------------------
# 1. the outline
# ---------------------------------------------------------------------------

def test_every_numbered_subsection_is_listed_with_its_opening_words():
    block = subsection_outline(RAW_6348)
    assert block.startswith("\n\n" + OUTLINE_BLOCK_OPEN)
    assert block.rstrip().endswith(OUTLINE_BLOCK_CLOSE)
    assert "- s.36 Confidentiality\n" in block
    assert "  (1) Information in respect of which a claim to confidentiality" in block
    assert "  (2) Information is exempt information if" in block


def test_paragraphs_are_folded_into_their_subsection_line_in_citation_form():
    """The point of the row: what s.36(2) PROVIDES is in its paragraphs, not in
    its lead-in ("Information is exempt information if-" says nothing)."""
    block = subsection_outline(RAW_6348)
    line = [ln for ln in block.split("\n") if ln.startswith("  (2) Information is exempt")][0]
    assert "(a) it was obtained by a Scottish public authority from another person" in line
    assert "(b) its disclosure by the authority" in line
    assert "actionable" in line
    assert "\ta)" not in line and "\n" not in line


def test_the_label_comes_from_the_url_segment_not_from_the_word_the_text_uses():
    """LEX renders a regulation's text as `Section 4)`. A label copied from the
    text would make the Worker write s.4(1) for reg. 4(1): a wrong pinpoint
    that reads as verified (P3.1's watch item)."""
    reg = _row(4, "http://www.legislation.gov.uk/id/ssi/2020/300/regulation/4",
               "Section 4) **Face coverings**\n\n1) A person must wear one. \n2) Unless exempt. ",
               legislation_id="ssi/2020/300")
    art = _row(2, "http://www.legislation.gov.uk/id/uksi/1999/1379/article/2",
               "Section 2) **Interpretation**\n\n1) In this Order. \n2) Unless the context. ",
               legislation_id="uksi/1999/1379")
    ins = _row(None, "http://www.legislation.gov.uk/id/asp/2009/12/section/A4",
               "Section A4) **Budget-setting regulations**\n\n1) The Ministers must. \n2) A budget may. ",
               legislation_id="asp/2009/12")
    block = subsection_outline(_raw(reg, art, ins))
    assert "- reg. 4 Face coverings" in block
    assert "- art. 2 Interpretation" in block
    assert "- s.A4 Budget-setting regulations" in block     # number None: URL and header agree
    assert "s.4 " not in block


def test_text_before_the_first_numbered_subsection_is_not_a_subsection():
    row = _row(5, "http://www.legislation.gov.uk/id/asp/2002/13/section/5",
               "Section 5) **Opening**\nAn opening body sentence.\n1) First. \n2) Second. ")
    block = subsection_outline(_raw(row))
    assert "  (1) First." in block and "  (2) Second." in block
    assert "opening body" not in block.lower()


def test_a_long_subsection_is_cut_at_a_word_and_marked():
    long = "1) " + " ".join(f"word{i}" for i in range(120)) + " \n2) Short. "
    row = _row(7, "http://www.legislation.gov.uk/id/asp/2002/13/section/7",
               "Section 7) **Long**\n\n" + long)
    line = [ln for ln in subsection_outline(_raw(row)).split("\n") if ln.startswith("  (1) ")][0]
    body = line[len("  (1) "):]
    assert body.endswith("…")
    assert len(body) <= MAX_SUBSECTION_CHARS + 1
    assert not body[:-1].endswith(" ") and "word" in body[:-1].split()[-1]


# ---------------------------------------------------------------------------
# 2. what it leaves out
# ---------------------------------------------------------------------------

def test_a_provision_with_fewer_than_two_subsections_has_no_sibling_to_lose():
    one = _row(9, "http://www.legislation.gov.uk/id/asp/2002/13/section/9",
               "Section 9) **One**\n\n1) The only subsection. ")
    block = subsection_outline(_raw(ROW_36, ROW_30, one))
    assert "s.36" in block
    assert "s.30" not in block and "s.9" not in block


def test_a_schedule_is_not_outlined():
    """LEX holds a Schedule as ONE provision whose `Section k)` lines are its
    paragraphs (P3.12). Numbering their sub-paragraphs as siblings of one
    another would be wrong, so a Schedule row is skipped whatever its text."""
    sch = _row(None, "http://www.legislation.gov.uk/ukpga/1986/45/schedule/ZA2",
               "SCHEDULE ZA2 Moratorium Section A18 \n\n"
               "Section 1) **Introductory**\nFor the purposes of section A18. \n\n"
               "Section 2) **Financial contracts**\n\n1) This paragraph applies. \n"
               "2) “Financial contract” means— \n\ta) a contract; \n",
               ptype="schedule", legislation_id="ukpga/1986/45")
    # Even with a section-style header, `provision_type` decides.
    sch2 = dict(sch, text="Section 1) **Introductory**\n\n1) One. \n2) Two. ")
    assert subsection_outline(_raw(sch)) == ""
    assert subsection_outline(_raw(sch2)) == ""
    assert "s.36" in subsection_outline(_raw(sch, ROW_36))


def test_a_row_without_a_provision_url_is_left_out():
    """The 1960s SIs: every row carries the instrument's own URL and `(1)`-style
    numbering. P1.6's rule - not a provision the model can cite - applies."""
    old = _row(1261, "http://www.legislation.gov.uk/id/uksi/1977/1261",
               "(1) The Interpretation Act 1889 shall apply.\n\n(2) In these Rules:—\n",
               legislation_id="uksi/1977/1261")
    act_url = _row(36, ACT, S36_TEXT)
    assert subsection_outline(_raw(old)) == ""
    assert subsection_outline(_raw(act_url)) == ""


@pytest.mark.parametrize("payload", [
    "not json at all",
    "",
    None,
    json.dumps({"results": []}),
    json.dumps({"results": "nope"}),
    json.dumps({"error": "boom"}),
    json.dumps({"legislation": {"title": "An Act", "url": ACT}, "full_text": S36_TEXT}),
    _raw(ROW_30),                                   # a single-body section
    _raw(_row(3, "http://www.legislation.gov.uk/id/uksi/2020/791/regulation/3",
              "Section 3) **Repealed**\n. . . . . . . . ")),
    _raw({"number": 36, "url": S36, "text": None}, "junk", 7),
])
def test_the_block_is_empty_when_there_is_nothing_to_say(payload):
    """Appended unconditionally by the caller, so "nothing to say" must be ""."""
    assert subsection_outline(payload) == ""


def test_the_block_survives_the_appended_tail():
    """`run_worker_tool` appends notes after the JSON; the outline is built
    from the raw result, but the same parser must not choke on a tail."""
    assert "s.36" in subsection_outline(RAW_6348 + "\n\n[SEARCH SCOPE — 3 provision(s)]")


# ---------------------------------------------------------------------------
# 3. bounds
# ---------------------------------------------------------------------------

def _many(number, n_subs, words=8):
    text = f"Section {number}) **Many**\n\n" + "".join(
        f"{i}) " + " ".join(f"w{i}x{j}" for j in range(words)) + ". \n"
        for i in range(1, n_subs + 1))
    return _row(number, f"http://www.legislation.gov.uk/id/asp/2002/13/section/{number}", text)


def test_a_provision_with_many_subsections_lists_the_first_ones_and_counts_the_rest():
    block = subsection_outline(_raw(_many(40, 20)))
    assert f"  ({MAX_SUBSECTIONS_PER_PROVISION}) " in block
    assert f"  ({MAX_SUBSECTIONS_PER_PROVISION + 1}) " not in block
    assert f"{20 - MAX_SUBSECTIONS_PER_PROVISION} more subsections" in block


def test_the_whole_block_is_bounded_and_says_what_it_left_out():
    rows = [_many(n, 12, words=40) for n in range(50, 62)]     # ~3K chars each
    block = subsection_outline(_raw(*rows))
    body = block[len("\n\n" + OUTLINE_HEADER):]
    assert len(body) <= MAX_BLOCK_CHARS + 200
    assert "- s.50 Many" in block                              # rank order kept
    assert "further provisions with numbered subsections, omitted here for length" in block
    # The first provision is always outlined, however long it is.
    assert "- s.99 Many" in subsection_outline(_raw(_many(99, 12, words=400)))


# ---------------------------------------------------------------------------
# 4. the wiring
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


async def _noop_chunk(*a, **k):
    return None


async def _fake_summarise(text, query, model, **kwargs):
    # A faithful stand-in for what was measured: the summary names the cited
    # subsection and drops its sibling.
    return "Section 36(1) exempts privileged communications.", False


def _run(name, args, raw, threshold, cache_on=False, **kw):
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=raw)) as ex, \
         patch("src.agent.agent_shared.get_request_provider_config",
               return_value={"_research_mode": "legislation_only",
                             "_local_prompt_cache_enabled": cache_on}), \
         patch("src.agent.provider_factory.get_summarise_threshold",
               return_value=threshold), \
         patch("src.agent.agent_shared.summarise_for_query", new=_fake_summarise):
        out = asyncio.run(run_worker_tool(
            name, args, "legal advice privilege", _noop_chunk, "test-model", **kw))
    return out, ex


SECTION_ARGS = {"legislation_id": FOISA, "query": "legal advice privilege"}


def test_a_summarised_section_search_gets_the_outline_after_the_urls_and_before_the_scope_note(_worker_config):
    out, _ = _run("search_legislation_sections", SECTION_ARGS, RAW_6348, threshold=100)
    assert out.startswith("Section 36(1) exempts privileged communications.")
    assert "(2) Information is exempt information if" in out
    assert out.index("[CITATION URLS") < out.index(OUTLINE_BLOCK_OPEN) < out.index("[SEARCH SCOPE")
    assert out.count(OUTLINE_BLOCK_OPEN) == 1


def test_an_unsummarised_section_search_gets_no_outline(_worker_config):
    """The full text is in front of the model already; restating it would be
    context spent on nothing measured (P1.6's reasoning for its own block)."""
    out, _ = _run("search_legislation_sections", SECTION_ARGS, RAW_6348, threshold=10 ** 9)
    assert "Section 36) **Confidentiality**" in out           # the raw text, as JSON
    assert OUTLINE_BLOCK_OPEN not in out and "[CITATION URLS" not in out


def test_a_local_cache_hit_still_gets_the_outline(_worker_config):
    """The cache stores the summary alone (D7); the blocks are appended outside
    it, so the second lawyer's Worker sees the siblings too."""
    with patch.object(lpc, "lookup", new=AsyncMock(return_value={
            "summary": "Cached: s.36(1) only.", "chars_in": 3000})):
        out, _ = _run("search_legislation_sections", SECTION_ARGS, RAW_6348,
                      threshold=100, cache_on=True)
    assert out.startswith("Cached: s.36(1) only.")
    assert OUTLINE_BLOCK_OPEN in out and "[CITATION URLS" in out


def test_a_memo_hit_returns_the_outline_with_the_result(_worker_config):
    memo: dict = {}
    first, ex = _run("search_legislation_sections", SECTION_ARGS, RAW_6348,
                     threshold=100, tool_memo=memo)
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=RAW_6348)) as ex2, \
         patch("src.agent.agent_shared.get_request_provider_config",
               return_value={"_research_mode": "legislation_only",
                             "_local_prompt_cache_enabled": False}):
        second = asyncio.run(run_worker_tool(
            "search_legislation_sections", SECTION_ARGS, "q", _noop_chunk,
            "test-model", tool_memo=memo))
    assert ex.await_count == 1 and ex2.await_count == 0
    assert second == first and OUTLINE_BLOCK_OPEN in second


def test_a_whole_act_retrieval_gets_no_outline(_worker_config):
    whole = json.dumps({"legislation": {"title": "FOISA", "url": ACT},
                        "full_text": S36_TEXT + "\n" + S15_TEXT})
    out, _ = _run("get_legislation_text", {"legislation_id": FOISA}, whole, threshold=100)
    assert OUTLINE_BLOCK_OPEN not in out


def test_the_shared_helper_is_the_products_own_composition():
    """One definition, used by `run_worker_tool` and by `seam_replay --from-raw`."""
    assert summarised_result_blocks("search_legislation_sections", RAW_6348) == (
        provision_url_block(RAW_6348) + subsection_outline(RAW_6348))
    assert summarised_result_blocks("get_legislation_text", RAW_6348) == provision_url_block(RAW_6348)
    assert summarised_result_blocks("search_legislation_sections", "not json") == ""


# ---------------------------------------------------------------------------
# 5. stripped from an answer
# ---------------------------------------------------------------------------

def test_the_block_is_stripped_from_an_answer_whole():
    block = subsection_outline(RAW_6348)
    text = "The report.\n" + block + "\n\nMore report."
    out, n = strip_scope_blocks(text)
    assert n == 1
    assert OUTLINE_BLOCK_OPEN not in out and OUTLINE_BLOCK_CLOSE not in out
    assert "(2) Information is exempt" not in out         # the body goes with it
    assert out == "The report.\n\nMore report."


def test_a_stray_outline_header_is_stripped_too():
    """The pinpoint block's precedent: a header without its close marker is
    removed on its own, and so is an orphaned close marker."""
    out, n = strip_scope_blocks("The report.\n[SECTION OUTLINE - stray]\nMore.")
    assert n == 1
    assert "SECTION OUTLINE" not in out and "The report." in out and "More." in out
    out, n = strip_scope_blocks("The report.\n[/SECTION OUTLINE]\nMore.")
    assert n == 1 and "SECTION OUTLINE" not in out and "More." in out


def test_a_quoted_outline_line_is_prose_and_stays():
    """A Worker that quotes a subsection's opening words into its report is
    doing what the block asks; only the markers are bookkeeping."""
    text = "Under s.36(2) information is exempt if (a) it was obtained from another person."
    assert strip_scope_blocks(text) == (text, 0)


# ---------------------------------------------------------------------------
# 6. the static text
# ---------------------------------------------------------------------------

def _static_text():
    """Every fixed string the block can carry, exercised in one build."""
    rows = [_many(n, 20, words=40) for n in range(50, 62)]
    block = subsection_outline(_raw(*rows))
    # Strip the synthetic subsection bodies so only the builder's own words remain.
    lines = [ln for ln in block.split("\n") if not ln.startswith("  (")
             or "more subsection" in ln]
    return "\n".join(lines)


def test_the_static_text_trips_no_detector():
    text = _static_text()
    assert OUTLINE_HEADER in text and "omitted here for length" in text and "more subsections" in text
    for det in (rr.NEG_ASSERTED, rr.NOT_FOUND, rr.NEG_BLAMED_USER, rr.IN_FORCE_CLAIM,
                rr.HALT_PARAPHRASE, rr.HALT_AS_TIMEOUT, rr.HALT_LITERAL,
                rr.SCOTS_CASELAW_GAP):
        assert not det.search(text), det.pattern[:60]
    assert rr.derivation_claims(text)[0] == []
    assert not any(rr._currency_asserted(s) for s in rr._sentences(text))
    assert rr.caselaw_gap_statements(text) == []


def test_the_static_text_names_no_provision_the_acceptance_grades():
    """`test_citation_depth` pins this for the prompts; the block is read by the
    same model at the same seam, so the same rule."""
    text = _static_text()
    for p in ("Sch 1 para 1(2)", "s.21(2)", "s.22(5)", "s.57(3)", "s.45(1)", "s.36(2)", "36(2)"):
        assert p not in text


def test_the_header_tells_the_model_what_to_do_with_it():
    flat = " ".join(OUTLINE_HEADER.split()).lower()
    assert "say in a line what its other subsections provide" in flat
    assert "give each subsection its own number" in flat
    assert "summary above may leave some of them out" in flat
