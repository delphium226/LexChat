"""FIX_PLAN P3.4 (bucket B9): the default-jurisdiction rule and the extent notes.

Two changes, both in `src/prompts.py`:

1. **The extent notes** (`_JURISDICTION_EXTENT_NOTES`, carried by the filter
   block when a jurisdiction filter is set) used to say "Prioritise legislation
   where extent includes S or E+W+S+NI", a letter format the LEX API never
   sends (P1.1: it sends territory names), and nothing told the model that most
   rows carry no extent at all (57.8% of the stored API rows, batch 9 D). The
   acceptance's part (a): no note names a letter code, and every note says that
   most results carry no stated extent.

2. **A default-jurisdiction rule** in the two prompts P3.4's acceptance
   sessions run on, the conversational Manager and the quick-lookup Worker, and
   in no other: no jurisdiction named means Scotland, said so; "the UK" means
   each of the four parts, with divergence flagged.

Every test here fails with `prompts.py` restored to the commit before P3.4.
"""
import re

import pytest

from src import prompts
from src.agent.tools import lex

# A territorial letter code as the old notes wrote them ("S", "E+W+S+NI",
# "NI"), and the joiners they used. "UK" is not one: the case-law sentence on
# the Scotland note names the UK Supreme Court.
LETTER_CODE = re.compile(r"(?<![A-Za-z])(?:E|W|S|NI|GB)(?![A-Za-z])|[+&]")
MOST_UNSTATED = re.compile(r"\bMost legislation search results carry no stated extent\b")
TERRITORY = {"E": "England", "W": "Wales", "S": "Scotland", "NI": "Northern Ireland",
             "UK": "United Kingdom"}

MANAGER_RULE = ("If the question names no jurisdiction and no jurisdiction filter is "
                "active, answer it for Scotland")
WORKER_RULE = ("if the brief names no jurisdiction, find the legislation that applies "
               "in Scotland")
RESEARCH_TYPES = ("legislation_only", "case_law_only", "legislation_and_case_law")
BOT_MODES = ("parliamentary_records", "westminster_records")


# ---------------------------------------------------------------------------
# 1. The extent notes (acceptance part (a), as booked)
# ---------------------------------------------------------------------------

def test_the_notes_cover_every_jurisdiction_filter_value():
    assert set(prompts._JURISDICTION_EXTENT_NOTES) == set(lex._JURISDICTION_ACCEPTS)


@pytest.mark.parametrize("jurisdiction", sorted(lex._JURISDICTION_ACCEPTS))
def test_no_extent_note_names_a_letter_code(jurisdiction):
    note = prompts._JURISDICTION_EXTENT_NOTES[jurisdiction]
    assert not LETTER_CODE.search(note), (jurisdiction, LETTER_CODE.search(note).group(0))


@pytest.mark.parametrize("jurisdiction", sorted(lex._JURISDICTION_ACCEPTS))
def test_every_extent_note_says_most_results_carry_no_stated_extent(jurisdiction):
    note = prompts._JURISDICTION_EXTENT_NOTES[jurisdiction]
    assert MOST_UNSTATED.search(note), jurisdiction
    # What the filter does with those rows, which is what makes the fact matter:
    # a territorial filter keeps them (P1.1), "UK-wide only" removes them.
    if jurisdiction == "uk_wide":
        assert "this filter removes them" in note
        assert "not about the law" in note
    else:
        assert "the filter keeps those too" in note
        assert "has not thereby been shown to apply" in note


@pytest.mark.parametrize("jurisdiction", sorted(lex._JURISDICTION_ACCEPTS))
def test_each_note_names_what_the_filter_keeps_in_the_apis_vocabulary(jurisdiction):
    """The note states the filter's own rule, in the territory names the API
    sends, so a change to `_JURISDICTION_ACCEPTS` that is not carried into the
    prompt fails here instead of misleading the model."""
    note = prompts._JURISDICTION_EXTENT_NOTES[jurisdiction]
    if jurisdiction == "uk_wide":
        m = re.search(r"kept only where their stated extent is the ([^.]+)\.", note)
    else:
        m = re.search(r"kept where their stated extent includes ([^.]+)\.", note)
    assert m, note
    named = {re.sub(r"^the ", "", x) for x in re.split(r", | or ", m.group(1))}
    expected = {TERRITORY[t] for t in lex._JURISDICTION_ACCEPTS[jurisdiction]
                if t in TERRITORY}
    assert named == expected, (jurisdiction, named, expected)


@pytest.mark.parametrize("jurisdiction", sorted(lex._JURISDICTION_ACCEPTS))
def test_the_filter_block_carries_the_note(jurisdiction):
    block = prompts.build_filter_constraint_block({"_jurisdiction": jurisdiction})
    assert prompts._JURISDICTION_EXTENT_NOTES[jurisdiction] in block
    assert not LETTER_CODE.search(block.split("\n", 1)[1])


def test_the_scotland_note_keeps_its_case_law_sentence():
    note = prompts._JURISDICTION_EXTENT_NOTES["scotland"]
    assert "holds no decisions of the Court of Session" in note
    assert "Scottish appeals decided by the UK Supreme Court are included" in note


# ---------------------------------------------------------------------------
# 2. The default-jurisdiction rule: in exactly the two prompts
# ---------------------------------------------------------------------------

_EXTRAS = (
    {},
    {"_suggested_questions_enabled": False},
    {"_research_mode_enabled": False},
    {"_consulted": True},
    {"_jurisdiction": "scotland", "_year_to": 2026},
)


@pytest.mark.parametrize("extra", _EXTRAS)
@pytest.mark.parametrize("chat_mode", (None, "research", "conversational", "deep_research"))
@pytest.mark.parametrize("research_mode", RESEARCH_TYPES + BOT_MODES)
def test_the_rule_reaches_exactly_the_conversational_manager_and_quick_lookup_worker(
        research_mode, chat_mode, extra):
    """Every dispatch branch of the three prompt builders (the parliament and
    Westminster branch returns early, P0.5's lesson), every flag that swaps
    text in or out, and a filtered request."""
    cfg = dict(extra)
    if chat_mode:
        cfg["_chat_mode"] = chat_mode
    cfg = cfg or None
    quick = chat_mode == "conversational" and research_mode not in BOT_MODES
    manager = prompts.get_manager_system_prompt(research_mode, cfg)
    worker = prompts.get_worker_system_prompt(research_mode, cfg)
    planner = prompts.get_planner_system_prompt(research_mode, cfg)
    assert (MANAGER_RULE in manager) is quick
    assert (WORKER_RULE in worker) is quick
    assert WORKER_RULE not in manager and MANAGER_RULE not in worker
    assert MANAGER_RULE not in planner and WORKER_RULE not in planner


@pytest.mark.parametrize("research_mode", RESEARCH_TYPES + BOT_MODES)
def test_the_rule_is_not_in_the_deep_research_synthesis(research_mode):
    text = prompts.get_deep_research_synthesis_prompt(research_mode)
    assert MANAGER_RULE not in text and WORKER_RULE not in text


def test_the_research_prompts_carry_no_default_jurisdiction():
    for name in ("MANAGER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT_HYBRID",
                 "WORKER_SYSTEM_PROMPT_CASE_LAW", "PLANNER_SYSTEM_PROMPT",
                 "PARLIAMENT_MANAGER_SYSTEM_PROMPT", "WESTMINSTER_MANAGER_SYSTEM_PROMPT"):
        text = getattr(prompts, name)
        assert "answer it for Scotland" not in text, name
        assert "applies in Scotland" not in text, name


def test_the_manager_rule_says_each_part():
    body = prompts._MANAGER_CONV_BODY
    section = re.search(r"\nJURISDICTION:\n(.*?)\n\n", body, re.S).group(1)
    # No jurisdiction named: Scotland, said so.
    assert "answer it for Scotland" in section
    assert "say in your answer that this is the position in Scotland" in section
    # "The UK": all four, divergence flagged, never one part for the whole.
    assert "answer for each of England, Wales, Scotland and Northern Ireland" in section
    assert "where the law differs between them, say so and give each" in section
    assert "never give one part's law as the answer for the whole UK" in section
    # A named jurisdiction, filter or instrument wins.
    assert "or an active filter names a jurisdiction" in section
    # The brief states it, and names no instrument for it (P3.13: a Manager
    # prompt edit reaches the FIRST delegation brief).
    assert "Put the jurisdiction in every `delegate_research` brief" in section
    assert "do not add an Act or instrument for it that neither the user nor a tool " \
           "result has given you" in section


def test_the_worker_rule_is_one_bullet_in_the_mandate_and_about_legislation():
    """One bullet, not a block: a block appended to this prompt once changed its
    output format (P2.4's A/B). Scoped to legislation so a case-law query is
    not narrowed by an added "Scotland"."""
    text = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    mandate = text.split("YOUR MANDATE:\n", 1)[1].split("\n\n", 1)[0]
    bullets = [b for b in mandate.split("\n") if b.startswith("- Jurisdiction:")]
    assert len(bullets) == 1
    b = bullets[0]
    assert WORKER_RULE in b
    assert "say that your answer is for Scotland" in b
    assert "each of England, Wales, Scotland and Northern Ireland" in b
    assert "say where it differs and give each" in b
    assert "If the brief names a jurisdiction, answer for that one." in b
    assert "JURISDICTION:" not in text


# ---------------------------------------------------------------------------
# 3. Every new sentence screened against the detectors that read answers
# ---------------------------------------------------------------------------

def _new_texts() -> dict:
    texts = {}
    for k, v in prompts._JURISDICTION_EXTENT_NOTES.items():
        # The case-law sentence on the Scotland note is P2.4's, not new here.
        texts[f"note {k}"] = v.split(" Note that the case law database")[0]
    texts["manager section"] = re.search(
        r"\nJURISDICTION:\n(.*?)\n\n", prompts._MANAGER_CONV_BODY, re.S).group(1)
    texts["worker bullet"] = re.search(
        r"\n(- Jurisdiction: .*?)\n", prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL).group(1)
    return texts


def test_the_new_wording_trips_no_detector():
    """A model can echo a prompt sentence into an answer, so each is screened
    as `test_footer_trips_no_detector` screens the product's footer.

    **`NEG_LIMITS` and `NEGATIVE_EXPLAINED` are deliberately not asserted.**
    Both match the bare word "filter", which the notes and the Manager rule
    must use (it is the control's name), and which the filter block's own
    header ("ACTIVE RESEARCH FILTERS") already carries; an answer that echoes it
    is disclosing a real limit, which is what those columns credit."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED,
        NEG_BLAMED_INDEX, NEG_BLAMED_USER, NEG_TERMS, NOT_FOUND, OPENER_VOCAB,
        SCOTS_CASELAW_GAP, _CMC_CONTEXT, _CMC_DENIED, _CUR_DATED, _CUR_DISCLOSED,
        _currency_asserted, _sentences, _without_footer, caselaw_gap_statements,
        derivation_claims, negcurrency_claim, sched_unit_clauses,
    )
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    texts = _new_texts()
    assert len(texts) == 7
    for where, text in texts.items():
        assert text, where
        assert derivation_claims(text)[0] == [], where
        assert caselaw_gap_statements(text) == [], where
        assert _without_footer(text) == text.strip(), where
        for rx in (NEG_ASSERTED, NOT_FOUND, NEG_TERMS, NEG_BLAMED_INDEX, NEG_BLAMED_USER,
                   IN_FORCE_CLAIM, _CUR_DISCLOSED, _CUR_DATED, SCOTS_CASELAW_GAP,
                   HALT_LITERAL, HALT_PARAPHRASE, HALT_AS_TIMEOUT, OPENER_VOCAB):
            assert not rx.search(text), (where, rx.pattern[:40])
        assert not [c for c, _, _ in sched_unit_clauses(text, unit_rx) if c], where
        for s in _sentences(text):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), (where, s)
            assert not _currency_asserted(s), (where, s)
            assert negcurrency_claim(s)[0] is None, (where, s)
