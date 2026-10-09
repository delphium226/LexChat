# Parallel batch 12, agent C: P3.20 built (Scottish case law from SCTS), gated off

Branch `worktree-agent-ac00db1e856699a20`. **$0 model spend**: no model call of any kind, no server, no replay
pin, run or restore, no seam draw. **27 live SCTS calls of the 40 the user agreed** (26 `POST
https://api.pa.web.scotcourts.gov.uk/web/search`, 1 `GET` of a judgment PDF on `https://www.scotcourts.gov.uk`),
all status 200, minimum gap 1.001 s, 458,545 bytes; no other host (`calls_c.out`). **20 of the 27 were wasted
by a fault in my own call door, not the product** (section 4).

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. With no commits of my own I ran
`git reset --hard a99e4d4` first; everything here is based on `a99e4d4`. No unexpected commit appeared.

`$C` below is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch12/C/` (`git check-ignore -v`:
`.gitignore:113`). Every command ran with `PYTHONIOENCODING=utf-8`,
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and, for pytest,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c`.

**Commits:** `78bcff7` (the product change), `1d9fff8` (tests and the `scts` grader), `dcfb937` (the citation
order, after the PDF dry run), and this note. **Tests: 3,133 passed** (the base's 3,017 plus 116 new;
`cd server_py && python -m pytest -q -p no:cacheprovider` → `$C/pytest_full.out`). `plan_lint`: 0 errors, 0
warnings (no plan file touched).

---

## 1. What was built, and where it differs from the brief

To the design on P3.20's row and batch 11 D's section 5, behind a new setting **`scts_caselaw_enabled`**
(`config.py`, env `SCTS_CASELAW_ENABLED`, **default off**) until both hosts are whitelisted on the target.

- **`server_py/src/agent/tools/scts.py`** (new): the SCTS search and the judgment text.
  - **Query**: every quoted phrase and every word required (`+`); an `a OR b` run as `+(a | b)` (probed live:
    17 against 16 for the plain required form); `AND` dropped (not an operator); one **any-term fallback** on
    zero, the same terms without `+`, made only when it could differ (more than one term). Square brackets,
    stray operators and inner punctuation cleaned (`3(2)(a)` becomes a phrase).
  - **Rows**: deduped on `documentLink`; `decision_date` = `additionalDate`; `published` = `date`; `ncn` only
    from a filename that starts with a citation, never a date; `sheriffdom`, `tags`, `searchType` dropped.
  - **Counts**: `shown`, `total` (`pagination.count.total`), `total_exact: true`; a page that is not full counts
    distinct judgments, not repeated rows.
  - **Rate control**: per request **60 search calls** (fallbacks included) and **20 judgment texts**, counted on
    the request's config dict (shared by every Worker and Deep Research step of one request); process-wide **2
    calls in flight** (one semaphore per event loop); every call through `_request_with_retry`. Past a cap: no
    call, and the result says so.
  - **Text**: an https PDF on `www.scotcourts.gov.uk` only; read with **pdfplumber in a thread**
    (`asyncio.to_thread`); 15 MB and 300-page caps, a `%PDF` check, an empty text is an error. No pypdf.
- **`search_case_law`** (executor): with the setting on and a case-law research type, Find Case Law and SCTS run
  together and the result gains **`scottish_results`** and a **`scottish`** block (`status`: ok, error, capped,
  not_searched; `shown`, `total`, `match`: all/any, `query_sent`, `dates`). The lawyer's and the model's dates
  (`case_law_date_window`, intersected) go to SCTS as `AdditionalDate`; the `court` code is Find Case Law's and
  is not sent. **Either half failing leaves the other**: a Find Case Law failure becomes an `error` beside the
  Scottish list instead of the whole call's error string.
- **`get_case_law_text`**: routed by host. An SCTS PDF (setting on) to the PDF route; Find Case Law as before;
  **anything else refused with no call** (it used to be fetched as `<url>/data.xml` from any host). All 952
  stored calls with a URL were Find Case Law https URLs (`census_c.py`), so the refusal moves none; the two
  stored calls with no `url` still return `Error executing tool: 'url'`.
- **Notes** (`agent_shared._case_law_note_with_scottish`, `search_scope.scottish_search_note`): Find Case Law's
  window note as today; the Scottish list's window note (all / first N of total / any-term fallback / error /
  capped / not searched) or zero note; one stop rule only when both lists are empty after an ok search; one
  MANDATORY NEXT STEP naming up to three judgments from each list, last. A result without the Scottish block
  goes through today's branch untouched.
- **Sources rail**: the Scottish rows join it (court and decision date as the meta).
- **Footer** (`search_scope._case_law_body`): **keyed on this turn's records, never on the setting.** A record
  carries `scts` only when its result carried the block. An ok SCTS search swaps today's coverage sentence (which
  says the Court of Session is absent) for the both-ran or SCTS-only wording; an errored one keeps today's
  sentence and says SCTS was attempted; no `scts` key (setting off, every record before P3.20) gives today's text
  byte for byte.
- **Prompts and tools**: `prompts.SCTS_PROMPT_WORDING`, nine (old, new) pairs swapped by `apply_scts_wording`
  only when on and only for a case-law research type (both case-law Workers, the quick-lookup Worker, the
  Scotland filter note, the Deep Research synthesis sources); `schemas._with_scts_descriptions` swaps the two
  case-law tool descriptions on copies.
- **Caching**: both tools stay in `CACHEABLE_TOOLS` (SCTS content is OGL); a test pins that and the drafting
  override (`_local_prompt_cache_enabled` false on a drafting request).
- **Grader**: `replay_report scts`, its own subcommand (section 7). `caselaw` is untouched.

**Where the built shape differs from the brief or from batch 11 D's proposal** (for the integrator to relay):
1. **The text fetch takes the filename's citation first**, the text's only as a fallback (D proposed text first).
   Measured over D's 40 stored PDFs with the built code (section 5): the two agree on 23 of the 24 that carry
   both, and the 24th is the judgment D recorded as printing its own citation a year early.
2. **Negated terms are dropped** (`-word`, `-"phrase"`, `NOT x`): D's rule stripped the `-` and would have made
   the excluded term required. No stored query held one (census, 1,580 searches).
3. **Four Worker-facing note wordings changed on the screen's evidence** (section 3) and the new zero notes are in
   `[SEARCH SCOPE — …]` form (strippable), unlike today's Find Case Law zero note.
4. **`SCTS_ERRORED_SENTENCE` says "which hold published decisions of those courts"**, not D's "which hold those
   Scottish courts' decisions" (SCTS publishes only some Sheriff Court decisions).
5. **The host allowlist on `get_case_law_text` applies with the setting off too** (Decision 5).
6. The Scottish list is 10 rows a search (D's estimate's size), not 50.

## 2. Dry runs over every stored input, with the BUILT code

`$C/dryrun_c.py <root> <label> [--scts-on]` renders, from every stored input in every replay directory (66 with
run files when run; none excluded), every output this change touches: the final string `run_worker_tool` returns
for each stored `search_case_law` result (execution patched to the stored raw result, summarisation patched to the
identity, local cache off: no model, no network), its source rows and its record; each turn's footer and clause;
and 48 prompt/tool texts (3 research types x 3 chat modes x with and without the Scotland filter, the synthesis
prompts, the Worker tool lists). Run on the base (`git archive a99e4d4` into `$C/base`) and on the built tree;
`$C/compare_c.py` → `$C/compare_c.out`:

| | base vs built, setting off | base vs built, setting on |
|---|---|---|
| notes (1,580 stored searches) | 1,580 identical | 1,580 identical (stored results carry no Scottish block) |
| source rows, records | 1,580 / 1,580 identical | identical |
| footers (416 turns) | 416 identical | 416 identical |
| prompt and tool texts (48) | 48 identical | **26 moved**: exactly the case-law research types' Worker prompts, Scotland filter blocks, tool lists and synthesis prompts; every legislation-only text unchanged |

Re-run on the final code after the last commit: the same.

**Input forms no stored run contains**, tested on synthetic input instead: a negated term, `NOT`, an unbalanced
quote, a query that cleans to nothing, a citation in square brackets in the Scottish note, an empty query; SCTS
answering 4xx, non-JSON, a raised exception, a failed fallback; a non-PDF, oversized, unreadable or empty PDF;
each cap reached; Find Case Law failing or rejecting a court code with SCTS ok; an `http`, query-string, look-alike
or other-host URL to `get_case_law_text`; the setting off with an SCTS URL; concurrent searches past the limit.

## 3. The wording, screened on the BUILT text

`cd server_py && python ../docs/prepilot-fixes/evidence/seam/batch12/C/screen_c.py` → `$C/screen_c.out` (batch 11
D's `b9_screen` over this worktree's `replay_report`, every detector the lessons list; today's built text at the
same site is the baseline, so only new trips count). Rendered: **42 footers** (7 record variants x standalone and
joined to a legislation line x 3 term classes), **448 notes** (7 Scottish-block classes x 4 date windows x 4
queries, among them a bracketed citation, a quoted phrase with OR, and an empty query, x 4 Find Case Law states),
**15 texts** (the nine prompt pairs, four tool texts, the PDF cap message, the text-route refusal).

- First screen: 322 new trips, all in Worker notes and one tool message: "not searched for" (`NEGATIVE_EXPLAINED`,
  `NEG_TERMS`) in the capped and not-searched notes, "did not complete" (`SCHED_LIMIT`) in the error note, the zero
  notes not strippable, "exactly" (`OPENER_VOCAB`) in the refusal. Reworded (section 1, item 3).
- **Final: 1 new trip, `SCOTS_CASELAW_GAP` on the case-law Worker prompt's PHASE 4 example** ("a Sheriff Court
  decision SCTS has not published"): a prompt, not an answer, and that detector fires on any mention of a
  Scottish court. **0 structure flags**: every footer is one `*Search scope:` line that `_without_footer` and
  `strip_answer_footer` strip whole, that `caselaw_gap_statements` reads as a disclosure, and that carries
  `CASE_LAW_CODE` exactly when no SCTS search ran ok; every note block holds no square bracket and
  `strip_scope_blocks` removes it.
- **Read, not only screened.** Reading the rendered notes found two faults the detectors could not: a query with
  its own quotes double-quoted (`""title to sue" widget"`) and an empty query rendered "the query the query". Both
  fixed in the Scottish note (today's Find Case Law note double-quotes too; left as it is).
- **P2.8's carried line** parses a footer with the new clause exactly as one with today's
  (`$C/p28_check_c.py` → `p28_check_c.out`: identical for today's, SCTS-ok and SCTS-errored clauses, with and
  without a Scotland filter).

**The three footer variants a lawyer can now read** (synthetic term; for Decision 1):

> *Search scope: for this reply the case-law databases (the National Archives' Find Case Law, and the Scottish
> Courts and Tribunals Service's published judgments) were searched for "widget duty". Between them they hold
> decisions of the UK Supreme Court and, from 1998, of the Court of Session, the High Court of Justiciary and the
> Sheriff Appeal Court, but not every Sheriff Court decision: the Scottish Courts and Tribunals Service publishes
> only some, and almost none in criminal cases, and neither database holds decisions of the courts of Northern
> Ireland. A search can miss a judgment a database holds, so one missing from these results may still exist, in
> these databases or elsewhere: that is not proof of absence. Where a rule of common law is taken from a judgment
> of a court outside Scotland, whether it also forms part of Scots law has not been checked.*

> *Search scope: for this reply the Scottish Courts and Tribunals Service's published judgments were searched for
> "widget duty". They hold decisions of the Court of Session, the High Court of Justiciary and the Sheriff Appeal
> Court from 1998, but not every Sheriff Court decision (only some are published, and almost none in criminal
> cases), not decisions of the UK Supreme Court and not those of the courts of Northern Ireland. A search can miss
> a judgment a database holds, so one missing from these results may still exist, in these databases or
> elsewhere: that is not proof of absence. A search of the National Archives' Find Case Law was attempted and
> returned an error.*

> (SCTS errored) today's line, with after its coverage sentence: *A search of the Scottish Courts and Tribunals
> Service's published judgments, which hold published decisions of those courts, was attempted and returned an
> error.*

The Worker-facing texts are the constants in the diff (`prompts.SCTS_PROMPT_WORDING`,
`schemas.SCTS_*_DESCRIPTION`, `search_scope.scottish_search_note` and the three zero/stop notes,
`executor.GET_CASE_LAW_TEXT_REFUSAL`, the PDF cap message in `scts.py`); all rendered in
`$C/screen_c_rendered.json` and `$C/wording_built.txt`.

**Other code texts about the same thing** (the lesson): `grep -rn -i "sheriff\|court of session\|justiciary\|find
case law" src` finds only the sites above, each either gated or today's text used only when the setting is off
(today's zero note in `agent_shared`, the tool descriptions in `CASE_LAW_TOOLS`, the prompt constants). No Manager
prompt or planner text describes case-law coverage. None contradicts the swapped wording once gated together.
**Not swapped, and true either way:** the doctrine sentence (kept when Find Case Law ran) and the synthesis's
"name the courts the cited decisions come from".

## 4. Live calls (27), and the door fault that cost 20

Every call went through one door, `$C/scts_door_c.py`: an httpx transport the BUILT product code ran through (the
executor's `httpx.AsyncClient` swapped for a client using it), enforcing the cap of 40 by reading its own log
before each call, at least 1.0 s from the end of one call to the next, https, the search path by POST and a `.pdf`
path by GET only, no query string; Find Case Law, LEX or anything else refused before a byte is sent (and not
counted). **Guards checked offline before the first call** (`door_check_c.py` → `door_check_c.out`, "ALL OK": 12
forms refused, call 41 refused against a fake log of 40, a 1.00 s wait, the real log untouched).

**Run 1 (calls 1-20) was wasted by the door**: it read each body decoded and rebuilt the response with the
original `Content-Encoding: gzip`, so the client failed to decode it a second time; the product's
`_request_with_retry` then retried each search three times. SCTS answered 200 every time. Fixed (decoded body, wire
headers dropped; a door failure after a call raised as a non-transport error so it is never retried), proven
offline on a gzip mock through the built `search_scts` before any further call (`door_check2_c.py` →
`door_check2_c.out`: one call, decoded once; a broken inner transport not retried), and run 2 stopped itself at the
first error or at 30 calls in the log.

**Run 2 (calls 21-27), `$C/live_probe_c.py` → `live_probe_c2.out`, `live_probe_c.json`** (generic doctrine terms
from `LEGAL_DATA_SOURCES` §3 only), confirms every shape the build reads:

| Step | Built call | Result |
|---|---|---|
| A1 | `search_scts('"title to sue" Wednesbury')` | sent `+"title to sue" +Wednesbury`; 16 (batch 11 D: 16); 10 rows; keys `title, court, judges, decision_date, published, ncn, url`; all URLs pass the text-route allowlist |
| A2 | same, decided 2006-01-01 to 2008-12-31 | 5 rows, every `decision_date` inside the window |
| A3 | `... OR "locus standi" ...` | sent `+("title to sue" \| "locus standi") +Wednesbury`: 17 (the alternation works) |
| A4 | `'"title to sue" zqxjkvwpqz'` | all-terms 0, then the any-term fallback: 354, `match: any` (2 calls) |
| B | `execute_worker_tool("search_case_law")`, setting on | Find Case Law refused by the door, so `error: "The Find Case Law search failed (ConnectError)."` beside `scottish.status: ok`, 5 Scottish rows |
| C | `execute_worker_tool("get_case_law_text")` on B's first URL | 389,235-byte PDF, 106,520 characters of text, citation read, title/court/date from the search |

13 of the 40 unused.

## 5. The PDF path and the slimmer over batch 11 D's stored responses (no network)

`cd server_py && python ../docs/prepilot-fixes/evidence/seam/batch12/C/pdfs_c.py` → `$C/pdfs_c.out`:
- **40 stored PDFs** read by the built `_pdf_text`: same character count as D's pdfplumber read on **40 of 40**;
  the built text citation equals D's on 40 of 40; filename citations present on 25, text citations on 31, both on
  24, **agreeing on 23** (the 24th: section 1, item 1); either present on 32.
- **93 stored search bodies** (757 rows) through the built slimmer: 757 rows kept (no repeats in those pages),
  `decision_date == additionalDate` on 757 of 757.

## 6. Tests, the revert and the mutants

`server_py/tests/test_scts_caselaw.py`, **116 tests**, every HTTP call an `httpx.MockTransport`, a minimal PDF built
in the test (pdfplumber reads it), synthetic names only. Sections: the query forms; citations and the slimmer; the
search (request shape, window, fallback, short-page count, errors, cap, request state, concurrency, titles); the
text (allowlist, pdfplumber off the loop, guards, cap); the executor (both lists, the research-type gate, either half
failing, a bad date refused before either call, text routing with the setting on and off); the notes and the rail;
the footer (byte-identical without an SCTS record, each variant, one stripped line, no detector); the prompts and
tools; caching; the grader.

- **Full revert** (`$C/revert_c.sh`: the base's `src/` and `tools/` with the built tests): **fails at
  collection** (an import error). The revert removes **1,324 added lines** (and restores 61) across 8 files
  (`git diff --numstat a99e4d4 -- server_py/src server_py/tools`). As rule 5 says, that proves only the import, so:
- **Single-site mutants** (`python docs/prepilot-fixes/evidence/seam/batch12/C/mutants_c.py` → `$C/mutants_c.out`;
  each anchor asserted once, CRLF-safe, on a scratch copy): **66 of 67 caught**. Every guard and cleaning step has
  one: bracket cleaning, negation and `NOT` handling, `AND`, inner punctuation, the single-term rule, the OR group,
  the filename lookahead, the text head limit, the dedupe, filename-only citations, the decision date, the fallback,
  the short-page count, the search cap and its counter, fail-soft, a failed fallback, the request state (kept, never
  on the shared default), the semaphore's size, the setting and research-type gates, https / exact host / `.pdf` / no
  query, PDF magic, size cap, empty text, `to_thread`, the PDF cap, both citation orders, the executor's three
  gates and the refusal, the note branch, both stop-rule conditions, both zero-note conditions, the rail, the
  footer key, the errored sentence, the doctrine sentence, the record's guard, the note's bracket and quote
  cleaning, all/any forms, the empty query, the five prompt wirings, the tool gate and deep copy, and the grader's
  seven conditions. **The one survivor is equivalent**: the grader removes the footer before counting
  scotcourts links, and no footer the product writes carries a link (`ANSWER_FOOTER` strips only the
  `*Search scope:` line). Four survivors of the first mutant run were real test gaps and were closed (fail-soft,
  the semaphore — my `net` fixture had stubbed `asyncio.sleep` module-wide, so nothing overlapped —, look-alike
  hosts, the any-term and empty-query note wording).
- `tests/test_case_law_gap.py`, `test_caselaw_window.py`, `test_caselaw_retry.py`, `test_drafting_security.py`: pass
  unchanged.

## 7. The grader: `replay_report scts`

Added to `server_py/tools/replay_report.py` only: the `scts` subparser (after `caselaw`'s), the `"scts": cmd_scts`
dispatch entry (after `"caselaw"`), and one block of functions before the P2.7 pre-flight section (`SCTS_CODE_BOTH`,
`SCTS_CODE_ONLY`, `scts_rows`, `scts_verdicts`, `cmd_scts`). **Nothing in `rail` or `lookup`** (agent D's).

Per answered turn: SCTS searches and how many ran ok; distinct SCTS judgments returned (searches and text fetches);
how many of those the prose links (footer removed); the old and new coverage sentences; Find Case Law links that are
not UK Supreme Court (for the hand-read of English authority presented as Scots law). Verdicts: **OLD_SENTENCE** (an
ok SCTS search and `CASE_LAW_CODE` in the answer: acceptance clause 3), **MISATTRIBUTED** (the new sentence with no
ok SCTS search), **UNRETURNED** (a scotcourts link no SCTS call returned that turn), **UNCITED** (with
`--require-cite`: an ok SCTS search and no returned judgment linked; clause 2's code half). Exits 1 on any finding,
and when no turn ran an ok SCTS search (nothing graded). **Before-column** (`$C/grader_before_c.py` →
`grader_before_c.out`): all 66 directories with run files exit 1 with "No turn ran an ok SCTS search", 0 findings.
For the acceptance: `python -m tools.replay_report --dir <sweep> scts --require-cite --only 6375`, then `scts` on the
controls, plus P3.3's hand-read for English authority.

## 8. The acceptance, priced

From every stored run (`$C/price_c.py` → `price_c.out`; all on the pinned Gemini):

| Session | Stored cost a rep | Case-law searches / texts a run (non-memo) |
|---|---|---|
| 6375 | median $1.28 (27 runs), wave4 median $1.40 (12), max $1.80 | 23.0 / 11.6 (max 44 / 20) |
| 6370 | median $0.78 (18), wave4 median $0.80 (15), max $1.40 | 8.4 / 1.7 |
| 6380 | $0.12-0.20 (3 runs, `baseline` to `wave2` only) | 3.0 / 2.0 |

The Scottish list adds about 4K characters a search to the Worker's context, re-sent each later round: an estimate
(not measured; no draw was made) of **about +15-25%** on case-law-heavy turns. **6375 n=3 about $4.80-6.75, up to
about $7.50 with one capped runaway (P4.10's ~$0.77); 6370 n=1 about $0.95-1.70; 6380 n=1 priced at $0.40. Total
about $6.20 at the median, about $9.60 at the high end** (batch 11 D's $4.90-8 used all-directory medians and no
uplift). **Live SCTS calls:** searches x about 1.5 (17 of 33 Scots-law queries returned 0 with every term required,
so about half make the fallback) plus Scottish text fetches: about 45 a 6375 rep, about 20 for 6370, about 7 for
6380, **about 160 in all; at most about 300 by the per-request caps**. The sweep needs `SCTS_CASELAW_ENABLED=true` in
the dev box's `server_py/.env` (never `.env.native`) and pdfplumber installed (it is, 0.11.10).

## What I did NOT do

No model call, seam draw, replay or server. No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `CLAUDE.md`, `CHANGELOG.md`,
`docs/LEGAL_DATA_SOURCES.md`, `docs/NETWORK_AND_DEPENDENCIES.md`, `server_py/test_apis.ps1`, `docs/api/AUDIT_TRACE.md`,
`docs/TODO.md`, the external-apis skill or any memory file. `caselaw` and agent D's `rail` / `lookup` untouched. No
`tools/scts_probe.py` (batch 11 D suggested one; not in this brief). No appellate-decision nudge across the two lists
(`detect_appellate_decisions` still reads Find Case Law's list only; an Outer House judgment and its Inner House
reclaiming motion are not linked). No change to the summarisation path or `WORKER_CONTEXT_BUDGET_CHARS` (SCTS texts
are a third the size of Find Case Law's). The +15-25% context uplift is an estimate, not a measurement. 13 of the 40
agreed calls unused.

**For the integrator, when merging** (not done here): `LEGAL_DATA_SOURCES.md` §3 and the external-apis skill ("Still
not called by the product" becomes "called, behind `scts_caselaw_enabled`"; the `+( | )` alternation confirmed
live; the citation-order finding); `AUDIT_TRACE.md` (two new `api_calls` URLs under `search_case_law` and
`get_case_law_text`, and the `scottish` / `scottish_results` keys in `raw_result`); CLAUDE.md's case-law notes; the
CHANGELOG; and, when the whitelist is in place, `NETWORK_AND_DEPENDENCIES.md`, `test_apis.ps1` and the offline
bundle (pdfplumber with pdfminer.six, Pillow and pypdfium2; TODO T3).

## Decisions for the user

1. **The lawyer-facing footer wording (section 3).** (a) *Recommended:* approve as built; every variant was screened
   (0 new trips on any footer) and still says what SCTS does not hold. (b) Add to the both-ran variant one sentence
   from today's ("Find Case Law's results for a Scottish question may come from courts outside Scotland"): today's
   line had it and the doctrine sentence only implies it, at the cost of a longer line. (c) Reword "from 1998, of
   the Court of Session, the High Court of Justiciary and the Sheriff Appeal Court" so the date is not read as
   applying to the Sheriff Appeal Court (created 2015-16).
2. **The Worker-facing wording** (the nine prompt pairs, the two tool descriptions, the notes, the refusal and cap
   messages). (a) *Recommended:* approve as built. (b) Approve without the prompt's "for a question of Scots law,
   cite the Scottish decisions that bear on it" instruction, leaving coverage to code alone (Invariant 2 already
   holds: both lists are always returned).
3. **The switch.** (a) *Recommended:* the env setting `SCTS_CASELAW_ENABLED`, default off, as built: it cannot be
   switched on on the target by an Admin Portal click before the hosts are whitelisted. (b) An Admin Portal feature
   flag, defaulting OFF (the house's flags default ON, so this would be the first that does not).
4. **The rate controls** (SCTS stated no limit). (a) *Recommended:* 60 searches and 20 texts a request, 2 in flight
   process-wide, as built (sized to the stored maximum of 46 case-law searches a turn). (b) Lower (40 / 10 / 1),
   bounding SCTS load harder and capping a 6375 Deep Research turn's Scottish searches. (c) Higher.
5. **`get_case_law_text`'s host allowlist with the setting off.** (a) *Recommended:* keep it always on: it refuses a
   URL that is neither Find Case Law's nor an SCTS PDF, which no stored call used (952 of 952 were Find Case Law),
   and closes a fetch-from-any-host path. (b) Apply it only with the setting on, so the off state matches the base
   for unseen inputs too.
6. **An SCTS judgment's citation on the text fetch.** (a) *Recommended:* the filename's first, the text's as a
   fallback, as built (23 of 24 agree; the 24th is a misprinted text citation). (b) The text's first, as batch 11 D
   proposed.
7. **The acceptance sweep** (P3.20's row, refined). (a) *Recommended:* 6375 n=3 plus 6370 and 6380 n=1: about $6.20
   at the median, about $9.60 at the high end; about 160 live SCTS calls (at most about 300 by the caps). (b) 6375
   n=3 only: about $4.80-7.50 and about 135 SCTS calls.
8. **The `caselaw` grader beside `scts`.** (a) *Recommended:* leave `caselaw` as it is and read `scts` beside it on
   an SCTS sweep; note that its `code` column keys on the old sentence, so on such a sweep it will print "No turn
   carries the code line" while its verdicts stay right (the new sentence still reads as a disclosure). (b) Teach
   its `code` column the two new openings (two lines, after agent D's merge, since both edit the file).
