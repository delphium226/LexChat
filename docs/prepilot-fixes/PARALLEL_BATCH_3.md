# Parallel batch 3: P4.15 built, P4.17 measured, a lawyer's pack, then the after-column

**Set up at the end of Session 34 (2026-10-01), for Session 35, at the user's request.** It
follows batches 1 and 2 (`PARALLEL_BATCH_1.md`, `PARALLEL_BATCH_2.md`), which worked: agents in
git worktrees, the main session integrating, any paid run put to the user first. The principle
is unchanged: **free work in parallel; expensive work serialised, run by the integrator only,
and put to the user with a figure before any money is spent.** Every agent in this batch is $0.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent** and **Lessons from batches 1 and 2**, verbatim. Nothing here should
need re-deriving. If something does, the agent says so in its note rather than guessing. The
matter-specific detail (lawyers' wording, rubric patterns) is NOT in this file. It is in the
gitignored files named below.

**What the user has already decided (Session 34 addendum, 2026-10-01; do not re-open):**
1. Build P4.15's option (a), the footer sentence, AND option (c), the grader correction, both
   at $0 and both before any replay.
2. Then ONE after-column, `wave4_b2_post`: about $17, cap $22. **Confirm the figure with the user
   before spending** (the user approved the plan, not yet the spend).
3. **P3.2 is PARKED** until a lawyer confirms the rubric's reading. No new P3.2 lever. P3.2 is
   still re-measured in the after-column, because a Worker prompt changed (P3.17).
4. P4.17 is booked, measure-first.
5. No separate row for the `wave4_p41_pre` Deep Research turn: (a) covers it. `_plain`'s
   nested-bracket gap stays as it is. C's code lever for P3.17, and giving the research Workers
   PHASE 2c, wait for the after-column. The phase's extra cost (about $0.15 a turn) is accepted.

---

## Where things stand (verified 2026-10-01, end of Session 34)

- **Branch** `fix/prepilot-defects`, head `6506c27` (the commit adding this file is on top of
  it), **pushed**: `origin/fix/prepilot-defects` equals local. **`main`** is at `a6b4a76`, release
  **`v2026.09.3`**. **Never push or merge to `main`**: the next cut (`v2026.10.1`) goes only when
  the user asks, using the procedure in CLAUDE.md *Releases*. **Branch pushes are allowed** (user
  decision, Session 34). The permission classifier has refused them before; if it does, ask the
  user and do not work around it.
- **Tests: 2077** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **43 of 61 rows**, 8 of 14 buckets. In
  progress: P0.4 and P5.2. B5 waits on P4.15 and P4.17; B6 on P3.2; B11 on P3.3 and P3.17.
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **55 replay directories**, the latest after-column `wave4_b1_post`.
  - The booked before-columns: `wave4_p33_pre` (P3.3's) and `wave4_p32_pre` (P3.2's).
  - The rubrics `rubrics/p32.json` (sha1 `e14b762…`) and `rubrics/p33.json` (sha1 `dce6d2f…`),
    as batch 2's agent A left them. Backups are in `rubrics/backup_batch2/`.
  - `rubrics/handread_wave4_b1_post.md`, the last hand-read.
  - `seam/batch2/{A,B,C,D,integrator,scratchpad_s34}/`. Agent D's P4.15 dry-run scripts are in
    `seam/batch2/D/` (`p415_dryrun.py`, `p415_shape.py`, `p415_detectors.py`,
    `p415_c_matches.py`, `p415_more.py`, `p415_para.py`, `p415_read.py`). The integrator's keep-awake
    helper is `seam/batch1/scratchpad_s33/keep_awake.py`.
- **Notes from batch 2** (committed): `docs/prepilot-fixes/notes/batch2_{A,B,C,D}.md`. D's note
  sections 1.1-1.7 are the P4.15 evidence and wording; section 1.5 is P4.17's origin; part 2 is
  P3.2's evidence.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, no pin file (~~`server_py/.replay_pin_state.json`~~ `server_py/tools/.replay_pin_state.json` absent; path corrected in Session 35, `STATE_PATH` in `tools/replay.py`), no
  worktrees. The dev box is on its normal settings. Eight merged `worktree-agent-*` branches
  remain locally (batches 1 and 2) and can be deleted.
- **Read before anything else:**
  - FIX_PLAN.md: "How to use this file", the Invariants, "Data handling", the top
    recommended-order line ("end of Session 34"), and rows P3.2, P3.3, P3.17, P4.15 and P4.17 in
    full.
  - SESSION_LOG.md, from "Session 34 — 2026-10-01 — parallel batch 2" to the end of the file:
    the interim entry, the continuation, the handover for Session 35 and **its addendum, which
    supersedes the handover's "Take next"**.

---

## The batch

| Agent | Work | Kind | Budget | Main files |
|---|---|---|---|---|
| **A** | **P4.15 (c)**: the grader reads the model's own "a search of … returned no results" as attribution | tooling | $0 | `tools/replay_report.py` (`NEG_BLAMED_INDEX`), `tests/test_replay_tooling.py` |
| **B** | **P4.15 (a)**: the footer sentence, built in product code | deterministic product code | $0 | `src/utils/search_scope.py`, `tests/test_case_law_gap.py`, `tests/test_echoed_footer.py` |
| **C** | **P4.17**, measured with options. **No product code.** | analysis | $0 | a note, plus a data-free tool only if one is needed |
| **D** | **A confirmation pack for a lawyer**: the legal readings behind the rubrics, as yes/no questions. **No code, nothing committed but a matter-free note.** | writing, gitignored | $0 | `$PREPILOT_EVIDENCE/lawyer_pack/` (gitignored) |

**Merge order: A, then B, then C, then D** (graders before the product they grade). A and B touch
different files and can run side by side. **No agent edits a rubric file in this batch.**

**Not in this batch:** any replay (the integrator's, after merging, put to the user first); any
P3.2 lever (parked); C's code lever for P3.17 (waits for the after-column).

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` (Invariants 1-6, "Data handling", your
   rows in full) and, in `docs/prepilot-fixes/SESSION_LOG.md`, everything from "Session 34 —
   2026-10-01 — parallel batch 2" to the end of the file. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, any rubric file or any memory
   file: the integrator folds your results in. Commit on your worktree's branch; **do not push,
   do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch3_<A|B|C|D>.md` and commit it. Put
   in it:
   - what you changed and why;
   - every number, with the exact command that produces it;
   - every dry-run edit or match you read (counts and locations only if the text names a matter);
   - what you did NOT do;
   - anything the integrator must decide.

   **Before any claim of "fixed", state the row's acceptance and whether it is met.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list
   every match and every drop before quoting a rate. For any code that writes text into an
   answer, dry-run it over every stored answer and read every edit.
5. **Tests:** each product or tool change gets a unit test at its seam. Each test is proven to
   FAIL with the change reverted on a scratch copy, **and the note says how many lines the
   revert removed** (a revert that removed nothing proves nothing). Run the full suite on your
   own test database before your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names,
   or instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget
   Order 1901"). Grep your staged diff for session ids, instrument ids and matter words before
   every commit. Rubric patterns, draws and anything quoting a matter stay in the gitignored
   evidence.
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so
   Python edits over multi-line text must normalise CRLF to LF before matching and restore CRLF
   on write. **A byte-level edit or revert must assert its anchor occurs exactly once before
   writing** (an LF anchor matches nothing in a CRLF file). **Never run Python with backslashes
   from a bash heredoc** (it mangles them): use the Edit tool, or write the script to a file
   first. Commit messages go in a file (`git commit -F`), ending with the attribution line the
   harness gives.
8. **Budget: $0.** No model call of any kind: no seam draw, no live Worker, no summariser call.
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** `$PREPILOT_EVIDENCE/seam/batch3/<your letter>/`
    (gitignored). Never write to the session scratchpad: it is shared by every agent, and in
    batch 2 one agent deleted a folder there.
11. **When you finish, reply with:**
    - your branch name and the commit list;
    - the test count and the spend;
    - the path of your note;
    - for each row or item: met, closed or not, and why.

## Lessons from batches 1 and 2 (give these verbatim with each brief)

- **Check your base before anything else.** In both batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are:
  - `git log --oneline -1`;
  - `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`.

  If HEAD is not `<INTEGRATOR_HEAD>` and you have no commits, run
  `git reset --hard <INTEGRATOR_HEAD>`. Say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a run of a single test
  file. Use plain `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown,
  so a run on the default database breaks the integrator's suite.
- **`summary_probe count --dir` takes a PATH**, not a directory name. Given a name it reads 0
  results. `glosses --dir` takes either.
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth, and a grader change is judged by whether its verdicts move towards the recorded
  hand-read, never by its pass rate. Batch 2 brought the graders into agreement with every
  recorded hand-read verdict; do not undo that.
- **Any text the product writes into an answer is read by every grader.** Check what your words
  do to `NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`, the halt
  detectors and the footer strippers, not only the detector you are aiming at. Agent D's first
  two P4.15 wordings tripped `NEG_LIMITS` and `NEG_TERMS`.

---

## Shared setup

- **Worktrees:** `isolation: "worktree"`. A worktree has no `server_py/.env`, and that is fine.
- **In a worktree, set on every tool command:**
  - `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`;
  - `PYTHONIOENCODING=utf-8` (the console is cp1252);
  - `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_<a|b|c|d>`.

  Pass `--dir` and `--also` paths under `$PREPILOT_EVIDENCE/replay/`.
- **Commands** (run from `server_py/`):
  - `python -m tools.plan_status`;
  - `python -m tools.replay_report --dir <path> <subcommand>`. The subcommands are `negatives`,
    `caselaw`, `scoperecord`, `nosearch`, `halts`, `derivations`, `commencements`, `currency`,
    `modes`, `deadend`, `siblings`, `scripted`, `lookup`, `drgaps`, `blanks`,
    `lost --require-label`, `interpret`, `stance`, `hedges` and `openers`;
  - `python -m tools.footer_echo --dir <path>`;
  - `python -m tools.summary_probe count|glosses`.
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.

---

## Agent A: P4.15 (c), the grader correction ($0)

**Read first:** `notes/batch2_D.md` sections 1.1-1.7. Option (c) is specified in 1.6, and its 64
newly matched sentences were listed and read by D (`$PREPILOT_EVIDENCE/seam/batch2/D/p415_c_matches.py --list`).

**The change:** `NEG_BLAMED_INDEX` (`tools/replay_report.py`, about line 285) gains ONE
alternative for the model's own attribution sentence, as D specified it: `a search of
<the|this|our> … <database|index|corpus|collection> … returned <no|zero>
<results|judgments|matches|cases>`. The pattern must stay within a sentence (`[^.]` gaps, as the
file's other alternatives do).

**Measure before and after** (`negatives` over every one of the 55 directories), then list every
verdict and every model-column count that moves. **The expected moves, from D's dry run:**
- exactly 9 `negatives` verdicts go from FAIL to PASS: `wave4_p33_pre` r1 t3, r2 t3, r3 t4;
  `wave4_p33_post` r1 t3, r1 t5, r2 t2, r2 t5; `wave4_b1_post` r2 t5, r3 t4;
- the 4 turns outside the shape stay failing (`wave2_p24_ab` 6385 r2 t4 and r3 t4,
  `wave4_p46_pre` r1 t4, `wave4_p41_pre` 6346_dr r1 t2);
- the model column moves in 4 directories only: `wave2` 8 to 14 explained, `wave4_p33_pre` 0 to
  14, `wave4_p33_post` 0 to 21, `wave4_b1_post` 2 to 19;
- `wave2_p22_final` (P2.2's acceptance directory) does not move;
- `commencements`, the other reader of `NEG_BLAMED_INDEX`, is unchanged everywhere.

Any difference from those numbers is reported, read, and explained before the commit. Re-read
every newly matched sentence (D read 64): each must report what a named search returned and
state no conclusion about the law.

**Tests:** synthetic sentences in `tests/test_replay_tooling.py`: the new form is credited; a
sentence stating a negative about the law with no search named is not; a sentence that names a
search and then concludes that the thing does not exist still fails.

**Acceptance (A's part of P4.15):** the 9 verdicts move and nothing else, every new match read,
and the tests fail with the change reverted. Say whether it is met. P4.15's own acceptance
(`negatives` 0 on 6370 n=3) is the integrator's after-column.

## Agent B: P4.15 (a), the footer sentence ($0, deterministic)

**Read first:** `notes/batch2_D.md` sections 1.1-1.7. Read `src/utils/search_scope.py` from
`_CASE_LAW_DATABASE` (about line 2030) to `case_law_scope_footer` (about line 2131), and both test
files below.

**The change:** a new constant in `search_scope.py`, `CASE_LAW_ABSENCE_SENTENCE`, worded EXACTLY
as D dry-ran it:

> A search can miss a judgment the database holds, so one missing from its results may still
> exist, in this database or elsewhere: that is not proof of absence.

- `_case_law_body` appends it after `CASE_LAW_COVERAGE_SENTENCE` and BEFORE
  `CASE_LAW_DOCTRINE_SENTENCE`, and only when the search ran (`done`). It is not added on an
  errored search, exactly as the doctrine sentence is not.
- It therefore reaches both the clause (`case_law_scope_clause`, joined to a legislation line)
  and the standalone line (`case_law_scope_footer`).
- Give it a comment in the file's style: why it exists (P4.15, B5), and that its wording trips
  only `NEG_BLAMED_INDEX` by design.

**Couplings you must keep, each pinned by an existing test (extend those tests rather than
weakening them):**
- `tests/test_case_law_gap.py::test_the_case_law_sentence_trips_no_detector_of_its_own` (about
  line 337) asserts that the case-law text trips no detector in its list. Keep every existing
  assertion. Add assertions that the new text DOES match `rr.NEG_BLAMED_INDEX` (by design) and
  does NOT match `rr.NEG_LIMITS` or `rr.NEG_TERMS`.
- `tests/test_case_law_gap.py` (about lines 249-321): **P2.8's carried line**
  (`carried_scope_footer`) parses only the legislation part, and a carried line restates
  legislation terms only (`assert carried and "case-law" not in carried`). Extend that round trip
  so it builds a fresh line with the new sentence, carries it, and asserts that neither the new
  sentence nor any case-law wording comes back in the carried line. This is "P2.8's round trip
  extended", which the P4.15 row requires.
- `tests/test_echoed_footer.py:126` asserts the footer ENDS with `CASE_LAW_DOCTRINE_SENTENCE +
  "*"`. With the sentence placed before the doctrine sentence, that holds. Add an assertion that
  the new sentence is present too.
- **P4.14's echo strip** (`_ECHOED_FOOTER`, and `tools/footer_echo`) and
  `replay_report._without_footer` must still strip the longer one-line footer. Add a test that a
  model-echoed copy of the new, longer footer is still stripped.
- `replay_report.CASE_LAW_CODE` must still prefix `CASE_LAW_COVERAGE_SENTENCE`
  (`test_the_instrument_is_coupled_to_the_product_sentence`). Do not change that sentence.

**Measure:**
- **Trap: the dry-run script's default wording is NOT the final one.** The `ATTR` default at the
  top of `$PREPILOT_EVIDENCE/seam/batch2/D/p415_dryrun.py` is D's earlier "A keyword search can
  miss …" wording, which tripped `NEG_LIMITS` and `NEG_TERMS`. The final wording reaches the
  script only through the `P415_ATTR` environment variable. The script inserts it directly after
  `CASE_LAW_COVERAGE_SENTENCE` (`COVERAGE + " " + ATTR`), which is where `_case_law_body` puts
  it. Pass the sentence from your built constant, not retyped. For example, write a two-line
  wrapper that sets `os.environ["P415_ATTR"] = search_scope.CASE_LAW_ABSENCE_SENTENCE` and
  `P415_VARIANTS="base,a"`, then runs the script with `runpy`. That proves the built text and
  the dry-run text are byte-identical.
- Run it with `<out>` under `$PREPILOT_EVIDENCE/seam/batch3/B/`, and confirm D's result: 204
  stored answers carry the clause; exactly 13 `negatives` verdicts go from FAIL to PASS (the 9
  in agent A's section plus the 4 outside the shape); nothing else moves in any of the 21
  subcommands. D's `p415_detectors.py` is the check that the sentence trips only
  `NEG_BLAMED_INDEX`.
- If your dry run differs from D's, stop and report it.

**Acceptance (B's part of P4.15, deterministic):** the sentence in place, every coupling above
held and tested, each new test failing with the change reverted, and the dry run moving exactly
D's 13 verdicts. Say whether it is met.

## Agent C: P4.17, measured with options ($0, no product code)

**Read first:** the P4.17 row; `notes/batch2_D.md` section 1.5; P2.8's row and the `_SEARCH_TOOLS`
comment in `src/utils/search_scope.py` (about line 2508), which records why a section-search-only
turn is silent (P2.8's deliberate choice).

**Measure** over every stored directory:
- every turn with the shape: `legislation_only` (or hybrid), at least one
  `search_legislation_sections` and/or `lookup_legislation` call, no `search_legislation`, and
  no footer reaching the lawyer. D counted 8 since P3.7;
- for each turn: what the answer asserts about anything missing, and what `negatives`,
  `scoperecord` and `nosearch` say about it;
- the one failing turn D found: `wave4_p33_post` p32_6406 r1 t4, a provision said not to be
  retrievable when LEX holds it (P3.12's shape).

**Then set out the options with their consequences:**
- **(d)** a code-emitted line naming the turn's section searches (and lookups), in the same
  single `*Search scope: …*` shape. Dry-run it as D did for P4.15: insert it into every stored
  answer of the shape, run the 21 subcommands, and list every verdict that moves. Watch that it
  reverses P2.8's silence, and check the carried-line parse and P4.14's echo strip;
- **(e)** leave the product silent and grade the shape some other way;
- **(f)** anything else the evidence shows.

Recommend one, and propose an acceptance for the row (it says "to be booked after the
measurement"). **Do not build it.**

## Agent D: a confirmation pack for a lawyer ($0, gitignored)

**Why:** P3.2 is parked until a lawyer confirms the rubric's reading. The readings behind P3.3's
rubric (6338, 6370, 6375) are also marked "to be confirmed by a lawyer" in FIX_PLAN. The user will
send the pack; the agent does not contact anyone.

**Write** `$PREPILOT_EVIDENCE/lawyer_pack/confirmation_pack.md` (gitignored: it names the
matters). It has one short section per reading:
- 6406 (P3.2);
- 6338, 6370 and 6375 (P3.3).

Each section gives:
- the question the session turned on, in one neutral sentence;
- the reading the rubric grades against, quoted from the rubric's `_note` field or the FIX_PLAN
  row, NOT re-derived;
- the provisions it rests on, each with its legislation.gov.uk link. Take each link from
  the stored run files' tool results; every one must be a URL a tool returned;
- **one yes/no question**, with space for the lawyer's answer and a comment.

Add a one-paragraph cover note in plain language: what AILA is checking, why the confirmation
matters (a fix is graded against these readings), and that no answer from the tool is being
attributed to the lawyer.

**Rules for the pack:**
- Quote no lawyer's question or answer verbatim.
- Name no lawyer.
- State no reading the rubrics and FIX_PLAN do not already record.
- Where a source is unclear, say so instead of resolving it.

**Commit only** `docs/prepilot-fixes/notes/batch3_D.md`. It says where the pack is and how many
readings and questions it holds, and names no matter, instrument or reading.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand":
   - `git status` clean, and HEAD at `6506c27` or later and pushed;
   - `python -m tools.plan_status` gives 43 of 61;
   - 55 replay directories, and both rubric hashes as above;
   - the four test databases exist;
   - nothing running and no pin file;
   - a baseline full suite on `lexchat_test` (2077).
2. **Ask the user once, before launching** (AskUserQuestion): launch the batch as set out here?
   Name the four agents, all $0.
3. **Launch A, B, C and D** as background agents with `isolation: "worktree"`. Give each:
   - its section, plus **Rules for every agent** and **Lessons from batches 1 and 2**, verbatim;
   - the integrator's HEAD sha as `<INTEGRATOR_HEAD>`;
   - its `PREPILOT_EVIDENCE` and `TEST_DATABASE_URL` values.

   While they run, do nothing expensive and edit none of their files.
4. **Review each result as it lands:**
   - confirm the branch contains `<INTEGRATOR_HEAD>`;
   - read the note and the diff;
   - grep the diff for session ids, instrument ids and matter words;
   - re-run the new tests with the change reverted, using a script that **asserts the anchor
     count and prints how many lines it removed**;
   - run the full suite on `lexchat_test`;
   - re-run at least one headline number from the note.

   For D, also open the pack. Check that every link in it appears in a stored tool result, and
   that it quotes no lawyer.

   **Merge in the order A, B, C, D**, each with `git merge --no-ff`, the suite after each. Push
   the branch after each clean merge.
5. **After A and B are both merged:** re-run D's dry run against the BUILT product with both (a)
   and (c), passing the built sentence through `P415_ATTR` as B's section describes, and record
   what moves. Expected, from D's note: the 13 turns PASS. `negatives` goes from exit 1 to exit
   0 on `wave4_p33_pre`, `wave4_b1_post`, `wave2_p24_ab`, `wave4_p41_pre` and `wave4_p46_pre`.
   `wave4_p33_post` stays at exit 1 (`p32_6406` r1 t4, P4.17's shape). Then fold into
   FIX_PLAN.md and SESSION_LOG.md:
   - annotate P4.15 (built; acceptance pending the after-column);
   - annotate P4.17 with C's options;
   - note D's pack on P3.2 and P3.3;
   - write one-line ledger rows, with no `|` in a cell;
   - use a byte script that asserts each row is found once and that the edits ADD an even
     number of `**` (the file's total is already odd: P0.2 carries a literal
     `` `**Key findings` `` in a code span);
   - `plan_status` stays at 61 unless a row is booked.
6. **Before the after-column: put the plan and the figure to the user** (AskUserQuestion). The
   user approved the plan and asked for the spend to be confirmed.
   - **What runs:** `wave4_b2_post`, the same shape as `wave4_b1_post`.
   - **Estimate:** `wave4_b1_post` cost $16.03 ($9.90 for the sessions and $6.13 for the script),
     plus about $0.10-0.15 a 6338 rep for PHASE 2c's extra Worker calls. **About $17, cap $22.**
   - **Procedure**, from `server_py/`:
     - `python -m tools.replay check` (the pinned model must still be served), then
       `python -m tools.replay pin`;
     - start uvicorn fresh: `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`, in
       the background, logging to a file in the session scratchpad. Record its PID;
     - start the keep-awake helper (`$PREPILOT_EVIDENCE/seam/batch1/scratchpad_s33/keep_awake.py`,
       in the background). It holds a Windows execution state and changes no setting;
     - `python -m tools.replay run --session 6338 6370 6375 6345 --reps 3 --max-spend 12
       --out-dir C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b2_post`;
     - `python -m tools.replay run --script
       C:/Projects/LexChat/docs/prepilot-fixes/evidence/scripts/p32_6406.json --reps 3
       --max-spend 10 --out-dir C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b2_post`;
     - `--max-spend` is checked between reps only, so it can overshoot by one rep. If the first
       run passes $12, stop and ask before the second;
     - **never commit while a run is going.** If a run stalls, re-run the SAME command: it
       resumes;
     - then `python -m tools.replay restore`, stop uvicorn by its PID, stop the keep-awake
       helper, and confirm there is no pin file.
7. **Grade `wave4_b2_post`.** Hand-read every `interpret` match and drop and every `stance`
   "none". Save the hand-read to the gitignored `evidence/rubrics/handread_wave4_b2_post.md`.
   - **P3.17 / P3.3's 6338 criteria, n=3:** per rep, turns 1 and 2 name the 1999 Order; no turn
     asserts that the 2010 Act or the 1978 Act governs the 2009 Act or s.35ZA; turn 3 says the
     Act sets no order. **P3.17 is ticked only if all three reps are clean.**
   - **P3.3's 6370 x3 and 6375 x3 criteria** (the row).
   - **P4.15:** `negatives` exits 0 on 6370, n=3. With (a) built this passes by construction,
     the same circularity P2.2 accepted; say so on the row. **Tick P4.15 only if it is met**
     and A's and B's deterministic parts were met.
   - **P3.2:** its booked criteria on `p32_6406` x3 and the 6345 x3 guard. It is a re-measure
     only, because the row is parked.
   - **P3.3 cannot be ticked this session even if 6338, 6370 and 6375 all pass.** Its booked
     acceptance includes P3.2's, and P3.2 is parked. Put that to the user; do not re-scope it
     yourself.
   - **Guards:**
     - `hedges` (0 hedged retrieval statements, 0 blanket caveats, each counted sentence read);
     - `replay_report --dir <after> discovery --before
       C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_p33_pre --only 6338 6370
       6375`, and the same with `--before …/wave4_p32_pre --only 6345`: `sources_kept` per slot
       not lower in more than 1 slot;
     - the exit-1 set: `halts negatives derivations commencements currency scoperecord nosearch
       caselaw modes deadend siblings scripted lookup drgaps blanks "lost --require-label"`.
       `commencements` exits 1 when no graded session is present, which is expected;
     - `openers` (P4.16 live), `tools.footer_echo --dir <path>` (P4.14), `caselaw` TWO_LINES 0;
     - `summary_probe count --dir <PATH>` (0 Act additions) and `summary_probe glosses --dir
       wave4_b2_post --session 6406 6338` (P3.16 must stay at 0).
   - **Cost:** report 6338's cost a rep against `wave4_b1_post`'s $0.34, which is PHASE 2c's
     cost in production.
8. **Hand over:**
   - a Session 35 entry and a handover for Session 36 in SESSION_LOG.md;
   - the memory entry `project_prepilot_freeze.md` and its MEMORY.md line;
   - copy the session scratchpad to the gitignored `evidence/seam/batch3/scratchpad_s35/`;
   - update the Fix Tracker only if the user asks (FIX_PLAN "How to use this file" step 7: read
     the live artifact and every line of the saved file first).

**Open with the user, carried (do not act on the target yourself):**
- deploying `v2026.09.3` to the target (`pg_dump` first, then pull, restart and
  `test_apis.ps1`; the local prompt cache moves to v3 there, so cached summaries empty, which is
  intended);
- telling the eval-harness owner about schema v6;
- D19's remaining items (deploy by tag; stamp the version on the audit event);
- sending D's confirmation pack to a lawyer, which is how P3.2 un-parks;
- P4.12, D20, D21/D22, P5.2, Thomas's document;
- from batch 1:
  - whether to book the research Worker's jurisdiction line as a row;
  - the 28 case-law summaries applying English authority to Scotland;
  - the two change-record id mis-expansions;
  - `wave2_p27` 6341 r2 t2;
- which rows go in the next cut (`v2026.10.1`; P3.16 and P4.16 are "Next release" on the
  tracker).
