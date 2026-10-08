# Parallel batch 10, agent B: P3.22's per-query retrieval check

Branch `worktree-agent-ae9b2ff6141edb544`. **$0 model spend**: no model call of any kind, no server,
no replay pin, run or restore. **134 live GETs to the National Archives**
(`caselaw.nationalarchives.gov.uk` only; the user agreed at launch to up to 150, at least 0.4 s
apart), every one through one door (`$B/tna_b10.py`) that enforces the cap of 150 in code, a 0.4 s
minimum gap after the previous call ended, and the host and scheme, and logs method, URL, status and
bytes to `$B/tna_calls_b10.jsonl`. Measured from the log (`$B/calls_stats.out`): 134 calls, all
`GET`, all 200, one host, 0 errors, minimum gap 0.400 s, 4,709,309 bytes, 240.6 s end to end (so at
most 134 in any 300 s, against the published 1,000). The door's guards were checked offline before
the first call (`python door_check.py`: another host and `http` refused before any call, call 151
refused against a fake log of 150, the real log untouched). The run was not interrupted. No other host.

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-9. With no commits of my own I
ran `git reset --hard 7c3c6ac3040075850ab1a934d3443ed43558637b` first. Everything here is based on
`7c3c6ac` (`<INTEGRATOR_HEAD>`).

`$B` is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch10/B/` in the worktree
(`git check-ignore -v`: `.gitignore:113`, `docs/prepilot-fixes/evidence/seam/`). `SP` is this
worktree's `server_py`, `R` is `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `C8` is
batch 8 C's scratch `.../evidence/seam/batch8/C`, `RUB` is `.../evidence/rubrics/p322.json`. Every
command runs with `PYTHONIOENCODING=utf-8`,
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b`.

**Changed:** nothing in the product, no grader, no test. One commit: this note. Scripts and outputs
stay in `$B`.

**Tests: 2783 passed** on `lexchat_test_b` (`cd SP && python -m pytest -q -p no:cacheprovider`,
`$B/pytest_full.out`); the same count as the base, as expected with no code change.

**How the authorities are named here.** The rubric names a matter's authorities, so this note refers
to each by its position in `p322.json` (`6359#2` is the second entry of 6359's list, and so on). The
in-corpus ones are 6359#2-#4 (#4 the carrier) and 6363#4-#10 (#4 the lead). **The two whose run count
fell are 6363#6 (a UKSC judgment, 3/3 to 1/3) and 6363#10 (a Court of Appeal judgment, 2/3 to 1/3).**

---

## 1. The answer. THE ORDERING LOST NEITHER; BOTH DROPS ARE THE WORKER'S QUERY CHOICE

The check: take every query each run issued, and run the same queries under the other ordering on
the same day. If a run's own queries return the authority under the default order but not under
relevance, the ordering cost that run the authority. If they return it under both orders, or under
neither, the ordering did not.

| Authority (rubric position) | Run count as graded, sweep 1 to 2a | Sweep 1's queries, default / relevance | 2a's queries, default / relevance |
|---|---|---|---|
| 6363#6 (UKSC) | 3/3 to 1/3 | 3/3 / **3/3** | **1/3** / 1/3 |
| 6363#10 (CA) | 2/3 to 1/3 | 2/3 / **2/3** | **1/3** / 1/3 |

Sweep 1's queries run under relevance still return both authorities in every run that got them. 2a's
queries run under the default order return them in no more runs than relevance did. **So both drops
come from the queries the Worker chose. The ordering cost no run either authority.**

**6363#6, query by query.** In sweep 1, 9 distinct queries returned it under the default order, at
stored ranks 10 to 34. None of the 9 was issued in 2a. Under relevance, 7 of the 9 still return it,
2 of them in the first three (ranks 2 and 3, against 10 under the default). Two lose it: both are
full 50-row pages where the default had it at rank 33 and rank 35. Every sweep 1 run still returns it
under relevance through another of its own queries.

In 2a, the only run whose queries return it under either order is r3. Its two queries had it at
ranks 12 and 32 under the default. Relevance keeps the first (rank 17) and loses the second, so the
run keeps it. The queries 2a's r1 and r2 issued return it under neither order.

**6363#10, query by query.** In sweep 1, 2 queries returned it, both at rank 1 under the default.
One of them was also issued in 2a, in r1, and returned it there at rank 2, both as stored and live.
Relevance returns it for both queries, inside the first three each time (ranks 2 and 3). 2a's r2 and
r3 issued none of the 3 queries that return it, under either order.

**A correction to the sweep 2 hand-read** (`handread_wave4_b9_sweep2.md`, P3.22 section). It said
6363#6 arrived "ONLY as a lower-ranked co-result of queries naming another case (ranks 15-34)". There
were in fact 9 queries. Five of them name another rubric authority as their search words (stored
ranks 10, 10, 15, 17 and 20). The other 4 are phrase searches (stored ranks 10, 33, 34 and 34). The
conclusion stands: 2a issued none of the 5 name queries. The hand-read also said "the ordering
effect is not ruled out for the UKSC one". It is now ruled out by the same-query pairs above.

## 2. Per query, every authority. MEASURED

**Where each tuple's pair of result lists came from.** There are 192 distinct
`(query, court, date_from, date_to)` tuples, from 295 stored `search_case_law` calls across the 12
runs. None of the tuples is dated, and 50 carry a court.
- **27** match a tuple in batch 8 C's saved feeds exactly, under both orders, so they needed no call.
- **98** have a stored page of fewer than 50 rows that holds no rubric authority. A page that short
  is the whole matching set, and the set is the same under either order: batch 8 C found that on 304
  of 304 such pages, and this batch's pairs found it on 62 of 62. So neither order returns a rubric
  authority for these tuples, and they needed no call.
- **67** were run live under both orders, which is the 134 calls.

The relevance request used the product's own `caselaw.CASE_LAW_ORDER_PARAMS`, imported (not copied)
and asserted equal to `relevance`/`50`. Every tuple went through the built `case_law_date_window`,
though none is dated.
`run_live.py` asserts that it imported `SP`'s code.

**Checks of the method** (`$B/analyze.out`, "checks"):
- **The pairs match what the Worker saw.** Of the 157 stored calls with a live or batch 8 C pair
  that were not memo hits, all 157 hold the same number of rows as their pair: 88 default calls and
  69 relevance calls.
- **Ranks moved by one in only 2 calls**, one run's turn issuing the same tuple twice: rank 34
  became 35 live, where a newer judgment had been added to the feed. No authority entered or left a
  list.
- **No 10-row trap.** 0 relevance pages came back with 10 rows; 32 tuples were full under both
  orders.
- **Eight cells checked by hand against the raw feed bodies**, using a plain regex rather than the
  product's parser (`python spot.py <Qid> <path>`, `$B/spot.out`). All 8 agree with the analysis:
  the four cells lost to relevance, one cell gained, one carrier demotion and two promotions into
  the first three.

**Totals over the 9 in-corpus authorities any query returns.** 6359#2 is returned by no query under
either order.

| | Count |
|---|---|
| query-authority cells (a query returns the authority under either order) | 103 |
| … returned under both orders / default only / relevance only | 89 / **4** / 10 |
| … in the nudge's first three: default / relevance | 22 / **44** |
| default first-three cells still returned under relevance | **22 of 22** |
| run-authority cells (a run's own queries return it under either order) | 48 |
| … default only / relevance only | **0** / 2 |
| … in the first three somewhere in the run: default / relevance | 16 / 28 |

**The 4 query cells lost under relevance.** Three are 6363#6 and one is 6363#8. Every one sits at
default rank 32 to 45 on a full 50-row page, and in every case another query of the same run returns
the authority under relevance. Three of the queries were issued in sweep 1, and one in 2a (r3,
covered in section 1).

**The 2 run cells relevance adds** are both 6359#3, in 2a's r2 and r3. The full pages put it at
ranks 3 and 7 under relevance, and the default does not return it at all. This is the ordering's
share of the 2/3-to-3/3 rise the grader reported: 2a's own queries return it in 1 of 3 runs under the
default and in 3 of 3 under relevance.

**Per authority** (queries returning it: both / default only / relevance only; first three: default
/ relevance):

| Authority | Both | Default only | Relevance only | First three, default | First three, relevance |
|---|---|---|---|---|---|
| 6359#2 | 0 | 0 | 0 | 0 | 0 |
| 6359#3 | 2 | 0 | 2 | 0 | 3 |
| 6359#4 (carrier) | 14 | 0 | 0 | 12 | **6** |
| 6363#4 (lead) | 10 | 0 | 6 | 3 | 11 |
| 6363#5 | 4 | 0 | 0 | 0 | 0 |
| 6363#6 | 8 | 3 | 0 | 0 | 2 |
| 6363#7 | 21 | 0 | 1 | 3 | 11 |
| 6363#8 | 22 | 1 | 0 | 1 | 8 |
| 6363#9 | 5 | 0 | 1 | 0 | 0 |
| 6363#10 | 3 | 0 | 0 | 3 | 3 |

**One movement the other way: the 6359 carrier.** Relevance takes it out of the nudge's first three
on 6 of the 14 queries that return it. Under the default it is first or second on 11 of them,
because it is recent. It is still returned by all 14 queries, and it was still retrieved and
read in 3 of 3 runs in 2a. Bar item 4 asks only that it is retrieved, so this changes no verdict. It
would matter if a Worker read only the nudge's first three, so it is worth a watch line.

## 3. A second genuine item-3 failure, missed by the grader and the hand-read. FOUND (not mine to fix)

Bar item 3 classes as LINKED, and fails, a Find Case Law link whose label names an out-of-corpus
authority. `replay_report`'s `MD_LINK` (`\[([^\]]{1,200})\]\(...\)`) cannot match a label that holds
a bracketed law-report citation, and in that case `p322_mention_class` falls through to the
citing-word test instead.

On a synthetic sentence, the label `[*Widget Co v Example Ltd* [1901] AC 9](https://caselaw.nationalarchives.gov.uk/eat/1901/4)`
gives `MD_LINK` no match and is classed `SECOND_HAND`. The same label without the bracketed citation
is classed `LINKED`.

Over the stored 6363/6359 answers (`python linked_check.py SP RUB R/wave4_b9_sweep1
R/wave4_b9_sweep2a R/baseline R/wave1 R/wave2`, `$B/linked_check.out`), I found 3 links of this
shape. Two are the known surname false positive (sweep 1 r1 t3 and 2a r2 t3, which link a different
judgment that is in the corpus). The third is **2a 6359 r3 t7**. I read it: the label names 6359#1,
the out-of-corpus key case, with its law-report citation, and the link goes to the carrier's
judgment. **A genuine LINKED failure, by the bar's own definition.** It joins r2 t6, so item 3 in 2a
has **2** genuine failures, not 1; sweep 1 has 0 by hand. In both failing turns the carrier was
retrieved and read, so neither is a retrieval failure. I did not test whether the ordering plays any
part in either. This is batch 10 E's file, and I have not edited it (Decision 3).

## 4. What I did NOT do

- No product, grader or test change. No replay, no seam draw, no model call.
- No live call beyond the 134; 16 of the agreed 150 unused. The 98 whole-set tuples were not
  re-fetched (their answer is fixed by the set identity, checked on 62 of 62 pairs here and 304 of
  304 by batch 8 C).
- I did not re-grade item 3 by hand beyond the three links in section 3, and I did not re-read the
  sweep 1 or 2a answers.
- I did not use `authorities`' item-3 verdicts as evidence: batch 10 E is fixing its surname match.
  I used its item-1 and item-2 counts, which that fix does not touch: run
  `replay_report --dir R/wave4_b9_sweep2a authorities --before R/wave4_b9_sweep1`, exit 1, output in
  `$B/authorities_2a_vs_1.out`. Item 1 shows two FAILs, 6363#6 at 3/3 to 1/3 and 6363#10 at 2/3 to
  1/3; the lead is 3/3 to 3/3 and the carrier 3/3 to 3/3.
- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`,
  `VERSION`, `docs/TODO.md`, `LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any rubric, the
  hand-reads, the lawyer pack or any memory file. Nothing pushed or merged; `main` untouched.

## 5. Matches and edits read; data handling

**Read:**
- P3.22's row in full, `notes/batch8_C.md` and `notes/batch9_B.md`.
- The Session 41 log and handover.
- Batch 8 C's rubric, `p322.json`, and the P3.22 sections of both sweep hand-reads.
- The `authorities` code and the `search_case_law` branch.
- The 14 query strings behind the two drops (by query id, in scratch).
- The 3 links in section 3.

**Kept out of the committed note:** every per-query detail, which holds the lawyers' search terms
(`calls.jsonl`, `plan.json`, `live_b10.jsonl`, `analyze.out`). Those stay in `$B`. This note names no
query, case, citation or matter word. The only session ids it names are 6363 and 6359, which are
P3.22's acceptance sessions.

**The staged diff was screened** with `python $B/staged_check.py <worktree>`. That is batch 9 B's
screen widened with this batch's query words and a judgment-path pattern; it checks session ids,
instrument ids, citations and judgment paths outside 1899-1902, and case and matter words. Its hits
are reported in the reply.

## 6. Numbers and commands

| Number | Command (from `$B`) |
|---|---|
| 295 stored calls, 192 tuples, 0 dated, 50 with a court, 33 issued in both sweeps; requests none/- x147 (sweep 1), relevance/50 x131 (2a) | `python collect.py SP R .` → `collect.out` |
| 27 C feed matches, 98 whole-set-no-authority, 67 tuples / 134 calls needed | `python plan.py SP RUB C8` → `plan.out` |
| the door's guards, offline | `python door_check.py` → `door_check.out` |
| 134 calls, all 200, min gap 0.400 s, 4,709,309 bytes | `python run_live.py SP` → `run_live.out`; the stats snippet → `calls_stats.out` |
| every per-query, per-authority and per-run number in sections 1-2 | `python analyze.py SP RUB C8` → `analyze.out` |
| 8 of 8 hand spot checks against raw bodies | `python spot.py <Qid> <path>` → `spot.out` |
| the grader's item-1/2 counts | `cd SP && python -m tools.replay_report --dir R/wave4_b9_sweep2a authorities --before R/wave4_b9_sweep1` → `authorities_2a_vs_1.out` |
| the nested-bracket links | `python linked_check.py SP RUB R/...` → `linked_check.out` |
| 2783 tests | `cd SP && python -m pytest -q -p no:cacheprovider` → `pytest_full.out` |

## 7. Decisions for the user or the integrator

**1. The re-booked bar item 1** (the row says: "re-book the bar's 'no fewer runs' item as a
per-query retrieval check").

- **(a) Recommended: a check on each run's own queries, plus the first three.**
  *"1. (re-booked, batch 10 B) Same queries, both orders: every distinct `search_case_law`
  `(query, court, dates)` that the before- and after-column runs of 6363 and 6359 issued is fetched
  on one day under the feed's default order and under `CASE_LAW_ORDER_PARAMS`, re-using saved feeds
  where a tuple matches exactly. A page under 50 rows is the whole matching set under either order.
  PASS where (i) no run's own queries return an in-corpus rubric authority under the default order
  that they do not return under relevance, and (ii) every rubric authority in a query's default first
  three is still returned by that query under relevance. Reported, not graded: the query cells lost
  to relevance (each with its default rank) and the first-three counts under each order."*
  It is deterministic on saved feeds, and it isolates the ordering from the Worker's query choice.
  On sweep 1 and 2a: (i) 0 of 48 run cells lost, (ii) 22 of 22. **MET.**
- (b) A strict per-query check: every query cell the default returns is also returned under
  relevance. **Not met**: 4 of 103 are lost, all at ranks 32-45 on full pages and all recovered by
  the same run. It would fail on any full page relevance reorders, and reordering full pages is the
  whole point of the build.
- (c) The first-three half alone, (ii): met 22 of 22. But it is blind to the case that fell, an
  authority the default never put in the first three.

**2. Whether this measurement settles item 1 for the existing columns.**

- **(a) Recommended: yes. Record item 1 as met on `wave4_b9_sweep1` and `wave4_b9_sweep2a` by this
  check, with no new replay for item 1.** Items 2 and 4 already met (3/3 to 3/3 each). Item 3 is the
  only open item, and it is about Invariant 1, not the ordering (Decision 3).
- (b) Re-run the check on a fresh before- and after-column before counting it. That costs a sweep
  (about $22 at Session 41's costs: $9.56 for sweep 1's 6363 and 6359 runs, $12.39 for 2a) for a check the existing columns already answer.

**3. The item-3 grader gap and the second genuine failure** (section 3).

- **(a) Recommended: relay to batch 10 E before it finishes, or book it for E's fix.** `MD_LINK` in
  `p322_mention_class` should allow one nested `[...]` in a label (my synthetic case above is a ready
  test), and item 3 should then be re-read by hand on both columns. With the gap fixed, 2a has 2
  genuine item-3 failures (r2 t6, r3 t7) against 0 in sweep 1.
- (b) Book it as its own P3 tooling row after batch 10, and hand-read item 3 until then.
- (c) Leave the grader; record r3 t7 in the hand-read only. The same gap would then hide the next
  occurrence.

**4. Watch line: the 6359 carrier leaves the nudge's first three on 6 of 14 queries under relevance**
(section 2).

- **(a) Recommended: a watch line on P3.22 (no bar change).** It is still returned by every query and
  was read in 3 of 3 runs in 2a. It matters only if a Worker comes to read just the first three.
- (b) Add "the carrier in the first three of at least one query per run" to item 4. That is stricter
  than the lawyer's need, which is that the guidance is reached.
