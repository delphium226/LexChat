# Local prompt caching — cross-user, cross-provider summary cache (no embeddings)

Scoped 2026-07-18. Supersedes the embedding-based variant discussed and shelved as
TODO D7 — this design uses **exact (canonicalised) prompt / document-summary pairs
only**, which eliminates D7's headline risk (semantic near-miss reuse → silent
incompleteness) by construction: a hit requires the byte-identical source document
AND an equivalent query, so the worst case is serving a summary of exactly the
right text for exactly the same question.

**Motivation** (from the D7 discussion): LEX documents are static, and at ~200
users on one deployment, query demand over the same Acts/sections will be heavily
correlated — the second lawyer asking the same question of the same section should
skip the summarisation LLM call (the only expensive step; the LEX fetch itself is
free and stays). The saving is mostly latency (tens of seconds on large docs) plus
one flash-model call per hit.

**Branch**: new branch off `main` after `feature/token-cost-caching` merges (this
builds directly on D5/D6 code: the summarisation block in `run_worker_tool`, the
feature-flag mechanism, the Cache tab, and the D4 test database).

## Where it sits in the pipeline

`server_py/src/agent/agent_shared.py`, `run_worker_tool` — the summarisation block
(`if len(result) > get_summarise_threshold(): result = await summarise_for_query(...)`,
currently ~lines 555–625). Only oversized tool results reach this block, which is
exactly the document-summary case. Wrap it:

1. Compute `content_hash = sha256(raw oversized result string)` and
   `query_key = canonicalise(query)` (see Keying below).
2. **Lookup** — on hit: use the cached summary, skip `summarise_for_query`
   entirely, count a `local_cache_hit` (do NOT count a summarisation), emit the
   normal "Extracting the relevant sections…" tool_start/tool_end pair so the UI
   stream stays consistent (result arrives near-instantly).
3. **Miss** — summarise as today, then **store** the summary. Store AFTER the
   size-cap truncation and BEFORE the phase-2 nudges are appended (nudges are
   request-contextual and appended outside the summarisation block either way).

Interaction with the D5 tool memo: none needed. The memo is per-request and checked
earlier (it stores the whole final tool result); a memo hit never reaches the
summarisation block. The local cache is the cross-request/cross-user layer beneath
it. Both are gated by independent flags.

## Keying — the correctness-critical part

Cache key = `(content_hash, query_hash)`:

- `content_hash` — sha256 hex of the raw pre-summarisation result string. This is
  the safety gate: identical hash ⇒ identical retrieved text ⇒ staleness is
  impossible (an amended section changes the LEX text, changes the hash, misses).
  No TTL or invalidation logic needed for correctness.
- `query_hash` — sha256 of the **canonicalised** worker query: lowercase →
  tokenise `[a-z0-9]+` → drop tokens ≤2 chars and English stopwords → dedup →
  **sort** → join with single spaces. (Same recipe as `_or_tsquery` in
  `agent/tools/parliament.py` — reimplement locally in the cache service, do not
  import from the parliament module.) This bridges trivial wording variants
  ("compensation, disturbance payments" vs "disturbance payments and compensation")
  without any semantic matching. Store the original `query_text` too, for
  debugging and future hit-rate analysis.
- **`summarise_model` is deliberately NOT in the key** — this is what makes the
  cache cross-provider (an Ollama-produced summary serves an OpenRouter request
  and vice versa; a good extraction of the same text for the same question is
  provider-agnostic). Store the model that produced each summary as a plain
  column for provenance. If summary quality ever proves model-sensitive, adding
  the model to the key is a one-line change that simply lowers the hit rate.

## Storage

New table `local_prompt_cache` (model `LocalPromptCache` in
`server_py/src/models.py`):

| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| content_hash | VARCHAR(64) NOT NULL | indexed |
| query_hash | VARCHAR(64) NOT NULL | |
| query_text | TEXT NOT NULL | original wording, for analysis |
| summary | TEXT NOT NULL | the cached summarisation output (post-cap, pre-nudge) |
| summarise_model | VARCHAR(255) | provenance only — not part of the key |
| doc_name | VARCHAR(512) | the `doc_name` computed in the summarisation block, for admin display |
| chars_in | INTEGER | size of the summarised input, for savings estimates |
| hit_count | INTEGER NOT NULL DEFAULT 0 | |
| last_hit_at | TIMESTAMP NULL | |
| created_at | TIMESTAMP NOT NULL DEFAULT NOW() | |

- `UNIQUE (content_hash, query_hash)`; insert with `ON CONFLICT DO NOTHING`
  (two concurrent misses on the same key race harmlessly).
- Migration: add the model AND a `CREATE TABLE IF NOT EXISTS` + index statements
  to the `migration_statements` list in `server_py/src/database.py` (existing
  pattern — create_all only covers fresh installs).
- Scope note: the table lives in each bot's own database, so the cache is shared
  across all users and both providers **of one bot** (legislation and parliament
  bots each get their own — correct, since their documents don't overlap).
- Growth: no eviction needed for correctness. Add cheap hygiene: on store, if a
  cheap `COUNT(*)` exceeds ~20,000 rows, delete rows with `hit_count = 0` older
  than 90 days. Do not build more than this without evidence.

## Service module

New `server_py/src/services/local_prompt_cache.py`:

- `canonicalise_query(query: str) -> str` — pure function, unit-testable.
- `async lookup(content_hash, query) -> str | None` — SELECT by key; on hit,
  UPDATE `hit_count`/`last_hit_at` (fire-and-forget) and return `summary`.
- `async store(content_hash, query, summary, summarise_model, doc_name, chars_in) -> None`.
- Both use `from ..database import async_session_maker` directly (same pattern as
  the parliament DB tools — note the D5 import-depth gotcha if the file ever moves).
- **Everything fail-soft**: any exception in lookup ⇒ return None (treated as a
  miss); any exception in store ⇒ log at debug and continue. A DB hiccup must
  never break a research request.

## Flag, metrics, admin UI (all follow the D6 patterns exactly)

- **Flag** `local_prompt_cache_enabled` (default **ON**): add to
  `_DEFAULT_FEATURES` + `FeaturesUpdate` (defaulted, for old client bodies) in
  `routers/developer.py`; stash `_local_prompt_cache_enabled` into the request
  provider-config ContextVar in `routers/ai.py` next to the two D6 flags;
  `run_worker_tool` checks `_get_cfg().get("_local_prompt_cache_enabled", True)`
  before lookup AND store. Absent key = enabled (direct callers/tests unaffected —
  but see Tests: stub the service there). Third toggle row in the AdminPortal
  Feature Flags list (it's already a mapped array — one entry).
- **Metrics** (two additive `request_timings` columns, both via
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` + model + `TimingCollector` counter +
  `to_dict()` entry — persistence is then automatic via `RequestTiming(**metrics)`
  in `routers/ai.py`):
  - `local_cache_hits` — `record_local_cache_hit(chars_saved)` increments it.
  - `local_cache_chars_saved` — the `chars_in` of each hit's cache entry summed
    per request: the summarisation *input* volume that was never sent to the
    flash model. This is the concrete savings number (a hit performs no
    summarisation, so `summarisation_chars_in` stays 0 for it — the two columns
    are complementary, never double-counted).
  Like `memo_hits`, these are savings, NOT loop-health: keep them out of
  `worker_tool_calls` / phase / redundant counts, and do NOT call
  `record_summarisation` on a hit.
- Optional (nice-to-have, not required): "Clear local cache" button in the Cache
  tab's Local prompt caching section → admin-only
  `DELETE /api/developer/local-cache` (truncate the table).

## Cache tab — "Local prompt caching" section

Extend `GET /api/stats/cache` (`routers/stats.py`) and `CacheTab.jsx` — additive
keys only, existing keys unchanged. Two data sources: `request_timings` for the
timeframe-filtered usage numbers, and the `local_prompt_cache` table itself for
the (timeframe-independent) cache-content numbers.

**New payload keys:**

- `kpi.localCacheHits` — SUM(local_cache_hits) over the timeframe
- `kpi.localCacheHitRequests` — COUNT(*) WHERE local_cache_hits > 0
- `kpi.localCacheHitRate` — SUM(local_cache_hits) /
  (SUM(local_cache_hits) + SUM(summarisation_calls)) over the timeframe, NULL-safe
  (0 when the denominator is 0). No new column needed: every miss that mattered
  performed a summarisation, so `summarisation_calls` IS the miss count — this is
  the headline "how often does the cache work?" number.
- `kpi.localCacheCharsSaved` — SUM(local_cache_chars_saved): summarisation input
  chars avoided (the honest savings unit; do NOT invent a $ figure — flash-model
  token pricing × chars is speculative and the Cost tab already owns spend).
- `localCache` object (from the cache table, not timeframe-filtered):
  `entries`, `distinctDocuments` (COUNT DISTINCT content_hash),
  `totalHitsServed` (SUM hit_count), `oldestEntry` (MIN created_at).
- `localCacheTop` — top ~10 reused entries: `docName`, `queryText`,
  `hitCount`, `charsIn`, `lastHitAt`, `createdAt` (ORDER BY hit_count DESC,
  only rows with hit_count > 0). This is the "what are 200 users actually
  re-asking?" view — it doubles as the evidence base for future tuning.
- `daily[].localCacheHits` — added to the existing daily series
- `recentHits` — extend the WHERE to `... OR local_cache_hits > 0` and add
  `localCacheHits` + `localCacheCharsSaved` to each row
- `flags.local_prompt_cache_enabled` — echoed like the other two

**UI (one new section on the Cache tab, below the existing charts):**

- Third flag badge in the header row: "Local cache: ON/OFF".
- KPI row of four cards: **Local Cache Hits** (with "N of M requests" subtext),
  **Hit Rate** (`localCacheHitRate` as %, subtext "hits vs summarisations
  performed"), **Summarisation Avoided** (`localCacheCharsSaved` formatted as
  chars/KB/MB), **Cached Summaries** (`localCache.entries`, subtext
  "`distinctDocuments` documents · `totalHitsServed` hits all-time").
- The daily memo-hits bar chart gains a second series for `localCacheHits`
  (grouped bars, same chart — don't add a third chart for one series).
- **Top reused summaries** table: Document, Query, Hits, Input Size, Last Hit —
  from `localCacheTop`. Empty state: "No cached summaries yet — entries appear
  after the first oversized document is summarised."
- Recent-hits table: add a "Local Hits" column alongside Memo Hits.
- All styling per the design tokens and the existing CacheTab patterns
  (`bg-paper` cards, `text-ink-*`, existing table classes).

**Tests for this section** (extend the D6 stats tests in `tests/test_stats.py`):
new keys present in the zero-data case; seeded rows produce correct
`localCacheHitRate` (including the 0-denominator case); `localCacheTop` ordering
and hit_count>0 filter; recentHits includes a row with only local hits.

## Tests (D4 gives tests their own DB — use it, the cache service can be tested against real Postgres)

1. `canonicalise_query`: ordering/stopword/case variants collapse to one key;
   distinct terms don't.
2. Service round-trip against the test DB: store → lookup hit (+hit_count bump);
   different content_hash or query_key → miss; ON CONFLICT double-store is a no-op.
3. `run_worker_tool` integration (extend `tests/test_token_caching.py` style):
   oversized stubbed tool result → first call summarises (stub
   `summarise_for_query`) and stores; second call with same result+query skips the
   summarise stub (call count 1) and records `local_cache_hits == 1`, no
   summarisation count. Different query wording beyond canonicalisation → miss.
4. Flag off (`_local_prompt_cache_enabled: False` in the ContextVar) → no lookup,
   no store, behaviour byte-identical to today.
5. Fail-soft: patch the service to raise → request still succeeds, counted as miss.
6. Stats endpoint: new keys present, zero-data case, seeded `local_cache_hits` row
   appears in recentHits.

## Verification (live)

Run the same oversized-document research query twice (the 3-Act comparison query
from the D5/D6 verification triggers summarisation reliably). Second run: server
log shows a cache hit instead of "summarising with model …", `local_cache_hits=1`
in the timing line, Cache tab shows the hit. Then repeat with the flag off and
confirm the second run summarises again. Finally run once on the OTHER provider
(Ollama vs OpenRouter) with the same query to demonstrate the cross-provider hit.

## Constraints & gotchas

- Additive-only DB changes (new table + one `request_timings` column).
- Flag-off behaviour byte-for-byte identical to today; flag defaults ON.
- Frontend: design tokens per `docs/frontend/design-system.md` (`bg-brand` vs
  `bg-accent`!); rebuild `client/dist` and `git add -f client/dist/` at commit.
- Dev machine: pytest now uses `lexchat_test` (D4) — no dev-DB re-seeding needed.
  `deepseek-v3.2:cloud` is broken (HTTP 410). OpenRouter key exists in the
  `provider.openrouter` AppSetting (user-configured models:
  `google/gemini-3.1-pro-preview` + `google/gemini-3-flash-preview`).
- Do NOT add embeddings, similarity thresholds, or fuzzy matching of any kind —
  exact canonicalised match only. That constraint is the design.

## Suggested order

1. Model + migration + `canonicalise_query` + service (+ tests 1–2)
2. `run_worker_tool` wiring + `local_cache_hits` metric (+ tests 3, 5)
3. Feature flag backend + ContextVar consumption (+ test 4)
4. Stats endpoint keys (+ test 6) → 5. Cache tab + toggle row UI
6. Full suite → rebuild dist → live two-run + cross-provider + flag-off checks
