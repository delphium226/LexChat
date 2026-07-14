# Per-Bot Efficiency Measurement — Implementation Plan

**Status:** PLANNED (not started)
**Audience:** coding agent in a fresh session — this document is self-contained; read it fully before touching code.
**Scope:** backend `server_py/` + one small frontend change. No new external dependencies.

---

## 1. Background — what exists today

The Admin Portal → Efficiency tab (`client/src/pages/admin/EfficiencyTab.jsx`) renders
`GET /api/stats/efficiency` (`server_py/src/routers/stats.py`, `get_efficiency_stats`, ~line 519).
The endpoint aggregates the `request_timings` table, which is populated per chat request in the
`finally` block of `/api/chat` (`server_py/src/routers/ai.py` ~line 242) from a `TimingCollector`
(`server_py/src/utils/stopwatch.py`) that is threaded through the whole Manager→Worker call stack.

Per-request breach alerting also exists: `evaluate_efficiency_breaches()` in
`server_py/src/config.py` (~line 126) compares a request's metrics against the module-level
`EFFICIENCY_THRESHOLDS` dict and writes an `ActivityLog(event_type="EFFICIENCY")` row on breach
(see `ai.py` ~line 259).

There are **two bots** running this same codebase as separate processes with separate databases:

- **Legislation bot** — `RESEARCH_MODE` env unset (per-request mode from the frontend:
  `legislation_only` / case-law / hybrid). Tools: `search_legislation`,
  `search_legislation_sections`, `get_legislation_text`, `search_case_law`, `get_case_law_text`.
- **Parliament bot** — `RESEARCH_MODE=parliamentary_records` (fixed via `bots/parliament/.env`).
  Tools: `search_scottish_plenary`, `get_scottish_plenary_debate`, `search_scottish_parliament`,
  `search_scottish_committee_transcripts`, `get_scottish_committee_transcript`, `search_bills`,
  `get_member_info`. A **search budget** of 3 (created in `agent_core.py` ~line 66, enforced in
  `agent_shared.py` `run_worker_tool` ~line 325) hard-stops search tools after 3 calls.

Because each bot has its own DB, the Efficiency tab already shows per-bot data. The problem is
that the *measurement itself* is legislation-calibrated and in places legislation-hard-wired, so
the parliament bot's dashboard is misleading.

## 2. Problems this plan fixes

| # | Problem | Where |
|---|---|---|
| P1 | Phase classification is stale: `search_scottish_plenary` is missing from `_PHASE1_SEARCH_TOOLS` and `get_scottish_plenary_debate` from `_PHASE2_RETRIEVAL_TOOLS` — and the plenary DB pipeline is the *preferred* route, so most parliament traffic is invisible to `avgPhase1`/`avgPhase2` and the fan-out numerator. | `stopwatch.py:3-10` |
| P2 | Redundancy key too coarse: `key_arg` falls back to `meeting_id` alone, but a transcript's identity is `(meeting_id, iob_id)`. Retrieving two *different agenda items* of one meeting (legitimate, common) is counted redundant → false red "Redundant-call rate" indicator **and** false EFFICIENCY breach rows in the activity log (`max_redundant_tool_calls: 0`). | `agent_shared.py:353-358` |
| P3 | The parliament bot's defining constraint isn't measured: budget-blocked search calls return **before** `record_worker_tool` runs, so a model hammering the budget wall looks efficient. | `agent_shared.py:328-348` |
| P4 | `avgDistinctRetrieved` counts only `legislation_id`s (`_LEGISLATION_RETRIEVAL_TOOLS`) — permanently 0 on the parliament bot. | `stopwatch.py:11-14, 119-121` |
| P5 | Fan-out ratio (`phase2_retrieval_calls / sources_kept`) is mis-shaped for parliament: every search *hit* becomes a source (`_extract_sources_from_tool`, `agent_shared.py:159-263`), inflating the denominator, while P1 deflates the numerator → the indicator is always green and uninformative. | `stats.py` SQL + `config.py:144-148` |
| P6 | One global `EFFICIENCY_THRESHOLDS` dict (explicitly "measured for the legislation bot" per its own comment) plus hardcoded `_band()` cut-points in `stats.py` grade both bots against legislation baselines. | `config.py:118-123`, `stats.py:582-623` |

## 3. Design decisions (already made — do not re-litigate)

1. **Bot-level profile selection via `settings.research_mode`** (`config.py` Settings, ~line 100;
   env var `RESEARCH_MODE`). The parliament bot sets it; the legislation bot leaves it blank.
   Blank / anything other than `"parliamentary_records"` → the `"legislation"` profile.
   *Known caveat, accepted:* the legislation bot serves case-law and hybrid requests too; we are
   NOT splitting profiles per-request. One profile per bot process.
2. **No breaking schema changes.** New columns are additive with `DEFAULT 0`, following the
   existing `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration pattern in
   `database.py` (~lines 70-90).
3. **Reuse `distinct_legislation_ids_retrieved`** as a generic "distinct primary resources
   retrieved" counter rather than adding a parallel column (P4). Column name stays (renaming a
   populated column isn't worth it); docstrings and the frontend label change.
4. **Indicators stay backend-driven.** `EfficiencyTab.jsx` already renders `indicators[]`
   dynamically (label/value/unit/target/status come from the API), so mode-specific indicators
   need almost no frontend work.
5. **Fan-out denominator becomes profile-selected**: `sources_kept` (legislation) vs
   `distinct_legislation_ids_retrieved` (parliamentary). Both are existing columns, so this is a
   SQL-expression switch, not a schema change.

## 4. Work items

Do them in this order; WI-1..3 are independent of WI-4..6 but WI-5/6 read the counters WI-1..3 fix.

---

### WI-1 — Fix phase classification (P1)

**File:** `server_py/src/utils/stopwatch.py`

- Add `"search_scottish_plenary"` and `"search_bills"` to `_PHASE1_SEARCH_TOOLS`.
- Add `"get_scottish_plenary_debate"` to `_PHASE2_RETRIEVAL_TOOLS`.
- Leave `get_member_info` unclassified deliberately (it's a metadata lookup, neither discovery
  search nor primary-source retrieval) — add a one-line comment saying so.

**Tests:** unit test that `record_worker_tool("search_scottish_plenary")` increments
`phase1_search_calls` and `record_worker_tool("get_scottish_plenary_debate", key)` increments
`phase2_retrieval_calls`. (There is currently no dedicated stopwatch test file — create
`server_py/tests/test_stopwatch.py`; the suite runs with `pytest` from `server_py/`.)

---

### WI-2 — Composite redundancy key for transcripts (P2)

**File:** `server_py/src/agent/agent_shared.py` (~lines 353-358, inside `run_worker_tool`)

Replace the current key derivation:

```python
key_arg = (
    args.get("legislation_id") or args.get("url")
    or args.get("gid") or args.get("meeting_id")
)
```

with one that treats a transcript's identity as `(meeting_id, iob_id)`:

```python
key_arg = args.get("legislation_id") or args.get("url") or args.get("gid")
if not key_arg and args.get("meeting_id"):
    key_arg = f"{args['meeting_id']}:{args.get('iob_id', '')}"
```

Notes:
- `get_scottish_plenary_debate` and `get_scottish_committee_transcript` both take
  `meeting_id` + `iob_id` (+ `slug`, which is derivable and must NOT be part of the key).
- Redundancy detection in `TimingCollector.record_worker_tool` already keys on
  `(tool_name, key_arg)` — no change needed there.

**Tests (in `test_stopwatch.py` or a small `run_worker_tool` test):**
- Same `meeting_id`, different `iob_id` → NOT redundant.
- Same `meeting_id` + same `iob_id` twice → 1 redundant call.
- Legislation path unchanged: same `legislation_id` twice → redundant.

---

### WI-3 — Count budget-blocked search calls (P3)

**Files:** `stopwatch.py`, `agent_shared.py`, `models.py`, `database.py`

1. `stopwatch.py` — add to `TimingCollector`:
   - field `self.search_budget_blocked: int = 0`
   - recorder `def record_search_budget_blocked(self) -> None: self.search_budget_blocked += 1`
   - include `"search_budget_blocked"` in `to_dict()`.
2. `agent_shared.py` — in the budget early-return branch (~line 329, `if search_budget["remaining"] <= 0:`),
   before building `stop_msg`, add:
   ```python
   if timing_collector:
       timing_collector.record_search_budget_blocked()
   ```
   Do NOT also call `record_worker_tool` there — blocked calls should stay out of
   `worker_tool_calls`/phase counts; they get their own counter.
3. `models.py` — add to `RequestTiming`:
   `search_budget_blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)`
   (match the style of the neighbouring efficiency columns, ~line 110-130).
4. `database.py` — append to the migration list (keep it grouped with the other
   `request_timings` efficiency ALTERs, ~line 71-89):
   `"ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS search_budget_blocked INTEGER NOT NULL DEFAULT 0"`

**Optional (do it — it's one line each):** while adding the column, also add
`research_mode VARCHAR(50)` to `request_timings` + `RequestTiming` + set it in `ai.py` when
constructing metrics (`metrics["research_mode"] = effective mode for the request`). This is not
consumed by this plan's queries but future-proofs per-mode filtering on the legislation bot.
If the effective per-request mode isn't cleanly available at that point in `ai.py`, skip this —
it is strictly optional.

**Tests:** collector unit test (recorder + `to_dict` key); an integration-style test of
`run_worker_tool` with `search_budget={"remaining": 0}` asserting the counter increments and
`worker_tool_calls` does not.

---

### WI-4 — Generalise "distinct resources retrieved" (P4)

**File:** `server_py/src/utils/stopwatch.py`

- Add `_TRANSCRIPT_RETRIEVAL_TOOLS = frozenset({"get_scottish_plenary_debate", "get_scottish_committee_transcript"})`.
- In `record_worker_tool`, extend the distinct-retrieval tracking:
  ```python
  if name in _LEGISLATION_RETRIEVAL_TOOLS or name in _TRANSCRIPT_RETRIEVAL_TOOLS:
      self._retrieved_lids.add(key_arg)
      self.distinct_legislation_ids_retrieved = len(self._retrieved_lids)
  ```
  (After WI-2, `key_arg` for transcript tools is the composite `meeting_id:iob_id`, so the set
  counts distinct transcripts.)
- Update the class docstring and the comment above `_LEGISLATION_RETRIEVAL_TOOLS` to say the
  counter now means "distinct primary resources retrieved (Acts / judgments-by-url via redundancy
  key / SP transcripts)". The DB column name is unchanged.

**Tests:** two different `(meeting_id, iob_id)` retrievals → `distinct_legislation_ids_retrieved == 2`;
repeat of one → still 2 (and 1 redundant).

---

### WI-5 — Mode-keyed efficiency profiles (P5, P6)

**File:** `server_py/src/config.py`

Replace the single `EFFICIENCY_THRESHOLDS` dict with profiles. Keep the module-level name
importable (stats.py imports it) by turning selection into a function:

```python
EFFICIENCY_PROFILES = {
    "legislation": {
        # per-request breach rules (evaluate_efficiency_breaches)
        "max_delegations": 1,
        "max_redundant_tool_calls": 0,
        "fanout_abs": 5,
        "fanout_ratio": 3.0,
        "fanout_denominator": "sources_kept",      # SQL column for the fan-out ratio
        # dashboard indicator bands: (warn_at, bad_at) for _band()
        "bands": {
            "delegation": (1.05, 1.15),
            "fanout": (2.0, 3.0),
            "redundant": (0.05, 0.10),
            "halt": (0.001, 0.02),
            "fallback": (0.1, 0.25),
        },
    },
    "parliamentary_records": {
        "max_delegations": 1,
        "max_redundant_tool_calls": 0,             # legitimate after WI-2's key fix
        "fanout_abs": 5,
        "fanout_ratio": 2.0,                       # retrievals per distinct transcript ≈ 1
        "fanout_denominator": "distinct_legislation_ids_retrieved",
        "max_budget_blocked": 0,                   # any blocked search = model looped on search
        "bands": {
            "delegation": (1.05, 1.15),
            "fanout": (1.3, 2.0),
            "redundant": (0.05, 0.10),
            "halt": (0.001, 0.02),
            "fallback": (0.15, 0.35),              # excerpt-heavy answers cite less precisely
            "budget_blocked": (0.05, 0.15),        # share of requests hitting the budget wall
        },
    },
}

def get_efficiency_profile() -> dict:
    mode = settings.research_mode or "legislation"
    return EFFICIENCY_PROFILES.get(mode, EFFICIENCY_PROFILES["legislation"])
```

- Delete the old `EFFICIENCY_THRESHOLDS` dict; update `evaluate_efficiency_breaches` to call
  `get_efficiency_profile()` and:
  - compute the fan-out ratio against the profile's denominator
    (`m.get("sources_kept")` vs `m.get("distinct_legislation_ids_retrieved")`),
  - add a breach when `"max_budget_blocked"` is present and
    `m.get("search_budget_blocked", 0) > profile["max_budget_blocked"]`
    (message like `"search budget exhausted (blocked=N)"`).
- Update the comment block above the profiles (it currently says values are legislation-only).
- **Fix the import in `stats.py`** (`from ..config import EFFICIENCY_THRESHOLDS` → `get_efficiency_profile`).

The band values for the parliamentary profile above are starting points, not measured baselines —
keep them as given and note in the comment that they should be re-tuned once real parliament
traffic accumulates.

**Tests:** profile selection (monkeypatch `settings.research_mode`); breach evaluation with a
parliamentary profile: budget-blocked breach fires; fan-out uses the distinct-retrieved denominator.

---

### WI-6 — Mode-aware `/api/stats/efficiency` endpoint

**File:** `server_py/src/routers/stats.py` (`get_efficiency_stats`)

1. At the top of the handler: `profile = get_efficiency_profile()`; derive
   `fanout_denom_col = profile["fanout_denominator"]` — **validate it against an allowlist**
   `{"sources_kept", "distinct_legislation_ids_retrieved"}` before interpolating into SQL
   (the queries here are f-string SQL; never interpolate an unvalidated string).
2. Replace every `GREATEST(sources_kept, 1)` in the three queries (KPI ~line 558-562, daily
   ~line 630, worst ~line 652-658) with `GREATEST({fanout_denom_col}, 1)`.
3. KPI query: add `COALESCE(AVG(search_budget_blocked), 0) AS avg_budget_blocked` and
   `COALESCE(SUM(CASE WHEN search_budget_blocked > 0 THEN 1 ELSE 0 END), 0) AS budget_hit_count`.
4. Indicators: read every `_band()` cut-point pair from `profile["bands"]` instead of literals.
   When the profile has a `budget_blocked` band (parliamentary only), append an indicator:
   ```python
   {
       "key": "budget_exhaustion",
       "label": "Search-budget exhaustion",
       "value": budget_hit_rate,             # budget_hit_count / total
       "unit": "% of queries hitting the search cap",
       "target": "≈0",
       "status": _band(budget_hit_rate, *profile["bands"]["budget_blocked"]),
   }
   ```
   Also adjust the fan-out indicator's `unit`/`target` text per mode
   (legislation: `"retrievals / kept source"`, target `"≤3"`;
   parliamentary: `"retrievals / distinct transcript"`, target `"≈1"`).
5. Response additions (update the Pydantic response models at the top of the file — they
   enumerate every key, so new keys MUST be added there or `response_model` will strip them):
   - `EfficiencyKpi`: `avgBudgetBlocked: float`
   - `EfficiencyResponse`: `researchMode: str` (the profile key actually used)
   - `thresholds` already `Dict[str, Any]` — return the selected `profile` there (the frontend
     shows it free-form; nested `bands` tuples serialise as lists, which is fine).
6. `worst` query: add `search_budget_blocked` to the SELECT and, for the parliamentary profile,
   make it the first ORDER BY key (`search_budget_blocked DESC, redundant_tool_calls DESC, ...`);
   add `budgetBlocked: int` to `EfficiencyWorst` and the response mapping.

**Tests:** `server_py/tests/test_stats.py` — the two existing efficiency tests
(`test_efficiency_empty` ~line 146, `test_efficiency_seeded` ~line 162) assert exact key sets;
add the new keys (`avgBudgetBlocked`, `researchMode`, `budgetBlocked` in `worst`). Add one test
that monkeypatches `settings.research_mode = "parliamentary_records"` and asserts (a) the
`budget_exhaustion` indicator is present, (b) `researchMode == "parliamentary_records"`, and
(c) a seeded row with `phase2_retrieval_calls=4, distinct_legislation_ids_retrieved=2,
sources_kept=20` produces fan-out 2.0 (not 0.2).

---

### WI-7 — Frontend label tweaks

**File:** `client/src/pages/admin/EfficiencyTab.jsx`

Indicators are already API-driven (`indicators.map(...)`), so the new indicator renders with no
work. Only static text needs touching:

1. Find the KPI tile labelled around "Distinct Acts retrieved" (search the JSX for
   `avgDistinctRetrieved`) and relabel using the new `researchMode` field from the response:
   `researchMode === 'parliamentary_records' ? 'Distinct transcripts retrieved' : 'Distinct Acts retrieved'`.
2. If a KPI tile exists for fan-out, make its caption mode-aware the same way
   (`retrievals / kept source` vs `retrievals / distinct transcript`).
3. The health-strip `InfoTip` (~line 61) mentions "many Acts" — make it generic
   ("many sources") rather than adding another conditional.

**Build & ship note (mandatory for this repo):** after editing, run `npm run build` in `client/`
(bash: `export PATH="/c/Users/rhett/node_portable/node-v22.15.0-win-x64:$PATH"` first) and
commit with `git add -f client/dist/` — the deployment target has no Node and serves the
committed `dist/`. Commit and push together.

---

### WI-8 — Documentation

- `CLAUDE.md`: in the relevant section, note that efficiency thresholds are now per-mode
  (`EFFICIENCY_PROFILES` keyed by `RESEARCH_MODE`), that the fan-out denominator differs by mode,
  and that `search_budget_blocked` exists.
- Update the module docstring of `get_efficiency_stats` (currently describes the
  legislation-shaped loop only).

## 5. Acceptance criteria

1. Full test suite green: `cd server_py && pytest` (baseline before this work: 46 passed).
2. On a parliament-bot process (`RESEARCH_MODE=parliamentary_records`):
   - `/api/stats/efficiency` returns `researchMode: "parliamentary_records"`, a
     `budget_exhaustion` indicator, and fan-out computed against distinct retrievals.
   - Retrieving two agenda items of the same meeting produces `redundant_tool_calls == 0`
     and no EFFICIENCY activity-log row.
   - A request whose worker calls `search_scottish_plenary` then `get_scottish_plenary_debate`
     records `phase1_search_calls == 1` and `phase2_retrieval_calls == 1`.
   - A request that attempts a 4th search records `search_budget_blocked == 1`.
3. On a legislation-bot process (env unset): `/api/stats/efficiency` output is numerically
   identical to before this change (same bands, same fan-out denominator, no budget indicator),
   except for the additive new response keys.
4. No SQL built from unvalidated strings (fan-out denominator allowlisted).

## 6. Out of scope

- Per-request profile selection on the legislation bot (case-law vs legislation vs hybrid).
- Re-tuning the parliamentary band values against measured traffic (follow-up once data exists).
- Any change to the search-budget mechanism itself, source extraction, or summarisation metrics.
- Historical backfill: existing parliament-bot rows keep their miscounted phase/redundant values;
  trends are only trustworthy from deployment of this change onward (worth a note in the commit
  message).
