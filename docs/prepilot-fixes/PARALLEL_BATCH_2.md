# Parallel batch 2: three agents on the open rows, one integrator

**Set up at the end of Session 33 (2026-10-01), for Session 34, at the user's request.** It
follows batch 1 (`PARALLEL_BATCH_1.md`), which worked: four agents in git worktrees, the main
session integrating, one paid after-column put to the user first. Batch 2 keeps the method and
adds the lessons batch 1 taught. The principle is the same: **free and cheap work in parallel;
expensive work serialised, run by the integrator only, and put to the user with a figure
before any money is spent.**

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent** and **Batch 1 lessons**, verbatim. Nothing here should need
re-deriving. If something does, the agent says so in its note rather than guessing. The
matter-specific detail (lawyers' wording, rubric patterns) is NOT in this file. It is in the
gitignored files named below.

---

## Where things stand (verified 2026-10-01)

- **Branch** `fix/prepilot-defects`, head `a449327` or later, pushed. **`main`** is at
  `a6b4a76`, release **`v2026.09.3`** (the third cut, 2026-09-29): everything through Session 33
  is on `main`. Tags `v2026.09.1`, `v2026.09.2` and `v2026.09.3` are all on origin. **Never push
  or merge to `main`**: the next cut (`v2026.10.1`) goes only when the user asks, using the
  procedure in CLAUDE.md *Releases*.
- **Tests: 2035** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives 41 of 59 rows, 8 of 14 buckets. In progress:
  P0.4, P5.2, P3.16 (built; ticking it is the user's call, see below).
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  55 replay directories, the latest after-column being `wave4_b1_post`. Also `rubrics/p32.json`,
  `rubrics/p33.json` (as edited by batch 1's agent B; backups in `rubrics/backup_batch1/`),
  **`rubrics/handread_wave4_b1_post.md`** (the integrator's hand-read of `wave4_b1_post`, whose
  last section lists the grader gaps this batch closes), `seam/batch1/` (batch 1's draws and the
  whole Session 33 scratchpad in `scratchpad_s33/`), and `seam/s32/`.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn running, no pin file (`server_py/.replay_pin_state.json` absent), no
  worktrees. The dev box is on its normal settings (`replay restore` was run). The four
  `worktree-agent-*` branches from batch 1 are merged and can be deleted.
- **Read before anything else:** FIX_PLAN.md ("How to use this file", Invariants, "Data
  handling", the top recommended-order line, rows P3.2, P3.3, P3.16, P3.17, P4.13, P4.15 in
  full), then SESSION_LOG.md from "Session 33 — 2026-09-29 — parallel batch 1" to the end
  (entry, continuation, handover for Session 34, addendum).

---

## The batch

| Agent | Work | Kind | Budget | Main files |
|---|---|---|---|---|
| **A** | Close the grader gaps found in `wave4_b1_post` | tooling + the gitignored rubrics | $0 | `tools/replay_report.py`, `tools/summary_probe.py`, `evidence/rubrics/p32.json`, `p33.json` |
| **B** | The opener strip's verb gap (P4.13's residual, to be booked as **P4.16**) | deterministic product code | $0 | `src/utils/openers.py`, `tests/test_answer_openers.py` |
| **C** | **P3.17**: 6338's general rule, retrieved by its application provision | measure free, then seam | **$3, stop at $3** | `src/prompts.py` and/or `src/agent/`, `tools/` |
| **D** | **P4.15** measured, with options, and evidence for **P3.2**'s next lever. **No product code.** | analysis | $0 | a note, plus a data-free tool if one is needed |

**Not in this batch:** P3.2's lever itself (the user decides the approach, using D's evidence);
P3.16's tick (a user decision, see below); any replay (the integrator's, after merging, put to
the user first).

**Budget:** agents at most $3 in all. Any after-column is the integrator's, priced and put to
the user before it is spent (see the integrator's step 6).

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` (Invariants 1-6, "Data handling", your
   rows in full) and, in `docs/prepilot-fixes/SESSION_LOG.md`, everything from "Session 33 —
   2026-09-29 — parallel batch 1" to the end of the file. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION` or any memory file: the integrator
   folds your results in. Commit on your worktree's branch; **do not push, do not merge, never
   touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch2_<A|B|C|D>.md` and commit it. Put
   in it:
   - what you changed and why;
   - every number, with the exact command that produces it;
   - every dry-run edit or match you read (counts and locations only if the text names a matter);
   - what you did NOT do;
   - anything the integrator must decide.

   **Before any claim of "fixed", state the row's acceptance and whether it is met.**
4. **Measure before building, and list what a change moves.** For any grader or detector, list
   every match and every drop before quoting a rate. For any code rewrite of text, dry-run it
   over every stored answer and read every edit.
5. **Tests:** each product or tool change gets a unit test at its seam. Each test is proven to
   FAIL with the change reverted on a scratch copy, **and the note says how many lines the
   revert removed** (a revert that removed nothing proves nothing: batch 1 lesson). Run the full
   suite on your own test database before your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names,
   or instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget
   Order 1901"). Grep your staged diff for session ids, instrument ids and matter words before
   every commit. Rubric patterns and draws stay in the gitignored evidence.
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so
   Python edits over multi-line text must normalise CRLF to LF before matching and restore CRLF
   on write. **Never run Python with backslashes from a bash heredoc** (it mangles them): use the
   Edit tool, or write the script to a file first. Commit messages go in a file
   (`git commit -F`), ending with the attribution line the harness gives.
8. **Budget:** stop at your figure. `--max-spend` does not exist for seam draws, so count the
   printed costs and estimate each paid step before starting it. Temperature 0 is not
   byte-deterministic: redraw a flagged payload 2-3 times a side, and draw both sides of an A/B
   **the same day**. Guard every paid scratch script with `if __name__ == "__main__":` and never
   import one scratch script from another (Session 32 lost $1.80 that way).
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`. Seam draws read the OpenRouter key from the dev database (read-only) and
   need no server.
10. **When you finish, reply with:**
    - your branch name and the commit list;
    - the test count and the spend;
    - the path of your note;
    - for each row or item: met, closed or not, and why.

## Batch 1 lessons (give these verbatim with each brief)

- **Check your base before anything else.** In batch 1, every worktree the Agent tool made came
  up on `main`, not on the integrator's HEAD. Your first commands are:
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
  hand-read, never by its pass rate.

---

## Shared setup

- **Worktrees:** `isolation: "worktree"`. A worktree has no `server_py/.env`, and that is fine.
- **In a worktree, set on every tool command:**
  - `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`;
  - `PYTHONIOENCODING=utf-8` (the console is cp1252);
  - `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_<a|b|c|d>`.

  Pass `--run`, `--dir` and `--also` paths under `$PREPILOT_EVIDENCE/replay/`.
- **Commands** (run from `server_py/`):
  - `python -m tools.plan_status`;
  - `replay_report` subcommands `interpret [--session S --sentences --drops --drafts --export --rubric R]`,
    `stance [--sentences]`, `hedges`, `openers [--all-dirs --export --strip]`, `caselaw`,
    `negatives`, `modes`, `drgaps`, `discovery --before D --only S`;
  - `summary_probe count|glosses|redraw|panel`;
  - `seam_replay synthesis|worker|manager --run F --turn N [--reps N] [--out D] [--dry-run] [--as-sent --at-rev recorded --date recorded] [--first-round]`;
  - `tools.footer_echo`.
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Model settings for seam draws:** the dev box's (`google/gemini-3.1-pro-preview`, summariser
  `google/gemini-3-flash-preview`), the same that the replays pin.
- **Where draws go:** `$PREPILOT_EVIDENCE/seam/batch2/<agent>/<before|after>/<slot>/`
  (gitignored: draws contain lawyers' matters).

---

## Agent A: close the grader gaps ($0)

**Why now:** graders are fixed BEFORE an after-column, never during one (Session 29's rule).
The batch 1 after-column (`wave4_b1_post`) found the gaps below. The sentences behind each are
in the last section of the gitignored
**`$PREPILOT_EVIDENCE/rubrics/handread_wave4_b1_post.md`**, with the run, rep and turn of each.
**You are the only agent that edits the rubric files.** Before your first edit, copy both to
`$PREPILOT_EVIDENCE/rubrics/backup_batch2/`. Make every edit atomic: raw-text edit, assert the
anchor occurs once, validate with `json.loads`, write a temp file, then `os.replace`.

**The items:**
1. **`stance`** (`p32.json`): the contradicted consequence in two new wordings: `wave4_b1_post`
   p32_6406 r1 export turn 9 and r2 export turn 7. The command read both as "no position".
2. **`interpret`** (`p33.json`, 6370): a NEGATED "do not explicitly state that they apply only
   to …" is counted as the contradicted claim and as asserted (r3 turn 4). It is the correct
   statement.
3. **`INTERP_HEDGE`** (code, `tools/replay_report.py`): "On your reading" is not read as a hedge
   (6370 r1 turn 6).
4. **`p33.json`** 6370's reported-statement exemption misses the form "It returned … decisions,
   such as X, which notes …" (r1 turn 4).
5. **`p33.json`** 6338: two regimes named side by side as both defining the word, which presents
   the later Act as applying (r2 turn 2). The rubric drops it, and it should count as a
   wrong-regime claim.
6. **`summary_probe glosses`** (code): the note filter misses "the text does not contain X;
   therefore, it does not provide Y" (p32_6406 r2 run-file turn 8).
7. **Optional, measure first and fix only if every moved sentence reads right:** Session 32's
   second 6370 over-count, a statement backed by a retrieved citation read as an unhedged
   reading.

**For each change:**
- Run the grader before and after over every directory holding the session: `interpret` over
  every directory holding 6338, 6370 or 6375, and `stance` over every directory holding 6406 or
  6345. Batch 1's agent B listed them in `notes/batch1_B.md`.
- Also run it over `wave4_b1_post` and over the kept seam draws (`seam/s32/`, `seam/batch1/D/`).
- Record every verdict that moves and every sentence that starts or stops counting, as counts
  and locations.
- The booked before-columns must still FAIL: `wave4_p33_pre` 9 of 9; `wave4_p32_pre` 3 of 3,
  plus 6345's 3.
- **In `wave4_b1_post`, the command's verdicts must move towards the recorded hand-read and
  never away from it.** The hand-read: 6338 0 of 3, 6370 0 of 3, 6375 3 of 3, p32_6406 0 of 3.
  Code changes get synthetic tests in `tests/test_replay_interpret.py`,
  `tests/test_replay_stance.py` and `tests/test_summary_probe.py`.

**Deliver:** the commits, the note, and one line per item saying closed, or why not.

## Agent B: the opener strip's verb gap, P4.16 ($0, deterministic)

`src/utils/openers.py`, `_FORMULAS`. The `bare` formula's verb list is challenge, question,
query, push back on, press on, flag, raise and pick up on. P4.13 widened its OBJECT ("my earlier
statement"). In `wave4_b1_post` p32_6406 r2 export turn 5, an answer opened with the unscoped
formula "You are correct to highlight this.", and the strip left it in place.

**The change:**
1. Read every first sentence of every stored answer that opens "You are/You're (absolutely)
   right/correct to <verb> …", and list every verb that occurs.
2. Widen the verb list to the challenge verbs actually found (at least "highlight"). Check the
   `thanks` formula's verbs the same way.
3. Leave scoped agreement ("You are correct that X") and a plain "Yes, that is correct."
   untouched, as the module docstring explains.

**Measure:** `python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/baseline openers --all-dirs --export --strip`
before and after. At `a449327` it reads 1,783 answers, 47 edited, 9 left as written. List and
read every NEW edit.

**Acceptance (to be booked as P4.16):** deterministic. Every new edit read and correct; a test
per new verb, each failing with the change reverted; no other stored answer changed.

## Agent C: P3.17, the general rule's application provision ($3, stop at $3)

**Read the P3.17 row and P3.3's 6338 criteria in full first.** Booked, not to be relaxed: per
rep, turns 1 and 2 name the 1999 Order; no turn asserts that the 2010 Act or the 1978 Act
governs the 2009 Act or s.35ZA; turn 3 says the Act sets no order.

The state in `wave4_b1_post` (hand-read, `handread_wave4_b1_post.md`):
- **Every rep fails ONLY on turn 1.** Turn 1 says the word is undefined. Two reps point to the
  rules for Acts of that date without naming the Order, and one stops there.
- Turn 2 names the Order in 3 of 3, and turn 3 is right in 3 of 3.
- There is one wrong-regime claim (r2 turn 2, Agent A's item 5).
- In `wave4_p33_post`, r2 and r3 retrieved the 2010 Act's Schedule 1 (the definitions) and not
  its s.1 (the provision saying which Acts it applies to).

**Step 1, free: locate the seam.** Over every stored 6338 rep in its lawyer's configuration
(Conversational, legislation and case law: `wave4_p33_pre`, `wave4_p33_post`, `wave4_b1_post`),
split turn 1 and turn 2 into:
- what the Worker searched and retrieved;
- what the summaries carried (`summary_probe`);
- what the Worker report said;
- what the answer said.

Find where the regime is lost at turn 1: never searched for, retrieved but dropped, or retrieved
and not named. Report that before choosing a lever.

**Step 2, paid, only if step 1 locates it: a lever, measured on the seam.**
- The row's candidates:
  - a code-side step: when a Worker's answer turns on an undefined word or cites a general-rule
    instrument, retrieve that instrument's application or commencement provision (the house
    style: Invariant 2, code beats prompt);
  - or a sentence in the Worker prompt naming the application provision as the thing to
    retrieve.
- Use `seam_replay worker` (about $0.03 a draw) or `manager` (about $0.03), redrawing stored
  payloads with `--as-sent --at-rev recorded --date recorded`.
- **Any edit to a Manager or Worker prompt needs the first-delegation drift probe**
  (`seam_replay manager --first-round --date recorded`, 8 sessions, 3 draws a side, about $0.40)
  before and after, on the same day. It must show no brief moving to another instrument.
- A seam pass is not a live pass. Say whether the seam evidence supports putting the lever into
  an after-column.

**Acceptance (the row):** P3.3's 6338 criteria, n=3. That is the integrator's after-column, not
yours.

## Agent D: P4.15, measured with options; evidence for P3.2's next lever ($0, no product code)

**Part 1, P4.15.**
- `replay_report negatives` fails turns where a hybrid turn reached its legislation by
  `lookup_legislation` and section search (P3.7) and ran no `search_legislation`. The footer then
  carries only P2.4's case-law clause, which says what the case-law database holds, but not that
  a search finding nothing is not proof there is none.
- Counts: 3 turns in `wave4_p33_pre`, 4 in `wave4_p33_post` and 2 in `wave4_b1_post`, all 6370.
- Measure over every stored directory: how many turns have this shape, what each footer says,
  and what each answer says about the missing item.
- Then set out the options with their consequences:
  - (a) the case-law clause carries the attribution (product text: what each grader and every
    stored answer would then read; dry-run it);
  - (b) the grader accepts the coverage sentence as attribution (what that stops counting
    everywhere);
  - (c) anything else the evidence shows.
- Recommend one. **Do not build it: the row says it is a decision.**

**Part 2, evidence for P3.2.** P3.2 has failed through three sessions of levers: the opener strip,
the retrieval hint and the prompt clause. In 3 of 3 `wave4_b1_post` reps, the model states a
consequence the regulation contradicts while the decisive passage is in its own context.
- Measure, free, over every stored p32_6406 rep: in each turn that states the contradicted
  consequence (`stance --sentences` plus the hand-read files), whether the decisive passage was in
  that turn's retrieved raw text, in its summary, and in the Worker report. That is the
  precondition for a code-side check of a claim against the text it was retrieved with.
- Also measure what a "disputing turn must re-delegate" rule (lever (a) in the P3.2 row) would
  have changed: how many challenge turns ran no delegation.
- Write it up as evidence for the user's decision, with no recommendation beyond what the
  numbers support.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand":
   - `git status` clean, HEAD `a449327` or later;
   - `python -m tools.plan_status`;
   - the replay directory count (55) and both rubrics present;
   - the four test databases exist;
   - nothing running, no pin file;
   - a baseline full suite on `lexchat_test` (2035).
2. **Ask the user once, before launching** (AskUserQuestion):
   - (i) tick P3.16 now? It is met by hand, and the command reads 1, a note;
   - (ii) launch the batch as set out here? Name the agents and budgets.
3. **Launch A, B, C and D** as background agents with `isolation: "worktree"`. Give each:
   - its section, plus **Rules for every agent** and **Batch 1 lessons**, verbatim;
   - the integrator's HEAD sha as `<INTEGRATOR_HEAD>`;
   - its `PREPILOT_EVIDENCE` and `TEST_DATABASE_URL` values.

   While they run, do nothing expensive and edit none of their files.
4. **Review each result as it lands:**
   - read the note and the diff;
   - grep the diff for session ids, instrument ids and matter words;
   - confirm the branch contains `<INTEGRATOR_HEAD>`;
   - re-run the new tests with the change reverted, confirming lines were removed;
   - run the full suite on `lexchat_test`;
   - re-run at least one headline number from the note.

   **Merge in the order A, B, C, D** (graders first), each with `git merge --no-ff`, the suite
   after each. Push the branch after each clean merge (the user allowed branch pushes in
   Session 33; never `main`).
5. **Fold into FIX_PLAN.md and SESSION_LOG.md.**
   - Book **P4.16** (B's row) in Wave 4, by the re-planning protocol.
   - Tick P4.16 only if its deterministic acceptance is met.
   - Re-grade `wave4_b1_post` and the booked before-columns with A's graders (free), and record
     where the command now agrees with the hand-read.
   - Write one-line ledger rows, keep an even `**` count, put no `|` in a cell, and use a byte
     script that asserts each row is found once.
   - `plan_status` must count 60 once P4.16 is booked.
6. **Before any replay:** put the plan and a dollar figure to the user.
   - If C's lever is supported, the minimum is **6338 x3 in its lawyer's configuration**
     (Conversational, legislation and case law; about $1.20 at `wave4_b1_post`'s $0.34 a rep).
   - If C edited a Manager or Worker prompt, also the rest of P3.3's set (6370, 6375 x3, about $8)
     and P3.2's (`p32_6406` script x3 plus 6345 x3, about $8).
   - Run it into a NEW directory (for example `wave4_b2_post`), following PARALLEL_BATCH_1.md
     step 6 exactly:
     - `replay check`, `replay pin`, uvicorn fresh;
     - keep the machine awake (`scratchpad_s33/keep_awake.py`, which holds a Windows execution
       state and changes no setting);
     - never commit while it runs; if it stalls, re-run the SAME command;
     - then `replay restore`, and stop the server by its PID.
   - Hand-read every `interpret` match and drop and every `stance` "none".
   - Run the exit-1 set (`halts negatives derivations commencements currency scoperecord
     nosearch caselaw modes deadend siblings scripted lookup drgaps blanks "lost --require-label"`;
     `commencements` exits 1 when no graded session is present, which is expected), `hedges`,
     `discovery --before <booked before-column> --only <sessions>` for the `sources_kept` guard,
     `summary_probe count --dir <path>` and `glosses`.
7. **Hand over:**
   - a Session 34 entry and a handover for Session 35 in SESSION_LOG.md;
   - save the hand-read to the gitignored `evidence/rubrics/handread_<dir>.md`;
   - copy the session scratchpad to the gitignored `evidence/seam/batch2/scratchpad_s34/`
     before the session ends;
   - update the memory entry `project_prepilot_freeze.md` and its MEMORY.md line;
   - update the Fix Tracker only if the user asks (FIX_PLAN "How to use this file" step 7: read
     the live artifact and every line of the saved file first).

**Open with the user, carried (do not act on the target yourself):**
- deploying `v2026.09.3` to the target (`pg_dump` first, then pull, restart and
  `test_apis.ps1`; the local prompt cache moves to v3 there, so cached summaries empty, which is
  intended);
- telling the eval-harness owner about schema v6 and the earlier items;
- D19's remaining items (deploy by tag; stamp the version on the audit event, now unblocked);
- the legal readings behind the rubrics, to be confirmed by a lawyer;
- P4.12, D20, D21/D22, P5.2, Thomas's document;
- from batch 1:
  - whether to book the research Worker's jurisdiction line as a row (P3.18's origin);
  - the 28 case-law summaries applying English authority to Scotland;
  - the two change-record id mis-expansions;
  - `wave2_p27` 6341 r2 t2 (an echoed footer followed by the model's own paragraph).
