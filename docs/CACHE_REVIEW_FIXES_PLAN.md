# Cache Review Fixes — Implementation Plan (D8)

**Scoped 2026-07-18** from a full review of the caching stack on
`feature/local-prompt-cache` (D5 provider prompt caching, D5#2 tool memo,
D6 admin UI, D7 local prompt cache). The review found one real bug
(cache poisoning on summariser failure), one missing operational control
(no purge), two ROI improvements (memo in standard mode; cache-key query
source), and a set of storage/observability hygiene items.

**Verdict context:** the three-layer architecture is sound and stays as-is.
No fuzzy/semantic keying, no TTLs, no LEX response cache (D5#3 NO-GO stands).

**Branch:** implement Phases 1–2 on `feature/local-prompt-cache` BEFORE it
merges (Phase 1 is a merge blocker). Phases 3–7 may land on the same branch
or as follow-ups — implementer's judgement based on review appetite.

---

## Phase 1 — BUG: don't cache degraded summaries (merge blocker)

**Problem.** `summarise_for_query` (`server_py/src/agent/summarisation.py`)
returns degraded output instead of failing:
- single-chunk failure → returns the **original raw text** (line ~73);
- per-chunk failure → substitutes the first `SUMMARISE_CHUNK_FALLBACK_CHARS`
  of the chunk (line ~94);
- final-consolidation failure → returns the concatenated partials (line ~115).

In `run_worker_tool` (`server_py/src/agent/agent_shared.py` ~628–648) that
degraded result is then truncated to the threshold and **stored in
`local_prompt_cache` unconditionally**. One transient Ollama 500 during
summarisation permanently poisons that `(content_hash, query_hash)` key for
every user, cross-provider — the stored "summary" is the truncated head of
raw Act text, served on every future hit. And rows with `hit_count > 0` are
never pruned, so a poisoned entry with traffic is immortal.

**Fix.** Make degradation explicit and skip the store when it occurred:

1. `summarise_for_query` returns `(text, degraded: bool)`:
   - `degraded=True` on any of the three fallback paths above (for the
     per-chunk case: if **any** chunk fell back).
   - Only call site is `agent_shared.py:610` (verify with grep before
     changing — `call_chunk, summarise_for_query` import at line 14).
2. In `agent_shared.py`, around the store site (~641–648), skip
   `_local_cache.store(...)` when:
   - `degraded` is True, **or**
   - the post-summarisation truncation branch fired (the
     `len(result) > threshold` branch at ~629 that calls
     `record_truncation`) — a capped summary is lossy in a
     request-specific way and must not be reused cross-user. Set a local
     `_truncated = True` in that branch and check it at the store.
3. Log at INFO when a store is skipped for either reason
   (`[LocalCache] Not storing degraded/truncated summary for '<doc>'`).

**Tests** (`server_py/tests/test_local_prompt_cache.py`):
- chunk_fn returns `None` (single-chunk path) → no row inserted; a second
  identical run re-attempts summarisation (no hit).
- summary still over threshold (mock summariser returning oversized text)
  → truncation fires, no row inserted.
- happy path still stores (existing tests must stay green).

---

## Phase 2 — Storage-layer hygiene (`local_prompt_cache.py` + `database.py`)

All in `server_py/src/services/local_prompt_cache.py` unless noted.

1. **Atomic lookup.** Replace the SELECT + UPDATE pair in `lookup()`
   (lines ~69–87) with a single statement:
   ```sql
   UPDATE local_prompt_cache
      SET hit_count = hit_count + 1, last_hit_at = NOW()
    WHERE content_hash = :ch AND query_hash = :qh
    RETURNING summary, chars_in
   ```
   One round trip, no read-then-write gap, and drops the `datetime.utcnow()`
   usage in `lookup`.

2. **Drop the redundant index.** `ix_local_prompt_cache_content_hash`
   (`database.py:274`) duplicates the leading column of the unique
   constraint `uq_local_prompt_cache_key (content_hash, query_hash)`.
   Remove the CREATE line and add a one-shot
   `DROP INDEX IF EXISTS ix_local_prompt_cache_content_hash` to the
   migration list (the list is idempotent-by-convention; DROP IF EXISTS fits).

3. **Cheapen the prune check in `store()`.** The `SELECT COUNT(*)` at
   line ~125 runs a full count on every store. Gate the whole
   count-and-prune block behind `random.random() < 0.02` (comment: hygiene
   sampling, not correctness — the 20K threshold is soft).

4. **Retention for hit rows.** Extend the prune DELETE so rows whose last
   activity is over a year old go too, regardless of hit_count:
   ```sql
   DELETE FROM local_prompt_cache
    WHERE (hit_count = 0 AND created_at < NOW() - INTERVAL '90 days')
       OR (COALESCE(last_hit_at, created_at) < NOW() - INTERVAL '365 days')
   ```
   Rationale: amended legislation strands old-hash rows forever otherwise.

5. **`datetime.utcnow()` → DB-side `NOW()`** in `store()` (`created_at`
   already defaults to NOW() in the DDL — just drop the `:now` param and
   let the default apply, or pass `NOW()` in the SQL).

6. **Version the canonicalisation.** The recipe in `canonicalise_query`
   (stopword list, `>2`-char cutoff, sort) is baked into every stored
   `query_hash`; any future tweak silently orphans all rows. Change
   `_query_hash` to hash `"v1|" + canonicalise_query(query)` and add a
   module constant `_CANON_VERSION = "v1"` with a comment: *bump this on
   any change to `canonicalise_query` or `_STOPWORDS` — it is an explicit
   full-cache invalidation.* NOTE: this itself invalidates today's entries
   once — acceptable now (cache is days old, dev machine only); do it in
   this phase or never.

**Tests:** existing suite green; add one test that a hit updates
`hit_count`/`last_hit_at` via the RETURNING path.

---

## Phase 3 — Admin purge control (escape hatch for poisoned entries)

Currently the only recovery from a bad cache entry is manual SQL on the
target. The flag only stops new reads; it cannot evict data.

1. **Endpoint** in `server_py/src/routers/stats.py` next to
   `GET /api/stats/cache` (~line 830s), same admin-only dependency:
   `DELETE /api/stats/cache/local` → `TRUNCATE local_prompt_cache` (or
   unconditional DELETE), returns `{"deleted": <count>}`.
   Optionally also `DELETE /api/stats/cache/local/{id}` for single-row
   eviction from the top-entries table — nice-to-have, not required.
2. **Frontend** (`client/src/pages/admin/CacheTab.jsx`): a "Clear local
   cache" button in the local-cache card, Danger-variant styling
   (`bg-danger` per design system), `window.confirm`-level confirmation
   with the row count in the message, refetch stats after. API helper in
   `client/src/services/api.js`.
3. Rebuild `client/dist` at ship time (force-add per deployment workflow).

**Tests:** endpoint test — seed rows, DELETE as admin → table empty;
non-admin → 403 (follow the existing `/api/stats/cache` test pattern in
`test_stats.py`).

---

## Phase 4 — Extend the tool memo to standard research mode

The memo (exact `(tool_name, canonical-args-JSON)` per-request dict) is
Deep-Research-only, but `redundant_tool_calls` exists precisely because
standard runs re-fetch the same Act. Same zero-staleness property — the
memo dies with the request.

1. In `agent_core.py`, `run_manager_agent` (the standard path): create
   `tool_memo` per request exactly as `run_deep_research` does at
   line ~477 (`{} if _get_cfg().get("_tool_memo_enabled", True) else None`)
   and pass it through `run_worker_agent_fn(...)` at line ~356 →
   `run_worker_agent(tool_memo=...)` (param already exists, line 54).
   The memo must be created **once per request** (outside
   `manager_tool_executor`) so multiple `delegate_research` calls share it.
2. **Keep the loop-health signal.** In `run_worker_tool`
   (`agent_shared.py` ~335–352), a memo hit currently returns before
   `record_worker_tool` runs, so redundancy is never counted. For standard
   mode that would mask the "model re-fetched the same Act" signal the
   Efficiency tab grades on. Change: on a memo hit, still call
   `timing_collector.record_worker_tool(name, key_arg)` (which flags the
   redundancy) **in addition to** `record_memo_hit()`. Decide consciously
   whether Deep Research keeps its current don't-count behaviour (it was
   deliberate — cross-step reuse is not model misbehaviour). Recommended:
   pass the mode or a `count_redundant` flag so DR keeps today's
   semantics and standard mode counts both.
3. Check the efficiency-breach interaction: a memo hit that is *also*
   counted redundant may trip the `redundant_tool_calls` breach rule on
   requests that now cost nothing extra. Acceptable (the signal is about
   model behaviour, not cost) — but note it in the commit message.

**Tests** (`test_token_caching.py`): standard-mode request where the worker
repeats an exact tool call → second call served from memo (`memo_hits=1`),
API executor invoked once, redundancy still recorded; flag OFF → memo off.

---

## Phase 5 — Cache-key query source (decision + implementation)

**Problem (known, in TODO D7):** the local-cache key query is the Worker's
brief — `args["query"]` from the Manager's `delegate_research` call
(`agent_core.py:357`) — which is LLM-paraphrased and varies per model/run.
Cross-user/provider hits on standard queries are therefore luck; Deep
Research briefs (user-approved plan text) key deterministically.

**Recommended change:** in **standard research mode only**, key the local
cache on the **raw user query** instead of the delegation brief:
- Stash the user's message in the request provider-config ContextVar
  (`routers/ai.py`, alongside `_doc_context` etc.): `"_cache_key_query"`.
- In `run_worker_tool`'s summarise block (`agent_shared.py` ~590), use
  `cfg.get("_cache_key_query") or query` for `lookup`/`store`. Deep
  Research must NOT set `_cache_key_query` (each step's plan text is the
  right key — steps with different intents must not collide).

**Known residual risk — document, don't solve:** if the Manager delegates
twice in one request with different sub-aspects and both retrieve
*byte-identical* text, the second reuses the first's summary despite a
different intent. In practice: `search_legislation_sections` content varies
with the sections query (different intent → different text → different
`content_hash`), so the exposure is mostly query-independent full-document
retrievals (`get_case_law_text`). Mitigations: the one-delegation rule
(worker-tuning, July 2026) makes multi-delegation rare; and the summary
was produced *for this user's question* in the common case. Put this
caveat in the module docstring. If it proves harmful, the fallback is
reverting to brief-keying — a one-line change.

**Tests:** same user question phrased identically but with different
mocked delegation briefs → both runs produce the same `query_hash`
(second is a hit). Deep-research path unaffected (step text still keys).

**Verification (live, optional but valuable):** repeat the 2026-07-18
cross-provider A/B — a *standard* (non-DR) query should now hit
cross-provider, which it previously only did via Deep Research.

---

## Phase 6 — Observability

1. **`request_timings.provider` column** (additive,
   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS provider VARCHAR(32)`,
   `database.py` + `models.py` + `stopwatch.py` — set from the resolved
   active provider in `routers/ai.py`). Then retire the
   `total_cost_usd > 0` "OpenRouter-eligible" proxy in
   `stats.py` `get_cache_stats` (~line 859) — filter
   `WHERE provider = 'openrouter'` with a COALESCE fallback to the old
   proxy for pre-column rows. Additive-only, no backfill (consistent with
   the efficiency-profiles precedent).
2. **Cache tab small print:** the local-cache hit rate
   (`hits / (hits + summarisation_calls)`, `stats.py:870–874`) is deflated
   across windows where the flag was OFF (those summarisations were never
   cache-eligible). Add a sentence to the existing small-print block in
   `CacheTab.jsx` (next to the Gemini `cache_discount` caveat).

---

## Phase 7 — Cross-user safety invariant (cheap, do with any phase)

The local cache is cross-user; it is safe today only because everything
reaching the summarise threshold in `run_worker_tool` is public-source
(LEX, Find Case Law, Official Report). Nothing structurally prevents a
future tool returning user/matter-scoped data from being cached cross-user.

**Change:** add a `CACHEABLE_TOOLS` frozenset allowlist in
`local_prompt_cache.py` (all current worker retrieval/search tools), pass
`name` into the lookup/store gate in `agent_shared.py`, and skip the cache
for tools not on the list. Module docstring states the invariant: *only
tool results derived purely from public sources may enter this cache; new
tools must be added to the allowlist deliberately.*

**Test:** a tool name off the allowlist → summarised but never
stored/looked up.

---

## Explicitly out of scope (decided at review)

- **Anthropic `cache_control` live verification** — the deployment runs
  Gemini on OpenRouter (implicit caching); the Anthropic path is a no-op
  today and stays dormant. TODO carries a line: verify live (incl.
  tool-role breakpoint acceptance) *when* an Anthropic model is first
  configured. Optional upgrades noted for then: `cache_control` on the
  tools array; two unused breakpoints.
- **LEX / case-law response cache (D5#3 / A5)** — NO-GO stands
  (LLM:API time ~16:1; 6/66 requests tripped summarisation).
- **Fuzzy/semantic keying, TTLs** — rejected by design; do not revisit.

## Suggested commit sequence

1. `fix(cache): never store degraded or truncated summaries` (Phase 1)
2. `perf(cache): storage hygiene — atomic lookup, prune sampling, retention, canon versioning` (Phase 2)
3. `feat(cache): admin purge for local prompt cache` (Phase 3, incl. dist rebuild)
4. `feat(cache): tool memo in standard research mode` (Phase 4)
5. `feat(cache): key local cache on raw user query in standard mode` (Phase 5)
6. `feat(stats): request_timings.provider + cache-tab caveats` (Phase 6)
7. Phase 7 rides with whichever commit touches `local_prompt_cache.py` last.

Run the full suite (`pytest`, expect 133+ green against `lexchat_test`)
after each phase; Phases 3 and 6.2 need a `client/dist` rebuild +
force-add at ship time.
