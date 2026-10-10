"""FIX_PLAN P3.4's research-mode follow-up (batch 12 E; user decision 2026-10-09).

The default-jurisdiction rule approved for the conversational Manager (no
jurisdiction named: Scotland, said so; "the UK": each of the four parts) now
also reaches the research Manager and the Deep Research planner, for the three
legislation research types. One text: the section is read out of
`_MANAGER_CONV_BODY`, never retyped; the planner's copy differs only in its
last bullet, which names the `scope_note` (the planner writes no brief).
"""
import pytest

from src import prompts

RESEARCH_TYPES = ("legislation_only", "case_law_only", "legislation_and_case_law")
BOT_MODES = ("parliamentary_records", "westminster_records")
SECTION = prompts.DEFAULT_JURISDICTION_SECTION
PLANNER_SECTION = prompts.PLANNER_JURISDICTION_SECTION
EXTRAS = (
    {},
    {"_suggested_questions_enabled": False},
    {"_research_mode_enabled": False},
    {"_consulted": True},
    {"_jurisdiction": "scotland", "_year_to": 2026},
)


def _bullets(section: str) -> list:
    return [line for line in section.split("\n") if line.startswith("- ")]


# --- one text ----------------------------------------------------------------

def test_the_section_is_the_conversational_managers_own():
    body = prompts._MANAGER_CONV_BODY
    assert body.count(SECTION) == 1
    assert SECTION.startswith("JURISDICTION:\n")
    assert body[body.index(SECTION) + len(SECTION):].startswith("\n\nWHEN USING delegate_research")
    bullets = _bullets(SECTION)
    assert len(bullets) == 4
    assert bullets[0].startswith("- If the question names no jurisdiction and no jurisdiction "
                                 "filter is active, answer it for Scotland")
    assert bullets[3].startswith("- Put the jurisdiction in every `delegate_research` brief")


def test_the_planners_copy_differs_only_in_its_last_bullet():
    ours, theirs = _bullets(PLANNER_SECTION), _bullets(SECTION)
    assert ours[:3] == theirs[:3]
    assert ours[3] == theirs[3].replace(
        "Put the jurisdiction in every `delegate_research` brief",
        "Put the jurisdiction in the `scope_note`, which every step's brief and the final "
        "report carry")
    assert "delegate_research" not in PLANNER_SECTION
    # The example jurisdictions and the no-instrument clause survive verbatim.
    assert '(for example "for Scotland", or "for each of England, Wales, Scotland and ' \
           'Northern Ireland, noting where the law differs")' in ours[3]
    assert "do not add an Act or instrument for it that neither the user nor a tool " \
           "result has given you" in ours[3]


# --- the research Manager ----------------------------------------------------------

@pytest.mark.parametrize("extra", EXTRAS)
@pytest.mark.parametrize("chat_mode", (None, "research", "deep_research"))
@pytest.mark.parametrize("research_mode", RESEARCH_TYPES)
def test_the_research_manager_carries_the_section_once(research_mode, chat_mode, extra):
    cfg = dict(extra)
    if chat_mode:
        cfg["_chat_mode"] = chat_mode
    text = prompts.get_manager_system_prompt(research_mode, cfg or None)
    assert text.count(SECTION) == 1
    i = text.index(SECTION)
    # After SCOPE, immediately before RESEARCH BRIEF CONSTRUCTION.
    assert text.index("\nSCOPE:\n") < i
    assert text[i + len(SECTION):].startswith("\n\nRESEARCH BRIEF CONSTRUCTION:\n")
    assert "You are the Senior Legal Interface" in text  # the research body, not the chat one


def test_a_consulted_request_keeps_the_section_and_the_consulted_block():
    text = prompts.get_manager_system_prompt("legislation_only", {"_consulted": True})
    assert text.count(SECTION) == 1
    assert text.endswith(prompts.CONSULTED_PEER_BLOCK)


def test_the_merged_research_constant_carries_it():
    assert prompts.MANAGER_SYSTEM_PROMPT == (
        prompts._RESEARCH_MANAGER_BODY + "\n\n" + prompts._MANAGER_CHIPS)
    assert prompts.MANAGER_SYSTEM_PROMPT.count(SECTION) == 1
    # The research body is the old body plus the section and nothing else.
    assert prompts._RESEARCH_MANAGER_BODY.replace(SECTION + "\n\n", "", 1) == prompts._MANAGER_BODY


@pytest.mark.parametrize("research_mode", RESEARCH_TYPES)
def test_the_conversational_manager_still_has_it_once(research_mode):
    text = prompts.get_manager_system_prompt(research_mode, {"_chat_mode": "conversational"})
    assert text.count(SECTION) == 1
    assert "Senior Legal Interface" not in text


@pytest.mark.parametrize("chat_mode", (None, "research", "conversational", "deep_research"))
@pytest.mark.parametrize("research_mode", BOT_MODES)
def test_the_parliament_bots_never_get_it(research_mode, chat_mode):
    cfg = {"_chat_mode": chat_mode} if chat_mode else None
    assert "JURISDICTION:\n- If the question names no" not in \
        prompts.get_manager_system_prompt(research_mode, cfg)
    assert "JURISDICTION:\n- If the question names no" not in \
        prompts.get_planner_system_prompt(research_mode, cfg)


# --- the Deep Research planner -------------------------------------------------

@pytest.mark.parametrize("extra", EXTRAS)
@pytest.mark.parametrize("research_mode", RESEARCH_TYPES)
def test_the_planner_carries_its_section_once_before_the_filters_rule(research_mode, extra):
    text = prompts.get_planner_system_prompt(research_mode, dict(extra) or None)
    assert text.count(PLANNER_SECTION) == 1
    assert SECTION not in text
    i = text.index(PLANNER_SECTION)
    assert text[i + len(PLANNER_SECTION):].startswith("\n\nRESPECT ACTIVE FILTERS:\n")
    assert "{options_rule}" not in text


def test_an_unknown_research_mode_gets_the_legislation_planner_and_the_section():
    text = prompts.get_planner_system_prompt("something_else", None)
    assert text.count(PLANNER_SECTION) == 1
    assert "CURRENT RESEARCH TYPE: Legislation only." in text


def test_the_planner_constant_itself_is_unchanged():
    assert "JURISDICTION:\n" not in prompts.PLANNER_SYSTEM_PROMPT


# --- the guards ----------------------------------------------------------------

def test_one_span_needs_its_start_exactly_once_and_an_end_after_it():
    assert prompts._one_span("a START x END b", "START", "END") == "START x "
    for text in ("no anchor END", "START a START b END", "END before START"):
        with pytest.raises(RuntimeError):
            prompts._one_span(text, "START", "END")


def test_insert_before_needs_its_anchor_exactly_once():
    assert prompts._insert_before("a\n\nANCHOR rest", "ANCHOR", "NEW") == "a\n\nNEW\n\nANCHOR rest"
    for text in ("nothing here", "ANCHOR and ANCHOR"):
        with pytest.raises(RuntimeError):
            prompts._insert_before(text, "ANCHOR", "NEW")


def test_the_planner_rewrite_needs_the_brief_clause_exactly_once():
    clause = "Put the jurisdiction in every `delegate_research` brief"
    assert "scope_note" in prompts._for_the_planner("- " + clause + " (x).")
    for text in ("- no clause here", f"- {clause}; {clause}"):
        with pytest.raises(RuntimeError):
            prompts._for_the_planner(text)


# --- the one new clause, screened ----------------------------------------------

def test_the_scope_note_clause_trips_no_detector():
    """The only words not already approved and screened (P3.4's
    `test_the_new_wording_trips_no_detector` screens the rest). `NEG_LIMITS`
    and `NEGATIVE_EXPLAINED` are left out there for the word "filter"; this
    bullet carries none, so they are asserted here."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM, NEG_ASSERTED,
        NEG_BLAMED_INDEX, NEG_BLAMED_USER, NEG_LIMITS, NEG_TERMS, NEGATIVE_EXPLAINED, NOT_FOUND,
        OPENER_VOCAB, SCHED_LIMIT, SCOTS_CASELAW_GAP, _CUR_DATED, _CUR_DISCLOSED,
        _currency_asserted, _sentences, _without_footer, caselaw_gap_statements,
        derivation_claims, negcurrency_claim, sched_clause_class,
    )
    text = _bullets(PLANNER_SECTION)[3]
    assert derivation_claims(text)[0] == []
    assert caselaw_gap_statements(text) == []
    assert _without_footer(text) == text.strip()
    for rx in (NEG_ASSERTED, NOT_FOUND, NEG_TERMS, NEG_LIMITS, NEG_BLAMED_INDEX,
               NEG_BLAMED_USER, IN_FORCE_CLAIM, _CUR_DISCLOSED, _CUR_DATED, SCOTS_CASELAW_GAP,
               HALT_LITERAL, HALT_PARAPHRASE, HALT_AS_TIMEOUT, OPENER_VOCAB, SCHED_LIMIT,
               NEGATIVE_EXPLAINED):
        assert not rx.search(text), rx.pattern[:40]
    for s in _sentences(text):
        assert not _currency_asserted(s), s
        assert negcurrency_claim(s)[0] is None, s
        assert sched_clause_class(s) == "", s


# --- decision 9(a): the hybrid research Worker's JURISDICTION SCOPE line ---------
#
# Since the follow-up, every Legislation & case law question that names no
# jurisdiction reaches this Worker with "for Scotland" in its brief; "that
# jurisdiction's legislation" could be read to exclude UK Acts that extend there,
# which the rule includes. Reworded to the rule's own reading (user decision
# 2026-10-09).

NEW_PHRASE = ("retrieve sections ONLY for the legislation that applies in that jurisdiction "
              "(UK legislation that extends there included).")
OLD_PHRASE = "retrieve sections ONLY for that jurisdiction's legislation."


def _scope_line(text: str) -> str:
    lines = [ln for ln in text.split("\n") if ln.startswith("- JURISDICTION SCOPE:")]
    assert len(lines) == 1
    return lines[0]


def test_the_hybrid_line_reads_applies_in_with_uk_legislation_included():
    line = _scope_line(prompts.WORKER_SYSTEM_PROMPT_HYBRID)
    assert NEW_PHRASE in line
    assert OLD_PHRASE not in prompts.WORKER_SYSTEM_PROMPT_HYBRID
    # The line's other two sentences are unchanged.
    assert ("For a Scotland question, do not pull English, Welsh, or Northern Irish instruments "
            "even if they appear in Phase 1 results.") in line
    assert ("If a judgment you have read cites legislation across several jurisdictions, follow "
            "up only on the legislation for the jurisdiction the brief asks about.") in line


def test_the_line_matches_the_managers_reading():
    # The research Manager's section says the same thing in its own words.
    assert "including UK legislation that extends there" in SECTION
    assert "UK legislation that extends there included" in _scope_line(
        prompts.WORKER_SYSTEM_PROMPT_HYBRID)


@pytest.mark.parametrize("chat_mode", (None, "research", "deep_research"))
def test_the_hybrid_worker_prompt_carries_the_new_line(chat_mode):
    cfg = {"_chat_mode": chat_mode} if chat_mode else None
    assert NEW_PHRASE in prompts.get_worker_system_prompt("legislation_and_case_law", cfg)


def test_no_other_worker_prompt_has_a_scope_line():
    for name in ("WORKER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT_CASE_LAW",
                 "WORKER_SYSTEM_PROMPT_CONVERSATIONAL", "PARLIAMENT_WORKER_SYSTEM_PROMPT",
                 "WESTMINSTER_WORKER_SYSTEM_PROMPT"):
        text = getattr(prompts, name)
        assert "JURISDICTION SCOPE" not in text, name
        assert NEW_PHRASE not in text, name


def test_the_hybrid_line_trips_no_detector_sentence_by_sentence():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import tools.replay_report as rr
    names = ("HALT_AS_TIMEOUT", "HALT_LITERAL", "HALT_PARAPHRASE", "IN_FORCE_CLAIM",
             "NEG_ASSERTED", "NEG_BLAMED_INDEX", "NEG_BLAMED_USER", "NEG_LIMITS", "NEG_TERMS",
             "NEGATIVE_EXPLAINED", "NOT_FOUND", "OPENER_VOCAB", "SCHED_LIMIT",
             "SCOTS_CASELAW_GAP", "_CUR_DATED", "_CUR_DISCLOSED", "MD_LINK")
    sentences = list(rr._sentences(_scope_line(prompts.WORKER_SYSTEM_PROMPT_HYBRID)))
    assert len(sentences) == 3
    for s in sentences:
        for n in names:
            assert not getattr(rr, n).search(s), (n, s)
        assert rr.derivation_claims(s)[0] == [], s
        assert rr.caselaw_gap_statements(s) == [], s
        assert not rr._currency_asserted(s), s
        assert rr.negcurrency_claim(s)[0] is None, s
        assert rr.sched_clause_class(s) == "", s
        assert not (rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s)), s
