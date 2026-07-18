# Cache admin UI plan — feature toggles + Cache stats tab

Scoped 2026-07-17. Builds directly on the D5 token-cost caching work on
`feature/token-cost-caching` (uncommitted as of scoping) — work on that branch.
Read `docs/TODO.md` D5 status first for what exists: `_apply_anthropic_cache_control`
(openrouter_client.py), the `tool_memo` threading (agent_core → agent_shared), and the
three additive `request_timings` columns `memo_hits`, `cached_prompt_tokens`,
`cache_discount_usd`.

## Part 1 — Cache on/off toggles (Developer tab → Feature flags)

**Two flags, not one** (recommended; each mechanism has independent risk — the
OpenRouter tool-role `cache_control` part is still unverified live, so being able to
kill just that one matters operationally):
- `prompt_caching_enabled` (default **true**) — gates `_apply_anthropic_cache_control`
- `tool_memo_enabled` (default **true**) — gates creation of the memo dict in
  `run_deep_research`

**Backend** (`server_py/src/routers/developer.py`):
- Add both keys to `_DEFAULT_FEATURES` and to `FeaturesUpdate` as `bool = True`
  (defaulted so an old saved `features` JSON or an old client POST body stays valid).
- `save_features` persists all three keys.

**Flag consumption** — flags must reach agent code without new function params.
Follow the existing `_research_mode` pattern: where `/api/chat` (routers/ai.py)
resolves the provider config, read features (one `AppSetting` select) and stash
`cfg["_prompt_caching_enabled"]` / `cfg["_tool_memo_enabled"]` into the request
config ContextVar. Then:
- `_apply_anthropic_cache_control` returns the input unchanged when
  `_get_cfg().get("_prompt_caching_enabled", True)` is false.
- `run_deep_research` (agent_core.py) sets `tool_memo = {} if enabled else None`
  (read via `_get_cfg()`); `tool_memo=None` already means "no memo" downstream.
- Default **True** everywhere when the key is absent, so direct callers/tests and
  the parliament bot are unaffected.

**Frontend** (`client/src/pages/AdminPortal.jsx`, Developer tab → Feature flags
section): two more toggle rows styled identically to the existing Matters toggle,
labels e.g. "Prompt caching (Anthropic via OpenRouter)" and
"Deep Research tool-result memo", with one-line descriptions. `features` state
already round-trips via `getFeatures`/`saveFeatures` in the API module.

**Tests**: features endpoint round-trips new keys + old body still accepted;
flag off → `_apply_anthropic_cache_control` identity for anthropic models;
flag off → `run_deep_research` passes `tool_memo=None` (extend the stub-based
tests in `tests/test_deep_research.py` / `tests/test_token_caching.py`).

## Part 2 — Admin Portal "Cache" tab

New tab id `cache` alongside the existing tabs in `AdminPortal.jsx`, with the
standard timeframe selector (7/30/90 days / all — copy whichever pattern the
Efficiency tab uses).

**New endpoint** `GET /api/stats/cache?days=N` (admin-only, in
`server_py/src/routers/stats.py`, same auth/timeframe conventions as
`get_efficiency_stats`). All data comes from `request_timings` — no new columns.
Suggested payload:

- **KPI row**
  - `memoHits` (SUM memo_hits) + `memoHitRequests` (COUNT WHERE memo_hits>0)
    over deep-research rows; also `deepResearchRequests` for context
  - `cachedPromptTokens` (SUM cached_prompt_tokens)
  - `cacheDiscountUsd` (SUM cache_discount_usd)
  - `cacheHitRequests` / `openrouterEligibleRequests` — share of requests that saw
    any provider cache hit (cached_prompt_tokens>0)
  - `totalCostUsd` for the same period, so the discount reads as a % saving
- **Daily series** (for two small charts): date → memo_hits,
  cached_prompt_tokens, cache_discount_usd, total_cost_usd
- **Recent-hits table**: last ~20 rows WHERE memo_hits>0 OR cached_prompt_tokens>0:
  created_at, request_id, chat_mode, memo_hits, cached_prompt_tokens,
  cache_discount_usd, total_cost_usd
- Echo current flag state (from `_read_features`) so the tab can show
  "prompt caching: ON/OFF, tool memo: ON/OFF" banners — makes "why is this all
  zero?" self-explanatory.

**Known limitation to state in the UI** (small print, not a blocker): per-request
*total* prompt tokens are not persisted, so a cached-token *ratio* can't be shown —
only absolute cached tokens and the provider-reported discount. (Optional additive
column `prompt_tokens` if the ratio is ever wanted; not in scope.)

**Charting**: reuse whatever the Usage/Cost tabs use (inline SVG / existing chart
helpers) — no new dependencies.

**Tests**: stats endpoint — admin-only (401/403 for non-admin), shape of KPIs with
seeded `RequestTiming` rows, timeframe filter, zero-data case.

## Constraints (same as D5)
- Additive-only DB changes (none expected).
- Ollama + OpenRouter must both keep working; flags default ON = current behaviour.
- Frontend: use design tokens (`docs/frontend/design-system.md`) — no raw palette
  classes; rebuild `client/dist` and remember it needs `git add -f` at commit time
  (the current dist on disk already contains the Deep Research UI rebuild from
  2026-07-17 — don't lose it).
- Dev-machine gotchas: pytest wipes the dev DB (D4) — re-run `init_db()` and re-seed
  `AppSetting(key="provider.ollama", value='{"model": "mistral-large-3:675b-cloud"}')`
  before manual testing; deepseek-v3.2:cloud is broken (HTTP 410); no OpenRouter API
  key exists on the dev machine (Part 1's prompt-caching toggle can only be
  unit-tested locally).

## Suggested order
1. Backend flags (+ tests) → 2. flag consumption in agent code (+ tests) →
3. Developer-tab toggle UI → 4. `/api/stats/cache` endpoint (+ tests) →
5. Cache tab UI → 6. full suite + local visual check (rebuild dist, hard-refresh).
