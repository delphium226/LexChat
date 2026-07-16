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

### A2. Appeals nudge on case-law search results
**Problem:** retrieving the appellate decision of a case is search luck — some L31
runs got only the first-instance *Coulthard* [2024] EWHC 3252 (Admin) and missed
[2025] EWCA Civ 1671. The prompt rule (fb88b41) is soft.
**Fix:** extend the Phase-2 nudge pattern — after `search_case_law` results are
slimmed, detect citations with matching party names across court levels (EWHC → EWCA)
and append `[NOTE: an appellate decision of this case is in the results — retrieve
it]` to the tool result.
**Home:** `agent/tools/caselaw.py` (slimming) + `agent_shared.py` (nudge injection).

### A3. Golden-question eval harness
**Problem:** variance is eyeballed from single runs; format/citation compliance needs
to be a measured metric before changing the streaming path.
**Fix:** thin harness — loop over `docs/evals/GOLDEN_QUESTIONS_*.md`, call `/api/chat` per
question with n≥3 samples, parse the SSE token stream, regex-check required citations
and automatic-fail conditions, emit CSV with per-question grade spread. Published
metric: % A/B, % D separately (per the rubric in the golden-question files).
Reuses the SSE parsing from the 2026-07-15 test runs.

### A4. Worker report structure validation + one reformat retry
Cheaper mitigation for A1's problem: after the Worker returns, check the report has
the five section headers and ≥1 link under References; if not, issue ONE follow-up
call ("reformat your findings into the required structure; do not redo research") —
no tools re-run. Skip if A1 lands first.

### A5. LEX / case-law API response cache (pre-existing idea, re-scoped)
Response cache keyed on (endpoint, payload) with TTL; legislation text is highly
cacheable. Doesn't reduce variance for novel queries but makes eval re-runs (A3)
cheaper and more repeatable. LLM time dominates ~30:1, so this is an eval-cost play,
not a latency play. See also D5 (token-cost caching) — this is D5's sub-item 3.

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

### D4. Give the test suite its own database (`TEST_DATABASE_URL`)
`tests/conftest.py` points at the same `lexchat` DB as local dev and **drops all
tables at session end**, so every `pytest` run wipes local chats, provider settings,
and admin config (bit three times in one session, 2026-07-16). Add a
`TEST_DATABASE_URL` env var (fallback: `DATABASE_URL` + `_test` suffix), create the
test DB on demand, and refuse to run against a DB that already holds non-test data.

### D5. Token-cost caching (scoped 2026-07-16, not started)
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
