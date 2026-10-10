#!/usr/bin/env python
"""Harvest legislation.gov.uk's affected feeds and attach revocation flags to the made-under
snapshot (FIX_PLAN P3.33).

**Why the type-wide feeds.** Every revocation of an instrument is an effect on it in
legislation.gov.uk's Changes to Legislation record. One feed per instrument would be 68,780 reads
(about 12.5 hours); the type-wide feeds hold the same effects in about 1,850 pages: the whole SSI
feed, and the UK SI feed of each affected year (which also carries Welsh SIs and NI Orders in
Council, filed as wsi/ and nisi/ with UK SI numbers). Session 46 checked them against the
per-instrument feeds of 177 sampled instruments: every effect present, flags equal 177 of 177.

**A crawl is accepted only when it is consistent** (`crawl`): every page read; the entries read
equal the feed's stated total on the first and the last page; and a fresh re-read of the top
after the crawl (a page size no page URL uses, so neither this tool's store nor legislation.gov.uk's
URL-keyed cache answers it) shows nothing modified since the EARLIEST generation stamp of any page
read, and the same total. legislation.gov.uk serves a recently generated URL from a cache (Session
46: pages came back in 30 ms, generated 50 minutes before), so the window starts at the oldest page,
not at the attempt. An effect that gains a Modified moves to the top; one added or deleted changes
the total; one changed in place in the tail does not move. Otherwise the scope is crawled again
with its query string reordered, at most 3 attempts.

**`sort=modified` is not a complete daily delta**, and this tool does not pretend it is: the feed
is ordered strictly by each effect's Modified attribute, but 22% of SSI effects (13% of UK SI 2005's)
carry none and sit in a tail ordered by instrument number, where a recent effect on an old
instrument is never near the top.

**Layout** (the same as Session 46's evidence harvest, so `--attach` reads either): `calls.jsonl`
(one line per call: n, url, status, bytes, elapsed_ms, at), `raw/<n>.xml.gz` (each body),
`state.json` (per scope: the attempt, its start, clean, and the checks), `progress.log`.

    python -m tools.revocation_harvest --harvest DIR [--scopes ssi,uksi:1987-2026] [--max-calls 2400]
    python -m tools.revocation_harvest --status DIR
    python -m tools.revocation_harvest --attach DIR SNAPSHOT_DIR --version V [--checked YYYY-MM-DD]

Read-only, paced (`--gap`, default 0.6 s), capped in code, with madeunder_probe's identifying
User-Agent; resumable (a page already saved is never read again).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from tools.madeunder_probe import USER_AGENT
    from tools.lgu_probe import LGU, _utf8_stdout
except ImportError:  # run as a script from tools/
    from madeunder_probe import USER_AGENT  # type: ignore
    from lgu_probe import LGU, _utf8_stdout  # type: ignore

from src.utils.revocation_record import (  # noqa: E402  the one rule, shared with the server
    flags_from_effects, merge_effects, parse_feed, timestamp,
)

MAX_ATTEMPTS = 3
BACKOFF = (2, 5, 15, 60)
DEFAULT_GAP_S = 0.6
TIMEOUT_S = 120.0


# --------------------------------------------------------------------------
# URLs
# --------------------------------------------------------------------------

def page_url(scope: str, attempt: int, page: int = 1) -> str:
    """One page. Each attempt orders the same two parameters differently, so a re-crawl is a
    fresh read (this tool's store and legislation.gov.uk's cache key on the whole URL)."""
    if attempt == 1:
        q = "results-count=500&sort=modified" + (f"&page={page}" if page > 1 else "")
    elif attempt == 2:
        q = "sort=modified&results-count=500" + (f"&page={page}" if page > 1 else "")
    else:
        q = f"page={page}&results-count=500&sort=modified"
    return f"{LGU}/changes/affected/{scope}/data.feed?{q}"


def check_url(scope: str, attempt: int) -> str:
    """The re-read of the top after an attempt: a page size no page URL uses (499, 498, 497)."""
    return f"{LGU}/changes/affected/{scope}/data.feed?sort=modified&results-count={500 - attempt}"


def scopes_from(spec: str) -> list:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part.startswith("uksi:"):
            a, _, b = part[5:].partition("-")
            out += [f"uksi/{y}" for y in range(int(a), int(b or a) + 1)]
        elif part:
            out.append(part)
    return out


# --------------------------------------------------------------------------
# the store: one call log, one body per call
# --------------------------------------------------------------------------

class Store:
    def __init__(self, root: Path, cap: int = 0, gap: float = DEFAULT_GAP_S, transport=None):
        self.root, self.cap, self.gap = root, cap, gap
        self.log, self.raw = root / "calls.jsonl", root / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self._last = os.path.getmtime(self.log) if self.log.exists() else 0.0
        self._key, self._count, self._ok = None, 0, {}
        self._transport = transport

    def _index(self):
        key = self.log.stat().st_size if self.log.exists() else -1
        if key != self._key:
            ok, count = {}, 0
            if self.log.exists():
                for line in self.log.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        r = json.loads(line)
                        count += 1
                        if r.get("status") == 200:
                            ok[r["url"]] = r["n"]
            self._key, self._count, self._ok = key, count, ok
        return self._count, self._ok

    def calls(self) -> int:
        return self._index()[0]

    def saved(self, url: str) -> Optional[bytes]:
        n = self._index()[1].get(url)
        if n is None:
            return None
        return gzip.decompress((self.raw / f"{n:05d}.xml.gz").read_bytes())

    def get(self, url: str, purpose: str = "") -> tuple:
        """(status, body): the saved body if any, else one paced, logged, capped read."""
        body = self.saved(url)
        if body is not None:
            return 200, body
        if not url.startswith(LGU + "/changes/affected/"):
            raise ValueError(f"refused: {url}")
        n = self.calls() + 1
        if n > self.cap:
            raise RuntimeError(f"call cap reached ({self.cap}); refusing {url}")
        wait = self.gap - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        rec = {"n": n, "method": "GET", "url": url, "purpose": purpose,
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            status, body = (self._transport or _http_get)(url)
            rec.update(status=status, bytes=len(body or b""))
        except Exception as e:  # noqa: BLE001 - a failed attempt still counts against the cap
            status, body = None, None
            rec.update(status=None, bytes=0, error=repr(e)[:200])
        rec["elapsed_ms"] = round((time.time() - t0) * 1000)
        self._last = time.time()
        (self.raw / f"{n:05d}.xml.gz").write_bytes(gzip.compress(body or b""))
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return status, body


_client = None


def _http_get(url: str) -> tuple:
    global _client
    if _client is None:
        import httpx
        _client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S,
                               follow_redirects=True)
    r = _client.get(url)
    return r.status_code, r.content


# --------------------------------------------------------------------------
# one scope
# --------------------------------------------------------------------------

def _read(store: Store, url: str, purpose: str, log) -> tuple:
    for i, wait in enumerate((0,) + BACKOFF):
        if wait:
            log(f"   retry {i} in {wait}s: {url[-90:]}")
            time.sleep(wait)
        status, body = store.get(url, purpose)
        if status == 200 and body:
            try:
                return parse_feed(body.decode("utf-8", "replace")), body
            except ValueError as e:
                log(f"   unparsed ({e}) {url[-90:]}")
        elif status in (400, 404, 410):
            log(f"   {status} (not retried) {url[-90:]}")
            return None, None
    return None, None


def crawl(store: Store, scope: str, attempt: int, start: datetime, log=print) -> dict:
    """One attempt at one scope, begun at `start` (kept across a resume)."""
    rec = {"attempt": attempt, "start": start.isoformat(timespec="seconds"), "clean": False}
    first, _ = _read(store, page_url(scope, attempt), f"harvest {scope}", log)
    if first is None:
        rec["reason"] = "page 1 unread"
        return rec
    gens = [timestamp(first["generated"])]
    pages, total = first["total_pages"] or 1, first["total"]
    n_read, last = len(first["effects"]), first
    for pg in range(2, pages + 1):
        p, _ = _read(store, page_url(scope, attempt, pg), f"harvest {scope}", log)
        if p is None:
            rec.update(reason=f"page {pg} unread", pages=pages, total=total)
            return rec
        gens.append(timestamp(p["generated"]))
        n_read += len(p["effects"])
        last = p
    chk, _ = _read(store, check_url(scope, attempt), f"check {scope}", log)
    known = [g for g in gens if g]
    window_from = min([start] + known)
    check_gen = timestamp(chk["generated"]) if chk else None
    moved = 0
    for e in (chk or {}).get("effects", []):
        times = [t for t in (timestamp(e.get("modified")), timestamp(e.get("updated"))) if t]
        if times and max(times) >= window_from:
            moved += 1
    rec.update(end=datetime.now(timezone.utc).isoformat(timespec="seconds"), pages=pages,
               total=total, last_page_total=last["total"], entries_read=n_read,
               check_total=chk["total"] if chk else None, moved_during_crawl=moved,
               window_from=window_from.isoformat(timespec="seconds"),
               pages_generated_before_start=sum(1 for g in known if g < start),
               check_generated=check_gen.isoformat(timespec="seconds") if check_gen else None)
    problems = []
    if len(known) != len(gens):
        problems.append(f"{len(gens) - len(known)} page(s) with no generation stamp")
    if chk is not None and (not check_gen or (known and check_gen < max(known))):
        problems.append("check read not generated after every page")
    if n_read != total:
        problems.append(f"read {n_read} != total {total}")
    if last["total"] != total:
        problems.append(f"total changed {total}->{last['total']}")
    if chk is None:
        problems.append("check read failed")
    elif chk["total"] != total:
        problems.append(f"check total {chk['total']} != {total}")
    if moved:
        problems.append(f"{moved} effect(s) modified during the crawl")
    rec["clean"], rec["problems"] = not problems, problems
    return rec


def harvest(root: Path, scopes: list, cap: int, gap: float, transport=None) -> dict:
    store = Store(root, cap, gap, transport)
    state_path, progress = root / "state.json", root / "progress.log"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    def log(msg):
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        with progress.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def save():
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        tmp.replace(state_path)

    log(f"harvest start; calls {store.calls()} of cap {cap}")
    for scope in scopes:
        prev = state.get(scope, {})
        if prev.get("clean"):
            continue
        if not prev:
            attempt, start = 1, None
        elif prev.get("reason"):
            attempt, start = prev["attempt"], prev["start"]
        else:
            attempt, start = prev["attempt"] + 1, None
        while attempt <= MAX_ATTEMPTS:
            t0 = datetime.fromisoformat(start) if start else datetime.now(timezone.utc)
            state[scope] = {"attempt": attempt, "start": t0.isoformat(timespec="seconds"),
                            "clean": False, "reason": "in progress"}
            save()
            log(f"{scope}: attempt {attempt}")
            try:
                rec = crawl(store, scope, attempt, t0, log)
            except RuntimeError as e:  # the call cap
                log(f"STOP: {e}")
                state[scope]["reason"] = str(e)
                save()
                return state
            state[scope] = rec
            save()
            log(f"{scope}: clean={rec['clean']} pages={rec.get('pages')} total={rec.get('total')} "
                f"{rec.get('problems') or rec.get('reason') or ''} (calls {store.calls()})")
            if rec["clean"] or rec.get("reason"):
                break
            attempt, start = attempt + 1, None
    log(f"harvest pass end; calls {store.calls()} of cap {cap}")
    return state


# --------------------------------------------------------------------------
# attach the flags to the made-under snapshot
# --------------------------------------------------------------------------

def scope_effects(store: Store, scope: str, rec: dict) -> dict:
    """{EffectId: effect} for one clean scope, from its saved pages."""
    out: dict = {}
    for pg in range(1, int(rec["pages"]) + 1):
        body = store.saved(page_url(scope, int(rec["attempt"]), pg))
        if body is None:
            raise RuntimeError(f"{scope}: page {pg} of attempt {rec['attempt']} is not saved")
        merge_effects(out, parse_feed(body.decode("utf-8", "replace"))["effects"])
    return out


def attach(root: Path, snapshot_dir: Path, version: str, checked: Optional[str] = None) -> dict:
    """Write each record instrument's flag into the snapshot and each clean scope's check date
    into the manifest. A scope that is not clean is left out: its instruments read as not
    checked, never as "no revocation recorded"."""
    store = Store(root)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    snap = snapshot_dir / "made_under_snapshot.jsonl.gz"
    records = [json.loads(line) for line in gzip.open(snap, "rt", encoding="utf-8") if line.strip()]
    ids = {r["id"] for r in records}
    effects: dict = {}
    days = {}
    for scope, rec in sorted(state.items()):
        if not rec.get("clean"):
            continue
        merge_effects(effects, scope_effects(store, scope, rec).values())
        days[scope] = checked or str(rec.get("end") or rec["start"])[:10]
    flags = flags_from_effects(effects, ids)
    from src.utils.revocation_record import scope_of
    n_flag = Counter()
    for r in records:
        r.pop("revocation", None)
        if scope_of(r["id"]) in days and r["id"] in flags:
            r["revocation"] = flags[r["id"]]
            n_flag[flags[r["id"]]["state"]] += 1
    with gzip.open(snap, "wt", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    mpath = snapshot_dir / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest["revocations"] = {
        "source": ("legislation.gov.uk's Changes to Legislation record, the affected feeds of the "
                   "SSI type and of each UK SI year; tools/revocation_harvest.py (FIX_PLAN P3.33)"),
        "checked": days,
        "flagged": dict(n_flag),
    }
    mpath.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"scopes_attached": len(days), "scopes_not_clean": sorted(k for k, v in state.items()
                                                                     if not v.get("clean")),
            "effects": len(effects), "flagged": dict(n_flag), "version": version}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--harvest", metavar="DIR")
    g.add_argument("--status", metavar="DIR")
    g.add_argument("--attach", nargs=2, metavar=("DIR", "SNAPSHOT_DIR"))
    ap.add_argument("--scopes", default="ssi,uksi:1987-2026")
    ap.add_argument("--max-calls", type=int, default=2400)
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP_S)
    ap.add_argument("--version", default="")
    ap.add_argument("--checked", default=None, help="--attach: one check date for every scope")
    a = ap.parse_args(argv)
    if a.harvest:
        harvest(Path(a.harvest), scopes_from(a.scopes), a.max_calls, a.gap)
        return 0
    if a.status:
        root = Path(a.status)
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        clean = [k for k, v in state.items() if v.get("clean")]
        print(f"calls {Store(root).calls()}; scopes clean {len(clean)} of {len(state)}")
        for k, v in state.items():
            if not v.get("clean"):
                print(f"  {k}: {v.get('problems') or v.get('reason')}")
        return 0
    if a.attach:
        if not a.version:
            ap.error("--attach needs --version")
        print(json.dumps(attach(Path(a.attach[0]), Path(a.attach[1]), a.version, a.checked), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
