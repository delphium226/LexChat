# Per-Request Efficiency Profiles (Legislation Bot) — Follow-up Scope

**Status:** SCOPED (not started). Follow-up to `EFFICIENCY_PER_BOT_PLAN.md` (shipped).
**Audience:** coding agent in a fresh session — read this fully first.
**Scope:** backend `server_py/` + the Efficiency-tab frontend. No new external deps.

---

## 1. Why this exists

`EFFICIENCY_PER_BOT_PLAN.md` gave each **bot process** one efficiency profile,
selected by `settings.research_mode` (the parliament bot sets
`RESEARCH_MODE=parliamentary_records`; the legislation bot leaves it blank →
`"legislation"` profile). That plan's design decision #1 explicitly accepted a
caveat:

> *the legislation bot serves case-law and hybrid requests too; we are NOT
> splitting profiles per-request. One profile per bot process.*

This follow-up removes that caveat **for the legislation bot only**. Its single
process serves three genuinely different retrieval shapes, and grades all three
against the legislation-only baseline:

| Per-request `research_mode` | Discovery | Retrieval | Distinct-resource denominator today |
|---|---|---|---|
| `legislation_only` | `search_legislation` | `search_legislation_sections`, `get_legislation_text` | Acts (counted) |
| `case_law_only` | `search_case_law` | `get_case_law_text` | **judgments NOT counted** (see §3.3) |
| `legislation_and_case_law` | both | both | Acts only |

A case-law answer retrieves judgments, not Acts; a hybrid answer does both. The
fan-out ratio and the "distinct resources retrieved" KPI are therefore
mis-shaped for the two non-legislation modes on the legislation bot — the same
class of problem the parliament work fixed, one level down.

## 2. Groundwork already in place (do not redo)

- **`request_timings.research_mode` column** already persists the effective
  per-request mode (`ai.py`: `settings.research_mode or body.research_mode or
  "legislation_only"`). Values seen on the legislation bot: `legislation_only`,
  `case_law_only`, `legislation_and_case_law`. This column is currently written
  but **read by nothing** — this plan is its first consumer.
- **`EFFICIENCY_PROFILES` / `get_efficiency_profile()`** in `config.py` are already
  the profile mechanism; this plan extends them from process-keyed to
  request-keyed on the legislation bot.
- **`_band()`, indicator loop, allowlisted fan-out denominator** in `stats.py` are
  all profile-driven already.

## 3. Design decisions to make (open — resolve before coding)

These are genuinely undecided; pick deliberately rather than defaulting.

### 3.1 Do case-law / hybrid actually need different *bands*, or just segmentation?
Two options, cheapest first:
- **(A) Segment-only.** Keep one legislation-family band set, but let the
  Efficiency tab **filter by `research_mode`** so trends aren't blended. Minimal
  risk; no new baselines to invent. Recommended first step.
- **(B) Distinct bands per mode.** Add `legislation_only` / `case_law_only` /
  `legislation_and_case_law` profiles with their own `fanout_ratio` etc. Only do
  this once (A) shows the shapes really diverge — otherwise you are inventing
  unmeasured cut-points again (the parliament bands are already flagged as
  guesses).

### 3.2 Process profile vs request profile — how do they compose?
`evaluate_efficiency_breaches(m)` runs per request and currently calls
`get_efficiency_profile()` (process-level). It should instead select by
`m["research_mode"]` **when the process is the legislation bot**, and stay
process-level on the parliament bot (which has one true mode). Suggested shape:
`get_efficiency_profile(research_mode: str | None = None)` — falls back to
`settings.research_mode` when arg is None, so existing callers are unaffected.

### 3.3 Case-law retrieval is not counted as a distinct resource
`get_case_law_text` is **not** in `_LEGISLATION_RETRIEVAL_TOOLS`
(`stopwatch.py`), so `distinct_legislation_ids_retrieved` stays 0 for
`case_law_only` requests, and a case-law fan-out denominator of
`distinct_legislation_ids_retrieved` would be always-0 (ratio blows up). Fix
options: add `get_case_law_text` to the distinct-retrieval set (its `key_arg` is
the judgment `url`, already the redundancy key), OR keep `sources_kept` as the
denominator for case-law/hybrid. Decide alongside §3.1.

## 4. Work items (once §3 is resolved)

- **WI-A** `config.py`: extend `get_efficiency_profile()` to accept an optional
  per-request mode; if pursuing 3.1(B), add the new profile keys. Map the three
  legislation-family request modes to whichever profile(s) 3.1 chose.
- **WI-B** `config.py`: `evaluate_efficiency_breaches(m)` selects its profile via
  `m.get("research_mode")` on the legislation bot. Add a unit test that a
  `case_law_only` metrics dict is graded by the case-law rules.
- **WI-C** `stopwatch.py` (only if 3.3 → count judgments): add `get_case_law_text`
  to the distinct-retrieval set; test that a case-law retrieval increments
  `distinct_legislation_ids_retrieved`.
- **WI-D** `stats.py`: add an optional `mode` query param to
  `GET /api/stats/efficiency`; when present, add `AND research_mode = :mode` to
  `research_filter` and select that mode's profile. Absent → current behaviour
  (all research requests, process profile). Return the available modes
  (`SELECT DISTINCT research_mode`) so the frontend can build a selector.
- **WI-E** `EfficiencyTab.jsx`: add a mode filter (only shown on the legislation
  bot — hide when `researchMode === 'parliamentary_records'`, which has one mode).
  The existing `researchMode`-aware labels/captions already switch correctly.
- **WI-F** docs: update the CLAUDE.md "Per-Bot Efficiency Measurement" section and
  this plan's status.

## 5. Acceptance criteria

1. Suite green (`cd server_py && pytest`).
2. `GET /api/stats/efficiency` with no `mode` param is **numerically identical**
   to current output (additive keys only) on both bots.
3. `GET /api/stats/efficiency?mode=case_law_only` on the legislation bot scopes
   every average/indicator to case-law requests and grades them with the
   case-law rules.
4. No SQL from unvalidated strings — `mode` bound as a parameter (not
   f-string-interpolated) or allowlisted against the DISTINCT set.

## 6. Out of scope

- Re-tuning any band against measured traffic (needs data first; see 3.1(A)).
- The parliament bot (already one true mode; unaffected).
- Backfilling `research_mode` on pre-change rows — they are NULL; treat NULL as
  "unknown/all" in the filter, do not guess.
