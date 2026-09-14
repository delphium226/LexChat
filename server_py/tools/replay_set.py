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

Other decisions
---------------
* **A turn that is not Deep Research takes the session's `Filter: Chat mode`
  snapshot**, falling back to `research` (the `ChatRequest.chat_mode` default,
  and the frontend's). For a Deep Research session that snapshot is the
  post-revert `conversational`, which is the correct reading for the turns
  either side of the run: 6406 turn 1 is a conversational-mode deflection
  ("I recommend switching to Research mode"), and the user switched on for
  turn 2.
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

# `ChatRequest.chat_mode` default, and the frontend's.
DEFAULT_CHAT_MODE = "research"
# `resolve_research_mode` default.
DEFAULT_RESEARCH_MODE = "legislation_only"

# The Deep Research fingerprint. Only DEEP_RESEARCH_SYNTHESIS_PROMPT asks for a
# "**Key findings** bullet list" — see the module docstring for the measurement.
DR_MARKER = re.compile(r"\*\*key\s*findings", re.IGNORECASE)


@dataclass
class Turn:
    index: int  # 1-based position among the session's user turns
    question: str
    chat_mode: str
    chat_mode_source: str  # dr_marker | snapshot | default
    got_reply: bool
    recorded_cost_usd: float = 0.0
    recorded_answer_chars: int = 0


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

    research_mode: str = DEFAULT_RESEARCH_MODE
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


def load_sessions(
    csv_path: str | None = None,
    classification: str | None = None,
) -> list[Session]:
    """Build the replay set from the export plus the frozen classification."""
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
        fallback_mode = snapshot_mode or DEFAULT_CHAT_MODE
        fallback_source = "snapshot" if snapshot_mode else "default"

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
                        chat_mode=fallback_mode,
                        chat_mode_source=fallback_source,
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
                if r.get("Message cost (USD)"):
                    try:
                        t.recorded_cost_usd = round(float(r["Message cost (USD)"]), 6)
                    except ValueError:
                        pass
                if DR_MARKER.search(content):
                    t.chat_mode = "deep_research"
                    t.chat_mode_source = "dr_marker"

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
                research_mode=_blank(head.get("Filter: Research mode"))
                or DEFAULT_RESEARCH_MODE,
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
        has = bool(s.deep_research_turns)
        if has and s.session_mode == "deep_research":
            continue
        if has and s.session_mode is None:
            rep["session_mode_blank_with_marker"].append(s.session_id)
        elif has:
            rep["marker_but_not_session_mode"].append(s.session_id)
        elif s.session_mode == "deep_research":
            rep["session_mode_but_no_marker"].append(s.session_id)
    return rep


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
