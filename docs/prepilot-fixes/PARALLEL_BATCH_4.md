# Parallel batch 4: the graders corrected, P4.17 and P4.18 built, P3.17 measured

**Set up at the end of Session 35 (2026-10-02), for Session 36, at the user's request.** It
follows batches 1-3 (`PARALLEL_BATCH_1.md` to `_3.md`), which worked: agents in git worktrees,
the main session integrating, any paid run put to the user first. The principle is unchanged:
**free work in parallel; expensive work serialised, run by the integrator only, and put to the
user with a figure before any money is spent.** Every agent in this batch is $0.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent** and **Lessons from batches 1-3**, verbatim. Nothing here should need
re-deriving; if something does, the agent says so in its note rather than guessing. The
matter-specific detail (lawyers' wording, rubric patterns, the hand-read) is NOT in this file. It
is in the gitignored files named below.

**What the user has already decided (2026-10-02; do not re-open):**
1. **P4.17: build agent C's option (d), with the full clause set.** Instruments are named by id,
   as C's prototype and P3.5's clause do (the integrator may confirm this one sub-choice in the
   launch question). The acceptance is BOOKED on the P4.17 row.
2. **P3.17: measure first, $0.** Locate where the new turn-2 and turn-3 failures arise and set
   out options. Nothing is built until the user chooses. C's deferred code lever and the research
   Workers' PHASE 2c stay deferred.
3. **The four grader gaps are fixed before any further after-column, and one agent may edit the
   gitignored rubrics, with backups first** (as batch 2's agent A did).
4. **P4.18 is booked and fixed in this batch ($0, deterministic):** P2.5's currency clause
   contradicting P3.5's change-record clause on 27 stored footers. Booking it reopened bucket B4.
5. Unchanged from Session 34: **P3.2 stays PARKED** until a lawyer answers the confirmation pack;
   P3.3 cannot be ticked while P3.2 is parked (its booked acceptance includes P3.2's).

---

## Where things stand (verified 2026-10-02, end of Session 35)

- **Branch** `fix/prepilot-defects`, **pushed** (`origin/fix/prepilot-defects` equals local);
  head = the commit adding this file (on top of `67f59b9`). **`main`** is at `a6b4a76`, release
  **`v2026.09.3`**. **Never push or merge to `main`**: the next cut (`v2026.10.1`) goes only
  when the user asks (CLAUDE.md *Releases*). **Branch pushes are allowed** (user decision); if the
  permission classifier refuses one, ask the user and do not work around it.
- **Tests: 2093** (`python -m pytest -q` from `server_py/`, default test database
  `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **44 of 62 rows**, **7 of 14 buckets** (B4
  reopened by P4.18). In progress: P0.4 and P5.2. Fixed since `v2026.09.3`, "Next release":
  P3.16, P4.16, P4.15 (CHANGELOG *Unreleased* lists them).
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - **56 replay directories**, the latest after-column **`wave4_b2_post`** (head `0527c48`,
    $16.99: 6338, 6370, 6375, 6345 x3 plus the `p32_6406` script x3).
  - The booked before-columns: `wave4_p33_pre` (P3.3's) and `wave4_p32_pre` (P3.2's).
  - Rubrics `rubrics/p32.json` (sha1 `e14b76242b5c…`) and `rubrics/p33.json` (sha1
    `dce6d2f5404c…`), unchanged since batch 2. Older backups: `rubrics/backup_batch2/`.
  - **`rubrics/handread_wave4_b2_post.md`**: the last hand-read. Its last section, "Grader gaps
    found", is agent A's work list; its per-session sections are the verdicts A must reproduce.
  - **`lawyer_pack/confirmation_pack.md`**: the confirmation pack (4 readings, 4 yes/no
    questions, 18 links). Not yet sent; sending it is the user's action.
  - `seam/batch3/{A,B,C,D}/`: batch 3's agent scratch. **Agent C's P4.17/P4.18 harness is in
    `seam/batch3/C/`**: `p417_rebuild.py` (rebuilds each turn's search record and footer with the
    product's own recorders and builders), `p417_dryrun.py` (21 subcommands per variant, all 56
    directories), `p417_diff.py`, `p417_rc.py`, `p417_shape.py`, `p417_couplings.py`,
    `p417_option_d.py` (**a scratch prototype, not the product**), `p417_contra.py` (the 27
    contradictions). Agent D's P4.15 dry run is in `seam/batch2/D/`.
  - `seam/batch3/scratchpad_s35/`: Session 35's whole scratchpad, including `grade/` (every
    grader output for `wave4_b2_post`), the run logs, and `verify_pack_links.py` /
    `verify_pack_quotes.py` (the integrator's pack checks).
  - The keep-awake helper: `seam/batch1/scratchpad_s33/keep_awake.py`.
- **Notes from batch 3** (committed): `docs/prepilot-fixes/notes/batch3_{A,B,C,D}.md`. **C's note
  sections 5.2-5.4 and 8 are P4.17's specification; section 7 (f4) is P4.18's.**
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, **no pin file** (it lives at **`server_py/tools/.replay_pin_state.json`**,
  `STATE_PATH` in `tools/replay.py`, not `server_py/`), no worktrees. Twelve merged
  `worktree-agent-*` branches and `batch3-B` remain locally and can be deleted.
- **Read before anything else:**
  - FIX_PLAN.md: "How to use this file", the Invariants, "Data handling", the top
    recommended-order line ("end of Session 35"), and rows **P2.5, P2.8, P3.3, P3.5, P3.17,
    P4.15, P4.17 and P4.18** in full.
  - SESSION_LOG.md, from "Session 35 — 2026-10-01 — parallel batch 3" to the end of the file:
    the interim entry, the continuation, the handover for Session 36 and both addenda.

---

## The batch

| Agent | Work | Kind | Budget | Main files |
|---|---|---|---|---|
| **A** | **The four grader gaps** found in `wave4_b2_post`'s hand-read | tooling + gitignored rubrics | $0 | `tools/replay_report.py` (`interpret`, `stance`, `INTERP_HEDGE`), `tests/test_replay_tooling.py`, `evidence/rubrics/p32.json`, `p33.json` |
| **B** | **P4.17 (d)**: the section-search scope line, full clause set | deterministic product code | $0 | `src/utils/search_scope.py` (a new builder), `src/agent/agent_core.py` (two assembly sites), a new test file, one new grader line in `tools/replay_report.py` |
| **C** | **P4.18**: the currency clause's contradiction | deterministic product code | $0 | `src/utils/search_scope.py` (`_currency_footer_clause` only), `tests/test_search_scope.py` |
| **D** | **P3.17 measured with options**, plus the **s.35ZA insertion point** for the lawyer pack. **No product code.** | analysis | $0 (plus free read-only LEX GETs) | a note; the gitignored pack |

**Merge order: A, then C, then B, then D** (graders before the product they grade; C's small
change before B's larger one in the same file). **Collision points, by design:** B and C both
edit `search_scope.py` (C only inside `_currency_footer_clause`, about line 1262; B adds a new
builder and touches nothing of C's function); A and B both edit `tools/replay_report.py` (B adds
its grader line as a NEW function and subcommand appended near the end of the file; A must not
touch `nosearch` or B's area). The integrator resolves any textual conflict at merge.

**Not in this batch:** any replay (the integrator's, after merging, put to the user first); any
P3.2 lever (parked); any P3.17 lever (measure only); any rubric edit except by agent A.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` (Invariants 1-6, "Data handling", your
   rows in full) and, in `docs/prepilot-fixes/SESSION_LOG.md`, everything from "Session 35 —
   2026-10-01 — parallel batch 3" to the end of the file. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION` or any memory file: the
   integrator folds your results in. **Only agent A edits a rubric file.** Commit on your
   worktree's branch; **do not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch4_<A|B|C|D>.md` and commit it. Put
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
   writing** (an LF anchor matches nothing in a CRLF file; a `$`-anchored grep finds nothing on a
   CRLF line). **Never run Python with backslashes from a bash heredoc** (it mangles them): use
   the Edit tool, or write the script to a file first. Commit messages go in a file (`git commit
   -F`), ending with the attribution line the harness gives.
8. **Budget: $0.** No model call of any kind: no seam draw, no live Worker, no summariser call.
   (Agent D alone may make read-only GET requests to the public LEX API, which is not a model
   and costs nothing.)
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** `$PREPILOT_EVIDENCE/seam/batch4/<your letter>/`
    (gitignored). Never write to the session scratchpad. **If the harness blocks writes outside
    your worktree** (it did for one batch 3 agent), write to your worktree's own gitignored
    `docs/prepilot-fixes/evidence/seam/batch4/<your letter>/` instead and say so in your reply,
    so the integrator copies it out before removing the worktree.
11. **When you finish, reply with:**
    - your branch name and the commit list;
    - the test count and the spend;
    - the path of your note, and where your scratch is;
    - for each row or item: met, closed or not, and why.

## Lessons from batches 1-3 (give these verbatim with each brief)

- **Check your base before anything else.** In all three batches every worktree the Agent tool
  made came up on `main`, not on the integrator's HEAD. Your first commands are:
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
  hand-read verdict recorded up to then; `wave4_b2_post` found four new gaps. Do not undo the
  earlier agreement.
- **Any text the product writes into an answer is read by every grader.** Check what your words
  do to `NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`, the halt
  detectors and the footer strippers, not only the detector you are aiming at. In batch 3 C's
  first P4.17 wording tripped `NEG_ASSERTED` ("a search ... did not return"), and D's first two
  P4.15 wordings tripped `NEG_LIMITS` and `NEG_TERMS`; "ranked" trips `NEG_LIMITS`.
- **A dry run must use the BUILT code, never a prototype or a retyped string.** Batch 3's brief
  caught D's script defaulting to an old wording; pass the built constant or import the built
  builder, and assert the two are the same before trusting the result.
- **Check that a gitignored folder is really ignored** (`git check-ignore -v <path>`) before you
  write matter text into it. Batch 3's `lawyer_pack/` was not, until the integrator added it.

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
    `lost --require-label`, `interpret`, `stance`, `hedges` and `openers`. `interpret` and
    `stance` take `--rubric <path>`, `--session`, `--sentences`, `--drops`, `--chars`;
  - `python -m tools.footer_echo --dir <path>`;
  - `python -m tools.summary_probe count|glosses`;
  - `python -m tools.lex_probe` (agent D: the LEX API evidence probes).
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Run-file turns vs export turns:** for `p32_6406`, export turn = run-file turn + 1 from script
  turn 3 on. `stance` prints export turns.

---

## Agent A: the four grader gaps ($0; rubric edits allowed)

**Read first:** `$PREPILOT_EVIDENCE/rubrics/handread_wave4_b2_post.md` in full (gitignored; it
quotes matters, so nothing from it goes into a committed file), then `notes/batch2_A.md` (how the
last grader-gap batch was done) and `notes/batch1_B.md`.

**Back up both rubrics first** to `$PREPILOT_EVIDENCE/rubrics/backup_batch4/` and record their
sha1s before and after in your note.

**The four gaps** (the hand-read's "Grader gaps found"; quoted wording is in that file):
1. `interpret`, 6338 turn 3: a hedged sequence reading ("on one reading, ... must precede ...")
   is not matched. P3.3's booked criterion fails it ("a hedged conclusion that they must be
   sequential still fails"), so it must grade as the sequence conclusion, hedged or not.
2. `interpret`, 6338 turn 2: an "overlap" framing that offers the newer interpretation Act as one
   of two readings for the inserted section is graded only through a TRUE sentence about the
   inserting Act. Make the wrong-regime reading itself the match, and stop the true sentence
   matching.
3. `interpret`, 6370: an "As you suggest, they apply ..." agreement is counted as a hedge (it is
   a firm agreement; "on/under the reading you suggest" stays a hedge, batch 2's rule), and four
   firm readings sit in the drops (listed in the hand-read).
4. `stance`, `p32_6406`: a negated sentence ("not defined as a 'rendered fat' ..., it cannot
   reach an end point under Chapter XI") is read as AFFIRM, and the contradicted consequence is
   missed there (r2 export t8) and in r1 export t9.

Put each fix where it belongs: generic behaviour (hedge words, negation handling) in code with
synthetic tests; matter-specific patterns in the gitignored rubric.

**Measure before and after**, over every directory each grader reads (`interpret` and `stance`
with their rubrics; `hedges`), and list every match, drop, verdict and count that moves.
**Acceptance (A's part):**
- On `wave4_b2_post` the commands give the recorded hand-read verdicts: 6338 r1 PASS, r2 FAIL
  (turn 3), r3 FAIL (turns 2 and 3); 6370 0 of 3; 6375 2 of 3; `p32_6406` 0 of 3 with position
  changes 2, 3, 3 and the contradicted consequence in 3 of 3.
- On `wave4_b1_post`, `wave4_p33_post`, `wave4_p33_pre` and `wave4_p32_pre`, no verdict moves
  except toward that directory's recorded hand-read (Session 33 and 34 entries, and
  `handread_wave4_b1_post.md`).
- `hedges` over `wave4_b2_post` still 0 hedged retrieval statements and 0 blanket caveats.
- Each code-side test fails with the change reverted.

Say whether it is met. Report 6370's unhedged count by command against the hand-read's about 15.

## Agent B: P4.17 (d), the section-search scope line ($0, deterministic)

**Read first:** the P4.17 row in full (its booked acceptance is your acceptance);
`notes/batch3_C.md` sections 1-5 and 8; P2.8's row; the `_SEARCH_TOOLS` comment in
`src/utils/search_scope.py` (about line 2531); `answer_scope_footer`, `carried_scope_footer`,
`lookup_scope_footer`, `case_law_scope_footer` and `_case_law_body`; the two assembly sites in
`src/agent/agent_core.py` (about line 1068, the Manager path: fresh, then carried, then lookup,
then case-law; about line 1421, the Deep Research path); and `tests/test_search_scope.py`
(`test_footer_trips_no_detector`, about line 1016; `test_a_turn_that_searched_gets_no_carried_line`,
about line 1523), `tests/test_case_law_gap.py` and `tests/test_echoed_footer.py`.

**The change:** a new builder in `search_scope.py` that fires if and only if the turn recorded a
`search_legislation_sections` and no `search_legislation`. One line, `*Search scope: for this
reply the text of <ids> in the legislation index was searched for <terms>. <the new sentence>
<the fresh footer's clause set>*`, starting from C's prototype (`p417_option_d.py`) and its
checked wording: the new sentence trips only `NEG_BLAMED_INDEX` (avoid "did not return", which
trips `NEG_ASSERTED`; avoid "ranked", which trips `NEG_LIMITS`; avoid "not found in this index",
false in P3.12's case). Slot it after the carried line and before the lookup line on the Manager
path, and after the fresh footer on the Deep Research path. It carries the lookup clause itself,
so the lookup line does not also fire. Not suppressed by `scope_unknown`. Not read by
`_FRESH_FOOTER` (P2.8 must never carry it). Amend
`test_a_turn_that_searched_gets_no_carried_line`'s docstring ("so it stays silent") without
weakening the test.

**The grader line** (part of the booked acceptance, item 3): a new function and subcommand
appended near the end of `tools/replay_report.py` (do not edit `nosearch`; agent A owns the
graders above): a section-search line on a turn that ran `search_legislation`, or ran no section
search, is MISATTRIBUTED; a turn of the shape without the line is MISSING. Exit 1 on either.
Over the stored directories it should report every shape turn as MISSING (none carries the line
yet) and nothing MISATTRIBUTED; say so.

**Measure** with C's harness, importing YOUR built builder (assert your builder's output equals
what the dry run inserts; do not use the prototype): over all 56 directories, the line lands on
exactly the shape turns (29 at C's count plus 8 in `wave4_b2_post`) and nowhere else, including
through the history; list every verdict that moves in the 21 subcommands and check each against
C's 5.3 table (with P4.15 (a) now in, expect `negatives` FAIL to PASS on `wave3_p35` 6409 r2 t3
and `wave4_p33_post` p32_6406 r1 t4, and `summary`'s counter artefacts). Read every one of the
37 edited lines. If your dry run differs from C's, stop and report it.

**Acceptance (B's part, deterministic):** the booked items (1) and (2) met, the grader line
built and tested, each new test failing with the change reverted. Item (3) is the integrator's
after-column. Say whether it is met.

## Agent C: P4.18, the currency clause's contradiction ($0, deterministic)

**Read first:** the P4.18 row (its acceptance is yours); `notes/batch3_C.md` section 7 (f4);
P2.5's and P3.5's rows; `_currency_footer_clause` (about line 1262) and
`_relations_footer_clause` (about line 865) in `src/utils/search_scope.py`;
`tests/test_search_scope.py` `test_footer_trips_no_detector`.

**Measure first:** `python $PREPILOT_EVIDENCE/seam/batch3/C/p417_contra.py` (27 of 455) and list
the 27 by directory, session, rep and turn. Read what each footer says.

**The change:** only inside `_currency_footer_clause`. When a change record WAS consulted for an
instrument (a `kind == "relations"` entry) but returned no commencement or repeal relation, the
clause must not say no change record was consulted. Say what is true instead (for example that
the change record consulted held no commencement or repeal relation for it, so in-force status is
still not established), keeping the no-check wording for a turn that consulted none. Keep it
clear of `NEG_ASSERTED`, `DERIVATION_ASSERTED`, P3.5's commencement detectors and
`CURRENCY_ASSERTED` (the function's docstring explains why; `test_footer_trips_no_detector` pins
it); extend that test rather than weakening it.

**Measure after** with C's rebuild harness (product builders, your branch): the 27 contradictions
go to 0; list every verdict that moves in the 21 subcommands over all 56 directories, and read
every changed footer. Watch `currency` (P2.5's own grader) and `commencements` in particular.

**Acceptance:** the P4.18 row's acceptance. Say whether it is met. The integrator ticks it at
merge if it is (deterministic, n=1).

## Agent D: P3.17 measured with options, and the s.35ZA insertion point ($0; no product code)

**Read first:** the P3.17 and P3.3 rows in full; `notes/batch2_C.md` (PHASE 2c and why);
`handread_wave4_b2_post.md`'s 6338 section; `lawyer_pack/confirmation_pack.md`'s Reading 2.

**Part 1, P3.17.** In `wave4_b2_post`, turn 1 names the right order in 3 of 3, but r3 turn 2
offers the newer interpretation Act as one of two readings for the inserted section, and r2 and
r3 turn 3 offer a hedged "the consultation must precede" reading (new: no earlier stored rep
does). For each of these turns, and for the clean ones as contrast, over every stored 6338 rep in
its lawyer's configuration (`wave4_p33_pre`, `wave4_p33_post`, `wave4_b1_post`,
`wave4_b2_post`):
- trace where the reading first appears: the raw tool results, the summaries the Worker saw,
  the Worker's report, or only the Manager's answer;
- whether PHASE 2c's extra retrieval (the newer Act's application provision) is what fed the
  turn-2 reading;
- whether P3.3's prompt clause ("give what the text does not settle as a reading") is what turns
  a structural argument into a hedged reading at turn 3;
- then set out options with their consequences (for example: a sharper clause in the
  quick-lookup Worker or conversational Manager prompt, with the drift probe it would need; a
  code-side check; waiting for the lawyer's answer to the pack's question, part 3, since the
  booked criterion itself is one of the readings the pack asks a lawyer to confirm), recommend
  one, and state what an after-column would need to measure. **Do not build anything, and draw
  no seam.**

**Part 2, the s.35ZA insertion point.** All three `wave4_b2_post` 6338 reps say s.35ZA was
inserted by a 2024 Act (`section 2(17)`); the rubric's reading and the pack say the 2019 Act;
stored change records carry relations in which the 2024 Act inserted text into s.35ZA (s.6(2),
type inserted). Establish, from the stored tool results first and then, if needed, read-only GETs
to the LEX API (`/amendment/search`, `/amendment/section/search`; `python -m tools.lex_probe` and
the `external-apis` skill describe them, including the http/https duplicate and silent-truncation
traps), which Act inserted the section and which inserted text into it. Record every URL and
response you rely on in your scratch folder. Then:
- add one short "A point our records leave unclear" note to Reading 2 of the pack (gitignored;
  keep its style: plain language, no lawyer quoted, no reading restated beyond what is recorded),
  citing only URLs a tool returned or that you fetched and recorded;
- if the evidence shows the rubric's or FIX_PLAN's "inserted by" statement is wrong, say so in
  your note for the integrator and the user. Do not edit the rubric (agent A owns it) or the
  pack's question.

**Commit only** `docs/prepilot-fixes/notes/batch4_D.md`: it names no matter, instrument or
reading (counts, directories, reps, turns and seams only), says where the pack edit is, and
lists the options.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand":
   - `git status` clean; HEAD is the commit adding this file, and pushed;
   - `python -m tools.plan_status` gives 44 of 62 and 7 of 14 buckets;
   - 56 replay directories and both rubric sha1s as above;
   - the four test databases exist;
   - nothing running (no python process, port 8000 free) and **no
     `server_py/tools/.replay_pin_state.json`**;
   - a baseline full suite on `lexchat_test` (2093).
2. **Ask the user once, before launching** (AskUserQuestion): launch the batch as set out here?
   Name the four agents, all $0. In the same question, confirm "instruments named by id" for B.
3. **Launch A, B, C and D** as background agents with `isolation: "worktree"`, in one message.
   Give each:
   - its section, plus **Rules for every agent**, **Lessons from batches 1-3** and **Shared
     setup**, verbatim;
   - the integrator's HEAD sha as `<INTEGRATOR_HEAD>`;
   - its `PREPILOT_EVIDENCE` and `TEST_DATABASE_URL` values.

   While they run, do nothing expensive and edit none of their files.
4. **Review each result as it lands:**
   - confirm the branch contains `<INTEGRATOR_HEAD>`;
   - read the note and the diff;
   - grep the added lines for session ids, instrument ids and matter words (a list is in
     `seam/batch3/scratchpad_s35/matter_words.txt`; add any new matter's words);
   - re-run the new tests with the change reverted on a scratch worktree, using a script that
     **asserts the anchor count and prints how many lines it removed**
     (`seam/batch3/scratchpad_s35/revert_check.py`);
   - run the full suite on `lexchat_test`;
   - re-run at least one headline number from the note;
   - **copy the agent's scratch out of its worktree** (`<worktree>/docs/prepilot-fixes/evidence/
     seam/batch4/<L>/`) into the main checkout's `evidence/seam/batch4/<L>/` before removing the
     worktree, and compare file counts.

   For A, re-run `interpret` and `stance` over the five directories in its acceptance and confirm
   the verdicts. For D, open the pack edit: every link must be one a tool returned or D fetched
   and recorded, and it must quote no lawyer (`verify_pack_links.py`, `verify_pack_quotes.py`).

   **Merge in the order A, C, B, D**, each with `git merge --no-ff`, the suite after each, and
   push the branch after each clean merge.
5. **After C and B are both merged:** re-run B's rebuild dry run and C's `p417_contra.py` on the
   merged tree, and record what moves (expected: the 27 contradictions at 0, the line on exactly
   the shape turns, and the verdicts B listed). Then fold into FIX_PLAN.md and SESSION_LOG.md:
   - **tick P4.18** if its acceptance is met (deterministic);
   - annotate P4.17 (items 1 and 2 met or not; item 3 waits for the after-column);
   - annotate P3.17 with D's options, and P3.3 and P3.2 with A's grader changes;
   - add a CHANGELOG *Unreleased* entry for each product change (P4.17's line, P4.18's
     wording) and for A's grader changes as tooling;
   - write one-line ledger rows, with no `|` in a cell;
   - use a byte script that asserts each row is found once and that the edits ADD an even number
     of `**` (the file's total is already odd, from a literal in P0.2);
   - `plan_status` stays at 62 unless a row is booked.
6. **Before any after-column: put the plan and the figure to the user** (AskUserQuestion).
   - **What it measures:** P4.17's item (3) live, which needs turns of the shape. `wave4_b2_post`
     had them in `p32_6406` (1 with no footer) and 6370 (7 hybrid turns). Re-measured as guards:
     P3.2 (parked) and 6370's half of P3.3, now with A's corrected graders.
   - **Proposed run:** `wave4_b4_post`: 6370 x3, then the `p32_6406` script x3.
   - **Estimate:** from `wave4_b2_post`, 6370 cost $0.72, $0.94 and $1.00 a rep ($2.66) and the
     script $5.70: **about $8.50, cap $12**.
   - **Procedure**, from `server_py/`:
     - `python -m tools.replay check`, then `python -m tools.replay pin` (the pin file appears at
       `server_py/tools/.replay_pin_state.json`);
     - start uvicorn fresh: `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`, in
       the background (PowerShell `Start-Process -PassThru` gives the real Windows PID), logging
       to a file in the session scratchpad; confirm `/api/bot-info` shows the merged build;
     - start the keep-awake helper in the background and record its PID;
     - `python -m tools.replay run --session 6370 --reps 3 --max-spend 4 --out-dir
       C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b4_post`;
     - `python -m tools.replay run --script
       C:/Projects/LexChat/docs/prepilot-fixes/evidence/scripts/p32_6406.json --reps 3
       --max-spend 8 --out-dir C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b4_post`;
     - `--max-spend` is checked between reps only, so it can overshoot by one rep. If the total
       passes $10, stop and ask before going on;
     - **never commit while a run is going.** If a run stalls (watch for 15 minutes with no log
       growth), re-run the SAME command: it resumes;
     - then `python -m tools.replay restore`, stop uvicorn and the helper by their PIDs, and
       confirm there is no pin file, no python process and port 8000 free.
7. **Grade `wave4_b4_post`.** Hand-read every `interpret` match and drop, every `stance` "none",
   and every negative on a turn of P4.17's shape. Save the hand-read to the gitignored
   `evidence/rubrics/handread_wave4_b4_post.md`.
   - **P4.17 item (3):** B's new subcommand (every shape turn carries the line, no other does),
     `negatives` on every shape turn, each hand-read; no other exit-1 subcommand worse than
     `wave4_b2_post`. **Tick P4.17 only if (1), (2) and (3) are met.** If no turn of the shape
     occurs, say so; (3) carries.
   - **P3.2** (parked, re-measure) and **6370** (P3.3's criteria): record; neither is tickable.
   - **Guards:** `hedges`; the exit-1 set (`halts negatives derivations commencements currency
     scoperecord nosearch caselaw modes deadend siblings scripted lookup drgaps blanks "lost
     --require-label"`; `commencements` exits 1 when no graded session is present, expected);
     `openers`; `tools.footer_echo`; `caselaw` TWO_LINES 0; `replay_report --dir <after>
     discovery --before C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b2_post
     --only 6370 p32_6406` (`sources_kept` per slot not lower in more than 1 slot).
8. **Hand over:**
   - a Session 36 entry and a handover for Session 37 in SESSION_LOG.md;
   - the memory entry `project_prepilot_freeze.md` and its MEMORY.md line;
   - copy the session scratchpad to the gitignored `evidence/seam/batch4/scratchpad_s36/`;
   - update the Fix Tracker only if the user asks (FIX_PLAN "How to use this file" step 7: read
     the live artifact and every line of the saved file first; if asked, P4.18, and P4.17 if
     ticked, become Fixed "Next release").

**Open with the user, carried (do not act on the target yourself):**
- sending the lawyer confirmation pack (after D's s.35ZA note), which is how P3.2 un-parks and how
  P3.3's readings are settled; confirm the cover note's promise first;
- deploying `v2026.09.3` to the target (`pg_dump` first, then pull, restart and
  `test_apis.ps1`; the local prompt cache moves to v3 there, so cached summaries empty, which is
  intended);
- telling the eval-harness owner about schema v6;
- D19's remaining items (deploy by tag; stamp the version on the audit event);
- which rows go in the next cut (`v2026.10.1`; P3.16, P4.16 and P4.15 are "Next release");
- P4.12, D20, D21/D22, P5.2, Thomas's document;
- from batch 1: whether to book the research Worker's jurisdiction line as a row; the 28 case-law
  summaries applying English authority to Scotland; the two change-record id mis-expansions;
  `wave2_p27` 6341 r2 t2.
