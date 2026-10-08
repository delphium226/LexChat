# Parallel batch 11: P3.12's next step, P4.12 and P4.3 built, P3.10 built, P3.20 measured

**Set up on 2026-10-08, at the end of Session 42, for Session 43, at the user's request** ("provide a prompt to
kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-10
(`PARALLEL_BATCH_1.md` to `_10.md`): agents in git worktrees, the main session integrating, nothing merged that
the integrator has not re-checked. **Every agent is $0 in model spend.** One agent (D) may make free, bounded
live calls to the Scottish Courts and Tribunals Service (SCTS) **only if the user agrees at launch**. The paid
steps are run by the integrator alone, each priced to the user first and run only on the user's go-ahead: **(1)
P3.12's seam draw on `wave4_b10_sweep` rep 1's turn-7 payload, at the start** (typically about $0.04-0.06 a
draw, but the default Worker seam is uncapped: a runaway draw costs up to about $2.30), and any seam draws of
agent A's candidate payloads; **(2) one replay sweep after the product merges**: P3.12's 6335 n=3 and P3.10's two
scripted turn-4 runs n=3 each (agent E prices it). Nothing is authorised yet.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus **Rules for
every agent**, **Lessons from batches 1-10** and **Shared setup**, verbatim. Nothing here should need
re-deriving; if something does, the agent says so in its note rather than guessing. Matter-specific detail
(lawyers' wording, case names, rubric patterns, hand-reads, ground-truth text, live payloads) is NOT in this
file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first) **unless a dependency means it can't be**.
   FIX_PLAN's top order line ("as at 2026-10-08, end of Session 42") is the order.
2. **P3.12 (P1 work, `[~]`):** the route now hands paragraphs 42-44 verbatim (16 of 16 stored calls; live in
   `wave4_b10_sweep` rep 1), and the reworded summary tail stopped "not retrieved"; but rep 1's Worker wrote only
   43(6) under a broad brief, while the seam on Session 41's r2 payload delivered 2 of 2. **Next (user decision,
   2026-10-08): seam-first on rep 1's turn-7 payload, to tell the draw from the payload; then a $0 lever only if
   the payload is the cause; then 6335 n=3, priced.** The acceptance stays 6335 turn 7 n=3 DELIVERED by hand
   (`depth`, each paragraph cited with its facts). Any Worker-facing wording goes to the user before merge.
3. **P4.12 (P2):** lever L1 + L2' + L3, gated (no retry after a Manager heavy empty; at most one retry, not two,
   after a Manager idle timeout; the 32,000-token output cap on Manager calls; the Manager keeps today's retries
   when no usable worker report is in hand). **Acceptance deterministic** (unit tests at each seam, each failing
   with its change reverted; single-site mutants for every guard; no replay, no seam draw). The row's title is
   widened to "a lost Manager reply". Its lever (i) (a retry with changed bytes) is **deferred**.
   `empty_completion.py`'s stale P4.10 comment is corrected at the build.
4. **P4.3 (P2):** lever **V4** at the Worker seam (drop the fall-back to the whole accumulator; keep a source the
   report names in words: title, SI number, EU number, old-SI form; drop the legislation `sub` token from the
   keep test; a title test with synthetic cases), with a **`replay_report rail`** grader on the careful-reader
   test. **Acceptance deterministic, $0, n=1** with the built code over every stored post-P2.1 report turn: (i) 0
   report turns whose rail is the unfiltered fall-back (from 90); (ii) the unused-source rate by the reader test
   at or below 15% in each chat mode; (iii) 0 sources the answer names removed from the rail; the next sweep
   re-graded on the same three; 6378 stays the regression check.
5. **P3.10 (P2):** acceptance re-booked on list match: replay n=3 on 6374 turn 4 and 6383 turn 4 (scripted
   turn-4 runs, about $4-5): every step working on an earlier step's list covers every listed instrument of the
   class it names, such steps' own `search_legislation` calls fall, no step halts, `sources_kept` does not fall.
   Lever: `_build_step_brief` adds one code-written line naming the instrument ids the earlier steps' report
   bodies link; **its wording goes to the user before merge**; every step 2+ or only flagged steps is decided at
   the build.
6. **P3.20 (P2):** SCTS agreed to our use of its judgments search **by phone, 2026-10-08, with no conditions
   given** (no written confirmation; rate, change notice, attribution and date reliability unanswered). **Its
   measure-first step runs in Session 43 as a $0 parallel agent beside P3.12** (live SCTS calls only if the user
   agrees at launch), the build after it.
7. **P3.22 stays `[~]` until its item 3 passes** (items 1, 2 and 4 met). Not in this batch.
8. **P4.23** (the Manager drops report links; a code linker, measure first) and **P4.24** (rail entries with a
   bare-id title or no URL) are booked, not in this batch. **P3.4's research-mode follow-up** and **P3.30** are
   booked, not in this batch.
9. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack** (five questions, ready, not sent).
10. **Agents propose; the integrator applies; the user approves anything not mechanical**, including any wording
    a lawyer or the Worker will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md, CLAUDE.md,
    `summary-table.html`, `docs/TODO.md`, `docs/LEGAL_DATA_SOURCES.md`, `docs/NETWORK_AND_DEPENDENCIES.md`, a
    rubric, the lawyer pack or a memory file.
11. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks. **Branch pushes
    were approved after every clean merge in Session 42; ask again at Session 43's start.**
12. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-08, end of Session 42)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit. **`main`** at `a6b4a76`, release
  **`v2026.09.3`**.
- **Tests: 2833** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **58 of 81 rows, 2 in progress (P3.12, P3.22), 9 of 14
  buckets**; **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings). Run both after every fold.
- **Fix Tracker v44** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`): 80 rows, 54 Fixed, 2 In progress, 18 Verified, 3 Blocked, 3 To be
  verified; header "as at 8th Oct 2026, 3:30pm".
- **What Session 42 built** (notes `docs/prepilot-fixes/notes/batch10_{A,B,C,D,E}.md`, committed):
  - **A (P3.12):** `schedule_units.paragraph_headings`, `heading_matches`, `matched_pieces` (`MATCHED`, bound
    `max(threshold, MATCHED_CUTS_MIN_CHARS` = 12,000), a query word distinctive in at most 3 headings, matched on
    the section search's own query); the reworded SUMMARY tails (`fetched_block`'s `summary_of`); in
    `agent_shared.schedule_route_block`. **At a warm context-length cache the pinned model's threshold (up to
    200,000) hands a 92K schedule over whole**, so the path acts at the 8,000 fallback (every stored replay).
  - **E (graders):** `authorities` names an out-of-corpus authority only by citation or full party names, and
    reads a link label holding a bracketed citation (a local `_P322_LINK`; the shared `MD_LINK` keeps the gap);
    `negcurrency` reads both section-search shapes; `corpus`'s labels; `commencements` grades scripted runs
    (its exit moves from 1 to 0 on 7 directories).
  - **B, C, D:** notes only (P3.22's per-query check; P4.3 and P3.10/P4.12 measured).
- **The sweep:** `wave4_b10_sweep` (head `8b4469c`), **1 file, `6335_rep1.json`, $0.99** (turn 1 $0.50: a Worker
  heavy empty capped by P4.10 at 30,719 tokens and re-delegated; turn 7 $0.12); stopped before rep 2 at the
  user's $1.90 cap. Turn 7 (one delegation): the route handed the heading list and paragraphs 42-44 verbatim
  (7,881 characters, after the summarised search rows); the brief asked "how the moratorium applies ..."; the
  Worker wrote 43(6) alone; SHALLOW by `depth`, not DELIVERED by hand (gitignored
  `evidence/rubrics/handread_wave4_b10_sweep.md`). Seam (Session 41's r2 payload with the new block): DELIVERED 2
  of 2; the reworded tail alone: PARTIAL 2 of 2, no "not retrieved".
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **64 replay directories** under `replay/`, all on the pinned `google/gemini-3.1-pro-preview`; the newest is
    `wave4_b10_sweep` (1 file).
  - Rubrics `p32.json` (`31379ecf…`), `p33.json` (`0031831b…`), `p327.json` (`5a14e273…`), `p322.json`
    (`863955e0…`), `p34.json` (`f0232e9d…`).
  - **Batch 10 scratch** `seam/batch10/{A,B,C,D,E,scratchpad_s42}/`:
    - **A:** `measure_a.py`, `dryrun_b10.py` + `compare_b10.py` (`DRYRUN_WT`/`DRYRUN_OUT`; rebuild `prev/` with
      `git archive 7c3c6ac server_py/src`), `screen_b10A.py`, `make_seam_payloads.py`,
      `seam_6335_r2_matched.json`, `seam_6335_r2_tail.json`, `brief_vs_query.py`, `mutants.py`.
    - **B:** `tna_b10.py` (the capped, paced, logged National Archives door: the pattern for any live door),
      `collect.py`, `plan.py`, `run_live.py`, `analyze.py`, `linked_check.py`.
    - **C:** `census.py` (run first), `agg.py`, `reader.py` (the careful-reader test), `dryrun_filter.py`
      (`P43_SERVER_PY` repoints it), `rebuild_diff.py`, `links2.py`, `nu_read.py`, `src_shapes.py`,
      `ab_payloads.py`.
    - **D:** `p310_recount.py` (`--detail`; the Session 15 regex, era split, list match), `p310_listread.py`,
      `p310_options.py`, `p412_manager.py`, `p412_retry_index.py`, `p412_rates.py` (repoint `SERVER`,
      `sys_path_server`, `REPO`).
    - **E:** `auth_parts.py`, `identity.py` (the 20-grader identity run), `nc_moves.py`, `cmc_scripted.py`,
      `price.py`, `mutants.py`.
    - **Integrator (`scratchpad_s42`):** `review_branch.sh` (base parameter; repoint its scratchpad path),
      `matter_grep.py`, `grade_b8.sh` (repoint), `sweep_total.py`, `route_trace.py` (prints the heading-list
      label), `b9_screen.py`, `b10_screenA.py` (a built-wording screen), the mutant runners `b10_mutA.py`,
      `b10_mutE.py` (and batch 9's `b9_mut{A..E}.py` in `seam/batch9/scratchpad_s41/`), `fold_s42.py`,
      `docs_s42.py`, `preserve_s42.py`, `scts_s42.py`, `tracker_v43.py`, `tracker_v44.py`,
      `whitelist_request_scts.md`, `s42_decisions.md` (every decision and review result of Session 42).
  - The keep-awake helper: `seam/batch1/scratchpad_s33/keep_awake.py`.
  - The raw transcript export (never in the repo):
    `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`.
- **Test databases** `lexchat_test_a` to `lexchat_test_e` exist (one per agent; never share one between two
  running agents). psql is at `C:/Program Files/PostgreSQL/18/bin/psql.exe`.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no worktree but the main
  checkout. Merged agent branches from batches 1-10 remain locally (deletable).

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.12** (P1 work) | Why rep 1's Worker wrote 43(6) alone: compare its payload with the delivering ones; a $0 candidate lever built only if the integrator's seam result points at the payload | measurement, then a candidate product change (unmerged until the user approves) | $0, no external call | `server_py/src/utils/schedule_units.py`, `agent_shared.schedule_route_block`, tests |
| **B** | **P4.12** (P2) | L1 + L2' + L3, gated; the stale comment | product, deterministic acceptance | $0, no external call | `utils/empty_completion.py`, `openrouter_client.py`, `ollama_client.py`, the Manager call path in `agent_core.py`, tests |
| **C** | **P4.3** (P2) | V4 at the Worker seam, and the `replay_report rail` grader | product + tooling, deterministic acceptance | $0, no external call | `agent_core.run_worker_agent`'s filter, `_source_is_used`, `server_py/tools/replay_report.py`, tests |
| **D** | **P3.20** (P2) | Measure first: the SCTS search against the stored Scots-law case-law turns, date reliability, PDF text, the gated wording sites; propose the design and acceptance | measurement, no product code | $0; SCTS calls only if agreed (up to 150) | its scratch only (plus its note) |
| **E** | **P3.10** (P2), and the sweep | The ids line in `_build_step_brief` (wording to the user); two turn-4 scripts; the list-match grading script; the sweep priced | product + scripts | $0, no external call | `agent_core.run_deep_research` / `_build_step_brief`, tests, `evidence/scripts/p310_*.json` |

**Why these five.** By severity: P3.12 is the only open P1 work not blocked on the lawyer pack (its paid seam
draw is the integrator's first step). The P2 rows ready to build are P4.12 and P4.3 (deterministic, $0, levers
decided) and P3.10 (lever decided, wording to approve, replay priced); P3.20 is unblocked by SCTS's permission
and is measure-first by the user's decision. **Not in this batch:** P3.22's item 3, P4.23, P3.4's research-mode
follow-up (each measure-first, next batch), P4.24 and the other P3 rows, anything Blocked.

**Merge order: B, then A (only if a candidate is built and the user approves its wording), then E (wording
approved), then the sweep (on the user's go-ahead), then C, then D.** **Never commit while a replay runs.**

**Collision points.**
- **`agent_core.py` is touched by B (the Manager call path), C (`run_worker_agent`'s filter) and E
  (`_build_step_brief`)**: different functions; each agent states the functions it changed, and the integrator
  merges in order and re-runs the suite after each merge.
- **No agent edits `tools/replay_report.py` except C** (the `rail` subcommand). A grader change any other agent
  needs goes in its note.
- **C merges AFTER the sweep:** V4 changes the rail and so `sources_kept`, which P3.10's acceptance reads
  (Invariant 3). Check `git diff <sweep head> HEAD -- server_py/src` after C's merge holds only C's change.
- **B before the sweep** saves money on a Manager runaway and changes no measured quantity of P3.12 or P3.10
  (it acts only on an empty Manager completion); say so in the sweep's hand-read if one occurs.
- **A's and E's wording is Worker-facing**: put to the user before merge, screened with the BUILT code against
  every detector (`b9_screen.py`, `b10_screenA.py`), `SCHED_LIMIT` and `sched_clause_class` included.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Verification protocol" (incl. "Iterate on a seam before you pay for a replay"), "Re-planning
   protocol", the top recommended-order line, the paragraph above the Ledger on what waits on the lawyer pack,
   and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`, everything from "Session 42 — 2026-10-08 —
   parallel batch 10" to the end of the file (incl. its three addenda); and the batch 10 notes your brief names.
   Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`,
   `docs/LEGAL_DATA_SOURCES.md`, `docs/NETWORK_AND_DEPENDENCIES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the
   lawyer pack or any memory file: the integrator folds your results in. Commit on your worktree's branch; **do
   not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch11_<A|B|C|D|E>.md` and commit it. Put in it:
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
   and every cleaning step** (bracket cleaning, uniqueness checks, completeness checks, length and
   emptiness thresholds): in Sessions 40, 41 and 42 the integrator's own mutants found an untested guard in
   every batch. Run the full suite on your own test database before your last commit, and report the count.
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
   agreed at launch**, and then: paced (at least 0.5 s apart; the National Archives at least 0.35 s;
   **SCTS at least 1 s**), under the cap your brief gives, every call logged (method, URL, status, bytes) to
   your gitignored scratch, the cap enforced in code (batch 10 B's `tna_b10.py` is the pattern), and counted
   in your note. **LEX's read endpoints are POST, and so is the SCTS search**, so "calls", not "GETs". Every
   other agent makes no external call at all. **If your run is interrupted and resumed, recount your call log
   first: the cap covers every call already made.**
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run`, `replay restore` or a
   `seam_replay` draw (`--dry-run` is allowed: it builds the payload and makes no call).
10. **Scratch goes in your own folder:** your worktree's gitignored
    `docs/prepilot-fixes/evidence/seam/batch11/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch11/<your letter>/`. **Never write to
    the session scratchpad, not even briefly.** Say in your reply which you did, with the file count
    on both sides.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend (and the number of live calls, per host); the path of your note and where your scratch is;
    for each item, met or not and why; and the numbered decisions for the user.

## Lessons from batches 1-10 (give these verbatim with each brief)

- **Check your base before anything else.** In all ten batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are `git log --oneline -1` and
  `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`. If HEAD is not `<INTEGRATOR_HEAD>` and you
  have no commits, run `git reset --hard <INTEGRATOR_HEAD>`, and say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a single test file. Use plain
  `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown, so a run on the
  default database breaks the integrator's suite (batch 10 E did this once, for two seconds).
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth; a detector is judged by whether its verdicts match what a careful reader would say,
  never by its rate. Read every match and every drop.
- **A grader can be blind to a new data shape.** P3.19 changed the change record's groups to
  `changes`; `negcurrency` still read `changed_provisions` (batch 7 A caught it). In batch 8, B's
  `schedules` read A's code-stated true negatives as SILENT until B2 fixed it. **After any change to a
  tool result's shape or a new code-written sentence, check every grader and recorder that reads it.**
  `depth --seams` strips the whole PROVISION FETCHED BY CODE block: read that block with `route_trace.py`.
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
  `sched_clause_class`, `SCHED_LIMIT`, the halt detectors, the footer strippers). Screen new wording against
  all of them (`test_footer_trips_no_detector`), sentence by sentence. A `[` or `]` inside a `[…]` block stops
  the strippers; the word "ranked" tripped `NEG_LIMITS` and `NEG_TERMS` before; "cut short" trips `SCHED_LIMIT`.
- **Render every variant of a template with every value class and read it.** Batch 10's wording read well for
  "Schedule 5" and broke for an unlabelled unit ("the retrieved the Schedule"; a lower-case "the Schedule
  runs" opening a sentence); only the integrator's screen of the built text found it.
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree. **A script that globs every replay directory picks up new ones** (there are 64 now):
  exclude them, or say the counts include them.
- **Read a booked bar against the before-column in the same mode.** P3.25's 6340 bar was set from
  Research-mode runs but booked in Conversational mode, where the before-column never met it.
- **Compare the same input under both conditions.** P3.22's drops looked like an ordering effect until the same
  queries were fetched both ways (batch 10 B): they were query choice. A before/after on run counts mixes the
  change with the model's choices.
- **Delivering text is not the Worker using it.** P3.12's route handed paragraphs 42-44 verbatim and the Worker
  wrote one sub-paragraph: measure at the composition seam, not only at the retrieval seam.
- **Validate a detector both ways.** Batch 10 C's careful-reader test found the stored `src_unused` grader
  overstating the unused rate (43% against 31%) because it missed sources linked by URL.
- **Check that a folder is really gitignored** (`git check-ignore -v <path>`) before you write matter
  text into it. **`docs/prepilot-fixes/evidence/` itself is NOT ignored**, only its listed subfolders
  (`seam/`, `replay/`, `rubrics/`, `lawyer_pack/` and others); `evidence/scripts/` is tracked.
- **The plan has been wrong before, and about external APIs too.** Re-probe a row's claim about a
  live service before building on it, and say which you checked. Read the API's spec before
  concluding what it cannot do, and check every parameter we send against it.
- **Thomas tests on a different model** (`glm-5.2:cloud`); every stored replay here ran on the
  pinned Gemini. Say which model a number comes from.
- **Every stored replay was summarised at the 8,000-character fallback** (a cold context-length cache), not
  the pinned model's ~200,000: a measurement about summarisation is a measurement at 8,000.
- **Seams and sweeps cost more than they look.** The default `seam_replay worker` draw has no output cap and
  `chat_loop` retries an empty up to three times (a runaway draw about $2.30); a sweep rep can run 1.6 times its
  stored maximum from a capped runaway alone ($0.99 against $0.61). Price at the runaway case.
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
- **A built shape can differ from the brief's** (batch 9 C built `commencement_dates` as a dict): say so in the
  first section of your note so the integrator can relay it.
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
    `schedules [--rubric --session --all-dirs --drops]`, `corpus`, `authorities`, `cmcdates`,
    `jurisdiction`. **The exit-1 set** is 16: `halts negatives derivations commencements currency scoperecord
    nosearch caselaw modes deadend siblings scripted lookup drgaps blanks lost --require-label`.
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`;
    `python -m tools.seam_replay worker|manager|synthesis --run <file> --turn N [--delegation K] --dry-run`
    (payload only; a draw is the integrator's); `python -m tools.lex_probe` (live LEX, if agreed);
    `python -m tools.lex_probe --caselaw` (live National Archives, if agreed).
- **Run files:** `replay/<dir>/<session>_rep<n>.json`; each has `turns[]` with `turn`, `chat_mode`,
  `research_mode`, `answer` and `audit`, whose `delegations[]` carry `brief`, `report` and `tools[]` (`name`,
  `args`, `raw_result`, `final_result`, `summarised`, `memo_hit`, `local_cache_hit`, `api_calls`, ...) and
  whose `empty_completions[]` carry `attempt`, `retried`, `completion_tokens`, `react_turn`; the top level
  carries `total_cost_usd` and `runtime_state.git_head`; a scripted run carries `script` (`base`,
  `turns[].from_turn`). Scripts live in the tracked `evidence/scripts/` (`p34_6378.json` is the shape: ids
  and indices only, never turn text).
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Node** (for a JS syntax check only): `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`.

---

---

## Agent A: P3.12, why rep 1's Worker wrote 43(6) alone, and a candidate lever ($0)

**Read first:** P3.12's row in full (Session 42's annotations, incl. "For the next step"); `notes/batch10_A.md`
(sections 2-5 and 8); the gitignored `evidence/rubrics/handread_wave4_b10_sweep.md`; `schedule_units.py`
(`matched_pieces`, `fetched_block`'s MATCHED tail, `paragraph_label`) and `agent_shared.schedule_route_block`;
`replay_report`'s `DEPTH_TRUTH["6335"]`; the run file `evidence/replay/wave4_b10_sweep/6335_rep1.json` (turn 7,
one delegation) and batch 10 A's `seam_6335_r2_matched.json`.

**Measure first ($0):** build rep 1's turn-7 Worker payload (`seam_replay worker --run <rep1> --turn 7
--delegation 1 --dry-run`) and Session 41 r2's with the new block (`seam_6335_r2_matched.json`), and list every
difference between them that could change what the Worker writes: the brief's wording and scope, the section
query, the block (3 paragraphs against 6), its position among the results and its size, the other tool results
and their order, the rounds after the block, the date line, the case-law results. Also list, over all stored
6335 turn-7 runs, each brief and whether it named the paragraphs or asked a narrower question. **The
integrator draws rep 1's payload on the seam at the start of the session (priced to the user) and relays the
result to you (SendMessage).** If rep 1's payload DELIVERs on the seam, the live miss was a draw: propose no
product change and stop at the measurement (say so in the note). If it does not, the payload is the cause:
**build one candidate $0 lever, as its own commit**, from what your comparison shows, for example the MATCHED
tail naming the paragraphs it carries and asking that each be reported with its own facts, or the block placed
where the Worker reads it; Worker-facing wording only through `fetched_block`'s tail (text the Worker reads
belongs in the tool result). **Tests** at the seam, each failing with the change reverted (lines removed),
single-site mutants for every guard; **screen every variant with the BUILT code** (`b10_screenA.py` in
`scratchpad_s42` is the integrator's; copy it to your scratch), rendered for a labelled and an unlabelled unit;
**dry-run** the 264 stored firing calls (A's `dryrun_b10.py` repointed) and list every block that moves; build
**seam payload variants** (rep 1's and r2's payloads with the candidate block) for the integrator to draw (no
draw yourself). **Say in your note** the exact wording of every variant for the user to approve, and the
payloads the integrator should draw.

## Agent B: P4.12 built, L1 + L2' + L3 gated ($0, product, deterministic acceptance)

**Read first:** P4.12's row in full (Session 42's decision and the aside); P4.10's, P4.11's and P4.2's rows;
`notes/batch10_D.md` section 2; `utils/empty_completion.py` (`is_heavy_empty`, `should_retry_empty`, the P4.10
comment); `openrouter_client.chat_loop` and `ollama_client.chat_loop` (`worker_call`, `max_tokens`,
`WORKER_MAX_OUTPUT_TOKENS`, `_MAX_STREAM_ATTEMPTS`, the empty-completion retry); the Manager's call path in
`agent_core.py` (`process_user_request`, P4.2's fallback, `LOST_ANSWER_NOTICE`); `docs/api/AUDIT_TRACE.md`
(`empty_completions[]`).

**Build:** on a **Manager** call only (the planner, the Deep Research synthesis and the Worker unchanged; state
it): **L1** no retry after a heavy empty (P4.10's `is_heavy_empty` shape); **L2'** at most one retry, not two,
after an upstream idle timeout; **L3** `max_tokens` = `WORKER_MAX_OUTPUT_TOKENS` (OpenRouter only, as for the
Worker); **gated**: where no usable (completed, not lost) worker report is in hand, the Manager keeps today's
retries, so a reply lost before any research never falls to the bare notice. Design how the call knows a report
is in hand (a flag from the Manager loop, not a guess), and say it. Correct `empty_completion.py`'s P4.10 comment
(two Manager heavy empties are now measured). **Measure first and dry-run:** run the built retry decision over
the 10 stored Manager-site empty calls (batch 10 D's `p412_manager.py`, repointed in a copy) and list, per call,
the attempts removed and the outcome; check 0 recoveries given up; confirm the cap cannot bind on any stored
clean Manager call (D's bound). **Acceptance (deterministic):** unit tests at each seam (`should_retry_empty`
with a Manager flag for each mechanism (a), (b) attempt 1 and 2, (c), (d); both clients' `chat_loop` on a
Manager call; the cap on the Manager payload only; a heavy empty reaching P4.2's fallback after one attempt; the
gate with and without a report in hand), each failing with its change reverted (lines removed), single-site
mutants for every guard. **Check what the audit trace records** (`empty_completions[]`'s `attempt`/`retried`)
and say whether `AUDIT_TRACE.md` needs a sentence (the integrator edits it). No new lawyer-facing text is
expected; if any arises, screen it and list it for the user.

## Agent C: P4.3 built, V4 and the `rail` grader ($0, product + tooling, deterministic acceptance)

**Read first:** P4.3's row in full (Session 42's annotations, incl. "For the build" and the forms list);
`notes/batch10_C.md` (all of it); `agent_core.run_worker_agent` (the `_source_is_used` filter at the Worker seam
and its fall-back to the whole accumulator; the P2.2 comment about `turns_source_fallback`), `_source_is_used`,
`agent_shared._extract_sources*`, `_is_duplicate_source`; `replay_report`'s `src_unused`, `_source_cited`,
`turns_source_fallback`; batch 10 C's `reader.py`, `census.py`, `dryrun_filter.py`.

**Build:** **V4** at the Worker seam: drop the fall-back to the whole accumulator; keep a source the report
names in words (its title, its SI number "YYYY/N", an EU number "N/YYYY", an old SI "YYYY No. N"; normalised,
never as the head of a longer title); drop the legislation `sub` token from the keep test. **The `replay_report
rail` subcommand** on the careful-reader test (validated both ways, `--drops` listing every disagreement), and
the old counters labelled as the token test's. **Acceptance (deterministic, $0, n=1, the built code):** (i) 0
post-P2.1 report turns whose rail is the unfiltered fall-back (from 90); (ii) the unused-source rate by the
reader test at or below 15% in each chat mode; (iii) 0 sources the answer names removed from the rail; listed
per turn with `dryrun_filter.py` repointed (`P43_SERVER_PY`). **Synthetic tests** for every form in
`notes/batch10_C.md` section 4 (an id that prefixes another, a short form, a case by party name alone, a Welsh
title, a comma before the year, the three number forms, a title inside a longer title), each failing with the
change reverted; single-site mutants for every guard and cleaning step. **Identity run** of the 16 exit-1
graders over all 64 directories before and after (batch 10 E's `identity.py` pattern): only the intended moves.
Check that an empty rail renders (the client has no test runner: read the component and say what it shows) and
that `turns_source_fallback`'s meaning change is relabelled. **You are the only agent editing
`tools/replay_report.py`.** Your branch merges after the sweep (V4 changes `sources_kept`, which P3.10's
acceptance reads).

## Agent D: P3.20 measured first ($0; SCTS calls only if agreed)

**Read first:** P3.20's and P5.2's rows in full (incl. Session 42's SCTS-permission annotation); P2.4's row;
`docs/LEGAL_DATA_SOURCES.md` section 3 (the endpoints, filters, coverage, search behaviour, PDF text, terms,
risks and the reproduce command); `server_py/src/agent/tools/caselaw.py` (the `search_case_law` and
`get_case_law_text` shapes, P4.19's retry, P3.23's shown/total split, the window note); `tests/test_case_law_gap.py`
and every product text that says the Court of Session is not covered (grep `Court of Session`, `Sheriff`,
`Justiciary`, `SCOTS_CASELAW_GAP`); the local `external-apis` skill; `CACHEABLE_TOOLS`.

**Measure ($0, plus live SCTS calls if the user agreed, cap 150, through a door like batch 10 B's
`tna_b10.py`: capped in code, at least 1 s apart, every call logged with method, URL, status and bytes; both
hosts, `api.pa.web.scotcourts.gov.uk` (POST search) and `www.scotcourts.gov.uk` (GET PDF)):**
1. Over every stored directory (say how many), the case-law turns that ask a Scots-law question (classify by
   the question and the answer; read every one you count), and for each, what an SCTS search for the query the
   Worker issued (quoted as the tool would quote it) returns: the total, the first five, and whether it holds
   the authority the lawyer named or the answer needed (6375 is the acceptance session; 6359's out-of-corpus
   key case is an English EAT judgment, so say whether SCTS can matter there).
2. Re-probe the search's behaviour (quoted phrases, unquoted OR, paging, the exact total, the court values
   from `/web/definition/1414`) and say what changed since 2026-10-02.
3. **Date reliability:** on a sample (say 40) across years and courts, compare `additionalDate` with the
   neutral citation's year in the filename or the PDF text; report the mismatch rate (2 of 5 were off on
   2026-10-02).
4. **PDF text** with the product's `pdfplumber` (in `requirements.txt`) and with `pypdf` on a sample: success,
   characters, time, and whether the neutral citation is extractable.
5. **The design, proposed:** the tool(s) (a new `search_scottish_case_law` and its text fetch, or a route
   inside `search_case_law`), the slimmed result shape, the quoting rule, the window note's wording, the retry
   and count shapes to copy (P4.19, P3.23), caching (`CACHEABLE_TOOLS`, OGL), the context budget for 12,000-81,000
   character judgments; **every gated wording site** (P2.4's footer, the case-law scope blocks, the prompts,
   `test_case_law_gap.py`) with proposed gated wording (screened against every detector) that keeps stating what
   SCTS does not hold (Northern Ireland; unpublished Sheriff Court decisions; criminal sheriff decisions almost
   absent); the deployment changes (`NETWORK_AND_DEPENDENCIES.md`, `server_py/test_apis.ps1`, the offline bundle
   with `pdfplumber`, `docs/TODO.md` T3); and the acceptance (the row's, refined) and its price.
No product code; no grader edit (C's file). If the user did not agree to live calls, use the stored evidence and
section 3's figures and say what could not be checked.

## Agent E: P3.10 built, its scripts, and the sweep priced ($0)

**Read first:** P3.10's row in full (Session 42's decision and "For the build"); `notes/batch10_D.md` section 1;
`agent_core.run_deep_research`, `_build_step_brief` (and its CONTEXT sentence), `PLANNER_SYSTEM_PROMPT`;
`utils/instrument_lookup.extract_instrument_citations` and P3.7's routing (`MAX_ROUTED_LOOKUPS` = 5);
batch 10 D's `p310_recount.py`, `p310_options.py`, `p310_listread.py`; `evidence/scripts/p34_6378.json` and
`p37r_6374.json`/`p37r_6383.json` (script shapes).

**Build:** in `_build_step_brief`, one code-written line for a step 2+ naming the instrument ids the earlier
steps' report BODIES link (the code-appended scope blocks cut, as D's list-match did). Measure both options
(every step 2+, or only steps the Session 15 regex flags) over the 148 stored post-P3.8 steps 2+ and recommend.
**Decide and say how the line meets P3.7:** an id in a brief triggers a routed lookup (up to 5 a step; 6374's
list is 6-8 instruments): exclude the line from the lookup's extraction, raise the cap for it, or accept, each
measured (calls added over the stored plans). The line must not contradict the CONTEXT sentence ("Research ONLY
this step's task ..."). Screen the wording with the BUILT code; **the wording goes to the user before merge**.
Tests at the seam, each failing with the change reverted (lines removed), single-site mutants for every guard
and cleaning step (the body cut, the id extraction, the class filter if any, the dedupe, the cap). **Dry-run**
the line for every stored step 2+ and list it (ids only). **Scripts:** `evidence/scripts/p310_6374.json` and
`p310_6383.json`, each the session's turn 4 (Deep Research) as recorded (ids and indices only; check the turn
mapping against the export and that `replay_set.scripted_session` builds each, no network). **The grading
script** for the acceptance (list match, own `search_legislation` calls, halts, `sources_kept`), from D's
`p310_recount.py` repointed, in your scratch (not `replay_report.py`, which is C's). **Price the sweep:**
6335 n=3 (stored reps $0.567-0.610 in `wave4_b9_sweep1`, $0.989 in `wave4_b10_sweep` with a capped runaway) and
the two scripts n=3 each (turn-4 costs from the stored runs), each command with `--reps 3` and a per-command
`--max-spend`, the median, the maximum, the runaway exposure, and the order (P1 first).

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit or later (if
   another session committed, read what changed); pushed; `plan_status` 58 of 81, 2 in progress, 9 of 14;
   `plan_lint` exit 0; rubric sha1s; the five test databases; nothing running (no python process, port 8000
   free), no pin file; a baseline full suite on `lexchat_test` (2833). Copy the integrator tools from
   `seam/batch10/scratchpad_s42/` (and `b9_mut*.py` from `seam/batch9/scratchpad_s41/`) to this session's
   scratchpad and repoint their paths (`review_branch.sh`'s base and scratchpad, `grade_b8.sh`'s scratchpad).
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four questions):
   launch A, B, C, D and E as set out? **May D make up to 150 SCTS calls** (free of model spend, at least 1 s
   apart; the alternative is stored evidence only)? **May I draw rep 1's turn-7 payload on the Worker seam now**
   (2 draws, typically about $0.10 in all, up to about $4.60 if both run away; stop and ask if the first costs
   over $0.30)? Confirm the merge order (B, A if approved, E, the sweep on the user's go-ahead, C, D) and **may
   the branch be pushed after each clean merge this session?**
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message. Give each
   its section, plus **Rules for every agent**, **Lessons from batches 1-10** and **Shared setup**, verbatim; the
   integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and `TEST_DATABASE_URL`
   (`lexchat_test_<a-e>`); and whether the user agreed to its live calls. While they run, do nothing expensive
   and edit none of their files.
4. **P3.12's seam draw (if agreed), right after launch:** `python -m tools.seam_replay worker --run
   $PREPILOT_EVIDENCE/replay/wave4_b10_sweep/6335_rep1.json --turn 7 --delegation 1 --reps 1 --out <scratchpad>`,
   twice, the running total after each; read each report by hand (42, 43, 44 each with its facts?); **relay the
   result to agent A by SendMessage** (DELIVERED or not, and what the report covered).
5. **Review each result as it lands** (as in batches 3-10):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines with `review_branch.sh <branch> <INTEGRATOR_HEAD>` (it runs `matter_grep.py`; NOT
     `grep -iF`, which aborts in Git Bash); every hit read, and a whole-line edit's pre-existing text told apart;
   - for every product or grader change, re-run the new tests with the change reverted on a scratch worktree
     (count the lines removed), plus **at least three single-site mutants of your own, at least one on a guard
     or a cleaning step** (`b10_mut*.py` are the pattern; mutate length and emptiness thresholds too: batch 10's
     two survivors were exactly those); send the agent back (SendMessage, its worktree kept) to close any gap a
     surviving mutant shows, unless it is provably harmless (say why);
   - **screen each product change's new wording with the BUILT code** against every detector, `SCHED_LIMIT` and
     `sched_clause_class` included (`b9_screen.py`, `b10_screenA.py`), rendered for every value class;
   - run the full suite on `lexchat_test`;
   - re-run one headline number from the note on the merged tree (a copy of the agent's script repointed, its
     outputs written to the scratchpad, never over the agent's evidence);
   - compare the agent's scratch file counts on both sides.
   **Do not remove an agent's worktree before its branch is merged.** Run `git worktree remove` from the main
   checkout. Put A's and E's wording (and any other new text) to the user before merge. If an agent's built shape
   differs from its brief, relay it to any agent that reads it.
6. **Merge B, then A (if built and approved), then E**, each `--no-ff`, the suite after each, pushed after each
   clean merge if the user agreed. **Tick P4.12 at B's merge** if its deterministic acceptance holds on the merged
   tree (the user confirms).
7. **The sweep, only on the user's go-ahead.** Put E's price to the user (AskUserQuestion: run, or defer); agree a
   cap. `python -m tools.replay check`, `replay pin`, uvicorn fresh with PowerShell `Start-Process -PassThru`
   (log to the session scratchpad), confirm `/api/bot-info` shows the merged build, start the keep-awake helper,
   record both PIDs; run E's commands into
   `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b11_sweep`, P1 first; `sweep_total.py` after each
   rep; **if one more rep could take the total past the cap, stop the `replay run` process between reps and ask**
   (the server cancels the in-flight request); never commit while it runs; then `replay restore`, stop both
   processes by PID, and confirm no pin file, no python process, port 8000 free. **Grade:** the exit-1 set
   (`grade_b8.sh`, repointed; `commencements` now grades scripted runs), `negcurrency` (no `--all` on one
   directory), `footer_echo`, `depth --answers --drops` and `schedules --session 6335 --drops` (6335 t7),
   `route_trace.py` on every 6335 turn 7, E's list-match script and `discovery --before` on the P3.10 runs.
   **Hand-read every `depth` verdict and every P3.10 list-match verdict** and save to the gitignored
   `evidence/rubrics/handread_wave4_b11_sweep.md`. Tick P3.12 only if 6335 t7 is DELIVERED in 3 of 3 by hand, and
   P3.10 only if its booked bar is met by hand.
8. **Merge C, then D** (D: notes only; check `git diff` touches nothing under `server_py/`). **Tick P4.3 at C's
   merge** if its deterministic acceptance holds on the merged tree (the user confirms).
9. **Assemble:**
   - tick only rows whose acceptance is met, stating the check; annotate each row in a byte script (each anchor
     once, CRLF kept, an even number of `**` added, no `|` in a cell, rows on one line; some rows, e.g. P2.3, have
     no closing pipe); a newly ticked row's Bucket-index entry gets ` **done**`; then `plan_lint` (0 errors) and
     `plan_status`;
   - **put the agents' decisions to the user**, grouped (AskUserQuestion, at most four questions per call,
     recommendation first), and record each answer on its row: D's P3.20 design and acceptance first (it decides
     the next build), then A's, B's, C's and E's;
   - CHANGELOG *Unreleased* (each product change in plain words; tooling separately); correct `CLAUDE.md` (the
     LLM stream retry paragraph for P4.12; the Worker optimisations for P3.10 and P4.3),
     `docs/api/AUDIT_TRACE.md` (if B's records change), `docs/LEGAL_DATA_SOURCES.md` (D's findings) and
     `docs/NETWORK_AND_DEPENDENCIES.md` (only when P3.20's build lands, not now).
10. **Hand over:** a Session 43 entry and a handover for Session 44 in SESSION_LOG.md (next by severity); the
    memory entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session scratchpad to the
    gitignored `evidence/seam/batch11/scratchpad_s43/`; update the local skills where a finding changes them
    (`external-apis` for D's SCTS findings); update the Fix Tracker only if the user asks (FIX_PLAN "How to use
    this file" step 7: Artifact `read` the live URL and Read every line of the saved file first; set `AS_AT` and
    `UPDATED`; a newly ticked row gets `fixed` and `ver: "Next release"`; P3.20's row text says SCTS agreed).

**Open with the user, carried (do not act on them yourself):** asking SCTS for a written confirmation of the
permission (save it to the gitignored evidence and cite it on P3.20 when it arrives); sending the whitelist request
for `api.pa.web.scotcourts.gov.uk` and `www.scotcourts.gov.uk` (draft:
`evidence/seam/batch10/scratchpad_s42/whitelist_request_scts.md`); sending the lawyer pack (unblocks P3.2, P3.3,
P3.17); applying for the National Archives licence (`docs/TODO.md` D23); deploying `v2026.09.3` to the target
(`pg_dump` first, then pull, restart and `test_apis.ps1`); telling the eval-harness owner about schema v6 and the
new `api_calls` and request keys in `AUDIT_TRACE.md`; D19's remaining items; which rows go in the next cut
(`v2026.10.1`: the seventeen "Next release" rows); D20, D21/D22; batch 1's three items; the p37_6373 substitution;
enrolling 6370's five hedged drops in `p33.json`; the watch items on P3.24, P3.27, P3.21, P3.4, P3.22 and P3.12;
and **saving and mapping any further external report in the session that receives it**.
