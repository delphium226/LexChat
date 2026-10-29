"""P3.56: one Sources-rail entry for one provision whose two URLs differ only in form.

A section search's source carries `http://www.legislation.gov.uk/<id>` (or
`.../id/<id>`), titled "Act, s.N"; the same provision reached by another route
(another Worker step, a text read, P4.24's URL for an entry that had none)
carries `https://www.legislation.gov.uk/id/<id>`, cited "<id>, s.N". The
accumulator's `_is_duplicate_source` compares URLs exactly, so the rail showed
both: 9 such pairs over P1.7's and P3.46's stored sweeps, each the same
provision under the same heading (`evidence/seam/s51/p356_build`).

Two entries are one when their legislation.gov.uk URLs are equal after the
scheme, a `www.` and an `/id/` segment are set aside, their `sub` (the
provision's heading) is equal, and their provision numbers taken from `cite`
are equal or one has none. Distinct provisions of one instrument stay apart,
as does a change-record entry (its `sub` describes the change). The richer
entry is kept, in the first entry's place, with the https URL where either had
one and any field it lacked taken from the other.

Pure, deterministic, never raises: on any failure the rail is returned
unchanged, and a rail with no such pair is returned as the same list.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_LEG_URL = re.compile(r"^https?://(?:www\.)?legislation\.gov\.uk/(?:id/)?(.+?)/*$", re.I)
# The provision a `cite` ends with: "Act 1996, s.202", "ssi/2004/520, s.10",
# "..., reg. 4", "..., Sch. 2".
_CITE_PROVISION = re.compile(
    r",\s*((?:s|reg|regs|art|para|rule|sch)\.?\s*[\w().-]+)\s*$", re.I)


def _key(src: dict):
    """(path, heading) for a legislation.gov.uk source, else None."""
    if not isinstance(src, dict):
        return None
    m = _LEG_URL.match(str(src.get("url") or "").strip())
    if not m:
        return None
    return m.group(1).lower(), str(src.get("sub") or "").strip().casefold()


def _provision(src: dict) -> str:
    m = _CITE_PROVISION.search(str(src.get("cite") or ""))
    return re.sub(r"[\s.]", "", m.group(1)).lower() if m else ""


def _same(a: dict, b: dict) -> bool:
    pa, pb = _provision(a), _provision(b)
    return not pa or not pb or pa == pb


def _richness(src: dict) -> int:
    return sum(1 for k, v in src.items() if not str(k).startswith("_") and k != "n" and v)


def _merge(first: dict, other: dict) -> dict:
    keep, drop = (first, other) if _richness(first) >= _richness(other) else (other, first)
    out = dict(keep)
    for k, v in drop.items():
        if v and not out.get(k):
            out[k] = v
    urls = [str(s.get("url") or "") for s in (keep, drop)]
    https = [u for u in urls if u.lower().startswith("https://")]
    if https:
        out["url"] = https[0]
    return out


def collapse_scheme_duplicates(rail: list) -> tuple:
    """Returns (rail, collapsed): the rail with each such pair made one entry,
    and how many entries were removed. The same list when none was."""
    try:
        if not rail or len(rail) < 2:
            return rail, 0
        out: list = []
        index: dict = {}          # key -> positions in `out`
        removed = 0
        for src in rail:
            k = _key(src)
            hit = None
            if k is not None:
                for pos in index.get(k, ()):
                    if _same(out[pos], src):
                        hit = pos
                        break
            if hit is None:
                if k is not None:
                    index.setdefault(k, []).append(len(out))
                out.append(src)
            else:
                out[hit] = _merge(out[hit], src)
                removed += 1
        return (out, removed) if removed else (rail, 0)
    except Exception as e:  # Invariant 5: the rail is never worth a failed answer
        logger.warning("[Sources] Rail duplicate collapse skipped: %s", e)
        return rail, 0
