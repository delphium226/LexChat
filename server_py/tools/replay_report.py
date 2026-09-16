#!/usr/bin/env python
"""Turn replay run files into measurements (FIX_PLAN P0.3, and the acceptance
tests for P1.1, P1.3, P1.4, P2.1, P2.2, P4.2, P4.3).

`replay.py` captures what happened; this module says what it means. It computes
only **deterministic** signals — things a regex or an arithmetic comparison can
settle — and deliberately stops short of judging whether a session's original
failure reproduced. That judgement is a reading of the answer against the frozen
diagnosis and belongs to a person; these signals are what that person reads
first, and they are what a later acceptance test asserts on.

The most valuable signal here is `filter_loss`, because it is measured from both
sides of the defect at once. A `search_legislation` tool record carries the LEX
response in `api_calls[].response` and the text the model actually received in
`final_result`, so the count the API returned and the count that survived
post-filtering are both in the trace:

    api total=97  results=20   ->   final_result {"results": [], "total": 0}

That single line is B2 (`_matches_jurisdiction` discarding every result) and the
second half of B5 (`slimmed["total"] = len(results)` overwriting the API's real
match count) visible in one place, with no inference. It is the "before" number
P1.1 and P1.3 need, and re-running this module after Wave 1 is their "after".

Usage:
    python -m tools.replay_report summary  --dir <replay dir>
    python -m tools.replay_report session  --dir <replay dir> --session 6410
    python -m tools.replay_report baseline --dir <replay dir> > BASELINE_draft.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# --- Detectors ---------------------------------------------------------------

# `chat_loop` returns this as the worker's assistant content when it runs out of
# tool-call steps; `run_deep_research` then treats it as the step's findings.
HALT_LITERAL = re.compile(r"\[Research halted", re.I)
# What the synthesis turns that into by the time the lawyer sees it.
#
# **Widened 2026-09-15 (P1.5) after measuring it: the original caught 9 of the 14
# real disclosures.** It required near-exact wording — "operational limit",
# "research was halted" — and the model does not paraphrase to a fixed script.
# It missed "exceeded its *processing* limits", "timed out while searching",
# "exceeded the maximum *permitted steps*", and "Research Step 2 ... was halted"
# (an intervening clause defeated `research (?:process )?was halted`).
#
# That is the dangerous direction for P2.1, whose acceptance asserts the ABSENCE
# of halt language: a blind detector passes the row while the halt still reaches
# the lawyer. Validated over the whole baseline — 14/14 disclosures matched, and
# the only hit on a non-halt turn is 6383 turn 1, which is not a false positive
# but the corpus's worst case (the raw string as the entire answer, reaching the
# lawyer without any delegation report carrying it).
HALT_PARAPHRASE = re.compile(
    r"\[research halted"
    r"|this answer is incomplete"          # P2.1's code-emitted disclosure
    r"|tool-call rounds?"
    r"|tool[- ]call step"
    r"|exceed(?:ed|ing|s)? (?:the |its |their )?"
    r"(?:maximum |technical |processing |operational |permitted |internal |system )*"
    r"(?:number of )?(?:research )?(?:step|limit)"
    r"|(?:operational|processing|technical|system|internal) limits?"
    r"|(?:research|search|step|process|analysis)[^.]{0,70}\bwas halted\b"
    r"|\bhalted (?:by the system|due to|prior to|after|across|before)"
    r"|(?:research|agent|search|step|process)[^.]{0,50}\btimed out\b"
    r"|\btimed out\b[^.]{0,50}(?:search|research|attempt)",
    re.I,
)

# P2.1 condition (3): the halt disclosed with the WRONG reason. "Timed out"
# is the specific falsehood 6340 produced, and it is not a harmless synonym —
# a timeout implies the same question might succeed on a retry, where a step
# cap says it will not. Negations are excluded so P2.1's own notice ("it is
# **not** a timeout") does not match itself.
HALT_AS_TIMEOUT = re.compile(
    r"(?<!not a )(?<!not\*\* a )(?:timed out|timeout|time[- ]?out)",
    re.I,
)

NOT_FOUND = re.compile(
    r"\b(no (?:relevant )?(?:results?|legislation|provisions?|records?|cases?|"
    r"regulations?|instruments?)\b|not (?:be )?(?:found|located|retrieved)"
    r"|could not (?:be )?(?:find|locate|retrieve|identify)"
    r"|does not appear to (?:be|exist)|no .{0,30}have been made)",
    re.I,
)
# A negative is "explained" if it says what was searched / under what filters.
#
# **Deliberately left as it was, and deliberately NOT used to grade P2.2.** It is
# a coarse screen — the bare word "filter" anywhere in an answer satisfies it —
# and it has been reported against the whole corpus since Wave 0. Tightening it
# in place would silently redefine every earlier reading of `bare_negatives`,
# which is the mistake `provision_links_manufactured` was explicitly not allowed
# to make (SESSION_LOG, Session 5). P2.2's acceptance uses the three conditions
# below instead, and `cmd_negatives` prints both so the two can be compared.
NEGATIVE_EXPLAINED = re.compile(
    r"search(?:ed|ing)? (?:for|term|the)|filter|jurisdiction (?:filter|was set)"
    r"|scope of (?:the|my) search|query used|search terms",
    re.I,
)

# --- P2.2 (B5) acceptance ----------------------------------------------------
#
# The row: *"6409 and 6367 name their search terms and active filters in the
# negative answer"*, and **Invariant 1 applies with force** — the test is that
# the negative is EXPLAINED, not that it becomes a positive. So nothing here
# rewards finding something; `NEG_ASSERTED` turns are the denominator and the
# three conditions are all about what the answer says *about its own limits*.
#
# Three conditions, each a different failure in the corpus:
#
#   1. TERMS   — the answer says what was looked for. 6409 turn 9's entire
#                negative was "SSI 2025/377 could not be found in the
#                legislation database. Could you verify the SSI number?"
#   2. LIMITS  — it says under what constraint the search ran: a named filter, a
#                stated year window, or the fact that it was a ranked search of
#                an index rather than an enumeration.
#   3. BLAMED  — the miss is attributed to the index or the search. The failing
#                direction is attributing it to the LAW ("no such regulations
#                have been made") or to the LAWYER ("could you confirm the SI
#                number?", 6373 — where the citation was right and the index was
#                short, verified 404 on 2026-09-15).
#
# All three are regex screens over prose and are therefore evidence, not proof.
# `--answers` prints the negative in context because that reading is the actual
# acceptance; these columns say which turns to read first.
#
# **The first draft of this regex was a detector artefact and is recorded here
# rather than quietly replaced.** It opened `\b(?:no|not|never)\b[^.]{0,60}
# \b(?:found|exist|made|in force|…)\b` plus a bare `(?:does|do|did) not
# (?:contain|include|provide|…)`, which scored **61 of 153 turns, 61 failing —
# 100%**. A rate of 100% is an artefact until proven otherwise (SESSION_LOG's
# standing hazard 1), and it was: it could not tell a **research** negative from
# a **legal** one. It fired on *"no winding-up order may be made, except by the
# company's directors"* (6335 t2) and *"'sale of goods' does not include the
# sale of meals"* (6341 t4) — both correct statements of retrieved law, and
# neither anything to do with B5. Grading those as bare negatives would have
# pushed the model to hedge findings it had actually retrieved, which is the
# regression Invariant 1 and P3.3's counter-pressure note both warn about.
#
# So the subject has to be the *research*, not the law: something was looked for
# and not found, or the corpus itself is named as falling short.
NEG_ASSERTED = re.compile(
    # something was looked for and not found
    r"\bcould not (?:be )?(?:find|locate|retrieve|identify)"
    r"|\b(?:not|never) (?:be )?(?:found|located|retrieved|identified)\b"
    r"|\bno (?:relevant |specific |directly relevant )?"
    r"(?:results?|matches?|records?|cases?|case law|judgments?|legislation|"
    r"provisions?|regulations?|instruments?|ssis?|sis?|commencement)\b"
    # the corpus named as falling short
    r"|\b(?:database|index|corpus|collection|search(?: tools?)?|holdings?)\b"
    r"[^.]{0,50}\b(?:does|do|did) not (?:contain|include|hold|index|cover|"
    r"return|appear to)\b"
    r"|\bnot (?:currently )?(?:available|held|present|indexed) in the\b"
    r"|\bis a 404\b|\breturns? (?:a )?404\b"
    # absence asserted of an instrument or a commencement — B5's signature
    # sentence, and the one seven of the seventeen measured negatives use
    r"|\bno (?:\w+ ){0,3}(?:regulations?|orders?|instruments?|ssis?|rules?|"
    r"provisions?) (?:have|has|had|were|was) (?:yet )?been (?:made|laid|"
    r"commenced|brought into force|enacted)\b"
    r"|\b(?:have|has) not (?:yet )?been (?:made|commenced|brought into force)\b"
    r"|\bno (?:\w+ ){0,3}(?:have|has) been made\b"
    r"|\bthere (?:is|are) no (?:such|record|evidence|trace|indication)\b"
    # "No Statutory Instruments **were found** prescribing …" (6367). Added
    # 2026-09-15 after the first acceptance run scored that answer as asserting
    # no negative at all. The noun list above could not reach it — "Statutory"
    # is not in its adjective set — and widening the noun list is the wrong fix,
    # because `no <anything> orders?` is what made the first draft count
    # *"no winding-up order may be made"* as a bare negative. The discriminator
    # is the VERB: "were found" is about the search, "may be made" is about the
    # law. Re-validated over Wave 1 — it adds turns and none of them is a
    # finding of law.
    r"|\bno\b[^.\n]{0,60}\b(?:were|was|are|is) (?:found|located|retrieved|"
    r"identified|returned|surfaced|available)\b",
    re.I,
)
# **Rebuilt 2026-09-15, after patching it twice failed twice — which is the
# lesson, not the patches.** The first version demanded "searched" immediately
# followed by "for" and scored 6367 rep 1's *"Searched the legislation index 2
# time(s) for: '…'"* as naming nothing. Widening the gap then still missed 6409
# rep 2 turn 3's *"A search of the legislation index for commencement regulations
# (using terms such as '…')"*. Each patch was a fresh guess at how a model might
# phrase one idea, which is an unbounded set — the instrument was wrong in kind,
# not in detail.
#
# So the test is now **sentence-level co-occurrence** rather than adjacency: a
# sentence that talks about searching AND carries a quoted string is naming its
# search terms, whatever order it puts them in. `_names_search_terms` applies it;
# these two parts are the halves it looks for. A quoted run of ≥6 characters is
# required so an ordinary "no" or a stray apostrophe cannot satisfy it.
_SEARCH_WORD = re.compile(
    r"\b(?:search(?:ed|es|ing)?|quer(?:y|ies|ied)|keywords?|search terms?|"
    r"looked for)\b",
    re.I,
)
_QUOTED_RUN = re.compile(r"[\"“][^\"”\n]{6,}[\"”]|'[^'\n]{8,}'")
# A model naming its terms without quoting them: "a search of the legislation
# index **for commencement regulations**". Found in the final acceptance sweep,
# where requiring quotation marks scored a whole rep of genuinely explanatory
# answers as naming nothing. `for` must have an object — "a search of the
# database," on its own names no terms and must not count.
_SEARCH_FOR_OBJECT = re.compile(r"\bsearch\w*\b[^.\n]{0,45}?\bfor\b\s+(?![\s.])\S", re.I)
# Kept as the explicit-phrase fallback for an answer that names its terms without
# quoting them ("the search terms used were: commencement, uprating").
NEG_TERMS = re.compile(
    r"\bsearch(?:es|ed)?\s+(?:terms?|quer(?:y|ies)|keywords?)\b"
    r"|\bquer(?:y|ies)\s+(?:used|run|for|was|were)"
    r"|\bkeywords?\s+(?:used|search)"
    r"|\bsearch(?:ed|es|ing)?\b[^.\n]{0,60}?\bfor\b[:\s]*[\"'“]"
    r"|\bterms such as\b|\bsearches (?:run|carried out|performed)\b",
    re.I,
)


def _names_search_terms(answer: str) -> bool:
    """Does the answer say what it searched for?

    Sentence-level: a sentence that is about searching and contains a quoted
    string is naming its terms. Falls back to the explicit-phrase patterns for
    the unquoted forms.
    """
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer or ""):
        if _SEARCH_WORD.search(sentence) and (
            _QUOTED_RUN.search(sentence) or _SEARCH_FOR_OBJECT.search(sentence)
        ):
            return True
    return bool(NEG_TERMS.search(answer or ""))
NEG_LIMITS = re.compile(
    r"\bfilter(?:s|ed|ing)?\b"
    r"|\bjurisdiction (?:filter|was set|of)\b"
    r"|\branked (?:keyword )?search\b|\bkeyword search\b"
    r"|\bnot (?:an )?exhaustive\b|\bnot a complete (?:list|search)\b"
    r"|\btop \d+ (?:of|results)\b"
    r"|\bdate range\b|\byear range\b|\brestricted to\b|\blimited to\b"
    r"|\bthis answer is incomplete\b",     # P2.1's notice: a halt IS a limit
    re.I,
)
# The index named as the thing that fell short, rather than the law or the user.
#
# The last alternative exists because of one measured miss, and the number is
# worth recording. 6409 turn 7's whole answer was *"The research agent could not
# locate 'The Social Security (Amendment) (Scotland) Act 2025 (Commencement No. 1
# and Saving and Transitional Provisions) Regulations 2025' in the legislation
# database"* — **158 characters** between the "not" and the "database", because
# that is how long a commencement SSI's title is. A proximity window wide enough
# to span it would span half a paragraph, so the verb-to-phrase alternative below
# matches the attribution directly instead — and it spans NEWLINES rather than
# sentences (`[^\n]`, not `[^.]`), because **every commencement instrument's title
# contains a full stop**: "Commencement **No.** 1". A sentence window keyed on "."
# cannot cross the exact titles this corpus is about, which is why the first
# attempt at this alternative also missed. This is the easiest of the three
# conditions to satisfy, which is correct: the discriminating power belongs in
# `terms` and `limits`, which are what the row asks for ("name their search terms
# and active filters").
NEG_BLAMED_INDEX = re.compile(
    r"\b(?:not|absent|missing)\b[^.]{0,100}\b(?:index(?:ed)?|database|corpus|"
    r"collection|holdings?)\b"
    r"|\b(?:find|found|locate|located|retriev\w+|identif\w+|search\w*)\b"
    r"[^\n]{0,220}\bin (?:the|this|our) (?:legislation |case ?law |available )?"
    r"(?:database|index|corpus|collection)\b"
    r"|\b(?:index|database|corpus)\b[^.]{0,40}\b(?:does not (?:hold|contain|"
    r"include|index)|is incomplete|coverage|gap)"
    r"|\bnot held\b|\bcoverage (?:is|gap|of the)\b"
    r"|\bnot (?:evidence|proof) (?:of|that)\b[^.]{0,40}\b(?:absence|does not exist)"
    r"|\babsence from the index\b",
    re.I,
)
# The failing direction: the lawyer's own citation questioned. 6373 and 6409.
NEG_BLAMED_USER = re.compile(
    r"(?:could|can) you (?:confirm|verify|check|clarify)[^.?]{0,60}"
    r"(?:number|year|citation|reference|title)"
    r"|\b(?:verify|confirm|double[- ]check) the (?:ssi|si|s\.?i\.?) number\b"
    r"|\bare you sure\b|\bis that the correct (?:number|citation|reference)\b",
    re.I,
)

IN_FORCE_CLAIM = re.compile(
    r"\b(?:is|are|remains?|currently) (?:still )?in force"
    r"|\bin force (?:as (?:at|of)|on)\b|\bcurrently in force\b",
    re.I,
)

SCOTS_CASELAW_GAP = re.compile(
    r"court of session|sheriff (?:court|appeal)|scottish courts?.{0,40}"
    r"(?:not|absent|excluded)|national archives.{0,60}(?:does not|not index)",
    re.I,
)

MD_LINK = re.compile(r"\[([^\]]{1,200})\]\((https?://[^)\s]+)\)")
# A label that names a specific provision.
PROVISION_LABEL = re.compile(
    r"\b(section|sections|s\.|ss\.|regulation|regulations|reg\.|regs\.|"
    r"article|articles|art\.|schedule|schedules|sch\.|paragraph|para\.)\s*"
    r"(\d+[A-Z]*)",
    re.I,
)
_LABEL_TO_PATH = {
    "section": "section", "sections": "section", "s.": "section", "ss.": "section",
    "regulation": "regulation", "regulations": "regulation", "reg.": "regulation",
    "regs.": "regulation",
    "article": "article", "articles": "article", "art.": "article",
    "schedule": "schedule", "schedules": "schedule", "sch.": "schedule",
    "paragraph": "paragraph", "para.": "paragraph",
}


def _is_title_year(num: str) -> bool:
    """Is this "provision number" actually the year in an instrument's title?

    `PROVISION_LABEL` matches the word "regulations" followed by digits, which
    fires on the *name* of every SI ever cited: "The Sale of Tobacco ...
    Regulations 2013" reads as
    "regulation 2013" and the checker then demands `/regulation/2013` in the URL.
    Measured over the Wave 0 baseline this was **73 of the 88** links the report
    called wrong (83%), including links that were perfectly correct:
    `.../uksi/2020/791/regulation/2` labelled "...Regulations 2020" was counted
    as missing its provision. It inflated B14 roughly six-fold.

    A real provision is never numbered like a year. Provision numbers run to a
    few hundred at most (the largest in this corpus is s.117); a four-digit
    1200-2099 token after "Regulations"/"Sections" is the instrument's year.

    Deliberately NOT keyed on the URL's year segment alone: the model sometimes
    links a *different* instrument than the one it names, so "Regulations 1979"
    against `/uksi/1985/1272` would still be a title reference while the years
    disagree."""
    return len(num) == 4 and num.isdigit() and 1200 <= int(num) <= 2099


def _json_or_none(s: Any) -> Any:
    """Parse the JSON object a tool result *starts* with.

    `json.loads` is not enough: `run_worker_tool` appends the Phase-2 nudge
    ("[NEXT STEP: Call search_legislation_sections ... legislation_id: ...]")
    after the JSON, so a plain parse raises "Extra data" on exactly the calls
    that returned results — the successful ones. Silently reading those as
    unparseable would count every productive search as un-measurable and leave
    the filter-loss figure describing only the searches that came back empty.
    `raw_decode` stops at the end of the first object and ignores the tail.
    """
    if not isinstance(s, str):
        return s if isinstance(s, (dict, list)) else None
    try:
        obj, _ = json.JSONDecoder().raw_decode(s.lstrip())
        return obj
    except Exception:
        return None


# `executor.py` truncates every legislation search to this many results AFTER
# the post-filters run, then overwrites `total` with the truncated length. The
# cap is deliberate slimming; the overwrite is P1.3's defect. Any "results lost"
# figure that ignores the cap attributes ordinary truncation to the filters and
# overstates B2 several-fold — so every measure below is defined against it.
RESULT_CAP = 5


@dataclass
class FilterLoss:
    """One `search_legislation` call, counted on both sides of the filters."""

    query: str
    api_total: int | None
    api_returned: int | None
    tool_returned: int | None
    tool_total: int | None

    @property
    def measurable(self) -> bool:
        return self.api_returned is not None and self.tool_returned is not None

    @property
    def wiped_out(self) -> bool:
        """The API found results and the model was shown none.

        Unambiguous: the cap cannot produce an empty list from a non-empty one,
        so zero out of non-zero is the filters removing everything.
        """
        return bool(self.api_returned) and self.tool_returned == 0

    @property
    def filters_bit(self) -> bool:
        """The filters demonstrably removed results.

        True when the API returned at least `RESULT_CAP` rows but the model saw
        fewer — with no filtering the cap alone would have delivered exactly
        `RESULT_CAP`. A call that returns exactly `RESULT_CAP` is cap-bound and
        says nothing either way, which is why it is not counted.
        """
        return (
            self.measurable
            and self.api_returned >= RESULT_CAP
            and self.tool_returned < RESULT_CAP
        )

    @property
    def rows_lost_min(self) -> int:
        """Lower bound on rows the filters removed, net of the cap.

        The API is asked for 20 and the model may see at most `RESULT_CAP`, so
        only the shortfall below the cap is attributable to filtering. This
        understates the true loss (rows beyond the cap that the filters also
        removed are invisible) and is reported as a floor, never a total.
        """
        if not self.measurable:
            return 0
        return max(0, min(self.api_returned, RESULT_CAP) - self.tool_returned)

    @property
    def total_misreported(self) -> bool:
        """The API's real match count did not survive to the model.

        P1.3: `slimmed["total"] = len(results)` after truncation, so the model
        is told "5 matched" when the API said 189 — it cannot distinguish a
        genuinely narrow result set from a wide one it was shown the top of.
        """
        return (
            self.api_total is not None
            and self.tool_total is not None
            and self.api_total != self.tool_total
        )


@dataclass
class BadLink:
    label: str
    url: str
    expected_segment: str


@dataclass
class RunSignals:
    session_id: str
    rep: int
    verdict: str
    primary: str
    secondary: list
    diag: str
    filters: dict
    model_mismatch: list
    total_cost_usd: float
    elapsed_s: float

    turns: int = 0
    turns_errored: int = 0
    turns_empty_answer: int = 0
    turns_billed_but_empty: int = 0  # P4.2's acceptance condition
    turns_needing_clarification: int = 0

    halt_in_worker_report: int = 0  # B1, at source
    halt_language_in_answer: int = 0  # B1, as the lawyer sees it
    # B1, the case nobody named: a worker halted, the answer is non-empty, and it
    # says nothing about it. Invariant 1 requires a disclosure to be TRUE; no
    # disclosure at all is the worse failure, because the lawyer has no signal
    # that the answer is incomplete. 3 turns in the Wave 0 baseline.
    halts_undisclosed: int = 0
    # P2.1's conditions (2) and (3), separated from "was it disclosed at all".
    # A halt can be disclosed and still be disclosed WRONGLY: 6340 told the
    # lawyer the agent "exceeded its operational limits (timed out)" — it hit a
    # step cap, and a timeout implies retrying might work.
    halt_raw_marker_in_answer: int = 0
    halt_called_a_timeout: int = 0

    filter_losses: list = field(default_factory=list)
    searches: int = 0
    searches_wiped_out: int = 0
    searches_filters_bit: int = 0
    searches_total_misreported: int = 0
    rows_lost_min: int = 0

    bare_negatives: int = 0  # B5: a not-found with no explanation
    explained_negatives: int = 0
    in_force_claims: int = 0  # B4
    scots_gap_disclosures: int = 0  # B12
    bad_links: list = field(default_factory=list)  # B14
    total_links: int = 0
    # B14's real question, and the one `bad_links` cannot answer: where did this
    # provision URL come from? A manufactured URL resolves to a real page, so it
    # reads as a verified citation and is not — more dangerous than a link that
    # merely misses its provision.
    #
    # THREE outcomes, not two. ~~Two: in `final_result` or manufactured.~~
    # **Corrected 2026-09-15 during P1.6 — the ninth instrument trap, and it was
    # reading a third of the answer.** `final_result` is the summarised text when
    # summarisation fired, and 70% of section searches are summarised, so a URL
    # the retrieval genuinely returned survives only in `raw_result`. Scoring
    # against `final_result` alone called every one of those manufactured:
    #
    #   * `shown`         — the URL was in the text the model was handed. Copied.
    #   * `reconstructed` — the tool returned it but the summariser dropped it, so
    #     the model rebuilt it. Substantiated (the provision WAS retrieved) but
    #     built by guessing, which is the mechanism P1.4 removed the instruction
    #     for. This is what P1.6's citation-URL block closes.
    #   * `manufactured`  — no tool returned it anywhere. The provision was never
    #     retrieved and the citation is unsupported. The real defect.
    #
    # Measured over the whole corpus (all reps), Wave 0 -> Wave 1:
    # shown 7 -> 110, reconstructed 447 -> 26, **manufactured 75 -> 0**.
    # The previously published "327/327 (100%) -> 26/136 (19%)" conflated the
    # last two and so understated what P1.4 achieved.
    provision_links: int = 0
    provision_links_manufactured: int = 0
    provision_links_reconstructed: int = 0
    sources_kept: int = 0
    sources_unused: int = 0  # B8: kept but not textually cited
    turns_source_fallback: int = 0  # B8: rail showed an unvouched-for list
    tool_calls: Counter = field(default_factory=Counter)
    delegations: int = 0

    def as_row(self) -> dict:
        return {
            "session": self.session_id,
            "rep": self.rep,
            "verdict": self.verdict,
            "bucket": self.primary,
            "cost": round(self.total_cost_usd, 4),
            "mins": round(self.elapsed_s / 60, 1),
            "turns": self.turns,
            "empty": self.turns_empty_answer,
            "billed_empty": self.turns_billed_but_empty,
            "halt_src": self.halt_in_worker_report,
            "halt_ans": self.halt_language_in_answer,
            "searches": self.searches,
            "wiped": self.searches_wiped_out,
            "bit": self.searches_filters_bit,
            "lost>=": self.rows_lost_min,
            "bare_neg": self.bare_negatives,
            "inforce": self.in_force_claims,
            "bad_links": len(self.bad_links),
            "links": self.total_links,
            "src_unused": self.sources_unused,
            "src_kept": self.sources_kept,
            "src_fallbk": self.turns_source_fallback,
        }


def _source_cited(src: dict, text: str) -> bool:
    """Whether a source is *textually cited* in the answer.

    This mirrors the token branch of `agent_core._source_is_used` exactly —
    same tokens, same >=6-char floor, same substring test — and deliberately
    omits its `excerpt` branch. That omission is the whole point.

    `audit["sources"]` is the ALREADY-FILTERED `kept` list, so re-running the
    full `_source_is_used` over it would return True for everything and measure
    nothing. A source kept solely because it carried an excerpt is one the
    Worker retrieved and the answer never mentioned — "consulted, not cited",
    which is the distinction P4.3 exists to surface. Note `_lid` is stripped
    from the audit payload (the `_`-prefix filter at agent_core.py:267), so
    `cite` does the work it would otherwise do: for legislation that is the
    bare id (`asp/2009/12`), which appears inside any provision URL built from
    it (`.../asp/2009/12/section/35`).
    """
    for tok in (src.get("url"), src.get("cite"), src.get("sub")):
        if tok and len(str(tok)) >= 6 and str(tok) in text:
            return True
    return False


_PROVISION_URL = re.compile(r"/(?:section|regulation|article|schedule|rule)/")


_LEG_URL_IN_TEXT = re.compile(r'https?://[^\s"<>)\]]*legislation\.gov\.uk[^\s"<>)\],]*', re.I)


def _walk_urls(obj, out: set) -> None:
    """Collect every legislation.gov.uk URL anywhere in a parsed tool result.

    Key-agnostic and recursive on purpose: the two LEX endpoints spell the
    identifier `url`, `uri` and `id`, and reading only `results[].url` missed
    `get_legislation_text`'s top-level one entirely.
    """
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str) and "legislation.gov.uk" in v.lower():
                out.add(_norm_leg_url(v))
            else:
                _walk_urls(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_urls(v, out)


def _norm_leg_url(url: str) -> str:
    """Reduce a legislation.gov.uk URL to a comparable key.

    Mirrors `src/utils/citation_links.normalise_leg_url` — the measurement and
    the enforcement must agree on what "the same URL" means, or one of them is
    lying. Four spellings are live at once: `http`/`https`, with and without
    `www.`, with and without the `/id/` segment (the two LEX endpoints differ),
    and with or without a trailing slash.
    """
    s = str(url or "").strip().rstrip(".,;:)]}'\"")
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.split("#", 1)[0].split("?", 1)[0]
    return s.replace("/id/", "/", 1).rstrip("/").lower()


def _urls_returned_by_tools(doc: dict) -> tuple:
    """(shown_to_model, returned_by_any_tool) — two sets, and the pair matters.

    `final_result` is what the model was actually handed; `raw_result` is what
    the tool returned before summarisation. They are the same string only when
    the result passed through unsummarised, and **70% of section searches are
    summarised** — the summary keeps the section numbers and drops every URL.

    Reading only `final_result` (what this function did until P1.6) scores a URL
    the retrieval genuinely returned as manufactured, because the model had to
    rebuild it from the Act's base URI. That is a real and fixable weakness, but
    it is not the same failure as citing a provision nothing ever retrieved, and
    collapsing them hid the second behind the first.
    """
    shown: set = set()
    returned: set = set()
    for t in doc.get("turns", []):
        for dg in (t.get("audit") or {}).get("delegations", []):
            for tl in dg.get("tools", []):
                # `shown` is scanned as TEXT, not parsed as JSON. A summarised
                # result is prose, and P1.6 appends the citation-URL block after
                # it — neither is JSON, so a parse-first reading would report the
                # fix as having changed nothing. The question here is literally
                # "was this string in front of the model".
                for u in _LEG_URL_IN_TEXT.findall(tl.get("final_result") or ""):
                    shown.add(_norm_leg_url(u))
                # `returned` stays structural: a URL sitting inside a quoted
                # section's *body text* is not a retrieval of that provision.
                _walk_urls(_json_or_none(tl.get("raw_result")), returned)
    returned |= shown
    return shown, returned


def analyse_run(doc: dict) -> RunSignals:
    sig = RunSignals(
        session_id=doc["session_id"],
        rep=doc.get("rep", 1),
        verdict=doc.get("verdict_at_prepilot", ""),
        primary=doc.get("primary_bucket", ""),
        secondary=doc.get("secondary_buckets", []),
        diag=doc.get("diag_at_prepilot", ""),
        filters={k: v for k, v in (doc.get("filters") or {}).items() if v},
        model_mismatch=doc.get("model_mismatch", []),
        total_cost_usd=doc.get("total_cost_usd", 0.0),
        elapsed_s=doc.get("elapsed_s", 0.0),
    )
    # Gathered once per run: a URL retrieved in turn 1 is legitimately cited in
    # turn 4, so provenance is a run-level question, not a per-turn one.
    shown_urls, tool_urls = _urls_returned_by_tools(doc)

    for t in doc.get("turns", []):
        sig.turns += 1
        answer = t.get("answer") or ""
        status = t.get("status")
        cost = (t.get("timing") or {}).get("total_cost_usd", 0.0) or 0.0

        if status == "error" or status == "http_error":
            sig.turns_errored += 1
        if status == "needs_clarification":
            sig.turns_needing_clarification += 1
            continue
        if not answer.strip():
            sig.turns_empty_answer += 1
            # The informative case: content was generated and lost downstream.
            if cost > 0:
                sig.turns_billed_but_empty += 1

        if HALT_PARAPHRASE.search(answer):
            sig.halt_language_in_answer += 1
        if HALT_LITERAL.search(answer):
            sig.halt_raw_marker_in_answer += 1
        if HALT_AS_TIMEOUT.search(answer):
            sig.halt_called_a_timeout += 1

        if NOT_FOUND.search(answer):
            if NEGATIVE_EXPLAINED.search(answer):
                sig.explained_negatives += 1
            else:
                sig.bare_negatives += 1
        if IN_FORCE_CLAIM.search(answer):
            sig.in_force_claims += 1
        if SCOTS_CASELAW_GAP.search(answer):
            sig.scots_gap_disclosures += 1

        for label, url in MD_LINK.findall(answer):
            sig.total_links += 1
            if _PROVISION_URL.search(url):
                sig.provision_links += 1
                key = _norm_leg_url(url)
                if key not in tool_urls:
                    sig.provision_links_manufactured += 1
                elif key not in shown_urls:
                    sig.provision_links_reconstructed += 1
            # Walk every candidate, not just the first: an instrument is routinely
            # cited by full title AND provision ("The X Regulations 2013,
            # regulation 2"), and the title matches first.
            for m in PROVISION_LABEL.finditer(label):
                kind = _LABEL_TO_PATH.get(m.group(1).lower())
                if not kind:
                    continue
                num = m.group(2)
                # `paragraph` has no stable legislation.gov.uk segment of its own
                # (it lives under a schedule), so it is not asserted on.
                if kind == "paragraph":
                    continue
                if _is_title_year(num):
                    continue
                if f"/{kind}/{num}" not in url:
                    sig.bad_links.append(BadLink(label, url, f"/{kind}/{num}"))
                break

        audit = t.get("audit") or {}
        sources = audit.get("sources") or []
        cited = sum(1 for s in sources if _source_cited(s, answer))
        sig.sources_kept += len(sources)
        sig.sources_unused += len(sources) - cited
        # `agent_core` falls back to the UNFILTERED accumulator when filtering
        # would have left nothing, so a turn citing none of its sources is
        # showing the rail a list no one vouched for. Counting those turns
        # separately keeps them from inflating the "consulted, not cited" rate,
        # which is a different condition with a different fix.
        if sources and cited == 0:
            sig.turns_source_fallback += 1

        # A halt is read from THREE places, because each one alone has a hole:
        #   * `delegations[].halted` — audit schema v2 (P2.1), the authoritative
        #     field, absent from every run file recorded before it existed;
        #   * the literal marker in a delegation report — what v1 runs have, and
        #     what P2.1 now removes from the report, so it cannot be relied on
        #     going forward either;
        #   * `timing.max_turns_halted` — the product's own counter, and the only
        #     one that catches a halt in the MANAGER's loop, which produces no
        #     delegation report at all (6383 turn 1).
        turn_halted = bool((t.get("timing") or {}).get("max_turns_halted"))
        for dg in audit.get("delegations", []):
            sig.delegations += 1
            if dg.get("halted") or HALT_LITERAL.search(dg.get("report") or ""):
                sig.halt_in_worker_report += 1
                turn_halted = True
            for tl in dg.get("tools", []):
                sig.tool_calls[tl["name"]] += 1
                if tl["name"] != "search_legislation":
                    continue
                sig.searches += 1
                out = _json_or_none(tl.get("final_result"))
                api_total = api_returned = None
                for ac in tl.get("api_calls", []):
                    resp = ac.get("response")
                    if isinstance(resp, dict) and "results" in resp:
                        api_total = resp.get("total")
                        api_returned = len(resp.get("results") or [])
                        break
                fl = FilterLoss(
                    query=str((tl.get("args") or {}).get("query", ""))[:120],
                    api_total=api_total,
                    api_returned=api_returned,
                    tool_returned=len(out.get("results") or [])
                    if isinstance(out, dict)
                    else None,
                    tool_total=out.get("total") if isinstance(out, dict) else None,
                )
                sig.filter_losses.append(fl)
                sig.rows_lost_min += fl.rows_lost_min
                if fl.wiped_out:
                    sig.searches_wiped_out += 1
                if fl.filters_bit:
                    sig.searches_filters_bit += 1
                if fl.total_misreported:
                    sig.searches_total_misreported += 1

        # A halt the lawyer was never told about. Scored per TURN and after every
        # delegation has been seen, and only where there is an answer it could
        # have been disclosed in — an empty body is B13, a different defect with
        # a different fix, and counting it here would double-book it.
        if turn_halted and answer.strip() and not HALT_PARAPHRASE.search(answer):
            sig.halts_undisclosed += 1

    return sig


def load_runs(directory: Path) -> list[dict]:
    docs = []
    for p in sorted(directory.glob("*.json")):
        try:
            docs.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[!] unreadable {p.name}: {e}", file=sys.stderr)
    return docs


# --- Commands ----------------------------------------------------------------


def cmd_summary(args) -> int:
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}", file=sys.stderr)
        return 1
    sigs = [analyse_run(d) for d in docs]

    hdr = [
        "session", "rep", "verdict", "bucket", "cost", "mins", "turns", "empty",
        "billed_empty", "halt_src", "halt_ans", "searches", "wiped",
        "bit", "lost>=", "bare_neg", "inforce", "bad_links", "links",
        "src_unused", "src_kept", "src_fallbk",
    ]
    widths = {h: max(len(h), 6) for h in hdr}
    rows = [s.as_row() for s in sigs]
    print("  ".join(h.ljust(widths[h]) for h in hdr))
    print("  ".join("-" * widths[h] for h in hdr))
    for r in rows:
        print("  ".join(str(r[h]).ljust(widths[h]) for h in hdr))

    print("\n--- Totals over", len(sigs), "run(s) ---")
    print(f"  spend                       ${sum(s.total_cost_usd for s in sigs):.2f}")
    print(f"  wall clock                  {sum(s.elapsed_s for s in sigs)/3600:.1f} h")
    print(f"  turns                       {sum(s.turns for s in sigs)}")
    print(f"  turns with an empty answer  {sum(s.turns_empty_answer for s in sigs)}")
    print(f"    of those, billed >$0      {sum(s.turns_billed_but_empty for s in sigs)}   <- P4.2 acceptance")
    print(f"  runs with a halted worker   {sum(1 for s in sigs if s.halt_in_worker_report)}")
    print(f"  runs with halt text shown   {sum(1 for s in sigs if s.halt_language_in_answer)}   <- B1 / P2.1")
    print(f"  turns halted with NO mention  {sum(s.halts_undisclosed for s in sigs)}   <- B1 / P2.1 (silent halt)")
    tot_s = sum(s.searches for s in sigs)
    tot_w = sum(s.searches_wiped_out for s in sigs)
    tot_b = sum(s.searches_filters_bit for s in sigs)
    print(f"  search_legislation calls    {tot_s}   (each capped to "
          f"{RESULT_CAP} results AFTER filtering, by design)")
    print(f"    filters removed EVERYTHING {tot_w}"
          f"{f'  ({100*tot_w/tot_s:.0f}%)' if tot_s else ''}   <- B2 / P1.1")
    print(f"    filters demonstrably bit  {tot_b}"
          f"{f'  ({100*tot_b/tot_s:.0f}%)' if tot_s else ''}")
    print(f"    rows lost to filters      >={sum(s.rows_lost_min for s in sigs)}"
          f"  (floor: loss beyond the cap is unobservable)")
    print(f"    real total not passed on  {sum(s.searches_total_misreported for s in sigs)}   <- B5 / P1.3")
    tl = sum(s.total_links for s in sigs)
    bl = sum(len(s.bad_links) for s in sigs)
    pl = sum(s.provision_links for s in sigs)
    pm = sum(s.provision_links_manufactured for s in sigs)
    pr = sum(s.provision_links_reconstructed for s in sigs)
    print(f"  provision URLs cited        {pl}, MANUFACTURED (no tool returned it) {pm}"
          f"{f'  ({100*pm/pl:.0f}%)' if pl else ''}   <- B14 / P1.4, the provenance question")
    print(f"    reconstructed (retrieved, but summarised away before the model saw it) {pr}"
          f"{f'  ({100*pr/pl:.0f}%)' if pl else ''}   <- B14 / P1.6")
    print(f"  provision links             {tl}, wrong granularity {bl}"
          f"{f'  ({100*bl/tl:.1f}%)' if tl else ''}   <- B14 / P1.4")
    print(f"  bare negatives              {sum(s.bare_negatives for s in sigs)}"
          f" (explained: {sum(s.explained_negatives for s in sigs)})   <- B5 / P2.2")
    print(f"  unsupported in-force claims {sum(s.in_force_claims for s in sigs)}   <- B4 / P2.5")
    sk = sum(s.sources_kept for s in sigs)
    su = sum(s.sources_unused for s in sigs)
    print(f"  sources kept                {sk}, consulted-not-cited {su}"
          f"{f'  ({100*su/sk:.0f}%)' if sk else ''}   <- B8 / P4.3")
    print(f"  turns citing NONE of their sources (rail fallback): "
          f"{sum(s.turns_source_fallback for s in sigs)}")
    mism = [s for s in sigs if s.model_mismatch]
    if mism:
        print(f"\n  [!] {len(mism)} run(s) on a model other than the pin: "
              f"{sorted({m for s in mism for m in s.model_mismatch})}")
    return 0


def cmd_session(args) -> int:
    docs = [d for d in load_runs(Path(args.dir)) if d["session_id"] == args.session]
    if not docs:
        print(f"No runs for session {args.session} in {args.dir}", file=sys.stderr)
        return 1
    for d in docs:
        s = analyse_run(d)
        print("=" * 78)
        print(f"{s.session_id} rep{s.rep}  {s.verdict}/{s.primary}  "
              f"${s.total_cost_usd:.4f}  {s.elapsed_s/60:.1f}min")
        print(f"pre-pilot diagnosis: {s.diag}")
        print(f"filters: {s.filters}")
        print(f"tools: {dict(s.tool_calls)}")
        if s.filter_losses:
            print("\nsearch_legislation, both sides of the filters:")
            for fl in s.filter_losses:
                flag = ("  <-- FILTERS REMOVED ALL" if fl.wiped_out
                        else "  <-- filters bit" if fl.filters_bit else "")
                print(f"  api total={fl.api_total} returned={fl.api_returned}"
                      f"  ->  model saw results={fl.tool_returned} total={fl.tool_total}"
                      f"{flag}   q={fl.query!r}")
        if s.bad_links:
            print("\nprovision links resolving to the wrong granularity:")
            for b in s.bad_links:
                print(f"  {b.label!r} -> {b.url}  (expected {b.expected_segment})")
        for t in d["turns"]:
            print(f"\n--- turn {t['turn']} [{t['chat_mode']}] {t['status']}  "
                  f"prepilot={t.get('prepilot')}")
            print(f"Q: {t['question'][:300]}")
            body = t["answer"] if args.full else t["answer"][:1200]
            print(f"A: {body}")
    return 0


def cmd_baseline(args) -> int:
    """Emit the deterministic half of BASELINE.md, per session, for a human to
    finish. The reproduce / does-not-reproduce verdict is deliberately left
    blank — it is a reading of the answer against the frozen diagnosis."""
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}", file=sys.stderr)
        return 1
    by: dict[str, list[RunSignals]] = {}
    for d in docs:
        by.setdefault(d["session_id"], []).append(analyse_run(d))

    print("| Session | Verdict | Bucket | Reps | Cost | Signals |")
    print("|---|---|---|---|---|---|")
    for sid in sorted(by):
        runs = by[sid]
        r0 = runs[0]
        notes = []
        if any(r.halt_language_in_answer for r in runs):
            notes.append(f"halt text shown in {sum(1 for r in runs if r.halt_language_in_answer)}/{len(runs)}")
        if any(r.searches_wiped_out for r in runs):
            w = sum(r.searches_wiped_out for r in runs)
            t = sum(r.searches for r in runs)
            d_ = sum(r.rows_lost_min for r in runs)
            notes.append(f"{w}/{t} searches emptied by filters (>={d_} rows lost)")
        if any(r.turns_billed_but_empty for r in runs):
            notes.append(f"billed-but-empty turns: {sum(r.turns_billed_but_empty for r in runs)}")
        if any(r.turns_empty_answer for r in runs):
            notes.append(f"empty answers: {sum(r.turns_empty_answer for r in runs)}")
        if any(r.bad_links for r in runs):
            notes.append(f"bad provision links: {sum(len(r.bad_links) for r in runs)}/{sum(r.total_links for r in runs)}")
        if any(r.bare_negatives for r in runs):
            notes.append(f"bare negatives: {sum(r.bare_negatives for r in runs)}")
        if any(r.in_force_claims for r in runs):
            notes.append(f"in-force claims: {sum(r.in_force_claims for r in runs)}")
        if any(r.sources_unused for r in runs):
            notes.append(f"unused sources: {sum(r.sources_unused for r in runs)}/{sum(r.sources_kept for r in runs)}")
        if any(r.turns_errored for r in runs):
            notes.append(f"errored turns: {sum(r.turns_errored for r in runs)}")
        if any(r.model_mismatch for r in runs):
            notes.append("MODEL MISMATCH")
        cost = sum(r.total_cost_usd for r in runs)
        print(f"| {sid} | {r0.verdict} | {r0.primary} | {len(runs)} | "
              f"${cost:.2f} | {'; '.join(notes) or 'none'} |")
    return 0


# --- Wave-over-wave comparison (FIX_PLAN P1.5 and every later re-baseline) ----

# The signals a wave-over-wave read actually turns on, with the row that owns
# each. Every one is summed from `analyse_run`; nothing here recomputes a metric,
# so the single definition of "wiped out" or "bad link" stays in one tested place.
_COMPARE_METRICS: list[tuple[str, str, str]] = [
    ("searches", "search_legislation calls", ""),
    ("searches_wiped_out", "  filters removed EVERYTHING", "B2/P1.1"),
    ("searches_filters_bit", "  filters demonstrably bit", "B2/P1.1"),
    ("rows_lost_min", "  rows lost to filters (floor)", "B2/P1.1"),
    ("searches_total_misreported", "  real total not passed on", "B5/P1.3"),
    ("total_links", "provision links seen", ""),
    ("provision_links", "provision URLs cited", ""),
    ("provision_links_manufactured", "  MANUFACTURED (never retrieved)", "B14/P1.4"),
    ("provision_links_reconstructed", "  reconstructed (summarised away)", "B14/P1.6"),
    ("n_bad_links", "  wrong granularity", "B14/P1.4"),
    ("halt_runs", "runs with a halted worker", "B1/P2.1"),
    ("halt_answer_runs", "runs with halt text shown", "B1/P2.1"),
    ("halts_undisclosed", "  turns halted with NO mention", "B1/P2.1"),
    ("in_force_claims", "unsupported in-force claims", "B4/P2.5"),
    ("bare_negatives", "bare negatives", "B5/P2.2"),
    ("explained_negatives", "  (explained negatives)", ""),
    ("sources_kept", "sources kept", "B8/P4.3"),
    ("sources_unused", "  consulted, not cited", "B8/P4.3"),
    ("turns_source_fallback", "  turns citing none of theirs", "B8/P4.3"),
    ("turns_empty_answer", "turns with an empty answer", "B13/P4.2"),
    ("turns_billed_but_empty", "  of those, billed >$0", "B13/P4.2"),
    ("turns_needing_clarification", "turns that asked for clarification", ""),
    ("turns_errored", "errored turns", ""),
    ("delegations", "worker delegations", ""),
]


def _agg(sigs: list[RunSignals]) -> dict:
    """Sum one directory's signals. `halt_runs` counts RUNS, not occurrences —
    a run that halts twice is still one run that halted, which is how BASELINE.md
    states it."""
    out = {
        "runs": len(sigs),
        "turns": sum(s.turns for s in sigs),
        "cost": sum(s.total_cost_usd for s in sigs),
        "hours": sum(s.elapsed_s for s in sigs) / 3600,
        "n_bad_links": sum(len(s.bad_links) for s in sigs),
        "halt_runs": sum(1 for s in sigs if s.halt_in_worker_report),
        "halt_answer_runs": sum(1 for s in sigs if s.halt_language_in_answer),
    }
    for f in (
        "searches", "searches_wiped_out", "searches_filters_bit",
        "searches_total_misreported", "rows_lost_min", "total_links",
        "in_force_claims", "bare_negatives", "explained_negatives",
        "sources_kept", "sources_unused", "turns_source_fallback",
        "turns_empty_answer", "turns_billed_but_empty",
        "turns_needing_clarification", "turns_errored", "delegations",
        "halts_undisclosed", "provision_links", "provision_links_manufactured",
        "provision_links_reconstructed",
    ):
        out[f] = sum(getattr(s, f) for s in sigs)
    return out


def _delta(before: float, after: float) -> str:
    if before == after:
        return "="
    if before == 0:
        return f"+{after:g} (new)"
    pct = 100.0 * (after - before) / before
    return f"{after - before:+g} ({pct:+.0f}%)"


def cmd_compare(args) -> int:
    """Two replay directories, the same sessions, side by side.

    **The denominators must match or every number lies.** A targeted-n=3
    baseline holds more run files than a fresh n=1 sweep (65 against 41 for
    Wave 0), so comparing whole directories measures the extra repetitions, not
    the change. This restricts BOTH sides to rep 1 by default, which is the
    comparison BASELINE.md's published totals were computed on.
    """
    before_docs = load_runs(Path(args.before))
    after_docs = load_runs(Path(args.after))
    if not before_docs or not after_docs:
        print("Need run files in both --before and --after", file=sys.stderr)
        return 1

    if not args.all_reps:
        before_docs = [d for d in before_docs if d.get("rep", 1) == 1]
        after_docs = [d for d in after_docs if d.get("rep", 1) == 1]

    b_sigs = [analyse_run(d) for d in before_docs]
    a_sigs = [analyse_run(d) for d in after_docs]

    b_ids = {s.session_id for s in b_sigs}
    a_ids = {s.session_id for s in a_sigs}
    only_b, only_a = sorted(b_ids - a_ids), sorted(a_ids - b_ids)

    scope = "rep 1 only (like for like)" if not args.all_reps else "ALL reps"
    print(f"BEFORE  {args.before}")
    print(f"AFTER   {args.after}")
    print(f"Scope:  {scope} — {len(b_sigs)} vs {len(a_sigs)} run(s); totals over the "
          f"{len(b_ids & a_ids)} session(s) in common")
    if only_b:
        print(f"  [!] only in BEFORE: {', '.join(only_b)}")
    if only_a:
        print(f"  [!] only in AFTER:  {', '.join(only_a)}")
    mism = sorted({m for s in a_sigs for m in s.model_mismatch})
    if mism:
        print(f"  [!] AFTER ran on a model other than the pin: {mism}")

    # Totals over the sessions present on BOTH sides only. A sweep that skipped
    # or failed a session would otherwise shrink the "after" denominator and make
    # every metric look better by exactly the amount that went missing — the same
    # class of error as counting a targeted-n=3 baseline against an n=1 sweep.
    common = b_ids & a_ids
    b, a = (_agg([s for s in b_sigs if s.session_id in common]),
            _agg([s for s in a_sigs if s.session_id in common]))
    print()
    print(f"{'':44}{'before':>10}{'after':>10}   change")
    print("-" * 82)
    print(f"{'runs / turns':44}{str(b['runs']) + '/' + str(b['turns']):>10}"
          f"{str(a['runs']) + '/' + str(a['turns']):>10}")
    print(f"{'spend':44}{'$' + format(b['cost'], '.2f'):>10}"
          f"{'$' + format(a['cost'], '.2f'):>10}   {_delta(b['cost'], a['cost'])}")
    print(f"{'wall clock (h)':44}{b['hours']:>10.1f}{a['hours']:>10.1f}")
    print()
    for key, label, row in _COMPARE_METRICS:
        tag = f"  <- {row}" if row else ""
        print(f"{label:44}{b[key]:>10}{a[key]:>10}   "
              f"{_delta(b[key], a[key])}{tag}")

    # Per session, so a headline that moves for the wrong reason is visible.
    print()
    print("--- per session (before -> after) ---")
    print(f"{'sess':6}{'bkt':5}{'wiped/searches':>18}{'badlinks/links':>16}"
          f"{'halt':>10}{'inforce':>11}{'empty':>9}{'cost':>16}")
    by_b = {s.session_id: s for s in b_sigs}
    by_a = {s.session_id: s for s in a_sigs}
    for sid in sorted(b_ids & a_ids):
        sb, sa = by_b[sid], by_a[sid]
        print(
            f"{sid:6}{sb.primary:5}"
            f"{f'{sb.searches_wiped_out}/{sb.searches}->{sa.searches_wiped_out}/{sa.searches}':>18}"
            f"{f'{len(sb.bad_links)}/{sb.total_links}->{len(sa.bad_links)}/{sa.total_links}':>16}"
            f"{f'{sb.halt_in_worker_report}->{sa.halt_in_worker_report}':>10}"
            f"{f'{sb.in_force_claims}->{sa.in_force_claims}':>11}"
            f"{f'{sb.turns_empty_answer}->{sa.turns_empty_answer}':>9}"
            f"{f'${sb.total_cost_usd:.2f}->${sa.total_cost_usd:.2f}':>16}"
        )
    return 0


def cmd_halts(args) -> int:
    """P2.1's acceptance, run over a replay directory.

    Four of the five conditions are mechanical and are checked here per TURN;
    the fifth — "no invented cause" — is a reading of the prose and is left to a
    person, with the answer printed so they can do it. Printing per turn rather
    than per run matters: a session's failure lives in one turn of four, and a
    run-level total hides which.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.1 acceptance over {args.dir}")
    print()
    print(f"{'session':>8} {'rep':>3} {'turn':>4} {'halted':>6} "
          f"{'discl':>5} {'raw':>4} {'timeout':>7} {'meta':>4}  verdict")
    print("-" * 78)
    bad = 0
    halted_turns = 0
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for t in doc.get("turns", []):
            audit = t.get("audit") or {}
            dgs = audit.get("delegations", [])
            meta = any(dg.get("halted") for dg in dgs)
            halted = bool((t.get("timing") or {}).get("max_turns_halted")) or meta or any(
                HALT_LITERAL.search(dg.get("report") or "") for dg in dgs)
            if not halted:
                continue
            halted_turns += 1
            answer = t.get("answer") or ""
            disclosed = bool(HALT_PARAPHRASE.search(answer))
            raw = bool(HALT_LITERAL.search(answer))
            timeout = bool(HALT_AS_TIMEOUT.search(answer))
            # (5) is satisfied by the audit field OR, on a Manager-loop halt
            # where there is no delegation at all, by the request-level counter.
            meta_ok = meta or not dgs
            ok = disclosed and not raw and not timeout and meta_ok
            bad += 0 if ok else 1
            print(f"{doc['session_id']:>8} {doc.get('rep',1):>3} {t['turn']:>4} "
                  f"{'yes':>6} {('yes' if disclosed else 'NO'):>5} "
                  f"{('YES' if raw else '-'):>4} {('YES' if timeout else '-'):>7} "
                  f"{('yes' if meta_ok else 'NO'):>4}  {'PASS' if ok else 'FAIL'}")
    print()
    print(f"{halted_turns} halted turn(s); {bad} failing.")
    if args.answers:
        for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
            for t in doc.get("turns", []):
                if not bool((t.get("timing") or {}).get("max_turns_halted")):
                    continue
                print()
                print(f"=== {doc['session_id']} rep{doc.get('rep',1)} "
                      f"turn {t['turn']} ===")
                print((t.get("answer") or "")[: args.chars])
    return 0 if bad == 0 else 1


def _turn_queries(turn: dict) -> list:
    """Every search query this turn actually ran, in order, deduped.

    Read from the trace rather than inferred from the answer: "what was searched"
    is a fact about the run, and the whole point of the row is that the answer
    was not saying it.
    """
    out: list = []
    for dg in (turn.get("audit") or {}).get("delegations", []):
        for tl in dg.get("tools", []):
            if tl.get("name") not in ("search_legislation",
                                      "search_legislation_sections",
                                      "search_case_law"):
                continue
            q = str((tl.get("args") or {}).get("query") or "").strip()
            if q and q not in out:
                out.append(q)
    return out


# P2.2's code-emitted lawyer-facing footer (`answer_scope_footer`). Stripped
# before the MODEL column is graded — otherwise the footer satisfies the
# conditions on every answer and the report stops being able to say whether the
# model itself complied. The verdict column is graded on the WHOLE answer, since
# what reaches the lawyer is what matters; the model column is the honest
# measure of the instruction half, and both are printed.
ANSWER_FOOTER = re.compile(r"\n*\*Search scope:.*?\*\s*$", re.I | re.S)


def _without_footer(answer: str) -> str:
    return ANSWER_FOOTER.sub("", answer or "").strip()


def _filters_could_bite(doc: dict, turn: dict) -> bool:
    """Was a filter in force that could actually have excluded material?

    **This distinction was missing from the first version of the acceptance and
    it was grading against something the row does not ask for.** The row requires
    a negative to state "what was searched, under which filters"; where no filter
    was set there are no filters to state, and demanding the model recite an
    inert one is demanding noise. 6409 and 6367 both ran with
    `{year_to: 2026, current_only: true}` — `current_only` no longer exists in
    the product (P1.2 removed it) and a 2026 upper bound excluded nothing in
    September 2026. So `limits` is reported as n/a for those turns rather than
    failed.

    Biting means: a jurisdiction or legislation_type filter, a lower year bound,
    or an observed `removed_by_filters` on any search in the turn.
    """
    f = doc.get("filters") or {}
    if f.get("jurisdiction") or f.get("legislation_type") or f.get("year_from"):
        return True
    for dg in (turn.get("audit") or {}).get("delegations", []):
        for tl in dg.get("tools", []):
            out = _json_or_none(tl.get("final_result"))
            if isinstance(out, dict) and (out.get("removed_by_filters") or 0) > 0:
                return True
    return False


def cmd_negatives(args) -> int:
    """P2.2's acceptance, run over a replay directory, graded per TURN.

    Per-turn and not per-session, for the reason P2.1's sweep established the
    hard way: which turn carries the failure moves between reps (6383's halt
    moved from turn 1 to turn 4; 6384 stopped halting altogether). Grading a
    named session asks a stochastic question.

    **Invariant 1 is the whole point of the output shape.** A turn that asserts
    no negative at all is not a pass — it is not in the denominator. This command
    cannot be satisfied by answering more; only by explaining better.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.2 acceptance over {args.dir}")
    print("  terms  = the answer says what was searched for")
    print("  limits = it names a filter, a window, or that the search was ranked")
    print("           (n/a where no filter in force could have excluded anything)")
    print("  index  = the miss is attributed to the index/search …")
    print("  USER   = … rather than to the lawyer's citation (a FAIL on its own)")
    print("  model  = the same three, graded on the model's prose with P2.2's")
    print("           code-emitted footer stripped off")
    print()
    # The search-shape numbers BASELINE.md's B5 section quotes. Printed here
    # rather than left to a throwaway script, because they are the numbers that
    # decided this row's design — the zero-result branch it was written against
    # fires on 4 of 790 searches, while 783 of 783 are windowed — and a number
    # with no command behind it cannot be checked by the next session.
    import statistics
    shape = {"searches": 0, "zero": 0, "windowed": 0, "measurable": 0}
    matched_counts = []
    for doc in docs:
        for t in doc.get("turns", []):
            for dg in (t.get("audit") or {}).get("delegations", []):
                for tl in dg.get("tools", []):
                    if tl.get("name") != "search_legislation":
                        continue
                    shape["searches"] += 1
                    out = _json_or_none(tl.get("final_result"))
                    if not isinstance(out, dict):
                        continue
                    res = out.get("results")
                    shown = len(res) if isinstance(res, list) else out.get("returned")
                    total = out.get("total_matched")
                    if not isinstance(total, int):
                        total = out.get("total") if isinstance(out.get("total"), int) else None
                    if shown == 0:
                        shape["zero"] += 1
                    if isinstance(shown, int) and isinstance(total, int):
                        shape["measurable"] += 1
                        matched_counts.append(total)
                        if total > shown:
                            shape["windowed"] += 1
    if shape["searches"]:
        med = statistics.median(matched_counts) if matched_counts else 0
        p90 = sorted(matched_counts)[int(len(matched_counts) * 0.9)] if matched_counts else 0
        print(f"Search shape: {shape['searches']} search_legislation call(s); "
              f"{shape['zero']} returned ZERO results; "
              f"{shape['windowed']}/{shape['measurable']} measurable were WINDOWED "
              f"(median {med:.0f} candidates ranked, p90 {p90}, max "
              f"{max(matched_counts) if matched_counts else 0}).")
        print("  A windowed search shows the top few of a ranked list, so absence")
        print("  from it is not absence from the corpus. That is what B5's")
        print("  negatives were drawn from.")
        print()

    print(f"{'session':>8} {'rep':>3} {'turn':>4} {'queries':>7} "
          f"{'terms':>5} {'limits':>6} {'index':>5} {'USER':>4} {'loose':>5} "
          f"{'model':>5}  verdict")
    print("-" * 90)
    neg_turns = 0
    bad = 0
    rows = []
    model_turns: list = []
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for t in doc.get("turns", []):
            answer = t.get("answer") or ""
            # **The denominator is selected on the MODEL's prose, not on the
            # whole answer — and getting this wrong was the twelfth instrument
            # error on this work, the first caused by the product change it was
            # measuring.** P2.2's own footer says "anything reported above as
            # not found was not found in this index", which trips
            # `NEG_ASSERTED`. Selecting on the full answer therefore enrolled
            # every researched turn, including purely positive ones: the count
            # went 23 -> 34 and the model column fell 52% -> 14%, because the
            # added turns had no negative to explain. Whether a negative was
            # asserted is a fact about what the model wrote.
            bare = _without_footer(answer)
            if not answer.strip() or not NEG_ASSERTED.search(bare):
                continue
            neg_turns += 1
            queries = _turn_queries(t)
            terms = _names_search_terms(answer)
            biting = _filters_could_bite(doc, t)
            limits = bool(NEG_LIMITS.search(answer))
            index = bool(NEG_BLAMED_INDEX.search(answer))
            user = bool(NEG_BLAMED_USER.search(answer))
            loose = bool(NEGATIVE_EXPLAINED.search(answer))
            ok = terms and index and not user and (limits or not biting)
            # The same three conditions against the model's own prose only.
            model_ok = (
                _names_search_terms(bare)
                and bool(NEG_BLAMED_INDEX.search(bare))
                and not bool(NEG_BLAMED_USER.search(bare))
                and (bool(NEG_LIMITS.search(bare)) or not biting)
            )
            model_turns.append(model_ok)
            bad += 0 if ok else 1
            rows.append((doc, t, ok))
            lim_cell = ("yes" if limits else "NO") if biting else (
                "yes" if limits else "n/a")
            print(f"{doc['session_id']:>8} {doc.get('rep',1):>3} {t['turn']:>4} "
                  f"{len(queries):>7} {('yes' if terms else 'NO'):>5} "
                  f"{lim_cell:>6} {('yes' if index else 'NO'):>5} "
                  f"{('YES' if user else '-'):>4} {('yes' if loose else 'no'):>5}  "
                  f"{('yes' if model_ok else 'no'):>5}  "
                  f"{'PASS' if ok else 'FAIL'}")
    print()
    print(f"{neg_turns} turn(s) asserting a negative; {bad} failing.")
    if model_turns:
        mo = sum(model_turns)
        print(f"Of those, {mo} ({100 * mo // len(model_turns)}%) are explained by the "
              f"MODEL's own prose, with the code-emitted footer removed. That is the "
              f"number that measures the instruction half;\n      the verdict "
              f"column measures what the lawyer actually sees.")
    print("NOTE: a turn that asserts no negative is NOT in this denominator. "
          "Under Invariant 1\n      this test cannot be passed by answering more, "
          "only by explaining better.")
    if args.answers:
        for doc, t, ok in rows:
            if args.failing_only and ok:
                continue
            print()
            print(f"=== {doc['session_id']} rep{doc.get('rep',1)} turn {t['turn']} "
                  f"({'PASS' if ok else 'FAIL'}) ===")
            print("queries run:")
            for q in _turn_queries(t):
                print(f"    {q[:150]}")
            print("filters:", {k: v for k, v in (doc.get("filters") or {}).items() if v})
            print((t.get("answer") or "")[: args.chars])
    return 0 if bad == 0 else 1


# --- P2.3 (B3b) acceptance ---------------------------------------------------
#
# *"SSI X was made under section 91"* is the B3 claim. *"Under section 91 of the
# Act, Ministers must consult"* is correct legal writing about a retrieved
# provision. **A detector that cannot tell them apart grades correct writing as a
# defect and pushes the model to hedge what it retrieved** — the regression
# Invariant 1 exists to prevent, and precisely how P2.2's first `NEG_ASSERTED`
# failed (61 of 153 turns, 100% failing).
#
# So a derivation needs THREE things in one sentence, and neither negation nor
# pure modality:
#     (1) an instrument reference,
#     (2) a derivation predicate,
#     (3) the provision or Act it is said to derive from.
#
# **Two drafts were artefacts and are recorded rather than quietly replaced.**
# Draft 1 scored **69 of 155 turns** on two bugs: a regex alternation that
# reduced to a bare `\bis` (`r"\bis|are|was|were\s+enabled by"` — the alternation
# binds looser than the concatenation), and an instrument screen so loose that
# the bare word "regulations" satisfied it. Draft 2 over-corrected to 1 turn by
# compiling the instrument screen case-SENSITIVELY, which missed the heaviest
# claim in the corpus because it opens "Several SSIs ...".
#
# **Validated in both directions on real answers.** Over the post-Wave-1 corpus
# it counts 12 turns and drops 21 sentences carrying the same vocabulary; all 21
# drops were read and all 21 are correct — negatives ("no SSIs made under s.95
# were found"), statements of law about a class ("regulations made under s.95
# are subject to the affirmative procedure"), the Act's own power-conferring
# provision ("section 27(2) provides the enabling power"), a restatement of the
# user's query, and — the one that matters most — 6383 t2's *"the agent could
# not retrieve the preamble to definitively confirm if it was made under section
# 95"*, which is the exactly right answer and must never be graded as a defect.
# Reproduce the drop set with `--drops`.
_DERIV_TITLE = re.compile(
    r"(?:The\s+)?[A-Z][A-Za-z0-9'’—\-,.&/() ]{6,160}?"
    r"\s(?:Regulations|Rules|Order|Orders|Scheme)\s+\d{4}")
_DERIV_NUMBERED = re.compile(
    r"(?:S\.?S\.?I\.?|S\.?I\.?)\s*\d{4}[/ ]\d+|(?:ssi|uksi|nisr|wsi|ssr)/\d{4}/\d+",
    re.I)
_DERIV_DEICTIC = re.compile(
    r"\bthis instrument\b|\bthese Regulations\b|\bthese Rules\b|\bthis Order\b"
    r"|\bthis SSI\b|\bthis SI\b|\bthe \d{4} (?:Regulations|Order|Rules)\b", re.I)
# Indefinite but quantified — "several SSIs", "multiple Scottish Statutory
# Instruments" — still a claim about real instruments. The gap admits bracketed
# words because of "several Scottish Administration (Offices) Orders".
_DERIV_QUANTIFIED = re.compile(
    r"\b(?:several|multiple|various|numerous|a number of|the following|both|"
    r"two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:[\w()'’\-]+\s+){0,5}?"
    r"(?:SSIs?|SIs?|instruments?|regulations?|orders?|rules?)\b"
    # A numeral counts too — 6383 rep 2 t4's *"Over 130 instruments explicitly
    # cite section 95 in their preamble"* is the single largest unverifiable
    # claim in the corpus. But a bare `\d+` with a wide gap is what made draft 1
    # read "Paragraph 1 specifies that an Order made under section 126(8) …" as
    # a claim, so the numeral must sit next to the noun it counts.
    # An explicit "over 130" can sit further from its noun ("over 130 Scottish
    # Statutory Instruments"), so the modifier buys a wider gap; a BARE numeral
    # must be adjacent.
    r"|\b(?:over|more than|at least|around|approximately|some)\s+\d+\s+"
    r"(?:[\w'’\-]+\s+){0,3}?"
    r"(?:SSIs?|SIs?|instruments?|regulations?|orders?|rules?)\b"
    r"|\b\d+\s+(?:[\w'’\-]+\s+){0,1}?"
    r"(?:SSIs?|SIs?|instruments?|regulations?|orders?|rules?)\b", re.I)
# A finite predicate asserts derivation of its subject.
_DERIV_FINITE = re.compile(
    r"\b(?:was|were|is|are|has been|have been|had been)\s+"
    r"(?:\w+\s+){0,2}?made\s+(?:under|pursuant to|by virtue of|in exercise of)\b"
    r"|\b(?:was|were|is|are)\s+enabled\s+by\b"
    r"|\bcit(?:e|es|ed|ing)\b[^.\n]{0,90}?\bas\s+(?:its|their|the)\s+"
    r"enabling\s+(?:power|powers|authority)"
    r"|\bcit(?:e|es|ed|ing)\s+(?:\w+\s+){0,2}?(?:section|sections|s\.|ss\.|"
    r"subsection)\s*\d"
    r"|\brel(?:y|ies|ied)\s+(?:on|upon)\s+(?:\w+\s+){0,2}?(?:section|s\.|"
    r"subsection)\s*\d"
    # 6374 t4 carries the derivation on a fronted adverbial, not a predicate:
    # "Pursuant to the enabling power in section 126(8), several ... Orders
    # have designated additional offices."
    r"|\b(?:pursuant to|under|by virtue of)\s+the\s+enabling\s+"
    r"(?:power|powers|authority)\b", re.I)
# A participial "X made under s.Y" is a NOUN PHRASE describing a class, not a
# claim — "regulations made under s.95 are subject to the affirmative
# procedure" is a statement of law read straight off s.96.
_DERIV_PARTICIPIAL = re.compile(
    r"\bmade\s+(?:under|pursuant to|by virtue of|in exercise of)\b"
    r"|\benabling\s+(?:power|authority)\s+(?:for|behind|of)\b", re.I)
_DERIV_SRC = re.compile(
    r"\b(?:section|sections|s\.|ss\.|subsection)\s*\d+"
    r"|\bthe\s+[A-Z][A-Za-z0-9'’()\-,. ]{4,120}?\bAct\s+\d{4}"
    r"|\b(?:this|that|the)\s+(?:enabling\s+)?(?:power|authority)\b"
    r"|\bthe\s+\d{4}\s+Act\b|\bthe\s+Act\b", re.I)
# The model presenting the class as something it found, which makes even a
# participial assertive: "here are two examples of other SSIs made under s.95:"
_DERIV_PRESENTED = re.compile(
    r"\bhere (?:are|is)\b|\bthese are\b|\bthe following\b|\bexamples? of\b"
    r"|\binclude[sd]?\b|\bidentified\b|\bwere found\b"
    # "Yes, there ARE over 130 SSIs made under section 95" — existential, and
    # the single largest unverifiable claim in the corpus. Found by reading the
    # `--drops` audit over wave2_p21, which is what that audit is for.
    r"|\bthere (?:are|is|were|was)\b", re.I)
# `\bno\b(?!\s*\.)` and not `\bno\b`, and this is the SAME trap a third time.
# "Commencement **No.** 1" is in the title of every commencement instrument in
# this corpus, so a bare `\bno\b` reads every derivation claim about one as
# negated and silently drops it — in the row whose whole job is to count them.
# SESSION_LOG records the trap for `NEG_BLAMED_INDEX` (a sentence window keyed
# on `.` cannot cross these titles) and again for the sentence splitter above.
_DERIV_NEG = re.compile(
    r"\bno\b(?!\s*\.)|\bnot\b|\bnone\b|\bnever\b|\bcannot\b|\bunable\b"
    r"|\bwithout\b|\bfail(?:s|ed)? to\b|\bnothing\b", re.I)
_DERIV_MODAL = re.compile(
    r"\b(?:may|must|can|could|would|shall|should|will|might)\b", re.I)
# Any sentence in the same vocabulary — the denominator for the `--drops` audit.
_DERIV_LOOSE = re.compile(
    r"\bmade under\b|\benabling (?:power|authority)\b|\benabled by\b"
    r"|\bpowers? conferred\b|\bin exercise of\b|\bpursuant to (?:section|s\.)"
    r"|\bmade (?:pursuant to|by virtue of|in exercise of)\b"
    r"|\bunder the (?:power|authority)\b", re.I)
# The instrument-preamble recital, as it arrives in `legislation.description`.
# Mirrors `search_scope._ENABLING_RECITAL`; kept separate because a tool must
# not import the product it is grading.
_DERIV_RECITAL = re.compile(
    r"in exercise of (?:the |his |her |their |its )?powers?"
    r"|powers? (?:in that behalf )?conferred (?:on|upon|by)"
    r"|by virtue of (?:the )?powers?"
    r"|makes? the following (?:Regulations|Order|Rules|Scheme)"
    r"|has determined under section", re.I)


# **Abbreviation dots, and this corpus is made of them.** SESSION_LOG records the
# trap once already — every commencement SSI's title contains "Commencement
# No. 1", so a sentence window keyed on `.` cannot cross the titles this work is
# about — and the derivation detector walked into the same wall from the other
# side. The very first acceptance run scored *"S.I. 1963/2111 was made under
# section 69(4) of the National Insurance Act 1946"* as no claim at all, because
# the splitter cut it into "For example, S.", "I.", "1963/2111 was made under
# …", and the fragment that kept the predicate had lost its instrument.
#
# So the dots inside an abbreviation are masked before splitting and restored
# after. `\b[A-Za-z]\.` covers the initial-style forms (S.I., S.S.I., s., r.)
# in one rule; the rest are the multi-letter legal abbreviations that end a
# token without ending a sentence.
_ABBREV = re.compile(
    r"\b(?:[A-Za-z]|No|Nos|ss|reg|regs|art|arts|para|paras|sch|sched|ch|cl|rr"
    r"|cf|etc|vs|approx|Sess)\.",
    re.I)
_DOT = "\x00"


def _sentences(text: str):
    for para in (text or "").split("\n"):
        masked = _ABBREV.sub(lambda m: m.group(0).replace(".", _DOT), para)
        for s in re.split(r"(?<=[.!?])\s+", masked):
            s = s.replace(_DOT, ".").strip()
            if s:
                yield s


def derivation_claims(answer: str) -> tuple:
    """(asserted, filtered) — sentences claiming a derivation, and near-misses."""
    asserted, filtered = [], []
    for s in _sentences(answer):
        if not _DERIV_SRC.search(s):
            continue
        specific = bool(_DERIV_TITLE.search(s) or _DERIV_NUMBERED.search(s)
                        or _DERIV_DEICTIC.search(s))
        if _DERIV_FINITE.search(s):
            ok = specific or bool(_DERIV_QUANTIFIED.search(s))
        elif _DERIV_PARTICIPIAL.search(s):
            ok = specific or (bool(_DERIV_PRESENTED.search(s))
                              and bool(_DERIV_QUANTIFIED.search(s)))
        else:
            continue
        if not ok:
            continue
        neg = bool(_DERIV_NEG.search(s))
        mod = bool(_DERIV_MODAL.search(s))
        (filtered if (neg or mod) else asserted).append(s)
    return asserted, filtered


# **A third route was built here, measured, and deleted — recorded so it is not
# rebuilt.** The row's wording permits a claim where "a retrieved preamble,
# provision or `description` states it", and the first acceptance run produced a
# case that looked like the middle one: 6374 said *"Both confirm the Orders are
# made under section 126(8)"*, and Scotland Act 1998 s.126(8) — retrieved —
# does say "any other office ... specified in an Order in Council made under
# this subsection".
#
# So a `retrieved_enabling_provision` screen was added for
# `made under this (subsection|section)` and its relatives. Measured over the
# before-column it fired on **11 of the 12 unverified turns**, which under this
# file's standing hazard makes it an artefact, and it is one: **generic
# regulation-making boilerplate appears in essentially every enabling Act**, so
# the signal is present whenever the parent Act was retrieved at all — which is
# always. It could not separate 6374's short sound inference from 6383's *"Over
# 130 instruments explicitly cite section 95 in their preamble"*.
#
# The finding is the useful part, and it narrows the ROW: **a provision states
# the class, never the instance.** "Orders in Council made under this subsection"
# does not establish that *this* Order was one. Only a preamble or a
# `description` names an individual instrument, so those are the only two routes
# that can support a claim about one.


def retrieved_enabling(turn: dict) -> list:
    """Instruments whose enabling-power recital this turn actually retrieved.

    Read from `raw_result`, because the recital lives in
    `legislation.description` and is the first thing a summariser drops.
    """
    out = []
    for dg in (turn.get("audit") or {}).get("delegations", []):
        for tl in dg.get("tools", []):
            o = _json_or_none(tl.get("raw_result"))
            if not isinstance(o, dict):
                continue
            cands = []
            leg = o.get("legislation")
            if isinstance(leg, dict):
                cands.append((str(leg.get("legislation_id")
                                  or (tl.get("args") or {}).get("legislation_id") or ""),
                              str(leg.get("description") or "")))
            for r in (o.get("results") or []):
                if isinstance(r, dict) and r.get("description"):
                    cands.append((str(r.get("legislation_id") or ""), str(r["description"])))
            for lid, descr in cands:
                if descr and _DERIV_RECITAL.search(descr) and lid not in [x[0] for x in out]:
                    out.append((lid, descr[:200]))
    return out


# P2.3's own clause on the lawyer-facing footer contains the words "made under"
# and "enabling power". `_without_footer` strips the whole trailing italic run,
# so the model column is clean — the check that this is so is
# `test_search_scope.py::test_footer_trips_no_detector`, because P2.2's footer
# corrupting P2.2's own denominator is the failure mode this line exists to
# avoid repeating.
def cmd_derivations(args) -> int:
    """P2.3's acceptance, over a replay directory, graded per TURN.

    Denominator: turns asserting that a named instrument was made under a
    provision. **A turn that makes no such claim is not in it** — as with P2.2,
    this test cannot be passed by saying less about the law, only by not
    claiming a derivation the retrieval never established.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.3 acceptance over {args.dir}")
    print("  A derivation claim = a named instrument + a derivation predicate +")
    print("  the provision it is said to derive from, not negated, not modal.")
    print("  Citing a provision ('under s.91, Ministers must ...') is NOT one.")
    print()

    if args.drops:
        n = 0
        for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
            for t in doc.get("turns", []):
                ans = _without_footer(t.get("answer") or "")
                a, f = derivation_claims(ans)
                kept = set(a) | set(f)
                for s in _sentences(ans):
                    if _DERIV_LOOSE.search(s) and s not in kept:
                        n += 1
                        print(f"  {doc['session_id']} t{t['turn']}: {s[:200]}")
        print()
        print(f"{n} sentence(s) in the same vocabulary NOT counted as a claim.")
        print("Read them: an under-read here forbids nothing, and an over-read")
        print("grades correct legal writing as a defect (Invariant 1).")
        return 0

    print(f"{'session':>8} {'rep':>3} {'turn':>4} {'claims':>6} {'preamble':>9}  verdict")
    print("-" * 74)
    turns = bad = 0
    total_turns = 0
    rows = []
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for t in doc.get("turns", []):
            answer = t.get("answer") or ""
            if answer.strip():
                total_turns += 1
            # Graded on the model's prose: P2.3's footer clause uses this
            # vocabulary, and a product change must not enrol turns into the
            # denominator of the instrument measuring it (P2.2, error 12).
            asserted, _ = derivation_claims(_without_footer(answer))
            if not asserted:
                continue
            turns += 1
            ret = retrieved_enabling(t)
            ok = bool(ret)
            if not ok:
                bad += 1
            rows.append((doc, t, asserted, ret, ok))
            print(f"{doc['session_id']:>8} {doc.get('rep', 1):>3} {t['turn']:>4} "
                  f"{len(asserted):>6} {len(ret):>9}  "
                  f"{'ok (preamble retrieved)' if ok else 'UNVERIFIED'}")
    print()
    claims_total = sum(len(r[2]) for r in rows)
    claims_bad = sum(len(r[2]) for r in rows if not r[4])
    print(f"{turns} of {total_turns} answered turn(s) assert a derivation "
          f"({claims_total} claim(s) in total); {bad} turn(s) and {claims_bad} "
          f"claim(s) with NO enabling-power text retrieved.")
    print("NOTE: a turn asserting no derivation is NOT in this denominator, and")
    print("      'could not verify what it was made under' is a PASS, not a miss.")
    if args.answers:
        for doc, t, asserted, ret, ok in rows:
            if args.failing_only and ok:
                continue
            print()
            print(f"=== {doc['session_id']} rep{doc.get('rep', 1)} turn {t['turn']} "
                  f"({'ok' if ok else 'UNVERIFIED'}) ===")
            print("question:", (t.get("question") or "")[:200])
            for s in asserted:
                print(f"   CLAIM > {s[:300]}")
            for lid, descr in ret:
                print(f"   RECITAL [{lid}]: {descr[:170]!r}")
    return 0 if bad == 0 else 1


# --- P3.5 (B3) acceptance ----------------------------------------------------
#
# **This row is graded against an external ground truth, and that is unusual
# here on purpose.** Every other acceptance in this plan grades what the answer
# says about its own limits; P3.5 grades whether a specific true fact reached
# the lawyer. It can, because the fact is small, checkable and independent of
# the model: `asp/2025/2` has eight provisions commenced by SSI and `asp/2025/9`
# has twenty, and both sessions were told "No commencement regulations have been
# made yet".
#
# Sampled live 2026-09-16; re-print with `python -m tools.lex_probe
# --commencement`, which emits these entries in exactly this shape so the next
# session can diff rather than trust. A constant nobody can re-derive is the
# failure this plan keeps recording.
COMMENCEMENT_TRUTH = {
    "6409": ("asp/2025/2", ["ssi/2025/119", "ssi/2025/377"]),
    "6410": ("asp/2025/9", ["ssi/2025/388"]),
    "6382": ("asp/2018/9", ["ssi/2018/250", "ssi/2018/298", "ssi/2018/357",
                            "ssi/2018/393", "ssi/2019/269", "ssi/2020/127",
                            "ssi/2020/295", "ssi/2020/75", "ssi/2021/474",
                            "ssi/2024/57"]),
    "6383": ("asp/2018/9", ["ssi/2018/250", "ssi/2018/298", "ssi/2018/357",
                            "ssi/2018/393", "ssi/2019/269", "ssi/2020/127",
                            "ssi/2020/295", "ssi/2020/75", "ssi/2021/474",
                            "ssi/2024/57"]),
}

# Is this sentence about commencement at all? The screen, not the verdict — a
# sentence has to be in this vocabulary before the denial test is applied to it.
_CMC_CONTEXT = re.compile(
    r"\bcommenc(?:e|ed|es|ement|ing)\b|\b(?:in|into) force\b"
    r"|\bappointed day\b",
    re.I,
)

# The denial, and **the discriminator is the NOUN, not the verb.**
#
# "The remaining provisions have not yet been brought into force" is TRUE of
# `asp/2025/2` — twenty of its twenty-eight sections are uncommenced — and
# grading it as a defect would push the model to hedge a correct statement,
# which is the regression Invariant 1 exists to prevent and exactly how P2.2's
# first `NEG_ASSERTED` failed at 100%. The defect is denying that a commencing
# INSTRUMENT exists, so the negated noun must be an instrument (regulations,
# orders, SSIs) and never a provision, section or Part.
#
# The second limb is the "not found" shape P2.2's fix produced — "no
# commencement regulations were found in the index". Post-P3.5 that is still a
# false negative when the change record holds one, and it is the shape the
# after-column is most likely to take, so it must be counted.
_CMC_DENIED = re.compile(
    r"\bno\b(?:\s+\w+){0,3}\s+"
    r"(?:regulations?|orders?|instruments?|s\.?s\.?i\.?s?|ssis?|sis?)\b"
    r"[^.\n]{0,40}?\b(?:have|has|had|were|was)\b[^.\n]{0,25}?\bbeen\b"
    # `found` and its relatives sit in this limb as well as the next one, and
    # that is a measured correction rather than belt and braces. Under P2.2 the
    # shape moved from "no commencement regulations have been MADE" to "...have
    # been FOUND" (6409 rep 1 turn 5, `wave2_p22_final`), which the first draft
    # of this limb missed entirely and scored as addressing commencement not at
    # all — an under-read in the before-column of the row that has to move it.
    r"[^.\n]{0,25}?\b(?:made|laid|enacted|issued|brought into force"
    r"|found|located|identified|retrieved|returned|recorded)\b"
    r"|\bno\b(?:\s+\w+){0,3}\s+"
    r"(?:regulations?|orders?|instruments?|s\.?s\.?i\.?s?|ssis?|sis?)\b"
    r"[^.\n]{0,40}?\b(?:were|was|are|is)\s+"
    r"(?:found|located|identified|retrieved|returned|in force|in existence)\b"
    r"|\bno\s+commencement\s+"
    r"(?:regulations?|orders?|instruments?|ssis?|sis?)\b"
    r"[^.\n]{0,40}?\b(?:exist|exists|could be found|are recorded|is recorded)\b",
    re.I,
)

# **A denial of the REMAINDER is not a denial of existence**, and the acceptance
# run is what forced the distinction. 6410 rep 2 turn 2 answered *"SSI 2025/388
# ... Based on the recorded changes to the Act, no further commencement
# regulations have been found"* — which is **true, sourced and exactly the answer
# the row exists to produce**: the change record holds precisely one commencing
# instrument. Grading it as the defect would punish the fix.
#
# **The exclusion is scoped to the noun phrase, and that is load-bearing rather
# than fussy.** `wave2_p22` 6409 rep 3 turn 6 says *"no commencement regulations
# bringing FURTHER sections into force were identified"* — the qualifier there
# attaches to *sections*, and the sentence is a flat denial that any commencing
# regulation was found. A bare `further` anywhere in the sentence would have
# dropped it, moving a BEFORE-column number to make the after-column look
# better. So the qualifier must sit immediately after "no", and the turn must
# also name a real instrument — a remainder is only a remainder of something.
_CMC_REMAINDER = re.compile(
    r"\bno\s+(?:further|subsequent|additional|other|more)\s+(?:\w+\s+){0,2}"
    r"(?:regulations?|orders?|instruments?|s\.?s\.?i\.?s?|ssis?|sis?)\b",
    re.I,
)

# **The denominator is structural, and picking it was the hard part.**
#
# The first draft graded every answered turn in a session with a known truth,
# and scored six of wave1's eighteen as `correct` — including 6409 turn 8, whose
# entire question is *"SSI 2025/119"*. Repeating back an instrument the LAWYER
# supplied is not a retrieved relation, and counting it would have shown a
# before-column that already half-passes. The same trap in the other direction
# would exclude the turns the row exists for.
#
# So a turn is in scope when its QUESTION asks about commencement and does not
# itself name one of the instruments being graded. That is 6409 turns 1-6 and
# 6410 turns 1-2 — exactly the turns that produced "No commencement regulations
# have been made yet" — and it is computed, not listed.
_CMC_QUESTION = re.compile(
    r"\bcommenc(?:e|ed|es|ement|ing)\b|\b(?:in|into) force\b"
    r"|\bappointed day\b|\bwhen did .{0,40}(?:come|came) into\b",
    re.I,
)


def _truth_for(session_id: str):
    return COMMENCEMENT_TRUTH.get(str(session_id))


def _names_instrument(text: str, instruments) -> list:
    """Which of these instruments the text actually names.

    Matched on the year/number pair rather than on the `ssi/2025/119` spelling,
    because a lawyer-facing answer writes "SSI 2025/119", "S.S.I. 2025 No. 119"
    or "the Commencement No. 1 Regulations 2025 (SSI 2025/119)". A bare
    `2025/119` is deliberately NOT enough — it would match a great deal that is
    not an instrument reference.
    """
    found = []
    for lid in instruments:
        parts = lid.split("/")
        if len(parts) != 3:
            continue
        series, year, num = parts
        pat = re.compile(
            r"\b" + series + "/" + year + "/" + num + r"\b"
            r"|\b(?:s\.?s\.?i\.?|s\.?i\.?)\.?\s*(?:No\.?\s*)?"
            + year + r"[/ ]\s*(?:No\.?\s*)?" + num + r"\b"
            r"|\b" + year + "/" + num + r"\s*\([Cc]\.",
            re.I,
        )
        if pat.search(text or ""):
            found.append(lid)
    return found


def _consulted_changes(turn: dict) -> list:
    """The change-record calls this turn made, and what each returned."""
    out = []
    for dg in (turn.get("audit") or {}).get("delegations", []):
        for tl in dg.get("tools", []):
            if tl.get("name") != "get_legislation_changes":
                continue
            o = _json_or_none(tl.get("raw_result"))
            named = []
            if isinstance(o, dict):
                for g in (o.get("related") or []):
                    if isinstance(g, dict) and not g.get("self") \
                            and g.get("legislation_id") \
                            and g["legislation_id"] not in named:
                        named.append(g["legislation_id"])
            out.append({
                "args": tl.get("args") or {},
                "relations": o.get("relations") if isinstance(o, dict) else None,
                "others": named,
            })
    return out


# A denial that names the reason the research fell short is a different thing
# from a denial about the law, and grading them the same would punish the
# behaviour three lawyers praised. Both detectors are P2.1's and P2.2's, reused
# rather than reinvented: a halt disclosure, or the index named as the thing
# that came up short.
def _denial_is_attributed(sentence: str) -> bool:
    return bool(HALT_PARAPHRASE.search(sentence)
                or NEG_BLAMED_INDEX.search(sentence))


def commencement_verdict(session_id: str, answer: str,
                         consulted_others=()) -> tuple:
    """(verdict, instruments_named, denial_sentences) for one in-scope turn.

    Five verdicts, and the separation of the last two is the whole care in this
    function:

      * ``"correct"`` — the answer names an instrument that really did commence
        provisions of the Act, and does not deny that any exists.
      * ``"false"``   — it denies a commencing instrument exists and names none,
        with no limit stated. This is what 6409 and 6410 were told.
      * ``"mixed"``   — it does both, which is a real shape (naming one SSI while
        denying that others exist) and must not be scored as a clean pass.
      * ``"limited"`` — it says none was found AND attributes that to a stated
        limit of the research (a halt, or the index). **Honest, and still not
        the answer**, so it is neither a pass nor the defect: P2.1 and P2.2 own
        that failure and P3.5 must not take credit for it. 6409 turn 6 is the
        case — the run halted and said so.
      * ``"silent"``  — the answer addresses neither, which on an in-scope turn
        is a non-answer rather than a pass.

    **`consulted_others` overrides the attribution excuse**, and that is what
    keeps the after-column strict. If this turn actually called
    `get_legislation_changes` and the record named a commencing instrument, then
    the material was in hand and a denial is a plain defect however politely it
    is hedged.
    """
    truth = _truth_for(session_id)
    if not truth:
        return "silent", [], []
    named = _names_instrument(answer, truth[1])
    denials = [s for s in _sentences(answer)
               if _CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)]
    if named and denials:
        # A denial of the remainder, by a turn that named the instrument the
        # record does hold, is the right answer and not a hedge — see
        # `_CMC_REMAINDER`.
        if all(_CMC_REMAINDER.search(d) for d in denials):
            return "correct", named, []
        return "mixed", named, denials
    if named:
        return "correct", named, []
    if denials:
        if not consulted_others and all(_denial_is_attributed(d) for d in denials):
            return "limited", [], denials
        return "false", [], denials
    return "silent", [], []


def cmd_commencements(args) -> int:
    """P3.5's acceptance, over a replay directory, graded per TURN.

    Grades only the sessions in `COMMENCEMENT_TRUTH`, because the verdict needs
    an independently verified answer and there is one only for those.

    **The headline is `DELIVERED`, and that is deliberate.** It rests on a fact
    check against an externally verified ground truth — did the answer name an
    instrument that really did commence provisions of this Act — and needs no
    prose classification at all, so it cannot be a detector artefact. The
    `false` / `limited` / `silent` split below it is diagnosis, and it is the
    part that reads prose.

    That split is deliberately conservative about what counts as the defect.
    *"A search of the legislation index for commencement regulations did not
    return any results"* (6409 rep 1 turn 1, `wave2_p22_final`) is scored
    `silent`, not `false`: it asserts something about the search rather than
    about the statute book, which is exactly what P2.2 was built to produce, and
    counting it here would book P2.2's win as P3.5's defect and push the model
    back toward hedging. The lawyer is still not told about `ssi/2025/119` —
    which is why `DELIVERED` is the headline and not `false`.

    `--drops` prints every commencement-vocabulary sentence that was NOT graded
    as a denial, which is the both-directions audit this work requires of any
    new detector. Read them: the ones that must stay uncounted are true
    statements about provisions ("the remaining sections are not yet in force")
    and honest limits ("no commencement record is held for this Act").
    """
    docs = load_runs(Path(args.dir))
    docs = [d for d in docs if _truth_for(d.get("session_id"))]
    if not docs:
        print("No graded session in %s (expected any of %s)"
              % (args.dir, ", ".join(sorted(COMMENCEMENT_TRUTH))))
        return 1

    tally = Counter()
    answered = in_scope = consulted_turns = 0
    rows, drops = [], []
    for doc in sorted(docs, key=lambda d: (str(d.get("session_id")), d.get("rep", 1))):
        sid = str(doc.get("session_id"))
        truth = _truth_for(sid)
        for t in doc.get("turns", []):
            ans = t.get("answer") or ""
            if not ans.strip():
                continue
            answered += 1
            question = t.get("question") or ""
            calls = _consulted_changes(t)
            if calls:
                consulted_turns += 1
            scoped = bool(_CMC_QUESTION.search(question)) and not _names_instrument(
                question, truth[1])
            if not scoped:
                if args.answers:
                    rows.append((sid, doc.get("rep", 1), t.get("turn"), "out",
                                 [], [], calls, question))
                continue
            in_scope += 1
            body = _without_footer(ans)
            retrieved = [o for c in calls for o in c["others"]]
            verdict, named, denials = commencement_verdict(sid, body, retrieved)
            tally[verdict] += 1
            rows.append((sid, doc.get("rep", 1), t.get("turn"), verdict,
                         named, denials, calls, question))
            if args.drops:
                for sent in _sentences(body):
                    if _CMC_CONTEXT.search(sent) and not _CMC_DENIED.search(sent):
                        drops.append((sid, doc.get("rep", 1), t.get("turn"), sent))

    print("P3.5 (B3) — commencement relations over %s  (%d graded run file(s))"
          % (args.dir, len(docs)))
    print()
    print("  answered turns in graded sessions        %5d" % answered)
    print("  ... that consulted the change record     %5d" % consulted_turns)
    print("  IN SCOPE (question asks about commencement")
    print("           and does not name the instrument) %5d" % in_scope)
    print("  DELIVERED the relation                     %5d" % tally["correct"])
    print("  did NOT                                    %5d"
          % (in_scope - tally["correct"]))
    print()
    print("    naming a real commencing instrument      %5d" % tally["correct"])
    print("    DENYING one exists, naming none          %5d   <- the defect"
          % tally["false"])
    print("    doing both                               %5d" % tally["mixed"])
    print("    saying none found, blaming a stated limit %5d   "
          "<- honest, still unanswered" % tally["limited"])
    print("    saying neither                           %5d" % tally["silent"])
    print()
    for sid, rep, turn, verdict, named, denials, calls, question in rows:
        mark = {"correct": "OK   ", "false": "FALSE", "mixed": "MIXED",
                "limited": "LIMIT", "silent": "NONE ", "out": "-    "}[verdict]
        print("  %s %s rep%s t%s  %s" % (mark, sid, rep, turn, question[:70]))
        for c in calls:
            a = c["args"]
            print("        called get_legislation_changes %s direction=%s -> %s "
                  "relation(s), others: %s"
                  % (a.get("legislation_id"), a.get("direction", "to"),
                     c["relations"], ", ".join(c["others"][:6]) or "none"))
        if named:
            print("        names: %s" % ", ".join(named))
        for d in denials:
            print("        DENIAL: %s" % d[:200])
    if args.drops:
        print()
        print("  --drops: %d commencement sentence(s) NOT graded as a denial"
              % len(drops))
        for sid, rep, turn, sent in drops:
            print("    %s rep%s t%s: %s" % (sid, rep, turn, sent[:180]))
    if args.before:
        _invariant_one(Path(args.before), Path(args.dir))
    return 0


def _invariant_one(before: Path, after: Path) -> None:
    """Did the answers SHRINK to buy the number?

    **The check this row most needed, and the one a bare pass rate hides.** A
    retrieved relation invites over-claiming where P2.3's prohibition invited
    hedging, and either failure shows up as answers getting shorter while the
    metric improves. Compared per TURN SLOT and averaged across reps, because the
    two directories have different rep counts and a raw mean would be dominated
    by whichever session was replayed more.
    """
    def sessions_in(d: Path) -> set:
        return {json.loads(f.read_text(encoding="utf-8")).get("session_id")
                for f in d.glob("*.json")}

    # **Compare the SHARED sessions only.** The first version keyed on "has a
    # ground truth", which let `wave1`'s 6382 into the before column while the
    # after column has no 6382 at all — and it moved the tool-rate from 10.4 to
    # 13.4, a number that would have been published. Two populations are not a
    # before and an after.
    shared = sessions_in(before) & sessions_in(after)

    def lengths(d: Path):
        out, calls, turns = {}, 0, 0
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if doc.get("session_id") not in shared:
                continue
            for t in doc.get("turns", []):
                a = t.get("answer") or ""
                if not a.strip():
                    continue
                turns += 1
                out.setdefault((doc["session_id"], t["turn"]), []).append(len(a))
                for dg in (t.get("audit") or {}).get("delegations", []):
                    calls += len(dg.get("tools", []))
        return out, calls / max(turns, 1)

    (a, a_rate), (b, b_rate) = lengths(before), lengths(after)
    common = sorted(set(a) & set(b))
    if not common:
        print("\n  --before: no matching turn slots")
        return
    grew = 0
    print("\n  Invariant 1 — mean answer length per turn slot, %s -> %s"
          % (before.name, after.name))
    for k in common:
        am = sum(a[k]) / len(a[k])
        bm = sum(b[k]) / len(b[k])
        grew += bm > am
        print("    %s t%-3s %7.0f -> %7.0f  %s"
              % (k[0], k[1], am, bm, "grew" if bm > am else "shrank"))
    print("    %d of %d turn slots grew. A fix that buys its number by making "
          "answers" % (grew, len(common)))
    print("    shorter is a regression even where the row goes green.")
    # Scoped to the GRADED sessions, unlike `corpus`, which reports the whole
    # directory — the two answer different questions and the numbers differ.
    print("    tool calls per answered turn (graded sessions only): "
          "%.1f -> %.1f" % (a_rate, b_rate))


# --- P2.5 (B4): in-force claims, and whether anything retrieved supports them --
#
# **`IN_FORCE_CLAIM` above is deliberately left alone.** It produced the
# published 27 -> 30 series and widening it would move a number already in
# `BASELINE.md`, which is the trap Session 8 recorded. It is also blind to the
# purest form of the defect: it requires "is/are/remains/currently in force" and
# so catches none of `wave1`'s bare Status bullets — `In force (revised).`
# (6341 x3, 6384 x6, 6389 x3), `Status: Revised (In force).` (6406 x4),
# `Status: Revised (In Force).` (6335). Counted properly there are **24 turns
# and 47 assertions** in `wave1`, not 30 and 34. Both instruments are reported
# below so the old series stays comparable and the new one is the real picture.
#
# Three classes, because they need different handling and only the middle one is
# always wrong:
#
#   * an **assertion** that legislation is in force (`_CUR_ASSERT`);
#   * an assertion whose stated evidence is the **text version**
#     (`_CUR_FROM_VERSION`) — "is currently in force (revised)", "Status:
#     Revised (In force)". This is the signature, it is never supportable, and
#     it must go to zero;
#   * a **commencement-date** statement (`_CUR_DATED`) — "came into force on
#     1 July 1999". Graded separately: P3.5 made some of these retrievable, and
#     6411's is the one that was invented.
#
# What is NOT an assertion, validated against all 86 `in force` sentences in
# `wave1` and re-checked in both directions with `--drops`:
#
#   * **subordinate and conditional uses**, which are usually statutory text
#     being quoted — "while an interim order is in force, no other proceedings
#     ..." (6335 t4, quoting s. 252(2)(b)), "while certain administrative
#     sections came into force the day after Royal Assent" (6357 t6);
#   * **negatives and partials** — "not yet in force", "no longer in force",
#     "only partially in force" (6410 t1). Those are repeal or non-commencement
#     statements, and the qualified ones are the answer this row wants, not the
#     defect. A detector that counted them would score an honest answer as the
#     failure.
_CUR_SUBORDINATE = re.compile(
    r"\b(?:while|whilst|where|when|if|during|unless|until|whenever|any|an?)\b"
    r"[^.;:]{0,70}\b(?:is|are|remains?|was|were)\s+"
    r"(?:in[- ]force|in operation|in effect|operative)\b",
    re.I,
)
_CUR_NEGATED = re.compile("|".join([
    r"\b(?:not|never|no longer|nor|neither)\b[^.;:]{0,30}"
    r"\b(?:in[- ]force|in operation|in effect|current law|operative)\b",
    r"\bin[- ]force\b[^.;:]{0,20}\b(?:not|no longer)\b",
    r"\b(?:partially|partly|part) in[- ]force\b",
    r"\bnot (?:yet )?(?:been )?(?:brought |commenced )?in(?:to)? force\b",
]), re.I)
# **A statement that currency could NOT be established is the answer this row
# wants, and it must never be counted as the defect.** Found by the both-
# directions audit: `baseline` 6383 t4 says *"nor could their active status in
# Scotland be verified"* — an honest negative that the standalone branch read as
# an assertion. Left in, a post-fix answer saying "in-force status was not
# verified" would have been scored as the failure, so the error ran against the
# fix rather than for it; either way the instrument would have been wrong.
_CUR_DISCLAIM_VERB = (r"(?:verif(?:y|ied|iable)|establish(?:ed)?|"
                      r"determin(?:e|ed|able)|confirm(?:ed)?|ascertain(?:ed)?)")
_CUR_UNVERIFIED = re.compile("|".join([
    r"\b(?:not|never|no|nor|neither|cannot|can ?not|could ?n[o']t|unable|"
    r"without)\b[^.;:]{0,60}\b" + _CUR_DISCLAIM_VERB + r"\b",
    r"\b" + _CUR_DISCLAIM_VERB + r"\b[^.;:]{0,30}\b(?:not|no)\b",
    r"\bun(?:verified|confirmed|established|determined)\b",
]), re.I)
# The three text-version values, which is the whole of the currency vocabulary
# the index actually has. Interpolated rather than repeated because it appears
# in seven alternatives below and a divergent copy is how a detector goes blind.
_CUR_VERSION = r"(?:revised|final|stub)"
# The affirmative assertion, in the five shapes the corpus uses. The fourth
# alternative is the one the old `IN_FORCE_CLAIM` has no equivalent of: a bare
# Status bullet whose entire value is the claim.
_CUR_ASSERT = re.compile("|".join([
    r"\b(?:is|are|remains?|remain)\s+"
    r"(?:still\s+|currently\s+|now\s+|already\s+)?in[- ]force\b",
    r"\bcurrently in[- ]force\b",
    r"\bin[- ]force as (?:at|of)\b",
    r"(?:^|\*\*|\||\bstatus(?:es)?\b[^\n:]{0,20}:\s*)\s*\(?in[- ]force\b",
    r"\b" + _CUR_VERSION + r"\s*[/(]\s*in[- ]force\b",
]), re.I | re.M)
# The signature: the text version offered as the evidence for currency. Never
# supportable, so this column must reach zero on its own. Seven alternatives
# because the corpus writes it in both orders, inside one bracket and across
# two, and after a `Status:` label — "In force (revised)", "Status: Revised (In
# force)", "(Status: In force / Revised)", "is on the statute book (Revised / In
# force)", "currently in force, with statuses recorded as either final or
# revised". **A bare co-occurrence test is deliberately NOT used**: it would
# trip on the legitimate post-P3.5 sentence "the revised text held shows that
# section 9 came into force on 10 May 2025", so the version token has to be
# bracketed or sit behind a `Status` label.
_CUR_FROM_VERSION = re.compile("|".join([
    r"\(\s*(?:status\s*[:=]\s*)?[^)\n]{0,25}" + _CUR_VERSION
    + r"[^)\n]{0,25}\)[^.;\n]{0,45}in[- ]force",
    r"in[- ]force[^.;\n]{0,45}\(\s*(?:status\s*[:=]\s*)?[^)\n]{0,25}"
    + _CUR_VERSION + r"[^)\n]{0,25}\)",
    r"\([^)\n]{0,30}in[- ]force[^)\n]{0,30}" + _CUR_VERSION + r"[^)\n]{0,15}\)",
    r"\([^)\n]{0,30}" + _CUR_VERSION + r"[^)\n]{0,30}in[- ]force[^)\n]{0,15}\)",
    r"\bstatus(?:es)?\b[^.;\n]{0,20}[:=][^.;\n]{0,30}" + _CUR_VERSION
    + r"[^.;\n]{0,30}in[- ]force",
    r"\bstatus(?:es)?\b[^.;\n]{0,20}[:=][^.;\n]{0,30}in[- ]force[^.;\n]{0,30}"
    + _CUR_VERSION,
    r"in[- ]force[^.;\n]{0,60}\bstatus(?:es)?\b[^.;\n]{0,40}" + _CUR_VERSION,
]), re.I)
# **The paraphrase branch, and it exists because the fix provoked it.** The
# second smoke run — with the prohibition on "in force" in place — came back
# with *"Yes, the Scotland Act 1998 IS IN OPERATION and remains a fundamental
# pillar of the UK constitution"*, sourced to a 2026 UKSC judgment that
# *"confirms its ACTIVE STATUS"*. That is the same unsupported proposition in
# different words, and it is 6411's original diagnosis verbatim: *"determined
# in-force status by reference to case law"*. A detector blind to the evasion
# its own fix causes would have read zero and published it.
#
# **Two halves, both required, and the second is what keeps case law out.** A
# legislation noun must appear in the sentence, because "*Donoghue* remains good
# law" and "that principle continues to apply" are statements about a judgment —
# a different question, answered by different tools, belonging to the case-law
# prompt's "Jurisdiction & Currency" section. "good law" is therefore NOT in the
# vocabulary at all, deliberately: there is no way to tell its subject from the
# sentence, and over-counting a legitimate case-currency statement would move a
# number wrongly.
_CUR_LEGISLATION_NOUN = re.compile(
    r"\b(?:act|acts|regulations?|order|orders|instrument|instruments|"
    r"legislation|statute|statutes|provisions?|section|sections|schedule|"
    r"s\.|ss\.|ssi|uksi|asp|ukpga)\b",
    re.I,
)
_CUR_PARAPHRASE = re.compile("|".join([
    r"\b(?:is|are|remains?|remain)\s+(?:still\s+|currently\s+|now\s+)?"
    r"(?:in operation|operative|current law|the current law|in effect)\b",
    r"\b(?:continues?|continue)\s+to\s+(?:apply|have effect|be in force)\b",
    r"\b(?:is|are)\s+still\s+appl(?:ies|y|icable)\b",
]), re.I)
# Phrases whose subject is a pronoun, so the legislation noun is in the previous
# sentence. Matched alone because neither is said of a case.
_CUR_PARAPHRASE_STANDALONE = re.compile(
    r"\bactive status\b|\bstill on the statute book and in force\b", re.I)
# A dated commencement statement. Retrievable since P3.5 (by the second hop into
# the commencing instrument), and invented in 6411 — so graded, not excluded.
_CUR_DATED = re.compile("|".join([
    r"\b(?:came|come|comes|coming|brought|bring|brings)\s+in(?:to)?\s+force\b"
    r"[^.;\n]{0,80}\b(?:on|from|with effect from)\b[^.;\n]{0,40}\b\d{4}\b",
    r"\bin[- ]force (?:on|from|with effect from)\b[^.;\n]{0,40}\b\d{4}\b",
]), re.I)
# Any currency vocabulary at all — the denominator for `--drops`, so the
# both-directions audit reads everything the classifier chose to let through.
_CUR_CONTEXT = re.compile(
    r"\bin[- ]force\b|\binto force\b|\bin operation\b|\boperative\b"
    r"|\bcurrent law\b|\bactive status\b|\bcontinues? to apply\b"
    r"|\b(?:is|are|remains?)\s+(?:still\s+)?in effect\b",
    re.I,
)


def _currency_asserted(sentence: str) -> bool:
    """Does this sentence assert that legislation is currently in force?

    One place, so the product test, `cmd_currency` and any later row read the
    same rule. The paraphrase branch needs a legislation noun; see
    `_CUR_PARAPHRASE`.
    """
    if _CUR_NEGATED.search(sentence) or _CUR_SUBORDINATE.search(sentence):
        return bool(_CUR_FROM_VERSION.search(sentence))
    if _CUR_ASSERT.search(sentence) or _CUR_FROM_VERSION.search(sentence):
        return True
    # The paraphrase branches only, and only where the sentence is not itself
    # saying that currency could not be established. `_CUR_ASSERT` above does
    # not need the guard: "is currently in force" is not a sentence anyone
    # writes while disclaiming it, and `_CUR_NEGATED` already covers "is not".
    if _CUR_UNVERIFIED.search(sentence):
        return False
    if _CUR_PARAPHRASE_STANDALONE.search(sentence):
        return True
    return bool(_CUR_LEGISLATION_NOUN.search(sentence)
                and _CUR_PARAPHRASE.search(sentence))


def _currency_support(turn: dict) -> dict:
    """What this turn actually retrieved that could support a currency claim.

    **Structural, computed from the audit trace, and that is the whole point.**
    The prose half of this grading asks only "does the answer assert currency";
    whether anything supports it is read off the tools, so the headline is a
    conjunction of one prose test and one fact about the run rather than a
    judgement about a sentence's sourcing. Detectors on this work have been
    wrong seventeen times; the trace has not.

    All four facts are collected and printed, and **only `commenced` counts as
    support for an affirmative assertion.** The first draft counted the title
    marker too, and that was wrong in the flattering direction: it graded 6411's
    *"Yes, the Scotland Act 1998 is in force"* as SOURCED because an unrelated
    `uksi/2024/697` appeared repeal-marked somewhere in the same turn's search
    results. The marker is an **asymmetric** signal — its presence is evidence
    an instrument is NOT in force, its absence is evidence of nothing — so it
    can support only a negative, and `_CUR_NEGATED` already keeps negatives out
    of the assertion count. A **repeal relation** is excluded for the same
    reason and a sharper one: an answer reading "the Act remains in force except
    ss. 38-39, repealed by uksi/2014/486" would score SOURCED off the repeal
    while the overclaim is in the other half of the sentence.

    `valid_date` is deliberately not support either. It is the date the held text
    is up to date to, which is a text-version date — treating it as currency
    evidence here would be the same conflation the row is about, committed by
    its own instrument.
    """
    out = {"commenced": 0, "repeals": 0, "orders": 0, "marked": [], "changes": 0}
    marker = re.compile(r"\((repealed|revoked|expired|spent)\b[^)]*\)", re.I)
    for dg in (turn.get("audit") or {}).get("delegations", []):
        for tl in dg.get("tools", []):
            name = tl.get("name")
            o = _json_or_none(tl.get("raw_result"))
            if name == "get_legislation_changes" and isinstance(o, dict):
                out["changes"] += 1
                # Prefer the counts the slimmer computes (P2.5 added them); fall
                # back to the effect histogram so a PRE-P2.5 run file still
                # grades — which is what makes the before-column measurable.
                eff = o.get("effects") if isinstance(o.get("effects"), dict) else {}
                c = o.get("provisions_commenced")
                if not isinstance(c, int):
                    c = sum(v for k, v in eff.items()
                            if str(k).strip().lower() == "coming into force")
                r = o.get("repeal_or_revocation_relations")
                if not isinstance(r, int):
                    r = sum(v for k, v in eff.items()
                            if any(tok in str(k).lower()
                                   for tok in ("repeal", "revok", "revoc")))
                ords = o.get("commencement_orders_of_amendments")
                if not isinstance(ords, int):
                    ords = sum(v for k, v in eff.items()
                               if str(k).strip().lower() == "commencement order")
                out["commenced"] += c
                out["repeals"] += r
                out["orders"] += ords
            elif name == "search_legislation" and isinstance(o, dict):
                for row in o.get("results") or []:
                    if not isinstance(row, dict):
                        continue
                    if marker.search(str(row.get("title") or "")):
                        lid = str(row.get("legislation_id") or "")
                        if lid and lid not in out["marked"]:
                            out["marked"].append(lid)
    return out


def currency_verdict(answer: str, support: dict) -> tuple:
    """(verdict, assertions, version_cited, dated) for one answered turn.

    Four verdicts:

      * ``"unsupported"`` — the answer asserts that legislation is in force and
        the run retrieved **no** commencement relation, **no** repeal relation
        and **no** repeal-marked title. Nothing it could have relied on. This is
        the defect and it must reach zero.
      * ``"sourced"``     — it asserts currency and the run retrieved a `coming
        into force` relation. **Not a claim that the sentence is right** — a
        commencement relation for ss. 9 and 20 does not make "the Act is in
        force" true — only that a record was in hand. `unsupported` is the
        headline because it is the unambiguous half. **`sourced` is the
        suppression check and must not fall to zero**, or the fix bought its
        number by silencing answers the material now supports.
      * ``"none"``        — no assertion. The intended state for an instrument
        with no commencement record.
      * ``"dated_only"``  — no bare assertion, but a commencement DATE is stated.
        Split out because the date needs a second hop and 6411's was invented.
    """
    sents = [s for s in _sentences(answer) if _CUR_CONTEXT.search(s)]
    asserts, version, dated = [], [], []
    for s in sents:
        if _CUR_FROM_VERSION.search(s):
            version.append(s)
        if _currency_asserted(s):
            asserts.append(s)
        if _CUR_DATED.search(s) and not _CUR_NEGATED.search(s):
            dated.append(s)
    # ONLY a retrieved `coming into force` relation. See `_currency_support`
    # for why the repeal relation and the title marker are printed and not
    # counted — both can support a negative and neither can support this.
    supported = bool(support["commenced"])
    if asserts or version:
        return ("sourced" if supported else "unsupported"), asserts, version, dated
    if dated:
        return "dated_only", asserts, version, dated
    return "none", asserts, version, dated


def cmd_currency(args) -> int:
    """P2.5's acceptance (B4), over a replay directory, graded per TURN.

    **The headline is `UNSUPPORTED`: the answer said legislation is in force and
    the run retrieved nothing that could establish it.** One prose test
    (`_CUR_ASSERT`) against one structural fact (`_currency_support`, read off
    the audit trace), so the number cannot be moved by a wording change in the
    product — which is what happened to P2.2's denominator.

    **`SOURCED` beside it is the suppression check and is as important.** P3.5
    made commencement and repeal retrievable; a fix for this row that simply
    forbade the claim would drive `unsupported` to zero by driving `sourced`
    there too, and Invariant 1 read in the inverse direction says that is a
    regression. `--before` adds the answer-length comparison for the same reason.

    `--drops` prints every currency-vocabulary sentence NOT graded as an
    assertion, which is the both-directions audit. The ones that must stay
    uncounted are statutory quotations ("while an interim order is in force"),
    negatives ("not yet in force"), qualified partials ("only partially in
    force") and commencement dates, which are graded in their own column.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print("No run files in %s" % args.dir)
        return 1

    tally = Counter()
    answered = 0
    old_turns = old_sentences = 0
    new_sentences = version_sentences = dated_sentences = 0
    rows, drops = [], []
    for doc in sorted(docs, key=lambda d: (str(d.get("session_id")), d.get("rep", 1))):
        sid = str(doc.get("session_id"))
        for t in doc.get("turns", []):
            ans = t.get("answer") or ""
            if not ans.strip():
                continue
            answered += 1
            body = _without_footer(ans)
            # The old instrument, unchanged, so the published series stays
            # comparable. Counted on the same body as the new one.
            old_hits = [s for s in _sentences(body) if IN_FORCE_CLAIM.search(s)]
            if old_hits:
                old_turns += 1
                old_sentences += len(old_hits)
            support = _currency_support(t)
            verdict, asserts, version, dated = currency_verdict(body, support)
            tally[verdict] += 1
            new_sentences += len(asserts)
            version_sentences += len(version)
            dated_sentences += len(dated)
            if verdict != "none" or args.answers:
                rows.append((sid, doc.get("rep", 1), t.get("turn"), verdict,
                             asserts, version, dated, support))
            if args.drops:
                for s in _sentences(body):
                    if not _CUR_CONTEXT.search(s):
                        continue
                    if s in asserts or s in version:
                        continue
                    drops.append((sid, doc.get("rep", 1), t.get("turn"), s))

    print("P2.5 (B4) — in-force claims over %s  (%d run file(s))"
          % (args.dir, len(docs)))
    print()
    print("  answered turns                             %5d" % answered)
    print("  UNSUPPORTED — asserts legislation is in force and")
    print("    retrieved NO commencement relation        %5d   <- the defect"
          % tally["unsupported"])
    print("  SOURCED — asserts it with a `coming into")
    print("    force` record in hand                     %5d   <- must NOT reach 0"
          % tally["sourced"])
    print("  states a commencement DATE only            %5d" % tally["dated_only"])
    print("  asserts nothing about currency             %5d" % tally["none"])
    print()
    print("  assertion sentences (new instrument)       %5d" % new_sentences)
    print("  ... citing a TEXT VERSION as the evidence  %5d   <- must reach 0"
          % version_sentences)
    print("  commencement-date sentences                %5d" % dated_sentences)
    print("  turns matching the OLD `IN_FORCE_CLAIM`    %5d  (%d sentence(s)) "
          "<- the published 27->30 series" % (old_turns, old_sentences))
    print()
    for sid, rep, turn, verdict, asserts, version, dated, sup in rows:
        mark = {"unsupported": "UNSUP", "sourced": "SRCED", "dated_only": "DATE ",
                "none": "-    "}[verdict]
        print("  %s %s rep%s t%s   retrieved: commenced=%d repeals=%d orders=%d "
              "marked=%s"
              % (mark, sid, rep, turn, sup["commenced"], sup["repeals"],
                 sup["orders"], ",".join(sup["marked"][:3]) or "none"))
        for s in version:
            print("        VERSION-AS-EVIDENCE: %s" % s.strip()[:170])
        for s in asserts:
            if s not in version:
                print("        ASSERTS: %s" % s.strip()[:170])
        for s in dated:
            print("        DATED:   %s" % s.strip()[:170])
    if args.drops:
        print()
        print("  --drops: %d currency sentence(s) NOT graded as an assertion"
              % len(drops))
        for sid, rep, turn, s in drops:
            print("    %s rep%s t%s: %s" % (sid, rep, turn, s.strip()[:170]))
    if args.before:
        _invariant_one(Path(args.before), Path(args.dir))
    return 0


def cmd_corpus(args) -> int:
    """The retrieval shape of a replay directory — every number P2.3 published.

    **Why this exists.** Session 6 set the rule after `replay_report negatives`
    had to grow a search-shape header: *a number with no command behind it
    cannot be checked by the next session*. P2.3 then published six such numbers
    out of throwaway scripts — how much raw retrieval there is, how many
    instrument preambles it ever contained, whether `description` survives
    slimming, which route the Worker actually uses to touch an instrument, and
    how much the tool memo costs P2.2's search record. They are the numbers that
    decided the row's design and its scope, so they belong behind a command.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1

    tools = Counter()
    raw_chars = 0
    search_rows = with_description = 0
    recitals = []
    secondary_touch = Counter()
    memo = Counter()
    lost_runs = lost_queries = 0
    runs = 0
    lost_turns = set()
    answered = leaked = dup_footer = dagger = 0

    for doc in docs:
        for t in doc.get("turns", []):
            _ans = t.get("answer") or ""
            if _ans.strip():
                answered += 1
                if any(m in _ans for m in
                       ("[SEARCH SCOPE", "[ENABLING POWER", "[CHANGE RECORD")):
                    leaked += 1
                if _ans.count("*Search scope:") > 1:
                    dup_footer += 1
                if PROVISION_MARKER in _ans:
                    dagger += 1
            for dg in (t.get("audit") or {}).get("delegations", []):
                runs += 1
                recorded, memoed = set(), set()
                for tl in dg.get("tools", []):
                    nm = tl.get("name") or "?"
                    tools[nm] += 1
                    raw = tl.get("raw_result")
                    if isinstance(raw, str):
                        raw_chars += len(raw)
                    if tl.get("memo_hit"):
                        memo[nm] += 1
                    lid = str((tl.get("args") or {}).get("legislation_id") or "")
                    if nm in ("get_legislation_text", "search_legislation_sections") \
                            and lid.split("/")[0].lower() in _SECONDARY_SERIES:
                        secondary_touch[nm] += 1
                    if nm == "search_legislation":
                        q = str((tl.get("args") or {}).get("query") or "")
                        (memoed if tl.get("memo_hit") else recorded).add(q)
                    o = _json_or_none(raw)
                    if not isinstance(o, dict):
                        continue
                    if nm == "search_legislation":
                        for r in (o.get("results") or []):
                            if isinstance(r, dict):
                                search_rows += 1
                                if r.get("description"):
                                    with_description += 1
                    leg = o.get("legislation")
                    if isinstance(leg, dict):
                        d = str(leg.get("description") or "")
                        if d and _DERIV_RECITAL.search(d):
                            recitals.append((lid, d[:120]))
                missing = memoed - recorded
                if missing:
                    lost_runs += 1
                    lost_queries += len(missing)
                    lost_turns.add((doc["session_id"], doc.get("rep", 1), t["turn"]))

    print(f"Retrieval shape over {args.dir}  ({len(docs)} run file(s))")
    print()
    print(f"  raw retrieval                 {raw_chars / 1e6:.1f}M chars over "
          f"{sum(tools.values())} tool result(s)")
    for nm, n in tools.most_common():
        print(f"    {nm:34} {n:5}   ({memo[nm]} served from the tool memo)")
    print()
    print("  P2.3 — where an enabling power can come from")
    print(f"    search rows seen                 {search_rows:5}")
    print(f"    ... carrying a `description`     {with_description:5}   "
          "<- _slim_search_results strips it (P3.6)")
    print(f"    instrument preambles retrieved   {len(recitals):5}   "
          "<- the ONLY route, via legislation.description")
    for lid, d in recitals[:5]:
        print(f"      {lid or '(id not in args)':18} {d!r}")
    print(f"    instruments touched by section search {secondary_touch['search_legislation_sections']:5}")
    print(f"    instruments touched by text retrieval {secondary_touch['get_legislation_text']:5}   "
          "<- the rare route; record BOTH")
    print()
    print("  P2.9 — what the tool memo costs P2.2's search record")
    print(f"    worker runs                                    {runs:5}")
    print(f"    ... losing a memo-served query from their own")
    print(f"        record (no `record_search` on that path)   {lost_runs:5}   "
          f"({100 * lost_runs / runs if runs else 0:.0f}%)")
    print(f"    distinct queries lost from a worker report     {lost_queries:5}")
    print(f"    turns affected                                 {len(lost_turns):5}")
    print("    Those queries never reach worker_scope_block or answer_scope_footer,")
    print("    so the disclosure under-reports what was actually searched.")

    # P3.5's shape numbers, here for the same reason all the others are: they
    # decided the row and they were published, so they must be re-runnable.
    print()
    print("  P3.5 — answer hygiene and loop cost")
    print(f"    answered turns                                 {answered:5}")
    print(f"    tool calls per answered turn                   "
          f"{sum(tools.values()) / max(answered, 1):5.1f}")
    print(f"    turns whose answer LEAKED an agent-facing block{leaked:5}   "
          "<- must be 0")
    print(f"    turns carrying the scope footer TWICE          {dup_footer:5}   "
          "<- P2.2 defect, fixed at P3.5")
    print(f"    turns carrying a P1.6 provision dagger         {dagger:5}   "
          "<- the measured cost of labels-not-URLs")
    return 0


# P1.6's demotion marker, counted by `corpus` as the measured cost of P3.5's
# decision to emit provision LABELS rather than provision URLs.
PROVISION_MARKER = "\u2020"

_SECONDARY_SERIES = ("ssi", "uksi", "nisr", "wsi", "ssr", "uksro", "nisro",
                     "ukci", "ukmo")


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="replay_report")
    p.add_argument("--dir", default=str(
        Path(__file__).resolve().parents[2]
        / "docs" / "prepilot-fixes" / "evidence" / "replay" / "baseline"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary")
    se = sub.add_parser("session")
    se.add_argument("--session", required=True)
    se.add_argument("--full", action="store_true")
    sub.add_parser("baseline")

    c = sub.add_parser("compare", help="two replay dirs, same sessions, side by side")
    c.add_argument("--before", required=True)
    c.add_argument("--after", required=True)
    c.add_argument("--all-reps", action="store_true",
                   help="do not restrict to rep 1 (denominators will differ)")

    h = sub.add_parser("halts", help="P2.1 acceptance: every halted turn, graded")
    h.add_argument("--answers", action="store_true", help="print the answers too")
    h.add_argument("--chars", type=int, default=1200)

    n = sub.add_parser("negatives",
                       help="P2.2 acceptance: every turn asserting a negative, graded")
    n.add_argument("--answers", action="store_true", help="print the answers too")
    n.add_argument("--failing-only", action="store_true",
                   help="with --answers, print only the failing turns")
    n.add_argument("--chars", type=int, default=1600)

    dv = sub.add_parser("derivations",
                        help="P2.3 acceptance: every turn asserting a "
                             "'made under' derivation, graded")
    dv.add_argument("--answers", action="store_true", help="print the claims in context")
    dv.add_argument("--failing-only", action="store_true",
                    help="with --answers, print only the unverified turns")
    dv.add_argument("--drops", action="store_true",
                    help="print every sentence in the same vocabulary that was "
                         "NOT counted — the both-directions audit")

    cm = sub.add_parser("commencements",
                        help="P3.5 acceptance: commencement relations, graded per turn")
    cm.add_argument("--answers", action="store_true", help="print every turn")
    cm.add_argument("--drops", action="store_true",
                    help="every commencement sentence NOT graded as a denial")
    cm.add_argument("--before", default=None,
                    help="a second replay dir: prints the Invariant 1 check "
                         "(did answers shrink to buy the number?)")

    cu = sub.add_parser("currency",
                        help="P2.5 acceptance: in-force claims, graded per turn")
    cu.add_argument("--drops", action="store_true",
                    help="print every currency sentence NOT graded as an assertion")
    cu.add_argument("--answers", action="store_true",
                    help="list turns that assert nothing too")
    cu.add_argument("--before", metavar="DIR",
                    help="a replay dir to compare answer lengths against "
                         "(Invariant 1: did the answers shrink to buy the number)")
    sub.add_parser("corpus",
                   help="retrieval shape: raw volume, where an enabling power "
                        "can come from, and what the tool memo costs P2.2")
    args = p.parse_args(list(argv) if argv is not None else None)
    return {
        "summary": cmd_summary,
        "session": cmd_session,
        "baseline": cmd_baseline,
        "compare": cmd_compare,
        "halts": cmd_halts,
        "negatives": cmd_negatives,
        "derivations": cmd_derivations,
        "commencements": cmd_commencements,
        "currency": cmd_currency,
        "corpus": cmd_corpus,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
