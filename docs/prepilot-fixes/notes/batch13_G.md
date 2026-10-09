# Batch 13, agent G: P3.34 measured (corpus-wide definition search; $0, 23 LEX calls)

Session 45, 2026-10-09. **Measurement only.** No product code, no test, no row edited. This note is the only
tracked file changed.

## 0. Setup, and what this note does not contain

- **Base.** The worktree came up on `main` (`a6b4a76`), as in every batch. With no commits of my own I ran
  `git reset --hard 1889abb` (the integrator HEAD). The note is based on `1889abb`.
- **Spend: $0 in model spend.** No seam, replay, server or model call.
- **Live calls: 23 of the 30 agreed, all to LEX, all `POST /legislation/section/search`, all HTTP 200.** No
  other host and no other endpoint. Every call went through one door (`lex_g13.py`, batch 12 G's pattern). It
  enforces the cap of 30 and a gap of at least 0.5 s by reading its log back before each call, refuses any host
  but `lex.lab.i.ai.gov.uk`, and logs method, URL, payload, status, bytes and elapsed time. The smallest
  measured gap was 0.50 s. Responses totalled 9.0 MB; each call took 222-913 ms.
- **No matter text.** The three defined terms, the query strings, instrument ids and titles, and every quoted
  definition stay in the gitignored scratch `docs/prepilot-fixes/evidence/seam/batch13/G/`. In this note a query
  form is written with `<term>` in place of the word. Sessions and turns are cited as the row cites them.
- **Every number below comes from** `python gt.py && python final.py` and `python perrun.py`, run in that folder
  with `PYTHONIOENCODING=utf-8`. They read the logged responses only and make no call. `per_answer_bare.py`,
  `dump_matches.py`, `drops.py`, `a_only.py` and `extent_split.py` produce the hand-reading lists. The probe
  that made the calls is `probe.py` (`python probe.py "<purpose>" '<payload json>'`).

## 1. Headlines

| Question (the brief) | Answer | Check |
|---|---|---|
| Does `search_legislation_sections` without a `legislation_id` search the corpus? | **Yes.** With `legislation_id` null, empty or omitted it searches the whole index: 91 instruments in 100 rows on the first call. `legislation_type` (a list), `legislation_category`, `offset` and `size` all work. Results are deterministic: a repeated request returned a byte-identical body. **`size` changes the ranking.** At `size` 10 the top 10 were rows ranked 1-22 at `size` 100. At `size` 300 the first 100 shared 70 rows with the `size` 100 list. A larger `size` raised precision at 100 (29 against 24 defining rows). | Calls 1, 14, 15, 17, 16 against 2 (`final.py` E). Passes. |
| How many of the defining instruments the stored runs found does one corpus-wide query return? | **On the 6341 term, 20 of 28 with one call (23 with two). On the 6384 term, 5 of 5. On the 6363 term, 1 of 1.** On every turn this is more than any single stored run retrieved: one call returns 28, 7 and 32 defining instruments, against a per-run maximum of 12, 5 and 1. | `final.py` C, `perrun.py`. Passes. |
| At what precision? | **Raw rows: low and term-dependent.** Defining rows in the top 10 were 10, 3 and 1 of 10 for the three terms. Over 300 rows, 35, 7 and 41 defined the term. **After a code filter** (the quoted term followed by a definitional verb): **120 of 120 distinct kept rows are definitions by hand-read** across all 23 calls. | `final.py` D; `matches_final.txt`, every row read. Passes. |
| The brief's "29 across 19 runs on 6341 t7" | Read by hand, the 29 are **15 instruments defining the bare term, 7 defining a compound term containing it, and 7 that define neither.** The 7 are cited in a defining sentence, for example "Act X contains no definition". One call returns a defining row for **12 of the 15**, two calls 13. The 2 never returned are one schedule of about 300,000 characters held as a single provision, and one pre-1963 instrument with a non-standard id. | `final.py` B and C. The A-union equals the hand classification (asserted). |

**Proposal: GO, at P2, with a code tool, not an index** (decision 1). The tool would run one corpus-wide
section search and keep only the rows that define the term. It would return the defining clause, the provision
link and the stated extent, never the raw rows. An index is NO-GO for now: one call already reaches at least what
the stored runs found on two of the three terms, and 20 of 28 on the third.

## 2. What was measured, and how

### 2.1 The ground truth (`gt.py`)

- **A, the answer-cited union.** This is batch 12 F's `p334_defs.py` detector, reimplemented verbatim: the
  instruments linked in an answer sentence that names the term and a definitional word. It reproduces F's
  figures exactly: 6341 t7, 19 answers, 0-14 each, union 29; 6384 t4, union 10; 6363 t1, union 11.
- **T_strict, text-verified.** These are the instruments whose retrieved text, in any tool result of any turn of
  any stored run of the session, contains the quoted bare term followed by a definitional verb. The verbs are
  means, includes, has the (same) meaning, shall mean, is to be construed, and in relation to. The list form also
  counts: `"a", "<term>" and "b" have respectively the same meanings as in ...`. Totals: **28** (6341), **5**
  (6384), **1** (6363). The list form and a comma inside the closing quote were added after the first call's rows
  were read. Both have synthetic tests in `test_terms.py` (8 cases, 0 failures).
- **The A detector overstates the bare-term union.** On the three headline turns, 18 of the 50 A-union entries
  define neither the bare term nor a compound term (7 of 29, 4 of 10, 7 of 11). It also folds compound-term
  definitions in (7, 1 and 3). **Any acceptance grader for this row should count text-verified definers, not A**
  (decision 5).

### 2.2 The calls (`final.py` D has every line)

| Calls | Term | Query form | Filter | `size` |
|---|---|---|---|---|
| 1, 2, 3 (offset 100), 16, 17 (repeat of 2), 18, 23 | 6341 | `"<term>" means` | none / 4 types / category | 100, 300 |
| 4 | 6341 | `definition of <term>` | 4 types | 100 |
| 5, 22 | 6341 | a definition-shaped sentence (`"<term>" means a <genus> used for ...`) | 4 types | 100, 300 |
| 21 | 6341 | `"<term>" includes` | 4 types | 300 |
| 14, 15 | 6341 | `"<term>" means`, `legislation_id` omitted / `""` | none | 10 |
| 6, 19; 7; 8; 9 | 6384 | quoted-means; quoted-means; definition-shaped; `definition of` | none; 4 types | 100, 300 |
| 10, 20; 11; 12; 13 | 6363 | the same four forms | none; 4 types | 100, 300 |

"4 types" is `legislation_type: [ukpga, uksi, asp, ssi]`. "Category" is `legislation_category: [primary, secondary]`.

### 2.3 Results per configuration (`final.py` C)

| Term | Configuration | LEX calls | Defining rows / rows | Defining instruments | Of T_strict | Headline turn: bare-term definers of A |
|---|---|---|---|---|---|---|
| 6341 | quoted-means, 4 types, `size` 100 | 1 | 24 / 100 | 20 | 19 / 28 | t7: 12 / 15 |
| 6341 | quoted-means, 4 types, `size` 300 | 1 | 35 / 300 | 28 | 20 / 28 | t7: 12 / 15 |
| 6341 | quoted-means, no filter, `size` 300 | 1 | 52 / 300 | 44 | 22 / 28 | t7: 12 / 15 |
| 6341 | quoted-means + definition-shaped, 4 types, `size` 300 | 2 | 44 distinct / 600 | 37 | 23 / 28 | t7: 13 / 15 |
| 6341 | all 9 calls on this term | 9 | 67 distinct / 1,700 | 59 | 26 / 28 | t7: 13 / 15 |
| 6384 | quoted-means, no filter, `size` 100 | 1 | 7 / 100 | 7 | 5 / 5 | t4: 5 / 5 |
| 6363 | quoted-means, no filter, `size` 100 | 1 | 14 / 100 | 14 | 1 / 1 | t1: 1 / 1 |
| 6363 | quoted-means, no filter, `size` 300 | 1 | 41 / 300 | 32 | 1 / 1 | t1: 1 / 1 |

Per turn, against the A-union, counting an instrument only through a defining row (one call, quoted-means,
`size` 300):

| Session | Turn: defining row for X of the A-union |
|---|---|
| 6341 (4 types) | t2 5/8, t3 6/13, t4 5/10, t5 4/6, t6 7/10, t7 12/29 |
| 6384 | t1 2/4, t4 5/10 |
| 6363 | t1 1/11 |

The A-union denominators include the non-definers of section 2.1, so these fractions understate the tool.

**Against what the stored runs did (`perrun.py`).** This counts bare-term defining instruments in each stored
run's own tool results for the turn.

| Turn | Stored runs | Defining instruments retrieved per run (min, median, max) | Section searches per run (median, max) | One corpus-wide call |
|---|---|---|---|---|
| 6341 t7 | 18 | 4, 7.5, 12 | 23, 35 | 28 (4 types) or 44 (no filter) |
| 6341 t6 | 18 | 0, 7.5, 11 | 12.5, 22 | the same |
| 6341 t2-t5 | 18 each | max 4 / 9 / 5 / 7 | 2.5-7 | the same |
| 6384 t4 | 6 | 1, 4.5, 5 | 15.5, 20 | 7 |
| 6384 t1 | 6 | 0, 1, 2 | 2, 3 | 7 |
| 6363 t1 | 9 | 0, 1, 1 | 8, 11 | 14 (`size` 100) or 32 (`size` 300) |

Per stored answer, the hand-classified bare-term definers it cites (`per_answer_bare.py`): 6341 t7 0-12 (median
3, 19 answers); 6384 t4 1-5 (median 4, 7); 6363 t1 0-1 (median 1, 10).

### 2.4 Precision: every match and every drop read

- **Matches.** `dump_matches.py` lists every row the strict detector kept across all 23 calls: **120 distinct
  rows. I read each: 120 of 120 define the bare term.** They include borrowed definitions ("has the same meaning
  as in ..."), a bilingual form (`"<term>" ("<Welsh>") means`), and three amending provisions that insert or
  substitute a definition.
- **Drops.** `drops.py` lists every row where the bare term appears in quotes and the detector did not fire:
  **21 rows.** I read each.
  - **5 are definitional and were missed:**
    - a list where the verb follows a line break ("The expression "<term>" in this section— (a) ... has the
      same meaning");
    - three sections whose heading is "Meaning of / Definition of / Interpretation of references to "<term>"",
      where the body is a construction rule;
    - one "the words "<term>s" ... shall read".
  - **16 are not definitions:** amendments that change someone else's definition ("in the definition of
    "<term>" ... substitute"), substitution rules ("references to an injunction ... substituted references to an
    "<term>""), designation clauses, and one explanatory note.
- **Row recall of the detector: 120 of 125 definitional rows (96%).** Four instruments, all on the 6363 term, are
  lost at instrument level. A heading rule (keep a row whose title holds the quoted term with meaning,
  definition or interpretation) would recover 3 of the 5 rows. It is untested.

### 2.5 Facts about the endpoint (re-probed; the spec read first)

- **The spec.** `docs/api/LexAPISpec.md` and the stored `openapi.json` (`evidence/seam/batch4/D/lex/`) both mark
  `legislation_id` optional ("If not provided, all legislation will be included based on the other filters").
  Only `query` is required. The other fields are `legislation_category` (list), `legislation_type` (list),
  `year_from`, `year_to`, `offset`, `size` and `include_text` (default true). **Verified live:** null, `""` and
  omission all search the corpus. `""` and omission returned identical rows.
- **`size` is not a page size alone.** It changes which rows rank top (section 1). The product's own section
  search sends `size` 10, so a corpus-wide call at `size` 10 would rank worse than one at 100 or 300.
- **Response sizes.** `size` 300 returned 0.51-1.64 MB in 0.6-0.9 s. Such a response must never reach the model
  or the summariser. The tool hands over cut clauses only.
- **Stated extent is mostly absent on the definers found.** Of the 28 defining instruments of the 4-type call on
  the 6341 term:
  - 8 state an extent that includes Scotland or the UK;
  - 2 state England and Wales only;
  - 18 state none (2 of them a Scottish type).

  The unfiltered call adds Northern Ireland, Welsh and untyped definers (`extent_split.py`). A Scotland list
  therefore has to say "extent not stated" for most rows, under P1.1's "applies in" rule (decision 2).
- **Untyped and non-standard ids.** 34 of 300 unfiltered rows on one term had `legislation_type: null` and ids
  that are not type/year/number (old SIs and orders, some marked "unclear"). A type or category filter excludes
  them. A link built from such an id is unverified.
- **One provision of about 300,000 characters (a whole schedule) never ranked** in any form, at any `size`. A
  definition inside a very long provision is the clearest miss of a search-based lever.

## 3. The lever proposed (for decision 1), and what it sits beside

**The shape:** a Worker tool, for example `find_definitions(term, jurisdiction?)`. **In code:**

1. One `POST /legislation/section/search` with no `legislation_id`, query `"<term>" means`, `size` 300. The
   number of calls and the filter are decisions 2 and 3.
2. Keep a row only if its text defines the bare term: the strict detector of section 2.1, ideally with the
   heading rule. Regex-escape the term and allow flexible whitespace for a multi-word term.
3. Group by instrument. For each, return:
   - the provision URL the API gave;
   - the defining clause, cut at the next definition or about 300 characters;
   - the stated extent, or "not stated".

   Cap the list (about 40, as P3.31's record does) and give the total.
4. A window note, worded by the user, saying it is a search, not a census. Measured here: a definition in a very
   long provision, or worded as a construction rule, can be missed. The note must not invite a negative ("no
   other definitions exist").
5. Never summarised. Cacheable (public LEX data): add it to `CACHEABLE_TOOLS` deliberately.

**Code texts that sit beside it (the batch-12 lesson; none contradicts it yet, each to be checked when built):**

- P3.1's per-instrument section budget (`section_budget_blocks`) counts rounds per `legislation_id`. A call with
  no id needs a rule of its own.
- P2.7's discovery budget counts `search_legislation` rounds. Decide whether this tool counts.
- The Worker prompt's "start with one combined query per instrument" sentence.
- `worker_scope_block` and its negatives. A definitions list must not let a "no other definition" claim through.
  Screen any wording against `NEG_LIMITS`/`NEG_TERMS`: "ranked" has tripped them before.
- P3.17's PHASE 2c (the application provision). A list of competing definitions does not say which applies, and
  6338's B11 failure was exactly that choice, so the tool must not displace P3.17's route.
- P1.1's "applies in" rule for any jurisdiction filter.

**Input forms no stored run or live call here contains** (test on synthetic text before any build):

- multi-word terms;
- terms with an apostrophe or hyphen;
- definitions in single curly quotes only (as EU annexes render: `‘term’ means`);
- "refers to" and "is to be read as" forms;
- "references to X are to" construction rules;
- a definition split across a line break;
- a plural defined term.

All three measured terms were single words.

## 4. What I did not do

- No product, test, tool or plan change. No FIX_PLAN or tracker edit.
- No model call, seam, replay or server. No call to any host but LEX, and no LEX endpoint but section search. 7
  of the 30 agreed calls are unused.
- I did not test the heading rule or any multi-word term live.
- I did not judge whether each definer applies in Scots law beyond its stated extent. I did not grade an answer's
  legal completeness beyond the union of what stored runs and these calls found. The true number of statutory
  definitions of each term is unknown, and the "new definers" counts show the stored union is a lower bound.
- I did not price a replay (the integrator's).
- I did not re-read 6338 (B11; F's reading stands).

## 5. Decisions for the user

1. **P3.34: go or no-go, and which lever?**
   - (a) **Recommended: GO (P2), a code tool.** One corpus-wide section search, a code filter that keeps only
     rows defining the term (120 of 120 kept rows correct), and the defining clause, link and stated extent
     returned. It reaches at least what the best stored run found on every turn measured, for one LEX call.
   - (b) Make `legislation_id` optional on `search_legislation_sections` and tell the Worker to use it. This is
     cheaper, but it hands the model raw rows of which 1-10 in 10 define the term, at `size` 10 (which ranks
     worse), and it relies on prompt obedience (Invariant 2).
   - (c) Harvest a definitions index. NO-GO now: it is the heaviest harvest, and the search already meets the
     stored union on two of three terms. Its only measured gains are the long-schedule and odd-id misses.
   - (d) Drop the row.
2. **Jurisdiction.**
   - (a) **Recommended:** no API type filter. Report each definer's stated extent, saying "extent not stated"
     where absent (most rows). When a jurisdiction filter is set, apply P1.1's "applies in" rule in code to
     stated extents and keep unknowns, marked.
   - (b) The 4-type API filter when Scotland is asked. Top-10 precision on one term rose from 7 to 10 of 10,
     but it silently drops untyped old instruments and NI/Welsh definers.
   - (c) The category filter (primary + secondary). It drops untyped and local-Act rows and keeps NI/Welsh.
3. **Calls per use.**
   - (a) **Recommended:** one call, `"<term>" means`, `size` 300.
   - (b) Two calls, adding a definition-shaped second form. That gave +3 of T_strict and +9 definers on the
     hardest term, at double the calls and about 0.8 MB more read.
   - (c) Page with `offset` instead. Page 2 at `size` 100 held 5 defining rows in 100. A larger `size` did
     better.
4. **Compound terms** (a qualifier plus the term).
   - (a) **Recommended:** bare term only in the list. Name compound-term definitions found in the same rows
     separately, labelled, with no extra call and no completeness claim (2 of 7 reached on the hardest turn).
   - (b) Exclude them.
   - (c) A compound mode with its own detector and acceptance, measured first.
5. **Acceptance** (if go).
   - (a) **Recommended:**
     - A deterministic live check (`lex_probe`-style), one call per term: list at least 20 of 28, 5 of 5 and
       1 of 1 of T_strict, with every listed row a definition.
     - Unit tests on synthetic text for the detector, every form in section 3 and a mutant for each guard.
     - Replays: 6341 t7 and 6384 t4 at n=3, 6363 t1 at n=1 (priced first). Each answer must cite at least the
       best stored answer's bare-term definers (12, 5 and 1, hand-classified, not F's detector). No instrument
       may be named as defining the term when its retrieved text does not.
     - Controls: 6362 t4 and 6413 t1 (batch 12 F), plus 6338 t1, where P3.17's application provision must still
       be reached.
   - (b) The deterministic check alone, with the replay deferred to the next sweep.
   - (c) The replays alone.
6. **Who is offered the tool?**
   - (a) **Recommended:** the research Workers. Answer separately for the conversational quick-lookup Worker
     (P3.25 removed `get_legislation_text` from it), since 6384 t1 ran in that mode.
   - (b) Both Workers from the start.
   - (c) The research Worker only.

## 6. Scratch

`docs/prepilot-fixes/evidence/seam/batch13/G/` in the worktree (gitignored: `.gitignore:113`,
`docs/prepilot-fixes/evidence/seam/`). It holds the call log `lex_calls_g13.jsonl` (23 lines), the 23 gzipped
responses in `raw_lex/`, the scripts named above, `gt.json`, `score.json` and the hand-reading lists
`matches_final.txt` and `drops_final.txt`. It is copied at the end to the main checkout's
`docs/prepilot-fixes/evidence/seam/batch13/G/`.
