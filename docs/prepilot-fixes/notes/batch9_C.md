# Parallel batch 9, agent C: P3.21 built (the commencement date from legislation.gov.uk's record)

Session 41, 2026-10-06. Branch `worktree-agent-aa4bf3414d4fd6e5f`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard ca3d45ca0e4705123aa23ed0c7fc0c1ab9a77918` before any work.** Everything below is
based on `ca3d45c`. Two commits: `36ddcee` (the build) and `0f159e7` (the Worker's static texts,
separable: decision 2).

**Spend: $0 in model spend.** No model call, no server, no replay pin/run/restore. **Live calls, as
agreed at launch: 35 LEX calls (cap 40, enforced in code by `lexcall.py`, which reads its own log
before every call), paced at least 0.6 s apart, every call logged (method, URL, status, bytes) in
the gitignored `calls_lex.jsonl`. No other host.** Full suite on `lexchat_test_c`: **2539 passed**
(2482 + 57 new).

This note names no instrument, title or question from a session; a session's instrument is named by
its role. Commands run from the scratch `$C = docs/prepilot-fixes/evidence/seam/batch9/C` (gitignored:
`git check-ignore -v` gives `.gitignore:113:docs/prepilot-fixes/evidence/seam/`) with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`, `PYTHONIOENCODING=utf-8`, and
`$S` = this worktree's `server_py`; every script that imports product code asserts it imports `$S`
(repoint, do not edit, to re-run on the merged tree).

## 0. The output shape (agent E's input). It differs from the brief's in one respect.

On a `get_legislation_changes` result, **direction `"to"` only**, whose LISTED groups include a
`coming into force` group made by another instrument (`self: false`):

- **Each `changes` entry the record dates** gains two keys:
  `{"by": "reg. 2", "changed": ["s. 1", "s. 2"], "in_force": "YYYY-MM-DD", "qualification": "wholly in force"}`.
  `qualification` is the feed's own string, verbatim, present wherever the feed gives one (it did
  on every stored effect): "wholly in force", "for specified purposes", "in force in so far as not
  already in force", "for E.", "for W.", "for S.", "for N.I.", the "for X. for specified purposes"
  forms, "Other" and "coming into force in accordance with".
- **An entry whose provisions take different dates is SPLIT**, one entry per (date, qualification),
  so **the same `by` can appear on several entries of one group**; a provision with two dated
  effects (2 relations in the saved feeds) appears under both dates. Provisions the record does
  not date stay together in one entry in **exactly the old shape** `{"by", "changed"}` (no
  `in_force` key, never `null`). Order within a `by`: dated entries by date, then the undated one.
- **Result level, `commencement_dates` is a DICT whose `status` holds the brief's value** (this is
  the difference: the brief listed the values, not the container):
  - `{"status": "retrieved", "source": "legislation.gov.uk's Changes to Legislation record, read through the LEX API", "relations": <listed commencement relations by another instrument>, "dated": <of them dated>, "refused": <of them refused>}`,
    plus, only when they apply: `"refused_instruments": [ids]` (a date earlier than the
    instrument's made date), `"made_date_not_read": [ids]` (made date not read: no answer within
    8 s, an error, or beyond the 8-read cap; their relations carry no date), and
    `"feed_window": {"read": N, "total": M}` (the feed had more effects than 2 pages hold).
  - `{"status": "not_retrieved", "reason": "no_reply" | "http_<code>" | "unreadable" | "error"}`;
    the record is otherwise exactly as before. (Not "timeout": `replay_report`'s `HALT_AS_TIMEOUT`
    reads answers for that word, and the reason reaches the model.)
  - **Absent** when no hop ran: direction `"by"`, no listed commencement by another instrument,
    an id that is not a plain path, or a result not in our shape.
- `"retrieved"` with `dated: 0` is possible (nothing matched, or every date refused or unchecked);
  the wording treats it as "found nothing" (unchanged).
- Never in the result: a refused date or a made date (so the model cannot echo either).
- Pinned by `tests/test_commencement_dates.py::test_the_output_shape`.

**For E's grader:** a date an answer states for a provision is backed by an `in_force` on an entry
whose `changed` lists that provision, in the group whose `legislation_id` is the commencing
instrument named (and, for an instrument, by any `in_force` in its group). Existing graders were
checked against the new shape:
`negcurrency` reads `changes` through `_nc_changed_provisions`, which de-duplicates (a split entry
changes nothing); `currency` and `commencements` read counts and group ids, unchanged.

## 1. What I built, and why

**`server_py/src/agent/tools/commencement_dates.py` (new, 551 lines)**, called from the executor's
`get_legislation_changes` branch after the slimmer (12 lines in `executor.py`):

- **The feed:** the subject's `changes/affected/<id>/data.feed?results-count=500[&page=2]`, the
  whole path and query URL-encoded into one segment of `GET {LEX}/legislation/proxy/{segment}`
  (as `lgu_probe --via lex` does); at most 2 pages; one read per change-record call; **memoised per
  request** (the request's config dict, shared by reference by every tool call of the request;
  with no request config, no memo) **with the slot reserved before the `await`** (an
  `asyncio` task stored first: A2's P3.12 lesson), so a batched round on one subject reads once;
  a failure is memoised too, for that request. A failed page 1 fails the hop; a failed page 2
  keeps page 1 and states the window.
- **Matching:** each listed relation on (changed provision, commencing instrument, affecting
  provision), scheme-free (ids are short ids) and case- and space-normalised, against the feed's
  dated `coming into force` effects of the subject by another instrument (batch 8 D's
  `compare_commencements`, re-implemented: product code does not import `tools/lgu_probe.py`).
- **The made-date check, and where the made date comes from.** A date earlier than the commencing
  instrument's made date is refused. **The made date is legislation.gov.uk's own metadata:**
  `ukm:Made` (an SI) or `ukm:EnactmentDate` (an Act) in `/<id>/introduction/data.xml`, read
  through the same proxy (checked live: 7.6 KB for a commencement order, 2 calls). The feed carries
  no made date (every attribute and element of the 29,932 effects in D's saved feeds read:
  `census_feed.py` and the element census in this session), and LEX's lookup has none for SIs
  (in D's `raw_lex/` lookups of the 157 commencing instruments: `enactment_date` null on 148 of the
  149 held, the one exception an Act; 8 not held). **A date whose
  made date could not be read is not given** (it could not be checked). At most **8 made-date reads
  per change-record call** (4 at a time, beside the feed read): over the 1,094 stored `"to"` calls
  in batch 8 D's collection (58 directories), 354 list a commencing instrument by another, median 2,
  p90 6, max 14; 8 covers 929 of their 981 instruments (95%) and 337 of the 354 calls in full
  (`python $C/census_calls.py`). **Made dates
  read are kept for the life of the process** (they never change; only a successful read is kept;
  bounded at 4,096); the cap counts reads, so a held made date costs none. That store is my
  addition, made after the live smoke (decision 1).
- **Bounds:** an 8 s timeout on every phase of every read, one attempt, no retry (the decided
  bound; `_request_with_retry` would multiply it). Fail-soft throughout: the hop never raises.
- **Safety:** a response with a `<!DOCTYPE`/`<!ENTITY` is refused before parsing; a non-feed 200
  (an error page) is "unreadable", never "no effects"; ids that are not plain paths are never put
  in a proxy path.

**The wording, gated in `server_py/src/utils/search_scope.py` (232 lines added, 6 removed)** on the
hop's result read off the record (`_commencement_dates`: the gate is an entry that really carries
`in_force`, not the count alone): unchanged where no hop ran or it dated nothing; where it dated
something, the date is said to be the day the named instrument brought the provision into force,
with its source and qualification, never in-force status today (P2.5); the repeal half unchanged
(no repeal is dated). A failed read adds one sentence to the Worker's note and changes nothing else.
The recorders (`record_relations`, `record_currency`) carry a `dated` count for the limbs and footers.

**`conftest.py` (22 lines):** an autouse fixture makes the hop's client refuse every request in
every test (no test may reach the network; tests that patch `_request_with_retry` would otherwise
have let the hop call LEX) and empties the made-date store per test.

**`lex.py`:** one comment sentence in P3.5's block (no code), outside `_slim_search_results`.

**Commit 2 (`0f159e7`), the static texts** (decision 2): the tool description and three prompt
sentences said the record has no dates and cannot be gated; reworded to be true with a date and
without (schemas.py 5/2 lines, prompts.py 3/3; no line D's brief names).

## 2. The dry run, with the BUILT code ($0, no call)

```
python $C/dryrun.py $S --list --cold     # dryrun_summary_cold.txt (= dryrun_summary.txt), dryrun_list_cold.txt (ids)
python $C/dryrun.py $S                   # dryrun_summary_warm.txt (the made-date store kept across the corpus)
python $C/acceptance.py $S               # acceptance.txt (6409 and 6411, ids)
```

Globs **all 59 replay directories** (503 run files, `wave4_b8_sweep` included). Each stored
change-record call is re-slimmed from its stored `/amendment/search` rows by the built slimmer (the
"before") and run through the built hop (the "after"), the HTTP served by a mock transport:
**the feed from batch 8 D's saved affected feeds** (`raw_lgu/`, mapped by URL from
`log_lgu.jsonl`) and **the made date** real where one was read (D's one, plus the 13 read live
here: `made_live.json`), else a synthetic page whose `ukm:Made` is 1 January of the instrument's
own year (the earliest its number allows), so the dry run's refusals are those the year or a real
made date catch. Memo hits are rebuilt from the same turn's earlier call. Wording rebuilt with the
product's recorders and builders, per call, per delegation and per turn.

- **Tool results: 1,515** (1,215 that reached the API + 300 memo hits): 1,425 `"to"`, 90 `"by"`.
  **The hop ran on 430** (all `"to"`), absent on 1,085. **Calls with no saved feed: 0** (every hop
  subject has one; the served 404 count is 0). All 430 `retrieved`, all 430 dated something.
- **Relations** (listed commencement relations by another instrument, per tool result, repeats
  counted): **23,363 listed, 22,777 dated (97.5%)**; 586 not dated: **79** no matching feed effect
  (D's label-rendering twins and one empty provision), **319** beyond the 2-page window (17 tool
  results cut, on 5 subjects), **184** made date not read (the cap; 22 tool results; with the store
  kept across the corpus, 78), **4** refused.
- **Every date refused: 4 relations, 1 tool result** (in a `wave2` directory): the one feed error D
  found, refused against the instrument's real made date (read live). **No other date was refused:
  2,934 dated provisions were checked against a real made date** (13 commencing instruments whose
  made date was read live), the rest against the year bound.
- **Nothing else moved:** in all 430, no key other than `related[].changes` and
  `commencement_dates` differs, every listed (changed, by) pair is kept and none is invented
  (`compare_dicts`); entries split: +689 entries. Qualifications on dated entries: wholly in force
  2,425, for specified purposes 996, in force in so far as not already in force 752, Other 95, for
  W. 41, for E. 39, for E. for specified purposes 22, for W. for specified purposes 17, for N.I. 5,
  for S. 5, for N.I. for specified purposes 2, coming into force in accordance with 2.
- **Wording sites that move:** the Worker's note closing on **430 of 1,515** tool results (all to
  the dated closing; the not-retrieved sentence cannot occur in a dry run whose feeds are saved);
  **`_relations_limb` 388 of 859 delegations; `_currency_limb` 388 of 859** (the commencement line
  and the dropped "again"); **`_relations_footer_clause` 313 of 539 turns; `_currency_footer_clause`
  313 of 539 turns.** `_relation_currency_limb`'s "either" moves inside the note.
- **Size:** growth per hop result median 657, p90 2,157, max 16,749 characters (largest result
  60,641). Results over the summarisation threshold: on a 128K-token model (51,200 chars) 2 before,
  2 after; on the pinned Gemini (200,000) 0 and 0.
- **6409:** 62 stored change-record tool results on its Act, all `retrieved`, **8 of 8 relations
  dated, both commencing instruments, each with a qualification** (one "wholly in force", one "for
  specified purposes"). **6411:** 8 stored calls, **hop absent in all 8** (its Act has no
  commencement by another instrument), so every wording site is unchanged: the negative branch.

**Input forms no stored run contains, tested on synthetic input** (`tests/test_commencement_dates.py`):
a failed feed (no answer within 8 s, a connection error, HTTP 502, HTTP 429, an error page); a failed
second page; a made date not read (timeout) and its retry by the next request; more than 8
commencing instruments, with and without held made dates; a non-ISO date in the feed or the
metadata; a `DOCTYPE`/entity declaration; a non-path id; two calls on one subject in one batched
round (the stored runs are sequential); a status claiming dates with no dated entry.

## 3. Live calls (35 of the 40 agreed, all to LEX)

```
python $C/probe_made.py <2 introduction paths>          # which document carries the made date: 2 calls
python $C/smoke.py $S <6409's Act> <6411's Act> <a UK Act with a 2-page feed>   # 15 calls
python $C/replay_smoke.py $S <the UK Act>               # $0: the 3rd subject re-run over its logged responses
python $C/smoke.py $S <a Scottish Act> <6409's Act> <6409's Act>                # 16 calls
python $C/made_from_log.py $S                           # the made dates read, into made_live.json
```

By kind: **7 `POST /amendment/search`, 6 `GET` proxy feed pages (6 of 6 answered: median 215 ms,
max 418 ms), 22 `GET` proxy introductions (17 answered: median 358 ms, max 4.7 s; 5 gave no answer
within 8 s, all during hops: 5 of 20 hop reads, 25%).** The smoke's transport serialises the reads to
pace them, so its wall times overstate the product's (which runs the reads 4 at a time, beside the
feed).

- **6409's Act:** 3 requests, **8 of 8 relations dated, both instruments, with qualifications, 0
  refused**; 2.9 s and 2.7 s with the made dates read, **1.4 s and no introduction read** on the
  third (the store held both).
- **6411's Act:** hop absent (one call, the `POST`); the Worker's note unchanged.
- **A UK Act with a 2-page window (the subject of D's feed error):** 358 listed, 118 dated, **4
  refused (the feed error, against the made date read live)**, window 1,000 of 1,568, and 8
  instruments undated for want of a made date (3 reads with no answer within 8 s, 5 beyond the cap).
  The smoke's print step failed on a sort over `None` (my script, fixed) after the product had made
  every call; `replay_smoke.py` re-ran the built code over the logged responses at $0.
- **A Scottish Act with 10 commencing instruments:** 184 listed, 152 dated, 0 refused, 4
  instruments undated for want of a made date (2 no answer within 8 s, 2 beyond the cap); 32.7 s
  wall through the serialising transport.

**Added calls and latency per turn, at the cap.** Per change-record call with a hop: 1 to 2 feed
pages + at most 8 made-date reads = **at most 10 calls** (the `/amendment/search` call is not new).
Over the stored corpus (cold, every turn as if on a fresh server): per hop call median 3, p90 8, max
10; per turn with any (313 of 539 turns with a change record) median 3, p90 8, max 26. With the
made-date store kept: per hop call median 1, p90 2; per turn median 1, p90 3, max 24. **Latency per
hop call: worst case about 16 s** (2 feed pages in sequence at 8 s each, the made-date reads beside
them in at most 2 rounds of 8 s); **typically about 1 to 3 s** on the live reads above. A turn with
several subjects pays it per subject; the per-request memo pays it once per subject. These reads
are LEX calls and count in `request_timings`' LEX-API time under `get_legislation_changes`.

## 4. The exact new wording, every variant (synthetic ids; `python $C/wording.py $S` prints them all)

**Worker-facing note on the result (`amendment_search_note`), the closing.** Unchanged where no hop
ran or it dated nothing. **Dated** (replaces "Two things this record does NOT contain ..."):

> The relations themselves carry no date. The `in_force` date on {dated} of the {relations} commencement relation(s) made by another instrument listed here was added by code from legislation.gov.uk's Changes to Legislation record, read through the LEX API, with that record's `qualification` (such as "wholly in force" or "for specified purposes"): you MAY state such a date, with its qualification, as the date the instrument named against that entry brought those provisions into force, citing that record. It records when they were brought into force, not whether they have since been amended or repealed, so it is never evidence of in-force status today. Do not give a date for a relation listed without `in_force`.{refused}{unchecked}{window} There is no made-under relation, so this record says nothing about any instrument's enabling power.]

where, only when they apply: {refused} = " For relations made by {ids} no date is given: the date that record holds for them is earlier than the day the instrument was made, which is impossible."; {unchecked} = " For relations made by {ids} no date is given: the day that instrument was made could not be read, so the date could not be checked against it."; {window} = " That record was read for the first {read} of the {total} changes it lists for {subject}, so a relation without a date here may be in the part that was not read." ({ids}: at most 6, then "and N more".)

**Not retrieved** (one sentence added before the unchanged closing):

> Code tried to read the date of each commencement made by another instrument from legislation.gov.uk's Changes to Legislation record, through the LEX API, and could not this time ({reason}), so no date is given against any relation here.

{reason}: "the record did not answer within 8 seconds" / "the record answered with an error, HTTP {code}" / "what came back was not a readable record" / "the request failed".

**`_relation_currency_limb` (in the same note), dated:** "The record gives no date for them either." becomes "The record gives no date for them."

**Manager and Deep Research synthesis, `_relations_limb`, dated** (replaces "The change record carries no dates and no made-under relation: do not state a commencement date, or an enabling power, from it."):

> The change record's relations carry no dates of their own, and no made-under relation. For the record of {subjects}, code added the date legislation.gov.uk's Changes to Legislation record gives for each commencement made by another instrument, with that record's qualification: a date the report gives for such a commencement may be stated, with its qualification, as the date that instrument brought the provision into force, citing that record, and never as evidence of in-force status today. Do not state any other commencement date, or an enabling power, from the change record.

**`_commencement_lines` (P3.24's line), dated.** `other_full`: "{lid}: {n} commencement relation(s) made by another instrument, all listed. A provision listed there may be stated as commenced by the instrument named against it, with the date legislation.gov.uk's Changes to Legislation record gives for it where the report gives one: the day that instrument brought it into force, with its qualification, never its status today; one of its provisions not listed there may be called not recorded as commenced, citing this record, without a date." (was "...citing this record. Neither carries a date."). `other_cut`: the same sentence in place of "A provision listed there may be stated as commenced by the instrument named against it", then "; one not listed may be in the part not shown, so do not state whether it has been commenced." unchanged. `self_only`, `unlisted`, `none`, `by`: unchanged (never dated).

**`_currency_limb`, dated:** "... is supported, again without a date." becomes "... is supported, without a date."

**Lawyer-facing footer, `_relations_footer_clause`, dated** (replaces "; those records carry no dates, so any date given above was read from the instrument itself and not from the relation."):

> ; those records carry no dates of their own, so a commencement date given above for a provision commenced by another instrument is the date legislation.gov.uk's Changes to Legislation record gives for that commencement, read through the LEX API, with its qualification. It says when the provision was brought into force, not whether it has been amended or repealed since; any other date was read from the instrument itself.

**Lawyer-facing footer, `_currency_footer_clause`, dated** (the sourced branch; P4.18's branch and the no-record branch unchanged):

> Whether legislation is in force is not something this index reports; what was checked is the recorded changes for {sourced}, which name the instruments involved provision by provision, and, for the commencements of {dated} made by another instrument, the date legislation.gov.uk's Changes to Legislation record gives for each. Neither is a check of whether a provision has since been amended or repealed.

**Static texts (commit 2, every legislation Worker call):** the tool description's "It does NOT return dates, and" becomes "The relations carry no dates of their own: where legislation.gov.uk's Changes to Legislation record dates a commencement made by another instrument, code adds that date to the entry as `in_force`, and the result says when it could not. It does NOT say ..."; `_RELATIONSHIP_RULE`'s "The change record gives no DATES." becomes "The change record's relations give no DATES of their own. Where code has added an `in_force` date to a commencement made by another instrument (from legislation.gov.uk's Changes to Legislation record; the note on the result says so), you may state it, with its qualification, as the date that instrument brought the provision into force. Otherwise the record establishes ..." (rest unchanged); `_IN_FORCE_RULE` (a)'s "The relation carries no date; for a date, ..." becomes "The relation carries no date of its own; where code added an `in_force` date to it, give that date with its qualification as the date the instrument brought the provision into force, never as its status today; otherwise, for a date, ..."; the research Worker's tool list "— but no dates, and no enabling power." becomes "— with no dates of their own (code adds a commencement's `in_force` date where legislation.gov.uk's record gives one), and no enabling power."

**Screened** (`tests/test_commencement_dates.py`, own file, batch 7 D's pattern; nothing added to
the shared `test_footer_trips_no_detector`): every new sentence of every variant, and each of its
sentences, against `NEG_ASSERTED`, `NOT_FOUND`, `derivation_claims`, `IN_FORCE_CLAIM`,
`_CUR_DISCLOSED`, `NEG_TERMS`, `NEG_LIMITS`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, the three halt
detectors, `OPENER_VOCAB`, `_names_search_terms`, `_without_footer`, the commencement denial
(`_CMC_*`), `_currency_asserted`, `negcurrency_claim` and (static texts) the lookup classifier:
**0 hits.** The currency clause keeps P2.5's opening word for word, so it is held to that opening's
one `IN_FORCE_CLAIM` (as the shared test holds it) and to no more public-pattern or classifier
verdicts than the clause it replaces. The whole Worker note, dated and failed, against undated: no
public pattern and no sentence classifier (derivations, search terms, negcurrency, currency,
commencement denial, lookup, case-law gap, schedule clauses) counts more. Counting every compiled
pattern including the parts (vocabulary screens, sentence splitters) is not a measure for a longer
closing; `python $C/pattern_rises.py $S` lists which parts rise. The blocks still strip whole
(`strip_scope_blocks`, `_without_footer`).

## 5. The code texts beside this change, and whether any contradicts a retrieved date

- **P2.5's currency clause** (`_currency_footer_clause`): said "nothing above has been checked
  against a commencement date"; false where dated, so gated (above). Its opening stays.
- **P3.24's commencement lines** (`_commencement_line`): "Neither carries a date" gated for
  `other_full`; `other_cut` gains the same permission; `self_only`/`unlisted`/`none`/`by` never
  carry a hop date (self relations are out of scope), so unchanged and consistent.
- **P4.18's branch** (a record consulted, holding no commencement or repeal): a hop needs a listed
  commencement, so it never runs there; unchanged, no contradiction.
- **The footer clauses** (`_relations_footer_clause`, `_currency_footer_clause`): gated (above).
- **Unchanged and consistent:** `_currency_limb`'s opening ("NOTHING in this step establishes that
  any instrument is in force as at today") and its Status paragraph; `_relation_currency_limb`'s
  "CANNOT establish that this legislation is in force as a whole"; `_relation_commencement_bits`
  (state each listed provision as commenced; self relations: read the provision for its date);
  `_COMMENCEMENT_RECORD_RULE`; the Deep Research synthesis rule (a commencement a step attributes to
  a change record); `currency_note` (title markers).
- **Contradicted until commit 2 is taken:** the tool description ("It does NOT return dates"),
  `_RELATIONSHIP_RULE` ("The change record gives no DATES"), `_IN_FORCE_RULE` (a) ("The relation
  carries no date") and the research Worker's tool list ("but no dates"). The gated note reconciles
  them ("The relations themselves carry no date"), but Session 40's lesson is that a contradicting
  code text can win; decision 2.
- **A second source of a date for the same instrument:** a LEX `description` the Worker reads (a
  search row once agent D's P3.6 keeps it, truncated; a `lookup_legislation` record; a whole text)
  can state a date for a commencing instrument, and D measured a one-date description disagreeing
  with the feed on 14% of the relations both date (descriptions cover part of an order). This build
  reads no description (the brief's aside that C reads `description` through `lookup_legislation`
  describes the design batch 8 D replaced). Nothing tells the Worker which to prefer; watch item for
  sweep 2, decision 5.

## 6. What the audit trace records, and what `docs/api/AUDIT_TRACE.md` would need

Under the `get_legislation_changes` tool record's `api_calls`, after the `/amendment/search` call(s),
**by size and by what was read, never the body:** `id` `<call id>-lgu-feed-p1` / `-lgu-feed-p2`
(feed pages) and `<call id>-made-<type>-<year>-<number>` (made-date reads); `method` `GET`; `url` the
proxy URL with the encoded path; `request` null; `status` the HTTP status or null; `response`
`{"bytes", "effects", "total", "page", "total_pages"}` (a feed page), `{"bytes", "made"}` (a made
date, `null` where none is stated), or `{"bytes", "error": "no_reply" | "http_<code>" |
"unreadable" | "error"}`; `elapsed_ms`. A memo-served or store-served read records no call. The
tool's `raw_result` and `final_result` may carry `changes[].in_force`, `changes[].qualification`
and `commencement_dates`. **No schema change** (additive keys, `AUDIT_SCHEMA_VERSION` stays 6).
`AUDIT_TRACE.md` would need: the two new api_call kinds and their `response` summaries, the three
result keys, and that `request_timings`' LEX-API time now includes these reads. (Not edited.)

## 7. Tests, the revert and the mutants

- **57 tests** in `tests/test_commencement_dates.py` (55 in `36ddcee`, 2 in `0f159e7`), synthetic
  throughout ("Widget" ids, `asp/1901/1`, `ssi/1901/3`), at the seams: the parsers, the index,
  `apply_dates`, the hop (served by a mock transport through `_client`), the executor branch, every
  gated wording site, the detector screens, the output shape, the static texts.
- **Revert of `36ddcee`** on a scratch copy (`python $C/mutants.py $S`, `mutants.txt`): the product
  files and `conftest.py` put back to `ca3d45c` and the new module removed, **822 lines** (551 of
  them the new module; 12 executor, 5 lex.py, 232 search_scope, 22 conftest): **the test file fails
  at collection.** Because that proves only the import, **50 single-site mutants**, every guard and
  every cleaning step (each anchor asserted to occur exactly once, CRLF normalised): the made-date
  check off, strict, or passing an unread date; self groups, other effects, direction `"by"`, self
  and other-subject feed effects, any effect type, unnormalised labels; 3 pages; a 30 s timeout; the
  slot not reserved; the memo not kept; the store not written, not read, keeping a non-date,
  unbounded; the cap off; a DOCTYPE accepted; any root accepted; a non-ISO feed or made date
  accepted; a failed page 2 failing the hop; a non-200 read as a page; the body in the audit; the
  failed-feed reason, refused list, unchecked list, window or qualification dropped; unsafe subject
  or instrument ids used; the hop raising; the executor not hopping; and every wording gate (the
  structure gate, the dated closing, the not-retrieved sentence, "either", both recorders, the
  limb, both footer clauses, both commencement lines, the cross-call carry, "again", "and N more",
  the HTTP reason). **All 50 caught**; the first run left 3 alive (a non-ISO feed date, the gate on
  the count alone, "and N more"), each fixed with a test before the numbers above.
- **Revert of `0f159e7`** (`python $C/mutants_static.py $S 36ddcee`, `mutants_static.txt`): **8
  lines**, 1 test fails; 4 single-site mutants (each static text put back), **4 caught**.
- **Full suite: 2539 passed** on `lexchat_test_c`
  (`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c python -m pytest -q -p no:cacheprovider`).

## 8. What I did NOT do

- No grader (`replay_report.py` is agent E's); no edit to the shared `test_footer_trips_no_detector`.
- No `"by"` hop (the subject's affected feed does not describe the changes it makes); no
  self-commencing dates (decided out).
- No retry on a failed read; no feed store across requests (the decided per-request memo).
- Did not match the 79 label-rendering relations D read by hand (they stay undated, as D left them).
- Did not read any LEX `description`; no date is ever inferred from a description, a year or a
  made date (the made date only refuses).
- The dry run cannot see a real failure rate (its feeds are saved and its made dates served); the
  live smoke measured one, on 4 subjects.
- Did not edit `docs/api/AUDIT_TRACE.md`, FIX_PLAN, SESSION_LOG, the tracker, CLAUDE.md or any memory file.
- No replay: whether a Worker states the date with its qualification and source is sweep 2's
  question (6409 n=3, 6411 n=3 on the negative branch).

## 9. Decisions for the user

1. **What happens when a made date cannot be read.** Live, 5 of 20 hop made-date reads gave no
   answer within 8 s (feeds 6 of 6 answered); each such instrument's dates are not given in that
   request.
   - **(a) Keep as built (recommended):** no date without the check, and a made date once read is
     kept for the life of the process, so a later request reads it again only if it was never read.
     On 6409, both made dates were read in 2 of 2 live requests and none was read on the third.
   - (b) Also retry a failed made-date read once: fewer missing dates, worst case 16 s for that read
     (still within the two feed pages' 16 s if run beside them).
   - (c) Fail open to a year bound: give the date when the made date was not read, checked only
     against 1 January of the instrument's own year (which would not have caught D's feed error),
     and say so in the note.
   - (d) Drop the process-level store (per request only, like the feed): more reads, more misses.
2. **The static texts (commit `0f159e7`).**
   - **(a) Take it (recommended):** four texts the Worker reads on every call said the record has
     no dates; a code-stated fact has lost to a contradicting code text before (Session 40). It
     reaches every legislation Worker prompt and the tool schema, and its first-round effect cannot
     be measured at $0: read 6409's and 6411's Worker tool choices in sweep 2.
   - (b) Drop it: the gated note alone reconciles ("the relations themselves carry no date").
   - (c) Take only the tool description's change.
3. **The made-date read cap per change-record call.**
   - **(a) 8 (recommended):** 95% of stored instruments, 337 of 354 calls in full; with the store,
     the warm corpus needs far fewer (cap-undated 184 relations cold, 78 warm).
   - (b) 12: all but 3 stored calls in full, up to 14 calls per hop.
   - (c) 5: fewer calls, 84% of instruments.
4. **The not-retrieved sentence** (the brief: unchanged where the hop "found nothing"; the user's
   decision: fail-soft "saying the date was not retrieved").
   - **(a) Keep the one added sentence (recommended):** the Worker is told the record could not be
     read, in words, not only in the JSON status.
   - (b) Drop it: the closing is byte-identical to today's and only `commencement_dates` says so.
5. **A description's date beside the feed's** (D's P3.6 and P3.25's lookup can put an instrument's
   own description, sometimes dated, in front of the Worker; D measured 14% disagreement).
   - **(a) Watch it in sweep 2 and book a row only if an answer states a description date that the
     feed contradicts (recommended).**
   - (b) Add now, to the dated closing: "where an instrument's description gives a different date,
     the record's date is the one for that provision" (screened, not built).
   - (c) Book a row now.

## Scratch

`docs/prepilot-fixes/evidence/seam/batch9/C/` (gitignored): every script above, `calls_lex.jsonl`
(the 35 calls) and `raw/` (their bodies), `made_live.json`, `smoke_live.txt`, `acceptance.txt`,
`dryrun_summary*.txt`, `dryrun_list*.txt`, `mutants*.txt`, `wording.txt`, `added_lines.txt`, the
commit messages. Copied with `cp -r` to the main checkout's `docs/prepilot-fixes/evidence/seam/batch9/C/`.
