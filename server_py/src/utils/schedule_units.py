"""Schedules and annexes: what a whole-text read carries (FIX_PLAN P3.27).

**P3.27, the defect.** LEX's `/legislation/text` takes `include_schedules`,
default `false` ("only sections are returned"), and `get_legislation_text`
never sent it, so every whole-text read the product made left out every
schedule and annex and said nothing. Measured over the stored evidence (batch 7
B, `notes/batch7_B.md`): 98 of the 195 turns that read a whole text read one
whose schedules or annexes LEX holds; 23 turns needed such a unit, 14 of their
answers carry a negative about it, and LEX holds the unit in all 14. Live, the
flagged text is the unflagged text with the schedules appended (60 of 60), so
the executor makes both calls and the boundary is exact: the unflagged length.
One flagged call alone places it in only 22 of 27 (a heading inside the
sections, or schedule text with no heading). The line below is built from the
two raw responses, after summarisation (P2.3's `enabling_power_note` pattern),
and names only the schedules and annexes the text carries, or says the index
holds none for the instrument. It says nothing else: not what they contain,
and nothing about whether the instrument has schedules the index does not hold.

**Every block here is addressed to the Worker.** Each sits in a tool result and
is stripped from an answer by `search_scope.strip_scope_blocks`
(`_TOOL_BLOCK`). No header carries a square bracket inside it,
and the wording is screened against every answer detector in
`tools/replay_report.py` (`tests/test_search_scope.py::
test_footer_trips_no_detector`).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

__all__ = [
    "SCHEDULE_TEXT_START",
    "INCLUDE_SCHEDULES_KEY",
    "mark_schedule_boundary",
    "schedule_headings",
    "schedules_note",
    "full_text_of",
]

# ---------------------------------------------------------------------------
# P3.27: what a whole-text read carries
# ---------------------------------------------------------------------------

# Keys the executor adds to a `get_legislation_text` result (additive,
# Invariant 5). `SCHEDULE_TEXT_START` is the character offset in `full_text`
# where the appended schedule and annex text begins, which is the length of the
# unflagged text: equal to `len(full_text)` when the index holds none, and
# None when the unflagged call failed or its text was not a prefix of the
# flagged one, in which case the line says less.
INCLUDE_SCHEDULES_KEY = "include_schedules"
SCHEDULE_TEXT_START = "schedule_text_starts_at"


def full_text_of(resp: Any) -> Optional[str]:
    """`full_text` from a `/legislation/text` response, or None."""
    if isinstance(resp, list):
        resp = resp[0] if resp else None
    if isinstance(resp, dict) and isinstance(resp.get("full_text"), str):
        return resp["full_text"]
    return None


def mark_schedule_boundary(flagged: Any, unflagged: Any) -> Any:
    """Stamp the flagged response with where its schedule text starts.

    `flagged` is the `/legislation/text` response sent with
    `include_schedules: true`; `unflagged` the same call without it, or None
    when that call failed. Returns `flagged` (a dict gains the two keys; any
    other shape is returned untouched, and the line built from it says less).
    Never raises.
    """
    try:
        if not isinstance(flagged, dict):
            return flagged
        flagged[INCLUDE_SCHEDULES_KEY] = True
        text = full_text_of(flagged)
        base = full_text_of(unflagged) if unflagged is not None else None
        start = None
        if text is not None and base is not None and text.startswith(base):
            start = len(base)
        flagged[SCHEDULE_TEXT_START] = start
        return flagged
    except Exception:
        return flagged


_ORDINALS = (
    "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH",
    "NINTH", "TENTH", "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH",
    "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH", "EIGHTEENTH", "NINETEENTH",
    "TWENTIETH",
)
_ORD = "|".join(_ORDINALS)
# A heading opens a paragraph: at the start of the text searched, or after a
# blank line. Four forms, all seen in the 27 live texts that grow with the flag
# (batch 7 B): "SCHEDULE 1A ...", an unnumbered "SCHEDULE ..." (an
# instrument's only schedule), "SECOND SCHEDULE ...", and "ANNEX XIV ..." /
# "ANNEX ...". A numbered label must carry a digit (1, 1A, B1, ZA2, 4ZZA), so a
# title word after an unnumbered heading ("SCHEDULE APPEARANCE OF ...") is
# never read as a label. Upper case only, with one exception below: a
# mixed-case "Schedule" opens a cross-reference as often as a heading.
_PARA_START = r"(?:\A|\n[ \t]*\n)[ \t]*"
_HEADING = re.compile(
    _PARA_START
    + r"(?:(?P<ord>" + _ORD + r"|THE)\s+SCHEDULE\b"
    + r"|SCHEDULE[ \t]+(?P<num>[A-Z]{0,3}\d{1,3}[A-Z]{0,4})\b"
    + r"|(?P<bare>SCHEDULE)(?=[\s—–:.,-]|$)"
    + r"|ANNEX[ \t]+(?P<anum>[IVXLC]{1,7}|\d{1,3}|[A-Z])\b"
    + r"|(?P<abare>ANNEX)(?=[\s—–:.,-]|$))"
)
# Two real headings in the live texts are written "Schedule 4 Prosecution and
# ..." and "Schedule 5 Enactments Repealed ..."; the one false hit of that form
# is "Schedule 1. " ending a sentence. So a mixed-case heading needs its title:
# a space and a capitalised word straight after the label.
_HEADING_MIXED = re.compile(
    _PARA_START + r"Schedule[ \t]+(?P<num>[A-Z]{0,3}\d{1,3}[A-Z]{0,4})[ \t]+(?=[A-Z][a-z])"
)


def _heading_label(m: "re.Match") -> tuple:
    """(kind, label, display) for one heading match."""
    g = m.groupdict()
    if g.get("ord"):
        if g["ord"] == "THE":
            return "schedule", "", "the Schedule"
        return "schedule", g["ord"].lower(), f"the {g['ord'].capitalize()} Schedule"
    if g.get("num"):
        return "schedule", g["num"], f"Schedule {g['num']}"
    if g.get("bare"):
        return "schedule", "", "the Schedule"
    if g.get("anum"):
        return "annex", g["anum"], f"Annex {g['anum']}"
    return "annex", "", "the Annex"


def schedule_headings(text: str, start: int = 0) -> list:
    """Every schedule or annex heading in `text[start:]`, in order, first
    occurrence of each label only, as `[(offset, kind, label, display)]`.

    Offsets are into `text[start:]`. A label met twice (an amending schedule
    quoting a substituted heading, say) is listed once. Never raises.
    """
    try:
        seg = text[start:] if text else ""
        hits = []
        for rx in (_HEADING, _HEADING_MIXED):
            for m in rx.finditer(seg):
                kind, label, display = _heading_label(m)
                # The offset of the heading word, not of the blank line.
                off = m.end() - len(m.group(0).lstrip())
                hits.append((off, kind, label, display))
        hits.sort(key=lambda h: h[0])
        out, seen = [], set()
        for h in hits:
            key = (h[1], h[2])
            if key in seen:
                continue
            seen.add(key)
            out.append(h)
        return out
    except Exception:
        return []


_MAX_LISTED = 40
_SCHEDULES_OPEN = "[SCHEDULES AND ANNEXES — "


def _and_join(items: list) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _clean_id(lid: str) -> str:
    return re.sub(r"[\[\]]", "", str(lid or "").strip())[:60] or "this instrument"


def schedules_note(args: dict, data: Any) -> str:
    """P3.27's line on every `get_legislation_text` result, from the RAW result.

    Four cases, each a statement about this text and nothing else:
      * the schedule text was located and carries headings: they are named;
      * the index holds none for the instrument (flagged == unflagged);
      * schedule text follows the sections but carries no heading this
        recognises: that is said, without guessing a name;
      * the boundary is unknown (the second call failed, or its text was not a
        prefix of the first): the line says only that the text was requested
        with the schedules included. Less, never more (Invariant 5).
    "" for an error, or a result that is not a text record. Never raises.
    """
    try:
        d = data
        if isinstance(data, str):
            try:
                d, _ = json.JSONDecoder().raw_decode(data.lstrip())
            except ValueError:
                return ""
        if isinstance(d, list):
            d = d[0] if d else {}
        if not isinstance(d, dict) or d.get("error") or not d.get(INCLUDE_SCHEDULES_KEY):
            return ""
        text = full_text_of(d)
        if text is None:
            return ""
        lid = _clean_id((args or {}).get("legislation_id"))
        start = d.get(SCHEDULE_TEXT_START)
        if not isinstance(start, int) or not 0 <= start <= len(text):
            return (
                f"\n\n{_SCHEDULES_OPEN}this text of {lid} was requested with "
                "its schedules and annexes included, where the index holds "
                "them. Which ones it carries was not checked.]"
            )
        if not text[start:].strip():
            return (
                f"\n\n{_SCHEDULES_OPEN}the index holds no schedule or annex "
                f"text for {lid}, so this text is its sections only.]"
            )
        heads = schedule_headings(text, start)
        if not heads:
            return (
                f"\n\n{_SCHEDULES_OPEN}this text of {lid} carries, after its "
                "sections, further text that the index holds as schedule or "
                "annex text. It carries no schedule or annex heading.]"
            )
        names = [h[3] for h in heads]
        listed = names[:_MAX_LISTED]
        more = len(names) - len(listed)
        listed_phrase = _and_join(listed) + (f" and {more} more" if more else "")
        lead = text[start:start + heads[0][0]].strip()
        preceded = (
            " Some text with no schedule or annex heading comes before the first of them."
            if lead else ""
        )
        under = "this heading" if len(names) == 1 else "these headings"
        return (
            f"\n\n{_SCHEDULES_OPEN}this text of {lid} carries, after its "
            "sections, the schedule and annex text the index holds, under "
            f"{under}: {listed_phrase}.{preceded}]"
        )
    except Exception:
        return ""
