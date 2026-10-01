# Batch 2, agent A: the grader gaps from `wave4_b1_post` (Session 34, 2026-10-01)

**Scope:** the seven items in `PARALLEL_BATCH_2.md` (agent A), taken from the last section of
the gitignored `evidence/rubrics/handread_wave4_b1_post.md`. Five are rubric data (four in
`p33.json`, one in `p32.json`), two are code (`INTERP_HEDGE` in `tools/replay_report.py`, the
note filter in `tools/summary_probe.py`). **Spend: $0.** No paid call, no server, no
`replay pin|run|restore`.

This note gives counts and locations only. The moved sentences and the rubric patterns name
lawyers' matters, so they stay in the gitignored evidence (`evidence/seam/batch2/A/out/`, one
directory of grader output per step: `before`, `item1` ... `item7`).

**Base:** the worktree came up on `main` at `a6b4a76`, not on the integrator's head. It had no
commits, so I ran `git reset --hard 578718f` before any work, as the brief says.

## Acceptance, stated before any claim

The brief's conditions: close each item or say why not; run the graders before and after every
change over every directory holding the graded sessions, over `wave4_b1_post` and over the
kept seam draws; record every verdict that moves and every sentence that starts or stops
counting; keep the booked before-columns failing (`wave4_p33_pre` 9 of 9; `wave4_p32_pre` 3 of 3
plus 6345's 3); in `wave4_b1_post`, move the command's verdicts towards the recorded hand-read
and never away; give each code change a synthetic test proven to fail with the change reverted.
**All are met** (evidence below).

## The seven items, one line each

1. **Closed** (`p32.json`, 6406). Four entries added to `deny`, three of them also to
   `contradicted`: the wording "cannot be a [the category]", the end product's requirements
   "apply only/exclusively/solely to [the category]", those requirements "cannot be used to
   process [the material]", and "derived from [the material] cannot meet the definition of [the
   end product]". `wave4_b1_post` p32_6406 r1 goes from PASS to FAIL by command, as the hand-read
   found; r2 export turn 7 now reads deny with a contradicted claim, as the hand-read found.
2. **Closed** (`p33.json`, 6370). The contradicted-claim item gets an `unless` for a negated
   "do(es) not explicitly/expressly state/provide/say"; the `scope_reading` exemption's "do(es) not state"
   now allows "explicitly"/"expressly" before the verb. One sentence stops counting (both as the
   contradicted claim and as asserted).
3. **Closed** (code, `INTERP_HEDGE`). Added `(on|under) your (reading|interpretation|
   construction)`. One answer sentence in the whole corpus moves, asserted to hedged.
4. **Closed** (`p33.json`, 6370 `scope_reading` reported-statement exemption). The miss had two
   causes: the verb is present tense ("notes"), and the gap holds a markdown link to a judgment
   whose label carries a bracketed year, which `_plain` cannot unwrap, so the URL's full stops
   broke the `[^.]` gap. The entry now allows present-tense verbs and a link URL inside the
   gap (it matches everything the old entry did). One sentence stops counting.
5. **Closed** (`p33.json`, 6338). A new `wrong` item: the word defined "by"
   the later Act's Schedule "and" the earlier Order (either order), with guards for the
   "same definition / does not apply / rather than" forms. The existing item could not take it:
   its `unless` list exempts any sentence naming the Order's long title, and this one does.
   Corpus-wide the new pattern matches exactly one sentence, the target. One sentence moves
   from DROP to a wrong-regime claim.
6. **Closed** (code, `summary_probe glosses`). A note is now also recognised by its two
   subjects: the supplied text named before the marker ("the provided/supplied/retrieved
   text ...") and "it" (or the text) right after it. I did not add "provide" to the
   `_ABOUT_SUMMARY` verbs: that would also drop a gloss drawn from absence about the
   instrument ("...; therefore, these Regulations do not provide for X"), which the module's
   design says is counted. One summary stops counting.
7. **Closed, narrowed** (`p33.json`, 6370 `scope_reading`, optional). Measured first: of 109
   asserted scope sentences in the replays and drafts, 16 carry a citation link, and several of
   those are the contested reading itself, so "has a citation" is not the test. The entry added
   exempts a sentence whose "apply to X" object is followed directly by a "(regulation N)"
   citation, and only when the sentence has no "only/exclusively/solely" and the object is
   not the contested category. Two sentences move. I read both against the raw text their run
   retrieved: each cited regulation says in terms that "These Regulations apply to" the
   category named. **Deliberately not moved:** `wave4_b1_post` 6370 r2 turn 3 ("Under
   [regulation N], the regulations apply to applications for [the contested category]"), which
   the hand-read calls retrieval. Any pattern that took it would also take the contested reading
   with a citation, so the command stays one sentence harsher than the hand-read there.

## What each change moved (every line of every before/after diff)

| Item | Where it moved | Change | Verdict |
|---|---|---|---|
| 1 | `wave4_b1_post` p32_6406 r1 export t9 (run-file t8) | stance none to deny; 3 deny sentences, 2 contradicted | **PASS to FAIL**; changes 0 to 1 |
| 1 | `wave4_b1_post` p32_6406 r2 export t7 (run-file t6) | stance none to deny; 1 sentence, contradicted | stays FAIL; changes stay 1 |
| 1 | `wave4_b1_post` p32_6406 r2 export t9 | one more deny sentence on a turn already deny | none |
| 2 | `wave4_b1_post` 6370 r3 t4 | 1 sentence wrong + asserted, now a DROP | stays FAIL (t5, t6) |
| 3 | `wave4_b1_post` 6370 r1 t6 | 1 sentence asserted, now hedged | stays FAIL (t2, t4, t5) |
| 4 | `wave4_b1_post` 6370 r1 t4 | 1 sentence asserted, now uncounted (off the rubric's topic, so not a DROP) | stays FAIL |
| 5 | `wave4_b1_post` 6338 r2 t2 | 1 DROP, now a wrong-regime claim | stays FAIL (t1 already fails) |
| 6 | `wave4_b1_post` p32_6406 r2 run-file t8, a section-search summary | 1 counted gloss, now a note | n/a (the detector has no verdict) |
| 7 | `wave4_p33_post` 6370 r2 t5 | 1 asserted, now a DROP | stays FAIL |
| 7 | `wave4_b1_post` 6370 r2 t5 | 1 asserted, now a DROP | stays FAIL |

Nothing else moved in any output: no other replay directory, no export answer, no seam draw
(72 Session 32 drafts and agent D's 29 batch-1 drafts graded by `interpret --drafts`; the 30
6406 Manager-seam draws of Session 32, plus agent C's 42 6406 summary draws, by `stance_of`
and `contradicted`; 356 seam `.md` files by the new gloss filter, which fires on none), and
`hedges` over all 55 directories is byte-identical before and after.

**Verdict moves in total: one,** `wave4_b1_post` p32_6406 r1, PASS to FAIL, which is the
hand-read's verdict.

**`wave4_b1_post` against the recorded hand-read, after:**

| | Hand-read | Command before | Command after |
|---|---|---|---|
| 6338 | 0 of 3 | 0 of 3 | 0 of 3 |
| 6370 | 0 of 3 | 0 of 3 | 0 of 3 |
| 6375 | 3 of 3 | 3 of 3 | 3 of 3 |
| p32_6406 | 0 of 3 | 1 of 3 (r1 PASS) | **0 of 3** |
| 6338 wrong-regime claims | 1 | 0 | 1 |
| 6370 unhedged readings (all reps) | about 6 | 13 | 9 |
| 6370 readings given as readings | about 12 | 8 | 9 |
| p32_6406 contradicted claim | 3 of 3 reps | 2 of 3 | 3 of 3 |
| gloss matches on 6406/6338 | 0 real | 1 | 0 |

Every count moved towards the hand-read and none away. The 6370 gap that remains is over-counts
the hand-read lists that are not among these items (the t2 restatements of the exemption
itself, r3 t6's neutrality statement, and item 7's r2 t3).

**Booked before-columns, still failing:** `wave4_p33_pre` 9 of 9 FAIL (6338, 6370, 6375, r1-r3);
`wave4_p32_pre` p32_6406 3 of 3 FAIL and 6345 3 of 3 FAIL; the export's 6338, 6370 and 6375 FAIL.

**Totals** (graded, failing): `interpret` 52 and 46, before and after; `stance` 27, 25 before
and 26 after; `interpret --drafts` 101 and 89, before and after. Corpus `INTERP_HEDGE` matches:
429 to 431 of 37,845 sentences (one answer sentence plus one line of a Session 33 notes file
that sits under `seam/` and is not an answer). `summary_probe glosses`: 224 to 223 counted, in
172 to 171 run-file turns; case-law listed rows unchanged.

## Commands

From `server_py/` in the worktree, with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`, `PYTHONIOENCODING=utf-8`,
`R=$PREPILOT_EVIDENCE/replay`, `S=$PREPILOT_EVIDENCE/seam`:

```
python -m tools.replay_report --dir $R/baseline interpret --export --sentences --drops --chars 2000 \
  --also $R/wave0_conv $R/wave1 $R/wave2 $R/wave2_p24 $R/wave2_p24_final $R/wave2_p24_pre \
         $R/wave2_p24_smoke $R/wave4_p33_pre $R/wave4_p33_post $R/wave4_b1_post
python -m tools.replay_report --dir $R/wave4_p32_pre stance --sentences --chars 2000 \
  --also $R/wave4_p33_post $R/wave4_b1_post $R/baseline $R/wave1 $R/wave2 $R/wave0_conv
python -m tools.replay_report --dir $S/s32/manager_ab/before interpret --drafts --sentences --drops \
  --chars 2000 --also $S/s32/manager_ab/after $S/s32/drift_probe $S/batch1/D
python -m tools.replay_report --dir $R/<first> hedges --list --also <the other 54 directories>
python -m tools.summary_probe glosses --list
```

The directory lists are every replay directory holding 6338, 6370 or 6375 (11) and every one
holding 6406 or 6345 (7), found by listing all 55. The whole sequence is
`evidence/seam/batch2/A/run_graders.sh <label>` (gitignored), and `cmp.sh <a> <b>` diffs two
labels. Four small scratch scripts, kept beside it and not committed, did the rest: the 6406
seam-draw stance check (`stance_of` plus `contradicted` on each draw), the corpus-wide
`INTERP_HEDGE` sentence list, a probe listing every sentence a candidate pattern or `unless`
entry would start or stop counting before it was written (`cand.py`, `cand_all.py`,
`unless_probe.py`, `gloss_probe.py`, `gloss_draws.py`), and `rawgrep.py`, which read item 7's
cited provisions out of the runs' own raw results.

## Rubric files (gitignored, main checkout)

- Backed up before the first edit to `evidence/rubrics/backup_batch2/` (`p32.json` sha1
  `fc8d8c2…`, `p33.json` sha1 `a91f9d3…`, the batch-1 "after" hashes).
- Every edit was atomic (`evidence/seam/batch2/A/edit_rubric.py`): a raw-text edit from a spec
  file, each anchor asserted to occur exactly once, the result validated with `json.loads`,
  written to a temp file in the same directory and moved over the original with `os.replace`.
  `p33.json` keeps CRLF and `p32.json` LF. For items 5 and 7 the stored pattern was then
  compared with the probed regex and found identical.
- Five edits: `p32.json` one (item 1, two lists); `p33.json` four (items 2, 4, 5, 7). After:
  `p32.json` sha1 `e14b762…`, `p33.json` sha1 `dce6d2f…`. The `_note` fields are unchanged.

## Tests

- New: `test_your_reading_is_a_hedge` (`tests/test_replay_interpret.py`; four forms of the
  hedge, a control "On your facts" that stays asserted, and `hedge_counts`) and
  `test_a_note_that_the_text_does_not_provide_something_is_not_a_gloss`
  (`tests/test_summary_probe.py`; the note, the same consequence drawn about the instrument,
  which stays counted, and "it" with no supplied-text subject, which stays counted). All text is
  synthetic.
- **Proven to fail with the change reverted** (`evidence/seam/batch2/A/revert_proof.py`, which
  copies `tools/`, `src/` and the two test files to a scratch tree and removes lines at byte
  level, printing the count): with nothing removed both tests pass; with the `INTERP_HEDGE`
  line removed (**1 line removed**) the hedge test fails; with the note filter removed (**2
  lines removed**, the `if` and its `continue`) the gloss test fails. Each revert's failure is
  the new test's, not the other's.
- `tests/test_replay_stance.py` is unchanged: item 1 is rubric data, and `stance` has no code
  change.
- Full suite on `lexchat_test_a` with every change in place: **2037 passed** (2035 at
  `578718f` plus the two new tests), 18.5s.

## What I did NOT do

- I did not edit the opener strip (the hand-read file's item 7, `utils/openers.py`): it is
  agent B's (P4.16).
- I did not try to make `_plain` unwrap a markdown link whose label carries brackets (item 4's
  root cause). That would change what every grader reads; the rubric entry tolerates it instead.
- I did not exempt item 7's third sentence (above), or the other 6370 over-counts the hand-read
  lists outside these items.
- I did not touch `FIX_PLAN.md`, `SESSION_LOG.md`, the tracker, CLAUDE.md, CHANGELOG, VERSION or
  memory. No push, no merge.

## For the integrator

- **The rubric edits are already live** in the shared evidence. Any grade taken from now on,
  by any agent, uses them. Agent C's 6338 grading picks up item 5's new wrong-regime item.
  Agent D's P3.2 evidence picks up item 1's patterns.
- **The command now agrees with the `wave4_b1_post` hand-read on all four verdicts** (it
  disagreed on p32_6406 r1). The hand-read stays the ground truth for the next after-column.
- **One cause is generic, not fixed:** `_plain` leaves a markdown link whose label contains
  `[...]` (a neutral citation's year) unwrapped, so any rubric gap written as `[^.]` stops at
  the URL. Item 4's entry works round it. Whether `_plain` should handle nested brackets is a
  decision, because it would move sentences in every grader.
