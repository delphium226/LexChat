"""P3.10: hand a Deep Research step the instruments the earlier steps found.

**Why this exists.** `run_deep_research` runs each approved step as an isolated
Worker, and `_build_step_brief` passes the step, the scope note and the
question, never what an earlier step found. The planner still writes steps that
work on an earlier step's list ("Check the amendment status of the identified
Orders"). Measured at HEAD (batch 10 D, `notes/batch10_D.md` section 1): every
one of the 12 such steps after P3.8 re-derived its list with its own
`search_legislation` calls (62 in all), and 5 of 12 worked on a different list
from the one the earlier step reported (4 shorter, 1 longer). The dropped
instruments reached the answer through the synthesis, but without the
dependent step's check.

**The lever is code, not a planner rule** (Invariant 2): one line in the step's
brief, written by code, naming the instrument ids the earlier steps' reports
cite. The ids come from the report BODIES: the scope block code appends to every
Worker report (and any tool block a Worker echoed) names ids the model never
listed, a change record's or a revoked title's, so it is cut first with the
product's own `strip_scope_blocks`. The ids are read with P3.7's own parser,
`extract_instrument_citations`, which reads both the id form a link carries
(`ssi/1901/3` inside a legislation.gov.uk URL) and the citation a lawyer writes
("SSI 1901/3"); batch 10 D's first grader missed the second form.

**It must not trigger P3.7's routed lookups.** `run_worker_agent` looks up every
instrument its brief names by number, at most five a brief. The ids on this
line were cited by the earlier steps' reports, so the index has already
answered for them, and a cap of five on a list of six to eight would hand the
Worker a held/absent block for an arbitrary part of the list.
`routed_lookup_block` therefore reads the brief through `without_handover_line`.
An instrument the step's own text names is still looked up, as before.

**Which steps get the line.** Every step after the first whose earlier steps'
report bodies cite at least one instrument (user decision, 2026-10-09). It was
first given only to a step whose wording a pattern recognised (the Session 15
pattern plus "the identified" followed by a class's full title); in the
acceptance replay (`wave4_b11_sweep`) the line worked on every step it reached,
and the one miss was a step the pattern did not recognise ("Review the
retrieved secondary legislation ..."), which re-derived the list and dropped an
instrument. A planner can phrase the dependency in more ways than a pattern
can list, so there is no pattern: the line is conditional ("Where this task
works on instruments an earlier step identified ..."), and a step that does
not work on the list is not asked to do anything new.

Pure functions only; `agent_core.run_deep_research` calls them. Never raises:
a failure here returns "" and the step runs as it did before (Invariant 5).
"""

from __future__ import annotations

import re
from typing import Iterable

# The label the line opens with. It is also how `without_handover_line` finds
# the line again, so the brief's own text (the question is quoted into the
# CONTEXT paragraph) cannot be mistaken for it: the label must open a line.
HANDOVER_LABEL = "EARLIER STEPS' INSTRUMENTS:"

# How many ids the line names. Over the 531 stored steps 2+ that would get a
# line (every era, batch 12 B's dry run) the median list is 3 and the 90th
# percentile 7; 5 lists are longer than 15 (38 to 39, every one from a step
# that listed instruments from P3.31's made-under record). At 15, one stored step
# was handed 14 of 37 SSIs plus "and 23 more" and worked on exactly the 14, so
# the cap is P3.31's listing limit, 40 (user decision, 2026-10-09). Past the cap
# the line says how many more there are.
MAX_HANDED_ON_IDS = 40

_LINE_START = re.compile(r"^" + re.escape(HANDOVER_LABEL) + r"[^\n]*\n?", re.M)


def report_body(report: str) -> str:
    """A step's report without the blocks code appended to it (the scope
    record) or a Worker echoed into it (any tool block)."""
    from .search_scope import strip_scope_blocks

    return strip_scope_blocks(report or "")[0]


def handed_on_ids(reports: Iterable[str]) -> list:
    """The instrument ids the reports' bodies cite, in order of first
    appearance (report by report), each once."""
    from .instrument_lookup import extract_instrument_citations, legislation_id

    out: list = []
    for report in reports or []:
        # No limit here: the cap is on what the line names, and it says how
        # many more there are.
        for ref in extract_instrument_citations(report_body(report), limit=10_000):
            lid = legislation_id(ref)
            if lid not in out:
                out.append(lid)
    return out


def handover_line(reports: Iterable[str]) -> str:
    """The line for a later step's brief, or "" when the earlier steps' reports
    cite no instrument. Never raises."""
    try:
        ids = handed_on_ids(reports)
        if not ids:
            return ""
        shown = ", ".join(ids[:MAX_HANDED_ON_IDS])
        more = len(ids) - MAX_HANDED_ON_IDS
        if more > 0:
            shown += f" and {more} more"
        # Conditional ("Where this task works on ..."), so it adds nothing to a
        # step that does not, and never widens a step's task: the CONTEXT
        # sentence after it ("Research ONLY this step's task") stays true.
        # "Among these": the list is every instrument the reports cite, the
        # parent Act included, not only the ones the task means. No "search for"
        # or "searching for": an echo of the line in an answer would then read
        # to `replay_report`'s NEGATIVE_EXPLAINED as a negative that names its
        # search (the screen's one trip on the first draft).
        return (
            f"{HANDOVER_LABEL} the reports of the earlier steps of this plan cite these "
            f"instruments, by legislation_id: {shown}. Where this task works on instruments "
            "an earlier step identified, they are among these: work on each one of the kind "
            "the task names, by its legislation_id, rather than finding the list again, "
            "and look further only if the task asks for more than the earlier steps reported."
        )
    except Exception:
        return ""


def without_handover_line(text: str) -> str:
    """`text` with the handover line removed, for P3.7's routed lookups."""
    try:
        return _LINE_START.sub("", text or "")
    except Exception:
        return text or ""
