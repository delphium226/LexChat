#!/usr/bin/env python
"""Pre-pilot session replay runner (FIX_PLAN P0.1).

Replays a pre-pilot session's user turns, in order, through `/api/system/chat`
under that session's recorded filters, and writes the `audit` trace plus the
final answer to one JSON file per run.

Why `/api/system/chat` and not `/api/chat`
------------------------------------------
`/api/chat` emits no tool events, so a replay against it can only see what was
*answered*, never what was *retrieved* — and most rows in FIX_PLAN assert on the
retrieval. `/api/system/chat` runs the identical pipeline with
`emit_tool_details=True` and emits the structured `audit` event
(`delegations[] -> tools[] -> api_calls[]`, `raw_result` beside `final_result`).
Spec: `docs/api/AUDIT_TRACE.md`.

Four things about this runner that are load-bearing, and non-obvious
-------------------------------------------------------------------
1. **The model is pinned in the DATABASE, not in the request body.**
   `system.py` resolves `provider_config.get("model") or body.model`, so the
   `provider.openrouter` app_settings row always wins and `body.model` is a
   fallback that never fires in practice. `replay.py pin` writes that row (and
   stashes the previous value for `restore`); every run then asserts the
   returned `audit["model"]` equals the pin and marks the run `model_mismatch`
   if it does not. A replay on the wrong model measures a different system —
   CLAUDE.md records model choice as the dominant variable, ~10x on identical
   infrastructure.

2. **Chat mode is a property of the TURN, not of the session.** Deep Research is
   one-shot — the frontend drops back to conversational when a run completes —
   so a session flagged `deep_research` typically ran one Deep Research turn
   among several conversational ones, and not necessarily the first: in 6409 it
   was turn 6 of 11, in 6406 turns 2 and 3 of 12. Only 20 of the 155 replayed
   turns are Deep Research. `replay_set.py` derives this per turn and documents
   the evidence; replaying a whole session in one mode would measure a system
   nobody used and, on the Deep Research side, cost several times more.

3. **Deep Research needs a plan first.** `/api/system/chat` returns HTTP 400 for
   `chat_mode="deep_research"` without `deep_research_plan`, by design, so a
   harness cannot bank a standard research run as a Deep Research result. The
   pre-pilot's *approved* plans are not recoverable (see `replay_set.py`), so a
   DR turn here drafts a fresh plan via `POST /api/research/plan` and executes
   it unedited. That adds planner stochasticity the original session did not
   have; the drafted plan is written into the run file so it stays inspectable.

4. **The local prompt cache is cross-user and would make n=3 a single sample.**
   Run 1 populates it; runs 2 and 3 read it back and skip summarisation, so the
   repetitions stop being independent draws and the whole point of n>1
   (Invariant 4: "a single replay pass is not evidence") is lost. `pin` turns
   `local_prompt_cache_enabled` off for the duration and `restore` puts it back.
   Every run records the flag state it actually ran under.

Usage
-----
    python -m tools.replay check                  # model served? server up? state?
    python -m tools.replay pin                    # pin model + cache flag (saves prior state)
    python -m tools.replay restore                # put the dev box back
    python -m tools.replay run --session 6404 --reps 1
    python -m tools.replay run --all --out-dir ../docs/prepilot-fixes/evidence/replay/baseline

Run from `server_py/`. Output is gitignored (lawyers' verbatim questions).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_set import Session, load_sessions  # noqa: E402

# --- Pinned configuration (FIX_PLAN "Replay configuration", 2026-09-14) --------

# All 176 pre-pilot assistant messages ran on this model. Do not substitute: if
# it is withdrawn, stop and re-decide (FIX_PLAN P0.1).
PINNED_MODEL = "google/gemini-3.1-pro-preview"

# The pre-pilot's summarisation model is NOT recoverable — no per-message column
# records it and the pre-pilot DB is not on this machine. None means "leave the
# dev box's value alone and record what it was", which is the honest option:
# inventing a value would be a silent confound either way.
PINNED_SUMMARISATION_MODEL: str | None = None

# Feature flags forced for the duration of a sweep, with the reason.
PINNED_FEATURES = {
    # n>1 repetitions must be independent draws; a cross-user summary cache
    # makes runs 2..n echoes of run 1.
    "local_prompt_cache_enabled": False,
}

DEFAULT_BASE_URL = os.environ.get("REPLAY_BASE_URL", "http://localhost:8000")
DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://lexuser:lexpassword@localhost:5432/lexchat"
)
DEFAULT_USER = os.environ.get("REPLAY_USER", "admin")
DEFAULT_PASSWORD = os.environ.get("REPLAY_PASSWORD", "admin")

# A single deep-research turn can run eight worker steps against live APIs.
TURN_TIMEOUT_S = float(os.environ.get("REPLAY_TURN_TIMEOUT_S", "1800"))
PLAN_TIMEOUT_S = float(os.environ.get("REPLAY_PLAN_TIMEOUT_S", "300"))

STATE_PATH = Path(__file__).resolve().parent / ".replay_pin_state.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "prepilot-fixes" / "evidence" / "replay"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Provider / feature state (read and written straight in the DB) -----------
#
# Settings are DB-first by design (CLAUDE.md): `.env` holds startup fallbacks
# only, and the Admin Portal writes the same rows this does.


async def _db_connect():
    import asyncpg

    return await asyncpg.connect(DEFAULT_DB_URL)


async def read_state() -> dict:
    """Current provider config and feature flags, api_key never returned."""
    conn = await _db_connect()
    try:
        rows = await conn.fetch(
            "SELECT key, value FROM app_settings WHERE key IN "
            "('active_provider', 'features', 'provider.openrouter')"
        )
        d = {r["key"]: r["value"] for r in rows}
        provider = json.loads(d.get("provider.openrouter") or "{}")
        features = json.loads(d.get("features") or "{}")
        return {
            "active_provider": d.get("active_provider"),
            "model": provider.get("model"),
            "summarisation_model": provider.get("summarisation_model"),
            "temperature": provider.get("temperature"),
            "api_key_present": bool(provider.get("api_key")),
            "features": features,
        }
    finally:
        await conn.close()


async def _write_provider_and_features(
    model: str | None,
    summarisation_model: str | None,
    feature_overrides: dict[str, bool],
) -> None:
    conn = await _db_connect()
    try:
        async with conn.transaction():
            raw = await conn.fetchval(
                "SELECT value FROM app_settings WHERE key='provider.openrouter'"
            )
            provider = json.loads(raw or "{}")
            if model is not None:
                provider["model"] = model
            if summarisation_model is not None:
                provider["summarisation_model"] = summarisation_model
            await conn.execute(
                "UPDATE app_settings SET value=$1 WHERE key='provider.openrouter'",
                json.dumps(provider),
            )
            if feature_overrides:
                raw_f = await conn.fetchval(
                    "SELECT value FROM app_settings WHERE key='features'"
                )
                features = json.loads(raw_f or "{}")
                features.update(feature_overrides)
                await conn.execute(
                    "UPDATE app_settings SET value=$1 WHERE key='features'",
                    json.dumps(features),
                )
    finally:
        await conn.close()


# --- Preflight ---------------------------------------------------------------


async def openrouter_serves(model: str, api_key: str | None) -> dict:
    """Is `model` in the catalogue, and does it actually answer?

    Catalogue presence is necessary and not sufficient — a withdrawn preview
    model can linger in a listing — so this also issues one minimal
    tool-calling completion, which is the shape every replay turn depends on.
    """
    out: dict[str, Any] = {"model": model, "in_catalogue": False, "served": None}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get("https://openrouter.ai/api/v1/models")
        r.raise_for_status()
        ids = {m["id"] for m in r.json().get("data", [])}
        out["in_catalogue"] = model in ids

        if not api_key:
            out["served"] = None
            out["detail"] = "no API key available for a live probe"
            return out

        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with the word OK."}],
            "max_tokens": 2000,
            "temperature": 0,
        }
        try:
            pr = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if pr.status_code != 200:
                out["served"] = False
                out["detail"] = f"HTTP {pr.status_code}: {pr.text[:300]}"
                return out
            data = pr.json()
            out["served"] = True
            out["returned_model"] = data.get("model")
            out["provider"] = data.get("provider")
            out["probe_cost_usd"] = (data.get("usage") or {}).get("cost")
        except Exception as e:  # pragma: no cover - network
            out["served"] = False
            out["detail"] = f"{type(e).__name__}: {e}"
    return out


async def _api_key() -> str | None:
    conn = await _db_connect()
    try:
        raw = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key='provider.openrouter'"
        )
        return json.loads(raw or "{}").get("api_key") or None
    finally:
        await conn.close()


# --- SSE client --------------------------------------------------------------


@dataclass
class TurnResult:
    """One replayed user turn."""

    turn: int
    question: str
    chat_mode: str = "research"
    chat_mode_source: str = ""
    status: str = "ok"  # ok | error | needs_clarification | http_error
    answer: str = ""
    error: str | None = None
    audit: dict | None = None
    timing: dict | None = None
    plan: dict | None = None
    plan_clarification: dict | None = None
    suggestions: list = field(default_factory=list)
    elapsed_s: float = 0.0
    events_seen: dict = field(default_factory=dict)
    # What the pre-pilot recorded for this same turn, so a run file can be read
    # against its own baseline without going back to the CSV.
    prepilot: dict = field(default_factory=dict)


class ReplayClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(TURN_TIMEOUT_S, connect=15.0),
            follow_redirects=True,
        )
        await self.login()
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()

    async def login(self) -> None:
        """Authenticate. The endpoint sits behind `get_current_user`.

        The login response carries the token in the body as well as setting the
        cookie, and `get_current_user`'s Authorization-header branch exists for
        machine callers — which is what this is. The httpx client keeps the
        cookie too, so both paths are live; the header is the one relied on.
        """
        assert self._client is not None
        r = await self._client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if r.status_code != 200:
            raise SystemExit(
                f"Login failed for {self.username!r}: HTTP {r.status_code} {r.text[:200]}\n"
                "Set REPLAY_USER / REPLAY_PASSWORD if the dev box differs."
            )
        self.token = r.json()["token"]
        self._client.headers["Authorization"] = f"Bearer {self.token}"

    def _filters(self, s: Session) -> dict:
        return {
            "research_mode": s.research_mode,
            "jurisdiction": s.jurisdiction,
            "year_from": s.year_from,
            "year_to": s.year_to,
            "date_from": s.date_from,
            "date_to": s.date_to,
            "court": s.court,
            "legislation_type": s.legislation_type,
            "current_only": s.current_only,
            "record_type": s.record_type,
            "sessions": s.sessions,
            "house": s.house,
        }

    async def draft_plan(self, messages: list[dict], s: Session) -> dict:
        assert self._client is not None
        body = {"messages": messages, "model": PINNED_MODEL, **self._filters(s)}
        r = await self._client.post(
            "/api/research/plan", json=body, timeout=PLAN_TIMEOUT_S
        )
        if r.status_code != 200:
            return {"_http_error": f"HTTP {r.status_code}: {r.text[:400]}"}
        return r.json()

    async def chat(
        self, messages: list[dict], s: Session, chat_mode: str, plan: dict | None
    ) -> TurnResult:
        """One `/api/system/chat` request, consuming the SSE stream."""
        assert self._client is not None
        body: dict[str, Any] = {
            "messages": messages,
            # A fallback only: provider_config["model"] wins in system.py. Sent
            # anyway so a misconfigured box fails toward the pin, not away.
            "model": PINNED_MODEL,
            "chat_mode": chat_mode,
            "audit": True,
            "audit_max_field_chars": 0,
            **self._filters(s),
        }
        if plan is not None:
            body["deep_research_plan"] = plan

        result = TurnResult(turn=0, question=messages[-1]["content"])
        counts: dict[str, int] = {}
        t0 = time.perf_counter()
        try:
            async with self._client.stream(
                "POST", "/api/system/chat", json=body
            ) as resp:
                if resp.status_code != 200:
                    raw = (await resp.aread()).decode("utf-8", "replace")
                    result.status = "http_error"
                    result.error = f"HTTP {resp.status_code}: {raw[:400]}"
                    result.elapsed_s = time.perf_counter() - t0
                    return result
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    kind = ev.get("type", "?")
                    counts[kind] = counts.get(kind, 0) + 1
                    if kind == "audit":
                        result.audit = ev
                    elif kind == "timing":
                        result.timing = ev
                    elif kind == "result":
                        msg = ev.get("message") or {}
                        result.answer = msg.get("content", "") or ""
                        result.suggestions = msg.get("suggestions") or []
                    elif kind == "error":
                        result.status = "error"
                        result.error = ev.get("error")
        except Exception as e:
            result.status = "error"
            result.error = f"{type(e).__name__}: {e}"

        if not result.answer and result.audit:
            # A failed run still emits whatever trace it gathered.
            result.answer = result.audit.get("answer") or ""
        result.events_seen = counts
        result.elapsed_s = time.perf_counter() - t0
        return result


# --- Replay ------------------------------------------------------------------


async def replay_session(
    client: ReplayClient, s: Session, rep: int, pinned_state: dict
) -> dict:
    """Replay every user turn of one session, carrying the history forward.

    The endpoint is stateless — `messages` is the whole conversation — so a
    multi-turn session is replayed the way the frontend drives it: send turn 1,
    append the answer we got back (NOT the pre-pilot's answer), send turn 2.
    Appending our own answer is what makes turn 2 a replay of the system rather
    than a replay of a transcript, which is the point for B6/B7 rows where the
    defect lives in how the model reacts to its own earlier turn.
    """
    started = _now()
    t0 = time.perf_counter()
    messages: list[dict] = []
    turns: list[TurnResult] = []

    for t in s.turns:
        i, question, mode = t.index, t.question, t.chat_mode
        messages.append({"role": "user", "content": question})

        plan = None
        plan_clarification = None
        if mode == "deep_research":
            drafted = await client.draft_plan(messages, s)
            if "_http_error" in drafted:
                tr = TurnResult(turn=i, question=question, chat_mode=mode,
                                status="error",
                                error=f"planner: {drafted['_http_error']}")
                turns.append(tr)
                messages.append({"role": "assistant", "content": ""})
                continue
            if drafted.get("needs_clarification"):
                # The lawyer answered this live; the runner cannot. Record it,
                # carry the question into the history as the assistant turn,
                # and let the next recorded user turn stand as the answer —
                # which is what the transcript shows happening.
                plan_clarification = drafted
                tr = TurnResult(
                    turn=i,
                    question=question,
                    chat_mode=mode,
                    status="needs_clarification",
                    answer=drafted.get("question", ""),
                    plan_clarification=drafted,
                )
                turns.append(tr)
                messages.append(
                    {"role": "assistant", "content": drafted.get("question", "")}
                )
                continue
            plan = drafted.get("plan")
            if not plan:
                tr = TurnResult(turn=i, question=question, chat_mode=mode,
                                status="error",
                                error=f"planner returned no plan: {str(drafted)[:300]}")
                turns.append(tr)
                messages.append({"role": "assistant", "content": ""})
                continue

        tr = await client.chat(messages, s, mode, plan)
        tr.turn = i
        tr.chat_mode = mode
        tr.chat_mode_source = t.chat_mode_source
        tr.plan = plan
        tr.plan_clarification = plan_clarification
        tr.prepilot = {
            "got_reply": t.got_reply,
            "cost_usd": t.recorded_cost_usd,
            "answer_chars": t.recorded_answer_chars,
        }
        turns.append(tr)
        messages.append({"role": "assistant", "content": tr.answer})

        print(
            f"    turn {i}/{len(s.turns)} [{mode}]: {tr.status}"
            f"  {tr.elapsed_s:6.1f}s  {len(tr.answer):6d} chars"
            f"  ${(tr.timing or {}).get('total_cost_usd', 0):.4f}"
            f"  model={(tr.audit or {}).get('model')}",
            flush=True,
        )

    # A run on the wrong model measures a different system; flag it loudly
    # rather than letting it into a baseline unnoticed.
    models = {t.audit.get("model") for t in turns if t.audit}
    mismatch = sorted(m for m in models if m and m != PINNED_MODEL)

    total_cost = sum((t.timing or {}).get("total_cost_usd", 0.0) for t in turns)
    return {
        "schema": "aila-replay/1",
        "session_id": s.session_id,
        "rep": rep,
        "started_at": started,
        "finished_at": _now(),
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "verdict_at_prepilot": s.verdict,
        "primary_bucket": s.primary,
        "secondary_buckets": s.secondary,
        "diag_at_prepilot": s.diag,
        "session_mode_at_prepilot": s.session_mode,
        "filter_snapshot_chat_mode": s.filter_chat_mode,
        "deep_research_turns": s.deep_research_turns,
        "filters": client._filters(s),
        "pinned_model": PINNED_MODEL,
        "model_mismatch": mismatch,
        "runtime_state": pinned_state,
        "total_cost_usd": round(total_cost, 6),
        "turns": [
            {
                "turn": t.turn,
                "question": t.question,
                "chat_mode": t.chat_mode,
                "chat_mode_source": t.chat_mode_source,
                "prepilot": t.prepilot,
                "status": t.status,
                "answer": t.answer,
                "error": t.error,
                "elapsed_s": round(t.elapsed_s, 1),
                "suggestions": t.suggestions,
                "plan": t.plan,
                "plan_clarification": t.plan_clarification,
                "events_seen": t.events_seen,
                "timing": t.timing,
                "audit": t.audit,
            }
            for t in turns
        ],
    }


def _reps_for(s: Session, override: int | None) -> int:
    """n=3 for a FAIL, n=1 for a DEFECT (FIX_PLAN, Invariant 4)."""
    if override:
        return override
    return 3 if s.verdict == "FAIL" else 1


async def cmd_run(args) -> int:
    sessions = load_sessions(csv_path=args.csv, classification=args.classification)
    if args.session:
        wanted = set(args.session)
        sessions = [s for s in sessions if s.session_id in wanted]
        missing = wanted - {s.session_id for s in sessions}
        if missing:
            print(f"[!] unknown session id(s): {sorted(missing)}", file=sys.stderr)
            return 2
    elif args.all:
        sessions = [s for s in sessions if s.verdict in ("FAIL", "DEFECT")]
    else:
        print("Give --session ID [ID ...] or --all", file=sys.stderr)
        return 2

    state = await read_state()
    if state["model"] != PINNED_MODEL and not args.allow_unpinned:
        print(
            f"[!] active model is {state['model']!r}, not the pinned "
            f"{PINNED_MODEL!r}.\n    Run `python -m tools.replay pin` first, "
            "or pass --allow-unpinned to measure a different system deliberately.",
            file=sys.stderr,
        )
        return 2
    if state["features"].get("local_prompt_cache_enabled") and not args.allow_unpinned:
        print(
            "[!] local_prompt_cache_enabled is ON. Repetitions would not be "
            "independent draws (run 2 reads run 1's summaries).\n"
            "    Run `python -m tools.replay pin`, or pass --allow-unpinned.",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_state = {
        "model": state["model"],
        "summarisation_model": state["summarisation_model"],
        "temperature": state["temperature"],
        "active_provider": state["active_provider"],
        "local_prompt_cache_enabled": state["features"].get(
            "local_prompt_cache_enabled"
        ),
        "tool_memo_enabled": state["features"].get("tool_memo_enabled"),
        "prompt_caching_enabled": state["features"].get("prompt_caching_enabled"),
        "suggested_questions_enabled": state["features"].get(
            "suggested_questions_enabled"
        ),
        "git_head": _git_head(),
    }

    planned = sum(_reps_for(s, args.reps) for s in sessions)
    print(
        f"Replaying {len(sessions)} session(s), {planned} run(s) total, "
        f"model={state['model']}, head={runtime_state['git_head']}\n"
        f"Output: {out_dir}",
        flush=True,
    )

    # Deliberately serial. Running sessions concurrently would cut the wall
    # clock several-fold, but three parallel deep-research runs fan out to a
    # shared, rate-limited LEX API; `_request_with_retry` backs off on 429 and
    # returns the error once its budget is spent, which shows up as a degraded
    # retrieval — i.e. as a failure reproducing when it did not. A corrupted
    # baseline costs more than the hours saved.
    grand_cost = 0.0
    done = 0
    async with ReplayClient(args.base_url, args.user, args.password) as client:
        for s in sessions:
            reps = _reps_for(s, args.reps)
            for rep in range(1, reps + 1):
                path = out_dir / f"{s.session_id}_rep{rep}.json"
                if path.exists() and not args.overwrite:
                    print(f"  [skip] {path.name} exists", flush=True)
                    continue
                if args.max_spend and grand_cost >= args.max_spend:
                    print(
                        f"\n[!] STOPPING: spend ${grand_cost:.2f} reached the "
                        f"--max-spend ${args.max_spend:.2f} cap. "
                        f"{done} run(s) written; re-run to resume (existing "
                        "files are skipped).",
                        flush=True,
                    )
                    return 3
                dr = s.deep_research_turns
                print(
                    f"  {s.session_id} rep {rep}/{reps} "
                    f"({s.verdict}/{s.primary or '-'}, {len(s.turns)} turn(s)"
                    f"{', DR on ' + str(dr) if dr else ''})",
                    flush=True,
                )
                rec = await replay_session(client, s, rep, runtime_state)
                path.write_text(
                    json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                grand_cost += rec["total_cost_usd"]
                done += 1
                print(
                    f"    -> {path.name}  ${rec['total_cost_usd']:.4f}  "
                    f"(running ${grand_cost:.2f})",
                    flush=True,
                )

    print(f"\n{done} run(s) written. Recorded spend ${grand_cost:.2f}.")
    return 0


def _git_head() -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


async def cmd_check(args) -> int:
    state = await read_state()
    key = await _api_key()
    print("Provider state (from app_settings, DB-first by design):")
    for k in ("active_provider", "model", "summarisation_model", "temperature"):
        print(f"  {k:24} = {state[k]!r}")
    print(f"  {'api_key_present':24} = {state['api_key_present']}")
    print("\nFeature flags that change what a replay measures:")
    for k in (
        "local_prompt_cache_enabled",
        "tool_memo_enabled",
        "prompt_caching_enabled",
        "suggested_questions_enabled",
        "deep_research_mode_enabled",
    ):
        print(f"  {k:28} = {state['features'].get(k)}")

    print(f"\nPinned model probe: {PINNED_MODEL}")
    probe = await openrouter_serves(PINNED_MODEL, key)
    for k, v in probe.items():
        print(f"  {k:16} = {v!r}")

    ok = probe["in_catalogue"] and probe["served"] is not False
    print(f"\nServer at {args.base_url}:")
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{args.base_url}/api/bot-info")
            print(f"  GET /api/bot-info -> {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  unreachable: {type(e).__name__}: {e}")
        print("  (start it with: python -m uvicorn src.main:app --port 8000)")

    print(f"\nVERDICT: pinned model {'AVAILABLE' if ok else 'NOT AVAILABLE'}")
    if not ok:
        print("STOP — do not substitute a model. See FIX_PLAN P0.1.")
    return 0 if ok else 1


async def cmd_pin(args) -> int:
    before = await read_state()
    key = await _api_key()
    probe = await openrouter_serves(PINNED_MODEL, key)
    if not probe["in_catalogue"] or probe["served"] is False:
        print(f"[!] {PINNED_MODEL} is not available: {probe}", file=sys.stderr)
        print("STOP — do not substitute. See FIX_PLAN P0.1.", file=sys.stderr)
        return 1

    if not STATE_PATH.exists():
        STATE_PATH.write_text(
            json.dumps(
                {
                    "saved_at": _now(),
                    "model": before["model"],
                    "summarisation_model": before["summarisation_model"],
                    "features": {
                        k: before["features"].get(k) for k in PINNED_FEATURES
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Saved previous state to {STATE_PATH.name}")
    else:
        print(f"{STATE_PATH.name} already exists — keeping the ORIGINAL saved state.")

    await _write_provider_and_features(
        PINNED_MODEL, PINNED_SUMMARISATION_MODEL, PINNED_FEATURES
    )
    after = await read_state()
    print(f"  model                 {before['model']!r} -> {after['model']!r}")
    print(
        f"  summarisation_model   {before['summarisation_model']!r} -> "
        f"{after['summarisation_model']!r}  (deliberately unchanged — the "
        "pre-pilot's value is not recoverable)"
    )
    for k in PINNED_FEATURES:
        print(
            f"  {k}   {before['features'].get(k)!r} -> {after['features'].get(k)!r}"
        )
    print("\nRestart the server so it re-reads nothing stale, then run the sweep.")
    print("Remember: `python -m tools.replay restore` when the sweep is done.")
    return 0


async def cmd_restore(args) -> int:
    if not STATE_PATH.exists():
        print(f"[!] no {STATE_PATH.name} — nothing to restore.", file=sys.stderr)
        return 1
    saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    await _write_provider_and_features(
        saved.get("model"),
        saved.get("summarisation_model"),
        {k: v for k, v in (saved.get("features") or {}).items() if v is not None},
    )
    after = await read_state()
    print(f"Restored from {saved['saved_at']}:")
    print(f"  model               = {after['model']!r}")
    print(f"  summarisation_model = {after['summarisation_model']!r}")
    for k in PINNED_FEATURES:
        print(f"  {k} = {after['features'].get(k)!r}")
    STATE_PATH.unlink()
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="replay", description=__doc__.split("\n")[0]
    )
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="preflight: model served, server up, current state")
    sub.add_parser("pin", help="pin the model + replay feature flags in the DB")
    sub.add_parser("restore", help="undo pin")

    r = sub.add_parser("run", help="replay session(s)")
    r.add_argument("--session", nargs="+", help="session id(s) from the export")
    r.add_argument("--all", action="store_true", help="every FAIL/DEFECT session")
    r.add_argument("--reps", type=int, default=None,
                   help="override; default 3 for FAIL, 1 for DEFECT")
    r.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    r.add_argument("--overwrite", action="store_true")
    r.add_argument("--max-spend", type=float, default=None,
                   help="stop before starting a run once this much has been "
                        "spent (USD); re-run to resume")
    r.add_argument("--allow-unpinned", action="store_true",
                   help="run even though the model/flags are not pinned")
    r.add_argument("--user", default=DEFAULT_USER)
    r.add_argument("--password", default=DEFAULT_PASSWORD)
    r.add_argument("--csv", default=None)
    r.add_argument("--classification", default=None)

    args = p.parse_args(list(argv) if argv is not None else None)
    fn = {"check": cmd_check, "pin": cmd_pin, "restore": cmd_restore, "run": cmd_run}[
        args.cmd
    ]
    return asyncio.run(fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
