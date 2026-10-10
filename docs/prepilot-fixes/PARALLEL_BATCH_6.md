# Parallel batch 6: the next rows by severity (P3.19, P3.24, P4.21; P3.12 and P3.25 measured)

**Set up on 2026-10-05, after Session 37, for Session 38, at the user's request** ("provide a prompt to
kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-5
(`PARALLEL_BATCH_1.md` to `_5.md`): agents in git worktrees, the main session integrating, nothing
merged or applied that the integrator has not re-checked. **Every agent in this batch is $0 and no
replay is run.** The principle is unchanged: free work in parallel; anything expensive serialised,
run by the integrator only, and put to the user with a figure first.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent**, **Lessons from batches 1-5** and **Shared setup**, verbatim. Nothing here
should need re-deriving; if something does, the agent says so in its note rather than guessing.
Matter-specific detail (lawyers' wording, rubric patterns, hand-reads, Thomas's report) is NOT in
this file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first), **unless a dependency means it
   can't be** (2026-10-05). Within a severity: first a row a higher-severity row needs, then $0
   deterministic work before a paid replay, and rows waiting on an outside party last. The order is
   FIX_PLAN's top recommended-order line ("as at 2026-10-05, after Thomas's 30 September retest").
2. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack** (parked; a BLOCKED note heads each row,
   Blocked on the tracker). Nothing in this batch touches them. Sending the pack is the user's
   action (`evidence/lawyer_pack/confirmation_pack.md`, sha1 `d26bb016…`, not sent).
3. **Thomas's 30 September retest is booked** as P3.24-P3.26 and P4.20-P4.22 (FIX_PLAN section
   "External review — Thomas, 30 September 2026"). Their rows are the spec.
4. **P4.8's strip is to be built** (batch 5 C5), but it is P3, so it waits behind the P1 and P2 rows.
5. **Agents propose; the integrator applies; the user approves anything not mechanical**, including
   any wording a lawyer will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md,
   CLAUDE.md, `summary-table.html`, `docs/TODO.md`, a rubric, the lawyer pack or a memory file.
6. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks.
   Branch pushes are allowed; if the permission classifier refuses one, ask the user.
7. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-05, end of Session 37's third addendum)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit (after `0e4eef2`).
  **`main`** at `a6b4a76`, release **`v2026.09.3`**.
- **Tests: 2162** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **47 of 75 rows**, **8 of 14 buckets**.
  **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings): run it after every FIX_PLAN fold.
- **Open P1 rows:** P3.19 and P3.24 (buildable); P3.2 and P3.17 (Blocked).
- **Fix Tracker v35** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`): 74 rows, 42 Fixed, 26 Verified, 3 Blocked, 3 TBV.
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - 57 replay directories under `replay/`, the latest `wave4_b4_post`; every one ran on the pinned
    `google/gemini-3.1-pro-preview`.
  - Rubrics `rubrics/p32.json` (sha1 `31379ecf…`) and `p33.json` (`0031831b…`); backups in
    `rubrics/backup_batch5/`.
  - Thomas's retest: `seam/thomas_s37/2026-09-30-evals-developer-report.md` and the census scripts
    `thomas_census.py`, `thomas_census2.py`, `extent_census.py` beside it.
  - Batch 5 scratch: `seam/batch5/{A,B,C,D,integrator,scratchpad_s37}/`. **P3.19's measuring script
    is `seam/batch5/B/p319_scope.py`** (walks every stored change-record response with the built
    slimmer). The integrator's review tools are `seam/batch4/scratchpad_s36/revert_check.py` and
    `hunk_anchors.py`; the matter-word list is `seam/batch3/scratchpad_s35/matter_words.txt`.
- **Notes from batch 5** (committed): `docs/prepilot-fixes/notes/batch5_{A,B,C,D}.md`. B's note
  holds P3.19's measurement and premise check; C's holds the case-law rows.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no worktrees.
  Twenty merged `worktree-agent-*` branches and `batch3-B` remain locally and can be deleted.

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.19** (P1) | Keep each change-record relation's changed/effecting pairing; state a cut list's window | product, deterministic | $0 | `server_py/src/agent/tools/lex.py` (`_slim_amendment_results`), `tests/test_amendment_relations.py` |
| **B** | **P3.24** (P1), measure first | A detector for negative commencement and currency claims; the count; lever options | tooling + a note; **no product code** | $0 | `server_py/tools/replay_report.py` (a new subcommand), a new test file, `tests/test_search_scope.py` (register the detector) |
| **C** | **P4.21** (P2) | Reword the lookup footer clause so it no longer says the citation is not wrong | product, deterministic; **wording put to the user before merge** | $0 | `server_py/src/utils/search_scope.py` (`_lookup_footer_clause`, ~line 2354), its tests |
| **D** | **P3.12** and **P3.25** (both P2), measure first | Two measurements and option sets; no code | analysis, a note only | $0 | `notes/batch6_D.md` |

**Why these four.** They are the rows the severity order puts first that can run in parallel at $0
without touching each other's files: the two buildable P1s (P3.19 builds; P3.24 must be measured
before any lever is chosen, by its row), then the P2s in order (P3.12 first because P3.2 needs it,
then P4.21 and P3.25). P3.12's and P3.25's own first steps are measurements, so D does those and
builds nothing. **Not in this batch:** any replay or seam draw; P3.24's or P3.12's lever (the user
chooses after the measurement, with a replay figure); the case-law build (P4.19, P3.23, P3.9,
P3.22); anything Blocked; P4.8 and the other P3 rows.

**Merge order: A, B, C, D.** Collision points: A owns `lex.py`; B owns `replay_report.py`; C owns
`search_scope.py`; D commits only its note. **B and C meet in one place:** C's new footer wording
must not trip any detector, and B adds a detector. So B registers its detector in
`tests/test_search_scope.py::test_footer_trips_no_detector` (which imports named detectors:
`NEG_ASSERTED`, `derivation_claims`, `_currency_asserted` and others), and the integrator merges B
before C and re-runs that test after C. If both edit that test file, the integrator resolves it by
hand. A and C do not meet: P3.19 changes what the tool returns, and the footer clauses read only
counts (`by_other_legislation`, `provisions_commenced`), as batch 5 B checked.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the top recommended-order line, the paragraph above the Ledger
   on what waits on the lawyer pack, and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`,
   everything from "Session 37 — 2026-10-02 — parallel batch 5" to the end of the file. Do not
   re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`, any
   `PARALLEL_BATCH_*.md`, any rubric, the lawyer pack or any memory file: the integrator folds your
   results in. Commit on your worktree's branch; **do not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch6_<A|B|C|D>.md` and commit it. Put in it:
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
   revert that removed nothing proves nothing). Run the full suite on your own test database before
   your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names, or
   instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget Order
   1901", `ssi/1901/3`). Grep your staged diff for session ids, instrument ids and matter words before
   every commit. Rubric patterns, draws, hand-reads and anything quoting a matter stay in the
   gitignored evidence. (FIX_PLAN.md names sessions and instruments; your note need not repeat them:
   cite the row.)
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so Python
   edits over multi-line text must normalise CRLF to LF before matching and restore CRLF on write.
   **A byte-level edit or revert must assert its anchor occurs exactly once before writing** (an LF
   anchor matches nothing in a CRLF file; a `$`-anchored grep finds nothing on a CRLF line). **Never
   run Python with backslashes from a bash heredoc** (it mangles them): use the Edit tool, or write
   the script to a file first. Commit messages go in a file (`git commit -F`), ending with the
   attribution line the harness gives.
8. **Budget: $0.** No model call of any kind: no seam draw, no live Worker, no summariser call, no
   paid API. No calls to LEX, the National Archives or legislation.gov.uk either: every measurement
   here runs over stored evidence.
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** your worktree's gitignored
    `docs/prepilot-fixes/evidence/seam/batch6/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch6/<your letter>/` (this worked for
    all four agents in batch 5). Never write to the session scratchpad. Say in your reply which you did.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend; the path of your note and where your scratch is; for each item, met or not and why; and
    the numbered decisions for the user.

## Lessons from batches 1-5 (give these verbatim with each brief)

- **Check your base before anything else.** In all five batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are `git log --oneline -1` and
  `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`. If HEAD is not `<INTEGRATOR_HEAD>` and you
  have no commits, run `git reset --hard <INTEGRATOR_HEAD>`, and say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a single test file. Use plain
  `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown, so a run on the
  default database breaks the integrator's suite.
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth; a detector is judged by whether its verdicts match what a careful reader would say,
  never by its rate. Read every match and every drop.
- **Any text the product writes into an answer is read by every grader** (`NEG_ASSERTED`,
  `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`, `derivation_claims`,
  `_currency_asserted`, the halt detectors, the footer strippers). New footer wording is screened
  against all of them (`test_footer_trips_no_detector`); P2.2's own footer once corrupted its
  denominator.
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree.
- **Check that a folder is really gitignored** (`git check-ignore -v <path>`) before you write matter
  text into it. **`docs/prepilot-fixes/evidence/` itself is NOT ignored**, only its listed subfolders
  (`seam/`, `replay/`, `rubrics/`, `lawyer_pack/` and others); `evidence/external/` was not.
- **The plan has been wrong before, and the instrument more often than the product.** Check a row's
  claim against the code or the stored evidence before repeating it, and say which you checked.
  Batch 5 found a row's count wrong (P3.3's "7 of 9" was 6 of 9) and a brief's statement half-true
  (`plan_status` reads the Bucket index's B-lines for membership, not only the ticks).
- **Thomas tests on a different model** (`glm-5.2:cloud`); every stored replay here ran on the
  pinned Gemini. Say which model a number comes from.
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
    `modes`, `deadend`, `siblings`, `scripted`, `lookup`, `drgaps`, `blanks`,
    `lost --require-label`, `interpret`, `stance`, `hedges`, `openers`, `sectionscope`,
    `discovery`, `depth`, `lostcost`;
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`.
- **Run files:** `replay/<dir>/<session>_rep<n>.json`; each has `turns[]` with `turn`, `chat_mode`,
  `research_mode`, `answer` and `audit`, whose `delegations[]` carry `report` and `tools[]` (`name`,
  `args`, `raw_result`, `final_result`, `summarised`, `memo_hit`, `local_cache_hit`, ...).
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.

---

## Agent A: P3.19, keep which provision made which change ($0, product, deterministic)

**Read first:** P3.19's row in full (its acceptance is booked; batch 5 B's premise check is on the row);
`notes/batch5_B.md` section 2.3; `server_py/src/agent/tools/lex.py` from `_MAX_CHANGED_PROVISIONS`
(line ~379) through `_slim_amendment_results` (~470-618); `tests/test_amendment_relations.py`
(55 tests pin today's shape); the `external-apis` skill's `/amendment/search` traps (35% `http`/`https`
duplicates, `size` truncating silently with no count, self-referential commencement rows); and
`$PREPILOT_EVIDENCE/seam/batch5/B/p319_scope.py`.

**The defect (checked by batch 5 B at `dde8b41`):** the slimmer groups relations by (instrument,
effect) and sorts `changed_provisions` and `effected_by` apart, so a group with two or more of each
no longer says which effecting provision made which change; and `effected_by` is cut at
`_MAX_EFFECTING_PROVISIONS = 6` with no count, where the changed list's cut at 60 records
`changed_provisions_not_listed`. Over the 1,216 stored `/amendment/` responses in 47 directories,
13,523 of the 20,991 groups emitted lose the pairing, 6,363 cut the effecting list silently, and the
slimmed output is a median 3,448 characters a call (max 49,050).

**Build** the fix the row describes: every relation the tool reports keeps its own changed and
effecting pair, and a cut list states its window (P3.5's rule). Keep the output bounded: report the
size before and after over every stored call, and if the median grows a lot, say so and offer a
bound as a decision rather than choosing one silently. **Measure first** with the built slimmer
(re-run `p319_scope.py`, repointed in a copy if needed, before and after).

**Acceptance (the row's, deterministic, n=1):** unit tests at the slimmer, each failing with the
change reverted: every relation keeps its own changed and effecting pair, and a cut list states its
window; a dry run over every stored change-record result shows each reported relation naming the
affecting provision its API row names, with the output size before and after; no `replay_report`
subcommand moves that is not listed and read (run the exit-1 set over at least `wave4_b4_post`,
`wave4_b2_post` and the directories holding 6338 and 6409, before and after).

**Also say:** whether the local prompt cache needs a version bump (batch 5 B said no: it keys on the
slimmed result, so a new shape simply misses old entries; confirm in `CACHEABLE_TOOLS` and the cache
key code); and what the Worker prompts say about the tool's output shape (`_RELATIONSHIP_RULE`,
`amendment_search_note`), so any wording that describes the old shape is listed for the integrator.
P3.21 depends on this row (the same slimmer); do not build any of P3.21.

## Agent B: P3.24, measure the negative commencement claim ($0, tooling and a note, no product code)

**Read first:** P3.24's row in full; P2.5's row; in `server_py/tools/replay_report.py` the comment
above `_CMC_DENIED` (~line 1780, why a negative about a PROVISION was deliberately not graded),
`_CUR_NEGATED` and the comment above it (~2235-2300), `_currency_asserted` (~2482),
`_currency_support` (~2514: what a turn retrieved, `commenced=`, `repeals=`, `orders=`, `marked=`),
and `cmd_currency` (~2622); `tests/test_search_scope.py::test_footer_trips_no_detector` (~line 1016);
the gitignored `$PREPILOT_EVIDENCE/seam/thomas_s37/2026-09-30-evals-developer-report.md` (his
evidence: two runs of 6410, one of 6378, on `glm-5.2:cloud`; it names matters, so nothing from it
goes into a committed file).

**The question:** how often does an answer on the pinned model state that a provision is not yet
commenced, not in force, or remains in force, and how often is that statement supported by what the
turn retrieved, rather than read from the absence of a commencement relation? P2.5's grader skips the
negative shape by design ("not yet commenced" returns False from `_currency_asserted`; "remains in
force" returns True; checked 2026-10-05), because a true negative exists (`asp/2025/2`: 20 of its 28
sections uncommenced). So the detector must separate a supported negative from an unsupported one,
not count negatives.

**Build** a new `replay_report` subcommand (suggested `negcurrency`) that, for every answered turn,
lists each sentence making a negative or continuing commencement or currency claim, with the turn's
support from `_currency_support` and anything else in the stored tool results that bears on it (a
commencement relation naming that provision; the instrument's own commencement provision; a
`valid_date`; a text-version marker). Classify each as SUPPORTED, UNSUPPORTED (read from an absence)
or UNCLEAR, and print every match and drop. Unit tests on synthetic text, each failing with the
change reverted. **Register the detector** in `test_footer_trips_no_detector`, so footer wording is
screened against it, and run that test: no existing footer clause may trip it (if one does, report it
as a decision, do not reword the footer).

**Measure:** run it over every stored directory; give totals and per-directory counts, and the
counts for 6410 and 6378 on their own. Read every UNSUPPORTED and UNCLEAR match by hand; save the
reading to the gitignored `$PREPILOT_EVIDENCE/seam/batch6/B/handread_p324.md` (matter text allowed
there, not in the note). Report how many of the detector's verdicts the hand-read overturns.

**Then give the user the choices,** as decisions: the lever (a rule beside `_IN_FORCE_RULE` on the
three legislation Worker prompts and the conversational ones; a code-built line, Invariant 2; or
both); the acceptance to book (the row's: n=3 on 6410 and 6378, no unsupported negative, true ones
still stated); and **a replay figure for that acceptance**, from the recorded cost of those sessions
in the stored run files (say which files and fields). Build no lever.

## Agent C: P4.21, the lookup footer's "not a sign that the citation is wrong" ($0, product, deterministic)

**Read first:** P4.21's row in full; P3.7's row; P2.4's row (the citation-blame defect P3.7's wording
was written against: 6373's Worker blamed a correct citation); `server_py/src/utils/search_scope.py`
`_lookup_footer_clause` (~line 2354, the sentence at ~2373) and the P2.4 comment block above it
(~2184); `server_py/src/agent/tools/schemas.py` ~lines 100-120 (the `lookup_legislation` tool
description, which also says a not-held result is "not evidence that the citation is wrong");
`tests/test_search_scope.py::test_footer_trips_no_detector`; `replay_report lookup` (`cmd_lookup`,
~line 6625).

**The defect:** a lookup that finds an instrument not held cannot tell a missing instrument from a
mistyped number, so "that is a gap in the index, not a sign that the citation is wrong" is a default,
not a finding. 69 stored answers carry it. The fix must not go back to the defect P2.4 fixed (the
model telling the lawyer to check a correct citation).

**Do:** (1) list every product site that tells the lawyer or the model that a not-held result says
anything about the citation (grep `src` for "citation"); (2) draft two or three replacement wordings
for the footer clause that state only what the lookup established (looked up by its number; not held
in this index) and that this does not show whether the number is right, without inviting the lawyer
to doubt a correct citation; (3) screen each against every detector (`test_footer_trips_no_detector`,
and the exit-1 `replay_report` set over a dry run of every stored footer rebuilt with the new
wording); (4) build your recommended wording, with tests failing with the change reverted; (5) for the
tool description in `schemas.py`, say whether its sentence is accurate (it tells the MODEL a
not-held result is not evidence the citation is wrong, which is true) and leave it unless it is not.

**Acceptance (the row's, deterministic):** the new wording in a unit test failing with the change
reverted; every stored footer rebuilt and re-screened against every detector; P3.7's and P2.4's
citation-blame readouts unchanged (`replay_report lookup` before and after over the directories that
hold 6373 and 6409). **Put the exact sentence, and the alternatives you screened, at the top of your
note: the integrator puts it to the user before merging, because a lawyer reads it.**

## Agent D: P3.12 and P3.25 measured, with options ($0, a note only)

Two independent measurements; no product or tool code; scripts in your gitignored scratch.

**P3.12 (P2; P3.2's criterion (v) needs it).** Read P3.12's row in full, P3.2's row (criterion (v)
and its five failed columns), P3.8's row (where P3.12 came from), batch 5 B's note on P3.12
(section 1 and M7), `utils/search_scope.py` `section_search_note` (~line 316) and
`server_py/tools/provision_hints.py`. LEX holds a Schedule as ONE provision (Session 18: 6335's
"Schedule B1 paragraph 43" is inside one of the Act's 674 provisions), so a paragraph asked for by
number is never returned on its own. **Measure, as the row says:** over every stored run file, how
often a Phase-2 query names a Schedule paragraph, and how often the Schedule itself is then
retrieved; and, on P3.2's control turn in every `p32_6406` directory, what the Worker searched for
and what it was given when it called the sub-unit not held. **Then options**, each with what it
would change and how it would be tested: a per-occurrence line in the section-search result
(`section_search_note`) saying a Schedule is one provision and a paragraph inside it is reached by
retrieving the Schedule; the Worker prompt's phrasing for schedule paragraphs; or a code route that
retrieves the Schedule when a paragraph is named (Invariant 2). Give a replay figure for the row's
acceptance (6335 turn 7, n=3; Session 18 recorded 6335 n=3 at $2.52; check against the stored run
files' recorded cost).

**P3.25 (P2).** Read P3.25's row, P2.3's and P2.5's rows (why a recital and `valid_date` arrive only
through `get_legislation_text`), the conversational Worker prompt (`WORKER_SYSTEM_PROMPT_CONVERSATIONAL`
in `server_py/src/prompts.py`: "Do NOT fall back to `get_legislation_text`", and its ENABLING POWER and
currency sections), and `get_worker_tools` (`server_py/src/agent/tools/schemas.py` ~line 734).
**Measure,** using `$PREPILOT_EVIDENCE/seam/thomas_s37/thomas_census.py` as the starting point: of
the 143 answered conversational turns (in 1,314) that call it, what each call retrieved (an
instrument with a recital, a `valid_date`, whole-Act text), whether the answer used it (a recital
quoted, a valid date stated, a provision quoted that no section search returned), what it cost
(characters returned, summarised or not, tool calls in the turn), and why the Worker called it (the
turn's earlier tool results: a lookup of a numbered instrument, a failed section search). **Then
options:** remove the tool from the conversational Worker in code (and how a quick lookup would then
reach a recital and `valid_date`); keep it and make the prompt consistent; or cap it in code (one
call per turn, or only for an instrument a lookup returned). Recommend one, and say how its
acceptance would be tested.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit
   or later (if another session has committed, read what changed and say so); pushed; `plan_status`
   47 of 75 and 8 of 14 (or the new counts, explained); `plan_lint` exit 0; rubric sha1s; the four
   test databases; nothing running (no python process, port 8000 free), no pin file; a baseline full
   suite on `lexchat_test` (2162).
2. **Ask the user once, before launching** (AskUserQuestion): launch A, B, C and D as set out, all
   $0? Offer to drop D if they would rather keep the batch to the three rows.
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message.
   Give each its section, plus **Rules for every agent**, **Lessons from batches 1-5** and **Shared
   setup**, verbatim; the integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL`. While they run, do nothing expensive and edit none of their files.
4. **Review each result as it lands** (as in batches 3-5):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines for session ids (allowed), instrument ids and matter words (not allowed,
     except synthetic `ssi/1901/*`);
   - for A, B and C, re-run the new tests with the change reverted on a scratch worktree, using
     `revert_check.py` with anchors from `hunk_anchors.py` (it asserts the anchor count and prints
     the lines removed), or, for new functions, a script that replaces each new function's body with
     a no-op (batch 5's `seam/batch5/scratchpad_s37/a/revert_a.py` is the model);
   - run the full suite on `lexchat_test`;
   - re-run one headline number from each note on the merged tree (A: the dry run's pairing and size
     figures; B: the subcommand's totals and the 6410/6378 counts; C: `replay_report lookup` before
     and after; D: two figures re-derived from its scripts);
   - copy the agent's scratch out of its worktree before removing it, and compare file counts.

   **Merge in the order A, B, C, D**, each `--no-ff`, the suite after each, the branch pushed after
   each clean merge (never `main`). **Before merging C, put its exact sentence (and the alternatives)
   to the user** and merge only the approved wording; after merging C, re-run
   `test_footer_trips_no_detector` (B's detector is in it by then).
5. **Assemble:**
   - **Tick P3.19 and P4.21** only if their deterministic acceptances are met on the merged tree
     (state the check); annotate each row with what was built and measured, in a byte script (each
     anchor once, CRLF kept, an even number of `**` added, no `|` in a cell, rows on one line); then
     `plan_lint` (0 errors) and `plan_status`. A ticked row's Bucket-index entry gets ` **done**`
     (plan_lint enforces it).
   - **Put B's and D's decisions to the user**, grouped (AskUserQuestion, at most four questions per
     call, recommendation first): P3.24's lever, acceptance and replay figure; P3.12's option and
     replay figure; P3.25's option; anything A or C raised. Record each answer on its row.
   - CHANGELOG *Unreleased*: P3.19 and P4.21 as product changes (plain words: what a lawyer or the
     model now sees); B's detector as tooling. Add an even number of `**`.
6. **No replay in this batch.** If the user wants an after-column (for example P3.19's effect on a
   change-record session, or P3.24's acceptance), price it first and put it to them.
7. **Hand over:** a Session 38 entry and a handover for Session 39 in SESSION_LOG.md (next by
   severity: P3.24's lever if chosen, else the P2 rows in the top order line's order); the memory
   entry `project_prepilot_freeze.md` and its MEMORY.md line; copy the session scratchpad to the
   gitignored `evidence/seam/batch6/scratchpad_s38/`; update the Fix Tracker only if the user asks
   (FIX_PLAN "How to use this file" step 7: read the live artifact and every line of the saved file
   first; a newly ticked row gets `fixed` and `ver: "Next release"`).

**Open with the user, carried (do not act on them yourself):** sending the lawyer pack (unblocks
P3.2, P3.3, P3.17; confirm the cover note's promise first); sending SCTS the note (P3.20's
prerequisite); applying for the National Archives licence (`docs/TODO.md` D23); deploying
`v2026.09.3` to the target (`pg_dump` first, then pull, restart and `test_apis.ps1`); telling the
eval-harness owner about schema v6; D19's remaining items; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2 are "Next release"); P4.12, D20, D21/D22;
from batch 1, the research Worker's jurisdiction line as a row, the 28 case-law summaries applying
English authority to Scotland, `wave2_p27` 6341 r2 t2; from batch 4, the p37_6373 substitution
P4.17's line exposes; enrolling 6370's five hedged drops in `p33.json` before the next after-column
(batch 5 D2); and **saving and mapping any further external report in the session that receives it**
(Thomas's 23 September report never reached the plan).
