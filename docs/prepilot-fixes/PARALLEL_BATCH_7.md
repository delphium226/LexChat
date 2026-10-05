# Parallel batch 7: P3.24's lever, P3.27 measured, P3.25 built, the case-law build begun

**Set up on 2026-10-05, at the end of Session 38, for Session 39, at the user's request** ("provide a
prompt to kick off the next piece of work ... a safe, multi-agent approach"). It follows batches 1-6
(`PARALLEL_BATCH_1.md` to `_6.md`): agents in git worktrees, the main session integrating, nothing
merged that the integrator has not re-checked. **Every agent is $0 in model spend.** Two agents may
make free, bounded live GETs (B to LEX, D to the National Archives) **only if the user agrees at
launch**. The one paid step is P3.24's acceptance replay, **already authorised by the user (up to
$1.31, pinned Gemini only)** and run by the integrator alone, between merges.

This file is the brief. The integrator reads it whole. Each agent is given its own section, plus
**Rules for every agent**, **Lessons from batches 1-6** and **Shared setup**, verbatim. Nothing here
should need re-deriving; if something does, the agent says so in its note rather than guessing.
Matter-specific detail (lawyers' wording, rubric patterns, hand-reads, Thomas's report) is NOT in
this file; it is in the gitignored files named below.

**What the user has already decided (do not re-open):**
1. **Work is taken by severity** (the Fix Tracker's `sev`, P1 first) **unless a dependency means it
   can't be** (2026-10-05). FIX_PLAN's top order line ("as at 2026-10-05, end of Session 38") is the
   order. P3.12 (P2) comes before P3.25 in it, but its build waits on agent B's LEX probe, so this
   batch measures for P3.12 and builds P3.25.
2. **P3.24 (Session 38, user decisions):** the lever is **both, the code line first**: a
   per-instrument line in `_currency_limb` computed from the change record (a provision may be
   called "not recorded as commenced" only where that instrument's record holds commencement
   relations by ANOTHER instrument; otherwise neither commenced nor uncommenced is stated), plus
   one sentence beside `_IN_FORCE_RULE` pointing at it. **Acceptance:** n=3 on 6410 and 6378,
   **pinned Gemini only**, no unsupported negative or continuing claim (graded by
   `replay_report negcurrency` and a hand-read), true ones still stated (Invariant 1). **Spend
   authorised: up to $1.31.** The detector's limits are accepted; every after-column is hand-read.
3. **P3.27 (booked Session 38, tracker P1):** measure first. **P3.12's lever is the code route**
   (fetch a named schedule or annex unit when it is missing, cut it out where it cuts cleanly, else
   hand over the whole schedule summarised), **after a live LEX payload probe**. **P3.25's lever:
   remove `get_legislation_text` from the conversational Worker in code, and route the recital and
   `valid_date` through `lookup_legislation`**, with a code lookup for an SI the Worker
   section-searches so 6340's permitted branch survives. **Their replays are priced to the user
   after the probe and the builds, in one sweep** (D's estimate about $5.50); none runs in this batch.
4. **The case-law build** (batch 5 C2): one build, four commits in this order: **P4.19, P3.23
   (stating today's order, newest first), P3.9**; then P3.22's paced measure-first, a replay
   before-column, P3.22 and its after-column. This batch does the first three only. The National
   Archives licence (`docs/TODO.md` D23) is booked and does not block them.
5. **P3.19's output size is accepted as built**; count the change records summarised on the next
   after-column (P3.24's replay is that column). P3.19's and P4.21's Worker-facing wording is left.
6. **P3.2, P3.3 and P3.17 are BLOCKED on the lawyer pack.** Nothing here touches them.
7. **Agents propose; the integrator applies; the user approves anything not mechanical**, including
   any wording a lawyer will read. No agent edits FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md,
   CLAUDE.md, `summary-table.html`, `docs/TODO.md`, a rubric, the lawyer pack or a memory file.
8. **Never merge or push to `main`**; the next cut (`v2026.10.1`) goes only when the user asks.
   Branch pushes are allowed; if the permission classifier refuses one, ask the user.
9. **The Fix Tracker is updated only when the user asks.**

---

## Where things stand (verified 2026-10-05, end of Session 38)

- **Branch** `fix/prepilot-defects`, **pushed**, head = this file's commit. **`main`** at `a6b4a76`,
  release **`v2026.09.3`**.
- **Tests: 2195** (`python -m pytest -q` from `server_py/`, default test database `lexchat_test`).
- **Ledger:** `python -m tools.plan_status` gives **49 of 77 rows**, **8 of 14 buckets**;
  **`python -m tools.plan_lint` exits 0** (0 errors, 0 warnings). Run both after every fold.
- **Open P1 rows:** P3.24 (lever decided) and P3.27 (measure first); P3.2 and P3.17 (Blocked).
- **Fix Tracker v37** (<https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, source
  `docs/prepilot-fixes/summary-table.html`): 76 rows, 44 Fixed, 26 Verified, 3 Blocked, 3 TBV.
- **Evidence** (gitignored, main checkout only, `C:/Projects/LexChat/docs/prepilot-fixes/evidence`):
  - 57 replay directories under `replay/`, every one on the pinned `google/gemini-3.1-pro-preview`.
    6410 and 6378 are in `wave4_p37_reach` and `wave4_p37_reach_pre` (their recorded cost: 6410
    $0.124 and $0.106, 6378 $0.217 and $0.185; highest 6378 $0.312 in `wave1`).
  - Rubrics `rubrics/p32.json` (sha1 `31379ecf…`), `p33.json` (`0031831b…`).
  - Batch 6 scratch: `seam/batch6/{A,B,C,Cx,D,scratchpad_s38}/`. **B's hand-read of P3.24 is
    `seam/batch6/B/handread_p324.md`**; B's removal-gap script `seam/batch6/B/removal_gap.py`; **D's
    scripts** `seam/batch6/D/p312_measure.py`, `p312_fulltext_schedules.py`, `p312_control_6406.py`,
    `p312_cut_feasibility.py`, `p325_measure.py`, `p325_lookup_vs_text.py` (each takes the replay
    directory as its argument and imports `server_py` from its own location); **A's dry run**
    `seam/batch6/A/dryrun.py` and `amendment_calls.pkl` (every stored `/amendment/` response);
    A's 16-subcommand exit-1 set `seam/batch6/A/grade.sh` (its `SUBS` line is the set).
  - Thomas's 30 September report: `seam/thomas_s37/2026-09-30-evals-developer-report.md`.
  - Review tools: `seam/batch4/scratchpad_s36/revert_check.py` and `hunk_anchors.py`; a
    function-stub revert in `seam/batch6/scratchpad_s38/revB/revert_b.py`; the matter-word grep
    `seam/batch6/scratchpad_s38/matter_grep.py` (with `review_branch.sh` beside it) over
    `seam/batch3/scratchpad_s35/matter_words.txt`; the keep-awake helper
    `seam/batch1/scratchpad_s33/keep_awake.py`.
- **Notes from batch 6** (committed): `docs/prepilot-fixes/notes/batch6_{A,B,C,D}.md`. **B's note
  sections 6 and 8** and **D's note sections 0, 1.4 and 2.3-2.4** are the specs for agents A, B and C
  below.
- **Test databases** `lexchat_test_a` to `lexchat_test_d` exist, one per agent.
- **Machine:** no uvicorn, no pin file (`server_py/tools/.replay_pin_state.json`), no worktrees.
  24 merged `worktree-agent-*` branches and `batch3-B` remain locally and can be deleted.

---

## The batch

| Agent | Row (tracker severity) | Work | Kind | Budget | Main files |
|---|---|---|---|---|---|
| **A** | **P3.24** (P1) | Build the decided lever: the per-instrument line in `_currency_limb`, then the sentence beside `_IN_FORCE_RULE` | product, deterministic build; acceptance by the integrator's replay | $0 | `server_py/src/utils/search_scope.py` (`_currency_limb` ~1179, the `get_legislation_changes` branch of the currency recorder ~1148), `server_py/src/prompts.py` (`_IN_FORCE_RULE` ~204), tests |
| **B** | **P3.27** (P1), measure first; **P3.12**'s probe | Measure the whole-text schedule gap over stored evidence; a bounded live LEX probe for P3.27 and P3.12; P3.12's ground truth | analysis, a note; **no product code** | $0; LEX GETs only if the user agrees | `notes/batch7_B.md`, gitignored scratch |
| **C** | **P3.25** (P2) | Remove `get_legislation_text` from the conversational Worker; route recital and `valid_date` through `lookup_legislation` | product, deterministic build; its replay priced later | $0 | `server_py/src/agent/tools/schemas.py` (`get_worker_tools` ~734), `server_py/src/agent/agent_core.py` (~222), `server_py/src/agent/tools/executor.py` (the `lookup_legislation` branch, ~512), `server_py/src/utils/instrument_lookup.py`, `server_py/src/prompts.py` (`WORKER_SYSTEM_PROMPT_CONVERSATIONAL` ~487), the recorders it needs in `search_scope.py`, tests |
| **D** | **P4.19**, **P3.23**, **P3.9** (all P2) | The first three commits of the case-law build, in that order | product, deterministic | $0; National Archives GETs only if the user agrees | `server_py/src/agent/tools/executor.py` (the `search_case_law` branch), `server_py/src/agent/tools/caselaw.py`, `server_py/tools/lex_probe.py`, tests |

**Why these four.** By severity: the two P1 rows (P3.24's lever, decided; P3.27, measure first),
then the P2 rows in the top order line's order, skipping P3.12's build, which needs B's probe first
(the dependency exception). **Not in this batch:** P3.12's build (next batch, from B's probe); P3.22
and its replays; any replay but P3.24's; P3.21; anything Blocked; the P3 rows (P4.8 first, then
P4.20, P4.22, P3.26, P3.28, ...).

**Merge order: A, B, then P3.24's replay, then C, D.** P3.24's acceptance is measured on a head
that holds A's lever and no other product change, so its result is attributable (Invariant 3).
Review C and D while the replay runs, but **never commit while a replay is running**; merge them
after `replay restore`.

**Collision points.**
- **A and C both edit `prompts.py`**: A only `_IN_FORCE_RULE` (shared by `WORKER_SYSTEM_PROMPT`,
  `_HYBRID` and `_CONVERSATIONAL`, at ~314, ~427, ~525), C only `WORKER_SYSTEM_PROMPT_CONVERSATIONAL`'s
  own body. Neither touches the other's constant.
- **A and C both edit `search_scope.py`**: A owns `_currency_limb` and the `get_legislation_changes`
  branch of the currency recorder; C owns any new `lookup_legislation` branch it adds to a recorder
  (for `valid_date` or the recital) and must not touch A's. If both edit one function, the
  integrator resolves by hand.
- **C and D both edit `executor.py`**: C the `lookup_legislation` branch, D the `search_case_law`
  branch. Different hunks.
- **D and `agent_shared.py`**: P3.23's row says the zero-result note and the Phase-2 nudge key on
  `total`; D keeps them keyed on the shown count. If C also edits `agent_shared.py`, resolve by hand.
- **Footer and limb wording:** any new text the product writes must pass
  `tests/test_search_scope.py::test_footer_trips_no_detector` (it now holds `negcurrency`). A's line
  sits in the Worker's scope block, which the Worker can echo into a report and a Manager into an
  answer; screen it as footer text.

---

## Rules for every agent (give these verbatim with each brief)

1. **Read first:** `docs/prepilot-fixes/FIX_PLAN.md` ("How to use this file", Invariants 1-6, "Data
   handling", "Re-planning protocol", the top recommended-order line, the paragraph above the Ledger
   on what waits on the lawyer pack, and your rows in full); in `docs/prepilot-fixes/SESSION_LOG.md`,
   everything from "Session 38 — 2026-10-05 — parallel batch 6" to the end of the file; and the
   batch 6 note your brief names. Do not re-derive what they establish.
2. **Stay in your worktree and on your files.** Do not edit `FIX_PLAN.md`, `SESSION_LOG.md`,
   `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `docs/TODO.md`, any
   `PARALLEL_BATCH_*.md`, any rubric, the lawyer pack or any memory file: the integrator folds your
   results in. Commit on your worktree's branch; **do not push, do not merge, never touch `main`.**
3. **Write your note** as `docs/prepilot-fixes/notes/batch7_<A|B|C|D>.md` and commit it. Put in it:
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
   (batch 6 A's mutants), so the tests are shown to check behaviour. Run the full suite on your own
   test database before your last commit, and report the count.
6. **Data handling:** never commit lawyers' question or answer text, search terms, case names, or
   instrument ids and titles from a session. Tests and fixtures use synthetic text ("Widget Order
   1901", `ssi/1901/3`). Grep your staged diff for session ids, instrument ids and matter words before
   every commit. Rubric patterns, draws, hand-reads, live payloads and anything quoting a matter stay
   in the gitignored evidence. (FIX_PLAN.md names sessions and instruments; your note need not
   repeat them: cite the row.)
7. **Line endings:** tracked files are CRLF in the working tree. The Write tool writes LF, so Python
   edits over multi-line text must normalise CRLF to LF before matching and restore CRLF on write.
   **A byte-level edit or revert must assert its anchor occurs exactly once before writing** (an LF
   anchor matches nothing in a CRLF file; a `$`-anchored grep finds nothing on a CRLF line). **Never
   run Python with backslashes from a bash heredoc** (it mangles them): use the Edit tool, or write
   the script to a file first. Commit messages go in a file (`git commit -F`), ending with the
   attribution line the harness gives.
8. **Budget: $0 in model spend.** No model call of any kind: no seam draw, no live Worker, no
   summariser call, no paid API. **Live GETs to LEX (agent B) or the National Archives (agent D) only
   if your brief says the user agreed at launch**, and then: paced at least 0.5 s apart, under the
   cap your brief gives, every call logged (URL, status, bytes) to your gitignored scratch, and
   counted in your note. Every other agent makes no external call at all; every measurement runs
   over stored evidence.
9. **No server, no replay:** never start uvicorn, never run `replay pin`, `replay run` or
   `replay restore`.
10. **Scratch goes in your own folder:** your worktree's gitignored
    `docs/prepilot-fixes/evidence/seam/batch7/<your letter>/` (check it with `git check-ignore -v`
    first), copied at the end with a shell `cp -r` to
    `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch7/<your letter>/`. Never write to the
    session scratchpad. Say in your reply which you did, with the file count on both sides.
11. **When you finish, reply with:** your branch name and the commit list; the test count and the
    spend (and, for B and D, the number of live calls); the path of your note and where your scratch
    is; for each item, met or not and why; and the numbered decisions for the user.

## Lessons from batches 1-6 (give these verbatim with each brief)

- **Check your base before anything else.** In all six batches every worktree the Agent tool made
  came up on `main`, not on the integrator's HEAD. Your first commands are `git log --oneline -1` and
  `git merge-base --is-ancestor <INTEGRATOR_HEAD> HEAD`. If HEAD is not `<INTEGRATOR_HEAD>` and you
  have no commits, run `git reset --hard <INTEGRATOR_HEAD>`, and say in your note that you did.
- **Set `TEST_DATABASE_URL` before your first pytest run**, including a single test file. Use plain
  `postgresql://`, not `+asyncpg`. `conftest.py` drops every table at teardown, so a run on the
  default database breaks the integrator's suite.
- **The graders have been wrong in both directions in every after-column.** A hand-read is the
  ground truth; a detector is judged by whether its verdicts match what a careful reader would say,
  never by its rate. Read every match and every drop. (Batch 6 D's first `valid_date` count was 55;
  55 of the 57 hits were the product's own code-written limb, found only by reading them.)
- **Any text the product writes into an answer, or into a block the model can echo, is read by every
  grader** (`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`,
  `derivation_claims`, `_currency_asserted`, `negcurrency_claim`, `OPENER_VOCAB`, the halt
  detectors, the footer strippers). New wording is screened against all of them
  (`test_footer_trips_no_detector`). Batch 6 C chose "accurate" over "right" because
  `OPENER_VOCAB` reads "right".
- **A dry run must use the BUILT code, never a prototype or a retyped string**; a script that asserts
  it imports a particular worktree's code must be repointed (not edited in place) to re-run on the
  merged tree. Batch 6 A's first two builds hid provisions the old output showed (1,420, then 18);
  only the dry run over every stored input caught them.
- **Check that a folder is really gitignored** (`git check-ignore -v <path>`) before you write matter
  text into it. **`docs/prepilot-fixes/evidence/` itself is NOT ignored**, only its listed subfolders
  (`seam/`, `replay/`, `rubrics/`, `lawyer_pack/` and others).
- **The plan has been wrong before, and the instrument more often than the product.** Check a row's
  claim against the code or the stored evidence before repeating it, and say which you checked.
  Batch 6 found a row's count wrong (P3.19's 20,991 groups were 21,033) and a claim half-true
  ("`replay_report` never imports `lex.py`": its graders don't, but `lookup`'s live path does).
- **Read the API's spec before concluding what it cannot do, and check every parameter we send
  against it.** Batch 6 D found `include_schedules` on `/legislation/text`, never sent, so every
  whole-text read since the product began omitted schedules and annexes.
- **Thomas tests on a different model** (`glm-5.2:cloud`); every stored replay here ran on the
  pinned Gemini. Say which model a number comes from. On the pinned model P3.24's defect has not
  appeared since P3.5.
- **Tooling traps on this machine:** Git Bash's `grep -iF` aborts (exit 134), so a `$(grep -ciF ...)`
  prints blanks silently: use Python for case-insensitive fixed-string search. `git worktree remove`
  fails ("Permission denied") while the shell's cwd is inside the worktree.
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
    `hedges`, `openers`, `sectionscope`, `discovery`, `depth`, `lostcost`. **The exit-1 set** is
    batch 6 A's 16: `halts negatives derivations commencements currency scoperecord nosearch caselaw
    modes deadend siblings scripted lookup drgaps blanks lost --require-label`.
  - `python -m tools.footer_echo --dir <path>`; `python -m tools.summary_probe count|glosses`;
    `python -m tools.lex_probe` (live LEX checks; B only, if agreed).
- **Run files:** `replay/<dir>/<session>_rep<n>.json`; each has `turns[]` with `turn`, `chat_mode`,
  `research_mode`, `answer` and `audit`, whose `delegations[]` carry `report` and `tools[]` (`name`,
  `args`, `raw_result`, `final_result`, `summarised`, `memo_hit`, `local_cache_hit`, ...).
- **psycopg2 is not installed.** Use asyncpg if a script needs the database.
- **Node** (for a JS syntax check only): `C:\Users\rhett\node_portable\node-v22.15.0-win-x64`.

---

## Agent A: P3.24, build the decided lever ($0, product, deterministic build)

**Read first:** P3.24's row in full (its Session 38 annotation records the measurement and the
decisions); `notes/batch6_B.md` sections 1, 6 and 8 (the lever as B specified it, and F3); P2.5's
and P4.18's rows; P3.19's row (the change record's new `changes` shape); in
`server_py/src/utils/search_scope.py`, `record_relations` (~768), `_relations_limb` (~810), the
currency recorder's `get_legislation_changes` branch (~1148: it logs `commenced` from
`provisions_commenced`, which counts an Act's self-referential relations, B's F3) and
`_currency_limb` (~1179); `server_py/src/agent/tools/lex.py` from `_REPEAL_EFFECT_TOKENS` (~469)
through `_slim_amendment_results`; `_IN_FORCE_RULE` in `server_py/src/prompts.py` (~204) and the
three prompts that include it; `tests/test_search_scope.py::test_footer_trips_no_detector`.

**Build, code line first (Invariant 2).** In `_currency_limb`, one line per instrument whose change
record the step consulted, computed from what the record holds: where it holds commencement
relations made by ANOTHER instrument (not the Act's own commencement section: B's F3), a provision
not among them may be called "not recorded as commenced", citing that; where it holds none, or the
record was not consulted, no provision of that instrument may be called commenced or uncommenced,
and the line says so. Record what the line needs at the recorder (a per-instrument count of
commencement relations by another instrument), from the RAW result, as every recorder at that seam
does. Then **one sentence beside `_IN_FORCE_RULE`** pointing the Worker at that line. Do not touch
the repeal count (`_REPEAL_EFFECT_TOKENS` is P3.28, not this row) or the footer clauses (P4.20).

**Measure what it moves, with the built code:** rebuild the scope block for every stored delegation
that consulted a change record (the recorders run on each tool's `raw_result`; `seam_replay
--from-raw`'s builder `agent_shared.summarised_result_blocks` shows the pattern) and list, per
instrument, the line before and after; count instruments in each of the line's cases; and confirm
that every claim `negcurrency` grades SUPPORTED on the stored answers would still be permitted by
the new line (Invariant 1: a true negative must stay stateable). Screen every variant of the new
text in `test_footer_trips_no_detector`.

**Tests**, each failing with the change reverted (and the line count removed): the line's cases
(commencement by another instrument; only self-referential relations; no record consulted; an
empty record); the recorder's new field; the prompt sentence present in exactly the three prompts
that carry `_IN_FORCE_RULE`.

**Acceptance (the row's, booked):** a replay, n=3 on 6410 and 6378, pinned Gemini, run by the
integrator after merging A and B. You run nothing paid. **Say in your note** which words of the new
line the integrator should read for in the hand-read, and give the exact sentence you added to the
prompt, so the user can see it.

## Agent B: P3.27 measured, and the LEX probe P3.12 needs ($0; live LEX GETs only if agreed)

**Read first:** P3.27's row in full; P3.12's row (its Session 38 annotation); P3.25's row; P2.3's
row (why a recital is read from `legislation.description` on `/legislation/text`);
`notes/batch6_D.md` sections 0, 1.1-1.4 (the schedule gap, D's code-route design and its cut
feasibility) and 2.3; the `external-apis` skill (`/legislation/text`'s three traps, `/amendment/search`);
`server_py/src/agent/tools/executor.py`'s `get_legislation_text` branch (~532); D's scripts in
`$PREPILOT_EVIDENCE/seam/batch6/D/`.

**Measure first, over stored evidence ($0, no live call):** every stored `get_legislation_text`
call, research and conversational Workers both: was the instrument one with a schedule or annex
(known from a section search in the stored corpus, as D's `p312_fulltext_schedules.py` does)? Did
the turn need a provision in one (the brief, or a section-search query, naming a schedule,
paragraph, annex or chapter)? What did the report and the answer then say about that provision
(not held, not retrievable, not in the text, nothing)? Count each, list every turn, and read each
negative by hand (the hand-read goes in your gitignored scratch).

**Then the live probe, only if the user agreed at launch.** Cap: **300 GETs**, at least 0.5 s apart,
every call logged. (1) For each distinct instrument a stored whole-text read touched (or, if more
than the cap allows, the 18 with known schedule units first, then a sample stated in the note):
`/legislation/text` with and without `include_schedules=true`; sizes, whether the known units are
present, and the size distribution with the flag (this sets any bound on sending it). (2) For P3.12:
how a single schedule or annex provision's text is reached (by its provision id through which
endpoint, or only by the whole text with the flag), what the payload is for P3.12's own Schedule,
and whether D's cut rules hold on the live text. (3) **P3.12's ground truth:** the text of the
Schedule paragraphs P3.12's acceptance names (6335 turn 7), read live and saved to the gitignored
scratch, so `replay_report depth` can be given it (where it goes in the repo is a decision for the
user: `DEPTH_TRUTH` already holds live-verified provisions).

**Then the choices, as decisions:** P3.27's lever (a code-written line on every whole-text result
saying schedules and annexes are not included; sending the flag, always or under a size bound; or
both), with what each changes and how it would be tested; P3.12's code route as the probe now
supports it (endpoint, cut rules, the fallback), with its tests; and whether P3.27 and P3.12 should
be built together. **Build nothing.** If the user did not agree to live calls, do the stored
measurement only and say what the probe would settle.

## Agent C: P3.25, take `get_legislation_text` from the conversational Worker ($0, product)

**Read first:** P3.25's row in full (its Session 38 annotation is the measurement);
`notes/batch6_D.md` sections 2.1-2.4 (what the 247 calls retrieved and were used for, the reroute
evidence, the options); P2.3's and P2.5's rows (the recital and `valid_date` routes, and P2.3's
permitted branch, which 6340 used); P3.7's row (`lookup_legislation` and its code routing);
`server_py/src/agent/tools/schemas.py` (`get_worker_tools` ~734 and the `lookup_legislation`
schema); `server_py/src/agent/agent_core.py` (~222, where the Worker's tools are chosen);
`server_py/src/agent/tools/executor.py` (the `lookup_legislation` branch, which returns
`description[:600]` and drops `valid_date`); `server_py/src/utils/instrument_lookup.py`;
`WORKER_SYSTEM_PROMPT_CONVERSATIONAL` in `server_py/src/prompts.py` (~487: "Do NOT fall back to
`get_legislation_text`", and its ENABLING POWER and currency sections); the recorders in
`search_scope.py` that read a recital (`_recital_in` ~468) and `valid_date` (~1158).

**Build, as decided:** (1) the conversational Worker is not offered `get_legislation_text`, in code
(the tool list depends on the chat mode; the research Workers keep it); (2) `lookup_legislation`
passes on `valid_date` and enough of `description` to carry a recital (check D's 7 of 8 against the
600-character cut on the stored lookup payloads), and the recorders read the recital and
`valid_date` from a lookup result as they do from a text result; (3) a code lookup for an SI the
conversational Worker section-searches, so P2.3's permitted branch (an SI's own recital) still has
its source; (4) the conversational prompt says nothing that relies on the removed tool and nothing
that contradicts the new route. Keep any prompt edit minimal: a prompt edit reaches every call the
prompt drives (FIX_PLAN's Verification protocol, lesson (1) of Session 22), and say in your note
which calls this one drives.

**Measure what it moves, with the built code:** over every stored conversational turn that called
`get_legislation_text` (D's 143 turns, 247 calls), what the new route would have supplied instead
(recital, `valid_date`), from the stored lookup payloads where they exist; and confirm the research
Workers' tool lists and prompts are byte-identical to before.

**Tests**, each failing with the change reverted: the conversational tool list lacks the tool and
the research lists keep it; the lookup result carries `valid_date`; the recorders read the recital
and `valid_date` from a lookup; the code lookup fires for a section-searched SI and not otherwise.
**Book the acceptance in your note as a proposal** (deterministic: the above; replay: on which
sessions, n, and what is graded, with a figure from the stored run files' recorded cost); the user
decides it. Any wording a lawyer could read goes to the user before merge.

## Agent D: the case-law build, P4.19, P3.23, P3.9 ($0; National Archives GETs only if agreed)

**Read first:** P4.19's, P3.23's, P3.9's and P3.22's rows in full (P3.22's gives the build order and
why it stays separate); `notes/batch5_C.md` (the case-law review and its constraints);
`docs/LEGAL_DATA_SOURCES.md` section 4; `server_py/src/agent/tools/executor.py`'s `search_case_law`
branch and `_request_with_retry` (A5a); `server_py/src/agent/tools/caselaw.py`
(`_fetch_judgment_text`, which opens its own client); the `agent_shared.py` sites that key on the
case-law `total`; `server_py/tools/lex_probe.py`; the `external-apis` skill's National Archives
section.

**Build, one commit per row, in this order:**
1. **P4.19:** route `search_case_law` and `_fetch_judgment_text` through `_request_with_retry`;
   say in the tests whether retrying a timeout or transport error is wanted at the 15 s case-law
   timeout (batch 5 C's note on the row); a 400 still returns at once, unretried.
2. **P3.23:** report the shown count and the approximate total separately, from the feed's `last`
   link (an upper bound: the last page can be empty), and state the window in P2.2's form,
   **stating today's order, newest first** (P3.22 flips it later); keep the zero-result note and the
   Phase-2 nudge keyed on the shown count.
3. **P3.9:** send the date form the feed honours (`from_date_0/1/2`, `to_date_0/1/2`), keep the
   intersection of model and user dates, reject an impossible interval, and say in the code that
   the form is not in the published spec. **Do not adopt `order=relevance`** (P3.22).

**Measure what each moves, with the built code:** over the 1,257 stored `search_case_law` calls
(batch 5 C's `caselaw_census.py`, in `$PREPILOT_EVIDENCE/seam/batch5/C/`), the params each call
would now send and the result text each would now produce (P3.23's window line), listing every
output that moves; screen any new result text against every detector.

**Tests**, each failing with the change reverted, as each row's acceptance gives. **Live checks**
(P3.23's and P3.9's acceptances each name a `lex_probe` live check): write them; **run them only if
the user agreed at launch**, cap **60 GETs**, at least 1 s apart, logged; otherwise leave them
unrun and say so. If time runs short, stop after a complete row; a half-built row is not merged.

---

## The integrator (the main session)

1. **Check the state** against "Where things stand": `git status` clean; HEAD is this file's commit
   or later (if another session has committed, read what changed and say so); pushed; `plan_status`
   49 of 77 and 8 of 14 (or the new counts, explained); `plan_lint` exit 0; rubric sha1s; the four
   test databases; nothing running (no python process, port 8000 free), no pin file; a baseline full
   suite on `lexchat_test` (2195).
2. **Ask the user once, before launching** (AskUserQuestion, recommendation first): launch A, B, C
   and D as set out? **May B make up to 300 free GETs to LEX, and D up to 60 to the National
   Archives?** (Free of model spend; the alternative is stored-evidence only, with the probes left
   for later.) Confirm that P3.24's replay (up to $1.31, already authorised) runs between the A/B
   and C/D merges.
3. **Launch** the agreed agents as background agents with `isolation: "worktree"`, in one message.
   Give each its section, plus **Rules for every agent**, **Lessons from batches 1-6** and **Shared
   setup**, verbatim; the integrator's HEAD sha as `<INTEGRATOR_HEAD>`; its `PREPILOT_EVIDENCE` and
   `TEST_DATABASE_URL`; and, for B and D, whether the user agreed to live calls. While they run, do
   nothing expensive and edit none of their files.
4. **Review each result as it lands** (as in batches 3-6):
   - confirm the branch contains `<INTEGRATOR_HEAD>`; read the note and the diff;
   - grep the added lines for session ids (allowed), instrument ids and matter words (not allowed,
     except synthetic years such as 1899-1902), with `scratchpad_s38/matter_grep.py` (not `grep -iF`);
   - for A, C and D, re-run the new tests with the change reverted on a scratch worktree
     (`hunk_anchors.py` + `revert_check.py`, and a function-stub revert like
     `scratchpad_s38/revB/revert_b.py` where a full revert only fails at import), and report the
     lines removed; run `git worktree remove` from the main checkout, never from inside;
   - run the full suite on `lexchat_test`;
   - re-run one headline number from each note on the merged tree (A: the before/after line census;
     B: two figures from its stored measurement; C: the conversational tool list and the census of
     what the new route supplies; D: one row's dry-run count);
   - copy the agent's scratch out of its worktree before removing it, and compare file counts.
5. **Merge A, then B**, each `--no-ff`, the suite after each, the branch pushed after each clean
   merge (never `main`). Put A's prompt sentence to the user if they have not seen it.
6. **P3.24's acceptance replay** (authorised up to $1.31, pinned Gemini), on the head holding A and B:
   - from `server_py/`: `python -m tools.replay check`, then `python -m tools.replay pin` (the pin
     file appears at `server_py/tools/.replay_pin_state.json`);
   - start uvicorn fresh: `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`, in the
     background (PowerShell `Start-Process -PassThru` gives the real Windows PID), logging to a file
     in the session scratchpad; confirm `/api/bot-info` shows the merged build; start the keep-awake
     helper and record its PID;
   - `python -m tools.replay run --session 6410 6378 --reps 3 --max-spend 1.31 --out-dir
     C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b7_p324`. `--max-spend` is
     checked between reps only, so it can overshoot by one rep: **if the total passes $1.31, stop
     and ask before going on.** Never commit while it runs; if it stalls (15 minutes with no log
     growth), re-run the SAME command: it resumes;
   - then `python -m tools.replay restore`, stop uvicorn and the helper by their PIDs, and confirm
     there is no pin file, no python process and port 8000 free.
   - **Grade** `wave4_b7_p324`: `negcurrency --all` (no UNSUPPORTED; every SUPPORTED claim read; the
     true negatives still stated), the exit-1 set, `modes`, and **the count of change records
     summarised** (P3.19's decision: `get_legislation_changes` tool records with `summarised` true,
     against `wave4_p37_reach`). Hand-read every `negcurrency` match and every negative on a turn
     that consulted a change record; save it to the gitignored
     `evidence/rubrics/handread_wave4_b7_p324.md`. P3.24 is ticked only if every rep passes by hand
     (n=3, all clean).
7. **Merge C, then D**, as in step 5, after the replay is restored. Put any wording from C or D that a
   lawyer could read to the user before its merge.
8. **Assemble:**
   - tick only rows whose acceptance is met on the merged tree, stating the check (P3.24 by the
     replay; P4.19, P3.23 and P3.9 by their deterministic acceptances, with their live checks if
     run; P3.25 stays open until its replay); annotate each row in a byte script (each anchor once,
     CRLF kept, an even number of `**` added, no `|` in a cell, rows on one line); a newly ticked
     row's Bucket-index entry gets ` **done**`; then `plan_lint` (0 errors) and `plan_status`;
   - **put the agents' decisions to the user**, grouped (AskUserQuestion, at most four questions per
     call, recommendation first): P3.27's lever, P3.12's route and whether they are built together,
     P3.25's acceptance and its replay figure, anything A or D raised. Record each answer on its row;
   - CHANGELOG *Unreleased*: each product change in plain words (what a lawyer or the model now
     sees); tooling separately. Add an even number of `**`.
9. **Hand over:** a Session 39 entry and a handover for Session 40 in SESSION_LOG.md (next by
   severity: P3.27's and P3.12's builds, then P3.25's replay with P3.12's, then the rest of the P2
   rows in the top order line's order); the memory entry `project_prepilot_freeze.md` and its
   MEMORY.md line; copy the session scratchpad to the gitignored `evidence/seam/batch7/scratchpad_s39/`;
   update the local skills (`.claude/` is gitignored) where a finding changes what they say; update
   the Fix Tracker only if the user asks (FIX_PLAN "How to use this file" step 7: read the live
   artifact and every line of the saved file first; a newly ticked row gets `fixed` and
   `ver: "Next release"`).

**Open with the user, carried (do not act on them yourself):** sending the lawyer pack (unblocks
P3.2, P3.3, P3.17; confirm the cover note's promise first); sending SCTS the note (P3.20's
prerequisite); applying for the National Archives licence (`docs/TODO.md` D23); deploying
`v2026.09.3` to the target (`pg_dump` first, then pull, restart and `test_apis.ps1`); telling the
eval-harness owner about schema v6; D19's remaining items; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, P3.19 and P4.21 are "Next release"); P4.12,
D20, D21/D22; batch 1's three items (the research Worker's jurisdiction line as a row, the 28
case-law summaries applying English authority to Scotland, `wave2_p27` 6341 r2 t2); the p37_6373
substitution P4.17's line exposes; enrolling 6370's five hedged drops in `p33.json` before the next
P3.3 after-column (batch 5 D2); B's F3 from batch 6 (an Act's self-referential relations counted as
commencements by `provisions_commenced` and `_currency_support`; noted on P3.24, not booked, and
agent A's line must not repeat it); and **saving and mapping any further external report in the
session that receives it**.
