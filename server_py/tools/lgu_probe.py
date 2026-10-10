#!/usr/bin/env python
"""Probe legislation.gov.uk's dated effects for FIX_PLAN P3.21 and P5.4 (c).

P3.21 wants the DATE a provision was commenced, not only the instrument that
commenced it. LEX's `/amendment/search` names the instrument and carries no
date (0 of 19,031 `coming into force` rows, P2.5). Two candidate sources:

* **LEX's `description`** of the commencing instrument, from
  `POST /legislation/lookup` ("These Regulations bring sections 31 and 36 ...
  into force on 8 October 1901"). Free text: some state one date, some several,
  some "the appointed day", and some say nothing about commencement at all.
  `description_dates` reads it and says which, listing every match and drop.
* **legislation.gov.uk's "Changes to Legislation" feed**, LEX's own upstream:
  `/changes/affected/<id>/data.feed` (changes made TO an instrument) and
  `/changes/affecting/<id>/data.feed` (changes it MAKES). Each `ukm:Effect`
  is provision-to-provision, like a LEX row, and carries `ukm:InForceDates`:
  `<ukm:InForce Date="1901-10-22" Applied="true" Qualification="wholly in
  force"/>`, or `Prospective="true"` and no date. `Applied` says whether the
  effect has been applied to the revised text. `parse_effects_feed` reads it.

**Routes.** The target cannot reach www.legislation.gov.uk (not whitelisted).
LEX's `GET /legislation/proxy/{legislation_id}` passes a URL-encoded
legislation.gov.uk path through, including `changes/...` feeds and a query
string encoded into the path (checked live, batch 8 D), so `--via lex` reads the
same feed through the host the target already calls. That is an undocumented
use of an endpoint the spec calls a metadata proxy; `--via lgu` reads it direct.

    python -m tools.lgu_probe --effects affecting <type/year/number>
    python -m tools.lgu_probe --effects affected <type/year/number> --via lex
    python -m tools.lgu_probe --descriptions <type/year/number> [...]
    python -m tools.lgu_probe --compare <type/year/number> [--via lex]

**Every run is read-only, paced (0.6 s between calls), capped (`--max-calls`,
default 40, enforced in code) and prints every call** (method, URL, status,
bytes); `--log FILE` also appends each call to a JSONL file, and the cap then
counts the calls already in that file, so several runs share one budget.
No auth is sent to either host.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote, urlparse

LGU = "https://www.legislation.gov.uk"
LEX = "https://lex.lab.i.ai.gov.uk"
MIN_GAP_S = 0.6
PER_PAGE = 500

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
    "leg": "http://www.legislation.gov.uk/namespaces/legislation",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}

COMMENCEMENT = "coming into force"
SCOTTISH_CLASSES = {"ScottishAct", "ScottishStatutoryInstrument"}


# --------------------------------------------------------------------------
# ids and paths
# --------------------------------------------------------------------------

def short_id(value: Any) -> str:
    """`http://www.legislation.gov.uk/id/asp/1901/1` -> `asp/1901/1`."""
    s = str(value or "")
    path = urlparse(s).path if "://" in s else s
    path = path.strip("/")
    if path.startswith("id/"):
        path = path[3:]
    return path


def feed_path(kind: str, legislation_id: str, page: int = 1, per_page: int = PER_PAGE) -> str:
    """The legislation.gov.uk path of one page of an effects feed.

    `kind` is "affected" (changes made TO the instrument) or "affecting"
    (changes it makes)."""
    if kind not in ("affected", "affecting"):
        raise ValueError(kind)
    q = f"results-count={per_page}" + (f"&page={page}" if page > 1 else "")
    return f"/changes/{kind}/{short_id(legislation_id)}/data.feed?{q}"


def proxy_path(lgu_path: str) -> str:
    """The same legislation.gov.uk path through LEX's proxy, query and all."""
    return "/legislation/proxy/" + quote(lgu_path.lstrip("/"), safe="")


# --------------------------------------------------------------------------
# the effects feed
# --------------------------------------------------------------------------

def _int(text: Optional[str]) -> Optional[int]:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def parse_effects_feed(xml_text: str) -> dict:
    """One page of a Changes to Legislation Atom feed -> plain dicts.

    Returns `{"total", "page", "total_pages", "per_page", "effects": [...]}`.
    Each effect keeps what P3.21 needs: both sides (instrument and provision
    label), the effect type, `applied` / `requires_applied`, and every
    `ukm:InForce` (`date` None where the feed states none, e.g. prospective).
    A page that is not a feed raises ValueError: a probe must not read an
    error page as "no effects".
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"not XML: {e}") from None
    if root.tag != f"{{{NS['atom']}}}feed":
        raise ValueError(f"not an Atom feed: {root.tag}")
    out = {
        "total": _int(root.findtext("os:totalResults", namespaces=NS)),
        "page": _int(root.findtext("leg:page", namespaces=NS)) or 1,
        "total_pages": _int(root.findtext("leg:totalPages", namespaces=NS)),
        "per_page": _int(root.findtext("os:itemsPerPage", namespaces=NS)),
        "effects": [],
    }
    for eff in root.iter(f"{{{NS['ukm']}}}Effect"):
        a = eff.attrib
        in_force = []
        for f in eff.iter(f"{{{NS['ukm']}}}InForce"):
            fa = f.attrib
            in_force.append({
                "date": fa.get("Date") or None,
                "applied": fa.get("Applied"),
                "prospective": fa.get("Prospective") == "true",
                "qualification": fa.get("Qualification") or "",
            })
        out["effects"].append({
            "id": a.get("EffectId"),
            "type": a.get("Type") or "",
            "affected": short_id(a.get("AffectedURI")),
            "affected_class": a.get("AffectedClass") or "",
            "affected_provisions": a.get("AffectedProvisions") or "",
            "affecting": short_id(a.get("AffectingURI")),
            "affecting_class": a.get("AffectingClass") or "",
            "affecting_provisions": a.get("AffectingProvisions") or "",
            "applied": a.get("Applied") == "true",
            "requires_applied": a.get("RequiresApplied") == "true",
            "modified": a.get("Modified"),
            "in_force": in_force,
        })
    return out


def is_commencement(effect: dict) -> bool:
    return str(effect.get("type") or "").strip().lower() == COMMENCEMENT


def effect_dates(effect: dict) -> list:
    """The distinct in-force dates an effect states, sorted (may be empty)."""
    return sorted({f["date"] for f in effect.get("in_force") or [] if f.get("date")})


def summarise_effects(effects: list) -> dict:
    """Counts P3.21 and P5.4 (c) turn on, over a list of parsed effects.

    `commencements_other` excludes an instrument commencing itself (P3.5's
    self-referential rule), as the hop would. `outstanding` is an effect the
    feed says must be applied to the revised text and has not been
    (`RequiresApplied` and not `Applied`).
    """
    s = collections.Counter()
    by_scot = {True: collections.Counter(), False: collections.Counter()}
    for e in effects:
        s["effects"] += 1
        scot = e.get("affected_class") in SCOTTISH_CLASSES
        b = by_scot[scot]
        b["effects"] += 1
        if e.get("requires_applied") and not e.get("applied"):
            s["outstanding"] += 1
            b["outstanding"] += 1
        if not is_commencement(e):
            continue
        s["commencements"] += 1
        b["commencements"] += 1
        if e.get("affected") == e.get("affecting"):
            s["commencements_self"] += 1
            continue
        s["commencements_other"] += 1
        dates = effect_dates(e)
        if dates:
            s["commencements_other_dated"] += 1
            b["commencements_other_dated"] += 1
            if len(dates) > 1:
                s["commencements_other_multi_date"] += 1
        elif any(f.get("prospective") for f in e.get("in_force") or []):
            s["commencements_other_prospective"] += 1
        else:
            s["commencements_other_undated"] += 1
        b["commencements_other"] += 1
        if e.get("requires_applied") and not e.get("applied"):
            s["commencements_other_outstanding"] += 1
    out = dict(s)
    out["scottish"] = dict(by_scot[True])
    out["other_jurisdictions"] = dict(by_scot[False])
    return out


# --------------------------------------------------------------------------
# LEX descriptions
# --------------------------------------------------------------------------

_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December")
_MONTH_NO = {m.lower(): i + 1 for i, m in enumerate(_MONTHS.split("|"))}
_DAY = r"\d{1,2}\s*(?:st|nd|rd|th)?"
# A full date ("8 October 1901", "1st January 1902", "1stNovember 1902", "the
# 1st day of April 1903"), or a list ending in one ("20th June and 1st July
# 1901", "1st and 22nd April 1902"): the earlier items take the next stated
# month and the final year.
_ITEM = rf"{_DAY}(?:\s*day\s+of)?\s*(?:{_MONTHS})?"
_DATE_LIST = re.compile(
    rf"(?<!\d)((?:{_ITEM}\s*(?:,\s*(?:and\s+)?|\s+and\s+|\s*&\s*))*"
    rf"{_DAY}(?:\s*day\s+of)?\s*(?:{_MONTHS}),?\s+\d{{4}})(?!\d)",
    re.I,
)
_ONE = re.compile(rf"(\d{{1,2}})\s*(?:st|nd|rd|th)?(?:\s*day\s+of)?\s*({_MONTHS})?", re.I)
_YEAR = re.compile(r"(\d{4})\s*$")
# Commencement language. "appoint" covers "appoints 1st October 1901 as the
# day"; "operation" covers Northern Ireland's "brings into operation"; "in
# force" covers "brings Part 5 fully in force ... on 6th April 1902".
_COMMENCE = re.compile(
    r"\bin(?:to)?\s+(?:force|operation)\b|\bcommenc|\bappoint|\bcom(?:e|es|ing)\s+into", re.I)
# The verb a date hangs on: the LAST one before it in its clause (a bracketed
# aside is its own clause). Present or passive-present ("brings", "appoints",
# "is brought") is this instrument's commencement; past ("came into force",
# "brought ... into force" with no "is", "was commenced") reports an EARLIER
# commencement, by Royal Assent or another instrument ("The ... (Commencement
# No.1) Order 1901 brought some other provisions ... into force on 1stJuly
# 1901"), and is not this instrument's date.
_VERB = re.compile(
    r"\b(?:(is|are|be|been|was|were|has|have|had|will|shall)\s+)?(not\s+)?"
    r"(?:(?:already|also|only|being|then|fully|further)\s+)*"
    r"(bring|brings|brought|appoint|appoints|appointed|commence|commences|commenced|"
    r"commencing|come|comes|came|coming)\b", re.I)
_PRESENT = {"bring", "brings", "appoint", "appoints", "commence", "commences", "commencing",
            "come", "comes", "coming"}
_PASSIVE_PRESENT_AUX = {"is", "are", "be", "will", "shall"}
_UNTIL = re.compile(r"\b(?:until|till)(?:\s+the\s+end\s+of)?(?:\s+the)?\s*$", re.I)
# "the period of six months beginning with 25th March 1902": a period's anchor,
# not a commencement date.
_PERIOD = re.compile(r"\b(?:beginning|starting|ending)\s+(?:with|on)\s*$", re.I)
# Split only where a full stop or semicolon is followed by a capitalised WORD,
# so "etc. (Scotland)", "S.S.I. 1901/3" and "c. 12" do not end a sentence.
_SENTENCE = re.compile(r"(?<=[.;])\s+(?=[A-Z][a-z])")


def _clause_before(sent: str, at: int) -> str:
    """The text a date at `at` hangs on: from an unclosed "(" if it is inside
    one, else the sentence so far with every closed (...) aside removed."""
    head = sent[:at]
    depth, open_at = 0, None
    for i, ch in enumerate(head):
        if ch == "(":
            depth += 1
            if depth == 1:
                open_at = i
        elif ch == ")" and depth:
            depth -= 1
    if depth and open_at is not None:
        return head[open_at + 1:]
    while True:
        stripped = re.sub(r"\([^()]*\)", " ", head)
        if stripped == head:
            return head
        head = stripped


def _hangs_on(sent: str, at: int) -> tuple:
    """(taken, why) for a date at `at` in `sent`."""
    clause = _clause_before(sent, at)
    if _PERIOD.search(clause):
        return False, "a period's anchor date (beginning with)"
    until = bool(_UNTIL.search(clause))
    verbs = list(_VERB.finditer(clause))
    if not verbs:
        if until:
            return False, "an end date (until)"
        return (True, "") if _COMMENCE.search(clause) else (False, "no commencement verb before it")
    v = verbs[-1]
    aux, neg, lemma = (v.group(1) or "").lower(), bool(v.group(2)), v.group(3).lower()
    if lemma in _PRESENT:
        present = True
    elif lemma == "came":
        present = False
    else:  # brought / commenced / appointed
        present = aux in _PASSIVE_PRESENT_AUX
    if not present:
        return False, "an earlier commencement (past tense)"
    if neg:
        # "is not commenced until 1st April 1902" states the date; "will not
        # come into force on 1st December 1901" denies it.
        return (True, "") if until else (False, "a negated commencement")
    if until:
        return False, "an end date (until)"
    return True, ""


def _expand(span: str) -> list:
    """`"20th June and 1st July 1901"` -> `["1901-06-20", "1901-07-01"]`."""
    ym = _YEAR.search(span)
    if not ym:
        return []
    year = int(ym.group(1))
    body = span[:ym.start()]
    items = [(int(m.group(1)), (m.group(2) or "").lower()) for m in _ONE.finditer(body)
             if m.group(1)]
    out = []
    month = None
    for day, mon in reversed(items):
        if mon:
            month = _MONTH_NO[mon]
        if month is None or not 1 <= day <= 31:
            continue
        out.append(f"{year:04d}-{month:02d}-{day:02d}")
    return sorted(set(out))


def description_dates(text: Any) -> dict:
    """Read the commencement date(s) a LEX `description` states, if any.

    Returns:
      * `class`: "dated" (a date in a sentence with commencement language),
        "undated" (commencement language, no date: "the appointed day", "the
        days they appoint", "various days"), "no_statement" (no commencement
        language at all), or "empty".
      * `dates`: the distinct ISO dates of the "dated" matches.
      * `matches`: each dated sentence, its date span and dates.
      * `drops`: every date span NOT taken, with why: no commencement
        language in its sentence; an earlier commencement (the verb it hangs
        on is past tense: Royal Assent, or another instrument); a negated
        commencement; an end date ("until").
      * `first_date_at`: the character offset of the first taken date, so a
        caller can check it falls inside a cap (`lookup_legislation` keeps
        600 characters).
    Never infers a date from the instrument's year or made date.
    """
    t = " ".join(str(text or "").split())
    res = {"class": "empty", "dates": [], "matches": [], "drops": [], "first_date_at": None}
    if not t:
        return res
    has_commence = False
    pos = 0
    for sent in _SENTENCE.split(t):
        start = t.find(sent, pos)
        pos = start + len(sent)
        commence = bool(_COMMENCE.search(sent))
        has_commence = has_commence or commence
        for m in _DATE_LIST.finditer(sent):
            dates = _expand(m.group(1))
            if not dates:
                continue
            if not commence:
                res["drops"].append({"span": m.group(1), "why": "no commencement language in its sentence"})
                continue
            taken, why = _hangs_on(sent, m.start(1))
            if not taken:
                res["drops"].append({"span": m.group(1), "why": why})
            else:
                res["matches"].append({"span": m.group(1), "dates": dates, "sentence": sent})
                if res["first_date_at"] is None:
                    res["first_date_at"] = start + m.start(1)
    res["dates"] = sorted({d for m in res["matches"] for d in m["dates"]})
    if res["dates"]:
        res["class"] = "dated"
    elif has_commence:
        res["class"] = "undated"
    else:
        res["class"] = "no_statement"
    return res


# --------------------------------------------------------------------------
# LEX rows against the feed
# --------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return " ".join(str(s or "").lower().split())


def compare_commencements(lex_rows: list, effects: list, subject: str) -> dict:
    """LEX `coming into force` relations TO `subject` against the feed's.

    Keyed (changed provision, affecting instrument, affecting provision),
    scheme-free (LEX's http/https twins collapse) and self-referential rows
    left out (P3.5). Reports how many match, how many each side alone holds,
    and of the matched how many the feed dates.
    """
    lid = short_id(subject)
    lex = set()
    for r in lex_rows or []:
        if not isinstance(r, dict) or _norm(r.get("type_of_effect")) != COMMENCEMENT:
            continue
        ch, af = short_id(r.get("changed_legislation")), short_id(r.get("affecting_legislation"))
        if ch != lid or not af or af == ch:
            continue
        lex.add((_norm(r.get("changed_provision")), af, _norm(r.get("affecting_provision"))))
    lgu = {}
    for e in effects or []:
        if not is_commencement(e) or e.get("affected") != lid or e.get("affecting") == lid:
            continue
        k = (_norm(e.get("affected_provisions")), e.get("affecting"), _norm(e.get("affecting_provisions")))
        lgu.setdefault(k, set()).update(effect_dates(e))
    both = lex & set(lgu)
    return {
        "lex": len(lex), "lgu": len(lgu), "matched": len(both),
        "lex_only": len(lex - set(lgu)), "lgu_only": len(set(lgu) - lex),
        "matched_dated": sum(1 for k in both if lgu[k]),
        "lgu_dated": sum(1 for v in lgu.values() if v),
        "instruments_lex": len({k[1] for k in lex}),
        "instruments_lgu": len({k[1] for k in lgu}),
    }


# --------------------------------------------------------------------------
# paced, capped, logged HTTP
# --------------------------------------------------------------------------

class PacedClient:
    """Read-only HTTP with the pacing and cap enforced here, not by the caller.

    With `log`, every call is appended to that JSONL file and the cap counts
    the lines already in it, so separate runs share one budget.
    """

    def __init__(self, cap: int, log: Optional[Path] = None, min_gap: float = MIN_GAP_S,
                 transport: Optional[Callable] = None, echo: bool = True):
        self.cap, self.log, self.min_gap, self.echo = cap, log, min_gap, echo
        self._last = 0.0
        self._made = 0
        self._transport = transport

    def _prior(self) -> int:
        if self.log and self.log.exists():
            return sum(1 for ln in self.log.read_text(encoding="utf-8").splitlines() if ln.strip())
        return 0

    def request(self, method: str, url: str, payload: Optional[dict] = None):
        if not (url.startswith(LGU + "/") or url.startswith(LEX + "/")):
            raise ValueError(f"host not allowed: {url}")
        n = self._prior() + 1 if self.log else self._made + 1
        if n > self.cap:
            raise RuntimeError(f"call cap reached ({self.cap}); refusing {method} {url}")
        wait = self.min_gap - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        if self._transport is not None:
            status, body = self._transport(method, url, payload)
        else:
            import httpx
            if method == "GET":
                r = httpx.get(url, timeout=120.0)
            else:
                r = httpx.post(url, json=payload, timeout=120.0)
            status, body = r.status_code, r.content
        self._last = time.time()
        self._made += 1
        rec = {"n": n, "method": method, "url": url, "payload": payload, "status": status,
               "bytes": len(body), "elapsed_ms": round((self._last - t0) * 1000)}
        if self.log:
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        if self.echo:
            print(f"  [{n}] {method} {url} -> {status} ({len(body):,} bytes)")
        return status, body


def fetch_feed(client: PacedClient, kind: str, legislation_id: str, via: str = "lgu",
               per_page: int = PER_PAGE) -> dict:
    """Every page of one effects feed, merged. Raises on a non-200 or non-feed page."""
    effects, page, total = [], 1, None
    while True:
        p = feed_path(kind, legislation_id, page, per_page)
        url = (LEX + proxy_path(p)) if via == "lex" else (LGU + p)
        status, body = client.request("GET", url)
        if status != 200:
            raise RuntimeError(f"{url} -> {status}")
        parsed = parse_effects_feed(body.decode("utf-8", "replace"))
        effects.extend(parsed["effects"])
        total = parsed["total"]
        if not parsed["total_pages"] or page >= parsed["total_pages"]:
            break
        page += 1
    return {"total": total, "effects": effects, "pages": page}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _cmd_effects(client, kind, ids, via) -> int:
    for lid in ids:
        f = fetch_feed(client, kind, lid, via)
        s = summarise_effects(f["effects"])
        print(f"{kind} {lid}: {f['total']} effects in {f['pages']} page(s)")
        print("  " + json.dumps(s))
        types = collections.Counter(e["type"] for e in f["effects"])
        print("  top types: " + ", ".join(f"{t!r} {n}" for t, n in types.most_common(6)))
    return 0


def _cmd_descriptions(client, ids) -> int:
    for lid in ids:
        typ, year, num = short_id(lid).split("/")
        status, body = client.request("POST", f"{LEX}/legislation/lookup",
                                      {"legislation_type": typ, "year": int(year), "number": int(num)})
        desc = ""
        if status == 200:
            desc = (json.loads(body.decode("utf-8")) or {}).get("description") or ""
        d = description_dates(desc)
        print(f"{lid}: {d['class']} {d['dates']} (first date at char {d['first_date_at']}; "
              f"description {len(desc)} chars)")
        for m in d["matches"]:
            print(f"    match {m['span']!r} -> {m['dates']}")
        for x in d["drops"]:
            print(f"    drop  {x['span']!r}: {x['why']}")
    return 0


def _cmd_compare(client, ids, via) -> int:
    for lid in ids:
        status, body = client.request("POST", f"{LEX}/amendment/search",
                                      {"legislation_id": short_id(lid), "search_amended": True,
                                       "size": 20000})
        rows = json.loads(body.decode("utf-8")) if status == 200 else []
        f = fetch_feed(client, "affected", lid, via)
        print(f"{lid}: " + json.dumps(compare_commencements(rows, f["effects"], lid)))
    return 0


def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="lgu_probe", description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--effects", nargs="+", metavar=("KIND", "ID"),
                   help="KIND is affected or affecting, then one or more ids")
    g.add_argument("--descriptions", nargs="+", metavar="ID",
                   help="LEX lookup of each id and the date(s) its description states")
    g.add_argument("--compare", nargs="+", metavar="ID",
                   help="LEX coming-into-force relations TO each id against the feed's")
    ap.add_argument("--via", choices=("lgu", "lex"), default="lgu",
                    help="read the feed direct (lgu) or through LEX's proxy (lex)")
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--log", type=Path, default=None)
    a = ap.parse_args(argv)
    client = PacedClient(cap=a.max_calls, log=a.log)
    try:
        if a.effects:
            kind, ids = a.effects[0], a.effects[1:]
            if kind not in ("affected", "affecting") or not ids:
                ap.error("--effects KIND ID [ID ...], KIND affected or affecting")
            return _cmd_effects(client, kind, ids, a.via)
        if a.descriptions:
            return _cmd_descriptions(client, a.descriptions)
        return _cmd_compare(client, a.compare, a.via)
    except RuntimeError as e:
        print(f"stopped: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
