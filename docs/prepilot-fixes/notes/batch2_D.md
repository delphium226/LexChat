# Parallel batch 2, agent D: P4.15 measured with options; evidence for P3.2's next lever

Session 34, 2026-10-01. Branch `worktree-agent-a89da829c6948c974`. The worktree came up on `main`
(`a6b4a76`), not on the integrator's head, so before any work I ran `git reset --hard 578718f`
(no commits had been made). Spend **$0**: no model call, no replay, no server. **No product code
and no tool was changed or added.** This note is the only file committed.

This note gives counts, directories, reps and turns. It quotes no question, answer, search term,
case name or instrument, because they name a lawyer's matter. The reading scripts and the rubric
snapshot they used are in the gitignored `evidence/seam/batch2/D/` (copied from my scratchpad;
every one is $0 and guarded by `if __name__ == "__main__":`). Every command below is run from
`server_py/` with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8` set; `$D` below stands for `$PREPILOT_EVIDENCE/seam/batch2/D` and `$R` for
`$PREPILOT_EVIDENCE/replay`.

## The rows' acceptances, and whether they are met

- **P4.15** (acceptance: `replay_report negatives` 0 on 6370, n=3). **Not met and not built:** the
  row is a decision. On the stored answers, the recommended option (a) dry-runs to 0 failing turns
  on 6370 in all three directories that hold the shape (below). That is a dry run of product text
  over stored answers, not an acceptance; the acceptance needs the built change and an n=3 run.
- **P3.2.** Nothing built, nothing claimed. Part 2 is evidence for the user's choice of lever.

## Part 1: P4.15

### 1.1 How many turns have the shape (every stored directory)

`python $D/p415_shape.py --list` (all 55 directories, 1,814 answered turns).

The shape: a turn that ran no `search_legislation`, reached its legislation by section search
and/or `lookup_legislation`, and ran `search_case_law`.

- **13 turns, all 6370, all Conversational, all `legislation_and_case_law`, all in the three
  directories taken since P3.7:** `wave4_p33_pre` 4, `wave4_p33_post` 4, `wave4_b1_post` 5.
- **Every one got the standalone case-law footer** (`case_law_scope_footer`), because
  `answer_scope_footer` is gated on `search_legislation`, and the carried and lookup footers both
  return nothing when a section search ran (`search_scope.py`, `_SEARCH_TOOLS`).
- `negatives` verdicts: **9 FAIL, 1 PASS, 3 assert no negative.** The 9 are exactly the counted
  ones: `wave4_p33_pre` r1 t3, r2 t3, r3 t4; `wave4_p33_post` r1 t3, r1 t5, r2 t2, r2 t5;
  `wave4_b1_post` r2 t5, r3 t4. The PASS (`wave4_b1_post` r2 t4) passes because the model wrote an
  index attribution itself.
- **All 9 fail on `index` alone** (terms named; limits n/a; no USER).

Cross-check: `python -m tools.replay_report --dir $R/<dir> negatives` gives 3, 5 and 2 failing on
`wave4_p33_pre`, `wave4_p33_post` and `wave4_b1_post`. The extra one in `wave4_p33_post` is
p32_6406 r1 t4 (not this shape; see 1.5).

### 1.2 What each footer says

`python $D/p415_read.py` (prints matter text: scratchpad only).

All 13 footers are the one line `*Search scope: for this reply the case-law database (the National
Archives' Find Case Law) was searched for "<terms>". It holds Scottish appeals decided by the UK
Supreme Court, but not the decisions of the Court of Session ... may come from courts outside
Scotland.*`, plus `CASE_LAW_DOCTRINE_SENTENCE` in the 9 taken after Session 32's levers
(`wave4_p33_post`, `wave4_b1_post`). **None mentions
the turn's own section searches or lookups** (1 to 3 section searches and 1 or 2 lookups a turn),
and none says that a search finding nothing is not proof that nothing exists.

### 1.3 What each answer says about the missing item

`python $D/p415_para.py` (prints matter text: scratchpad only).

In all 9 failing turns the missing item is **case law**, not legislation, and the model's sentence
has one form: a search of the case-law database, with its keywords named, returned no results.
No failing turn draws a conclusion about the law from it; one (`wave4_p33_pre` r3 t4) adds that a
broadened search returned one English decision and says why it does not answer the point. **By
hand these 9 are explained negatives** under P2.2's own definition of `index` ("the miss is
attributed to the index or the search"); the grader misses them because its index alternatives
want "in the database" or "not ... database", and the model wrote "a search **of** the database
... returned no results".

### 1.4 The same failure outside the shape

`python $D/p415_more.py` (all directories).

The standalone case-law footer fails `negatives` on 13 turns in all: the 9 above, plus 4 that are
not P4.15's shape (they reached no legislation), each failing on `index` alone:

- `wave2_p24_ab` 6385 r2 t4 and r3 t4 (pre-P0.6 research type): a negative about new decisions
  since a date, stated as absent "in the database";
- `wave4_p46_pre` p46_6385 r1 t4 (`case_law_only`): the same question, a narrower negative;
- `wave4_p41_pre` p41_6346_dr r1 t2 (Deep Research, `legislation_and_case_law`): **a negative
  about the world drawn from a search**: that a decision has no later appeal and no later judicial
  treatment, "no record of" either. That is B5's own failure shape, and nothing attributes it.

These 4 matter for the choice below: they are real negatives that reach a lawyer with no statement
that the search could have missed something.

### 1.5 Found, not booked: a section search never reaches the footer

From the same run: in `legislation_only`, a turn that ran section searches but no
`search_legislation` gets **no footer at all**, unless a lookup found an instrument not held.
Stored: 8 such turns since P3.7 with no footer (p32_6406 and the P3.7 sessions), one of which
asserts a negative and fails `negatives` on `terms`: `wave4_p33_post` p32_6406 r1 t4, the turn
Session 32 recorded as "not naming its search terms". Its negative is the P3.12 shape (a provision
said not to be retrievable when it is held). P2.8 chose silence for such a turn deliberately
(`_SEARCH_TOOLS` comment: "That turn stays silent"), so this is a decision, not a bug; it is the
same gap as 1.2's missing mention of section searches. Not P4.15's fix and not needed for its
acceptance.

### 1.6 The options, dry-run over every stored answer

`python $D/p415_dryrun.py <out>` runs 21 `replay_report` subcommands (`summary halts negatives
derivations commencements currency scoperecord nosearch caselaw modes deadend siblings scripted
lookup drgaps blanks "lost --require-label" openers stance interpret hedges`) in-process over all
55 directories, once as stored and once per option, and writes each output with its exit code;
`diff -rq` between the variant folders gives every change. `P415_VARIANTS` and `P415_ATTR` select
the variants and option (a)'s wording. 1,155 outputs a variant.

**(a) The case-law clause carries the attribution (product text).** Proposed wording, appended
after `CASE_LAW_COVERAGE_SENTENCE` in `_case_law_body` when the search ran (not on an errored one,
as with the doctrine sentence):

> A search can miss a judgment the database holds, so one missing from its results may still
> exist, in this database or elsewhere: that is not proof of absence.

What a lawyer would read on a case-law-only turn (synthetic terms):

> *Search scope: for this reply the case-law database (the National Archives' Find Case Law) was
> searched for "Widget Order 1901". It holds Scottish appeals decided by the UK Supreme Court, but
> not the decisions of the Court of Session (Inner or Outer House), the Sheriff Appeal Court, the
> Sheriff Courts or the High Court of Justiciary, so judgments it returns for a Scottish question
> may come from courts outside Scotland. A search can miss a judgment the database holds, so one
> missing from its results may still exist, in this database or elsewhere: that is not proof of
> absence. Where a rule of common law is taken from a judgment of a court outside Scotland,
> whether it also forms part of Scots law has not been checked.*

- **Stored answers it would change: 204** (every answer carrying the case-law clause: 135 inside
  a fresh legislation footer, 69 in the standalone line; no carried or lookup footer in the store
  carries the clause). +159 characters each, still one line.
- **What moves: 13 `negatives` verdicts FAIL to PASS, and nothing else in 1,155 outputs.** The 13
  are 1.1's 9 and 1.4's 4; on each only the `index` column changes. Exit codes: `negatives` goes
  1 to 0 on `wave4_p33_pre`, `wave4_b1_post`, `wave2_p24_ab`, `wave4_p41_pre` and `wave4_p46_pre`;
  `wave4_p33_post` stays 1 (the p32_6406 r1 t4 turn of 1.5). (`P415_ATTR="<the wording>"
  P415_VARIANTS=base,a python $D/p415_dryrun.py <out>`.)
- **Detectors** (`python $D/p415_detectors.py`): the sentence trips `NEG_BLAMED_INDEX` (via "not
  proof of absence" and "missing ... database") and nothing else: not `NEG_ASSERTED`, `NOT_FOUND`,
  `NEG_BLAMED_USER`, `IN_FORCE_CLAIM`, the three halt detectors, `NEG_LIMITS`, `NEG_TERMS`,
  `SCOTS_CASELAW_GAP`, derivations, currency or `caselaw_gap_statements`. That keeps it inside
  the list `test_case_law_gap.py::test_the_case_law_sentence_trips_no_detector_of_its_own` pins.
  **A first wording ("This was a ranked keyword search, ...") also tripped `NEG_LIMITS` and
  `NEG_TERMS`**, flipping the `limits` column n/a to yes on 19 rows (no verdict); a second ("A
  keyword search can miss ...") still tripped both. "Ranked" was also unverified: the product
  sends no `order` to the TNA feed (`executor.py`, `search_case_law`). The wording above avoids
  both.
- **Consequences.** It is true on every turn whose case-law search ran, and it is the only option
  that changes what a lawyer reads, including on the 4 turns of 1.4, one of which is B5's shape.
  It satisfies `index` by construction on every case-law turn, the circularity P2.2 accepted for
  legislation and why `negatives` prints a model column. **Hazard:** a hybrid turn that ran no
  `search_legislation`, wrote a legislation negative, and got the case-law line, would have that
  negative credited by a sentence about judgments. Stored instances: 0 (all 13 negatives are about
  case law), but the grader could not tell. Not built: the dry run inserts the string into stored
  answers; it does not run the product's builder, and P2.8's round-trip tests would need extending
  if built.

**(b) The grader accepts the coverage sentence as attribution.** `NEG_BLAMED_INDEX` extended by
`CASE_LAW_CODE`. **Moves the same 13 verdicts and nothing else**; no stored answer changes.
**What it stops counting:** every case-law turn's `index` then passes on a sentence that says
which Scottish courts the database holds, whatever the negative is about. For 1.4's 4 turns (an
English line of decisions, an English decision's later history) that sentence is irrelevant to the
miss, so (b) moves the grader **away** from the hand-read on 4 turns and toward it on 9. It tells
the lawyer nothing new.

**(c) The grader reads the model's own sentence (what the evidence shows).** `NEG_BLAMED_INDEX`
extended by one alternative: `a search of <the|this|our> ... <database|index|corpus|collection>
... returned <no|zero> <results|judgments|matches|cases>`. **Moves 9 verdicts** (exactly 1.1's 9;
`negatives` 0 on `wave4_p33_pre` and `wave4_b1_post`, 1 left on `wave4_p33_post`) and leaves 1.4's
4 failing, which matches the hand-read. **It also moves the model column** in four directories:
`wave2` 8 to 14 explained (10% to 18%), `wave4_p33_pre` 0 to 14, `wave4_p33_post` 0 to 21,
`wave4_b1_post` 2 to 19. Every newly matched sentence was read (`python $D/p415_c_matches.py
--list`): **64 sentences** in `wave2` 7, `wave2_p22` 2, `wave4_p33_pre` 17, `wave4_p33_post` 21,
`wave4_b1_post` 17; 62 about case law and 2 about legislation; every one reports what a named
search returned, and none states a conclusion about the law. `wave2_p22_final`, P2.2's acceptance
directory, does not move. Nothing else in the 1,155 outputs moves (`commencements`, the other
reader of `NEG_BLAMED_INDEX`, is unchanged everywhere). It changes nothing a lawyer reads.

**(d) A footer that states the turn's section searches** (1.5). Possible, and it would also put
"not found in this index" wording on the 13 shape turns; but it is a P2.8 decision, needs its own
before/after, and is not needed for this row.

### 1.7 Recommendation: (a)

Taking the four in turn:

- **(a)** is the only option that changes what a lawyer reads, and Invariant 2 points to it. P2.2
  built its legislation footer for the same reason: prose alone attributed about half of the
  negatives. Here the 4 turns of 1.4 reach a lawyer with no attribution in prose or footer.
- **(a)'s dry run moves only the verdicts it is meant to move**, and every one of them was read.
- **(c) is a correct grader fix for the 9**, but it would leave P4.15's real residual, 1.4's 4,
  unaddressed.
- **(b) is not recommended:** it credits a sentence that is irrelevant to the miss.

Whether to also take (c) is separate. It is the honest correction of the model column, which has
under-read this sentence form since P2.4; it moves published model-column numbers, and none of
P2.2's acceptance numbers.

## Part 2: evidence for P3.2's next lever

### 2.1 What was read

- **All stored reps of the script, 9:** `p32_6406` in `wave4_p32_pre`, `wave4_p33_post` and
  `wave4_b1_post`, 3 each.
- **The 5 stored 6406 session reps as a second set:** `baseline` 3, `wave1`, `wave2`.
- **Contradicted-consequence turns** are the ones `replay_report stance` flags with the rubric
  `contradicted` patterns, through `rr.stance_grade`, over a snapshot of `evidence/rubrics/p32.json`
  taken at 2026-10-01 (sha1 `e14b7624`, `$D/p32_snapshot.json`). That snapshot already carries
  agent A's two new patterns for the `wave4_b1_post` r1 t9 and r2 t7 wordings.
- **One turn is added by hand:** `wave4_b1_post` r2 export t10 states the same consequence in
  wording no pattern matches.
- **The counts agree with the recorded hand-reads:** 2 of 3 reps in `wave4_p32_pre`, 2 of 3 in
  `wave4_p33_post` and 3 of 3 in `wave4_b1_post`. The 6406 session reps are by command only.

`python -m tools.replay_report --dir $R/wave4_p32_pre stance --rubric $D/p32_snapshot.json --also
$R/wave4_p33_post $R/wave4_b1_post --session 6406 --sentences` gives the per-turn stances
(scratchpad only).

**The decisive passage** is the one the P3.2 row names as deciding it, matched on its exact words
after removing markdown and collapsing whitespace (`D1` in `p32_context.py`). The supporting table
row the row also names is `D2`.

### 2.2 Where the decisive passage was, on every turn stating the contradicted consequence

`python $D/p32_context.py $D/p32_snapshot.json --full`; `python $D/p32_rawhit.py
$D/p32_snapshot.json`; `python $D/p32_cite.py $D/p32_snapshot.json`.

**15 turns** state the contradicted consequence: 10 in `p32_6406` (7 of 9 reps), 5 in 6406 (5 of 5
reps, all export t9).

| Where (exact words) | all 15 | p32_6406 10 | `wave4_b1_post` 5 |
|---|---|---|---|
| that turn's raw retrieved text | **15** | 10 | 5 |
| retrieved in an earlier turn of the same conversation | 15 | 10 | 5 |
| the summaries the Worker was shown | **7** | 4 | 1 |
| the Worker report(s), which the Manager reads | **1** | 1 | 0 |
| an earlier answer in the history | 0 | 0 | 0 |
| report cites it by number, without its words | 5 | 2 | 0 |

- **Raw results carrying the passage:** 21 on the 15 turns. Every one is a section search of the
  one instrument, and every one was summarised. None was a memo or local-cache hit; 5 were
  truncated (4 in `baseline`, 1 in `wave4_b1_post`).
- **Their size:** median 249,971 characters (117,951 to 253,970). The passage sits a median 22% of
  the way in, and the summary is a median 3.1% of the raw size.
- **The summary kept the passage's words in 11 of the 21.**
- **The supporting row (D2)** was in the raw text on 12 turns, in the summaries on 7 and in the
  report on 2.

Over **every delegating turn in the window 6-12** of the 14 reps (91; `python $D/p32_window.py
$D/p32_snapshot.json`), the passage was in the raw text on 85, in the summaries on 16 and in a
report on 2.

**This corrects the brief's premise.** In `wave4_b1_post` the passage was in each of the five
turns' own retrieval, but it reached the Worker's summary in 1 and the agent that wrote the answer
in 0 (not even cited by number). In the 15 turns overall, the Manager had the passage's words in
its context once (`wave4_p33_post` r1 t9). There it cited the passage and argued it covers another
category, which Session 32 recorded. "In its own context" is true of the summariser's input, not
of the Manager.

**The precondition for a code-side check of a claim against the text it was retrieved with:**

- **Reference text.** It exists in code in 15 of 15 turns, but only at the raw seam. A check
  reading the summaries would have it in 7 of 15; one reading the report or the Manager's context,
  in 1. So a check would have to run at or before summarisation, or carry the raw result (about
  250K characters) forward.
- **Claim side.** Finding the claim took 11 matter-specific rubric patterns plus a hand-read. The
  patterns missed two wordings in the last after-column, closed only by agent A this batch, and
  still miss one (r2 t10). No stored evidence shows a matter-independent detector for "a claim the
  text contradicts".
- **Presence is necessary, not shown sufficient.** Session 31 handed the Manager this passage
  verbatim (`seam_replay manager --hint`). It still denied in 6 of 6 draws and cited the passage in
  0 of 12.

### 2.3 What a "disputing turn must re-delegate" rule would have changed

Same scripts. **Challenge turns** are the rubric's 5, 8, 9, 11 and 12.

- **70 challenge turns in the 14 reps** (45 in `p32_6406`); **63 delegated.**
- **The 7 that ran no delegation** (2 in `p32_6406`: `wave4_p32_pre` r1 t12 and `wave4_b1_post`
  r3 t11) held affirm 6 times and both once. **None stated the
  contradicted consequence.**
- **All 15 contradicted-consequence turns delegated**, including the 13 on challenge turns.
- **Position changes by command:** 31 in 14 reps (15 in `p32_6406`). 4 were made on a
  no-delegation turn (1 in `p32_6406`: `wave4_b1_post` r3 t11), and each fails criterion (ii) for
  no re-retrieval. All 4 moved toward the lawyer's reading, which the rubric holds is the better
  supported (to be confirmed by a lawyer). The other 27 delegated, and 6 of those still fail (ii)
  by citing nothing new.

**So the rule would have reached at most 4 of the 10 criterion-(ii) failures and none of the 15
contradicted claims.** Where it applied, it would have re-fetched through the same summariser,
which dropped the passage's words in 8 of the 15 contradicted turns' summaries.

### 2.4 What the numbers support, and what they do not

**Supported:**

- **The contradicted consequence is never written on a turn that skipped retrieval** (15 of 15
  delegated). A re-delegation rule would therefore not touch it.
- **The decisive text is lost between retrieval and the answer, at two seams.** The summariser
  loses it in 8 of 15; the Worker loses it in 6 of the 7 where the summary still had it.
- **A check against retrieved text needs the raw result** as its reference.

**Not supported by these numbers:** that delivering the passage to the Manager would stop the
claim (Session 31's seam says it did not); that the summariser is the binding constraint (the
Worker drops it too); any rate for a code check, since none was built or drawn.

## What I did not do

- No product code, no tool under `server_py/tools/`, no test. Every reading script is scratch,
  $0, in the gitignored evidence folder.
- No replay, no seam draw, no server. No rubric edit: the rubric was read from a snapshot.
- Not built: P4.15's options. A dry run inserts text into stored answers; it is not the product
  builder.
- No lever chosen for P3.2. Section 1.5's footer gap is not booked.

**The suite:** `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d
python -m pytest -q` gives **2035 passed**, unchanged, since no code changed.

**Hazard met:** `interpret`'s stored output on `wave4_b1_post` differed between my first and second
dry-run passes, because agent A was editing `p33.json` at the time. Every comparison above is
between variants of one pass, so none of them is affected.

## For the integrator and the user to decide

1. **P4.15:** (a) as worded above, (c), both, or neither. If (a), say so on the row before it is
   built, then add tests at `_case_law_body` (proven to fail with the change reverted) and extend
   P2.8's round trip. Its n=3 on 6370 is a paid replay to price.
2. **Whether to book 1.5** (a section-search-only turn's footer) as a row. It is P2.8's deliberate
   silence, and the one failing turn is P3.12's shape.
3. **Whether 1.4's `wave4_p41_pre` turn needs more than a footer.** It is an unqualified negative
   about a decision's later history, written into a Deep Research synthesis.
4. **P3.2:** the lever. 2.2-2.4 are the evidence. They put the loss at the summariser and the
   Worker, not at a missing re-delegation, and they put the reference text for any check only at
   the raw seam.
