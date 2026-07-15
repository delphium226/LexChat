# TODO

**This file is the canonical todo list for the project** (as of 2026-07-15). Deferred
work previously tracked across auto-memory notes, `*_PLAN.md` docs, and GitHub issues
(stale since April 2026) should be recorded or referenced here going forward.

---

## Tidy-up branch (`chore/tidy-up`) — remaining chores

All fixes-queue items are closed (test suite green at 56 passed; visual smoke done).
Agreed sequencing: triage working tree → merge → regenerate bundle LAST.

### T1. Triage uncommitted working-tree changes
`client/src/App.jsx`, `components/DataSensitivityNotice.jsx`, `components/SourcesRail.jsx`
are modified (plus corresponding `client/dist` changes) and
`evals/GOLDEN_QUESTIONS_PARLIAMENT.md` is untracked. Commit or discard before merge —
uncommitted work is invisible to the target.

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
**Fix:** thin harness — loop over `evals/GOLDEN_QUESTIONS_*.md`, call `/api/chat` per
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

## Deferred / scoped follow-ups

### D1. Per-request efficiency profiles on the legislation bot
Scoped 2026-07-14, not started. The legislation bot serves three retrieval shapes
(`legislation_only` / `case_law_only` / `legislation_and_case_law`) but grades all
against the legislation-only baseline. Groundwork laid (`request_timings.research_mode`
column persisted, profile machinery extensible). **Full self-contained plan:
`server_py/PER_REQUEST_EFFICIENCY_PROFILE_PLAN.md`** — includes the open decisions
(dashboard segmentation vs per-mode bands; process-level vs per-request profile
composition; `get_case_law_text` missing from the distinct-retrieval set).

### D2. Re-tune parliamentary efficiency bands once real traffic accumulates
The parliament profile's dashboard indicator bands in `EFFICIENCY_PROFILES`
(`config.py`) are unmeasured starting points (noted at ship time).

### D3. Semantic retrieval (pgvector) — NO-GO, revisit only on new evidence
Measured 2026-07-13: FTS ~85% raw / ~97%+ with Worker reformulation; cheap wins
shipped (`589667c`). Revisit only if a reformulation-resistant miss class emerges.
Plan: `bots/parliament/SEMANTIC_RETRIEVAL_PLAN.md` (DEFERRED/NO-GO).
