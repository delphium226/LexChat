# Parallel batch 7, agent D: the case-law build (P4.19, P3.23, P3.9)

Branch `worktree-agent-a37e30c5970c6c57c`. **$0 model spend**: no model call of any kind, no
server, no replay pin, run or restore. **36 live GETs to the National Archives** (user agreed at
launch, cap 60), every one at least 1.1 s after the previous, logged (URL, status, bytes) to
`$D/calls.jsonl`: all 36 returned 200, 1,068,419 bytes in all. No other external call.

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-6. With no commits of my
own I ran `git reset --hard 6011b4fe0ba669cd68e225ac349c35f70f5fc724` first. Everything below is
based on `6011b4f`.

`$D` is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch7/D/` (checked with `git
check-ignore -v`: `.gitignore:113`, `docs/prepilot-fixes/evidence/seam/`). Every command runs
with `PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`
and `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d`; `R` is
`$PREPILOT_EVIDENCE/replay`.

## Commits

| Commit | Row |
|---|---|
| `bf53346` | P4.19: case-law calls through `_request_with_retry` |
| `87ec5e3` | P3.23: the shown count and the matching total apart; the window note; `lex_probe --caselaw` |
| `47c8c4e` | P3.9: the date form the feed honours; intersection kept; an empty or malformed window refused |
| `cbed549` | P3.23 follow-up: the window note stays strippable on a bracketed query (found by the dry run) |
| (this note) | |

**Tests: 2231 passed** on `lexchat_test_d` (2195 at base + 36 new), `python -m pytest -q`, run
after `cbed549`.

---

## 1. P4.19: retry case-law calls on a rate limit. MET

**Changed.** `search_case_law` (`executor.py`) GETs through `_request_with_retry(client, "GET",
url, params=..., timeout=15.0)`. `_fetch_judgment_text` (`caselaw.py`) takes an optional
`client`; the executor passes its own, and without one the function opens a client as before;
either way the GET goes through the helper with `timeout=15.0` per request. The helper is
imported inside the function (`executor` imports `caselaw`, so a top-level import would be
circular). A 400 (invalid court) and a 404 are not in `_RETRY_STATUS` and return at once.

**Timeouts and transport errors (batch 5 C's question on the row): retried, deliberately, and
the test file says so.** Measured over every stored call (`python $D/caselaw_latency.py R`):

| | API calls | median | p90 | p99 | max | >10 s | >14 s | failures |
|---|---|---|---|---|---|---|---|---|
| `search_case_law` | 1,149 | 181 ms | 960 ms | 2,864 ms | 13,125 ms | 2 | 0 | 3, all DNS transport errors (`getaddrinfo failed`) |
| `get_case_law_text` | 564 | 180 ms | 256 ms | 474 ms | 2,569 ms | 0 | 0 | one 404 (not retried, rightly); 2 calls with no `url` arg (never reached the network) |

So the only failures the helper would have changed are the three transport errors, which is what
a retry is for, and the 15 s timeout never fired. The worst-case cost of retrying a real timeout
is four attempts at 15 s plus 3.5 s of backoff. Decision D1 below.

**Tests** (`tests/test_caselaw_retry.py`, 8): 429 (with `Retry-After`) then 200 for the search,
the judgment fetch through the executor, and the judgment fetch with no client; a 503 and a 502;
a timeout retried with the 15 s per-request timeout pinned on every attempt; a persistent 429
still an error after 4 attempts; a 400 and a 404 returned at once, unretried.

**Revert** (`python $D/revert_check.py p419 HEAD tests/test_caselaw_retry.py --
server_py/src/agent/tools/executor.py server_py/src/agent/tools/caselaw.py`, on a scratch copy):
**40 lines removed, 6 of 8 fail**; the 2 that pass are the 400 and 404 guards, which hold before
and after by design. **Each half alone:** the executor reverted only, 4 fail (the search tests);
`_fetch_judgment_text` mutated to GET directly with its new signature (`mut_p419_caselaw.py`), 2
fail (the judgment tests). Outputs in `$D/revert_p419*.out`.

**What moves on stored inputs:** nothing, unless a 429, 5xx, timeout or transport error occurs.
Of the stored calls, the 3 DNS failures would have been retried.

## 2. P3.23: the shown count and the matching total. MET (with a corrected premise)

**A premise in the row is wrong, and the code is built on the corrected one. The feed's `last`
link is counted at TEN judgments a page, whatever page size is asked for.** The row (and
`docs/LEGAL_DATA_SOURCES.md` section 4, and the local `external-apis` skill) read it "at the page
size requested", "to within one page", with "the last page can be empty". Measured live (scratch
scripts `explore2.py`, `true_count.py`; GETs 1-25 in `calls.jsonl`):

| Query (public test queries) | rows / page | `last` | true count, by paging | at 50 a page `last` would say |
|---|---|---|---|---|
| a one-word surname (the row's own test query) | 50 | 520 | 5,193 (pages 104 full to 43; 105 empty) | up to 26,000 |
| the same with `per_page=50` sent | 50 | **520** | | |
| the same at `per_page=10`, page 520 | 10 | 520 | **3 rows: 519 x 10 + 3 = 5,193** | |
| a two-party case name | 50 | 12 | 116 (page 3 holds 16; 4, 6, 11, 12 empty) | up to 600 |
| a dated query (P3.9's form) | 19 | 2 | 19 (page 2 empty) | up to 100 |
| a court-filtered query | 1 | 1 | 1 | |
| zero results | 0 | 0 | 0 | |
| `negligence` (the committed probe's query) | 50 | 909 | 9,084 (page 909 at 10 a page holds 4) | up to 45,450 |

The "empty last page" was the artefact of reading the link at 50 a page. At ten a page the total
is known to within ten: `total_min = (last-1)*10+1`, `total_max = last*10`. A page with fewer
rows than the page size is the whole set whatever the link says (19 rows with `last` 2).

**Changed.**
- `caselaw.case_law_count(xml_text, shown)` returns `shown`, `total` (exact where known, else
  the range's upper end; with no usable `last` on a full page, the shown count with
  `total_exact: False`, so `total` stays an int for every consumer), `total_exact`,
  `total_min`, `total_max`. Additive: `results` and `query` are unchanged; `total` changes
  meaning as P1.3's did (the truer number).
- `search_scope.case_law_search_note(args, data)`: the window statement in P2.2's form, appended
  after summarisation and before the Phase-2 nudge (so the imperative stays last):
  "`[SEARCH SCOPE — the 50 most recent of about 5,200 judgments in Find Case Law matching "…"
  (the feed reports between 5,191 and 5,200), listed newest first, by date rather than by
  relevance. An older judgment that matches can sit outside these 50: to reach it, search again
  with narrower terms (a party's name, a court or dates) rather than treat this list as
  complete.]`", or "`all N judgment(s) … listed newest first, by date rather than by
  relevance.`" for a complete set, or "the feed gave no figure" with no `last` link. Nothing on a
  zero or errored search. Today's order is `CASE_LAW_RESULT_ORDER`, one constant, for P3.22 to
  flip. In `[SEARCH SCOPE — …]` form, so `_TOOL_BLOCK` strips an echo.
- `agent_shared`: the zero-result note and the Phase-2 nudge are keyed on the number of results
  shown (`len(results)`), never on `total` (the row's constraint).
- `tools/caselaw_probe.py`, run as `python -m tools.lex_probe --caselaw` (3 lines added to
  `lex_probe.py`'s argparse block) or `python -m tools.caselaw_probe`: `check_count` uses the
  product's parser and `case_law_count`, pages to the last page at ten a page, and asserts the
  true count is in the product's range. **Run live: PASS** (`negligence`: 9,084 in 9,081-9,090;
  first run on the row's surname query: 5,193 in 5,191-5,200). Output `$D/probe_p323*.out`.

**Follow-up commit (`cbed549`), found by the dry run (section 4):** 14 of the 781 stored
searches with results had a square bracket in the query (a neutral citation), which put a bracket
inside the note, where `_TOOL_BLOCK` (`[^\[\]]*\]`) stops: an echoed note would have survived the
strip. The quoted query now shows them as round brackets. Its test fails with the fix reverted
(6 lines removed). The same exposure exists in principle in P2.2's legislation notes, which quote
the query unsanitised, but **0 of 13,655 stored legislation search queries carry a bracket**
(`python $D/leg_brackets.py R`), so it is not booked.

**Tests** (`tests/test_caselaw_window.py`, 18): the parser (a `last` link, a short page with
`last` 2, no `last` link, zero, a full page whose link fits); the executor's JSON through a
mocked feed; the note's three branches, the court, silence on zero and errors, the strip, the
bracketed query; **the note screened on every branch against every answer detector**
(`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `NEG_LIMITS`, `NEG_TERMS`,
`HALT_PARAPHRASE`, `HALT_AS_TIMEOUT`, `IN_FORCE_CLAIM`, `OPENER_VOCAB`, `SCOTS_CASELAW_GAP`,
`_CUR_DISCLOSED`, `derivation_claims`, and per sentence `_CMC_CONTEXT`+`_CMC_DENIED`,
`_currency_asserted`, `negcurrency_claim`); and at the `run_worker_tool` seam, a zero-shown
result with `total: 10` gets the zero note and no nudge, and a shown page gets the window before
the nudge. Kept in my own file rather than `test_footer_trips_no_detector`, to avoid the merge
conflict batch 6 had there; the detector list is the same.

**Revert** (`revert_check.py p323 … executor.py caselaw.py agent_shared.py search_scope.py`):
**136 lines removed; collection fails at import.** So six mutants, one per half
(`make_specs_p323.py`, `run_mutants.sh`; `$D/mutants_p323.out`), each on the built tree:

| Mutant | Fails |
|---|---|
| the executor's `total` back to `len(entries)` | 2 |
| `agent_shared` keyed on `total` again | 1 |
| `last` read at 50 a page (the row's reading) | 4 |
| `case_law_search_note` stubbed to `""` | 7 |
| `agent_shared` without the window note | 1 |
| the "short page is the whole set" rule removed | 3 |

**Wording check.** Every window note the built code produced on the stored inputs (781) was
screened against the same detectors (`python $D/screen_notes.py <server_py> $D/dryrun_head.jsonl`):
7 trips, all `OPENER_VOCAB` (which reads only an answer's first sentence), **all 7 carried in by
the quoted query text, 0 by the product's wording** (`screen_detail.py`: the two that survived
blanking the query are queries holding an inner double quote, so the blanking stopped early).

## 3. P3.9: the date filter. MET (the named case's premise moved; see D3)

**Changed.** `caselaw.case_law_date_window(args, cfg)` builds `from_date_0/1/2` and
`to_date_0/1/2` (day, month, year, unpadded, as verified live) from the INTERSECTION of the
model's `date_from`/`date_to` and the lawyer's `_date_from`/`_date_to` (later start, earlier end;
now on parsed dates, not strings; `YYYY` and `YYYY-MM` widen to their span). An empty window (a
start after its end, including one emptied by the intersection, whose message says so) or a
malformed date returns an `error` result with **no request made**. `date_from`/`date_to` are no
longer sent. The code says the form is **not in the published spec** (comment above the builder
and at the call site). The result carries the applied window as `dates`; the P3.23 note names it
("dated 2015-01-01 to 2015-12-31", "dated from …", "dated up to …"). `order=relevance` is not
adopted.

**Tests** (`tests/test_caselaw_dates.py`, 10): the params built (and the ignored names gone); no
date sent when none is set; the intersection; the lawyer's dates alone; a start after the end, an
intersection-emptied window and two malformed dates each refused with no request; year and month
widening; the note naming the dates; the three refusal messages and the dated notes screened
against every detector (as above).

**Revert** (`revert_check.py p39 … executor.py caselaw.py search_scope.py`): **119 lines
removed; collection fails at import.** Five mutants (`make_specs_p39.py`;
`$D/mutants_p39.out`): the old param names sent (3 fail), no intersection (3), no refusal of an
empty window (3), the refusal ignored by the executor (3), the dates left out of the note (1).

**Live** (`python -m tools.lex_probe --caselaw`, the `check_dates` half; `$D/probe_p39_generic.out`):
`negligence`, Court of Appeal (Civil), 2015: **50 judgments, 0 outside 2015; 0 of them on the
first undated page (50 rows); "up to 2015-12-31" alone: 50, 0 outside. PASS.** One end alone
matters: 25 of the 88 stored dated calls sent only `date_from` (`python $D/date_formats.py R`;
every stored date is `YYYY-MM-DD`; 0 pairs have the start after the end).

**The row's named case** (Thomas's reproduction; run from scratch, `run_thomas.py` and
`thomas_plain.py`, so its query and citation are in no committed file): the 2025 window with the
row's court returns **19 judgments, all dated 2025, the named judgment among them**. It is **not**
on the first page of the plain query (50 rows, dated 2026-07-28 to 2026-10-02). **But it IS on the
first page of the same query with the same court and no dates today**: that page now holds all 19
of the 2025 judgments, so the row's "returns the same 50 results … as no window at all" no longer
describes the court-filtered query (the corpus has moved since 2026-09-18). The committed probe
therefore asserts the general property (none of the window's judgments on the first undated page,
for an older year) rather than a named judgment; `check_dates(known=...)` keeps the named form
available. Decision D3.

## 4. What the build moves, over every stored input (dry run, built code)

`python $D/dryrun.py <server_py> R <out.jsonl>` drives the **built** `run_worker_tool` and
executor over all 1,257 stored `search_case_law` calls, with the HTTP layer a MockTransport
serving a feed rebuilt from each call's stored `raw_result` entries, and summarisation switched
off by patching the threshold (so no model or cache call can happen; the script asserts it
imported the tree it names). Run twice: on an archive of `6011b4f`'s `server_py`
(`$D/base_6011b4f/`) and on this branch; `python $D/compare.py $D/dryrun_base.jsonl
$D/dryrun_head.jsonl` diffs them call by call and classifies every move (`$D/compare.out`):

| | calls |
|---|---|
| compared (4 stored results were errors or not JSON, skipped) | 1,253 |
| **params** identical | 1,165 |
| **params** moved: the date names to `from_date_*`/`to_date_*`, nothing else | **88** |
| requests made, base vs head (none refused) | identical |
| **JSON** gains `shown`, `total_exact`, `total_min`, `total_max` | 1,253 |
| … and `dates` (the dated calls) | 88 |
| **JSON** `total` changes (the full pages) | **123** |
| **notes** identical (zero-result searches: the zero note unchanged) | 472 |
| **notes**: the window note added, "all N" form, the rest identical | 658 |
| **notes**: the window note added, "of about" form, the rest identical | 123 |
| **UNEXPECTED moves** (any other params, JSON or notes change; zero note or nudge moving) | **0** |

(The first comparison found 14 unexpected note moves: the bracketed queries, fixed in
`cbed549`; the re-run is the table above.) **Two limits of a $0 dry run:** a stored full page has
no recorded `last` link, so the 123 "of about" notes were rendered with a placeholder `last` (999)
and their figures are not measurements; and the 88 dated calls would now return different
judgments live (the window applies), which cannot be measured without sending the stored queries
to the National Archives, which I did not do. P3.9's row already names the stored dated calls as
its before-column. The user date filter is set in 0 stored turns (the dry run reads
`audit.filters`). Size: the note adds a mean of 213 characters (174 for "all", 417 for "of
about", max 525) to a result whose median is 2,583.

## 5. Other findings

1. **The Phase-2 nudge still calls `results[:3]` "the 1-3 most relevant cases"**, which are the
   three newest; the new window note now says, in the same tool result, that the list is by date
   rather than by relevance. P3.22 resolves both (it is the next step in this build). D4.
2. **A refused window is recorded as an errored search** (`record_case_law_search`, `ok: False`),
   so the lawyer-facing case-law line says a search "was attempted … and returned an error". True
   enough (no search ran), not precise; 0 stored calls would be refused. D5.
3. **`docs/LEGAL_DATA_SOURCES.md` section 4, the local `external-apis` skill, and P3.23's and
   P3.22's rows state the `last` link's page size wrongly** (section 2). Not edited (not my files).
   D2.
4. P3.22's measure-first will send `per_page=50` with `order`; the `last` link stays at ten a page
   (`per_page=50` sent explicitly still gave 520), so `case_law_count` needs no change for it, and
   `check_count` will see it if that changes.

## 6. Numbers and commands

| Number | Command (from `$D` unless shown; `R` as above) |
|---|---|
| 36 live GETs, all 200, 1,068,419 bytes, min gap 1.1 s | read `calls.jsonl` (one JSON line per call) |
| latency and failure table (section 1) | `python caselaw_latency.py R` |
| 142 of 1,257 stored searches summarised (why the note is appended after summarisation) | `python caselaw_summarised.py R` |
| `last`-link table (section 2) | `explore2.py`, `true_count.py` (live; outputs in this note) |
| P3.23 probe PASS 9,084 in 9,081-9,090 | `cd server_py && python <D>/run_probe.py count` (or `python -m tools.lex_probe --caselaw`) |
| P3.9 probe PASS 50 / 0 / 0 / 50 / 0 | `cd server_py && python <D>/run_probe.py dates` |
| the named case: 19 in 2025, on the plain first page False, on the same-court first page True | `run_thomas.py`, `thomas_plain.py` (from `server_py`) |
| 88 dated calls, all `YYYY-MM-DD`, 63 both ends, 25 one end, 0 inverted | `python date_formats.py R` |
| dry-run table (section 4) | `dryrun.py` twice, then `python compare.py dryrun_base.jsonl dryrun_head.jsonl` |
| 781 notes screened, 7 trips, 0 from the product's wording | `python screen_notes.py <server_py> dryrun_head.jsonl`; `screen_detail.py` |
| 14 bracketed queries | `python check_brackets.py dryrun_head.jsonl x` (before `cbed549`) |
| 0 of 13,655 legislation queries bracketed | `python leg_brackets.py R` |
| note size 213 mean | read `dryrun_head.jsonl` (`len(window)+2`) |
| reverts and mutants (sections 1-3) | `revert_check.py`, `run_mutants.sh`, `make_specs_p3*.py`; outputs `revert_*.out`, `mutants_*.out` |
| 2231 tests | `cd server_py && python -m pytest -q` |

**Matches read:** no answer text. The dry run and the screens printed counts; the 14 bracket rows
and the 2 `OPENER_VOCAB` survivors were read by structure only (which characters, which span),
not by content. Before every commit the staged diff's added lines were screened for session ids,
instrument ids outside 1899-1902 and batch 3's 28 matter words (`staged_check.py`: 0 hits each
time). **The P3.23 commit was amended before anything else was built on it** to take a session's
case name out of a code comment, a test docstring and the probe's default query (the name is in
FIX_PLAN's rows, but it is also a case from the pre-pilot transcripts); `git diff 6011b4f HEAD`
contains it nowhere.

## 7. What I did NOT do

- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `summary-table.html`, `CLAUDE.md`, `CHANGELOG.md`,
  `VERSION`, `docs/TODO.md`, `LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, any skill, rubric
  or memory file. Nothing pushed or merged; `main` untouched.
- No live call with a stored (lawyer's) query: every GET used a public test query. So the dated
  calls' new results and the full pages' real totals are not measured (section 4).
- P3.22 not started (`order=relevance` not sent; the nudge's "most relevant" left).
- `test_footer_trips_no_detector` not extended (my screening is in my own test files, D6).
- No change to `executor.py`'s `lookup_legislation` branch (agent C's).

## 8. Decisions for the user or the integrator

**D1. Retry a timeout or transport error at the case-law calls?**
- **(a) Recommended: keep the helper's behaviour (built).** The only stored failures were 3 DNS
  transport errors, which a retry is for; the 15 s timeout never fired in 1,713 calls; the worst
  case is bounded at about a minute.
- (b) Retry statuses only for case law: a flag on `_request_with_retry`; a 15 s stall then fails at
  once, as before.

**D2. The `last` link's page size is stated wrongly in four places** (P3.23's and P3.22's rows,
`docs/LEGAL_DATA_SOURCES.md` section 4, the local `external-apis` skill).
- **(a) Recommended: correct all four in the fold**, citing section 2's table (counted at ten a
  page; the empty last page is the artefact of reading it at fifty).
- (b) Correct only the rows, and leave the reference documents until P3.22.

**D3. P3.9's acceptance names a judgment that is no longer beyond the first page of the
court-filtered query** (it still is beyond the plain query's first page).
- **(a) Recommended: accept the row as met** on the unit tests, the generic live check (PASS),
  and the named case run from scratch (in the window: yes; on the plain first page: no), and
  amend the acceptance text to the generic property.
- (b) Keep the named-judgment wording and record that only the plain-query half holds.
- (c) Choose a new named judgment that sits beyond the same-court first page, and commit it to the
  probe (it would need to be one from no session).

**D4. The nudge calls the three newest results "the most relevant" while the new note says the
list is by date.**
- **(a) Recommended: leave it to P3.22**, which flips the order and is the next step of this build.
- (b) Reword the nudge now ("the first 1-3 listed that bear on the question"); model-facing text,
  so screened again.

**D5. A refused date window reaches the lawyer's case-law line as a search that "returned an
error".**
- **(a) Recommended: leave it** (true, and 0 stored calls would be refused).
- (b) Record a refused window as its own state and word it in the footer.

**D6. Where the case-law wording's detector screen lives.**
- **(a) Recommended: leave it in `test_caselaw_window.py` and `test_caselaw_dates.py`** (same
  detectors as `test_footer_trips_no_detector`, no merge conflict).
- (b) Fold it into `test_footer_trips_no_detector` at merge, so one test holds every product
  wording.
