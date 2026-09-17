"""What a retrieval can and cannot establish — FIX_PLAN P2.2 (B5), P2.3 (B3b)
and P2.4 (B12).

P2.4 is further down, in its own section: the case-law corpus gap, disclosed in
code on every turn that searched case law, and the not-held note that stops a
404 being read as a wrong citation.

Two rows, one module, because they are the same fix at the same four seams: the
tool result, the worker's report, the lawyer-facing footer, and the
unconditional strip. **P2.2** says a negative must state the limits it was
reached under. **P2.3** says an instrument's enabling power may be asserted only
where it was retrieved — see the B3(b) section further down for its own
measurement and its own reasoning.

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
    "enabling_power_note",
    "amendment_search_note",
    "currency_note",
    "record_search",
    "record_enabling_power",
    "record_relations",
    "record_currency",
    "worker_scope_block",
    "strip_scope_blocks",
    "answer_scope_footer",
    "carried_scope_footer",
    "strip_answer_footer",
    "incomplete_steps_note",
    "CASE_LAW_COVERAGE_SENTENCE",
    "record_case_law_search",
    "case_law_scope_clause",
    "case_law_scope_footer",
    "not_held_note",
    "record_not_held",
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


# P3.5 (B3): the routing clause, on both search blocks. It is one sentence and
# it earns its place from the measured turns. 6409 turn 5 concluded "no
# commencement regulations have been made yet" after five `search_legislation`
# calls and one section search; 6409 turn 6 ran **41** searches hunting a
# commencement instrument by title and halted at the step cap with nothing;
# 6410 turn 1 read `asp/2025/9`'s own s. 39 ("the Scottish Ministers may by
# regulations appoint a day") and concluded from it that no day had been
# appointed. Every one of those is the moment a false negative forms, and every
# one of them is a search block away from the tool that answers it. The prompt
# already carries the rule; P2.2 measured the prompt-only version of this shape
# at 56%.
_RELATION_ROUTE_CLAUSE = (
    " Commencement, amendment, repeal and revocation are a special case: do NOT "
    "conclude anything about them from these rows. Call `get_legislation_changes` "
    "with the legislation_id — it is the only tool that returns those relations, "
    "and it answers in one call what no number of searches can."
)


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
        # P2.3 (B3b): only where a derivation claim can arise — a page of Acts
        # cannot produce one, and an unconditional clause would be noise on the
        # majority of searches.
        adjacency = (
            _ADJACENCY_CLAUSE
            if isinstance(results, list)
            and any(_is_secondary(r.get("legislation_id")) for r in results
                    if isinstance(r, dict))
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
            f"anything does not exist on the strength of this result.{adjacency}"
            f"{_RELATION_ROUTE_CLAUSE}{_CURRENCY_CLAUSE} "
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

    # P2.3 (B3b): the preamble is not a ranked provision, so a section search of
    # an SI can never establish its enabling power — and this is the route the
    # Worker actually uses for instruments (628 calls across the replay corpus,
    # against 32 `get_legislation_text`).
    enabling = _SECTION_ENABLING_CLAUSE if _is_secondary(leg) else ""
    if shown:
        return (
            f"\n\n[SEARCH SCOPE — {shown} provision(s) of {leg}, ranked by "
            f"relevance to {query_phrase}. This is NOT the full contents of the "
            "instrument: a provision that does not appear here may still be in "
            "it. Do NOT state that a provision, power or duty is absent from "
            f"{leg} on the strength of this result, and do NOT speculate about "
            f"why a provision was not returned.{enabling}{_RELATION_ROUTE_CLAUSE} If you report something "
            "as not found, say what was searched for and in which instrument.]"
        )
    return (
        f"\n\n[SEARCH SCOPE — 0 provisions of {leg} matched {query_phrase}. That "
        "means the ranked search did not surface one — NOT that the instrument "
        "lacks such a provision, and NOT that the instrument is unavailable. Do "
        "not speculate about the cause; you do not know it. If you report this, "
        "say what was searched for and in which instrument, and say the search "
        "did not locate it rather than that it does not exist.]"
    )


# ---------------------------------------------------------------------------
# B3(b) — an enabling power may be asserted only where it was retrieved
# (FIX_PLAN P2.3)
# ---------------------------------------------------------------------------
#
# *Made under* is the one relation of B3's five that `/amendment/search` cannot
# supply (P5.1): amendment, commencement, repeal and revocation are retrievable
# and get P3.5, this one gets a rule. The model was answering it from
# **search-result adjacency** — in 6340 it listed three real, correctly cited SIs
# as made under s.117 of the Education (Scotland) Act 1962, which is a 404 in
# LEX; they were simply the top keyword hits for the Act's title. Link-checking
# cannot catch that, which is what makes it the worst bucket.
#
# **Where the enabling power actually IS retrievable, measured rather than
# assumed — and the handover's premise was half wrong.** It is NOT in `full_text`
# (`ssi/2020/295` opens at "Section 1) Citation and commencement"; the "In
# exercise of the powers conferred by ..." recital is absent). It IS in
# `legislation.description` on the `/legislation/text` response, which
# `get_legislation_text` returns unslimmed — so the permitted branch is live
# today and needs nothing from P3.6. 6340 rep 1 exercised it: the model read
# `uksi/1979/766`'s recital verbatim and reported its enabling powers correctly.
#
# **Coverage, 103 instruments sampled live 2026-09-16 (`lex_probe --enabling`):**
#
#     uksi pre-1990        18/25 (72%) carry a recital
#     uksi 1990-2009        0/25
#     uksi 2010+            0/25
#     ssi 1990-2009         0/13      <- the corpus these lawyers work in
#     ssi 2010+             0/15
#
# One further instrument carried the recital in `full_text` and not in
# `description`, which is why `_recital_in` checks both: a rule that missed a
# real recital would forbid a claim the material actually supports.
#
# So for Scottish instruments the rule is in practice a **total** prohibition,
# and for modern UK SIs very nearly one. That is stated here rather than left
# implicit: a rule whose permitted branch almost never fires is a prohibition,
# and calling it a conditional would misdescribe the product.
#
# Nothing else in the tool set carries the relation. Over the whole post-Wave-1
# replay corpus — 38.8M characters of raw retrieval over 2,504 tool results —
# only **12 results carried an instrument preamble**, covering **6 distinct
# instruments, every one of them in session 6340**, and all of them pre-1990 UK
# SIs. Reproduce with `python -m tools.replay_report --dir <dir> corpus`.

# The recital an SI's preamble opens with. Deliberately broader than "in
# exercise of the powers conferred by": the corpus also uses "under and by
# virtue of the powers conferred on them by", "by virtue and in exercise of the
# powers in that behalf conferred by", and the 1963 form "Whereas the Treasury
# has determined under section 69(4) ...". All are statements of derivation.
_ENABLING_RECITAL = re.compile(
    r"in exercise of (?:the |his |her |their |its )?powers?"
    r"|powers? (?:in that behalf )?conferred (?:on|upon|by)"
    r"|by virtue of (?:the )?powers?"
    r"|makes? the following (?:Regulations|Order|Rules|Scheme)"
    r"|has determined under section",
    re.I,
)

# Secondary legislation, by `legislation_id` prefix. An Act has no enabling
# power of its own, so the whole block is silent on `ukpga`/`asp`/`anaw`/`nia`
# — telling a model not to assert something that cannot arise is noise, and
# noise in a block is what gets the block ignored.
_SECONDARY_PREFIXES = (
    "ssi", "uksi", "nisr", "wsi", "ssr", "uksro", "nisro", "ukci", "ukmo",
)


def _is_secondary(legislation_id: Any) -> bool:
    lid = str(legislation_id or "").strip().lower().lstrip("/")
    return lid.split("/")[0] in _SECONDARY_PREFIXES


def _text_record(data: Any) -> dict:
    """The `{legislation, full_text}` object, whichever shape it arrives in.

    `lex_probe` unwraps a single-element list here and this does too. Over the
    replay corpus every one of the 93 parseable `get_legislation_text` results
    was a bare dict, so the list branch is defensive rather than observed — but
    getting it wrong fails in the direction that forbids a claim the material
    supports, which nothing downstream would flag.
    """
    if isinstance(data, list):
        data = data[0] if data else {}
    if isinstance(data, str):
        try:
            obj, _ = json.JSONDecoder().raw_decode(data.lstrip())
        except Exception:
            return {}
        if isinstance(obj, list):
            obj = obj[0] if obj else {}
        return obj if isinstance(obj, dict) else {}
    return _as_dict(data)


def _recital_in(data: Any) -> str:
    """The enabling-power recital this `/legislation/text` record carries, if any.

    Checks `legislation.description` first because that is where it lives, and
    then the head of `full_text` — 1 of the 103 sampled instruments carried it
    only there, and a rule that silently misses a real recital would forbid a
    claim the material actually supports.
    """
    d = _text_record(data)
    leg = d.get("legislation")
    descr = str((leg or {}).get("description") or "") if isinstance(leg, dict) else ""
    if descr and _ENABLING_RECITAL.search(descr):
        return descr.strip()
    head = str(d.get("full_text") or "")[:1200]
    if head and _ENABLING_RECITAL.search(head):
        return head.strip()
    return ""


def enabling_power_note(args: dict, data: Any) -> str:
    """The block appended to every `get_legislation_text` result for an SI/SSI.

    Two branches, and unlike the search notes the *empty* one is the common case:
    0 of 28 sampled Scottish instruments state their enabling power. Both are
    statements of fact about this record, computed in code, which is the point —
    the model cannot tell "the preamble is absent from what I was given" from
    "the preamble does not exist", and it has been guessing the difference.

    Silent for primary legislation and for an errored result.
    """
    args = args or {}
    lid = str(args.get("legislation_id") or "").strip()
    if not _is_secondary(lid):
        return ""
    d = _text_record(data)
    if not d or d.get("error"):
        return ""

    recital = _recital_in(d)
    if recital:
        # Bounded: a preamble runs to a few hundred characters and the point is
        # to hand back the words, not the document.
        #
        # Square brackets are removed from the quote, and that is load-bearing
        # rather than cosmetic: `strip_scope_blocks` matches this block with
        # `\[ENABLING POWER[^\[\]]*\]`, so a `[` or `]` inside the recital would
        # end the match early and leave agent-facing bookkeeping rendering in
        # front of a lawyer. The same single-bracket form as the other tool
        # block, and the same reason it stays balanced.
        quoted = recital[:600].replace("[", "(").replace("]", ")")
        quoted += "..." if len(recital) > 600 else ""
        return (
            f"\n\n[ENABLING POWER — this record DOES state what {lid} was made "
            f"under, and these words are the only evidence of it you have:\n"
            f'  "{quoted}"\n'
            f"You MAY state the enabling power of {lid}, citing this text. Do NOT "
            "extend the claim to any other instrument: each one states its own, "
            "and most records do not state it at all.]"
        )
    return (
        f"\n\n[ENABLING POWER — this record does NOT state what {lid} was made "
        "under. No endpoint we call returns a made-under relation, and this "
        "record carries no enabling-power recital, so nothing you hold "
        f"establishes it. Do NOT write that {lid} was made under, cites, or "
        "relies on any provision as its enabling power, and do not infer one "
        "from the instrument's title or subject matter. If the question turns "
        "on it, say the enabling power could not be verified from the available "
        "material.]"
    )


# Appended to `search_legislation` and `search_legislation_sections` results.
# Short on purpose: it rides on blocks that already exist and are already long,
# and it is gated so it only appears where a derivation claim can actually
# arise. 6340's mechanism was adjacency — three SIs that merely ranked highly
# for an Act's title were reported as made under it — so the sentence names
# that inference and forbids it.
_ADJACENCY_CLAUSE = (
    " These rows carry NO relationship data: nothing here states what any "
    "instrument was made under. An instrument ranking highly in a search for an "
    "Act's title has NOT thereby been shown to be made under that Act — do not "
    "say that it was."
)
_SECTION_ENABLING_CLAUSE = (
    " Ranked provisions do not include the preamble, so this result cannot tell "
    "you what this instrument was made under; do not state an enabling power "
    "from it."
)


# Both routes by which the Worker touches a single instrument. **Both are
# recorded, and the section route is the one that matters**: over the replay
# corpus the Worker called `search_legislation_sections` 628 times against 32
# `get_legislation_text` calls, so recording only the latter would leave the
# report block and the lawyer-facing clause silent on almost every turn where a
# derivation claim can actually arise — including most of 6383's.
_ENABLING_ROUTES = ("get_legislation_text", "search_legislation_sections")


def record_enabling_power(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record what a retrieval established about one instrument's enabling power.

    Read by `worker_scope_block` and `answer_scope_footer`, which address the
    Manager and the lawyer respectively — neither of whom ever sees a tool
    result. Same division of labour as P2.2 and, before it, `provision_url_block`.

    Only `get_legislation_text` can ever set `stated`: the preamble is not a
    ranked provision, so a section search establishes that the instrument was
    looked at and nothing more.

    Never raises (Invariant 5).
    """
    if log is None:
        return
    try:
        if name not in _ENABLING_ROUTES:
            return
        lid = str((args or {}).get("legislation_id") or "").strip()
        if not _is_secondary(lid):
            return
        # A 404 is not an instrument that was looked at and found silent — it is
        # an instrument that was never read. 15 of the corpus's 108
        # `get_legislation_text` calls come back as the literal string
        # "Error executing tool: {...Legislation not found...}". Recording those
        # would inflate the "N instrument(s) looked at" denominator on the
        # worker's report and fire the lawyer-facing clause on a turn that
        # retrieved nothing at all.
        record = _text_record(data)
        if not record or record.get("error"):
            return
        stated = (name == "get_legislation_text") and bool(_recital_in(record))
        log.append({"tool": "enabling_power", "legislation_id": lid[:60],
                    "stated": stated})
    except Exception:
        pass


def _enabling_limb(log: Optional[list]) -> str:
    """The enabling-power limb of the worker's report block.

    Returns "" when the step touched no secondary legislation, because then no
    derivation claim about an instrument can arise and the sentence would be
    noise.
    """
    rows = [e for e in (log or []) if e.get("tool") == "enabling_power"]
    if not rows:
        return ""
    stated, silent = [], []
    for e in rows:
        lid = e.get("legislation_id") or ""
        bucket = stated if e.get("stated") else silent
        if lid and lid not in bucket:
            bucket.append(lid)
    silent = [x for x in silent if x not in stated]
    total = len(stated) + len(silent)
    if stated:
        return (
            f"Enabling power: retrieved for {len(stated)} of {total} instrument(s) "
            f"looked at — {', '.join(stated[:8])} (their own preambles state it). "
            "For EVERY other instrument named in this report the enabling power "
            "was NOT retrieved and is NOT known: do not write that it was made "
            "under, cites or relies on any provision."
        )
    return (
        f"Enabling power: NOT retrieved for any of the {total} instrument(s) "
        "looked at. No endpoint we call returns a made-under relation and none "
        "of these records states one. Do NOT write that any instrument was made "
        "under, cites or relies on a provision as its enabling power — say it "
        "could not be verified instead. Ranking near an Act in a keyword search "
        "is not evidence of being made under it."
    )


# ---------------------------------------------------------------------------
# B3 — the relationship, retrieved (FIX_PLAN P3.5)
# ---------------------------------------------------------------------------
#
# P2.3 forbade the unverified *made under* claim. This is the other four fifths
# of B3, and it goes the opposite way: commencement, amendment, repeal and
# revocation ARE retrievable (`/amendment/search`, found at P5.1), so the rule
# is *go and get it*, not *do not say it*.
#
# **The measured failure.** 6409 asked which sections of `asp/2025/2` had been
# commenced by regulation and was told "No commencement regulations have been
# made yet"; the record holds eight provisions commenced by SSI. 6410 got the
# same sentence about `asp/2025/9`; the record holds twenty commenced by
# `ssi/2025/388`. Neither is a hedge that went too far — both are confident
# negatives against data one endpoint away.
#
# **A retrieved relation invites the opposite error, and that is what this
# module guards.** P2.3's risk was over-claiming from nothing; P3.5's is
# over-claiming from something — reading a `not stated` effect as a
# commencement, reading the Act's own commencement section as a regulation,
# or reading a truncated window as a complete list. Each of those is a
# **structural** fact about the result, so each is stated in code rather than
# left to the model to notice.

# Rows whose `type_of_effect` is null are kept and labelled with this, never
# dropped — see `_slim_amendment_results`. The block below names the label so
# the model cannot treat it as an effect it recognises.
_EFFECT_NOT_STATED = "not stated"


def amendment_search_note(args: dict, data: Any) -> str:
    """The scope block appended to every `get_legislation_changes` result.

    Four branches' worth of facts, all computed from the result rather than
    asserted in general terms:

    * **what this can and cannot establish** — the relation, never a date, and
      never an enabling power (P2.3 still owns that one);
    * **the self-referential split** — an Act commencing its own sections under
      its own commencement provision is not commencement by regulation, and 28
      of `asp/2025/2`'s 36 relations are exactly that;
    * **the window** — if the fetch was cap-bound the list is a prefix of an
      unknown larger set, and saying so is the whole of P1.3's lesson;
    * **the empty case** — which is the one that produced 6409's and 6410's
      false negatives, and which must stay an honest negative rather than
      become a confident one in the other direction.
    """
    args = args or {}
    d = _as_dict(data)
    if not d or d.get("error"):
        return ""

    lid = str(d.get("legislation_id") or args.get("legislation_id") or "this legislation")
    direction = d.get("direction") or "to"
    relations = d.get("relations")
    if not isinstance(relations, int):
        return ""

    if not relations:
        # Honest failure, in the direction Invariant 1 protects. An empty
        # change record is a real and common answer — 112 of the 271
        # legislation_ids the replay corpus touched have none — but the index
        # is incomplete, so "nothing is recorded" is not "nothing happened".
        return (
            f"\n\n[CHANGE RECORD — no commencement, amendment, repeal or revocation "
            f"relation is recorded for {lid} in this direction. That is the change "
            "record being empty, NOT proof that the instrument has never been "
            "commenced or amended: a change not yet recorded here is invisible to "
            "this tool. Say that no such change is recorded, and say where you "
            f"looked. {LEX_COVERAGE_SENTENCE}]"
        )

    by_other = d.get("by_other_legislation")
    by_self = d.get("by_this_legislation_itself")
    effects = d.get("effects") if isinstance(d.get("effects"), dict) else {}

    bits = [
        f"\n\n[CHANGE RECORD — {relations} recorded relation(s) for {lid}: "
        + (
            "changes made TO it by other legislation"
            if direction == "to"
            else "changes it makes TO other legislation"
        )
        + ". These are legislation.gov.uk's own change records and are the only "
        "evidence of a commencement, amendment, repeal or revocation you have; "
        "you MAY state a relation listed here, citing the instrument named "
        "against it."
    ]

    if isinstance(by_self, int) and by_self:
        bits.append(
            f" {by_self} of them are marked `self: true` — {lid} acting on its OWN "
            "provisions under its own commencement or transitional provision. That "
            "is NOT commencement by regulation and NOT an amendment by another "
            f"instrument: if you are asked what commenced {lid}, the answer is the "
            f"{by_other if isinstance(by_other, int) else 0} relation(s) with "
            "`self: false`, and the self-referential ones are the Act commencing "
            "itself."
        )
    if effects.get(_EFFECT_NOT_STATED):
        bits.append(
            f" {effects[_EFFECT_NOT_STATED]} row(s) carry `type_of_effect: \"not "
            "stated\"` — the record shows a change was made and does NOT say what "
            "kind. Do not describe those as a commencement, an amendment or a "
            "repeal; say a change is recorded without a stated effect."
        )
    if d.get("window_complete") is False:
        bits.append(
            f" This list is TRUNCATED at {d.get('window_size')} rows and the API "
            "reports no total, so it is a window onto an unknown larger set: the "
            "instruments and provisions below are real, but the list is NOT "
            "complete and you must not present it as exhaustive."
        )
    # P2.5 (B4): which of these relations bear on currency, and — the branch
    # that corrects rather than extends P3.5 — which of them look as though they
    # do and do not. Placed before the closing caveats so the caveats still end
    # the block.
    bits.append(_relation_currency_limb(d))
    bits.append(
        " Two things this record does NOT contain, whatever it shows: there is no "
        "DATE on any relation, so you cannot say when a provision came into force "
        "from this — retrieve the commencing instrument for that; and there is no "
        "made-under relation, so it says nothing about any instrument's enabling "
        "power.]"
    )
    return "".join(bits)


def record_relations(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record what a change-record retrieval established, for the two agents downstream.

    Same division of labour as P2.2's `record_search` and P2.3's
    `record_enabling_power`: the Worker sees the tool result, and the agent that
    writes the answer — a Manager holding a `delegate_research` result, or the
    Deep Research synthesis holding a step's findings — never does.

    Never raises (Invariant 5).
    """
    if log is None:
        return
    try:
        if name != "get_legislation_changes":
            return
        d = _as_dict(data)
        if not d or d.get("error"):
            return
        relations = d.get("relations")
        if not isinstance(relations, int):
            return
        others = []
        for g in (d.get("related") or []):
            if isinstance(g, dict) and not g.get("self") and g.get("legislation_id"):
                if g["legislation_id"] not in others:
                    others.append(g["legislation_id"])
        log.append({
            "tool": "change_record",
            "legislation_id": str(
                d.get("legislation_id") or args.get("legislation_id") or ""
            )[:60],
            "direction": d.get("direction") or "to",
            "relations": relations,
            "by_other": d.get("by_other_legislation") if isinstance(
                d.get("by_other_legislation"), int) else 0,
            "others": others[:8],
            "complete": d.get("window_complete") is not False,
        })
    except Exception:
        pass


def _relations_limb(log: Optional[list]) -> str:
    """The change-record limb of the worker's report block.

    Silent when the step consulted no change record, because then nothing about
    commencement or amendment was established either way and the sentence would
    be noise — the same gate as `_enabling_limb`.

    **The empty-record case is the one that matters here.** A step that looked
    and found nothing is the step whose report says "no commencement regulations
    have been made", and the Manager writing that sentence has seen neither the
    tool result nor the note on it.
    """
    rows = [e for e in (log or []) if e.get("tool") == "change_record"]
    if not rows:
        return ""
    looked, found, empty, truncated = [], [], [], False
    for e in rows:
        lid = e.get("legislation_id") or ""
        if lid and lid not in looked:
            looked.append(lid)
        if e.get("by_other"):
            for o in e.get("others") or []:
                if o not in found:
                    found.append(o)
        elif not e.get("relations"):
            if lid and lid not in empty:
                empty.append(lid)
        if not e.get("complete"):
            truncated = True
    parts = [
        f"Change record (commencement / amendment / repeal / revocation): consulted "
        f"for {', '.join(looked[:8]) or 'n/a'}."
    ]
    if found:
        parts.append(
            f" Relations by another instrument were retrieved and name "
            f"{', '.join(found[:8])} — you MAY state those, citing the instrument."
        )
    if empty:
        parts.append(
            f" NO relation is recorded for {', '.join(empty[:8])}. Report that as "
            "nothing being recorded in the change record, NOT as a finding that no "
            "commencement or amendment has been made."
        )
    if truncated:
        parts.append(
            " At least one of those lists was truncated, so it is not exhaustive."
        )
    parts.append(
        " The change record carries no dates and no made-under relation: do not "
        "state a commencement date, or an enabling power, from it."
    )
    return "".join(parts)


def _relations_footer_clause(entries: Optional[list]) -> str:
    """The lawyer-facing half of P3.5, as one clause on the existing footer.

    Gated on the **structural** fact that this turn consulted a change record,
    for the reason `_enabling_footer_clause` is: a prose detector deciding
    whether the answer contains a commencement claim fails silently, and this
    work has been burned by that repeatedly.

    Two things a lawyer cannot otherwise tell apart, and both are the reason the
    clause exists rather than a general disclaimer: whether a stated
    commencement was retrieved or inferred, and whether a "nothing found" was a
    search that came back empty or a change record that came back empty. The
    second is what 6409 and 6410 were told.

    Worded to stay clear of `NEG_ASSERTED` (P2.2) and `DERIVATION_ASSERTED`
    (P2.3), which read these answers — P2.2's own footer tripped the first and
    corrupted its denominator. Pinned by `test_footer_trips_no_detector`.
    """
    rows = [e for e in (entries or []) if e.get("tool") == "change_record"]
    if not rows:
        return ""
    consulted = []
    for e in rows:
        lid = e.get("legislation_id") or ""
        if lid and lid not in consulted:
            consulted.append(lid)
    any_found = any(e.get("by_other") for e in rows)
    truncated = any(not e.get("complete") for e in rows)
    lead = (
        " Commencement and amendment relations above come from legislation.gov.uk's "
        f"recorded changes for {', '.join(consulted[:3])}, which this research "
        "consulted directly"
    )
    if any_found:
        lead += (
            "; those records carry no dates, so any date given above was read from "
            "the instrument itself and not from the relation."
        )
    else:
        lead += (
            ", and those records list nothing in the direction consulted. An empty "
            "change record means the change is not recorded, which is a weaker "
            "statement than the change never having been made."
        )
    if truncated:
        lead += (
            " At least one record was longer than could be listed in full, so "
            "treat the instruments named above as examples rather than a complete "
            "set."
        )
    return lead


# ---------------------------------------------------------------------------
# B4 — in-force status, which nothing in the tool surface establishes (P2.5)
# ---------------------------------------------------------------------------
#
# P1.2 removed the `current_only` filter and the two places it asserted currency
# — the "In force as at <today>" pill and the system-prompt line *"Status:
# In-force legislation only"*. This is the model half, and the re-baseline
# measured that removing the filter did **not** clear the bucket: in-force
# claims went 27 -> 30 across the sweep, because three prompt sites still tell
# the Worker to state currency and the report structure makes
# "Jurisdiction & Status" a mandatory section.
#
# **The model was not inventing a source. It was quoting the only field that
# looked like one.** 30 turns of the Wave 1 sweep carry 34 in-force sentences
# and almost every one reads *"is currently in force (revised)"* or *"(status:
# revised)"*. `status` records which text version legislation.gov.uk holds —
# `final` 60.3%, `revised` 38.8%, `stub` 0.9% over 15,160 model-visible rows —
# and says nothing about currency. `_slim_search_results` now emits it as
# `text_version`, which removes the affordance instead of arguing with it.
#
# **What this row may NOT do is forbid the claim.** P3.5 made commencement
# retrievable and routes the Worker to `get_legislation_changes` for exactly
# these questions; a blanket prohibition would suppress answers that are now
# properly sourced, which is Invariant 1 read in the inverse direction. So the
# rule is about the *blanket* claim, and the seams below separate the evidence
# that exists from the claim that does not:
#
#   * **`text_version`** — a text-version marker. No currency content at all.
#   * **a `(repealed …)` / `(revoked …)` / `(expired)` marker in the TITLE** —
#     a real negative signal, on **258 of 15,160** model-visible search rows
#     (1.7%, 43 distinct titles). Asymmetric and that is the point: its presence
#     is evidence the instrument is NOT in force, its absence is no evidence
#     either way. A **date** follows the keyword in only **8 of those 256**, so
#     the title is a flag and not a date route.
#     ~~256 of 12,640, 2.0%, 42 titles~~ — that was five of the seven replay
#     directories. `lex_probe --inforce` walks all seven and is the figure.
#   * **`coming into force` relations** — P3.5's route. Provision-level, sourced,
#     and carries no date: **0 of 19,031** such relations embed one in
#     `type_of_effect` (552 of 89,465 relations do, none of them commencement),
#     so the date still needs the second hop into the commencing instrument.
#   * **the repeal/revocation family** — provision-level and sourced, the
#     negative counterpart of the above.
#   * **`Commencement Order` relations** — NOT the subject's commencement. See
#     `_slim_amendment_results`; this is the one that would have turned 6411's
#     unsourced answer into a differently-sourced wrong one.
#   * **`valid_date` on `/legislation/text`** — the date the held revised text is
#     stated to be up to date to (`2026-03-11` for the Scotland Act 1998).
#     Available on the 18% of turns that reach Phase 3, and rising under P3.5.
#     It is not an in-force date, and it is the honest thing the Status line can
#     say when nothing else is retrievable — a substitution rather than a
#     silence, which is what keeps this fix on the right side of Invariant 1.
#
# None of them establishes that an Act **as a whole** is in force as at today,
# and that is the specific claim the corpus is full of: *"All referenced
# legislation is currently in force"* (6341), *"Yes, the Scotland Act 1998 is in
# force"* (6411), *"All cited legislation is currently in force"* (6363, 6375).
#
# Reproduce every figure above with `python -m tools.lex_probe --inforce` and
# `python -m tools.replay_report --dir <dir> currency`.

# What the title marker looks like. legislation.gov.uk appends it to the short
# title of a wholly repealed or revoked instrument. Anchored to the opening
# parenthesis so an Act *named* "… (Repeals) Act" is not caught, and the 42
# distinct matching titles in the corpus were read one by one before this was
# relied on.
_TITLE_STATUS_MARKER = re.compile(
    r"\((repealed|revoked|expired|spent)\b([^)]*)\)", re.I
)

# `valid_date` on a `/legislation/text` response: the date the held revised text
# is stated to be up to date to. NOT an in-force date, and the wording below
# never lets it become one.
_VALID_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _title_markers(results: Any) -> list:
    """Titles among these search rows that carry a repeal/revocation marker.

    Returns `[(legislation_id, keyword, tail)]`, tail being whatever followed the
    keyword inside the bracket — a date on 8 of the 258 corpus rows that match,
    empty on the rest.
    """
    out = []
    if not isinstance(results, list):
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        m = _TITLE_STATUS_MARKER.search(str(r.get("title") or ""))
        if not m:
            continue
        out.append((
            str(r.get("legislation_id") or "")[:60],
            m.group(1).lower(),
            m.group(2).strip()[:40],
        ))
    return out


# The currency limb of the `search_legislation` scope block. Unconditional on
# the non-empty branch, like everything else in that block: a detector deciding
# whether *this* search is about currency would have to read the model's intent
# before the model has formed it.
#
# **Kept to one sentence, and that is a measured constraint rather than taste.**
# This clause rides on every productive `search_legislation` result — 790 of
# them in one sweep — so each 100 characters here is ~80 KB of Worker context
# across a run, and `test_a_long_query_is_capped_not_dropped` bounds the whole
# block at 2,000 characters for that reason. The load-bearing half of this row
# is elsewhere (`text_version` itself, `_currency_limb`, `_IN_FORCE_RULE`); this
# is the reminder at the point of misreading.
_CURRENCY_CLAUSE = (
    " `text_version` is which text version the index holds (`final`, `revised`, "
    "`stub`) and is NOT evidence that anything is in force: state currency only "
    "from a `get_legislation_changes` relation, never from these rows."
)


def currency_note(args: dict, data: Any) -> str:
    """The currency limb for a `search_legislation` result. Empty unless it earns it.

    Two parts, and only this one is conditional: the standing warning about
    `text_version` rides on the main search block (`_CURRENCY_CLAUSE`), and this
    adds the **positive** finding when the page actually contains one — a title
    carrying `(repealed)` or `(revoked)`.

    That branch is worth its own block because it is the rare case where a search
    result *does* say something about currency, and it says it in the direction a
    lawyer must not miss. 1.7% of rows, so on 98% of searches this returns "".
    """
    d = _as_dict(data)
    if not d or d.get("error"):
        return ""
    marked = _title_markers(d.get("results"))
    if not marked:
        return ""
    listed = "; ".join(
        f"{lid or '(unidentified)'} — title says " + kw + (f" {tail}" if tail else "")
        for lid, kw, tail in marked[:6]
    )
    more = len(marked) - 6
    return (
        f"\n\n[CURRENCY — {len(marked)} of the rows above carry a repeal or "
        f"revocation marker in the TITLE itself: {listed}"
        + (f" (and {more} more)" if more > 0 else "")
        + ". That marker is legislation.gov.uk's own and you MAY rely on it: "
        "treat those instruments as repealed or revoked and do NOT present them "
        "as current law. Where the marker carries no date, the date of repeal is "
        "not established by it. The absence of a marker on the other rows is NOT "
        "evidence that they are in force — nothing in a search result is.]"
    )


def _relation_currency_limb(d: dict) -> str:
    """The three currency-bearing relation classes, appended to a change record.

    Only the middle branch is a *correction* of P3.5 rather than an addition to
    it: P3.5's block invites the model to state any relation the record lists,
    citing the instrument named against it, and 29 of `ukpga/1998/46`'s
    relations are `Commencement Order` rows belonging to other Acts' amendments.
    """
    commenced = d.get("provisions_commenced")
    orders = d.get("commencement_orders_of_amendments")
    repeals = d.get("repeal_or_revocation_relations")
    bits = []
    if isinstance(commenced, int) and commenced:
        bits.append(
            f" {commenced} relation(s) are `coming into force` and name a "
            "provision of this legislation: those ARE its own commencement and "
            "you may state them, citing the instrument against each."
        )
    if isinstance(orders, int) and orders:
        bits.append(
            f" {orders} relation(s) carry the effect `Commencement Order` and are "
            "marked `commences_this_legislation: false`. Those are NOT "
            "commencements of this legislation: each is a commencement order for "
            "an AMENDMENT made to it by some other Act, which is why the "
            "provision against them is a placeholder and not a section number. "
            "Do NOT name any of those instruments as having commenced this "
            "legislation or any of its provisions."
        )
    if isinstance(repeals, int) and repeals:
        bits.append(
            f" {repeals} relation(s) are repeals or revocations: those establish "
            "that the named provision is no longer in force, and you may state "
            "them the same way. The record gives no date for them either."
        )
    if isinstance(commenced, int) and not commenced:
        bits.append(
            " NO relation here is a `coming into force` relation for this "
            "legislation, so this record does NOT establish when or whether any "
            "of its provisions were commenced. Say that the commencement is not "
            "recorded here; do not conclude it was never commenced, and do not "
            "substitute a `Commencement Order` row for it."
        )
    bits.append(
        " Whatever this record shows, it CANNOT establish that this legislation "
        "is in force as a whole, as at today. Do not write that it is."
    )
    return "".join(bits)


def record_currency(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record the currency evidence one tool call actually produced. Never raises.

    Called from `run_worker_tool` for the three tools that can produce any:
    `search_legislation` (a title marker), `get_legislation_changes` (a relation)
    and `get_legislation_text` (`valid_date`). Same division of labour as
    `record_search`, `record_enabling_power` and `record_relations` — the Worker
    sees the tool results, and the agent that writes *"all cited legislation is
    currently in force"* has seen none of them.
    """
    if log is None:
        return
    try:
        d = _as_dict(data)
        if not d or d.get("error"):
            return
        if name == "search_legislation":
            marked = _title_markers(d.get("results"))
            if marked:
                log.append({
                    "tool": "currency",
                    "kind": "title_marker",
                    "marked": [
                        {"legislation_id": lid, "keyword": kw, "tail": tail}
                        for lid, kw, tail in marked[:8]
                    ],
                })
        elif name == "get_legislation_changes":
            lid = str(d.get("legislation_id") or args.get("legislation_id") or "")[:60]
            log.append({
                "tool": "currency",
                "kind": "relations",
                "legislation_id": lid,
                "commenced": d.get("provisions_commenced") or 0,
                "orders": d.get("commencement_orders_of_amendments") or 0,
                "repeals": d.get("repeal_or_revocation_relations") or 0,
            })
        elif name == "get_legislation_text":
            # `_text_record` returns the `{legislation, full_text}` wrapper, and
            # `valid_date` is on the NESTED record — the same shape trap
            # `lex_probe`'s docstring records for `text` vs `full_text`. Reading
            # it off the wrapper is silently always empty, which would forbid a
            # statement the material supports and flag nothing.
            leg = _text_record(d).get("legislation")
            leg = leg if isinstance(leg, dict) else {}
            vd = str(leg.get("valid_date") or "")
            if _VALID_DATE.match(vd):
                log.append({
                    "tool": "currency",
                    "kind": "valid_date",
                    "legislation_id": str(
                        args.get("legislation_id") or leg.get("id") or ""
                    )[:60],
                    "valid_date": vd,
                })
    except Exception:
        pass


def _currency_limb(log: Optional[list]) -> str:
    """The currency limb of the worker's report block.

    **Not silent when the step produced no currency evidence**, which is the
    opposite gate from `_enabling_limb` and `_relations_limb` and is deliberate:
    a step that established nothing about currency is exactly the step whose
    report says *"all cited legislation is currently in force"*. So the gate is
    "did this step touch legislation at all", and the two branches differ in what
    they permit rather than in whether they speak.
    """
    if not log:
        return ""
    touched = [
        e for e in log
        if e.get("tool") in ("search_legislation", "search_legislation_sections",
                             "change_record")
    ]
    rows = [e for e in log if e.get("tool") == "currency"]
    if not touched and not rows:
        return ""

    marked, commenced, repealed, valid = [], [], [], []
    for e in rows:
        kind = e.get("kind")
        if kind == "title_marker":
            for m in e.get("marked") or []:
                label = f"{m.get('legislation_id') or '?'} ({m.get('keyword')})"
                if label not in marked:
                    marked.append(label)
        elif kind == "relations":
            lid = e.get("legislation_id") or "?"
            if e.get("commenced") and lid not in commenced:
                commenced.append(lid)
            if e.get("repeals") and lid not in repealed:
                repealed.append(lid)
        elif kind == "valid_date":
            label = f"{e.get('legislation_id') or '?'} to {e.get('valid_date')}"
            if label not in valid:
                valid.append(label)

    parts = [
        "In-force status: NOTHING in this step establishes that any instrument is "
        "in force as at today. The index records which text version it holds, not "
        "currency, and no tool returns an in-force flag."
    ]
    if commenced:
        parts.append(
            f" Commencement relations WERE retrieved for {', '.join(commenced[:6])}"
            " — a provision-level statement about those, citing the commencing "
            "instrument, is supported. The relations carry no dates."
        )
    if repealed:
        parts.append(
            " Repeal or revocation relations were retrieved for "
            f"{', '.join(repealed[:6])} — a statement that those provisions are no "
            "longer in force is supported, again without a date."
        )
    if marked:
        parts.append(
            " These carry a repeal or revocation marker in their own title and "
            f"must NOT be presented as current law: {', '.join(marked[:6])}."
        )
    if valid:
        parts.append(
            f" The held text is stated to be up to date to: {', '.join(valid[:4])}"
            " — that is a text-version date, not an in-force date, and it is the "
            "most a Status section can say about currency for those instruments."
        )
    parts.append(
        " So in the Jurisdiction & Status section, state territorial extent from "
        "the metadata, and for currency state ONLY what is listed above — and "
        "state it, rather than calling a tool and reporting nothing from it. If "
        "nothing is listed, say that in-force status could not be verified from "
        "the available sources and say what would establish it. The prohibition "
        "is on the PROPOSITION and not on a form of words: \"currently in "
        "force\", \"in operation\", \"still good law\", \"current law\", "
        "\"active status\", \"continues to apply\" and \"all cited legislation "
        "is in force\" are the same unsupported claim in different words, and a "
        "judgment citing an Act is not evidence that the Act is in force today."
    )
    return "".join(parts)


def _currency_footer_clause(entries: Optional[list]) -> str:
    """The lawyer-facing half of P2.5, as one clause on the existing footer.

    Gated on the **structural** fact that this turn searched the legislation
    index — the same gate the footer itself has — rather than on a prose detector
    deciding whether the answer contains a currency claim. Every other clause on
    this footer is gated the same way, for the reason recorded above
    `_enabling_footer_clause`: a prose detector in the product fails silently.

    Two branches. Where a commencement or repeal relation was retrieved the
    lawyer needs to know the statement is provision-level and undated; where none
    was, the lawyer needs to know that no currency check was performed at all —
    which is the thing 42 of 62 pre-pilot sessions could not have known, because
    the UI was telling them the opposite.

    **The title-marker limb was drafted here and removed after the smoke run.**
    The marker is recorded per SEARCH ROW, not per cited instrument, so the
    footer read *"the index's own title for uksi/2024/697 marks it as repealed"*
    on an answer about the Scotland Act 1998 — an unrelated row that happened to
    rank on the same page. Naming it is not provenance, it is noise in a
    disclosure a lawyer has to read, and the alternative (check whether the
    answer cites it) is the prose detector this module refuses to put in the
    product. The marker still reaches the model twice, via `currency_note` and
    `_currency_limb`, which is where it can actually be acted on.

    Worded to stay clear of `NEG_ASSERTED` (P2.2), `DERIVATION_ASSERTED` (P2.3),
    P3.5's commencement detectors and this row's own `CURRENCY_ASSERTED`. P2.2's
    footer tripped its own denominator and P2.3's first two drafts tripped two
    detectors; `test_footer_trips_no_detector` now covers four rows' clauses
    because of it.
    """
    rows = [e for e in (entries or []) if e.get("tool") == "currency"]
    if not rows:
        return ""
    sourced = []
    for e in rows:
        if e.get("kind") == "relations":
            lid = e.get("legislation_id") or ""
            if lid and (e.get("commenced") or e.get("repeals")) and lid not in sourced:
                sourced.append(lid)
    lead = (
        " Whether legislation is in force is not something this index reports, so "
        "nothing above has been checked against a commencement date"
    )
    if sourced:
        lead += (
            "; what was checked is the recorded changes for "
            f"{', '.join(sorted(sourced)[:3])}, which name the instruments "
            "involved provision by provision but carry no dates."
        )
    else:
        lead += " and no change record was consulted for this answer."
    return lead


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
_TOOL_BLOCK = re.compile(
    r"\[/?(?:SEARCH SCOPE|ENABLING POWER|CHANGE RECORD|CURRENCY)[^\[\]]*\]", re.I
)


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


# ---------------------------------------------------------------------------
# P2.7 — a search the discovery budget refused is a limit, not a finding
# ---------------------------------------------------------------------------
#
# The parliamentary budget's stop tells the model to write that "no relevant
# records were found". Copied to legislation, that manufactures the bare
# negative P2.2 exists to stop. A refused search did not run, so it is kept out
# of `record_search` (the footer must not list a search that never happened)
# and recorded here instead, as the limit it is. The worker's block tells the
# agent writing the answer; the footer tells the lawyer. Both are gated on the
# structural fact that a search was refused this turn, never on the prose.

_BUDGET_TOOL = "discovery_budget"


def record_budget_stop(log: Optional[list], name: str, args: dict, budget: Optional[dict]) -> None:
    """Record one search the discovery budget refused. Never raises."""
    if log is None:
        return
    try:
        budget = budget or {}
        log.append({
            "tool": _BUDGET_TOOL,
            "blocked_tool": name,
            "query": str((args or {}).get("query") or "")[:200],
            "limit": budget.get("limit"),
            "run": budget.get("id"),
        })
    except Exception:
        pass


def _budget_rows(log: Optional[list]) -> list:
    return [e for e in (log or []) if isinstance(e, dict) and e.get("tool") == _BUDGET_TOOL]


def _budget_limb(log: Optional[list]) -> str:
    """The worker-block line saying discovery was cut short. "" if it was not.

    Worded around "searching was cut short" so it cannot be read by
    `scope_record_gap` as a count of searches that ran (that regex keys on
    "Searched the legislation index").
    """
    try:
        rows = _budget_rows(log)
        if not rows:
            return ""
        limit = next((e.get("limit") for e in rows if e.get("limit")), None)
        terms = []
        for e in rows:
            q = (e.get("query") or "").strip()
            if q and q not in terms:
                terms.append(q)
        n = len(rows)
        listed = "; ".join(f'"{q}"' for q in terms[:3])
        return (
            "Searching was cut short: this step used its limit of "
            + (f"{limit} rounds of " if limit else "")
            + f"legislation-index searches, and {n} further "
            + ("search it asked for was" if n == 1 else "searches it asked for were")
            + " not run"
            + (f" (for: {listed})" if listed else "")
            + ". Material this step did not reach may still be in the index. If "
            "the answer you write reports anything as not found, it MUST also say "
            "that searching was stopped by a limit on how much one research step "
            "may search, before it finished. Calling delegate_research again with "
            "the same brief will meet the same limit."
        )
    except Exception:
        return ""


def _budget_footer_clause(entries: Optional[list]) -> str:
    """The lawyer-facing half of P2.7, as one clause on the existing footer.

    Worded clear of `NEG_ASSERTED`, `HALT_PARAPHRASE` and `HALT_AS_TIMEOUT`: no
    "not found", no "internal limit", no "halted", no "timed out". A budget stop
    is not a halt (the step still wrote a report), and a halt detector that read
    this line would grade halts as disclosed on turns that did not halt. Pinned
    by `test_discovery_budget.py`.
    """
    try:
        rows = _budget_rows(entries)
        if not rows:
            return ""
        steps = len({e.get("run") for e in rows})
        n = len(rows)
        who = ("one research step" if steps == 1 else f"{steps} research steps")
        return (
            f" Searching was also limited: {who} reached the cap on how much "
            f"searching a step may do, and {n} further "
            + ("search it asked for was" if n == 1 else "searches it asked for were")
            + " not run, so the answer above may not reflect everything a longer "
            "search would have found."
        )
    except Exception:
        return ""


def worker_scope_block(log: Optional[list], cfg: Optional[dict] = None) -> str:
    """The scope record appended, in code, to a Worker's report.

    Addressed to the agent that will read the report — a Manager holding it as a
    `delegate_research` result, or the Deep Research synthesis holding it as a
    step's findings — which is the agent that actually writes the negative.

    Deliberately compact: it is a provenance footer, not a transcript. The full
    query list lives in the audit trace, and 6409 turn 7 ran 25 searches, so
    printing them all would bury the report it is attached to.
    """
    # P2.4 (B12): a case-law search is recorded in the same log, for the
    # lawyer-facing footer only. It must not wake this block: a case-law-only
    # step would get a block demanding "the search terms above" with none above,
    # which is P2.9's defect in a new place. So a log holding nothing else is
    # treated as empty, exactly as it was before case law was recorded.
    if not log or all(e.get("tool") == CASE_LAW_TOOL for e in log):
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
    # P2.7. Next to the searches it qualifies: the list above is not everything
    # this step would have searched for.
    _budget = _budget_limb(log)
    if _budget:
        lines.append(_budget)
    filters = _filters_phrase(cfg, {})
    lines.append(f"Filters in force for the whole step: {filters}.")
    # P2.3 (B3b). Same reason as everything else in this block: the Worker saw
    # the per-instrument ENABLING POWER notes, and the agent that writes the
    # report's claims never does.
    _enabling = _enabling_limb(log)
    if _enabling:
        lines.append(_enabling)
    # P3.5 (B3). Same reason again, and it is the sharpest case of it: the
    # sentence "no commencement regulations have been made" is written by the
    # Manager or the DR synthesis, neither of which has seen the change record
    # the Worker consulted — or failed to consult.
    _relations = _relations_limb(log)
    if _relations:
        lines.append(_relations)
    # P2.5 (B4). The one limb here that speaks even when its step found nothing,
    # because "nothing found" is the state in which the blanket in-force claim
    # gets written — see `_currency_limb`.
    _currency = _currency_limb(log)
    if _currency:
        lines.append(_currency)
    # P2.4 (6373). The Manager relayed "could you check the citation" from a
    # report whose tool result it never saw; the fact travels with the report.
    _not_held = _not_held_limb(log)
    if _not_held:
        lines.append(_not_held)
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


def _enabling_footer_clause(entries: Optional[list]) -> str:
    """The lawyer-facing half of P2.3, as one clause on the existing footer.

    **Not a second footer, and not unconditional.** P2.2 put one line of
    provenance on every researched answer and recorded that as the decision most
    open to being overruled; adding a second on every answer would double a cost
    already judged marginal. This one is gated on a *structural* fact — did this
    turn retrieve the text of any statutory instrument — not on a prose detector
    deciding whether the answer contains a derivation claim. A prose detector in
    the product fails silently, which is the trap this work has hit twelve times.

    It is true whether or not the model asserted anything, which is what makes an
    unconditional-within-its-gate statement safe: "where the answer states one"
    is vacuous on an answer that states none.

    Worded to stay out of the way of the detectors already reading these answers
    — `NEG_ASSERTED` (P2.2) and `DERIVATION_ASSERTED` (P2.3) — because P2.2's own
    footer tripped `NEG_ASSERTED` and corrupted its denominator. Pinned by
    `test_search_scope.py::test_footer_trips_no_detector`.
    """
    rows = [e for e in (entries or []) if e.get("tool") == "enabling_power"]
    if not rows:
        return ""
    stated = [e.get("legislation_id") for e in rows if e.get("stated")]
    stated = [x for x in dict.fromkeys(stated) if x]
    # The wording dodges `NEG_ASSERTED` deliberately, and the first draft did
    # not: "no instrument consulted here carried the preamble" trips its
    # `\bno … instruments?` limb, which would have enrolled every turn carrying
    # this clause into P2.2's negatives denominator — P2.2's own error,
    # repeated one row later. The test is what caught it.
    if stated:
        # "The enabling power OF an instrument … uksi/1979/766" was the first
        # draft and it tripped P2.3's OWN detector — an instrument id plus
        # "enabling power of" is a derivation phrase in ordinary prose, which is
        # the point of the detector and not something to loosen. The clause
        # moves instead.
        return (
            " An instrument's enabling power is recorded here only where its own "
            f"preamble states it; that applied only to {', '.join(stated[:4])}, "
            "and for anything else mentioned above the derivation is unverified."
        )
    return (
        " This index does not record which enabling power an instrument was "
        "granted by, and none of the material consulted here carried the "
        "preamble that states it, so any such derivation given above is "
        "unverified."
    )


# The footer the model sometimes copies back, and the reason it must be removed
# before a fresh one is appended.
#
# **Found live during P3.5's smoke run, and it is P2.2's defect, not P3.5's** —
# it is visible in `wave2_p22_final` too. The footer is prose addressed to the
# lawyer, so `strip_scope_blocks` leaves it alone (correctly); it then travels
# into the next turn's conversation history, the model reproduces it verbatim at
# the end of its answer, and the code appends its own. The lawyer reads the same
# disclosure twice, which is exactly how a disclosure stops being read at all.
#
# Anchored to the end and matched line by line because the footer is a single
# line with no newlines inside it. A greedy dot-all run from the first
# occurrence would delete any answer text a model happened to put after a copied
# footer; this cannot.
_ECHOED_FOOTER = re.compile(
    r"(?:\n*^\*Search scope:[^\n]*\*[ \t]*)+\s*\Z", re.M
)


def strip_answer_footer(text: str) -> str:
    """Remove a scope footer the model copied out of the previous turn.

    Applied immediately before `answer_scope_footer` appends the real one, so
    exactly one reaches the lawyer and it is the one computed from THIS turn's
    searches. Never raises.
    """
    if not text:
        return text
    try:
        return _ECHOED_FOOTER.sub("", text).rstrip()
    except Exception:
        return text


def _listed_terms(queries) -> tuple:
    """(terms, rendered) for a footer: the first two queries, quoted once.

    The model routinely quotes its own query ('"Water Industry Commission"'),
    which wrapped again renders as `""…""`. Strip the model's quoting and dedupe
    case-insensitively before re-quoting once.

    **Every quote character, not just the outer ones**, and P2.3's acceptance
    sweep is what showed why. `.strip('"')` on `"Education (Scotland) Act
    1962" 117` removes the leading quote and leaves the internal one, so the
    lawyer read `"Education (Scotland) Act 1962" 117"`, which is unbalanced and
    reads as two searches where there was one. Phrase-search quoting is
    deliberately lost here: the line is provenance prose, and the exact queries
    are in the audit trace.
    """
    terms, seen = [], set()
    for q in queries:
        q = re.sub(r"[\"'“”]+", " ", q or "")
        q = re.sub(r"\s+", " ", q).strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            terms.append(q)
    quoted = ", ".join(f'"{t}"' for t in terms[:2])
    rest = len(terms) - 2
    more = f" ({rest} further quer{'y' if rest == 1 else 'ies'} not listed)" if rest > 0 else ""
    return terms, quoted + more


# ---------------------------------------------------------------------------
# B12 — the case-law corpus gap, disclosed in code (FIX_PLAN P2.4)
# ---------------------------------------------------------------------------
#
# **The gap is total, and the obvious wording of it is false.** The National
# Archives' Find Case Law offers 42 court codes and none is Scottish;
# `court=csoh` is rejected with a 400 (P5.2, Session 5). But Scottish appeals
# that reached the UK Supreme Court ARE indexed (*Daly v HM Advocate*, *ABC v
# Principal Reporter*, *X v Lord Advocate*). So "no Scottish case law" or
# "Scottish courts are not indexed" would understate what is there and teach a
# lawyer to distrust a sound UKSC result, which is the Invariant 1 regression.
# What is missing is four named courts. "Does not comprehensively index", the
# wording the prompts used to carry, is false in the other direction: the gap
# is not partial.
#
# **An empty result is a disclosure; a full one is the trap.** A Scots-law
# query returns 50 English judgments that mention Scotland, not nothing. So the
# one note the code already emitted (on ZERO results, `agent_shared.py`) never
# fires where it matters. In 6375 turn 2, a Deep Research run with 18-30
# `search_case_law` calls, the lawyer was told nothing and was given English
# common-interest privilege as Scots law. That doctrine error is P3.3's; this is
# the disclosure that should have sat beside it. Before-column: 0 of 65 turns
# that searched case law in the replay corpus carry this disclosure from the
# code, and 4 carry it from the model (`replay_report caselaw`).
#
# **Gated on the structural fact that this turn called `search_case_law`.** Not
# on a jurisdiction filter: 6375 ran with none. Not on reading the question or
# the answer for "Scots law": that is a prose detector in the product, which
# this module refuses (see `answer_scope_footer`). The statement is true for
# every user, and this deployment is the Scottish Government's.
#
# **One line, never two.** The clause joins the legislation line when there is
# one (fresh or carried), and stands alone only when there is not, which is
# every `case_law_only` turn (6385). Three things read that line and each
# breaks on a second one: `_earlier_footers` parses only the LAST line of the
# trailing footer block, so a case-law line after the legislation one would
# switch P2.8's carried line off without an error; `replay_report corpus`
# counts two `*Search scope:` openers in one answer as a duplicate footer; and
# the lawyer reads one disclosure more readily than two.
#
# **"Privy Council" is deliberately absent.** The prompts used to say Scottish
# matters appear via the UK Supreme Court "or Privy Council". Only the UKSC
# route is verified; three `court=ukpc` probes (2026-09-17) found no Scottish
# case, which proves nothing either way.

CASE_LAW_TOOL = "search_case_law"
_CASE_LAW_DATABASE = "the case-law database (the National Archives' Find Case Law)"

# Worded to stay clear of `NEG_ASSERTED`, `NOT_FOUND` and every other detector
# that reads these answers (pinned by `test_case_law_gap.py`). "It holds … but
# not the decisions of" rather than "does not index" or "no judgments": both of
# those trip `NEG_ASSERTED`, which would enrol a positive turn as a negative the
# moment any instrument read the whole answer instead of the prose.
CASE_LAW_COVERAGE_SENTENCE = (
    "It holds Scottish appeals decided by the UK Supreme Court, but not the "
    "decisions of the Court of Session (Inner or Outer House), the Sheriff "
    "Appeal Court, the Sheriff Courts or the High Court of Justiciary, so "
    "judgments it returns for a Scottish question may come from courts outside "
    "Scotland."
)


def record_case_law_search(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record one case-law search for the lawyer-facing footer. Never raises.

    Self-gated on the tool name, so a caller may pass every tool through it.
    `ok` is False when the search came back as an error (the executor's
    `Error executing tool: …` string, or JSON carrying `error`, which is what a
    rejected court code returns), so the footer never says a search ran when it
    failed.
    """
    if log is None or name != CASE_LAW_TOOL:
        return
    try:
        d = _as_dict(data)
        results = d.get("results")
        log.append({
            "tool": CASE_LAW_TOOL,
            "query": str((args or {}).get("query") or "")[:200],
            "shown": len(results) if isinstance(results, list) else None,
            "ok": bool(d) and not d.get("error"),
        })
    except Exception:
        pass


def _case_law_body(entries: Optional[list]) -> str:
    """The case-law statement, without its opening words or markup. "" if none."""
    rows = [e for e in (entries or [])
            if isinstance(e, dict) and e.get("tool") == CASE_LAW_TOOL]
    if not rows:
        return ""
    done = [e for e in rows if e.get("ok", True)]
    terms, listed = _listed_terms(e.get("query") for e in (done or rows))
    if done:
        head = f"{_CASE_LAW_DATABASE} was searched" + (f" for {listed}" if terms else "")
    else:
        head = (f"a search of {_CASE_LAW_DATABASE} was attempted"
                + (f" for {listed}" if terms else "")
                + " and returned an error")
    return f"{head}. {CASE_LAW_COVERAGE_SENTENCE}"


def case_law_scope_clause(entries: Optional[list]) -> str:
    """P2.4 (B12): the case-law statement as a clause on an existing scope line.

    Appended inside the legislation line, fresh or carried, so a turn that
    searched both corpora still shows the lawyer one line. "" when this turn ran
    no case-law search. Never raises.
    """
    try:
        body = _case_law_body(entries)
        return f" For this reply {body}" if body else ""
    except Exception:
        return ""


def case_law_scope_footer(entries: Optional[list]) -> str:
    """P2.4 (B12): the case-law statement as a scope line of its own.

    For a turn with no legislation line to join, which is every `case_law_only`
    turn and a hybrid turn that searched only case law with nothing carried.
    The caller tries the legislation lines first and uses this only when both
    are empty, so exactly one line reaches the lawyer. Same single-line
    `*Search scope: …*` shape, which `_ECHOED_FOOTER` and
    `replay_report._without_footer` both strip. Never raises.
    """
    try:
        body = _case_law_body(entries)
        return f"\n\n*Search scope: for this reply {body}*" if body else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# P2.4, second half: a record the index does not hold is not a wrong citation
# ---------------------------------------------------------------------------
#
# **Measured before building, at HEAD `4890573`** (`wave2_p24_pre`, 6373 n=3).
# FrankieH cited SSI 2026/170, correctly; LEX 404s it. All three Worker reports
# attributed the miss to her: *"It is possible the citation contains an error"*,
# *"please verify the year and SSI number"*, *"It appears there may be a
# confusion with … SSI 2021/170"*. The Manager passed that on in two of the
# three (one as "Could you check the citation", one as "It is possible you are
# referring to the 2021 Regulations"), and filtered it in the third.
#
# **Where the inference forms is structural.** Every one of those runs called
# `get_legislation_text` on `ssi/2026/170` and was handed
# `Error executing tool: {"detail":"Legislation not found: ssi/2026/170"}`. The
# model reads "not found" on a direct retrieval by id as proof the id is wrong.
# The twelve pre-P2.4 replay directories hold 36 such results, 31 of them in the
# two sessions where a lawyer's citation was questioned (6409 and 6373). The reporting rule on every
# search note already says "never to the user's citation", and did not reach
# this, because this is not a search result.
#
# So the fact is stated at that result, in code, and carried to the Manager in
# the worker's block, the same two seams P2.2 needed. Not a lawyer-facing
# clause: "is this instrument held" is P3.7's (`/legislation/lookup`), and a
# footer cannot stop the prose questioning the citation, which is what
# `negatives` grades.

_NOT_HELD = re.compile(r"Legislation not found:\s*([A-Za-z0-9/_.-]+)")


def _not_held_id(args: dict, data: Any) -> str:
    """The id a retrieval reported as not held, or "" if it did not."""
    if not isinstance(data, str) or not data.startswith("Error executing tool"):
        return ""
    found = _NOT_HELD.search(data)
    if not found:
        return ""
    return str((args or {}).get("legislation_id") or found.group(1)).strip()[:60]


def not_held_note(args: dict, data: Any) -> str:
    """The note appended to a retrieval the index answered with not-found.

    In `[SEARCH SCOPE — …]` form, with no brackets inside, so the strip that
    already removes tool blocks from an answer covers it unchanged. Never
    raises.
    """
    try:
        lid = _not_held_id(args, data)
        if not lid:
            return ""
        return (
            f"\n\n[SEARCH SCOPE — not held: this index has no record under the id "
            f"{lid}. That is a fact about the index, not about the law and not "
            f"about the user's citation. {LEX_COVERAGE_SENTENCE} A correct, "
            "current citation is therefore often not held, and recent instruments "
            "least of all. Do NOT write that the citation may be wrong or "
            "contain an error, do NOT ask the user to check, verify or confirm "
            "it, and do NOT present a different instrument (another year or "
            "number) as the one the user meant. Say plainly that this index does "
            "not hold it and that its contents could not be checked here. If "
            "you built this id yourself, the id format may be at fault, not the "
            "user.]"
        )
    except Exception:
        return ""


def record_not_held(log: Optional[list], name: str, args: dict, data: Any) -> None:
    """Record a not-found retrieval for the worker's block. Never raises."""
    if log is None:
        return
    try:
        lid = _not_held_id(args, data)
        if lid:
            log.append({"tool": "not_held", "legislation_id": lid, "via": name})
    except Exception:
        pass


def _not_held_limb(log: Optional[list]) -> str:
    """The worker-block line naming what the index did not hold. "" if nothing."""
    ids = [e.get("legislation_id") for e in (log or []) if e.get("tool") == "not_held"]
    ids = [x for x in dict.fromkeys(ids) if x]
    if not ids:
        return ""
    return (
        f"Not held in this index (a direct retrieval by id found no record): "
        f"{', '.join(ids[:8])}. That is the index's gap, not an error in the "
        "user's citation: do not ask the user to check, verify or confirm it, "
        "and do not suggest they meant a different year or number."
    )


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
    all_entries = list(searches or [])
    searches = [s for s in all_entries if s.get("tool") == "search_legislation"]
    if not searches:
        return ""
    # Quote handling and the two-term cut are shared with the case-law clause;
    # see `_listed_terms`.
    terms, listed = _listed_terms(s.get("query") for s in searches)
    if not terms:
        return ""
    filters_phrase = _lawyer_filters_phrase(cfg)
    # P2.4 (B12): the case-law clause goes LAST, inside this one line. First
    # would break `_FRESH_FOOTER`'s anchored parse; a second line would be
    # skipped by `_earlier_footers`, which reads only the last one.
    # P2.7: the budget clause comes straight after the sentence it qualifies
    # (what the searches can and cannot establish), and after the parse's
    # anchor, so `_FRESH_FOOTER` reads the line exactly as before.
    return (
        f"\n\n*Search scope: the legislation index was searched for {listed}; "
        f"{filters_phrase}. This is a ranked search of an index that is known to be "
        "incomplete — roughly 85% of 2025 Scottish SIs and under 10% of "
        "instruments made in 2026 are held (sampled Sep 2026) — so anything "
        "reported above "
        "as not found was not found in this index, which is not the same as being "
        f"absent from the law.{_budget_footer_clause(all_entries)}"
        f"{_enabling_footer_clause(all_entries)}"
        f"{_relations_footer_clause(all_entries)}"
        f"{_currency_footer_clause(all_entries)}"
        f"{case_law_scope_clause(all_entries)}*"
    )


# P2.8 (B5): the footer `answer_scope_footer` writes, read back out of the
# conversation history. Only the fresh form is read, never the carried one: a
# carried line restates searches already recorded in an earlier fresh footer,
# so reading it would add nothing and would let one carried line feed the next.
# Coupled to the f-string above by `test_search_scope.py`, which round-trips
# every shape that function can emit. If the wording changes and the parse
# stops matching, the carried line goes silent (today's behaviour). It does not
# go wrong.
_FRESH_FOOTER = re.compile(
    r'\*Search scope: the legislation index was searched for '
    r'(?P<terms>"[^"\n]*"(?:, "[^"\n]*")*)'
    r'(?: \((?P<rest>\d+) further quer(?:y|ies) not listed\))?; '
    r'(?P<filters>[^\n]*?)\. This is a ranked search\b'
)
# Both search tools, not just the one the fresh footer lists. A turn that only
# searched WITHIN an instrument has run a search, so "no search of the index
# was run for this reply" would be false there. That turn stays silent.
_SEARCH_TOOLS = ("search_legislation", "search_legislation_sections")
_MAX_CARRIED_TERMS = 2


def _earlier_footers(messages: Optional[list]) -> list:
    """Every fresh scope footer at the end of an earlier assistant message.

    Reads only the LAST line of each message's trailing footer block, which is
    the one code appended: `strip_answer_footer` removes any copy the model
    wrote before the real one goes on. Only assistant messages are read, so a
    lawyer pasting an old answer into their own message contributes nothing.
    """
    out = []
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = m.get("content")
        if not isinstance(content, str) or "*Search scope:" not in content:
            continue
        tail = _ECHOED_FOOTER.search(content)
        if not tail:
            continue
        last = tail.group(0).strip().splitlines()[-1].strip()
        found = _FRESH_FOOTER.match(last)
        if not found:
            continue
        out.append({
            "terms": re.findall(r'"([^"\n]*)"', found.group("terms")),
            "rest": int(found.group("rest") or 0),
            "filters": found.group("filters").strip(),
        })
    return out


def carried_scope_footer(
    messages: Optional[list], searches: Optional[list] = None,
) -> str:
    """The scope line for a reply that searched nothing, after replies that did.

    **P2.8 (B5).** `answer_scope_footer` is per TURN, and a conversation is not.
    A follow-up the Manager answers from history runs no search, so it got no
    footer, even when it restates an earlier negative. The lawyer then read an
    unqualified "not found" two turns after seeing the qualified one. Measured
    over the ten replay directories: four turns in two sessions, each session
    repeating it in 2 of 3 reps (6409, 6341).

    **Gated on structure, not on the answer.** It fires when this turn recorded
    no search and an earlier assistant message carries a code-emitted fresh
    footer. It does not fire because the answer "repeats a negative"; that
    would be a prose detector in the product, which this module refuses (see
    `answer_scope_footer`). It therefore also fires on clarifying questions and
    positive follow-ups. That is the same trade P2.2 made for researched turns.

    **Worded so that it cannot describe a search it did not run.** It says
    first that no search was run for this reply, and labels every term as
    searched *earlier in this conversation*. It does not say the reply relied
    on those searches. So on a reply drawn from training knowledge alone
    (`wave1/6341 r1 t8`, "what is a stub"), it states a true fact that the
    lawyer needs: nothing was looked up for this answer. The not-found clause
    is scoped to results "in those searches", so it lends no index authority
    to a negative the model produced from memory.

    Kept in the `*Search scope: …*` single-line shape on purpose. That is the
    shape `_ECHOED_FOOTER` strips when the model copies it back, and the shape
    `replay_report._without_footer` removes before grading the model's prose.
    In any other shape, its "not found" words would trip `NEG_ASSERTED` and
    enrol purely positive turns as negatives. That was P2.2's own error.

    The caller must NOT call this when a delegation failed or a peer was
    consulted. In either case this turn's searches are unknown, and "no search
    was run" might be false. Never raises.
    """
    try:
        entries = list(searches or [])
        if any(e.get("tool") in _SEARCH_TOOLS for e in entries):
            return ""
        earlier = _earlier_footers(messages)
        if not earlier:
            return ""
        # Newest first: the restated negative is most often the latest one.
        terms, seen = [], set()
        for f in reversed(earlier):
            for t in f["terms"]:
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    terms.append(t)
        if not terms:
            return ""
        shown = terms[:_MAX_CARRIED_TERMS]
        # An exact count only where one is knowable. Across several replies an
        # unlisted query may repeat a listed one, so summing their counts
        # could overstate the number of searches. Say "further" instead.
        if len(earlier) == 1:
            rest = earlier[0]["rest"] + len(terms) - len(shown)
        elif all(f["rest"] == 0 for f in earlier):
            rest = len(terms) - len(shown)
        else:
            rest = None
        if rest is None:
            more = " (further queries not listed)"
        elif rest > 0:
            more = f" ({rest} further quer{'y' if rest == 1 else 'ies'} not listed)"
        else:
            more = ""
        filters = {f["filters"] for f in earlier}
        filters_phrase = (
            filters.pop() if len(filters) == 1 else
            "the filters differed between those replies and are stated beneath each"
        )
        quoted = ", ".join(f'"{t}"' for t in shown)
        return (
            "\n\n*Search scope: no search of the legislation index was run for "
            f"this reply. Earlier in this conversation it was searched for "
            f"{quoted}{more}; {filters_phrase}. Each was a ranked search of an "
            "index that is known to be incomplete, so a result reported as not "
            "found in those searches was not found in this index, which is not "
            f"the same as being absent from the law.{_enabling_footer_clause(entries)}"
            f"{_relations_footer_clause(entries)}"
            f"{_currency_footer_clause(entries)}"
            # P2.4 (B12): a hybrid follow-up that searched only case law. This
            # clause is about THIS reply's own search, so it is true here too.
            f"{case_law_scope_clause(entries)}*"
        )
    except Exception:
        return ""


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
