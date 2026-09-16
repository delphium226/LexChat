"""B5 — a negative must state the limits it was reached under (FIX_PLAN P2.2).

A "not found" from this system is read by a lawyer as a statement about the
statute book. Measured over the Wave 1 sweep it usually is not one, and the
model is never told the difference.

**What the measurement showed, and it is not what the row assumed.** The row was
written against the missing zero-result nudge on `search_legislation` — the only
search tool without one. That branch is real and is fixed here, but post-Wave-1
it fires on **4 of 790** searches. Meanwhile **17 turns asserted a negative and
not one of them came from an empty search**: every one was drawn from a result
set that had results, just not the wanted one. So the bare negative is not
mainly a zero-result problem. It is a **window** problem:

    783 of 783 measurable `search_legislation` calls were windowed.
    The model sees 5 rows of a median 141 ranked matches (p90 185, max 220).

Concluding "no commencement regulations have been made" from the top 5 of 141 is
not a finding; it is the shape of the tool. Seven of the 17 negatives are that
exact sentence (6409 x5, 6410 x2).

The total is a **ranking depth, not a count of relevant instruments** — LEX ranks
the whole corpus against the wording, and the query *"zzqx nonexistent statute
about interplanetary haggis"* returns **185 matches** live. The note says so in
terms: a model told "5 of 185" and not told what the 185 *is* has every reason to
go looking for the other 180, which is the discovery loop P2.7 exists to stop.

The second limb is **coverage**, and it is the one that turns a true-sounding
negative false. `search_legislation` cannot distinguish "the index does not hold
it" from "it does not exist", and the index is thin in exactly the places these
lawyers work. Verified live 2026-09-15 (`python -m tools.lex_probe --coverage`
plus the census below):

    ssi/2025/377   404 — 6409 asked for it by number three times and was told
                   "could not be found ... could you verify the SSI number?"
    ssi/2026/170   404 — 6373; FrankieH's citation was right and AILA
                   questioned it (this is P2.4's case as well)
    ssi/2025/119   200 — held, and asked for in the same session

Questioning a correct citation because the index is short is worse than saying
nothing: it spends the lawyer's time disproving the tool.

**Coverage numbers, and a correction to P5.3 that this module sits downstream
of.** P5.3 recorded "UK SI 2026 ~0% held" from a 20-point lookup sample. That
reads as "nothing from 2026 is in the index" and it is **false**: a
`/legislation/search` cross-check returns **27 distinct `uksi/2026/*`
instruments, and all 12 spot-checked resolve on lookup**. A 60-point census puts
the rate at ~2%, not 0 — low single digits, not nothing. So the wording below
never says "none": a lawyer told none stops looking. That is the probe's own
warning (a sparse sample of absences proves nothing about a corpus) applying to
the probe's own headline.

**And the same trap caught the replacement figure a day later.** "Under 5%" was
written from one 60-point sample; re-running `lex_probe --coverage` the next day
returned **8%** for the same series. Ordinary noise at n=60 (1 hit vs 5) — and
enough to falsify a claim already sitting in a string lawyers read. Every figure
below is now a **bound chosen to survive the spread**, not the last number
measured, and nothing here quotes a bare percentage without saying when it was
sampled.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

__all__ = [
    "LEX_COVERAGE_SENTENCE",
    "legislation_search_note",
    "section_search_note",
    "record_search",
    "worker_scope_block",
    "strip_scope_blocks",
    "answer_scope_footer",
    "incomplete_steps_note",
]

# Measured with `python -m tools.lex_probe --coverage`, which also runs the
# search cross-check. **Two independent 60-point samples of the same series,
# taken a day apart, and they disagree:**
#
#                      2026-09-15      2026-09-16
#     ASP 2025          10/10 (100%)    10/10 (100%)
#     SSI 2025          52/60 ( 87%)    51/60 ( 85%)
#     SSI 2026           1/60 (  2%)     5/60 (  8%)   <- 4x apart
#     UK SI 2026         1/60 (  2%)     1/60 (  1%)   <- P5.3's "0%" was an artefact
#     UKPGA 1962        12/20 ( 60%)    28/60 ( 46%)
#
# **So the figures below are stated as bounds that survive the spread, not as
# the last number measured.** Writing "under 5%" from the first sample would
# have been contradicted by the second the following day — in a string a
# government lawyer reads and may rely on. A 2%-vs-8% spread on n=60 is ordinary
# sampling noise (1 hit vs 5); a product claim has to be true across it.
# Re-measure before quoting it anywhere, and widen the bound rather than chasing
# the sample.
LEX_COVERAGE_SENTENCE = (
    "The index is incomplete and unevenly so (sampled Sep 2026: Acts of the "
    "Scottish Parliament complete, roughly 85% of 2025 SSIs held, under 10% of "
    "instruments made in 2026, and older gaps are per-instrument rather than by "
    "date). Absence from the index is therefore NOT evidence of absence in law."
)

# What any negative drawn from a search must carry. One string, so the
# legislation and section notes cannot drift apart.
#
# (a) is bounded on purpose. 6409 turns 6 and 7 ran 17 and 25 searches, and an
# instruction to "give the exact search terms used" invites all 25 into the
# answer — turning a disclosure into a log and burying the finding. Two or three
# specific terms discharge the duty; the full list is in the audit trace.
# (b) says "or say plainly that none were applied" because the commonest case is
# no filters at all, and silence there is indistinguishable from not checking.
_REPORTING_RULE = (
    "If you report anything as not found, you MUST (a) quote the search terms "
    "you used — the two or three most specific, not every query you ran; "
    "(b) name the filters in force, or say plainly that none were applied; "
    "(c) attribute the miss to the search or the index, never to the user's "
    "citation; and (d) NOT speculate about why it was not found — you do not "
    "know."
)


def _filters_phrase(cfg: Optional[dict], args: dict) -> str:
    """Name every limit this search actually ran under, in the model's own terms.

    Both sources matter and neither alone is complete: the user's filters live on
    the request config, while the year window the search used is the
    *intersection* of the user's and the model's own arguments (executor.py takes
    max/min). A negative reached inside a 2019-2026 window is a different claim
    from a negative reached across the corpus, and the model cannot say which
    unless it is told which it was.
    """
    cfg = cfg or {}
    bits = []
    jur = cfg.get("_jurisdiction")
    if jur:
        bits.append(f"jurisdiction={jur}")
    lt = cfg.get("_legislation_type")
    if lt:
        bits.append(f"legislation_type={lt}")

    def _window(user, model, pick):
        vals = [v for v in (user, model) if v]
        return pick(vals) if vals else None

    yf = _window(cfg.get("_year_from"), args.get("year_from"), max)
    yt = _window(cfg.get("_year_to"), args.get("year_to"), min)
    if yf or yt:
        bits.append(f"years {yf or 'any'}-{yt or 'any'}")
    return ", ".join(bits) if bits else "none"


def _as_dict(data: Any) -> dict:
    """Parse the JSON object a tool result starts with; {} for anything else.

    `raw_decode` rather than `loads` for the same reason `replay_report` uses it:
    by the time anything reads a tool result it may already carry an appended
    nudge, and a plain parse raises "Extra data" on exactly the calls that
    succeeded.
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            obj, _ = json.JSONDecoder().raw_decode(data.lstrip())
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def legislation_search_note(
    args: dict, data: Any, cfg: Optional[dict] = None
) -> str:
    """The scope block appended to every `search_legislation` result.

    Two branches, and the *non-empty* one is the one that matters — see the
    module docstring. Both state the same three things (what was searched, under
    which limits, and what the result can and cannot establish); they differ only
    in what the counts mean.

    Deliberately unconditional on the non-empty path. A detector deciding when a
    negative is "likely" would have to read the model's intent before the model
    has formed it, and on this work the detectors have been wrong more often than
    the product.
    """
    args = args or {}
    d = _as_dict(data)
    if d.get("error"):
        return ""

    query = str(args.get("query") or "").strip()
    query_phrase = f'"{query[:200]}"' if query else "(no query given)"
    filters = _filters_phrase(cfg, args)

    results = d.get("results")
    shown = len(results) if isinstance(results, list) else d.get("returned")
    # P1.3 put the API's real match count back on the response. Before it,
    # `total` was overwritten with the truncated length and this note could not
    # have been written at all — "top 5 of 5" would have been the only thing the
    # data supported, which is the misreport rather than the window.
    matched = d.get("total_matched")
    if not isinstance(matched, int):
        matched = d.get("total") if isinstance(d.get("total"), int) else None
    removed = d.get("removed_by_filters") or 0

    if shown:
        window = (
            f"top {shown} of {matched} candidates ranked by relevance"
            if isinstance(matched, int) and matched > shown
            else f"{shown} result(s)"
        )
        removed_phrase = (
            f" {removed} row(s) on this page were removed by those filters."
            if removed
            else ""
        )
        return (
            f"\n\n[SEARCH SCOPE — {window} for {query_phrase}. Filters in force: "
            f"{filters}.{removed_phrase} The index ranks the whole corpus against "
            "your wording, so that total is a ranking depth and NOT a count of "
            "relevant instruments — do not go looking for the rest of them. What "
            "it does mean is that a ranked search cannot establish absence: an "
            "instrument, commencement, amendment or provision missing from these "
            "rows may still be held, and may still exist. Do NOT state that "
            f"anything does not exist on the strength of this result. "
            f"{LEX_COVERAGE_SENTENCE} {_REPORTING_RULE}]"
        )

    # Zero results. Rare since Wave 1 (4 of 790), but it is the one case where
    # the model sees literally nothing and has to say so unaided.
    counts = []
    if isinstance(matched, int):
        counts.append(f"the index reported {matched} match(es) for it")
    if removed:
        counts.append(f"{removed} retrieved row(s) were removed by the filters")
    counts_phrase = ("; " + ", and ".join(counts) + ".") if counts else "."
    return (
        "\n\n[SEARCH SCOPE — this search returned 0 results to you. Searched for "
        f"{query_phrase}. Filters in force: {filters}{counts_phrase}"
        " If you have already tried 2-3 different wordings without results, stop "
        "searching and report the negative — do not keep searching. "
        f"{LEX_COVERAGE_SENTENCE} {_REPORTING_RULE}]"
    )


def section_search_note(args: dict, data: Any) -> str:
    """The scope block appended to every `search_legislation_sections` result.

    This tool had no note of any kind. It is the second source of bare negatives:
    6383 turn 2 ("could not retrieve the preamble"), and 6335 turn 7, which
    reported that a targeted search "returned no results" — it had not, the
    provisions simply were not in the ranked ten — and then invented a cause:
    *"it is possible the database is having difficulty parsing the Schedule B1
    structure."* Hence the explicit no-speculation clause; it is the same failure
    the halted-worker report already forbids (P2.1).

    **No retry licence here, deliberately.** The case-law and Hansard zero-result
    nudges say "you may retry once"; this one says stop. P2.7 measured the
    legislation Worker looping on discovery — 26% redundant calls on the turns
    that hit the step cap, against a 15% base rate — and a fresh invitation to
    re-query is the last thing that path needs.
    """
    args = args or {}
    d = _as_dict(data)
    if d.get("error"):
        return ""

    query = str(args.get("query") or "").strip()
    query_phrase = f'"{query[:200]}"' if query else "(no query given)"
    leg = str(args.get("legislation_id") or "").strip() or "this instrument"

    results = d.get("results")
    shown = len(results) if isinstance(results, list) else d.get("returned")
    if not isinstance(shown, int):
        return ""

    if shown:
        return (
            f"\n\n[SEARCH SCOPE — {shown} provision(s) of {leg}, ranked by "
            f"relevance to {query_phrase}. This is NOT the full contents of the "
            "instrument: a provision that does not appear here may still be in "
            "it. Do NOT state that a provision, power or duty is absent from "
            f"{leg} on the strength of this result, and do NOT speculate about "
            "why a provision was not returned. If you report something as not "
            "found, say what was searched for and in which instrument.]"
        )
    return (
        f"\n\n[SEARCH SCOPE — 0 provisions of {leg} matched {query_phrase}. That "
        "means the ranked search did not surface one — NOT that the instrument "
        "lacks such a provision, and NOT that the instrument is unavailable. Do "
        "not speculate about the cause; you do not know it. If you report this, "
        "say what was searched for and in which instrument, and say the search "
        "did not locate it rather than that it does not exist.]"
    )


def incomplete_steps_note(halts: list, steps_total: int = 0) -> str:
    """Instruction to the Deep Research synthesis when a plan step was cut short.

    P2.1 made the halt visible to the lawyer; it does not stop the *synthesis*
    drawing a conclusion out of the hole. In 6382 rep 2 of P2.1's own acceptance
    sweep, steps 2 and 3 halted and the report still opened *"no Scottish
    Statutory Instruments made under section 95 ... were found that contain the
    '£' symbol"* — the two steps that would have established that are the two
    that stopped. The contradiction was visible (the notice says in terms that
    this is not a finding of absence) and the answer still led with a negative it
    had not earned.

    Placed in the synthesis **user payload** rather than in
    `DEEP_RESEARCH_SYNTHESIS_PROMPT`, for the same reason `halt_worker_report` is
    a tool result and not a system rule: an instruction naming *these* steps, in
    the material being composed from, is per-occurrence and cannot be diluted by
    the rest of a long standing prompt.
    """
    steps = [h for h in (halts or []) if h.get("step")]
    if not steps:
        return ""
    labels = []
    for h in sorted(steps, key=lambda x: x["step"]):
        title = (h.get("title") or "").strip()
        labels.append(f"step {h['step']}" + (f" ({title})" if title else ""))
    if len(labels) > 1:
        named = ", ".join(labels[:-1]) + f" and {labels[-1]}"
        plural = True
    else:
        named = labels[0]
        plural = False
    scale = f" ({len(labels)} of {steps_total} steps)" if steps_total else ""
    those = "those steps" if plural else "that step"
    return (
        "\n\nINCOMPLETE STEPS — READ BEFORE WRITING THE BLUF:\n"
        f"{named} did not finish: {'they were' if plural else 'it was'} stopped "
        f"by an internal limit on tool-call rounds{scale}. The findings below for "
        f"{those} are missing because the work stopped, NOT because the material "
        "was searched for and not found.\n"
        f"You MUST NOT write, in the BLUF or anywhere else, that anything covered "
        f"by {those} does not exist, was not made, or could not be found. State "
        "instead that the point was not established because that part of the "
        "research did not complete. Answer fully from the steps that DID "
        "complete, and be specific about which question remains open."
    )


# ---------------------------------------------------------------------------
# The seam the first acceptance run found open
# ---------------------------------------------------------------------------
#
# **The tool-result block alone does not reach the agent that writes the
# negative, and the first acceptance run proved it.** In 6367 rep 1 the
# `[SEARCH SCOPE ...]` block was in the Worker's context **27 times**, and the
# report the lawyer read still opened *"No Statutory Instruments were found
# prescribing further details ..."* with no search terms, no filters, and — in
# the body — *"A search up to 2026 **confirms** that no Statutory Instruments
# prescribe ..."*, which is precisely the overclaim the block forbids. Graded
# against the four Worker reports: three carried no scope language at all and
# the fourth attributed its miss to the index but named neither terms nor
# limits.
#
# The reason is structural, and it is P2.1's lesson in a second place. The
# Worker sees the tool results; the **Manager** sees only the Worker's report,
# and the **Deep Research synthesis** sees only the step findings. Whoever
# writes the BLUF has never seen a scope block. An instruction at the tool seam
# asks the Worker to carry the facts forward in prose, and Invariant 2 says not
# to ask — so the facts are carried forward by code, exactly as
# `provision_url_block` hands provision URLs across the summarisation boundary
# they were being lost at.

_MAX_LOGGED_QUERIES = 12

# The worker block is delimited so one regex can strip it whole. The tool-result
# form is a single bracketed run and is matched separately. Both are loose about
# the wording inside, for the reason `HALT_MARKER` is loose about its limit: a
# later edit to the prose must not leave an unstripped block behind.
#
# **The worker pattern requires "research step" in its opening marker, and that
# is a safety property rather than tidiness.** The strip runs on the Manager's
# ANSWER. If a model ever quoted a tool-result block in its prose — which it is
# not asked to do and nothing prevents — a worker pattern that matched any
# `[SEARCH SCOPE …]` opener would start there and run, lazily, to the report's
# closing marker at the very end, deleting the entire answer body in between.
# Requiring the word the two openers differ on makes that unreachable. The order
# in `strip_scope_blocks` matters for the mirror-image reason: the generic
# tool pattern also matches the worker block's OPENING line on its own, so
# running it first would orphan the body and its close marker.
_WORKER_BLOCK_OPEN = "[SEARCH SCOPE — what this research step actually did]"
_WORKER_BLOCK_CLOSE = "[/SEARCH SCOPE]"
_WORKER_BLOCK = re.compile(
    r"\[SEARCH SCOPE[^\]]*research step[^\]]*\][\s\S]*?\[/SEARCH SCOPE\]", re.I
)
_TOOL_BLOCK = re.compile(r"\[/?SEARCH SCOPE[^\[\]]*\]", re.I)


def record_search(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record one search for the worker's scope block. Never raises.

    Called from `run_worker_tool` for the two legislation search tools. A
    diagnostic must never be the reason a retrieval goes missing (Invariant 5),
    so every failure here is swallowed.
    """
    if log is None:
        return
    try:
        d = _as_dict(data)
        results = d.get("results")
        shown = len(results) if isinstance(results, list) else d.get("returned")
        matched = d.get("total_matched")
        if not isinstance(matched, int):
            matched = d.get("total") if isinstance(d.get("total"), int) else None
        log.append({
            "tool": name,
            "query": str(args.get("query") or "")[:200],
            "legislation_id": str(args.get("legislation_id") or "")[:60],
            "shown": shown if isinstance(shown, int) else None,
            "matched": matched,
        })
    except Exception:
        pass


def worker_scope_block(log: Optional[list], cfg: Optional[dict] = None) -> str:
    """The scope record appended, in code, to a Worker's report.

    Addressed to the agent that will read the report — a Manager holding it as a
    `delegate_research` result, or the Deep Research synthesis holding it as a
    step's findings — which is the agent that actually writes the negative.

    Deliberately compact: it is a provenance footer, not a transcript. The full
    query list lives in the audit trace, and 6409 turn 7 ran 25 searches, so
    printing them all would bury the report it is attached to.
    """
    if not log:
        return ""
    searches = [e for e in log if e.get("tool") == "search_legislation"]
    sections = [e for e in log if e.get("tool") == "search_legislation_sections"]

    lines = [f"\n\n{_WORKER_BLOCK_OPEN}"]
    if searches:
        shown = [e["shown"] for e in searches if isinstance(e.get("shown"), int)]
        matched = [e["matched"] for e in searches if isinstance(e.get("matched"), int)]
        terms = []
        for e in searches:
            q = (e.get("query") or "").strip()
            if q and q not in terms:
                terms.append(q)
        more = len(terms) - _MAX_LOGGED_QUERIES
        shown_terms = "; ".join(f'"{q}"' for q in terms[:_MAX_LOGGED_QUERIES])
        lines.append(
            f"Searched the legislation index {len(searches)} time(s) for: "
            + shown_terms
            + (f" (and {more} more)" if more > 0 else "")
        )
        if shown and matched:
            lines.append(
                f"Those searches showed {sum(shown)} row(s) drawn from "
                f"{max(matched)} ranked candidates at most — the index ranks the "
                "whole corpus against the wording, so that is a ranking depth, "
                "not a count of relevant instruments."
            )
    if sections:
        ids = []
        for e in sections:
            lid = (e.get("legislation_id") or "").strip()
            if lid and lid not in ids:
                ids.append(lid)
        lines.append(
            f"Searched within {len(ids) or len(sections)} instrument(s) for "
            f"specific provisions: {', '.join(ids[:8]) or 'n/a'}"
            + (" (ranked extracts, not the full contents of any of them)")
        )
    filters = _filters_phrase(cfg, {})
    lines.append(f"Filters in force for the whole step: {filters}.")
    lines.append(
        "NONE of this can establish that something does not exist. If any part "
        "of the answer you write reports something as not found, it MUST quote "
        "the search terms above (two or three are enough), state these filters "
        "or say plainly that none were applied, and attribute the miss to the "
        "search or the index — never to the user's citation. Do not say a "
        f"search \"confirms\" an absence; it cannot. {LEX_COVERAGE_SENTENCE}"
    )
    lines.append(_WORKER_BLOCK_CLOSE)
    return "\n".join(lines)


def _lawyer_filters_phrase(cfg: Optional[dict]) -> str:
    """Name only the filters that could actually have excluded something.

    **Different from `_filters_phrase`, deliberately.** The agent-facing block
    reports every parameter the search ran under, because the agent is being
    asked to reason about them. The lawyer-facing footer must not: 6409 and 6367
    both ran with `year_to = 2026`, which excluded nothing in September 2026, and
    the first draft of this footer told the lawyer *"filters in force: years
    any-2026"* — stating a constraint that did not constrain. An overstated limit
    invites a lawyer to re-run a search that was never narrowed, which wastes the
    time this row exists to protect.

    Biting means a jurisdiction or type filter, a lower year bound, or an upper
    bound that is actually in the past.
    """
    from datetime import date

    cfg = cfg or {}
    bits = []
    if cfg.get("_jurisdiction"):
        bits.append(f"jurisdiction = {cfg['_jurisdiction']}")
    if cfg.get("_legislation_type"):
        bits.append(f"type = {cfg['_legislation_type']}")
    yf, yt = cfg.get("_year_from"), cfg.get("_year_to")
    try:
        yt_binds = bool(yt) and int(yt) < date.today().year
    except (TypeError, ValueError):
        yt_binds = False
    if yf and yt_binds:
        bits.append(f"years {yf}-{yt}")
    elif yf:
        bits.append(f"years from {yf}")
    elif yt_binds:
        bits.append(f"years up to {yt}")
    if not bits:
        return "no jurisdiction, type or date filter narrowed it"
    return "filters in force: " + ", ".join(bits)


def answer_scope_footer(searches: Optional[list], cfg: Optional[dict] = None) -> str:
    """The lawyer-facing scope line, emitted by code on every researched answer.

    **Why this exists, when the instruction blocks already say it.** Measured over
    the acceptance replay (n=3 on 6409 and 6367, 23 turns asserting a negative),
    carrying the facts to the agent that writes the answer moved compliance from
    **0% to 52%** — a real move, and 48% of negatives still told a lawyer
    something was not found without saying what had been looked for. Invariant 2
    is written for exactly this: where a row offers a choice between "tell the
    model to" and "make it so", take the second. P2.1 reached the same place by
    the same route, and for the same reason — a false negative here is a lawyer
    relying on an unqualified negative.

    **Unconditional on any turn that searched, rather than gated on a detector
    that decides the answer contains a negative.** A prose detector in the
    product is the thing this work has been burned by ten times, and the failure
    would be silent: an unrecognised phrasing means no footer and no signal. The
    cost of being unconditional is a line of provenance on answers that found
    what they were looking for — which for a verifying audience is not obviously
    a cost. This is the decision most open to being overruled, and it is
    deliberately one line.

    Distinct from `worker_scope_block`, which is an instruction addressed to an
    agent and is stripped before rendering; this is prose addressed to a lawyer.
    """
    searches = [s for s in (searches or []) if s.get("tool") == "search_legislation"]
    if not searches:
        return ""
    # The model routinely quotes its own query ('"Water Industry Commission"'),
    # which wrapped again renders as `""…""`. Strip the model's quoting and
    # dedupe case-insensitively before re-quoting once.
    terms, seen = [], set()
    for s in searches:
        q = (s.get("query") or "").strip().strip("\"'“”").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            terms.append(q)
    if not terms:
        return ""
    quoted = ", ".join(f'"{t}"' for t in terms[:2])
    rest = len(terms) - 2
    more = f" ({rest} further quer{'y' if rest == 1 else 'ies'} not listed)" if rest > 0 else ""
    filters_phrase = _lawyer_filters_phrase(cfg)
    return (
        f"\n\n*Search scope: the legislation index was searched for {quoted}{more}; "
        f"{filters_phrase}. This is a ranked search of an index that is known to be "
        "incomplete — roughly 85% of 2025 Scottish SIs and under 10% of "
        "instruments made in 2026 are held (sampled Sep 2026) — so anything "
        "reported above "
        "as not found was not found in this index, which is not the same as being "
        "absent from the law.*"
    )


def strip_scope_blocks(text: str) -> tuple:
    """Remove every scope block from `text`. Returns (text, count).

    Unconditional, exactly like `strip_halt_markers`. These blocks are addressed
    to an *agent*, not to a lawyer — "NONE of this can establish that something
    does not exist" is an instruction, not prose a government lawyer should be
    reading — and the Manager is told to pass a Worker's report through in
    research mode, so without this the bookkeeping renders on screen.

    The division of labour is P2.1's exactly: the block is the instruction, and
    the model's own sentence is the disclosure. What P2.1 additionally has, and
    this does not, is a code-emitted lawyer-facing notice; that was judged too
    noisy here, because a scope footer on every *positive* answer is clutter and
    there is no structural test for "this answer contains a negative" that does
    not amount to a prose detector.
    """
    if not text:
        return text, 0
    out, n = _WORKER_BLOCK.subn("", text)
    out, n2 = _TOOL_BLOCK.subn("", out)
    n += n2
    if n:
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, n
