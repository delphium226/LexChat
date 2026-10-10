# Parallel batch 11, agent D: P3.20 measured first (the SCTS judgments API)

Branch `worktree-agent-a955e98e806d274ef`. **$0 model spend**: no model call of any kind, no server, no
replay pin, run or restore, no seam draw. **134 live SCTS calls** (the user agreed at launch to up to 150):
**93 `POST https://api.pa.web.scotcourts.gov.uk/web/search`, 1 `GET .../web/definition/1414`, 40 `GET`
PDFs from `https://www.scotcourts.gov.uk`**. No other host. Every call went through one door, `$D/scts_b11.py`,
which enforces in code the cap of 150 (reading its own log back before each call), at least 1.0 s from the end
of one call to the start of the next, `https` only, the two hosts only and on each host only the agreed method
and path (the search path, the one definition path, a path containing `.pdf`), and logs method, URL, body,
status and bytes to `$D/scts_calls_b11.jsonl`. **The guards were checked offline before the first call**
(`python door_check.py` → `$D/door_check.out`, "ALL OK": 12 forms refused before any call, among them another
host, `http`, a GET of the search path, a POST to the definition, `/web/definition/1415`, the RSS path, a query
string, the `api.dv.` development host and a look-alike host; call 151 refused against a fake log of 150; a 0.99
s wait asked for after a call that had just ended; a stubbed call logged with method, URL, status and bytes; the
real log untouched, 0 calls). From the log (`python stats.py` → `$D/stats.out`): 134 calls, all status 200, 0
errors, minimum gap 1.00 s, 12,998,335 bytes; search median 198 ms (max 1,230), PDF median 242 ms (max 2,082).
No 429 or other throttling signal. The run was not interrupted.

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. With no commits of my own I
ran `git reset --hard 024e396096244e6ff4172f1a34f26eab38a3fd6a` first; everything here is based on `024e396`.

`$D` is my gitignored scratch, `docs/prepilot-fixes/evidence/seam/batch11/D/` in the worktree
(`git check-ignore -v`: `.gitignore:113`, `docs/prepilot-fixes/evidence/seam/`). Every command ran from `$D`
(or from the worktree's `server_py` where stated) with `PYTHONIOENCODING=utf-8`,
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d`.

**Changed:** nothing in the product, no grader, no test. One commit: this note. **Tests: 2833 passed** on
`lexchat_test_d` (`cd server_py && python -m pytest -q -p no:cacheprovider` → `$D/pytest_full.out`), the
base's count, as expected with no code change.

**How results are named here.** SCTS results returned for a session's queries are case names from that
matter, so this note names none of them and quotes no Worker query: each is cited by its key in
`$D/item1.json` (turn, then query rank by stored frequency, then result position, e.g. `6375:t2 q2 #2`). The
generic probes in section 2 (the ones `docs/LEGAL_DATA_SOURCES.md` §3 already prints) are named.

**pypdf was not measured.** It is not installed on this machine (checked in both interpreters, Python 3.14
and 3.12), and installing it needs PyPI, a host outside the agreed set. Section 4 compares pdfplumber (the
product's library) with pdfminer.six's own `extract_text`, which pdfplumber is built on. Decision 6 asks
whether pypdf is wanted at all.

---

## 1. The stored corpus: which case-law turns ask a Scots-law question, and what SCTS returns for them

**Census** (`python census.py` → `$D/census.out`, `$D/census.txt`; matter text, gitignored): **64 replay
directories, 538 run files, 2,177 turns; 407 run-turns called `search_case_law`, which are 44 distinct
(session, turn) pairs in 17 sessions** (13 export sessions plus the scripted `p41_6343`, `p41_6346`,
`p41_6346_dr`, `p46_6385`). The count includes every directory there is (there are 64; none excluded).

**Classified by the question and the stored answer** (`python context.py <sessions> 500`; I read the question
of all 44 and the opening of at least one stored answer of each, plus the earlier turns of each session for
context):

| Class | Session:turns | Distinct turns | Run-turns |
|---|---|---|---|
| **Scots law, case law could bear on it** (a Scottish Act, SSI or body, or a Scotland filter, and a point of interpretation or doctrine) | 6375 t1-t2 (acceptance); 6348 t4; 6380 t1-t2; 6370 t1-t6; 6338 t1-t3 | **14** | **201** |
| Scottish statute, and the question did not need case law | 6340 t1; 6354 t1; 6407 t1-t3; 6411 t1 | 6 | 24 |
| Jurisdiction not stated, UK or GB-wide law | 6335 t6-t7; 6359 t1-t7; 6363 t1-t5; 6385 t1, t3, t4; `p46_6385` t1, t3, t4 | 20 | 155 |
| English law, stated in the question | `p41_6343` t2; `p41_6346` t2-t3; `p41_6346_dr` t2 | 4 | 27 |

Sums: 44 turns, 407 run-turns. Two judgement calls, stated: 6363 (a definition question with the governing
legislation unnamed, the answers English) is "not stated", though a Scottish Government notice would make it Scots law;
6338 counts as Scots law although the P3.3 rubric's own reading makes its answer statutory. One anomaly: the
only 6348 t4 case-law run-turn (`wave3_p31_smoke/6348_rep1`) is recorded under `legislation_only`.

**The SCTS searches** (`python item1.py` → `$D/item1.out`, `$D/item1.json`; the selection was fixed in code
before any call: the top 1-6 distinct Worker queries of each turn by stored frequency, 43 planned, 42 sent, one
identical SCTS query reused with no call). Each Worker query was sent **through the proposed quoting rule**
(`$D/scts_query.py`, section 5: every quoted phrase and every other word required), `limit` 5.

| Turn | Queries | Totals | First five hold a Scottish judgment that bears on the question? |
|---|---|---|---|
| 6375 t1 | 4 | 1, 0, 0, 0 | **Yes, by text.** `q1 #1`, a 2011 Inner House judgment, records the doctrine P3.3's row names for 6375 asserted "under Scots law" and decides an argument on it (read in `texts/0087.txt`) |
| 6375 t2 | 6 | 1, 2, 0, 0, 0, 4 | **Yes, by text.** `q2 #2` and `q6 #1` are one 2026 Inner House FOISA appeal that discusses the privilege the question turns on under s.36(1) (read in `texts/0088.txt`); `q2 #1` a second 2026 FOISA appeal; `q6`'s four are Court of Session judgments containing the Act's title and its s.36 |
| 6348 t4 | 1 | 1 | **No.** The one hit (a 2009 Inner House FOISA appeal) names s.36 only in a list of exemptions (`texts/0091.txt`) |
| 6380 t1 | 1 | 99 | Not by title (judicial reviews; none about publishing a consultation response); unread |
| 6380 t2 | 3 | 40, 11, 47 | **Plausible by title, unread:** Court of Session judicial reviews of Scottish Ministers' decisions on the doctrine t2 asks about |
| 6370 t1, t2, t5 | 2 each | 0 in all six | No Scottish judgment contains the instrument's full title (t1, t2) or the t5 combinations |
| 6370 t3, t4, t6 | 2 each | 4, 18; 3, 6; 0, 2 | **Plausible by title, unread:** Court of Session judgments that contain the full title of the planning instrument the turns name (or its words) and the term the turns turn on (a 2024 Outer House judicial review and its 2025 reclaiming motion among them) |
| 6338 t1-t3 | 2 each | 6, 66; 0, 0; 0, 0 | No: titles unrelated to the interpretation point (the rubric's answer is statutory) |

**Counts:** over the 14 Scots-law turns, 33 queries; **16 returned at least one judgment, 17 returned 0** under
the all-required rule (`stats.out`). **2 turns (6375 t1, t2) have a Scottish judgment that bears on the
question confirmed by reading its text; 4 (6380 t2, 6370 t3, t4, t6) plausibly do by title (unread); 8 have
none.** Whether a judgment "bears on" a point of law is a legal reading; these are mine and should go to a
lawyer with the pack if they are to be relied on.

**6375, the acceptance session, in more detail** (4 more calls, `python item1b.py` → `$D/item1b.out`, shorter
forms a Worker reaches after a narrow first query, `$D/item1b.json`): 2, 3, 13 and 1 hits; the first two
hold the 2011 judgment above (and its first-instance decision), the third puts the 2026 FOISA appeal first.
**So SCTS holds what P3.3's rubric says our tools could not verify: Scottish judgments discussing the
doctrine 6375 turns on, and Court of Session FOISA authority on the privilege the question asks about.** It does not settle P3.3 (BLOCKED on the lawyer pack), but it changes what a 6375 answer can
cite.

**6359.** Both authorities the lawyer named are English Employment Appeal Tribunal judgments: SCTS returns
0 for each by party names (`6359:t6` keys). SCTS does not publish EAT decisions (the EAT is a GB tribunal
outside SCTS), so **SCTS cannot help 6359's named authorities**. A Court of Session appeal from the EAT in
Scotland could be held, but the 18 hits for the turn's stored query are, by title,
personal-injury and contract cases (`6359:t5 q1`). **6363 and 6335** (jurisdiction not stated) return 1-25
Scottish judgments per query, Sheriff Court and Court of Session, unread.

## 2. Search behaviour re-probed, and what changed since 2026-10-02

Commands: `python probe1.py` (2 calls), `probe2.py` (16), `probe3.py` (20); outputs `$D/probe{1,2,3}.out`,
`$D/definition_1414.json`, `$D/p2_*.json`, `$D/p3.json`.

| Check | 2026-10-02 | 2026-10-08 |
|---|---|---|
| Whole index (empty query) | 13,213 | **13,222** (+9) |
| `Wednesbury` | 528 | 529 |
| `"title to sue"` / `"Wednesbury unreasonable"` / quoted ILRA title | 354 / 123 / 27 | **354 / 123 / 27** (unchanged) |
| ILRA title unquoted | 12,703 | 12,712 (still OR) |
| Court values in `/web/definition/1414` | — | **13**: Court of Session, High Court of Justiciary, National Personal Injury Court, Sheriff Appeal Court Civil, Sheriff Appeal Court Criminal, Sheriff Court Civil, Sheriff Court Criminal, and six Upper Tribunal chambers (General Regulatory, Health and Education, Housing and Property, Local Taxation, Social Security, Tax) |
| Per court (13 calls, sum = 13,222) | CoS 7,121, HCJ 2,899, SC civ 1,986, SAC civ 410, SAC crim 157, PI 155, UT HPC 269, UT SS 96, SC crim 3 | CoS 7,125, HCJ 2,900, SC civ 1,988, SAC civ 412, SAC crim 157, PI 155, UT HPC 269, UT SS 96, **UT LTC 48, UT GRC 41, UT HEC 23, UT Tax 5**, SC crim 3 |

**Corrections and new findings:**
- **§3's coverage table omitted four Upper Tribunal chambers (117 judgments)**, which is why its rows summed to
  13,096 against a stated 13,213. The definition lists all 13 values.
- **A leading `+` makes a term or phrase required (AND), which §3 did not test and which decides the quoting
  rule.** `+"title to sue" +Wednesbury` gives 16, against 867 for `"title to sue" AND Wednesbury`; **`AND`
  and `and` are not operators** (`title AND sue` = `title sue` = 3,592; `+title +sue` = 801). A required
  stopword is ignored (`+Wednesbury +the` = 529). `*` is a prefix wildcard (`occupi*` 1,800). **`-` broadens**
  (`Wednesbury -"title to sue"` = 12,884: "any" semantics, so a negated term matches every document without
  it). Party names work as required words (3 words, 16 hits).
- **The total is exact as a row count, but rows can repeat.** `"title to sue"` paged at `limit=100` gave
  100 + 100 + 100 + 54 = 354 rows, **352 distinct `documentLink`s** (two Inner House judgments listed twice).
  Dedupe on `documentLink`. `limit=100` works; the definition's own page size is 50.
- **Order:** a query lists by relevance (not by date); an empty query lists newest published first.
- **A citation is not a lookup.** `"[2017] CSIH 28"` and `"2017 CSIH 28"` both give 3, the judgment itself
  third, after two that cite it. Square brackets make no difference.
- **The `Court` and `AdditionalDate` filters work** (`"title to sue"` + Court of Session: 263; four court-and-date
  searches, 80 rows, none with an `additionalDate` outside its window, `$D/item3_search.out`).
- PDFs are served directly (40 of 40 status 200, no redirect, 108,790-623,884 bytes).

## 3. Date reliability: `additionalDate` against the date printed in the judgment

Sample: **40 PDFs**, fixed in code before any PDF call (`python sample.py`, seeded; `$D/sample.json`):
5 item-1 candidates, 10 of the 21 rows whose filename citation year differs from `additionalDate`'s year
(over-sampled on purpose), and 25 across courts and eras (Court of Session 1998-2004, 2005-2012, 2013-2019,
2020-2026; High Court of Justiciary 1998-2004, 2013-2019, 2020-2026; Sheriff Appeal Court criminal and civil;
Sheriff Court criminal and civil; Personal Injury Court; Upper Tribunal). Rows came from the item 1-2 searches
and six court/era searches (`item3_search.py`, 6 calls). Fetched by `fetch_pdfs.py` (40 calls), read by
`python extract.py` (no network; `$D/extract.out`, `$D/extract.json`, `$D/texts/`), counted by `stats.py`.

**Against the date printed at the head of the judgment (the ground truth):**
- **36 of 40: `additionalDate` is the first date printed in the opening.**
- **1 of 40 wrong: off by three years** (a 2021 Sheriff Court note, `n=94`: printed "28 April 2021",
  `additionalDate` 2024-04-28, the year mistyped).
- 1 across a year end by 35 days (`n=106`: opinion printed 9 December 2011, `additionalDate` 2012-01-13,
  probably the date the written opinion issued; its citation is `[2012]`); 1 by 13 days within a year
  (`n=103`); 1 whose judgment prints only "December 2011" (`n=121`, consistent).

**Against the neutral citation's year:** over the 297 rows seen with a citation in the filename
(`python rows_seen.py` → `$D/rows_seen2.out`), **21 (7.1%) differ from `additionalDate`'s year: 15 High Court of
Justiciary, 6 Sheriff Court or Sheriff Appeal Court civil**, always a later citation year (1 to 4 years). In 9
of the 10 sampled, the printed date agrees with `additionalDate`: the citation carries the year the judgment
was issued or published, which for an appeal published late (common in the High Court of Justiciary) is
years after the decision. The tenth is the mistyped `n=94`.

**So §3's risk 2 was half wrong.** On 2026-10-02 a 2012 decision-date filter returned a `[2015] HCJAC` and a
2020 filter a `[2021] SC GLW`; that is this pattern (`n=98`-`101` reproduce it: decisions of 2010-2012 with
2013-2014 citations), and `additionalDate` was right. **The metadata error rate measured is 1 in 40 (2.5%),
and 2 in 40 (5%) if the year-end case counts.** The 40 are stratified and over-sample the mismatches, so this
is not an index-wide rate. One more trap: **a judgment can print its own citation wrongly** (`n=90` prints
a citation whose year is one earlier than the year its filename, the URL printed in the same PDF and its
decision date all give).

## 4. PDF text: pdfplumber and pdfminer.six on the 40

From `extract.py` / `stats.py` (this dev machine, Python 3.14):

| | pdfplumber 0.11.10 (product) | pdfminer.six 20260107 `extract_text` |
|---|---|---|
| Succeeded | **40 of 40** | 40 of 40 |
| Characters | 3,809-99,997, **median 24,777**, total 1,285,518 | 3,982-100,318, median 25,716 (median ratio 1.033: layout spacing) |
| Pages | 2-36, median 10 (median 1,972 characters a page) | same |
| Time per PDF | 0.07-1.48 s, **median 0.46 s**, 21.5 s for all 40 | 0.03-0.81 s, median 0.21 s |

**36 of 40 exceed 8,000 characters** (the summarisation fallback every stored replay ran at) and 10 exceed
50,000. For comparison, the stored Find Case Law judgment texts (`python fcl_sizes.py`: 947
`get_case_law_text` calls, 770 summarised, 204 distinct judgments) run to a **median 72,391 characters, p90
216,196, max 1,272,993**: SCTS judgments are a third the size, so they fit the existing path (section 5).

**Neutral citation:** in the opening text (`[YYYY] COURT N`, the first 4,000 characters) in **31 of 40**, and
in **31 of the 34 decided from 2005**; the 3 without are two Sheriff Court civil judgments of 2008 and 2011
(none printed) and one 2026 Upper Tribunal decision printed unbracketed (`2026UT70`). The filename carries a
citation in only **25 of 40**, so for modern judgments with a descriptive filename (7 here) the citation comes
from the text alone. All 6 decided before 2005 carry none, as expected.

## 5. The design, proposed

**Tool shape (Decision 1). Recommended: `search_case_law` searches both databases and returns two lists**,
`results` (Find Case Law, unchanged) and `scottish_results` (SCTS), each with its own count and window note,
when the feature is on. Reason: 6375's failure was the model answering a Scots-law question from what it got,
and Invariant 2 prefers code to obedience. A separate `search_scottish_case_law` tool would leave coverage to
the prompt, and the quick-lookup Worker is told to call `search_case_law` once. Cost: one SCTS POST per
case-law search (median 198 ms, about 2.5K characters slimmed at 10 rows). **The text fetch stays
`get_case_law_text`, routed by host**: a `caselaw.nationalarchives.gov.uk` URL as today, a
`https://www.scotcourts.gov.uk/media/…pdf` URL to the PDF route, anything else refused in code.

**Slimmed SCTS result** (per row, deduped on `documentLink`): `title`; `court` (the one-element list joined);
`judges`; `decision_date` (`additionalDate`, ISO date, labelled as the date of decision SCTS records);
`published` (`date`); `ncn` (from the filename only when it matches the citation pattern, else null, and never
used for a date); `url` (`https://www.scotcourts.gov.uk` + `documentLink`). Drop `sheriffdom` (empty in every
row seen), `tags`, `searchType`. Counts in P3.23's shape: `shown`, `total` (`pagination.count.total`),
`total_exact: true`. **The text fetch** returns `{url, title, ncn, text}` like Find Case Law's, with `ncn`
from the opening text (filename as fallback), the PDF parsed **off the event loop** (`asyncio.to_thread`:
pdfplumber is synchronous and took up to 1.5 s here, which would stall every other request), a size cap on
the download, and the PDF's own date line left in the text.

**Quoting rule** (prototype `$D/scts_query.py`, offline cases in its `__main__`): each quoted phrase becomes
`+"phrase"`, each other word `+word`; an `OR` between two items (the Worker writes it for Find Case Law)
becomes `+(a | b)`; `AND`/`NOT` and stray operator characters are dropped; a word with inner punctuation
(`3(2)(a)`) becomes a phrase; square brackets are removed. The Worker's query is unchanged for Find Case Law.
**Zero results (Decision 2): measured, 17 of 33 Scots-law queries returned 0 under all-required.** Re-running
four of them with the same terms and no `+` (`python item1c.py`, 4 calls): **2 of 4 useful** (both 6375 forms
put the FOISA judgments of section 1 in the first five; the 6370 and 6338 forms returned noise
led by single words). Recommended: one code fallback, stated in the window note (wording below).

**Window note** (Worker-facing, `[SEARCH SCOPE — …]` form so `_TOOL_BLOCK` strips an echo), proposed in
`$D/wording.py`: all shown, "all {n} judgment(s) in the Scottish Courts and Tribunals Service's published
judgments{limits} that contain every term of {q}, listed most relevant first, by relevance to the search words
rather than by date"; partial, "the first {n} of {total} … Another judgment that matches can sit outside these
{n}: to reach it, search again with narrower terms (a party's name, a court or dates) rather than treat this
list as complete"; fallback, "the first {n} of {total} judgments … that contain any of the terms of {q},
listed most relevant first: a query requiring every term returned 0. One that contains only some of the terms
may not answer the question." Limits read "(court: …; decided {from} to {to})". A zero-result note for the
SCTS half mirrors today's.

**Retry and counts:** both SCTS calls through `_request_with_retry` (POST supported; 429/5xx/transport
retried, a 400 returned at once), as P4.19 did for Find Case Law; counts as P3.23 (above). **Rate (Decision
4):** SCTS gave no limit; recommended a per-request cap on SCTS calls and a small process-wide concurrency
limit, both in code. **Dates (Decision 3):** the `AdditionalDate` filter is sound (section 3); recommended to
expose it as the date of decision, intersected with the lawyer's dates as `case_law_date_window` does.

**Caching:** SCTS is Crown copyright under the Open Government Licence, a public source, so the results of
`search_case_law` and `get_case_law_text` stay in `CACHEABLE_TOOLS` with SCTS content in them (same names; the
key is the raw result's hash, so the new shape misses old rows and needs no `_CANON_VERSION` bump). A test
must pin that the drafting override still forces the cache off. **Context budget:** SCTS texts (median 25K,
max 100K) are smaller than Find Case Law's (median 72K, max 1.27M), so the existing summarisation threshold
and the 250K `WORKER_CONTEXT_BUDGET_CHARS` cover them; nothing new is needed.

**Every gated wording site** (gate: one predicate, the feature on and the research type including case law;
the footer keys on what this turn's records show ran):

| Site | Today | Proposed when on (`$D/wording.py`) |
|---|---|---|
| `search_scope.CASE_LAW_COVERAGE_SENTENCE` and `_case_law_body`'s head (P2.4 footer) | Find Case Law holds UKSC Scottish appeals, not the Court of Session, SAC, Sheriff Courts or HCJ | Both ran: "the case-law databases (… Find Case Law, and the Scottish Courts and Tribunals Service's published judgments) were searched for …. Between them they hold decisions of the UK Supreme Court and, from 1998, of the Court of Session, the High Court of Justiciary and the Sheriff Appeal Court, but not every Sheriff Court decision: the Scottish Courts and Tribunals Service publishes only some, and almost none in criminal cases, and neither database holds decisions of the courts of Northern Ireland." SCTS errored: today's sentence (true of Find Case Law) plus "A search of … SCTS …, which hold those Scottish courts' decisions, was attempted and returned an error." Find Case Law errored: an SCTS-only coverage sentence |
| `CASE_LAW_ABSENCE_SENTENCE` | "the database" | "a database … these databases" when both ran |
| `CASE_LAW_DOCTRINE_SENTENCE` | | unchanged (still true), kept only when Find Case Law ran |
| `case_law_search_note` / new SCTS note; `agent_shared` zero note | Find Case Law only | as above |
| `prompts.WORKER_SYSTEM_PROMPT_CASE_LAW` (mandate line, DATABASE COVERAGE) | "holds NO decisions of the Court of Session …" | both databases described, `scottish_results` named, "do not present a decision of a court outside Scotland as stating Scots law" |
| `WORKER_SYSTEM_PROMPT_HYBRID` PHASE 3 coverage; `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` case-law line | Find Case Law only | both lists named |
| `_JURISDICTION_EXTENT_NOTES["scotland"]`; `_SYNTHESIS_SOURCES` (case-law types) | Find Case Law only | SCTS named |
| `schemas.CASE_LAW_TOOLS` (both descriptions) | Find Case Law only | both databases; `court` applies to Find Case Law only; the required-terms rule stated |
| `tests/test_case_law_gap.py` | pins the four absent courts at every site | parametrised on the gate: off, every text byte-identical to today; on, no site says the Court of Session is absent from the databases searched, and each keeps the residual gaps |

Every proposed variant keeps stating what SCTS does not hold: Northern Ireland, unpublished Sheriff Court
decisions, criminal sheriff decisions almost absent (and pre-1998 decisions).

**Screened** (`cd server_py && python ../docs/…/batch11/D/screen_d.py` → `$D/screen_d.out`; `b9_screen.py`
copied from the integrator's scratchpad, running this worktree's `tools/replay_report.py`; 13 texts, 12
footer lines (3 variants x standalone and joined x 1 and 3 terms), 49 notes (3 queries, among them one with a
citation in round brackets, x 4 limit forms x (3 count shapes and the fallback), plus the zero note)). Today's
built text at each site is screened too, so only **new** trips count. Two wordings were changed on the
screen's evidence (the tool description's "filter" tripped `NEG_LIMITS`; the first fallback wording tripped
`NEG_ASSERTED`, then `NEGATIVE_EXPLAINED` and `OPENER_VOCAB`). **Final: 24 new trips, all
`SCOTS_CASELAW_GAP` on notes whose limits name a Scottish court** (that detector fires on any mention of the
Court of Session; the block is Worker-facing and `strip_scope_blocks` removes it whole); 0 others. All 12
footer lines are one `*Search scope:` line, stripped whole by `_without_footer`, read as a disclosure by
`caselaw_gap_statements`, and none carrying today's `CASE_LAW_CODE` sentence on a variant where SCTS ran. The
zero note is no more strippable than today's (checked). **These are prototype strings, not built text: the
build must re-screen what its code renders.**

**What the graders need** (C's file, so for the integrator): `replay_report caselaw` identifies the code's
line by `CASE_LAW_CODE` (today's opening), so a both-ran footer is "disclosed" but not "code"; it needs the new
opening as a second constant, and a new check for the acceptance's third clause (an ok SCTS search this turn
and `CASE_LAW_CODE` in the footer is a FAIL). The other code texts that speak of the same thing: P3.3's
6375 grading of English authority presented as Scots law, the P2.4 footer, the prompts above; none
contradicts the proposal once gated together.

**Deployment changes** (none made): `docs/NETWORK_AND_DEPENDENCIES.md`, the two hosts in the three tables
that list Find Case Law (lines 69, 107, 132: purpose, required-for, TLS-inspection bypass); `server_py/
test_apis.ps1`, a `POST /web/search` (`limit` 1) and a GET of the PDF it names, beside the case-law checks at
line 40; the offline bundle (`docs/TODO.md` T3, `requirements.txt` line 6): `pdfplumber==0.11.10` pulls in
`pdfminer.six==20260107`, `Pillow>=12.2.0` and `pypdfium2>=5.9.0`, all of which must be in the bundle; the
external-apis skill and `docs/LEGAL_DATA_SOURCES.md` §3 (the corrections in sections 2-3); a
`tools/scts_probe.py` like `caselaw_probe` that re-checks the `+` semantics, the total, the court values and
the date filter live, so a change to the search is seen. `docs/api/AUDIT_TRACE.md`: a new `api_calls` URL
(the SCTS POST) under `search_case_law`.

**Acceptance, refined** (the row's three clauses, made gradable):
1. *Deterministic:* unit tests at the slimmer (dedupe, `decision_date`, filename citation only on a pattern
   match, URL host), the quoting rule (every form above, plus the empty query, refused), the window notes
   (each variant), the footer (each variant; gate off byte-identical), the host allowlist on the text route,
   the PDF parse off the event loop, `CACHEABLE_TOOLS` and the drafting override; each failing with the
   change reverted and single-site mutants for each guard (the dedupe, the citation pattern, the bracket
   cleaning, the zero fallback, the gate).
2. *Replay, 6375 n=3:* every rep's answer cites at least one judgment that an SCTS search or text fetch
   returned that turn (a `scotcourts.gov.uk` URL from the audit), and presents no English authority as Scots
   law (P3.3's 6375 criterion; P3.3 itself stays BLOCKED on the lawyer pack).
3. *Replay, the same reps:* no footer on a turn with an ok SCTS search carries `CASE_LAW_CODE`.
4. *Controls, n=1 each (proposed):* 6370 (the Scottish planning turns that section 1 shows SCTS can reach; P3.3's
   6370 criteria must not regress) and 6380 (a Scotland filter).

**Price** (stored costs, pinned Gemini; `python costs.py` → `$D/costs.out`): 6375 $0.70-1.80 a rep, median
$1.28, so **n=3 about $3.85, $5.39 at the stored maximum, about $6.50 with one P4.10-capped runaway**; 6370
n=1 $0.72-1.00 (`wave4_b2_post`, `wave4_b4_post`); 6380 n=1 $0.12-0.20 (stored only in `baseline` to
`wave2`; price at $0.40). **Total about $4.9 at the median, $8 at the high end.** It also makes **live SCTS
calls**: 6375 averaged 2.4 case-law searches on turn 1 and 23 on its Deep Research turn 2 (61 over 25 and 620
over 27 stored runs), so about 26 SCTS searches and up to about 10 PDFs a rep, **about 110 for n=3 and about
135 with the controls**: a volume the user should agree, given no stated SCTS limit.

## What I did NOT do

No product code, no grader edit, no test change, no seam draw, no replay, no server. No external host but
the two SCTS hosts. pypdf not measured (not installed; PyPI not agreed). The relevance of SCTS results to
6380, 6370, 6363 and 6335 is judged by title only; I read the text of the 6375 and 6348 candidates alone.
`/web/rss/Judgments` not called (outside the agreed set). No index-wide date-error rate (the sample is
stratified and over-samples mismatches). 16 of the 150 agreed calls unused.

## Decisions for the user

1. **Tool shape.** (a) *Recommended:* `search_case_law` searches both databases and returns two labelled
   lists; coverage is code-enforced (Invariant 2), at one extra SCTS call per case-law search. (b) A separate
   `search_scottish_case_law` tool: cleaner shapes, but whether Scottish judgments are searched is left to the
   prompt, as in 6375. (c) SCTS only when the jurisdiction filter is Scotland: misses 6375, which had none.
2. **SCTS zero results under the all-required rule (17 of 33 Scots-law queries).** (a) *Recommended:* one code
   fallback to the same terms in "any" form, stated in the window note (2 of 4 useful measured). (b) No
   fallback; the zero note asks the Worker to search again with fewer terms (costs model rounds). (c) Fallback
   requiring the quoted phrases only (untested).
3. **Date filter.** (a) *Recommended:* expose `AdditionalDate` as the date of decision (36 of 40 exact, 1 of 40
   wrong); never derive a date from the citation. (b) No date filter in the first build.
4. **Rate control for SCTS (no limit given).** (a) *Recommended:* a per-request cap on SCTS calls plus a small
   process-wide concurrency limit, in code, with `_request_with_retry`. (b) A global pace of one call a second
   (slows parallel Workers). (c) Retry only.
5. **Ask SCTS in writing** (with the written confirmation already carried): (a) *Recommended:* one email
   covering confirmation, any rate or volume limit, notice before the search changes, and attribution wording.
   (b) Confirmation only. (c) Nothing further.
6. **pypdf.** (a) *Recommended:* not needed; pdfplumber, already a dependency, extracted 40 of 40. (b) Add pypdf
   as a fallback extractor (a new dependency in the bundle).
7. **Acceptance sweep.** (a) *Recommended:* 6375 n=3 plus 6370 and 6380 n=1: about $4.9-8 and about 135 live
   SCTS calls. (b) 6375 n=3 only: about $3.9-6.5 and about 110 SCTS calls.
8. **Graders (C's file; for the integrator to schedule).** (a) *Recommended:* add the new code-sentence
   opening and the "SCTS ran and `CASE_LAW_CODE` present" check to `replay_report caselaw` in the build
   session. (b) Grade the third acceptance clause by hand.
