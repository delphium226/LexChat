# Batch 1, agent B: the grader gaps (Session 33, 2026-09-29)

**Scope:** the six items in the gitignored `evidence/rubrics/batch1_B_rubric_gaps.md`
(three in `p33.json`, one in `INTERP_HEDGE`, two in `p32.json`, one not to be fixed). They are
all misreadings found by the Session 32 hand-read of `wave4_p33_post`. **Spend: $0** (no
paid call of any kind). No server, no `replay pin|run|restore`.

This note gives counts and file/rep/turn locations only. The sentences and the rubric
patterns name lawyers' matters, so they stay in the gitignored evidence. Every sentence that
moved was read by hand from the grader's `--sentences --drops` output in the session
scratchpad.

## Acceptance, stated before any claim

The brief sets these conditions: close each item (or say why not); record every verdict that
moves and every sentence that starts or stops counting, over every directory in the gaps
file's "Check after every change"; keep the booked before-columns failing
(`wave4_p33_pre` 9 of 9; `wave4_p32_pre` 3 of 3 plus 6345's 3); give each code change a
synthetic test that fails with the change reverted. **All are met** (evidence below).

## The six items, one line each

1. **Closed** (`p33.json`, 6370 `scope_reading` `unless`). The reported-judicial-statement
   exemption now allows a gap of up to 160 characters, with no full stop, between the court
   word and the verb. One sentence stops counting.
2. **Closed** (`p33.json`, 6370 `scope_reading` pattern). `becomes` was added beside
   `is|are`. One sentence starts counting.
3. **Closed** (code, `INTERP_HEDGE` in `server_py/tools/replay_report.py`). Added
   `under (the|that|this|one|a) reading`. One replay sentence and one seam-draw sentence move
   from asserted to hedged. There is a new test.
4. **Closed** (`p32.json`, 6406, one entry added to both `deny` and `contradicted`). The new
   entry is anchored on the wording the gaps file names ("requirements of" plus the chapter).
   It is deliberately narrow: "requirements **of**" only, so a conditional sentence in
   `wave4_p32_pre` r1 that says "requirements for" is not caught, and the chapter number is
   bounded so that the neighbouring chapter does not match. `wave4_p33_post` p32_6406 r2 goes from PASS to FAIL
   by command, which is what the hand-read found.
5. **Closed** (`p32.json`, 6406 `affirm`). One sentence-local, bounded entry for an answer
   that calls the denial of the proposition "incorrect". r1 export turn 7 goes from none to
   affirm.
6. **Not fixed, as instructed.** The implicit switch (r1 export turn 8) stays a hand-read
   item. No pattern was written. r1 t8 still grades `n`.

## What each change moved (every line of the before/after diff)

Directories checked after **every** change:
- `interpret --export --sentences --drops` over `baseline wave0_conv wave1 wave2 wave2_p24
  wave2_p24_final wave2_p24_pre wave2_p24_smoke wave4_p33_pre wave4_p33_post`. That is every
  replay directory holding 6338, 6370 or 6375 (checked by listing all 54; `wave2_p24_ab` holds
  none of them).
- `stance --sentences` over `wave4_p32_pre wave4_p33_post baseline wave1 wave2 wave0_conv`.
  That is every directory holding 6406 or 6345; `wave0_conv` was added beyond the gaps file's
  list because it holds a 6345.
- **Also, beyond the brief:** `interpret --drafts --sentences --drops` over the kept Session 32
  seam draws (`evidence/seam/s32/manager_ab/before`, `.../after`, `.../drift_probe`; 72 graded
  draws), and `stance_of` plus the `contradicted` list over every 6406 seam draw (30 files).
  These draws hold a booked number (Session 32's Manager-seam A/B, 6370 0 of 15 to 5 of 15).

| Item | Where it moved | Change | Verdict |
|---|---|---|---|
| 1 | `wave4_p33_post` 6370 r2 t4 | 1 sentence asserted, now exempt (reads as a DROP) | stays FAIL (t2, t4, t5, t6 still asserted) |
| 2 | `wave4_p33_post` 6370 r1 t3 | 1 sentence DROP, now asserted (t3 a1 to a2) | stays FAIL (already failing on t3) |
| 3 | `wave4_p33_post` 6370 r3 t6 | 1 sentence asserted, now hedged | stays FAIL (t5 asserted) |
| 3 | seam `manager_ab/after` 6370r1 `6370_t6_manager_rep2.md` | 1 sentence asserted, now hedged (a2h2 to a1h3) | stays FAIL |
| 4 | `wave4_p33_post` p32_6406 r2 t9 (run-file t8) | stance none to deny, 1 contradicted claim | **PASS to FAIL** |
| 5 | `wave4_p33_post` p32_6406 r1 t7 (run-file t6) | stance none to affirm; changes 3 to 4 (the t9 finding now reads affirm to both) | stays FAIL |

Nothing else moved in any output: no other replay directory, no export answer, no other seam
draw, and no 6406 seam draw.

**Verdict moves in total:** one, `wave4_p33_post` p32_6406 r2, PASS to FAIL (item 4). After the
changes, r1's command count of position changes (4) agrees with the Session 32 hand count ("4
changes by hand, 3 by command"). No `interpret` verdict moved anywhere. In `wave4_p33_post`,
6370 is still 0 of 3, 6338 is still 0 of 3 and 6375 is still 2 of 3.

**Booked before-columns, still failing:** `wave4_p33_pre` 9 of 9 FAIL (6338, 6370 and 6375,
r1 to r3). `wave4_p32_pre` p32_6406 3 of 3 FAIL and 6345 3 of 3 FAIL. The export's 6338, 6370
and 6375 still FAIL.

**Totals** (graded reps, failing): `interpret` 43, 40 before and after. `stance` 21, 20
before and 21, 21 after. Seam drafts 72, 60 before and after. Session 32's Manager-seam A/B is
unchanged: 6370 is 0 of 15 before and 5 of 15 after; 6338 is 0 of 12 and 1 of 12.

**`INTERP_HEDGE` beyond the rubric sessions** (it also feeds `hedges`' interp/1k): a
corpus-wide sentence search for the new form, over all 54 replay directories and the export's
answers for the five rubric sessions, finds **exactly one sentence**, the 6370 r3 t6 one above.
`hedges` over all 54 directories prints byte-identical output before and after.

## Commands

From `server_py/` in the worktree, with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`PYTHONIOENCODING=utf-8` and `R=$PREPILOT_EVIDENCE/replay`:

```
python -m tools.replay_report --dir $R/baseline interpret --export --sentences --drops \
  --also $R/wave0_conv $R/wave1 $R/wave2 $R/wave2_p24 $R/wave2_p24_final $R/wave2_p24_pre \
         $R/wave2_p24_smoke $R/wave4_p33_pre $R/wave4_p33_post
python -m tools.replay_report --dir $R/wave4_p32_pre stance --sentences \
  --also $R/wave4_p33_post $R/baseline $R/wave1 $R/wave2 $R/wave0_conv
python -m tools.replay_report --dir $PREPILOT_EVIDENCE/seam/s32/manager_ab/before interpret \
  --drafts --sentences --drops --also $PREPILOT_EVIDENCE/seam/s32/manager_ab/after \
  $PREPILOT_EVIDENCE/seam/s32/drift_probe
python -m tools.replay_report --dir $R/baseline hedges --also <the other 53 dirs>
```

The 6406 seam-draw stance check and the corpus sentence search were small scratch scripts.
They call `replay_report.stance_of` and `_interp_sentences`/`_plain` on each draw or answer,
and they were not committed.

## Rubric files (gitignored, main checkout)

- Backed up before the first edit to `evidence/rubrics/backup_batch1/` (`p32.json` sha1
  `3613b54…`, `p33.json` sha1 `47f37f1…`).
- Each edit was a single atomic write. The script edited the raw JSON text so the formatting
  was kept, asserted that the anchor occurred exactly once, validated with `json.loads`, wrote
  a temp file and then called `os.replace`. `p33.json` keeps its CRLF; `p32.json` was LF and
  stays LF. Both files parse. After: `p32.json` sha1 `fc8d8c2…`, `p33.json` sha1 `a91f9d3…`.
- Five pattern edits: p33 two (items 1 and 2), p32 three entries (item 4 in `deny` and
  `contradicted`, item 5 in `affirm`). The `_note` fields were not changed.

## Tests

- New: `test_under_a_reading_is_a_hedge_like_on_a_reading` (`tests/test_replay_interpret.py`,
  synthetic "Widget Order 1901" text). It covers five forms of the new hedge, a control ("Under
  this Order, ..." stays asserted), and `hedge_counts`.
- **Proven to fail with the change reverted:** on a scratch copy of `tools/` and the test file
  with the new `INTERP_HEDGE` line removed, the test FAILS (asserted, not hedged). With the
  line restored it passes.
- Items 1, 2, 4 and 5 are rubric data, not code, so they have no unit test; their evidence is
  the before/after diff above.
- Full suite on `lexchat_test_b` with the change in place: **1984 passed** (1983 at
  `01b66b0`, plus the new test). It ran in 18.5s.

## What I did NOT do

- I did not change `interpret` for the other over-count the Session 32 entry names for 6370
  ("grounded retrieval with a citation"). It is not in the gaps file, and the hand-read
  verdicts stand regardless.
- I wrote no pattern for item 6.
- I did not touch `FIX_PLAN.md`, `SESSION_LOG.md`, the tracker or memory.
- I made no paid call and did not start the server.

## For the integrator

- **The worktree came up on `main` (`b2a3fd8`), not the integrator's HEAD.** My branch had no
  commits, so I reset it to `01b66b0` before starting. The other agents' worktrees may have the
  same base; check before merging.
- **One test run went to `lexchat_test`**, the default: `pytest` on the two grader test files
  (32 tests, about 1s), before I set `TEST_DATABASE_URL`. The conftest session fixture drops
  every table at teardown, so if the integrator's own suite was running on `lexchat_test` at
  that moment it may have seen a spurious failure. Every later run used `lexchat_test_b`.
- The rubric edits are already live in the shared evidence. A grade taken from now on (by
  agent D with `p33.json` too) uses the fixed rubrics. Agent D's 6375 grades cannot move: none
  of the five edits touches 6375's items.
