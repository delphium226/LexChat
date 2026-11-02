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

# P3.57 follow-up (Session 52, worker p357b): the sibling line saying what an
# earlier step's text scan by code read and found. `without_handover_line`
# removes it too: it names up to 40 ids, which P3.7 must not look up.
SCAN_HANDOVER_LABEL = "EARLIER STEPS' TEXT SCAN:"

_LINE_START = re.compile(
    r"^(?:" + re.escape(HANDOVER_LABEL) + "|" + re.escape(SCAN_HANDOVER_LABEL) + r")[^\n]*\n?",
    re.M)


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


def scan_handover_line(entries: Iterable[dict]) -> str:
    """P3.57 follow-up: the line for a later step's brief where an earlier
    step's text scan by code (`utils/literal_scan.py`) read a made-under
    list's texts for a string. "" where no earlier step ran one. Never raises.

    **Why.** `wave5_p357` 6382, 3 of 3: step 2 was handed the 20 ids the scan
    found '£' in (the line above) but not that the scan had read them, so it
    section-searched each for "£"; the ranked search did not return SSI
    2025/340's regulation 3, the step reported 2025/340 as not containing '£',
    and the synthesis called it a discrepancy. Conditional ("Where this task
    asks ..."), like the line above, so it asks nothing of a step that does
    not work on the string."""
    try:
        from .literal_scan import SCAN_ENTRY, _id_list, _q

        rows = [e for e in (entries or []) if isinstance(e, dict) and e.get("tool") == SCAN_ENTRY]
        if not rows:
            return ""
        e = rows[-1]
        q = _q(e["literal"])
        read = len(e["found"]) + len(e["absent"])
        unread = (f"; not read, {len(e['unread'])} ({_id_list(e['unread'])})"
                  if e["unread"] else "")
        return (
            f"{SCAN_HANDOVER_LABEL} an earlier step's code read the whole text of {read} of the "
            f"{e['listed']} instruments the made-under record listed (every provision and "
            f"schedule as made) and searched each one for {q}: found in {len(e['found'])} "
            f"({_id_list(e['found'])}); not found in the text read in {len(e['absent'])} "
            f"({_id_list(e['absent'])}){unread}. That result stands for each instrument it "
            f"read, so this task need not and should not section-search them for {q}: a "
            "section search ranks provisions by meaning, and one that does not return "
            f"{q} does not show that an instrument lacks it. Where this task asks which of "
            f"them contain {q}, take it from this scan."
        )
    except Exception:
        return ""


def without_handover_line(text: str) -> str:
    """`text` with the handover line removed, for P3.7's routed lookups."""
    try:
        return _LINE_START.sub("", text or "")
    except Exception:
        return text or ""
