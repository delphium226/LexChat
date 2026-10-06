# Parallel batch 9, agent B: P3.22 built (case-law results by relevance)

Branch `worktree-agent-a5e4f7e6a425a1119`. **$0 model spend**: no model call of any kind, no
server, no replay pin, run or restore. **10 live GETs to the National Archives**
(`caselaw.nationalarchives.gov.uk` only; the user agreed at launch to up to 20, at least 0.35 s
apart), every one through one door (`$B/tna_b9.py`) that enforces the cap of 20, a 0.5 s minimum gap
after the previous call ended and the host, and logs method, URL, status and bytes to
`$B/tna_calls_b9.jsonl`. Measured from the log: 10 calls, all `GET`, all 200, one host, minimum gap
0.500 s, 473,676 bytes, 11.1 s end to end. No other host. The run was not interrupted.

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-8. With no commits of my own I
ran `git reset --hard ca3d45ca0e4705123aa23ed0c7fc0c1ab9a77918` first. Everything here is based on
`ca3d45c` (`<INTEGRATOR_HEAD>`).

`$B` is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch9/B/` in the worktree
(`git check-ignore -v`: `.gitignore:113`, `docs/prepilot-fixes/evidence/seam/`), copied at the end to
the main checkout's same path. `SP` is this worktree's `server_py`, `R` is
`C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `C8` is batch 8 C's scratch
`C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch8/C`. Every command runs with
`PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b`.

**Commits:** `82394b7` (the build, one commit: params, note flip, probe, tests), `90360d8` (tests
only: each guard of the probe's count and dates checks, found by a surviving mutant), and this note.

**Tests: 2498 passed** on `lexchat_test_b` (2482 at base + 16), `cd SP && python -m pytest -q -p
no:cacheprovider`, run after the last code change (`$B/pytest_full.out`).

---

## 1. What I built, and why. BUILT

As decided (FIX_PLAN P3.22, Session 40): the feed's default order is `-date`, so every case-law search
handed the model the 50 newest matches, and the Phase-2 nudge's "most relevant" first three were the
three newest.

- **`caselaw.py`**: new `CASE_LAW_ORDER_PARAMS = {"order": "relevance", "per_page":
  str(CASE_LAW_PAGE_SIZE)}` with a comment block: `order=relevance` is the advanced search's sort and
  is NOT in the published spec (`public_api.yml` v0.6.0: `date`, `updated`, `transformation`, default
  `-date`), re-checked live by `tools/caselaw_probe.check_order`; any explicit `order` resets the page
  to 10 rows without `per_page`; `last` still counts at ten a page, so `case_law_count` is unchanged.
  `CASE_LAW_PAGE_SIZE`'s comment no longer says "we send no `per_page`".
- **`executor.py`** (`search_case_law` branch): `params.update(CASE_LAW_ORDER_PARAMS)` after the court
  and the dates, so the request is exactly the one batch 8 C measured live
  (`query, [court], [dates], order, per_page`). Nothing else in the branch moves.
- **`search_scope.py`**: the window note's three order statements flipped (section 2); the comment
  above `CASE_LAW_ABSENCE_SENTENCE` no longer says the product sends no `order`; the docstring adds
  "no 'top N of'" (a `NEG_LIMITS` phrase, which is why the note says "the first N of").
- **`tools/caselaw_probe.py`**: `RELEVANCE_PARAMS` is now the product's own object
  (`RELEVANCE_PARAMS = CASE_LAW_ORDER_PARAMS`, imported at module level). **Beyond the brief's line,
  and a decision (Decision 2):** `check_count`'s first GET and `check_dates`' two dated GETs now send
  the product's order params too, so each check reads the request the product makes (its docstring
  says every check does). `check_dates`' undated comparator stays the feed's default order (newest
  first), which is what makes "none of the window's judgments on the first undated page" mean the
  window reached past it. `check_order` is unchanged except its docstring.
- **Not changed, as decided:** the Phase-2 nudge's "the 1–3 most relevant cases below"
  (`agent_shared.py`), which is now true; `case_law_count`; the zero-result note.

## 2. The exact new wording of every note variant (for the user before merge)

The note is appended to the `search_case_law` tool result (the Worker reads it; `_TOOL_BLOCK` strips
it if a Worker echoes it). Three statements changed, nothing else:

| | Before (`ca3d45c`) | After (`82394b7`) |
|---|---|---|
| `CASE_LAW_RESULT_ORDER` | newest first, by date rather than by relevance | most relevant first, by relevance to the search words rather than by date |
| a full page with a total | the {N} most recent of about {T} judgments | the first {N} of about {T} judgments |
| a full page, no figure | the {N} most recent judgments | the first {N} judgments |
| the closing advice | An older judgment that matches can sit outside these {N} | Another judgment that matches can sit outside these {N} |

The three variants as built, on the synthetic query (from `python $B/screen.py SP`, `$B/screen.out`,
which prints all eleven forms):

1. **The whole set** (a page that is not full, or a full page whose `last` link fits it):
   `[SEARCH SCOPE — all 7 judgment(s) in Find Case Law matching "widget", listed most relevant first, by relevance to the search words rather than by date.]`
2. **A full page with a total** (with a court and dates the limits go in brackets after "Find Case
   Law", as before):
   `[SEARCH SCOPE — the first 50 of about 5,200 judgments in Find Case Law matching "widget" (the feed reports between 5,191 and 5,200), listed most relevant first, by relevance to the search words rather than by date. Another judgment that matches can sit outside these 50: to reach it, search again with narrower terms (a party's name, a court or dates) rather than treat this list as complete.]`
3. **A full page with no `last` link**:
   `[SEARCH SCOPE — the first 50 judgments in Find Case Law matching "widget"; the feed gave no figure for how many match in all, listed most relevant first, by relevance to the search words rather than by date. Another judgment that matches can sit outside these 50: to reach it, search again with narrower terms (a party's name, a court or dates) rather than treat this list as complete.]`

With no query the note says "matching the query"; a bracketed query is shown in round brackets (both
as before). Live, on the product's own request (section 5), variant 2 read "the first 50 of about
9,090 judgments … (the feed reports between 9,081 and 9,090)".

**Screen: 0 trips on every variant, the same as the base wording** (`python $B/screen.py SP` and on
`$B/base_ca3d45c/server_py`: "TOTAL TRIPS (excluding info): 0" both). Screened against `NEG_ASSERTED`,
`NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `NEG_LIMITS`, `NEG_TERMS`, `HALT_LITERAL`,
`HALT_PARAPHRASE`, `HALT_AS_TIMEOUT`, `IN_FORCE_CLAIM`, `OPENER_VOCAB`, `SCOTS_CASELAW_GAP`,
`_CUR_DISCLOSED`, `NEGATIVE_EXPLAINED`, `derivation_claims`, per sentence `_CMC_*`,
`_currency_asserted`, `negcurrency_claim`, `sched_clause_class` (all ''), `sched_unit_clauses`
(none), the word "ranked", a bracket inside the block, and `strip_scope_blocks` (1 block stripped,
the answer left whole). Two informational readings are the same before and after: `_without_footer`
only trims the note's leading blank line, and `_names_search_terms` credits the note (the words
"SEARCH SCOPE" with the quoted query already did so at base). The screen is committed in
`test_caselaw_window.py::test_window_note_trips_no_detector`, widened to 12 variants and to the
detectors `test_search_scope.test_footer_trips_no_detector` uses that it lacked (`HALT_LITERAL`, the
schedule-clause grader, `_without_footer`), so I added nothing to the shared test (the collision
point with agent C).

## 3. The dry run with the BUILT code. MET (0 unexpected moves)

**Method** (`$B/dryrun_b9.py`, batch 7 D's `dryrun.py` repointed in a copy; each run asserts it
imported the named tree): every stored `search_case_law` call is run through `run_worker_tool` with
summarisation switched off (the threshold patched, and `summarise_for_query` replaced by a function
that raises) and an `httpx.MockTransport` that answers each request with **the feed the live National
Archives returned for exactly those params** in batch 8 C's re-run (`C8/tna_calls.jsonl` and
`C8/raw/`, keyed on the parsed params, order-insensitive, blank values kept; for C's two retried
tuples the later, 200, feed). So the base tree's request is served C's default-order feed and the
built tree's request C's relevance feed **only if its params are exactly the ones C sent**.
`$B/compare_b9.py` then joins the two runs call by call and classifies every output that moves.

```
python $B/dryrun_b9.py $B/base_ca3d45c/server_py R C8 $B/dry_base.jsonl   # base, ca3d45c
python $B/dryrun_b9.py SP R C8 $B/dry_head.jsonl                          # the build
python $B/compare_b9.py $B/dry_base.jsonl $B/dry_head.jsonl $B/moved_calls.jsonl  # -> compare.out
```

**Directories.** 59 read (any `wave4_b9*` excluded, in case a sweep lands while this runs); 23 hold
calls. **1,267 calls, not 1,257:** `wave4_b8_sweep` (Session 40, after C's live run) holds 10 calls
on 5 tuples, for which no live feed exists. For those 10 the mock serves a feed rebuilt from the
call's own stored result (batch 7 D's method) to both trees, so their params and notes are checked
but their order cannot move (Decision 3). **The other 1,257 are exactly C's:** under the base every
one was served C's default-order feed (1,253, plus 4 from C's retry), under the build every one C's
relevance feed (1,253 plus 4); 0 unmatched, 0 lawyer date filters in any stored turn.

**What moved, call by call** (every call is listed, with its moves, in the gitignored
`$B/moved_calls.jsonl`; no query in it):

| | calls |
|---|---|
| params: `order=relevance` and `per_page=50` added, **nothing else** | 1,267 of 1,267 |
| results: the same list | 673 (the 495 zero-row calls, 169 short pages whose order relevance kept, and the 9 rebuilt calls with rows) |
| results: the same set, reordered | 512 |
| results: a different set (full pages; 50 rows under both) | 82 |
| window note: only the three order statements moved ("all" 684, "about" 88) | 772 |
| window note: none under either (zero rows) | 495 |
| zero-result note | 495 identical |
| the nudge's text (all but its url lines) | 772 identical |
| sources (the accumulator) | 673 identical, 512 same set reordered, 82 follow the different set |
| search log (the lawyer-facing footer's input) | 1,267 identical |
| every other JSON key (`shown`, `total`, `total_exact`, `total_min`, `total_max`, `dates`, `query`) | identical on every call |
| **UNEXPECTED moves** (any other params, keys, row count, note text, nudge text, sources, log; a call served a saved feed under one tree and not the other) | **0** |

Combined: 495 calls moved params only (zero rows); 178 params + note (169 C-fed short pages whose
order did not change, and 9 rebuilt calls); 4 params + results + note with the same first three;
492 params + results + note + first three; 98 those and the appellate block too.

**The first three the nudge names** (C-fed, so comparable with batch 8 C): by call, of 763 calls with
results, **590 change (77%)**: 121 the same three reordered, 469 a different set (217 share none, 121
share one, 131 share two), and 173 identical. By distinct tuple, of 356: **269 change (76%)**: 60
reordered, 209 a different set (109, 60, 40), 87 identical. **C's own measure is reproduced exactly
through the product's code path:** first three shared 0/1/2/3 on 109/132/70/45 tuples, and 217 calls
sharing none. So C's "about seven tuples in ten" is the list (set or order) changing; the set changes
on about six in ten.

**The appellate block** (`detect_appellate_decisions`): flags changed on 95 calls, added on 2, removed
on 1, identical on 224, none under either on 945. C hand-read a sample of these moves (relevance's new
flags more often genuine); I did not re-read them. The detector's false positives are P3.29.

**A correction to a number, not to the build:** C's "the ordering changes the set the model sees on 52
tuples (123 stored calls)" mixes two counts. 123 is how many stored calls *held* 50 rows when stored;
live, the 52 full tuples carry **82** stored calls (the rest now return short pages, mostly because
their dates now apply). `python` over `C8/live.jsonl` and `C8/calls.jsonl`: "full tuples (relevance)
52, full tuples (default) 52; stored calls whose tuple is full live: 82; stored calls that held 50
rows when stored: 123".

**Forms no stored call produces** (`python $B/forms.py $B/dry_head.jsonl`, `$B/forms.out`): the
"no figure" variant (a full page with no `last` link: 0 calls), a one-ended "dated up to" window (0),
a full page with a court and dates together (0), and no query (0). Each is tested on synthetic input
(`test_caselaw_window.py::_every_note_variant`, 12 variants, and the screen above). The stored calls
do contain the "all" and "about" variants, with and without a court, dated both ends and from only,
and 10 bracketed queries.

## 4. Other code texts that speak of the same thing (batch 8's lesson)

Every text the model or the lawyer reads about case-law order, checked against the change: the nudge
("the 1–3 most relevant cases below", `agent_shared.py`), `prompts.py`'s three "1–3 / 1–2 most
relevant cases" lines and `get_case_law_text`'s schema description ("the 1–3 most relevant cases
found in Phase 1") all become true; `CASE_LAW_ABSENCE_SENTENCE` ("A search can miss a judgment the
database holds …") agrees with "Another judgment that matches can sit outside these N"; the zero-result
note, the appellate note, the coverage and doctrine sentences and the `search_case_law` tool
description say nothing about order. **None contradicts the new note.** The live documents that still
say "newest first" are the integrator's to correct (section 8).

## 5. The live smoke (user-agreed). MET

`python $B/live_smoke.py SP` (`$B/live_smoke.out`), 10 GETs through the door, with the BUILT code and
the probe's committed default query:

- `check_count` on the product's request: shown 50, `last` 909, product range 9,081-9,090; page 909 at
  ten a page holds 6, true count 9,086: **PASS** (so `last` still counts at ten a page under
  relevance; `case_law_count` needs no change, as C found on 52 of 52 full pages).
- `check_dates` (Court of Appeal (Civil), 2015, the product's dated requests): 50 judgments, 0 outside
  the window; the undated default page shares 0 of them; one end only, 50 and 0 outside: **PASS**.
- `check_order`: default 50 rows, newest first; the product's params 50 rows, same `last` (909), not
  newest first, 0 of the first three shared; `order` alone 10 rows (the trap is still there): **PASS**.
- **The product's own request** through `run_worker_tool`: undated, 50 rows (no 10-row trap), not
  newest first, the same list as the probe's relevance GET (same URL), the note as in section 2;
  dated, 50 rows all inside 2015, the same list as the probe's window GET. 6 of 6 checks PASS.

**Not re-checked live:** that `order=relevance` is still absent from the published spec (the
integrator's one GET in Session 40 read v0.6.0; I made no call to any other host).

## 6. Tests, the revert and the mutants

**Tests added (16):** `test_caselaw_order.py` (new, 10): both params pinned, each failing alone, and
the exact param set; court and dates sent exactly as before; a refused window still sends nothing;
the audit's `api_call_start` payload carries both; the feed's order kept in the result (an older row
first stays first); the constant is the pair at page size 50; a full relevance page counted as
before; the order statement names relevance; all three statements flipped on every branch; the
nudge names the first three as the feed listed them. `test_caselaw_probe_order.py` (+6): the probe's
params are the product's object; `check_count` and `check_dates` send the product's request; each of
their guards fails alone. `test_caselaw_window.py`: wording updated, the screen widened (12 variants,
more detectors), the strip test over every variant.

**Revert** (`python $B/revert_b9.py SP $B/base_ca3d45c/server_py $B`, `$B/revert.out`): restoring
the four product files from `ca3d45c` on a scratch copy **removes 85 lines and restores 32**. The four
modules together fail at collection (`ImportError`: `CASE_LAW_ORDER_PARAMS`); alone,
`test_caselaw_window.py` fails 3 and `test_caselaw_probe_order.py` 3 on behaviour (the wording, and
the count and dates checks' params), and `test_caselaw_dates.py` passes 10 (it pins P3.9, untouched).

**Mutants** (`python $B/mutants_b9.py SP $B/base_ca3d45c/server_py $B`, `$B/mutants.out`; each a
fresh scratch copy, one byte-level edit whose anchor occurs exactly once, CRLF kept): **27 of 28
caught** (1 to 5 failures each). Each half of the old defect alone: no order params (3 fail), order
without `per_page` (3), `per_page` without order (3), `order=-date` (3), the constant's page size at
10 (5), `CASE_LAW_RESULT_ORDER` back to newest first (5), "most recent of about" back (2), "most
recent judgments" back (2), "An older judgment" back (1). The wording guards: "ranked" (3), a bracket
inside the block (4), "top N of" (4), the query's bracket cleaning removed (3). The probe: a copied
`RELEVANCE_PARAMS` (1), each of the four GETs given the wrong params (1 each), each guard of
`check_dates` dropped (five mutants, 1 each), `check_count`'s range guard dropped (1), a short page
paged (1). A re-sort by date in the executor (1) or in the nudge (1).
**The first run found a gap:** `check_dates`' outside-window guard survived (the ignored-window test
also tripped the overlap guard); `90360d8` adds a test failing each guard alone, and the mutant now
fails 1. **One survivor, provably harmless:** `check_count`'s `n_last > 0` (M22). With the range check
in place it is implied: `total_min >= (last - 1) * 10 + 1` and the paged count is
`(last - 1) * 10 + n_last`, so `n_last = 0` always falls below the range. It is pre-existing (P3.23's
probe), not part of this build.

## 7. Graders and recorders that read what changed (batch 8's lesson)

- **No tool-result shape changes**: no key added, removed or renamed (dry run: 0 JSON key moves).
- **The audit trace's `api_calls[].request`** for `search_case_law` gains `order` and `per_page` (it
  is the `api_call_start` payload, pinned by a test). Additive. For E: **to tell which ordering a
  stored run used, read `request.order`** (absent before P3.22, `relevance` after), not the note.
- **Graders keyed on the note's wording:** none. `grep` over `SP/tools` and `SP/tests` for "newest",
  "most recent", `CASE_LAW_RESULT_ORDER` and `case_law_search_note` finds only the case-law tests I
  updated (and two unrelated `newest` hits). `replay_report` is untouched (E's file).
- The note sits in a tool result, read by the Worker; the Manager and the lawyer never see it unless
  a Worker echoes it, and then `_TOOL_BLOCK` strips it (tested on every variant).

## 8. For the integrator (documents this build makes stale; I edited none)

- `CLAUDE.md:80` ("a window note says the list is newest first (`CASE_LAW_RESULT_ORDER`, flipped by
  P3.22)"); `docs/LEGAL_DATA_SOURCES.md:52` (the 50 newest matches) and `:168` (default order);
  CHANGELOG *Unreleased* (a P3.22 entry: the model now sees the most relevant matches, and the note
  says so); `docs/api/AUDIT_TRACE.md` (the two new request keys); the local `external-apis` skill
  ("Default order is `-date` … We send no `order`" and "(not built yet)").
- `tools/lex_probe.py`'s `--caselaw` help text still says "P3.23/P3.9" (one line; left alone because
  agent C may edit `lex_probe.py`).

## 9. Matches and edits read; data handling

Read: P3.22's, P3.23's and P3.9's rows, `notes/batch8_C.md` whole, the Session 40 log and handover,
the brief, the code named in it, batch 7 D's `dryrun.py`/`compare.py` and C's `run_live.py`,
`tna.py`, `census.py`, `retry.py`. I did **not** open C's rubric, transcripts or session dumps (not
needed for the build). The dry run's per-call files hold stored queries and stay in the gitignored
scratch; this note names no query, case, matter word or citation, and the tests use "widget", "Widget
Co v Example Ltd" and 1899-1902. Each staged diff was screened before its commit with
`python $B/staged_check.py <worktree>` (session ids, instrument ids and citations outside 1899-1902,
C's case and matter words, the integrator's batch 3 matter-word list): the build 1 hit (the generic
word "annex" in the schedule-clause regex, as in `test_search_scope.py`), the test commit 0, this
note 3 (that generic word, quoted in this sentence, and the two session ids of P3.22's acceptance,
which are allowed).

## 10. What I did NOT do

- No change to the nudge, `case_law_count`, the zero-result note, `replay_report.py` or the shared
  `test_footer_trips_no_detector`. No replay, no before- or after-column, no seam draw.
- No live call for the 5 tuples of `wave4_b8_sweep` (Decision 3), and none outside the smoke.
- No re-read of C's appellate sample; no read of the published spec.
- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`,
  `VERSION`, `docs/TODO.md`, `LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the
  lawyer pack, a skill or a memory file. Nothing pushed or merged; `main` untouched.

## 11. Numbers and commands

| Number | Command (from `$B` unless said) |
|---|---|
| 10 calls, 1 host, all 200, min gap 0.500 s, 473,676 bytes | read `tna_calls_b9.jsonl` |
| the probe's three checks and the product's two requests, all PASS | `python live_smoke.py SP` → `live_smoke.out` |
| 0 detector trips on every variant, base and build | `python screen.py SP` → `screen.out`; `python ../../screen.py .` in `base_ca3d45c/server_py` → `screen_base.out` |
| 1,267 calls, 59 dirs (23 with calls), 1,257 served C's feeds, 10 rebuilt | `python dryrun_b9.py <tree> R C8 <out>` → `dry_base.out`, `dry_head.out` |
| every move, 0 unexpected, first three 590 of 763 calls and 269 of 356 tuples, C's 109/132/70/45 | `python compare_b9.py dry_base.jsonl dry_head.jsonl moved_calls.jsonl` → `compare.out` |
| the note forms the stored calls contain | `python forms.py dry_head.jsonl` → `forms.out` |
| revert 85 removed, 32 restored; ImportError; 3 + 3 behavioural fails | `python revert_b9.py SP base_ca3d45c/server_py .` → `revert.out` |
| 28 mutants, 27 caught (the survivor provably harmless) | `python mutants_b9.py SP base_ca3d45c/server_py .` → `mutants.out` |
| 2498 tests | `cd SP && python -m pytest -q -p no:cacheprovider` → `pytest_full.out` |

## 12. Decisions for the user or the integrator

**1. The note's new wording** (section 2; a lawyer reads it only if a Worker's echo survives the strip,
but the Worker reads it on every search).
- **(a) Recommended: as built.** "listed most relevant first, by relevance to the search words rather
  than by date"; "the first N of about T"; "Another judgment that matches can sit outside these N".
  Mirrors the old sentence, no "ranked", 0 detector trips.
- (b) "the N most relevant of about T" in place of "the first N of about T": says what the N are in
  one phrase, but repeats "relevant" in the same sentence as the order statement.
- (c) Batch 8 C's shorter order statement, "listed by relevance to the search words" (no "most
  relevant first"): less redundant, but no longer tells the Worker which end of the list is the best.

**2. The probe's count and dates checks now send the product's request** (beyond the brief's
"`RELEVANCE_PARAMS` points at the product's params").
- **(a) Recommended: keep.** Every check then reads the request the product makes; live, the count
  and the dates both PASS under relevance, and a feed change that broke either only under relevance
  would now be seen.
- (b) Revert those two checks to the feed's default order (keep only `RELEVANCE_PARAMS` and
  `check_order` on the product's params): the P3.23 and P3.9 checks then test a request the product
  no longer sends.

**3. The 10 stored calls made after batch 8 C's live run** (`wave4_b8_sweep`, 5 tuples), whose order
cannot be dry-run without a live feed.
- **(a) Recommended: leave them.** Their params and notes are checked (rebuilt feeds, 0 unexpected
  moves), and the 1,257 calls C ran live give the ordering effect; sweep 2's after-column measures
  the real thing on 6363 and 6359.
- (b) Fetch their 5 tuples live under both orderings (10 GETs, which fit the 10 left of the agreed
  20), then re-run the dry run with all 1,267 on live feeds. Free, but a use of the calls the brief
  did not name, so only with the user's say-so.
