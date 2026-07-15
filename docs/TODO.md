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

### T2. Merge `chore/tidy-up` → `main`
Merge smoke: both bots (legislation :8000, parliament :8001) × both providers
(Ollama, OpenRouter). Nothing on this branch is live until merged — the target
deploys via `git pull origin main`.

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
not a latency play.

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
