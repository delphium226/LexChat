"""P3.3 (B11): does the summariser add law that is not in the text it summarises?

**Why this exists (Session 32).** 6338's wrong interpretation Act did not come
from the Worker or the Manager: the summariser (the model that condenses a large
tool result, `summarise_prompt`) was handed the Worker's brief as its "research
question" and answered it from training, adding the Act to section-search
results that never mention it. The Worker then reported it as retrieved. The
source rule (`SUMMARY_SOURCE_RULE`) was built on these numbers.

Three commands, all over stored run files (`audit.delegations[].tools[]` carry
both `raw_result` and `final_result`):

    python -m tools.summary_probe count [--dir D ...]
        FREE. Summarised results whose summary matches a rubric session's
        `summary_adds` pattern while its raw text does not (a tool that
        retrieved one of the rubric's `self_ids` is excluded: its raw text has
        no title to match). By directory and session.

    python -m tools.summary_probe redraw --dir D --session S [--reps N]
        PAID (the summarisation model, about $0.01 a call). Re-summarises each
        slot `count` finds in D, with the product's prompt and with the same
        prompt minus the source rule, N draws a side; counts additions.

    python -m tools.summary_probe panel [--n 24] [--reps 2] [--seed 32]
        PAID. The no-loss check on OTHER sessions' results: provisions kept
        (numbers present in the raw text), characters, and "the text does not
        contain" statements, with and without the rule.

The patterns name a matter's law, so they live in the gitignored rubric
(`evidence/rubrics/p33.json`, key `summary_adds` per session); this code is
generic. Temperature 0 is not byte-deterministic: redraw a side on the same
day, and read the counts as a band, not a point.
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The gitignored evidence; PREPILOT_EVIDENCE points a git worktree at the main
# checkout's copy (Session 32's parallel batch).
EVIDENCE = Path(os.environ.get("PREPILOT_EVIDENCE")
                or ROOT / "docs" / "prepilot-fixes" / "evidence")
REPLAY = EVIDENCE / "replay"
RUBRIC = EVIDENCE / "rubrics" / "p33.json"
sys.path.insert(0, str(ROOT / "server_py"))

PROVISION = re.compile(
    r"\b(?:section|s\.|ss\.|regulation|reg\.|article|art\.|schedule|sch\.|paragraph|para\.)"
    r"\s*(\d+[A-Z]*(?:\(\w+\))*)", re.I)
NEGATIVE = re.compile(
    r"does not (?:contain|include|provide|state|define)|not (?:provided|included) in (?:the|this) text",
    re.I)
PANEL_DIRS = ("wave4_p37c", "wave4_p47b", "wave3_p313c", "wave4_p32_pre", "wave4_p46",
              "wave2_p27", "wave3_p38", "wave4_p45")


def _rubric(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tools(doc: dict):
    for t in doc.get("turns") or []:
        for dg in (t.get("audit") or {}).get("delegations") or []:
            for tl in dg.get("tools") or []:
                yield t, dg, tl


def _summarised(tl: dict) -> bool:
    raw, fin = tl.get("raw_result") or "", tl.get("final_result") or ""
    return bool(raw and fin and raw != fin)


def added_slots(doc: dict, adds: list, self_ids: list) -> list:
    """(turn, delegation, tool) where the summary names what the raw text does not."""
    pats = [re.compile(p, re.I) for p in adds]
    selfs = [re.compile(re.escape(s), re.I) for s in self_ids]
    out = []
    for t, dg, tl in _tools(doc):
        if not _summarised(tl):
            continue
        if any(s.search(json.dumps(tl.get("args") or {})) for s in selfs):
            continue
        raw, fin = tl["raw_result"], tl["final_result"]
        if any(p.search(fin) for p in pats) and not any(p.search(raw) for p in pats):
            out.append((t, dg, tl))
    return out


def cmd_count(args) -> int:
    rub = _rubric(Path(args.rubric))
    dirs = [Path(d) for d in args.dir] if args.dir else sorted(p for p in REPLAY.iterdir() if p.is_dir())
    total = hits = 0
    by = {}
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            total += sum(1 for _t, _d, tl in _tools(doc) if _summarised(tl))
            base = str((doc.get("script") or {}).get("base") or doc.get("session_id"))
            entry = rub.get(base) or {}
            if not entry.get("summary_adds"):
                continue
            n = len(added_slots(doc, entry["summary_adds"], entry.get("self_ids") or []))
            if n:
                hits += n
                by.setdefault(d.name, {}).setdefault(base, 0)
                by[d.name][base] += n
    print(f"summarised tool results: {total}; with a rubric addition absent from the raw text: {hits}")
    for d, s in by.items():
        print(f"  {d:<24} {s}")
    return 0


async def _key_and_model() -> tuple:
    import asyncpg  # noqa: PLC0415
    from tools.seam_replay import DEFAULT_DB_URL  # noqa: PLC0415
    conn = await asyncpg.connect(DEFAULT_DB_URL)
    try:
        row = await conn.fetchval("SELECT value FROM app_settings WHERE key='provider.openrouter'")
    finally:
        await conn.close()
    p = json.loads(row or "{}")
    if not p.get("api_key"):
        raise SystemExit("no OpenRouter api_key in app_settings")
    return p["api_key"], p.get("summarisation_model") or "google/gemini-3-flash-preview"


def _prompts():
    from src.agent import summarisation as s  # noqa: PLC0415

    def without_rule(text, query):
        return s.summarise_prompt(text, query).replace(f"{s.SUMMARY_SOURCE_RULE} ", "", 1)

    return s, {"with rule": s.summarise_prompt, "without rule": without_rule}


async def _draw(client, key, model, prompt) -> tuple:
    r = await client.post("https://openrouter.ai/api/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "temperature": 0, "stream": False,
                                "messages": [{"role": "user", "content": prompt}]}, timeout=300)
    j = r.json()
    return (j["choices"][0]["message"]["content"] or ""), float((j.get("usage") or {}).get("cost") or 0)


async def _redraw(args) -> int:
    import httpx  # noqa: PLC0415
    rub = _rubric(Path(args.rubric)).get(args.session) or {}
    if not rub.get("summary_adds"):
        print(f"  the rubric has no summary_adds for {args.session}")
        return 2
    pats = [re.compile(p, re.I) for p in rub["summary_adds"]]
    s, sides = _prompts()
    slots = []
    for f in sorted(Path(args.dir).glob(f"{args.session}_rep*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for t, dg, tl in added_slots(doc, rub["summary_adds"], rub.get("self_ids") or []):
            if len(tl["raw_result"]) <= s.SUMMARISE_CHUNK_CHARS:
                slots.append((f.stem, t.get("turn"), tl.get("name"), tl["raw_result"], dg.get("brief") or ""))
    key, model = await _key_and_model()
    print(f"{len(slots)} slot(s), {args.reps} draw(s) a side, model {model}")
    tally, cost = {k: [0, 0] for k in sides}, 0.0
    async with httpx.AsyncClient() as client:
        for stem, turn, name, raw, brief in slots:
            for side, fn in sides.items():
                res = await asyncio.gather(*[_draw(client, key, model, fn(raw, brief))
                                             for _ in range(args.reps)])
                n = sum(1 for out, _c in res if any(p.search(out) for p in pats))
                cost += sum(c for _o, c in res)
                tally[side][0] += n
                tally[side][1] += args.reps
                print(f"  {stem} t{turn} {name:<28} {side:<13} adds {n}/{args.reps}")
    print("TOTAL " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in tally.items()) + f"; cost ${cost:.3f}")
    return 0


def _provisions(s: str) -> set:
    return {m.group(1).lower() for m in PROVISION.finditer(s)}


async def _panel(args) -> int:
    import httpx  # noqa: PLC0415
    s, sides = _prompts()
    pool = []
    for d in PANEL_DIRS:
        for f in sorted((REPLAY / d).glob("*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if str(doc.get("session_id")) in (args.exclude or []):
                continue
            for t, dg, tl in _tools(doc):
                if (_summarised(tl) and len(tl["final_result"]) < len(tl["raw_result"])
                        and len(tl["raw_result"]) <= s.SUMMARISE_CHUNK_CHARS):
                    pool.append((d, doc.get("session_id"), t.get("turn"), tl.get("name"),
                                 tl["raw_result"], dg.get("brief") or ""))
    random.seed(args.seed)
    slots = random.sample(pool, min(args.n, len(pool)))
    key, model = await _key_and_model()
    print(f"{len(slots)} of {len(pool)} eligible results; {args.reps} draw(s) a side; seed {args.seed}")
    agg, cost = {k: [0, 0, 0] for k in sides}, 0.0
    async with httpx.AsyncClient() as client:
        for d, sid, turn, name, raw, brief in slots:
            raw_p = _provisions(raw)
            row = []
            for side, fn in sides.items():
                res = await asyncio.gather(*[_draw(client, key, model, fn(raw, brief))
                                             for _ in range(args.reps)])
                cost += sum(c for _o, c in res)
                texts = [o for o, _c in res]
                kept = sum(len(_provisions(x) & raw_p) for x in texts)
                chars = sum(len(x) for x in texts)
                neg = sum(len(NEGATIVE.findall(x)) for x in texts)
                agg[side][0] += kept
                agg[side][1] += chars
                agg[side][2] += neg
                row.append(f"{side}: prov {kept} chars {chars // args.reps} neg {neg}")
            print(f"  {d:<14} {sid} t{turn} {name:<28} " + " | ".join(row))
    print("TOTAL " + " | ".join(f"{k}: provisions {a}, chars {b}, 'does not contain' {c}"
                                for k, (a, b, c) in agg.items()) + f"; cost ${cost:.3f}")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="summary_probe")
    p.add_argument("--rubric", default=str(RUBRIC))
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count", help="free: summaries adding what the raw text lacks")
    c.add_argument("--dir", nargs="+", default=None)
    r = sub.add_parser("redraw", help="paid: re-summarise with and without the source rule")
    r.add_argument("--dir", required=True)
    r.add_argument("--session", required=True)
    r.add_argument("--reps", type=int, default=3)
    pn = sub.add_parser("panel", help="paid: the no-loss check on other sessions")
    pn.add_argument("--n", type=int, default=24)
    pn.add_argument("--reps", type=int, default=2)
    pn.add_argument("--seed", type=int, default=32)
    pn.add_argument("--exclude", nargs="*", default=["6338"])
    args = p.parse_args(argv)
    if args.cmd == "count":
        return cmd_count(args)
    return asyncio.run(_redraw(args) if args.cmd == "redraw" else _panel(args))


if __name__ == "__main__":
    raise SystemExit(main())
