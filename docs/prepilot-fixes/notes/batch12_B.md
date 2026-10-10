# Batch 12, agent B: P3.10's line on every step 2+ (built), its dry run, and 6374 n=3 priced ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every batch. I had made no commits, so I ran
`git reset --hard a99e4d4` (the `<INTEGRATOR_HEAD>`). This note and the branch are based on `a99e4d4`.

**Spend: $0.** No model call, no seam draw (not even `--dry-run`), no replay, no server, **no live call to any
host (0 calls)**. **Tests: 3015 passed** (3017 at the base, minus 2: the handover file went from 23 tests to 21) (`python -m pytest -q -p no:cacheprovider` from `server_py/`,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b`; `pytest_full.out` in scratch).

**Model.** Every stored run read here ran on the pinned `google/gemini-3.1-pro-preview` (summariser
`google/gemini-3-flash-preview`), summarised at the 8,000-character fallback.

**Scratch.** `docs/prepilot-fixes/evidence/seam/batch12/B/` (gitignored by `.gitignore:113`, checked with
`git check-ignore -v`), copied with `cp -r` to the main checkout's path of the same name (file counts in section
8). The scripts import THIS worktree's code (`agent-a6d61e8a6a7d3ed48/server_py`), or the base exported to
`old/server_py` (`git archive a99e4d4 server_py/src server_py/tools`); to re-run on the merged tree, pass its
`server_py` (`dryrun_b12.py <server_py> <out>`, `p310_grade_b12.py --server`) and repoint `p310_recount.py`'s
`sys_path_server` and `REPO`. They read **all 66 replay directories** (40 hold a plan); a new directory changes
the counts.

**Functions changed (collision note for agent D):** in `agent_core.py`, **`_build_step_brief` only** (the
gate removed; docstring). `run_deep_research` and `run_worker_agent` are untouched. In `utils/step_handover.py`:
**`works_on_earlier_list`, `_SESSION15` and `_IDENTIFIED_TITLED` removed** (nothing else imported them:
`grep -rn works_on_earlier_list server_py` is empty), the module docstring's "Which steps get the line"
paragraph and the `MAX_HANDED_ON_IDS` comment rewritten. `handover_line`, `handed_on_ids`, `report_body`,
`without_handover_line`, the cap (15) and the lookup exclusion are unchanged. `tests/test_step_handover.py`:
the gate's 12 tests replaced (section 4).

**Built shape against the brief.** As briefed: the line on every step 2+ (no regex gate), the lookup exclusion
and the caps kept. **The wording is unchanged** (the user approved it at batch 11), but rendering it on the
steps it now reaches shows its last sentence is not inside the condition (decision 1).

---

## 1. What was built, and why

`_build_step_brief(step, approved_plan, user_query, earlier_reports)` now adds the line whenever
`earlier_reports` is non-empty and `handover_line(earlier_reports)` is non-empty, whatever the step's wording.
`run_deep_research` already passed the reports of the steps already run, so step 1 never gets a line (no
earlier reports) and a step whose earlier bodies cite no instrument gets none. The line still sits after SCOPE
and before the CONTEXT sentence, and P3.7's routed lookups still read the brief through
`without_handover_line`.

**Why:** in `wave4_b11_sweep` the line worked on every step it reached (7 of 7 covered their list with no
search of their own), and the one miss was a step the gate did not recognise (`p310_6374` rep 2, step 4,
"Review the retrieved secondary legislation ..."): no line, 4 own searches, 1 instrument dropped. The user
decided (2026-10-09) to give the line to every step 2+, since its wording is conditional.

**The wording (unchanged; it now reaches every step 2+):**

> EARLIER STEPS' INSTRUMENTS: the reports of the earlier steps of this plan cite these instruments, by
> legislation_id: uksi/1901/4, ssi/1902/30. Where this task works on instruments an earlier step identified, they
> are among these: work on each one of the kind the task names, by its legislation_id, rather than finding the
> list again. Look further only if the task asks for more than the earlier steps reported.

## 2. The dry run with the BUILT code: every stored step 2+, and every brief that moves

Commands (from the scratch folder; `PYTHONIOENCODING=utf-8`):
`python dryrun_b12.py <abs>/old/server_py dry_old.json` (the base `a99e4d4`'s built, gated code),
`python dryrun_b12.py <worktree>/server_py dry_new.json` (this change's built code), then
`python compare_b12.py > compare_b12.out` and `python extra_checks.py > extra_checks.out`. Each rebuilds every
stored Deep Research step's brief from its plan, its question and the earlier steps' **recorded** reports,
exactly as `run_deep_research` passes them. **The per-step list of the briefs that move is
`moved_b12.txt` (scratch, 457 rows: location, era, research type, step class, and the ids on the new line;
ids only, no text). It names sessions' instruments, so it is not reproduced here.**

**Input-form checks (all pass):**
- Over **829 stored steps** (227 plans, 40 of the 66 directories), the built code with no earlier reports
  rebuilds **820** stored briefs byte-equal. The other **9 are the 9 stored briefs that carry the line** (served
  by the gated code: 6 in `wave4_b11_sweep`, 3 in `wave4_p331`); with that line taken out, **829 of 829** are
  equal. The base and the built code agree on all 829 (they differ only when earlier reports are passed).
- On those 9, **the line both codes build from the recorded reports equals the stored line, 9 of 9**: the dry
  run reproduces what served them.
- **Step 1 briefs that move: 0.** No step 2+ with no line is missing an earlier delegation in the record (0).

**What moves (base gated → built every step), steps 2+:**

| | count |
|---|---|
| steps 2+ | 602 |
| **briefs that move** | **457**, every one "line added" (no line changed, none removed) |
| steps with a line under both | 74, the line identical under both (74 of 74) |
| steps with a line, built | **531** (base: 74) |
| steps with no line, built | 71, all because the earlier bodies cite no instrument |

| era (by each run file's `git_head`) | moved | lined (built) | steps 2+ |
|---|---|---|---|
| before P2.7 | 235 | 275 | 322 |
| P2.7 to P3.1 | 82 | 94 | 96 |
| P3.1 to P3.8 | 12 | 12 | 12 |
| after P3.8 | 128 | 150 | 172 |

| research type (turn, else its audit) | moved | lined | steps 2+ |
|---|---|---|---|
| `legislation_only` | 325 | 399 | 439 |
| `legislation_and_case_law` | 132 | 132 | 163 |
| `case_law_only` | 0 | 0 | 0 (no stored Deep Research turn) |

By batch 10 D's step classes (the Session 15 pattern or the titled form = "list"; D's hand list, after P3.8
only): list-dependent with a line under both 74; list-dependent with no line under either 6 (earlier bodies cite
nothing, all before P2.7); **provision-dependent 7, newly lined; other steps 450, newly lined**.

**Ids on a line, built:** median 3, p90 7, max 15 (the cap). **Before the cap**: median 3, p90 7, **max 39;
5 lines exceed 15 and say "and N more" (23 or 24 more), and all 5 are in `wave4_p331`**, after P3.8: steps
working on a list that P3.31's made-under record returned (38 to 39 ids). Line length median 425, p90 492,
max 601 characters. **The cap has already cost a list once (section 2a, decision 5).**
After P3.8 alone: 150 of 172 steps 2+ lined (batch 11 E's 148 plus the 24 steps of `wave4_b11_sweep` and
`wave4_p331`, both newer than E's count).

**`wave4_b11_sweep` (the gated code's acceptance runs), steps 2+:** 15; 6 carried the line; **9 move**: in
`p310_6374` rep 1 step 2, rep 2 steps 2-4 (step 4 is the miss), rep 3 steps 2-3; in `p310_6383` reps 1-3,
step 2.

**P3.7 (the lookup exclusion holds): over all 829 built briefs, the routed extraction through
`without_handover_line` equals the extraction of the brief with no line, 829 of 829.** No lookup is added.

**Input forms no stored run contains, tested on synthetic input:** a case-law-only plan (no stored Deep Research
turn ran case law only: a judgment's link and neutral citation hand on nothing, a legislation.gov.uk link
inside a case-law report is handed on); a step with no detail; a step with no question (no CONTEXT: the line
closes the brief); a failure reading the earlier reports (no line, the brief otherwise unchanged); a plan of
three steps (step 3's line names step 1's then step 2's ids, each once). Already tested and kept: more than 15
ids, a lost step, a halted step written up, an echoed lookup block.

### 2a. The cap of 15 against P3.31's lists (found here; the cap is unchanged, as briefed)

`wave4_p331` (the other session's P3.31 sweep, served by the gated code) holds **one stored list-dependent step
that got the line: its earlier bodies cite 37 SSIs and the line named 15 ("... and 23 more").** E's grader
(`grade_b11sweep.out`, `grade_b11sweep_detail.txt`, re-run here): the step **DROPS 23 of 37**, with **0** own
`search_legislation` calls; it worked on **exactly the 14 SSIs the line named** (the 15th id on the line is not
an SSI). The line did what it says, and the "and 23 more" was not followed up. Before P3.31 no stored list came
near the cap (batch 11 E: max 10 after P3.8); P3.31's tool lists up to 40 instruments, so a made-under question
in Deep Research now produces lists the cap cuts. That is 6383's shape: a `p310_6383` rep at HEAD (which carries
P3.31) may meet it. Not measured further here; decision 5.

**An id type the line cannot carry (not a change of mine, found by the render):** a report citing only an
`sdsi` id gets no line, because P3.7's `extract_instrument_citations` does not read that type. The same is true
of P3.7's own routing. No stored line is affected that I can see (every stored line was built); noted for P3.7.

## 3. What else reads the brief, now on every step 2+ (lesson: every code text beside the line)

- **The Worker** (its user message). The line is read beside P3.7's lookup block (for instruments the step's
  own text names; consistent: both true statements), P3.1's per-instrument section cap, P2.7's discovery
  budget and the CONTEXT sentence ("Research ONLY this step's task"). None contradicts the line.
  **But its last sentence is not conditional** (decision 1): "Look further only if the task asks for more than
  the earlier steps reported" stands as a sentence of its own. On a list-dependent step that is the intent. The
  line now also reaches **discovery steps** (the task finds instruments itself). A rough text classifier
  (`discovery_steps.py`, counts only, `discovery_steps.out`) puts **148 of the 457 newly lined steps** in that
  shape, and **40 of them get a line that already names an instrument of the class they look for**. On such a
  step the sentence can read as "do not search". **`p310_6374` has such steps in all three stored reps** (rep 1
  step 2; rep 2 step 3; rep 3 steps 2 and 3, which ran 8 to 16 searches of their own), so the 6374 n=3 sweep
  measures this directly: watch those steps' own searches and new finds, and bar (4), `sources_kept`.
- **The summariser** (`run_worker_tool` passes the brief as the query to `summarise_for_query`, and P3.12's
  schedule route does the same for a unit it summarises). Every summary made in a step 2+ is now asked against a
  brief that names the earlier instruments (531 of 602 stored steps; before, 74). P3.12's unit detection and
  paragraph matching read the tool's own `query` argument, not the brief, so they do not move.
- **The local prompt cache key in Deep Research** (`_cache_key_query` is empty in Deep Research, so the key is
  the brief). A step 2+ now hits only when the earlier steps' reports cited the same instruments. A Deep Research
  key already required identical model-drafted plan text, so cross-user hits there were already rare;
  unmeasured (every stored replay ran with the cache off).
- **The audit's `delegations[].brief`**, read by `replay_report lookup --routing` without
  `without_handover_line` (agent D's fix in this batch). Its overstatement grows with this change: **briefs
  whose line names ids that the routing does not read: 72 of 829 under the gate, 520 of 829 under every step**
  (`extra_checks.out`). D's fix matters more after this merge.
- **`seam_replay worker`** replays the stored brief, so it agrees with the product. `summary_probe` reads the
  stored brief as the summariser query, as the product does.

## 4. Tests, the revert and the mutants

`tests/test_step_handover.py`: **21 tests** (was 23). The gate's 12 tests (`works_on_earlier_list`: 6 forms
recognised, 5 not, 1 malformed) and the "other steps unchanged" test are replaced by:
`test_every_later_step_gets_the_line_whatever_its_wording` (6 cases: two forms the gate knew, the form it missed,
an independent step, a provision-dependent step, no detail; each asserts the line's position before CONTEXT and
that removing it gives the brief exactly as before P3.10); `..._first_step_and_a_step_whose_earlier_reports_cite_
nothing_are_unchanged`; `test_a_case_law_report_hands_on_only_the_legislation_it_links`;
`test_a_failure_reading_the_reports_leaves_the_brief_as_it_was`; `test_a_step_with_no_question_still_gets_the_
line_last`; `test_run_deep_research_hands_every_later_step_what_all_earlier_steps_cite` (three steps, worded as
independent tasks, through the executor).

Command (scratch): `TEST_DATABASE_URL=… python mutants_b12.py` → `mutants_b12.out` (each case on a fresh copy of
`server_py` in `mut/`, removed after; anchors asserted to occur once, CRLF kept).
- **Revert** (`agent_core.py` and `step_handover.py` back to `a99e4d4`: **removes the 29 lines this change
  added and restores the 48 it removed**, the gate and its two patterns among them): **7 of 21 tests fail** (the four
  wording cases the gate rejects, the case-law test, the no-question test and the three-step executor test).
- **9 mutants of the replacement, 8 caught, 1 equivalent:** a wording gate put back (6 fail); a gate on the
  step having detail (1); an empty line appended (3); the line after CONTEXT (7); no earlier reports passed (2);
  only the previous step's report passed (1); the reports passed in reverse order (1); step 1 handed a report
  (2). **The `if earlier_reports:` guard removed SURVIVES and is equivalent**: `handover_line(None)` and
  `handover_line([])` already return "", so the guard only saves an import for step 1.
- **Batch 11 E's 12 mutants of the code kept, re-run against the new test file, 12 caught:** the body cut, the
  id form only, the dedupe, the cap at 5, the cap not applied, the "more" threshold, the "more" count, the
  emptiness guard, the line read by P3.7's extractor, the strip's line-start anchor, the strip removing only the
  label, and **`handover_line`'s fail-soft guard, which E's set did not mutate and which first SURVIVED here**:
  it had no test. It now has one (`test_a_failure_reading_the_reports_...`), which matters more now that every
  step 2+ goes through it.

## 5. The wording screen (built code)

Command (from `server_py/`): `python <scratch>/screen_b12.py > <scratch>/screen_b12.out`: the integrator's
`b9_screen.screen` (every answer-reading detector, whole and per sentence; unchanged) over the line rendered by
the built code for one `ukpga`, `asp`, `ssi`, `uksi`, `eur`, `nisr` and `wsi` id, two ids, a mixed five, at the
cap, one past it, 39 ids (the stored maximum) and the citation forms ("SSI 1901/3", "S.I. 1902/30",
"SR 1903/4"). **0 trips over 13 texts.** Option (b)'s wording (decision 1), rendered as a string transform of
the built line and labelled a proposal: **0 trips over 13 texts.** The full built brief is printed and read for
six kinds of step 2+ (list-dependent in the gate's form and in the form it missed, discovery, independent,
provision-dependent, case law) and for a step with no question. The line holds no square bracket, so the
`[…]`-block strippers do not apply; `strip_scope_blocks` leaves an echo of it in an answer alone (checked).

## 6. The grader for the 6374 n=3 sweep

Batch 11 E's `p310_grade.py` (bars 1-4) **graded `wave4_b11_sweep`'s rep 2 as having no dependent step**: its
dependent-step test is the gate's own pattern, so it missed the same step the gate missed, and its bar (1) read
PASS (6 of 6) over a step that dropped an instrument (`grade_b11sweep.out`, re-run here). Its default
before-column now also picks up `wave4_p331` (newer than E's grader; one of its 6383 turns carries the line).

`p310_grade_b12.py` (scratch) wraps it: (1) `--hand FILE.json` adds a dependent step by hand and grades its
list by E's definitions; every step 2+ that the broad screen flags (batch 10 D's `BROAD`, plus "retrieved",
"compiled", "the secondary legislation", the missed form's words) but neither pattern matches is printed as a
HAND-READ CANDIDATE; (2) every lined step 2+ that is not dependent gets its own `search_legislation` count and
its "new finds" (ids worked on that are not on the line), against the before-column's non-dependent steps 2+;
(3) the before-column excludes any turn whose steps carry the line, and the gated runs print as a middle
column. **Self-test (passes):** on `wave4_b11_sweep` with `hand_b11sweep.json` (that one step) it reproduces
Session 43's hand-read: rep 2 step 4 DROPS 1 (`grade_b12_selftest.out`). Its class filter reads "all" for a
"secondary legislation" step, so it lists 7 (the parent Act included) where the hand-read counted 6: **hand-read
the class of every hand-added step.** Before-column, non-dependent steps 2+: own `search_legislation` mean 2.10,
median 2; new finds mean 4.6 (n=10); the gated column's: mean 7.78, median 8; new finds 6.9 (n=9).

**For the sweep, hand-classify all 9 steps 2+ of the three `p310_6374` turns** (the plans differ per rep), then
run `p310_grade.py --before <the unlined dirs>` for bars (1)-(4) and `p310_grade_b12.py --hand …` for the
hand-added steps and the newly lined steps.

## 7. The price of 6374 n=3 (no spend; stored costs only)

Command (scratch): `python price_b12.py > price_b12.out`. The stored `p310_6374` reps (`wave4_b11_sweep`,
served by the gated code): **$1.132, $0.997, $1.027** (run totals; one turn each; 425-569 s; rep 3 had 2 empty
completions, both rate limits at 0 tokens, recovered); n=3 total $3.16, median $1.027, max $1.132. The stored
post-P3.8 full-session turn 4 of 6374 (n=5): median $0.767, max $0.862, **ratio 1.34** (the brief's "about
1.35"). Over the 76 stored post-P3.8 Deep Research turns, 5 had any empty completion, all 0 tokens.

| | per rep | n=3 |
|---|---|---|
| stored median | $1.03 | **about $3.10** |
| stored max | $1.13 | $3.40 |
| + the planner call (not in any run file's cost) | about $0.01-0.05 | about $0.03-0.15 |
| realistic worst rep (one capped Worker runaway, about $0.38, P4.10) | about $1.51 | |
| tail rep (a synthesis runaway: the synthesis and planner are not Worker or Manager calls, so uncapped and retried up to 3 times, about $2.30) | about $3.4 | |

**Direction of the change on cost: unknown.** Steps 2-3 of the stored reps ran 8 to 16 searches of their own
with no line; if the line leads them to work on the list, they get cheaper (the gated lined steps ran 0
searches, 8-12 tools); if it does not, the cost is as stored.

**Command** (from `server_py/`, the server up and pinned; a new directory so the gated column stays intact):
`python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p310_6374.json --reps 3
--out-dir $PREPILOT_EVIDENCE/replay/wave4_b12_p310 --max-spend 2.30`.
`--max-spend` is checked before each run (`grand_cost >= cap` stops), so **2.30 lets rep 3 start after two reps
at the stored maximum ($2.26)** and stops it if either of the first two ran away; Session 43's 1.75 stopped at
n=2. **Bound for the command: $2.30 plus one rep, about $3.81 realistic, about $5.70 in the tail.** Keep the
running total by hand (`sweep_total.py`), and stop between reps if one more could pass the figure the user
agrees. The 6383 script needs no re-run for this change's acceptance (6383 met 3 of 3), but its step 2 now gets a
line too (a discovery step in all three stored reps; the line there names 1 id, not of the SSI class it looks
for); about $1.80 more for n=3 if the user wants it (decision 3).

## 8. What I did NOT do

- No model call, seam draw (not even `--dry-run`), replay, server or live call; no edit to `replay_report.py`
  (D's), FIX_PLAN, the log, the tracker, CHANGELOG, CLAUDE.md, any rubric or any memory file.
- I did not change the wording (decision 1) or the research types the line goes to (decision 2).
- I did not touch `run_deep_research`, `run_worker_agent` or `agent_shared.py` (the summariser query and cache
  key, section 3).
- I did not measure the line's effect on any Worker: that is the sweep's job.
- I did not commit the grader, the dry-run scripts or their outputs: they are in scratch.
- Scratch: copied with `cp -r` to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch12/B/`:
  **36 files on both sides** (`find B -type f | wc -l`). `old/` (the exported base tree, rebuildable with `git archive`) and `mut/` (deleted by the
  mutant script) are not copied.

## 9. Decisions for the user (each self-contained; my recommendation first)

1. **The line's last sentence, now that the line reaches every step 2+.** The approved wording ends with a
   sentence of its own, "Look further only if the task asks for more than the earlier steps reported.", which
   is not inside the "Where this task works on instruments an earlier step identified" condition. On a
   discovery step (about 148 of the 457 newly lined stored steps; in all three stored `p310_6374` reps) it can
   read as "do not search".
   - **(a) Recommended: fold it into the condition before the sweep:** "... work on each one of the kind the
     task names, by its legislation_id, rather than finding the list again, and look further only if the task
     asks for more than the earlier steps reported." One sentence, so the limit applies only where the
     condition does. Screened: 0 trips over 13 renderings. A one-line change to `handover_line` and its wording
     test.
   - (b) Keep the approved wording as built, and let the 6374 n=3 sweep show whether discovery steps narrow
     (their own searches, new finds and bar (4)).
   - (c) Reword (the user's text), re-screened before merge.
2. **Which research types get the line.** It now goes to any Deep Research step 2+ whose earlier reports cite a
   legislation id, whatever the research type. A case-law-only or parliamentary Worker has no tool that takes a
   legislation_id; no stored Deep Research turn ran either way.
   - **(a) Recommended: leave it as built.** Those Workers' earlier reports rarely cite legislation ids, the
     line is conditional, and a case-law step in a mixed plan can use the instruments as search terms.
   - (b) Give it only to the legislation research types (`legislation_only`, `legislation_and_case_law`):
     `run_deep_research` passes the research type to `_build_step_brief` (two lines and a test).
3. **The acceptance sweep.**
   - **(a) Recommended: `p310_6374` n=3 only, as priced** (about $3.10, the command above, `--max-spend 2.30`,
     into a new directory), graded with `p310_grade.py` (bars 1-4) and `p310_grade_b12.py` after a hand
     classification of all 9 steps 2+.
   - (b) Also `p310_6383` n=3 (about +$1.80): its step 2 now gets a line, so a discovery step there is measured
     too.
   - (c) Run after decision 1 (a) only, so the sweep measures the wording that would ship.
4. **The grader.** E's `p310_grade.py` grades dependent steps by the gate's own pattern, so it cannot see the
   miss this change fixes.
   - **(a) Recommended: grade the sweep with both scripts and a hand classification of every step 2+** (section
     6), and say in the row which steps were added by hand.
   - (b) Promote `p310_grade_b12.py`'s additions into `replay_report` as a `p310` subcommand (a later P3 row).
5. **The cap of 15 ids on the line, now that P3.31 returns lists of up to 40** (section 2a: one stored step
   worked on exactly the 14 SSIs the line named and dropped the 23 it summarised as "and 23 more").
   - **(a) Recommended: raise `MAX_HANDED_ON_IDS` to 40** (P3.31's tool lists at most 40), so the line never
     decides how much of a list a step sees; about 520 more characters at 40 ids. Whether one step can work on
     37 instruments is then the step's own budgets' business (P3.1, P2.7, the context budget), which state their
     limits. One constant and its test; the line re-screened at 40.
   - (b) Keep 15 and run `p310_6383` at HEAD (decision 3 b) to see whether a made-under list reaches a
     dependent step in the acceptance runs before changing anything.
   - (c) Keep 15 as booked.
