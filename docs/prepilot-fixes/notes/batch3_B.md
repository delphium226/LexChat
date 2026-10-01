# Parallel batch 3, agent B: P4.15 (a), the case-law footer's absence sentence

Session 35, 2026-10-01. Branch `batch3-B`. The worktree came up on `main` (`a6b4a76`), not on
the integrator's head, with no commits made, so before any work I ran
`git reset --hard 72dc84efdd9a384333287591f8077f42dc3658c1` and created `batch3-B` from it.
Spend **$0**: no model call, no replay, no server. Every command below is run from `server_py/`
of this worktree with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8`; pytest also with
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b`. `$B` stands
for `$PREPILOT_EVIDENCE/seam/batch3/B` (gitignored; my scripts and outputs are there). This note
names directories, sessions, reps and turns only; it quotes no answer.

## The acceptance, and whether it is met

**B's part of P4.15 (deterministic):** the sentence in place, every coupling held and tested,
each new test failing with the change reverted, and the dry run moving exactly D's 13 verdicts.
**Met.** Each part below.

This is not P4.15's row acceptance (`negatives` 0 on 6370 n=3), which needs the after-column
`wave4_b2_post`; nothing here claims it.

## What I changed, and why

`server_py/src/utils/search_scope.py`:

- a new constant `CASE_LAW_ABSENCE_SENTENCE`, worded exactly as D dry-ran it (D's note 1.6): "A
  search can miss a judgment the database holds, so one missing from its results may still exist,
  in this database or elsewhere: that is not proof of absence." (158 characters);
- a comment in the file's style: P4.15 (B5), why (the coverage sentence never said that a search
  finding nothing is not proof of absence; a turn with no `search_legislation` gets the case-law
  line alone), the gate, the placement, that it trips only `NEG_BLAMED_INDEX` by design, and why
  the two earlier wordings were rejected;
- `_case_law_body`: the tail is now `" {ABSENCE} {DOCTRINE}"` when a search ran (`done`) and
  empty otherwise, so the sentence sits after `CASE_LAW_COVERAGE_SENTENCE` and before
  `CASE_LAW_DOCTRINE_SENTENCE`, never on an errored search, and reaches both
  `case_law_scope_clause` and `case_law_scope_footer` (and so `answer_scope_footer`,
  `carried_scope_footer` and `lookup_scope_footer`, which all join the clause);
- `__all__` gains the constant.

`git diff --numstat 72dc84e -- server_py/src`: 26 lines added, 3 removed, one file.
`CASE_LAW_COVERAGE_SENTENCE` and `CASE_LAW_DOCTRINE_SENTENCE` are unchanged, so
`replay_report.CASE_LAW_CODE` still prefixes the coverage sentence
(`test_the_instrument_is_coupled_to_the_product_sentence` passes unchanged).

## Couplings, each tested (existing tests extended, none weakened)

`server_py/tests/test_case_law_gap.py`:

- **New `test_a_search_that_ran_says_a_miss_is_not_proof_of_absence`:** in the clause, the
  standalone line, a mixed ran/errored line and a fresh legislation line with the clause, the
  sentence appears once, directly after the coverage sentence (one space), before the doctrine
  sentence, and the line still ends with the doctrine sentence; the standalone line is still one
  line; not on an errored-only search, not on a legislation-only footer.
- **`test_the_case_law_sentence_trips_no_detector_of_its_own`:** every existing assertion kept.
  Added: the sentence matches `rr.NEG_BLAMED_INDEX` and matches neither `rr.NEG_LIMITS` nor
  `rr.NEG_TERMS`; the same on the code's text from the coverage sentence on, in the clause and
  the standalone line (read from there because the opening `was searched for "a"` already
  matches `NEG_TERMS`, before and after this change); an errored-only line does not match
  `NEG_BLAMED_INDEX`.
- **P2.8's round trip (`test_p28_reads_back_a_fresh_footer_that_carries_the_clause`, all 4
  parametrisations):** the fresh line carries the sentence exactly when its case-law search ran,
  and the carried line built from it contains neither the sentence, nor the coverage or doctrine
  sentence, nor "judgment" or "case law" (on top of the existing "case-law"). Also extended:
  `test_a_standalone_case_law_line_is_never_read_as_a_legislation_search` (the standalone line
  now carries the sentence and is still never parsed as a legislation line) and
  `test_a_hybrid_follow_up_that_searched_only_case_law_keeps_one_line` (that turn's carried
  line has the sentence; a later unsearched reply's carried line restates the legislation terms
  and never the sentence or "case-law").

`server_py/tests/test_echoed_footer.py`:

- `test_an_echo_ahead_of_the_link_note_is_stripped` (line 126's end-of-line assertion kept):
  the sentence is present once, before the doctrine sentence.
- **New `test_an_echo_of_the_longer_case_law_line_is_stripped`** (2 cases: a fresh legislation
  line with the clause, and the standalone case-law line, each now longer by the sentence): the
  echo is one line carrying the sentence; through the Manager path the lawyer gets one scope line,
  this turn's, with the sentence once and the doctrine sentence last; `strip_answer_footer`
  (P4.14's `_ECHOED_FOOTER`), `replay_report._without_footer` and `tools/footer_echo`'s
  `split_answer`/`rebuild` each take the longer line whole.

## Revert checks (on a scratch copy, `$B/revert/server_py`)

- **Partial revert, 1 line** (`python $B/revert.py .`: the `_case_law_body` tail line back to its
  pre-change form, anchor asserted exactly once in the CRLF-normalised text, the constant left
  defined so the tests fail on assertions, not on import): `pytest tests/test_case_law_gap.py
  tests/test_echoed_footer.py` **11 failed, 72 passed**. Failing: the new placement test, P2.8's
  round trip in 3 of its 4 parametrisations (the 4th has only an errored case-law search, where
  the sentence is correctly absent either way), the standalone-line test, the hybrid follow-up
  test, the detector-list test, line 126's test (2 cases) and the new echo test (2 cases). Every
  new or extended test fails.
- **Full revert, 26 lines removed and 3 restored** (`git show 72dc84e:server_py/src/utils/
  search_scope.py` over the scratch copy): both test modules fail at import
  (`CASE_LAW_ABSENCE_SENTENCE` undefined).

## The dry run (D's script, unchanged, fed the built constant)

- `python $B/run_dryrun.py $B/dryrun` sets `P415_ATTR` from
  `search_scope.CASE_LAW_ABSENCE_SENTENCE` (never retyped) and `P415_VARIANTS=base,a`, prints
  the trees imported (product and graders both from this worktree's `server_py`; graders as at
  `72dc84e`, `replay_report.py` untouched), asserts D's hard-coded `COVERAGE` equals
  `CASE_LAW_COVERAGE_SENTENCE` (True, so the insertion point is where `_case_law_body` puts the
  sentence), then runs `$PREPILOT_EVIDENCE/seam/batch2/D/p415_dryrun.py` with `runpy`.
  For the stored answers taken after Session 32 the inserted text is then byte-identical to the
  built line (coverage, absence, doctrine); older answers carry no doctrine sentence, as stored.
- Result: **55 directories, 1,155 outputs a variant; 204 stored answers changed** (D: 204).
- `python $B/compare.py $B/dryrun` (every differing output, unified diff): **6 outputs differ,
  all `negatives`; 13 verdicts FAIL to PASS, each on the `index` column alone (NO to yes); nothing
  else moves in any of the 21 subcommands.** The 13:
  - `wave4_p33_pre` 6370 r1 t3, r2 t3, r3 t4;
  - `wave4_p33_post` 6370 r1 t3, r1 t5, r2 t2, r2 t5;
  - `wave4_b1_post` 6370 r2 t5, r3 t4;
  - `wave2_p24_ab` 6385 r2 t4, r3 t4;
  - `wave4_p46_pre` p46_6385 r1 t4;
  - `wave4_p41_pre` p41_6346_dr r1 t2.

  Exit codes: `negatives` 1 to 0 on `wave4_p33_pre`, `wave4_b1_post`, `wave2_p24_ab`,
  `wave4_p41_pre`, `wave4_p46_pre`; `wave4_p33_post` stays 1 (5 failing to 1, the remaining one
  being p32_6406 r1 t4, P4.17's shape). **Identical to D's result; nothing differs.**
- **Detectors:** `python $B/detectors.py` (D's `p415_detectors.py` list, on the built constant;
  it also checks that D's literal equals the constant: True): the sentence trips
  `NEG_BLAMED_INDEX` and nothing else (`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_USER`,
  `IN_FORCE_CLAIM`, the three halt detectors, `NEG_LIMITS`, `NEG_TERMS`, `SCOTS_CASELAW_GAP`,
  `NEGATIVE_EXPLAINED` all False; no derivation claim, no currency assertion, no case-law gap
  statement). On the code's text from the coverage sentence on, `NEG_BLAMED_INDEX` goes False to
  True and `NEG_LIMITS`, `NEG_TERMS`, `NEG_ASSERTED`, `NOT_FOUND` stay False.

The dry run reads stored answers, which carry no model echo of the new line; the echo strip is
pinned by the unit test above instead. Read: only the 6 diff hunks (grader rows: counts and
locations, no matter text); no answer text was printed or needed, since the inserted text is
fixed and D read every one of the 13 turns.

## Tests

Full suite on `lexchat_test_b`: **2080 passed** (`python -m pytest -q -p no:cacheprovider`;
2077 at the integrator head, plus the new placement test and the new echo test's 2 cases).

## What I did not do

- No edit to `replay_report.py` (agent A's (c) is there), to any rubric, `FIX_PLAN.md`,
  `SESSION_LOG.md`, `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md` or `VERSION`.
- No replay, no server, no model call; no push, no merge, `main` untouched.
- No change to P2.8's carried line, the lookup footer or the legislation footer's own text.
- Did not re-run D's (b) or (c) variants (A's section measures (c) against its built grader).

## For the integrator to decide or know

- **Merge interaction with agent A's (c).** My dry run used the grader at `72dc84e`. Once A's
  wider `NEG_BLAMED_INDEX` is merged, the 9 shape turns pass by (c) on the model column as well;
  the code column's 13 should be unchanged, but the combined dry run (both variants together) is
  the integrator's to run after merging, if wanted.
- **D's hazard stands:** a hybrid turn with no `search_legislation` that writes a *legislation*
  negative and gets only the case-law line would have that negative credited by a sentence about
  judgments. Stored instances 0 (D); the grader cannot tell. P4.17 is the related gap.
- The existing test fixture text "FOISA section 36" is reused in one new assertion (it was already
  the hybrid follow-up test's synthetic legislation search).
- The branch is `batch3-B` (I created it after the reset), not the worktree's auto-named branch.
