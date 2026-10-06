# Parallel batch 8, agent A: P3.27 then P3.12, one build ($0, no external call)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 87ceeff1f3478cec38d9edf6d7010b78d16d8436` (the integrator's
head). This note is based on `87ceeff`. The run was interrupted once when the integrator's session
ended; on resuming I checked `git status` and `git diff --stat` and re-read my uncommitted diff
before going on (the P3.12 work in progress was intact).

**Branch** `worktree-agent-a5655c6d5f4d0102d`, two commits:

- `e2efe78` P3.27: `get_legislation_text` sends `include_schedules`, with a code line naming what
  the text carries;
- `18ac25f` P3.12: code fetches a named schedule or annex unit that a section search left out;
- plus this note (third commit).

**Spend.** $0 in model spend. **No external call of any kind**: every LEX response used below is
one of batch 7 B's saved live payloads (`evidence/seam/batch7/B/raw/`), served through an httpx
`MockTransport`. The full suite was run with `HTTP_PROXY`/`HTTPS_PROXY` set to a closed local port,
so an accidental outbound call would have failed rather than gone out. No server, no replay, no
summariser call (stubbed in the dry runs). Every stored run file used here ran on the pinned
`google/gemini-3.1-pro-preview`; no number comes from `glm-5.2:cloud`.

**Scratch.** Everything is in the gitignored `docs/prepilot-fixes/evidence/seam/batch8/A/`
(`git check-ignore -v` gives `.gitignore:113`). Commands below run from that folder with
`PYTHONIOENCODING=utf-8`. Each script asserts that it imports the worktree's built code; to re-run on
the merged tree, repoint `WT` in the script (do not edit the code paths in place).

---

## 1. P3.27 (commit `e2efe78`)

### 1.1 What changed, and why

- **`executor.py`, the `get_legislation_text` branch.**
  - The call now sends `{"legislation_id": ..., "include_schedules": true}`. That flagged response
    is the result, and its failure path is unchanged (a 404 still returns the same error string, and
    no second call is made).
  - After it succeeds, the same endpoint is called without the flag. Its only use is the boundary:
    one flagged call places it in only 22 of 27 (batch 7 B).
  - **Fail-soft (Invariant 5).** Any failure of the second call (a non-200, a transport error, a
    non-prefix text) keeps the flagged text and leaves the boundary unknown, so the line says less.
  - The second call's `api_call_end` reaches the audit as `{"full_text_chars": N}`, not the text
    again. A large Act's sections are 0.9 MB, and the first call already carries them.
- **New `src/utils/schedule_units.py` (the pure part).**
  - `mark_schedule_boundary` adds two keys to the result (additive): `include_schedules: true` and
    `schedule_text_starts_at` (the unflagged length, or null).
  - `schedules_note` builds the line from the RAW result (P2.3's `enabling_power_note` pattern).
    `run_worker_tool` appends it after summarisation, right after the ENABLING POWER block.
  - Headings are read only in the appended text, at a paragraph start:
    - "SCHEDULE 1A" (a label must carry a digit, so a title word is never read as a label);
    - an unnumbered "SCHEDULE ...", read as "the Schedule";
    - an ordinal heading ("SECOND SCHEDULE");
    - "ANNEX XIV" or a bare "ANNEX";
    - a mixed-case "Schedule 4 Title" only when a capitalised title follows the label, because the
      live texts have "Schedule 1. " ending a sentence.
  - Each label is named once.
- **`search_scope._TOOL_BLOCK`** strips `[SCHEDULES AND ANNEXES — …]`. It does not match the bare
  word: the pattern is case-insensitive, and an answer's citation link can open with "[Schedules 1
  and 2](…)" (a test pins this).
- **Footer: no change.** I decided the lawyer-facing footer need not speak of this, and recorded
  nothing in the scope record, for three reasons:
  - the line is a statement about what the Worker was handed;
  - its one negative ("the index holds no schedule or annex text for X") is already true and
    code-stated where the Worker reads it;
  - a footer change is lawyer-facing and would need the user.

  Decision 2 offers a Manager-facing limb instead.

### 1.2 The exact wording (every variant)

`<id>` is the `legislation_id` argument and `<names>` is the list of headings, joined with commas and
"and". The integrator should read for these words in the hand-read.

1. Headings named:
   `[SCHEDULES AND ANNEXES — this text of <id> carries, after its sections, the schedule and annex
   text the index holds, under these headings: <names>.]`
   - With one heading it says "under this heading".
   - When text with no heading precedes the first heading, it adds: ` Some text with no schedule or
     annex heading comes before the first of them.`
   - After 40 headings it adds "and N more".
2. None held:
   `[SCHEDULES AND ANNEXES — the index holds no schedule or annex text for <id>, so this text is its
   sections only.]`
3. Schedule text with no heading:
   `[SCHEDULES AND ANNEXES — this text of <id> carries, after its sections, further text that the
   index holds as schedule or annex text. It carries no schedule or annex heading.]`
4. Boundary unknown (the second call failed):
   `[SCHEDULES AND ANNEXES — this text of <id> was requested with its schedules and annexes
   included, where the index holds them. Which ones it carries was not checked.]`

**Checks on the wording:**

- All four are screened in `test_footer_trips_no_detector` (seven variants, every detector the test
  holds: passes).
- None carries a square bracket inside the block (`test_every_variant_strips_whole_and_has_no_inner_bracket`:
  passes).

### 1.3 Dry run with the built code

Command: `python dryrun_p327.py [--list]`. The executor branch runs end to end on B's 60 saved
payload pairs through a mocked transport, then `schedules_note` runs on what it returned. The full
listing of every line is in `dryrun_p327_list.txt` (gitignored: it holds instrument ids).

- **Calls.** 60 instruments; 120 calls (60 flagged, 60 unflagged).
- **The result.** In 60 of 60 the text passed on is the flagged text, and the stamped boundary equals
  the unflagged length (asserted in the script).
- **Lines by kind** (every line listed in the scratch file):

  | Kind | Lines |
  |---|---|
  | headings named | 22 |
  | none held | 33 |
  | schedule text with no heading | 5 |

  - The 33 "none held" are exactly B's 33 instruments that do not grow.
  - The 5 "no heading" are B's unheaded repeal table, a salary table, a notice form, an explanatory
    note and an arrangement-of-paragraphs page.
- **Cross-check against batch 6 D's 79 known units.** 78 are named by heading. The 79th is the
  malformed provision URL, whose text sits in a "no heading" line.
  - The script's own count says 75. Its naming check spells the 1891 Act's three ordinal units
    "Schedule First", and the line names them "the First Schedule"; they are the same three units.
- **Cross-check against the 16 saved section-lookup payloads.**
  - The line names no schedule that the lookup lacks.
  - One lookup row the line does not name (an SI's Schedule 8) has empty text in the lookup itself.
    So the line is right that the text carries none.
- **The second call failing**, simulated with a 503 on all 60: one variant, line 4, 60 times. The
  flagged text is kept in every case.
- **Summariser input over B's 419 stored non-memo reads:**

  | Measure | Before | After | Ratio |
  |---|---|---|---|
  | B's measure (`full_text` characters, threshold 8,000) | 10,307,667 | 20,207,402 | ×1.96 |
  | 150K chunks (B's measure) | 174 | 227 | |
  | The string `run_worker_tool` actually summarises (the built executor's JSON output) | 10,854,170 | 21,070,138 | ×1.94 |

  - B's ×1.96 is reproduced exactly.
  - On the executor's own string, 15 reads move from verbatim to summarised (B counted 4 on
    `full_text` length).

### 1.4 Tests (`tests/test_schedules.py`, P3.27 part, plus the screen)

The tests cover:

- the executor sends the flag and makes the unflagged call, in that order;
- a failed second call (a 503, a timeout) keeps the text and the line says less;
- a failed flagged call fails exactly as before, with no second call;
- each line case: numbered, ordinal, unnumbered, annex, none held, no heading, lead text, mixed-case
  heading against a cross-reference, a heading inside the sections not read, a repeated label named
  once, boundary unknown, silence on an error;
- the strip, and the citation link left alone;
- the boundary stamp is additive and never guesses;
- the line reaches what the Worker receives after summarisation.

**Revert:** restoring the three product files to `87ceeff` and deleting the new module removes
**302 lines**, and the test file fails at collection (the module import).

**Single-site mutants** (`python mutants.py spec_p327.json`, `mutants_p327.txt`): **13 mutants, each
fails 1 to 4 tests.** They are:

1. no flag;
2. the second call skipped;
3. its body ignored;
4. the line not appended;
5. no prefix check;
6. the none-held branch off;
7. the strip not widened;
8. the strip widened to the bare word;
9. the mixed-case heading without a title;
10. no mixed-case heading;
11. a label that needs no digit;
12. no dedupe;
13. the boundary ignored by the line.

Two mutants (9 and 11) first survived. I tightened the two tests (a cross-reference to a label not
otherwise present; a short title word), and both now fail.

---

## 2. P3.12 (commit `18ac25f`)

### 2.1 What changed, and why

- **The trigger** (`schedule_units.named_units`, `unit_in_results`). It fires on a
  `search_legislation_sections` query that names:
  - "Schedule X" (with or without a paragraph, a Part or a chapter), or
  - "Annex X" (with or without a chapter).

  The word is case-insensitive and the label is not, so "schedules to the Act" names nothing.

  A paragraph number (or Part) is attached only when the query names exactly one schedule, and an
  annex chapter only when it names one annex. The trigger fires when a named unit is missing from
  the results.
  - Matching is by the row's `url`, or `uri`/`id` for pre-P1.4 raw lists.
  - An instrument's only, unnumbered `/schedule` answers "Schedule 1".
  - It does nothing when the result is not a row list: an error, or a budget refusal.
- **The route** (`agent_shared.schedule_route_block`, called from `run_worker_tool` after the
  result's own summarisation, fail-soft).
  - It calls the new `executor.fetch_provision_list`: `/legislation/section/lookup` with
    `limit: 5000`.
  - That is one call per instrument per worker run (a per-run `provision_fetches` dict that
    `agent_core.run_worker_agent` creates), and at most 5 instruments a run (`MAX_ROUTED_LOOKUPS`,
    P3.7's bound).
  - It picks the unit by `uri` and cuts it (`schedule_units.cut_pieces`):
    - an annex chapter by `cut_annex`;
    - a schedule paragraph by `cut_schedule_paragraph`: clean only where its `Section N)` line is
      unique and the next headed paragraph is N+1 (or a lettered insert); otherwise labelled with
      the paragraphs it runs through, or "to its end";
    - a paragraph with no single heading line sends the whole schedule;
    - anything else is the whole unit.
  - Anything over the verbatim threshold, or over the worker's context budget, is summarised for the
    query (`summarise_for_query`, P1.6's pattern).
  - On a failed list, it calls `executor.fetch_text_with_schedules` (P3.27's flag) and cuts at the
    unit's heading (`cut_unit_from_text`). If that also fails, a line says the question is open.
  - The unit's URL is added to `retrieved_urls`, so a link to it survives the provision-link
    enforcement.
  - Both calls emit `api_call_*` events on the section search's own `on_chunk`, so the audit puts
    them under that tool, with a size and not the payload.
- **It runs for both Workers.** It hangs off `search_legislation_sections`, which both have, and
  `agent_core` passes the dict to every legislation Worker. `test_both_workers_reach_the_route` runs
  `run_worker_agent` under `conversational` (and asserts that P3.25's code lookup ran, so the
  quick-lookup path really was taken) and under `research`.
- **`cut_annex` moved into product code.** It is in `schedule_units`, unchanged. The dev tool's
  `provision_hints._cut_annex(text, ref)` now delegates to it.
  - `test_provision_hints.py` passes.
  - Product, pre-move function and delegate agree on 216 of 216 annex, chapter and section cases
    over the saved annexes (`python cut_check.py`, part 3).
- **`search_scope`** strips the block whole (`_FETCHED_BLOCK`, like the outline, because the body is
  statutory text and may hold a bracket), and `_TOOL_BLOCK` strips any stray header or closer.

### 2.2 The exact wording (every variant)

`<U>` is the unit ("Schedule B1", "Annex XIV"), `<id>` the instrument and `<url>` LEX's `uri`.

**Block header**, `[PROVISION FETCHED BY CODE — <lead><tail>]`, followed by the pieces and then
`[/PROVISION FETCHED BY CODE]`.

- **Lead**, from the provision list:
  `the index holds <U> of <id> as one provision (url: <url>). This search's results left it out, so
  code fetched it from the index's provision list.`
- **Lead**, from the fallback:
  `the index's provision list for <id> did not come back, so code cut <U> out of the instrument's
  whole text with its schedules, at its heading and the next schedule or annex heading.`
- **Tail**, cut: ` Below is the part of it this search named, labelled.`
- **Tail**, whole: ` Below is the whole of <U>.`
- **Tail**, summarised: ` Below is <U> summarised for this research question, because it runs to
  <N> characters. The summary is not the statutory text: quote the provision only from retrieved
  text.`
- **Reason**, added after the tail when a sub-unit was not cut:
  - `Paragraph <p> has no single heading of its own in it to cut at.`
  - `Paragraphs <list> have no single heading of their own in it to cut at.`
  - `It carries no heading for Chapter <C> to cut at.`

**Piece labels** (plain sentences, before each cut):

- `Paragraph <p> of <U>, cut at its own heading and the next one:`
- `The text of <U> from the heading of paragraph <p> to the next headed paragraph. It runs through
  paragraphs <p> to <t>, because the paragraphs after <p> in it carry no heading of their own:`
- `The text of <U> from the heading of paragraph <p> to the next headed paragraph, which may hold
  more than paragraph <p>:`
- `The text of <U> from the heading of paragraph <p> to its end, which may hold later paragraphs that
  carry no heading of their own:`
- `Chapter <C> of <U>, cut at its heading and the next chapter's heading:`

**Lines** (no body):

- `[PROVISION FETCHED BY CODE — the index holds <n> provisions for <id>, and its schedules and
  annexes among them are <list>: <U> is not one of them. This search's results left it out for that
  reason.]`
  - When the list holds none, the middle clause reads `and none of them is a schedule or an annex`.
- `[PROVISION FETCHED BY CODE — whether the index holds <U> of <id> is open: code fetched only the
  first <n> provisions of its list, and <U> was not among them.]`
- `[PROVISION FETCHED BY CODE — the index lists <U> of <id> as a provision and holds no text for
  it.]`
- `[PROVISION FETCHED BY CODE — the index holds <id> without its provision text, so it holds none for
  <U> either.]`
- `[PROVISION FETCHED BY CODE — the index's provision list for <id> did not come back, so code could
  fetch <U> neither from it nor from the whole text. Whether the index holds <U> is open: do not
  report it as absent.]`

**Checks on the wording:**

- Every header, label and line is in `test_footer_trips_no_detector` (26 texts, all detectors:
  passes).
- One draft tripped `NEG_ASSERTED` and was reworded: "the index holds no provision text for <id>".
  The screen caught it.
- Several sentences put "index" before "not" on purpose. `NEG_BLAMED_INDEX` reads a "not" followed
  within 100 characters by "index", so "this search did not return <U>, which the index holds" was
  rejected before it was written.

**What the integrator should read for in the hand-read:**

- whether a Worker quotes a cut paragraph as the provision (wanted), or quotes a SUMMARY as
  statutory text (the tail forbids it);
- whether the answer on P3.2's control turn still calls the annex not held or not retrievable;
- on 6374, whether "the index holds 3 provisions … none of them is a schedule" reaches the answer
  as an index fact and not as a search limit.

### 2.3 Dry runs with the built code

**The trigger.**

Command: `python trigger_p312.py [--exclude-new] [--list]`. The output is `trigger_p312.txt`, and
the disagreements with their queries are in `trigger_disagree.txt` (gitignored: matter text).

- **Coverage.** 5,128 stored section searches with `wave4_b7_p324` excluded (B's and D's count),
  5,149 with it. The firing counts are identical either way.
- **Built trigger.** It fires on **178 calls on 12 instruments**. Of those, 115 calls on 3
  instruments name a sub-unit and 63 name the unit alone; 22 of the 178 are memo hits.
  - By chat mode: conversational 97, research 66, Deep Research 15.
  - B's figures from D's detector were 124 calls on 5 instruments for a sub-unit, and 163 calls on 16
    counting schedule-only queries.
- **Every disagreement read.** There are 49, and each verdict is the built trigger's:
  - **17 that D's detector fires on and the built trigger does not.**
    - 11 are pre-P1.4 raw-list results that did carry the unit under `uri`: D's detector reads only
      `url`, and one is a sole unnumbered schedule.
    - 6 are budget refusals, where no search ran (`trigger_donly.py`).
  - **32 that the built trigger fires on and D's does not.**
    - 31 are "Annex X" queries with no chapter. D has no annex-only class; the brief includes it.
    - 1 names two schedules, and only the second is missing: D reads only the first label.
- **Must not fire.** In 117 calls a named unit was already in the results. The route's output there
  is empty in all 117 (`dryrun_p312.py`), and in 6 calls it does nothing on a refused or errored
  result.

**The route.**

Command: `python dryrun_p312.py [--list] [--blocks]`. Every stored call is passed through
`schedule_route_block` exactly as `run_worker_tool` passes it, with the built
`fetch_provision_list` served B's saved lookups. The summariser is stubbed, the threshold is 8,000,
and the context budget is not modelled. The output is `dryrun_p312.txt`, `dryrun_p312_list.txt`
(every firing call: keys, unit, outcome) and `dryrun_p312_blocks.txt` (all 31 distinct blocks;
gitignored).

- **156 firing calls** (plus the 22 memo hits, which in the product return the first call's block).
- **Mock calls served:** 84 `/section/lookup` (one per instrument per delegation) and 1
  `/legislation/text`.
- **The one instrument without a saved lookup** is 1 call. It was served a 503, so it exercises the
  fallback and the failure line: "fetch failed". It is counted, not hidden.
- **Outcomes:**

  | Outcome | Calls |
  |---|---|
  | paragraph cut (all on P3.12's turn) | 45 |
  | annex chapter cut (on P3.2's session) | 39 |
  | whole verbatim | 1 |
  | summarised whole unit | 66 |
  | summarised because a named paragraph has no single heading | 1 |
  | unit absent, complete list | 3 |
  | fetch failed | 1 |

  - The 66 summarised whole units are mostly "Annex XIV" with no chapter (89,133 characters), or a
    schedule named alone.
  - Of the 3 "unit absent", one is on 6374's Order: 3 provisions, none a schedule. That is true,
    confirmed live by batch 7 B.
- **Summariser calls the route would make:** 70, with inputs from 8,102 to 92,066 characters.
- **Every block strips whole from an answer:** 156 of 156.
- **Per turn.**
  - P3.12's turn 7: 45 paragraph cuts and 11 summaries (queries naming Schedule B1 with no
    paragraph).
  - P3.2's control turn (run turn 4) across the `p32_6406` directories: 16 chapter cuts and 9
    summaries (queries naming the annex with no chapter).

**The cuts against the ground truth** (`python cut_check.py`):

- P3.12's three paragraphs come out at 733, 1,450 and 1,935 characters, **byte-equal to batch 7 B's
  `p312_truth.txt`**.
- P3.2's control chapter comes out at 2,494 characters, byte-equal to `p32_control_truth.txt`.
- Over the 133 saved live schedules (lookup payloads only, so not B's 134-schedule set), the 311
  `Section N)` paragraphs give: 246 clean, 34 span-labelled, 29 to the end, 2 no unique heading.

### 2.4 Tests (`tests/test_schedules.py`, P3.12 part, plus the screen)

- **Trigger:** every query form; present, missing, error and sole-schedule results; does not fire on
  a present unit, a section query, an errored result, the route disabled, or another tool; memoised
  once per run; bounded per run.
- **Cuts:** clean paragraph (and its URL counted as retrieved); a heading met twice not cut; a
  swallowing span labelled; to the end; annex chapter; no marker verbatim, and summarised over the
  threshold; summarised over the context budget.
- **Lines:** absent from a complete list (with and without schedules); a list cut short; a unit
  listed without text; an instrument without text; the fallback to the whole text with schedules;
  both failing.
- **Strip and route:** every block strips whole, with no inner header bracket (a bracket in the body
  included); both Workers reach the route through `run_worker_agent`; a failing route leaves the
  search result as it was.

**Revert:** restoring the six files to `e2efe78` removes **728 lines**, and 21 tests fail.

**Single-site mutants** (`spec_p312.json`, `mutants_p312.txt`): **20 mutants, each fails 1 to 3
tests.** They are:

1. the block not appended;
2. agent_core passes no dict;
3. fires when the unit is present;
4. no memo;
5. no bound;
6. a swallowing cut called clean;
7. uniqueness not required;
8. the annex chapter not cut;
9. never summarised;
10. the budget ignored;
11. an open list called complete;
12. the sole schedule unmatched;
13. no text fallback;
14. the strip not widened;
15. the label case-insensitive;
16. paragraphs attached with two schedules;
17. the URL not harvested;
18. `limit: 1`;
19. "No sections found" read as a failure;
20. the route failing hard.

Mutant 20 first survived; I added `test_a_failing_route_leaves_the_section_search_as_it_was`, and it
now fails.

**Gaps the integrator's review found, now closed** (follow-up commit). Two of the integrator's three
single-site mutants in `schedule_units.py` survived the tests:

- `cut_unit_from_text` with `!= 1` changed to `< 1` (a heading met twice cut at the first);
- `_clean` without its bracket replacement.

I added two tests:

- `test_a_heading_met_twice_in_the_whole_text_is_not_cut`: a contents line plus the schedule, so
  the fallback returns nothing and the line says the question is open;
- `test_a_bracket_in_the_id_or_url_never_reaches_a_header`: a bracket in the `legislation_id` and in
  the `uri`, across every block and line builder, with the header bracket-free and the strip whole.

**The second test exposed a real defect, and I fixed it.** `unit_absent_line` built its "schedules
and annexes among them" list from LEX's uris without cleaning them. A bracket in a uri would reach
the header and end `_TOOL_BLOCK`'s match early. The labels now pass through `_clean` too, which is
the one product change in this commit.

**Mutants** (`spec_review.json`, `mutants_review.txt`): each fails exactly 1 test, and the tests pass
without them.

| Mutant | Fails |
|---|---|
| the integrator's (1) | the heading-twice test |
| the integrator's (2) | the bracket test |
| my inventory fix reverted | the bracket test |
| the integrator's third (`through = nn`) | `test_a_paragraph_whose_cut_swallows_the_next_is_labelled`, as reported |

**Full suite** on `lexchat_test_a`, with outbound HTTP blocked:

- after commit 1: **2357 passed**;
- after commit 2: **2377 passed** (base 2339);
- after the review follow-up: **2379 passed**.

---

## 3. What the build moves in the graders and the tooling (checked, not edited)

- **`replay_report negcurrency`** reads `get_legislation_text`'s `full_text` for commencement
  wording (`_nc_cmc`).
  - With schedules appended, a commencement schedule's words now count as the instrument's own
    evidence. One SI's schedules are titled "PROVISIONS OF THE ACT WHICH COME INTO FORCE ON ...".
  - That is real text, and the after-column may differ from the before-column for that reason.
- **`replay_report corpus`'s leak check** (`cmd_corpus`, around line 5507) lists the tool-block
  markers it looks for in answers. It does not know `[SCHEDULES AND ANNEXES` or
  `[PROVISION FETCHED BY CODE`, so a leak of either would be invisible there. **A grader change is
  needed and I did not make it** (A must not edit `replay_report.py`).
- **`summary_probe glosses`** cuts `final_result` at the first code-appended block (`\n\n[` plus
  capitals). So both new blocks are correctly excluded from the summariser's own text.
  - The route's own summary of a large unit sits inside the PROVISION FETCHED BY CODE block. It is
    therefore not probed for glosses either: a gap, not a false hit.
- **`seam_replay`** rebuilds only `summarised_result_blocks` from a stored raw result. A stored
  payload predates both changes, and the seam neither redraws the P3.27 line nor fetches a unit.
  A Worker-seam probe of these changes needs a fresh after-column.
- **The rest.** The audit's `raw_result` for a whole-text read gains the two keys. `record_currency`,
  `_recital_in` and `enabling_power_note` read the same fields as before, and their suite tests
  pass.

## 4. What I did NOT do

- No live call to LEX or any host, no model call, no replay, no server. The route's summaries and
  the Worker's reading of the line are unmeasured: that is the sweep.
- I did not edit FIX_PLAN, SESSION_LOG, the tracker, CLAUDE.md, the CHANGELOG, `DEPTH_TRUTH`, a
  rubric, `replay_report.py` or any memory file.
- I did not build:
  - a footer or scope-record change;
  - a size bound on the flag (the user's decision: none at first);
  - the trigger extension in decision 1.
- `plan_status` and `plan_lint` were not run, because nothing they read changed.

## 5. Decisions for the user

1. **The 6374 guard: extend P3.12's trigger to an unlabelled "Schedule".**

   Measured (`trigger_p312` variant, run inline): on 6374's Order, 82 section searches name the
   word "schedule" and **81 carry no label**, so the route fires on 1. Corpus-wide, 105 section
   searches name an unlabelled "schedule" and get no schedule row back, **104 of them in 6374's
   session**.

   P3.27's line covers the research Worker's 81 whole-text reads of that Order: "the index holds no
   schedule or annex text". But P3.25 removed the whole text from the quick-lookup Worker, so on a
   conversational 6374 turn the true negative still rests on the Worker's own words.

   1. **(Recommended) Extend the trigger to "the Schedule" with no label,** acting only where the
      provision list holds no schedule row ("none of them is a schedule": a code-stated true
      negative) or exactly one (hand it over, as for "Schedule 1"). It is one small commit with its
      own dry run, and it makes the guard code-stated in both modes.
   2. **Leave it.** The sweep shows whether the Worker carries the negative unaided on the
      conversational turns.
2. **A Manager-facing limb for P3.27.** The line is Worker-facing; batch 7 B found the report right
   and the answer wrong on two P3.2 turns.
   1. **(Recommended) Wait for the sweep.** Add a limb to `worker_scope_block` (stripped, never
      lawyer-facing) only if the answers still paraphrase "not included" as "unable to retrieve".
   2. **Add it now**, so that the sweep measures both seams at once.
3. **The grader leak list.**
   1. **(Recommended) The integrator adds `[SCHEDULES AND ANNEXES` and `[PROVISION FETCHED BY CODE`
      to `cmd_corpus`'s marker list** before grading the sweep, in one line.
   2. **Rely on `strip_scope_blocks`** and its tests alone.
4. **The second call's audit response is a size, not the text** (`full_text_chars`); the same holds
   for the route's lookup (`provisions`).
   1. **(Recommended) Keep it so.** The eval harness gets the flagged text once, and the route's
      lookup can be 1.6 MB.
   2. **Emit the full bodies,** like every other call, at the cost of trace size.
