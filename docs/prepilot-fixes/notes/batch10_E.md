# Parallel batch 10, agent E: grader fixes, and P3.12's re-run priced ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. With no commits of mine I
ran `git reset --hard 7c3c6ac3040075850ab1a934d3443ed43558637b` (the integrator's head). This note is based on
`7c3c6ac`. Branch `worktree-agent-aee344403a085ca96`; commits listed at the end.

**Spend: $0.** No model call, no server, no replay pin/run/restore, **no external call of any kind** (none was
authorised). **Model:** every stored run read here ran on the pinned `google/gemini-3.1-pro-preview` (summariser
`google/gemini-3-flash-preview`); nothing below comes from `glm-5.2:cloud`.

**Scratch:** gitignored `docs/prepilot-fixes/evidence/seam/batch10/E/` (`git check-ignore -v` gives
`.gitignore:113`), copied to the main checkout's same path at the end. Every command runs from `server_py/`
with `PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_e`; `S=` that scratch folder,
`E=$PREPILOT_EVIDENCE/replay`. The scripts there take the worktree path as their argument; to re-run them on
the merged tree, pass the main checkout's path (they import the module from the path given, never a copy).

**Shape note for the integrator (lesson 2):** no tool result's shape changed (tooling only, nothing under
`server_py/src/`). One rubric key is new and optional (`parties`, `citations` on an out-of-corpus authority);
the current `evidence/rubrics/p322.json` needs no change and gives the verdicts below.

---

## 1. What changed, and why (`server_py/tools/replay_report.py` only)

1. **`authorities`, item 3: an out-of-corpus authority is named by its full party names or its citation,
   never by one surname** (user decision 3 in the brief; Session 41's three false FAILs). A sentence names
   one when it carries a FULL form: F1 its law-report citation (`citations`, else the one in its label);
   F2 "A v B" (a distinctive word of the first party, " v ", the first distinctive word of the second
   party, gaps of at most 40 characters with no bracket; a closing bracket may follow the first party, for
   "R (X) v Y"); F3 a party's first two distinctive words together; F4 a two-word `mention` match (the
   rubric's own full alternatives). Parties come from `parties` or, by default, from the label's "A v B"
   (its citation and a trailing court bracket removed). A one-word `mention` match (a SHORT form, the
   surname a later sentence uses) counts **only once the run has named the authority in full, in this
   answer or an earlier one**. And **a match whose every word is in the title of a judgment that a
   `search_case_law` call in the run returned (this turn or earlier) and that the sentence cites (by
   citation or URL) is that judgment, never the out-of-corpus authority** (the brief's rule). The same
   guard applies inside the LINKED and source-phrase checks (`_P322OocMention`).
2. **`authorities`, item 3: a link label holding a bracketed citation is a link** (the coordinator's extra
   item, agreed by the user 2026-10-08; batch 10 B found it). `p322_mention_class`'s LINKED test now uses a
   local `_P322_LINK`, which allows one nested `[...]` (up to 60 characters) in a label; the shared
   `MD_LINK` is unchanged (a test pins that).
3. **`negcurrency` reads a section search in the `{"results": [...]}` shape** as well as the bare list
   (`negcurrency_evidence`; any other shape reads as nothing and never raises). Batch 9 E's count: 4,748 of
   5,314 stored section searches have the dict shape, every directory from `wave0_conv` on.
4. **`corpus`'s labels true before and after P3.6.** "`<- _slim_search_results strips it (P3.6)`" is now
   "`<- 0 before P3.6 (_slim_search_results stripped it); kept, cut to 600 characters, since`". The line
   below it said a whole text's `legislation.description` was "the ONLY route" to a preamble, false since
   P3.7 (`lookup_legislation`) and P3.6 (a search row); it now says so. I changed this second label too
   (same stale cause, same block). Check: 0 of 38,523 stored search rows in all 63 directories carry a
   `description` (`raw_result`), so "0 before P3.6" is true of every stored directory.
5. **`commencements` grades scripted runs** (optional item, done): the truth is looked up by the run's base
   session (`script.base`), and each scripted turn is printed as "t3 (export t7)". Full-session output is
   byte-identical.

## 2. Item 1 (authorities): every verdict that moves, per part

`python $S/auth_parts.py <worktree>` (`$S/auth_parts.txt`) grades item 3 over all 18 stored 6359/6363 runs
(`baseline`, `wave1`, `wave2`, `wave4_b9_sweep1`, `wave4_b9_sweep2a`; no other directory holds either
session, scripts included) under four builds: the base, the nested-bracket part alone, the surname part alone
(commit 1), and both. **28 item-3 verdicts; 4 move; nothing else differs.**

| Run, turn (6359, the out-of-corpus key case) | Base | Nested only | Surname only | Both |
|---|---|---|---|---|
| `wave4_b9_sweep1` r1 t3 | FAIL (UNQUALIFIED) | FAIL (LINKED) | not named | not named |
| `wave4_b9_sweep2a` r2 t3 | FAIL (UNQUALIFIED) | FAIL (LINKED) | not named | not named |
| `wave4_b9_sweep2a` r3 t3 | FAIL (UNQUALIFIED) | FAIL (UNQUALIFIED) | not named | not named |
| `wave4_b9_sweep2a` r3 t7 | PASS (SECOND_HAND) | **FAIL (LINKED)** | PASS | **FAIL (LINKED)** |

- **The surname part** moves exactly the three t3 rows: Session 41's three false positives (each cites a
  different, in-corpus judgment sharing the key case's first party's surname; that turn's search returned
  it). Each rule alone clears all three (`python $S/which_rule.py <worktree>`, `$S/which_rule.txt`:
  anchoring alone and the title guard alone give the same 28 verdicts as both).
- **The nested part** turns two of those false positives from UNQUALIFIED to LINKED (still FAIL, and
  cleared by the surname part), and moves **`wave4_b9_sweep2a` r3 t7 PASS to FAIL**: its sentence links a
  label naming the key case and its law-report citation to the carrier judgment's URL. **Hand-read: a
  genuine LINKED failure** (agrees with batch 10 B's `linked_check.out`). Session 41's hand-read had it as
  a pass.
- **The genuine `wave4_b9_sweep2a` r2 t6 stays a FAIL** under every build. The stored `wave1`/`wave2` FAILs
  (6363 r1 t1, t4; 6359 r1 t6, t7) are unchanged under every build.
- **Result, as built:** `wave4_b9_sweep1` 0 item-3 FAILs (was 1); `wave4_b9_sweep2a` 2, r2 t6 and r3 t7
  (was 3: r2 t3, r2 t6, r3 t3). Items 1, 2 and 4 are untouched: `authorities --before wave4_b9_sweep1` on
  `wave4_b9_sweep2a` prints the same item-1/2 section with the base and the built module (the two 6363
  "fewer" rows are unchanged).
- `bash $S/auth_all.sh $S/auth_after.txt` is the plain command over the five directories (exit 1: the
  genuine FAILs).

**Input forms no stored run contains, tested on synthetic input:** the citation alone (F1); "Widget V.
Gadget"; "A v B" with a corporate second party ("E. Gadget & Co Ltd"); a bracketed first party
("R (Widget) v ..."); a trailing court bracket in the label; a rubric with `parties`/`citations`; a
retrieved title with no "v"; a judgment retrieved in an earlier turn and cited later; one retrieved only
after the citing turn (no guard); a full form sharing one word with a retrieved title (still counts); a link
label with a nested citation, for the key case (LINKED) and for a retrieved judgment (not LINKED).

## 3. Item 2 (negcurrency): the identity run, every move read

`python $S/identity.py <worktree>` runs the 16 exit-1 graders plus `negcurrency --drops`, `corpus`,
`commencements --drops --answers` and `authorities` (rubric `p322.json`) with the base module and the built
one over all **63** directories (`$S/identity.txt`; both outputs of every difference in `$S/moves/`).
**20 graders x 63 directories = 1,260 outputs: 1,173 identical, 87 differ, every difference an intended
move:** `corpus` 63 (the label lines only), `negcurrency` 4 directories, `commencements` 9 directories (18
outputs, two invocations each), `authorities` 2 (`wave4_b9_sweep1`, `wave4_b9_sweep2a`, section 2). **Of the
16 exit-1 graders, only `commencements` moves (section 4); the other 15 are identical on all 63
directories.** Run on the built module after the last code commit; its list of moves equals the earlier run's
on the first commit.

`negcurrency` moves in 4 directories, **19 claims, all read by hand** (`python $S/nc_moves.py <worktree>`,
`$S/nc_moves.txt`, each with its sentence and the provision text now read):

- **1 verdict moves:** `wave0_conv` 6341 r1 t8, UNSUPPORTED to UNCLEAR (a dated commencement provision of an
  unrelated instrument, retrieved by section search in an earlier turn; the sentence names no instrument).
  **By hand neither verdict is right: the sentence is a definition** (it lists what a "stub" in the database
  can mean, one being "not yet in force"), not a claim about any instrument. The move takes a false
  UNSUPPORTED out of the count; the definitional false positive itself is the claim detector's and is not
  fixed here (section 7).
- **18 reasons move, verdict unchanged (UNSUPPORTED):** `wave1` 6410 r1 t1 (2 claims), `wave2_p22` 6409 (6),
  `wave2_p22_final` 6409 (10): "no change record for the instrument named / consulted (read from an absence)"
  becomes "commencement provision retrieved, which names the mechanism, and no change record (read from an
  absence)". By hand, in every one the turn's section search returned the Act's own commencement section
  (some sections on the day after Royal Assent, the rest on a day Ministers appoint by regulations) and no
  change record was consulted; the claims ("partially in force", "the majority ... not yet in force", "no
  commencement orders have been made") rest on that absence. The new reason is the accurate one; the
  verdict stands.
- No directory's totals change except `wave0_conv` (UNSUPPORTED 1 to 0, UNCLEAR 0 to 1). The moves are few
  because the mechanism and date branches are reached only where no commencement relation is in hand: every
  `wave3_*`/`wave4_*` claim already had a change record.

**Forms tested on synthetic input:** both shapes for a mechanism and a dated provision (evidence and
verdict); `{"results": null}`, a missing key, a string, a non-dict row, a number and a dict in `results`.

## 4. Items 3 and 4: `corpus` and `commencements`

- **`corpus`** differs in all 63 directories, only in the two label lines: `python` check over `$S/moves`
  shows 0 lines differing outside the text after "<-".
- **`commencements`** now grades scripted runs in 9 directories (`wave4_b8_sweep`, `wave4_b9_sweep2b`,
  `wave4_p315_pre`, `wave4_p37`, `wave4_p37_pre`, `wave4_p37_reach`, `wave4_p37_reach_pre`, `wave4_p37b`,
  `wave4_p37c`); **its exit moves from 1 ("no graded session") to 0 in 7 of them**, so the exit-1 set's
  expected output changes there (Session 41's hand-reads note "commencements 1, it never grades a scripted
  run"). Every `p37_6409` rep (21) is graded; the `p37r_6383` scripts (3) have no in-scope turn.
  `python $S/cmc_scripted.py <worktree>` (`$S/cmc_scripted.txt`): **42 in-scope turns, all `correct`**:
  export t1 in 21 of 21 names both commencing instruments with the provisions they commenced; export t7 in
  21 of 21 names the first. **Hand-read: no denial in any of the 42; I agree with every export-t1 verdict.
  Export t7 is a trap the grader shares with the full sessions:** its question names the first commencing
  instrument by its title, which `_names_instrument` (ids and citations only) does not see, so the turn is
  in scope and its "DELIVERED" is the lawyer's own instrument repeated back (the full-session `6409` t7 rows
  are in scope the same way, graded NONE there). Not changed (decision 3).

## 5. Item 5: P3.12's re-run priced (6335 n=3, Conversational as recorded)

`python $S/price.py` (`$S/price.txt`). Recorded `total_cost_usd` per stored rep, each in the recorded mode
(Conversational x7; turns 6-7 `legislation_and_case_law`, set by the replay from the export's reviewer
sources):

| Basis | Reps | Median / rep | Max / rep | n=3 at median | n=3 at max | Cap |
|---|---|---|---|---|---|---|
| **`wave4_b9_sweep1`** (head `3daf7a6`; the brief's basis) | $0.574, $0.610, $0.567 | **$0.574** | **$0.610** | **$1.72** | **$1.83** | **$1.90** |
| `wave4_b8_sweep` (head `68fd879`), for comparison | $0.597, $0.466, $0.489 | $0.489 | $0.597 | $1.47 | $1.79 | $1.80 |
| both, six reps | | $0.570 | $0.610 | $1.71 | $1.83 | $1.90 |

Cap = 3 x the recorded maximum of one rep, rounded up to $0.10 (batch 9 E's method): `--max-spend` is checked
between reps only, so the command runs all three reps while each costs no more than the recorded maximum and
stops early when they run hot. It cannot stop a rep in flight: a Manager runaway took one Session 41 rep to
$4.75 (lesson 7), so the sweep's real exposure is the cap plus one runaway rep.

```
O=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b10_sweep
python -m tools.replay run --session 6335 --reps 3 --out-dir $O --max-spend 1.90
```
(`--session`, `--reps`, `--out-dir`, `--max-spend` checked against `tools/replay.py`'s argparse.)

**Would A's lever change the cost?** By cents a rep at most, direction unknown until A's bound is fixed.
Turn 7 costs $0.143, $0.172, $0.152 in `wave4_b9_sweep1` (one fifth to one quarter of a rep). In 5 of the 6
stored P3.12-era reps the route summarised the whole 92,066-character Schedule at turn 7: one Flash summariser
call (`summarisation_chars_in` 269,430 / 158,051 / 201,730 in sweep 1 each include exactly the 92,066; the
summary returned is a few thousand characters). A's lever replaces that call with no model call (a heading list
and cut paragraphs), so it saves one Flash call on ~23K tokens a firing, and adds its verbatim text (larger
than the summary, up to A's bound) to the Pro Worker's context for its remaining rounds and to the report the
Manager reads. Both effects are small beside the turn-7 spread across the six stored reps ($0.125 to $0.172).
If A's bound is large (tens of thousands of characters re-read over several Worker rounds), raise the cap to
$2.00. Every stored replay was summarised at the 8,000-character fallback (cold context-length cache); the
sweep will be too, which is the condition under which the 92K Schedule reaches the summariser at all.

## 6. For the integrator: what reads A's PROVISION FETCHED BY CODE block (not edited)

- **`sched_clause_class` (`schedules`) reads ANSWER clauses only** (footer stripped), so A's labels reach it
  only when a Worker or Manager echoes them into an answer. An echoed clause about the unit is classed
  OFFER on `SCHED_OFFER` ("would you like me to", "I can retrieve/pull/fetch/look", "deeper look/search",
  "more comprehensive search"); LIMIT on `SCHED_LIMIT` ("cut short", "system/step/search/research/tool-call/
  internal/round ... limit" within 25 characters, "limit was reached", "did not complete", "halted", "not
  fully retrieved", "initial/quick search", "timed out"); INDEX on `SCHED_INDEX_NEG` ("index/database ...
  lacks / does not hold / holds no / has no / without its ... text", "no text/schedules ... index", "missing
  from the index", "none of them is a schedule", "<unit> is not one of them", "holds none for"); NEG/TEXT
  on `SCHED_NEG_EXTRA` ("not held", "missing from", "not retrieved", "was not retrieved/returned/included",
  "not retrievable", "unable to retrieve", "cannot be retrieved", "not included/contained/present/available
  in the", "text ... does not contain/include", "did not return", "not returned", "unavailable in/from")
  and `NEG_ASSERTED`. **For A's reworded summary tail:** no "not" next to "retrieved", no "not included in
  this", no "limit" after "search"/"step"/"round", no "cut short" (D's lesson). For a heading list: "only the
  paragraphs whose headings match ... are shown" is safe; "the other paragraphs were not included/returned"
  is NEG on a held unit (a FAIL).
- **`depth`** grades answers only against `DEPTH_TRUTH`; **`depth --seams`** reads each summarised section
  search's `final_result` through `_summary_text`, i.e. the product's `strip_scope_blocks`, whose
  `_FETCHED_BLOCK` removes everything from the `[PROVISION FETCHED BY CODE ...]` header to
  `[/PROVISION FETCHED BY CODE]`. **So A's verbatim cuts and heading list, inside the block, are invisible
  to `--seams`**; read the route's handover with `route_trace.py`. If A's header gains a `]` before its end,
  or the opener/closer strings change, both `_FETCHED_BLOCK` (and `_TOOL_BLOCK`) and `corpus`'s
  `CORPUS_LEAK_MARKERS` (the literal opener and closer) stop matching.

## 7. Found on the way, not fixed

1. **`negcurrency` counts a definition as a claim** (`wave0_conv` 6341 r1 t8: a list of what a database
   "stub" may mean). Rare (one in all 63 directories that moved; I did not census the unmoved ones).
2. **`commencements`' scope misses a question naming the instrument by title** (section 4; decision 3).
3. **I ran one pytest of two test files without `TEST_DATABASE_URL` set**, so its session fixture ran
   `create_all` then `drop_all` on the default `lexchat_test` (once, about 2 seconds, while adding the
   nested-bracket test). Tables there are
   recreated by the next suite's `create_all`; a suite running on `lexchat_test` at that moment would have
   failed. Every other run (including the full suite below) used `lexchat_test_e`.
4. A first full-suite run errored throughout while my mutant runs (pytest on the same `lexchat_test_e`)
   were dropping its tables; it was stopped and re-run alone (section 8).

## 8. Tests, revert, mutants, suite

- **Tests:** `server_py/tests/test_replay_batch10.py`, **28 tests**, all synthetic ("Widget v E
  Gadget Sprocket & Co [1899] AC 52", `asp/1901/1`, session "9001").
- **Full revert** (the base `replay_report.py` on a scratch copy, `$S/rev/`, never the worktree; the diff is
  225 lines added and 19 changed; the revert removes the 225 and restores the 19): **20 failed, 8 passed** (`$S/revert_pytest.txt`). The tests that pass on the revert are the
  invariance checks (the list shape, a genuine failure, a session run printed as before, a script with no
  truth, odd shapes, the later-retrieval case).
- **Single-site mutants** (`python $S/mutants.py <worktree>`, `$S/mutants.txt`; every anchor asserted to
  occur once, CRLF kept): **42 mutants, 42 caught, 0 survive**. One per guard and cleaning step: the title guard (in the sentence
  test and in the LINKED/source checks; given no titles; any word for every word; the "v" discard; titles
  from this turn only; titles shared, not copied, across turns; titles never collected), anchoring (always,
  never, never computed, computed after the answer), F1-F4 (each removed; the bracket-free gap; "v" as any
  word; any word of the second party; the closing bracket), the party cleaning (stop words, short words,
  `parties` ignored, the label's citation and trailing bracket, every bracket removed), `citations` ignored,
  the old every-match-full behaviour, the nested link label (the nested pair removed; the LINKED test back
  on `MD_LINK`); `negcurrency`'s shape reader (old reader, wrong key, the non-list guard); both `corpus`
  labels; `commencements` (the old filter, the export label missing or on every run, the verdict and the
  truth read from the session id). Nine survived the first run (a full form shadowing the guard, the "v"
  discard, earlier-turn titles, `parties`, the trailing bracket, `_P322OocMention`'s redundant anchoring
  test, "v" as any word, any word of party B, a number in `results`); a test was added for each, and the
  redundant anchoring parameter was removed from `_P322OocMention` (every classified sentence is anchored, so
  that mutant was equivalent).
- **Full suite on `lexchat_test_e`: 2811 passed** (2783 + 28), run alone after the last code change.
- **Data handling:** every staged diff screened with `$S/matter_grep.py` (batch 9 E's: case names, topic
  words, session instrument ids, citations outside 1899-1902) and a session-id grep: 0 hits at each commit.

## 9. What I did NOT do

- No product code; no model call, server, replay or external call.
- No edit to FIX_PLAN, SESSION_LOG, the tracker, CHANGELOG, CLAUDE.md, any rubric, the lawyer pack or memory.
- No edit to `sched_clause_class`, `depth` or anything that reads A's block (section 6).
- Not fixed: the definitional `negcurrency` false positive; `commencements`' title-blind scope.
- Not pushed, not merged.

## 10. Decisions for the user (or the integrator)

1. **P3.12's re-run (6335 n=3, Conversational as recorded).**
   1. **(Recommended) Run it after A's merge with `--max-spend 1.90`** ($1.72 at the recorded median, $1.83
      at the maximum): 3 x the recorded maximum, the brief's basis; A's lever moves turn 7 by cents.
   2. Run it with `--max-spend 2.00`, if A's bound puts tens of thousands of verbatim characters in the
      Worker's context.
   3. Defer it until A's wording is approved and a seam probe shows the Worker reads the new block.
2. **`wave4_b9_sweep2a` 6359 r3 t7 is now an item-3 FAIL (LINKED).**
   1. **(Recommended) Record it on P3.22's row as a second genuine item-3 failure in the after-column**,
      with the corrected count (sweep 1: 0 genuine; sweep 2a: 2), since the before-column has none of this
      shape.
   2. Re-read it by hand before recording (the link points at the carrier, which does cite the key case,
      so one could call the label a mis-link rather than a claim to have read the key case).
3. **`commencements`' scope and a question naming the instrument by title.**
   1. **(Recommended) Leave the scope test, and read export t7 (and full-session t7) by hand**: a fix moves
      before-column rows in every full-session 6409 directory, for a turn that is not P3.5's question.
   2. Extend `_names_instrument` to the instrument's title (from `COMMENCEMENT_TRUTH` or the turn's
      retrieval), with an identity run listing every row that leaves scope.
4. **The rubric's new optional keys.**
   1. **(Recommended) Leave `p322.json` as it is:** the label-derived parties give the verdicts above.
   2. Add `parties` and `citations` to its three out-of-corpus entries, making the full forms explicit
      (the integrator's edit; then re-run `auth_parts.py`).

## Commits

- `3af296c` the surname fix, `negcurrency`'s shape, the `corpus` labels, `commencements` on scripts, tests.
- `bed806b` the nested-bracket link label (the coordinator's extra item), and its test.
- `57c45c9` this note; the follow-up below in the commit after it.

## Follow-up (integrator)

**The gap.** One of the integrator's four mutants survived all 28 tests. It changed
`_p322_is_cited_judgment`'s `if not words: return False` to `return True`. Under it, a match with no letters
other than "v" counts as a cited, retrieved judgment, so the mention is discarded whether or not the sentence
cites anything. F1-F3 as built always carry letters, but a rubric's `citations` and `mention` are arbitrary
text, so the guard can be reached. The other three were caught (anchoring kept to this answer only; the title
guard applied to an uncited retrieved judgment; the nested-label bound cut to 3).

**Closed** with `test_a_match_with_no_letters_is_never_a_cited_judgment`. A rubric whose `citations` holds
the digits-only "[1899] 52", named in a sentence citing no judgment, with and without a retrieved title in
play, must name the authority in full. The test also checks the function directly on that match and on a
bare " v ".

**Mutants:** the integrator's mutant was added as A30 in `$S/mutants.py`, run on the scratch copy `$S/rev/`,
never the worktree. **43 mutants, 0 survive; A30 is caught (1 test fails).** The build passes 29 of 29. The
full revert now fails 21 of 29.

**Tests:** 29 in the file. **Full suite on `lexchat_test_e`: 2812 passed.** `TEST_DATABASE_URL` was set on
every run.
