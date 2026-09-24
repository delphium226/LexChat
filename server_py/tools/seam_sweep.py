"""The Worker seam over MANY stored delegations at once (P4.6).

`seam_replay worker` draws one payload. A prompt row's A/B wants the same
draw over every stored delegation that showed the defect, on both sides, and
the counts behind one command. This selects the delegations, draws each one
through `seam_replay`'s own builders, and prints one line per payload and
the totals:

    python -m tools.seam_sweep --dirs baseline wave1 wave2 \\
        --turns 6335:1,3,4 6346:1,2,3,5 6343:1,2,4,5 6347:1 6350:2 \\
        --report-matches p46 [--without-fix --rev <sha>] [--out DIR]

A delegation that made no tool call is drawn with `--first-round` (its
prompt and brief, real tools offered, stopped at the first call), because
the composition seam needs recorded results. Such a draw can come back as
SEARCHED: the Worker chose to search, and what it would then write is not
observable here. Each draw costs about $0.01-0.05. Rep 1 files only.

**The Deep Research synthesis seam (P4.7)** over a named payload set, both
sides from one command, each draw written to `--out` (keep it in the
scratchpad: a report echoes the lawyer's terms) and graded:

    python -m tools.seam_sweep --synthesis p47 --out DIR [--without-fix --rev <sha>]
    python -m tools.seam_sweep --synthesis p47 --grade DIR     # no model call

`--grade` reads both sides' saved draws back and prints the A/B table and the
Invariant 1 panel. About $0.11 a draw.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
import tools.seam_replay as sr  # noqa: E402

REPLAY = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "replay"

# Which delegations to draw: those whose recorded report matches.
REPORT_MATCHES = {
    "p46": rr.SCRIPTED_NEGATIVES["database"],
    "any": re.compile(r""),
}


def select(dirs: list, turns: dict, pattern) -> list:
    """(dir, session, turn, delegation index, tool count, run path) per payload."""
    out = []
    for d in dirs:
        for sid, wanted in turns.items():
            f = REPLAY / d / f"{sid}_rep1.json"
            if not f.exists():
                continue
            doc = json.loads(f.read_text(encoding="utf-8"))
            for t in doc.get("turns", []):
                if t.get("turn") not in wanted:
                    continue
                for k, dg in enumerate((t.get("audit") or {}).get("delegations") or [], 1):
                    if not pattern.search(dg.get("report") or ""):
                        continue
                    n = len([x for x in dg.get("tools") or [] if not x.get("budget_blocked")])
                    out.append((d, sid, t["turn"], k, n, f))
    return out


# --- the Deep Research synthesis seam (P4.7) --------------------------------
#
# Chosen before any build (FIX_PLAN P4.7, Session 26) and fixed here so the
# published command is the whole definition. (dir, session, rep, turn).
P47_SETS = {
    # Every legislation_only synthesis in `wave2` (the Wave 3 baseline, one per
    # Deep Research turn of the 12 sessions that have one); the three other
    # stored reports that mention case law (`replay_report drgaps --all-dirs
    # --list`); and one post-P3.1 payload each for 6374 and 6409, whose
    # findings cite at subsection depth. (The P4.1 script's Deep Research
    # synthesis is not here: its turn 2 ran hybrid.)
    "p47_legislation": [
        ("wave2", "6341", 1, 7), ("wave2", "6357", 1, 3), ("wave2", "6357", 1, 6),
        ("wave2", "6365", 1, 1), ("wave2", "6367", 1, 1), ("wave2", "6374", 1, 2),
        ("wave2", "6374", 1, 4), ("wave2", "6382", 1, 1), ("wave2", "6383", 1, 4),
        ("wave2", "6384", 1, 4), ("wave2", "6389", 1, 1), ("wave2", "6406", 1, 2),
        ("wave2", "6406", 1, 3), ("wave2", "6408", 1, 2), ("wave2", "6409", 1, 6),
        ("wave1", "6408", 1, 2), ("wave2_p21", "6383", 3, 4),
        ("wave2_p28_smoke", "6341", 1, 7),
        ("wave3_p38", "6374", 1, 2), ("wave3_p35", "6409", 1, 6),
    ],
    # The hybrid syntheses whose stored report carries a TRUE case-law
    # negative (the `drgaps` recall check): Invariant 1 says it must survive.
    "p47_hybrid": [
        ("baseline", "6363", 1, 5), ("baseline", "6407", 1, 3), ("wave1", "6407", 1, 3),
        ("wave2", "6407", 1, 3), ("wave2_p24", "6375", 3, 2),
        ("wave2_p24_pre", "6375", 1, 2), ("wave2_p24_pre", "6375", 3, 2),
        ("wave4_p41_pre", "p41_6346_dr", 1, 2),
    ],
}
P47_SETS["p47"] = P47_SETS["p47_legislation"] + P47_SETS["p47_hybrid"]

DR_MARKER = re.compile(r"\*\*key\s*findings", re.I)
# A gap stated by what the retrieval did not establish (Thomas's wording and
# the P4.7 prompt's), counted beside the classifier's case-law negatives so a
# hybrid report that rewords its true negative still counts as stating it.
GAP_BY_RETRIEVAL = re.compile(
    r"\bdo(?:es)?\s+not\s+(?:establish|address|consider|interpret)\b"
    r"|\bdid\s+not\s+(?:establish|address|return|identify|find|complete)\b", re.I)
# Case law as the subject of a gap sentence. Wider than `drgaps`'s source
# regex, which must stay narrow because it FLAGS a defect: here a sentence is
# only being counted as stating a gap. **Corrected at first use (Session 26):**
# the v2 after-draw of `wave2_p24_pre`/6375 r3 t2 said step 1 "did not return
# findings", so the "common law cases" it covered were not established. That
# is a gap stated by what happened (step 1's findings are empty), and the
# narrow regex read it as silence.
# ("authority" was tried and dropped: it matched a legislation title, a
# "Specified Authority" Order, on 6407.)
_CL_GAP_SUBJECT = re.compile(rr.DR_CASE_WORD.pattern + r"|\bcases\b", re.I)

# Pinpoint spellings, canonicalised before two labels are compared.
# **Corrected at first use (Session 26):** the comparison was literal, so an
# after-draw of `wave3_p38`/6374 t2 that wrote "s. 126(7)(a)" where the
# findings wrote "Section 126(7)(a)" scored as losing 5 of 6 pinpoints it kept.
_PIN_WORDS = (
    (r"\bsections?\b\.?|\bss?\.", "s"),
    (r"\bschedules?\b|\bsched\b\.?|\bsch\b\.?", "sch"),
    (r"\bparagraphs?\b|\bparas?\b\.?", "para"),
    (r"\barticles?\b|\barts?\b\.?", "art"),
    (r"\bregulations?\b|\bregs?\b\.?", "reg"),
)


def pin_key(pin: str) -> str:
    s = pin.lower()
    for pat, rep in _PIN_WORDS:
        s = re.sub(pat, rep, s)
    return re.sub(r"[\s.,]", "", s)


def pinned_pairs(text: str) -> set:
    """{(normalised provision URL, canonical pinpoint)} over the links in `text`."""
    from src.utils.citation_links import (  # noqa: PLC0415
        _PINPOINT, is_provision_url, normalise_leg_url)
    out = set()
    for label, url in MD_LINK_NESTED.findall(text or ""):
        if not is_provision_url(url):
            continue
        for m in _PINPOINT.finditer(label):
            out.add((normalise_leg_url(url), pin_key(m.group(0))))
    return out


# A Markdown link whose label may hold ONE level of balanced brackets, as a
# judgment's does: `[*Berezovsky v Hine* [2011] EWCA Civ 1089](url)`, which
# CommonMark renders as a link. **Corrected at first use (Session 26):**
# `replay_report.MD_LINK` forbids `]` in a label, so it does not see that
# link at all, and a v2 hybrid draw (`wave2_p24_pre`/6375 r1 t2) that linked
# all six of its judgments this way graded as having dropped them.
MD_LINK_NESTED = re.compile(
    r"\[((?:[^\[\]\n]|\[[^\[\]\n]*\]){1,300})\]\((https?://[^)\s]+)\)")


def link_targets(text: str) -> set:
    """The distinct targets the text links to, scheme and `/id/` folded.
    A link count rises and falls with repeated citations; this is the set a
    report may not lose (added in Session 26)."""
    return {u.rstrip("/").replace("http://", "https://").replace("/id/", "/")
            for _label, u in MD_LINK_NESTED.findall(text or "")}


def case_law_gap_sentences(text: str) -> int:
    """Sentences stating a gap about case law: a case-law negative, or a
    gap put by what the retrieval did (does not establish / did not return
    or complete)."""
    return sum(1 for s in rr._sentences(text or "")
               if _CL_GAP_SUBJECT.search(s)
               and (rr.DR_ABSENT.search(s) or GAP_BY_RETRIEVAL.search(s)))


def synthesis_grade(text: str, doc: dict, turn: dict) -> dict:
    """One draw's numbers. Nothing here quotes the text."""
    from src.agent.agent_core import _REPORT_SECTIONS, _extract_section_headers  # noqa: PLC0415

    rm = sr._cfg_for(doc, turn)["_research_mode"]
    cl = rr.dr_classify(text)
    absent = sum(1 for k, _ in cl if k in ("absent", "absent_excluded"))
    gap_cl = case_law_gap_sentences(text)
    headers = _extract_section_headers(text)
    sections = _REPORT_SECTIONS.get(rm, _REPORT_SECTIONS["legislation_only"])
    missing = [s for s in sections if not any(s.lower() in h for h in headers)]
    have = pinned_pairs("\n".join(f["content"] for f in sr.step_findings_from(turn)))
    return {
        "research_mode": rm,
        "urls": link_targets(text),
        "cl_absent": absent,
        "cl_excluded": sum(1 for k, _ in cl if k == "excluded"),
        "cl_gap": gap_cl,
        "links": len(MD_LINK_NESTED.findall(text)),
        "pins": len(pinned_pairs(text) & have), "pins_of": len(have),
        "missing": missing,
        "marker": bool(DR_MARKER.search(text)),
        "currency": rr.currency_verdict(text, rr._currency_support(turn))[0],
        "chars": len(text),
    }


def _draw_name(p: tuple, without_fix: bool) -> str:
    d, sid, rep, turn = p
    return f"{d}__{sid}_r{rep}_t{turn}{'_nofix' if without_fix else ''}.md"


def _synthesis_payload(p: tuple) -> tuple:
    d, sid, rep, turn_no = p
    return sr.load_turn(REPLAY / d / f"{sid}_rep{rep}.json", turn_no)


_RM_SHORT = {"legislation_only": "leg", "case_law_only": "caselaw",
             "legislation_and_case_law": "hybrid", "parliamentary_records": "holyrood",
             "westminster_records": "westminster"}


def _grade_line(p: tuple, g: dict) -> str:
    d, sid, rep, turn = p
    rm = _RM_SHORT.get(g["research_mode"], g["research_mode"])
    return (f"  {d:<16} {sid:<12} r{rep} t{turn:<2} {rm:<8} "
            f"cl-absent {g['cl_absent']}  cl-excl {g['cl_excluded']}  cl-gap {g['cl_gap']}  "
            f"links {g['links']:>2}  pins {g['pins']}/{g['pins_of']}  "
            f"key-findings {'yes' if g['marker'] else 'NO'}  currency {g['currency']:<11} "
            f"missing {','.join(g['missing']) or '-'}  {g['chars']:,} chars")


def synthesis_sweep(set_name: str, out: Path, without_fix: bool, rev: str) -> int:
    payloads = P47_SETS[set_name]
    side = f"WITHOUT fix ({rev})" if without_fix else "current code"
    print(f"seam_sweep synthesis {set_name}: {len(payloads)} payload(s)  {side}")
    out.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for p in payloads:
        doc, turn = _synthesis_payload(p)
        msgs = sr.synthesis_messages(doc, turn, without_fix, rev)
        cfg = asyncio.run(sr._provider_cfg(sr._cfg_for(doc, turn)))
        content, cost, _m = asyncio.run(sr.run_seam(msgs, cfg))
        total += cost
        (out / _draw_name(p, without_fix)).write_text(content, encoding="utf-8")
        print(_grade_line(p, synthesis_grade(content, doc, turn)) + f"  ${cost:.4f}", flush=True)
    print(f"  total ${total:.4f}")
    return 0


def synthesis_grade_dir(set_name: str, out: Path) -> int:
    """Both sides' saved draws, graded, with the A/B totals and Invariant 1."""
    payloads = P47_SETS[set_name]
    rows = []
    for p in payloads:
        doc, turn = _synthesis_payload(p)
        pair = {}
        for side, nofix in (("before", True), ("after", False)):
            f = out / _draw_name(p, nofix)
            if f.exists():
                pair[side] = synthesis_grade(f.read_text(encoding="utf-8"), doc, turn)
        rows.append((p, pair))
    print(f"seam_sweep synthesis {set_name}, graded from {out}")
    for side in ("before", "after"):
        print(f"\n  {side}:")
        for p, pair in rows:
            if side in pair:
                print(_grade_line(p, pair[side]))
    both = [(p, pr) for p, pr in rows if "before" in pr and "after" in pr]
    print(f"\n  A/B over {len(both)} payload(s) drawn on both sides "
          f"(of {len(payloads)}):")
    for rm in sorted({pr["after"]["research_mode"] for _p, pr in both}):
        sub = [(p, pr) for p, pr in both if pr["after"]["research_mode"] == rm]
        print(f"\n    {rm} ({len(sub)} payloads)        before   after")

        def tot(side, key, sub=sub):
            return sum(pr[side][key] for _p, pr in sub)

        def cnt(side, fn, sub=sub):
            return sum(1 for _p, pr in sub if fn(pr[side]))

        for label, key in (("case-law 'not found' sentences", "cl_absent"),
                           ("case-law 'excluded' sentences", "cl_excluded"),
                           ("case-law gap stated (negative or 'does not establish')", "cl_gap"),
                           ("links, summed", "links"), ("pinpoints kept, summed", "pins")):
            print(f"      {label:<56} {tot('before', key):>6} {tot('after', key):>7}")
        print(f"      {'pinpoints available in the findings, summed':<56} "
              f"{tot('before', 'pins_of'):>6} {tot('after', 'pins_of'):>7}")
        for label, fn in (
                ("reports with a case-law 'not found'", lambda g: g["cl_absent"]),
                ("reports stating a case-law gap", lambda g: g["cl_gap"]),
                ("reports carrying **Key findings**", lambda g: g["marker"]),
                ("reports with every section of the type", lambda g: not g["missing"]),
                ("currency UNSUPPORTED (P2.5)", lambda g: g["currency"] == "unsupported")):
            print(f"      {label:<56} {cnt('before', fn):>6} {cnt('after', fn):>7}")
        print(f"      {'distinct link targets, summed':<56} "
              f"{sum(len(pr['before']['urls']) for _p, pr in sub):>6} "
              f"{sum(len(pr['after']['urls']) for _p, pr in sub):>7}")
        lost = [(p, pr['before']['urls'] - pr['after']['urls']) for p, pr in sub]
        lost = [(p, u) for p, u in lost if u]
        print(f"      payloads whose after-draw lost a target the before-draw linked: "
              f"{len(lost)}" + ("" if not lost else ": " + "; ".join(
                  f"{p[0]}/{p[1]} r{p[2]} t{p[3]} {len(u)} "
                  f"({sum('caselaw' in x for x in u)} judgments)" for p, u in lost)))
        fell = [(p, pr) for p, pr in sub
                if pr["after"]["links"] < pr["before"]["links"]
                or pr["after"]["pins"] < pr["before"]["pins"]]
        print(f"      payloads where links or pinpoints fell: {len(fell)}"
              + ("" if not fell else ": " + "; ".join(
                  f"{p[0]}/{p[1]} r{p[2]} t{p[3]} links {pr['before']['links']}->"
                  f"{pr['after']['links']} pins {pr['before']['pins']}->{pr['after']['pins']}"
                  for p, pr in fell)))
    return 0


def _parse_turns(specs: list) -> dict:
    out = {}
    for s in specs:
        sid, _, ts = s.partition(":")
        out[sid] = {int(x) for x in ts.split(",") if x}
    return out


def main(argv=None) -> int:
    rr._utf8_stdout()
    p = argparse.ArgumentParser(prog="seam_sweep")
    p.add_argument("--dirs", nargs="+")
    p.add_argument("--turns", nargs="+", metavar="SESSION:T1,T2")
    p.add_argument("--report-matches", default="p46", choices=sorted(REPORT_MATCHES))
    p.add_argument("--synthesis", choices=sorted(P47_SETS), default=None,
                   help="the Deep Research synthesis seam over a named payload set "
                        "(P4.7) instead of the Worker seam; needs --out")
    p.add_argument("--grade", metavar="DIR", default=None,
                   help="with --synthesis: grade both sides' saved draws in DIR; "
                        "no model call")
    p.add_argument("--without-fix", action="store_true")
    p.add_argument("--rev", default=None,
                   help=f"the before-side revision (Worker seam default {sr.PRE_P31_REV}; "
                        "the synthesis seam requires it explicitly)")
    p.add_argument("--out", default=None, help="write each draw to DIR/<dir>/")
    p.add_argument("--list", action="store_true", help="list the payloads; no model call")
    args = p.parse_args(argv)

    if args.synthesis:
        if args.grade:
            return synthesis_grade_dir(args.synthesis, Path(args.grade))
        if args.list:
            for pl in P47_SETS[args.synthesis]:
                print("  ", *pl)
            return 0
        if not args.out:
            p.error("--synthesis needs --out (keep it in the scratchpad)")
        if args.without_fix and not args.rev:
            p.error("--synthesis --without-fix needs an explicit --rev")
        return synthesis_sweep(args.synthesis, Path(args.out), args.without_fix,
                               args.rev or "HEAD")
    if not (args.dirs and args.turns):
        p.error("the Worker seam needs --dirs and --turns")
    args.rev = args.rev or sr.PRE_P31_REV

    from src.agent.tools import get_worker_tools

    payloads = select(args.dirs, _parse_turns(args.turns), REPORT_MATCHES[args.report_matches])
    print(f"seam_sweep: {len(payloads)} payload(s)  "
          f"{'WITHOUT fix (' + args.rev + ')' if args.without_fix else 'current code'}")
    if args.list:
        for pl in payloads:
            print("  ", *pl[:5])
        return 0
    tally = {"composed": 0, "searched": 0, "failing": 0, "corpus": 0}
    total = 0.0
    for d, sid, turn_no, k, n_tools, f in payloads:
        doc, turn = sr.load_turn(f, turn_no)
        cfg_turn = sr._cfg_for(doc, turn)
        cfg = asyncio.run(sr._provider_cfg(cfg_turn))
        if n_tools == 0:
            msgs = sr.worker_first_round_messages(doc, turn, k, args.without_fix, args.rev)
            tools = get_worker_tools(cfg_turn.get("_research_mode") or "legislation_only")
            content, calls, cost, _m = asyncio.run(sr.run_first_round(msgs, cfg, tools))
            shape = "FIRST"
        else:
            msgs = sr.worker_messages(doc, turn, k, args.without_fix, args.rev)
            content, cost, _m = asyncio.run(sr.run_seam(msgs, cfg))
            content, calls, shape = sr.strip_scope_blocks(content)[0], [], "COMPOSE"
        total += cost
        head = f"  {d:9} {sid} t{turn_no} d{k} tools={n_tools:<2} {shape:7} ${cost:.4f}"
        if calls:
            tally["searched"] += 1
            print(f"{head}  SEARCHED ({len(calls)} call(s))", flush=True)
            continue
        tally["composed"] += 1
        c = rr._scripted_counts(content)
        tally["failing"] += bool(rr._scripted_failing(c))
        tally["corpus"] += bool(c["corpus"])
        print(f"{head}  {len(content):,} chars  {sr._scripted_line(content)}", flush=True)
        if args.out:
            o = Path(args.out) / d
            o.mkdir(parents=True, exist_ok=True)
            (o / f"{sid}_t{turn_no}_d{k}{'_nofix' if args.without_fix else ''}.md").write_text(
                content, encoding="utf-8")
    print(f"\n  {len(payloads)} payload(s): {tally['composed']} composed a report, "
          f"{tally['searched']} chose to search first; of the reports, "
          f"{tally['failing']} carry a scripted negative and {tally['corpus']} a "
          f"'database does not contain'-style sentence.  total ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
