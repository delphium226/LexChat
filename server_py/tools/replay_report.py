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
from typing import Any, Iterable, Optional

# --- Tool records ------------------------------------------------------------

def _ran(tl: dict) -> bool:
    """False for a call a discovery budget refused (P2.7).

    A refused call is a tool record, but no search ran, so every count of
    searches that ran must skip it. The legislation stop message deliberately
    carries no `results`, which would otherwise read as a zero-result search.
    No directory before P2.7 holds a refused legislation call, so this moves no
    published number.
    """
    return not tl.get("budget_blocked")


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
                if tl["name"] != "search_legislation" or not _ran(tl):
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
                                      "search_case_law") or not _ran(tl):
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
                    if tl.get("name") != "search_legislation" or not _ran(tl):
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


# A question that asks about currency, loosely. Deliberately loose: this is the
# denominator for a COST measure, and over-counting "asked" understates the cost.
_CUR_QUESTION = re.compile(
    r"\bin[- ]force\b|\bcommenc|\brepeal|\brevok|\bcurrent\b|\bup to date\b"
    r"|\bstill (?:appl|good|valid)", re.I)
# The disclaimer the fix produces, as it reaches a lawyer.
_CUR_DISCLOSED = re.compile(
    r"in[- ]force status (?:was|could|is)?\s?(?:not|n't)\s?(?:be |been )?"
    r"(?:verified|established|confirmed|determined|reported)"
    r"|not (?:possible to |able to )?(?:verif|establish|confirm|determin)\w*"
    r"[^.;\n]{0,40}in[- ]force"
    r"|in[- ]force status (?:is|was) not (?:recorded|reported|established)"
    r"|does not (?:report|record) (?:whether|in[- ]force)",
    re.I,
)


def _currency_on_unasked_turns(docs) -> None:
    """The measured COST of `_currency_limb` speaking unconditionally.

    **This exists because `BASELINE.md` quotes the number, and a number quoted
    at a reader needs a command behind it.** The limb fires on every step that
    touched legislation, not only on the ones asked a currency question, so a
    question about the definition of "shop" can come back carrying an "in-force
    status was not verified" paragraph.

    That is judged the right trade rather than noise — "Jurisdiction & Status"
    is a mandatory report section that has to say *something*, and what it said
    before was *"All referenced legislation is currently in force"* about a
    session citing an Act whose ss. 38-39 are repealed. But it is a change to
    answers nobody asked for, so it is measured rather than assumed away.
    """
    asked = unasked = asked_disc = unasked_disc = 0
    rows = []
    for doc in sorted(docs, key=lambda d: (str(d.get("session_id")), d.get("rep", 1))):
        for t in doc.get("turns", []):
            body = _without_footer(t.get("answer") or "")
            if not body.strip():
                continue
            q = t.get("question") or ""
            was_asked = bool(_CUR_QUESTION.search(q))
            disc = [x.strip() for x in _sentences(body) if _CUR_DISCLOSED.search(x)]
            if was_asked:
                asked += 1
                asked_disc += bool(disc)
            else:
                unasked += 1
                unasked_disc += bool(disc)
            if disc:
                rows.append((doc["session_id"], doc.get("rep", 1), t.get("turn"),
                             was_asked, disc))
    print()
    print("  --unasked: the cost of a limb that speaks unconditionally")
    print("    question DID ask about currency            %5d" % asked)
    print("    ... carrying a currency disclaimer         %5d   <- wanted" % asked_disc)
    print("    question did NOT ask about currency        %5d" % unasked)
    print("    ... carrying one anyway                    %5d   <- the cost"
          % unasked_disc)
    for sid, rep, turn, was_asked, disc in rows:
        print("    %s %s rep%s t%s" % ("ASKED  " if was_asked else "UNASKED",
                                       sid, rep, turn))
        for d in disc[:2]:
            print("        %s" % d[:160])


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
# A subordinate or interrogative clause is not an assertion. `whether` is in the
# list because an indirect question is never a claim — "it was not possible to
# determine WHETHER the Regulations are in operation" is the answer this row
# wants, and `_CUR_NEGATED`'s 30-character window is too short to reach across
# the intervening clause. Known and accepted edge: a sentence that asks and then
# answers ("the record does not say whether s. 9 is in force, but it is") is
# suppressed, which `while` and `if` have always done here too.
_CUR_SUBORDINATE = re.compile(
    r"\b(?:while|whilst|where|when|whether|if|during|unless|until|whenever|"
    r"any|an?)\b"
    # **The comma is load-bearing and is the whole of the distinction.** The
    # trigger and the in-force phrase must be in the SAME clause. With the
    # adverb slot below but a comma allowed in the gap, *"While we cannot verify
    # every provision, the Act is currently in force"* matched — a concessive
    # clause about verification followed by a main-clause assertion, which is
    # exactly the sentence that must still count. With the comma excluded,
    # *"To determine if a specific section is currently in force, we would need
    # to check the individual commencement orders"* (6411 rep 2) still matches,
    # because there the `if` and the phrase sit together.
    r"[^.;:,]{0,70}\b(?:is|are|remains?|remain|was|were)\s+"
    # The same optional adverb slot `_CUR_ASSERT` has, and it must stay in step
    # with it. Without it, 6411 rep 2's conditional was graded as an assertion
    # because `is` was no longer adjacent to `in force`. Two patterns that have
    # to agree about a phrase, only one of which knows about adverbs, is a
    # detector waiting to be wrong.
    r"(?:still\s+|currently\s+|now\s+|already\s+)?"
    r"(?:in[- ]force|in operation|in effect|operative|(?:the )?current law)\b",
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
# wants, and it must never be counted as the defect.**
#
# Two errors were found writing this guard, one in each direction, and the
# shape it ended up with is what avoids both.
#
# *Found by the both-directions audit over the historical corpus:* `baseline`
# 6383 t4 says *"nor could their active status in Scotland be verified"* — an
# honest negative that the standalone paraphrase branch read as an assertion.
# Left in, a post-fix answer saying so would have been scored as the failure,
# which runs against the fix rather than for it.
#
# *Found by reading `_CUR_ASSERT` against the product's own new wording:* its
# Status-bullet branch matches a sentence merely STARTING with "In force", so
# **"In-force status: not verified"** — which `_currency_limb` now tells the
# model to write — scores as the defect. `_CUR_NEGATED` catches *"in-force
# status was not verified"* (via "in-force" + <=20 chars + "not") but not the
# colon form, because its character class excludes `:`.
#
# *And the fix for those must not become the opposite error.* A guard on any
# negated establishment verb anywhere in the sentence would drop *"While we
# cannot verify every provision, the Act is currently in force"* — a false
# negative in the flattering direction, which is the worse of the two. So the
# guard is scoped to the **disclaimer shape**: the subject is the status and the
# predicate is a negated establishment verb. A sentence that disclaims and then
# asserts still counts, because the assertion is not about the status's
# verifiability.
_CUR_STATUS_SUBJECT = (
    r"(?:in[- ]force status|in[- ]force position|currency|active status|"
    r"commencement status|current status|current in[- ]force status)")
_CUR_NEG_WORD = (r"(?:not|never|nor|neither|no|cannot|can ?not|could ?n[o']t|"
                 r"unable|without)")
_CUR_ESTABLISH_VERB = (
    r"(?:verif(?:y|ied|iable)|establish(?:ed)?|determin(?:e|ed|able)|"
    r"confirm(?:ed)?|ascertain(?:ed)?|report(?:ed)?)")
#
# **The distance windows between the subject and the negation were wrong, and
# the acceptance run's first rep is what showed it.** The model wrote exactly
# the sentence `_currency_limb` asks for — *"In-force status for the remaining
# instruments (the 1886, 1912, 1930, and 1936 Acts, as well as the 1950, 1963,
# and 1974 Orders) was not verified"* — and 95 characters of parenthetical list
# put "was not verified" outside a 50-character window, so the disclaimer was
# graded as the defect. Windows between clauses cannot be set from a sample.
#
# So the rule is **positional only where position carries meaning**: the status
# subject anywhere in the sentence, plus a negation ADJACENT to an establishment
# verb. The adjacency is what keeps *"While we cannot verify every provision,
# the Act is currently in force"* counted — it has the adjacency but no status
# subject, because its subject is the Act.
_CUR_NEGATED_VERB = re.compile("|".join([
    r"\b" + _CUR_NEG_WORD + r"\b[^.;\n]{0,60}\b" + _CUR_ESTABLISH_VERB + r"\b",
    r"\b" + _CUR_ESTABLISH_VERB + r"\b[^.;\n]{0,30}\b(?:not|no)\b",
    r"\bun(?:verified|confirmed|established|determined)\b",
]), re.I)
_CUR_SUBJECT_RE = re.compile(_CUR_STATUS_SUBJECT, re.I)
# The footer's own sentence, which contains "in force" by necessity, plus the
# limb's own "could not be verified" phrasing where the subject is elided.
_CUR_DISCLAIMER_LITERAL = re.compile(
    r"is not something this index reports"
    r"|no (?:commencement|change) record was (?:retrieved|consulted)",
    re.I,
)


# **Advice about what establishing currency WOULD take is not a claim that it
# is established.** 6411 rep 2, on the strengthened prompt, wrote *"To establish
# exactly which provisions are currently in force today, you would need to
# consult the specific commencement orders"* — an infinitival purpose clause
# with an embedded interrogative, graded as an assertion because no
# `_CUR_SUBORDINATE` trigger word appears in it.
#
# **Adding `which` to that trigger list is the wrong fix**: "The provisions
# which are currently in force include ss. 1-5" IS an assertion and would be
# suppressed. So the guard is the SHAPE again — a purpose clause naming an
# establishment verb, plus advice about what it would take. Both halves are
# required, because the purpose clause alone appears inside real assertions
# ("we checked whether it is in force and it is").
_CUR_ESTABLISH_INF = (
    r"(?:establish|determine|confirm|verify|check|ascertain|find out)")
_CUR_ADVICE_CLAUSE = (
    r"(?:you|one|a reader|the reader)?\s*would (?:need|have) to"
    r"|would (?:be )?requir(?:e|ed)"
    r"|you (?:should|can|must|may want to|will need to)\s+"
    r"(?:consult|check|refer|review|look)"
    r"|it would be necessary to")
_CUR_ADVICE = re.compile(
    r"\bto\s+" + _CUR_ESTABLISH_INF + r"\b[^.;\n]{0,120}(?:"
    + _CUR_ADVICE_CLAUSE + r")"
    r"|(?:" + _CUR_ADVICE_CLAUSE + r")[^.;\n]{0,120}\bto\s+"
    + _CUR_ESTABLISH_INF + r"\b",
    re.I,
)


def _currency_disclaimed(sentence: str) -> bool:
    """Is this sentence saying that currency could NOT be established?

    See the note above `_CUR_NEGATED_VERB`. Two conditions, neither of them a
    distance window across a clause boundary.
    """
    if _CUR_DISCLAIMER_LITERAL.search(sentence) or _CUR_ADVICE.search(sentence):
        return True
    return bool(_CUR_SUBJECT_RE.search(sentence)
                and _CUR_NEGATED_VERB.search(sentence))


# A bare section heading is not a claim. `_sentences` splits by line, so
# `*   **In-Force Status:**` arrives on its own with its content on the lines
# below — and `_CUR_ASSERT`'s `\*\*` branch matches the "In-Force" straight
# after the bold marker. Found in the acceptance run's 6341 rep 1 turn 7, where
# the heading was scored as an assertion and the paragraph under it was an
# honest disclaimer.
_CUR_BARE_HEADING = re.compile(
    r"^[\s*\-•>#]*\**\s*[A-Za-z][^:\n]{0,48}:\**\s*$")
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
    # `_CUR_FROM_VERSION` is never guarded: a text version offered as the
    # evidence for currency is not a supportable claim under any hedging, so it
    # counts even in a sentence that also negates or disclaims.
    if _CUR_FROM_VERSION.search(sentence):
        return True
    if _CUR_BARE_HEADING.match(sentence):
        return False
    if _CUR_NEGATED.search(sentence) or _CUR_SUBORDINATE.search(sentence):
        return False
    # The disclaimer guard applies to `_CUR_ASSERT` as well as to the paraphrase
    # branches, because the Status-bullet branch matches a sentence merely
    # starting with "In force" and "In-force status: not verified" is what the
    # product now tells the model to write. Scoped to the disclaimer SHAPE so a
    # sentence that hedges and then asserts still counts — see
    # `_CUR_NEGATED_VERB`.
    if _currency_disclaimed(sentence):
        return False
    if _CUR_ASSERT.search(sentence):
        return True
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
    if args.unasked:
        _currency_on_unasked_turns(docs)
    if args.before:
        _invariant_one(Path(args.before), Path(args.dir))
    return 0


def _turn_tool_calls(turn: dict) -> int:
    """Worker tool calls recorded on this turn, across every delegation."""
    return sum(len(dg.get("tools") or [])
               for dg in ((turn.get("audit") or {}).get("delegations") or []))


def blank_verdict(turn: dict) -> tuple:
    """Grade one stored turn against P4.2's invariant.

    Returns `(kind, cost, body_chars, answer_chars)` where kind is one of:

      "ok"          — the lawyer got a body.
      "billed"      — **the violation.** No body, and the turn was charged for.
      "free"        — no body and no charge. Reported, never counted as a
                      violation: 6374 rep 3 turn 3 is the one such turn in 616
                      (0 delegations, 0 tools, $0) and it is a different failure
                      — nothing ran at all, rather than something ran and the
                      answer was lost. The row's acceptance excludes it by
                      construction, which is why the invariant is worded against
                      cost rather than against blankness.

    **The body, not the answer.** `_without_footer` strips the code-emitted scope
    footer P2.2 appends. A blank turn since P2.2 is not an empty string — it is a
    footer with nothing above it, which is what 6383 rep 1 turn 4 looked like on
    screen. Grading on `answer` alone would have scored that turn as fine.

    **Cost is `timing.total_cost_usd`.** There is no `cost_usd` key on a run file;
    looking for one silently grades every turn as free.
    """
    answer = turn.get("answer") or ""
    body = _without_footer(answer)
    cost = float((turn.get("timing") or {}).get("total_cost_usd") or 0.0)
    if body.strip():
        return "ok", cost, len(body.strip()), len(answer)
    return ("billed" if cost > 0 else "free"), cost, 0, len(answer)


def empty_completion_calls(probes: list) -> list:
    """Group `audit.empty_completions` records into provider CALLS.

    Returns one `(attempts, recovered)` pair per call that came back empty at
    least once.

    **One record is one failed ATTEMPT, not one call.** A call that fails all
    three attempts leaves three records, the first two marked `retried: true`.
    The first version of `blanks` counted each `retried: true` record as a
    recovery. On `wave2_p28` (6409 rep 3 turn 11), the first directory with
    schema v3 records in it, that reported "recovered 2, NOT recovered 1" for a
    single call that recovered from nothing. That error flatters the provider.

    A call is recovered when its LAST record says `retried: true`, because the
    retry then succeeded and left no record. Records are grouped by what
    identifies the request (model, payload size, ReAct round) and split
    wherever the attempt number does not continue.
    """
    calls: list = []
    open_calls: dict = {}
    for pr in probes or []:
        if not isinstance(pr, dict):
            continue
        key = (pr.get("model"), pr.get("sent_chars"), pr.get("react_turn"))
        attempt = pr.get("attempt") or 1
        call = open_calls.get(key)
        if call is None or not call["last_retried"] or attempt <= call["last_attempt"]:
            call = {"attempts": 0}
            calls.append(call)
            open_calls[key] = call
        call["attempts"] += 1
        call["last_attempt"] = attempt
        call["last_retried"] = bool(pr.get("retried"))
    return [(c["attempts"], c["last_retried"]) for c in calls]


def cmd_blanks(args) -> int:
    """P4.2 acceptance (deterministic): a non-empty body whenever cost > 0.

    **Why the acceptance is an invariant and not a session-turn pair.** The row
    cites 6370 message #8; the baseline replay blanked at turns 2 and 3 while the
    pre-pilot's turn 2 answered normally, and 6383's Deep Research turn blanked on
    the run after four runs that produced 6,503-9,190 chars. The turn moves. What
    does not move is that a lawyer was charged for a turn that showed them
    nothing.

    Reads `audit.empty_completions` (schema v3) where present: after the fix a
    recovered retry still leaves a record, so a directory can show zero
    violations and a non-zero rate of the underlying provider fault. That
    distinction is the whole reason the diagnostic was built before the fix.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P4.2 acceptance over {args.dir}")
    print()
    rows = []
    turns = free = recovered = unrecovered = attempts = 0
    probes_seen = False
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for t in doc.get("turns", []):
            turns += 1
            kind, cost, body_chars, answer_chars = blank_verdict(t)
            audit = t.get("audit") or {}
            probes = audit.get("empty_completions") or []
            # The KEY, not its truthiness. A healthy v3 turn carries `[]`, and
            # testing `if probes:` reported a clean v3 directory
            # (`wave2_p28_smoke`) as predating the field.
            if "empty_completions" in audit:
                probes_seen = True
                # ~~one record = one recovery if `retried`~~: one record is one
                # failed attempt. See `empty_completion_calls`.
                for n_attempts, ok in empty_completion_calls(probes):
                    attempts += n_attempts
                    if ok:
                        recovered += 1
                    else:
                        unrecovered += 1
            if kind == "ok":
                continue
            if kind == "free":
                free += 1
            rows.append((doc["session_id"], doc.get("rep", 1), t.get("turn"),
                         kind, cost, answer_chars, t.get("chat_mode"),
                         _turn_tool_calls(t), probes))

    bad = [r for r in rows if r[3] == "billed"]
    if rows:
        print(f"{'session':>8} {'rep':>3} {'turn':>4} {'kind':>7} {'cost':>9} "
              f"{'answer':>7} {'tools':>5}  mode")
        print("-" * 72)
        for sid, rep, turn, kind, cost, answer_chars, mode, ntools, probes in rows:
            print(f"{sid:>8} {rep:>3} {turn:>4} {kind:>7} {cost:>9.4f} "
                  f"{answer_chars:>7} {ntools:>5}  {mode or '?'}")
            for pr in probes:
                print(f"{'':>26}   probe: finish_reason={pr.get('finish_reason')} "
                      f"native={pr.get('native_finish_reason')} "
                      f"completion_tokens={pr.get('completion_tokens')} "
                      f"reasoning_chars={pr.get('reasoning_chars')} "
                      f"stream_error={pr.get('stream_error')} "
                      f"retried={pr.get('retried')}")
        print()

    print(f"turns                      {turns}")
    print(f"blank AND billed (VIOLATION) {len(bad)}")
    print(f"blank but free (excluded)    {free}")
    if probes_seen:
        print(f"empty completion attempts               {attempts}")
        print(f"  calls affected, recovered by retry    {recovered}")
        print(f"  calls affected, NOT recovered         {unrecovered}")
        if unrecovered:
            print("  (a call NOT recovered with a body still shown came from a "
                  "worker or was covered by P4.2's fallback; read the turn)")
    else:
        print("empty-completion probes: none recorded "
              "(directory predates audit schema v3)")
    print()
    if bad:
        print("INVARIANT BROKEN: a turn was charged for and showed the lawyer "
              "no body.")
    else:
        print("Invariant holds: every billed turn returned a body.")
    return 0 if not bad else 1


_SCOPE_COUNT = re.compile(r"Searched the legislation index (\d+) time\(s\)")
_SCOPE_SECTIONS = re.compile(r"Searched within (\d+) instrument\(s\)")
_SCOPE_BLOCK_CLOSE = "[/SEARCH SCOPE]"


def scope_record_gap(delegation: dict) -> Optional[tuple]:
    """P2.9 acceptance: did this worker run record every search it issued?

    Returns `(issued, memo_hits, recorded)` for one delegation that issued at
    least one `search_legislation` call, or None if it issued none.

    **Read the block, not the log.** `search_log` is not serialised onto a run
    file; what IS serialised is the worker's report with `worker_scope_block`
    appended, and that block states `Searched the legislation index N time(s)`.
    Comparing N against the delegation's own `tools[]` is therefore a direct
    measure of what the agent writing the negative was actually told.

    **A run whose every search was a memo hit produces no such line at all** —
    the block is still emitted (the other recorders populate `search_log`) but
    carries no searched-for sentence, while still instructing that a negative
    "MUST quote the search terms above". `recorded` is 0 for those, which is the
    honest reading: nothing was recorded.
    """
    tools = [t for t in (delegation.get("tools") or [])
             if t.get("name") == "search_legislation" and _ran(t)]
    if not tools:
        return None
    report = delegation.get("report") or ""
    if _SCOPE_BLOCK_CLOSE not in report:
        # No block at all — this run predates P2.2. Distinguished by the MARKER,
        # not by a recorded count of zero: an all-memo run legitimately has a
        # block with no searched-for line, and inferring block-absence from
        # "recorded == 0" mislabels it as pre-P2.2. That misread made `wave1`
        # report 13 runs "with a scope block" when it has none.
        return None
    m = _SCOPE_COUNT.search(report)
    return len(tools), sum(1 for t in tools if t.get("memo_hit")), (int(m.group(1)) if m else 0)


def cmd_scoperecord(args) -> int:
    """P2.9 acceptance: every search a worker run issued must be in its own record.

    `search_log` is per-WORKER-RUN; the tool memo is per-REQUEST. A step served
    from an earlier step's identical search never recorded that query as its
    own, so it went missing from `worker_scope_block` (what the agent writing
    the negative is told) and from `answer_scope_footer` (what the lawyer is
    told), and the footer's count ran short.

    **`wave1` and `wave2_p21` predate P2.2 and have no scope block at all**, so
    they are reported separately rather than counted — treating "no block" as
    "recorded nothing" inflates the loss roughly fourfold, which is the first
    answer this command gave and it was wrong.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.9 acceptance over {args.dir}")
    print()
    runs = issued = memo = recorded = 0
    no_block = 0
    lossy, mismatch = [], []
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for t in doc.get("turns", []):
            for dg in ((t.get("audit") or {}).get("delegations") or []):
                if not [x for x in (dg.get("tools") or [])
                        if x.get("name") == "search_legislation" and _ran(x)]:
                    continue
                got = scope_record_gap(dg)
                if got is None:
                    no_block += 1
                    continue
                n, mh, rec = got
                tag = f"{doc['session_id']}r{doc.get('rep', 1)}t{t.get('turn')}"
                runs += 1
                issued += n
                memo += mh
                recorded += rec
                lost = n - rec
                if lost > 0:
                    lossy.append((tag, n, rec, mh))
                    if lost != mh:
                        mismatch.append((tag, n, rec, mh))

    if no_block:
        print(f"[!] {no_block} worker run(s) carry no scope block at all — this "
              f"directory predates P2.2. Not counted below.")
        print()
    if not runs:
        print("No worker run in this directory has a scope block to check.")
        return 0

    if lossy:
        print(f"{'run':>18} {'issued':>7} {'recorded':>9} {'memo':>5} {'lost':>5}")
        print("-" * 48)
        for tag, n, rec, mh in lossy:
            print(f"{tag:>18} {n:>7} {rec:>9} {mh:>5} {n - rec:>5}")
        print()

    print(f"worker runs with a scope block        {runs}")
    print(f"search_legislation calls issued       {issued}")
    print(f"  of which memo hits                  {memo}"
          f"  ({100 * memo / issued:.0f}%)" if issued else "")
    print(f"recorded in the run's own block       {recorded}")
    print(f"MISSING from the record               {issued - recorded}")
    print(f"runs losing >=1 query                 {len(lossy)}"
          f"  ({100 * len(lossy) / runs:.0f}%)")
    print()
    # The identity is what identifies the memo as the SOLE cause. If it ever
    # fails, something other than a memo hit is eating the record and this row's
    # one-line fix is not the whole answer.
    # Only meaningful while something is missing. After P2.9 a memo hit IS
    # recorded, so on a complete record `issued - recorded` is 0 and the memo
    # count is not. Printing `False` there read as a fault on the first
    # post-P2.9 directory (`wave2_p28`), when it is the fix working.
    if issued - recorded:
        print(f"identity  (issued - recorded) == memo hits : "
              f"{issued - recorded == memo}")
    else:
        print("identity  (issued - recorded) == memo hits : n/a, nothing is "
              "missing (memo hits are recorded)")
    print(f"runs where the loss is NOT the memo count  : {len(mismatch)}"
          + (f"  {mismatch[:5]}" if mismatch else ""))
    print()
    if issued - recorded:
        print("RECORD INCOMPLETE: a search the run issued is absent from the "
              "record it hands the agent that writes the negative.")
    else:
        print("Record complete: every search issued is in its run's own record.")
    return 0 if issued == recorded else 1


# P2.8's carried scope line (`search_scope.carried_scope_footer`), identified by
# its fixed opening clause. A fresh footer says the opposite, in these words.
CARRIED_SCOPE = "no search of the legislation index was run for this reply"
FRESH_SCOPE = "*Search scope: the legislation index was searched for"
_LEG_SEARCH_TOOLS = ("search_legislation", "search_legislation_sections")


def nosearch_rows(doc: dict) -> list:
    """Every answered turn in one run that ran no legislation search.

    **Promoted from the ad-hoc script in SESSION_LOG Session 12**, which used
    the wrong regex. Asserting a negative is graded with `NEG_ASSERTED` (P2.2's
    acceptance detector) on the model's prose with the footer removed, exactly
    as `cmd_negatives` selects its denominator. It is **not** graded with
    `NOT_FOUND`, the P0.3 baseline regex. That regex found 1 turn of shape (A)
    where there are 5, and led to a recommendation to close a real defect.

    Shapes, by what the audit trace shows ran:
      "A" — no delegation at all. The Manager answered from the history.
      "B" — delegated, and the Worker made zero tool calls (Session 12's (B)).
      "C" — delegated, tools ran, none of them a legislation search.

    `searched_before` is true when an EARLIER answered turn in this run searched
    the legislation index. Only answered turns count, because only they join the
    history the next turn is sent (`replay.py`). It is the audit-side mirror of
    the product's gate, which reads the fresh footer out of that history.

    `line` is "carried", "fresh" or "none": the scope statement the lawyer saw.
    """
    rows = []
    searched_before = False
    for t in doc.get("turns", []):
        answer = t.get("answer") or ""
        audit = t.get("audit") or {}
        dgs = audit.get("delegations") or []
        tools = [x for dg in dgs for x in (dg.get("tools") or [])]
        searched_now = any(x.get("name") in _LEG_SEARCH_TOOLS and _ran(x) for x in tools)
        if answer.strip():
            bare = _without_footer(answer)
            if CARRIED_SCOPE in answer:
                line = "carried"
            elif FRESH_SCOPE in answer:
                line = "fresh"
            else:
                line = "none"
            rows.append({
                "turn": t.get("turn"),
                "searched_now": searched_now,
                "shape": ("A" if not dgs else "B" if not tools else "C"),
                "neg": bool(NEG_ASSERTED.search(bare)),
                "searched_before": searched_before,
                "line": line,
                "peer": bool(audit.get("peer_consults")),
                "chars": len(bare),
            })
            if searched_now:
                searched_before = True
    return rows


def nosearch_verdict(row: dict) -> Optional[str]:
    """P2.8's acceptance for one answered turn. None means nothing wrong.

    "UNQUALIFIED" — the defect. The turn searched nothing, an earlier turn did,
                    the model asserts a negative, and the lawyer saw no scope
                    statement beside it.
    "MISATTRIBUTED" — the row's other half. A scope statement describes a search
                    this turn did not run: a fresh footer on a turn that searched
                    nothing, a carried line on a turn that searched, or a carried
                    line with no earlier search behind it.

    A peer-consult turn is exempt from UNQUALIFIED. The product stays silent
    there on purpose, because the peer's searches are not in this turn's record.
    """
    if row["searched_now"]:
        return "MISATTRIBUTED" if row["line"] == "carried" else None
    if row["line"] == "fresh":
        return "MISATTRIBUTED"
    if row["line"] == "carried" and not row["searched_before"]:
        return "MISATTRIBUTED"
    if (row["neg"] and row["searched_before"] and row["line"] == "none"
            and not row["peer"]):
        return "UNQUALIFIED"
    return None


def cmd_nosearch(args) -> int:
    """P2.8 acceptance (with P2.10 folded in): replies that searched nothing.

    **Exits 1 on a finding**, like `negatives` and `scoperecord`. A directory
    with no scope footer anywhere predates P2.2. It is reported and exits 0,
    because nothing there could have carried a scope statement.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.8 acceptance over {args.dir}")
    print("  shape A = no delegation;  B = delegated, zero tool calls;")
    print("          C = delegated, tools ran, no legislation search")
    print("  neg     = NEG_ASSERTED on the model's prose (footer removed)")
    print("  before  = an earlier answered turn searched the legislation index")
    print("  line    = the scope statement the lawyer saw")
    print()
    has_footers = any("*Search scope:" in (t.get("answer") or "")
                      for d in docs for t in d.get("turns", []))
    answered = negs = 0
    counts = {s: [0, 0] for s in "ABC"}          # [turns, of which neg]
    # `after_neg` is the fraction of the carried line's firings that had a
    # negative to qualify. It is P2.8's measured cost, published in BASELINE.md.
    after_search = after_neg = carried = 0
    listed = []
    bad = []
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        for row in nosearch_rows(doc):
            answered += 1
            negs += row["neg"]
            verdict = nosearch_verdict(row)
            if verdict:
                bad.append((doc, row, verdict))
            if row["searched_now"]:
                continue
            counts[row["shape"]][0] += 1
            counts[row["shape"]][1] += row["neg"]
            if row["searched_before"]:
                after_search += 1
                after_neg += row["neg"]
                carried += row["line"] == "carried"
            if args.all or row["neg"] or verdict:
                listed.append((doc, row, verdict))

    if listed:
        print(f"{'session':>8} {'rep':>3} {'turn':>4} {'shape':>5} {'neg':>4} "
              f"{'before':>6} {'line':>8} {'peer':>4} {'chars':>6}  verdict")
        print("-" * 72)
        for doc, row, verdict in listed:
            print(f"{doc['session_id']:>8} {doc.get('rep', 1):>3} {row['turn']:>4} "
                  f"{row['shape']:>5} {('yes' if row['neg'] else '-'):>4} "
                  f"{('yes' if row['searched_before'] else '-'):>6} "
                  f"{row['line']:>8} {('yes' if row['peer'] else '-'):>4} "
                  f"{row['chars']:>6}  {verdict or 'ok'}")
            if args.answers:
                turn = next(t for t in doc["turns"] if t.get("turn") == row["turn"])
                print(f"{'':>10}Q: {str(turn.get('question') or '')[:args.chars]}")
                print(f"{'':>10}A: {(turn.get('answer') or '')[:args.chars]}")
        print()

    print(f"answered turns                               {answered}")
    print(f"  asserting a negative (NEG_ASSERTED)        {negs}")
    for s, label in (("A", "no delegation"),
                     ("B", "delegated, zero tool calls"),
                     ("C", "delegated, no legislation search")):
        print(f"  ({s}) {label:<36} {counts[s][0]:>4}   of which negative {counts[s][1]}")
    print(f"no-search turns after a searched turn        {after_search}"
          f"   of which negative {after_neg}   carrying the carried line {carried}")
    print()
    unq = [b for b in bad if b[2] == "UNQUALIFIED"]
    mis = [b for b in bad if b[2] == "MISATTRIBUTED"]
    print(f"UNQUALIFIED   restated negative, no scope statement   {len(unq)}")
    print(f"MISATTRIBUTED scope statement for a search not run    {len(mis)}")
    for doc, row, verdict in mis:
        print(f"    {doc['session_id']} r{doc.get('rep', 1)} t{row['turn']}: "
              f"line={row['line']} searched_now={row['searched_now']} "
              f"before={row['searched_before']}")
    print()
    if args.before:
        _invariant_one_prose(Path(args.before), Path(args.dir), args.only)
        print()
    if not has_footers:
        print("[!] No answer in this directory carries a scope footer: it predates "
              "P2.2, so nothing could have been qualified. Not a pass, an absence. "
              "Exit 0.")
        return 0
    return 0 if not bad else 1


def _invariant_one_prose(before: Path, after: Path, only: Optional[list]) -> None:
    """Invariant 1 for P2.8: did the MODEL's answers shrink, or stop reporting
    negatives, once the carried line existed?

    **Graded on the prose with the footer removed, unlike `_invariant_one`.**
    P2.8 appends a line to answers that had none, so full answers grow by
    construction and a full-length comparison would pass whatever the model did.
    Shared sessions only, and `--only` narrows further: 6409's before-column is
    `wave2_p22_final` and 6341's is `wave2_p25`. That is two runs of this
    command, not one run over a merged population.
    """
    def load(d: Path):
        docs = [x for x in load_runs(d)
                if not only or str(x.get("session_id")) in only]
        return {str(x["session_id"]) for x in docs}, docs

    b_ids, b_docs = load(before)
    a_ids, a_docs = load(after)
    shared = b_ids & a_ids
    if not shared:
        print(f"  --before: no session shared with {before.name}")
        return

    def measure(docs):
        slots, per_run = {}, {}
        for doc in docs:
            sid = str(doc["session_id"])
            if sid not in shared:
                continue
            run = per_run.setdefault((sid, doc.get("rep", 1)),
                                     {"neg": 0, "nosearch": 0, "tools": 0, "turns": 0})
            for row in nosearch_rows(doc):
                slots.setdefault((sid, row["turn"]), []).append(row["chars"])
                run["turns"] += 1
                run["neg"] += row["neg"]
                run["nosearch"] += not row["searched_now"]
            run["tools"] += sum(_turn_tool_calls(t) for t in doc.get("turns", []))
        return slots, per_run

    (b_slots, b_runs), (a_slots, a_runs) = measure(b_docs), measure(a_docs)
    print(f"  Invariant 1 (model prose, footer removed): {before.name} -> "
          f"{after.name}, sessions {', '.join(sorted(shared))}")
    for sid in sorted(shared):
        def per_rep(runs, key):
            vals = [v[key] for (s, _), v in runs.items() if s == sid]
            return sum(vals) / max(len(vals), 1), len(vals)
        for key, label in (("turns", "answered turns / rep"),
                           ("neg", "turns asserting a negative / rep"),
                           ("nosearch", "turns that searched nothing / rep"),
                           ("tools", "worker tool calls / rep")):
            (bv, bn), (av, an) = per_rep(b_runs, key), per_rep(a_runs, key)
            print(f"    {sid} {label:<36} {bv:7.1f} (n={bn}) -> {av:7.1f} (n={an})")
        common = sorted(k for k in set(b_slots) & set(a_slots) if k[0] == sid)
        grew = 0
        lines = []
        for k in common:
            bm = sum(b_slots[k]) / len(b_slots[k])
            am = sum(a_slots[k]) / len(a_slots[k])
            grew += am > bm
            lines.append(f"      t{k[1]:<3} {bm:7.0f} -> {am:7.0f}  "
                         f"{'grew' if am > bm else 'shrank'}")
        print(f"    {sid} mean prose length per turn slot: {grew} of "
              f"{len(common)} grew")
        for ln in lines:
            print(ln)


# --- P2.4 (B12) acceptance: the case-law corpus gap --------------------------
#
# **Why `SCOTS_CASELAW_GAP` cannot grade this row, in both directions.**
#
# (1) It over-reads. It fires on the mere mention of a Scottish court, so
#     *"Rule 35.8 of the Rules of the Court of Session 1994"*, *"the Clerk of the
#     Sheriff Appeal Court"* and *"sheriff court jurisdiction"* all count as a
#     disclosure. Over the twelve pre-P2.4 directories it fires on 26 answered
#     turns. 22 of them never searched case law, and only one of those 22
#     (`wave1/6408 r1 t3`) actually states the gap. It is left as it is,
#     because `summary` and `compare` publish its count; `caselaw` uses
#     `caselaw_gap_statements` instead.
# (2) After P2.4 it is satisfied by construction. The code line names the Court
#     of Session on every turn that searched case law, so a full-answer read
#     cannot tell the code's disclosure from the model's. Hence the split, as in
#     `negatives`: "disclosed" on the full answer, "model" on the prose with the
#     footer removed.
#
# `caselaw_gap_statements` asks for three things in ONE sentence: a Scottish
# court (or Scottish case law) is named, the corpus is named ("index",
# "database", "covers", "includes", …), and a limit is stated ("not", "only",
# "except", …). Validated over all twelve pre-P2.4 directories with `--drops`
# (every sentence naming a Scottish court that was NOT counted) and `--answers`
# (every one that was).

# The code's own sentence, by its fixed opening. `search_scope.
# CASE_LAW_COVERAGE_SENTENCE` starts with it; `test_case_law_gap.py` pins that.
CASE_LAW_CODE = ("It holds Scottish appeals decided by the UK Supreme Court, "
                 "but not the decisions of the Court of Session")
_SCOTS_COURT = re.compile(
    r"court of session|\bcs(?:oh|ih)\b|sheriff (?:appeal )?courts?\b"
    r"|high court of justiciary|scottish (?:domestic )?(?:courts?|case ?law|cases|"
    r"judgments?|decisions|jurisprudence)\b|courts? (?:of|in) scotland",
    re.I,
)
_GAP_CORPUS = re.compile(
    r"\b(?:index\w*|database|corpus|collection|cover\w*|includ\w*|holds?|"
    r"contain\w*|available|represented|hosts?|national archives|find case law)\b",
    re.I,
)
_GAP_LIMIT = re.compile(
    r"\b(?:not|no|only|except|unless|outside|exclud\w*|absent|missing|lacks?|"
    r"neither|nor|without)\b|n't\b",
    re.I,
)
_UKSC = re.compile(r"supreme court|\buksc\b", re.I)
_CASELAW_URL = re.compile(r"\]\((https?://caselaw\.nationalarchives\.gov\.uk/([a-z]+)/[^)\s]+)\)", re.I)
# How the National Archives titles a Scottish appeal. A proxy, and a
# conservative one: it can miss a Scottish appeal whose title names none of
# these, never the reverse in practice.
_SCOTTISH_TITLE = re.compile(
    r"\(scotland\)|lord advocate|\b(?:hm|his majesty's|her majesty's) advocate\b"
    r"|scottish ministers|advocate general for scotland|principal reporter",
    re.I,
)


# A court's name inside an instrument's title is not the court. Found by the
# all-turns audit, not the case-law-turn one: `baseline/6372 r3 t2`, *"the Rules
# of the Court of Session 1994 … do not contain an explicit provision"*, has a
# court, a corpus-ish verb and a negation, and says nothing about case law.
_COURT_IN_TITLE = re.compile(
    r"rules of the (?:court of session|sheriff (?:appeal )?court)\b"
    r"|(?:court of session|sheriff (?:appeal )?courts?) (?:rules|fees|act)\b"
    r"|act of sederunt|courts reform \(scotland\)",
    re.I,
)


def caselaw_gap_statements(text: str) -> list:
    """Every sentence that states the case-law corpus gap. [] for none."""
    out = []
    for sentence in _sentences(text or ""):
        s = sentence.replace(_DOT, ".")
        if (_SCOTS_COURT.search(_COURT_IN_TITLE.sub(" ", s))
                and _GAP_CORPUS.search(s) and _GAP_LIMIT.search(s)):
            out.append(s.strip())
    return out


def _caselaw_titles(turn: dict) -> dict:
    """url -> title, from every `search_case_law` result this turn retrieved."""
    titles = {}
    for dg in (turn.get("audit") or {}).get("delegations") or []:
        for tl in dg.get("tools") or []:
            if tl.get("name") != "search_case_law":
                continue
            o = _json_or_none(tl.get("raw_result"))
            for r in (o.get("results") or []) if isinstance(o, dict) else []:
                if isinstance(r, dict) and r.get("url"):
                    titles[str(r["url"]).rstrip("/")] = str(r.get("title") or "")
    return titles


def caselaw_rows(doc: dict) -> list:
    """One row per answered turn: what it searched, and what the lawyer was told."""
    rows = []
    for t in doc.get("turns", []):
        answer = t.get("answer") or ""
        if not answer.strip():
            continue
        tools = [x for dg in (t.get("audit") or {}).get("delegations") or []
                 for x in dg.get("tools") or []]
        prose = _without_footer(answer)
        model = caselaw_gap_statements(prose)
        titles = _caselaw_titles(t)
        uksc = {u.rstrip("/") for u, court in _CASELAW_URL.findall(prose)
                if court.lower() == "uksc"}
        rows.append({
            "turn": t.get("turn"),
            "mode": t.get("chat_mode") or "",
            "cl_calls": sum(1 for x in tools if x.get("name") == "search_case_law"),
            "disclosed": bool(caselaw_gap_statements(answer)),
            "code": CASE_LAW_CODE in answer,
            "model": model,
            "model_names_uksc": any(_UKSC.search(s) for s in model),
            "lines": answer.count("*Search scope:"),
            "chars": len(prose),
            "caselaw_links": len({u for u, _ in _CASELAW_URL.findall(prose)}),
            "uksc_cited": len(uksc),
            "uksc_scottish_cited": sum(
                1 for u in uksc if _SCOTTISH_TITLE.search(titles.get(u, ""))),
        })
    return rows


def caselaw_verdict(row: dict) -> Optional[str]:
    """P2.4's acceptance for one answered turn. None means nothing wrong.

    "UNDISCLOSED"   — the turn searched case law and the lawyer was not told
                      what the corpus lacks. The defect.
    "MISATTRIBUTED" — the code's line on a turn that searched no case law.
    "TWO_LINES"     — more than one `*Search scope:` line. The clause must join
                      the legislation line, never follow it: P2.8's parse reads
                      only the last line, and `corpus` counts two as a duplicate.
    """
    if row["cl_calls"] and not row["disclosed"]:
        return "UNDISCLOSED"
    if row["code"] and not row["cl_calls"]:
        return "MISATTRIBUTED"
    if row["lines"] > 1:
        return "TWO_LINES"
    return None


def cmd_caselaw(args) -> int:
    """P2.4 acceptance: every turn that searched case law, and its disclosure.

    **Exits 1 on a finding**, like `negatives`, `nosearch` and `halts`. A
    directory that predates P2.4 exits 1 too, and says so: its UNDISCLOSED rows
    ARE the before-column. It is deliberately not excused the way `nosearch`
    excuses a pre-P2.2 directory, because "no code line anywhere" is also what a
    post-P2.4 directory looks like if the wiring silently failed.
    """
    docs = load_runs(Path(args.dir))
    if not docs:
        print(f"No run files in {args.dir}")
        return 1
    print(f"P2.4 acceptance over {args.dir}")
    print("  cl        = search_case_law calls this turn (audit trace)")
    print("  disclosed = the gap is stated anywhere in the answer the lawyer saw")
    print("  code      = the code-emitted line is present")
    print("  model     = the gap is stated in the model's prose (footer removed)")
    print("  uksc/scot = UK Supreme Court judgments linked in the prose, and how")
    print("              many of those are Scottish appeals (by their TNA title)")
    print()
    bad = []
    per = {}
    listed = []
    for doc in sorted(docs, key=lambda d: (d["session_id"], d.get("rep", 1))):
        sid = str(doc["session_id"])
        agg = per.setdefault(sid, dict(runs=0, turns=0, disclosed_all=0, cl=0,
                                       disclosed=0, code=0, model=0))
        agg["runs"] += 1
        for row in caselaw_rows(doc):
            agg["turns"] += 1
            agg["disclosed_all"] += row["disclosed"]
            verdict = caselaw_verdict(row)
            if verdict:
                bad.append((doc, row, verdict))
            if row["cl_calls"]:
                agg["cl"] += 1
                agg["disclosed"] += row["disclosed"]
                agg["code"] += row["code"]
                agg["model"] += bool(row["model"])
            if args.all or row["cl_calls"] or verdict:
                listed.append((doc, row, verdict))

    if listed:
        print(f"{'session':>8} {'rep':>3} {'turn':>4} {'mode':>13} {'cl':>3} "
              f"{'disclosed':>9} {'code':>4} {'model':>5} {'uksc':>4} {'scot':>4} "
              f"{'chars':>6}  verdict")
        print("-" * 84)
        for doc, row, verdict in listed:
            yn = lambda v: "yes" if v else "-"   # noqa: E731
            print(f"{doc['session_id']:>8} {doc.get('rep', 1):>3} {row['turn']:>4} "
                  f"{row['mode'][:13]:>13} {row['cl_calls']:>3} "
                  f"{yn(row['disclosed']):>9} {yn(row['code']):>4} "
                  f"{yn(row['model']):>5} {row['uksc_cited']:>4} "
                  f"{row['uksc_scottish_cited']:>4} {row['chars']:>6}  "
                  f"{verdict or 'ok'}")
            if args.answers:
                for s in row["model"]:
                    print(f"{'':>10}model: {s[:args.chars]}")
        print()

    print(f"{'session':>8} {'runs':>4} {'turns':>5} {'disclosing':>10} | "
          f"{'searched case law':>17} {'disclosed':>9} {'code':>4} {'model':>5}")
    for sid, a in sorted(per.items()):
        print(f"{sid:>8} {a['runs']:>4} {a['turns']:>5} {a['disclosed_all']:>10} | "
              f"{a['cl']:>17} {a['disclosed']:>9} {a['code']:>4} {a['model']:>5}")
    tot = {k: sum(a[k] for a in per.values()) for k in
           ("turns", "disclosed_all", "cl", "disclosed", "code", "model")}
    print(f"{'total':>8} {'':>4} {tot['turns']:>5} {tot['disclosed_all']:>10} | "
          f"{tot['cl']:>17} {tot['disclosed']:>9} {tot['code']:>4} {tot['model']:>5}")
    stated = [(r, s) for _, r, _ in listed for s in r["model"]]
    if stated:
        with_uksc = sum(1 for r, s in stated if _UKSC.search(s))
        print(f"model statements of the gap: {len(stated)}, of which name the UK "
              f"Supreme Court route: {with_uksc}")
    print()
    counts = Counter(v for _, _, v in bad)
    for v in ("UNDISCLOSED", "MISATTRIBUTED", "TWO_LINES"):
        print(f"{v:<14}{counts[v]}")
    if args.drops:
        print()
        print("Sentences naming a Scottish court that were NOT graded as a "
              "statement of the gap (both-directions audit):")
        for doc in docs:
            for t in doc.get("turns", []):
                for s in _sentences(_without_footer(t.get("answer") or "")):
                    s = s.replace(_DOT, ".")
                    if _SCOTS_COURT.search(s) and not caselaw_gap_statements(s):
                        print(f"  {doc['session_id']} r{doc.get('rep', 1)} "
                              f"t{t.get('turn')}: {s.strip()[:args.chars]}")
    if args.before:
        print()
        _caselaw_invariant_one(Path(args.before), Path(args.dir), args.only)
    if not tot["code"] and tot["cl"]:
        print()
        print("[!] No turn carries the code line: this directory predates P2.4, "
              "or the wiring failed. Its UNDISCLOSED rows are a before-column.")
    return 0 if not bad else 1


def _caselaw_invariant_one(before: Path, after: Path, only: Optional[list]) -> None:
    """Invariant 1 for P2.4, on the prose with the footer removed.

    The line must make answers more precise about the corpus without making the
    model less willing to cite a sound Scottish appeal to the UK Supreme Court.
    So per session, per rep: answered turns, case-law calls, prose length per
    turn slot, case-law links cited, UKSC links cited, and how many of those
    are Scottish appeals.
    """
    def load(d: Path):
        return [x for x in load_runs(d)
                if not only or str(x.get("session_id")) in only]

    b_docs, a_docs = load(before), load(after)
    shared = ({str(x["session_id"]) for x in b_docs}
              & {str(x["session_id"]) for x in a_docs})
    if not shared:
        print(f"  --before: no session shared with {before.name}")
        return

    def measure(docs):
        slots, runs = {}, {}
        for doc in docs:
            sid = str(doc["session_id"])
            if sid not in shared:
                continue
            run = runs.setdefault((sid, doc.get("rep", 1)), Counter())
            for row in caselaw_rows(doc):
                slots.setdefault((sid, row["turn"]), []).append(row["chars"])
                run["turns"] += 1
                run["cl"] += row["cl_calls"]
                run["links"] += row["caselaw_links"]
                run["uksc"] += row["uksc_cited"]
                run["scot"] += row["uksc_scottish_cited"]
                run["model"] += bool(row["model"])
        return slots, runs

    (b_slots, b_runs), (a_slots, a_runs) = measure(b_docs), measure(a_docs)
    print(f"  Invariant 1 (model prose, footer removed): {before.name} -> "
          f"{after.name}, sessions {', '.join(sorted(shared))}")
    for sid in sorted(shared):
        for key, label in (("turns", "answered turns / rep"),
                           ("cl", "search_case_law calls / rep"),
                           ("links", "case-law judgments linked / rep"),
                           ("uksc", "UKSC judgments linked / rep"),
                           ("scot", "... of which Scottish appeals / rep"),
                           ("model", "turns stating the gap in prose / rep")):
            bv = [v[key] for (s, _), v in b_runs.items() if s == sid]
            av = [v[key] for (s, _), v in a_runs.items() if s == sid]
            print(f"    {sid} {label:<38} {sum(bv) / max(len(bv), 1):7.1f} "
                  f"(n={len(bv)}) -> {sum(av) / max(len(av), 1):7.1f} (n={len(av)})")
        common = sorted(k for k in set(b_slots) & set(a_slots) if k[0] == sid)
        grew = 0
        lines = []
        for k in common:
            bm = sum(b_slots[k]) / len(b_slots[k])
            am = sum(a_slots[k]) / len(a_slots[k])
            grew += am > bm
            lines.append(f"      t{k[1]:<3} {bm:7.0f} -> {am:7.0f}  "
                         f"{'grew' if am > bm else 'shrank'}")
        print(f"    {sid} mean prose length per turn slot: {grew} of "
              f"{len(common)} grew")
        for ln in lines:
            print(ln)


# --- P2.7 pre-flight: the discovery distribution a budget must come from ------
#
# P2.7's row: "the right number must come from the distribution, not a guess".
# This prints it, per WORKER RUN (one audit delegation: a Manager
# `delegate_research` or one Deep Research step), because a search budget is
# created per `run_worker_agent` call. Written at the end of Session 14 so the
# P2.7 session starts from a command, not from a throwaway script.
#
# **Calls, not rounds.** The step cap counts ReAct rounds and the model batches
# calls within a round: `wave2_p28/6341 r1 t7` step 2 halted at 20 rounds with
# 41 tool calls. A per-call budget and a per-round cap are different units.
#
# **Memo hits are excluded from the "issued" count**, because the parliamentary
# budget's design never charges a memo hit (`run_worker_tool` returns before
# the budget check). ~~and the same would presumably hold for legislation~~
# **It does not: P2.7 (Session 15) charges them**, because 57 of the 81 memo
# hits on post-P3.5 halted runs repeat the same step's own search. They are
# printed separately, and they count in "search rounds", which is P2.7's unit.
#
# A measurement, not a check: always exits 0.

_DISCOVERY_TOOLS = ("search_legislation", "search_case_law")
_RETRIEVAL_TOOLS = ("search_legislation_sections", "get_legislation_text",
                    "get_case_law_text", "get_legislation_changes")
_BUDGETS = (3, 4, 5, 6, 8, 10, 12, 15, 20)
_ROUND_BUDGETS = (4, 5, 6, 7, 8, 10, 12)

# **P2.7 built its budget on ROUNDS, so this command counts them too.** A round
# is not recorded on a tool record; it is rebuilt from `started_at`. The calls
# of one round are created together and start within milliseconds, and rounds
# are separated by an LLM call that takes seconds. Checked on the 13 post-P3.5
# halted runs: the rebuilt count is 20 on every one, which is the cap. The
# command prints that agreement on every directory it reads, so a drift in the
# method shows up where it is used.
_ROUND_GAP_S = 1.0


def _rounds(tools: list) -> list:
    """The worker run's tool records, grouped into ReAct rounds by start time."""
    rounds, cur, last = [], [], None
    for tl in sorted(tools, key=lambda x: float(x.get("started_at") or 0)):
        s = float(tl.get("started_at") or 0)
        if cur and last is not None and s - last > _ROUND_GAP_S:
            rounds.append(cur)
            cur = []
        cur.append(tl)
        last = s
    if cur:
        rounds.append(cur)
    return rounds


def discovery_runs(doc: dict) -> list:
    """One row per worker run in a replay run file."""
    rows = []
    for t in doc.get("turns", []):
        for dg in (t.get("audit") or {}).get("delegations") or []:
            tools = dg.get("tools") or []
            issued = Counter()
            memo = Counter()
            refused = Counter()     # P2.7: stopped by a discovery budget, never ran
            keys = Counter()        # (tool, resource): production's redundancy key
            exact = Counter()       # (tool, resource, query): a literal repeat
            queries = set()
            for tl in tools:
                nm = tl.get("name") or "?"
                a = tl.get("args") or {}
                if not _ran(tl):
                    refused[nm] += 1
                    continue
                if tl.get("memo_hit"):
                    memo[nm] += 1
                else:
                    issued[nm] += 1
                if nm == "search_legislation":
                    queries.add(re.sub(r"\s+", " ", str(a.get("query") or "")).strip().lower())
                if nm in _RETRIEVAL_TOOLS:
                    key = a.get("legislation_id") or a.get("url") or ""
                    if a.get("direction"):
                        key = f"{key}:{a['direction']}"
                    keys[(nm, key)] += 1
                    exact[(nm, key, str(a.get("query") or ""))] += 1
            halted = dg.get("halted") or None
            # Audit schema v1 (before P2.1) has no `halted` field. Fall back to
            # the marker in the report, as `halts` does. Before P2.6 the A4
            # reformat retry could rewrite that marker away (6340), so on a v1
            # directory the halted count is a floor.
            marker = bool(HALT_LITERAL.search(dg.get("report") or ""))
            rounds = _rounds(tools)
            rows.append({
                "session": str(doc.get("session_id")),
                "rep": doc.get("rep", 1),
                "turn": t.get("turn"),
                "kind": dg.get("kind") or "",
                "step": dg.get("step"),
                "halted": bool(halted) or marker,
                "halt_source": "meta" if halted else ("marker" if marker else ""),
                "schema": (t.get("audit") or {}).get("schema_version"),
                "rounds": (halted or {}).get("steps"),
                # Rebuilt from start times (see `_rounds`): rounds with any tool
                # call, and rounds in which a legislation search RAN (memo
                # hits count, refused calls do not), which is what the P2.7
                # budget charges.
                "rounds_rebuilt": len(rounds),
                "search_rounds": sum(
                    1 for r in rounds
                    if any(x.get("name") == "search_legislation" and _ran(x) for x in r)
                ),
                "leg_refused": refused["search_legislation"],
                "tools": len(tools),
                "leg": issued["search_legislation"],
                "leg_memo": memo["search_legislation"],
                "leg_distinct": len(queries - {""}),
                "cl": issued["search_case_law"],
                "cl_memo": memo["search_case_law"],
                "sections": issued["search_legislation_sections"] + memo["search_legislation_sections"],
                "text": issued["get_legislation_text"] + memo["get_legislation_text"],
                "judgments": issued["get_case_law_text"] + memo["get_case_law_text"],
                "changes": issued["get_legislation_changes"] + memo["get_legislation_changes"],
                # `same_resource` mirrors `TimingCollector.record_worker_tool`'s
                # key (tool + resource), but per worker run, not per request.
                "same_resource": sum(n - 1 for n in keys.values() if n > 1),
                "repeat_retrievals": sum(n - 1 for n in exact.values() if n > 1),
                "budget_blocked": sum(1 for tl in tools if tl.get("budget_blocked")),
            })
    return rows


def _pct(values: list, q: float):
    if not values:
        return "-"
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def cmd_discovery(args) -> int:
    """P2.7 pre-flight: discovery calls per worker run, halted vs completed."""
    dirs = [Path(args.dir)] + [Path(d) for d in (args.also or [])]
    rows = []
    for d in dirs:
        for doc in load_runs(d):
            if args.only and str(doc.get("session_id")) not in args.only:
                continue
            for r in discovery_runs(doc):
                rows.append({**r, "dir": d.name})
    if not rows:
        print(f"No worker runs in {', '.join(str(d) for d in dirs)}")
        return 0
    halted = [r for r in rows if r["halted"]]
    done = [r for r in rows if not r["halted"]]
    print(f"P2.7 discovery distribution over {', '.join(d.name for d in dirs)}")
    print(f"  worker runs {len(rows)}  (halted {len(halted)}, completed {len(done)})")
    print(f"  sessions: {', '.join(sorted({r['session'] for r in rows}))}")
    print("  issued = calls that reached the API (memo hits excluded; P2.7 charges them by round)")
    v1 = sum(1 for r in rows if (r["schema"] or 1) < 2)
    if v1:
        print(f"  [!] {v1} run(s) predate audit schema v2, so their halts are read from the")
        print("      report marker, which the pre-P2.6 reformat retry could erase: a floor.")
        print(f"      halted by marker: {sum(1 for r in halted if r['halt_source'] == 'marker')}")
    print()
    refused = sum(r["leg_refused"] for r in rows)
    print(f"  search_legislation calls REFUSED by the P2.7 budget: {refused}, "
          f"in {sum(1 for r in rows if r['leg_refused'])} run(s)  "
          "(excluded from every count below)")
    metas = [r for r in halted if r["halt_source"] == "meta" and r["rounds"]]
    if metas:
        agree = sum(1 for r in metas if r["rounds_rebuilt"] == r["rounds"])
        print(f"  round rebuild agrees with the halt metadata on {agree} of "
              f"{len(metas)} halted run(s)")
    print()
    print(f"{'per worker run':<44} {'n':>4} {'med':>5} {'p75':>5} {'p90':>5} {'max':>5}")
    for label, key in (("search_legislation issued", "leg"),
                       ("search_legislation SEARCH ROUNDS", "search_rounds"),
                       ("search_legislation memo hits", "leg_memo"),
                       ("search_legislation distinct queries (memo incl.)", "leg_distinct"),
                       ("search_case_law issued", "cl"),
                       ("discovery issued (both)", None),
                       ("retrieval calls (4 tools, memo incl.)", "retr"),
                       ("same-resource retrievals (prod. key)", "same_resource"),
                       ("exact repeat retrievals (+query)", "repeat_retrievals"),
                       ("tool calls, all", "tools")):
        for group, grp in (("halted", halted), ("completed", done)):
            if key is None:
                vals = [r["leg"] + r["cl"] for r in grp]
            elif key == "retr":
                vals = [r["sections"] + r["text"] + r["judgments"] + r["changes"] for r in grp]
            else:
                vals = [r[key] for r in grp]
            print(f"  {label + ' — ' + group:<42} {len(vals):>4} {_pct(vals, .5):>5} "
                  f"{_pct(vals, .75):>5} {_pct(vals, .9):>5} {max(vals) if vals else '-':>5}")
    print()
    print("If a per-run budget of N issued calls existed, runs that would have been")
    print("stopped (a call beyond N), and the calls it would have blocked:")
    print(f"{'N':>4} | {'search_legislation only':^34} | {'search_legislation + search_case_law':^38} | "
          f"{'search_legislation incl. memo hits':^34}")
    print(f"{'':>4} | {'halted':>10} {'completed':>11} {'blocked':>9} | "
          f"{'halted':>10} {'completed':>11} {'blocked':>13} | "
          f"{'halted':>10} {'completed':>11} {'blocked':>9}")
    for n in _BUDGETS:
        def hit(grp, f):
            return sum(1 for r in grp if f(r) > n)
        leg = lambda r: r["leg"]                      # noqa: E731
        both = lambda r: r["leg"] + r["cl"]           # noqa: E731
        memo = lambda r: r["leg"] + r["leg_memo"]     # noqa: E731
        print(f"{n:>4} | {hit(halted, leg):>4} of {len(halted):<3} {hit(done, leg):>5} of {len(done):<4} "
              f"{sum(max(0, leg(r) - n) for r in rows):>7} | "
              f"{hit(halted, both):>4} of {len(halted):<3} {hit(done, both):>5} of {len(done):<4} "
              f"{sum(max(0, both(r) - n) for r in rows):>9} | "
              f"{hit(halted, memo):>4} of {len(halted):<3} {hit(done, memo):>5} of {len(done):<4} "
              f"{sum(max(0, memo(r) - n) for r in rows):>7}")
    print()
    print("P2.7 counts ROUNDS in which search_legislation ran (memo hits included).")
    print("Runs with more than K search rounds, i.e. runs a budget of K would stop.")
    print("On a directory taken WITH the budget, no run should exceed its K.")
    print(f"{'K':>4} | {'halted':>10} {'completed':>11}")
    for k in _ROUND_BUDGETS:
        print(f"{'K' + str(k):>4} | "
              f"{sum(1 for r in halted if r['search_rounds'] > k):>4} of {len(halted):<3} "
              f"{sum(1 for r in done if r['search_rounds'] > k):>5} of {len(done):<4}")
    if args.runs or args.all:
        print()
        print(f"{'dir':<16} {'sess':>5} {'rep':>3} {'turn':>4} {'kind':<18} {'stp':>3} "
              f"{'halt':>4} {'rnd':>4} {'srnd':>4} {'tools':>5} {'leg':>4} {'memo':>4} "
              f"{'ref':>4} {'dist':>4} {'cl':>4} "
              f"{'sect':>4} {'text':>4} {'judg':>4} {'chg':>4} {'same':>4} {'rpt':>4}")
        for r in sorted(rows, key=lambda r: (r["dir"], r["session"], r["rep"], r["turn"] or 0, r["step"] or 0)):
            if not args.all and not r["halted"]:
                continue
            print(f"{r['dir']:<16} {r['session']:>5} {r['rep']:>3} {r['turn']:>4} "
                  f"{r['kind'][:18]:<18} {str(r['step'] or '-'):>3} "
                  f"{('yes' if r['halted'] else '-'):>4} {r['rounds_rebuilt']:>4} "
                  f"{r['search_rounds']:>4} {r['tools']:>5} {r['leg']:>4} "
                  f"{r['leg_memo']:>4} {r['leg_refused']:>4} {r['leg_distinct']:>4} "
                  f"{r['cl']:>4} {r['sections']:>4} "
                  f"{r['text']:>4} {r['judgments']:>4} {r['changes']:>4} {r['same_resource']:>4} "
                  f"{r['repeat_retrievals']:>4}")
    if args.before:
        print()
        _discovery_invariant_one(Path(args.before), dirs[0], args.only)
    return 0


def discovery_turns(doc: dict) -> list:
    """One row per ANSWERED turn: what P2.7's pass bar compares.

    `sources_kept` is `request_timings.sources_kept`, the sources the lawyer's
    rail shows. The row's bar is that it must not fall while halts do, because
    a budget that buys fewer halts with thinner answers breaks Invariant 1.
    """
    rows = []
    for t in doc.get("turns", []):
        answer = t.get("answer") or ""
        if not answer.strip():
            continue
        timing = t.get("timing") or {}
        runs = discovery_runs({"session_id": doc.get("session_id"),
                               "rep": doc.get("rep", 1), "turns": [t]})
        rows.append({
            "turn": t.get("turn"),
            "sources_kept": int(timing.get("sources_kept") or 0),
            "at_cap": bool(timing.get("max_turns_halted")),
            "runs": len(runs),
            "halted_runs": sum(1 for r in runs if r["halted"]),
            "leg": sum(r["leg"] for r in runs),
            "search_rounds": sum(r["search_rounds"] for r in runs),
            "refused": sum(r["leg_refused"] for r in runs),
            "retrievals": sum(r["sections"] + r["text"] + r["judgments"] + r["changes"]
                              for r in runs),
            "chars": len(_without_footer(answer)),
        })
    return rows


def _discovery_invariant_one(before: Path, after: Path, only: Optional[list]) -> None:
    """P2.7's pass bar: halts fall, and `sources_kept` per turn slot does not.

    Shared sessions only. Per session, per-rep means; then, per turn slot, the
    mean `sources_kept` and prose length (footer removed) before and after.
    A slot "fell" when its mean is lower after. At n=3 a slot's mean moves with
    the model, so read the count of slots that fell, not any one slot.
    """
    def load(d: Path):
        return [x for x in load_runs(d)
                if not only or str(x.get("session_id")) in only]

    b_docs, a_docs = load(before), load(after)
    shared = ({str(x["session_id"]) for x in b_docs}
              & {str(x["session_id"]) for x in a_docs})
    if not shared:
        print(f"  --before: no session shared with {before.name}")
        return

    def measure(docs):
        slots, runs = {}, {}
        for doc in docs:
            sid = str(doc["session_id"])
            if sid not in shared:
                continue
            run = runs.setdefault((sid, doc.get("rep", 1)), Counter())
            for row in discovery_turns(doc):
                slot = slots.setdefault((sid, row["turn"]), {"kept": [], "chars": []})
                slot["kept"].append(row["sources_kept"])
                slot["chars"].append(row["chars"])
                run["turns"] += 1
                for k in ("sources_kept", "runs", "halted_runs", "leg",
                          "search_rounds", "refused", "retrievals"):
                    run[k] += row[k]
                run["at_cap"] += row["at_cap"]
                run["halted_turns"] += bool(row["halted_runs"])
        return slots, runs

    (b_slots, b_runs), (a_slots, a_runs) = measure(b_docs), measure(a_docs)
    print(f"  P2.7 pass bar (prose with the footer removed): {before.name} -> "
          f"{after.name}, sessions {', '.join(sorted(shared))}")
    for sid in sorted(shared):
        for key, label in (("turns", "answered turns / rep"),
                           ("runs", "worker runs / rep"),
                           ("halted_runs", "HALTED worker runs / rep"),
                           ("halted_turns", "turns with a halted run / rep"),
                           ("at_cap", "turns at the step cap (timing) / rep"),
                           ("leg", "search_legislation issued / rep"),
                           ("search_rounds", "search rounds / rep"),
                           ("refused", "searches refused by the budget / rep"),
                           ("retrievals", "retrieval calls / rep"),
                           ("sources_kept", "SOURCES KEPT / rep")):
            bv = [v[key] for (s, _), v in b_runs.items() if s == sid]
            av = [v[key] for (s, _), v in a_runs.items() if s == sid]
            print(f"    {sid} {label:<38} {sum(bv) / max(len(bv), 1):7.1f} "
                  f"(n={len(bv)}) -> {sum(av) / max(len(av), 1):7.1f} (n={len(av)})")
        common = sorted(k for k in set(b_slots) & set(a_slots) if k[0] == sid)
        fell = shrank = 0
        lines = []
        for k in common:
            bk = sum(b_slots[k]["kept"]) / len(b_slots[k]["kept"])
            ak = sum(a_slots[k]["kept"]) / len(a_slots[k]["kept"])
            bc = sum(b_slots[k]["chars"]) / len(b_slots[k]["chars"])
            ac = sum(a_slots[k]["chars"]) / len(a_slots[k]["chars"])
            fell += ak < bk
            shrank += ac < bc
            lines.append(f"      t{k[1]:<3} sources {bk:6.1f} -> {ak:6.1f} "
                         f"{'FELL' if ak < bk else 'held'}   "
                         f"prose {bc:7.0f} -> {ac:7.0f} {'shrank' if ac < bc else 'grew'}")
        print(f"    {sid} per turn slot: sources_kept fell in {fell} of {len(common)}, "
              f"prose shrank in {shrank} of {len(common)}")
        for ln in lines:
            print(ln)


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
                # `[CURRENCY` added at P2.5. The list has to grow with
                # `_TOOL_BLOCK` in `search_scope.py` or a new block's leak is
                # invisible here — which is how P2.3 shipped
                # `[ENABLING POWER …]` with the strip un-widened.
                if any(m in _ans for m in
                       ("[SEARCH SCOPE", "[ENABLING POWER", "[CHANGE RECORD",
                        "[CURRENCY")):
                    leaked += 1
                if _ans.count("*Search scope:") > 1:
                    dup_footer += 1
                if PROVISION_MARKER in _ans:
                    dagger += 1
            for dg in (t.get("audit") or {}).get("delegations", []):
                runs += 1
                recorded, memoed = set(), set()
                for tl in dg.get("tools", []):
                    if not _ran(tl):
                        continue
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


# --- P3.1 (B10) acceptance ----------------------------------------------------
#
# **Graded against an external ground truth, like P3.5's**, because "the
# provision at the granularity asked for" is a fact about the statute book and
# not about how the answer hedges. Every entry below was checked against the
# live LEX text on 2026-09-18 (`POST /legislation/section/search`), and every
# bar is the lawyer's own complaint (Invariant 6), not a reading of the score:
#
#   * **6396** — "It found the correct enactment but not the correct
#     provisions". The rule is SSI 2007/174 Sch 1 para 1(2): a dairy animal's
#     first tag within 36 hours of birth and its second within 20 days, 20 days
#     for other cattle. LEX renders a schedule paragraph as "Section 1)", so the
#     model writes "Schedule 1, Section 1(2)"; that is paragraph-level and it
#     counts. Stating the two limits WITHOUT citing the paragraph is not
#     delivery: `baseline` rep 1 did exactly that from memory while saying the
#     Regulations "could not be retrieved".
#   * **6365** — "it only ever cited full sections and did not cite relevant
#     subsections". The timeline's four anchors are Water Industry (Scotland)
#     Act 2002 ss.45 and 57 and Public Finance and Accountability (Scotland) Act
#     2000 ss.21 and 22, and each must be cited at subsection depth at least
#     once. The other half of that complaint (the 2000 Act missed "until
#     prompted") happened in the CONVERSATIONAL part of the session, which is
#     not replayed, and the replayed question names the Act, so finding it is
#     not graded; citing it at depth is.
#   * **6348** — "did not initially elaborate on the full provision, only
#     referring to s36(1) and not s36(2)". FOISA s.36(2), named WITH its
#     substance (information obtained from another person; an actionable breach
#     of confidence), before the lawyer had to ask for it at turn 3. "Initially"
#     is turn 1, which is the headline; turn 2 is graded too.
#
# **The footer is stripped first, and that is load-bearing.** P2.2's scope line
# quotes the search terms, and a worker that searched for "section 36(2)
# actionable breach of confidence" would otherwise satisfy 6348 by construction.

# "s.57", "s 57", "s57", "ss.21", "section 57", "sections 21". The apostrophe
# guard keeps "Scotland's 20 days" from reading as section 20.
_SEC_PREFIX = r"(?:(?<!['’])\bss?\.?\s?(?=\d)|\bsections?\s+)"
# One level of subdivision: "(3)", "(3a)", "(1A)", "(b)", "(iv)".
_SUBSEC = r"\s?\((?:\d+[A-Za-z]{0,2}|[a-z]{1,4})\)"
# A section number followed by nothing that makes it a different provision:
# not "57A", not "57/", not "570".
_SEC_END = r"(?![\dA-Za-z/])"


def _section_patterns(num: str) -> tuple:
    """(deep, coarse) for one section number: cited with a subsection, or without.

    Deep: ``s.57(3)``, ``section 57(3)(a)``, ``Section 57(3a)``, and the long
    form ``subsection (3) of section 57``. Coarse: ``section 57`` with no
    subsection, including as a later member of a list (``sections 21 and 22``),
    which is how a whole-section citation is most often written.
    """
    n = re.escape(num)
    deep = re.compile(
        _SEC_PREFIX + n + _SEC_END + _SUBSEC
        + r"|\bsub-?sections?\s*\(\w+\)[^.\n]{0,40}?\bof\s+" + _SEC_PREFIX + n
        + _SEC_END,
        re.I)
    coarse = re.compile(
        _SEC_PREFIX + n + _SEC_END + r"(?!\s?\()"
        + r"|\bsections\s+\d+[A-Z]?(?:\s*(?:,|and|or|to|&)\s*\d+[A-Z]?)*"
          r"\s*(?:,|and|or|to|&)\s*" + n + _SEC_END + r"(?!\s?\()",
        re.I)
    return deep, coarse


@dataclass(frozen=True)
class DepthReq:
    """One provision a turn must deliver, at the depth the lawyer asked for.

    `deep` is the provision at the required depth and `coarse` the same
    provision cited more coarsely. `facts` are operative facts that must also be
    stated, anywhere in the answer or, with `near`, in the sentence that cites
    the provision or the one after it. A match counts only where
    `_attribute_instrument` assigns it to `act`.
    """
    label: str
    act: str
    deep: Any
    coarse: Any
    facts: tuple = ()
    near: bool = False


_S36_SUBSTANCE = re.compile(
    r"\bactionable\b"
    r"|\bobtained\b[^.\n]{0,80}?\b(?:from|by)\b[^.\n]{0,30}?"
    r"\b(?:another|a third|third|other)\b"
    r"|\bthird[- ]part(?:y|ies)\b",
    re.I)

DEPTH_TRUTH = {
    "6396": {
        "turns": (1,),
        "acts": {
            "ssi/2007/174": re.compile(
                r"Cattle Identification \(Scotland\) Regulations 2007"
                r"|\b(?:ssi/)?2007/174\b",
                re.I),
        },
        "reqs": (
            DepthReq(
                label="Sch 1 para 1(2): 36 hours / 20 days",
                act="ssi/2007/174",
                deep=re.compile(
                    r"\bsch(?:edule|\.)?\s*1\b[^.\n]{0,30}?"
                    r"(?:para(?:graph)?s?\.?|sections?|s\.)\s*1\b(?![\d/])"
                    r"|\b(?:para(?:graph)?\.?|section)\s*1(?:\s?\(\d\))*"
                    r"[^.\n]{0,30}?\bof\s+sch(?:edule|\.)?\s*1\b",
                    re.I),
                coarse=re.compile(
                    r"\bsch(?:edule|\.)?\s*1\b(?!\d)|\bregulation\s*5\b", re.I),
                facts=(re.compile(r"\b36\s*hours?\b", re.I),
                       re.compile(r"\b20\s*days?\b", re.I)),
            ),
        ),
    },
    "6365": {
        "turns": (1,),
        "acts": {
            "asp/2002/3": re.compile(
                r"Water Industry \(Scotland\) Act|\b2002 Act\b|\basp/2002/3\b"
                r"|\bWI\(?S\)?A\b",
                re.I),
            "asp/2000/1": re.compile(
                r"Public Finances? and Accountability|\b2000 Act\b|\basp/2000/1\b"
                r"|\bPFA\(?S\)?A\b",
                re.I),
        },
        "reqs": tuple(
            DepthReq(label=f"{short} s.{num}", act=act,
                     deep=_section_patterns(num)[0],
                     coarse=_section_patterns(num)[1])
            for act, short, num in (
                ("asp/2002/3", "WI(S)A 2002", "45"),
                ("asp/2002/3", "WI(S)A 2002", "57"),
                ("asp/2000/1", "PFA(S)A 2000", "21"),
                ("asp/2000/1", "PFA(S)A 2000", "22"),
            )
        ),
    },
    "6348": {
        "turns": (1, 2),
        "acts": {
            "asp/2002/13": re.compile(
                r"Freedom of Information \(Scotland\) Act|\bFOI\(?S\)?A\b"
                r"|\basp/2002/13\b",
                re.I),
        },
        "reqs": (
            DepthReq(
                label="FOISA s.36(2), with its substance",
                act="asp/2002/13",
                # Any reference to s.36 that is not specifically s.36(1): a
                # sentence saying "section 36 also covers information obtained
                # from another person" elaborates s.36(2) without its number.
                deep=re.compile(
                    _SEC_PREFIX + r"36" + _SEC_END + r"(?!\s?\(1\))"
                    r"|\bsub-?section\s*\(2\)[^.\n]{0,40}?\bof\s+" + _SEC_PREFIX
                    + r"36" + _SEC_END,
                    re.I),
                coarse=re.compile(_SEC_PREFIX + r"36" + _SEC_END, re.I),
                facts=(_S36_SUBSTANCE,),
                near=True,
            ),
        ),
    },
}


def _attribute_instrument(text: str, pos: int, acts: dict) -> Optional[str]:
    """Which of the session's instruments a provision reference at `pos` is to.

    The nearest instrument mention on the same line, on either side, so that a
    markdown link's label (``[… Act 2000 - s.21(2)](…/asp/2000/1/section/21)``)
    and a bold ``**Water Industry (Scotland) Act 2002, Section 57(3a)**`` both
    resolve; failing that, the last mention before it anywhere in the answer.
    Needed only where one answer cites two instruments (6365), and printed by
    `--answers` so it can be audited.
    """
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end < 0:
        line_end = len(text)
    best = None
    for key, rx in acts.items():
        for m in rx.finditer(text, line_start, line_end):
            dist = pos - m.end() if m.end() <= pos else max(0, m.start() - pos)
            if best is None or dist < best[0]:
                best = (dist, key)
    if best is not None:
        return best[1]
    last = None
    for key, rx in acts.items():
        for m in rx.finditer(text, 0, pos):
            if last is None or m.start() > last[0]:
                last = (m.start(), key)
    return last[1] if last else None


def _sentence_window(text: str, pos: int) -> str:
    """The sentence (or list line) holding `pos`, plus the one after it."""
    masked = _ABBREV.sub(lambda m: m.group(0).replace(".", _DOT), text)
    bounds = [0] + [m.end() for m in re.finditer(r"(?<=[.!?])\s+|\n+", masked)]
    bounds.append(len(text))
    for i in range(len(bounds) - 1):
        if bounds[i] <= pos < bounds[i + 1]:
            return text[bounds[i]:bounds[min(i + 2, len(bounds) - 1)]]
    return text[max(0, pos - 200):pos + 200]


def _grade_depth_req(text: str, req: DepthReq, acts: dict) -> tuple:
    """(status, match, window) for one requirement: deep, coarse or missed.

    ``coarse`` covers every way of being short of the required depth: the
    provision cited only as a whole section, the facts stated without the
    provision, or the provision cited without its facts.
    """
    def owned(rx):
        return [m for m in rx.finditer(text)
                if _attribute_instrument(text, m.start(), acts) == req.act]

    deep = owned(req.deep)
    for m in deep:
        if req.near:
            window = _sentence_window(text, m.start())
            if all(f.search(window) for f in req.facts):
                return "deep", m, window
        elif all(f.search(text) for f in req.facts):
            return "deep", m, None
    coarse = owned(req.coarse)
    facts_seen = (not req.near) and any(f.search(text) for f in req.facts)
    if deep or coarse or facts_seen:
        first = (deep or coarse or [None])[0]
        return "coarse", first, None
    return "missed", None, None


def depth_verdict(session_id: str, answer: str) -> tuple:
    """(verdict, [(req, status, match, window)]) for one graded turn.

    ``DELIVERED`` every requirement at depth; ``PARTIAL`` some; ``SHALLOW``
    none at depth but the provision is there at a coarser level, which is B10
    itself (right Act, wrong depth); ``MISSED`` none of it. Graded on the
    answer with the scope footer removed.
    """
    truth = DEPTH_TRUTH.get(str(session_id))
    if not truth:
        return "n/a", []
    body = _without_footer(answer)
    graded = []
    for req in truth["reqs"]:
        status, m, window = _grade_depth_req(body, req, truth["acts"])
        graded.append((req, status, m, window))
    statuses = [g[1] for g in graded]
    if all(s == "deep" for s in statuses):
        return "DELIVERED", graded
    if any(s == "deep" for s in statuses):
        return "PARTIAL", graded
    if any(s == "coarse" for s in statuses):
        return "SHALLOW", graded
    return "MISSED", graded


# Any provision reference, for the whole-directory profile: how often a cited
# section, regulation, article or paragraph carries a subdivision at all.
_ANY_PROVISION_REF = re.compile(
    r"(?:" + _SEC_PREFIX
    + r"|\b(?:reg(?:ulation)?s?|art(?:icle)?s?|para(?:graph)?s?)\.?\s?)"
    r"(\d+[A-Z]{0,2})" + _SEC_END + r"((?:" + _SUBSEC + r")?)",
    re.I)


def depth_profile(answer: str) -> tuple:
    """(provision references, how many carry a subdivision) in one answer."""
    body = _without_footer(answer)
    refs = _ANY_PROVISION_REF.findall(body)
    return len(refs), sum(1 for _, sub in refs if sub)


def _depth_slots(doc: dict) -> dict:
    """Per turn: prose (footer removed), links, provision links, sources kept."""
    out = {}
    for t in doc.get("turns", []):
        ans = t.get("answer") or ""
        links = MD_LINK.findall(ans)
        out[t.get("turn")] = {
            "prose": len(_without_footer(ans)),
            "links": len(links),
            "provision_links": sum(1 for _, u in links if _PROVISION_URL.search(u)),
            "sources_kept": len((t.get("audit") or {}).get("sources") or []),
        }
    return out


def _depth_invariant_one(before: Path, after: Path) -> None:
    """P3.1's Invariant 1 panel: did prose, links or sources fall to buy depth?

    Per session and turn slot, means over reps, graded sessions only. P2.4's
    A/B is why links are here: a Phase 2 or prompt change took case-law links
    reaching the answer from 7 of 15 to 2 of 13 without touching anything the
    acceptance measured.
    """
    def load(d):
        per = {}
        for doc in load_runs(d):
            sid = str(doc.get("session_id"))
            if sid in DEPTH_TRUTH:
                per.setdefault(sid, []).append(doc)
        return per

    b, a = load(before), load(after)
    shared = sorted(set(b) & set(a))
    print()
    print(f"  --before {before.name}  (Invariant 1: means per turn slot, "
          f"shared graded sessions: {', '.join(shared) or 'none'})")
    if not shared:
        return
    keys = ("prose", "links", "provision_links", "sources_kept")
    fell = Counter()
    slots = 0

    def means(docs):
        acc = {}
        for doc in docs:
            for turn, m in _depth_slots(doc).items():
                acc.setdefault(turn, []).append(m)
        return {turn: {k: sum(x[k] for x in ms) / len(ms) for k in keys}
                for turn, ms in acc.items()}

    for sid in shared:
        mb, ma = means(b[sid]), means(a[sid])
        for turn in sorted(set(mb) & set(ma), key=lambda x: (x is None, x)):
            slots += 1
            row = []
            for k in keys:
                x, y = mb[turn][k], ma[turn][k]
                if y < x:
                    fell[k] += 1
                row.append(f"{k} {x:,.1f} -> {y:,.1f}")
            print(f"    {sid} t{turn}  (reps {len(b[sid])} -> {len(a[sid])})  "
                  + "  ".join(row))
    print("    fell in: " + ", ".join(f"{k} {fell[k]}/{slots}" for k in keys)
          + "   (P2.7's measured noise floor for sources_kept: 3 of 8 slots)")


def cmd_depth(args) -> int:
    """P3.1's acceptance: the provision at the granularity asked for, per turn.

    Grades only the sessions in `DEPTH_TRUTH`. Always exits 0: it is a
    measurement over stochastic sessions, and the pass bar (n=3, all clean on
    the headline turn) is read off its output, not off an exit code.

    `--answers` prints the evidence behind every requirement, with the
    instrument each match was attributed to; `--drops` prints every sentence in
    the requirement's vocabulary that was NOT counted as delivering it. Read
    both, in both directions, before quoting a number.
    """
    docs = [d for d in load_runs(Path(args.dir))
            if str(d.get("session_id")) in DEPTH_TRUTH]
    print(f"P3.1 (B10) - provision depth over {args.dir}  "
          f"({len(docs)} graded run file(s))")
    if not docs:
        print("  no graded session (expected any of %s)"
              % ", ".join(sorted(DEPTH_TRUTH)))
    rows, drops = [], []
    headline = {}
    for doc in sorted(docs, key=lambda d: (str(d.get("session_id")),
                                           d.get("rep", 1))):
        sid = str(doc.get("session_id"))
        truth = DEPTH_TRUTH[sid]
        by_turn = {t.get("turn"): t for t in doc.get("turns", [])}
        verdicts = []
        for turn in truth["turns"]:
            t = by_turn.get(turn)
            ans = (t or {}).get("answer") or ""
            if not ans.strip():
                verdicts.append((turn, "NO ANSWER", []))
                continue
            verdict, graded = depth_verdict(sid, ans)
            verdicts.append((turn, verdict, graded))
            if args.drops:
                # Only requirements this turn did NOT deliver: for those, every
                # sentence in the requirement's vocabulary is a candidate
                # under-read. A delivered requirement's evidence is --answers'.
                body = _without_footer(ans)
                for req, status, _, _ in graded:
                    if status == "deep":
                        continue
                    for sent in _sentences(body):
                        if (req.coarse.search(sent) or req.deep.search(sent)
                                or any(f.search(sent) for f in req.facts)):
                            drops.append((sid, doc.get("rep", 1), turn,
                                          f"[{req.label}] {sent}"))
        rows.append((sid, doc.get("rep", 1), doc.get("git_head"), verdicts,
                     by_turn))
        first = verdicts[0][1] if verdicts else "NO ANSWER"
        before_asked = any(v == "DELIVERED" for _, v, _ in verdicts)
        h = headline.setdefault(sid, Counter())
        h["reps"] += 1
        h[first] += 1
        h["by_last_graded"] += int(before_asked)

    print()
    print("  headline turn (the first graded turn), per session:")
    for sid in sorted(headline):
        h = headline[sid]
        turns = DEPTH_TRUTH[sid]["turns"]
        tail = ""
        if len(turns) > 1:
            tail = (f"   delivered by turn {turns[-1]}: "
                    f"{h['by_last_graded']}/{h['reps']}")
        print(f"    {sid}  t{turns[0]}  DELIVERED {h['DELIVERED']}/{h['reps']}"
              f"  PARTIAL {h['PARTIAL']}  SHALLOW {h['SHALLOW']}"
              f"  MISSED {h['MISSED']}  NO ANSWER {h['NO ANSWER']}{tail}")
    print()
    for sid, rep, head, verdicts, by_turn in rows:
        line = "  ".join(f"t{turn} {verdict}" for turn, verdict, _ in verdicts)
        print(f"  {sid} rep{rep}  {line}   [{head or '?'}]")
        for turn, verdict, graded in verdicts:
            for req, status, m, window in graded:
                print(f"        t{turn} {status:7} {req.label}")
                if args.answers and m is not None:
                    body = _without_footer(by_turn[turn].get("answer") or "")
                    who = _attribute_instrument(body, m.start(),
                                                DEPTH_TRUTH[sid]["acts"])
                    ctx = body[max(0, m.start() - 60):m.end() + 60]
                    print(f"            match {m.group(0)!r} -> {who}")
                    print(f"            ...{ctx!r}...")
                    if window:
                        print(f"            window: {window[:300]!r}")
        if args.answers:
            for turn, _, _ in verdicts:
                q = (by_turn.get(turn) or {}).get("question") or ""
                print(f"        t{turn} question: {q[:120]}")
    if args.drops:
        print()
        print(f"  --drops: {len(drops)} sentence(s) in a requirement's vocabulary "
              f"NOT counted as delivering it")
        for sid, rep, turn, sent in drops:
            print(f"    {sid} rep{rep} t{turn}: {sent[:220]}")
    if args.all:
        print()
        print("  depth profile over every answered turn (section/regulation/"
              "article/paragraph references carrying a subdivision):")
        per = {}
        for doc in load_runs(Path(args.dir)):
            sid = str(doc.get("session_id"))
            for t in doc.get("turns", []):
                if (t.get("answer") or "").strip():
                    n, sub = depth_profile(t["answer"])
                    acc = per.setdefault(sid, [0, 0, 0])
                    acc[0] += 1
                    acc[1] += n
                    acc[2] += sub
        tot = [sum(v[i] for v in per.values()) for i in range(3)]
        for sid in sorted(per):
            turns, n, sub = per[sid]
            print(f"    {sid}  turns {turns:3}  refs {n:4}  with subdivision "
                  f"{sub:4}  ({100 * sub / max(n, 1):3.0f}%)")
        print(f"    ALL   turns {tot[0]:3}  refs {tot[1]:4}  with subdivision "
              f"{tot[2]:4}  ({100 * tot[2] / max(tot[1], 1):3.0f}%)")
    if args.before:
        _depth_invariant_one(Path(args.before), Path(args.dir))
    return 0


# P1.6's demotion marker, counted by `corpus` as the measured cost of P3.5's
# decision to emit provision LABELS rather than provision URLs.
PROVISION_MARKER = "\u2020"

_SECONDARY_SERIES = ("ssi", "uksi", "nisr", "wsi", "ssr", "uksro", "nisro",
                     "ukci", "ukmo")


def _utf8_stdout() -> None:
    """Make stdout survive being redirected on Windows.

    **Found during the Session 9 handover audit, and the failure mode is why it
    is worth a helper.** On this box `sys.stdout` is cp1252 when redirected to a
    file or a pipe (the console itself copes), so printing a replay answer that
    contains a character the model happened to use — a warning sign, an em dash
    in the wrong form, a quotation mark — raises `UnicodeEncodeError`. It dies
    **partway through**, so the redirected output looks TRUNCATED rather than
    failed, and the exit code is the only tell. `replay_report --dir <dir>
    currency --drops --before <dir> > out.txt` hit it on a 101-row drops list,
    which is exactly the shape of command a session redirects to a file.

    `errors="replace"` rather than a sanitiser at each print site: there are six
    sites that echo answer text in this file alone, and the next one added would
    not know to sanitise.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: Iterable[str] | None = None) -> int:
    _utf8_stdout()
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
    cu.add_argument("--unasked", action="store_true",
                    help="the measured cost: turns carrying a currency "
                         "disclaimer whose question never asked about currency")
    sub.add_parser("scoperecord",
                   help="P2.9 acceptance: every search a worker run issued, "
                        "against what its own scope block recorded")
    ns = sub.add_parser("nosearch",
                        help="P2.8 acceptance: replies that ran no legislation "
                             "search, and the scope statement beside them")
    ns.add_argument("--all", action="store_true",
                    help="list every no-search turn, not only negatives and findings")
    ns.add_argument("--answers", action="store_true",
                    help="print the question and answer under each listed turn")
    ns.add_argument("--chars", type=int, default=600)
    ns.add_argument("--before", metavar="DIR",
                    help="Invariant 1 on the model's prose (footer removed), "
                         "shared sessions only")
    ns.add_argument("--only", nargs="+", metavar="SESSION",
                    help="with --before, restrict both sides to these sessions")
    cl = sub.add_parser("caselaw",
                        help="P2.4 acceptance: turns that searched case law, and "
                             "whether the corpus gap was disclosed (code vs model)")
    cl.add_argument("--all", action="store_true",
                    help="list every answered turn, not only case-law turns and findings")
    cl.add_argument("--answers", action="store_true",
                    help="print each model sentence graded as stating the gap")
    cl.add_argument("--drops", action="store_true",
                    help="print every sentence naming a Scottish court that was "
                         "NOT graded as stating the gap")
    cl.add_argument("--chars", type=int, default=400)
    cl.add_argument("--before", metavar="DIR",
                    help="Invariant 1 on the model's prose (footer removed), "
                         "shared sessions only")
    cl.add_argument("--only", nargs="+", metavar="SESSION",
                    help="with --before, restrict both sides to these sessions")
    dc = sub.add_parser("discovery",
                        help="P2.7 pre-flight: discovery calls per worker run, "
                             "halted vs completed, and what a budget of N would block")
    dc.add_argument("--also", nargs="+", metavar="DIR",
                    help="further replay dirs to pool with --dir (say which in any write-up)")
    dc.add_argument("--only", nargs="+", metavar="SESSION")
    dc.add_argument("--runs", action="store_true", help="list every halted worker run")
    dc.add_argument("--all", action="store_true", help="list every worker run")
    dc.add_argument("--before", metavar="DIR",
                    help="P2.7 acceptance: compare halts and sources_kept per turn "
                         "slot against DIR, shared sessions only (use --only)")
    dp = sub.add_parser("depth",
                        help="P3.1 acceptance: the provision at the granularity "
                             "asked for, graded per turn against a verified truth")
    dp.add_argument("--answers", action="store_true",
                    help="print the evidence and attribution behind every requirement")
    dp.add_argument("--drops", action="store_true",
                    help="print every sentence in a requirement's vocabulary "
                         "NOT counted as delivering it")
    dp.add_argument("--all", action="store_true",
                    help="also profile subdivision depth over every answered turn")
    dp.add_argument("--before", metavar="DIR",
                    help="Invariant 1: prose, links and sources per turn slot "
                         "against DIR, graded sessions only")
    sub.add_parser("blanks",
                   help="P4.2 acceptance: every turn that showed the lawyer no "
                        "body, and whether it was billed for")
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
        "scoperecord": cmd_scoperecord,
        "nosearch": cmd_nosearch,
        "caselaw": cmd_caselaw,
        "discovery": cmd_discovery,
        "depth": cmd_depth,
        "blanks": cmd_blanks,
        "corpus": cmd_corpus,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
