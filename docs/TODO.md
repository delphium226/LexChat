# TODO

**This file is the canonical todo list for the project** (as of 2026-07-15). Deferred
work previously tracked across auto-memory notes, `*_PLAN.md` docs, and GitHub issues
(stale since April 2026) should be recorded or referenced here going forward.

---

## Tidy-up branch (`chore/tidy-up`) — remaining chores

All fixes-queue items are closed (test suite green at 56 passed; visual smoke done).
Agreed sequencing: triage working tree → merge → regenerate bundle LAST.

### T1. Triage uncommitted working-tree changes — DONE 2026-07-15 (commit `fc8b02d`)
The in-progress change was parliament-aware copy (splash, chat empty state, sources
rail) — committed with rebuilt dist, plus `docs/evals/GOLDEN_QUESTIONS_PARLIAMENT.md`.
Working tree clean; branch ready for the T2 merge smoke.

### T2. Merge `chore/tidy-up` → `main` — DONE 2026-07-15 (main at `f6f6c61`)
Final docs-reorg commit `f6f6c61` (moved `.md` files under `docs/`, updated path
references), then fast-forwarded `main` (52 commits, no conflicts) and pushed.
Rollback tag `pre-tidy-up-merge` (annotated, at pre-merge `6bd5fbc`) pushed to origin.
`chore/tidy-up` kept for now (not deleted); active work continues on `main`.
Note: not yet deployed — the target still needs `git pull origin main` + restart.

### T3. Regenerate the offline bundle (LAST, after merge)
`package_offline_native.ps1`. The current bundle predates the doc-upload feature and
LACKS the pdfplumber/python-docx wheels — a fresh air-gapped install would fail.

### T4. Credential loose ends
- Old `server/.env` credentials remain in git history (no history rewrite chosen) —
  rotate if still valid. (Ollama SSH key rotation done 2026-07-13; DB-creds rotation
  explicitly dropped by user decision 2026-07-13.)
- Rotate the OpenRouter API key: it is returned in plaintext by
  `GET /api/developer/provider-config` and has appeared in session transcripts.
- Related hardening: mask `api_key` in the provider-config GET response
  (`has_api_key` boolean, same pattern as `peer_bots.api_key`).

---

## Agent quality — variance follow-ups (scoped 2026-07-15)

Context: run-to-run variance in format compliance and search luck on golden question
L31; prompt-level fixes landed in `fb88b41`; temperature already lowered to 0.0 for
both providers on both bots (DB `AppSetting`, via Admin Portal API — smoke-tested OK).

### A1. Stream worker report verbatim in research mode
**Problem:** the Manager re-generates the Worker's report token by token, so format
compliance depends on prompt obedience. On L31, 1 of 3 runs lost all section headers
and the References section despite the PASS-THROUGH ACCURACY rule.
**Fix:** in research mode, stream the Worker's report to the client verbatim in code;
the Manager's LLM call contributes only the conversational wrapper (intro + follow-up
question). Same philosophy as the Phase-2 nudges / search budget: code enforcement >
prompt. Touches the SSE streaming path in `chat_loop` — land after A3 exists so
regressions are measurable. Supersedes A4.

### A2. Appeals nudge on case-law search results — DONE 2026-07-22
**Problem:** retrieving the appellate decision of a case is search luck — some L31
runs got only the first-instance *Coulthard* [2024] EWHC 3252 (Admin) and missed
[2025] EWCA Civ 1671. The prompt rule (fb88b41) is soft.
**Fix:** extend the Phase-2 nudge pattern — after `search_case_law` results are
slimmed, detect citations with matching party names across court levels (EWHC → EWCA)
and append `[NOTE: an appellate decision of this case is in the results — retrieve
it]` to the tool result.
**Home:** `agent/tools/caselaw.py` (slimming) + `agent_shared.py` (nudge injection).

**Done 2026-07-22:** pure helper `detect_appellate_decisions(results)` in
`caselaw.py` — ranks each result by court (`_COURT_RANK`: EWHC/CSOH/UKUT=2,
EWCA/CSIH/NICA=3, UKSC/UKPC=4) and flags any appellate-court result that shares a
*distinctive* party token with a lower-court result. Distinctiveness = alphabetic
token ≥4 chars, minus an institutional/department stopword set (so unrelated JRs
against the same "Secretary of State … Home Department" don't link) and minus tokens
appearing in >3 results. Matches on both party sides, so it survives party-order
flips on appeal. Wired into the existing `search_case_law` `n>0` branch in
`agent_shared.py` as an appended `[NOTE — APPELLATE DECISION PRESENT: …]` nudge
(only when both levels are in the result set — the real L31 case). 6 unit tests in
`test_caselaw_parsers.py` (Coulthard EWHC→EWCA, Miller EWCA→UKSC, boilerplate
false-positive guard, same-level guard, first-instance-only, no-url). 156 tests green.
Backend-only, no dist rebuild. Live single-query verification against the National
Archives still worth doing once a provider key/session is handy, but the logic is
deterministic (pure function + string append) and fully unit-covered.

### A3. Golden-question eval harness
**Problem:** variance is eyeballed from single runs; format/citation compliance needs
to be a measured metric before changing the streaming path.
**Fix:** thin harness — loop over `docs/evals/GOLDEN_QUESTIONS_*.md`, call `/api/chat` per
question with n≥3 samples, parse the SSE token stream, regex-check required citations
and automatic-fail conditions, emit CSV with per-question grade spread. Published
metric: % A/B, % D separately (per the rubric in the golden-question files).
Reuses the SSE parsing from the 2026-07-15 test runs.

### A4. Worker report structure validation + one reformat retry — DONE 2026-07-22
Cheaper mitigation for A1's problem: after the Worker returns, check the report has
the five section headers and ≥1 link under References; if not, issue ONE follow-up
call ("reformat your findings into the required structure; do not redo research") —
no tools re-run. Skip if A1 lands first.

**Done 2026-07-22 (A1 not yet built, so A4 is the active mitigation):** in
`run_worker_agent` (`agent_core.py`), after the worker chat loop and BEFORE source
filtering (so the filter sees the reformatted content). `_report_needs_reformat`
is a high-precision structural check (avoids wasting the retry on well-formed
reports): fails only when the report has <2 recognisable section headers (flat
blob — the observed regression), OR has no References section, OR retrieved sources
but cites no link. A source-less "nothing found" answer is NOT required to carry a
link. `_reformat_worker_report` issues one no-tools `chat_loop_fn` call (empty tools
list) with a reformat-only system prompt built from the mode's required section
labels (`_REPORT_SECTIONS`, mirroring each worker prompt's OUTPUT STRUCTURE) — adds
NO new content, pure reorganise; fail-soft (any error keeps the original). Skipped
entirely in conversational chat mode (deliberately unstructured). Header detection
(`_extract_section_headers`) handles ATX (`## Foo`) and numbered/bold labels
(`1. **Foo:**`). 11 unit tests in `test_worker_report_structure.py` (pure-check
cases + retry-wiring integration via a stub chat_loop: malformed→1 reformat with
empty tools, well-formed→no retry, conversational→skipped). 167 tests green.
Backend-only, no dist rebuild.

### A5. LEX / case-law API response cache (pre-existing idea, re-scoped)
Response cache keyed on (endpoint, payload) with TTL; legislation text is highly
cacheable. Doesn't reduce variance for novel queries but makes eval re-runs (A3)
cheaper and more repeatable. LLM time dominates ~30:1, so this is an eval-cost play,
not a latency play. See also D5 (token-cost caching) — this is D5's sub-item 3.

**Rate-limit reframing (2026-07-22):** the LLM:API latency argument was measured at
low concurrency and misses the real driver — the LEX API is **rate limited** and the
deployment shares a single outbound IP across ~200 users. None of the existing cache
layers reduce cross-user LEX *call volume* (tool memo is per-request; the local
prompt cache D7 keys on the hash of the raw result, so it must fetch from LEX first —
it saves summarisation, not the API call). So A5 is the only layer that would cut
call volume and keep the shared IP under the ceiling. Moves A5 from NO-GO toward a
conditional GO as a **throughput** play — but still gated on knowing the actual limit
(req/s, per-IP vs per-key; not documented in-repo) and expected peak concurrency.
The cheaper, higher-priority companion fix (LEX backoff, below) is now done.

### A5a. LEX API backoff + Retry-After retry — DONE 2026-07-22
The three LEX POST endpoints (`search_legislation`, `search_legislation_sections`,
`get_legislation_text` in `agent/tools/executor.py`) went straight to
`raise_for_status()`, so a 429 under load became a dropped retrieval → a silently
incomplete answer (a correctness bug, independent of whether A5 is built). Added
`_request_with_retry` (+ `_retry_after_seconds`, `_backoff_delay`): retries 429 and
transient 5xx (502/503/504) and network timeouts/transport errors with bounded
exponential backoff (0.5→1→2s, +jitter, cap 8s; up to 3 retries / 4 attempts),
honouring `Retry-After` capped at 30s. Non-retryable statuses (e.g. the case-law 400)
and exhausted retries return unchanged, so persistent-failure behaviour matches today
(just later). Case-law/National-Archives GETs left untouched (different host, not the
rate-limited concern — trivial to extend later). The per-call `record_lex_api_call`
timing now spans retries+backoff, so rate-limit pain shows up in `lex_api_total_ms`
rather than hiding. 10 unit tests (`test_lex_retry.py`) with an httpx MockTransport +
stubbed sleep (429→200 honours Retry-After, transient 503, persistent 429 exhausts to
4 attempts, non-retryable 400 passes through, network-error retry, Retry-After cap).
177 tests green. Backend-only, no dist rebuild.

---

## Product backlog (migrated from GitHub issues, 2026-07-15)

GitHub issues are no longer used for todo tracking. The two open issues (#9, #17)
were migrated here in full and closed; these entries are the canonical specs.

### B1. Silent error handlers give users no feedback (bug; was issue #9)
Bare `.catch(() => {})` handlers swallow errors users need to see:
1. **Chat history load** (`getChats()` at `App.jsx:116` and `App.jsx:776`): on failure
   (network error, auth expiry, DB issue) the sidebar shows an empty thread list with
   no indication anything went wrong — users may assume they have no history.
   **Fix:** inline error state in the sidebar, e.g. a small "Could not load threads"
   message with a retry link.
2. **Preference saves** (`research_mode` at `App.jsx:684`, `chat_mode` at
   `App.jsx:348`): on failure the UI reflects the new selection but it isn't
   persisted — reverts silently on next login.
   **Fix:** capture the previous value before the optimistic update; on error revert
   the UI selection and show brief feedback:
   ```js
   const previousMode = researchMode;
   setResearchMode(opt.value);
   updatePreferences({ research_mode: opt.value }).catch(() => {
       setResearchMode(previousMode);
       // show error feedback
   });
   ```
Also consider the same treatment for the other bare `.catch(() => {})` sites found
2026-07-15: chat title rename (`App.jsx:413`/`424`), `AdminPortal.jsx:154`/`159`/`1860`,
`MatterNotesModal.jsx:144`. A toast notification system would handle all of these
cleanly; if none is added, an inline `useState`-based error banner is sufficient.
(The original issue referenced `App.jsx:319`/`881` — stale since the App.jsx
component split; locations above are current.)

### B2. Matters: AI proactive research gap detection (feature; was issue #17)
After multiple research chats on a matter, lawyers may not know what angles they have
missed. Adds a "Find research gaps" action that analyses all research done on a matter
and suggests specific queries the lawyer has not yet investigated. Conceptually
similar to the research brief (issue #15) but forward-looking: instead of summarising
what was found, it identifies what was *not* asked. Output is a ranked list of
suggested next research queries, actionable enough to paste directly into a new chat.

**1. New backend endpoint** — `POST /api/matters/{matter_id}/gaps` in
`server_py/src/routers/matters.py`:
1. Load all chats where `Chat.matter_id == matter_id` and `Chat.user_id == current_user["id"]`.
2. Per chat, collect all `user` messages (the research questions asked) and all
   `assistant` messages (findings — brief extract only, e.g. first 500 chars, to keep
   prompt size down).
3. Build a structured prompt:
   ```
   You are a senior UK government lawyer reviewing research conducted on a legal matter.

   MATTER: {matter.title}
   DESCRIPTION: {matter.description or "(none)"}
   {optional legal_area/extent lines if issue #16 fields exist}

   RESEARCH CONDUCTED SO FAR:
   {for each chat, numbered list of user queries and brief finding extracts}

   ---

   Your task: identify gaps in the research coverage.

   A thorough legal analysis of this matter would typically require investigating:
   - Relevant primary legislation and any amendments
   - Statutory instruments and subordinate legislation
   - Key case law applying or interpreting the legislation
   - Procedural requirements and timescales
   - Extent and territorial scope considerations
   - Any pending legislation or recent amendments

   Based on what has been researched so far, list up to 8 specific research queries
   the lawyer should run next. For each:
   - Write the query as a complete question, ready to paste into a research chat
   - Add a one-line explanation of why this gap matters

   Only suggest queries that have NOT already been covered. Be specific — generic
   suggestions like "research the Act" are not helpful.
   ```
4. Call the LLM via `get_summarise_model()` (one-shot, non-streaming; same call
   pattern as `summarisation.py` — it returns `(model_name, client_function)`).
5. Return `{"suggestions": "<markdown text>"}` — do not save as a note automatically.

**2. Frontend** — in `MatterNotesModal.jsx` (or a new `MatterGapsModal.jsx`): a
"Find research gaps" button alongside "Generate research brief"; on click call the
endpoint and display the response in a modal/expandable panel; a "Save as note"
button posting the text to `POST /api/matters/{matter_id}/notes`; loading state
(call may take 15–30 s).

**3. API helper** in `client/src/services/api.js`:
```js
export async function getMatterGaps(matterId) {
  const res = await fetch(`/api/matters/${matterId}/gaps`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Gap analysis failed');
  return res.json();
}
```

**Acceptance criteria:**
- On a matter with ≥1 research chat, returns specific, actionable queries within 60 s.
- Suggestions are clearly distinct from what was already asked.
- Result can be saved as a matter note with one click.
- On a matter with no chats, the button is disabled with tooltip "No research chats yet".
- Endpoint returns HTTP 200 with `{"suggestions": ""}` rather than an error when
  there is nothing to suggest.

**Notes:** does not require issue #14/#16 but benefits from #16's structured metadata;
suggestion quality is model-dependent (generic output on weak models is a model
problem, not a bug); do not stream — a single completion displayed at once.

### B3. Deep Research mode (feature; scoped 2026-07-16 — BUILT 2026-07-16 on `feature/deep-research`, uncommitted)
**Status:** implemented per the build spec, all layers. 22 new tests (97 total green);
live E2E verified via Ollama (plan → edit → 5-step execution → integrated report with
persisted `messages.research_plan`; clarification path; carve-out confirmed — no breach
alert on a 5-delegation deep-research run, while a same-session conversational request
still alerted). Synthesis prompt includes a Key-findings bullet block in the BLUF with
material gaps surfaced in the summary. Awaiting review/commit; rebuild `client/dist`
+ force-add at ship time. Original scope below.
New opt-in `chat_mode = "deep_research"` that drafts an editable research plan, lets
the lawyer add/remove/reorder/edit steps, then on approval executes the plan
autonomously (code-orchestrated: one worker run per step + a synthesis call) and
returns an integrated report. Plan-first improves scoping/steerability and yields an
auditable approved-plan artifact — a good fit for the government-lawyer users. **L2
only** (plan → approve → run); L3 (pause-and-review between steps) explicitly excluded.
Two-phase flow: new `POST /api/research/plan` (JSON, planner-only agent) → editable
plan card → existing `POST /api/chat` with an added `deep_research_plan` field for
execution. **Full self-contained build spec:
`docs/deep-research/IMPLEMENTATION_PLAN.md`** — includes the code-orchestration
decision, efficiency-breach carve-out for the fan-out, additive `messages.research_plan`
audit column, and file-by-file changes across backend + frontend. Relates to A3 (the
plan-first strategy is a candidate for the eval harness once both exist).

---

## Deferred / scoped follow-ups

### D1. Per-request efficiency profiles on the legislation bot
Scoped 2026-07-14, not started. The legislation bot serves three retrieval shapes
(`legislation_only` / `case_law_only` / `legislation_and_case_law`) but grades all
against the legislation-only baseline. Groundwork laid (`request_timings.research_mode`
column persisted, profile machinery extensible). **Full self-contained plan:
`docs/planning/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md`** — includes the open decisions
(dashboard segmentation vs per-mode bands; process-level vs per-request profile
composition; `get_case_law_text` missing from the distinct-retrieval set).

### D2. Re-tune parliamentary efficiency bands once real traffic accumulates
The parliament profile's dashboard indicator bands in `EFFICIENCY_PROFILES`
(`config.py`) are unmeasured starting points (noted at ship time).

### D3. Semantic retrieval (pgvector) — NO-GO, revisit only on new evidence
Measured 2026-07-13: FTS ~85% raw / ~97%+ with Worker reformulation; cheap wins
shipped (`589667c`). Revisit only if a reformulation-resistant miss class emerges.
Plan: `docs/parliament/SEMANTIC_RETRIEVAL_PLAN.md` (DEFERRED/NO-GO).

### D4. Give the test suite its own database (`TEST_DATABASE_URL`) — DONE 2026-07-17
`tests/conftest.py` points at the same `lexchat` DB as local dev and **drops all
tables at session end**, so every `pytest` run wipes local chats, provider settings,
and admin config (bit three times in one session, 2026-07-16). Add a
`TEST_DATABASE_URL` env var (fallback: `DATABASE_URL` + `_test` suffix), create the
test DB on demand, and refuse to run against a DB that already holds non-test data.

**Done 2026-07-17 (on `feature/token-cost-caching`):** conftest resolves
`TEST_DATABASE_URL` (fallback `<dev-db>_test` → `lexchat_test`), exports it as
`DATABASE_URL` **before any `src` import** so `src.database`'s import-time engine
(and `async_session_maker`, used directly by `/api/chat` etc.) targets the test DB
too — not just the `get_db` override; env vars beat `.env` in pydantic-settings,
with an assert that the override took. Auto-creates the DB via the `postgres`
maintenance DB; two refusal guards (both verified): same-name-as-dev → exit, and
tables-present-but-no-`test_db_marker` → exit before anything is dropped (guard
runs pre-create_all; teardown never reached). Verified: 119 tests green against
auto-created `lexchat_test`; dev-DB canary row + provider seed + admin user all
survived the run; `lexchat` and `lexchat_parliament` both refused.

### D5. Token-cost caching (scoped 2026-07-16; #1 and #2 BUILT 2026-07-16 on `feature/token-cost-caching`; #3 analysed → NOT built)
**Context.** The dominant token cost is the ReAct loop re-sending the full
conversation (system prompt + all accumulated tool results) as input tokens on
*every* turn — a worker that makes 6 tool calls pays for its retrieved legislation
text ~6×. Deep Research (B3) multiplies this by plan-step count (each step is a full
worker run), so caching matters more now than when first discussed. Tuned hybrid
query ≈ $0.18 on OpenRouter; a 5-step deep-research run is ~N× that. Earlier
conclusion still holds: summarisation-output caching is a poor fit (summaries are
query-dependent → near-zero hit rate).

Three sub-items, in ROI order:

1. **Provider prompt caching on the OpenRouter path (highest ROI, small change).**
   OpenAI/Gemini models cache automatically (we may already get partial discounts);
   Anthropic models need explicit `cache_control` breakpoints in the request payload.
   Change: in `openrouter_client.py` `chat_loop`, mark the system prompt (stable
   across turns) and the message prefix with `cache_control` when the model is
   Anthropic. Typical agent-loop saving: 50–90% of repeated input tokens. Ollama
   cloud exposes no caching mechanism — nothing to do on that provider.
   Verify via OpenRouter usage stats / `cache_discount` fields in the response.

2. **Per-request tool-result memo for Deep Research (trivial, targets measured
   waste).** Plan steps run as isolated workers, so two steps that retrieve the same
   Act each pay fetch + summarise (observed in the first live run:
   `redundant_tool_calls=1` — two steps both fetched the Acquisition of Land Act
   1981). Change: `run_deep_research` passes a per-request dict
   `(tool_name, canonical_args) → result` into `run_worker_tool` (alongside the
   existing `search_budget` pattern); exact-match repeats short-circuit, skipping the
   API call *and* the duplicate summarisation. No TTL/invalidation questions — the
   memo dies with the request. Exact-arg matches only; do not fuzzy-match queries.

3. **LEX / case-law response cache — already scoped as A5; build only on evidence.**
   Saves latency + eval-rerun cost more than tokens (the LLM still reads the text
   either way; token savings only where the summarise threshold is re-tripped for the
   same oversized doc). Before building, size it from existing metrics:
   `lex_api_total_ms` (is LEX latency material? A5 says LLM dominates ~30:1) and
   `summarisation_chars_in` (is the same doc being re-summarised often?).

**Measurement first for #1/#3:** the Efficiency tab already records per-request
`total_cost_usd`, `summarisation_chars_in/out`, and `lex_api_total_ms` — a week of
real traffic quantifies the ceiling before any code is written. #2 needs no
measurement; the redundancy counter already proves it.

**Follow-up scoped 2026-07-17 (not started): D6 below — cache feature toggles +
Admin Portal Cache stats tab. Plan: `docs/CACHE_ADMIN_UI_PLAN.md`.**

**Status 2026-07-16 (`feature/token-cost-caching`, off `feature/deep-research`):**
- **#1 built** — `_apply_anthropic_cache_control` in `openrouter_client.py` marks the
  system prompt + last text-bearing message with `cache_control` for `anthropic/*`
  models only (non-Anthropic payloads byte-identical). Cached-token usage
  (`prompt_tokens_details.cached_tokens`, `cache_discount`) is logged and persisted
  as additive `request_timings` columns `cached_prompt_tokens` / `cache_discount_usd`.
  Live verification against OpenRouter is OUTSTANDING — no OpenRouter API key exists
  on the dev machine (it lived in the `AppSetting` row wiped by the D4 conftest bug);
  verify the tool-role breakpoint is accepted once a key is available.
  **Update 2026-07-17 (key restored):** provider-side caching verified live on the
  configured `google/gemini-3.1-pro-preview` — implicit (automatic) caching, no
  cache_control needed: a heavy 3-Act query (16 worker tools, 12 ReAct turns,
  $0.258) recorded **30,345 cached prompt tokens across 7 of ~13 LLM calls**
  (~3.4K→6.7K/turn as context grew); a small query (turns ≈1.5–3K tokens) got 0 —
  Gemini's implicit-cache minimum prefix (~4K tokens) is the threshold. Gotcha:
  OpenRouter reports `cache_discount` **only for Anthropic**; for Gemini the
  saving is baked into the billed cost, so `cache_discount_usd` stays 0 even on
  hits (Cache tab small print explains this). The Anthropic `cache_control` path
  (incl. tool-role breakpoint acceptance) remains unverified live — the user runs
  Gemini models on OpenRouter.
- **#2 built** — `run_deep_research` threads a per-request `tool_memo` dict through
  `run_worker_agent` → `run_worker_tool` (same pattern as `search_budget`). Exact
  `(tool_name, canonical-args-JSON)` repeats return the cached final result, skip the
  API call + re-summarisation, re-extract sources from the stored raw result into the
  reusing step's accumulator, and count only in the new `memo_hits` metric (not
  worker/phase/redundant counts, no budget consumption). Standard/conversational
  modes pass `tool_memo=None` — behaviour unchanged.
- **#3 NOT built (evidence does not justify it).** Legislation-bot `request_timings`
  history was destroyed by D4 conftest wipes, so sized from the parliament bot's 66
  surviving rows (2026-06-03→07-14) as a proxy: LLM time dominates external-API time
  ~16:1 (avg 73.6s vs 4.7s; p50 API 1,629 ms, p90 16.6s), and only 6/66 requests
  tripped the summarisation threshold (heavily skewed: p90 chars_in = 0, max 632K).
  A response cache would shave seconds off a ~80s request and rarely dodge a
  re-summarisation → defer until target traffic shows otherwise (re-measure after D4
  gives tests their own DB so legislation-bot history survives).

### D7. "Local prompt caching" — cross-user/cross-provider summary cache, exact-match (BUILT 2026-07-18 on feature/local-prompt-cache, live-verified)
Cross-user cache of Worker document summaries (LEX text is static; at ~200 users
query demand over the same Acts will be heavily correlated — the second lawyer
asking the same question of the same section skips the summarisation LLM call).
**No embeddings** — the earlier embedding-based variant (discussed 2026-07-17) was
rejected because semantic near-miss reuse risks silent incompleteness; this design
uses exact (canonicalised) prompt/summary pairs keyed on
`(content_hash of retrieved text, canonicalised-query hash)`, which eliminates
that risk by construction and makes staleness impossible (amended text → new hash
→ miss). Cross-provider by design (`summarise_model` stored for provenance, NOT in
the key). New `local_prompt_cache` table, `local_cache_hits` metric,
`local_prompt_cache_enabled` flag, Cache-tab surfacing — all following the D5/D6
patterns. **Implementation plan (now implemented): `docs/LOCAL_PROMPT_CACHE_PLAN.md`.**
Built on `feature/local-prompt-cache` (off `feature/token-cost-caching`);
133 tests green. Live-verified 2026-07-18: second identical run served from
cache (159s→84s, `local_cache_hits=1`, 194,822 chars saved); flag-off A/B
re-summarised as before; cross-provider hit demonstrated via a fixed Deep
Research plan (summary stored under mistral-large-3/Ollama served under
gemini-3.1-pro/OpenRouter, 141s→38s). Observed caveat: prompt-driven Manager
delegation wording varies between models, so cross-provider hits on standard
research queries need canonicalisation-equivalent phrasing — Deep Research
briefs (user-approved plan text) are deterministic and always key identically.

### D8. Cache review fixes (scoped 2026-07-18; BUILT 2026-07-18, all 7 phases on feature/local-prompt-cache, one commit per phase, 145 tests green)
A review of the D5/D6/D7 caching stack found one real bug and a set of
improvements. **Full self-contained plan: `docs/CACHE_REVIEW_FIXES_PLAN.md`.**
Phases in priority order:
1. **BUG (merge blocker for `feature/local-prompt-cache`):** `summarise_for_query`
   falls back to raw/partial text on failure, and that degraded (then truncated)
   output is stored in `local_prompt_cache` — one transient summariser error
   permanently poisons the key cross-user/cross-provider. Fix: degraded flag +
   skip store on degradation or truncation.
2. Storage hygiene: atomic `UPDATE...RETURNING` lookup, drop redundant
   content_hash index, sample the prune COUNT, 365-day retention for hit rows,
   version the canonicalisation (`v1|` hash prefix).
3. Admin purge endpoint + Cache-tab "Clear local cache" button (no escape hatch
   exists today for a poisoned entry).
4. Extend the tool memo to standard research mode (redundant_tool_calls proves
   the waste; keep recording redundancy on memo hits for loop health).
5. Key the local cache on the raw user query in standard mode (delegation-brief
   wording varies per model — the biggest hit-rate lever); Deep Research keeps
   step-brief keys. Residual full-doc collision caveat documented in the plan.
6. `request_timings.provider` column (retire the `total_cost_usd > 0` proxy) +
   Cache-tab hit-rate small print.
7. `CACHEABLE_TOOLS` allowlist — write down the public-sources-only invariant.
Out of scope (decided): Anthropic cache_control live check stays dormant until
an Anthropic model is configured; D5#3/A5 NO-GO stands; no fuzzy keying/TTLs.

### D9. Logging improvements (reviewed + scoped 2026-07-19; PR A, PR B & PR D BUILT, PR C deferred, Item 6 deferred)
Review of the backend logging strategy. **Full self-contained plan with per-item
Problem/Change/Files/Verify and PR slicing: `docs/LOGGING_IMPROVEMENTS_PLAN.md`.**
- **PR A — DONE 2026-07-19.** `LOG_LEVEL`/`CONSOLE_LOG_LEVEL` runtime level control
  (Item 3); `sptv` logger configured — was logging to a handler-less root, so INFO
  dropped and WARNING+ went to bare stderr (Item 1); HTTP middleware try/finally +
  5xx→ERROR (Item 7a); `error.log` handler on the `http` logger (Item 7c). Files:
  `utils/logger.py`, `config.py`, `main.py`, `CLAUDE.md`. Verified via smoke test.
- **PR B — DONE 2026-07-19.** Traceback pass (Item 2): `exc_info=True` on ~24
  genuine-fault handlers (agent layer, services, crawler loop-level catch-alls,
  `database.py`, `ai.py`/`research.py`); fail-soft/high-volume paths left terse.
  145 tests green.
- **PR C — DEFERRED.** Sensitive-data redaction (Item 4): full user query text is
  logged at INFO (`agent_core.py:58`, `learning.py:145`) and email addresses at
  `auth.py:174` + `email_service.py` — a concern for OFFICIAL-SENSITIVE / government-
  lawyer users given 14-day log retention. Plan adds `redact_text()`/`redact_email()`
  helpers, redact at INFO, full text only at DEBUG. **Open decision for the deploying
  org:** whether query text may appear even at DEBUG. Record the decision in
  `CLAUDE.md` when built.
- **PR D — DONE 2026-07-19 (Items 5 + 7b).**
  Correlation/request IDs across all loggers (Item 5): new `utils/log_context.py`
  (`request_id_var` ContextVar, default `-`, + `RequestIdFilter`); `[%(request_id)s]`
  added to `LOG_FORMAT` with the filter attached inside both handler factories (so
  every record has the attribute — guards `KeyError: 'request_id'`); the id is
  minted/accepted (inbound `X-Request-ID`) and set/reset in the `log_requests`
  middleware, and echoed on the response. Propagation verified through the endpoint's
  `create_task` (ai.py:235 pattern) to `agent` lines — no signature changes, same
  mechanism as the provider-config ContextVar. Align/disable uvicorn's access logger
  (Item 7b): `--no-access-log` added to all three launch scripts, and `uvicorn.error`
  adopted into the app handlers so startup/lifecycle errors reach `error.log`. Unit
  tests in `tests/test_log_context.py`; 150 tests green. Backend-only (no dist
  rebuild). Build plan: `docs/LOGGING_PR_D_PLAN.md`.
- **Item 6 — DEFERRED separately (2026-07-19).** Optional JSON/structured file output
  for a SIEM (no new dependency; toggled by `LOG_FORMAT_JSON`). Split out of PR D and
  parked — build only if the deployment gains a central log aggregator. Depends on
  Item 5 (so `request_id` is a first-class JSON field).

### D6. Cache admin UI: feature toggles + Cache stats tab (scoped 2026-07-17, BUILT 2026-07-17)
Two feature flags in Developer tab → Feature flags (`prompt_caching_enabled`,
`tool_memo_enabled`, both default ON = current behaviour), consumed via the request
provider-config ContextVar (same pattern as `_research_mode`); plus a new Admin
Portal "Cache" tab backed by `GET /api/stats/cache` over the D5 `request_timings`
columns (`memo_hits`, `cached_prompt_tokens`, `cache_discount_usd`): KPI row, daily
series, recent-hits table, and current flag state. Full plan with file references
and suggested order: `docs/CACHE_ADMIN_UI_PLAN.md`. Work on
`feature/token-cost-caching`.

**Status 2026-07-17 (built, uncommitted on `feature/token-cost-caching`):**
- Flags live in `_DEFAULT_FEATURES`/`FeaturesUpdate` (developer.py) — old saved
  features JSON and old client POST bodies stay valid (merge-over-defaults +
  defaulted Pydantic fields). Consumed via `_prompt_caching_enabled` /
  `_tool_memo_enabled` in the request config ContextVar (set in routers/ai.py);
  gate `_apply_anthropic_cache_control` and `run_deep_research`'s `tool_memo`.
  Absent key = enabled, so direct callers/tests/parliament bot unchanged.
- `GET /api/stats/cache?days=N` (admin-only, stats.py) — KPI row, daily series,
  recent-hits table (last 20 with memo_hits>0 OR cached_prompt_tokens>0), and
  flag-state echo. "OpenRouter-eligible" proxied by `total_cost_usd > 0` (no
  provider column on request_timings). New Cache tab (`admin/CacheTab.jsx`) +
  two extra Feature-flag toggle rows in AdminPortal.jsx; dist rebuilt.
- Verified: 119 tests green (12 new); live A/B on identical 2-step deep-research
  runs — flag ON: step 2 `search_legislation` served from memo (memo_hits=1);
  flag OFF: same call re-executed, memo_hits=0; Cache tab endpoint returned the
  real hit row. Prompt-caching toggle unit-tested only (no OpenRouter key on dev
  machine — live payload check still outstanding, same as D5).
