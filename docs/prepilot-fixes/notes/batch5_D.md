# Batch 5, agent D: the grader gaps from `wave4_b4_post` (Session 37, 2026-10-02)

**Scope:** the four items in the "Grader gaps found" section of the gitignored
`evidence/rubrics/handread_wave4_b4_post.md`, plus the two batch 4 A decisions the user took at
launch: **(i) YES**, extend the 6338 turn-3 sequence item from "must ... precede" to "should
precede" / "would need to conclude before"; **(ii) YES**, keep the `p32_6406` r2 export t7
implicit-affirm entry. Two gaps are fixed in code (`tools/replay_report.py`: `derivation_claims`
and `INTERP_HEDGE`); the rest are rubric data (`p33.json` for 6338 and 6370, `p32.json` for 6406).
**Spend: $0.** No model call, no server, no `replay pin|run|restore`, no API call.

This note gives counts and locations only. The moved sentences and the rubric patterns name
lawyers' matters, so they stay in the gitignored evidence.

**Base:** the worktree came up on `main` at `a6b4a76`, not on the integrator's head. It had no
commits, so I ran `git reset --hard dde8b41` before any work. Everything here is based on
`dde8b41`.

**Scratch:** the harness refused compound shell commands that touch git, so scripts were written
with the Write tool into the worktree's own gitignored
`docs/prepilot-fixes/evidence/seam/batch5/D/` (checked with `git check-ignore -v`). Plain `cp` to
the main checkout worked: the rubric backups, the rubric install (a Python script) and, at the
end, a copy of the whole scratch folder to `$PREPILOT_EVIDENCE/seam/batch5/D/`. Grader outputs
per label are under `out/` there: `before`, `before2`, `after1`, `after2` and `installed`.

## Acceptance, stated before any claim

D's part of the brief, and whether each check passes:

| Check | Result |
|---|---|
| `wave4_b4_post` `derivations`: 0 unverified | **PASS** (was 1 of 51 turns; now 0 of 51) |
| `wave4_b4_post` `interpret` 6370: 1 of 3, r3 PASS | **PASS** (was 0 of 3) |
| `wave4_b4_post` `stance` `p32_6406`: positions as hand-read, changes 1, 5, 1, contradicted 3 of 3 | **PASS** (positions now equal the hand-read's main reading in all three reps) |
| other five named directories: no verdict moves except toward their hand-read | **PASS** (no rep verdict moves in any of them; every count that moves is listed below) |
| `hedges` unchanged over all 57 directories | **NOT byte-identical**: one number moves, `wave4_b4_post` interpretive hedges per 1,000 words 3.1 to 3.2, a direct result of gap 2. Every guard column (answers, retrieval statements, hedged, caveats) and the whole `--list` output are identical in all 57. Decision 1 below. |
| each code-side test fails with its change reverted | **PASS** (below) |

**6370's unhedged count on `wave4_b4_post`, by command: 4 (r1 1, r2 3, r3 0), against the
hand-read's about 4 (r1 1, r2 about 3, r3 0).** It was 13 (5, 4, 4). Readings given as readings,
by command: 8 (6, 2, 0), against about 12 by hand (see "Not done").

| `wave4_b4_post` | Hand-read | Command before | Command after |
|---|---|---|---|
| `derivations` unverified | 0 | 1 (6370 r3 t3) | **0** |
| 6370 r1 / r2 / r3 | FAIL / FAIL / PASS | FAIL / FAIL / FAIL | **FAIL / FAIL / PASS** |
| 6370 unhedged | about 4 (1, ~3, 0) | 13 (5, 4, 4) | **4 (1, 3, 0)** |
| `p32_6406` positions t6-t12 | r1 d d (a) d n a a; r2 d a a b d b a; r3 d d n d n a a | r1 n d n d n a n; r2 d a n b d b a; r3 n n n d n a a | **r1 d d n d n a a; r2 d a a b d b a; r3 d d n d n a a** |
| changes | 1 (3 if r1 t8 counts), 5, 1 | 1, 5, 1 | 1, 5, 1 |
| contradicted | 3 of 3 (t9 each) | 3 of 3 | 3 of 3 |

r1 t8 stays "none": the hand-read's main reading counts 1 change for r1 and calls t8 "an
implicit affirm at most", so no pattern was written for it.

## The gaps, one line each

1. **Closed, code** (`derivation_claims`). The sentence was "Applications made under section N
   of the Act ... ([regulation N(n)](link))": a participial "made under", made *specific* only by
   the instrument number in the link's URL. A new `_DERIV_NOT_INSTRUMENT` removes a derivation
   predicate whose head is a thing a person makes (application, appeal, request, proposal,
   representation, objection, complaint, claim, payment, requirement, referral, notification,
   nomination; with or without "is/are/was/were/has been ... "), and the predicate tests run on
   the rest of the sentence, so a real claim beside it still counts. Measured first
   (`deriv_probe.py`): 284 sentences in the "made under" vocabulary over 57 directories; among
   those `derivation_claims` counts, "applications" is the only non-instrument head. A second
   route was measured and not taken: reading specificity from link labels only (dropping URLs)
   moves the same single sentence today (`deriv_url_probe.py`: 1 sentence specific only through a
   URL), but would also stop a real claim whose instrument is named only by its link.
2. **Closed, code** (`INTERP_HEDGE`): "on/under a/the/one first/second/third/fourth/fifth/
   further/other/opposite/contrary/opposing/rival reading/view/interpretation/construction". Over
   the whole corpus (every replay answer, every seam `.md`, the export's rubric sessions; 42,033
   sentences) it adds exactly one sentence, the target (`hedge_cand.py`; corpus matches 540 to
   541). **"On the alternative reading" was already a hedge** (the existing "the ... alternative
   reading" alternative; checked by calling `INTERP_HEDGE` on the sentence), so the hand-read's
   wording of this gap is wrong on that half. That sentence (r2 t4) is a DROP because the 6370
   item's pattern does not enrol it, which moves no verdict.
3. **Closed, rubric** (`p33.json`, 6370 `scope_reading`): five `unless` entries and one widened
   entry, each probed before writing (`unless_probe.py`, every replay directory, the export and
   every seam draw, graded turns):
   - a restatement of the exemption provision's own words ("do not apply [to a project] if [the
     project | it] constitutes [the class] to which ..."): 6 sentences (`wave4_b1_post` r1 t2,
     `wave4_b2_post` r1 t2, `wave4_b4_post` r1 t2, r3 t2, r3 t6, `wave4_p33_post` r2 t6);
   - "does not settle": 3 (`wave4_b2_post` r2 t5, `wave4_b4_post` r1 t6, r2 t6);
   - a sentence reporting a case-law search: 2 (`wave4_b4_post` r1 t6, r2 t6, the second also
     caught by the line above);
   - a lead-in to a list of cited provisions ("... state they apply to:"): 1 (b4 r3 t3);
   - a sentence about a case ("It did not directly address ..."): 1 (b4 r3 t4);
   - the existing retrieval exemption ("apply to X (regulation N(n))") widened to a citation of
     two paragraphs ("(regulation N(n) and (m))"): 1 (b4 r2 t3).

   And one pattern alternative for a firm reading the hand-read lists among the drops ("the
   Regulations define their scope and apply their requirements through ..."): 1 sentence, b4 r2
   t3, counted unhedged.
4. **Closed, rubric** (`p32.json`, 6406), measured with `stance_delta.py` (every 6406 run in
   every replay directory, the export and every seam draw; output `gap4_delta_out.txt`):
   - deny "would be classified as [the other material] rather than a [category]" / "would fall
     under the specific definition of [the other material] rather than the general category of
     [category]": b4 r1 t6 and r3 t6 none to deny; b4 r2 t6 gains a second deny sentence (already
     deny). The unbound first draft also took a conditional in `wave4_b1_post` r3 t7 ("if [it]
     is classified as ... rather than ..."), so the entry is bound to "would".
   - deny "does not need to be classified as a [category]": b4 r3 t7 none to deny, **and
     `baseline` 6406 r2 t7 none to deny** (the same sentence form; changes stay 3, verdict stays
     FAIL). Decision 3.
   - affirm "could be processed into a [product]": b4 r1 t12 none to affirm; `wave4_b2_post`
     r2 t12 gains a second affirm sentence (already affirm).
   - affirm, implicit, b4 r2 t8: "[... Annex N], the [material] ... must undergo further
     processing" (the turn then puts it through the chapter's process). Matches that one
     sentence in the corpus. It moves positions only (r2 changes are 5 either way). Decision 4.

**Decision (i), applied** (`p33.json`, 6338 `must_sequence`): "must ... precede" becomes
"(must|should) ... precede", plus "would [logically/...] need/have to conclude/finish/end/be
completed before". Newly caught, every match over every replay directory, the export and every
seam draw (`seq1_out.txt`): **2 sentences, `wave4_b1_post` 6338 r1 t3 and `wave4_p33_post` 6338
r2 t3**, the two batch 4 A named. A wider probe for any other sequence wording on turn 3
(`seqwide_out.txt`) found one more sentence, a passive "must be preceded by a statement" that
restates the provision, deliberately not caught. **No rep verdict moves:** `wave4_b1_post` r1
already fails on turn 1 (by hand and by command), `wave4_p33_post` r2 on turns 1 and 2 (by
command; A's note records the hand-read failing it elsewhere). At turn level the two turns now
fail where those directories' hand-reads graded turn 3 clean: that is what (i) decides.

**Decision (ii):** the r2 export t7 implicit-affirm entry is untouched and still matches only its
sentence.

## What moved (every line of the before/after diff)

Directories: `interpret` over every replay directory holding 6338, 6370 or 6375 (13, now with
`wave4_b4_post`) plus the export; `stance` over every directory holding 6406 or 6345 (9);
`interpret --drafts` over the whole `seam/` tree (109 graded draws); `stance_of` plus
`contradicted` over every 6406 seam draw; `derivations` (with `--answers`, and with `--drops`) on
each of the 57 replay directories; `hedges` and `hedges --list` over all 57; and every sentence
`INTERP_HEDGE` matches over every replay answer, every seam `.md` (excluding `seam/batch5/`, where
other agents were writing during the run) and the export.

| Where | Change | Rep verdict |
|---|---|---|
| `wave4_b4_post` `derivations` | 6370 r3 t3 claim to none (now a `--drops` line) | 1 to 0 unverified (hand-read: 0) |
| `wave4_b4_post` 6370 r1 | t2 restatement dropped; t6 "does not settle", case-law search dropped, "third reading" asserted to hedged | FAIL stays (hand-read FAIL) |
| `wave4_b4_post` 6370 r2 | t3 retrieval dropped, t3 firm reading added; t6 "does not settle" dropped | FAIL stays (hand-read FAIL) |
| `wave4_b4_post` 6370 r3 | t2, t6 restatements, t3 lead-in, t4 sentence about a case dropped | **FAIL to PASS** (hand-read PASS) |
| `wave4_b2_post` 6370 r1, r2 | r1 t2 restatement, r2 t5 "does not settle" dropped (both hand-read over-counts) | FAIL stays (hand-read 0 of 3) |
| `wave4_b1_post` 6370 r1 | t2 restatement dropped (hand-read over-count) | FAIL stays (hand-read 0 of 3) |
| `wave4_p33_post` 6370 r2 | t6 restatement dropped | FAIL stays (hand-read 0 of 3) |
| `wave4_b1_post` 6338 r1, `wave4_p33_post` 6338 r2 | t3 gains `must_sequence` (decision (i)) | FAIL stays |
| `wave4_b4_post` `p32_6406` r1 | t6 none to deny, t12 none to affirm | FAIL, changes 1 stay |
| `wave4_b4_post` `p32_6406` r2 | t8 none to affirm; t6 a second deny sentence | FAIL, changes 5 stay |
| `wave4_b4_post` `p32_6406` r3 | t6, t7 none to deny | FAIL, changes 1 stay |
| `wave4_b2_post` `p32_6406` r2 | t12 a second affirm sentence | unchanged |
| `baseline` 6406 r2 | t7 none to deny | FAIL, changes 3 stay |
| `hedges` | `wave4_b4_post` interp/1k 3.1 to 3.2 | (no verdict) |
| `INTERP_HEDGE` corpus | +1 sentence (the target) | |

Nothing else moved: `wave4_p33_pre` and `wave4_p32_pre` are byte-identical in every grader;
`interpret --drafts` and the 6406 seam draws are identical; `derivations` is identical on the other
56 directories. Totals (graded, failing): `interpret` 64 and 55 before, 64 and 54 after;
`stance` 36 and 35, unchanged; `interpret --drafts` 109 and 91, unchanged.

**Unhedged 6370 counts by command, the six named directories** (before to after; hand-read):
`wave4_b4_post` 13 to 4 (about 4); `wave4_b2_post` 19 to 17 (about 15: the remaining two
over-counts are the retrieval sentences r1 t4 and r3 t6, not in this gap list); `wave4_b1_post`
9 to 8 (about 6); `wave4_p33_post` 7 to 6 (about 7: the dropped sentence is a restatement, which
the rule written into the hand-reads since `wave4_b2_post` excludes); `wave4_p33_pre` 22
unchanged (about 21); `wave4_p32_pre` holds no 6370.

## Commands

From `server_py/`, with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`PYTHONIOENCODING=utf-8`, `R=$PREPILOT_EVIDENCE/replay`, `RUB=$PREPILOT_EVIDENCE/rubrics`:

```
python -m tools.replay_report --dir $R/wave4_b4_post derivations
python -m tools.replay_report --dir $R/wave4_b4_post interpret --rubric $RUB/p33.json --sentences --drops
python -m tools.replay_report --dir $R/wave4_b4_post stance --rubric $RUB/p32.json --sentences
python -m tools.replay_report --dir $R/baseline interpret --rubric $RUB/p33.json --export --sentences --drops \
  --chars 2000 --also <the other 12 directories holding 6338, 6370 or 6375>
python -m tools.replay_report --dir $R/wave4_p32_pre stance --rubric $RUB/p32.json --sentences --chars 2000 \
  --also <the other 8 directories holding 6406 or 6345>
python -m tools.replay_report --dir $R/<first> hedges [--list] --also <the other 56 directories>
```

The whole sequence is the scratch `run_graders.sh <label>` (with `CODE=` for the code tree and
`RUBRICS=` for the rubric directory); `cmp.py <a> <b>` diffs two labels and `verdicts.py <a> <b>`
lists every rep whose verdict or sequence line differs. `before` and `before2` are the head's
code (`git show dde8b41:...` into a scratch tree) with the backed-up rubrics, identical to each
other; `after2` and `installed` are identical.

## Rubric files (gitignored, main checkout)

- Backed up before the first edit to `evidence/rubrics/backup_batch5/`: `p32.json` sha1
  `7927e642…`, `p33.json` sha1 `5e5769ab…` (the brief's hashes).
- Edited as copies in the worktree with batch 4 A's `edit_rubric.py` (patterns written from
  Python raw strings; `p33.json` round-trips byte for byte; `p32.json` edited as raw text), then
  installed by `install_rubrics.py` (asserts the main files still had the backed-up hashes,
  validates JSON, temp file plus `os.replace`). **After: `p32.json` sha1 `31379ecf…` (8,203
  bytes), `p33.json` sha1 `0031831b…` (13,538 bytes).** The `_note` fields are unchanged.
- Edits: `p33.json` 9 (6370: 5 `unless` added, 1 `unless` widened, 1 pattern alternative; 6338:
  1 substring, 1 alternative); `p32.json` 4 (2 `deny`, 2 `affirm` added).
- Rubric-only changes have no code-side revert test; the verdicts they move are in the table
  above (only `wave4_b4_post` 6370 r3, FAIL to PASS, with gap 2's code change).

## Tests

- New, synthetic text only: `test_an_application_made_under_a_section_is_not_a_derivation_claim`
  (`tests/test_replay_tooling.py`: an application or appeal made under a section, even beside a
  numbered instrument or a link to one, is no claim; a real claim beside it still counts; a
  plain claim still counts) and `test_a_numbered_or_contrasted_reading_is_a_hedge`
  (`tests/test_replay_interpret.py`: "On a third reading", "On the other reading", "Under a
  second reading" hedge; a Bill's "third reading" does not; `hedge_counts` both ways).
- **Proven to fail with each change reverted** (scratch `revert_proof.py`: copies `tools/`, `src/`
  and the two test files to a scratch tree and reverts at byte level, each anchor asserted to
  occur exactly once, CRLF kept): the derivation change reverted (**14 lines removed, 2
  restored**), only the derivation test fails among the new ones; the hedge change reverted (**6
  lines removed**), only the hedge test fails; both reverted (20 removed, 2 restored),
  `replay_report.py` is then identical to `dde8b41`'s and exactly the two new tests fail beyond
  the baseline. Ten existing `test_replay_tooling.py` tests fail in the scratch copy with nothing
  reverted (they read the repository's docs tree and the export, which the copy does not hold);
  they fail identically in every label.
- Full suite on `lexchat_test_d`: **2137 passed** (2135 at `dde8b41` plus the two new tests).

## What I did NOT do

- I did not enrol the five hedged 6370 readings the hand-read lists among the drops on
  `wave4_b4_post` (r2 t4 "On the alternative reading ..."; r3 t3, t4, t5, t6 "On one reading
  ..."). They would count as hedged and move no verdict, but **r3 now PASSES by command because
  nothing on it is enrolled, not because its hedged readings are read as hedged**. Decision 2.
- I did not remove the two remaining `wave4_b2_post` 6370 over-counts (r1 t4, r3 t6, retrieval
  statements): not in this gap list.
- I did not write a pattern for `p32_6406` r1 t8 (the hand-read's "implicit affirm at most"; its
  main reading counts it none).
- I did not touch `FIX_PLAN.md`, `SESSION_LOG.md`, the tracker, CLAUDE.md, CHANGELOG, VERSION or
  memory, and did not push or merge.

## Decisions for the integrator or the user

1. **`hedges` is not byte-identical.** Gap 2 adds one interpretive hedge to `wave4_b4_post`, so
   its interp/1k column reads 3.2 where it read 3.1; every guard column and the `--list` output
   are identical over all 57 directories. Options: (a) accept, since the column counts
   `INTERP_HEDGE` and the gap is that it missed a hedge; (b) give `interpret` its own hedge
   lexicon so `hedges` never moves when the 6370 grading does. **Recommend (a)**: (b) splits one
   definition of a hedge in two for one sentence.
2. **6370 r3 passes by under-read.** Options: (a) leave it (the verdict equals the hand-read);
   (b) widen `scope_reading` to enrol the five hedged drops, measured first over every directory,
   so a future rep that states one of them firmly is caught. **Recommend (b), as a small grader
   item before the next after-column**, not mid-batch.
3. **`baseline` 6406 r2 t7 now reads deny.** Its sentence has the same form the `wave4_b4_post`
   hand-read reads as deny (r3 t7); batch 4 A read it only as "no affirm". Its change count (3)
   and verdict do not move. Options: keep the entry, or narrow it to the b4 sentence alone.
   **Recommend keep**: one reading for one sentence form.
4. **A second implicit-position entry** (`p32_6406` r2 t8, `wave4_b4_post`), on decision (ii)'s
   precedent. It moves positions only, not the change count. Keep or drop. **Recommend keep**,
   as (ii) did for its sibling; drop it if the user would rather leave implicit positions to the
   hand-read.
5. **The hand-read's gap 2 wording is wrong on one half**: "on the alternative reading" was
   already a hedge. Worth a one-line correction in the gitignored hand-read so the next session
   does not chase it.
