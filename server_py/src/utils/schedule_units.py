"""Schedules and annexes: what a whole-text read carries (FIX_PLAN P3.27) and
the code route to one named unit a section search did not return (P3.12).

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

**P3.12, the defect.** LEX holds a schedule or an annex as ONE provision
(`/schedule/B1`, `/annex/XIV`): there is no `/schedule/B1/paragraph/43` to rank,
and the section search does not reliably reach the unit by name (batch 7 B:
a schedule asked for by its name was not in the top 50 for its Act). P3.12's
Worker searched for one paragraph eighteen times; on P3.2's control turn the
annex chapter came back from a section search in 2 of 15 reps. So when a
section search's query names a schedule or annex unit the results lack, code
fetches the instrument's provisions by `/legislation/section/lookup` (which
returns every provision with its text), picks the unit by `uri`, and hands it
over: an annex chapter cut at its heading (`cut_annex`, 112 of 112 live
chapters); a schedule paragraph cut only where its `Section N)` line is unique
AND the next headed paragraph is N+1 (348 of 440 live), otherwise labelled with
the paragraphs the cut runs through; otherwise the whole unit, summarised for
the query when it is large (P1.6's pattern). A unit the provision list does not
hold is said in code (Invariant 1: the negative is true, and attributed to the
index, not to a search limit). The HTTP calls are in `agent/tools/executor.py`
and the orchestration in `agent_shared.py`; this module is the pure part.

**Every block here is addressed to the Worker.** Each sits in a tool result and
is stripped from an answer by `search_scope.strip_scope_blocks`
(`_FETCHED_BLOCK`, `_TOOL_BLOCK`). No header carries a square bracket inside it,
and the wording is screened against every answer detector in
`tools/replay_report.py` (`tests/test_search_scope.py::
test_footer_trips_no_detector`).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "SCHEDULE_TEXT_START",
    "INCLUDE_SCHEDULES_KEY",
    "mark_schedule_boundary",
    "schedule_headings",
    "schedules_note",
    "full_text_of",
    "ScheduleUnit",
    "named_units",
    "unit_in_results",
    "pick_provision",
    "unit_inventory",
    "cut_annex",
    "cut_schedule_paragraph",
    "cut_unit_from_text",
    "paragraph_label",
    "fetched_block",
    "unit_absent_line",
    "unit_without_text_line",
    "instrument_without_text_line",
    "fetch_failed_line",
    "provision_list_facts",
    "provision_list_sentence",
    "bare_schedule_action",
    "row_unit",
    "sole_schedule_reason",
    "BARE_ABSENT",
    "BARE_ONE",
    "cut_pieces",
    "paragraph_headings",
    "heading_matches",
    "matched_pieces",
    "MATCHED_CUTS_MIN_CHARS",
    "CUT",
    "WHOLE",
    "SUMMARY",
    "MATCHED",
    "FROM_LIST",
    "FROM_TEXT",
    "PARAGRAPH_CUT",
    "SPAN_CUT",
    "TO_THE_END",
    "NOT_CUT",
    "FETCHED_OPEN",
    "FETCHED_CLOSE",
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


# ---------------------------------------------------------------------------
# P3.12: the unit a section-search query names
# ---------------------------------------------------------------------------

@dataclass
class ScheduleUnit:
    """One schedule or annex unit a query names."""
    kind: str                       # "schedule" | "annex"
    label: str                      # "B1", "2", "XIV"
    paragraphs: tuple = ()          # ("42", "43", "44"), schedules only
    part: str = ""                  # a Part, Chapter or Head of a schedule
    chapter: str = ""               # an annex chapter numeral

    def display(self) -> str:
        word = "Schedule" if self.kind == "schedule" else "Annex"
        # An unlabelled unit is the instrument's own schedule ("the Schedule").
        return f"{word} {self.label}" if self.label else f"the {word}"


# The word is case-insensitive, the label is not: "Schedules 1 and 2" names
# Schedule 1 and "schedules to the Act" names nothing (batch 7 B's first draft
# read "Schedules" as "Schedule S").
_SCH_WORD = r"\b(?i:schedules?|sch(?:ed)?\.?)"
_SCH_LABEL = r"([A-Z]{0,3}\d{1,3}[A-Z]{0,4}|[A-Z]\d?)\b"
_SCH_RX = re.compile(_SCH_WORD + r"[ \t]*" + _SCH_LABEL)
_PARA_WORD = r"\b(?i:paragraphs?|paras?\.?|para\b|¶)"
_PNUM = r"\d{1,3}[A-Z]{0,2}"
# Batch 8 A2: a further number joined by spaces alone ("paragraphs 12 13 14",
# which the Worker writes as often as "12, 13 and 14"). Read only as a whole
# token: never the start of a longer number, a year or a citation ("1990",
# "2009/12", "1.5"), and never a day of a date or a count ("1 April",
# "14 days", "5 per cent"). `_paragraphs` also stops such a run where it stops
# ascending.
_NOT_A_PARA_NEXT = (
    r"[ \t]+(?i:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|"
    r"days?|weeks?|months?|years?|hours?|minutes?|per|percent)\b"
)
_SPACE_PNUM = (r"[ \t]+" + _PNUM + r"(?:\([^)]{1,6}\))*"
               r"(?![0-9A-Za-z/%]|[.:]\d|[ \t]*%|" + _NOT_A_PARA_NEXT + r")")
_PARA_RX = re.compile(
    _PARA_WORD + r"[ \t]*(" + _PNUM + r"(?:\([^)]{1,6}\))*"
    r"(?:[ \t]*(?:,|and|to|-|–|&)[ \t]*(?:and[ \t]+)?" + _PNUM + r"(?:\([^)]{1,6}\))*"
    r"|" + _SPACE_PNUM + r")*)"
)
_SCH_PART_RX = re.compile(
    _SCH_WORD + r"[ \t]*[A-Z]{0,3}\d{1,3}[A-Z]{0,4}[ \t,]+"
    r"(?i:part|chapter|head)[ \t]+([A-Z0-9]{1,6})\b"
)
# The word alone, singular ("the Schedule", "schedule of fees"): `\b` after it
# keeps the plural ("schedules to the Act") out. Read only where the query
# names no labelled schedule (user decision, 2026-10-06, batch 8 A decision 1).
_SCH_BARE_RX = re.compile(r"\b(?i:schedule)\b")
_ANNEX_RX = re.compile(r"\b(?i:annex)[ \t]+([IVXLC]{1,7}|\d{1,3})\b")
_CHAPTER_RX = re.compile(r"\b(?i:chapter)[ \t]+([IVXL]{1,6})\b")
_MAX_PARAGRAPHS = 4
_MAX_UNITS = 2


def _expand_range(a: str, b: str) -> list:
    if a.isdigit() and b.isdigit() and 0 < int(b) - int(a) <= 6:
        return [str(i) for i in range(int(a), int(b) + 1)]
    return [a, b]


def _space_run(piece: str) -> list:
    """A run of paragraph numbers joined by spaces alone ("12 13 14", or
    "12 13 to 15"), read only while it ascends: a number that does not follow
    the one before it ends the run, so a stray number never joins it."""
    out, prev = [], None
    for m in re.finditer(rf"({_PNUM})(?:[ \t]*(?:to|-|–)[ \t]*({_PNUM}))?", piece):
        first = int(re.match(r"\d+", m.group(1)).group())
        if prev is not None and first <= prev:
            break
        items = _expand_range(m.group(1), m.group(2)) if m.group(2) else [m.group(1)]
        out.extend(items)
        prev = int(re.match(r"\d+", items[-1]).group())
    return out


def _paragraphs(query: str) -> tuple:
    """The schedule paragraph numbers a query names, ranges expanded, capped."""
    out = []
    for m in _PARA_RX.finditer(query):
        body = re.sub(r"\([^)]{1,6}\)", "", m.group(1))
        for p in re.split(r"[ \t]*(?:,|&|\band\b)[ \t]*", body):
            p = p.strip()
            if not p:
                continue
            rng = re.fullmatch(rf"({_PNUM})[ \t]*(?:to|-|–)[ \t]*({_PNUM})", p)
            if rng:
                out.extend(_expand_range(rng.group(1), rng.group(2)))
                continue
            if re.fullmatch(_PNUM, p):
                out.append(p)
                continue
            out.extend(_space_run(p))
    seen = []
    for p in out:
        if p not in seen:
            seen.append(p)
    return tuple(seen[:_MAX_PARAGRAPHS])


def named_units(query: Any) -> list:
    """Every schedule or annex unit `query` names, as `ScheduleUnit`s, at most
    `_MAX_UNITS`. A paragraph number (or a Part) is attached to a schedule only
    when the query names exactly one schedule, an annex chapter only when it
    names exactly one annex: the model quotes "Schedule X" and "paragraph N"
    separately as often as together (batch 6 D's hand-read). Never raises.
    """
    try:
        q = str(query or "")
        if not q:
            return []
        sched_labels, annex_labels = [], []
        for m in _SCH_RX.finditer(q):
            if m.group(1) not in sched_labels:
                sched_labels.append(m.group(1))
        for m in _ANNEX_RX.finditer(q):
            if m.group(1) not in annex_labels:
                annex_labels.append(m.group(1))
        one_sched = len(sched_labels) == 1
        paras = _paragraphs(q) if one_sched else ()
        part_m = _SCH_PART_RX.search(q) if one_sched else None
        units = [ScheduleUnit("schedule", lab, paragraphs=paras,
                              part=part_m.group(1) if part_m else "")
                 for lab in sched_labels]
        # P3.12, decision 1: "the Schedule" with no label. The route acts on it
        # only where the provision list holds no schedule or annex, or exactly
        # one schedule (`bare_schedule_action`).
        if not sched_labels and _SCH_BARE_RX.search(q):
            units.append(ScheduleUnit("schedule", ""))
        ch = _CHAPTER_RX.search(q) if len(annex_labels) == 1 else None
        units += [ScheduleUnit("annex", lab, chapter=ch.group(1) if ch else "")
                  for lab in annex_labels]
        return units[:_MAX_UNITS]
    except Exception:
        return []


def _url_of(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("url") or row.get("uri") or row.get("id") or "").strip().rstrip("/")


def _seg(unit: ScheduleUnit) -> str:
    return "schedule" if unit.kind == "schedule" else "annex"


def _is_sole_unit_url(url: str, unit: ScheduleUnit) -> bool:
    """An unnumbered `/schedule` (or `/annex`): legislation.gov.uk writes an
    instrument's only schedule without a number. It answers a query naming
    Schedule 1 (or Annex I, Annex 1)."""
    return (url.lower().endswith(f"/{_seg(unit)}")
            and unit.label.upper() in ("1", "I"))


def unit_in_results(data: Any, unit: ScheduleUnit) -> Optional[bool]:
    """Did this section search return the unit? None when the result is not a
    list of rows (an error), so the caller does nothing. Never raises."""
    try:
        d = data
        if isinstance(data, str):
            d, _ = json.JSONDecoder().raw_decode(data.lstrip())
        rows = d.get("results") if isinstance(d, dict) else d
        if not isinstance(rows, list):
            return None
        if not unit.label:
            # "the Schedule": any schedule row in the results answers it.
            return any(re.search(r"/schedule(?:/[^/]+)?$", _url_of(r), re.I) for r in rows)
        want = f"/{_seg(unit)}/{unit.label}".lower()
        return any(_url_of(r).lower().endswith(want) or _is_sole_unit_url(_url_of(r), unit)
                   for r in rows)
    except Exception:
        return None


def pick_provision(rows: Any, unit: ScheduleUnit) -> Optional[dict]:
    """The unit's row from a `/legislation/section/lookup` list, by `uri`: an
    exact `/schedule/<label>` (or `/annex/<label>`), case-insensitive; else, for
    Schedule 1 or Annex I, the instrument's only, unnumbered one, where it has
    no numbered one. None otherwise."""
    if not isinstance(rows, list):
        return None
    want = f"/{_seg(unit)}/{unit.label}".lower()
    for r in rows:
        if _url_of(r).lower().endswith(want):
            return r
    numbered = [r for r in rows if re.search(rf"/{_seg(unit)}/[^/]+$", _url_of(r), re.I)]
    if not numbered:
        for r in rows:
            if _is_sole_unit_url(_url_of(r), unit):
                return r
    return None


BARE_ABSENT, BARE_ONE = "absent", "one"


def bare_schedule_action(rows: Any, complete: bool) -> tuple:
    """What the route does for "the Schedule" with no label, from the
    provision list: `(BARE_ABSENT, None)` where the complete list holds no
    schedule or annex row (the true negative, stated in code);
    `(BARE_ONE, row)` where it holds exactly one schedule row (handed over
    whole, as for "Schedule 1"); `(None, None)` otherwise. With two or more
    schedules the query does not say which, so nothing is guessed; with
    annexes and no schedule, "the Schedule" is not obviously any of them; a
    list cut short says nothing about absence."""
    if not isinstance(rows, list):
        return None, None
    scheds = [r for r in rows if re.search(r"/schedule(?:/[^/]+)?$", _url_of(r), re.I)]
    annexes = [r for r in rows if re.search(r"/annex(?:/[^/]+)?$", _url_of(r), re.I)]
    if not scheds and not annexes:
        return (BARE_ABSENT, None) if complete else (None, None)
    if len(scheds) == 1:
        return BARE_ONE, scheds[0]
    return None, None


def row_unit(row: dict) -> "ScheduleUnit":
    """The unit a schedule row is, from its uri: "Schedule 3" or "the Schedule"."""
    m = re.search(r"/schedule(?:/([^/]+))?$", _url_of(row), re.I)
    return ScheduleUnit("schedule", _clean(m.group(1), 12) if m and m.group(1) else "")


def sole_schedule_reason(lid: str) -> str:
    """Said after the tail when "the Schedule" was handed over."""
    return f"It is the only schedule the index holds for {_clean(lid, 60)}."


def unit_inventory(rows: Any) -> list:
    """The schedules and annexes a provision list holds, in its own order:
    "Schedule 2", "the Schedule", "Annex XIV"."""
    out = []
    for r in rows if isinstance(rows, list) else []:
        m = re.search(r"/(schedule|annex)(?:/([^/]+))?$", _url_of(r), re.I)
        if not m:
            continue
        word = "Schedule" if m.group(1).lower() == "schedule" else "Annex"
        name = f"{word} {m.group(2)}" if m.group(2) else f"the {word}"
        if name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# P3.12: cutting the unit out of its text
# ---------------------------------------------------------------------------

# Moved here from `tools/provision_hints.py` (Session 31's dev tool, which now
# delegates to it), unchanged in behaviour: LEX renders a heading run into its
# title ("CHAPTER XIGeneral ...", "Section 3Specific ..."), so a numeral is
# ended by a non-numeral or by a capital followed by a lower-case letter, never
# by a word boundary.
_ROMAN_END = r"(?=[^IVXL]|[IVXL][a-z]|$)"


def cut_annex(text: str, chapter: str = "", section: str = "") -> tuple:
    """(slice, how). A chapter is cut on its upper-case heading, to the next
    chapter heading; a section only where its heading occurs once in the
    chapter span. `how`: "whole annex", "chapter cut", "chapter heading
    absent", with ", section cut" or ", section heading xN" after it."""
    text = text or ""
    span, how = text, "whole annex"
    if chapter:
        m = re.search(rf"\bCHAPTER\s*{chapter}{_ROMAN_END}", text)
        if m:
            nxt = re.search(rf"\bCHAPTER\s*[IVXL]+{_ROMAN_END}", text[m.end():])
            span = text[m.start(): m.end() + (nxt.start() if nxt else len(text))]
            how = "chapter cut"
        else:
            how = "chapter heading absent"
    if section:
        hits = list(re.finditer(rf"Section\s*{section}(?=\s*[A-Z])", span))
        if len(hits) == 1:
            nxt = re.search(r"Section\s*\d+(?=\s*[A-Z])", span[hits[0].end():])
            span = span[hits[0].start(): hits[0].end() + (nxt.start() if nxt else len(span))]
            how = (how + ", section cut") if how == "chapter cut" else "section cut"
        else:
            how += f", section heading x{len(hits)}"
    return span, how


# A schedule paragraph's own heading line, "Section 43) **...**" at a line
# start (LEX writes "Section" for a schedule paragraph). Un-headed paragraphs
# are rendered bare ("44) ..."), like sub-paragraphs, so they cannot be told
# apart and are never cut on (batch 6 D: a bare marker is unique for only 106
# of 397).
_SEC_LINE = re.compile(r"(?m)^[ \t]*Section\s+(\d{1,3})([A-Z]{0,3})\)")
PARAGRAPH_CUT = "paragraph cut"
SPAN_CUT = "span cut"
TO_THE_END = "to the end"
NOT_CUT = "no unique heading"


def _split_label(label: str) -> tuple:
    m = re.fullmatch(r"(\d{1,3})([A-Z]{0,3})", str(label or "").strip().upper())
    return (int(m.group(1)), m.group(2)) if m else (None, "")


def cut_schedule_paragraph(text: str, label: str) -> tuple:
    """(slice, how, through) for paragraph `label` of a schedule's text.

    * PARAGRAPH_CUT: its `Section N)` line is unique and the next headed
      paragraph is N+1 (or a lettered insert after N), so the slice is exactly
      paragraph N (batch 7 B: 348 of 440 live paragraphs);
    * SPAN_CUT: unique, but the next headed paragraph comes later, so the slice
      also holds the un-headed paragraphs between; `through` is the last
      paragraph it runs through (None if the numbering restarts);
    * TO_THE_END: unique and the last headed paragraph: the slice runs to the
      end of the schedule;
    * NOT_CUT: no unique heading line; the slice is None.
    """
    text = text or ""
    n, suf = _split_label(label)
    if n is None:
        return None, NOT_CUT, None
    hits = [m for m in _SEC_LINE.finditer(text) if int(m.group(1)) == n and m.group(2) == suf]
    if len(hits) != 1:
        return None, NOT_CUT, None
    m = hits[0]
    nxt = _SEC_LINE.search(text, m.end())
    if not nxt:
        return text[m.start():].strip(), TO_THE_END, None
    span = text[m.start():nxt.start()].strip()
    nn, ns = int(nxt.group(1)), nxt.group(2)
    if (nn == n + 1 and not ns) or (nn == n and ns > suf):
        return span, PARAGRAPH_CUT, None
    through = nn if ns else nn - 1
    return span, SPAN_CUT, (through if through > n else None)


def cut_unit_from_text(full_text: str, unit: ScheduleUnit) -> Optional[str]:
    """The unit's own text out of a whole text with its schedules appended,
    from its heading to the next schedule or annex heading. P3.12's fallback
    when the provision list does not come back. None when the heading is
    absent or met more than once."""
    try:
        text = full_text or ""
        hits = []
        for rx in (_HEADING, _HEADING_MIXED):
            for m in rx.finditer(text):
                kind, label, _ = _heading_label(m)
                hits.append((m.end() - len(m.group(0).lstrip()), kind, label))
        hits.sort()
        want = [i for i, h in enumerate(hits)
                if h[1] == unit.kind and h[2].upper() == unit.label.upper()]
        if len(want) != 1:
            return None
        i = want[0]
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        return text[hits[i][0]:end].strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# P3.12: the block
# ---------------------------------------------------------------------------

# Delimited, like P3.11's outline, because the body is retrieved statutory text
# and may carry a square bracket; the header, the piece labels and the closer
# carry none. `search_scope.strip_scope_blocks` removes the block whole if a
# model echoes it, and `_TOOL_BLOCK` a stray header or closer.
FETCHED_OPEN = "[PROVISION FETCHED BY CODE — "
FETCHED_CLOSE = "[/PROVISION FETCHED BY CODE]"


def _clean(text: str, cap: int = 200) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip().replace("[", "(").replace("]", ")")
    return s[:cap]


def paragraph_label(unit: ScheduleUnit, para: str, how: str, through: Optional[int]) -> str:
    """The one-sentence label put before a cut paragraph, by how it was cut."""
    name = unit.display()
    if how == PARAGRAPH_CUT:
        return f"Paragraph {para} of {name}, cut at its own heading and the next one:"
    if how == SPAN_CUT and through is not None:
        return (f"The text of {name} from the heading of paragraph {para} to the next "
                f"headed paragraph. It runs through paragraphs {para} to {through}, "
                f"because the paragraphs after {para} in it carry no heading of their own:")
    if how == SPAN_CUT:
        return (f"The text of {name} from the heading of paragraph {para} to the next "
                f"headed paragraph, which may hold more than paragraph {para}:")
    return (f"The text of {name} from the heading of paragraph {para} to its end, "
            "which may hold later paragraphs that carry no heading of their own:")


CUT, WHOLE, SUMMARY = "cut", "whole", "summary"
FROM_LIST, FROM_TEXT = "list", "text"


def cut_pieces(unit: ScheduleUnit, text: str) -> tuple:
    """`(pieces, how, reason)` for one unit's text, before any size rule.

    * an annex chapter, cut at its heading (`cut_annex`): CUT;
    * schedule paragraphs, each cut by `cut_schedule_paragraph`: CUT, only
      when every named paragraph has a unique heading line; one that has none
      sends the whole schedule instead, with the reason said;
    * anything else (the unit alone, a schedule Part, a chapter heading the
      annex lacks): WHOLE.
    """
    text = str(text or "")
    if unit.kind == "annex" and unit.chapter:
        span, how = cut_annex(text, unit.chapter)
        if how == "chapter cut":
            label = (f"Chapter {unit.chapter} of {unit.display()}, cut at its heading "
                     "and the next chapter's heading:")
            return [(label, span)], CUT, ""
        return [("", text)], WHOLE, f"It carries no heading for Chapter {unit.chapter} to cut at."
    if unit.kind == "schedule" and unit.paragraphs:
        pieces, uncut = [], []
        for p in unit.paragraphs:
            span, how, through = cut_schedule_paragraph(text, p)
            if how == NOT_CUT:
                uncut.append(p)
            elif all(span != s for _, s in pieces):
                pieces.append((paragraph_label(unit, p, how, through), span))
        if pieces and not uncut:
            return pieces, CUT, ""
        names = _and_join(uncut)
        reason = (f"Paragraph {names} has no single heading of its own in it to cut at."
                  if len(uncut) == 1 else
                  f"Paragraphs {names} have no single heading of their own in it to cut at.")
        return [("", text)], WHOLE, reason
    return [("", text)], WHOLE, ""


# ---------------------------------------------------------------------------
# Batch 10 A (P3.12's next lever, user decision 2026-10-07): a schedule too
# large to hand over whole, whose query names no paragraph
# ---------------------------------------------------------------------------
#
# Session 41's sweep: no Manager brief named the paragraphs the question needed,
# every Worker query named the Schedule alone, so the route handed over the
# whole 92,066-character Schedule summarised for the question, and the summary
# kept some paragraphs and dropped others. Measured over every stored route
# call (`notes/batch10_A.md`): every query that reached that summary on a
# schedule with paragraph headings shares a word with the headings of the
# paragraphs it needed. So, for such a schedule, the Worker gets its paragraph
# headings (number and heading, in order) and the paragraphs whose heading
# shares a distinctive word with the section search's own query, each cut by
# `cut_schedule_paragraph`'s rules. Today's summary stays where nothing
# matches, a matched paragraph cannot be cut, or the cuts exceed the bound.

MATCHED = "matched"
# The bound on the cut text handed over verbatim: the verbatim threshold, or
# this, whichever is larger. At the 8,000-character fallback threshold (every
# stored replay; any model whose context length is unknown) the largest
# query-matched set on a stored call is 8,494 characters (six paragraphs) and
# the smallest that must not pass, under the any-word rule this module does not
# use, is 18,756 (fifteen paragraphs).
MATCHED_CUTS_MIN_CHARS = 12_000
# A query word in more of the unit's headings than this is not distinctive.
_MAX_HEADINGS_PER_WORD = 3
_MAX_HEADINGS_LISTED = 150
_HEADING_CHARS = 120
# A paragraph's heading line, "Section 4) **Widget fees**": the same line
# `_SEC_LINE` cuts at, with the heading words between the asterisks.
_HEADING_TEXT = re.compile(
    r"(?m)^[ \t]*Section\s+(\d{1,3})([A-Z]{0,3})\)[ \t]*(?:\*\*([^\n]*?)\*\*)?")
_QUERY_STOP = frozenset("""
a an the of and or to in on for by with under from at as be is are was were any other its
it their this that these those which where when what who how not no nor into onto upon
about after before between within without than then there such each all some more most may
must shall will would can could should does did has have had act acts order orders rule rules
regulation regulations schedule schedules sch sched annex annexes paragraph paragraphs para
paras part parts chapter chapters section sections provision provisions subparagraph article
articles text full
""".split())


def paragraph_headings(text: str) -> list:
    """[(number, heading)] for every `Section N) **heading**` line of a
    schedule's text, in order. The heading is cleaned (no square bracket,
    whitespace collapsed) and capped; "" where the line carries none."""
    return [(m.group(1) + m.group(2), _clean(m.group(3) or "", _HEADING_CHARS))
            for m in _HEADING_TEXT.finditer(str(text or ""))]


def _word_stems(text: str, drop: frozenset = frozenset()) -> set:
    """Lower-case words of three letters or more, stop words and `drop` out,
    a plural ending taken off ("licences" -> "licence")."""
    out = set()
    for w in re.findall(r"[a-z]+", str(text or "").lower()):
        if len(w) <= 2 or w in _QUERY_STOP or w in drop:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def heading_matches(headings: list, query: Any, unit: ScheduleUnit) -> list:
    """The numbers of the headings that share a distinctive word with `query`,
    in order. A query word is distinctive when it is in at most
    `_MAX_HEADINGS_PER_WORD` of the unit's headings; the unit's own label is
    not a query word."""
    label = frozenset(re.findall(r"[a-z]+", unit.label.lower()))
    words = [_word_stems(h) for _, h in headings]
    freq = Counter(w for ws in words for w in ws)
    wanted = {w for w in _word_stems(query, label) if 1 <= freq[w] <= _MAX_HEADINGS_PER_WORD}
    return [num for (num, _), ws in zip(headings, words) if ws & wanted]


def _heading_list_piece(unit: ScheduleUnit, headings: list) -> tuple:
    shown = headings[:_MAX_HEADINGS_LISTED]
    lines = [f"{num}: {h or '(untitled)'}" for num, h in shown]
    if len(headings) > len(shown):
        lines.append(f"and {len(headings) - len(shown)} more headings after paragraph "
                     f"{shown[-1][0]}")
    label = (f"The paragraph headings of {unit.display()}, in order, each after the "
             "number of the paragraph it opens:")
    return label, "\n".join(lines)


def matched_pieces(unit: ScheduleUnit, text: str, query: Any, bound: int) -> Optional[list]:
    """`[(label, text)]` for a schedule too large to hand over whole whose
    query names no paragraph: its heading list first, then each paragraph
    whose heading shares a distinctive word with `query`, cut and labelled by
    `cut_schedule_paragraph`'s rules (`paragraph_label`). None, so the caller
    summarises as before, where the unit is not a schedule or names a
    paragraph or a chapter, it carries no heading line, nothing matches, a
    matched paragraph cannot be cut (its heading line is not unique), or the
    cuts together exceed `bound`. Never raises."""
    try:
        if unit.kind != "schedule" or unit.paragraphs or unit.chapter:
            return None
        text = str(text or "")
        headings = paragraph_headings(text)
        if not headings:
            return None
        cuts = []
        for num in heading_matches(headings, query, unit):
            span, how, through = cut_schedule_paragraph(text, num)
            if how == NOT_CUT:
                return None
            if all(span != s for _, s in cuts):
                cuts.append((paragraph_label(unit, num, how, through), span))
        if not cuts or sum(len(s) for _, s in cuts) > bound:
            return None
        return [_heading_list_piece(unit, headings)] + cuts
    except Exception:
        return None


def fetched_block(lid: str, unit: ScheduleUnit, url: str, pieces: list, how: str,
                  reason: str = "", total_chars: int = 0, source: str = FROM_LIST,
                  summary_of: str = WHOLE) -> str:
    """The block handed to the Worker. `pieces` is [(label, text)]. `how` is
    CUT (each piece labelled), WHOLE (the unit verbatim), MATCHED (batch 10
    A: the heading list and the query-matched paragraphs, each labelled) or
    SUMMARY (the unit, or with `summary_of=CUT` the cut, summarised for the
    query). `source` is FROM_LIST (the provision list) or FROM_TEXT (P3.12's
    fallback: cut out of the whole text because the provision list did not
    come back). `reason` says why a named sub-unit was not cut. One block per
    unit.

    Batch 10 A: the summarised tail used to end "The summary is not the
    statutory text: quote the provision only from retrieved text", and in
    Session 41's sweep a Worker reported the summarised paragraphs as "not
    retrieved". It now says that code retrieved the unit and that the summary
    is a condensed reading of that retrieved text, with no "not" beside
    "retrieved"."""
    lid_c, name = _clean(lid, 60), unit.display()
    where = f" (url: {_clean(url, 160)})" if url else ""
    if source == FROM_TEXT:
        lead = (f"the index's provision list for {lid_c} did not come back, so code "
                f"cut {name} out of the instrument's whole text with its schedules, at "
                f"its heading and the next schedule or annex heading.")
    else:
        lead = (f"the index holds {name} of {lid_c} as one provision{where}. This "
                "search's results left it out, so code fetched it from the index's "
                "provision list.")
    if how == SUMMARY:
        if summary_of == CUT:
            tail = (f" Code retrieved the whole of {name} and cut out the parts of it this "
                    f"search named, {total_chars:,} characters, and below is a summary of "
                    "those retrieved parts, condensed for this research question.")
        else:
            tail = (f" Code retrieved the whole of {name}, {total_chars:,} characters, and "
                    "below is a summary of that retrieved text, condensed for this research "
                    "question.")
        tail += (f" A paragraph the summary leaves out is still part of the retrieved "
                 f"{name}. Cite {name} for what the summary says, and quote its words only "
                 "from text shown verbatim.")
    elif how == MATCHED:
        tail = (f" {name} runs to {total_chars:,} characters, longer than one result hands "
                "over whole, so below are its paragraph headings, in order, and then each "
                "paragraph whose heading shares a word with this search's query, cut from "
                "the retrieved text and labelled. To read another headed paragraph in its "
                f"own words, name {name} and its number from the list below in a section "
                "search: code cuts it out the same way.")
    elif how == WHOLE:
        tail = f" Below is the whole of {name}."
    else:
        tail = " Below is the part of it this search named, labelled."
    if reason:
        tail += f" {reason}"
    body = []
    for label, text in pieces:
        body.append((label + "\n" if label else "") + str(text or "").strip())
    return (f"\n\n{FETCHED_OPEN}{lead}{tail}]\n" + "\n\n".join(body) + f"\n{FETCHED_CLOSE}")


def unit_absent_line(lid: str, unit: ScheduleUnit, rows: list, complete: bool) -> str:
    """The line for a unit the provision list does not hold. A definite
    statement about the index only when the list came back complete
    (Invariant 1: a true negative, stated in code); otherwise it says the
    question is open."""
    lid_c, name = _clean(lid, 60), unit.display()
    if not complete:
        return (f"\n\n{FETCHED_OPEN}whether the index holds {name} of {lid_c} is open: "
                f"code fetched only the first {len(rows):,} provisions of its list, and "
                f"{name} was not among them.]")
    # The labels come from LEX's own uris, so they are cleaned like the id:
    # a bracket in one would end `_TOOL_BLOCK`'s match early (batch 8 review).
    inv = [_clean(name, 40) for name in unit_inventory(rows)]
    return (f"\n\n{FETCHED_OPEN}the index holds {len(rows):,} provisions for {lid_c}, "
            f"and {_held_clause(inv)}: {name} is not one of them. This search's results "
            "left it out for that reason.]")


def _held_clause(inv: list, cap: Optional[int] = None) -> str:
    """What a complete provision list holds besides its sections: "its
    schedules and annexes among them are ..." or "none of them is a schedule
    or an annex". With `cap`, at most that many names, then "and N more"."""
    if not inv:
        return "none of them is a schedule or an annex"
    names = list(inv)
    if cap is not None and len(names) > cap:
        names = names[:cap] + [f"{len(inv) - cap} more"]
    return f"its schedules and annexes among them are {_and_join(names)}"


# ---------------------------------------------------------------------------
# Batch 8 A2: what a complete code-read provision list establishes when P3.1's
# section-search cap stops a Worker on that instrument
# ---------------------------------------------------------------------------
#
# In the sweep (Session 40) a Worker was told in code, correctly, that the
# index holds no schedule for an instrument (the P3.12 line above), kept
# searching it, hit P3.1's cap, and the cap's text ("may still be in it") won:
# the answers put the missing Schedule down to the limit. Where code has read
# the instrument's COMPLETE provision list in the same worker run, the cap's
# refusal, the scope block's limb and the lawyer's footer clause now say what
# that list established. A list cut short, failed or without text says
# nothing new (`provision_list_facts` returns None).

_MAX_HELD_NAMED = 8


def provision_list_facts(outcome: Any) -> Optional[dict]:
    """`{"provisions": N, "units": [...]}` from a provision-list outcome
    (`executor.fetch_provision_list`) that came back COMPLETE with rows; None
    for anything else. Never raises."""
    try:
        if not isinstance(outcome, dict) or outcome.get("status") != "ok" \
                or outcome.get("complete") is not True:
            return None
        rows = outcome.get("rows")
        if not isinstance(rows, list) or not rows:
            return None
        return {"provisions": len(rows),
                "units": [_clean(n, 40) for n in unit_inventory(rows)][:_MAX_LISTED]}
    except Exception:
        return None


def provision_list_sentence(lid: str, facts: dict) -> str:
    """"the index holds N provisions for <lid>, and none of them is a
    schedule or an annex" (or names its schedules and annexes). No full stop,
    no bracket. "" when `facts` is not usable."""
    try:
        n = int(facts["provisions"])
        units = [str(u) for u in (facts.get("units") or [])]
    except Exception:
        return ""
    return (f"the index holds {n:,} provisions for {_clean(lid, 60)}, "
            f"and {_held_clause(units, cap=_MAX_HELD_NAMED)}")


def unit_without_text_line(lid: str, unit: ScheduleUnit) -> str:
    return (f"\n\n{FETCHED_OPEN}the index lists {unit.display()} of {_clean(lid, 60)} "
            "as a provision and holds no text for it.]")


def instrument_without_text_line(lid: str, unit: ScheduleUnit) -> str:
    return (f"\n\n{FETCHED_OPEN}the index holds {_clean(lid, 60)} without its "
            f"provision text, so it holds none for {unit.display()} either.]")


def fetch_failed_line(lid: str, unit: ScheduleUnit) -> str:
    name = unit.display()
    return (f"\n\n{FETCHED_OPEN}the index's provision list for {_clean(lid, 60)} did "
            f"not come back, so code could fetch {name} neither from it nor from the "
            f"whole text. Whether the index holds {name} is open: do not report it "
            "as absent.]")
