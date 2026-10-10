# Parallel batch 5: the plan made consistent, and the new grader gaps closed

**Set up at the end of Session 36 (2026-10-02), for Session 37, at the user's request.** It
follows batches 1-4 (`PARALLEL_BATCH_1.md` to `_4.md`): agents in git worktrees, the main session
integrating, nothing merged or applied that the integrator has not re-checked. **Every agent in this
batch is $0 and no replay is planned.** The principle is unchanged: free work in parallel; anything
expensive serialised, run by the integrator only, and put to the user with a figure first.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent**, **Lessons from batches 1-4** and **Shared setup**, verbatim. Nothing
here should need re-deriving; if something does, the agent says so in its note rather than
guessing. Matter-specific detail (lawyers' wording, rubric patterns, hand-reads) is NOT in this
file; it is in the gitignored files named below.

**Why this batch (user decision, 2026-10-02).** FIX_PLAN.md has grown to about 470 KB over 36
sessions, mostly by annotation, and six rows were booked on 2026-10-02 by a separate session from
two data-source reviews. A structural probe at the end of Session 36 (below) found the counts sound
but the cross-references drifted, and the semantic state of several open rows inconsistent. The user
agreed to review the plan for internal consistency **before** building anything further, scoped to
the open rows and the cross-references, not a re-read of the history.

**What the user has already decided (2026-10-02; do not re-open):**
1. **Review the plan first, $0**: mechanical consistency (by a tool, so it can be re-run) and a
   semantic pass over the 23 open rows only. History (ticked rows' annotations, old
   recommended-order lines) is not re-read or rewritten.
2. **Agents propose, the integrator applies, the user approves anything that is not mechanical.**
   No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md, CLAUDE.md, summary-table.html or a
   memory file.
3. **P3.2 stays PARKED** until a lawyer answers the confirmation pack; P3.3 cannot be ticked while
   P3.2 is parked. The pack (`evidence/lawyer_pack/confirmation_pack.md`, sha1 `10da6f9d…`) is
   ready; sending it is the user's action.
4. From Session 36: the grader gaps found in `wave4_b4_post` are fixed before any further
   after-column (agent D here, if the user includes it at launch).

---

## Where things stand (verified 2026-10-02, end of Session 36)

- **Branch** `fix/prepilot-defects`, **pushed**, head `3ca9edb` or later (this file's commit).
  **`main`** at `a6b4a76`, release **`v2026.09.3`**. **Never push or merge to `main`**: the next cut
  (`v2026.10.1`) goes only when the user asks. Branch pushes are allowed (user decision); if the
  permission classifier refuses one, ask the user and do not work around it.
- **Tests: 2135** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **46 of 69 rows**, **8 of 14 buckets**. In
  progress: P0.4, P5.2. Fixed since `v2026.09.3` ("Next release"): P3.16, P4.16, P4.15, P4.18,
  P4.17 (CHANGELOG *Unreleased* lists them).
- **Six rows booked on 2026-10-02 by another session** (four docs-only commits, `0d72d7c` to
  `eeb87f0`, pushed): P3.20, P3.21, P5.4 (from `docs/LEGAL_DATA_SOURCES.md`, a legal data sources
  map) and P3.22, P3.23, P4.19 (from a review of the National Archives API spec). P3.19 was booked
  by Session 36 (B3). **Another session can commit to this branch at any time: run `git log` and
  `plan_status` before every fold.**
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - 57 replay directories, the latest `wave4_b4_post` (Session 36's after-column, $9.88).
  - Rubrics `rubrics/p32.json` (sha1 `7927e64…`) and `rubrics/p33.json` (sha1 `5e5769a…`; only its
    `_note` changed since batch 4 A's `7e3091e…`). Backups: `rubrics/backup_batch4/`.
  - Hand-reads: `rubrics/handread_wave4_b4_post.md` (its "Grader gaps found" section is agent D's
    work list), `handread_wave4_b2_post.md` (with a Session 36 correction appended).
  - `seam/batch4/{A,B,C,D,integrator,scratchpad_s36}/`: batch 4's scratch; **the structural probe
    is `seam/batch4/scratchpad_s36/plan_probe.py`** (read-only; run from the repo root).
  - The keep-awake helper: `seam/batch1/scratchpad_s33/keep_awake.py` (no replay is planned).
- **Notes from batch 4** (committed): `docs/prepilot-fixes/notes/batch4_{A,B,C,D}.md`.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no worktrees.
  Sixteen merged `worktree-agent-*` branches and `batch3-B` remain locally and can be deleted.

### The structural probe's findings at `3ca9edb` (`python <evidence>/seam/batch4/scratchpad_s36/plan_probe.py`)

- 69 rows, 46 ticked. `plan_status`'s counts are right (it reads ticks, not the index).
- **16 ticked rows not marked `**done**` in the "Bucket → row index":** P1.2, P1.3, P1.6, P2.2, P2.5,
  P2.7, P3.8, P3.15, P3.16, P3.18, P4.10, P4.11, P4.13, P4.14, P4.16, P5.1. (The index's marking was
  never applied uniformly; decide one convention.)
- **21 rows named in no index line:** P0.1-P0.7, P1.5, P2.6, P3.6, P3.12, P3.14, P3.21, P3.22,
  P3.23, P4.4, P4.8, P4.9, P4.19, P5.3, P5.4. Some belong outside a bucket on purpose (P0
  measurement rows, P1.5); **P3.22's own row says it is deliberately in no bucket's closure list**;
  the rest need a placement or an explicit "(no bucket)" entry.
- **3 ticked rows whose `Depends on` names an open row:** P3.16 and P3.18 on P3.3; P4.13 on P3.2
  (residual rows built by user decision; the plan's "do not start a row whose Depends on is
  unticked" rule says otherwise).
- 17 recommended-order lines; the top one is "end of Session 36". Older ones are history.

### Semantic inconsistencies already known (Session 36), for agent B

1. **P3.3's booked acceptance contradicts P3.3's own lever.** Its prompt clause tells the
   conversational Manager to give what the text does not settle "as a reading"; the booked 6338
   turn-3 criterion fails "a hedged conclusion that they must be sequential", and batch 4 D showed
   the turn-3 hedged sequence reading is produced by that clause (4 of 9 answers since it, always
   "on one reading", always beside the correct statement; `notes/batch4_D.md`). P3.17's acceptance
   is P3.3's 6338 criteria, so it inherits the conflict. The lawyer pack's supplementary question
   (Reading 2) asks exactly this.
2. **A chain blocked on one external event, stated nowhere in one place:** P3.2 parked on the
   lawyer; P3.3 not tickable while P3.2 is parked; P3.17 graded on P3.3's criteria.
3. **New rows overlapping existing ones with no stated relationship:** P3.20 and P5.2; P3.21 and
   P2.5/P4.18 (whose footer says no date was retrieved); P3.23 and P1.3/P2.2 (the legislation
   windowing fix); P3.12 and P4.17 (which explains that negative, not fixes it).

---

## The batch

| Agent | Work | Kind | Budget | Main files |
|---|---|---|---|---|
| **A** | **`tools/plan_lint`**: the structural checks as a tool, plus a proposed mechanical fold | tooling | $0 | `server_py/tools/plan_lint.py` (new), `server_py/tests/test_plan_lint.py` (new); a fold script in its scratch |
| **B** | **Semantic review, open rows part 1** (legislation, interpretation, measurement): P0.4, P0.7, P3.2, P3.3, P3.4, P3.6, P3.12, P3.14, P3.17, P3.19, P3.21, P5.4 | analysis, a note only | $0 | `notes/batch5_B.md` |
| **C** | **Semantic review, open rows part 2** (case law, presentation, external) plus cross-document consistency: P3.9, P3.10, P3.20, P3.22, P3.23, P4.3, P4.8, P4.9, P4.12, P4.19, P5.2 | analysis, a note only | $0 | `notes/batch5_C.md` |
| **D** *(optional, the user decides at launch)* | **The grader gaps from `wave4_b4_post`** | tooling + gitignored rubrics | $0 | `tools/replay_report.py` (`derivations`, `INTERP_HEDGE`, `interpret`, `stance`), tests, `evidence/rubrics/p32.json`, `p33.json` |

**Merge order: A, D, B, C** (the tool first, so B and C's claims can be re-checked with it; D's
grader changes next; the two notes last). **Collision points:** A touches only new files; D owns
`tools/replay_report.py`; B and C commit only their notes. B and C may both mention a cross-row
relationship (for example P3.21 against P4.18); the integrator reconciles duplicates.

**Not in this batch:** any product code; any replay or seam draw; any FIX_PLAN edit by an agent;
P3.19's build (wait until B confirms its premise and acceptance); sending the lawyer pack.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the "Bucket → row index", the top recommended-order line, and
   your rows in full) and, in `docs/prepilot-fixes/SESSION_LOG.md`, everything from "Session 36 —
   2026-10-02 — parallel batch 4" to the end of the file. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, any `PARALLEL_BATCH_*.md` or any
   memory file: the integrator folds your results in. **Only agent D edits a rubric file.** Commit on
   your worktree's branch; **do not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch5_<A|B|C|D>.md` and commit it. Put in it:
   - what you changed or found, and why;
   - every number, with the exact command that produces it;
   - every match or edit you read (counts and locations only if the text names a matter);
   - what you did NOT do;
   - anything the integrator or the user must decide, each as a numbered, self-contained decision
     with the options and your recommendation.

   **Before any claim of "fixed" or "consistent", state the check and whether it passes.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list every
   match and every drop before quoting a rate. For a proposed plan edit, quote the exact current text
   it replaces (row and the first words of the sentence) so the integrator can apply it with an
   anchor.
5. **Tests:** each tool change gets a unit test at its seam. Each test is proven to FAIL with the
   change reverted on a scratch copy, **and the note says how many lines the revert removed** (a
   revert that removed nothing proves nothing). Run the full suite on your own test database before
   your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names, or
   instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget Order
   1901"). Grep your staged diff for session ids, instrument ids and matter words before every
   commit. Rubric patterns, draws and anything quoting a matter stay in the gitignored evidence.
   (FIX_PLAN.md itself names sessions and instruments; your note need not repeat them: cite the row.)
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so Python
   edits over multi-line text must normalise CRLF to LF before matching and restore CRLF on write.
   **A byte-level edit or revert must assert its anchor occurs exactly once before writing** (an LF
   anchor matches nothing in a CRLF file; a `$`-anchored grep finds nothing on a CRLF line). **Never
   run Python with backslashes from a bash heredoc** (it mangles them): use the Edit tool, or write
   the script to a file first. Commit messages go in a file (`git commit -F`), ending with the
   attribution line the harness gives.
8. **Budget: $0.** No model call of any kind: no seam draw, no live Worker, no summariser call, no
   paid API. Read-only GETs to public APIs are not needed in this batch; do not make them.
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** `$PREPILOT_EVIDENCE/seam/batch5/<your letter>/`
    (gitignored). Never write to the session scratchpad. **In batch 4 the harness blocked the Write
    tool outside every worktree**: write to your worktree's own gitignored
    `docs/prepilot-fixes/evidence/seam/batch5/<your letter>/` and, if a shell `cp` to the main
    checkout's path works, copy it there at the end; say in your reply which you did.
11. **When you finish, reply with:**
    - your branch name and the commit list;
    - the test count and the spend;
    - the path of your note, and where your scratch is;
    - for each item: met, closed or not, and why; and the numbered decisions for the user.

## Lessons from batches 1-4 (give these verbatim with each brief)

- **Check your base before anything else.** In all four batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are:
  - `git log --oneline -1`;
  - `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`.

  If HEAD is not `<INTEGRATOR_HEAD>` and you have no commits, run
  `git reset --hard <INTEGRATOR_HEAD>`. Say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a run of a single test file.
  Use plain `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown, so a run on
  the default database breaks the integrator's suite.
- **`summary_probe count --dir` takes a PATH**, not a directory name.
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth; a grader change is judged by whether its verdicts move towards the recorded
  hand-read, never by its pass rate. Do not undo the earlier agreement.
- **Any text the product writes into an answer is read by every grader** (`NEG_ASSERTED`,
  `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`, the halt detectors, the footer
  strippers). Not relevant to a $0 review, but relevant to any amendment you propose.
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree.
- **Check that a gitignored folder is really ignored** (`git check-ignore -v <path>`) before you write
  matter text into it.
- **The plan has been wrong before, and the instrument more often than the product.** A row's own
  evidence, a handover's "new" and a rubric's "inserted by" have each been wrong (Session 36:
  the turn-3 hedged reading was not new; the inserting Act was 2024, not 2019). Check a row's claim
  against the code or the stored evidence before repeating it, and say which you checked.
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
  - `python -m tools.plan_status`;
  - `python -m tools.replay_report --dir <path> <subcommand>`. The subcommands include `negatives`,
    `caselaw`, `scoperecord`, `nosearch`, `halts`, `derivations`, `commencements`, `currency`,
    `modes`, `deadend`, `siblings`, `scripted`, `lookup`, `drgaps`, `blanks`,
    `lost --require-label`, `interpret`, `stance`, `hedges`, `openers`, `sectionscope`,
    `discovery`. `interpret` and `stance` take `--rubric <path>`, `--session`, `--sentences`,
    `--drops`, `--chars`; `derivations` takes `--answers`, `--failing-only`, `--drops`;
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`.
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Run-file turns vs export turns:** for `p32_6406`, export turn = run-file turn + 1 from script
  turn 3 on. `stance` prints export turns.

---

## Agent A: `tools/plan_lint`, and a proposed mechanical fold ($0)

**Read first:** `server_py/tools/plan_status.py` (how it parses rows, ticks and buckets; reuse its
parsing, do not fork it), `$PREPILOT_EVIDENCE/seam/batch4/scratchpad_s36/plan_probe.py` (the probe
to turn into the tool), FIX_PLAN's "How to use this file", "Re-planning protocol", the Ledger's
status legend and the "Bucket → row index".

**Build `python -m tools.plan_lint`** (exit 0 clean, 1 on any error; warnings print but do not fail).
Checks, each a function with a unit test on a synthetic plan string:
1. **Row shape:** every ledger line `| \`[x|~| |-]\` | **Pn.m** | ... |` has the expected number of
   cells (a stray `|` inside a cell splits it); row ids unique.
2. **Bucket index coverage:** every row is named in exactly one bucket line or in the
   `*(no bucket)*` line, or is on an explicit allowlist the tool reads from the plan (propose where:
   for example the `*(no bucket)*` line); report rows in none and rows in more than one.
3. **Done marks:** a `**done**` mark in the index agrees with the row's tick, under ONE convention
   (propose it: mark every ticked row, or none; the note says which and why).
4. **Dependencies:** every `Depends on` id exists; a ticked row depending on an open row is a
   WARNING (it happened by user decision three times) unless the row says why.
5. **The top recommended-order line's counts** ("N of M rows", "K of 14 buckets") agree with
   `plan_status` (WARNING: older lines are history).
6. **`**` parity:** each row line and each added paragraph has an even number of `**`; the file's
   one known odd literal (P0.2) is allowlisted by its exact text.
7. **UTF-8:** the file decodes as UTF-8 (a cp1252 byte broke it on 2026-10-02; fixed in `e5c32b3`).

Then **write, but do not apply,** `$PREPILOT_EVIDENCE/seam/batch5/A/fold_b5_A.py`: a byte script in
the house style (assert each anchor once, CRLF preserved, line count unchanged, even `**` added)
that makes `plan_lint` exit 0 for checks 2 and 3 only (index coverage and done marks), using the
placements agent C proposes where a placement is a judgement (if C's note is not available, place
only the uncontroversial ones: the P0 rows and P1.5 to `*(no bucket)*`, and list the rest as
decisions). Run it on a scratch copy, show `plan_lint` before and after, and show `plan_status`
unchanged (46 of 69, 8 of 14).

**Acceptance (A's part):** `plan_lint` built and tested, each test failing with its check reverted;
on the plan at `<INTEGRATOR_HEAD>` it reports exactly the probe's findings (16 done-mark
mismatches, 21 unindexed rows, 3 dependency warnings) plus anything new, each listed; the fold
script on a scratch copy takes checks 2 and 3 to 0 errors and leaves `plan_status` unchanged.

## Agent B: semantic review, open rows part 1 ($0, a note only)

**Rows:** P0.4 `[~]`, P0.7, P3.2, P3.3, P3.4, P3.6, P3.12, P3.14, P3.17, P3.19, P3.21, P5.4. Read
each row in full, then `notes/batch4_{B,C,D}.md` and `docs/LEGAL_DATA_SOURCES.md` (P3.21, P5.4).

**For each row, one table line and, where needed, a proposed amendment:**
- **Premise still true at HEAD?** Check every function, file, line reference and number the row's
  CURRENT text relies on against the code (`grep`, `git log -S`) or the stored evidence; say which
  you checked. A reference that moved is a mechanical amendment; a premise that no longer holds is a
  decision.
- **Acceptance:** still achievable, still consistent with the row's lever and with other rows'
  acceptances, and stated as booked (n, sessions, graders)?
- **Dependencies and overlaps:** what it depends on and what depends on it, stated or not; overlaps
  with other rows (open or ticked).
- **Status:** is `[ ]`/`[~]` right? Is the row blocked on an external event, and does it say so?

**Must cover, with options and a recommendation each (decisions for the user):**
1. **P3.3's acceptance against its own lever** (known inconsistency 1 above) and P3.17's inherited
   criterion: options include (a) keep the booked criterion and change the lever's wording, (b)
   re-book the criterion to accept a hedged reading offered beside the correct statement, (c) hold
   both until the lawyer answers the pack's supplementary question. Say what each does to the
   recorded verdicts (`wave4_b2_post`, `wave4_b4_post`), by command and by the recorded hand-reads.
2. **The lawyer-blocked chain** (P3.2, P3.3, P3.17): propose one sentence, for the top of the
   ledger or the rows, that states what waits on the pack and what does not.
3. **P3.19:** confirm its premise in `_slim_amendment_results` (`agent/tools/lex.py`) and that its
   acceptance is buildable as booked; say whether it can be built next at $0.
4. **P3.21 against P2.5/P4.18** (the footer that says no date was retrieved) and **P3.12 against
   P4.17**: state the relationship each row should record.
5. **P0.4 and P0.7**: are they still needed, or superseded (P0.7 needs the target)?

**Acceptance (B's part):** every listed row has a table line with the checks named; every
inconsistency found is either a mechanical amendment (exact anchor and replacement text) or a
numbered decision with options; nothing is applied.

## Agent C: semantic review, open rows part 2, and cross-document consistency ($0, a note only)

**Rows:** P3.9, P3.10, P3.20, P3.22, P3.23, P4.3, P4.8, P4.9, P4.12, P4.19, P5.2 `[~]`. Read each
row in full, `docs/LEGAL_DATA_SOURCES.md`, FIX_PLAN's "External review — Thomas" and "Merging back"
sections.

**For each row:** the same table as agent B (premise checked against code or evidence, acceptance,
dependencies and overlaps, status). **Must cover, with options and a recommendation each:**
1. **P3.20 against P5.2** (decision versus build), and whether P5.2 stays `[~]`.
2. **P3.22 and P3.23 against P1.3/P2.2** (the legislation windowing fix) and against P3.9 (the
   case-law date filter, the same `search_case_law` call); whether one build should take P3.9,
   P3.22, P3.23 and P4.19 together, and in what order (each changes what `search_case_law` returns,
   so Invariant 3 applies: do not change retrieval and measure in the same step).
3. **Bucket placement** for every row the probe found in no index line (all 21, not only yours):
   propose a bucket or `*(no bucket)*` for each, with a one-line reason. Agent A's fold uses these.
4. **Cross-document consistency:** CLAUDE.md's `fix/prepilot-defects` paragraph and its "Releases"
   section, CHANGELOG *Unreleased*, `summary-table.html`'s `ROWS` (refs, statuses, which rows are
   Fixed against FIX_PLAN's ticks), `docs/TODO.md` entries the plan cites (D16, D20-D22, B6), and
   `PARALLEL_BATCH_4.md`'s "Open with the user" list: list every statement that is now false, with
   the exact text and the true one. **Do not edit them.**

**Acceptance (C's part):** as B's, plus a placement for each of the 21 rows and the cross-document
list.

## Agent D (optional): the grader gaps from `wave4_b4_post` ($0; rubric edits allowed)

**Include only if the user agrees at launch.** **Read first:** the gitignored
`$PREPILOT_EVIDENCE/rubrics/handread_wave4_b4_post.md` in full (its last section is the work list;
it quotes matters, so nothing from it goes into a committed file), then `notes/batch4_A.md` (how the
last grader batch was done). **Back up both rubrics first** to
`$PREPILOT_EVIDENCE/rubrics/backup_batch5/` and record sha1s before and after.

**The gaps** (wording in the hand-read):
1. `derivations` reads "applications made under section N" (an application made under a section,
   not an instrument's enabling power) as a derivation claim (6370 r3 t3).
2. `INTERP_HEDGE` does not read "on a third reading" or "on the alternative reading" as hedges.
3. `interpret` 6370 still counts reg 3(2)(a) restatements and "does not settle" statements, and a
   sentence about a case (known since `wave4_b2_post`; batch 4 A left them).
4. `stance` p32_6406 missed two affirms (r1 export t12; r2 export t8) and read three denies as none
   (r1 t6, r3 t6, r3 t7).

**Decisions the user takes at launch** (batch 4 A's open items, put in the launch question):
(i) extend the 6338 turn-3 sequence pattern from "must ... precede" to "should precede" / "would
need to conclude before"? (ii) keep the `p32_6406` r2 export t7 implicit-affirm rubric entry?

**Acceptance (D's part):** on `wave4_b4_post` the commands give the recorded hand-read verdicts
(`derivations` 0 unverified; 6370 1 of 3 with r3 PASS; `p32_6406` positions as hand-read, changes
1, 5, 1 by the hand-read's main reading, contradicted 3 of 3); on `wave4_b2_post`, `wave4_b1_post`,
`wave4_p33_post`, `wave4_p33_pre`, `wave4_p32_pre` no verdict moves except toward that directory's
recorded hand-read; `hedges` unchanged over all 57 directories; each code-side test fails with its
change reverted. Report 6370's unhedged count by command against the hand-read's about 4.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit
   (or later: if another session has committed, read what changed and say so); pushed;
   `plan_status` 46 of 69 and 8 of 14 (or the new counts, explained); `plan_probe.py` reproduces the
   findings above; rubric sha1s; the four test databases; nothing running, no
   `server_py/tools/.replay_pin_state.json`; a baseline full suite on `lexchat_test` (2135).
2. **Ask the user once, before launching** (AskUserQuestion): launch A, B and C as set out, all $0?
   Include D? If D: decisions (i) and (ii).
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message.
   Give each its section, plus **Rules for every agent**, **Lessons from batches 1-4** and **Shared
   setup**, verbatim; the integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL`. While they run, do nothing expensive and edit none of their files.
4. **Review each result as it lands** (as in batches 3-4):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines for session ids, instrument ids and matter words
     (`seam/batch3/scratchpad_s35/matter_words.txt`);
   - for A and D, re-run the new tests with the change reverted on a scratch worktree, using a
     script that asserts the anchor count and prints the lines removed
     (`seam/batch4/scratchpad_s36/revert_check.py` and `hunk_anchors.py`, which builds the anchors
     from the diff's hunks);
   - run the full suite on `lexchat_test`;
   - re-run at least one headline number from the note (A: `plan_lint` on the merged tree; B and C:
     spot-check three premise checks each against the code);
   - copy the agent's scratch out of its worktree before removing it, and compare file counts.

   **Merge in the order A, D, B, C**, each `--no-ff`, the suite after each, the branch pushed after
   each clean merge (never `main`).
5. **Assemble the review:**
   - run A's fold script (`fold_b5_A.py`) on the merged tree, after `git log` shows no new commit
     from another session (if one has landed, re-run `plan_lint` and adjust); `plan_lint` checks 2
     and 3 at 0 errors, `plan_status` unchanged;
   - merge B's and C's mechanical amendments (anchors re-checked against HEAD) into one byte script,
     apply it, re-run `plan_lint`;
   - **put every numbered decision from B and C to the user**, grouped (AskUserQuestion, at most four
     questions per call, the recommendation first); apply only what is approved, in a third script;
   - fold into SESSION_LOG (a Session 37 entry) and CHANGELOG *Unreleased* (tooling: `plan_lint`; D's
     grader changes); the edits must ADD an even number of `**` (the file's total is odd from a P0.2
     literal) and put no `|` in a cell.
6. **No after-column in this batch.** If the user wants one (for example P3.19 after it is built),
   it is put to them with a figure first, as before.
7. **Hand over:** a Session 37 entry and a handover for Session 38 in SESSION_LOG.md; the memory
   entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session scratchpad to the
   gitignored `evidence/seam/batch5/scratchpad_s37/`; update the Fix Tracker only if the user asks
   (FIX_PLAN "How to use this file" step 7: read the live artifact and every line of the saved file
   first).

**Open with the user, carried (do not act on the target yourself):** sending the lawyer pack
(`evidence/lawyer_pack/confirmation_pack.md`; confirm the cover note's promise first); deploying
`v2026.09.3` to the target (`pg_dump` first, then pull, restart and `test_apis.ps1`; the local prompt
cache moves to v3 there, so cached summaries empty, which is intended); telling the eval-harness
owner about schema v6; D19's remaining items (deploy by tag; stamp the version on the audit event);
which rows go in the next cut (`v2026.10.1`; P3.16, P4.16, P4.15, P4.18 and P4.17 are "Next
release"); P4.12, D20, D21/D22, P5.2, Thomas's document; from batch 1: the research Worker's
jurisdiction line as a row, the 28 case-law summaries applying English authority to Scotland,
`wave2_p27` 6341 r2 t2; from batch 4: the p37_6373 substitution P4.17's line exposes (B's note
section 4), the control-turn conflict on what Annex XIV Chapter V lists (`handread_wave4_b4_post.md`).
