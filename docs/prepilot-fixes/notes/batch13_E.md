# Parallel batch 13, agent E: P3.46 (P2)

**Base.** My worktree came up on `main` (`a6b4a76`) with no commits of mine; I ran `git reset --hard 1889abb`
before anything else. This note is based on `1889abb`. No unexpected commit appeared on the branch while I worked.

**Branch** `worktree-agent-ad9d229ff341d2750`, three commits on `1889abb`:

| Commit | What |
|---|---|
| `b94ca55` | feat: the not-returned note in `search_case_law`'s result |
| `9e7a383` | test: mutants close four untested guards; two redundant checks removed |
| `3f91133` | tools: `authorities` reads the first statement and the back-reference |

**Spend $0. Live calls 0** (no model call, no external host). Full suite on `lexchat_test_e`: **3,459 passed**
(`cd server_py; TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_e python -m pytest -q`;
3,379 at the base, +64 in `test_named_case.py`, +16 in `test_authorities_first_statement.py`).

**The built shape, where it differs from the brief.** (1) The note is written by code in `caselaw.py` and wired in
`agent_shared.run_worker_tool`, not in `executor.py`: `run_worker_tool` is where every other case-law note is
composed, after summarisation, so the summariser never sees or drops it. (2) It also handles the Scottish list
(P3.20), so it reads correctly when `SCTS_CASELAW_ENABLED` is on. (3) A case named **by a law report alone** is never
called missing (neither database lists judgments by law report): it gets its own wording, "cannot be matched". The
user should look at that class (decision 2).

---

## 1. The note (`server_py/src/agent/tools/caselaw.py`, `server_py/src/agent/agent_shared.py`)

### 1.1 What changed, function by function

- **New in `caselaw.py`:** `named_cases(query)` (the cases a query names), `case_returned(case, rows)`,
  `named_case_note(args, data)`, the constants `NAMED_CASE_FCL`, `NAMED_CASE_SCTS`, `NAMED_CASE_BOTH`, and helpers
  `_named_words`, `_is_name_token`, `_side`, `_ncn_key`, `_url_ncn_key`, `_shown`, `_row_ncn_keys`,
  `_row_title_words`, `_join`, `_not_among`; regexes `_NAMED_NCN_RX`, `_NAMED_URL_RX`, `_NAMED_REPORT_RX`,
  `_NAMED_TOKEN_RX`. Appended at the end of the file; no existing function touched. `scts.py` untouched.
- **Changed in `agent_shared.py`:** `run_worker_tool` only, one block after the two case-law branches:
  `case_law_note = named_case_note(args, result) + case_law_note` for every `search_case_law` result, and an import.
  Prepended, so the imperative (MANDATORY NEXT STEP, or the zero note's stop rule) stays last (P2.2's order). No
  other agent's section names `run_worker_tool`'s case-law block; A's summary seam and D's lookup-title wrapper are
  elsewhere in the same function (merge note for the integrator).

**What it detects.** A case is named as "A v B" with capitalised parties (quotes, a citation, a lower-case word, a
colon or semicolon end a party; "and", "of", "&" and the like join one; two names in one query are split at the
last "and", "or" or comma between their "v"s), by a neutral citation (E&W, UK, Scottish incl. P3.20's forms, NI),
or by a law report (bracketed year, volume, series, page; or "1901 SLT 7"). A citation directly after a name (only a
space or comma between) is that case's.

**What counts as returned (it errs towards "returned").** A result whose title carries a distinctive word of each
party (a party with none, "R" or "Secretary of State for the Home Department", is not required; generic, corporate
and short all-capitals words are not distinctive), or a result carrying the neutral citation in its `ncn`, its title
or its Find Case Law URL (the Court of Appeal's division counts; the High Court's and the tribunals' do not). Find
Case Law's list counts only if it ran (no `error`); the Scottish list only if its block says `ok`.

### 1.2 Measure: the dry run with the BUILT code over every stored call

`cd server_py; python ../docs/prepilot-fixes/evidence/seam/batch13/E/p346_dryrun.py C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay <out>`
(the script asserts it imports this worktree's code; it counts all 70 directories present on 2026-10-09):

- **1,682 `search_case_law` calls**; 4 raw results not JSON; 1,611 name no case; **67 name a case**.
- **54 get the note**: 48 with a case not returned (51 named cases; 15 of the 48 calls returned 0 rows) and 6
  naming a law report alone (all 6343). **13 get none**, every named case returned (10 by name, one of them with its citation; 3 by
  neutral citation alone).
- By session: 6359 29 notes (8 none), 6363 10 (1 none), 6343 9 (1 none), 6346 6 (3 none). 31 distinct (query,
  rows) tuples. **Every one of the 67 lines read** (`E/p346_dryrun.txt`, gitignored: queries name cases).
- **Both ways.** `E/p346_titles.py` prints, for each distinct not-returned case with rows (13), every result title
  sharing any word with it: the only near misses share one party's surname and are other cases (correctly not
  returned); the 50-row searches naming a neutral citation were checked by URL (the judgment absent, and present in
  another search's results, which the dry run counts as returned). **No false "not returned" found.** Every 6359 instance of
  batch 12 E's hand-read followed a search that now gets the note.
- **Forms no stored run contains**, tested on synthetic input in `test_named_case.py`: any call naming a case with
  the Scottish list present (none stored), a law report beside a name or alone in Scottish form, two or three names
  in one query, a name split from a citation by a word or semicolon, a citation before a name, lower case,
  capitals throughout, "In re", anonymised "A v B", every neutral-citation court family, a Find Case Law error with
  the Scottish list ok, SCTS capped.
- Re-run after the mutant fixes (commit 2): byte-identical output.

### 1.3 The wording (to the user before merge), rendered by the BUILT code for every value class

`cd server_py; python ../docs/prepilot-fixes/evidence/seam/batch13/E/p346_render.py <out>` (synthetic input).
The note is Worker-facing, in the tool result, in `[SEARCH SCOPE — …]` form with no bracket inside (a citation
is shown in round brackets), so `_TOOL_BLOCK` strips a copy a Worker echoes. **One case named by name**, a page
that is not the whole matching set (the template every other class varies):

> [SEARCH SCOPE — a case this search names is not among its results: none of the 50 judgments it returned is Widget
> Co v Example Ltd. That is all it shows: the judgment may well exist, Find Case Law may hold it among the matching
> judgments not shown or under words this search did not use, and it is no sign that the name or citation is wrong.
> Unless another search returns it and you retrieve it, its text has not been read: do not state what it decided as
> though you had read it. Say instead that it was not among the judgments returned, or attribute what you say about
> it to a retrieved judgment that cites it, and name that judgment.]

The variants (only the changed sentence shown):

| Class | Opening sentence | Other change |
|---|---|---|
| Name, whole set (2 of 2) | "…: none of the 2 judgments it returned is Widget Co v Example Ltd." | "Find Case Law may hold it under words this search did not use" (no "not shown") |
| Name, 1 result | "…: the 1 judgment it returned is not Widget Co v Example Ltd." | as whole set |
| Name, 0 results | "this search returned 0 judgments, so a case it names is not among them: Widget Co v Example Ltd." | as whole set |
| Neutral citation alone | "…: the 1 judgment it returned is not the judgment cited as (1901) UKSC 9." | |
| Name and neutral citation | "… is not Widget Co v Example Ltd (1901) UKSC 9." | either decides "returned" |
| Name and law report | "… is not Widget Co v Example Ltd (1901) AC 9." | the name decides |
| **Law report alone** | "this search names a law report, (1901) AC 9, which cannot be matched to its results: Find Case Law lists judgments by title and neutral citation, not by law report, so none of the judgments returned is shown to be the case reported there." | "Unless a judgment you retrieve proves to be that case, do not state what it decided as though you had read it. Say instead that it could not be matched to the judgments returned, or …" |
| Two not returned | "cases this search names are not among its results: none of the 2 judgments it returned is Widget Co v Example Ltd or Gizmo v Sprocket." | plural throughout: "the judgments may well exist … them … the names or citations are wrong … their text … they … them" |
| Two, 0 results | "this search returned 0 judgments, so the cases it names are not among them: Widget v Example and Gizmo v Sprocket." | plural |
| Two, 1 result | "… the 1 judgment it returned is neither Widget v Example nor Gizmo v Sprocket." | plural |
| Three, 1 result | "… is none of Widget v Example, Gizmo v Sprocket or Ratchet v Pawl." | plural |
| One returned, one not | names only the one not returned | singular |
| Name missing plus a law report | the name's sentence, then "This search also names a law report, (1902) QB 7, which cannot be matched …" | "Say instead that they were not among, or could not be matched to, the judgments returned, …" |
| Two law reports | "this search names law reports, (1901) AC 9 and (1902) 1 QB 7, … is shown to be a case reported there." | plural |
| Scottish list on, both ran | as above | "Find Case Law or the Scottish Courts and Tribunals Service's published judgments may hold it …" (with "among the matching judgments not shown" when either list is partial) |
| Scottish list on, Find Case Law errored | counts the Scottish rows only | "the Scottish Courts and Tribunals Service's published judgments may hold it …" |
| Scottish list on, law report | | "Find Case Law or the Scottish Courts and Tribunals Service's published judgments list judgments by title …" |
| SCTS capped or errored | Find Case Law's rows only | "Find Case Law may hold it …" |
| No note | every named case returned; the query names none; Find Case Law errored and no Scottish list ran; any other tool | |

All 21 rendered variants are in `test_named_case.py::_variants` and `E/p346_render.txt`.

**Screened** (`test_every_variant_trips_no_detector`, every variant, sentence by sentence where a detector is):
`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `NEG_LIMITS`, `NEG_TERMS`, `NEGATIVE_EXPLAINED`,
the three halt detectors, `IN_FORCE_CLAIM`, `OPENER_VOCAB`, `SCOTS_CASELAW_GAP`, `_CUR_DISCLOSED`, `SCHED_LIMIT`,
`derivation_claims`, `sched_unit_clauses`, `sched_clause_class`, `_currency_asserted`, `negcurrency_claim`, the
commencement denial pair, "ranked", a bracket inside the block; and the strip removes each one. 0 trips. Words the
draft carried and lost on the screen: "not retrieved" (`NEG_ASSERTED`, `NOT_FOUND`), "no judgments" and "no result"
(`NEG_ASSERTED`), "not proof that … does not exist" (`NEG_BLAMED_INDEX`), "right" and "point" (`OPENER_VOCAB`
matches word prefixes), "did not return" (`NEG_ASSERTED`'s search-did-not-return limb within 50 characters).

### 1.4 Who reads it, and the other code texts that speak of the same case

- **Read by the Worker only** (it is in the tool result). It reaches a lawyer only if a Worker echoes it, and
  `_TOOL_BLOCK` strips that. `worker_scope_block` and the lawyer's footer are unchanged.
- **Graders that read `search_case_law` results** (`authorities`, `caselaw`, `scts`, `discovery`, `commencements`)
  read `raw_result`, or `final_result` only as JSON; the note makes `final_result` non-JSON exactly as the existing
  notes already do. `authorities`' fallback reads `final_result` for citations in square brackets; the note shows
  them in round brackets. No grader is blind to it and none miscounts it.
- **Beside it, consistent:** the window note ("Another judgment that matches can sit outside these N"), the zero
  note and its stop rule, the Scottish notes, the MANDATORY NEXT STEP (read the returned judgments), and the
  footer's `CASE_LAW_ABSENCE_SENTENCE`.
- **Beside it, in tension (decision 3):** `_NOT_HELD_RULE` (research Workers) and its twins in the quick-lookup
  Worker and both Manager prompts say that when "an instrument or case the brief cites is not found (a search that
  does not return it …), report that this index does not hold it". The note says the database may hold it. P2.4's
  half of that rule (never question the citation) is restated in the note; the "does not hold" half is broader
  than one search shows. I did not edit any prompt.
- **P3.45 (agent A):** the note is appended after summarisation, outside the summary and outside the local-cache
  entry, and it names the query's own case. A check that compares a summary's case citations with its raw source
  never sees it; a check run over `final_result` would find the case in the raw result's `query` field.

### 1.5 Tests, revert, mutants

`test_named_case.py` (64 tests): parsing, matching, every variant, the screen, the strip, and the wiring through
`run_worker_tool` (order before the window note and the zero note, the Scottish branch, no note for another tool).
Harness `E/p346_mutants.py` on a scratch copy of `server_py` (control first, it passes): **the full revert removes
396 lines** (`caselaw.py` 388, `agent_shared.py` 8) **and the tests fail** (at import, so single-site mutants
check behaviour); **35 of 35 single-site mutants caught** (every guard and cleaning step: the acronym, length and
stopword filters, both clause breaks, both joiner trims, the split between names, the citation attachment, the
report/citation overlap, the dedupe, both-parties matching, the citation and URL keys, the Court of Appeal division,
the report-only verdict, the error, status and no-search guards, both partial-page tests, bracket cleaning, each
count branch, the say-verb, the database name, and three wiring mutants). The first pass caught 27 of 33: two
survivors were checks no input could reach (removed), four were untested guards (tests added, commit 2).

---

## 2. The grader (`server_py/tools/replay_report.py`, `authorities` only)

**Changed:** `p322_answer_verdict` (new optional `bare` argument; the first-statement rule) and the item-3 loop of
`p322_run`. **New:** `p322_is_bare`, `_P322_BACKREF`, `_P322_BARE_STRIP`. Agent B's `depth` is untouched.

- **First statement.** PASS where any sentence is NOT_HELD, or where the FIRST sentence that says something of the
  authority is SECOND_HAND; LINKED anywhere is FAIL; otherwise EARLIER (an earlier answer of the run passed) or FAIL.
  Before, any SECOND_HAND sentence passed the answer.
- **A bare listing** (a reference-list entry: once the authority's name and any link target are out, no lower-case
  word of four or more letters and no lead word of four or more outside the name) is not a statement and is skipped
  when finding the first; an answer that only lists it is judged on its first listing, as before.
- **The back-reference.** A sentence that names no authority, follows one that does, and carries a demonstrative
  and a rule-word ("this principle", "that test", "the same approach") with a citing word, is a mention, classified
  as usual and marked "a back-reference to the sentence before". It can never be the first statement (unless the
  naming sentence was a bare listing), so it records the tie without saving a holding-first answer.

**Validated against batch 12 E's hand-read, every instance** (`E/auth_vs_hand.py` over
`python -m tools.replay_report --dir <RP>/wave2 authorities --all-dirs --chars 400`; 18 runs, 25 answer-turns; a
turn's verdict is the worst over its authorities, as the hand-read counts it):

| | PASS | EARLIER | FAIL | Agree with the hand-read |
|---|---|---|---|---|
| By hand | 11 | 5 | 9 | |
| Grader at `1889abb` | 14 | 5 | 6 | 22 of 25 |
| **Grader at `3f91133`** | **11** | **5** | **9** | **25 of 25** |

Every verdict that moved (diff of the two outputs, read): the three disagreements, each the holding-first shape
(one 6359 answer; one 6363 Deep Research key-findings bullet; one 6363 case-list entry), and nothing else. The one
back-reference in the stored answers is found and marked (the 6359 twin the hand-read named); 4 bare listings are
marked, every one a reference-list entry after the answer's statements of that authority. **Item 3 now: before-column (`wave4_b9_sweep1`) 1
FAIL, after-column (`wave4_b9_sweep2a`) 3 FAIL, `wave1` 2, `wave2` 3, as the hand-read found.**

**Left as it is:** per authority, one 6363 answer's second authority is PASS by hand and EARLIER by the grader (its
first sentence ends in a colon and the judgment it came through is cited in the list after it); the turn's verdict
is EARLIER either way. The shared `MD_LINK`'s bracket gap (Session 42) is untouched.

**Tests and mutants.** `test_authorities_first_statement.py` (16 tests); two stored tests moved to the new rule,
each saying why: `test_replay_batch9::test_the_answer_verdict_reads_every_sentence_and_the_earlier_answers` (the
holding-first pair now FAILs) and `test_replay_batch10::test_a_short_form_counts_once_named_in_full_in_the_answer_or_earlier`
(its short form before the tie is now the first statement; a tie-first twin added). `E/grader_mutants.py`: control
passes; **the full revert of `replay_report.py` (78 lines added, 8 changed back) fails**; **19 of 19 single-site
mutants caught** after one test was added for the last survivor (a back-reference after a listing).

---

## 3. The acceptance, priced (not run)

P3.46's acceptance: 6359 and 6363 n=3, by hand with the taught grader beside it. Stored per-rep cost on the pinned
Gemini (`python E/p346_price.py <RP>`; 9 stored reps each):

| | min | median | max | n=3 at the median | n=3 at the max |
|---|---|---|---|---|---|
| 6359 (8 turns) | $0.93 | $1.16 | $1.49 | $3.48 | $4.47 |
| 6363 (5 turns) | $1.92 | $2.01 | $4.75 (a Manager runaway, `sweep2a` r1) | $6.03 | about $9.00 (one runaway rep, two at $2.12) |

**About $9.50 healthy, up to about $13.50 with one runaway rep** like `sweep2a`'s (P4.12 now trims a Manager
runaway's retries when a report is in hand, so that ceiling should be lower). Every stored rep ran at the
8,000-character summarisation fallback. Cutting 6359 at turn 7 (its graded turns are 6 and 7) saves about one
turn in eight.

## 4. What I did NOT do

- No model call, seam draw, replay, server or live call. The note's effect on what the Worker writes is unmeasured
  (decision 1).
- No prompt edit (`_NOT_HELD_RULE` and its twins left as they are: decision 3). No change to `scts.py`,
  `executor.py`, `search_scope.py` or the rubric.
- The note does not look at earlier searches in the same run (a case another search already returned still gets the
  note on a search that missed it; the wording is conditional for that reason: "Unless another search returns it").
- No edit to FIX_PLAN, SESSION_LOG, the tracker, CLAUDE.md, CHANGELOG or any memory file.

## 5. Decisions for the user (recommendation first)

1. **The acceptance run (6359 and 6363 n=3).**
   - (a) **Run it after merge, priced at about $9.50 (up to about $13.50), graded by hand and by the taught
     `authorities`**; the bar is the row's (no out-of-collection holding stated as read), which the stored columns
     fail in 9 of 25 answer-turns.
   - (b) First a few `seam_replay worker --as-sent --at-rev recorded --date recorded --max-tokens 32000` draws on a
     stored 6359 turn-6 payload rebuilt with the note (about $0.40 to $1), to see whether the Worker's report changes.
   - (c) Defer.
2. **A case named by a law report alone** (6 stored calls, all one session).
   - (a) **Keep the "cannot be matched" wording** as built: true, and it still tells the Worker not to state the
     holding as read.
   - (b) No note for a law report alone: quieter, and the Worker gets nothing in that case.
3. **The prompts' "say that this index does not hold it"** (`_NOT_HELD_RULE` and three twins), which for a case
   asks more than one search shows and sits beside this note.
   - (a) **Leave the prompts until the acceptance run shows whether the Worker follows the note or the rule**
     (P3.13's lesson: a prompt edit reaches every call).
   - (b) Reword the case half to "say that the searches made did not return it", measured first with a first-round
     probe, as its own row.
4. **The wording itself** (section 1.3).
   - (a) **Approve as built.**
   - (b) Shorten to the first sentence and the "do not state what it decided" sentence (about half the length;
     loses the reasons and the instruction on what to say instead).
5. **The grader's bare-listing rule** (a reference-list entry is not a statement): (a) **keep** (it moves no stored
   verdict, and stops a Deep Research report's case list from deciding a verdict on its own); (b) drop it and judge
   every first mention, listings included.
