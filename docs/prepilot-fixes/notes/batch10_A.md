# Parallel batch 10, agent A: P3.12's next lever, measured then built ($0, no external call)

**Branch:** `worktree-agent-a894fa9c2e5a24a18`. **Base:** `<INTEGRATOR_HEAD>` = `7c3c6ac`. The worktree
came up on `main` (`a6b4a76`) with no commits, so I ran `git reset --hard 7c3c6ac` before anything else.
No other commit reached my branch while I worked.

**Commits:**

- `1eed90d` fix(prepilot): P3.12's next lever: a large schedule named alone goes as headings and matched
  paragraphs;
- `a08acc9` refactor(prepilot): three redundant guards dropped, two tests added;
- `cdbc617` test(prepilot): a lettered paragraph's heading; an equivalent guard dropped;
- this note.

**Spend:** $0. No model call, no live call to any host, no server, no replay, no seam draw. Every LEX
response used below is one of batch 7 B's saved live payloads, served through an httpx `MockTransport`.
Every stored run read here ran on the pinned `google/gemini-3.1-pro-preview`, and was summarised at the
8,000-character fallback; no number comes from `glm-5.2:cloud`.

**Tests:** full suite **2803 passed** on `lexchat_test_a`, outbound HTTP pointed at a closed port (base
2783, plus 20). `plan_status` 58 of 79 and `plan_lint` 0 errors, 0 warnings: unchanged, I edited nothing
they read.

**Scratch:** my worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch10/A/` (`git check-ignore -v`:
`.gitignore:113`), copied at the end to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch10/A/`.
Every command below runs from that folder unless it says `server_py/`, with `PYTHONIOENCODING=utf-8`.

**Built shape against the brief.** As briefed, with four choices the brief left to me, each in a decision
below: the bound is `max(threshold, 12,000)` on the cut text; a query word is "distinctive" when it is in at
most three of the unit's headings; the words matched are the section search's own query, not the research
question; and the fallback is today's summary alone, without the heading list. One addition: a summarised
CUT (named paragraphs whose cuts exceed the threshold) now says it is the cut that was summarised. Before,
it used the whole-unit wording.

---

## 1. Measured first (before any product change)

**Command:** `python measure_a.py [--detail]` (`measure_a.txt`; `measure_a_detail.txt` prints queries, so it
is scratch only). This is batch 8 A's `dryrun_p312.py` pattern, repointed to my worktree and asserted.

- Every stored `search_legislation_sections` call in all **63** replay directories (none excluded,
  `wave4_b8_sweep` and `wave4_b9_sweep1` included) goes through the route as `run_worker_tool` passes it.
- Provision lists come from batch 7 B's saved lookups. The summariser is stubbed and records its input.
  The threshold is 8,000.
- The context budget is modelled from each delegation's earlier tool results (limit 250,000).
- A prototype of the lever is then run on every input that reached the SUMMARY branch.

**Counts:**

- 5,562 stored section searches.
- The route fires on **264** calls, plus 56 memo hits, which carry the first call's block.
- 182 list reads and 3 text reads were served by the mock.
- **77 calls reach the SUMMARY branch.** Of these:

| Shape | Calls |
|---|---|
| unit whose text has no `Section N)` heading line (annexes; schedules with bare markers only) | 53 |
| query names a paragraph or chapter (outside the lever: a named paragraph with no heading of its own, or cuts over the threshold) | 7 |
| headed schedule, no query word in any heading (one 60,481-character schedule with 3 headings) | 1 |
| **headed schedule, a query word matches** (all on P3.12's Schedule, 92,066 characters, 76 headings) | **16** |

**Heading census** (`python heading_census.py`, `heading_census.txt`), over the 149 schedule and annex rows
in the saved lookups:

- 30 carry at least one heading line;
- the most headings in one unit is 76, the longest heading is 84 characters, and the longest list in the
  built format is 2,776 characters;
- 9 headings in 7 units are empty (`****`);
- 1 unit repeats a number.

**The matching rule, measured three ways** on the 16:

| Rule | Paragraphs in 14 calls | Paragraphs in 2 calls | Wide matches |
|---|---|---|---|
| any non-stop query word | 42, 43, 44 | 42, 43, 44 plus three others | one call matches **15 paragraphs (18,756 characters)**, from a word in 15 headings |
| a word in at most 3 headings (**built**) | 42, 43, 44 | 42, 43, 44 plus three others | none |
| a word in at most 10% of headings | same as the built rule | same as the built rule | none |

- On the built rule, the 14 calls get 42, 43 and 44 (4,118 characters).
- The 2 calls get those plus paragraphs 6, 15 and 23 (8,494 characters). Their query also names a
  word in those three headings.
- **Every stored query that reached the summary on this Schedule shares a heading word with paragraphs
  42-44.** That includes all three of Session 41's reps, and r2, whose Worker said "not retrieved".

**Sizes against the threshold and the budget:**

- At 8,000, cuts plus heading list fit in 14 of 16 calls.
- The 2 six-paragraph calls are over 8,000 whatever is counted. This sets the bound (decision 2).
- The context budget is never close: at most 55,915 characters were used before any call that reached
  the summary, against 250,000.

**So the measurement supports the build.**

---

## 2. What changed (product)

`server_py/src/utils/schedule_units.py` (pure part) and `server_py/src/agent/agent_shared.py`
(`schedule_route_block`); nothing else.

**New in `schedule_units`:**

- `paragraph_headings(text)`: `[(number, heading)]` for every `Section N) **heading**` line, in order. The
  heading goes through `_clean` (no square bracket, whitespace collapsed) and is capped at 120 characters.
- `heading_matches(headings, query, unit)`: the numbers of the headings that share a distinctive word with
  the query.
  - Words are lower-case and 3 letters or more.
  - Stop words are dropped, including the unit words `schedule`, `paragraph`, `part`, `chapter`,
    `section` and `provision`.
  - A plural ending is taken off ("licences" to "licence", "-ies" to "-y", never "-ss").
  - The unit's own label is never a query word.
  - A word is distinctive when it is in at most `_MAX_HEADINGS_PER_WORD` = 3 of the unit's headings.
- `matched_pieces(unit, text, query, bound)`: the heading list piece first, then each matched paragraph cut
  by `cut_schedule_paragraph` and labelled by the existing `paragraph_label` (clean only where the heading
  line is unique and the next headed paragraph is N+1; a labelled span otherwise).
  - It returns **None** (the caller summarises as before) for:
    - an annex;
    - a unit naming a paragraph or a chapter;
    - nothing matching (this covers a unit with no heading line);
    - a matched paragraph with no unique heading line (NOT_CUT);
    - cuts over `bound`.
  - It never raises.
- The heading list: at most 150 headings, then `and <k> more headings after paragraph <N>`.
- `MATCHED` (a new `how`) and `MATCHED_CUTS_MIN_CHARS` = 12,000.
- `fetched_block(..., summary_of=WHOLE)`: the MATCHED tail, and the two reworded SUMMARY tails (2.1).

**In `schedule_route_block`:**

- When the unit's text is over the verbatim threshold, it calls
  `matched_pieces(unit, text, args["query"], max(threshold, MATCHED_CUTS_MIN_CHARS))`.
- The result is accepted only if the whole matched body (labels, list and cuts) fits the context budget:
  `used + pending_chars + size <= limit`.
- Otherwise, or where only the budget (not the threshold) sends the unit to the summariser, it summarises
  exactly as before.
- The URL harvest, the block's position in the tool result and the per-run fetch slot are unchanged.

### 2.1 The exact wording (for the user, before merge)

`<U>` is the unit ("Schedule 5", "the Schedule"), `<N>` its size in characters. The lead (`the index holds
<U> of <id> as one provision (url: ...). This search's results left it out, so code fetched it from the
index's provision list.`, or the text-fallback lead) and every `reason` are unchanged and still follow the
tail.

**MATCHED tail (new):**

> ` <U> runs to <N> characters, longer than one result hands over whole, so below are its paragraph
> headings, in order, and then each paragraph whose heading shares a word with this search's query, cut
> from the retrieved text and labelled. To read another headed paragraph in its own words, name <U> and its
> number from the list below in a section search: code cuts it out the same way.`

**Heading list (new), the first piece of a MATCHED block:**

> `The paragraph headings of <U>, in order, each after the number of the paragraph it opens:`
> then one line per heading, `<number>: <heading>`, or `<number>: (untitled)` for an empty heading;
> after 150 headings, `and <k> more headings after paragraph <number>`.

**The matched paragraphs** carry the existing piece labels, unchanged ("Paragraph <p> of <U>, cut at its own
heading and the next one:" and the three span labels).

**SUMMARY tail of a whole unit (reworded; was "Below is <U> summarised for this research question, because
it runs to <N> characters. The summary is not the statutory text: quote the provision only from retrieved
text."):**

> ` Code retrieved the whole of <U>, <N> characters, and below is a summary of that retrieved text, condensed
> for this research question. A paragraph the summary leaves out is still part of the retrieved <U>. Cite
> <U> for what the summary says, and quote its words only from text shown verbatim.`

**SUMMARY tail of a cut (reworded the same way; new variant):**

> ` Code retrieved the whole of <U> and cut out the parts of it this search named, <N> characters, and below
> is a summary of those retrieved parts, condensed for this research question. A paragraph the summary
> leaves out is still part of the retrieved <U>. Cite <U> for what the summary says, and quote its words
> only from text shown verbatim.`

No "not" appears anywhere in the new text, and no square bracket.

### 2.2 Screens (built code; all pass)

- **`test_footer_trips_no_detector`**: every variant above is added to `_fetched_wording_variants`, from both
  sources, with and without a reason. That covers the MATCHED tail, the cut SUMMARY tail, the heading list
  label, the untitled line and the cap line. The test checks `NEG_ASSERTED`, `NOT_FOUND`,
  `derivation_claims`, `IN_FORCE_CLAIM`, `_CUR_DISCLOSED`, `NEG_TERMS`, `NEG_LIMITS`, `NEG_BLAMED_INDEX`,
  `NEG_BLAMED_USER`, the three halt detectors, `OPENER_VOCAB`, the footer strip, `_CMC_*`,
  `_currency_asserted` and `negcurrency_claim`.
- **My own screen** (`screen_b10A.py` run from `server_py/`, output `screen_b10A.txt`). It uses the
  integrator's `b9_screen.screen`, copied, sentence by sentence, including `SCHED_LIMIT`,
  `SCHED_INDEX_NEG`, `NEGATIVE_EXPLAINED` and `sched_clause_class`. It also runs `sched_unit_clauses` per
  clause and `_P312_NOT_DELIVERED`.
  - 22 texts (every tail by source by reason, the bare unit, the list label, the untitled line and the cap
    line): **0 trips, 0 flagged.**
  - A first draft tripped **`NEGATIVE_EXPLAINED`** on "search for <U> with its number" in all six MATCHED
    variants. It was reworded to "name <U> and its number ... in a section search".
- **`test_every_matched_variant_reads_as_held_to_the_schedule_grader`** (in `test_schedules.py`, not E's
  file): `sched_unit_clauses` classes every clause of every new text as `""`. None is INDEX, TEXT, NEG,
  LIMIT or OFFER. None matches `SCHED_LIMIT`, `_P312_NOT_DELIVERED`, or "not ... retriev".
- **`depth`** (`depth_echo_check.py`, `depth_echo_check.txt`, scratch: it carries DEPTH_TRUTH's statutory
  words). An answer citing paragraphs 42-44 with their facts:
  - grades DELIVERED alone;
  - still grades DELIVERED with the MATCHED tail, the list label and the SUMMARY tail echoed into each
    citing sentence's window;
  - a control with "its text was not retrieved" in each citing sentence grades SHALLOW, as it should.

**Labels for E's `sched_clause_class` check** (every new product string; none should class as a negative or
a limit, and none does today):

1. the MATCHED tail;
2. the whole-unit SUMMARY tail;
3. the cut SUMMARY tail;
4. "The paragraph headings of <U>, in order, each after the number of the paragraph it opens:";
5. "<number>: (untitled)";
6. "and <k> more headings after paragraph <number>".

**Grader notes (no change made; I did not edit `replay_report.py`):**

- `depth --seams` removes the whole `[PROVISION FETCHED BY CODE ...]` block before grading the
  summarised-search seam, so it will not show what a MATCHED block carried. Read the block with
  `route_trace.py`.
- `route_trace.py`'s label regex prints the paragraph labels of a MATCHED block. It does not print the
  heading-list label, which starts "The paragraph headings", not "The text of". That is harmless.
- The old tail still appears as a fixture string in `tests/test_replay_schedules.py` (`_TAILS`). It tests
  the grader on recorded wording, so I left it.

### 2.3 Other code texts about the same instrument (lessons)

- **P3.1's cap, and A2's complete-list refusal, limb and footer:** consistent with the new text.
  - The MATCHED tail invites a further section search naming a paragraph number.
  - After 3 rounds on the instrument, P3.1 refuses that search.
  - A2's text then says that a listed provision the step did not reach was cut short by a limit, which is
    true.
  - The tail's "code cuts it out the same way" holds whenever the search runs (decision 1, option 2,
    removes the sentence if the user prefers).
- **P4.17's section-search line** ("may still be in the instrument"), **P3.27's `schedules_note`** (another
  tool), **P3.11's outline** and **P1.6's citation URLs** (the search result's own blocks): unchanged, and
  none contradicts the new text.
- **The old SUMMARY tail's "quote the provision only from retrieved text"** is gone. The new tail says the
  unit WAS retrieved, and permits citing the summary.

---

## 3. Dry run with the BUILT code (both trees)

**Commands:**

```
git archive 7c3c6ac server_py/src | tar -x -C prev     # the base tree
DRYRUN_WT=<this folder>/prev/server_py DRYRUN_OUT=dry_prev.json python dryrun_b10.py
DRYRUN_WT=<worktree>/server_py          DRYRUN_OUT=dry_new.json  python dryrun_b10.py
python compare_b10.py            > compare_b10.txt     # --queries prints query text: scratch only
```

`dryrun_b10.py` asserts that every module came from the tree it was pointed at. It was re-run on the
committed tree (`cdbc617`) after the last product change, with identical results. `prev/` was deleted at the
end; the `git archive` line rebuilds it.

**Inputs:**

- 63 directories, 5,562 section searches, **264 firing calls**. The 56 memo hits carry their first call's
  block.
- **33 firing calls have no saved lookup**, on 8 instruments (`unsaved_and_live.txt`). The dry run serves
  them a 503:
  - 30 are "the Schedule" with no label on a failed list, and get nothing, as before;
  - 3 get the fetch-failed line, as before.

**Every firing call's block:**

| Change | Calls |
|---|---|
| unchanged | 190 |
| SUMMARY tail reworded only (whole unit), summary body and all else byte-equal | 52 |
| SUMMARY tail reworded only (a cut summarised) | 6 |
| **SUMMARY to MATCHED** | **16** |
| anything else | **0** (asserted) |

- Summariser calls fall from 77 to 61.
- Every moved call is listed with its key, mode, instrument and change in `compare_b10.txt`.
  - The 16 MATCHED calls are all P3.12's turn, across `baseline`, `wave0_conv`, `wave1`, `wave2`,
    `wave3_p38_pre`, `wave4_b8_sweep` (2) and `wave4_b9_sweep1` (all 3 reps).
  - The 58 reworded tails are on 6 sessions' schedules and annexes. P3.2's annex turns are among them;
    their chapter cuts are unchanged.

**The 16 MATCHED blocks:**

| Block | Calls | Size | Contents |
|---|---|---|---|
| headings, then 42, 43 and 44 | 14 | **7,883 characters** (heading list and its label 2,873) | three clean cuts; under 8,000 |
| headings, then 6, 15, 23, 42, 43, 44 | 2 | **12,840 characters** | 6, 15 and 23 as labelled spans; 42-44 clean |

The two six-paragraph calls are `wave3_p38_pre` r2 and `wave4_b9_sweep1` r2.

**P3.12's paragraphs:** in **16 of 16** MATCHED calls, paragraphs 42, 43 and 44 are each cut clean and
byte-equal to batch 7 B's ground truth (`p312_truth.txt`). That includes all three of Session 41's reps.
Check: `compare_b10.py`'s last line (passes).

**What the dry run cannot see:**

- **Live summarised calls on an instrument with no saved lookup** (`unsaved_and_live.txt`). There are two
  firing calls, plus their 2 memo hits, both on one Act's 161,434-character schedule on P3.22's session (in
  `wave4_b9_sweep1` and `wave4_b9_sweep2a`).
  - One names a paragraph, so it is outside the lever.
  - The other names none. Whether that schedule carries heading lines, and whether the query's word is
    distinctive in them, is unknown without its payload. I made no live call.
- **The production threshold.** With a warm context-length cache, the pinned model's threshold is up to
  200,000, so a 92,066-character unit goes over WHOLE and neither branch runs.
  - The lever acts at the 8,000 fallback: every stored replay, and any model missing from the cache, such
    as Thomas's.
  - It also acts wherever the unit is larger than the threshold.

### 3.1 Forms no stored run contains, tested on synthetic input

Each form is a test in `tests/test_schedules.py` ("batch 10 A" part), on "Widget Order 1901"-style text:

- a query matching more than fits the bound (cuts over the bound, with the boundary exact);
- a query whose only heading word is in 4 headings (not distinctive);
- stop words and two-letter words;
- a matched paragraph whose heading number repeats (NOT_CUT, so the summary);
- the bound when the threshold is larger than 12,000 (the `max`);
- a matched block over the context budget, including the search result's own pending text;
- a unit under the threshold that only the budget sends to the summariser (summarised as before);
- an annex carrying heading lines;
- a unit naming a paragraph or a chapter;
- the text fallback after a failed list;
- "the Schedule" as the only schedule;
- a lettered heading (6A);
- over 150 headings, a heading over 120 characters, and a bracket in a heading;
- a malformed unit (fail-soft).

Two forms ARE stored: a schedule with no heading lines (53 calls), and a headed schedule whose query
matches no heading (1 call).

---

## 4. Tests

In `server_py/tests/test_schedules.py`, a new "batch 10 A" part:

- 17 functions, 20 cases with the parametrised one (the suite's +20);
- a seam test through `run_worker_tool`, which pins the section search's query, not the research question,
  as the one matched;
- the grader-reading test;
- two existing asserts updated to the new tail wording.

In `tests/test_search_scope.py`, the screen variants were extended.

**Revert:** restoring `schedule_units.py` and `agent_shared.py` to `7c3c6ac` on a scratch copy removes **185
lines** (restores 12). **23 tests fail.**

**Single-site mutants:** `python spec_b10.py`, then `python mutants.py spec_b10.json` (`mutants_b10.txt`;
batch 9 A's runner, copied).

- Each mutant runs `test_schedules.py`, `test_search_scope.py`, `test_replay_schedules.py` and
  `test_section_budget.py` in a scratch copy.
- Two `test_replay_schedules` tests are deselected there: they read `evidence/scripts/` relative to the
  tree, which a scratch copy lacks. They pass in the worktree.
- **32 of 32 single-site mutants are caught**, each failing 1 to 9 tests.

| # | Mutant | Fails |
|---|---|---|
| a1 | the matched path never taken | 8 |
| a2 | the threshold guard dropped (a budget-only summary takes the path) | 1 |
| a4 | the bound ignores the threshold | 1 |
| a5 | the bound ignores the 12,000 floor | 7 |
| a6 | the budget check dropped | 1 |
| a7 | the budget ignores the pending search text | 1 |
| a8 | the research question matched instead of the search query | 8 |
| a9 | `summary_of` not passed | 1 |
| u1 to u3 | the kind, paragraph and chapter guards, one at a time | 1 each |
| u4 | an uncuttable match skipped instead of falling back | 1 |
| u5 | the no-match check dropped | 5 |
| u6 | the bound check dropped | 1 |
| u7 | `>=` for `>` on the bound | 1 |
| u8 | `<` for `<=` on distinctiveness | 1 |
| u9 | distinctiveness dropped | 3 |
| u10 | the unit label kept as a query word | 1 |
| u11 | stop words kept | 2 |
| u12 | two-letter words kept | 2 |
| u13 | "-ies" not stemmed | 1 |
| u14 | "-s" not stemmed | 2 |
| u15 | "-ss" stemmed | 1 |
| u16 | the heading list uncapped | 1 |
| u17 | headings uncapped | 1 |
| u18 | headings not cleaned (bracket, whitespace) | 2 |
| u19 | "(untitled)" not said | 1 |
| u20 | not fail-soft | 1 |
| u21 | the MATCHED tail missing | 3 |
| u22 | the old summary sentence restored | 9 |
| u23 | the cut summary tail ignored | 2 |
| u24 | the heading regex drops a letter suffix | 1 |

**Equivalent guards found and removed, not kept:**

- `matched_pieces`' empty-headings exit, its span dedupe and its `freq >= 1` test (`a08acc9`);
- the route's `how == WHOLE` test (`cdbc617`).

Each was implied by a later check, so a mutant of it could not fail. u24 first survived; `cdbc617` added the
lettered-heading test that catches it.

---

## 5. The seam payload for the integrator's draw (not drawn)

`python make_seam_payloads.py` writes two copies of `wave4_b9_sweep1/6335_rep2.json`, the rep whose Worker
called the summarised paragraphs "not retrieved". In each, only turn 7, delegation 0, tool 2's
`final_result` differs (asserted):

- `seam_6335_r2_matched.json`: the route's block replaced by the built MATCHED block for that call (headings
  plus 6, 15, 23, 42, 43 and 44);
- `seam_6335_r2_tail.json`: the stored summary kept, and only its tail reworded to the built wording.
  This isolates the tail.

`seam_replay worker --turn 7 --delegation 1 --dry-run` builds both. It made no model call.

| File | Messages | Characters |
|---|---|---|
| the original | 8 | 38,626 |
| tail | 8 | 38,762 |
| matched | 8 | 46,674 |

What to read in a draw:

- whether the report gives paragraphs 42-44 with their facts from the cut text;
- whether any report calls a paragraph of the Schedule "not retrieved";
- with the tail copy, whether the reworded tail alone removes that reading.

---

## 6. What I did NOT do

- No model call, seam draw, replay, server or live call. Whether the Worker now reads the cuts and stops
  saying "not retrieved" is the integrator's draw and the 6335 n=3 sweep.
- I did not edit `replay_report.py` (E's file), FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md, a rubric, the
  tracker or a memory file. I did not push or merge.
- I did not change the paragraph-named path, the annex path, the 8 per-run list bound or P3.1's cap.
- I did not try to reach the Act on P3.22's session that has no saved lookup (section 3).

## 7. Decisions for the user

1. **The new wording (section 2.1).** It is Worker-facing, and a Worker can echo it.
   1. **(Recommended) Approve as built.** It passes every detector, and `depth` and `schedules` read an
      echo as intended.
   2. **Approve without the MATCHED tail's last sentence** ("To read another headed paragraph ... code cuts
      it out the same way."). Choose this if inviting a further section search on the instrument (which
      P3.1's cap can refuse after 3 rounds) is unwanted. The Worker then gets the headings with no hint of
      how to use them.
2. **The bound on the cut text.**
   1. **(Recommended) `max(threshold, 12,000)`, as built.**
      - At the 8,000 fallback, all 16 stored matches pass, including the two six-paragraph ones (8,494
        characters, block 12,840).
      - The 15-paragraph wide match (18,756) that a looser rule would make still falls back.
      - Where the threshold is larger, it governs.
   2. **The threshold alone.** The 2 six-paragraph calls fall back to the summary. One of them is Session
      41's r2 shape, the rep that said "not retrieved".
   3. **A larger floor (say 20,000).** It admits wider matches that no stored call makes, at a larger
      block.
3. **The fallback when nothing matches or the cuts exceed the bound.**
   1. **(Recommended) Today's summary, with the reworded tail, as briefed and built.** One stored call
      takes it on a headed schedule.
   2. **The summary plus the heading list.** The Worker could then name a paragraph in its next search. That
      is a larger block, and a variant to screen and measure.
4. **The words matched against the headings.**
   1. **(Recommended) The section search's own query, as built.** It is deterministic per call, and the
      seam test pins it.
   2. **Also the research question (the Manager's brief).** More words mean more matches, and a higher risk
      of exceeding the bound. On the 6 reps of the two sweeps the route ran in, the brief would match the
      same paragraphs as the query in 5, and add one more paragraph in 1 (Session 40's r3)
      (`brief_vs_query.py`, run from `server_py/`).
5. **What to draw before the paid sweep** (the integrator's choice; priced by E).
   1. **(Recommended) Draw `seam_6335_r2_matched.json` and `seam_6335_r2_tail.json` first** (a few cents),
      then 6335 n=3 as booked.
   2. **Go straight to the 6335 n=3 sweep.**
