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


def _parse_turns(specs: list) -> dict:
    out = {}
    for s in specs:
        sid, _, ts = s.partition(":")
        out[sid] = {int(x) for x in ts.split(",") if x}
    return out


def main(argv=None) -> int:
    rr._utf8_stdout()
    p = argparse.ArgumentParser(prog="seam_sweep")
    p.add_argument("--dirs", nargs="+", required=True)
    p.add_argument("--turns", nargs="+", required=True, metavar="SESSION:T1,T2")
    p.add_argument("--report-matches", default="p46", choices=sorted(REPORT_MATCHES))
    p.add_argument("--without-fix", action="store_true")
    p.add_argument("--rev", default=sr.PRE_P31_REV)
    p.add_argument("--out", default=None, help="write each draw to DIR/<dir>/")
    p.add_argument("--list", action="store_true", help="list the payloads; no model call")
    args = p.parse_args(argv)

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
