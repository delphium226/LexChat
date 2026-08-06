# Drafting bot — session log

Append-only, newest last. One entry per session. Read `BUILD_PLAN.md` first, then this file
for what actually happened.

The **Surprises / deviations** line is the one that matters — it is where a cold-starting
session learns that reality diverged from the plan.

## Entry template

```markdown
## Session N — <date> — <ledger row>
**Done:** …
**Surprises / deviations from BUILD_PLAN:** …
**State of the branch:** <commit sha>, tests <green|N failing>
**Next action:** <the single next thing>
```

---

## Session 0 — 2026-08-05 — S0 Security prereqs

**Done:**
- Created the tracking artefacts: `BUILD_PLAN.md` (plan + tickable ledger; comparable-tools
  scan moved to Appendix A), this log, and the two `CLAUDE.md` edits (the
  `feature/drafting-bot` exception under Active Branch, and the lazy-loaded pointer).
  Commit `2aa574d`.
- S0, commit `6be5338`, on `main`: `secure=True` on the auth cookie; new `utils/redact.py`
  (`redact_text` / `redact_email` / `redact_args`) applied at `agent/tools/executor.py` and
  `routers/auth.py`; `drafting_mode_enabled` feature flag (4 backend sites);
  `local_prompt_cache_enabled` forced off for `research_mode == "drafting"` in
  `build_request_config`, with the reason recorded in `CLAUDE.md`.
- New `tests/test_drafting_security.py` (24 tests) pinning all four.

**Surprises / deviations from BUILD_PLAN:**
- **The cache disable is enforced in code, not left to the Admin Portal toggle.** The plan says
  "turn `local_prompt_cache_enabled` off for this bot"; as an operator setting that is a memory,
  not a control, and the failure mode is a draft clause in a cross-user plaintext table. Put it
  in `build_request_config` — the one seam all three agent endpoints share. **Side effect: the
  Cache tab will show "Local cache" ON for a drafting bot. That is correct, not a bug.**
- **Redaction is only half done, and the remaining half matters more than the half that is
  done.** The S0 row names `executor.py` and `auth.py`, which is what I changed. But
  `agent_core.py:176` logs the Manager's delegation brief at INFO, and in a review flow that
  brief can quote the draft. `learning.py:145` logs a full query too (admin-only). Both are
  one-liners; both are out of the S0 row so I left them. **Close them before the bot sees real
  drafts.** Also: full text still appears at `LOG_LEVEL=DEBUG` by design — flagged in
  `CLAUDE.md` as a decision for the deploying org.
- `redact_args` is a third helper the logging plan does not spec — the executor logs a *dict*,
  and blanket-redacting it would have destroyed the log's operational value (you could no
  longer see which Act was fetched). It is an **allowlist**, so it fails safe: a future tool
  with a new free-text param is redacted by default.
- My first draft of the executor test called a real tool name and **made a live HTTP request to
  the LEX API** (confirmed: `POST /legislation/section/search 200 OK`). Rewritten to use an
  unrecognised tool name, which exercises the same log statement — it is emitted before tool
  dispatch — and returns without a network call. Worth watching for: LEX is rate-limited at
  1000 req/hour per shared IP, so a test suite must never call it.
- `secure=True` means the cookie is not set over plain HTTP, including local dev on :8000.
  Harmless — the frontend uses the bearer token and `get_current_user` falls back to the
  `Authorization` header — but if cookie auth appears broken locally, this is why.
- Checked and **not** a problem: `AdminPortal.jsx` round-trips the server's full flag dict, so
  the missing `drafting_mode_enabled` toggle row does not silently reset the flag. The UI row
  belongs with S1/S6.

**State of the branch:** `main` at `6be5338`, tests green (350 passed; baseline was 326).
Nothing pushed. `feature/drafting-bot` does **not** exist yet.

**Next action:** create `feature/drafting-bot` off `main` and start S1 (bot scaffolding) — the
7 dispatch keys are the risk, because a missed one silently inherits legislation behaviour.

---

## Session 1 — 2026-08-06 — S1 Bot scaffolding

**Done:**
- Branched `feature/drafting-bot` off `main` at `c220185`. Baseline confirmed green (350 passed)
  before any change.
- `bots/drafting/{bot_config.json, .env, assets/logo.svg}` — `drafting_bot` / "DraftChat", port
  8003, DB `lexchat_drafting`, `RESEARCH_MODE=drafting` in the **`.env`** (the `.env` comment
  records that `agent.research_mode` in `bot_config.json` is decorative).
- All 7 dispatch keys added: `EFFICIENCY_PROFILES` (config.py), `get_worker_tools`
  (tools/schemas.py), `get_worker_system_prompt` / `get_manager_system_prompt` /
  `_filter_constraint_block_for_mode` / `_PLANNER_MODE_NOTES` (prompts.py), `_REPORT_SECTIONS`
  (agent/agent_core.py).
- **The dispatch test** — 9 new tests in `tests/test_suggestions.py`, one per dispatch site plus
  the conversational-chat-mode path and a pin that `search_drafting_guidance` is not there yet.
  Each asserts *both* halves: resolves to the drafting object AND is not the legislation
  fallback. `"drafting"` also added to `_MANAGER_PROMPT_CASES`, so it now runs through all six
  existing parametrised prompt-wiring tests (chips on/off, consulted-peer suffix).
- Frontend: `isDrafting` in `App.jsx`, filter-pill bar and `ResearchFiltersModal` both gated off,
  drafting empty-state copy, and the two-way ternaries in `constants/research.js` given an
  explicit drafting branch with null-guards in `useFilters.js`.
- `deployment/start_federation_dev.ps1` gains a fourth bot entry; step 4 wires a full mesh, so
  that registers drafting↔legislation (and ↔ both parliament bots) with no other change.
- All of the above is commit `4cf385b`; this log entry is its own commit, as in S0.
- **Live boot verified**: `lexchat_drafting` created, bot up on :8003, `/api/bot-info` returns
  `research_mode: "drafting"`, `/api/stats/efficiency` returns `researchMode: drafting` with the
  drafting profile (no `max_budget_blocked` — correct, drafting has no search budget), logo
  endpoint 200. No parliament crawler started.

**Surprises / deviations from BUILD_PLAN:**
- **`get_worker_tools` needed a distinct list object, not just a branch.** Drafting's tool set is
  the legislation one until S3 adds `search_drafting_guidance`, so `return WORKER_TOOLS` would
  have been byte-identical to the fallback — and therefore **untestable**: the dispatch test
  could not tell "branch present" from "branch missing". Added `DRAFTING_TOOLS = list(WORKER_TOOLS)`
  and the test asserts *identity* (`is DRAFTING_TOOLS`, `is not WORKER_TOOLS`). Same shape of
  problem will recur for any future mode whose initial config equals the fallback.
- **An 8th site the plan does not list: the conversational-worker-prompt guard**
  (`get_worker_system_prompt`, prompts.py ~549). It reads
  `research_mode not in ("parliamentary_records", "westminster_records")` — a separate condition
  from the `base` dict lookup the plan names, and adding only the dict key would have given the
  drafting bot the **generic legislation-shaped conversational worker prompt** in conversational
  mode while looking correctly wired in research mode. Drafting now joins that tuple, matching
  the parliament/Westminster bots. Pinned by its own test. `get_manager_mode_note` has a
  similar-looking tuple at prompts.py:589 and needs **no** change — the drafting manager branch
  early-returns before it is ever called.
- **The `_filter_constraint_block_for_mode` branch returns `""` and that is the point.** Falling
  through would have emitted a jurisdiction / in-force block describing filters the drafting bot
  never shows. The test proves it is the branch and not an empty cfg, by asserting the same cfg
  yields a non-empty block on the legislation path.
- **The `client/dist/` trap.** I ran `npm run build` only to confirm the JSX parses — but `dist/`
  is **tracked** (force-added), so the build dirtied tracked files and left `index.html` pointing
  at a new hashed bundle. Reverted with `git checkout -- client/dist` so this commit is
  source-only, per the ledger putting the rebuild at S6. If you build to check compilation on a
  session that is not S6, revert dist before committing.
- **`bots/*/.env` is gitignored, so the parliament and Westminster ones exist only on this
  machine.** Only `bots/legislation/.env` is tracked (and it holds just `BOT_ID` /
  `BOT_CONFIG_PATH`). That means a fresh clone of this branch would get `bots/drafting/` with no
  `.env`, `start_federation_dev.ps1` would skip it via its `Test-Path` guard, and the bot would
  boot with `RESEARCH_MODE` unset — i.e. **as a legislation bot wearing a drafting name**, the
  exact silent-inheritance failure this whole session is about. Force-added it (`git add -f`).
  It holds no secrets: the dev DB credentials are already in `CLAUDE.md`. This is the same
  reasoning S0 used to reject the Admin Portal toggle for the cache flag — a per-machine file is
  an operator memory, not a control.
- Report structure: `_REPORT_SECTIONS["drafting"]` and the worker prompt's OUTPUT STRUCTURE block
  are two copies of the same list. A test now asserts every section name appears in the prompt,
  so S4/S5 cannot change one and forget the other.
- **Prompts are placeholders and are labelled as such in the source.** `_DRAFTING_BODY`,
  `_DRAFTING_CHIPS`, `DRAFTING_WORKER_SYSTEM_PROMPT` and the planner note carry the structural
  contract (delegate, verbatim pass-through, OUTPUT STRUCTURE, chips rules, no-invented-convention)
  and nothing drafting-specific. They will look finished at a glance. They are not — S4 writes the
  real ones against the S2/S3 corpus and tools.

**Still open, deliberately not done in S1:**
- The `drafting_mode_enabled` **Admin Portal toggle row** (S0 note 4 suggested "S1/S6"). Left out:
  it is not in the S1 ledger row, and nothing reads `_drafting_mode_enabled` yet, so the toggle
  would toggle nothing. Belongs with S6.
- The two redaction sites S0 flagged (`agent/agent_core.py:176` delegation brief,
  `routers/learning.py:145`) are **still open**. Not in the S1 row either. They must be closed
  before the bot sees real pre-publication drafts.

**State of the branch:** `feature/drafting-bot` at `4cf385b` (code) + this log commit, tests green
(365 passed; 350 at the S0 baseline, 15 added). Nothing pushed; `main` still at `c220185`.

**Next action:** S2 — the `DraftingGuidance` model and the hand-written DDL + GIN index in
`database.py`. If S2 runs long, stop after schema + DDL and leave the Drafting Matters! ingest for
its own session, as the ledger advises.
