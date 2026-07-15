# TODO — Agent Quality Backlog

Items scoped 2026-07-15 after the XL Bully (golden question L31) variance investigation.
Context: run-to-run variance in format compliance and search luck; prompt-level fixes
landed in `fb88b41`, these are the code-level follow-ups. Temperature is already
lowered to 0.0 for both providers on both bots (DB `AppSetting`, via Admin Portal API).

## 1. Stream worker report verbatim in research mode
**Problem:** the Manager re-generates the Worker's report token by token, so format
compliance depends on prompt obedience. On L31, 1 of 3 runs lost all section headers
and the References section despite the PASS-THROUGH ACCURACY rule.
**Fix:** in research mode, stream the Worker's report to the client verbatim in code;
the Manager's LLM call contributes only the conversational wrapper (intro + follow-up
question). The report can't be condensed because the Manager never regenerates it.
Same philosophy as the Phase-2 nudges / search budget: code enforcement > prompt.
**Notes:** touches the SSE streaming path in `chat_loop` — land after the eval harness
(item 3) exists so regressions are measurable. Supersedes item 4 if implemented.

## 2. Appeals nudge on case-law search results
**Problem:** whether the Worker retrieves the appellate decision of a case is search
luck — some L31 runs got only the first-instance *Coulthard* [2024] EWHC 3252 (Admin)
and missed [2025] EWCA Civ 1671. The prompt rule (fb88b41) is soft.
**Fix:** extend the Phase-2 nudge pattern — after `search_case_law` results are
slimmed, detect citations with matching party names across court levels
(EWHC → EWCA) and append `[NOTE: an appellate decision of this case is in the
results — retrieve it]` to the tool result.
**Home:** `agent/tools/caselaw.py` (slimming) + `agent_shared.py` (nudge injection).

## 3. Golden-question eval harness
**Problem:** variance is currently eyeballed from single runs; format/citation
compliance needs to be a measured metric before changing the streaming path.
**Fix:** thin harness — loop over `evals/GOLDEN_QUESTIONS_LEGISLATION.md` (and the
parliament set), call `/api/chat` per question with n≥3 samples, parse the SSE token
stream, regex-check required citations and automatic-fail conditions, emit CSV with
per-question grade spread. Published metric: % A/B, % D separately (per the rubric
in the golden-question files).
**Notes:** reuses the SSE parsing used in the 2026-07-15 test runs. A LEX/caselaw
response cache (see below) would make re-runs cheaper and more repeatable.

## 4. Worker report structure validation + one reformat retry
**Problem:** same as item 1, cheaper mitigation.
**Fix:** after the Worker returns, check the report contains the five section headers
and ≥1 link under References; if not, issue ONE follow-up call ("reformat your
findings into the required structure; do not redo research") — no tools re-run, so
it costs a fraction of a delegation.
**Notes:** skip if item 1 lands first.

## 5. LEX / case-law API response cache (pre-existing idea, re-scoped)
**Problem:** repeated eval runs re-fetch identical Acts/judgments; doesn't reduce
variance for novel queries but makes eval re-runs cheaper and more deterministic.
**Fix:** response cache keyed on (endpoint, payload) with TTL; legislation text is
highly cacheable. See earlier caching discussion — LLM time dominates ~30:1, so this
is an eval-cost play, not a latency play.
