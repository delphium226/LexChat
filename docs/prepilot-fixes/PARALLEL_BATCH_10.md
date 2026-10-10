# Parallel batch 10: P3.12's next lever, P3.22's per-query check, P4.3, P3.10 and P4.12 measured, grader fixes

**Set up on 2026-10-08, at the end of Session 41, for Session 42, at the user's request** ("provide a prompt to
kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-9
(`PARALLEL_BATCH_1.md` to `_9.md`): agents in git worktrees, the main session integrating, nothing merged that
the integrator has not re-checked. **Every agent is $0 in model spend.** One agent (B) may make free, bounded
live calls to the National Archives **only if the user agrees at launch**. The paid step is **one small replay
sweep (P3.12's re-run, 6335 n=3, about $1.75 to $2), run by the integrator alone after A's merge, priced to
the user first from agent E's table and run only on the user's go-ahead.** Nothing is authorised yet.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus **Rules for
every agent**, **Lessons from batches 1-9** and **Shared setup**, verbatim. Nothing here should need
re-deriving; if something does, the agent says so in its note rather than guessing. Matter-specific detail
(lawyers' wording, case names, rubric patterns, hand-reads, ground-truth text, live payloads) is NOT in this
file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first) **unless a dependency means it can't be**.
   FIX_PLAN's top order line ("as at 2026-10-08, end of Session 41") is the order.
2. **P3.12 (P1, `[~]`): the next lever is measure-first, $0 first** (user decision, 2026-10-07): when a fetched
   schedule or annex unit is too large to hand over whole and the query names no paragraph, hand over the
   unit's paragraph headings and cut the paragraphs whose headings match the query, rather than one summary;
   and reword the summarised block's tail ("The summary is not the statutory text: quote the provision only
   from retrieved text") so a summary is never read as "not retrieved". Measured on the stored route calls
   before any build. Criterion (v) stays met. The acceptance stays 6335 turn 7 n=3 (`depth`, each paragraph
   cited with its facts).
3. **P3.22 (P2, `[~]`): keep the build** (relevance ordering, `per_page=50`); **re-book the bar's "no in-corpus
   authority retrieved in fewer runs" item as a per-query retrieval check** (does the same query still return
   the authority under relevance), testable at $0 with a few National Archives calls; **fix `replay_report
   authorities`' surname match** (match the full name or the citation, never the surname alone) before any
   further P3.22 column.
4. **`replay_report negcurrency`'s section-search shape gap: a tooling fix with an identity run** (every verdict
   that moves listed) before P3.24's watch items are next measured.
5. **P3.27, P3.21, P3.4 and P3.6 are ticked** (Session 41). Their watch items are on their rows. Do not
   re-open them.
6. **P3.4's research-mode follow-up** (the research Manager and the Deep Research planner, with their own
   Research-mode before-column) is booked, not in this batch.
7. **P3.30 (P3)** is booked (a code-built ENABLING POWER block from a search row's recital); not in this batch.
8. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack** (five questions, ready, not sent).
9. **Agents propose; the integrator applies; the user approves anything not mechanical**, including any
   wording a lawyer or the Worker will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md,
   CLAUDE.md, `summary-table.html`, `docs/TODO.md`, `docs/LEGAL_DATA_SOURCES.md`, a rubric, the lawyer pack or
   a memory file.
10. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks. **Branch pushes
    were approved by the user after every clean merge in Session 41; ask again at Session 42's start** (the
    permission classifier refused the first push in Sessions 40 and 41).
11. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-08, end of Session 41)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit. **`main`** at `a6b4a76`, release
  **`v2026.09.3`**.
- **Tests: 2783** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **58 of 79 rows, 2 in progress (P3.12, P3.22), 9 of 14
  buckets** (B9 closed in Session 41); **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings). Run both
  after every fold.
- **Fix Tracker v42** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`): 78 rows, 54 Fixed, 2 In progress, 16 Verified, 3 Blocked, 3 To be
  verified; header "as at 8th Oct 2026, 11:45am".
- **What Session 41 built** (notes `docs/prepilot-fixes/notes/batch9_{A,B,C,D,E}.md`, committed):
  - **A:** `agent_shared._fetch_once` reserves P3.12's per-run provision-list slot before the fetch's await;
    `MAX_PROVISION_FETCHES` = 8 (its own constant); a failed read stays recorded.
  - **B (P3.22):** `caselaw.CASE_LAW_ORDER_PARAMS` (`order=relevance`, `per_page=50`); the window note says
    "listed most relevant first, by relevance to the search words rather than by date", "the first N of about
    T", "Another judgment that matches can sit outside these N"; `caselaw_probe` sends the product's request.
  - **C (P3.21):** `agent/tools/commencement_dates.py` (the legislation.gov.uk affected feed through LEX's
    `/legislation/proxy`, `changes[].in_force`/`qualification`, the made-date check, the result-level
    `commencement_dates` dict); the gated wording in `search_scope.py`; four static texts.
  - **D:** P3.4's JURISDICTION section (conversational Manager) and bullet (quick-lookup Worker), the extent
    notes without letter codes; P3.6's `lex._search_description` (600 characters) and the gated SEARCH SCOPE
    clauses (`_DESCRIPTION_CLAUSE` says "possibly truncated").
  - **E:** `replay_report authorities` (P3.22, rubric `evidence/rubrics/p322.json`), `cmcdates` (P3.21; use
    `--negative-allows-supported` on 6411, user decision), `jurisdiction` (P3.4, rubric `p34.json`); scripts
    `p34_6378.json`, `p34_6360.json`.
- **The sweeps** (all pinned Gemini; hand-reads gitignored in `evidence/rubrics/`): `wave4_b9_sweep1` ($14.47:
  P3.27/P3.12 re-run, P3.22's and P3.4's before-columns), `wave4_b9_sweep2a` ($12.39: P3.22 after),
  `wave4_b9_sweep2b` ($1.45: P3.21 after), `wave4_b9_sweep3` ($1.09: P3.4 after). Hand-reads
  `handread_wave4_b9_sweep1.md` (with sweep 3 as an addendum) and `handread_wave4_b9_sweep2.md`.
  - **P3.12's 6335 t7 (sweep 1):** DELIVERED 0 of 3. The route fired in 3 of 3, but no Manager brief named
    paragraphs 42-44 and every Worker query named "Schedule B1" alone, so the whole Schedule (92,066 characters)
    was summarised for the question; the summary held paragraph 42 only (r1), 43-44 (r2) or all three (r3,
    whose answer gave 42 and 43 at depth, not 44); in r2 the Worker called the summarised provisions "not
    retrieved by the search". `route_trace.py` on `wave4_b9_sweep1/6335_rep{1,2,3}.json` turn 7 shows it.
  - **P3.22's columns:** every request `none/-` before and `relevance/50` after; the lead UKSC judgment 3/3 to
    3/3, the carrier 3/3 to 3/3; two 6363 authorities fell (3/3 to 1/3, 2/3 to 1/3): by hand, one arrived in
    sweep 1 only as a lower-ranked co-result of queries naming another case (ranks 15-34, newest-first), which
    sweep 2a never issued; the other came back every time its own query was issued. One genuine item-3 failure
    (6359 r2 t6) and three grader surname false positives (6359 r1 t3 in sweep 1; r2 t3 and r3 t3 in 2a).
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **63 replay directories** under `replay/`, all on the pinned `google/gemini-3.1-pro-preview`; the newest four
    are `wave4_b9_sweep1` (17 files), `wave4_b9_sweep2a` (6), `wave4_b9_sweep2b` (6), `wave4_b9_sweep3` (7).
  - Rubrics `p32.json` (`31379ecf…`), `p33.json` (`0031831b…`), `p327.json` (`5a14e273…`), `p322.json`
    (`863955e0…`), `p34.json` (`f0232e9d…`).
  - **Batch 9 scratch** `seam/batch9/{A,B,C,D,E,scratchpad_s41}/`:
    - **A:** `dryrun_slot.py` (A2's `dryrun_p312.py` pattern, round-aware, with `DRYRUN_WT`, `DRYRUN_MODE`
      seq/model/burst, `DRYRUN_SYNTH`), `bound_refusals.py`, `synth_lookups.json`, `gaps.py`.
    - **B:** `dryrun_b9.py`/`compare_b9.py` (every stored case-law call through `run_worker_tool`, served
      batch 8 C's live feeds), `tna_b9.py` (the capped, paced, logged National Archives door), `live_smoke.py`.
    - **C:** `dryrun.py`, `acceptance.py`, `lexcall.py`, `made_live.json`, `smoke.py`.
    - **D:** `extent_count.py`, `desc_census.py`, `cap_p36.py`, `dryrun_p36_tree.py`, `recitals_p36.py`,
      `overlap_p321.py`, `reach_p34.py`, `seam_ab_check.py`, `head_server_py.tar`.
    - **E:** `p322.json`, `p34.json`, `price.py`, `inventory.py`, `confound.py`, `identity.py`,
      `sections_shape.py`, `scan_sources.py`, `mutants.py`.
    - **Integrator (`scratchpad_s41`):** `review_branch.sh` (base parameter; repoint its scratchpad path),
      `matter_grep.py`, `grade_b8.sh` (the exit-1 set + `negcurrency` + `footer_echo`; repoint), `sweep_total.py`
      (a sweep's running total: **`--max-spend` is per command**), `route_trace.py`, `b9_screen.py` (every
      answer-reading detector over a dict of texts, incl. `SCHED_LIMIT`, `sched_clause_class`, the bracket and
      strip checks) with `b9_screen{B,C,D}.py` (built-wording screens), the mutant runners
      `b9_mut{A,B,C,D,E}.py`, `fold_s41.py`, `docs_s41.py`, `preserve_s41.py`, `tracker_v42.py`,
      `s41_decisions.md` (every decision and review result of Session 41).
  - Batch 8 C's live feeds (`seam/batch8/C/`) and rubric (`rubric_p322_6363_6359.md`), batch 7 B's saved LEX
    lookups (`seam/batch7/B/raw/`) and P3.12's ground truth (`p312_truth.txt`).
  - The keep-awake helper: `seam/batch1/scratchpad_s33/keep_awake.py`.
  - The raw transcript export (never in the repo):
    `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`.
- **Test databases** `lexchat_test_a` to `lexchat_test_e` exist (one per agent; never share one between two
  running agents). psql is at `C:/Program Files/PostgreSQL/18/bin/psql.exe`.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no registered worktrees.
  Local merged agent branches from batches 1-9 remain (deletable). Possibly-remaining scratch dirs
  `C:\Temp\b8_revA*`, `C:\Temp\b9_rev*` are disposable.

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.12** (P2 tracker, the P1 work in the order line) | Measure, then build, the decided lever: headings plus a query-matched cut for a too-large unit, and the summary tail reworded | product, deterministic build; replay by the integrator | $0, no external call | `server_py/src/utils/schedule_units.py`, `server_py/src/agent/agent_shared.py` (`schedule_route_block`), tests |
| **B** | **P3.22** (P2) | The per-query retrieval check: does the same query return each rubric authority under both orderings | measurement, no product code | $0; National Archives calls only if agreed (up to 150) | its scratch only (plus its note) |
| **C** | **P4.3** (P2; B8, the only fully open bucket) | Measure first and propose the re-booked acceptance and the lever (the unused-source rate on report turns, link counts, Thomas's inline-URL rule) | measurement, no product code | $0, no external call | its scratch only (plus its note) |
| **D** | **P3.10** (P2) and **P4.12** (P2) | Re-book P3.10's acceptance on what a dependent step costs and whether its list matches; recount P4.12's episodes (incl. Session 41's Manager runaway) and its candidate levers | measurement, no product code | $0, no external call | its scratch only (plus its note) |
| **E** | tooling, and the sweep priced | `authorities`' surname match; `negcurrency`'s section-search shape (identity run); `cmd_corpus`'s stale label; `commencements` grading scripted runs (optional); the P3.12 re-run priced | tooling only, no product code | $0, no external call | `server_py/tools/replay_report.py`, tests |

**Why these five.** By severity: P3.12 is the only open P1 work not blocked on the lawyer pack. The P2 rows in
the order line are P3.22 (its per-query check), P4.3 and P3.10 (each to be re-booked before any build), P4.12
(measure-first) and P3.20 (last, waiting on SCTS's reply), with P3.4's research-mode follow-up booked. B, C and
D are measure-only so their results can be decided by the user at the end of the session and built next. E's
grader fixes are booked prerequisites (P3.22's next column; P3.24's next measurement). **Not in this batch:**
P3.20 (external), P3.4's research-mode follow-up (it needs its own before-column sweep), P3.30 and the other P3
rows, anything Blocked.

**Merge order: E, then A, then the sweep (P3.12's re-run, on the user's go-ahead), then B, C, D** (notes and
scratch only; merge in any order once read). **Never commit while a replay runs.**

**Collision points.**
- **No agent edits `tools/replay_report.py` except E.** A grader change any other agent needs goes in its note.
- **A is the only agent editing product code.** B, C and D commit only their note (and nothing under
  `server_py/src/`); their scripts stay in their gitignored scratch.
- **A's new wording is Worker-facing** (the PROVISION FETCHED BY CODE block); it is put to the user before
  merge, screened with the BUILT code against every detector (`b9_screen.py`), and E's `schedules` and `depth`
  graders must read its new labels correctly (A lists every new label; E's `sched_clause_class` must class
  none of them as a negative or a limit).
- **The sweep's head must hold E's and A's merges and nothing of B, C or D's** (they change no product code, so
  this holds by construction; check `git diff <sweep head> HEAD -- server_py/src` is empty after their merges).

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the top recommended-order line, the paragraph above the Ledger
   on what waits on the lawyer pack, and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`,
   everything from "Session 41 — 2026-10-06 to 2026-10-08 — parallel batch 9" to the end of the file; and the
   batch 8 notes your brief names. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`,
   `docs/LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the lawyer pack or any memory
   file: the integrator folds your results in. Commit on your worktree's branch; **do not push, do
   not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch10_<A|B|C|D|E>.md` and commit it. Put in it:
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
    `docs/prepilot-fixes/evidence/seam/batch10/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch10/<your letter>/`. **Never write to
    the session scratchpad, not even briefly.** Say in your reply which you did, with the file count
    on both sides.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend (and the number of live calls, per host); the path of your note and where your scratch is;
    for each item, met or not and why; and the numbered decisions for the user.

## Lessons from batches 1-9 (give these verbatim with each brief)

- **Check your base before anything else.** In all nine batches every worktree the Agent tool made
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
  merged tree. **A script that globs every replay directory picks up new ones** (there are 63 now):
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
- **Batch 9's lessons (Session 41).** (1) **The integrator's own mutants found a gap in three of five agents**
  (an untested memo guard on a failed read; a new sentence whose "cut short" trips `SCHED_LIMIT`, which the
  agent's screen did not run directly; an untested command-line option): write a mutant for every guard,
  option and cleaning step, and screen new wording against `SCHED_LIMIT` and `sched_clause_class` sentence by
  sentence. (2) **A built shape can differ from the brief's** (C built `commencement_dates` as a dict): say so in
  the first section of your note so the integrator can relay it. (3) **A before/after bar on retrieval counts
  mixes ordering with query choice** (P3.22): compare the same query under both conditions. (4) **Measure what
  the upstream actually sends** (P3.12: no Manager brief in three reps named the paragraphs the route needed).
  (5) **A grader that matches one surname is wrong** (3 false FAILs in `authorities`). (6) **Every stored replay
  was summarised at the 8,000-character fallback** (a cold context-length cache), not the pinned model's
  ~200,000: a measurement about summarisation is a measurement at 8,000. (7) **A Manager runaway can cost a
  single rep $4.75**; the per-command cap cannot stop it inside a rep.
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

---

## Agent A: P3.12's next lever, measured then built ($0, product)

**Read first:** P3.12's and P3.27's rows in full (P3.12's Session 41 annotation especially);
`notes/batch8_A.md` sections 2.1-2.4, `notes/batch8_A2.md`, `notes/batch9_A.md`; the gitignored
`evidence/rubrics/handread_wave4_b9_sweep1.md` (the P3.12 section); `schedule_units.py` (`named_units`,
`cut_pieces`, `cut_schedule_paragraph`, `fetched_block`, the label and line builders) and
`agent_shared.schedule_route_block` (the WHOLE and SUMMARY branches); `replay_report`'s `DEPTH_TRUTH["6335"]`
(what each paragraph must say).

**The defect (Session 41's sweep 1):** with no paragraph named, the route hands over the whole Schedule
summarised for the question; on a 92,066-character Schedule the summary keeps some paragraphs and drops others,
and once the Worker read the block's tail as "not retrieved".

**Measure first, over every stored route firing call** (A's `dryrun_slot.py` / `dryrun_p312.py` pattern
repointed in a copy, batch 7 B's saved lookups through a mocked transport, `wave4_b8_sweep` and `wave4_b9_sweep1`
included; say how many calls and which have no saved lookup): for each call that reached the SUMMARY branch,
what a heading list plus a query-matched cut would hand over instead (which paragraphs' headings match the
query's words, how many characters, whether it stays under the verbatim threshold and the context budget), and
for 6335 turn 7's calls in particular whether paragraphs 42, 43 and 44 would be cut and handed over verbatim
(their headings and the query words are in the gitignored `seam/batch7/B/p312_truth.txt` and the run files).
List every call whose output moves, and the forms no stored run contains (a unit with no paragraph headings; a
query matching no heading; a query matching more headings than fit), tested on synthetic input.

**Build (only if the measurement supports it; say so in the note if it does not, and stop at the
measurement):** for a fetched unit over the verbatim threshold whose query names no paragraph, hand over (1)
the unit's paragraph headings (number and heading, in order), and (2) the paragraphs whose heading shares a
distinctive query word, each cut by `cut_schedule_paragraph`'s existing rules (clean only where unique and the
next heading is N+1; labelled otherwise), within a character bound you choose and justify from the measurement;
fall back to today's summary only where nothing matches or the cuts exceed the bound. Reword the summarised
block's tail so it cannot be read as "not retrieved": it must say that the unit WAS retrieved and that the
summary is a condensed reading of retrieved text (draft the wording; no "not" next to "retrieved"; screen it).
Nothing else the Worker reads may change. **Tests** at each seam, each failing with the change reverted (lines
removed), single-site mutants for every guard and cleaning step (the matching, the bound, the fallback, label
cleaning). **Screen every new label and line with the BUILT code** against every detector (`b9_screen.py` in
`scratchpad_s41` is the integrator's; write your own screen in your scratch), and check `replay_report
schedules` (`sched_clause_class`) and `depth` read them as intended (E is fixing other graders in parallel;
put any grader change you need in your note). **Say in your note** the exact new wording of every variant, for
the integrator to put to the user before merge, and the seam payload the integrator could draw to check the
Worker's reading (no draw yourself).

## Agent B: P3.22's per-query retrieval check ($0; National Archives calls only if agreed)

**Read first:** P3.22's row in full (Session 41's annotation); `notes/batch8_C.md`, `notes/batch9_B.md`; the
gitignored `seam/batch8/C/rubric_p322_6363_6359.md` (the bar) and `evidence/rubrics/handread_wave4_b9_sweep2.md`
(the P3.22 section); `replay_report authorities` (E's, merged) and its rubric `evidence/rubrics/p322.json`.

**The question:** did relevance ordering lose the two 6363 authorities that fell between sweep 1 and sweep 2a,
or did the Worker's searches change? **Measure ($0 + live calls if agreed, cap 150, through a door like
`seam/batch9/B/tna_b9.py`: capped in code, at least 0.4 s apart, every call logged with method, URL, status and
bytes):** collect every distinct `search_case_law` query (with its court and dates) from the 6363 and 6359 runs
of `wave4_b9_sweep1` and `wave4_b9_sweep2a`; re-run each under today's default order and under the product's
params (`caselaw.CASE_LAW_ORDER_PARAMS`, imported, not copied; the dates built by the built
`case_law_date_window`); for every in-corpus rubric authority report, per query, whether each ordering returns
it and at what rank, and whether it falls inside the first three the nudge names. Answer: for each authority
whose run count fell, was any query that returned it under the default also issued in 2a, and does relevance
still return it for that query? Count batch 8 C's saved feeds first and re-use them where a tuple matches
exactly (no call needed). **Propose the re-booked bar item** (wording for the row, deterministic where it can
be) as a decision. No product code; no grader edit (E's). If the user did not agree to live calls, do it on
saved feeds only and say which queries could not be checked.

## Agent C: P4.3 measured and re-booked ($0, no product code)

**Read first:** P4.3's row in full (incl. batch 5 C's re-booking decision and Thomas's action 7); P2.4's and
P3.13's rows (the Manager-drops-links observations); `agent_core._source_is_used`, the sources-rail code
(`accumulated_sources`) and `citation_links`; `replay_report caselaw` (`caselaw_links`) and any existing
unused-source counter.

**Measure first, over every stored directory (63; say which are pre-P2.1 and exclude them from rates, since
halts inflate the unused rate):** on report turns only, the unused-source rate (a source kept in the rail and
referenced nowhere in the answer), split by chat mode and by research type; the number of links a Worker report
carries and how many reach the answer (the Manager's drop rate), split by Conversational and Research; and for
6378 (the regression check) whether SSI 2008/216 reaches the answer body. Then a $0 dry run of each candidate
lever where code can be dry-run (a rail flag for consulted-not-cited, computed by the built `_source_is_used`
over the stored answers; the inverse diagnostic), and for Thomas's prompt rule (keep each retained
proposition's supporting URL inline, invent none) say what a seam A/B would cost and which payloads (the
Manager seam, offered its tools, `--date recorded`). **Propose** the re-booked acceptance (a bar on the
unused-source rate on report turns and on links kept) and the lever, as decisions with options. No product
code, no seam draw.

## Agent D: P3.10 re-booked and P4.12 measured ($0, no product code)

**Read first:** P3.10's and P4.12's rows in full; P2.7's, P3.8's, P4.10's and P4.11's rows; `notes/batch9_*`
for Session 41's runaway (P4.12's Session 41 annotation); `agent_core.run_deep_research`,
`_build_step_brief`, `PLANNER_SYSTEM_PROMPT`; `replay_report discovery`, `lostcost`, `lost`, `blanks`.

**P3.10:** recount dependent steps (the Session 15 regex, as `p310_dependent.py` in batch 5 C's scratch
reproduces it) over every directory, split before and after P3.1 and P2.7, and for each dependent step at HEAD
(after P3.8): its cost, its rounds, its halt, and whether the list it works on matches the list the earlier
step produced (instrument ids). **Propose** an acceptance on what a dependent step costs and whether its list
matches, and options (planner merges steps; the executor hands findings on), as decisions.
**P4.12:** recount every Manager-side empty or stalled completion over all 63 directories (`lostcost
--all-dirs`, `lost --all-dirs`), separating (a) heavy empties (P4.10's runaway shape, like `wave4_b9_sweep2a`
6363 r1 t3: three empties at 62,914 completion tokens, retried) from (b) upstream idle timeouts, with the cost
and wall time each added; say whether P4.10's no-retry rule should extend to the Manager (it re-delegates
nothing, so a lost Manager reply falls to P4.2's fallback) and what each candidate would cost or save on the
stored episodes. **Propose** levers and an acceptance as decisions. No seam draw (they cost money).

## Agent E: grader fixes, and the sweep priced ($0)

**Read first:** `notes/batch9_E.md` (all of it, incl. its section 8); P3.22's and P3.24's rows (Session 41's
grader notes); P3.6's row (the stale label); `server_py/tools/replay_report.py` (`cmd_authorities`,
`negcurrency_evidence`, `cmd_corpus`, `cmd_commencements`); the integrator's hand-read of the surname false
positives (`evidence/rubrics/handread_wave4_b9_sweep1.md` and `_sweep2.md`).

**Build (tooling only):**
1. **`authorities`' out-of-corpus match:** match an out-of-corpus authority by its full party names or its
   citation, never one surname; a cited judgment returned by a `search_case_law` call in the run is never the
   out-of-corpus authority. Re-grade sweep 1 and 2a and the stored columns: the 3 known false positives clear,
   the genuine 6359 r2 t6 (sweep 2a) stays a FAIL, every other verdict identical (list every move).
2. **`negcurrency`'s section-search shape:** read the `{"results": ...}` shape (4,748 of 5,314 stored section
   searches) as well as the list shape. **Identity run** over all 63 directories before and after, listing every
   verdict that moves, each read by hand.
3. **`cmd_corpus`'s label** "<- _slim_search_results strips it (P3.6)" made true after P3.6.
4. **Optional, if time:** `commencements` grades scripted runs through `from_turn` (it never has; every
   P3.25/P3.21 hand-read noted it).
5. **The sweep priced:** P3.12's re-run, 6335 n=3 (FAIL session), Conversational as recorded (turns 6-7
   `legislation_and_case_law`), with the recorded cost of each stored rep (`wave4_b9_sweep1`'s three: $0.574,
   $0.610, $0.567), a median, a maximum and the exact command with `--reps 3` and a per-command `--max-spend`;
   and say whether A's lever would change the cost (fewer summariser calls, more verbatim text).
**Tests** on synthetic run files, each failing with the check reverted, plus single-site mutants; the 16
exit-1 graders' output unchanged on every directory except where a fix is meant to move it (an identity run like
`seam/batch9/E/identity.py`).

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit or later (if
   another session committed, read what changed); pushed; `plan_status` 58 of 79, 2 in progress, 9 of 14;
   `plan_lint` exit 0; rubric sha1s; the five test databases; nothing running (no python process, port 8000
   free), no pin file; a baseline full suite on `lexchat_test` (2783). Copy the integrator tools from
   `seam/batch9/scratchpad_s41/` to this session's scratchpad and repoint their scratchpad paths.
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four questions):
   launch A, B, C, D and E as set out? **May B make up to 150 National Archives calls?** (Free of model spend;
   the alternative is saved feeds only.) Confirm the merge order (E, A, the sweep on the user's go-ahead, then
   B, C, D). **May the branch be pushed after each clean merge this session?**
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message. Give each
   its section, plus **Rules for every agent**, **Lessons from batches 1-9** and **Shared setup**, verbatim; the
   integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and `TEST_DATABASE_URL`
   (`lexchat_test_<a-e>`); and whether the user agreed to its live calls. While they run, do nothing expensive
   and edit none of their files.
4. **Review each result as it lands** (as in batches 3-9):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines with `review_branch.sh <branch> <INTEGRATOR_HEAD>` (it runs `matter_grep.py`; NOT
     `grep -iF`, which aborts in Git Bash);
   - for every product or grader change, re-run the new tests with the change reverted on a scratch worktree
     (count the lines removed), plus **at least three single-site mutants of your own, at least one on a guard
     or a cleaning step** (`b9_mut*.py` are the pattern); send the agent back (SendMessage, its worktree kept) to
     close any gap a surviving mutant shows, unless it is provably harmless (say why);
   - **screen each product change's new wording with the BUILT code** against every detector, `SCHED_LIMIT` and
     `sched_clause_class` included (`b9_screen.py`; batch 9's screen found D's "cut short");
   - run the full suite on `lexchat_test`;
   - re-run one headline number from the note on the merged tree (a copy of the agent's script repointed, its
     outputs written to the scratchpad, never over the agent's evidence);
   - compare the agent's scratch file counts on both sides.
   **Do not remove an agent's worktree before its branch is merged.** Run `git worktree remove` from the main
   checkout. Put A's wording to the user before its merge. If an agent's built shape differs from its brief,
   relay it to any agent that reads it.
5. **Merge E, then A**, each `--no-ff`, the suite after each, pushed after each clean merge if the user agreed.
6. **The sweep, only on the user's go-ahead.** Put E's price to the user (AskUserQuestion: run, or defer); agree
   a cap. `python -m tools.replay check`, `replay pin`, uvicorn fresh with PowerShell `Start-Process -PassThru`
   (log to the session scratchpad), confirm `/api/bot-info` shows the merged build, start the keep-awake helper,
   record both PIDs; run E's command into `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b10_sweep`;
   `sweep_total.py` after the command; **if a single rep could take the total past the cap, stop and ask** (a
   Manager runaway took one Session 41 rep to $4.75); never commit while it runs; then `replay restore`, stop
   both processes by PID, and confirm no pin file, no python process, port 8000 free. **Grade:** the exit-1 set
   (`grade_b8.sh`, repointed), `modes`, `negcurrency` (no `--all` on one directory), `footer_echo`, `depth
   --answers --drops` (6335 t7), `schedules --session 6335 --drops`, `route_trace.py` on every 6335 turn 7 (did
   the route hand over headings and cuts, or a summary; what did the Worker do with them). **Hand-read every
   `depth` verdict** and save to the gitignored `evidence/rubrics/handread_wave4_b10_sweep.md`. Tick P3.12 only
   if 6335 t7 is DELIVERED in 3 of 3 by hand.
7. **Merge B, C and D** (notes only; check `git diff` touches nothing under `server_py/`).
8. **Assemble:**
   - tick only rows whose acceptance is met, stating the check; annotate each row in a byte script (each anchor
     once, CRLF kept, an even number of `**` added, no `|` in a cell, rows on one line); a newly ticked row's
     Bucket-index entry gets ` **done**`; then `plan_lint` (0 errors) and `plan_status`;
   - **put the agents' decisions to the user**, grouped (AskUserQuestion, at most four questions per call,
     recommendation first). Record each answer on its row: B's re-booked P3.22 item, C's P4.3 acceptance and
     lever, D's P3.10 acceptance and P4.12 lever;
   - CHANGELOG *Unreleased* (A's change in plain words; E's tooling separately); correct
     `docs/LEGAL_DATA_SOURCES.md`, `docs/api/AUDIT_TRACE.md` and CLAUDE.md where a finding changes them.
9. **Hand over:** a Session 42 entry and a handover for Session 43 in SESSION_LOG.md (next by severity); the
   memory entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session scratchpad to the
   gitignored `evidence/seam/batch10/scratchpad_s42/`; update the local skills where a finding changes them;
   update the Fix Tracker only if the user asks (FIX_PLAN "How to use this file" step 7: Artifact `read` the live
   URL and Read every line of the saved file first; set `AS_AT` and `UPDATED`; a newly ticked row gets `fixed`
   and `ver: "Next release"`; a new row gets `added`).

**Open with the user, carried (do not act on them yourself):** sending the lawyer pack (five questions; unblocks
P3.2, P3.3, P3.17, and confirms P3.22's 6363 list); sending SCTS the note (P3.20's prerequisite); applying for
the National Archives licence (`docs/TODO.md` D23); deploying `v2026.09.3` to the target (`pg_dump` first, then
pull, restart and `test_apis.ps1`); telling the eval-harness owner about schema v6 and the new `api_calls`
(P3.27/P3.12, P3.21) and request keys (P3.22) in `AUDIT_TRACE.md`; D19's remaining items; which rows go in the
next cut (`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, P3.19, P4.21, P3.24, P4.19, P3.23, P3.9, P3.25,
P3.27, P3.21, P3.4 and P3.6 are "Next release"); P4.12, D20, D21/D22; batch 1's three items; the p37_6373
substitution; enrolling 6370's five hedged drops in `p33.json` before the next P3.3 after-column; the watch
items on P3.24, P3.27, P3.21 and P3.4; and **saving and mapping any further external report in the session that
receives it**.
