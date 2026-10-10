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
    from tools.replay_report import _currency_asserted, _sentences, _without_footer, derivation_claims
except ImportError:  # run as a script from tools/
    from replay_report import (  # type: ignore
        _currency_asserted, _sentences, _without_footer, derivation_claims)

S95 = set("""
ssi/2018/275 ssi/2020/99 ssi/2020/351 ssi/2020/475 ssi/2021/73 ssi/2021/122 ssi/2021/170
ssi/2021/174 ssi/2021/178 ssi/2021/415 ssi/2021/416 ssi/2022/31 ssi/2022/41 ssi/2022/54
ssi/2022/129 ssi/2022/217 ssi/2022/302 ssi/2022/326 ssi/2022/336 ssi/2023/111 ssi/2023/258
ssi/2023/302 ssi/2023/346 ssi/2024/8 ssi/2024/105 ssi/2024/141 ssi/2024/166 ssi/2024/173
ssi/2024/311 ssi/2024/363 ssi/2025/3 ssi/2025/100 ssi/2025/195 ssi/2025/282 ssi/2025/336
ssi/2025/340 ssi/2026/170
""".split())
assert len(S95) == 37

# P3.33: what legislation.gov.uk records about the 37's revocation, hand-checked (Session 46:
# every removal effect on each instrument read by hand from its own affected feed; the
# type-wide feeds agree). Words-only removals ("word omitted" on ssi/2021/178) are not
# revocations and are in neither set.
S95_REVOKED_WHOLE = {"ssi/2022/217"}          # revoked by ssi/2024/311, with effect from 2025-03-21
S95_REVOKED_PART = set("""
ssi/2020/351 ssi/2021/73 ssi/2021/122 ssi/2021/174 ssi/2022/54 ssi/2023/302 ssi/2024/166 ssi/2025/3
""".split())
assert len(S95_REVOKED_PART) == 8 and not S95_REVOKED_PART & S95_REVOKED_WHOLE

MADE_UNDER_TURNS = {"6383": (1, 2, 3, 4), "6382": (1,), "6340": (1,)}
TOOL = "find_instruments_made_under"
_ID = re.compile(r"\b((?:ssi|uksi)/\d{4}/\d+)\b")
# "S.S.I. 2024/311", "SSI 2024/311": a named instrument without a link.
_CITE = re.compile(r"\bS\.?S\.?I\.?\s*(\d{4})/(\d+)\b")


def named_ids(answer: str) -> set:
    ids = set(_ID.findall(answer or ""))
    ids |= {f"ssi/{y}/{n}" for y, n in _CITE.findall(answer or "")}
    return ids


_REVOKE_WORD = re.compile(
    r"\b(?:revok\w*|revoc\w*|repeal\w*|ceas\w*\s+to\s+have\s+effect|omitted)\b", re.I)
_PART_WORD = re.compile(
    r"\b(?:in\s+part|partly|partially|part\s+of|some\s+(?:of\s+its\s+)?provisions|certain\s+provisions"
    r"|specific\s+provisions|provisions\s+within"
    r"|provisions?\s+(?:of|in)|regulations?\s+\d|reg\.\s*\d|paragraphs?\s+\d|schedule\s+\d|parts?\s+\d)\b",
    re.I)
_NEGATED = re.compile(r"\b(?:no|not|never|none)\b[^.;\n]{0,40}\b(?:revok|revoc|repeal)", re.I)
_STILL = re.compile(
    r"\b(?:is|are|remains?|remain|still|currently)\b[^.;\n]{0,30}"
    r"\b(?:in\s+force|in\s+effect|has\s+effect|have\s+effect|operative|in\s+operation)\b", re.I)


def revocation_claims(body: str) -> dict:
    """Which of the 37 a turn says are revoked, in whole or in part, and every sentence that
    reads as an in-force claim. A sentence's subject is what it names BEFORE "by": "SSI
    2022/217 was revoked by SSI 2024/311" says 2022/217 was revoked, not 2024/311 (both are
    among the 37). A detector, so every hit is listed for a hand read."""
    whole, part, in_force = set(), set(), []
    for s in _sentences(body):
        if _STILL.search(s) or _currency_asserted(s):
            in_force.append(s)
        # A title is not a claim: "(Consequential Amendment, Revocation and Saving Provision)
        # Regulations 2024". A link keeps its URL (the id) and loses its label.
        s = re.sub(r"\[[^\]]*\]\(([^)]*)\)", r" \1 ", s)
        s = re.sub(r"\([^()]*\bRevocations?\b[^()]*\)", " ", s)
        m = _REVOKE_WORD.search(s)
        if not m or _NEGATED.search(s):
            continue
        before, after = s[: m.start()], s[m.end():]
        cut = re.search(r"\bby\b", after)
        after_subject = after[: cut.start()] if cut else after
        if re.match(r"(?:revokes|revoking|repeals|repealing|omits)\b", m.group(0), re.I):
            ids = named_ids(after)            # "SSI 2024/311 revokes SSI 2022/217"
        elif named_ids(before) & S95:
            ids = named_ids(before)           # "SSI 2022/217 was revoked by ..." / a list line
        else:
            ids = named_ids(after_subject)    # "revocation recorded for SSI 2022/217 (by ...)"
        (part if _PART_WORD.search(s) else whole).update(ids & S95)
    whole -= part
    return {"said_whole": whole, "said_part": part, "in_force": in_force}


def revocation_grade(body: str, named: set) -> dict:
    c = revocation_claims(body)
    said = c["said_whole"] | c["said_part"]
    return {
        "whole_correct": sorted(c["said_whole"] & S95_REVOKED_WHOLE),
        # said revoked in whole, but the record holds only a partial removal or none
        "whole_wrong": sorted(c["said_whole"] - S95_REVOKED_WHOLE),
        "part_correct": sorted(c["said_part"] & (S95_REVOKED_PART | S95_REVOKED_WHOLE)),
        "part_wrong": sorted(c["said_part"] - S95_REVOKED_PART - S95_REVOKED_WHOLE),
        # a wholly revoked instrument the answer names without saying so
        "whole_missed": sorted((named & S95_REVOKED_WHOLE) - said),
        "part_missed": sorted((named & S95_REVOKED_PART) - said),
        "in_force": c["in_force"],
    }


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
            "revocation": revocation_grade(body, ids) if sid != "6340" else None,
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
            rv = t.get("revocation")
            if rv:
                print(f"        revocation (P3.33): whole {len(rv['whole_correct'])}/1 "
                      f"wrong {rv['whole_wrong']}  part {len(rv['part_correct'])} wrong {rv['part_wrong']}  "
                      f"missed whole {rv['whole_missed']} part {len(rv['part_missed'])}  "
                      f"in-force sentences {len(rv['in_force'])}")
                for s in rv["in_force"][:3]:
                    print(f"        ? {s[:200]}")
    print(f"total ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
