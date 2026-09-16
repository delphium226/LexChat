#!/usr/bin/env python
"""Where the pre-pilot fix plan actually stands (FIX_PLAN ledger, weighted).

    python -m tools.plan_status

**Why this is a command and not a paragraph.** Session 6 set the rule that a
number with no command behind it cannot be checked by the next session, and a
progress summary is the number most likely to be quoted and least likely to be
re-derived — it goes stale the moment a row is ticked. Everything here is read
live from `FIX_PLAN.md` and `evidence/classification.json`; nothing is typed in.

**Rows are not the useful denominator, and that is the point of the third
table.** 33 rows is an implementation count. What a reader wants is how much of
the *pre-pilot failure* is addressed, so the buckets are joined to the frozen
per-session classification and weighted by the sessions each one was the primary
diagnosis for. The two numbers diverge sharply — a third of the rows can close
half the failing sessions, or none of them.

Three things it deliberately does NOT do:

* it does not judge whether a `[x]` is *really* done — the ledger is the record,
  and a row is only tickable once its acceptance passed (FIX_PLAN "Verification
  protocol");
* it does not count Wave 5 toward completion, because those rows are external
  with unknown lead time and the merge policy says they must not hold the push
  hostage;
* it does not read the replay directories, so it is free and works on a clone
  with no evidence present.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes"
FIX_PLAN = DOCS / "FIX_PLAN.md"
CLASSIFICATION = DOCS / "evidence" / "classification.json"

_WAVE = re.compile(r"^### (Wave \d[^\n]*)")
# A ledger row: status box, id, then the bolded title. The title is taken only
# as far as the first bold run — the rest of the cell is the row's whole history
# and runs to thousands of characters.
_ROW = re.compile(r"^\| `\[(.)\]` \| \*\*(P[\d.]+)\*\* \| \*\*([^*]+)\*\*")
# The bucket -> rows table at the foot of the plan.
_BUCKET = re.compile(r"^\| (B\d+)([^|]*)\| ([^|]+)\|")

_MARK = {"x": "done", " ": "open", "~": "wip", "-": "dropped"}


def _rows() -> list:
    wave, out = None, []
    for line in FIX_PLAN.read_text(encoding="utf-8").split("\n"):
        m = _WAVE.match(line)
        if m:
            wave = m.group(1).replace("—", "-")
            continue
        m = _ROW.match(line)
        if m:
            out.append((wave, _MARK.get(m.group(1), m.group(1)),
                        m.group(2), m.group(3).strip()))
    return out


def _buckets() -> dict:
    """bucket id -> (label, [row ids it depends on])."""
    out = {}
    for line in FIX_PLAN.read_text(encoding="utf-8").split("\n"):
        m = _BUCKET.match(line)
        if not m:
            continue
        rows = re.findall(r"P\d+\.\d+", m.group(3))
        if rows:
            out[m.group(1)] = (m.group(2).strip(), rows)
    return out


def main(argv=None) -> int:
    rows = _rows()
    if not rows:
        print(f"No ledger rows found in {FIX_PLAN}")
        return 1
    status = {rid: st for _, st, rid, _ in rows}

    print(f"Pre-pilot fix plan — {FIX_PLAN}")
    print()

    # --- by wave ---------------------------------------------------------
    print("  BY WAVE")
    waves = {}
    for wave, st, rid, _title in rows:
        waves.setdefault(wave, Counter())[st] += 1
    for wave, c in waves.items():
        total = sum(c.values())
        bits = ", ".join(f"{n} {s}" for s, n in sorted(c.items()))
        print(f"    {c['done']:>2} of {total:<2}  {wave[:58]:60} ({bits})")
    overall = Counter(st for _, st, _, _ in rows)
    print(f"    {overall['done']} of {len(rows)} rows done "
          f"({100 * overall['done'] / len(rows):.0f}%), "
          f"{overall['wip']} in progress, {overall['open']} open")

    # --- by bucket -------------------------------------------------------
    buckets = _buckets()
    print()
    print("  BY BUCKET (a bucket closes only when EVERY row it depends on is done)")
    closed, partial, openb = set(), set(), set()
    for b, (label, deps) in buckets.items():
        states = [status.get(d, "?") for d in deps]
        done = [d for d, s in zip(deps, states) if s == "done"]
        if len(done) == len(deps):
            closed.add(b)
            mark = "CLOSED "
        elif done:
            partial.add(b)
            mark = "partial"
        else:
            openb.add(b)
            mark = "open   "
        outstanding = [d for d, s in zip(deps, states) if s != "done"]
        tail = ("  waiting on " + ", ".join(outstanding)) if outstanding else ""
        print(f"    {mark} {b:4} {label[:34]:36}{tail}")
    print(f"    {len(closed)} of {len(buckets)} buckets closed, "
          f"{len(partial)} partial, {len(openb)} open")

    # --- weighted by sessions -------------------------------------------
    if not CLASSIFICATION.exists():
        print("\n  (classification.json absent — session weighting skipped)")
        return 0
    cls = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    verdicts = Counter(s.get("verdict") for s in cls.values())
    primary = Counter(s.get("primary") for s in cls.values() if s.get("primary"))

    print()
    print(f"  WEIGHTED BY SESSION ({len(cls)} pre-pilot sessions: "
          + ", ".join(f"{n} {v}" for v, n in sorted(verdicts.items())) + ")")
    print("  — how many sessions each bucket was the PRIMARY diagnosis for.")
    tally = Counter()
    for b, n in primary.most_common():
        state = ("closed" if b in closed else
                 "partial" if b in partial else "open")
        tally[state] += n
        label = buckets.get(b, ("", []))[0][:30]
        print(f"    {state:8} {b:4} {n:>3} session(s)   {label}")
    tot = sum(tally.values())
    print(f"    primary bucket CLOSED for {tally['closed']} of {tot} classified "
          f"sessions; partial {tally['partial']}; open {tally['open']}")
    print()
    print("  A session is counted once, against its primary bucket only. Secondary")
    print("  buckets are not weighted here — several sessions carry three or four,")
    print("  so a sum over them would double-count the same session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
