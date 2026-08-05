# Drafting bot — build plan

**Status:** in build. **Branch:** `feature/drafting-bot` (S1 onward; S0 landed on `main`).
**Read this file first** at the start of every session, then `SESSION_LOG.md` next to it for
what actually happened.

Adding a legislative-drafting bot (`RESEARCH_MODE=drafting`) as a fourth bot type alongside
the existing legislation, parliament (Holyrood) and westminster bots.

---

## Context

The customer (a UK government organisation; users are qualified Scottish Government lawyers)
has asked whether AILA could be turned into a **legislation drafting** tool.

Two bodies of drafting guidance are in play:
- **"Drafting Matters!"** (Scottish Government PCO, 2nd edition Dec 2018) — public, on gov.scot
  as HTML pages plus a PDF. Part 1 covers drafting technique (plain language, punctuation,
  gender neutrality, citation, cross-references, definitions, numbering); Part 2 covers specific
  topics (arbitration, criminal law/offences/penalties, Crown application, statutory bodies,
  public offices, commencement, subordinate-legislation powers, textual amendments, repeals).
- **Internal PCO drafting guidance** — classified **OFFICIAL-SENSITIVE**, not currently available
  to us. This is the single biggest open variable in the whole assessment.

---

## Verdict (summary)

**Feasible, and the platform is unusually well-suited to it — but only for a bounded scope.**

*"Drafting tool"* is three quite different products, with very different risk and difficulty
profiles. Ranked by feasibility on this platform:

| Scope | Difficulty | Value | Verdict |
|---|---|---|---|
| **A. Drafting-guidance Q&A + precedent finder** ("how do we usually word a commencement provision?", "show me recent ASPs that create a summary-only offence") | Low — this is AILA's existing shape | High, immediately | **Do this first** |
| **B. Draft *reviewer* / conventions checker** (paste a clause, get flagged deviations from Drafting Matters + internal guidance, with citations to the rule) | Medium | High — and it is the *safest* AI role in drafting | **Do this second** |
| **C. Draft *generator*** (produce clauses/schedules from policy instructions) | High | Contested — see Risks | **Pilot narrowly, or not at all** |

The strategic argument for B over C is set out under *Risks*, and it matches what every
comparable government programme has actually shipped (Appendix A).

---

## Agreed scope

- **Product:** (A) drafting-guidance Q&A + precedent finder, **and** (B) draft reviewer /
  conventions checker. **Not** a draft generator.
- **Sensitive guidance:** build against the public *Drafting Matters!* only; design the corpus
  so the internal OFFICIAL-SENSITIVE guidance drops in as a second source later.
- **Packaging:** a fourth bot, `RESEARCH_MODE=drafting`, own process + own Postgres DB.
- **Output:** a structured review report rendered in-chat (rule breached → location in draft →
  suggested fix), not a downloadable file.

---

## Codebase reuse assessment

### Already built, reusable as-is (this is the good news)

| Capability | Where | Note for drafting |
|---|---|---|
| **Document upload + text extraction** | `routers/documents.py` — PDF via `pdfplumber`, DOCX via `python-docx`, TXT/MD | A drafter can already paste *or upload* a draft clause / instructions. `python-docx` is already a dependency and **can write as well as read**. |
| Uploaded-doc injection into the agent | `_load_doc_context()` `routers/ai.py:298`, → `_doc_context` → manager prompt `agent_core.py:487` | Docs reach the **Manager only**; the Worker never sees them. Relevant if checking must happen worker-side. |
| **Code-orchestrated multi-step loop** | `run_deep_research` `agent_core.py:698-816` | Plain Python `for` over approved steps, one isolated worker each, then a tool-free synthesis call. Directly the shape of draft → check → revise. |
| **Check-output-then-corrective-retry** | `_report_needs_reformat` `agent_core.py:89-110` + `_reformat_worker_report` :113, loop at :238-252 | Already exactly "validate against a rule, issue one corrective pass". Capped at one iteration today. |
| Constrained tool-free LLM step | `planner_tool_executor` :400, `_no_tools_executor` :794 | The idiom for a deterministic, non-research model call. |
| **Plan-first UX** | `POST /api/research/plan` + editable plan card | An *approved drafting plan* artefact is arguably more valuable to PCO than an approved research plan. |
| **Federation** | `routers/federation.py`, `agent/federation_client.py` | Fully generic. A drafting bot can consult the legislation and Holyrood bots with **zero code change** — precedent lookup and *Pepper v Hart* purpose evidence come free. |
| Per-bot packaging | `bots/<id>/{bot_config.json,.env,assets}`, `shared/scripts/new_bot.ps1` | One bot = one process + one Postgres DB. Isolation is already the norm — see Risks. |
| Feature flags, audit trail, caching, efficiency metrics, auth | as existing | All inherited. |

### Extension points a new `RESEARCH_MODE=drafting` must touch

Every dispatch is a dict-lookup-with-default or if/elif with a **legislation fallback** — so
adding a mode never breaks the others, but *a missed key silently inherits legislation behaviour*.
Backend keys to add: `EFFICIENCY_PROFILES` (`config.py:149`), `get_worker_tools`
(`tools/schemas.py:638`), `get_worker_system_prompt` (`prompts.py:546`),
`get_manager_system_prompt` (`prompts.py:631` — note the **early-return** structure),
`_filter_constraint_block_for_mode` (`prompts.py:527`), `_REPORT_SECTIONS`
(`agent_core.py:51`), `_PLANNER_MODE_NOTES` (`prompts.py:967`).
A new tool set additionally touches ~9 places, of which the easy-to-forget ones are
`utils/stopwatch.py:3-28` (unlisted tools break the efficiency metrics),
`agent_shared.py:53-110` `_extract_sources_inner` (the References panel), and
`services/local_prompt_cache.py:53-62` `CACHEABLE_TOOLS`.

Frontend is ~90% generic — bot-awareness enters only at `useBotIdentity.js:27` and the
`isParliament` boolean prop-drilled from `App.jsx:306`. The filter selectors in
`constants/research.js:64-80` and `useFilters.js:112-135` are **two-way ternaries that would
fall through to Holyrood**; a drafting bot needing no research filters is the easiest case yet
(add `isDrafting`, hide the filter modal).

### Genuine gaps — the actual build cost

1. **No guidance corpus.** `MAX_DOC_CHARS_PER_FILE = 50_000` / `MAX_TOTAL_DOC_CHARS = 80_000`
   (`config.py:5-7`) — *Drafting Matters!* is far larger than the whole per-session budget, so
   "just upload the guidance" does not work. It needs to be an indexed corpus with a retrieval
   tool, i.e. the same pattern as `sp_plenary_items` / `sp_committee_items`.
2. **No conditional revise loop.** The DR loop is fixed-length; A4 is one-shot. Draft→check→
   revise-while-failing is a new control-flow shape, built from existing primitives.
3. **No document artifact output.** No `.docx`/`.pdf` generation, no download endpoint, no
   redline/diff. `exportChat.js` is clipboard rich-text only.
4. **No structural (XML) representation of legislation** — see Risks.

---

## Risks

### Blocking for OFFICIAL-SENSITIVE — must be resolved before the internal guidance lands

These are **existing platform gaps**, not new ones, but a drafting bot makes them acute because
the input is now *pre-publication legislative text*.

1. **`local_prompt_cache.query_text` stores the raw query in plaintext in a cross-user table.**
   `database.py:243`. In standard research mode the cache key query is deliberately the **raw
   user question** (`_cache_key_query`) — for a review bot that question *is the draft clause*.
   `CACHEABLE_TOOLS` (`services/local_prompt_cache.py:51-63`) governs which *tools* may be
   cached, but `search_legislation` is already on that allowlist, so precedent lookups during a
   review would write draft text into a table every user can read.
   **Fix: disable `local_prompt_cache_enabled` for the drafting bot outright** — and note the
   cache is near-worthless there anyway, since every draft is unique so the hit rate collapses.
   Separately, **do not add `search_drafting_guidance` to `CACHEABLE_TOOLS`.** That is a
   one-line change in a frozenset that looks like a free performance win and is the single most
   likely way to introduce a real security defect here.
2. **No SSO.** Local username + bcrypt only (`routers/auth.py:81`); no SAML/OIDC/Entra. Likely a
   blocker on its own for SG. Mitigating: there is **no self-registration** — users are
   admin-created only (`routers/users.py:73-76`), so the user set is closed.
3. **`secure=False` on the auth cookie**, with a `# Set to True in production` comment
   (`auth.py:104`). The target runs HTTPS on 443, so this is a one-line fix and should be done
   regardless of this project.
4. **No redaction; queries and emails hit disk for 14 days.** `executor.py:123` logs full query
   text, `auth.py:174` logs plaintext email, retention `backupCount=14` (`utils/logger.py:86`).
   Already specced but unbuilt — `docs/LOGGING_IMPROVEMENTS_PLAN.md:118-153` proposes
   `utils/redact.py`. Draft clauses in logs is a worse story than search queries in logs.
5. **No per-corpus access control.** Two flat roles, `"user"` / `"admin"`
   (`dependencies.py:71-72`). Every authenticated user reaches everything in the corpus. If the
   internal guidance has a narrower readership than the bot's user list, that needs building.
6. **Messages are plaintext, FTS-indexed, and have no retention policy.** `models.py:70-98`;
   deletion is manual/cascade only. Draft legislative text would persist indefinitely.
7. **`httpx.AsyncClient(verify=False)`** on all worker outbound calls (`executor.py:129`) —
   deliberate, for SSL inspection, but an SG security review will ask.

### Product risks

- **FTS is lexical; drafting questions are conceptual.** "must vs shall", "when do I need a
  Crown application provision" are exactly the queries `plainto_tsquery` handles worst. The
  `_or_tsquery` zero-result fallback (`parliament.py:376-390`) and prompt-level query-wording
  rules help, but the **pgvector NO-GO was measured against a transcript corpus, not a guidance
  corpus — that decision must be re-measured, not inherited.**
- **Chunking is the make-or-break design decision.** The codebase has already been bitten by
  exactly this: the old committee parser returned the whole meeting as one blob, which ruined
  FTS quality until fixed. A whole-chapter row ranks poorly and returns a useless 300-char
  excerpt. NZ PCO's headline finding says the same thing from the generation side — target
  small pieces of text, not whole documents.
- **LEX is an experimental service.** i.AI publish it as "not for production dependency",
  60 req/min & 1000 req/hour **per IP** — and every user of the deployment shares one IP.
  A review pass that fires several precedent lookups per clause multiplies request volume
  against that ceiling. `_request_with_retry` (`executor.py:68-108`) absorbs 429s but cannot
  create headroom.
- **No structural representation of legislation.** LEX returns JSON text only; there is no
  CLML/Akoma Ntoso path for legislation (case law *does* have one — `get_case_law_text` parses
  `/data.xml`). So checks that need structure (cross-reference integrity, numbering, amendment
  target resolution) are doing string work on prose. Getting CLML means calling
  `legislation.gov.uk/.../data.xml` directly — a **new whitelist entry** on the restricted target.
- **Nobody has shipped scope C.** Every comparable programme — i.AI/Lex, NZ PCO, Italy, Chile —
  stopped at search, checking, notes and analysis. That is corroboration for the agreed scope,
  and it is the answer to give the customer if they push toward generation.

### Not a risk

Drafting Matters! is public, Crown-copyright gov.scot material; indexing it is unproblematic.

---

## Proposed phasing

### Phase 0 — Security prerequisites (do first, small)
- Set `secure=True` on the auth cookie (`auth.py:104`).
- Add `drafting_mode_enabled` to `_DEFAULT_FEATURES` (`routers/developer.py:246-260`),
  `FeaturesUpdate`, the save dict, and `build_request_config` (`agent_request.py:151-154`) —
  the pattern is a ~5-line change; note the `.get(key, True)` convention means an absent key
  reads as enabled.
- **Turn `local_prompt_cache_enabled` off for this bot** and record why in `CLAUDE.md`.
- Implement `utils/redact.py` per `docs/LOGGING_IMPROVEMENTS_PLAN.md:118-153` and apply it at
  `executor.py:123` and `auth.py:174`.

### Phase 1 — Bot scaffolding
Mirror the Westminster bot, which is the proven template for adding a mode end to end.
- `bots/drafting/{bot_config.json, .env, assets/logo.svg}`; `RESEARCH_MODE=drafting` goes in the
  **`.env`** — note `agent.research_mode` in `bot_config.json` is decorative, nothing reads it.
  Own DB (`lexchat_drafting`).
- Add the `"drafting"` key at each dispatch: `EFFICIENCY_PROFILES` (`config.py:149`),
  `get_worker_tools` (`tools/schemas.py:638`), `get_worker_system_prompt` (`prompts.py:546`),
  `get_manager_system_prompt` (`prompts.py:631` — **new branch must append `consulted_suffix`**;
  the early-return structure is a documented trap), `_filter_constraint_block_for_mode`
  (`prompts.py:527`), `_REPORT_SECTIONS` (`agent_core.py:51`), `_PLANNER_MODE_NOTES`
  (`prompts.py:967`). A missed key silently inherits legislation behaviour.
- Frontend: add an `isDrafting` flag alongside `isParliament` (`App.jsx:306`) and hide the
  research-filter modal. Watch `constants/research.js:64-80` and `useFilters.js:112-135` —
  two-way ternaries that currently **fall through to Holyrood** for any third mode.
- Register as a federation peer of the legislation bot so `consult_peer` covers "what does s.7
  of the 1981 Act actually say" without duplicating LEX tooling. Zero code change.

### Phase 2 — Guidance corpus (the real new build)
- New model `DraftingGuidance` following `SpPlenaryItem` (`models.py:364-384`):
  `source` (`drafting_matters` / `internal`), `part`, `chapter`, `rule_ref`, `heading`,
  `full_text`, `structured` (JSON), `url`, `version_date`, `sensitivity`,
  `UniqueConstraint(source, rule_ref)`.
- DDL by hand in `database.py` — **no Alembic in this repo**: `CREATE TABLE IF NOT EXISTS` plus
  `CREATE INDEX ... USING GIN (to_tsvector('english', coalesce(full_text,'')))` alongside the
  existing ones at `database.py:287-307`. The index expression must match the query expression
  byte-for-byte.
- Ingest: one-shot admin-triggered script, **not** a crawler — guidance is near-static, so none
  of `parliament_crawler.py`'s high-water-mark / trailing-delta / Cloudflare-524 machinery is
  needed. Reuse `_extract_text` from `routers/documents.py:34-66` (`pdfplumber` / `python-docx`)
  as a plain function, and the `INSERT ... ON CONFLICT ... DO NOTHING` idiom.
- **Chunk per numbered rule / paragraph**, not per chapter — see Risks.
- `sensitivity` column exists from day one so the internal guidance drops in without a migration.
- Tool `search_drafting_guidance`: copy `_search_plenary_db` (`parliament.py:393-498`) including
  the empty-table graceful note and the `_or_tsquery` zero-result fallback.
  **Excluded from `CACHEABLE_TOOLS`.**
- Wire the LEX endpoints that already exist but aren't tools — `/amendment/search` and the
  explanatory-note endpoints (`docs/api/LexAPISpec.md:90-99`). A `schemas.py` entry plus an
  `elif` in `execute_worker_tool`; high value for drafting, low cost.
- New tool names must also be added to `utils/stopwatch.py:3-28` (phase classification — omitted
  tools blank out the efficiency metrics) and `agent_shared.py:53-110` `_extract_sources_inner`
  (the References panel).

### Phase 3 — Scope A: guidance Q&A + precedent finder
Prompt work plus the Phase-2 tools; this is AILA's existing Manager→Worker shape. Ships first
and is independently useful.

### Phase 4 — Scope B: the reviewer
Code-orchestrated, modelled on `run_deep_research` (`agent_core.py:698-816`):
```
split draft into clauses (deterministic, in Python)
for each clause:
    retrieve applicable guidance rules  (search_drafting_guidance)
    retrieve comparable enacted precedent (search_legislation_sections)
    one constrained model call -> findings[]   # _no_tools_executor idiom, agent_core.py:794
collate -> structured review report
```
- Chunking per clause is the NZ PCO finding applied directly: accuracy was significantly better
  targeting small pieces than handing over a whole bill.
- Every finding must carry a **citation to the governing rule** — this is the transparency
  requirement Propylon identifies and the thing that makes the output checkable.
- The output schema is enforced the way report structure already is: `_REPORT_SECTIONS["drafting"]`
  + `_report_needs_reformat` (`agent_core.py:89-110`) + the one-shot `_reformat_worker_report`
  corrective retry — reuse, don't reinvent.
- Findings render as a structured list in-chat; existing clipboard rich-text export
  (`exportChat.js`) already pastes into Word with formatting intact.

### Phase 5 — Evaluation
- Write `docs/evals/GOLDEN_QUESTIONS_DRAFTING.md` on the existing template
  (`docs/evals/GOLDEN_QUESTIONS_LEGISLATION.md`): ID, category, confidence, draft answer,
  required citations; A/B/C/D rubric; report **% A-or-B with % D separate**.
- Keep the **`trap` category** ("correct answer is: no such rule exists") — it matters *more*
  here, because a plausible-but-invented drafting convention is worse than no answer.
- Questions must be verified by a qualified drafter, as the existing sets state.
- Eval plumbing is inherited free: `/api/system/chat` with structural parity enforced by
  `SystemChatRequest` subclassing `ChatRequest`, plus the `audit` SSE event carrying
  `raw_result` alongside `final_result` (`docs/api/AUDIT_TRACE.md`). The runnable harness lives
  in the external `lexchat-eval` repo.
- **Re-measure the pgvector question against the guidance corpus** before accepting FTS-only.

---

## Branch and multi-session working

### Branch

**`feature/drafting-bot`**, long-lived, merged to `main` at the end.

This is a **deliberate exception** to the repo's standing rule — `CLAUDE.md` ("Active Branch")
says to commit straight to `main` because the target pulls from `origin/main`. That rule stands
for everything else; this project is scoped out of it by explicit instruction. Two consequences:

- **Nothing on this branch reaches the target until merge.** That is the point — an unfinished
  drafting bot must not be `git pull`-able onto a production server.
- The "Active Branch" section of `CLAUDE.md` records the exception and its scope, so a future
  session doesn't "helpfully" rebase onto `main`.

**One carve-out:** Phase 0 is security fixes (`secure=True` cookie, log redaction) that are
correct regardless of whether the drafting bot ever ships, and that the live deployment wants
now. Phase 0 goes to `main` as its own commit first; everything else stays on the branch.

`client/dist/` is gitignored and must be force-added (`git add -f client/dist/`) on any commit
that touches `client/src/` — but only the merge commit matters to the target.

### The actual problem with multi-session work

Context does not survive between sessions. Everything a future session needs must be **in the
repo**, not in a chat transcript and not in `~/.claude/plans/` (which is outside the repo, is
per-machine, and does not travel with the branch). Hence this file and `SESSION_LOG.md`.

---

## Session ledger

Tick a row only when its tests are green AND the work is committed.

- [x] **S0 — Security prereqs** *(on `main`, before branching)*
      `secure=True` (auth.py:104) · `utils/redact.py` per LOGGING_IMPROVEMENTS_PLAN.md:118-153,
      applied at executor.py:123 + auth.py:174 · `drafting_mode_enabled` flag (5 sites) ·
      `local_prompt_cache_enabled` OFF for the drafting bot + reason recorded in CLAUDE.md
- [ ] **S1 — Bot scaffolding**  bots/drafting/{bot_config.json,.env,assets} ·
      7 dispatch keys (config.py:149, schemas.py:638, prompts.py:546/631/527/967, agent_core.py:51) ·
      `isDrafting` in App.jsx:306 + hide filter modal
- [ ] **S2 — Corpus schema + ingest**  `DraftingGuidance` model · DDL in database.py ·
      GIN index · one-shot ingest of Drafting Matters!, chunked per numbered rule
- [ ] **S3 — Retrieval tools**  `search_drafting_guidance` + `_or_tsquery` fallback ·
      wire LEX /amendment/search + explanatory-note endpoints ·
      stopwatch.py:3-28 + `_extract_sources_inner` registration
- [ ] **S4 — Scope A prompts**  `_DRAFTING_BODY`/`_CHIPS`/worker prompt ·
      `_REPORT_SECTIONS["drafting"]` · consulted_suffix on the new branch
- [ ] **S5 — Reviewer backend**  per-clause code-orchestrated loop in agent_core.py
- [ ] **S6 — Reviewer frontend**  structured findings render · rebuild + `git add -f client/dist/`
- [ ] **S7 — Evaluation**  GOLDEN_QUESTIONS_DRAFTING.md · pgvector re-measurement · go/no-go recorded

Sessions 2 and 3 are the ones most likely to overrun — if session 2 is running long, stop after
the schema + DDL and leave ingest for its own session. Do not carry an un-green test suite
across a session boundary.

---

## S0 as built

Landed on `main`. Suite green, 326 → 350 tests (24 added, `tests/test_drafting_security.py`).
Four things a later session should know:

**1. `local_prompt_cache_enabled` is forced off in code for `research_mode == "drafting"`, not
left as an operator setting.** The flag defaults ON and lives in a per-bot `AppSetting` row, so
"turn it off on that bot" via the Admin Portal is an operator memory, not a control — and the
failure mode is draft legislative text in a cross-user plaintext table. The override lives in
`build_request_config` (`routers/agent_request.py`), the single seam `/api/chat`,
`/api/system/chat` and `/api/research/plan` all pass through, and ANDs with the admin flag so
no other mode changes.
**Consequence: on a drafting bot the Cache tab will show "Local cache" as ON. That is correct
— do not "fix" it.** The flag genuinely is on; the request-level override is what takes it off.

**2. Redaction was applied at the two sites the ledger names. Two more are still open.**
`utils/redact.py` is applied at `agent/tools/executor.py` (worker tool args) and
`routers/auth.py` (password-reset email). Still logging free text at INFO:
- `agent/agent_core.py:176` — `[Worker] Starting research on: {query}`, the Manager's
  delegation brief. **In a review flow that brief can quote the draft.**
- `routers/learning.py:145` — `[Learning] Test retrieval for query {body.query!r}`, admin-only.

Neither is in the S0 row, so neither was touched. **Both must be closed before the bot is given
real pre-publication drafts** — a one-line `redact_text(...)` each. Do not assume S0 finished
the job. Also open, and flagged in `CLAUDE.md`: full text still appears at `LOG_LEVEL=DEBUG` by
design, which is a decision the deploying org should confirm.

`redact_args()` (a third helper, beyond the two `LOGGING_IMPROVEMENTS_PLAN.md` specs) is
**allowlist-based and fails safe** — `SAFE_ARG_KEYS` logs in the clear, every other string value
is redacted. A tool added later with a new free-text parameter loses log fidelity, not
confidentiality. When S3 adds `search_drafting_guidance`, its structural args can be added to
`SAFE_ARG_KEYS`; its `query` must not be.

**3. `secure=True` means the cookie is not set over plain HTTP, including local dev on :8000.**
This is fine because the frontend authenticates with the bearer token from the login response
body and `get_current_user` falls back to the `Authorization` header — but if a future session
sees cookie auth failing locally, this is why, and the fix is not to revert the flag.

**4. The `drafting_mode_enabled` flag has no Admin Portal toggle row yet.** Backend only
(`_DEFAULT_FEATURES`, `FeaturesUpdate`, the save dict, `build_request_config`). This is *not* a
silent-reset trap: `AdminPortal.jsx` loads the server's full flag dict into state and posts it
back, so the flag round-trips correctly through any other toggle. Adding the UI row belongs
with S1/S6, when there is a mode to toggle.

---

## Session protocol

**Start of every session:** read this file, then `SESSION_LOG.md`; confirm the branch; run the
test suite to establish a known-green baseline; pick the first unticked ledger row.

**End of every session:** tests green → commit (do **not** push to `main`) → tick the ledger row
→ append an entry to `SESSION_LOG.md` recording anything surprising, any deviation from this
plan, and the single next action. That closing note is what makes a cold start cheap.

**Never** leave uncommitted work across a boundary: `server_py/tests/conftest.py` drops and
recreates tables, so a half-finished DDL change plus a test run is a bad combination. The suite
also requires a dedicated `_test` database and refuses to run against unmarked data.

---

## Verification

1. **Corpus** — after ingest, assert row count and mean `full_text` length (catch the
   whole-document-blob failure); spot-check that a known rule is retrievable by its concept
   rather than its exact heading. Confirm the GIN index is actually used (`EXPLAIN`), since the
   expression must match byte-for-byte.
2. **Dispatch completeness** — start the bot with `RESEARCH_MODE=drafting` and assert the
   manager/worker/planner prompts, tool set, `_REPORT_SECTIONS` and efficiency profile all
   resolve to drafting, not the legislation fallback. Extend the parametrised dispatch test in
   `tests/test_suggestions.py`, which already covers every branch.
3. **Security** — assert `search_drafting_guidance ∉ CACHEABLE_TOOLS`; run a review with a
   distinctive marker string in the draft and confirm it appears **nowhere** in
   `local_prompt_cache.query_text` or the log files.
4. **Reviewer accuracy** — run the golden set; report % A-or-B and % D separately.
   Include drafts with deliberately planted, known deviations and measure the catch rate.
5. **Rate limits** — measure LEX calls per review at realistic clause counts against the
   1000/hour per-IP ceiling.
6. **Federation** — confirm a drafting-bot question about a specific provision routes via
   `consult_peer` to the legislation bot and comes back cited.
7. Existing suite stays green (`server_py/tests/`; 326 tests at the S0 baseline).

---

## Appendix A — Comparable tools and the features they use

Customer-facing rationale, not build instruction. Kept here because it is the evidence base for
the agreed scope (A and B, not C).

### The most directly relevant precedent: **i.AI's "Lex"** — *which AILA already runs on*

`server_py/src/config.py:76` sets `lex_api_url = "https://lex.lab.i.ai.gov.uk/"`. The "LEX API"
this codebase depends on **is** the UK Government Incubator for AI's Lex service — built with
MoJ, GLD and The National Archives, and explicitly developed *for legislative drafters*, with
user research run with the **Office of the Parliamentary Counsel**.

That matters enormously for the customer conversation: the drafting use case is not a
speculative pivot, it is the use case Lex was built for, and AILA is already a client of it.

Lex's published shape:
- Corpus: ~219,655 Acts and SIs (1267–present, complete from 1963), ~69,910 judgments,
  ~892,210 **legislative amendments**, ~83,350 **explanatory notes**.
- Features: semantic search over legislative materials (open embedding models trained for
  UK legal language), and **AI-assisted generation of explanatory notes on government bills**.
- OPC user research asked for *exact-phrase* and *proximity* search — i.e. drafters want
  precedent-hunting precision, not chat.
- Caveat: hosted as an **experimental service, explicitly "not for production dependency"**,
  rate-limited 60 req/min, 1000 req/hour per IP. (This is already a live risk for AILA
  generally, and becomes sharper if drafting workloads are added.)

### New Zealand PCO — the best-evaluated analogue

A six-month R&D programme with five proof-of-concepts; **Use Case C** was AI-assisted
clause-by-clause **explanatory note** generation. Reported findings:
- **Chunk small.** Accuracy was significantly better targeting *small pieces* of text than
  handing the model a whole bill and asking for clause-by-clause output.
- **Generate-and-regenerate UI.** The value came from a guided interface where the drafter
  can regenerate and judge whether a draft is a useful *starting point* — the drafter's
  judgement is the product, not the model's output.
- Model-size trade-off flagged explicitly: bigger models are better but costlier and their
  errors are **harder to spot**.

### Italy — Chamber of Deputies / Senate

- **GENAI4LEX-B**: summarises committee amendments and **checks bills against drafting
  standards** — i.e. exactly scope B above, in production-ish use in a legislature.
- Senate: clusters similar amendments, flags probable filibustering.

### Chile — Chamber of Deputies

A bill-drafting assistant composed of **multiple co-operating AI assistants**, covering quorum
rating, admissibility, related norms and regulatory-impact analysis. Notable as a
multi-agent design, which is the architecture AILA already has.

### Estonia — the cautionary-and-encouraging case

A member of the public's AI tool spotted errors in casino tax legislation that human drafters
missed; the defect had been costing roughly **€2m/month** in lost revenue. The PM then
publicly recommended AI checking of bills. This is the single strongest argument for
scope B: **AI as a second pair of eyes has a demonstrated hit rate on real defects.**

### Commercial / structural: Xcential **LegisPro**, Propylon

- LegisPro drafts and amends in **Akoma Ntoso / LegalDocML / USLM** semantic XML — patented
  change sets, drag-and-drop citations, automated amending language, line numbering.
- The argued AI angle: semantic XML gives a model "a contextual map of the document's
  structure, components and relationships" — structure beats prose for machine reasoning.
- Propylon's two-part practitioner piece frames five requirements: **security, accuracy
  (noting "there is no known robust solution to the hallucination problem"), interpretation
  and context, transparency/explainability with verifiable source citations, and legal/ethical
  compliance** — and argues for **"augmented intelligence"**, never autonomous drafting.

### Relevant open data

legislation.gov.uk exposes structured law directly: append `/data.xml` for **CLML**
(richest semantics, TNA-maintained) or `/data.akn` for **Akoma Ntoso**; bulk downloads exist
in XHTML, CLML, AKN, HTML5-AKN, PDF and plaintext. This is the route to *structure-aware*
precedent search that Lex's text-oriented API does not give us.

### Feature set that recurs across all of the above

1. Precedent / precision search over enacted law (exact phrase, proximity, structural filters).
2. Retrieval-grounded answers with **clickable citations to the governing rule**.
3. Conventions/standards checking of a supplied draft.
4. Explanatory-note and summary generation from clause text.
5. Consistency + conflict checking against the existing statute book.
6. Amendment handling (textual amendment language, change sets).
7. Structured XML as the working representation, not free prose.
8. Human-in-the-loop everywhere: generate → drafter judges → regenerate.
