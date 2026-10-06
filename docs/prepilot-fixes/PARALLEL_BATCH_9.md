# Parallel batch 9: P3.27/P3.12's re-run, P3.22, P3.21 and P3.4 built, P3.6 built

**Set up on 2026-10-06, at the end of Session 40, for Session 41, at the user's request** ("provide a
prompt to kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-8
(`PARALLEL_BATCH_1.md` to `_8.md`): agents in git worktrees, the main session integrating, nothing
merged that the integrator has not re-checked. **Every agent is $0 in model spend.** Two agents may
make free, bounded live calls (B to the National Archives, C to LEX) **only if the user agrees at
launch**. The paid steps are **two replay sweeps, run by the integrator alone between merges, each
priced to the user first from agent E's table and run only on the user's go-ahead** (and an optional
third, P3.4's after-column, priced the same way). Nothing is authorised yet.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent**, **Lessons from batches 1-8** and **Shared setup**, verbatim. Nothing here
should need re-deriving; if something does, the agent says so in its note rather than guessing.
Matter-specific detail (lawyers' wording, case names, rubric patterns, hand-reads, ground-truth text,
live payloads) is NOT in this file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first) **unless a dependency means it
   can't be**. FIX_PLAN's top order line ("as at 2026-10-06, end of Session 40", amended to point at
   this brief) is the order.
2. **P3.27 and P3.12 (built, `[~]`):** both wordings approved; the unlabelled "the Schedule"
   extension approved; A2's two fixes approved and merged (a space-separated paragraph run read whole,
   ascending only; P3.1's cap states what a complete code-read provision list holds); **the re-run is
   6335 n=3, `p37r_6374` n=1 and full 6374 n=1, priced to the user first**; before it, **one small
   commit that reserves P3.12's per-run slot before the fetch's `await`** (A2's finding: a batched
   round made 6 reads against a bound of 5 and can fetch one instrument twice). No Manager-facing limb
   for P3.27 unless the re-run shows answers still turning "not included" into "unable to retrieve".
   P3.27's whole-text "none held" line is **not** yet treated as established by the cap (measure in
   the re-run). The audit records the new calls by size, not body. In `schedules`, a silent 6374 turn
   reports SILENT; `depth` on 6335 t7 needs each paragraph cited with its facts.
3. **P3.25 is ticked** (6340's criterion amended to suppression). Do not re-open.
4. **P3.22 (P2):** relevance ordering, `order=relevance` with `per_page=50`, one test pinning both;
   the window note's three order statements flipped in the same commit, without the word "ranked",
   re-screened; the Phase-2 nudge's "most relevant" left as it is (it becomes true). **The before-column
   is 6363 and 6359, n=3 each, recorded modes, at a head WITHOUT P3.22**, graded on batch 8 C's rubric
   (adopted as the bar; 6363's list also sent to a lawyer in the pack). The published spec was
   re-checked (`public_api.yml` v0.6.0: `order` enum `date`, `updated`, `transformation`; no
   `relevance`); say so in a code comment, and `check_order` guards it.
5. **P3.21 (P2):** the date from legislation.gov.uk's dated effects feed read through LEX's
   `GET /legislation/proxy`, with a check that no date precedes the commencing instrument's made date;
   **one affected-feed fetch per change-record call, memoised per request, at most 2 pages, an 8 s
   timeout, fail-soft** (the record returned as today, saying the date was not retrieved). Acceptance:
   the row's unit tests, **6409 n=3** (a date for both commencing instruments with its source and
   qualification) and **6411 n=3 on the negative branch only** (no commencement date stated: neither
   source has one). Self-commencing Acts are out (a follow-up). P5.4 (c) needs no new row.
6. **P3.29 (P3)** is booked (appellate detector false positives); not in this batch.
7. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack** (now five questions, ready, not sent).
8. **Agents propose; the integrator applies; the user approves anything not mechanical**, including
   any wording a lawyer will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md,
   CLAUDE.md, `summary-table.html`, `docs/TODO.md`, `docs/LEGAL_DATA_SOURCES.md`, a rubric, the
   lawyer pack or a memory file.
9. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks.
   Branch pushes are allowed; if the permission classifier refuses one, ask the user (it refused once
   in Session 40 and the user approved).
10. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-06, end of Session 40)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit. **`main`** at `a6b4a76`,
  release **`v2026.09.3`**.
- **Tests: 2482** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **54 of 78 rows, 2 in progress (P3.27, P3.12)**,
  **8 of 14 buckets**; **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings). Run both after
  every fold.
- **Fix Tracker v40** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`; v40, at the user's request, shows the date and time of the
  update in its header from an `AS_AT` constant and sorts unfinished rows first, P1 at the top).
- **What Session 40 built** (notes `docs/prepilot-fixes/notes/batch8_{A,A2,B,C,D}.md`, committed):
  - **P3.27:** `executor.py`'s `get_legislation_text` branch sends `include_schedules: true` and makes
    the unflagged call; `utils/schedule_units.py` `mark_schedule_boundary`, `schedules_note`.
  - **P3.12:** `agent_shared.schedule_route_block` (called from `run_worker_tool` after a
    `search_legislation_sections` result), `executor.fetch_provision_list` (`/legislation/section/lookup`,
    `limit` 5000), `executor.fetch_text_with_schedules` (the fallback); in `schedule_units`:
    `named_units`, `unit_in_results`, `_paragraphs` / `_space_run`, `cut_annex` (moved from
    `tools/provision_hints.py`, which delegates), `cut_schedule_paragraph`, `cut_unit_from_text`,
    `fetched_block` and the line builders, `bare_schedule_action`, `provision_list_facts`; the per-run
    `provision_fetches` dict that `agent_core.run_worker_agent` creates (`MAX_ROUTED_LOOKUPS` 5).
  - **A2:** `discovery_budget.section_stop_message(..., held=)` / `_held_stop_fields` and the
    `section_budget` limb and footer in `search_scope.py` now state a complete code-read provision list.
  - **Tooling:** `replay_report schedules` (rubric `evidence/rubrics/p327.json`), `DEPTH_TRUTH["6335"]`
    (`DepthReq` gained `span` and `unless`), `CORPUS_LEAK_MARKERS`; script `evidence/scripts/p32c_6406.json`;
    `tools/caselaw_probe.check_order`; `tools/lgu_probe.py`.
- **The sweep `wave4_b8_sweep`** ($9.55): P3.12's 6335 t7 DELIVERED 0 of 3 (para 42 3 of 3; 43-44 lost
  to a whole-Schedule summary and to the parser); 6406's criterion (v) met 3 of 3; the 6374 guard FAIL
  4 of 4 (the code-stated negative lost to P3.1's cap note). Hand-read:
  `evidence/rubrics/handread_wave4_b8_sweep.md`.
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **59 replay directories** under `replay/`, every one on the pinned `google/gemini-3.1-pro-preview`;
    newest `wave4_b8_sweep` (16 files).
  - Rubrics `rubrics/p32.json` (sha1 `31379ecf…`), `p33.json` (`0031831b…`), `p327.json` (`5a14e273…`);
    hand-reads `handread_wave4_b7_p324.md`, `handread_wave4_b8_sweep.md`.
  - **Batch 8 scratch** `seam/batch8/{A,A2,B,B2,C,D,scratchpad_s40}/`:
    - **C (P3.22):** `rubric_p322_6363_6359.md` (the ground truth, gitignored: case names, the lawyers'
      words by turn, the proposed bar's four items), `live.jsonl` and the gzipped raw feeds (**both
      orderings for every stored tuple**: B's dry run uses them, no live call needed), `tna.py` (the
      capped, paced, logged National Archives caller), `census.py`, `analyze.py`, `rubric_check.py`,
      `presence.json`.
    - **D (P3.21):** `raw_lgu/` (248 legislation.gov.uk feeds: the affecting feed of all 157
      commencing instruments and the **affected feed of all 32 stored subjects plus 6411's Act**: C's
      dry run uses them), `raw_lex/`, `collect.py`, `census.py`, `dates.py`, `compare.py`, `cost.py`,
      `acceptance.py`, the call logs.
    - **A, A2:** the dry-run scripts (`dryrun_p327.py`, `trigger_p312.py`, `dryrun_p312.py`,
      `cut_check.py`; A2's `make_prev_tree.py`, `mutants.py`) — each asserts it imports a named tree:
      repoint a copy, never edit in place.
    - **B, B2:** `inventory.json`, `price.py` (stored rep costs per run), `depth_identity.py`,
      `screen.py`.
    - **Integrator (`scratchpad_s40`):** `review_branch.sh` (base parameter), `matter_grep.py`,
      `grade_b8.sh` (the exit-1 set + `negcurrency` without `--all` + `footer_echo`), `sweep_total.py`
      (**a sweep's running total: `--max-spend` is per command**), `summ_count2.py` (per-tool
      summarised counts), `route_trace.py` (what P3.12's route and P3.27's line did per turn),
      `dump_answers.py`, `text_calls.py`, `recitals.py`, `b8_mutA.py`/`b8_mutB.py`/`b8_mutA2.py`
      (CRLF-safe mutant runners), `fold_s40.py`, `docs_s40.py`, `preserve_s40.py`, `tracker_v39.py`.
  - Replay scripts in `evidence/scripts/` (tracked: base session and turn indices only).
  - The raw transcript export (lawyers' questions; never in the repo):
    `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist; **create `lexchat_test_e`** for agent E
  at step 1 (`CREATE DATABASE lexchat_test_e OWNER lexuser;` with psql), or give E `lexchat_test_d`
  after D finishes (do not share a database between two running agents).
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no registered
  worktrees. Local merged branches from batches 1-8 remain and can be deleted. Untracked leftovers
  `C:\Temp\b8_revA`, `b8_revA2`, `b8_revA3` (disposable; the user may delete them).

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.12** (P2; P3.27's re-run depends on it) | Reserve the per-run slot before the fetch's `await` | product, small, deterministic | $0, no external call | `server_py/src/agent/agent_shared.py` (`schedule_route_block`), tests |
| **B** | **P3.22** (P2) | The build: relevance ordering, the note flipped | product, deterministic build; replay by the integrator | $0; National Archives calls only if agreed (up to 20) | `server_py/src/agent/tools/executor.py` (`search_case_law` branch), `server_py/src/agent/tools/caselaw.py`, `server_py/src/utils/search_scope.py` (`CASE_LAW_RESULT_ORDER`, `case_law_search_note`), `tools/caselaw_probe.py` (`RELEVANCE_PARAMS` pointed at the product), tests |
| **C** | **P3.21** (P2) | The build: the commencement-date hop | product, deterministic build; replay by the integrator | $0; LEX calls only if agreed (up to 40) | `server_py/src/agent/tools/executor.py` (`get_legislation_changes` branch), `server_py/src/agent/tools/lex.py` (`_slim_amendment_results`), `server_py/src/utils/search_scope.py` (the date wording sites P3.21's row lists), a new product module for the feed parser (product code must not import `tools/lgu_probe.py`), tests |
| **D** | **P3.4** (P2), then **P3.6** (P2) | Two builds, two commits: the default-jurisdiction rule and extent notes; `description` kept truncated in search rows | product; P3.4's replay by the integrator, P3.6 deterministic | $0, no external call | `server_py/src/prompts.py` (P3.4), `server_py/src/agent/tools/lex.py` (`_slim_search_results`, P3.6), tests |
| **E** | the sweeps' instruments, and both sweeps priced | Graders for P3.22, P3.21 and P3.4; P3.4's scripts; the confound check; prices and commands | tooling and scripts, no product code | $0, no external call | `server_py/tools/replay_report.py`, `docs/prepilot-fixes/evidence/scripts/`, tests |

**Why these five.** By severity: no unblocked P1 row is left except P3.27's re-run, which waits on
A's commit. The P2 rows in the order line are P3.22, P3.21, P3.4, P3.6, P4.3, P3.10, P4.12 and P3.20
(last, waiting on SCTS). P3.22 and P3.21 are decided and build-ready; P3.4 has a booked acceptance and
needs a before-column taken at a head without it; P3.6's acceptance is deterministic, so it can merge
without a replay. E builds the graders the sweeps need and prices them, as batch 8 B did. **Not in this
batch:** P4.3 and P3.10 (each needs its acceptance re-booked first), P4.12 (measure-first), P3.20
(external), P3.29 and the other P3 rows, anything Blocked.

**Merge order: A, E, then sweep 1 (on the user's go-ahead), then B, C, then sweep 2 (on the user's
go-ahead), then D (and sweep 3, P3.4's after-column, only on the user's go-ahead; it may wait for
Session 42).**
- **Sweep 1** (head = Session 40's tree + A + E): P3.27/P3.12's re-run (6335 n=3; `p37r_6374` and
  6374 n=1); **P3.22's before-column** (6363, 6359 n=3); **P3.4's before-column** (6378 t1 and 6360 t1,
  n per Invariant 4, Conversational as recorded, E's scripts).
- **Sweep 2** (head + B + C): **P3.22's after-column** (6363, 6359 n=3) and **P3.21's after-column**
  (6409 and 6411 n=3, or the script forms E chooses). **Before it, E's confound check decides whether
  B and C can share one sweep:** if a stored 6363/6359 run calls `get_legislation_changes`, or a stored
  6409/6411 run calls `search_case_law`, run P3.22's after-column with B merged and C not, then merge C
  and run P3.21's (Invariant 3).
- **D last**, so P3.4's change is in neither sweep's after-column but its own; P3.6 is ticked at merge
  if its deterministic acceptance holds on the merged tree.
- Review B, C and D while a sweep runs, but **never commit while a replay is running**; merge after
  `replay restore`.

**Collision points.**
- **B and C both edit `executor.py` and `search_scope.py`** (different branches and functions) and
  both add to `tests/test_search_scope.py::test_footer_trips_no_detector`. Each keeps its own screen in
  its own test file where it can (batch 7 D's pattern) and adds to the shared test only what must be
  there; the integrator resolves the merge in order (B then C) and re-runs the suite.
- **C and D both edit `lex.py`** (`_slim_amendment_results` against `_slim_search_results`).
- **C's output shape is E's input:** C adds to each commencement `changes` entry made by another
  instrument an `"in_force": "YYYY-MM-DD"` (and `"qualification"` where the feed gives one), and to
  the result a `"commencement_dates"` status (`"retrieved"`, `"not_retrieved"` with a reason, or absent
  when no hop ran). **If C has to change this shape, C says so in its note first thing, and the
  integrator tells E** (or E reads C's note before finishing its grader).
- **D's prompt change reaches every conversational Manager and quick-lookup Worker:** a first-round
  effect on delegation briefs is possible (P3.13's lesson); D says what it changes, and the integrator
  merges D last.
- **No agent edits `tools/replay_report.py` except E.** A grader change any other agent needs goes in
  its note.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the top recommended-order line, the paragraph above the Ledger
   on what waits on the lawyer pack, and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`,
   everything from "Session 40 — 2026-10-06 — parallel batch 8" to the end of the file; and the
   batch 8 notes your brief names. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`,
   `docs/LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the lawyer pack or any memory
   file: the integrator folds your results in. Commit on your worktree's branch; **do not push, do
   not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch9_<A|B|C|D|E>.md` and commit it. Put in it:
   - what you changed or found, and why;
   - every number, with the exact command that produces it;
   - every match or edit you read (counts and locations only if the text names a matter);
   - what you did NOT do;
   - anything the integrator or the user must decide, each as a numbered, self-contained decision
     with 2-4 options, your recommendation first, each option one or two sentences.

   **Before any claim of "fixed", "met" or "consistent", state the check and whether it passes.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list every
   match and every drop before quoting a rate. For a product change, dry-run it over every stored
   input it reads with the BUILT code, and list every output that moves. **Say also which input forms
   no stored run contains**, and test them on synthetic input: a dry run cannot see a form no stored
   run used (Session 40: "paragraphs 42 43 44").
5. **Tests:** each code change gets a unit test at its seam. Each test is proven to FAIL with the
   change reverted on a scratch copy, **and the note says how many lines the revert removed** (a
   revert that removed nothing proves nothing). Where a full revert only fails at import or on a
   missing key, also stub each new function or put each half of the old defect back one at a time
   (single-site mutants), so the tests are shown to check behaviour. **Write a mutant for every guard
   and every cleaning step** (bracket cleaning, uniqueness checks, completeness checks): in Session 40
   the integrator's mutants found two untested guards in agent A's build, and one hid a real defect.
   Run the full suite on your own test database before your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names, or
   instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget Order
   1901", `ssi/1901/3`, "Widget Co v Example Ltd"). Grep your staged diff for session ids,
   instrument ids and matter words before every commit (with Python: see the lessons). Rubric
   patterns, draws, hand-reads, live payloads, ground-truth text and anything quoting a matter stay
   in the gitignored evidence. (FIX_PLAN.md names sessions and instruments; your note need not repeat
   them: cite the row. The one standing exception is `DEPTH_TRUTH`, which holds public statutory
   ids and statutory words by the user's decision.)
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so Python
   edits over multi-line text must normalise CRLF to LF before matching and restore CRLF on write.
   **A byte-level edit or revert must assert its anchor occurs exactly once before writing** (an LF
   anchor matches nothing in a CRLF file; a `$`-anchored grep finds nothing on a CRLF line). **Never
   run Python with backslashes from a bash heredoc** (it mangles them): use the Edit tool, or write
   the script to a file first. Commit messages go in a file (`git commit -F`), ending with the
   attribution line the harness gives.
8. **Budget: $0 in model spend.** No model call of any kind: no seam draw, no live Worker, no
   summariser call, no paid API. **Live calls to an external host only if your brief says the user
   agreed at launch**, and then: paced (at least 0.5 s apart; the National Archives at least 0.35 s,
   under its published 1,000 requests per five minutes), under the cap your brief gives, every call
   logged (method, URL, status, bytes) to your gitignored scratch, the cap enforced in code (batch 7
   B's `lexcall.py` and batch 8 C's `tna.py` are the pattern), and counted in your note. **LEX's read
   endpoints are POST**, so "calls", not "GETs". Every other agent makes no external call at all.
   **If your run is interrupted and resumed, recount your call log first: the cap covers every call
   already made.**
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** your worktree's gitignored
    `docs/prepilot-fixes/evidence/seam/batch9/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch9/<your letter>/`. **Never write to
    the session scratchpad, not even briefly.** Say in your reply which you did, with the file count
    on both sides.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend (and the number of live calls, per host); the path of your note and where your scratch is;
    for each item, met or not and why; and the numbered decisions for the user.

## Lessons from batches 1-8 (give these verbatim with each brief)

- **Check your base before anything else.** In all eight batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are `git log --oneline -1` and
  `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`. If HEAD is not `<INTEGRATOR_HEAD>` and you
  have no commits, run `git reset --hard <INTEGRATOR_HEAD>`, and say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a single test file. Use plain
  `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown, so a run on the
  default database breaks the integrator's suite.
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth; a detector is judged by whether its verdicts match what a careful reader would say,
  never by its rate. Read every match and every drop.
- **A grader can be blind to a new data shape.** P3.19 changed the change record's groups to
  `changes`; `negcurrency` still read `changed_provisions` (batch 7 A caught it). In batch 8, B's
  `schedules` read A's code-stated true negatives as SILENT until B2 fixed it. **After any change to a
  tool result's shape or a new code-written sentence, check every grader and recorder that reads it.**
  `replay_report commencements` has never graded a scripted run (`p37_*`): read those by hand.
- **Know which agent reads a block before you write to it.** `worker_scope_block` (and
  `_currency_limb` in it) is appended to the Worker's report AFTER the Worker writes; only the
  Manager and the Deep Research synthesis read it. Text meant for the Worker belongs in the tool
  result (as P2.3's `enabling_power_note` and P3.27's `schedules_note` are).
- **Check every code text that speaks of the same instrument, not only the one you are building.**
  Session 40's sweep: P3.27's and P3.12's lines told the Worker, correctly, that the index holds no
  schedule for an instrument, on every step; P3.1's cap note for the same instrument said provisions
  "may still be in it", and every answer blamed the limit. A true code-stated fact loses to a
  contradicting one. List the other code texts your change sits beside, and say whether any
  contradicts it.
- **Any text the product writes into an answer, or into a block the model can echo, is read by every
  grader** (`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`,
  `derivation_claims`, `_currency_asserted`, `negcurrency_claim`, `OPENER_VOCAB`,
  `sched_clause_class`, the halt detectors, the footer strippers). Screen new wording against all of
  them (`test_footer_trips_no_detector`). A `[` or `]` inside a `[…]` block stops the strippers; the
  word "ranked" tripped `NEG_LIMITS` and `NEG_TERMS` before (the comment above
  `CASE_LAW_ABSENCE_SENTENCE`).
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree. **A script that globs every replay directory picks up new ones** (there are 59 now):
  exclude them, or say the counts include them.
- **Read a booked bar against the before-column in the same mode.** P3.25's 6340 bar was set from
  Research-mode runs but booked in Conversational mode, where the before-column never met it.
- **Check that a folder is really gitignored** (`git check-ignore -v <path>`) before you write matter
  text into it. **`docs/prepilot-fixes/evidence/` itself is NOT ignored**, only its listed subfolders
  (`seam/`, `replay/`, `rubrics/`, `lawyer_pack/` and others); `evidence/scripts/` is tracked.
- **The plan has been wrong before, and about external APIs too.** Re-probe a row's claim about a
  live service before building on it, and say which you checked. Read the API's spec before
  concluding what it cannot do, and check every parameter we send against it.
- **Thomas tests on a different model** (`glm-5.2:cloud`); every stored replay here ran on the
  pinned Gemini. Say which model a number comes from.
- **Tooling traps on this machine:** Git Bash's `grep -iF` aborts (exit 134), so a `$(grep -ciF ...)`
  prints blanks silently: use Python for case-insensitive fixed-string search. `git worktree remove`
  fails ("Permission denied") while the shell's cwd is inside the worktree. The harness's safety
  check blocks `rm` on a shell-variable path (write `"${S:?}"/...` or a literal path) and `rmdir`
  under a session working directory. `replay_report negcurrency --all` walks SUBdirectories: on a
  single replay directory, run it without `--all`. Windows Python cannot open a `/c/...` path: use
  `C:/...`.
- **A session's process can end mid-batch.** In Session 40 all four agents were cut off about an hour
  in and resumed from their transcripts in their worktrees. Commit as you go, and keep your scratch in
  your worktree until you copy it.
- **Another session may commit to the branch while you work.** Base your note on
  `<INTEGRATOR_HEAD>` and say so; the integrator reconciles.

---

## Shared setup

- **Worktrees:** `isolation: "worktree"`. A worktree has no `server_py/.env`, and that is fine.
- **In a worktree, set on every tool command:**
  - `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`;
  - `PYTHONIOENCODING=utf-8` (the console is cp1252);
  - `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_<a|b|c|d|e>`.

  Pass `--dir` and `--also` paths under `$PREPILOT_EVIDENCE/replay/`.
- **Commands** (run from `server_py/`):
  - `python -m tools.plan_status`; `python -m tools.plan_lint`;
  - `python -m tools.replay_report --dir <path> <subcommand>`. The subcommands include `negatives`,
    `caselaw`, `scoperecord`, `nosearch`, `halts`, `derivations`, `commencements`, `currency`,
    `negcurrency [--all --sessions S --drops --verbose]`, `modes`, `deadend`, `siblings`,
    `scripted`, `lookup`, `drgaps`, `blanks`, `lost --require-label`, `interpret`, `stance`,
    `hedges`, `openers`, `sectionscope`, `discovery`, `depth [--seams --answers --drops]`, `lostcost`,
    `schedules [--rubric --session --all-dirs --drops]`, `corpus`. **The exit-1 set** is 16: `halts
    negatives derivations commencements currency scoperecord nosearch caselaw modes deadend siblings
    scripted lookup drgaps blanks lost --require-label`.
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`;
    `python -m tools.lex_probe` (live LEX checks, if agreed); `python -m tools.lex_probe --caselaw`
    (live National Archives checks incl. `check_order`, if agreed); `python -m tools.lgu_probe
    --effects|--descriptions|--compare [--via lex]` (live, if agreed).
- **Run files:** `replay/<dir>/<session>_rep<n>.json`; each has `turns[]` with `turn`, `chat_mode`,
  `research_mode`, `answer` and `audit`, whose `delegations[]` carry `report` and `tools[]` (`name`,
  `args`, `raw_result`, `final_result`, `summarised`, `memo_hit`, `local_cache_hit`, `api_calls`, ...);
  the top level carries `total_cost_usd`; a scripted run carries `script` (`base`, `turns[].from_turn`).
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Node** (for a JS syntax check only): `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`.

---

## Agent A: P3.12's per-run slot, reserved before the `await` ($0, product, small)

**Read first:** P3.12's and P3.27's rows in full; `notes/batch8_A.md` sections 2.1-2.4 and
`notes/batch8_A2.md` ("Found on the way, not fixed"); `agent_shared.schedule_route_block` and how
`run_worker_tool` calls it; how `chat_loop` runs one round's tool calls (concurrently, as tasks);
`agent_core.run_worker_agent` (`provision_fetches`, `MAX_ROUTED_LOOKUPS`).

**The defect (A2, measured in `wave4_b8_sweep`, 6374 turn 4, Deep Research step 3):** the route
checks the per-run bound and the memo before its `await` and writes the result after it, so a round
in which the Worker sends several section searches lets every call pass the check: 6 provision-list
reads against a bound of 5, and one instrument can be fetched twice in a round. Only extra LEX calls;
no text came out wrong.

**Build:** reserve the instrument's slot (and count it against the bound) before the `await`, so
concurrent calls for the same instrument share one fetch (an in-flight future, or a lock per
instrument key `provision_fetch_key`) and the bound holds across a round; a failed fetch releases or
records its slot as A2's "fetch failed" case does today; fail-soft. Nothing a Worker reads may change
for a run whose calls are sequential. **Tests:** concurrent calls via `asyncio.gather` (the same
instrument twice: one fetch; six instruments with a bound of 5: five fetches and the sixth refused as
today), a failed fetch, the sequential case unchanged; each failing with the change reverted (lines
removed), plus single-site mutants. **Dry run** with the built code over every stored round that ran
more than one section search (count them; list every one whose fetch count changes), using batch 7
B's saved lookups through a mocked transport (A's `dryrun_p312.py` pattern, repointed in a copy).
**Say in your note** whether any output text moves (it should not).

## Agent B: P3.22 built ($0; National Archives calls only if agreed)

**Read first:** P3.22's row in full (its Session 40 decisions); `notes/batch8_C.md` whole; P3.23's
and P3.9's rows; `server_py/src/agent/tools/caselaw.py` (`case_law_count`, `case_law_date_window`,
`_parse_case_law_atom`, `detect_appellate_decisions`); the `search_case_law` branch of `executor.py`;
`search_scope.case_law_search_note`, `CASE_LAW_RESULT_ORDER` and the comment above
`CASE_LAW_ABSENCE_SENTENCE`; `agent_shared.py`'s Phase-2 nudge naming `results[:3]`;
`tools/caselaw_probe.py` (`check_order`, `RELEVANCE_PARAMS`); the `external-apis` skill's National
Archives section.

**Build (one commit, as decided):** `search_case_law` sends `order=relevance` **and** `per_page=50`
(a test pins both, and fails if either is dropped: the 10-row trap); a code comment says `relevance`
is the advanced search's sort and is not in the published spec (`public_api.yml` v0.6.0), guarded by
`check_order`; `RELEVANCE_PARAMS` in the probe points at the product's params. The window note's three
order statements flip in the same commit: `CASE_LAW_RESULT_ORDER` ("newest first, by date rather than
by relevance"), "the {n} most recent of about", and "An older judgment that matches can sit outside
these {n}"; new wording without "ranked", screened against every detector (`test_caselaw_window.py`'s
screen and `test_footer_trips_no_detector`), with no bracket inside a block. The nudge's "most
relevant" stays. `case_law_count` needs no change (the `last` link counts at ten a page under either
order: 52 of 52 in batch 8 C). **Dry run with the built code** over all 1,257 stored `search_case_law`
calls through a mocked transport serving **batch 8 C's saved live feeds under the relevance ordering**
(`seam/batch8/C/`), batch 7 D's `dryrun.py`/`compare.py` pattern repointed in a copy: list every call
whose params, JSON or notes move, and confirm nothing else moves; report how many first-three sets
change (C measured about seven tuples in ten). **Live calls, only if agreed, cap 20:** a smoke of
`check_order` and of the product's own request through `tna.py`'s pattern. **Say in your note** the
exact new wording of every note variant, for the integrator to put to the user before merge.

## Agent C: P3.21 built ($0; LEX calls only if agreed)

**Read first:** P3.21's row in full (its Session 40 decisions) and P5.4's; `notes/batch8_D.md` whole;
P2.5's, P3.5's, P3.19's and P3.24's rows; `notes/batch7_A.md` (the commencement split);
`server_py/src/agent/tools/lex.py` (`_slim_amendment_results`, `_COMMENCEMENT_OF_SUBJECT`); the
`get_legislation_changes` branch of `executor.py`; `search_scope.py`'s wording sites the row lists
(`amendment_search_note`, `_relations_limb`, `_relation_currency_limb`, `_currency_limb`,
`_relations_footer_clause`, `_currency_footer_clause`, P4.18's branch, P3.24's
`_commencement_lines`); `tools/lgu_probe.py` (the parser to re-implement in product code: product code
must not import a dev tool).

**Build:** after a `get_legislation_changes` result whose rows hold a commencement relation by
another instrument (P3.5's rule; P3.24's `self: false`), fetch the subject's legislation.gov.uk
**affected** effects feed once per change-record call, through LEX's `GET /legislation/proxy` (the
path and query string URL-encoded as `lgu_probe --via lex` does), memoised per request, at most 2
pages (1,000 relations), an 8 s timeout, fail-soft; match each commencement relation to its feed effect
(subject, changed provision, affecting instrument, affecting provision, scheme-free; batch 8 D's
`compare_commencements`) and add to each matched `changes` entry `"in_force": "YYYY-MM-DD"` and, where
the feed gives one, `"qualification"`; refuse any date earlier than the commencing instrument's made
date (state where the made date comes from, and test it; D found one feed error of exactly this kind);
add a result-level `"commencement_dates"` status (`"retrieved"`, `"not_retrieved"` with a reason, or
absent when no hop ran). **This shape is agent E's input: if you must change it, say so first thing in
your note.** The wording sites that say the record carries no dates change in the same commit, **gated
in code on the hop's result** (P3.20's pattern): unchanged where the hop did not run or found nothing,
and saying a date is the commencing instrument's stated in-force date (with its source and
qualification), never that the provision is in force now (P2.5; the repeal half stays). Screen every
new sentence against every detector. Self-commencing relations are out of scope (decided). **Dry run
with the built code** over every stored change-record call, the feed served from **batch 8 D's saved
affected feeds** (`seam/batch8/D/raw_lgu/`; say how many calls have no saved feed and count them):
list every output that moves, how many relations get a date, every date refused, and every wording
site that changes. **Live calls, only if agreed, cap 40:** a smoke through the proxy for two or three
subjects, logged. **Say in your note** the exact new wording of every variant, for the integrator to
put to the user before merge, and the added calls and latency per turn at the cap.

## Agent D: P3.4, then P3.6 (two builds, two commits; $0)

**Read first:** P3.4's and P3.6's rows in full; P3.14's row (the quick-lookup Worker is not told the
filters); P1.1's row; `prompts.py` (`_JURISDICTION_EXTENT_NOTES`, the four manager prompts and
`get_manager_system_prompt`'s dispatch, the quick-lookup Worker prompt); P3.13's lesson in FIX_PLAN's
Verification protocol (a prompt edit reaches every call that prompt drives, including the first
delegation brief); `lex.py` `_slim_search_results` and CLAUDE.md's note on why `description` was
stripped.

**Commit 1, P3.4 (acceptance booked: (a) deterministic, (b) replay).** The extent notes stop naming
letter codes and say that most rows carry no stated extent (Thomas's action 5, verified); a
default-jurisdiction rule reaches the conversational Manager **and** the quick-lookup Worker (the two
the acceptance sessions use): where a question names no jurisdiction, answer for Scotland and say so;
where it says "the UK", answer for all four and flag divergence rather than silently picking one. Keep
the research Workers' prompts byte-identical unless the row needs them (say which). Tests: (a) as
booked (no extent note names a letter code; each says most rows carry no stated extent), the rule
present in exactly the prompts it should be, each failing with the change reverted. Screen every new
sentence against every detector. **List every prompt the change reaches and every call it drives**
(the first delegation brief included); you cannot measure the first-round effect at $0, so say what
the integrator should read for. **Say in your note** the exact new wording, for the user.
**Commit 2, P3.6 (acceptance deterministic):** keep `description` in `search_legislation` rows,
truncated (the row: the sampled descriptions are 73-210 characters; choose and justify a cap from the
stored raw results), or only where it matches relationship language (choose, and say why);
unit tests as booked; **then the booked measurement**: Phase-1 summarisation calls unchanged over a
replay directory, computed with the built slimmer over every stored `search_legislation` raw result
(how many results cross the summarisation threshold before and after; list every one that moves).
Note that P3.21 (agent C) reads `description` through `lookup_legislation`, not search rows: no
overlap in code, but say whether the two would ever state a date for the same instrument.

## Agent E: the sweeps' instruments, and both sweeps priced ($0)

**Read first:** P3.22's, P3.21's, P3.4's, P3.27's and P3.12's rows in full (their booked
acceptances); `notes/batch8_B.md` (how `schedules` and `DEPTH_TRUTH` were built, and its pricing
method; `seam/batch8/B/price.py`); `notes/batch8_C.md` and the gitignored
`seam/batch8/C/rubric_p322_6363_6359.md` (the bar's four items); `notes/batch8_D.md` section 5;
`server_py/tools/replay_report.py`; `docs/prepilot-fixes/evidence/scripts/` and `tools/replay_set.py`.

**Build (tooling only, no product code):**
1. **P3.22's grader:** a `replay_report` subcommand (or an option on `caselaw`) that grades batch 8
   C's bar per run from a gitignored rubric you write to `seam/batch9/E/p322.json` (the integrator
   copies it to `evidence/rubrics/`): (1) each in-corpus authority retrieved (returned by a
   `search_case_law` call in the run) or not, and cited or not, counted per session across runs; (2)
   the rubric's leading Supreme Court judgment for 6363 retrieved in how many runs; (3) an answer naming
   an out-of-corpus authority does so second-hand or says the judgment is not in the database
   (Invariant 1); (4) the carrier judgment retrieved in every 6359 run reaching turns 6-7. Match
   authorities by neutral citation and by Find Case Law URL (merged), every match and drop printed.
   **Grade the stored 6363/6359 directories** (`baseline`, `wave1`, `wave2`) and hand-read each verdict;
   they predate P1.1 and the case-law build, so say what they can and cannot stand for.
2. **P3.21's grader:** a subcommand that lists every commencement date an answer states and grades it
   SUPPORTED (a retrieved feed date, description or text in the same conversation states it for that
   provision or instrument), UNSUPPORTED or UNCLEAR, every match and drop printed, reading agent C's
   shape (`changes[].in_force`, `qualification`, `commencement_dates`; see "Collision points") as well
   as today's; plus whether a commencement question got a date wherever one was retrieved, and, for
   6411, that no commencement date is stated. Register its claim regex in
   `test_footer_trips_no_detector` if any product footer could trip it. **Grade every stored 6409 and
   6411 directory** (the before-columns) and hand-read each verdict.
3. **P3.4's scripts and check:** scripts for 6378 turn 1 and 6360 turn 1 (`evidence/scripts/`, base
   session and turn indices only, Conversational and the recorded research type; confirm both from
   `replay_set`/`evidence/research_mode_reads.json`), and a check that the turn-1 answer names its
   jurisdiction explicitly (Scotland, or all four with divergence flagged where the question says "the
   UK"), patterns in a gitignored rubric, every match and drop printed. Grade the stored turn-1 answers
   of both sessions and hand-read each.
4. **The confound check for sweep 2:** does any stored 6363 or 6359 run call
   `get_legislation_changes`, and does any stored 6409 or 6411 run call `search_case_law`? Count per
   directory. If either, say that P3.22's and P3.21's after-columns must be separate sweeps.
5. **Both sweeps priced:** list every run (session or script, n, mode, what each grades), with the
   recorded cost of each stored rep in the recorded mode, a median and a maximum, and the exact `replay
   run` commands in order, **each with an explicit `--reps`** and a per-command `--max-spend`, for
   sweep 1 (P3.27/P3.12's re-run; P3.22's and P3.4's before-columns), sweep 2 (P3.22's and P3.21's
   after-columns) and sweep 3 (P3.4's after-column). Invariant 4: n=3 for a FAIL session, n=1 for a
   DEFECT one; say which each is (`evidence/classification.json`). Session 40's recorded costs ran above
   the stored figures (6335 $1.55 for n=3; `p37r_6374` $0.82 with a lost-completion episode): use
   `wave4_b8_sweep` where it has the run. **Say in your note** the priced sweeps as tables the
   integrator can put to the user, and which hand-reads each needs.

**Tests:** each new check on synthetic run files, failing with the check reverted, plus single-site
mutants.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit
   or later (if another session has committed, read what changed and say so); pushed; `plan_status`
   54 of 78, 2 in progress, 8 of 14 (or the new counts, explained); `plan_lint` exit 0; rubric sha1s;
   the test databases (create `lexchat_test_e`); nothing running (no python process, port 8000 free),
   no pin file; a baseline full suite on `lexchat_test` (2482).
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four
   questions): launch A, B, C, D and E as set out? **May B make up to 20 National Archives calls and C
   up to 40 LEX calls?** (Free of model spend; the alternative is stored evidence only.) Confirm the
   merge order (A, E, sweep 1 on the user's go-ahead, B, C, sweep 2 on the user's go-ahead, D, and
   sweep 3 only if the user wants it this session).
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message.
   Give each its section, plus **Rules for every agent**, **Lessons from batches 1-8** and **Shared
   setup**, verbatim; the integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL`; and whether the user agreed to its live calls. While they run, do nothing
   expensive and edit none of their files.
4. **Review each result as it lands** (as in batches 3-8):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines for session ids (allowed), instrument ids and matter words (not allowed,
     except synthetic years 1899-1902 and `DEPTH_TRUTH`'s public statutory text), with
     `seam/batch8/scratchpad_s40/review_branch.sh <branch> <INTEGRATOR_HEAD>` (it runs
     `matter_grep.py`; repoint its scratchpad path to this session's first);
   - for every product or grader change, re-run the new tests with the change reverted on a scratch
     worktree (restore the changed files from `<INTEGRATOR_HEAD>`, keep the new tests, count the lines
     removed), plus **at least three single-site mutants of your own, at least one on a guard or a
     cleaning step** (`b8_mutA.py` is the pattern); send the agent back to close any gap a surviving
     mutant shows, unless it is provably harmless (say why);
   - **screen each product change's new wording with the BUILT code against `sched_clause_class` and
     every other grader** (`screen_A_wording.py` in `scratchpad_s40` is the pattern);
   - run the full suite on `lexchat_test`;
   - re-run one headline number from each note on the merged tree;
   - copy the agent's scratch out of its worktree before removing it, and compare file counts.
     **Do not remove an agent's worktree before its branch is merged** (a removed worktree cannot be
     resumed: Session 40 had to launch B2 in B's place). Run `git worktree remove` from the main
     checkout, never from inside.
   Put any wording a lawyer could read to the user before its merge (B's, C's and D's).
5. **Merge A, then E**, each `--no-ff`, the suite after each, the branch pushed after each clean
   merge (never `main`; if the classifier refuses, ask the user). Copy E's rubrics to
   `evidence/rubrics/` (check `git check-ignore -v` first) and record their sha1s.
6. **Sweep 1, only on the user's go-ahead.** Put E's priced table to the user (AskUserQuestion: run it
   as priced, a cheaper subset, or defer); give the median and the maximum; agree a cap for the whole
   sweep. Then:
   - from `server_py/`: `python -m tools.replay check`, then `python -m tools.replay pin`;
   - start uvicorn fresh: `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`, in the
     background with PowerShell `Start-Process -PassThru` (the real Windows PID), logging to the
     session scratchpad; confirm `/api/bot-info` shows the merged build; start the keep-awake helper
     (`seam/batch1/scratchpad_s33/keep_awake.py`) and record both PIDs;
   - run E's commands in order into `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b9_sweep1`
     (or the names E gives), **keeping a running total with `sweep_total.py` after every command and
     capping each command at the lower of E's figure and what remains**; `--max-spend` is per command
     and checked between reps only, so an n=1 run cannot be stopped part-way: before starting one,
     check its recorded maximum fits what remains, and **if the total passes the agreed figure, stop
     and ask**. Never commit while it runs; if it stalls (15 minutes with no log growth), re-run the
     SAME command: it resumes;
   - then `python -m tools.replay restore`, stop uvicorn and the helper by their PIDs, and confirm no
     pin file, no python process and port 8000 free.
   - **Grade** each directory: the exit-1 set (`grade_b8.sh`, repointed), `modes`, `negcurrency`
     (without `--all` on a single directory), `footer_echo`; for P3.27/P3.12 `depth --answers --drops`
     (6335 t7), `schedules` (6374's guard, the held units), `route_trace.py` on every 6374 and 6335
     turn (did the cap's new text arrive; did the route fire); for P3.22 and P3.4 E's graders (the
     before-columns). **Hand-read every `depth` verdict, every 6374 guard verdict, every P3.22 and P3.4
     before-column verdict**; save to the gitignored `evidence/rubrics/handread_wave4_b9_sweep1.md`.
     Tick P3.27 and P3.12 only if their own acceptance passes by hand (n=3 all clean for a FAIL
     session; P3.27's guard on every 6374 slot that makes a statement).
7. **Merge B, then C** (after the restore), each `--no-ff`, the suite after each, pushed. Before C's
   merge, put C's wording to the user; before B's, B's.
8. **Sweep 2, only on the user's go-ahead**, exactly as step 6 (E's table; the confound check decides
   one sweep or two), into `wave4_b9_sweep2`; grade with E's graders and the exit-1 set; hand-read
   every P3.22 and P3.21 verdict to `evidence/rubrics/handread_wave4_b9_sweep2.md`. Tick P3.22 and
   P3.21 only on their own acceptance, by hand.
9. **Merge D** after the restore (P3.4's wording put to the user first); tick P3.6 at merge if its
   deterministic acceptance holds on the merged tree. **Sweep 3** (P3.4's after-column) only on the
   user's go-ahead; otherwise book it for Session 42 with its price.
10. **Assemble:**
    - tick only rows whose acceptance is met on the merged tree, stating the check; annotate each row
      in a byte script (each anchor once, CRLF kept, an even number of `**` added, no `|` in a cell,
      rows on one line); a newly ticked row's Bucket-index entry gets ` **done**`; then `plan_lint`
      (0 errors) and `plan_status`;
    - **put the agents' decisions to the user**, grouped (AskUserQuestion, at most four questions per
      call, recommendation first). Record each answer on its row;
    - CHANGELOG *Unreleased*: each product change in plain words (what a lawyer or the model now
      sees); tooling separately. Add an even number of `**`. Correct `docs/LEGAL_DATA_SOURCES.md`,
      `docs/api/AUDIT_TRACE.md` (any new `api_calls` or result keys: C adds feed calls and keys) and
      CLAUDE.md where a finding changes them.
11. **Hand over:** a Session 41 entry and a handover for Session 42 in SESSION_LOG.md (next by
    severity); the memory entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session
    scratchpad to the gitignored `evidence/seam/batch9/scratchpad_s41/`; update the local skills
    (`.claude/` is gitignored) where a finding changes what they say; update the Fix Tracker only if
    the user asks (FIX_PLAN "How to use this file" step 7: Artifact `read` the live URL and Read every
    line of the saved file first; a newly ticked row gets `fixed` and `ver: "Next release"`; set
    `AS_AT` to the local date and time of the update, e.g. "7th Oct 2026, 4:05pm", and `UPDATED`; a new
    row gets `added`, the day it is added; the table sorts unfinished rows first, P1 at the top).

**Open with the user, carried (do not act on them yourself):** sending the lawyer pack (five
questions now; unblocks P3.2, P3.3, P3.17, and confirms P3.22's 6363 list; confirm the cover note's
promise first); sending SCTS the note (P3.20's prerequisite); applying for the National Archives
licence (`docs/TODO.md` D23); deploying `v2026.09.3` to the target (`pg_dump` first, then pull,
restart and `test_apis.ps1`); telling the eval-harness owner about schema v6 and the P3.27/P3.12
`api_calls` note in `AUDIT_TRACE.md`; D19's remaining items; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, P3.19, P4.21, P3.24, P4.19, P3.23, P3.9 and
P3.25 are "Next release"); P4.12, D20, D21/D22; batch 1's three items; the p37_6373 substitution
P4.17 exposes; enrolling 6370's five hedged drops in `p33.json` before the next P3.3 after-column;
P3.24's three watch items; Session 40's watch items (`negatives` on `p37r_6383` t2; the
research-shaped echo on 6406; 6409's lost SSI date, which P3.21 should restore); and **saving and
mapping any further external report in the session that receives it**.
