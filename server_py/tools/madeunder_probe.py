#!/usr/bin/env python
"""Harvest SI enabling-power recitals for FIX_PLAN P3.31 (the made-under experiment).

**The question this answers.** "Which SIs were made under section N of the X Act?"
(6340, 6382, 6383). No live call reaches that relation: LEX has no made-under
endpoint (P5.1), its `description` carries a recital for some instruments only
(P2.3, P3.30), and the reverse direction needs a scan of every SI. The recital
itself ("... in exercise of the powers conferred by section 95 of the Social
Security (Scotland) Act 2018 and all other powers enabling them to do so ...")
is in each instrument's XML, `SecondaryPreamble`, as plain text with no
`<Citation>` markup. This probe reads it, cuts the recital out of the
preamble, parses the powers, and resolves each Act title exactly.

**Read `/made/data.xml`, not `/data.xml`.** A revoked SI's revised XML has its
preamble dotted out (SSI 2024/100); the as-made version keeps it. Older SIs
that legislation.gov.uk holds only as revised fall back to `/data.xml`, and
the record says which version was read.

**Three traps the parser exists for**, each found on a real preamble in the
feasibility study (i.AI's Lex Graph finder fell into all three):

* the recital ends where the powers end: "after consulting the committee ...
  under section 413 of the Insolvency Act 1986" is a consultation duty, not a
  power, so the window stops at "with the concurrence", "after consulting",
  "and (of) all other powers" and their relatives (`_WINDOW_END`);
* an Act title may contain parentheses and lower-case words ("Community Care
  and Health (Scotland) Act 2002"), so the title pattern admits both;
* provisions come as lists and anaphora: "sections 1(2)(a), 2 and 23(4) of",
  "section 2(2) of, and paragraph 1A of Schedule 2 to, the ... Act 1972",
  "of that Act", "the 2018 Act".

**Title resolution is exact or nothing.** `GET /id?title=<title>&type=primary`
answers 301 with one identifier on an exact match; anything else is recorded
as unresolved, never guessed (Lex Graph took the shortest of several matches).
legislation.gov.uk answers in regnal form for pre-1963 Acts
(`ukpga/Eliz2/10-11/47`), so both that and LEX's chronological form are kept.

**Routes.** Direct to www.legislation.gov.uk by default. LEX's
`/legislation/proxy/<encoded path>` returns the same as-made XML byte for byte
(checked 2026-10-08 on `ssi/2024/100/made/data.xml`), so `--via lex` reads it
through the host the target already calls. A harvest goes direct, so it does
not draw on LEX's shared rate limit.

**Every run is read-only, paced (`--gap`, default 0.3 s, inside the site's
fair-use limit of 1,500 requests per 5 minutes), capped (`--max-calls`,
enforced in code), sends an identifying User-Agent, and resumes**: a harvest
appends one JSON line per instrument and skips ids already in the file.

    python -m tools.madeunder_probe --made ssi/2024/100 uksi/2013/1046
    python -m tools.madeunder_probe --harvest ssi 2018-2026 --out FILE
    python -m tools.madeunder_probe --harvest uksi 1962-1981 --title scotland --out FILE
    python -m tools.madeunder_probe --resolve FILE           # Act titles -> ids, cached in FILE.titles.json
    python -m tools.madeunder_probe --reverse FILE asp/2018/9 95
    python -m tools.madeunder_probe --loose FILE "Social Security (Scotland) Act 2018" 95
"""
from __future__ import annotations

import argparse
import json
import time
import re
import sys
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

try:
    from tools.lgu_probe import LEX, LGU, PacedClient, proxy_path, _utf8_stdout
except ImportError:  # run as a script from tools/
    from lgu_probe import LEX, LGU, PacedClient, proxy_path, _utf8_stdout  # type: ignore

_TRANSIENT = (429, 500, 502, 503, 504)
USER_AGENT = "AILA-research-probe (FIX_PLAN P3.31; read-only; paced)"
DEFAULT_GAP_S = 0.3

from src.utils.made_under import (  # noqa: E402  the one parser, shared with the server
    _WINDOW_END, _WINDOW_START, _WS, parse_powers, preamble_text, recital_window, text_before_window,
)

# --------------------------------------------------------------------------
# One instrument
# --------------------------------------------------------------------------

def pdf_preamble(text: str) -> tuple:
    """(state, text) from the OCR text layer of a scanned instrument.

    legislation.gov.uk holds most pre-1987 SIs only as a PDF scan: the XML is a
    metadata stub with a `ukm:Alternative` link. The scan carries an OCR text
    layer with the recital on page 1, but with line-end hyphenation
    ("Govern-\\nment"), footnote markers ("Act 1958(a)") and stray glyphs, all
    of which are cleaned here before the same window and parser run.
    """
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text or "")
    t = re.sub(r"(\d{4})\s*\([a-z]\)", r"\1", t)          # "Act 1958(a)"
    t = re.sub(r"[^\x20-\x7E\n’]", " ", t)
    t = _WS.sub(" ", t).strip()
    if not _WINDOW_START.search(t):
        return ("none" if sum(c.isalpha() for c in t) < 20 else "no_recital"), t[:2000]
    return "ok", t[:4000]


def pdf_uri(xml_text: str) -> Optional[str]:
    m = re.search(r'<ukm:Alternative\b[^>]*URI="([^"]+\.pdf)"', xml_text)
    return m.group(1) if m else None


def record_from_xml(legislation_id: str, xml_text: str, version: str) -> dict:
    title_m = re.search(r"<dc:title>(.*?)</dc:title>", xml_text, re.S)
    title = _WS.sub(" ", title_m.group(1)).strip() if title_m else ""
    state, pre = preamble_text(xml_text)
    rec = _record(legislation_id, title, version, state, pre)
    if state == "none":
        rec["pdf"] = pdf_uri(xml_text)
    return rec


def _record(legislation_id: str, title: str, version: str, state: str, pre: str) -> dict:
    window = recital_window(pre) if state == "ok" else ""
    powers = parse_powers(window, text_before_window(pre)) if window else []
    flags = []
    if state == "ok" and not window:
        flags.append("no_recital_window")
    if window and not powers:
        flags.append("window_unparsed")
    if any(p["act"] is None for p in powers):
        flags.append("unresolved_anaphor")
    return {"id": legislation_id, "title": title, "version": version,
            "preamble": state, "window": window, "powers": powers, "flags": flags}


def pdf_record(client: PacedClient, rec: dict) -> dict:
    """Re-read a record that had no XML preamble from its PDF's text layer.

    Needs `pypdf` (dev machine only; not a product dependency).
    """
    from io import BytesIO
    from pypdf import PdfReader
    url = rec["pdf"].replace("http://", "https://")
    status, body = client.request("GET", url)
    if status != 200:
        return dict(rec, pdf_status=status)
    try:
        reader = PdfReader(BytesIO(body))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:2])
    except Exception as e:  # a damaged scan is a finding, not a crash
        return dict(rec, pdf_status=f"unreadable: {type(e).__name__}")
    state, pre = pdf_preamble(text)
    out = _record(rec["id"], rec.get("title", ""), "made-pdf", state, pre)
    out["pdf"] = rec["pdf"]
    return out


def _get(client: PacedClient, path: str, via: str) -> tuple:
    url = (LEX + proxy_path(path)) if via == "lex" else (LGU + path)
    return client.request("GET", url)


def fetch_record(client: PacedClient, legislation_id: str, via: str = "lgu",
                 full_fallback: bool = True) -> Optional[dict]:
    """The as-made record, falling back to the current version; None if not held."""
    # The introduction view carries the whole preamble at a fraction of the
    # size (UKSI 2013/1046: 9,847 bytes against 555,621), and gave the same
    # recital and powers as the full XML on 50 of 50 sampled SSIs (2026-10-08).
    # The full XML is tried only with `full_fallback`: a number neither
    # introduction answers is almost always one the site does not hold, and
    # the fallback doubles the cost of every such gap. A harvest without it is
    # checked afterwards by sampling its absent ids against the full XML.
    routes = [("made", "/introduction/made/data.xml"), ("current", "/introduction/data.xml")]
    if full_fallback:
        routes += [("made", "/made/data.xml"), ("current", "/data.xml")]
    for version, suffix in routes:
        # A transient 429/5xx is retried with backoff (one 500 on
        # uksi/1987/1598 stopped a 30,000-number run otherwise).
        for wait in (0, 2, 5, 15):
            if wait:
                time.sleep(wait)
            status, body = _get(client, f"/{legislation_id}{suffix}", via)
            if status not in _TRANSIENT:
                break
        if status == 200 and body.lstrip().startswith(b"<"):
            return record_from_xml(legislation_id, body.decode("utf-8", "replace"), version)
        if status not in (404, 410, 300):
            raise RuntimeError(f"{legislation_id}{suffix} -> {status}")
    return None


# --------------------------------------------------------------------------
# Enumeration
# --------------------------------------------------------------------------

_FEED_ID = re.compile(r"<id>http://www\.legislation\.gov\.uk/id/([a-z]+/\d{4}/\d+)</id>")


def list_year(client: PacedClient, typ: str, year: int, title: Optional[str]) -> list:
    """Every held id of a type and year, from the listing feed (20 a page)."""
    ids, page = [], 1
    while True:
        q = f"?page={page}" + (f"&title={quote(title)}" if title else "")
        status, body = _get(client, f"/{typ}/{year}/data.feed{q}", "lgu")
        if status != 200:
            break
        text = body.decode("utf-8", "replace")
        found = [i for i in _FEED_ID.findall(text) if i.startswith(f"{typ}/{year}/")]
        new = [i for i in found if i not in ids]
        ids.extend(new)
        more = re.search(r"<leg:morePages>(\d+)</leg:morePages>", text)
        if not new or not more or int(more.group(1)) == 0:
            break
        page += 1
    return ids


def max_number(client: PacedClient, typ: str, year: int) -> int:
    status, body = _get(client, f"/{typ}/{year}/data.feed", "lgu")
    if status != 200:
        return 0
    nums = [int(i.rsplit("/", 1)[1]) for i in _FEED_ID.findall(body.decode("utf-8", "replace"))
            if i.startswith(f"{typ}/{year}/")]
    return max(nums) if nums else 0


def _done_ids(out: Path) -> set:
    if not out.exists():
        return set()
    done = set()
    for ln in out.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            r = json.loads(ln)
            if not r.get("error"):
                done.add(r["id"])
    return done


def harvest(client: PacedClient, typ: str, years: Iterable[int], out: Path,
            title: Optional[str] = None, via: str = "lgu", full_fallback: bool = True) -> dict:
    """Append one record per held instrument; skip ids already in `out`.

    Without `title`, numbers 1..max are tried directly (the listing feed's
    first page gives the highest number; a gap answers 404 and costs a call).
    With `title`, the listing feed filtered by title gives the ids.
    """
    done = _done_ids(out)
    stats = {"fetched": 0, "absent": 0, "skipped": 0}
    for y in years:
        ids = (list_year(client, typ, y, title) if title
               else [f"{typ}/{y}/{n}" for n in range(1, max_number(client, typ, y) + 1)])
        for lid in ids:
            if lid in done:
                stats["skipped"] += 1
                continue
            try:
                rec = fetch_record(client, lid, via, full_fallback=full_fallback)
            except RuntimeError as e:
                # Recorded and skipped; `_done_ids` leaves it out, so the next
                # run of the same harvest retries it.
                with out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"id": lid, "error": str(e)[:200]}) + "\n")
                stats["errors"] = stats.get("errors", 0) + 1
                continue
            if rec is None:
                rec = {"id": lid, "absent": True}
                stats["absent"] += 1
            else:
                stats["fetched"] += 1
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            done.add(lid)
    return stats


# --------------------------------------------------------------------------
# Title resolution and the reverse query
# --------------------------------------------------------------------------

def resolve_title(client: PacedClient, title: str) -> Optional[str]:
    url = f"{LGU}/id?title={quote(title)}&type=primary"
    status, body = client.request("GET", url)
    # PacedClient's transport here does not follow redirects; the identifier is
    # in the Location header, which `_transport` returns as the body.
    if status in (301, 302, 303):
        loc = body.decode("utf-8", "replace").strip()
        m = re.search(r"/id/(.+?)/?$", loc)
        return m.group(1) if m else None
    return None


def load_records(path: Path) -> list:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def reverse(records: list, titles: dict, act: str, section: str) -> list:
    """Instruments whose recital names `section` of `act` (an id or a title)."""
    want = f"section/{section}"
    hits = []
    for r in records:
        for p in r.get("powers") or []:
            pid = titles.get(p.get("act") or "", None)
            if act in (pid, p.get("act")) and want in p.get("provisions", []):
                hits.append(r)
                break
    return hits


def loose_candidates(records: list, act_title: str, section: str) -> list:
    """Recall-first filter for building ground truth by hand: the preamble
    mentions the Act (or "the <year> Act") and the number anywhere."""
    year = act_title[-4:]
    num = re.compile(rf"\b{re.escape(section)}(?![0-9])")
    out = []
    for r in records:
        w = r.get("window") or ""
        if (act_title.lower() in w.lower() or f"the {year} act" in w.lower()) and num.search(w):
            out.append(r)
    return out


def reparse_context(rec: dict) -> str:
    """The antecedents an offline re-parse needs, from the record's own earlier parse.

    A stored record keeps its recital but not the preamble before it, which is
    where "that Act" and "the said Act" usually point. Without this, re-parsing
    offline threw away every resolution the fetch had made: 67 of 71 recovered
    SSI anaphors (1999-2017) and about 1,170 UK SIs were lost before it was
    caught. The Acts the record already resolved are handed back as "the <Act>",
    in order, so the parser can resolve to them and to nothing else.
    """
    return " ".join(f"the {p['act']}" for p in rec.get("powers") or [] if p.get("act"))


def build_snapshot(outdir: Path, inputs: list, label: str, not_covered: str,
                   version: str) -> dict:
    """The committed snapshot the server loads (`services/made_under_store`).

    Every held instrument is kept, with or without a recital, so the server's
    daily refresh does not treat an old instrument as new. A later input file
    overrides an earlier one for the same id (pass reparsed files last). Act ids
    come from each input's `.titles.json` cache (`--resolve`); a title that did
    not resolve exactly keeps `act_id: null`, and the server matches it by title.
    """
    import datetime as _dt
    import gzip
    recs, titles = {}, {}
    for path in inputs:
        cache = path.with_suffix(path.suffix + ".titles.json")
        if cache.exists():
            titles.update({k: v for k, v in json.loads(cache.read_text(encoding="utf-8")).items() if v})
        for r in load_records(path):
            if r.get("absent") or r.get("error"):
                continue
            recs[r["id"]] = r
    rows, with_powers, unresolved = [], 0, set()
    for lid in sorted(recs, key=lambda i: (i.split("/")[0], int(i.split("/")[1]), int(i.split("/")[2]))):
        r = recs[lid]
        powers = []
        for p in r.get("powers") or []:
            act = p.get("act")
            if not act:
                continue
            if act not in titles:
                unresolved.add(act)
            powers.append({"act": act, "act_id": titles.get(act), "provisions": p.get("provisions") or [],
                           "role": p.get("role") or "power"})
        with_powers += bool(powers)
        rows.append({"id": lid, "title": r.get("title") or "", "version": r.get("version") or "",
                     "recital": (r.get("window") or "")[:2000], "powers": powers})
    outdir.mkdir(parents=True, exist_ok=True)
    with gzip.open(outdir / "made_under_snapshot.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    years = sorted({int(i.split("/")[1]) for i in recs})
    manifest = {
        "version": version or _dt.date.today().isoformat() + ".1",
        "label": label, "not_covered": not_covered,
        "harvested_at": _dt.date.today().isoformat(),
        "types": sorted({i.split("/")[0] for i in recs}),
        "years": [years[0], years[-1]] if years else [],
        "instruments": len(rows), "with_powers": with_powers,
        "act_titles_unresolved": len(unresolved),
        "source": "legislation.gov.uk as-made XML preambles; tools/madeunder_probe.py (FIX_PLAN P3.31)",
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def make_transport():
    import httpx
    client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0,
                          follow_redirects=False)

    def _t(method, url, payload):
        r = client.get(url) if method == "GET" else client.post(url, json=payload)
        if r.status_code in (301, 302, 303) and "/id?" in url:
            return r.status_code, (r.headers.get("location") or "").encode()
        if r.status_code in (301, 302, 303, 307, 308):
            r = client.get(r.headers["location"] if r.headers["location"].startswith("http")
                           else LGU + r.headers["location"])
        return r.status_code, r.content
    return _t


def _years(spec: str) -> list:
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--made", nargs="+", metavar="ID")
    g.add_argument("--harvest", nargs=2, metavar=("TYPE", "YEARS"))
    g.add_argument("--resolve", metavar="FILE")
    g.add_argument("--reverse", nargs=3, metavar=("FILE", "ACT", "SECTION"))
    g.add_argument("--loose", nargs=3, metavar=("FILE", "ACT_TITLE", "SECTION"))
    g.add_argument("--snapshot", nargs="+", metavar=("OUTDIR", "IN"),
                   help="build server_py/data/made_under from harvest files (resolve titles "
                        "first with --resolve on each; their .titles.json caches are read)")
    g.add_argument("--reparse", nargs=2, metavar=("IN", "OUT"),
                   help="re-run the parser over stored windows (no network); re-fetch only "
                        "records whose preamble had no recognised window")
    g.add_argument("--pdf-pass", nargs=2, metavar=("IN", "OUT"),
                   help="re-read records with no XML preamble from their PDF scan")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--label", default="", help="--snapshot: the coverage label")
    ap.add_argument("--not-covered", default="", help="--snapshot: what the record omits")
    ap.add_argument("--version", default="", help="--snapshot: the snapshot version")
    ap.add_argument("--title", help="harvest only ids whose title matches (listing feed filter)")
    ap.add_argument("--via", choices=("lgu", "lex"), default="lgu")
    ap.add_argument("--no-full-fallback", action="store_true",
                    help="harvest: treat a number neither introduction view answers as absent")
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP_S)
    ap.add_argument("--quiet", action="store_true", help="do not print every call")
    a = ap.parse_args(argv)

    client = PacedClient(cap=a.max_calls, min_gap=a.gap, transport=make_transport(),
                         echo=not a.quiet)
    if a.made:
        for lid in a.made:
            rec = fetch_record(client, lid, a.via)
            print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0
    if a.harvest:
        if not a.out:
            ap.error("--harvest needs --out")
        stats = harvest(client, a.harvest[0], _years(a.harvest[1]), a.out, a.title, a.via,
                        full_fallback=not a.no_full_fallback)
        print(json.dumps(stats))
        return 0
    if a.resolve:
        path = Path(a.resolve)
        cache_path = path.with_suffix(path.suffix + ".titles.json")
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        titles = sorted({p["act"] for r in load_records(path) for p in r.get("powers") or []
                         if p.get("act")})
        todo = [t for t in titles if t not in cache]
        print(f"{len(titles)} distinct titles, {len(todo)} to resolve")
        for t in todo:
            cache[t] = resolve_title(client, t)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        unresolved = [t for t in titles if not cache.get(t)]
        print(f"resolved {len(titles) - len(unresolved)} of {len(titles)}; unresolved: {unresolved[:30]}")
        return 0
    if a.reverse:
        path = Path(a.reverse[0])
        cache_path = path.with_suffix(path.suffix + ".titles.json")
        titles = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        hits = reverse(load_records(path), titles, a.reverse[1], a.reverse[2])
        for h in hits:
            print(h["id"], "|", h["title"])
        print(f"{len(hits)} instruments")
        return 0
    if a.snapshot:
        outdir, inputs = Path(a.snapshot[0]), [Path(p) for p in a.snapshot[1:]]
        stats = build_snapshot(outdir, inputs, label=a.label, not_covered=a.not_covered,
                               version=a.version)
        print(json.dumps(stats, indent=1))
        return 0
    if a.reparse:
        src, dst = Path(a.reparse[0]), Path(a.reparse[1])
        refetched = 0
        with dst.open("w", encoding="utf-8") as fh:
            for rec in load_records(src):
                flagged = {"no_recital_window", "window_unparsed", "unresolved_anaphor"}
                if rec.get("absent") or rec.get("error") or rec.get("preamble") not in ("ok",):
                    pass
                elif flagged & set(rec.get("flags", [])) and rec.get("version") == "made":
                    # These need the preamble again: a new opening, or the
                    # text before the recital that an anaphor points into.
                    rec = fetch_record(client, rec["id"], a.via) or rec
                    refetched += 1
                elif rec.get("window"):
                    # The stored window was cut at the older end; the end has
                    # only gained stops, so the new cut is a prefix of it.
                    window = rec["window"]
                    e = _WINDOW_END.search(window)
                    if e:
                        window = window[: e.start()].strip(" ,")
                    rec = dict(rec, window=window)
                    powers = parse_powers(window, reparse_context(rec))
                    flags = [f for f in rec.get("flags", [])
                             if f not in ("window_unparsed", "unresolved_anaphor")]
                    if not powers:
                        flags.append("window_unparsed")
                    if any(p["act"] is None for p in powers):
                        flags.append("unresolved_anaphor")
                    rec = dict(rec, powers=powers, flags=flags)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps({"refetched": refetched}))
        return 0
    if a.pdf_pass:
        src, dst = Path(a.pdf_pass[0]), Path(a.pdf_pass[1])
        done = _done_ids(dst)
        n = 0
        for rec in load_records(src):
            if rec["id"] in done:
                continue
            if rec.get("preamble") == "none" and not rec.get("absent"):
                if not rec.get("pdf"):
                    # Harvested before the PDF fallback existed: the scan's
                    # name follows the id ("uksi/1962/2843" ->
                    # ".../pdfs/uksi_19622843_en.pdf"); on a miss, the XML
                    # stub names it.
                    typ, yr, num = rec["id"].split("/")
                    rec["pdf"] = f"{LGU}/{rec['id']}/pdfs/{typ}_{yr}{int(num):04d}_en.pdf"
                rec = pdf_record(client, rec)
                if rec.get("pdf_status") == 404:
                    status, body = _get(client, f"/{rec['id']}/made/data.xml", a.via)
                    uri = pdf_uri(body.decode("utf-8", "replace")) if status == 200 else None
                    if uri:
                        rec = pdf_record(client, dict(rec, pdf=uri))
                n += 1
            with dst.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps({"pdf_reads": n}))
        return 0
    if a.loose:
        hits = loose_candidates(load_records(Path(a.loose[0])), a.loose[1], a.loose[2])
        for h in hits:
            print(h["id"], "|", h["title"], "|", h["window"][:220])
        print(f"{len(hits)} candidates")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
