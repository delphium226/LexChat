#!/usr/bin/env python
"""The frozen replay set (FIX_PLAN P0.2).

Turns the pre-pilot transcript export into replayable `Session` records: the
ordered user turns **each with the chat mode it actually ran in**, the recorded
filter state, and the bucket(s) the session evidences.

The CSV is NOT in this repo and must not be committed — it holds the lawyers'
verbatim live casework questions. Regenerate from Admin Portal -> Developer ->
Session transcripts export (all time). See FIX_PLAN "Data handling".

Chat mode is PER TURN, and the export does not state it
-------------------------------------------------------
This is the one non-obvious thing in this module, and getting it wrong silently
invalidates the whole baseline.

`Session mode` in the export is a **thread-level** value. `feedback.py::_session_mode`
reports `deep_research` if Deep Research ran on *any* message in the thread, and
says so: "A thread that mixed the two is reported as deep_research". So a
session flagged `deep_research` is not a session in which every turn was Deep
Research — in 6409 it was turn 6 of 11, in 6341 turn 7 of 8.

Nor is the mode the first turn. Deep Research is deliberately one-shot:
`useChat.js::onDeepResearchComplete` drops the chat back to conversational when
a run finishes, and `App.jsx` persists that as the user's preference. A lawyer
who wants a second Deep Research turn has to switch back on. That is why
`Filter: Chat mode` (the toggle position when the feedback form was submitted)
reads `conversational` on 14 of the 16 in-scope Deep Research sessions — it is
recording the auto-revert, not a contradiction.

The authoritative per-message signal is `messages.research_plan`, which is
written only on a Deep Research assistant message. **It is not in the export,
and the pre-pilot database is not on this machine** (the local DB holds 18 dev
chats and one user). So it is reconstructed from the answer text:

    a turn ran Deep Research  <=>  its answer contains "**Key findings"

`DEEP_RESEARCH_SYNTHESIS_PROMPT` (prompts.py:1046) is the only prompt in the
codebase that asks for a "**Key findings** bullet list"; no worker or manager
prompt mentions it. Measured over the 47 sessions whose thread-level mode is
known, the marker is exact:

| | sessions carrying the marker |
|---|---|
| `Session mode == deep_research` (23) | 23 |
| `Session mode` conversational/research (24) | 0 |
| `Session mode` blank (15) | 0 |

It also independently reproduces a number derived by hand from the transcripts:
12 messages across **10 of 23** Deep Research sessions mention exceeding the
tool-call step limit, matching FIX_PLAN P2.1's "10 of 23 DR sessions (43%)".
And in every one of the 16 in-scope sessions the marked turn is among the most
expensive in the thread (6409 turn 6 at $0.51 against $0.03-0.05 elsewhere;
6341 turn 7 at $0.97 against $0.02-0.39), which is the cost signature of a
multi-step fan-out.

**Its limits, which matter for two rows.** The marker is read off the *answer*,
so a Deep Research turn that produced no answer at all cannot be seen — and 15
user turns across the corpus never received a reply, which is bucket B13/P4.2
itself. It would also miss a synthesis that dropped the block. The durable fix
is to export the stored flag: add a per-message "Deep research" column to the
Developer-tab transcript export, sourced from `messages.research_plan`, and
re-export. Until then this is inference, flagged per turn as
`chat_mode_source="dr_marker"` so no row builds on it unknowingly.

Research or Conversational is read off the answer too (P0.5)
------------------------------------------------------------
~~A turn that is not Deep Research takes the session's `Filter: Chat mode`
snapshot, falling back to `research` (the `ChatRequest.chat_mode` default, and
the frontend's).~~ **That fallback was a guess, and it was wrong for 12 of the
41 replayed sessions — 48 of 155 turns, in every sweep from `baseline` to
`wave3_p311` (FIX_PLAN P0.5, 2026-09-22).** The export's `Session mode` and
`Filter: Chat mode` are both blank for the 15 sessions run on 11-13 August
(6332-6351), because the columns were added on 13 and 19 August; the lawyers
ran them in Conversational mode with the Research feature flag off, and the
harness sent them as Research.

So mode is now read from the answer for those turns too, the same trick
`dr_marker` uses. The research Worker's OUTPUT STRUCTURE headings pass through
the Manager in Research mode and never appear in a conversational answer:

    Summary Answer (BLUF) | Detailed Analysis | Jurisdiction & Status
    | Statutory Framework | a `#`-headed References section

(`agent_core._REPORT_SECTIONS`, checked by `_report_needs_reformat` and
restored by the A4 reformat retry when the model drops them.) Measured:

| answers | carrying the report headings |
|---|---|
| pre-pilot, the 15 blank-mode sessions | **0 of 38** |
| pre-pilot, the 24 sessions recorded `conversational` | 0 of 64 |
| pre-pilot, non-DR turns of the 23 Deep Research sessions | 0 of 52 |
| replay in Research mode, `baseline` | 39 of 48 |
| replay in Research mode, `wave2` | 42 of 48 |
| replay in Conversational mode, `wave2` | 0 of 87 |

`python -m tools.replay_report modes` reproduces both halves of that table.

**Precedence, and why the snapshot still wins where it exists.** A turn is
`deep_research` if it carries `DR_MARKER`; otherwise, if its session has a
`Filter: Chat mode` snapshot, that snapshot stands (`chat_mode_source:
"snapshot"`) and the marker is used only to CHECK it — `mode_report` prints
every disagreement, and there are **none** on this corpus, in either
direction. Preferring the recorded field over the inference keeps the 29
snapshot-carrying sessions byte-identical to every sweep already taken, so
P0.5 moves exactly the turns it says it moves. Where there is no snapshot the
marker decides: `research_marker` or `conversational_marker`.

**A turn with no answer cannot be read, and 15 turns never got one** (bucket
B13/P4.2 itself). Those take **the nearest answered turn in the same session**
(`chat_mode_source: "neighbour"`), preferring the preceding turn on a tie and
skipping Deep Research turns — Deep Research is one-shot and the frontend
reverts, so a DR neighbour says nothing about the turn beside it, and copying
one would also replay an unasked-for $0.71 turn. All 8 such turns in
snapshot-less sessions resolve to `conversational`; the other 7 are in
snapshot-carrying sessions and take the snapshot. Only a session with no
answered non-DR turn at all would reach `DEFAULT_CHAT_MODE`, and none exists
here.

For a Deep Research session the snapshot is the post-revert `conversational`,
which is the correct reading for the turns either side of the run: 6406 turn 1
is a conversational-mode deflection ("I recommend switching to Research mode"),
and the user switched on for turn 2.

The research type is NOT readable the same way (P0.6)
-----------------------------------------------------
`Filter: Research mode` is blank for 20 of the 62 sessions — the twelve above
plus eight PASS sessions outside the replay set — and until P0.6 the harness
filled it with `legislation_only` and labelled it `default`. **That was wrong
on 16 of the twelve's 50 turns**, which ran with case law in the tool set.

An answer's shape does not give it away: a refusal quotes the case the lawyer
named, so a neutral citation is not evidence. What an answer CAN show, read
against the pre-pilot prompts, is behaviour: the legislation-only Manager
declines every case-law question; the hybrid one briefs the Worker to ALSO
search case law, so its answers report case-law results nobody asked for, in
the case-law tool's own coverage wording; case law from 2026 can only have
come from the tool. At the pre-pilot the type was one saved preference per
user, so a change is an event and a turn between two equal reads of the same
lawyer is bracketed. That is a human read, and it is committed as data, one
entry per turn with a neutral evidence note:
`docs/prepilot-fixes/evidence/research_mode_reads.json` (`load_research_reads`).
Where nothing settles a turn the read says `unknown`, and the harness says so
per turn (`research_mode_source`); `_resolve_research_modes` has the rules for
what such a turn sends. The target's `request_timings.research_mode` recorded
the real value per request and would replace the read (FIX_PLAN P0.7).

Other decisions
---------------
* **`Filter: Date to` maps to `year_to`, not `date_to`.** The export writes a
  bare year there (`2026`) for legislation sessions, while `date_from`/`date_to`
  are ISO dates used by the case-law and parliamentary tools. A 4-digit numeric
  value is read as a year; anything else passes through as a date. Mis-typing
  this would void the filter silently.

What this set cannot reproduce
------------------------------
* **The approved Deep Research plans are gone** — `messages.research_plan` again.
  A Deep Research turn is replayed against a freshly drafted plan, which adds
  planner stochasticity the original run did not have.
* **Attached documents and matter context are not replayed.** Both load from
  `chat_id`, and the pre-pilot chats do not exist on this machine.
* **Turns that never received a reply are kept in the set.** A turn that got no
  answer is exactly what P4.2 is about; `got_reply` records it.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CSV = os.environ.get(
    "REPLAY_CSV",
    r"C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv",
)
DEFAULT_CLASSIFICATION = (
    REPO_ROOT / "docs" / "prepilot-fixes" / "evidence" / "classification.json"
)
DEFAULT_REPLAY_SET = (
    REPO_ROOT / "docs" / "prepilot-fixes" / "evidence" / "replay_set.json"
)

# ~~`ChatRequest.chat_mode` default, and the frontend's.~~ **P0.5, 2026-09-22:
# this is the LAST RESORT only** — a turn with no answer in a session with no
# answered non-DR turn and no `Filter: Chat mode` snapshot. No session in this
# corpus reaches it. It is `conversational` because every one of the 154
# answered non-DR turns in the export is conversational-shaped, so `research`
# was not merely unrecorded, it was contradicted by the data.
DEFAULT_CHAT_MODE = "conversational"
# ~~`resolve_research_mode` default.~~ **P0.6, 2026-09-23: never a label, only
# what is SENT** for a turn nothing settles (source `unknown`) in a session
# with no read at all; the API needs a concrete value. It is the product's
# default, and it was the pre-pilot's per-user default too.
DEFAULT_RESEARCH_MODE = "legislation_only"
DEFAULT_RESEARCH_READS = (
    REPO_ROOT / "docs" / "prepilot-fixes" / "evidence" / "research_mode_reads.json"
)
RESEARCH_MODES = ("legislation_only", "case_law_only", "legislation_and_case_law")
# A reviewer read may settle less than the whole type: `case_law_included`
# says the tool set held case law, not whether it held legislation too.
RESEARCH_READ_VALUES = RESEARCH_MODES + ("case_law_included", "unknown")
RESEARCH_READ_BASES = ("answer", "lawyer", "bracketed")

# The Deep Research fingerprint. Only DEEP_RESEARCH_SYNTHESIS_PROMPT asks for a
# "**Key findings** bullet list" — see the module docstring for the measurement.
DR_MARKER = re.compile(r"\*\*key\s*findings", re.IGNORECASE)

# The Research-mode fingerprint (P0.5). The research Worker's OUTPUT STRUCTURE
# headings, which reach the lawyer through the Manager and never appear in a
# conversational answer — see the module docstring for the measurement.
#
# **Anchored to a heading, and that is a correction to the regex the published
# counts were first taken with.** The scratch version matched the bare phrases
# anywhere in the text, and `Statutory Framework` duly fired on a Deep Research
# planner asking "would you like to search for the statutory framework
# discussed in this case" (`wave0_conv` 6347 turn 2) — prose, not a report.
#
# The heading markup is NOT one fixed form. Counted over the corpus, the Worker
# emits at least five: `### 1. Summary Answer (BLUF)` (253), `2. **Detailed
# Analysis:**` (76), `**References:**` (35), `### Jurisdiction & Status` (18)
# and `### **1. Summary Answer (BLUF)**`. Enumerating them in order is how two
# earlier attempts at this regex went wrong — the first missed the
# number-before-bold form and the second the hash-bold-number form, and both
# looked fine because `\bBLUF\b` was quietly carrying them. So: require the
# line to OPEN with markup or a list number (the lookahead), consume a short
# run of it, then the heading name.
#
# Both forms were run over all 181 assistant messages in the export and all
# 1,175 turns in the 29 replay directories — **one disagreement, that one
# planner question** — so every published P0.5 count is unchanged. `BLUF` is
# kept as belt and braces (0 further disagreements): it is the one token that
# survives a heading the A4 reformat retry has mangled.
RESEARCH_REPORT_MARKER = re.compile(
    r"^[ \t>]*(?=[#*_\d])[#*_\d.)\t ]{1,12}"
    r"(?:Summary Answer|Detailed Analysis|Jurisdiction & Status"
    r"|Statutory Framework|References)"
    r"|\bBLUF\b",
    re.IGNORECASE | re.MULTILINE,
)

# What an answer's shape says about the mode it ran in. `None` = no answer.
SHAPE_TO_MODE = {
    "deep_research": "deep_research",
    "research": "research",
    "conversational": "conversational",
}


def answer_shape(text: str | None) -> str | None:
    """Which Worker wrote this answer, read off the answer alone.

    `None` for a turn that never got a reply — which is bucket B13 itself, and
    is the one limit this instrument shares with `dr_marker` (P0.4).
    """
    if not text:
        return None
    if DR_MARKER.search(text):
        return "deep_research"
    if RESEARCH_REPORT_MARKER.search(text):
        return "research"
    return "conversational"


@dataclass
class Turn:
    index: int  # 1-based position among the session's user turns
    question: str
    chat_mode: str
    # dr_marker | snapshot | research_marker | conversational_marker | neighbour
    # | default. Everything but `default` is evidence; `default` is unreachable
    # on this corpus and is kept only so the function is total (P0.5).
    chat_mode_source: str
    got_reply: bool
    recorded_cost_usd: float = 0.0
    recorded_answer_chars: int = 0
    # deep_research | research | conversational | None (no reply). What the
    # PRE-PILOT answer looked like — the evidence behind `chat_mode_source`,
    # kept per turn so a run file can be read without the CSV.
    recorded_answer_shape: str | None = None
    # P4.1 (Session 21): the export's `Message model` is blank on exactly the
    # assistant messages the Deep Research PLANNER wrote — the client saves a
    # clarification with no model (`useChat.js`), every other assistant
    # message carries the backend's — and `answer_shape` reads those five as
    # conversational, because a clarification has no report headings. 6346's
    # three answers are three of the five.
    recorded_model_blank: bool = False
    # P4.1 (B7): the research type is a property of the TURN too — 6346's
    # lawyer changed it mid-session — so it is carried per turn and sent per
    # request. `research_mode` is what the harness SENDS; the source says what
    # that rests on (P0.6): `snapshot` (the export states it), `reviewer` (a
    # human read settles it), `reviewer_partial` (a read settles only that
    # case law was in the tool set; sent as legislation_and_case_law),
    # `unknown` (nothing settles it) or `script`. `default` is never written
    # any more and `replay_report modes` treats it as a finding.
    research_mode: str = ""
    research_mode_source: str = ""


@dataclass
class Session:
    session_id: str
    user: str
    thread: str
    verdict: str
    primary: str
    secondary: list = field(default_factory=list)
    diag: str = ""

    session_mode: str | None = None  # thread-level, as exported
    filter_chat_mode: str | None = None  # toggle position at form submit

    # The export's own `Filter: Research mode`, or None where it is blank
    # (P0.6): run files record it as `filters.research_mode`, a historical
    # fact about the session, so it must not carry a value the export did
    # not. What each turn SENT is `Turn.research_mode`.
    research_mode: str | None = None
    jurisdiction: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    court: str | None = None
    legislation_type: str | None = None
    current_only: bool = False
    record_type: str | None = None
    sessions: list | None = None
    house: str | None = None

    turns: list = field(default_factory=list)
    recorded_cost_usd: float = 0.0
    recorded_models: list = field(default_factory=list)
    # P4.1: set on a scripted session (see `scripted_session`); None for one
    # built from the export.
    script: dict | None = None

    @property
    def user_turns(self) -> list:
        return [t.question for t in self.turns]

    @property
    def deep_research_turns(self) -> list:
        return [t.index for t in self.turns if t.chat_mode == "deep_research"]

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["deep_research_turns"] = self.deep_research_turns
        return d


def _blank(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def _year_or_date(v: str | None) -> tuple[int | None, str | None]:
    """Split a filter value into (year, iso_date)."""
    s = _blank(v)
    if s is None:
        return None, None
    if len(s) == 4 and s.isdigit():
        return int(s), None
    return None, s


def _resolve_modes(turns: list, snapshot_mode: str | None) -> None:
    """Give every turn a chat mode and say where it came from (P0.5).

    Called once per session, after the answers are in, because a turn that got
    no reply is resolved from its neighbours. Precedence, and the reasoning, is
    in the module docstring; the short version is that nothing here is allowed
    to be a guess.
    """
    for t in turns:
        if t.recorded_answer_shape == "deep_research":
            t.chat_mode, t.chat_mode_source = "deep_research", "dr_marker"
        elif t.got_reply and t.recorded_answer_chars and t.recorded_model_blank:
            # P4.1 (Session 21): a Deep Research PLANNER clarification — the
            # one assistant message the client saves with no model. It has no
            # report headings, so the shape marker read all five in the export
            # as conversational; three of them are 6346, the row's evidence
            # session, whose lawyer was therefore in Deep Research throughout.
            t.chat_mode, t.chat_mode_source = "deep_research", "planner_marker"
        elif snapshot_mode:
            t.chat_mode, t.chat_mode_source = snapshot_mode, "snapshot"
        elif t.recorded_answer_shape in SHAPE_TO_MODE:
            t.chat_mode = SHAPE_TO_MODE[t.recorded_answer_shape]
            t.chat_mode_source = f"{t.recorded_answer_shape}_marker"
        else:
            t.chat_mode, t.chat_mode_source = "", ""  # filled below

    # Unanswered turns: the nearest answered non-Deep-Research turn in the same
    # session, preferring the one before. Deep Research is one-shot (the
    # frontend reverts on completion), so a DR neighbour says nothing about the
    # turn beside it — and copying one would replay an unasked-for $0.71 turn.
    # A planner CLARIFICATION is the exception: nothing completed, so the
    # client did not revert, and the mode the next turn ran in is the same
    # Deep Research (6346 turn 4: "It is in deep research mode, please
    # summarise").
    readable = [
        (i, t) for i, t in enumerate(turns)
        if t.chat_mode and (t.chat_mode != "deep_research"
                            or t.chat_mode_source == "planner_marker")
    ]
    for i, t in enumerate(turns):
        if t.chat_mode:
            continue
        nearest = min(
            readable,
            key=lambda pair: (abs(pair[0] - i), 0 if pair[0] < i else 1),
            default=None,
        )
        if nearest is not None:
            t.chat_mode, t.chat_mode_source = nearest[1].chat_mode, "neighbour"
        else:
            t.chat_mode, t.chat_mode_source = DEFAULT_CHAT_MODE, "default"


def load_research_reads(path: Path | str | None = None) -> dict:
    """The reviewer's research-type reads (P0.6), as {(session_id, turn): read}.

    Validated hard, because a malformed read would be sent as if it were
    evidence: every entry needs a known value and basis, `source: reviewer`,
    and a non-empty evidence note, and nothing else — in particular no
    `question` key, since the notes sit in the repo and a lawyer's question
    must not (FIX_PLAN, Data handling). A missing file is an empty read set:
    every blank-export turn is then `unknown`, which is honest, not an error.
    """
    p = Path(path or DEFAULT_RESEARCH_READS)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict = {}
    for sid, turns in (data.get("sessions") or {}).items():
        for idx, read in turns.items():
            where = f"{p.name}: {sid} turn {idx}"
            extra = set(read) - {"value", "source", "basis", "evidence"}
            if extra:
                raise SystemExit(f"{where}: unexpected key(s) {sorted(extra)}")
            if read.get("value") not in RESEARCH_READ_VALUES:
                raise SystemExit(f"{where}: value must be one of {RESEARCH_READ_VALUES}")
            if read.get("source") != "reviewer":
                raise SystemExit(f"{where}: source must be 'reviewer'")
            if read.get("basis") not in RESEARCH_READ_BASES:
                raise SystemExit(f"{where}: basis must be one of {RESEARCH_READ_BASES}")
            if not (read.get("evidence") or "").strip():
                raise SystemExit(f"{where}: needs a one-line evidence note")
            out[(str(sid), int(idx))] = dict(read)
    return out


def _resolve_research_modes(sid: str, turns: list, stated: str | None,
                            reads: dict) -> None:
    """Give every turn a research type to SEND and say what it rests on (P0.6).

    The export states one value per session or none. Where it states one,
    every turn takes it (`snapshot`) and a reviewer read would be a second
    claim about the same fact, so one is refused. Where it is blank, the
    reviewer's read decides: an exact type is `reviewer`; `case_law_included`
    is sent as legislation_and_case_law — the one type that holds case law
    AND legislation, so it withholds neither — labelled `reviewer_partial`.

    **What an `unknown` turn sends.** The API needs a value, and the choice is
    a claim, so it is the smallest one available: the research type was ONE
    saved preference per user at the pre-pilot, so a change is an event, and
    sending the nearest read in the same session (the one before on a tie)
    asserts that no change happened that no evidence places. A global
    default would assert changes instead — 6341 turns 6-8 would drop case
    law after turn 5 and fire P4.1's mode-change marker on a change the
    lawyer never made. A session with no read at all sends
    `DEFAULT_RESEARCH_MODE`, exactly as before. Either way the turn is
    labelled `unknown`, so every run file carries the caveat.
    """
    if stated:
        own = sorted(i for (s, i) in reads if s == sid)
        if own:
            raise SystemExit(
                f"research_mode_reads: session {sid} has an export value "
                f"({stated}) and a reviewer read for turn(s) {own}; the export "
                "wins, so the read is a second claim - remove it")
        for t in turns:
            t.research_mode, t.research_mode_source = stated, "snapshot"
        return

    known: list = []
    for i, t in enumerate(turns):
        read = reads.get((sid, t.index))
        value = (read or {}).get("value", "unknown")
        if value in RESEARCH_MODES:
            t.research_mode, t.research_mode_source = value, "reviewer"
        elif value == "case_law_included":
            t.research_mode = "legislation_and_case_law"
            t.research_mode_source = "reviewer_partial"
        else:
            t.research_mode, t.research_mode_source = "", "unknown"
            continue
        known.append((i, t.research_mode))
    for i, t in enumerate(turns):
        if t.research_mode:
            continue
        nearest = min(known, key=lambda p: (abs(p[0] - i), 0 if p[0] < i else 1),
                      default=None)
        t.research_mode = nearest[1] if nearest else DEFAULT_RESEARCH_MODE


def mode_report(sessions: list) -> dict:
    """Cross-check the answer-shape marker against the export's own fields (P0.5).

    Two questions, both of which a scratch regex answered once and nobody could
    re-run: does the marker ever disagree with a recorded `Filter: Chat mode`
    snapshot, and how many recorded answers are research-shaped? A disagreement
    is a finding, not an error — surface it, as `reconciliation_report` does for
    the Deep Research marker.
    """
    rep: dict[str, Any] = {
        "snapshot_disagreements": [],
        "sources": {},
        "shapes": {},
        "by_recorded_mode": {},
        "default_source_turns": [],
        # P0.6: the research type's provenance, per turn. `research_unknown`
        # and `research_partial` NAME the turns whose tool set is not (fully)
        # known; `research_default` must stay empty.
        "research_sources": {},
        "research_unknown": [],
        "research_partial": [],
        "research_default": [],
    }
    for s in sessions:
        bucket = (
            "session_mode blank"
            if s.session_mode is None and s.filter_chat_mode is None
            else f"session_mode={s.session_mode or '-'}, "
                 f"snapshot={s.filter_chat_mode or '-'}"
        )
        row = rep["by_recorded_mode"].setdefault(
            bucket,
            {"sessions": 0, "research": 0, "conversational": 0,
             "deep_research": 0, "no_reply": 0, "blank_reply": 0},
        )
        row["sessions"] += 1
        for t in s.turns:
            rep["sources"][t.chat_mode_source] = (
                rep["sources"].get(t.chat_mode_source, 0) + 1
            )
            # An answer with no text cannot be read, and there are two ways to
            # get one: no assistant message at all (B13's lost turns) and an
            # assistant message that is the empty string (B13's blank replies).
            # P4.2 fixed both; keep them apart here so this report never
            # silently restates the frozen "15 turns without a reply" as 17.
            shape = t.recorded_answer_shape or (
                "blank_reply" if t.got_reply else "no_reply"
            )
            rep["shapes"][shape] = rep["shapes"].get(shape, 0) + 1
            row[shape] += 1
            if t.chat_mode_source == "default":
                rep["default_source_turns"].append(f"{s.session_id}:{t.index}")
            rsrc = t.research_mode_source or "unrecorded"
            rep["research_sources"][rsrc] = rep["research_sources"].get(rsrc, 0) + 1
            key = {"unknown": "research_unknown", "reviewer_partial": "research_partial",
                   "default": "research_default", "unrecorded": "research_default"}.get(rsrc)
            if key:
                rep[key].append(f"{s.session_id}:{t.index}")
            if (
                s.filter_chat_mode
                and t.recorded_answer_shape in ("research", "conversational")
                and SHAPE_TO_MODE[t.recorded_answer_shape] != s.filter_chat_mode
            ):
                rep["snapshot_disagreements"].append(
                    f"{s.session_id}:{t.index} snapshot={s.filter_chat_mode} "
                    f"marker={SHAPE_TO_MODE[t.recorded_answer_shape]}"
                )
    return rep


def load_sessions(
    csv_path: str | None = None,
    classification: str | None = None,
    research_reads: str | None = None,
) -> list[Session]:
    """Build the replay set from the export, the frozen classification and
    the reviewer's research-type reads (P0.6)."""
    path = Path(csv_path or DEFAULT_CSV)
    if not path.exists():
        raise SystemExit(
            f"Transcript export not found at {path}.\n"
            "It is deliberately not committed (lawyers' verbatim casework "
            "questions). Regenerate from Admin Portal -> Developer -> Session "
            "transcripts export (all time), or set REPLAY_CSV."
        )
    cls_path = Path(classification or DEFAULT_CLASSIFICATION)
    cls = json.loads(cls_path.read_text(encoding="utf-8"))
    reads = load_research_reads(research_reads)

    # utf-8-sig: the export carries a BOM.
    rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig")))

    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["Session ID"], []).append(r)

    out: list[Session] = []
    for sid, srows in grouped.items():
        c = cls.get(sid)
        if c is None:
            raise SystemExit(
                f"Session {sid} is in the export but not in {cls_path.name}. "
                "The classification is frozen — reconcile before replaying."
            )
        head = srows[0]

        snapshot_mode = _blank(head.get("Filter: Chat mode"))

        yf, df = _year_or_date(head.get("Filter: Date from"))
        yt, dt = _year_or_date(head.get("Filter: Date to"))

        raw_sessions = _blank(head.get("Filter: Sessions"))
        sess_list: list | None = None
        if raw_sessions:
            try:
                sess_list = [
                    int(x) for x in raw_sessions.replace(";", ",").split(",") if x.strip()
                ]
            except ValueError:
                sess_list = None

        # "Message #" is 1-based within the thread; sort numerically — string
        # order puts #10 before #2 on the long sessions.
        srows_sorted = sorted(srows, key=lambda r: int(r["Message #"] or 0))

        turns: list[Turn] = []
        cost = 0.0
        models: list[str] = []
        for r in srows_sorted:
            role = r["Message role"]
            content = r["Message content"] or ""
            if role == "user":
                turns.append(
                    Turn(
                        index=len(turns) + 1,
                        question=content,
                        # Filled by _resolve_modes once every answer is in:
                        # the shape of the turn AFTER this one is evidence for
                        # a turn that got no reply.
                        chat_mode="",
                        chat_mode_source="",
                        got_reply=False,
                    )
                )
            elif role == "assistant":
                if r.get("Message cost (USD)"):
                    try:
                        cost += float(r["Message cost (USD)"])
                    except ValueError:
                        pass
                m = _blank(r.get("Message model"))
                if m and m not in models:
                    models.append(m)
                if not turns:
                    continue  # an assistant message with no preceding user turn
                t = turns[-1]
                t.got_reply = True
                t.recorded_answer_chars = len(content)
                t.recorded_answer_shape = answer_shape(content)
                t.recorded_model_blank = m is None
                if r.get("Message cost (USD)"):
                    try:
                        t.recorded_cost_usd = round(float(r["Message cost (USD)"]), 6)
                    except ValueError:
                        pass

        _resolve_modes(turns, snapshot_mode)

        # P4.1: the export states one research type per session, or none —
        # blank for the twelve P0.5 sessions, where the reviewer's reads
        # decide and a turn nothing settles is `unknown` (P0.6).
        stated_rm = _blank(head.get("Filter: Research mode"))
        _resolve_research_modes(sid, turns, stated_rm, reads)

        out.append(
            Session(
                session_id=sid,
                user=c.get("user", ""),
                thread=c.get("thread", ""),
                verdict=c["verdict"],
                primary=c.get("primary", ""),
                secondary=c.get("secondary", []),
                diag=c.get("diag", ""),
                session_mode=_blank(head.get("Session mode")),
                filter_chat_mode=snapshot_mode,
                research_mode=stated_rm,
                jurisdiction=_blank(head.get("Filter: Jurisdiction")),
                year_from=yf,
                year_to=yt,
                date_from=df,
                date_to=dt,
                court=_blank(head.get("Filter: Court")),
                legislation_type=_blank(head.get("Filter: Legislation type")),
                current_only=(head.get("Filter: Current only") or "").strip().lower()
                == "true",
                record_type=_blank(head.get("Filter: Record type")),
                sessions=sess_list,
                house=_blank(head.get("Filter: House")),
                turns=turns,
                recorded_cost_usd=round(cost, 6),
                recorded_models=models,
            )
        )

    out.sort(key=lambda s: s.session_id)
    return out


def reconciliation_report(sessions: list[Session]) -> dict:
    """Cross-check the per-turn Deep Research marker against the exported
    thread-level `Session mode`. A disagreement is a finding, not an error —
    surface it rather than swallowing it."""
    rep = {
        "marker_but_not_session_mode": [],
        "session_mode_but_no_marker": [],
        "session_mode_blank_with_marker": [],
    }
    for s in sessions:
        # Only a COMPLETED Deep Research report counts on either side: the
        # exporter derives `Session mode` from `messages.research_plan`, which
        # a planner clarification never writes, so a `planner_marker` turn
        # (P4.1) is Deep Research the exporter cannot see.
        has = any(t.chat_mode_source == "dr_marker" for t in s.turns)
        if has and s.session_mode == "deep_research":
            continue
        if has and s.session_mode is None:
            rep["session_mode_blank_with_marker"].append(s.session_id)
        elif has:
            rep["marker_but_not_session_mode"].append(s.session_id)
        elif s.session_mode == "deep_research":
            rep["session_mode_but_no_marker"].append(s.session_id)
    return rep


# --- Scripted sessions (P4.1) ------------------------------------------------
#
# A row's acceptance can be a sequence the pre-pilot never ran: P4.1's is
# "refusal, mode change, same question", which needs the research type to
# CHANGE between turns. A script is a small committed JSON file that builds a
# session out of an exported one's turns by index, so the lawyer's question
# text stays in the export and never in the repo:
#
#   {"session_id": "p41_6346", "base": "6346", "verdict": "FAIL",
#    "primary": "B7", "note": "...",
#    "turns": [{"from_turn": 1, "research_mode": "legislation_only"},
#              {"from_turn": 3, "research_mode": "legislation_and_case_law"},
#              {"from_turn": 1, "research_mode": "legislation_and_case_law"}]}
#
# `chat_mode` on a scripted turn defaults to the base turn's resolved mode;
# `question` may be given literally instead of `from_turn` for text that is
# not a lawyer's (a harness prompt such as "Switch to Research mode"). Every
# other filter is the base session's.

SCRIPT_RESEARCH_MODES = (
    "legislation_only", "case_law_only", "legislation_and_case_law",
)


def load_script(path: Path | str) -> dict:
    p = Path(path)
    script = json.loads(p.read_text(encoding="utf-8"))
    for key in ("session_id", "base", "turns"):
        if key not in script:
            raise SystemExit(f"{p.name}: script needs `{key}`")
    if not script["turns"]:
        raise SystemExit(f"{p.name}: script has no turns")
    for i, t in enumerate(script["turns"], 1):
        if t.get("research_mode") not in SCRIPT_RESEARCH_MODES:
            raise SystemExit(
                f"{p.name}: turn {i} needs research_mode in {SCRIPT_RESEARCH_MODES}"
            )
        if "from_turn" not in t and not t.get("question"):
            raise SystemExit(f"{p.name}: turn {i} needs `from_turn` or `question`")
    return script


def scripted_session(script: dict, sessions: list) -> Session:
    """Build a Session from a script over one of the export's sessions."""
    base = next((s for s in sessions if s.session_id == str(script["base"])), None)
    if base is None:
        raise SystemExit(f"script {script['session_id']}: base session "
                         f"{script['base']} is not in the replay set")
    by_index = {t.index: t for t in base.turns}
    turns: list[Turn] = []
    for i, st in enumerate(script["turns"], 1):
        src = by_index.get(st.get("from_turn")) if "from_turn" in st else None
        if "from_turn" in st and src is None:
            raise SystemExit(f"script {script['session_id']}: base {base.session_id} "
                             f"has no turn {st['from_turn']}")
        question = st.get("question") or src.question
        chat_mode = st.get("chat_mode") or (src.chat_mode if src else DEFAULT_CHAT_MODE)
        turns.append(Turn(
            index=i,
            question=question,
            chat_mode=chat_mode,
            chat_mode_source="script",
            got_reply=bool(src.got_reply) if src else False,
            recorded_cost_usd=src.recorded_cost_usd if src else 0.0,
            recorded_answer_chars=src.recorded_answer_chars if src else 0,
            recorded_answer_shape=src.recorded_answer_shape if src else None,
            research_mode=st["research_mode"],
            research_mode_source="script",
        ))
    s = Session(
        session_id=str(script["session_id"]),
        user=base.user,
        thread=base.thread,
        verdict=script.get("verdict") or base.verdict,
        primary=script.get("primary") or base.primary,
        secondary=list(script.get("secondary") or base.secondary),
        diag=script.get("note") or base.diag,
        session_mode=base.session_mode,
        filter_chat_mode=base.filter_chat_mode,
        research_mode=turns[0].research_mode,
        jurisdiction=base.jurisdiction,
        year_from=base.year_from,
        year_to=base.year_to,
        date_from=base.date_from,
        date_to=base.date_to,
        court=base.court,
        legislation_type=base.legislation_type,
        current_only=base.current_only,
        record_type=base.record_type,
        sessions=base.sessions,
        house=base.house,
        turns=turns,
        recorded_cost_usd=base.recorded_cost_usd,
        recorded_models=list(base.recorded_models),
        script=script,
    )
    return s


def freeze(out_path: Path | None = None, **kw) -> Path:
    """Write the 41 defect-carrying sessions to the gitignored replay set."""
    sessions = load_sessions(**kw)
    target = [s for s in sessions if s.verdict in ("FAIL", "DEFECT")]
    path = Path(out_path or DEFAULT_REPLAY_SET)
    dr_turns = sum(len(s.deep_research_turns) for s in target)
    payload = {
        "schema": "aila-replay-set/2",
        "source_csv": str(Path(kw.get("csv_path") or DEFAULT_CSV)),
        "note": (
            "NOT FOR COMMIT — contains lawyers' verbatim research questions. "
            "Regenerate from Admin Portal -> Developer -> Session transcripts "
            "export (all time)."
        ),
        "counts": {
            "sessions": len(target),
            "fail": sum(1 for s in target if s.verdict == "FAIL"),
            "defect": sum(1 for s in target if s.verdict == "DEFECT"),
            "user_turns": sum(len(s.turns) for s in target),
            "deep_research_turns": dr_turns,
            "turns_without_reply": sum(
                1 for s in target for t in s.turns if not t.got_reply
            ),
        },
        "reconciliation": reconciliation_report(sessions),
        "chat_modes": mode_report(sessions),
        "sessions": [s.to_json() for s in target],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Freeze the pre-pilot replay set.")
    p.add_argument("--csv", default=None)
    p.add_argument("--classification", default=None)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    written = freeze(
        out_path=Path(a.out) if a.out else None,
        csv_path=a.csv,
        classification=a.classification,
    )
    data = json.loads(written.read_text(encoding="utf-8"))
    c = data["counts"]
    print(f"Wrote {written}")
    print(f"  sessions              {c['sessions']} (FAIL {c['fail']}, DEFECT {c['defect']})")
    print(f"  user turns            {c['user_turns']}")
    print(f"  deep-research turns   {c['deep_research_turns']}")
    print(f"  turns without a reply {c['turns_without_reply']}  (bucket B13 / P4.2)")
    print(f"  reconciliation        {json.dumps(data['reconciliation'])}")
    cm = data["chat_modes"]
    print(f"  chat-mode sources     {json.dumps(cm['sources'])}")
    print(f"  snapshot vs marker    {len(cm['snapshot_disagreements'])} disagreement(s)"
          f"{': ' + '; '.join(cm['snapshot_disagreements']) if cm['snapshot_disagreements'] else ''}")
    print(f"  research-type sources {json.dumps(cm['research_sources'])}")
    print(f"  research type unknown {', '.join(cm['research_unknown']) or 'none'}")
