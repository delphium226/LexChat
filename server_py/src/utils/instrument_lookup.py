"""P3.7 (bucket B5): the held/absent test for an instrument named by number.

**Why this exists.** Four of the corpus's negatives are the same question: is
this instrument, named by number, in the index? 6409 turns 9-11 (SSI 2025/377)
and 6373 turn 2 (SSI 2026/170) were answered by `search_legislation`, a RANKED
keyword search. Absence from the top 5 of a median 141 matches is not absence
from the corpus, so the model could say only that it "could not be found", and
in the pre-pilot it then asked the lawyer to check a correct citation. P2.2 and
P2.4 made that negative honest. They could not make it definite, because no tool
could answer the question. `POST /legislation/lookup {legislation_type, year,
number}` can: it returns the record (200) or `{"detail": "Legislation not
found: ssi 2025 No. 377"}` (404).

**Three states, not two** (the row's design note (a)). A 200 does not mean the
index holds the TEXT: `ssi/2025/119` is a record with no text, and its lookup
reports `number_of_provisions: 6`, so that field is not a text signal.
`/legislation/section/lookup` is: it 404s (`"No sections found for legislation
ID: …"`) on a stub and returns a list on a held instrument. So the tool reports
`held`, `held_without_text` or `not_held`, and `lookup_failed` for anything it
could not decide (a timeout, a 5xx), which must never read as a negative
(Invariant 1).

**Routed in code, not by a prompt rule** (Invariant 2). `run_worker_agent` runs
the lookup on every instrument its brief names by number before the Worker's
first round, and hands the Worker the outcome in a code-written block. The tool
is also offered, so the Worker can look up an instrument it meets mid-run (a
change record naming SSI 2025/377 is how 6409 turn 9 met it). No Worker prompt
names the tool: Session 14 measured a prompt block moving the quick-lookup
Worker to bullet lists and costing the lawyer case links, and Session 22 a
prompt edit moving a call it was not aimed at.

This module holds the pure parts: parsing a citation out of a brief,
normalising the tool's arguments, a lawyer-readable label, and the block. The
HTTP call is in `agent/tools/executor.py`; the scope record, the worker-block
limb and the footer clause are in `utils/search_scope.py`, beside the other
records the same seams carry.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Optional

LOOKUP_TOOL = "lookup_legislation"

HELD = "held"
HELD_WITHOUT_TEXT = "held_without_text"
NOT_HELD = "not_held"
LOOKUP_FAILED = "lookup_failed"
INVALID = "invalid"
DEFINITE_STATUSES = (HELD, HELD_WITHOUT_TEXT, NOT_HELD)

# The `LegislationType` enum in LEX's `/openapi.json` (read 2026-09-24). A type
# outside it is a 422 from the API, so it is refused here instead, as `invalid`,
# which is not a statement about the index.
LEX_LOOKUP_TYPES = frozenset({
    "ukpga", "asp", "asc", "anaw", "wsi", "uksi", "ssi", "ukcm", "nisr", "nia",
    "eudn", "eudr", "eur", "ukla", "ukppa", "apni", "gbla", "aosp", "aep", "apgb",
    "mwa", "aip", "mnia", "nisro", "nisi", "uksro", "ukmo", "ukci",
})

# How many instruments one brief may have looked up in code. A brief naming
# more is a list, and each lookup is two HTTP calls; the Worker can still call
# the tool for the rest.
MAX_ROUTED_LOOKUPS = 5

# The label a lawyer writes. Anything not listed renders as its id.
_LABELS = {
    "ssi": "SSI {y}/{n}",
    "uksi": "SI {y}/{n}",
    "wsi": "WSI {y}/{n}",
    "nisr": "SR {y}/{n}",
    "asp": "{y} asp {n}",
    "ukpga": "{y} c. {n}",
    "anaw": "{y} anaw {n}",
    "asc": "{y} asc {n}",
}

# An optional abbreviation in brackets between the name and the number is how
# the Manager writes a brief as often as not: "Scottish Statutory Instrument
# (SSI) 2025/377" (`wave3_p35` 6409 r1 t9, the one stored brief of nine the
# first version of this pattern missed).
_NUM = r"(?:\([A-Za-z. ]{2,10}\)\s*)?(\d{4})\s*(?:/|,?\s*No\.?\s*)\s*(\d{1,5})"
# Order matters: a Scottish or Welsh form is matched, and its span masked,
# before the bare "SI" / "Statutory Instrument" form can claim it.
_CITATION_PATTERNS = (
    # The id form the tools themselves use.
    ("id", re.compile(
        r"\b(" + "|".join(sorted(LEX_LOOKUP_TYPES, key=len, reverse=True))
        + r")/(\d{4})/(\d{1,5})\b", re.I)),
    ("ssi", re.compile(
        r"\b(?:S\.\s?S\.\s?I\.?|SSI|Scottish\s+Statutory\s+Instruments?)\s*" + _NUM, re.I)),
    ("wsi", re.compile(
        r"\b(?:W\.\s?S\.\s?I\.?|WSI|Wales\s+Statutory\s+Instruments?)\s*" + _NUM, re.I)),
    ("nisr", re.compile(r"\b(?:S\.\s?R\.|SR)\s*" + _NUM)),
    ("uksi", re.compile(
        r"\b(?:U\.?K\.?\s?S\.\s?I\.?|UKSI|S\.\s?I\.?|SI|Statutory\s+Instruments?)\s*" + _NUM,
        re.I)),
    # Acts of the Scottish Parliament: "2025 asp 2" and "asp 2025/2".
    ("asp", re.compile(r"\b(\d{4})\s+asp\s+(\d{1,3})\b", re.I)),
    ("asp", re.compile(r"\basp\s+" + _NUM, re.I)),
    # A UK Act by chapter, "2010 c. 15". Lower-case "c." only: "(C. 28)" after
    # an SSI number is the commencement-order series number, not a chapter, and
    # it is always written in capitals.
    ("ukpga", re.compile(r"\b(\d{4})\s+c\.\s?(\d{1,3})\b")),
)


def _plausible(year: int, number: int) -> bool:
    return 1200 <= year <= date.today().year + 1 and 1 <= number <= 99999


def extract_instrument_citations(text: str, limit: int = MAX_ROUTED_LOOKUPS) -> list:
    """Every instrument `text` names by type, year and number, in order of
    first appearance, deduplicated, as `(legislation_type, year, number)`.

    Deliberately conservative: a bare "2025/377" names no type, so it is not
    looked up (it could be an SSI, an SI or a WSI). The Manager's brief is the
    input, and it is told to carry SI numbers into the brief. Never raises.
    """
    try:
        text = text or ""
        found = []
        masked = list(text)
        for kind, rx in _CITATION_PATTERNS:
            for m in rx.finditer("".join(masked)):
                if kind == "id":
                    typ, y, n = m.group(1).lower(), int(m.group(2)), int(m.group(3))
                else:
                    typ, y, n = kind, int(m.group(1)), int(m.group(2))
                if typ in LEX_LOOKUP_TYPES and _plausible(y, n):
                    found.append((m.start(), (typ, y, n)))
                for i in range(m.start(), m.end()):
                    masked[i] = " "
        out = []
        for _, ref in sorted(found):
            if ref not in out:
                out.append(ref)
        return out[:limit]
    except Exception:
        return []


def lookup_args(args: Any) -> Optional[tuple]:
    """`(legislation_type, year, number)` from the tool's arguments, or None.

    Accepts the schema's three fields, and a `legislation_id` in the id form,
    which is what a model holding an id from another tool will pass.
    """
    if not isinstance(args, dict):
        return None
    try:
        lid = str(args.get("legislation_id") or "").strip().lower()
        if lid:
            m = re.fullmatch(r"(?:https?://www\.legislation\.gov\.uk/(?:id/)?)?"
                             r"([a-z]+)/(\d{4})/(\d{1,5})/?", lid)
            if not m:
                return None
            typ, y, n = m.group(1), int(m.group(2)), int(m.group(3))
        else:
            typ = str(args.get("legislation_type") or "").strip().lower()
            y, n = int(args.get("year")), int(args.get("number"))
        if typ not in LEX_LOOKUP_TYPES or not _plausible(y, n):
            return None
        return typ, y, n
    except (TypeError, ValueError):
        return None


def legislation_id(ref: tuple) -> str:
    return f"{ref[0]}/{ref[1]}/{ref[2]}"


def citation_label(ref: tuple) -> str:
    typ, y, n = ref
    return _LABELS.get(typ, "{t}/{y}/{n}").format(t=typ, y=y, n=n)


def routed_lookup_args(ref: tuple) -> dict:
    """The arguments code passes, identical to a model's, so the per-request
    memo serves a model that repeats the lookup."""
    return {"legislation_type": ref[0], "year": ref[1], "number": ref[2]}


def parse_lookup_result(data: Any) -> Optional[dict]:
    """The tool's own result, or None if `data` is not one."""
    try:
        got = json.loads(data) if isinstance(data, str) else data
    except (TypeError, ValueError):
        return None
    if not isinstance(got, dict) or got.get("tool") != LOOKUP_TOOL:
        return None
    return got


def _clean(text: Any, cap: int = 300) -> str:
    """One line, no square brackets (the block must survive `_TOOL_BLOCK`)."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    s = s.replace("[", "(").replace("]", ")")
    return s if len(s) <= cap else s[:cap].rsplit(" ", 1)[0] + "…"


async def routed_lookup_block(brief: str, tool_names, run_tool) -> str:
    """Look up every instrument `brief` names by number, through `run_tool(name,
    args)`, and return the block for the Worker's brief ("" if none).

    The one routing function: `run_worker_agent` passes its own tool executor,
    so the audit, the memo and the step's scope record see each lookup, and
    `tools/seam_replay.py` passes the bare LEX executor to rebuild the same
    brief for a first-round probe. Only where the tool is offered, which is the
    two legislation research types. Exceptions propagate: the caller decides
    what failing soft means.
    """
    if LOOKUP_TOOL not in set(tool_names or ()):
        return ""
    refs = extract_instrument_citations(brief)
    if not refs:
        return ""
    import asyncio

    results = await asyncio.gather(*(run_tool(LOOKUP_TOOL, routed_lookup_args(r)) for r in refs))
    return lookup_brief_block(results)


def lookup_brief_block(results: list) -> str:
    """The block `run_worker_agent` appends to the Worker's brief, from the
    results of the lookups it ran in code. "" when there is nothing to say.

    Sentences, not bullets: Session 14 measured a block in the quick-lookup
    Worker's context moving it to bullet lists, which cost case links in the
    answer. In `[SEARCH SCOPE — …]` form with no brackets inside, so the strip
    that removes tool blocks from an answer removes an echo of this too.
    """
    parts = []
    for raw in results or []:
        got = parse_lookup_result(raw)
        if not got:
            continue
        lid = got.get("legislation_id") or ""
        label = got.get("label") or lid
        status = got.get("status")
        title = _clean(got.get("title"), 200)
        named = f"{label} ({title})" if title else label
        # Both sentences end on what CAN still be retrieved. The first draft said
        # "do not search for it again", and on the first-round probe the Worker
        # then wrote at once on 4 of 5 stored briefs. At HEAD, 6409 t9 and t11
        # get "SSI 2025/377 brings s.18 into force" from the parent Act's change
        # record, a true positive the lawyer would have lost (Invariant 1). And
        # the change record answers BY the unheld instrument's own id: checked
        # live (Session 25), `/amendment/search` returns 1 relation made by
        # `ssi/2025/377` and 46 made by `ssi/2026/170`, neither of which the
        # index holds a record of.
        if status == NOT_HELD:
            parts.append(
                f"{label}: NOT HELD. The index has no record of it under that type, year "
                "and number, so a search for its title or number will not find it and its "
                "text cannot be read here. Report it as not held in this index, not as not "
                "found by a search. That is a gap in the index: it does not mean the "
                "instrument does not exist, and it is not an error in the citation. What "
                "it changes can still be retrieved: legislation.gov.uk's change records "
                "list what it commenced, amended or revoked even where the index holds no "
                f"record of it, so call get_legislation_changes with legislation_id {lid} "
                "and direction 'by' before you report."
            )
        elif status == HELD_WITHOUT_TEXT:
            desc = _clean(got.get("description"))
            parts.append(
                f"{named}: HELD WITHOUT TEXT. The index holds its record but none of its "
                f"text, so a search inside it returns nothing. Report it as held with no "
                f"text available here, never as not found."
                + (f" Its record describes it as: {desc}" if desc else "")
                + " What it commences or amends can still be read from change records "
                "(get_legislation_changes)."
            )
        elif status == HELD:
            # Not "use it": a Manager unsure of the type writes "SSI 2026/170
            # or any UK SI 2026/170" (`wave2_p24` 6373 r2 t3), and `uksi/2026/170`
            # is held and is an unrelated planning instrument. A held record is
            # a fact about that id, not an answer to the question.
            parts.append(
                f"{named}: HELD, with text, under legislation_id {lid}. Check that this "
                "title is the instrument the question is about before relying on it."
            )
        # lookup_failed and invalid say nothing about the index, so they add no
        # sentence: the Worker searches exactly as it did before P3.7.
    # The same year and number under two types are two instruments. Said
    # outright, because presenting one as the other is the substitution P2.4
    # measured ("you may be referring to the 2021 Regulations").
    seen: dict = {}
    for raw in results or []:
        got = parse_lookup_result(raw)
        if got and got.get("status") in DEFINITE_STATUSES:
            yn = "/".join(str(got.get("legislation_id") or "").split("/")[1:])
            seen.setdefault(yn, []).append(got.get("label") or got.get("legislation_id"))
    for labels in seen.values():
        if len(labels) > 1:
            parts.append(
                f"{' and '.join(labels)} share a year and number but are different "
                "instruments: never present one as the other."
            )
    if not parts:
        return ""
    return (
        "\n\n[SEARCH SCOPE — instrument lookup, run by code before your research on each "
        "instrument this brief names by number. A lookup is an exact test of whether the "
        "index holds that instrument, not a ranked search. "
        + " ".join(parts) + "]"
    )
