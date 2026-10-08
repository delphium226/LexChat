# Parallel batch 11, agent A: P3.12, why rep 1's Worker wrote one sub-paragraph, and a candidate lever ($0)

**Branch:** `worktree-agent-a495a86849083d460`. **Base:** `<INTEGRATOR_HEAD>` = `024e396`. The worktree came up
on `main` (`a6b4a76`) with no commits, so I ran `git reset --hard 024e396` before anything else. No other
commit reached my branch while I worked.

**Commits:**

- `d55d0e0` fix(prepilot): P3.12 candidate lever: the MATCHED tail names its paragraphs (product + tests);
- this note.

**Spend:** $0. No model call, no seam draw, no replay, no server, no live call to any host. The two seam draws
of rep 1's payload that this note relies on were the integrator's (relayed to me by SendMessage). Every stored
run read here ran on the pinned `google/gemini-3.1-pro-preview` and was summarised at the 8,000-character
fallback; no number comes from `glm-5.2:cloud`.

**Tests:** full suite **2838 passed** on `lexchat_test_a` (base 2833, plus 5). `plan_status` 81 rows, 58 ticked;
`plan_lint` 0 errors, 0 warnings: unchanged, I edited nothing they read.

**Scratch:** my worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch11/A/` (`git check-ignore -v`:
`.gitignore:113`), copied at the end to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch11/A/`.
Commands below run from that folder unless they say `server_py/`, with `PYTHONIOENCODING=utf-8` and
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`. Files that print brief or query text
(`show_payloads.txt`, `briefs_6335.txt`, `payloads/`) are scratch only.

**Built shape against the brief.** As briefed: one candidate lever, Worker-facing wording only through
`fetched_block`'s MATCHED tail. One addition the brief did not name: `schedule_units.matched_numbers(unit,
text, query)`, the paragraph numbers the MATCHED block cuts. `matched_pieces` now takes its own cuts from it,
and the route passes it to `fetched_block(..., matched=...)`, so the numbers the tail names and the paragraphs
the block carries come from one function. `fetched_block` gains one optional keyword, `matched` (default `()`,
which keeps batch 10's wording).

---

## 1. Measured first: rep 1's payload against Session 41 r2's with the MATCHED block

**Commands** (from `server_py/`):

```
python -m tools.seam_replay worker --run $PREPILOT_EVIDENCE/replay/wave4_b10_sweep/6335_rep1.json --turn 7 --delegation 1 --dry-run
python -m tools.seam_replay worker --run $PREPILOT_EVIDENCE/seam/batch10/A/seam_6335_r2_matched.json --turn 7 --delegation 1 --dry-run
python <scratch>/compare_payloads.py      # the same builder (tools.seam_replay.worker_messages), per-part sizes
python <scratch>/show_payloads.py         # the matter-bearing parts (scratch only)
python <scratch>/rounds.py                # the live round structure of both delegations
```

Rep 1: 8 messages, 43,741 characters. r2 with the MATCHED block: 8 messages, 46,674.

| Part | Rep 1 (`wave4_b10_sweep`, NOT DELIVERED 0 of 2 on the seam) | r2 + MATCHED (`seam_6335_r2_matched.json`, DELIVERED 2 of 2) | Could it change what the Worker writes? |
|---|---|---|---|
| Chat mode, research type | Conversational, legislation and case law | the same | no |
| System prompt | the quick-lookup Worker prompt, 11,762 characters | **identical** (same sha1): `prompts.py` is unchanged between both runs' heads (`3daf7a6`, `8b4469c`) and `024e396`, and the seam builds it with today's date for both | no (on the seam) |
| Date line | the seam's: today, for both. Live: 2026-10-08 against 2026-10-07 | the same on the seam | not on the seam |
| Brief | 250 characters. **Broad**: the turn's general question about the Schedule, **plus "for Scotland"**, plus case-law keywords. Names no paragraph and no limb | 313 characters. The same, but **narrowed to the restrictions on proceedings and enforcement**, and no jurisdiction | **yes**: the narrow brief names what paragraphs 42 and 43 are about; the jurisdiction matches the two Scots-specific limbs rep 1's draws wrote (43(5) and 43(6)) |
| Section query | the Schedule plus one word | the Schedule plus five words (restrictions, proceedings, enforcement) | yes, through what the route matched (next row) and the search rows' summary |
| The block | MATCHED: heading list, then paragraphs 42, 43 and 44, each cut clean; 7,853 characters | MATCHED: heading list, then 6, 15 and 23 as labelled spans, and 42, 43 and 44 clean; 12,810 characters | yes in principle; but the six-paragraph block is the one that delivered, so more text did not hurt |
| Block position | last in result 3, after the summarised search rows, the section outline and the SEARCH SCOPE line (28 characters after it) | the same position, the same order | **no**: identical |
| Result 3 before the block | a summary of the Act's other sections for the broad query (it mentions the Schedule's paragraphs only as cross-references) | a summary of the same sections for the narrow query | weakly |
| Result 1 (instrument search) | 6,844 characters, with descriptions (P3.6) | 4,433, without | no |
| Result 2 (case-law search) | a summary of the list, ordered **most relevant first** (P3.22) | ordered **newest first** | yes, through which judgment was read (next row) |
| Result 4 (judgment read) | an appellate judgment applying paragraph 43, whose summary names **paragraph 43(6) as the provision** | a judgment on another paragraph of the Schedule | **yes**: rep 1's report is 43(6) and this judgment; the judgment summary hands the Worker a ready one-provision framing |
| Rounds | live: two rounds (tools 1-2, then 3-4), then the write-up. The seam flattens all four into one round, for both | the same | not on the seam |
| Case-law results present | yes | yes | no difference |

**What the integrator's draws showed** (relayed; command `seam_replay worker --run <rep 1> --turn 7 --delegation
1 --reps 1 --print`, at `024e396`): draw 1 $0.0444, SHALLOW by `depth`, by hand not delivered (43(5), 43(6), then
the judgment); draw 2 $0.0421, PARTIAL by `depth`, by hand not delivered (42(2)-(4), 43(5), 43(6), the judgment;
no 43 security limb, no 44). Both one prose paragraph, quick-lookup style; neither says anything was not
retrieved. So the payload is the cause, not the draw.

**Reading.** The prompt is identical, so the cause is in the brief and the tool results. The quick-lookup
prompt asks for "2-5 sentences of concise prose" and "Do not broaden the scope". Under a broad brief that adds
a jurisdiction, with a judgment summary that names one sub-paragraph as the provision, the Worker wrote the
Scots-specific limbs and the judgment, inside its sentence budget. Under a brief that names the restrictions
limb, the same prompt and the same verbatim paragraphs delivered. The block's position does not differ.
**Nothing in the block tells the Worker which paragraphs it carries or that each matters**; the tail says only
"each paragraph whose heading shares a word with this search's query". That is the part of the payload the
product controls at this seam, so the lever goes there.

**Every stored turn-7 brief** (`python <scratch>/briefs_6335.py` from `server_py/`, `briefs_6335.txt`; 15
delegations in 14 run files over all 64 directories; brief and query text scratch only):

| Directory, rep, delegation | Mode | Names the paragraphs | Narrows to a limb | Names a jurisdiction | Route fired / MATCHED | Report by `depth` | Answer by `depth` |
|---|---|---|---|---|---|---|---|
| `baseline` r1 | research | no | yes | no | no / no | MISSED | SHALLOW |
| `wave0_conv` r1 | conversational | no | no | no | no / no | SHALLOW | PARTIAL |
| `wave1` r1, d1 of 2 | research | yes (e.g.) | yes | no | no / no | MISSED | SHALLOW |
| `wave1` r1, d2 of 2 | research | yes | yes | no | no / no | MISSED | SHALLOW |
| `wave2` r1 | research | no | yes | no | no / no | MISSED | MISSED |
| `wave3_p38_pre` r1 | research | no | no (asks about another Part's interaction) | no | no / no | PARTIAL | PARTIAL |
| `wave3_p38_pre` r2 | research | no | yes | no | no / no | SHALLOW | SHALLOW |
| `wave3_p38_pre` r3 | research | no | no | no | no / no | SHALLOW | SHALLOW |
| `wave4_b8_sweep` r1 | conversational | no | no | no | yes / no | PARTIAL | PARTIAL |
| `wave4_b8_sweep` r2 | conversational | no | no | no | yes / no | PARTIAL | PARTIAL |
| `wave4_b8_sweep` r3 | conversational | yes (e.g.) | no | no | yes / no | PARTIAL | PARTIAL |
| `wave4_b9_sweep1` r1 | conversational | no | no | no | yes / no | PARTIAL | PARTIAL |
| `wave4_b9_sweep1` r2 | conversational | no | **yes** | no | yes / no | SHALLOW | SHALLOW |
| `wave4_b9_sweep1` r3 | conversational | no | no | no | yes / no | PARTIAL | PARTIAL |
| **`wave4_b10_sweep` r1** | conversational | no | no | **yes, the only one** | yes / **yes** | SHALLOW | SHALLOW |

- "Narrows to a limb" is a regex over the brief (restriction, legal process or proceedings, enforcement,
  security, winding, interim), read by hand; "names the paragraphs" counts a paragraph number in the brief.
- The live route ran in the 7 conversational delegations of the three latest sweeps; it fired MATCHED only in
  rep 1 (the lever was built after the others ran).
- **5 of the 7 conversational briefs are broad** (no limb, no paragraph), 1 narrows to the restrictions limb
  (r2, the payload that delivered on the seam once given the MATCHED block), 1 names the paragraphs by example.
  So a broad brief is the usual shape in the recorded mode, and a lever that depends on the Manager narrowing
  the brief would not reach most runs. Rep 1 is the only brief that names a jurisdiction.

---

## 2. The candidate lever (`d55d0e0`)

`server_py/src/utils/schedule_units.py` and `server_py/src/agent/agent_shared.py`; nothing else.

- `matched_numbers(unit, text, query)`: `heading_matches(paragraph_headings(text), query, unit)`, `[]` on any
  failure. `matched_pieces` now iterates it (equivalent to before).
- `fetched_block(..., matched=())`: in the MATCHED tail, the clause "each paragraph whose heading shares a word
  with this search's query, cut from the retrieved text and labelled." is replaced by a clause naming the
  paragraphs and one sentence asking that each that bears on the question be reported on its own, from its own
  words. The numbers are cleaned (`_clean`, at most 8 characters; an empty one dropped). With no numbers, the
  batch 10 clause is kept unchanged.
- `schedule_route_block`: on the MATCHED path, `numbers = matched_numbers(unit, text, args.get("query"))`
  (the section search's own query, the same input `matched_pieces` used), passed as `matched=`.
- Unchanged: the lead, the heading list, the paragraph labels, the cuts, the bound, the budget check, the
  SUMMARY, CUT and WHOLE tails, the block's position in the tool result, and the "To read another headed
  paragraph" sentence.

### 2.1 The exact wording, for the user (every variant)

`<U>` is the unit ("Schedule 5", "the Schedule"); `<U'>` is `<U>` with its first letter capitalised; `<N>` is the
unit's size; `<p>` one number; `<list>` the numbers joined "a, b and c". The lead before it and any reason
after it are unchanged.

**MATCHED tail, several paragraphs (new):**

> ` <U'> runs to <N> characters, longer than one result hands over whole, so below are its paragraph
> headings, in order, and then paragraphs <list> of it, whose headings share a word with this search's
> query, each cut from the retrieved text and labelled. Each of those paragraphs that bears on the question
> gets a sentence or bullet of its own in the report: cite it by its number and say what it provides, taken
> from its words below rather than from a summary or a judgment that mentions it. To read another headed
> paragraph in its own words, name <U> and its number from the list below in a section search: code cuts it
> out the same way.`

**MATCHED tail, one paragraph (new):**

> ` <U'> runs to <N> characters, longer than one result hands over whole, so below are its paragraph
> headings, in order, and then paragraph <p> of it, whose heading shares a word with this search's query,
> cut from the retrieved text and labelled. If that paragraph bears on the question, it gets a sentence or
> bullet of its own in the report: cite it by its number and say what it provides, taken from its words below
> rather than from a summary or a judgment that mentions it. To read another headed paragraph in its own
> words, name <U> and its number from the list below in a section search: code cuts it out the same way.`

**MATCHED tail, no numbers known** (unreachable from the route, kept as the fail-soft): batch 10's wording,
byte-equal.

Rendered from the BUILT code for "Schedule 5" and for "the Schedule", with 0, 1, 2 and 6 numbers, and read: it
reads in all eight ("The Schedule runs to ... then paragraphs 5 and 6 of it, ..."). On P3.12's turn the
several-paragraph tail reads "... and then paragraphs 42, 43 and 44 of it, whose headings share a word ...".

**Why each part.** Naming the paragraphs tells the Worker what the block carries before it reaches the cuts
(the heading list alone is 2,873 characters of other headings). "A sentence or bullet of its own" answers the
quick-lookup prompt's 2-5 sentence budget, which allows "a short bullet list for multiple points", without
touching the prompt. "That bears on the question" keeps the prompt's "Do not broaden the scope", so r2's three
spans matched on a common word (restrictions on the power to appoint) need not be reported. "Rather than from a
summary or a judgment that mentions it" answers rep 1's judgment summary, which named one sub-paragraph as the
provision.

### 2.2 Screens (built code; all pass)

- **`b11_screenA.py`** (the integrator's `b10_screenA.py` copied, its path repointed to my scratch, the MATCHED
  blocks given the built numbers and also one, six and no numbers; run from `server_py/`, output
  `b11_screenA.txt`): **52 texts, 0 trips, 0 flagged.** It runs `b9_screen.screen` (every answer-reading
  regex: `NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `NEG_LIMITS`, `NEG_TERMS`, the
  three halt detectors, `IN_FORCE_CLAIM`, `OPENER_VOCAB`, `SCOTS_CASELAW_GAP`, `_CUR_DISCLOSED`,
  `NEGATIVE_EXPLAINED`, `SCHED_LIMIT`, `SCHED_INDEX_NEG`, plus `derivation_claims`, `_CMC_*`,
  `_currency_asserted`, `negcurrency_claim` and `sched_clause_class` per sentence, "ranked", the bracket and
  strip checks), and `sched_unit_clauses` per clause, `_P312_NOT_DELIVERED`, and "not ... retriev", for
  labelled and unlabelled units, both sources, with and without the sole-schedule reason.
- **A first draft tripped `OPENER_VOCAB`**: "is a point of its own in the report" (the word "point"), caught by
  `test_footer_trips_no_detector`. Reworded to "gets a sentence or bullet of its own in the report".
- **`test_footer_trips_no_detector`** (`tests/test_search_scope.py`): the variant list gains the one- and
  six-number tails, labelled and unlabelled, with and without a reason, from both sources (16 texts).
- **`test_every_matched_variant_reads_as_held_to_the_schedule_grader`** (`tests/test_schedules.py`): gains the
  same, read by `sched_unit_clauses`, `SCHED_LIMIT`, `_P312_NOT_DELIVERED` and "not ... retriev".
- **P4.6's `_scripted_counts`** on the four tails (whole block and header): 0 in every class.
- No new text contains "not", a square bracket, "ranked" or "cut short".
- No grader parses the MATCHED tail's words (`grep` for "shares a word", "longer than one result" and "code
  cuts it out" over `server_py/tools/` and `route_trace.py`: none). `route_trace.py` on the new payload prints
  the heading-list label and the three paragraph labels as before.

### 2.3 Other code texts about the same instrument (lessons)

- **The SEARCH SCOPE line** on the same result ("a provision that does not appear here may still be in it")
  and **P4.17's** line: unchanged, and consistent (the block says the paragraphs are here).
- **P3.1's cap** and **A2's** texts: unchanged; the last sentence of the tail, which invites a further search,
  is unchanged.
- **The summarised search rows above the block** (other provisions, summarised): the new sentence asks that a
  matched paragraph's content come from its own words rather than from a summary; it says nothing about the
  summarised rows' own provisions, so it does not contradict them.
- **The case-law blocks** (the SEARCH SCOPE and MANDATORY NEXT STEP lines on the search, the judgment's
  summary): the new sentence does not tell the Worker to drop the judgment, only not to take a paragraph's
  content from it. Whether the Worker still reports the judgment is one thing to read in the draws.
- **The SUMMARY tails** ("Cite <U> for what the summary says") are on another path; a unit gets one block,
  so a Worker never reads both tails about one unit.

---

## 3. Dry run with the BUILT code (both trees)

**Commands:**

```
git archive 024e396 server_py/src | tar -x -C prev       # the base tree (deleted at the end; rebuild with this line)
python mk_dryrun.py                                       # dryrun_b11.py = batch 10 A's dryrun_b10.py + DRYRUN_EXCLUDE
DRYRUN_WT=<scratch>/prev/server_py DRYRUN_OUT=dry_prev.json python dryrun_b11.py
DRYRUN_WT=<worktree>/server_py     DRYRUN_OUT=dry_new.json  python dryrun_b11.py
python compare_b11.py > compare_b11.txt
```

`dryrun_b11.py` asserts that every module came from the tree it was pointed at. It globs **all 64** replay
directories; `compare_b11.py` reports the 63 batch 10 A measured and the 64th (`wave4_b10_sweep`) apart.

**Inputs:** 5,568 stored section searches; the route fires on **265** calls (264 in the 63 directories, as
batch 10 A found, plus rep 1's turn 7), plus 56 memo hits. Summariser calls: **61 on both trees** (nothing moves
to or from the summary).

| Change | 63 directories | `wave4_b10_sweep` |
|---|---|---|
| unchanged | 248 | 0 |
| **MATCHED tail only** (the block equals the base block with the batch 10 clause replaced by the built text for the paragraphs that block carries; asserted byte for byte) | **16** | **1** |
| anything else | **0** (asserted) | 0 |

- **All 17 moved blocks are P3.12's turn 7** (every MATCHED block there is): `baseline` (2), `wave0_conv`,
  `wave1`, `wave2` (3), `wave3_p38_pre` (4, one with six paragraphs), `wave4_b8_sweep` (2), `wave4_b9_sweep1`
  (3, one with six), `wave4_b10_sweep` (1). Every call's key, mode and named numbers are in `compare_b11.txt`.
- **Three-paragraph block: 7,883 to 8,143 characters (+260); six-paragraph block: 12,840 to 13,111 (+271).**
  The bound is on the cut text (unchanged), so nothing moves to the summary; the three-paragraph block now
  passes 8,000 characters as a whole, which no rule reads.
- No other MATCHED-shaped block exists in the stored calls.

### 3.1 Forms no stored run contains, tested on synthetic input

Each is a test in `tests/test_schedules.py` ("batch 11 A" part), on "Widget"-style text:

- **one matched paragraph** (no stored MATCHED call has one): the singular tail, exact text, through the route;
- **an unlabelled unit** ("the Schedule") with one and with two numbers: "The Schedule runs to", "paragraph 5 of
  it", "name the Schedule";
- **a span paragraph named by its heading number** (also stored, in two calls): "paragraphs 1, 5 and 6", with
  the span label still saying it runs through 1 to 2;
- **numbers missing** (`()`, `None`, `("",)`, `(" ",)`): batch 10's tail, byte-equal, and no ask sentence;
- **numbers that need cleaning** (a bracket, whitespace, an empty one, one over 8 characters): one `[` and one
  `]` in the header, "paragraphs 4), 5 A and 12345678";
- **the text fallback** and **the sole-schedule reason**: in the screen and the detector test variants;
- **`matched_numbers` equals `matched_pieces`' own cuts** for four queries, `[]` where nothing matches, `[]` on a
  malformed unit.

A lettered number ("6A") reaches the tail through the same `_and_join`; it is covered by the existing lettered
test's route but not asserted in the tail.

---

## 4. Tests

`tests/test_schedules.py`: 5 new functions (`test_the_matched_tail_names_one_paragraph_in_the_singular`,
`..._names_the_paragraphs_of_a_span_by_their_heading`, `test_matched_numbers_are_matched_pieces_own_paragraphs`,
`test_the_matched_tail_without_numbers_keeps_batch_10_wording`, `test_the_matched_tail_cleans_the_numbers_it_names`);
`_MATCHED_TAIL` updated to the built text (used by the route test and the `run_worker_tool` seam test, which pins
the section search's query, not the research question, as the source of the numbers); the unlabelled-wording
test and the grader-reading test extended. `tests/test_search_scope.py`: the screen variants extended.

**Revert:** restoring `schedule_units.py` and `agent_shared.py` to `024e396` on a scratch copy removes **46
lines** (41 + 5); **10 tests fail**.

**Single-site mutants:** `python spec_b11.py`, then `python mutants.py spec_b11.json` (`mutants_b11.txt`; batch
10 A's runner, copied). Each runs `test_schedules.py`, `test_search_scope.py`, `test_replay_schedules.py` and
`test_section_budget.py` on a scratch copy (two `test_replay_schedules` tests deselected there, as in batch 10:
they read `evidence/scripts/` relative to the tree). **13 of 13 caught**; the control passes (322).

| # | Mutant | Fails |
|---|---|---|
| b2 | the route passes no numbers | 4 |
| b3 | the route takes the numbers from the research question, not the section query | 4 |
| b4 | the empty-number filter dropped (guard) | 2 |
| b5 | the numbers not cleaned (cleaning step) | 1 |
| b6 | the numbers not capped at 8 characters (length threshold) | 1 |
| b7 | `None` not guarded (emptiness) | 1 |
| b8 | no numbers takes the named path (emptiness guard) | 1 |
| b9 | the singular branch dropped | 2 |
| b10 | the plural ask sentence dropped | 2 |
| b11 | the singular ask sentence dropped | 1 |
| b12 | `matched_numbers` not fail-soft | 1 |
| b13 | `matched_numbers` ignores distinctiveness | 16 |

**Full suite:** **2838 passed** on `lexchat_test_a` with `TEST_DATABASE_URL` set (`pytest_full.txt`).

---

## 5. Seam payloads for the integrator's draw (not drawn)

`python make_seam_b11.py` writes three copies. In each, exactly one field of turn 7, delegation 0 differs from
its source (asserted after re-serialising), and the replaced block equals the base tree's dry-run block for that
call (asserted), so the substitution is exactly the lever's change.

| File | Source | What differs | `seam_replay --dry-run` |
|---|---|---|---|
| **`seam_b11_rep1_named.json`** | `replay/wave4_b10_sweep/6335_rep1.json` | tool 2's block: the built block (the tail names 42, 43 and 44); final_result 18,263 to 18,523 | 8 messages, 44,001 |
| **`seam_b11_r2_named.json`** | batch 10 A's `seam_6335_r2_matched.json` | tool 2's block: the built block for that call (names six); 23,824 to 24,095 | 8 messages, 46,945 |
| `seam_b11_rep1_r2brief.json` (diagnostic, optional) | rep 1 | the delegation's brief only, replaced by r2's narrow brief; no lever | 8 messages, 43,804 |

**Commands for the integrator** (from `server_py/`, one draw each, priced first: about $0.04-0.06 a draw on
these payloads, up to about $2.30 a runaway, since the default worker seam is uncapped and retried):

```
python -m tools.seam_replay worker --run <scratch>/seam_b11_rep1_named.json --turn 7 --delegation 1 --reps 1 --print --out <scratchpad>
python -m tools.seam_replay worker --run <scratch>/seam_b11_r2_named.json   --turn 7 --delegation 1 --reps 1 --print --out <scratchpad>
python -m tools.seam_replay worker --run <scratch>/seam_b11_rep1_r2brief.json --turn 7 --delegation 1 --reps 1 --print --out <scratchpad>   # optional
```

**What to read in each draw:** whether 42, 43 and 44 are each reported with their facts (`depth` plus the hand
read, as in Session 42); for rep 1, whether 43's security limb and paragraph 44 now appear;
for r2, that it still delivers and whether it now writes about the three common-word spans (6, 15, 23), which
would be scope noise; whether the judgment is still reported; whether the report outgrows quick-lookup shape;
and that no sentence calls anything not retrieved. The diagnostic draw tells whether the brief alone flips rep
1's payload; it is not needed to judge the lever.

---

## 6. What I did NOT do

- No model call, seam draw, replay, server or live call; the draws are the integrator's.
- I did not change the quick-lookup Worker prompt, the Manager's brief, the paragraph-named CUT path, the
  SUMMARY tails, the block's position, the bound, the budget check or P3.1's cap.
- I did not edit `replay_report.py`, FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md, a rubric, the tracker or a
  memory file. I did not push or merge.
- I did not test the research-mode Worker's response on the seam (the recorded research-mode turn-7 runs
  predate the route); the dry run shows its blocks move only in the tail.

---

## 7. Decisions for the user

1. **The candidate wording (section 2.1).** Worker-facing; a Worker can echo it.
   1. **(Recommended) Approve as built, conditional on the integrator's draws**: rep 1's named payload delivers
      42-44 with their facts, and r2's still delivers without scope noise. It passes every detector, and only
      P3.12's 17 stored blocks move.
   2. **Approve without "rather than from a summary or a judgment that mentions it."** Choose this if the draws
      show the Worker dropping the judgment; the naming and "a sentence or bullet of its own" remain.
   3. **Name the paragraphs only** (keep batch 10's sentence otherwise, no ask sentence). The smallest change,
      and the weakest: it does not answer the 2-5 sentence budget, which is the likeliest cause of a one-limb
      report. It would need its own build and screen.
2. **What to draw before any paid sweep** (the integrator's choice; priced at the runaway case).
   1. **(Recommended) `seam_b11_rep1_named.json` and `seam_b11_r2_named.json`, one draw each**, then decide;
      draw a second of rep 1's if the first delivers, since one draw is one sample at temperature 0.
   2. **The two plus the diagnostic brief swap** (one more draw, about $0.05): separates the brief from the
      block on rep 1's payload, which tells whether a Manager-side lever (a narrower brief) is also worth
      measuring.
   3. **Go straight to 6335 n=3** once the wording is approved.
3. **If the named payload still does not deliver on the seam.**
   1. **(Recommended) Measure the brief swap's draw before building more**: if the narrow brief alone delivers,
      the next lever is on the Manager's brief or the prompt's concision rule, not the block.
   2. **Move the block ahead of the summarised search rows** in the tool result (the other lever the brief
      named). The comparison above shows its position is identical in the delivering and the failing payload,
      so I would not expect it to help.

---

**Data handling.** The staged diff and this note were checked with the integrator's `matter_grep.py` (copied;
28 matter words, 0 hits) and a Python check for session numbers, instrument ids and matter words; the note
names no question, brief, search term, case name or instrument id from a session (it cites P3.12's row).
