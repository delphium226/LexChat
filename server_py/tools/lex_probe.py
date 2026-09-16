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
import re
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

    **Point lookups are a bad census instrument and misled this probe three
    times.** Twelve misses across `ssi/2026/{1..250}` read as "no 2026 SSIs at
    all", and a 20-point sample of UK SI 2026 returning nothing read as "nothing
    from 2026" — while `uksi/2026/772` was in the index the whole time and had
    been created a week earlier. A sparse sample of absences proves nothing about
    a corpus.

    **The third time, the warning above was already written and was ignored
    anyway, and the number reached a published row.** P5.3 recorded "UK SI 2026
    **~0%** held" off the 20-point sample. It is false in the direction that
    matters: `/legislation/search` surfaces **27 distinct `uksi/2026/*`**
    instruments and every one spot-checked resolves on lookup. The real rate is
    ~2% on 60 points — low single digits, not nothing. Retracted at P2.2
    (2026-09-15), where the wording that reached lawyers became "under 5%" and
    never "none", because a lawyer told "none" stops looking.

    So the cross-check is no longer advice in a docstring: it **runs**, below,
    every time this does. Samples are 60 points rather than 20 for the same
    reason.
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
    print("    (60-point samples since 2026-09-15 — see the cross-check below for why)")
    random.seed(7)
    for lt, year, hi, label in (("asp", 2025, 10, "ASP 2025"),
                                ("ssi", 2025, 390, "SSI 2025"),
                                ("ssi", 2026, 180, "SSI 2026"),
                                ("uksi", 2026, 860, "UK SI 2026"),
                                ("ukpga", 1962, 60, "UKPGA 1962")):
        picks = random.sample(range(1, hi + 1), min(60, hi))
        hits = 0
        for n in picks:
            r = httpx.post(f"{BASE}/legislation/lookup",
                           json={"legislation_type": lt, "year": year, "number": str(n)},
                           timeout=TIMEOUT)
            hits += r.status_code == 200
        print(f"    {label:12} {hits:2}/{len(picks)} held  ({100*hits//len(picks):3}%)")
    print("    NOTE: a 'not found' for 2026 secondary legislation is far more likely a")
    print("          coverage gap than an absence in law. That is P2.2's wording problem.")

    # ---------------------------------------------------------------------
    # The cross-check this script's own method warning demands — added
    # 2026-09-15 (P2.2) after the warning was ignored and the headline it
    # produced had to be retracted.
    #
    # P5.3 published "UK SI 2026 ~0% held" off a 20-point lookup sample. That
    # reads as "nothing made in 2026 is in the index", which is FALSE: search
    # surfaces dozens of held 2026 instruments. A 0/20 sample of a ~2% series
    # looks identical to an empty one, and only a second route can tell them
    # apart. The wording that reached the product says "under 5%", never
    # "none", because a lawyer told "none" stops looking.
    # ---------------------------------------------------------------------
    print()
    print("--- cross-check: does SEARCH find instruments the lookup census missed? ---")
    for lt, year in (("ssi", 2026), ("uksi", 2026)):
        found = set()
        for q in ("regulations", "order", "amendment", "scotland", "commencement"):
            r = httpx.post(f"{BASE}/legislation/search",
                           json={"query": f"{q} {year}", "limit": 50,
                                 "year_from": year, "include_text": False},
                           timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            d = r.json()
            for it in (d.get("results") if isinstance(d, dict) else d) or []:
                m = re.search(rf"/{lt}/{year}/(\d+)", it.get("uri", ""))
                if m:
                    found.add(int(m.group(1)))
        resolves = 0
        for n in sorted(found)[:12]:
            r = httpx.post(f"{BASE}/legislation/lookup",
                           json={"legislation_type": lt, "year": year, "number": str(n)},
                           timeout=TIMEOUT)
            resolves += r.status_code == 200
        probe = sorted(found)[:12]
        print(f"    {lt}/{year}: search surfaced {len(found):3} distinct instrument(s); "
              f"{resolves}/{len(probe)} spot-checked resolve on lookup")
    print("    NOTE: a sparse sample of ABSENCES proves nothing about a corpus. If these two")
    print("          routes disagree, the sample is the instrument — not the index.")

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


def enabling(sample: int = 25) -> int:
    """P2.3: where, if anywhere, is an instrument's ENABLING POWER retrievable?

    **The handover into P2.3 said this route did not exist, and it was half
    wrong in a way that decides the row.** The claim was that
    `/legislation/text` does not carry the preamble, checked on `ssi/2020/295`,
    whose `full_text` opens at "Section 1) Citation and commencement" with no
    recital anywhere. True of `full_text`, and true of that instrument. But the
    recital arrives in **`legislation.description`**, and `get_legislation_text`
    returns the response unslimmed — so the permitted branch of P2.3's rule is
    live today and needs nothing from P3.6.

    What decides how much it is worth is the *distribution*, not the existence:

        uksi pre-1990     18/25 (72%)      sampled 2026-09-16
        uksi 1990-2009     0/25
        uksi 2010+         0/25
        ssi  1990-2009     0/13   <- the corpus these lawyers actually work in
        ssi  2010+         0/15

    So for Scottish instruments the rule is a total prohibition and for modern
    UK SIs very nearly one. Modern descriptions say what an instrument
    *commences*, not what it was *made under*.

    Same method warning as `coverage()`: these are small samples of a
    heterogeneous corpus. Quote a bound, not a point estimate, and re-run this
    before quoting anything at all.
    """
    import random

    RECITAL = re.compile(
        r"in exercise of (?:the |his |her |their |its )?powers?"
        r"|powers? (?:in that behalf )?conferred (?:on|upon|by)"
        r"|by virtue of (?:the )?powers?"
        r"|makes? the following (?:Regulations|Order|Rules|Scheme)"
        r"|has determined under section", re.I)

    def _search(q, **kw):
        body = {"query": q, "limit": 50, "include_text": False}
        body.update(kw)
        r = httpx.post(f"{BASE}/legislation/search", json=body, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        d = r.json()
        return (d.get("results") if isinstance(d, dict) else d) or []

    buckets = collections.defaultdict(set)
    windows = ((None, None), (1950, 1989), (1990, 2009))
    for q in ("regulations", "order", "rules", "amendment", "commencement",
              "scotland", "education", "social security"):
        for yf, yt in windows:
            kw = {"year_from": yf, "year_to": yt} if yf else {}
            for it in _search(q, **kw):
                m = re.search(r"/((?:ssi|uksi|ssr|uksro))/(\d{4})/(\d+)",
                              it.get("uri", ""))
                if not m:
                    continue
                series, year = m.group(1), int(m.group(2))
                era = ("pre-1990" if year < 1990
                       else "1990-2009" if year < 2010 else "2010+")
                buckets[(series, era)].add(f"{series}/{year}/{m.group(3)}")

    random.seed(11)
    print("--- is the enabling-power recital retrievable, and for what? ---")
    print(f"{'series/era':20} {'n':>3} {'held':>5} {'has description':>16} "
          f"{'RECITAL':>8}")
    print("-" * 58)
    examples, only_full_text = [], 0
    tot = {"n": 0, "held": 0, "desc": 0, "rec": 0}
    for key in sorted(buckets):
        picks = random.sample(sorted(buckets[key]), min(sample, len(buckets[key])))
        held = desc = rec = 0
        for lid in picks:
            r = httpx.post(f"{BASE}/legislation/text",
                           json={"legislation_id": lid}, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            d = r.json()
            item = d[0] if isinstance(d, list) and d else d
            held += 1
            descr = str((item.get("legislation") or {}).get("description") or "")
            ft = str(item.get("full_text") or "")
            if descr:
                desc += 1
            if RECITAL.search(descr):
                rec += 1
                if len(examples) < 5:
                    examples.append((lid, descr[:190]))
            elif RECITAL.search(ft[:1500]):
                only_full_text += 1
        tot["n"] += len(picks)
        tot["held"] += held
        tot["desc"] += desc
        tot["rec"] += rec
        print(f"{key[0] + '/' + key[1]:20} {len(picks):>3} {held:>5} {desc:>16} {rec:>8}")
    print("-" * 58)
    print(f"{'TOTAL':20} {tot['n']:>3} {tot['held']:>5} {tot['desc']:>16} {tot['rec']:>8}")
    print(f"  recital present in full_text but NOT description: {only_full_text}")
    print("  NOTE: the recital is in `legislation.description`, NOT `full_text` —")
    print("        checking full_text alone says the route does not exist.")
    for lid, d in examples:
        print(f"    * {lid}: {d!r}")
    return 0



# The instruments the P3.5 acceptance sessions asked about, and the ONLY reason
# this mode exists: `replay_report commencements` grades the *before* column,
# where no change-record call was made and there is therefore nothing in the run
# file to grade against. That column needs an external ground truth, and a
# constant nobody can re-derive is the thing SESSION_LOG keeps warning about.
# So the constant lives in `replay_report.COMMENCEMENT_TRUTH` and this command
# re-prints it from the live API.
ACCEPTANCE_ACTS = [
    ("6409", "asp/2025/2", "Social Security (Amendment) (Scotland) Act 2025"),
    ("6410", "asp/2025/9", "Care Reform (Scotland) Act 2025"),
    ("6382/6383", "asp/2018/9", "Social Security (Scotland) Act 2018"),
]


def commencement() -> int:
    """P3.5: what the change record actually holds for the acceptance sessions.

    Both sessions were told *"No commencement regulations have been made yet"*.
    They were wrong, and this prints by how much.

    It also prints the two numbers that decide the tool's shape and that the
    handover into P3.5 did not have: how many rows collapse as **http/https
    duplicates of one relation**, and how many relations are the Act commencing
    **its own** provisions rather than a regulation doing it.
    """
    print("P3.5 ground truth — /amendment/search, search_amended=True")
    print()
    for session, lid, title in ACCEPTANCE_ACTS:
        try:
            rows = amendments(lid, True, size=20000)
        except Exception as e:
            print(f"  {lid}: {type(e).__name__} {e}")
            continue
        seen, uniq = set(), []
        for r in rows:
            k = (r.get("changed_legislation"), r.get("changed_provision"),
                 r.get("affecting_legislation"), r.get("affecting_provision"),
                 r.get("type_of_effect"))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        cif = [r for r in uniq if r.get("type_of_effect") == "coming into force"]
        selfref = [r for r in cif if r.get("affecting_legislation") == lid]
        byother = [r for r in cif if r.get("affecting_legislation") != lid]
        by = collections.Counter(r.get("affecting_legislation") for r in byother)
        provs = sorted({r.get("changed_provision") for r in byother if r.get("changed_provision")})
        print(f"  session {session}  {lid}  {title}")
        print(f"    {len(rows)} rows -> {len(uniq)} distinct relations "
              f"({len(rows) - len(uniq)} http/https duplicates of the same relation)")
        print(f"    coming into force: {len(cif)}  "
              f"(self-referential {len(selfref)}, by another instrument {len(byother)})")
        for inst, n in by.most_common():
            print(f"      {n:>4} provision(s) commenced by {inst}")
        print(f"    provisions commenced by another instrument: "
              f"{', '.join(provs[:30])}{' ...' if len(provs) > 30 else ''}")
        print(f"    COMMENCEMENT_TRUTH entry: "
              f'"{session}": ("{lid}", {sorted(by)!r}),')
        print()
    print("  Every `coming into force` relation above is invisible to "
          "`search_legislation`,")
    print("  `search_legislation_sections` and `get_legislation_text`. 6409 ran 41 "
          "searches")
    print("  for one of them and halted at the step cap with nothing.")

    print()
    print("--- the two numbers that shape the tool, measured rather than asserted ---")
    _duplicate_rate()
    _size_distribution()
    return 0


def _duplicate_rate() -> None:
    """How much of the feed is the same relation twice.

    The API emits each relation under BOTH URL schemes and its own `id` embeds
    the scheme, so the twins are not equal by id and a dedupe keyed on it removes
    nothing. This is the number that turns "15 commencements by ssi/2025/119"
    into 8, and it is concentrated rather than uniform.
    """
    sample = ("asp/2025/2", "asp/2018/9", "ukpga/1998/46", "asp/2014/18",
              "ukpga/2010/15", "ssi/2020/295", "asp/2000/1", "ukpga/1981/67")
    tot = dedup = 0
    print("  http/https duplicate rows (dedupe key is scheme-free):")
    for lid in sample:
        for direction in (True, False):
            try:
                rows = amendments(lid, direction, size=20000)
            except Exception as e:
                print(f"    ! {lid} {direction}: {type(e).__name__}")
                continue
            keys = {(r.get("changed_legislation"), r.get("changed_provision"),
                     r.get("affecting_legislation"), r.get("affecting_provision"),
                     r.get("type_of_effect")) for r in rows}
            tot += len(rows)
            dedup += len(keys)
            if direction:
                print(f"    {lid:14} {len(rows):>5} rows -> {len(keys):>5} relations "
                      f"({len(rows) - len(keys):>5} duplicates)")
    pct = 100 * (tot - dedup) / max(tot, 1)
    print(f"    TOTAL (both directions) {tot} rows -> {dedup} relations = "
          f"{pct:.0f}% duplicates")


def _size_distribution() -> None:
    """How often `size` binds, over the instruments a lawyer actually asked about.

    `size` truncates silently and the response carries no count field, so the
    only way to know a result is complete is to ask for more than it holds. This
    is what decides `_AMENDMENT_FETCH_SIZE` and its escalation, so it is measured
    against the real distribution rather than a guess — the legislation_ids the
    replay corpus touched, read out of the gitignored run files.
    """
    import statistics
    from pathlib import Path

    base = (Path(__file__).resolve().parents[2]
            / "docs" / "prepilot-fixes" / "evidence" / "replay")
    lids = set()
    for run in base.glob("*/*.json"):
        try:
            doc = json.loads(run.read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in doc.get("turns", []):
            for dg in (t.get("audit") or {}).get("delegations", []):
                for tl in dg.get("tools", []):
                    lid = str((tl.get("args") or {}).get("legislation_id") or "").strip()
                    if lid:
                        lids.add(lid)
    if not lids:
        print("  size distribution: no replay run files present — skipped")
        return
    cap = 2000
    counts = []
    bound = []
    for lid in sorted(lids):
        try:
            n = len(amendments(lid, True, size=cap))
        except Exception:
            continue
        counts.append(n)
        if n >= cap:
            bound.append(lid)
    counts.sort()
    print(f"  relation rows over the {len(counts)} legislation_ids the replay "
          f"corpus touched:")
    print(f"    zero relations {sum(1 for c in counts if c == 0)}   "
          f"median {statistics.median(counts):.0f}   "
          f"p90 {counts[int(0.9 * len(counts)) - 1]}   max {max(counts)}")
    print(f"    cap-bound at size={cap}: {len(bound)} "
          f"({100 * len(bound) / max(len(counts), 1):.1f}%) -> {', '.join(bound)}")
    for lid in bound:
        try:
            print(f"      {lid:16} completes at 20000 with "
                  f"{len(amendments(lid, True, size=20000))} rows")
        except Exception:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lex_probe")
    ap.add_argument("--surface", action="store_true", help="endpoint list only")
    ap.add_argument("--coverage", action="store_true",
                    help="P5.3: corpus size, freshness and per-series coverage")
    ap.add_argument("--enabling", action="store_true",
                    help="P2.3: where an instrument's enabling power is retrievable")
    ap.add_argument("--commencement", action="store_true",
                    help="P3.5: the change record for the acceptance sessions' Acts")
    args = ap.parse_args(argv)
    if args.coverage:
        return coverage()
    if args.enabling:
        return enabling()
    if args.commencement:
        return commencement()

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
