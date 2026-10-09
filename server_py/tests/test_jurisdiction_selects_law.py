"""Batch 12 A (FIX_PLAN P3.12): a jurisdiction selects the law, not the provisions.

P3.4 tells the conversational Manager to put the jurisdiction in every brief
("for Scotland"). On P3.12's turn the quick-lookup Worker then reported only the
provisions of a Schedule that name Scotland and dropped the paragraphs that apply
there without naming it, though code had handed it all of them verbatim. As-sent
seam draws (`notes/batch12_A.md`): the paragraph was dropped on 2 of 3 payloads;
the same payload with only " for Scotland" taken out of the brief gave every one.

The candidate is ONE sentence at the end of the quick-lookup Worker's existing
Jurisdiction bullet (P3.4's reason: a block once changed this prompt's output
format), and in no other prompt. Its wording is the user's to approve.

Every test here fails with `prompts.py` restored to its parent commit.
"""
import re

import pytest

from src import prompts

# The sentence, spelled out here so a change to the constant is a change to a test.
SENTENCE = (
    "A jurisdiction, whether the brief names it or it is the default, selects the law "
    "that applies there, not the provisions to report: give each provision on the "
    "question that applies there, including those that also apply elsewhere in the UK, "
    "not only those that name that jurisdiction or apply only there."
)
RESEARCH_TYPES = ("legislation_only", "case_law_only", "legislation_and_case_law")
BOT_MODES = ("parliamentary_records", "westminster_records")


def _bullet(text: str) -> str:
    mandate = text.split("YOUR MANDATE:\n", 1)[1].split("\n\n", 1)[0]
    bullets = [b for b in mandate.split("\n") if b.startswith("- Jurisdiction:")]
    assert len(bullets) == 1, bullets
    return bullets[0]


def test_the_constant_is_the_sentence():
    assert getattr(prompts, "_JURISDICTION_SELECTS_LAW", None) == SENTENCE


def test_the_sentence_closes_the_quick_lookup_workers_jurisdiction_bullet():
    """At the end of the one bullet, after P3.4's three rules, unchanged; not a
    block of its own, and once only."""
    text = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    b = _bullet(text)
    assert b.endswith("If the brief names a jurisdiction, answer for that one. " + SENTENCE)
    assert text.count(SENTENCE) == 1
    # P3.4's own bullet is otherwise byte-for-byte what it was.
    assert b[: -len(" " + SENTENCE)] == (
        "- Jurisdiction: if the brief names no jurisdiction, find the legislation that applies "
        "in Scotland (UK legislation that extends there included) and say that your answer is "
        "for Scotland. If the brief asks about the UK as a whole, find it for each of England, "
        "Wales, Scotland and Northern Ireland, say where it differs and give each, and never "
        "give one part's law as the answer for the whole UK. If the brief names a jurisdiction, "
        "answer for that one.")


def test_the_prompt_is_its_parent_plus_the_sentence_alone():
    """Removing the sentence (and the space before it) leaves P3.4's prompt
    with the bullet ending where it ended, and nothing else in the prompt
    moved."""
    text = prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    before = text.replace(" " + SENTENCE, "", 1)
    assert before != text
    assert "answer for that one.\n\nRESEARCH PROCESS — keep it tight:" in before


@pytest.mark.parametrize("chat_mode", (None, "research", "conversational", "deep_research"))
@pytest.mark.parametrize("research_mode", RESEARCH_TYPES + BOT_MODES)
def test_the_sentence_reaches_exactly_the_quick_lookup_worker(research_mode, chat_mode):
    """Every dispatch branch of the Worker, Manager and planner builders, and a
    filtered request: only the quick-lookup Worker carries it (the research
    Workers are a decision for the user, not part of this candidate)."""
    for extra in ({}, {"_jurisdiction": "scotland", "_year_to": 2026}):
        cfg = dict(extra)
        if chat_mode:
            cfg["_chat_mode"] = chat_mode
        cfg = cfg or None
        quick = chat_mode == "conversational" and research_mode not in BOT_MODES
        assert (SENTENCE in prompts.get_worker_system_prompt(research_mode, cfg)) is quick
        assert SENTENCE not in prompts.get_manager_system_prompt(research_mode, cfg)
        assert SENTENCE not in prompts.get_planner_system_prompt(research_mode, cfg)
    assert SENTENCE not in prompts.get_deep_research_synthesis_prompt(research_mode)


def test_no_research_or_manager_constant_carries_it():
    for name in ("MANAGER_SYSTEM_PROMPT", "MANAGER_SYSTEM_PROMPT_CONVERSATIONAL",
                 "WORKER_SYSTEM_PROMPT", "WORKER_SYSTEM_PROMPT_HYBRID",
                 "WORKER_SYSTEM_PROMPT_CASE_LAW", "PLANNER_SYSTEM_PROMPT",
                 "PARLIAMENT_WORKER_SYSTEM_PROMPT", "WESTMINSTER_WORKER_SYSTEM_PROMPT",
                 "PARLIAMENT_MANAGER_SYSTEM_PROMPT", "WESTMINSTER_MANAGER_SYSTEM_PROMPT"):
        assert SENTENCE not in getattr(prompts, name), name


def test_the_sentence_says_what_the_jurisdiction_selects():
    """The four parts that do the work, each pinned: the default is covered
    as well as a named jurisdiction; it selects law, not provisions; a provision
    that also applies elsewhere is in; and the narrowing it rules out is named."""
    s = _bullet(prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL)
    assert "whether the brief names it or it is the default" in s
    assert "selects the law that applies there, not the provisions to report" in s
    assert "including those that also apply elsewhere in the UK" in s
    assert "not only those that name that jurisdiction or apply only there" in s
    # Scoped to provisions on the question: P3.4's "Do not broaden the scope" stands.
    assert "each provision on the question" in s
    assert "Do not broaden the scope." in prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL


def test_the_sentence_trips_no_detector():
    """A model can echo a prompt sentence into an answer, so it is screened as
    P3.4's wording was, and against the columns P3.4's screen left out
    (`NEG_LIMITS`, `NEGATIVE_EXPLAINED`: this sentence has no "filter"), the
    schedule detectors and P3.12's own not-delivered pattern."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import replay_report as rr
    text = _bullet(prompts.WORKER_SYSTEM_PROMPT_CONVERSATIONAL)[len("- "):]
    sent = prompts._JURISDICTION_SELECTS_LAW
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    for t in (text, sent):
        assert rr.derivation_claims(t)[0] == []
        assert rr.caselaw_gap_statements(t) == []
        assert rr._without_footer(t) == t.strip()
        for name in ("NEG_ASSERTED", "NOT_FOUND", "NEG_TERMS", "NEG_BLAMED_INDEX",
                     "NEG_BLAMED_USER", "NEG_LIMITS", "NEGATIVE_EXPLAINED", "IN_FORCE_CLAIM",
                     "_CUR_DISCLOSED", "_CUR_DATED", "SCOTS_CASELAW_GAP", "HALT_LITERAL",
                     "HALT_PARAPHRASE", "HALT_AS_TIMEOUT", "OPENER_VOCAB", "SCHED_LIMIT",
                     "SCHED_INDEX_NEG", "_P312_NOT_DELIVERED"):
            assert not getattr(rr, name).search(t), (name, t[:40])
        assert not [c for c, _, _ in rr.sched_unit_clauses(t, unit_rx) if c]
        for s in rr._sentences(t):
            assert not (rr._CMC_CONTEXT.search(s) and rr._CMC_DENIED.search(s)), s
            assert not rr._currency_asserted(s), s
            assert rr.negcurrency_claim(s)[0] is None, s
            assert not rr.sched_clause_class(s), s
        assert sum(rr._scripted_counts(t).values()) == 0
    for word in ("ranked", "cut short", "[", "]", "retriev"):
        assert word not in sent.lower(), word
