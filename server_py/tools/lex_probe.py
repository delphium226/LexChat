#!/usr/bin/env python
"""Probe the LEX API's surface and relationship data (FIX_PLAN P5.1).

P5.1 was written as a question for the LEX team: *does the API expose
enabling-power, amendment, commencement or revocation relations in any form?*
Most of it turned out to be answerable from here, because **the API publishes an
OpenAPI spec at `/openapi.json`** and we had never looked at it. It documents
**13 endpoints; we call 3.**

This script re-runs the probe so a later session can verify the answer rather
than trust this one — which is the standing lesson of this work, where the
measuring instrument has been wrong more often than the product.

    python -m tools.lex_probe            # the whole probe
    python -m tools.lex_probe --surface  # just the endpoint list

**No auth.** `executor.py` sends no headers to LEX and neither does this. Every
call here is a read.

What the probe establishes, and the two traps it exists to stop being
re-discovered:

* `/legislation/text` returns `{legislation, full_text}` — **not** `text`. There
  IS a top-level `text` key on the nested `legislation` object and it is empty
  for everything, including Acts that are fully held. Reading it as "the text"
  says every instrument in the corpus is a stub.
* An instrument genuinely without text is **not** silently empty: `full_text` is
  the literal sentence `"No text content available for this legislation."`, and
  `/legislation/section/lookup` returns 404 where a held instrument returns 200.
  P5.1's drafted addendum claimed stub and absent were indistinguishable. They
  are not.
"""

import argparse
import collections
import json
import sys

import httpx

BASE = "https://lex.lab.i.ai.gov.uk"
TIMEOUT = 90

# Instruments chosen because the plan already makes claims about them.
ACT = "asp/2018/9"            # Social Security (Scotland) Act 2018 — 6382/6383
COMMENCEMENT_SSI = "ssi/2020/295"
STUB = "ssi/2025/119"         # P5.3 records this as "record exists, text empty"
ABSENT = ("ukpga", 1962, "47")  # Education (Scotland) Act 1962 — P5.3 records a 404


def surface() -> list:
    spec = httpx.get(f"{BASE}/openapi.json", timeout=TIMEOUT).json()
    rows = []
    for path, ops in sorted(spec.get("paths", {}).items()):
        for method, op in ops.items():
            if method.startswith("x-"):
                continue
            rows.append((method.upper(), path, op.get("summary", "")))
    return rows


def amendments(legislation_id: str, search_amended: bool, size: int = 200) -> list:
    """`search_amended=True` → amendments made TO it; False → amendments it MAKES.

    That flag is the direction of the relation, which is what P5.1 question 2
    asks whether is recoverable. It is.
    """
    r = httpx.post(
        f"{BASE}/amendment/search",
        json={"legislation_id": legislation_id, "search_amended": search_amended,
              "size": size},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, list) else (d.get("results") or [])


def coverage() -> int:
    """P5.3: how much of each series is actually held, and how fresh is it?

    **Point lookups are a bad census instrument and misled this probe twice** —
    twelve misses across `ssi/2026/{1..250}` read as "no 2026 SSIs at all", and a
    20-point sample of UK SI 2026 returning nothing read as "nothing from 2026",
    while `uksi/2026/772` was in the index and had been created a week earlier.
    In a series with ~20% coverage, a sparse sample of absences proves nothing.
    Cross-check against `/legislation/search` before concluding anything.
    """
    import random

    stats = httpx.get(f"{BASE}/api/stats", timeout=TIMEOUT).json()
    print("GET /api/stats")
    for k, v in stats.items():
        print(f"    {k:22} {v}")

    health = httpx.get(f"{BASE}/healthcheck", timeout=TIMEOUT).json()
    print()
    print("GET /healthcheck — collections in the vector store")
    for name, det in (health.get("collection_details") or {}).items():
        flag = "  <- no endpoint exposes this (see P5.2)" if "caselaw" in name else ""
        print(f"    {name:22} {det.get('points'):>10,} points{flag}")

    print()
    print("--- held / absent by series (lookup is definitive) ---")
    random.seed(7)
    for lt, year, hi, label in (("asp", 2025, 10, "ASP 2025"),
                                ("ssi", 2025, 390, "SSI 2025"),
                                ("ssi", 2026, 170, "SSI 2026"),
                                ("uksi", 2026, 800, "UK SI 2026"),
                                ("ukpga", 1962, 60, "UKPGA 1962")):
        picks = random.sample(range(1, hi + 1), min(20, hi))
        hits = 0
        for n in picks:
            r = httpx.post(f"{BASE}/legislation/lookup",
                           json={"legislation_type": lt, "year": year, "number": str(n)},
                           timeout=TIMEOUT)
            hits += r.status_code == 200
        print(f"    {label:12} {hits:2}/{len(picks)} held  ({100*hits//len(picks):3}%)")
    print("    NOTE: a 'not found' for 2026 secondary legislation is far more likely a")
    print("          coverage gap than an absence in law. That is P2.2's wording problem.")

    print()
    print("--- freshness: newest `created_at` seen in a search sample ---")
    newest = []
    for q in ("regulations", "act", "order", "amendment", "scotland"):
        r = httpx.post(f"{BASE}/legislation/search",
                       json={"query": q, "limit": 50, "include_text": False}, timeout=TIMEOUT)
        if r.status_code != 200:
            continue
        d = r.json()
        for it in (d.get("results") if isinstance(d, dict) else d) or []:
            if it.get("created_at"):
                newest.append((it["created_at"], str(it.get("title") or "")[:44]))
    newest.sort(reverse=True)
    for ca, title in newest[:5]:
        print(f"    {ca[:19]}  {title}")
    print("    NOTE: ingestion runs land ~02:00-02:30 UTC daily. Staleness is NOT the problem;")
    print("          per-instrument gaps are.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lex_probe")
    ap.add_argument("--surface", action="store_true", help="endpoint list only")
    ap.add_argument("--coverage", action="store_true",
                    help="P5.3: corpus size, freshness and per-series coverage")
    args = ap.parse_args(argv)
    if args.coverage:
        return coverage()

    print(f"LEX API surface ({BASE}/openapi.json)\n")
    called = {"/legislation/search", "/legislation/section/search", "/legislation/text"}
    for method, path, summary in surface():
        mark = "  <- we call this" if path in called else ""
        print(f"  {method:5} {path:46} {summary[:52]}{mark}")
    if args.surface:
        return 0

    print("\n--- relations: type_of_effect vocabulary ---")
    counter = collections.Counter()
    total = 0
    for lid in (ACT, "asp/2014/18", "ukpga/1981/67", "asp/2000/1", "asp/2002/3"):
        for direction in (True, False):
            try:
                rows = amendments(lid, direction)
            except Exception as e:  # a probe must not die on one instrument
                print(f"  ! {lid} search_amended={direction}: {type(e).__name__}")
                continue
            total += len(rows)
            counter.update(r.get("type_of_effect") for r in rows)
    print(f"  {total} rows, {len(counter)} distinct values. The ones P5.1 asks about:")
    for want in ("coming into force", "Commencement Order", "repealed", "revoked",
                 "words repealed", "words revoked", "repealed in part"):
        if counter.get(want):
            print(f"    {counter[want]:5}  {want}")
    print(f"    {counter.get(None, 0):5}  (none) <- {100*counter.get(None,0)//max(total,1)}% "
          f"carry no effect type at all")

    print("\n--- one commencement row, in full ---")
    rows = [r for r in amendments(ACT, True) if r.get("type_of_effect") == "coming into force"]
    if rows:
        print(json.dumps(rows[0], indent=2))
        print("  NOTE: provision-level on both sides, with URLs — and NO DATE field.")

    print("\n--- stub vs absent vs held ---")
    for lid in (ACT, COMMENCEMENT_SSI, STUB):
        t = httpx.post(f"{BASE}/legislation/text", json={"legislation_id": lid},
                       timeout=TIMEOUT).json()
        item = t[0] if isinstance(t, list) and t else t
        ft = item.get("full_text") or ""
        s = httpx.post(f"{BASE}/legislation/section/lookup",
                       json={"legislation_id": lid, "limit": 1}, timeout=TIMEOUT)
        print(f"  {lid:14} full_text={len(ft):>7} chars   section/lookup={s.status_code}"
              f"   {'<- SENTINEL' if ft.startswith('No text content') else ''}")
    lt, ly, ln = ABSENT
    r = httpx.post(f"{BASE}/legislation/lookup",
                   json={"legislation_type": lt, "year": ly, "number": ln}, timeout=TIMEOUT)
    print(f"  {lt}/{ly}/{ln:<9} lookup={r.status_code} <- genuinely absent, not a stub")

    print("\n--- `description`, which _slim_search_results discards ---")
    d = httpx.post(f"{BASE}/legislation/lookup",
                   json={"legislation_type": "ssi", "year": 2020, "number": "295"},
                   timeout=TIMEOUT).json()
    item = d[0] if isinstance(d, list) and d else d
    print(f"  {item.get('title')}")
    print(f"  description: {item.get('description')}")
    print("  NOTE: states the relationship AND the date. We strip this field before")
    print("        the model ever sees it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
