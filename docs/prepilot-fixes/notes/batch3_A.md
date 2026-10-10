# Parallel batch 3, agent A: P4.15 (c), the grader correction

Session 35, 2026-10-01. Branch `worktree-agent-a000ce9ca83520f30`. **The worktree came up on
`main` (`a6b4a76`), not on the integrator's head, so before any work I ran
`git reset --hard 72dc84efdd9a384333287591f8077f42dc3658c1`** (no commits had been made).
Spend **$0**: no model call, no replay, no server.

This note gives counts, directories, reps and turns. It quotes no question, answer, search term,
case name or instrument. Every command is run from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and `PYTHONIOENCODING=utf-8`
set. `$A` below is `../docs/prepilot-fixes/evidence/seam/batch3/A`.

**Where the scratch is, and why it is not where the brief said.** The harness refused writes
outside this worktree, so the scratch is in the worktree's own copy of the brief's path,
`<worktree>/docs/prepilot-fixes/evidence/seam/batch3/A/` (gitignored by the same `.gitignore`
line, `evidence/seam/`). **The integrator should copy that folder to the main checkout's
`evidence/seam/batch3/A/` before removing the worktree**, or it is lost with it. (An empty
`evidence/seam/batch3/A/` was created in the main checkout by my first `mkdir`; nothing is in it.)
It holds `run_all.py`, `c_matches.py`, `c_answers.py`, `footer_check.py`, `revert_c.py`,
`mutate_c.py`, the before/after grader outputs (`before/`, `after/`, 1,155 files each), the
64-sentence listing (`c_matches_list.txt`, matter text) and the two scratch copies (`revert/`,
`mutant/`).

## The acceptance, and whether it is met

**A's part of P4.15:** "the 9 verdicts move and nothing else, every new match read, and the tests
fail with the change reverted." **Met.**

- The 9 `negatives` verdicts D named move FAIL to PASS, and nothing else moves in 1,155 grader
  outputs other than the model column D predicted (below).
- All 64 newly matched sentences were re-read.
- The new tests fail with the change reverted (6 of 13 fail; the other 7 are guards, see Tests).

P4.15's own acceptance (`negatives` 0 on 6370, n=3) is the integrator's after-column and is not
claimed here. **The row is not closed by this branch:** (c) only corrects the grader; option (a)
is agent B's.

## What I changed, and why

`server_py/tools/replay_report.py`: `NEG_BLAMED_INDEX` gains ONE alternative, agent D's from
`notes/batch2_D.md` 1.6, byte for byte as D dry-ran it (`$PREPILOT_EVIDENCE/seam/batch2/D/
p415_dryrun.py`, `IDX_C`):

```
\bsearch(?:es)? of (?:the|this|our) [^.\n]{0,80}?\b(?:database|index|corpus|collection)\b
[^.\n]{0,240}?\breturned (?:no|zero) (?:results?|judgments?|matches|cases?)\b
```

with a comment saying why it exists and what it was measured to move. **One deviation from the
brief's wording, deliberately:** the brief says `[^.]` gaps "as the file's other alternatives
do"; D's alternative uses `[^.\n]`, which is stricter (it also stops at a line break). I kept D's,
so that the measured moves are the ones D read; it is still within one sentence.

Why: the model's commonest attribution of a case-law miss is "a search of the case-law database
for <terms> returned no results". That is P2.2's `index` condition ("the miss is attributed to the
index or the search"), but none of the older alternatives reads it (they want "in the database" or
"not ... database"), so the model column has under-read this form since P2.4, and 9 of 6370's
turns failed `negatives` on `index` alone while each says exactly this (D 1.3).

## Every number, with the command that produces it

**Before and after, all 21 subcommands D's dry run used, over all 55 directories:**
`python $A/run_all.py $A/before` on the integrator head, then the change, then
`python $A/run_all.py $A/after`; `diff -rq $A/before $A/after`. The script runs `summary halts
negatives derivations commencements currency scoperecord nosearch caselaw modes deadend siblings
scripted lookup drgaps blanks "lost --require-label" openers stance interpret hedges` in-process
per directory and writes each output with its exit code (1,155 outputs a side; no exception on
either side).

**Files that differ: exactly 4, all `negatives.txt`:** `wave2`, `wave4_p33_pre`,
`wave4_p33_post`, `wave4_b1_post`. No other subcommand's output changes in any directory.

**`negatives` verdicts that move: exactly 9, all FAIL to PASS, all 6370, all on `index` alone**
(the `index` cell goes NO to yes; `terms` yes and `limits` n/a are unchanged on every one):

| directory | turns (rep, turn) |
|---|---|
| `wave4_p33_pre` | r1 t3, r2 t3, r3 t4 |
| `wave4_p33_post` | r1 t3, r1 t5, r2 t2, r2 t5 |
| `wave4_b1_post` | r2 t5, r3 t4 |

These are exactly D's 9. Failing turns per directory: `wave4_p33_pre` 3 to 0, `wave4_p33_post` 5
to 1 (the one left is `p32_6406` r1 t4, failing on `terms`, not this shape: D 1.5, now P4.17),
`wave4_b1_post` 2 to 0. `negatives` exit codes: 15 directories exiting 1 before, 13 after
(`wave4_p33_pre` and `wave4_b1_post` go to 0).

**The 4 turns outside the shape stay failing, on `index`, unchanged:** `wave2_p24_ab` 6385 r2 t4
and r3 t4, `wave4_p46_pre` p46_6385 r1 t4, `wave4_p41_pre` p41_6346_dr r1 t2 (`grep FAIL
$A/after/<dir>/negatives.txt`). Their negatives do not have the sentence form, as D's hand-read
says, so the grader still fails them; covering them is option (a)'s job.

**The model column moves in exactly 4 directories, as D predicted:**

| directory | before | after |
|---|---|---|
| `wave2` | 8 (10%) | 14 (18%) |
| `wave4_p33_pre` | 0 (0%) | 14 (56%) |
| `wave4_p33_post` | 0 (0%) | 21 (58%) |
| `wave4_b1_post` | 2 (6%) | 19 (61%) |

That is 58 rows whose model cell goes no to yes (6 + 14 + 21 + 17), none the other way. Of the
58, 8 are verdicts above and 50 were already PASS through the footer. The ninth verdict,
`wave4_p33_pre` 6370 r2 t3, passes on the full answer but keeps "no" in the model column, because
its prose does not name its terms (below).

**`wave2_p22_final` (P2.2's acceptance directory) does not move** (`diff` reports its
`negatives.txt` identical). **`commencements`, the other reader of `NEG_BLAMED_INDEX`, is
byte-identical in all 55 directories** (15 exit 0, 40 exit 1, on both sides).

**Every newly matched sentence:** `python $A/c_matches.py --list` (prints matter text; the listing
is `$A/c_matches_list.txt`). It derives the pre-change regex by cutting the built alternative off
the built pattern, asserting that cut occurs exactly once.

- **64 sentences** in the model's prose matched by the new alternative and by nothing else:
  `wave2` 7, `wave2_p22` 2, `wave4_p33_pre` 17, `wave4_p33_post` 21, `wave4_b1_post` 17. **62 are
  about case law, 2 about legislation** (both `wave2_p22`, 6409 r1 t3 and t4). The same 64, the
  same split, as D.
- **Footers matched by the new alternative: 0** over every stored answer, so the change does not
  make the code-emitted footer any more self-crediting than it was.
- **I read all 64.** Each reports what a named search of a named database or index returned (no
  results, no judgments, zero results), with its keywords or a description of them. **None states
  a conclusion about the law.** The closest are clauses that qualify the search result itself,
  not the law: "meaning this index holds no judgments matching those terms" (1), "returned no
  results in this index" (1), and "returned no judgments/results interpreting this provision / to
  settle this interpretation / settling this boundary / clarifying this overlap / discussing this
  point" (7). All of these say what the search did not find, which is the attribution.

**Why 64 sentences make 58 model-column moves:** `python $A/c_answers.py` (ids only). 62 answers
newly pass `index` on the model's prose (the 2 `wave2_p22` sentences sit in answers another
alternative already credited, so they move nothing, which is why P2.2's directories do not move).
Of the 62, 58 move the model column; 4 assert a negative but stay "no" on another condition:
`wave2` 6407 r1 t1 on `limits` (a filter could bite and the prose names none), and
`wave4_p33_pre` 6370 r2 t1, t2, t3 on `terms` (the prose says "using your keywords" without
naming them; the footer names them, so the verdict passes).

**The product's own footer text:** `python $A/footer_check.py`: none of the 23 upper-case string
constants in `src/utils/search_scope.py`, nor agent B's proposed (a) sentence ("A search can miss a
judgment the database holds, ..."), is matched by the new alternative. So (c) adds no trip to the
detector list `test_case_law_gap.py` pins, and does not interact with B's sentence.

## Tests

`server_py/tests/test_replay_tooling.py`, 13 new tests, all synthetic text ("Widget Order 1901",
"widget licensing", "gadget levy"):

- `test_a_search_of_the_index_that_returned_nothing_is_an_index_attribution` (5 forms: case-law
  database, Find Case Law with keywords, "this index ... zero results", "our collection ... no
  matches", a legislation index): credited.
- `test_a_negative_about_the_law_with_no_search_named_is_not_attributed` (4): not credited.
- `test_a_named_search_followed_by_a_conclusion_of_absence_is_not_attributed` (3): a named search
  that "confirms that no court has considered" the thing; the search in one sentence and "returned
  no judgments" in the next; the same split by a line break. Not credited.
- `test_negatives_credits_the_reported_search_and_fails_the_conclusion`: end to end through
  `replay_report negatives` on a synthetic run file: the reported search is PASS with `index` and
  the model column yes; the named search followed by a conclusion of absence is FAIL on `index`.

**Revert check:** a scratch copy of `server_py` (`$A/revert/`), reverted by `python
$A/revert_c.py tools/replay_report.py`, which asserts its CRLF-normalised anchors occur exactly
once. **The revert removed 15 lines (18 replaced by 3)**, and the reverted file is identical to
`72dc84e`'s `replay_report.py` modulo CR. With it reverted: **6 failed, 7 passed** (the 5 credited
forms and the end-to-end test fail; the 7 guards pass, as they should, since the old regex
credited none of them).

**Mutation check of the guards** (they cannot fail on a revert, so I made them fail another way):
a second scratch copy (`$A/mutant/`) with the new alternative's two gaps widened from `[^.\n]` to
`[\s\S]` (`python $A/mutate_c.py tools/replay_report.py`): **2 failed, 12 passed**, the two
sentence-boundary guards (full stop, line break). So the sentence bound is pinned.

**Full suite on `lexchat_test_a`: 2090 passed** (2077 + 13), `python -m pytest -q`.

## What I did NOT do

- Did not build option (a) (agent B's), touch any product code, or edit any rubric.
- Did not run any replay, seam draw, server or model call.
- Did not change `NEG_BLAMED_INDEX`'s other alternatives or any other detector.
- Did not edit FIX_PLAN.md, SESSION_LOG.md, summary-table.html, CLAUDE.md, CHANGELOG.md, VERSION
  or any memory file. Did not push or merge.

## For the integrator to decide

- **A known limit of the alternative, with 0 stored instances:** a single sentence that reports
  the search AND concludes about the law ("a search of the database for X returned no results, so
  no court has considered the point") is credited, because the attribution is in it. None of the
  64 stored sentences does this (read), and splitting it would need a clause-level grader. Worth
  re-checking in the after-column's `c_matches.py --list` run, which re-reads the new matches on
  fresh answers.
- **The published model-column numbers move** in `wave2`, `wave4_p33_pre`, `wave4_p33_post` and
  `wave4_b1_post` (table above). None of P2.2's acceptance numbers moves.
- Copy `<worktree>/docs/prepilot-fixes/evidence/seam/batch3/A/` to the main checkout before
  removing the worktree (see the top).
