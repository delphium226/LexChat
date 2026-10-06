# Parallel batch 8: P3.27 and P3.12 built, their acceptance instruments, P3.22 and P3.21 measured

**Set up on 2026-10-06, at the end of Session 39, for Session 40, at the user's request** ("provide a
prompt to kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-7
(`PARALLEL_BATCH_1.md` to `_7.md`): agents in git worktrees, the main session integrating, nothing
merged that the integrator has not re-checked. **Every agent is $0 in model spend.** Three agents may
make free, bounded live calls (B to LEX, C to the National Archives, D to LEX and legislation.gov.uk)
**only if the user agrees at launch**. The one paid step is the **acceptance sweep for P3.27, P3.12
and P3.25**, run by the integrator alone between merges, **priced to the user first and run only on
their go-ahead** (stored estimate about $5.50 to $7; nothing is authorised yet).

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent**, **Lessons from batches 1-7** and **Shared setup**, verbatim. Nothing here
should need re-deriving; if something does, the agent says so in its note rather than guessing.
Matter-specific detail (lawyers' wording, rubric patterns, hand-reads, ground-truth text, live
payloads) is NOT in this file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first) **unless a dependency means it
   can't be**. FIX_PLAN's top order line ("as at 2026-10-05, end of Session 39", amended to point at
   this brief) is the order.
2. **P3.27 (P1) and P3.12 (P2) are ONE build, two commits, P3.27 first** (Session 39):
   - **P3.27's lever:** send `include_schedules: true` on `get_legislation_text` AND make the
     unflagged call too, and append a code-written line, built from the raw responses after
     summarisation (P2.3's `enabling_power_note` pattern), saying which schedules and annexes the text
     carries, or that the index holds none for this instrument. **No size bound at first**; the cost
     is counted on the after-column.
   - **P3.12's lever:** the code route by `/legislation/section/lookup` (a `limit` above the
     provision count) with the unit picked by `uri`; annex chapters cut with `_cut_annex`; a schedule
     paragraph cut only where its `Section N)` line is unique AND the next headed paragraph is N+1;
     otherwise the span labelled with what it runs through, or the whole schedule summarised for the
     query; on a lookup failure, the flagged whole text cut at the heading. `GET /legislation/proxy`
     is NOT the route (kept as a fallback, or for P5.4 (d)).
   - **P3.12's ground truth** goes into `replay_report`'s `DEPTH_TRUTH` as a `DepthReq` for 6335
     turn 7 (regexes over the statutory words only).
3. **Their acceptance** (booked on the rows): P3.27's deterministic tests and $0 dry run, then one
   replay sweep shared with P3.12 and P3.25, **including the Invariant 1 guard on 6374** (on 6374's
   turns naming its Order's Schedule, the answer still says the index holds no text for it, and no
   longer blames a search limit). **P3.25's booked replay:** `p37_6409` n=3 (the commenced-section
   list still delivered), 6340 n=3 Conversational (a supported derivation in every rep),
   `p37r_6374` and `p37r_6383` n=1 (`derivations` clean), `p32_6406` cut after export turn 5 n=3
   (shared with P3.12's criterion (v)). P3.12: 6335 turn 7 delivers paragraphs 42-44 (`depth`), n=3.
   **The sweep is priced to the user after the A and B merges; it runs only on their go-ahead.**
4. **P3.22** (P2, B12's last open product row with P3.20): its paced $0 measure-first, then a replay
   before-column, the build (flipping `CASE_LAW_RESULT_ORDER` and the nudge's "most relevant"), the
   after-column. **This batch does the measure-first and books the 6363 and 6359 ground truth only.**
   The National Archives licence (`docs/TODO.md` D23) is booked and does not block it.
5. **P3.21 runs with P5.4 (c)'s probe** (batch 5 B6), so the commencement date's source is chosen on
   both sets of numbers. **This batch measures; it builds nothing for P3.21.**
6. **P3.24's watch items stay watch items** (the row lists them); `negcurrency`'s known gap ("now
   apply", "still applies") is accepted with a hand-read of every after-column (batch 6 decision 5).
7. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack.** Nothing here touches them.
8. **Agents propose; the integrator applies; the user approves anything not mechanical**, including
   any wording a lawyer will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md,
   CLAUDE.md, `summary-table.html`, `docs/TODO.md`, `docs/LEGAL_DATA_SOURCES.md`, a rubric, the
   lawyer pack or a memory file.
9. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks.
   Branch pushes are allowed; if the permission classifier refuses one, ask the user.
10. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-06, end of Session 39)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit. **`main`** at `a6b4a76`,
  release **`v2026.09.3`**.
- **Tests: 2339** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **53 of 77 rows, 1 in progress (P3.25)**, **8 of 14
  buckets**; **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings). Run both after every fold.
- **Open P1 rows:** P3.27 (lever decided); P3.2 and P3.17 (Blocked).
- **Fix Tracker v38** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`).
- **What Session 39 built** (notes `docs/prepilot-fixes/notes/batch7_{A,B,C,D}.md`, committed):
  - **P3.24 done:** `search_scope._commencement_split` / `_commencement_lines` (the per-instrument
    line in `_currency_limb`), `_relation_commencement_bits` (the same split in the Worker's
    change-record block), `prompts._COMMENCEMENT_RECORD_RULE`. **The Worker never sees
    `_currency_limb`**: it is appended to the report after the Worker writes (`agent_core`), and is
    read by the Manager and the Deep Research synthesis only.
  - **P3.25 built (`[~]`):** `schemas.get_worker_tools(research_mode, chat_mode)`,
    `is_quick_lookup_worker`, `QUICK_LOOKUP_WITHHELD_TOOLS`, `withheld_tool_result`;
    `instrument_lookup.section_search_lookup` (a code lookup before the quick-lookup Worker's first
    section search of each SI, at most 5 a run); `lookup_legislation` passes on `valid_date`;
    `search_scope.lookup_enabling_note`; `run_worker_tool(result_suffix=...)`. **The quick-lookup
    Worker has no `get_legislation_text`**, so P3.27's change reaches only the research and Deep
    Research Workers, and the 16 conversational need-turns of P3.27 depend on P3.12's route.
  - **P4.19, P3.23, P3.9 done:** `caselaw.case_law_count`, `case_law_date_window`,
    `_fetch_judgment_text(url, client=...)`, `search_scope.case_law_search_note`,
    `CASE_LAW_RESULT_ORDER` ("newest first, by date rather than by relevance": P3.22 flips it),
    `tools/caselaw_probe.py` (`python -m tools.lex_probe --caselaw`). **The feed's `last` link counts
    at TEN judgments a page whatever `per_page` is sent**; every "about 26,000" figure in older notes
    was five times too high.
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **58 replay directories** under `replay/`, every one on the pinned
    `google/gemini-3.1-pro-preview`; newest `wave4_b7_p324` (P3.24's acceptance, $1.24).
  - Rubrics `rubrics/p32.json` (sha1 `31379ecf…`), `p33.json` (`0031831b…`); hand-read
    `rubrics/handread_wave4_b7_p324.md`.
  - **Batch 7 scratch** `seam/batch7/{A,B,C,D,scratchpad_s39}/`:
    - **B (the specs for agents A and B here):** `p312_truth.txt` (P3.12's ground truth: paragraphs
      42-44, cut live, statute text), `p32_control_truth.txt` (P3.2's control annex chapter),
      `probe_log.jsonl` and `raw/` (every live LEX response: `/legislation/text` with and without the
      flag for all 60 instruments, the section lookups, the proxy pages), `probe_summary.json`,
      `cut_rules_live.py`, `boundary.py`, `flag_cost.py`, `route_ids.py`, `lexcall.py` (the capped,
      paced, logged LEX caller: reuse it), `p327_inventory.py`, `p327_measure.py`, the hand-reads
      `handread_need_dump.txt` and `handread_noneed_dump.txt`.
    - **C:** `p325_dryrun.py`, `p325_compare.py`, `p325_costs.py` (recorded rep costs), `dry_head.jsonl`.
      **`p325_dryrun.py` globs EVERY replay directory**, so a new directory changes its counts:
      `scratchpad_s39/p325_dryrun_57.py` excludes `wave4_b7_p324`.
    - **D:** `caselaw_census.py` lineage, `dryrun.py`, `compare.py`, `dryrun_base.jsonl`,
      `calls.jsonl` (36 live calls), `run_thomas.py`, `date_formats.py`.
    - **A:** `collect.py`, `rebuild.py`, `census.py`, `deleg.pkl`, `worker_block_dryrun.py`.
    - **Integrator (`scratchpad_s39`):** `review_branch.sh` (base parameter), `matter_grep.py`,
      `grade_b7.sh` (the exit-1 set + `negcurrency` + `footer_echo` over one directory),
      `summ_count.py` (change-record calls summarised), `dump_turns.py`, `echo_check.py`,
      `reg4b.py`, `fold_s39.py` (the byte-fold pattern), `b7_mutA.py`/`b7_mutC.py` (CRLF-safe mutant
      runners), `prompt_check.py`.
  - Earlier review tools: `seam/batch4/scratchpad_s36/revert_check.py` and `hunk_anchors.py`; the
    keep-awake helper `seam/batch1/scratchpad_s33/keep_awake.py`; the matter words
    `seam/batch3/scratchpad_s35/matter_words.txt`.
  - Replay scripts in `evidence/scripts/` (tracked: base session and turn indices only, never turn
    text). **There is no `p32_6406` script cut after export turn 5 yet**; agent B writes it.
  - The raw transcript export (lawyers' questions; never in the repo):
    `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no worktrees. 24
  merged `worktree-agent-*` branches and `batch3-B` remain locally from batches 1-6 and can be deleted.

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.27** (P1), then **P3.12** (P2) | One build, two commits, as decided | product, deterministic build; acceptance by the integrator's sweep | $0, no external call | `server_py/src/agent/tools/executor.py` (the `get_legislation_text` branch ~540), `server_py/src/agent/agent_shared.py` (`run_worker_tool`, after a `search_legislation_sections` result), `server_py/src/utils/search_scope.py` (a schedules note beside `enabling_power_note`), a new product home for the cut helpers (`_cut_annex` today lives in the dev tool `server_py/tools/provision_hints.py`, which product code must not import), tests |
| **B** | the sweep's instruments (P3.27, P3.12, P3.25) | `DEPTH_TRUTH` entry for 6335 t7; the `p32_6406` cut script; the 6374 guard and P3.27's schedule check made gradeable; the sweep priced from stored costs | tooling and scripts, no product code | $0; LEX calls only if agreed (up to 40) | `server_py/tools/replay_report.py`, `docs/prepilot-fixes/evidence/scripts/`, tests |
| **C** | **P3.22** (P2) measure-first | The paced live re-run of every stored case-law query under both orderings; the 6363 and 6359 ground truth proposed | analysis, a note; no product code | $0; National Archives calls only if agreed (up to 1,300) | `notes/batch8_C.md`, gitignored scratch |
| **D** | **P3.21** (P2) measure-first with **P5.4 (c)** | Distinct commencing instruments and which state a date; legislation.gov.uk's dated effects compared | analysis, a note; a probe tool at most | $0; LEX and legislation.gov.uk calls only if agreed (up to 300 each) | `notes/batch8_D.md`, optionally a new `server_py/tools/lgu_probe.py`, gitignored scratch |

**Why these four.** By severity: P3.27 (P1) is the only unblocked P1 row, and P3.12 is in its build
by the user's decision. The sweep that accepts them needs instruments that do not exist yet (B), and
building those beside A keeps the paid step in this session. The next P2 rows in the order line are
P3.22 and P3.21; both are measure-first, so C and D measure without touching product code and cannot
collide with A. **Not in this batch:** P3.22's build and replays; P3.21's build; P3.4, P3.6, P4.3,
P3.10, P4.12, P3.20; anything Blocked; the P3 rows (P4.8, P4.20, P4.22, P3.26, P3.28, ...).

**Merge order: A, B, then the sweep (only on the user's go-ahead), then C, D.** The sweep measures a
head holding A's two commits and B's instruments on top of Session 39's merged tree (P3.25
included), so each row's result is attributable (Invariant 3). Review C and D while the sweep runs,
but **never commit while a replay is running**; merge them after `replay restore`.

**Collision points.**
- **A and B both touch the replay-grading side only through B**: A must not edit
  `tools/replay_report.py`; B must not edit product code. If A needs a grader change, it says so in
  its note.
- **A's new text** (the schedules line, any label on a cut unit) is read by the Worker and can be
  echoed into a report and an answer: it must pass `tests/test_search_scope.py::
  test_footer_trips_no_detector` (which holds `negcurrency`) and contain no `[` or `]` inside a
  `[…]` block (`strip_scope_blocks` and `_TOOL_BLOCK` stop at a bracket: P3.23's follow-up).
- **A and P3.25:** the quick-lookup Worker has no `get_legislation_text`; A's P3.12 route must run for
  BOTH the research and the quick-lookup Workers (it hangs off `search_legislation_sections`, which
  both have). Check `is_quick_lookup_worker` paths in the tests.
- **C and D** write notes and, at most, a new probe tool each (`tools/caselaw_probe.py` for C,
  `tools/lgu_probe.py` for D); different files.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the top recommended-order line, the paragraph above the Ledger
   on what waits on the lawyer pack, and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`,
   everything from "Session 39 — 2026-10-05 — parallel batch 7" to the end of the file; and the
   batch 7 note your brief names. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`,
   `docs/LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the lawyer pack or any memory
   file: the integrator folds your results in. Commit on your worktree's branch; **do not push, do
   not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch8_<A|B|C|D>.md` and commit it. Put in it:
   - what you changed or found, and why;
   - every number, with the exact command that produces it;
   - every match or edit you read (counts and locations only if the text names a matter);
   - what you did NOT do;
   - anything the integrator or the user must decide, each as a numbered, self-contained decision
     with 2-4 options, your recommendation first, each option one or two sentences.

   **Before any claim of "fixed", "met" or "consistent", state the check and whether it passes.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list every
   match and every drop before quoting a rate. For a product change, dry-run it over every stored
   input it reads with the BUILT code, and list every output that moves.
5. **Tests:** each code change gets a unit test at its seam. Each test is proven to FAIL with the
   change reverted on a scratch copy, **and the note says how many lines the revert removed** (a
   revert that removed nothing proves nothing). Where a full revert only fails at import or on a
   missing key, also stub each new function or put each half of the old defect back one at a time
   (single-site mutants), so the tests are shown to check behaviour. Run the full suite on your own
   test database before your last commit, and report the count.
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
   B's `lexcall.py` is the pattern), and counted in your note. **LEX's read endpoints are POST**, so
   "calls", not "GETs". Every other agent makes no external call at all.
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** your worktree's gitignored
    `docs/prepilot-fixes/evidence/seam/batch8/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch8/<your letter>/`. **Never write to
    the session scratchpad, not even briefly** (a batch 7 agent did, and moved the integrator's files).
    Say in your reply which you did, with the file count on both sides.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend (and the number of live calls, per host); the path of your note and where your scratch is;
    for each item, met or not and why; and the numbered decisions for the user.

## Lessons from batches 1-7 (give these verbatim with each brief)

- **Check your base before anything else.** In all seven batches every worktree the Agent tool made
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
  `changes`; `negcurrency` still read `changed_provisions`, so it would have graded a contradicted
  negative SUPPORTED on every directory after P3.19 (batch 7 A caught it). **After any change to a
  tool result's shape, check every grader and recorder that reads it.**
- **Know which agent reads a block before you write to it.** `worker_scope_block` (and
  `_currency_limb` in it) is appended to the Worker's report AFTER the Worker writes; only the
  Manager and the Deep Research synthesis read it. Text meant for the Worker belongs in the tool
  result (as P2.3's `enabling_power_note` and P3.5's `_relation_currency_limb` are). Batch 7's first
  P3.24 build put the rule where the Worker never sees it and left a contradicting one where it does.
- **Any text the product writes into an answer, or into a block the model can echo, is read by every
  grader** (`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`,
  `derivation_claims`, `_currency_asserted`, `negcurrency_claim`, `OPENER_VOCAB`, the halt
  detectors, the footer strippers). Screen new wording against all of them
  (`test_footer_trips_no_detector`). "not recorded as commenced" is in `negcurrency`'s drop
  vocabulary on purpose. A `[` or `]` inside a `[…]` block stops the strippers.
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree. **A script that globs every replay directory picks up new ones**: exclude them, or
  say the counts include them.
- **Check that a folder is really gitignored** (`git check-ignore -v <path>`) before you write matter
  text into it. **`docs/prepilot-fixes/evidence/` itself is NOT ignored**, only its listed subfolders
  (`seam/`, `replay/`, `rubrics/`, `lawyer_pack/` and others); `evidence/scripts/` is tracked.
- **The plan has been wrong before, and about external APIs too.** Batch 7 D found P3.23's row wrong
  about the feed it was fixing (the `last` link's page size) and P3.9's named judgment no longer
  discriminating (the corpus had moved). Re-probe a row's claim about a live service before building
  on it, and say which you checked.
- **Read the API's spec before concluding what it cannot do, and check every parameter we send
  against it** (batch 6: `include_schedules`). LEX's spec is at `/openapi.json`; its read endpoints
  are POST; `GET /legislation/proxy/<provision path>` returns legislation.gov.uk's page for one
  provision (batch 7 B).
- **Thomas tests on a different model** (`glm-5.2:cloud`); every stored replay here ran on the
  pinned Gemini. Say which model a number comes from.
- **Tooling traps on this machine:** Git Bash's `grep -iF` aborts (exit 134), so a `$(grep -ciF ...)`
  prints blanks silently: use Python for case-insensitive fixed-string search. `git worktree remove`
  fails ("Permission denied") while the shell's cwd is inside the worktree, and `--force` can leave an
  empty directory (`rmdir` it from outside). `replay_report negcurrency --all` walks SUBdirectories:
  on a single replay directory, run it without `--all` (with `--all` it reads 0 turns).
- **Another session may commit to the branch while you work.** Base your note on
  `<INTEGRATOR_HEAD>` and say so; the integrator reconciles.

---

## Shared setup

- **Worktrees:** `isolation: "worktree"`. A worktree has no `server_py/.env`, and that is fine.
- **In a worktree, set on every tool command:**
  - `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`;
  - `PYTHONIOENCODING=utf-8` (the console is cp1252);
  - `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_<a|b|c|d>`.

  Pass `--dir` and `--also` paths under `$PREPILOT_EVIDENCE/replay/`.
- **Commands** (run from `server_py/`):
  - `python -m tools.plan_status`; `python -m tools.plan_lint`;
  - `python -m tools.replay_report --dir <path> <subcommand>`. The subcommands include `negatives`,
    `caselaw`, `scoperecord`, `nosearch`, `halts`, `derivations`, `commencements`, `currency`,
    `negcurrency [--all --sessions S --drops --verbose]`, `modes`, `deadend`, `siblings`,
    `scripted`, `lookup`, `drgaps`, `blanks`, `lost --require-label`, `interpret`, `stance`,
    `hedges`, `openers`, `sectionscope`, `discovery`, `depth [--seams]`, `lostcost`. **The exit-1
    set** is 16: `halts negatives derivations commencements currency scoperecord nosearch caselaw
    modes deadend siblings scripted lookup drgaps blanks lost --require-label`.
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`;
    `python -m tools.lex_probe` (live LEX checks, if agreed); `python -m tools.lex_probe --caselaw`
    (live National Archives checks, if agreed).
- **Run files:** `replay/<dir>/<session>_rep<n>.json`; each has `turns[]` with `turn`, `chat_mode`,
  `research_mode`, `answer` and `audit`, whose `delegations[]` carry `report` and `tools[]` (`name`,
  `args`, `raw_result`, `final_result`, `summarised`, `memo_hit`, `local_cache_hit`, ...); the top
  level carries `total_cost_usd`.
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Node** (for a JS syntax check only): `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`.

---

## Agent A: P3.27 then P3.12, one build ($0, product, deterministic build)

**Read first:** P3.27's and P3.12's rows in full (their Session 39 annotations are the decisions and
the probe); `notes/batch7_B.md` whole (the measurement, the live probe, the cut rules, the decisions);
`notes/batch6_D.md` sections 0 and 1.1-1.4 (the gap and the first design); P2.3's row and
`search_scope.enabling_power_note` (the pattern for a code line built from the raw result after
summarisation); P3.25's row and `notes/batch7_C.md` (the quick-lookup Worker no longer has
`get_legislation_text`); in `server_py/src/agent/tools/executor.py` the `get_legislation_text`
branch and the `lookup_legislation` branch (which already calls `/legislation/section/lookup` as
P3.7's text check); `server_py/src/agent/agent_shared.py` `run_worker_tool` (where the per-tool
notes are appended, and `summarised_result_blocks`); `_cut_annex` in `server_py/tools/provision_hints.py`
(dev tooling: move or re-implement the cut in product code, say which, and keep the tool working);
the `external-apis` skill's LEX section (`include_schedules`, the Schedule as one provision, the
section lookup, the proxy).

**Commit 1, P3.27.** In the `get_legislation_text` branch, send `include_schedules: true`, and also
make the unflagged call (the same endpoint, flag false) so the code knows exactly where the schedules
start; fail soft (Invariant 5): if the second call fails, keep the flagged text and say less in the
line, never more. Pass the text on as today. Append, after summarisation, a code line built from the
two raw responses naming which schedules and annexes the text carries (headings in either form,
"SCHEDULE 2" or "SECOND SCHEDULE", and annexes), or saying that the index holds none for this
instrument; say nothing about anything else. Record what the line needs in the step's scope record if
the footer must speak of it (decide, and say why, in the note; a lawyer-facing change is put to the
user). Screen every variant of the wording (`test_footer_trips_no_detector`), with no bracket inside
the block. **Dry run with the built code:** the line over the 60 saved live payloads in
`seam/batch7/B/raw/` (every line listed), and the change in summariser input over the stored reads
(B measured x1.96 by its own script; reproduce it from the built code's payload).

**Commit 2, P3.12.** In `run_worker_tool`, after a `search_legislation_sections` result, when the
query names a schedule or annex unit (Schedule X, with or without a paragraph, Part or chapter;
Annex X, with or without a chapter) that the results do not contain: fetch the instrument's
provisions by `/legislation/section/lookup` (a `limit` above the provision count; one call per
instrument per worker run, memoised; bounded like P3.7's routed lookups), pick the unit by `uri`,
and append a labelled block: an annex chapter cut with `_cut_annex`; a paragraph cut only where its
`Section N)` line is unique and the next headed paragraph is N+1, otherwise the span labelled with
the paragraphs it runs through, or the whole schedule summarised for the query (P1.6's pattern);
on a lookup failure, the flagged whole text cut at the heading. It must run for the research AND the
quick-lookup Workers. **Dry run with the built code** over all 5,128 stored section-search calls:
list every call the trigger fires on (B: 124 calls on 5 instruments for a named sub-unit, 163 on 16
counting schedule-only queries) and every call where the unit was already in the results (it must
not fire), using the saved live lookup payloads in `seam/batch7/B/raw/` where they exist (no live
call: where none is saved, say so and count it).

**Tests**, each failing with its change reverted (state the lines removed) plus single-site mutants:
the flag sent and the unflagged call made; the line's cases (schedules named in each heading form,
none held, the second call failing); the route's trigger (fires on a missing unit, not on a present
one, not on a section query); each cut case (annex chapter, clean paragraph, swallowing paragraph
labelled, no marker summarised); both Workers reach the route; the screen.

**Acceptance (the rows', booked):** deterministic as above; then the integrator's sweep (P3.27's
need turns, 6335 turn 7 for P3.12, 6406's control turn, 6374's guard). You run nothing paid. **Say in
your note** the exact new wording of every line and label, and which words the integrator should read
for in the hand-read.

## Agent B: the sweep's instruments ($0; LEX calls only if agreed)

**Read first:** P3.27's, P3.12's and P3.25's rows in full (their booked acceptances); `notes/batch7_B.md`
section 2.4 and decision 4; `notes/batch7_C.md` (its section on the proposed acceptance, and
`p325_costs.py`); P3.2's row (criterion (v), the control turn, and why `p32_6406` cuts after export
turn 5); `server_py/tools/replay_report.py` (`DepthReq`, `DEPTH_TRUTH`, `depth`, `stance`,
`negatives`, `negcurrency`, `lookup`); `docs/prepilot-fixes/evidence/scripts/p32_6406.json` and the
`replay run --script` format; `tools/replay_set.py` (how a script's turns are taken from the export).

**Build (tooling only, no product code):**
1. **P3.12's ground truth in `DEPTH_TRUTH`**: a `DepthReq` (or more) for 6335 turn 7, regexes over
   the statutory words of paragraphs 42-44 (`seam/batch7/B/p312_truth.txt`), like the existing
   live-verified entries. Check the run files' turn numbering for 6335 (the export turn and the run
   turn can differ). **Grade every stored 6335 directory** with it and hand-read each verdict: the
   before-column must FAIL where the lawyer did not get the paragraphs (P3.12's row: reps 2 and 3 of
   `wave3_p38_pre` say the text was not retrieved).
2. **The `p32_6406` script cut after export turn 5** (`evidence/scripts/`, base session and turn
   indices only), so the control turn is the last turn run; confirm from the stored `p32_6406` reps
   which run turn is the control turn and that `stance`'s control reading still finds it.
3. **The 6374 guard made gradeable**: find which stored 6374 turns name its Order's Schedule (batch 7
   B's hand-read lists 16 turns), choose the script or session form the sweep should replay (an
   existing `p37r_6374` script or the session), and add a check (a `replay_report` subcommand or an
   option on an existing one) that an answer on such a turn says the index holds no text for that
   Schedule and does not blame a search limit, with every match and drop printed; run it over every
   stored directory holding 6374 and hand-read each verdict (B found 5 of 14 answers blaming a limit).
4. **P3.27's schedule check made gradeable**: on a turn that needed a schedule or annex unit (batch 7
   B's 23 need turns, by session), whether the answer calls a held unit "not held", "not retrievable"
   or "not in the text". Reuse `negatives`/`NEG_ASSERTED` where it fits; say where it does not.
5. **The sweep, priced**: list every run (session or script, n, mode, what each grades), with the
   recorded cost of each stored rep in the recorded mode (`total_cost_usd`), a median and a maximum
   total, and the exact `replay run` commands in order. Invariant 4: n=3 for a FAIL session, n=1 for a
   DEFECT one; say which each is (`evidence/classification.json`).

**Live LEX calls, only if the user agreed at launch, cap 40:** only to confirm a ground-truth detail
the saved payloads do not settle; reuse `seam/batch7/B/lexcall.py`. **Tests:** each new check on
synthetic run files, failing with the check reverted. **Say in your note** the priced sweep as a
table the integrator can put to the user, and which hand-reads it needs.

## Agent C: P3.22 measured ($0; National Archives calls only if agreed)

**Read first:** P3.22's row in full (its build order, the 10-row trap, what to measure, the ground
truth it asks for) and its Session 39 correction; P3.23's and P3.9's rows (built in Session 39);
`notes/batch7_D.md` whole; `notes/batch5_C.md`; `docs/LEGAL_DATA_SOURCES.md` section 4; the
`external-apis` skill's National Archives section; `server_py/src/agent/tools/caselaw.py`
(`case_law_count`, `case_law_date_window`, `_parse_case_law_atom`, `detect_appellate_decisions`);
`server_py/src/agent/agent_shared.py` (the Phase-2 nudge naming `results[:3]`); `tools/caselaw_probe.py`;
batch 5 C's `caselaw_census.py` and batch 7 D's `dryrun.py` in `$PREPILOT_EVIDENCE/seam/`.

**Measure first, live, only if the user agreed at launch (cap 1,300 calls, at least 0.35 s apart,
logged; the published limit is 1,000 per rolling five minutes):** re-run every distinct stored
`search_case_law` (query, court, dates) tuple (batch 5 C counted 612 over 1,257 calls; recount over
all 58 directories) under today's ordering and under `order=relevance` with `per_page=50` (both
parameters, or the 10-row trap returns), building the params with the built
`case_law_date_window` so the dates now apply. Report: the overlap of the result sets and of the
first three; for every stored turn whose answer names an authority, whether each ordering returns
it; and whether `detect_appellate_decisions`' nudges change for the worse. Re-check, live, that
`order=relevance` still works and is still absent from the published spec. **Then propose the ground
truth** P3.22's row asks for before its build: the authorities the 6363 and 6359 answers need, read
from the transcripts and the stored answers, as a gitignored rubric file with each authority's
neutral citation, why it is needed (the lawyer's own words cited by turn, not quoted in any
committed file), and whether each ordering returns it. If the user did not agree to live calls, do
the stored measurement only and say what the probe would settle. **Build nothing in the product;**
a probe added to `tools/caselaw_probe.py` is allowed, with tests on synthetic feeds. **Decisions:**
the ordering (relevance, or keep date), whether the window note and the nudge change with it, and
the before-column replay to book (sessions, n, price from stored costs).

## Agent D: P3.21 measured, with P5.4 (c)'s probe ($0; LEX and legislation.gov.uk calls only if agreed)

**Read first:** P3.21's and P5.4's rows in full; P2.5's, P3.5's, P3.19's and P3.24's rows (what the
change record holds, P3.19's `changes` shape, the self-referential relations and P3.24's line);
`notes/batch7_A.md` (the commencement split); `notes/batch6_B.md` sections 3 and 6 (F2: 62% of "to"
records hold no commencement relation; F3); `docs/LEGAL_DATA_SOURCES.md` (its P3.21 and P5.4
entries); `server_py/src/agent/tools/lex.py` (`_slim_amendment_results`, `_COMMENCEMENT_OF_SUBJECT`);
the `lookup_legislation` branch of the executor; `tools/lex_probe.py`.

**Measure first, over stored evidence ($0, no call):** over every stored `get_legislation_changes`
result, the distinct commencing instruments other than the subject itself (P3.5's rule, and P3.24's
`self` flag); how many have a stored `lookup_legislation` or text record; what share of their
`description`s state a date a pattern can read (with the pattern's every match and drop listed and
hand-read); and the added calls and characters per turn the hop would cost, which sets its cap.
**Then, only if the user agreed at launch:** (1) LEX `/legislation/lookup` for the commencing
instruments with no stored record (cap 300 calls), the same date census; (2) **P5.4 (c)**:
legislation.gov.uk's dated effects ("Changes to Legislation") for a sample of those Acts (cap 300
GETs, stated sample, a reproducible `tools/lgu_probe.py` command if you build one), compared with
`/amendment/search` (which carries no dates), including whether its effects are applied for Scottish
material; and note what the target would need whitelisted (legislation.gov.uk is not on it). **Build
nothing in the product.** **Decisions:** the date's source (LEX `description`, legislation.gov.uk
effects, or both), the hop's cap, the acceptance to book (6409 and 6411 per the row), and whether
P5.4 (c)'s answer warrants a new row.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit
   or later (if another session has committed, read what changed and say so); pushed; `plan_status`
   53 of 77, 1 in progress, 8 of 14 (or the new counts, explained); `plan_lint` exit 0; rubric sha1s;
   the four test databases; nothing running (no python process, port 8000 free), no pin file; a
   baseline full suite on `lexchat_test` (2339).
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first, at most four
   questions): launch A, B, C and D as set out? **May B make up to 40 LEX calls, C up to 1,300
   National Archives calls, and D up to 300 LEX and 300 legislation.gov.uk calls?** (Free of model
   spend; the alternative is stored evidence only.) Confirm the merge order (A, B, the priced sweep on
   the user's go-ahead, then C, D).
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message.
   Give each its section, plus **Rules for every agent**, **Lessons from batches 1-7** and **Shared
   setup**, verbatim; the integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL`; and whether the user agreed to its live calls. While they run, do nothing
   expensive and edit none of their files.
4. **Review each result as it lands** (as in batches 3-7):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines for session ids (allowed), instrument ids and matter words (not allowed,
     except synthetic years 1899-1902, and `DEPTH_TRUTH`'s public statutory text), with
     `seam/batch7/scratchpad_s39/review_branch.sh <branch> <INTEGRATOR_HEAD>` (it runs
     `matter_grep.py`; not `grep -iF`); repoint its scratchpad path to this session's first;
   - for A and B, re-run the new tests with the change reverted on a scratch worktree (restore the
     product files from `<INTEGRATOR_HEAD>`, keep the new tests, count the lines removed), plus at
     least one single-site mutant of your own (`b7_mutC.py` is a CRLF-safe runner), and report it;
     run `git worktree remove` from the main checkout, never from inside;
   - run the full suite on `lexchat_test`;
   - re-run one headline number from each note on the merged tree (A: the dry-run counts; B: one
     before-column `depth` verdict and the price; C and D: two figures from their stored
     measurement);
   - copy the agent's scratch out of its worktree before removing it, and compare file counts.
   Put any wording a lawyer could read to the user before its merge.
5. **Merge A, then B**, each `--no-ff`, the suite after each, the branch pushed after each clean
   merge (never `main`).
6. **The acceptance sweep, only on the user's go-ahead.** Put B's priced table to the user
   (AskUserQuestion: run it as priced, a cheaper subset, or defer); give the median and the maximum;
   set `--max-spend` to the figure agreed. Then:
   - from `server_py/`: `python -m tools.replay check`, then `python -m tools.replay pin`;
   - start uvicorn fresh: `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`, in the
     background with PowerShell `Start-Process -PassThru` (the real Windows PID), logging to the
     session scratchpad; confirm `/api/bot-info` shows the merged build; start the keep-awake helper
     and record its PID;
   - run B's commands in order into `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b8_sweep`
     (or the names B gives). `--max-spend` is checked between reps only, so it can overshoot by one
     rep: **if the total passes the agreed figure, stop and ask.** Never commit while it runs; if it
     stalls (15 minutes with no log growth), re-run the SAME command: it resumes;
   - then `python -m tools.replay restore`, stop uvicorn and the helper by their PIDs, and confirm no
     pin file, no python process and port 8000 free.
   - **Grade** each directory: the exit-1 set (`scratchpad_s39/grade_b7.sh`, repointed), `modes`,
     `negcurrency` (without `--all` on a single directory), `footer_echo`, `depth` (P3.12), B's 6374
     guard and P3.27 schedule checks, `stance`'s control reading (P3.2's criterion (v)), `derivations`
     and `lookup` (P3.25), and the change-record and whole-text summarised counts (`summ_count.py`,
     plus the same for `get_legislation_text`: the flag's cost). **Hand-read every negative on a turn
     that needed a schedule or annex unit, every `depth` verdict, every 6374 guard verdict and every
     6340 derivation**; save it to the gitignored `evidence/rubrics/handread_wave4_b8_sweep.md`. Tick
     a row only if its own acceptance passes by hand (n=3 all clean for a FAIL session).
7. **Merge C, then D**, as in step 5, after the restore.
8. **Assemble:**
   - tick only rows whose acceptance is met on the merged tree, stating the check; annotate each row
     in a byte script (each anchor once, CRLF kept, an even number of `**` added, no `|` in a cell,
     rows on one line); a newly ticked row's Bucket-index entry gets ` **done**`; P3.25 goes from
     `[~]` to `[x]` only on its replay; then `plan_lint` (0 errors) and `plan_status`;
   - **put the agents' decisions to the user**, grouped (AskUserQuestion, at most four questions per
     call, recommendation first): anything A raised on the line's wording or the footer; the sweep's
     outcome where it is a judgement call; P3.22's ordering and its before-column; P3.21's date
     source, cap and acceptance; whether P5.4 (c) warrants a row. Record each answer on its row;
   - CHANGELOG *Unreleased*: each product change in plain words (what a lawyer or the model now
     sees); tooling separately. Add an even number of `**`. Correct `docs/LEGAL_DATA_SOURCES.md`
     where a finding changes it.
9. **Hand over:** a Session 40 entry and a handover for Session 41 in SESSION_LOG.md (next by
   severity); the memory entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session
   scratchpad to the gitignored `evidence/seam/batch8/scratchpad_s40/`; update the local skills
   (`.claude/` is gitignored) where a finding changes what they say; update the Fix Tracker only if
   the user asks (FIX_PLAN "How to use this file" step 7: Artifact `read` the live URL and Read every
   line of the saved file first; a newly ticked row gets `fixed` and `ver: "Next release"`).

**Open with the user, carried (do not act on them yourself):** sending the lawyer pack (unblocks
P3.2, P3.3, P3.17; confirm the cover note's promise first); sending SCTS the note (P3.20's
prerequisite); applying for the National Archives licence (`docs/TODO.md` D23); deploying
`v2026.09.3` to the target (`pg_dump` first, then pull, restart and `test_apis.ps1`); telling the
eval-harness owner about schema v6; D19's remaining items; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, P3.19, P4.21, P3.24, P4.19, P3.23 and P3.9 are
"Next release"); P4.12, D20, D21/D22; batch 1's three items; the p37_6373 substitution P4.17 exposes;
enrolling 6370's five hedged drops in `p33.json` before the next P3.3 after-column; P3.24's three
watch items; and **saving and mapping any further external report in the session that receives it**.
