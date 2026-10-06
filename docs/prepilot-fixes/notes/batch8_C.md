# Parallel batch 8, agent C: P3.22 measured (relevance ordering for case law)

Branch `worktree-agent-a3be69096f363f137`. **$0 model spend**: no model call of any kind, no
server, no replay pin, run or restore. **1,241 live GETs to the National Archives**
(`caselaw.nationalarchives.gov.uk` only; the user agreed at launch to up to 1,300, at least 0.35 s
apart), every one through one door (`$C/tna.py`) that enforces the cap, a 0.4 s minimum gap after
the previous call ended and at most 900 in any rolling 300 s, and logs method, URL, status and bytes
to `$C/tna_calls.jsonl`. Measured from the log: minimum gap 0.400 s, at most 389 calls in any 300 s,
1,239 returned 200 and 2 returned 500 (both retried once, both 200), 15,096,731 bytes. No other host.
The run was interrupted once (the integrator's session ended) after it had finished; on resuming, the
log was recounted (1,230) and the cap applied to the total, so the retries and presence checks
brought it to 1,241.

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-7. With no commits of my own I
ran `git reset --hard 87ceeff1f3478cec38d9edf6d7010b78d16d8436` first. Everything here is based on
`87ceeff`.

`$C` is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch8/C/` (`git check-ignore -v`:
`.gitignore:113`, `docs/prepilot-fixes/evidence/seam/`). Every command runs with
`PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c`; `R` is
`$PREPILOT_EVIDENCE/replay`; `SP` is this worktree's `server_py`.

**Built:** nothing in the product. One probe, `check_order` in `server_py/tools/caselaw_probe.py`
(run by `python -m tools.lex_probe --caselaw` with the other two checks), and its tests on synthetic
feeds, `server_py/tests/test_caselaw_probe_order.py` (9).

**Tests: 2348 passed** on `lexchat_test_c` (2339 at base + 9), `python -m pytest -q -p
no:cacheprovider`, run after the last code change.

---

## 1. The live re-check of the feed (P3.22's claims). HOLDS

Through the committed probe, with every GET through the door (`python $C/recheck.py SP negligence
"<a public two-party case name>"`, 6 GETs, `$C/recheck.out`), both public test queries:

| | `negligence` | a public case name |
|---|---|---|
| default (no `order`, no `per_page`, what the product sends) | 50 rows, `last` 909, newest first | 50 rows, `last` 12, newest first |
| `order=relevance&per_page=50` | 50 rows, `last` 909, not newest first, 0 of the first three shared | 50 rows, `last` 12, not newest first, 0 shared |
| `order=relevance` alone | **10 rows (the 10-row trap is still there)** | 10 rows |

So `order=relevance` still ranks, over the same matching set (the same `last` link), and only with
`per_page` does it keep the 50-row page. The same held over every stored query (section 2: all 52
full pages kept 50 rows and the same `last` link).

**Not re-checked: that `order=relevance` is still absent from the published spec.** The spec
(`public_api.yml`) is on GitHub, a host the user did not agree to, and no copy is in the repo or the
evidence. Decision 6.

## 2. The re-run of every stored search (the measure-first). MEASURED

**Recount** (`python $C/census.py R $C`, globbing **all 58 replay directories**): 1,257 stored
`search_case_law` calls in 22 directories (the other 36, including the newest `wave4_b7_p324`, hold
none), **612 distinct (query, court, date_from, date_to) tuples**, 35 of them dated, 245 whose every
stored call returned nothing. Identical to batch 5 C's count. No stored call carries any other
argument.

**Run** (`python $C/run_live.py SP`, then `python $C/retry.py SP` for the two 500s): each tuple
twice, interleaved, today's params and the same plus `order=relevance&per_page=50`, the params built
by the **built** `case_law_date_window` (the script asserts it imported `SP`'s code), so the 35 dated
tuples now send the date form that applies. 0 refused by the window. Analysis:
`python $C/analyze.py SP R` (`$C/analyze.out`); recency: `python $C/recency.py`.

**Latency and errors, per ordering** (the 1,228 stored-tuple calls): median 220 ms both; p90 1,659 ms
today and 1,648 ms relevance; over the product's 15 s timeout 3 today and 4 relevance; 500s 0 today
and 2 relevance (both 200 on one retry, which P4.19's helper does). No material cost to relevance.

**Overlap** (all 612 tuples, both orderings 200):

| | tuples |
|---|---|
| zero rows under both orders | 256 |
| a short page (1-49 rows: the whole matching set): relevance returns **the same set**, reordered | 304 |
| … a different set | 0 |
| a full page (50 rows) | 52 |
| … the same `last` link under both orders | 52 of 52 |
| … relevance page holding 50 rows (no 10-row trap) | 52 of 52 |

On the 52 full pages the two 50s share a median of 12.5 rows (mean 17.3, min 0, max 46; 21 share 10
or fewer). **The first three**, which the Phase-2 nudge names: of 356 tuples with any result, 109
share none, 132 one, 70 two, 45 all three; weighted by stored calls (763), 217, 275, 177 and 94. So
the ordering changes the set the model sees on 52 tuples (123 stored calls) and the nudge's first
three on about seven tuples in ten.

**Recency** (the "recency bias" mechanism): on the full pages today's rows have a median year of 2025,
69% from 2025-26 and 3% before 2015; relevance's median 2021, 24% from 2025-26, 29% before 2015
(2,600 rows each). Over the first three of every tuple with results: today 2025, 68%, 7%; relevance
2023, 28%, 19% (894 rows each).

**Authorities named in answers.** Every stored turn that searched case law and whose answer names an
authority by neutral citation or Find Case Law URL: 184 turns, 522 authority-turns (a URL and an NCN
naming one judgment are merged). Each is checked against the union of that turn's live results:

| | authority-turns |
|---|---|
| returned by both orders | 465 |
| today's order only | 19 (15 distinct judgments, 14 of them dated 2025-26) |
| relevance only | 3 (2 distinct judgments, both UKSC 2021-22) |
| neither | 35 (10 distinct; 22 of them in one scripted session's dated replays, whose searches now apply their dates; the rest named from the model's own knowledge) |
| in the first three: both / today only / relevance only / neither | 274 / 70 / 53 / 125 |

Plus 17 law-report citations (no NCN) in 16 turns, not matchable to a feed row. **This measure is
biased towards today's order and must not be read as a quality score:** every answer was written by a
Worker that saw today's order's 50 and was told to fetch its first three, so the authorities it named
are drawn from that order by construction. The 19 it loses are recent judgments today's order had put
in front of the model; the ground truth (section 3) is the unbiased check, and on it relevance loses
nothing.

**`detect_appellate_decisions`** (the built function over both orders' rows, all 612 tuples): it
flags something on 136 tuples today and 137 under relevance (316 and 357 flags); the flags differ on
47 tuples (98 lost, 139 new; 77 of the lost because the flagged appeal is not in relevance's 50, 122
of the new because it was not in today's). **Hand-read** (`python $C/appellate_pairs.py SP`, a seeded
sample of 20 lost, 20 new, 20 kept; each read as "the same litigation at two levels" or not, from
titles and citations): **lost 3 of 20 genuine, new 8 of 20 genuine (1 uncertain), kept 5 of 20
genuine.** So the nudges do not change for the worse: relevance clusters a case with its appeal, and
the flags it drops are mostly false. **The detector is mostly false positives under either order**
(a shared token such as a place, "county", "holdings" or a first name links unrelated cases; 25% of
kept flags genuine): a pre-existing defect, not P3.22's (Decision 5).

## 3. The ground truth for 6363 and 6359 (P3.22's row asks for it first). PROPOSED

In the gitignored `$C/rubric_p322_6363_6359.md` (case names, neutral citations, the lawyers' words by
turn; per-turn table `$C/rubric_check.txt`, from `python $C/rubric_check.py`). 6363 and 6359 are
stored only in `baseline`, `wave1` and `wave2` (one run each). Seven presence GETs
(`python $C/presence.py SP`, `$C/presence.json`) checked whether each authority is in the corpus at
all: one relevance-ordered query on the party names, reading the whole matching set (14 to 50 rows).

- **6359:** three authorities the lawyer named (one key case, one expected Supreme Court case, one the
  lawyer accepts as a substitute) and the EAT judgment that carries the key case second-hand. **The
  key case is not in the corpus**; the two Supreme Court cases are, but no stored query reached them
  under either order (the model searched phrases, not names); the carrier is returned by both orders
  in all 8 turns that return it (in the first three in 8 today, 6 under relevance).
- **6363:** the lawyer named no case (the feedback says the fundamental cases were missing and the
  results looked recent; FIX_PLAN's P3.22 row records the latter as recency bias).
  Proposed: the three authorities the stored answers themselves call foundational, cited
  second-hand, **all three not in the corpus** (so the lawyer's own guess about the dataset is right
  for them and no ordering fixes it), four Supreme Court and three Court of Appeal judgments on
  occupation, all in the corpus. **Relevance returns every in-corpus authority wherever today's order
  does (0 of 33 cells lost)**, adds the leading Supreme Court judgment in 4 more turns (9 against 5)
  and two others in one each, and puts more in the first three (16 turn-cells against 10).
- The proposed bar for the acceptance is at the end of the rubric: no in-corpus authority retrieved in
  fewer runs after than before; the leading Supreme Court judgment in at least as many 6363 runs; an
  answer naming an out-of-corpus authority does so second-hand (Invariant 1); the EAT carrier still
  retrieved in 6359. **6363's Tier 1 is our proposal and needs a lawyer** (Decision 4).

## 4. What a build would move (for the integrator, not done here)

- **Params:** `order=relevance` and `per_page="50"` together on `search_case_law` (the probe's
  `RELEVANCE_PARAMS` should then point at the product's params, as its comment says). `last` still
  counts at ten a page under relevance (52 of 52 full pages kept today's `last`), so `case_law_count`
  needs no change.
- **The window note** (`search_scope.case_law_search_note`) states today's order three times:
  `CASE_LAW_RESULT_ORDER` ("newest first, by date rather than by relevance"), "the {n} most recent of
  about", and "An older judgment that matches can sit outside these {n}". All three must flip, and
  the wording must be screened: the comment above `CASE_LAW_ABSENCE_SENTENCE` records that "ranked"
  tripped `NEG_LIMITS` and `NEG_TERMS` before, so "listed by relevance to the search words" (no
  "ranked") is the safer form; `test_caselaw_window.py`'s detector screen pins it.
- **The Phase-2 nudge** ("the 1-3 most relevant cases below") becomes true as worded; no change
  needed, though "the first 1-3 listed that bear on the question" is more honest.
- Not dry-run here (nothing was built): by construction a build moves the params of every stored
  call and the note text of every call with results (781 at batch 7 D's dry run); the JSON shape
  need not change.

## 5. Numbers and commands

| Number | Command (from `$C`) |
|---|---|
| 1,241 calls, 1,239 x 200, 2 x 500, min gap 0.400 s, max 389 per 300 s, 15,096,731 bytes | read `tna_calls.jsonl` (snippet in this session's log; one JSON line per call) |
| 1,257 calls, 612 tuples, 35 dated, 245 all-zero, 58 directories globbed, 22 with calls | `python census.py R .` |
| the feed re-check (section 1) | `python recheck.py SP negligence "<case name>"` |
| latency, overlap, authorities, appellate counts (section 2) | `python analyze.py SP R` → `analyze.out` |
| recency medians and shares | `python recency.py` → `recency.out` |
| appellate hand-read sample (seed 8) | `python appellate_pairs.py SP` → `appellate_pairs.txt` |
| presence of the ground-truth authorities | `python presence.py SP` → `presence.json` |
| per-turn ground-truth table, 0 of 33 cells lost | `python rubric_check.py` → `rubric_check.txt` |
| stored costs for the replay price (Decision 3) | read `total_cost_usd` in `R/{baseline,wave1,wave2}/63{63,59}_rep1.json` |
| probe revert and mutants (section 6) | `python mutants.py <worktree> 87ceeff…` → `mutants.out` |
| 2348 tests | `cd SP && python -m pytest -q -p no:cacheprovider` → `pytest_full.out` |

## 6. The probe and its tests

`check_order(get, query, relevance_params)`: three GETs (default, the relevance params, `order`
alone); PASS needs a full relevance page, the same `last` link under both orders, and a relevance
list that differs from the default and is not newest first; the bare `order` call is reported (the
10-row trap), not asserted. `main()` runs it after the count and dates checks. Tests (9): the pass
case and the exact params sent; `RELEVANCE_PARAMS` pins both parameters; a fail each for an ignored
`order`, a different list still newest first, a page size back at 10 (same `last`), a changed matching
set, no `last` link; the bare call not asserted; `main` runs the check.

**Revert** (the probe file back to `87ceeff` on a scratch copy of `server_py` in `$C`): **63 lines
removed; the test module fails at collection** (import). So six single-site mutants, each on a
scratch copy: page-size check dropped (1 fails), matching-set check dropped (2), reorder check
dropped (2), newest-first test dropped (1), `main` without the order check (1), `per_page` left out of
the params (2). Every mutant is caught.

## 7. Matches and edits read; data handling

Read in full: the 6363 and 6359 transcripts (from the export, into the gitignored
`$C/transcripts_6363_6359.txt`) and their stored answers and searches (`$C/sessions_dump.txt`). Read
by title and citation: the 60 sampled appellate pairs. The 522 authority-turns were classified by
code; the 19, 3 and 35 differing ones were listed by citation and session (in
`$C/authorities_detail.jsonl`). Nothing from them is in a committed file: the note names no case,
query, matter word or session-specific citation; the probe's queries are the committed default
(`negligence`) and synthetic fixtures ("Widget Co v Example Ltd", 1901). The staged diff was screened
before each commit with `python $C/staged_check.py <worktree>` (session ids, instrument ids and
citations outside 1899-1902, and 27 matter and case words from this batch): 0 hits.

## 8. What I did NOT do

- No product change: `order` is not sent, `CASE_LAW_RESULT_ORDER`, the window note and the nudge are
  unchanged. No replay, no before-column.
- No fetch of the published spec (Decision 6). No call with a lawyer's query to any host but the
  National Archives, and none outside the cap.
- The appellate hand-read is a sample (60 of 455 flags), not every flag.
- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`,
  `VERSION`, `docs/TODO.md`, `LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any existing rubric,
  the lawyer pack, a skill or a memory file. Nothing pushed or merged; `main` untouched.

## 9. Decisions for the user or the integrator

**1. The ordering.**
- **(a) Recommended: relevance, `order=relevance` with `per_page=50`, one test pinning both.** The
  same matching set (52 of 52 full pages, 304 of 304 short pages), no 10-row trap, no latency cost;
  on the ground truth it loses no in-corpus authority (0 of 33) and adds the leading Supreme Court
  judgment in four more 6363 turns; recent judgments fall from 68% to 28% of the first
  three.
- (b) Keep today's newest-first order: the window note already says so; the recency complaint stays.
- (c) Relevance by default and an `order` argument the model may set to newest first for "recent"
  questions: more surface, and a model choice where code could decide.

**2. The window note and the nudge, if (1a).**
- **(a) Recommended: flip all three of the note's order statements in the same commit**
  (`CASE_LAW_RESULT_ORDER`, "most recent of about", "An older judgment …"), worded without "ranked",
  and re-run the detector screen; leave the nudge's "most relevant", which becomes true.
- (b) Flip the note and also reword the nudge to "the first 1-3 listed that bear on the question".
- (c) Flip only `CASE_LAW_RESULT_ORDER`: leaves "most recent" and "older" contradicting it.

**3. The before-column replay to book.**
- **(a) Recommended: 6363 and 6359, n=3 each, recorded modes, at the head carrying P3.9, P3.23 and
  P4.19 and not P3.22, graded on the rubric.** Priced from stored costs (pinned Gemini): 6363 $2.12,
  $2.01, $1.97 (mean $2.04), 6359 $0.93, $1.49, $1.13 (mean $1.18), so **about $9.65 a column and
  $19.30 with the after-column**; stored costs are from the earliest directories, and 6375's grew
  about 1.5 times between them and the latest, so allow up to about $14.50 a column.
- (b) n=1 each before (about $3.20), n=3 after: cheaper, but a single before-run is not evidence
  (Invariant 4).
- (c) No before-column: use this re-run plus the stored columns. Not comparable: the stored runs
  predate P1.1 and the case-law build.

**4. The ground truth.**
- **(a) Recommended: adopt the proposed rubric as P3.22's bar, and add 6363's Tier 1 (our proposal:
  the lawyer named no case) to the lawyer pack as a supplementary question**; 6359's rests on the
  lawyer's own words.
- (b) Adopt only 6359's items and 6363's in-corpus judgments, as non-regression only.

**5. `detect_appellate_decisions` is mostly false positives** (25% of kept flags genuine in the
sample; any shared token not in its stopword list links two cases).
- **(a) Recommended: book a new P3 row** (require two shared tokens, or a shared token that is not a
  place or a common word, and the lower judgment dated no later than the appeal); measure-first over
  this re-run's 612 tuples, $0.
- (b) Leave it: the nudge is advisory and relevance already improves it.

**6. The spec check not done** (`order=relevance` absent from `public_api.yml`).
- **(a) Recommended: the integrator fetches `public_api.yml` once (one GET to
  raw.githubusercontent.com) with the user's agreement, before the build's code comment says so.**
- (b) Rely on the 2026-10-02 reading and on `check_order`, which fails if the value stops working,
  whatever the spec says.
