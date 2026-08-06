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

---

## Session 2 — 2026-08-06 — S2 Corpus schema + ingest

Completed in full, ingest included — the split-session fallback was not needed.

**Done:**
- `DraftingGuidance` (`models.py`) following `SpPlenaryItem`: `source`, `part`, `chapter`,
  `rule_ref`, `heading`, `full_text`, `structured` (JSON), `url`, `version_date`, `sensitivity`,
  `fetched_at`, `UniqueConstraint(source, rule_ref)`.
- Hand-written DDL in `database.py` (no Alembic): `CREATE TABLE IF NOT EXISTS drafting_guidance`
  in the migration block, plus four indexes — three btree and
  `USING GIN (to_tsvector('english', coalesce(full_text,'')))`.
- `services/drafting_ingest.py` — one-shot ingest, no crawler, no background task.
- `routers/drafting.py` — `POST /api/drafting/ingest` and `GET /api/drafting/corpus`, both on an
  admin-by-default sub-router copying the `developer.py` convention. Registered in `main.py`.
- `tests/test_drafting_corpus.py` (18 tests). Suite 365 → **383 green**.
- **Live ingest run against `lexchat_drafting`: 285 rows, mean 975 chars, median 691, min 27,
  max 5992.** Re-run inserted 0 / skipped 285 — idempotent.

**Surprises / deviations from BUILD_PLAN:**

- **Source: the gov.scot HTML, not the PDF. The plan's `_extract_text` reuse does not happen.**
  This was the open question and the answer is not close. The PDF is a designed 171-page
  publication: under `pdfplumber` its **pull-quotes interleave mid-sentence into the body**
  (p.11 extracts as "WE WILL CONTINUE Two years have passed since we published the first edition
  of / TO DEVELOP / AND SHARE OUR / The reaction we received…"), every page carries a running
  header, and — decisively — **all heading levels flatten to bare lines** indistinguishable from
  prose, so per-topic chunking off the PDF would need font-size analysis. The HTML encodes a real
  two-level hierarchy (`<p><strong>` = chapter/section, `<p><em>` = sub-topic). It also needs no
  new dependency: stdlib `re` + a `_strip_html` helper, matching `parliament.py`. A DOM parser
  would have meant regenerating the offline dependency bundle (see the note at the top of
  `requirements.txt`). BUILD_PLAN Phase 2 amended.

- **Drafting Matters! has no numbered rules — in either format.** The ledger row said "chunked per
  numbered rule". There is nothing to number: the document's unit is a **named topic**
  ("shall v must", "Gender neutrality", "numbers generally") with a `Rules:` / `To note:` body.
  That unit is the chunk, and it happens to be the right size (median 691 chars). The
  make-or-break instruction survives intact in substance — per topic, never per chapter — but a
  future session looking for `rule_ref` values like "1.2.3" will not find them; `rule_ref` is a
  slug path (`p6/language/particular-words-and-expressions/shall-v-must`). BUILD_PLAN amended.

- **The List of Contents page (page 1) is load-bearing, and it is the only place the
  chapter/section split is stated.** In the body, a chapter ("Language") and a section
  ("Plain language") are both `<p><strong>…</strong></p>` — identical markup. Parsing the contents
  page gives an authoritative split. It also **recovers headings whose `<strong>` markup is
  missing in the body**: "Numbers and symbols" is a bare `<p>` in the HTML, and without recovery
  its four child topics would have been misfiled under "Dates".

- **Three body-markup traps, all pinned by tests.** (1) *Example provisions* are bolded exactly
  like headings ("1 Short title", "50A Form of ballot papers") — detected by a leading numeral or
  quote mark and kept as body. (2) Part 2 opens with a long bolded `Note:` paragraph — headings
  are capped at 120 chars. (3) gov.scot sometimes leaves a `<strong>` open across several
  `<br />`-separated contents entries; a multi-line span is treated as **sections, not chapters**,
  deliberately biased that way because a chapter misread as a section still gets its own chunk,
  whereas a section misread as a chapter loses its heading.

- **The GIN index is correct but the planner does not use it at 285 rows, and that is fine.**
  Plain `EXPLAIN` shows a Seq Scan (cost 73.29). With `enable_seqscan=off` it is a
  `Bitmap Index Scan on idx_drafting_guidance_full_text` with an exactly-matching `Index Cond`,
  so the expression matches byte-for-byte — the seq scan is a cost decision on a tiny table, not
  a defect. **Do not "fix" this.** The test forces `enable_seqscan=off` for the same reason.
  `DRAFTING_FTS_EXPR` in `models.py` is imported by both `database.py` and (at S3) the retrieval
  tool, so the match is structural rather than remembered.

- **`index=True` on a model column plus an explicit `CREATE INDEX` produces two indexes on the
  same column** (`ix_drafting_guidance_part` *and* `idx_drafting_guidance_part`). Caught by
  reading `pg_indexes` after the live run. Removed `index=True`; the DDL is the single
  declaration site. **The older `sp_committee_items` / `sp_plenary_items` tables have this same
  duplication today** (`committee_code`, `committee_name`, `meeting_date` — six redundant
  indexes). Not touched here: out of scope, and dropping indexes on a populated parliament bot is
  its own decision. Worth a cleanup line in `TODO.md`.

- **`sensitivity` needed `server_default`, and no other model in the file uses one.** With a
  Python-side `default` only, `Base.metadata.create_all` (what `conftest` builds) omits the
  `DEFAULT` clause the hand-written DDL gives the real table — so a raw INSERT omitting the
  column succeeds in production and raises `NotNullViolationError` under test. A real test caught
  it. Fixed for this column because it is the one gating OFFICIAL-SENSITIVE material; **the same
  latent ORM-vs-DDL divergence exists on every other table in `models.py`.**

- **Measured, and rejected: adding `heading`/`chapter` to the indexed FTS expression.** Tried it
  against the live corpus. It recovers one extra hit on one probe and nothing on the others,
  because the real failure is `plainto_tsquery`'s AND-of-all-terms, not missing vocabulary.
  Not worth changing a pinned index expression for. Kept `full_text`-only, matching
  `_search_plenary_db`.

**Retrieval quality as ingested — read this before S3:**
The BUILD_PLAN spot-check passes: `'avoiding masculine pronouns'` → *Language > Gender
neutrality* and `'how to word a commencement provision'` → *Form and key components of Bills >
Commencement provisions*, both by concept, neither by exact heading. But conversationally-phrased
probes hit the AND-cliff hard — `'obligation imposed on a person'`, `'splitting a long sentence
into paragraphs'` and `'referring to a section elsewhere in the same Act'` all return **zero
rows** under `plainto_tsquery`, while an OR query returns 78 for the first and ranks them badly
(top hit *Criminal liability of the Crown > Drafting considerations*). So:
- the `_or_tsquery` zero-result fallback in the S3 row is **necessary here, not inherited dogma**;
- and the OR fallback's ranking is visibly poor on this corpus, which is early evidence for the
  **pgvector re-measurement** the plan defers to S7. BUILD_PLAN already says that NO-GO was
  measured against a transcript corpus and must be re-measured against this one. It looks likely
  to go the other way. Do not let S7 inherit the transcript-corpus decision.

**Still open, deliberately not done in S2:**
- `search_drafting_guidance` is S3 and does not exist yet. The standing invariant is carried
  forward untouched: **it must not be added to `CACHEABLE_TOOLS`**, and its `query` arg must not
  go in `SAFE_ARG_KEYS`. `tests/test_drafting_security.py` still pins the former.
- The two redaction sites S0 flagged (`agent/agent_core.py:176` delegation brief,
  `routers/learning.py:145`) are **still open** — third session running. They are one-liners and
  must be closed before the bot sees real pre-publication drafts.
- No Admin Portal UI for the ingest; `POST /api/drafting/ingest` is called directly. Fine for a
  one-shot, but if it ever needs a button it belongs with S6.
- The internal OFFICIAL-SENSITIVE guidance is still unavailable. The schema takes it with no
  migration: a second `source` with `sensitivity='official_sensitive'`, pinned by a test.

**State of the branch:** `feature/drafting-bot` at `17ca4cc` (code) + this log commit, tests green
(**383 passed**; 365 at the S1 baseline, 18 added).

**Pushed — this changed at the end of S2 and breaks the pattern S0/S1 set.**
`feature/drafting-bot` now has a remote (`origin/feature/drafting-bot`, pushed at `09802ad`).
That is safe and does **not** weaken the deployment carve-out: the target pulls `origin/main`,
which this does not touch. Pull/rebase against the remote branch from here on rather than
assuming it is local-only. **`main` is still at `c220185` and must stay there.**

**Local machine state:** the dev DB `lexchat_drafting` already holds the ingested corpus
(285 rows). S3 can develop and test `search_drafting_guidance` against real data immediately —
no need to re-run the ingest. On a different machine, run `POST /api/drafting/ingest` as admin
(or the boot sequence: `init_db()` then `ingest_drafting_matters()`).

**⚠️ `main` is 3 commits ahead of `origin/main`, and one of them is S0.** `6be5338`
(`secure=True` cookie + log redaction) is committed locally but **never pushed**, so the
deployment target does not have it — three sessions and counting. BUILD_PLAN deliberately
carved S0 out to land on `main` because those fixes are correct regardless of whether the
drafting bot ships, and the live deployment wants them; that intent is currently unrealised.
Also unpushed: `2aa574d` and `c220185` (the plan and the S0 log). Pushing `main` is an
outward-facing act — it makes the changes pullable to production — so it is the user's call,
not a drive-by. Flagged to the user 2026-08-06; no decision yet.

**Next action:** S3 — `search_drafting_guidance` (copy `_search_plenary_db` including the
empty-table graceful note and the `_or_tsquery` fallback, which the numbers above show this corpus
needs), then the LEX `/amendment/search` + explanatory-note endpoints, then registration in
`utils/stopwatch.py:3-28` and `agent_shared.py` `_extract_sources_inner`.
