"""Whether each instrument in the made-under record is recorded as revoked (FIX_PLAN P3.33).

A made-under list (P3.31) says which instruments were made under a power; a lawyer asking that
mostly wants what still applies. legislation.gov.uk's "Changes to Legislation" record holds every
revocation as an effect on the revoked instrument, dated (`ukm:InForce@Date`) and qualified, the
same record P3.21 reads for commencement dates. This module turns those effects into one stored
flag per instrument. It is shared by the harvester (`tools/revocation_harvest.py`, which reads the
type-wide affected feeds and writes the flags into the made-under snapshot) and the server
(`services/made_under_store.py`), so the flag is built by one rule.

**What Session 46 measured, and each trap this module exists for:**

* **The type-wide feed is complete.** For 177 sampled instruments (the 37 of P3.33's acceptance
  set, 100 random SSIs, 40 random UK SIs of 2005) the type-wide feeds held every effect each
  instrument's own feed holds, and the flags agreed 177 of 177.
* **Welsh SIs and NI Orders in Council carry UK SI numbers.** The record holds them as
  ``uksi/Y/N``; the feed files their effects as ``wsi/Y/N`` and ``nisi/Y/N`` (4,586 of the 22,674
  effects on UK SIs of 2005). Matched on the record's id alone, 4 of 40 sampled UK SIs read as
  never revoked; `instrument_key` maps them.
* **A removal is of the WHOLE instrument only where its label names the instrument**
  ("Regulations", "Order", "Rules", ..., or blank in older entries). "Sch." is the schedule: 35
  such removals in the two probe crawls would otherwise read as whole revocations.
* **The classes are P3.28's** (`classify_removal`): a words-only removal is not a revocation;
  a qualified one (prospective, temporary, for specified purposes, for part of the UK, "in part
  for specified purposes", "(except reg. 12 ...)") is stated only with the feed's own words.
* **Dates.** 722 of 3,041 whole revocations in the probe crawls carry no ``InForce`` date; some
  older entries put it in the label instead ("rev (1.1.2006)"), read here and marked as from the
  label. 51 are dated after the day they were read (temporary orders that cease on a set day,
  revocations made in advance), so the flag stores the date and the renderer compares it with
  today: a revocation still to come is never stated as having happened.
* **The index lists some effects twice** (two versions of one EffectId, 69 of 64,461 SSI
  effects); the later version is kept.

**The B4 rules hold (P2.5, P3.24):** the flag states a RECORDED removal. It never says anything is
in force, and an instrument with no flag is "not recorded as revoked", which is not "in force".

Pure functions; no I/O. Pinned by `tests/test_revocation_record.py`.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import Any, Iterable, Optional

from .removal_effects import PROVISION, PROVISION_IN_PART, QUALIFIED, classify_removal

WHOLLY = "wholly"
PARTLY = "partly"
QUALIFIED_ONLY = "qualified"

# The AffectedProvisions labels that name the instrument itself (lower-cased). Read off every
# label on a removal in the probe crawls (`evidence/seam/s46/check_s46.py`, section B):
# "Regualtions" is the feed's own typo; "Act" appears on SIs; "residue" is what is left after
# earlier partial revocations. A blank label is the older entries' form ("rev", no provision).
WHOLE_LABELS = frozenset({"regulations", "regualtions", "order", "instrument", "rules",
                          "act of sederunt", "scheme", "act", "residue", ""})

# How much of each list is stored per instrument (the snapshot carries 86,744 instruments).
MAX_STORED = 5

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
    "leg": "http://www.legislation.gov.uk/namespaces/legislation",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}
_ID = re.compile(r"^https?://www\.legislation\.gov\.uk/(?:id/)?")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_XML = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.I)
_LABEL_DATE = re.compile(r"\((\d{1,2})\.(\d{1,2})\.(\d{4})\)")
# P3.28's words-only test (`removal_effects._WORDS`). `classify_removal` checks a qualifier
# first, so "words omitted (temp.)" comes back QUALIFIED; it is still text amended, not a
# revocation, and the flag skips it (ssi/2015/126 in the probe crawls).
_WORDS = re.compile(r"\bwords?\b|\bentr(?:y|ies)\b", re.I)


# ---------------------------------------------------------------------------
# the feed
# ---------------------------------------------------------------------------

def short_id(uri: Any) -> str:
    return _ID.sub("", str(uri or "")).strip("/")


def _int(text) -> Optional[int]:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def parse_feed(xml_text: str) -> dict:
    """One page of an affected feed: ``{"total", "page", "total_pages", "generated", "effects"}``.

    Each effect keeps what the flag needs plus its EffectId, Modified and the entry's
    <updated> (the harvest's consistency check and the de-duplication read them). Raises
    ValueError on anything that is not a feed, so an error page is never read as "no effects".
    """
    if not isinstance(xml_text, str) or not xml_text.strip():
        raise ValueError("empty")
    if _FORBIDDEN_XML.search(xml_text):
        raise ValueError("document type or entity declaration")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"not XML: {e}") from None
    if root.tag != f"{{{_NS['atom']}}}feed":
        raise ValueError(f"not an Atom feed: {root.tag}")
    out = {
        "total": _int(root.findtext("os:totalResults", namespaces=_NS)),
        "page": _int(root.findtext("leg:page", namespaces=_NS)) or 1,
        "total_pages": _int(root.findtext("leg:totalPages", namespaces=_NS)),
        "generated": root.findtext("atom:updated", namespaces=_NS),
        "effects": [],
    }
    for entry in root.findall("atom:entry", _NS):
        eff = entry.find(".//ukm:Effect", _NS)
        if eff is None:
            continue
        a = eff.attrib
        in_force = []
        for f in eff.iter(f"{{{_NS['ukm']}}}InForce"):
            d = (f.attrib.get("Date") or "").strip()
            in_force.append({"date": d if _ISO.match(d) else None,
                             "qualification": (f.attrib.get("Qualification") or "").strip()})
        out["effects"].append({
            "eid": a.get("EffectId") or a.get("URI") or "",
            "type": (a.get("Type") or "").strip(),
            "affected": short_id(a.get("AffectedURI")),
            "provisions": a.get("AffectedProvisions") or "",
            "by": short_id(a.get("AffectingURI")),
            "modified": a.get("Modified"),
            "updated": entry.findtext("atom:updated", namespaces=_NS),
            "in_force": in_force,
        })
    return out


def timestamp(value: Any) -> Optional[datetime]:
    """A feed timestamp in UTC. The feed mixes "...Z" and "...+01:00" with microseconds."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _stamp(e: dict) -> datetime:
    times = [t for t in (timestamp(e.get("modified")), timestamp(e.get("updated"))) if t]
    return max(times) if times else datetime(1900, 1, 1, tzinfo=timezone.utc)


def merge_effects(into: dict, effects: Iterable[dict]) -> dict:
    """Add effects to ``{EffectId: effect}``, keeping the later of two versions of one effect."""
    for e in effects:
        k = e.get("eid")
        if not k:
            continue
        if k not in into or _stamp(e) > _stamp(into[k]):
            into[k] = e
    return into


# ---------------------------------------------------------------------------
# the flag
# ---------------------------------------------------------------------------

def scope_of(legislation_id: str) -> str:
    """The harvest feed an instrument's effects come from: ``ssi`` (one type-wide feed) or
    ``uksi/<year>`` (one feed per affected year). The manifest records each feed's check date."""
    parts = str(legislation_id or "").strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "uksi":
        return f"uksi/{parts[1]}"
    return parts[0] if parts else ""


def instrument_key(affected: str) -> str:
    """The record's id for an affected id: Welsh SIs and NI Orders in Council are filed as
    ``wsi/Y/N`` and ``nisi/Y/N`` but carry UK SI numbers, and the record holds them as
    ``uksi/Y/N``."""
    t, _, rest = str(affected or "").partition("/")
    return f"uksi/{rest}" if t in ("wsi", "nisi") and rest else str(affected or "")


def _is_whole(e: dict) -> bool:
    return str(e.get("provisions") or "").strip().lower() in WHOLE_LABELS


def _dates(e: dict) -> tuple:
    """(dates, source): the feed's dated InForce entries, else a date in the label."""
    dated = [{"date": f["date"], "qualification": f.get("qualification") or ""}
             for f in e.get("in_force") or [] if f.get("date")]
    if dated:
        return dated, "feed"
    m = _LABEL_DATE.search(e.get("type") or "")
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            return [{"date": d, "qualification": ""}], "label"
        except ValueError:
            pass
    return [], None


def _relation(e: dict, subject: str, with_provisions: bool = False) -> dict:
    dates, source = _dates(e)
    r = {"type": e.get("type") or "", "by": e.get("by") or ""}
    if instrument_key(r["by"]) == subject:
        r["self"] = True
    if dates:
        r["dates"] = dates
        r["date_source"] = source
    if with_provisions:
        r["provisions"] = e.get("provisions") or ""
    return r


def flag_for(subject: str, effects: Iterable[dict]) -> Optional[dict]:
    """The stored flag for one instrument from the effects recorded against it, or None
    when none of them removes anything (words-only removals are text amended, not revoked)."""
    whole, partial, qualified = [], [], []
    for e in effects:
        cls, qual = classify_removal(e.get("type"))
        if cls == PROVISION and _is_whole(e):
            whole.append(e)
        elif cls in (PROVISION, PROVISION_IN_PART):
            partial.append(e)
        elif cls == QUALIFIED and not _WORDS.search(e.get("type") or ""):
            qualified.append(e)
    if not (whole or partial or qualified):
        return None
    order = lambda e: (e.get("by") or "", e.get("provisions") or "")  # noqa: E731
    f: dict = {"state": WHOLLY if whole else PARTLY if partial else QUALIFIED_ONLY}
    if whole:
        f["whole"] = [_relation(e, subject) for e in sorted(whole, key=order)[:MAX_STORED]]
    if partial:
        # The instrument that made most of the removals first ("by ssi/2025/336 (8) ...").
        counts: dict = {}
        for e in partial:
            counts[e.get("by") or ""] = counts.get(e.get("by") or "", 0) + 1
        by = sorted(counts, key=lambda b: (-counts[b], b))
        f["partial"] = {"count": len(partial), "by": by[:MAX_STORED], "by_count": len(by)}
    if qualified:
        f["qualified"] = [_relation(e, subject, with_provisions=True)
                          for e in sorted(qualified, key=order)[:MAX_STORED]]
        f["qualified_count"] = len(qualified)
    return f


def flags_from_effects(effects: dict, ids: Iterable[str]) -> dict:
    """``{legislation_id: flag}`` for every id in ``ids`` with a removal recorded against it."""
    wanted = set(ids)
    by: dict = {}
    for e in effects.values():
        key = instrument_key(e.get("affected") or "")
        if key in wanted:
            by.setdefault(key, []).append(e)
    out = {}
    for lid, effs in by.items():
        f = flag_for(lid, effs)
        if f:
            out[lid] = f
    return out


# ---------------------------------------------------------------------------
# reading a flag on a given day
# ---------------------------------------------------------------------------

def _today(today: Optional[str]) -> str:
    return today or date.today().isoformat()


def whole_in_effect(flag: Optional[dict], today: Optional[str] = None) -> Optional[bool]:
    """For a WHOLLY flag: True if a whole removal is dated on or before today, False if every
    dated one is still to come, None if none of them carries a date. Not a WHOLLY flag: None."""
    if not flag or flag.get("state") != WHOLLY:
        return None
    t = _today(today)
    dated = [d["date"] for r in flag.get("whole") or [] for d in r.get("dates") or [] if d.get("date")]
    if not dated:
        return None
    return min(dated) <= t


def category(flag: Optional[dict], today: Optional[str] = None) -> str:
    """One of: ``revoked`` (a whole removal dated today or earlier), ``revoked_undated``,
    ``revoked_later`` (every dated whole removal still to come), ``partly``, ``qualified``,
    ``none``."""
    if not flag:
        return "none"
    if flag.get("state") == WHOLLY:
        w = whole_in_effect(flag, today)
        return "revoked" if w else "revoked_undated" if w is None else "revoked_later"
    return "partly" if flag.get("state") == PARTLY else "qualified"


def _verb(effect_type: str) -> str:
    t = (effect_type or "").lower()
    if "cease" in t:
        return "as ceasing to have effect"
    if "repeal" in t:
        return "as repealed"
    if "lapse" in t:
        return "as lapsed"
    if "omit" in t:
        return "as omitted"
    return "as revoked"


def _when(r: dict, today: str) -> str:
    dates = r.get("dates") or []
    if not dates:
        return "no date recorded"
    parts = []
    for d in dates[:2]:
        q = d.get("qualification") or ""
        # "wholly in force" is the plain case; anything else is the record's own words
        # ("Other", "with effect in accordance with"), quoted so it is not read as ours.
        q = "" if q.lower() in ("", "wholly in force") else f" (date qualified in the record as \"{q}\")"
        later = ", a date still to come" if d["date"] > today else ""
        src = " (the date in the record's label)" if r.get("date_source") == "label" else ""
        parts.append(f"with effect from {d['date']}{src}{q}{later}")
    return "; ".join(parts)


def _by(r: dict) -> str:
    return "by its own provisions" if r.get("self") else f"by {r.get('by')}"


def _words(effect_type: str) -> str:
    """The record's own words, quoted only where they say more than the verb does."""
    t = (effect_type or "").strip()
    return "" if t.lower() in ("revoked", "repealed", "ceases to have effect", "omitted") \
        else f" (the record's words: \"{t}\")"


def describe(flag: Optional[dict], checked: Optional[str], today: Optional[str] = None) -> str:
    """The Worker-facing line for one listed instrument. Says only what the record holds.

    Short on purpose: a made-under list is never summarised and carries up to 40 of these,
    and the CURRENCY block beside it states the source and the day it was checked."""
    t = _today(today)
    if checked is None:
        return "not checked"
    if not flag:
        return "no revocation recorded"
    if flag.get("state") == WHOLLY:
        r = (flag.get("whole") or [{}])[0]
        line = f"recorded {_verb(r.get('type'))} in whole {_by(r)}, {_when(r, t)}{_words(r.get('type'))}"
    elif flag.get("state") == PARTLY:
        p = flag.get("partial") or {}
        n = int(p.get("count") or 0)
        others = p.get("by_count", 0) - min(len(p.get("by") or []), 2)
        by = ", ".join((p.get("by") or [])[:2]) + (
            f" and {others} other{'s' if others > 1 else ''}" if others > 0 else "")
        line = (f"recorded as revoked in part: {n} provision{'s' if n != 1 else ''} "
                f"revoked or omitted, by {by}")
    else:
        r = (flag.get("qualified") or [{}])[0]
        line = f"recorded with a qualified removal only: \"{r.get('type')}\" {_by(r)}, {_when(r, t)}"
    if flag.get("state") != QUALIFIED_ONLY and flag.get("qualified"):
        q = flag["qualified"][0]
        line += f"; also a qualified removal: \"{q.get('type')}\" {_by(q)}"
    return line


def tally(flags: Iterable[tuple], today: Optional[str] = None) -> dict:
    """Counts over ``(flag, checked)`` pairs: one per instrument found."""
    out = {"revoked": 0, "revoked_undated": 0, "revoked_later": 0, "partly": 0, "qualified": 0,
           "none": 0, "unchecked": 0}
    for flag, checked in flags:
        if checked is None:
            out["unchecked"] += 1
        else:
            out[category(flag, today)] += 1
    return out
