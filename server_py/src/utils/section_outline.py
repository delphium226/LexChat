"""P3.11 (B10 residual): the subsections of each retrieved provision, handed to
the Worker after summarisation.

**The defect.** 6348's lawyer: the answer *"did not initially elaborate on the
full provision, only referring to s36(1) and not s36(2)"*. P3.1 gave the
research Workers a rule (*"When you cite one subsection of a section, say in a
line what that section's other subsections provide"*) and 6348's turn 1 moved
from 0 of 3 to 1 of 3. The rule is obeyed at a rate, so under Invariant 2 the
lever is code.

**Where the sibling actually goes, measured over every stored 6348 run before
this was built (11 runs, 6 replay directories):** the section search returns
s.36 with both subsections every time, and the *summariser* keeps s.36(2) in
**1 of the 11** summaries. The row was written on the premise that "summaries
already keep subsection numbers, so the outline's value is salience, not
information"; that is true of the subsections the summary mentions and false
of the one it drops. A Worker that never sees s.36(2) cannot say what it
provides. So this is P1.6's situation exactly: the summariser cannot discard
what it never saw, and the fix is to hand the thing back after it, built from
the RAW result.

**What the block is.** For each provision the retrieval returned that has two
or more numbered subsections, one line per subsection: its number and the
opening words of its text, with its paragraphs folded in, cut at
`MAX_SUBSECTION_CHARS`. Provisions are labelled from the URL segment
(`s.36`, `reg. 4`, `art. 2`), never from the word the text uses, because LEX
renders a regulation's text as `Section 4)` and a wrong label here would be a
wrong pinpoint in the report. No URLs: P1.6's block, directly above it in the
result, already carries them.

**What it leaves out, deliberately.**
  * A Schedule. LEX holds a Schedule as ONE provision whose `Section k)` lines
    are its paragraphs (P3.12), so a subsection outline of one would number the
    sub-paragraphs of different paragraphs as if they were siblings.
  * A provision with fewer than two numbered subsections: there is no sibling
    to lose.
  * An item with no provision-level URL (the 1960s SIs whose rows carry the
    instrument's own URL and `(1)`-style numbering): the same rule P1.6 uses.
  * Everything on the unsummarised path: the full text is in front of the
    model already, and restating it is context spent on nothing measured.

**Measured on the corpus this was designed against** (26,265 section-search
rows over 27 replay directories): 14,253 rows are the `Section N) **Title**`
plus `N) ...` shape this parses; 6,852 more have that header and no numbered
subsection; 2,187 are Schedules; the rest are old-form or malformed rows.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .citation_links import _loads_prefix, is_provision_url, normalise_leg_url

logger = logging.getLogger(__name__)

__all__ = [
    "subsection_outline",
    "OUTLINE_BLOCK_OPEN",
    "OUTLINE_BLOCK_CLOSE",
    "OUTLINE_HEADER",
    "MAX_SUBSECTION_CHARS",
    "MAX_SUBSECTIONS_PER_PROVISION",
    "MAX_BLOCK_CHARS",
]

OUTLINE_BLOCK_OPEN = "[SECTION OUTLINE"
OUTLINE_BLOCK_CLOSE = "[/SECTION OUTLINE]"

# Addressed to the Worker. Worded so that an echo trips no detector in
# `tools/replay_report.py` (a test runs every one of them over it), and it
# names no provision - the acceptance grades one, and a prompt or block that
# named it would let a model land on it by copying the format.
OUTLINE_HEADER = (
    "[SECTION OUTLINE — the numbered subsections of each provision this "
    "retrieval returned, in the words of the retrieved text (opening words; a "
    "long subsection is cut short). The summary above may leave some of them "
    "out. When you cite one subsection of a provision, say in a line what its "
    "other subsections provide, taking that from this outline, and give each "
    "subsection its own number.]"
)

# One subsection's opening words. 300 keeps both limbs of a two-paragraph
# subsection ("if- (a) ...; and (b) ...") rather than the lead-in alone,
# which says nothing about what the subsection provides.
MAX_SUBSECTION_CHARS = 300
# A provision with more numbered subsections than this lists the first ones
# and says how many follow.
MAX_SUBSECTIONS_PER_PROVISION = 12
# The whole block, so ten long provisions cannot add more context than the
# summary they follow. Provisions are taken in the retrieval's own rank order.
MAX_BLOCK_CHARS = 6000

# "Section 36) **Confidentiality**", "Section A4) **...**", "Article 2) **...**",
# "Section 1) ****" (an empty title). LEX writes "Section" for a regulation and
# an article too, so the word is matched and then ignored.
_HEADER = re.compile(r"^(?:Section|Article)\s*(\S+?)\)\s*(?:\*\*(.*?)\*\*)?\s*$")
# A numbered subsection at column 0: "1) ", "2A) ". Paragraphs are tab-indented
# ("\ta) ") and so never match; neither does the header line.
_SUBSECTION = re.compile(r"^(\d+[A-Z]{0,2})\)\s")
# The provision segment of a legislation.gov.uk URL, for the label.
_URL_SEGMENT = re.compile(r"/(section|regulation|article|rule)/([^/]+)")
_LABEL_PREFIX = {"section": "s.", "regulation": "reg. ", "article": "art. ", "rule": "rule "}
_WS = re.compile(r"\s+")
# A paragraph or sub-paragraph marker as LEX renders it ("a) ", "ii) "), folded
# into its subsection's line as "(a) " / "(ii) " - the form a citation uses.
_PARA_MARK = re.compile(r"^([a-z]{1,5})\)\s")


def _provision_label(item: dict, header_number: str) -> str:
    """`s.36` / `reg. 4` / `art. 2`, from the URL's segment and the text's number.

    Empty when the item has no provision-level URL, which is the caller's
    signal to leave it out (P1.6's rule: a row without one is not a provision
    the model can cite).
    """
    url = str(item.get("url") or item.get("uri") or "")
    if not url or not is_provision_url(url):
        return ""
    m = _URL_SEGMENT.search("/" + normalise_leg_url(url))
    if not m:
        return ""
    kind, url_number = m.group(1), m.group(2)
    number = header_number or url_number
    return f"{_LABEL_PREFIX[kind]}{number}"


def _subsections(text: str) -> list:
    """[(number, flattened text), ...] for the column-0 numbered lines of one
    provision's text, each with its indented paragraphs folded in."""
    out: list = []
    current: Optional[list] = None
    lines = text.split("\n")[1:]          # the first line is the header
    for line in lines:
        m = _SUBSECTION.match(line)
        if m:
            if current is not None:
                out.append((current[0], " ".join(current[1])))
            current = [m.group(1), [line[m.end():].strip()]]
        elif current is not None:
            part = _PARA_MARK.sub(r"(\1) ", line.strip())
            if part:
                current[1].append(part)
        # Text before the first numbered subsection (an opening body) belongs
        # to no subsection and is not outlined.
    if current is not None:
        out.append((current[0], " ".join(current[1])))
    return [(n, _WS.sub(" ", t).strip()) for n, t in out]


def _opening(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].rstrip() + "…"


def _outline_one(item: dict) -> str:
    """The outline lines for one result row, or "" when it has nothing to say."""
    if not isinstance(item, dict):
        return ""
    if str(item.get("provision_type") or "").strip().lower() == "schedule":
        return ""                                 # P3.12: one item, many paragraphs
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return ""
    header = _HEADER.match(text.split("\n", 1)[0].strip())
    if not header:
        return ""
    label = _provision_label(item, header.group(1).strip())
    if not label:
        return ""
    subs = _subsections(text)
    if len(subs) < 2:
        return ""
    title = (header.group(2) or item.get("title") or "").strip()
    lines = [f"- {label} {title}".rstrip()]
    for number, body in subs[:MAX_SUBSECTIONS_PER_PROVISION]:
        lines.append(f"  ({number}) {_opening(body, MAX_SUBSECTION_CHARS)}")
    more = len(subs) - MAX_SUBSECTIONS_PER_PROVISION
    if more > 0:
        lines.append(f"  (… {more} more subsection{'s' if more != 1 else ''}, "
                     f"in the retrieved text)")
    return "\n".join(lines)


def subsection_outline(raw_result) -> str:
    """The outline block appended after a summarised section retrieval.

    Built from the RAW `search_legislation_sections` result, never from the
    summary, and returned as "" when there is nothing to say so the caller can
    append it unconditionally. Fail-soft: an unparseable result contributes
    nothing rather than raising into a research run.
    """
    try:
        parsed = _loads_prefix(raw_result)
        if not isinstance(parsed, dict):
            return ""
        results = parsed.get("results")
        if not isinstance(results, list):
            return ""
        entries: list = []
        omitted = 0
        used = 0
        for item in results:
            entry = _outline_one(item)
            if not entry:
                continue
            if entries and used + len(entry) > MAX_BLOCK_CHARS:
                omitted += 1
                continue
            entries.append(entry)
            used += len(entry) + 1
        if not entries:
            return ""
        if omitted:
            entries.append(
                f"- … and {omitted} further provision{'s' if omitted != 1 else ''} "
                "with numbered subsections, omitted here for length (the retrieved "
                "text has them)"
            )
        return "\n\n" + OUTLINE_HEADER + "\n" + "\n".join(entries) + "\n" + OUTLINE_BLOCK_CLOSE
    except Exception:  # pragma: no cover - defensive
        logger.debug("[Outline] subsection outline skipped", exc_info=True)
        return ""
