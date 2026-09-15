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

NOT_FOUND = re.compile(
    r"\b(no (?:relevant )?(?:results?|legislation|provisions?|records?|cases?|"
    r"regulations?|instruments?)\b|not (?:be )?(?:found|located|retrieved)"
    r"|could not (?:be )?(?:find|locate|retrieve|identify)"
    r"|does not appear to (?:be|exist)|no .{0,30}have been made)",
    re.I,
)
# A negative is "explained" if it says what was searched / under what filters.
NEGATIVE_EXPLAINED = re.compile(
    r"search(?:ed|ing)? (?:for|term|the)|filter|jurisdiction (?:filter|was set)"
    r"|scope of (?:the|my) search|query used|search terms",
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
    # B14's real question, and the one `bad_links` cannot answer: was this
    # provision URL ever RETURNED by a tool, or did the model build it by
    # appending `/section/{n}` to an Act's base URI? A manufactured URL usually
    # resolves to a real page, so it reads as a verified citation and is not —
    # which makes it more dangerous than a link that merely misses its
    # provision. Baseline 257/260 (99%); Wave 1 26/134 (19%).
    provision_links: int = 0
    provision_links_manufactured: int = 0
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


def _urls_returned_by_tools(doc: dict) -> set:
    """Every `url`/`uri` any tool handed back, normalised.

    legislation.gov.uk serves the same resource at `/id/asp/2000/1/section/21`
    and `/asp/2000/1/section/21`; the LEX endpoints use both spellings, so the
    `/id/` segment is dropped before comparing or every link would look
    manufactured.
    """
    out = set()
    for t in doc.get("turns", []):
        for dg in (t.get("audit") or {}).get("delegations", []):
            for tl in dg.get("tools", []):
                parsed = _json_or_none(tl.get("final_result"))
                if not isinstance(parsed, dict):
                    continue
                for r in parsed.get("results") or []:
                    if not isinstance(r, dict):
                        continue
                    u = r.get("url") or r.get("uri")
                    if u:
                        out.add(str(u).replace("/id/", "/"))
    return out


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
    tool_urls = _urls_returned_by_tools(doc)

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
                if url.replace("/id/", "/") not in tool_urls:
                    sig.provision_links_manufactured += 1
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

        turn_halted = False
        for dg in audit.get("delegations", []):
            sig.delegations += 1
            if HALT_LITERAL.search(dg.get("report") or ""):
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
    print(f"  provision URLs cited        {pl}, MANUFACTURED (never returned by a tool) {pm}"
          f"{f'  ({100*pm/pl:.0f}%)' if pl else ''}   <- B14 / P1.4, the provenance question")
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
    args = p.parse_args(list(argv) if argv is not None else None)
    return {
        "summary": cmd_summary,
        "session": cmd_session,
        "baseline": cmd_baseline,
        "compare": cmd_compare,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
