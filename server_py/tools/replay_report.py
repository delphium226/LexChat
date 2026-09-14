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
HALT_PARAPHRASE = re.compile(
    r"tool[- ]call step|exceeded (?:the )?(?:maximum )?(?:technical )?limit"
    r"|operational limit|research (?:process )?was halted|halted across",
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


def _json_or_none(s: Any) -> Any:
    if not isinstance(s, str):
        return s if isinstance(s, (dict, list)) else None
    try:
        return json.loads(s)
    except Exception:
        return None


@dataclass
class FilterLoss:
    """One `search_legislation` call, counted on both sides of the filters."""

    query: str
    api_total: int | None
    api_returned: int | None
    tool_returned: int | None
    tool_total: int | None

    @property
    def discarded(self) -> int:
        if self.api_returned is None or self.tool_returned is None:
            return 0
        return max(0, self.api_returned - self.tool_returned)

    @property
    def wiped_out(self) -> bool:
        """The API found results and the model was shown none."""
        return bool(self.api_returned) and self.tool_returned == 0

    @property
    def total_misreported(self) -> bool:
        """The API's real match count did not survive to the model."""
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

    filter_losses: list = field(default_factory=list)
    searches: int = 0
    searches_wiped_out: int = 0
    searches_total_misreported: int = 0
    results_discarded: int = 0

    bare_negatives: int = 0  # B5: a not-found with no explanation
    explained_negatives: int = 0
    in_force_claims: int = 0  # B4
    scots_gap_disclosures: int = 0  # B12
    bad_links: list = field(default_factory=list)  # B14
    total_links: int = 0
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
            "discarded": self.results_discarded,
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
            m = PROVISION_LABEL.search(label)
            if not m:
                continue
            kind = _LABEL_TO_PATH.get(m.group(1).lower())
            if not kind:
                continue
            num = m.group(2)
            # `paragraph` has no stable legislation.gov.uk segment of its own
            # (it lives under a schedule), so it is not asserted on.
            if kind == "paragraph":
                continue
            if f"/{kind}/{num}" not in url:
                sig.bad_links.append(BadLink(label, url, f"/{kind}/{num}"))

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

        for dg in audit.get("delegations", []):
            sig.delegations += 1
            if HALT_LITERAL.search(dg.get("report") or ""):
                sig.halt_in_worker_report += 1
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
                sig.results_discarded += fl.discarded
                if fl.wiped_out:
                    sig.searches_wiped_out += 1
                if fl.total_misreported:
                    sig.searches_total_misreported += 1

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
        "billed_empty", "halt_src", "halt_ans", "searches", "wiped", "discarded",
        "bare_neg", "inforce", "bad_links", "links", "src_unused", "src_kept",
        "src_fallbk",
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
    tot_s = sum(s.searches for s in sigs)
    tot_w = sum(s.searches_wiped_out for s in sigs)
    print(f"  search_legislation calls    {tot_s}")
    print(f"    returning 0 to the model  {tot_w}"
          f"{f'  ({100*tot_w/tot_s:.0f}%)' if tot_s else ''}   <- B2 / P1.1")
    print(f"    results discarded         {sum(s.results_discarded for s in sigs)}")
    print(f"    real total not passed on  {sum(s.searches_total_misreported for s in sigs)}   <- B5 / P1.3")
    tl = sum(s.total_links for s in sigs)
    bl = sum(len(s.bad_links) for s in sigs)
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
                flag = "  <-- ALL DISCARDED" if fl.wiped_out else ""
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
            d_ = sum(r.results_discarded for r in runs)
            notes.append(f"{w}/{t} searches wiped by filters ({d_} results discarded)")
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
    args = p.parse_args(list(argv) if argv is not None else None)
    return {"summary": cmd_summary, "session": cmd_session, "baseline": cmd_baseline}[
        args.cmd
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
