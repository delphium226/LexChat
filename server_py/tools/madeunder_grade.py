#!/usr/bin/env python
"""Grade a replay directory for FIX_PLAN P3.31 (the made-under record).

For each made-under turn of 6383 (turns 1-4), 6382 (turn 1) and 6340 (turn 1):

* **tool** - did a Worker call `find_instruments_made_under`;
* **found / 37** - how many of the 37 SSIs made under s.95 of the Social
  Security (Scotland) Act 2018 the answer names (by id in a link or in text);
* **other** - SSIs named that are NOT among the 37. Not every one is an error
  (an answer may name an instrument for another reason), so each is listed for
  a hand read;
* **unverified** - sentences P2.3's grader (`replay_report.derivation_claims`)
  reads as a made-under claim about an instrument outside the 37, after the
  footer is stripped. For 6340, every asserted claim naming s.117: the record
  holds no instrument made under s.117 of the 1962 Act.

The 37 come from the harvest (P3.31 Step 2, hand-read, recall-audited); they
are listed here, not loaded, so the grader does not depend on the store it is
grading.

    python -m tools.madeunder_grade ../docs/prepilot-fixes/evidence/replay/wave4_p331
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from tools.replay_report import _without_footer, derivation_claims
except ImportError:  # run as a script from tools/
    from replay_report import _without_footer, derivation_claims  # type: ignore

S95 = set("""
ssi/2018/275 ssi/2020/99 ssi/2020/351 ssi/2020/475 ssi/2021/73 ssi/2021/122 ssi/2021/170
ssi/2021/174 ssi/2021/178 ssi/2021/415 ssi/2021/416 ssi/2022/31 ssi/2022/41 ssi/2022/54
ssi/2022/129 ssi/2022/217 ssi/2022/302 ssi/2022/326 ssi/2022/336 ssi/2023/111 ssi/2023/258
ssi/2023/302 ssi/2023/346 ssi/2024/8 ssi/2024/105 ssi/2024/141 ssi/2024/166 ssi/2024/173
ssi/2024/311 ssi/2024/363 ssi/2025/3 ssi/2025/100 ssi/2025/195 ssi/2025/282 ssi/2025/336
ssi/2025/340 ssi/2026/170
""".split())
assert len(S95) == 37

MADE_UNDER_TURNS = {"6383": (1, 2, 3, 4), "6382": (1,), "6340": (1,)}
TOOL = "find_instruments_made_under"
_ID = re.compile(r"\b((?:ssi|uksi)/\d{4}/\d+)\b")
# "S.S.I. 2024/311", "SSI 2024/311": a named instrument without a link.
_CITE = re.compile(r"\bS\.?S\.?I\.?\s*(\d{4})/(\d+)\b")


def named_ids(answer: str) -> set:
    ids = set(_ID.findall(answer or ""))
    ids |= {f"ssi/{y}/{n}" for y, n in _CITE.findall(answer or "")}
    return ids


def tools_called(turn: dict) -> list:
    return [t.get("name") for d in (turn.get("audit") or {}).get("delegations", [])
            for t in d.get("tools", [])]


def grade(path: Path) -> dict:
    run = json.loads(path.read_text(encoding="utf-8"))
    sid = str(run.get("session_id"))
    out = []
    for t in run.get("turns", []):
        if t.get("turn") not in MADE_UNDER_TURNS.get(sid, ()):
            continue
        body = _without_footer(t.get("answer") or "")
        ids = named_ids(body)
        claims = derivation_claims(body)[0]
        if sid == "6340":
            # The failure is an instrument said to be made under s.117 of the
            # 1962 Act; a claim about another Act's power is not this one.
            unverified = [c for c in claims if re.search(r"\b117\b", c)]
        else:
            unverified = [c for c in claims
                          if (named_ids(c) - S95) and not (named_ids(c) & S95)]
        out.append({
            "turn": t.get("turn"), "tool": TOOL in tools_called(t),
            "found": len(ids & S95), "other": sorted(i for i in ids - S95 if i.startswith("ssi/")),
            "unverified": unverified, "chars": len(body), "error": t.get("error"),
        })
    return {"file": path.name, "session": sid, "cost": run.get("total_cost_usd"),
            "model_mismatch": run.get("model_mismatch"), "turns": out}


def main(argv=None) -> int:
    d = Path((argv or sys.argv[1:])[0])
    total = 0.0
    for f in sorted(d.glob("*_rep*.json")):
        g = grade(f)
        total += g["cost"] or 0
        print(f"== {g['file']}  ${g['cost'] or 0:.2f}"
              + ("  MODEL MISMATCH" if g["model_mismatch"] else ""))
        for t in g["turns"]:
            print(f"   t{t['turn']}: tool={'Y' if t['tool'] else 'n'}  found {t['found']}/37  "
                  f"other {len(t['other'])} {t['other'][:6]}  unverified {len(t['unverified'])}"
                  + (f"  ERROR {t['error']}" if t["error"] else ""))
            for c in t["unverified"][:3]:
                print(f"        ! {c[:200]}")
    print(f"total ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
