# Parallel batch 9, agent D: P3.4, then P3.6 (two builds, two commits; $0, no external call)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard ca3d45ca0e4705123aa23ed0c7fc0c1ab9a77918` (the integrator's
head). This note is based on `ca3d45c`. No other session's commits are in it.

**Branch** `worktree-agent-aba973608cfe65028`, three commits:

- `e46f93b` P3.4: the default-jurisdiction rule, and the extent notes without letter codes;
- `b48ad9f` P3.6: `description` kept in `search_legislation` rows, cut to 600 characters, with the
  two `[SEARCH SCOPE]` clauses it would have made false or self-defeating;
- this note.

**The two commits are separable** (P3.4 touches `prompts.py` only; P3.6 touches `lex.py` and
`search_scope.py` only), which matters for decision 4.

**Spend.** $0 in model spend. **No external call of any kind**: every LEX response used below is a
stored `api_calls[].response` from the replay directories, served to the BUILT executor in place of
the network. No server, no replay, no seam draw, no summariser call. Every stored run file read here
ran on the pinned `google/gemini-3.1-pro-preview`; no number comes from `glm-5.2:cloud`.

**Tests.** 131 new for P3.4 (`tests/test_default_jurisdiction.py`), 28 new for P3.6
(`tests/test_search_description.py`). **Full suite on `lexchat_test_d`: 2641 passed** (2482 + 159).

**Against the booked acceptances.**
- **P3.4 (a), deterministic: MET on this branch.** Checks: no extent note names a letter code,
  every note says most results carry no stated extent, and the rule is in exactly the two prompts.
  131 tests; 38 fail with `prompts.py` restored; 12 of 12 single-site mutants caught.
- **P3.4 (b), replay: NOT RUN** ($0 brief). It is the integrator's after-column, priced by E.
  Read section 1.4 first.
- **P3.6, deterministic: MET on this branch.**
  - `description` survives slimming within the 600 cap (28 tests; 15 of 15 mutants caught).
  - **Phase-1 summarisation calls are unchanged.** 0 of 6,521 re-run stored results cross the
    8,000 characters every stored replay was summarised at; before and after are both 0.
  - 0 later tools flip on the context budget.

**Two findings beyond the rows** (both measured, both for the integrator to fold):
- **Every stored replay was summarised at the 8,000-character fallback, not the pinned Gemini's
  200,000** (section 2.2).
- **212 distinct SSIs among the stored search rows carry an enabling-power recital in their
  description**, against P3.6's row's "0 of 28 SSIs" (decision 6).

**Scratch.** Gitignored `docs/prepilot-fixes/evidence/seam/batch9/D/` (`git check-ignore -v` gives
`.gitignore:113`), copied to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch9/D/`.
Every script asserts which tree it imports. `head_server_py.tar` is `git archive ca3d45c server_py`;
the mutant runners and the reach and seam checks extract it to `revtree/` (`mkdir revtree && tar -xf
head_server_py.tar -C revtree`) and use it as the before-tree. Commands run with
`PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`.

---

## 1. P3.4 (commit `e46f93b`)

### 1.1 What changed, and why

- **The extent notes** (`_JURISDICTION_EXTENT_NOTES`, which travel in the filter block when a
  jurisdiction filter is set) said "Prioritise legislation where extent includes S or E+W+S+NI",
  a letter format the API never sends (P1.1), and said nothing of the rows with no extent. Each now
  says, in the API's own territory names, what `_matches_jurisdiction` keeps, and that most results
  carry no stated extent. The unstated-extent sentence is one string (`_EXTENT_UNSTATED`), shared
  by the four territorial notes. The `uk_wide` note says that filter REMOVES those rows (it admits
  only a stated `['United Kingdom']`), so it misses UK-wide law that does not state it. The old
  `uk_wide` note scripted "If no UK-wide legislation exists for this topic, note this clearly", a
  negative about the law (P4.6's shape); the new one says the limit is the filter's, not the law's.
  The Scotland note keeps P2.4's case-law sentence unchanged.
- **The default-jurisdiction rule** goes in exactly the two prompts the acceptance sessions run on:
  - the conversational Manager (`_MANAGER_CONV_BODY`): a `JURISDICTION:` section of four bullets,
    placed after YOUR APPROACH;
  - the quick-lookup Worker (`WORKER_SYSTEM_PROMPT_CONVERSATIONAL`): ONE bullet in YOUR MANDATE,
    not a block, because a block appended to this prompt once changed its output format (P2.4's
    A/B, recorded above `_NOT_HELD_RULE`). It is scoped to legislation, so a case-law query is not
    narrowed by an added "Scotland".
  - Both sit INSIDE the triple-quoted literals, so `seam_replay --without-fix --rev ca3d45c`
    still swaps the whole literal for an A/B (checked, section 1.4).
- **The Manager states the jurisdiction in every brief and is told not to name an instrument for
  it** (P3.13's lesson: a Manager prompt edit reaches the first delegation brief). The quick-lookup
  Worker is never told the filters (P3.14), so it takes the jurisdiction from the brief.

### 1.2 The exact new wording, for the user (decisions 1 to 3)

**The conversational Manager, new section:**

> JURISDICTION:
> - If the question names no jurisdiction and no jurisdiction filter is active, answer it for
>   Scotland (the law that applies in Scotland, including UK legislation that extends there), and
>   say in your answer that this is the position in Scotland.
> - If the question asks about the UK as a whole (for example "in the UK" or "UK-wide"), answer for
>   each of England, Wales, Scotland and Northern Ireland: where the law differs between them, say
>   so and give each, and never give one part's law as the answer for the whole UK.
> - If the question or an active filter names a jurisdiction, or the question is about a named
>   instrument, answer for that jurisdiction or instrument.
> - Put the jurisdiction in every `delegate_research` brief (for example "for Scotland", or "for
>   each of England, Wales, Scotland and Northern Ireland, noting where the law differs"). Name the
>   jurisdiction only: do not add an Act or instrument for it that neither the user nor a tool
>   result has given you.

**The quick-lookup Worker, new bullet in YOUR MANDATE:**

> - Jurisdiction: if the brief names no jurisdiction, find the legislation that applies in Scotland
>   (UK legislation that extends there included) and say that your answer is for Scotland. If the
>   brief asks about the UK as a whole, find it for each of England, Wales, Scotland and Northern
>   Ireland, say where it differs and give each, and never give one part's law as the answer for
>   the whole UK. If the brief names a jurisdiction, answer for that one.

**The extent notes** (after "- Jurisdiction: <label>." in the filter block):

> **Scotland:** Legislation search results are kept where their stated extent includes Scotland
> or the United Kingdom. Most legislation search results carry no stated extent (their `extent` is
> empty), and the filter keeps those too unless the identifier marks them as another
> jurisdiction's legislation, so a result returned under this filter has not thereby been shown to
> apply in Scotland: give an instrument's extent only where its result or its retrieved text states
> it. Note that the case law database holds no decisions of the Court of Session, the Sheriff
> Appeal Court, the Sheriff Courts or the High Court of Justiciary; Scottish appeals decided by the
> UK Supreme Court are included.

> **England and Wales:** the same first two sentences with "England, Wales or the United Kingdom"
> and "England and Wales", then: "If a cited instrument's stated extent does not include England
> and Wales, say so." **Northern Ireland** and **Wales:** the same two sentences with "Northern
> Ireland or the United Kingdom" / "Wales or the United Kingdom".

> **UK-wide only:** Legislation search results are kept only where their stated extent is the
> United Kingdom. Most legislation search results carry no stated extent (their `extent` is
> empty), and this filter removes them, so legislation that applies across the UK without stating
> it is missing from these results. Say that the results were limited in this way; it is a fact
> about this filter, not about the law.

### 1.3 "Most rows carry no stated extent": checked, true

`python extent_count.py --no-memo` (the product's own `_extent_tokens`; "no stated extent" = it
returns nothing: `[]`, `['']` or missing), over every stored replay directory (57 of the 59 hold a
`search_legislation` record):

| Population | No stated extent |
|---|---|
| API rows (`api_calls[].response.results`, before any filter) | **40,148 of 69,430 (57.8%)** |
| distinct instruments among them | 4,529 of 7,189 (63.0%) |
| model-visible rows (`raw_result`, after filters; memo hits excluded) | 18,114 of 29,165 (62.1%) |

The model-visible share is inflated by the pre-P1.1 directories, whose filter kept only unknowns;
the API row is the clean number. P1.1's baseline (17,560 rows, 53%) agrees in direction.

### 1.4 Every prompt the change reaches, and every call it drives

`python reach_p34.py` builds every prompt the three builders can produce in both trees (5 research
modes x 4 chat modes x 4 flag sets x 6 jurisdiction values, plus the synthesis per mode and 13
constants: 1,458 texts) and lists what changed: **746**.

- **Changed constants: only `MANAGER_SYSTEM_PROMPT_CONVERSATIONAL` and
  `WORKER_SYSTEM_PROMPT_CONVERSATIONAL`.** `MANAGER_SYSTEM_PROMPT`, the three research Workers, the
  planner, the parliament and Westminster prompts, `CONSULTED_PEER_BLOCK` and the no-chips rules are
  byte-identical.
- **Changed with no filter set: only the conversational Manager and the quick-lookup Worker** (all
  72 of each: three research types, every flag set). 0 others.
- **Changed only when a jurisdiction filter is set** (the notes, which the row needs): the research
  Manager, the three research Workers and the Deep Research planner (180 each), and the planner
  under a conversational chat mode (60). Parliament/Westminster and the synthesis: never.

**Calls driven** (none measured: $0):
1. **The conversational Manager's first round**, which writes the first `delegate_research` brief
   (or a clarifying question). The brief now names a jurisdiction by design. In
   `replay_set.json`, 36 of the 41 replayed sessions have a conversational turn.
2. Its answer round (the "this is the position in Scotland" sentence), any second delegation, and
   its `<suggestions>` chips (which may now offer another jurisdiction).
3. **Every quick-lookup Worker call**, including its FIRST `search_legislation` query, which may now
   carry "Scotland" or "(Scotland)": a retrieval change, not only a wording one.
4. With a jurisdiction filter (13 of the 41 replay sessions, all Scotland, among them 6359, 6374
   and 6411): every Manager, research Worker and planner call reads the new note.

**What the integrator should read for, in P3.4's after-column (and any later sweep):**
- **The first brief of each conversational turn.** Does it name the jurisdiction? Does it name an
  instrument the lawyer did not give? The stored at-HEAD brief for 6360 turn 1 already names one
  (from training, not jurisdiction-driven), so compare before and after. The new rule forbids only
  an instrument added FOR the jurisdiction.
- **The quick-lookup Worker's first search query:** whether "Scotland" is added, and whether that
  moves which instrument is retrieved.
- **A clarifying question** ("which jurisdiction?") replacing an answer on a turn that answered
  before. That would be a regression of the default.
- **Case-law turns** (the conversational Manager also runs for "Case law only" and hybrid): a "for
  Scotland" brief reaching the case-law Worker, and whether answers then lean on the coverage gap.
- **Over-flagging:** the Scotland sentence on every turn of a long conversation, or on a question
  about one named UK-wide instrument (the third bullet should prevent it).

**The first round can be A/B'd at the cost of the draws.** `python seam_ab_check.py` (no model
call) shows that `--without-fix --rev ca3d45c` turns this tree's conversational Manager and
quick-lookup Worker prompts back into the integrator head's exactly, for all three research types
with no filter. With a Scotland filter the Manager swap is not exact, because the note also
changed. So `python -m tools.seam_replay manager --run <EV>/replay/wave4_p37_reach/6360_rep1.json
--turn 1 --first-round --date recorded [--without-fix --rev ca3d45c]` separates the first-brief
effect for 6360 and 6378 (both ran with no filter).

### 1.5 Tests, revert, mutants

- `tests/test_default_jurisdiction.py`, 131 tests:
  - (a) as booked: no extent note names a letter code (`E`, `W`, `S`, `NI`, `GB`, `+`, `&`), and
    each says "Most legislation search results carry no stated extent";
  - each note names exactly the territories `lex._JURISDICTION_ACCEPTS` keeps (so a filter change
    not carried into the prompt fails), and the filter block carries it;
  - the rule is in exactly the conversational Manager and quick-lookup Worker: every dispatch
    branch, flag and filter of the three builders, the planner and the synthesis;
  - the rule's clauses and the brief's no-instrument clause are present;
  - every new sentence trips no detector.
- **Revert** (`prompts.py` restored to `ca3d45c`: **63 lines removed, 7 restored**): **38 of 131
  fail**. The 93 that pass are the negative halves ("not in the research prompts") and two guards
  that held before; mutants M6 and M11 show the negative halves bite.
- **12 single-site mutants, all caught** (`python mut_p34.py`): each prompt piece removed alone;
  the Scotland note back to the letter code; the Wales note without the shared sentence; the
  Northern Ireland note dropping the UK; the rule added to the research Manager and to the research
  Worker; the brief's no-instrument clause removed; `uk_wide` saying "keeps"; the Worker rule as its
  own block; a NOT_FOUND-tripping Worker wording; "Most" changed to "Some".

### 1.6 Detector screen (`screen_p34.py`; pinned in `test_the_new_wording_trips_no_detector`)

Every new sentence was screened against: `NEG_ASSERTED`, `NOT_FOUND`, `NEG_TERMS`,
`NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `IN_FORCE_CLAIM`, `_CUR_DISCLOSED`, `_CUR_DATED`,
`SCOTS_CASELAW_GAP`, the three halt detectors, `OPENER_VOCAB`, `derivation_claims`,
`caselaw_gap_statements`, the footer stripper, the commencement denial, `_currency_asserted`,
`negcurrency_claim`, `sched_unit_clauses` and the corpus leak markers. **0 trips**, except the word
"filter":
- `NEG_LIMITS` and `NEGATIVE_EXPLAINED` match "filter" in the four territorial notes, the
  `uk_wide` note and the Manager section. The filter block's own header ("ACTIVE RESEARCH FILTERS")
  already matched both before P3.4, so this is not a new class.
- An answer that echoes "filter" is disclosing a real limit, which is what those columns credit.
  The test does not assert them, and says why.
- (`_GAP_CORPUS` and `_GAP_LIMIT` match common words, but they are sub-patterns of
  `caselaw_gap_statements`, which does not fire.)

---

## 2. P3.6 (commit `b48ad9f`)

### 2.1 Choice: keep every description, cut to 600 (not "only where it matches relationship
language")

`python desc_census.py` (every distinct stored search row, 7,189):
- **Lengths.** 6,535 carry real text: median **345** characters, p90 593, p99 1,197, max 10,946.
  The row's "73-210" was a ten-row sample. The API cuts 845 at 497 characters plus "...".
- **Dropped.** 282 are empty, 304 are dot leaders (no letter) and 68 are missing.
- **Relationship language.** 59.8% carry it, so a relationship-language gate would save little.
- **Why not a gate.** A gate is one more regex deciding what the model sees, and a gate can miss
  forms (the lesson every detector in this plan has taught). It would also drop the descriptions
  that help the Worker choose which instrument to retrieve in Phase 2.
- **What they hold.**
  - For most instruments: an explanatory note ("These Regulations amend ..."), or an Act's long
    title.
  - For older instruments, and for many SSIs: the front matter itself ("Made ... Coming into force
    ... The Scottish Ministers make the following Order in exercise of the powers conferred by
    ..."). That carries the instrument's own coming-into-force date and its recital.
  - 1,613 shown rows state "into force ... on <date>".
- **Provenance.** 1,780 of the 7,189 rows carry `provenance_source: llm_ocr`
  (`provenance_model: gpt-5-mini`): LEX's text for those instruments was transcribed by a model
  from print. This is not acted on here; it is relevant to how far any LEX text is quoted.

**The cap.** `python cap_p36.py`, the BUILT `_search_description` at each cap, over the 6,535:

| cap | whole | dated "into force ... on <date>" keeping its date | recital / made-under kept |
|---|---|---|---|
| 300 | 41.1% | 240 of 273 | 1,288 of 1,532 |
| 400 | 59.9% | 259 of 273 | 1,462 of 1,532 |
| 500 | 84.7% | 263 of 273 | 1,507 of 1,532 |
| **600** | **90.5%** | **266 of 273** | **1,515 of 1,532** |
| 800 | 95.8% | 270 of 273 | 1,523 of 1,532 |

**Chosen: 600.**
- It is `lookup_legislation`'s cap on the same field (`executor.py`, P3.7/P3.25), so a searched
  and a looked-up instrument show the same text up to the cut.
- Above it, each extra 200 characters keeps 4 more dated rows.
- The cut is at a space in the cap's second half, marked "..." (the API's own mark), and never
  mid-word: a date cut to "8 Octo" would be worse than none.
- Whitespace is collapsed. A value with no letter is dropped (no key).

### 2.2 The booked measurement: Phase-1 summarisation calls, unchanged

**Method.** `dryrun_p36_tree.py`, once in each tree, then `analyse_p36.py`:
- every stored `search_legislation` record is re-run through the BUILT executor
  (`execute_worker_tool`);
- the stored LEX response is served in place of `_request_with_retry`, under the turn's stored
  filters;
- each output is measured, with the code notes the product appends to it.
- **Coverage:** 6,521 re-run; 2,080 memo hits (they take their original's result) and 58 with no
  stored response were skipped.
- **Fidelity:** the before-tree output equals the stored `raw_result` byte for byte in **50 of the
  57 directories**, every one recorded after P2.5. The seven that differ (`baseline`, `wave1`,
  `wave2_p21`, `_p22`, `_p22_final`, `_p23`, `wave3_p35`) predate P2.5's `status` to
  `text_version` rename.

**A finding first: every stored replay was summarised at 8,000 characters, not 200,000.**
- `python threshold_probe.py`: in every directory, the largest unsummarised raw result is at most
  7,997 and the smallest summarised one at least 8,010.
- So `get_summarise_threshold()` fell back to `SUMMARISE_THRESHOLD_CHARS` on every replay. The
  dynamic context-length cache was cold, and `_resolve_model_context_length` never fetches.
- The same fallback applies to an Ollama model missing from `MODEL_LIST`, such as Thomas's
  `glm-5.2:cloud`.
- So 8,000 is the threshold that matters for this row.

**Results** (`analyse_p36.out`, `budget_p36.out`, `growth_p36.out`):

| | before | after |
|---|---|---|
| largest search result | 2,989 | **4,643** |
| results over 8,000 (the recorded threshold) | 0 | **0** (none moves) |
| results over 200,000 | 0 | 0 |
| rows shown with a description | — | 28,980 of 32,045 (90.4%); longest 599 |
| growth per call (output) | — | median 1,693, p90 2,230, max 2,941 |
| growth per call, with the block's clause change | — | median 1,960, p90 2,492, max 3,197 |

**Phase-1 summarisation calls: unchanged, 0 of 6,521 move.** This is pinned for the worst
realistic case in `test_five_long_rows_stay_under_the_default_summarise_threshold`: five rows, long
titles, and descriptions over the cap with curly quotes, which JSON escapes to six characters each.

**The knock-on, checked: the 250,000-character Worker context budget** (`budget_p36.py`).
- **The simulation.** Per delegation, in recorded order, "used" is the sum of earlier final
  lengths, and each search adds its measured growth.
- **It reproduces the recorded `summarised` flag on 15,213 of 15,213 tools.**
- **At 8,000: 0 tools flip** to summarisation.
- **The peak context of one Worker run rises from 188,337 to 235,779.** This is a pre-P2.7 run of
  29 searches; the median growth per delegation is 4,146 and p90 13,355.
- **At a hypothetical 200,000 threshold, 2 later tools would flip on the budget.** Both are in
  pre-P2.7 heavy runs (a `baseline` case-law text, a `wave2` section search). This is indicative
  only: no stored run ran at 200,000.

### 2.3 The code texts beside it: two would have become false or self-defeating, so they changed
(in `search_scope.py`; decision 5)

The `[SEARCH SCOPE]` block appended to every search result was written when no row carried a
description. Measured over the same 6,521 results with the built slimmer:

- **`_ADJACENCY_CLAUSE`'s "These rows carry NO relationship data: nothing here states what any
  instrument was made under" would be FALSE on 3,295 of the 5,632 results that carry it.** A shown
  description quotes the powers the instrument was made under ("In exercise of the powers conferred
  by section ..."). Hand-read: 24 of 25 sampled are recitals or "made under" statements. By the
  product's own recital test alone (`_ENABLING_RECITAL`, secondary instruments only, as P2.3 and
  P3.25 use it): 1,747 results showing 401 distinct instruments (`recitals_p36.py`).
- **`_RELATION_ROUTE_CLAUSE`'s "do NOT conclude anything about them from these rows"** would sit
  beside a description stating a relation on 5,415 results. That forbids quoting the dates the
  description was kept for (Session 40's lesson: a code text beside the new one contradicting it).
- **`_CURRENCY_CLAUSE`'s "state currency only from a `get_legislation_changes` relation, never from
  these rows"** stays true (a date a description states is not currency) and is unchanged.

**Built** (gated in code on the data, P3.20's pattern):
- where any shown row carries a description, the block drops the false sentence and points the
  route clause at "which rows came back";
- it adds ONE sentence, `_DESCRIPTION_CLAUSE`, after the currency clause;
- a result with no description keeps the old clauses byte for byte;
- the section-search block is unchanged.

After the change (re-run): the false sentence beside a recital description occurs **0** times (26
results without descriptions keep the old clause), and the old route phrase beside a relationship
description occurs **0** times. The block grows by 256 characters at the median (max 351). A long
query on a page of instruments reaches 2,495 characters, against 2,227 before.

**The exact new wording, for the user:**

> (adjacency, where descriptions are shown) An instrument ranking highly in a search for an Act's
> title has NOT thereby been shown to be made under that Act — do not say that it was.

> (route) Commencement, amendment, repeal and revocation are a special case: do NOT conclude
> anything about them from which rows came back. Call `get_legislation_changes` with the
> legislation_id — it is the only tool that returns those relations, and it answers in one call
> what no number of searches can.

> (new) A row's `description` is that instrument's own published summary, possibly cut short: you
> may quote it, citing the instrument (a date it gives for bringing provisions into force, for
> example), but it is not the change record, it is no evidence of current in-force status, and an
> enabling power it quotes still needs an ENABLING POWER block.

**Screened** (`screen_clauses_p36.py`; pinned in `test_the_new_clauses_trip_no_detector`):
- **0 trips for the three new texts**, and no bracket in them (they ride inside a `[…]` block).
- One wording was rejected: "it does not show that anything is in force now" tripped
  `IN_FORCE_CLAIM` and `_currency_asserted`.
- **A pre-existing finding:** the UNCHANGED `_CURRENCY_CLAUSE` ("is NOT evidence that anything is
  in force") trips `IN_FORCE_CLAIM` and `_currency_asserted`, so a Worker echoing it would be read
  as asserting currency. It is P2.5's text, and I left it alone.

**Other code texts about the same instrument, and whether they contradict the description:**
- `currency_note` ("nothing in a search result is [evidence that they are in force]"): consistent.
- `_IN_FORCE_RULE` (a): "for a date, retrieve the commencing instrument and quote it". Consistent:
  the row is the commencing instrument's own record.
- **`_RELATIONSHIP_RULE`: "Do not answer any of those from search results"** (in all three
  legislation Worker prompts, left byte-identical). Read together with the new clause: the
  relation still comes only from `get_legislation_changes`, and the description is quoted for what
  that instrument says (its date). A tension remains in wording, though not in instruction; watch
  for a Worker that declines to quote a dated description.
- **`_ENABLING_POWER_RULE`** (state made-under only from an `[ENABLING POWER]` block): the new
  clause repeats it. The Worker will now see recitals at Phase 1 that it may not state until a
  lookup or a text read builds the block (decision 6).
- `lookup_legislation`'s `description` (600, hard cut): the same text to the cut. The sources rail:
  unchanged (it reads named keys; a test pins it).

### 2.4 P3.21 (agent C): would the two ever state a date for the same instrument? Yes

`python overlap_p321.py`:
- **The overlap.** 367 stored turns hold a change record naming a commencing instrument by another
  instrument (`self: false`, the relation C dates from the legislation.gov.uk feed). **In 32 of
  them (16 distinct instruments), that same instrument is a shown search row whose description
  states "into force ... on <date>".**
- **Do the code texts contradict?** No, not in wording. C's code text says what the commencing
  instrument's stated in-force date is, with its source and qualification. Mine says a description
  is the instrument's own summary, quotable, and no evidence of current status.
- **When the two dates could differ:**
  - a description cut before a second date (7 of 273 dated descriptions lose a date at 600);
  - the feed's per-provision dates and "for specified purposes" qualifications, which a
    description words more loosely;
  - a feed error (batch 8 D found one date before the made date; C refuses those).
- **What follows.** The Worker could then see two dates for one commencement. E's P3.21 grader
  should treat a search row's `description` as a source of a stated date (SUPPORTED), and flag
  disagreements. There is no overlap in code: C edits `_slim_amendment_results`; I did not touch it.

### 2.5 The descriptions themselves as text a Worker can echo (`screen_desc_p36.py`)

Every one of the 2,480 distinct descriptions the dry run shows, screened as if echoed into an
answer:

| detector | matches |
|---|---|
| `OPENER_VOCAB` | 255 ("rights", "point", "agree": ordinary statutory vocabulary) |
| `derivation_claims` | 135 (recitals) |
| `_CUR_DATED` | 105 |
| `SCOTS_CASELAW_GAP` | 47 |
| `NEG_LIMITS` | 19 |
| `IN_FORCE_CLAIM`, `_currency_asserted` | 11 each |
| `NEG_BLAMED_INDEX` | 3 |
| `NOT_FOUND` | 1 |
| `negcurrency_claim`, commencement denial, `sched_unit_clauses`, leak markers | 0 |

Read by hand:
- **The 11 `_currency_asserted` matches are all local-Act preambles from the 1940s to 1960s**
  ("WHEREAS ... the unrepealed provisions ... are in force within the burgh"). An echo would be a
  stale currency claim, and the new clause's "no evidence of current in-force status" is worded to
  cover it.
- **`NOT_FOUND`** ("no objections ... have been made") and the 3 `NEG_BLAMED_INDEX` matches
  (a parenthetical "and not" naming a body) are statutory prose, not research negatives.
- **The rest is statutory vocabulary of the kind section text already carries.** No new class.
- **Neither `legislation.gov.uk` nor a block marker appears** in any description. 1,680 contain a
  bracket ("[12th July 1950.]"), all inside the JSON, none inside a block.

**For agent E and the integrator (grader notes; I edited no grader):**
- `retrieved_enabling` already reads `results[].description`. After P3.6 a recital in a search row
  counts as a retrieved enabling power, so the `derivations` support set grows. Pre-P3.6
  directories never had it, so compare columns with that in mind.
- `_currency_support` and `negcurrency_evidence` read search rows for title markers only. A date
  or a revocation a Worker quotes from a description is `dated_only` in `currency`, and has no
  evidence behind it in `negcurrency`.
- `cmd_corpus` prints "<- _slim_search_results strips it (P3.6)" beside its `description` count.
  That label is stale after the merge.

### 2.6 Input forms no stored run contains, tested on synthetic input

- A description of mostly non-ASCII characters, which JSON escapes six-fold: the worst realistic
  case is pinned under 8,000. An all-curly-quote description is not seen in 28,980 stored.
- One unbroken token longer than the cap: cut hard, not to nothing.
- Newlines and tabs.
- A non-string value (list, dict, int): no key.
- A date straddling the cut.
- A description containing a `legislation.gov.uk` URL: 0 stored. Synthetic: `harvest_legislation_urls`
  would add one junk key ("see http://... for the text"), which matches no citation, so it is
  harmless and left alone.

### 2.7 Tests, revert, mutants

- `tests/test_search_description.py`, 28 tests:
  - the cap (within it, marked, never mid-word, a date not split);
  - no-letter values give no key, and whitespace is collapsed;
  - through the executor, with and without a jurisdiction filter;
  - the worst case under the threshold;
  - the block byte-identical without descriptions, and the variants and the new sentence with them;
  - a page of Acts gets no adjacency clause;
  - the section block and the empty branch are untouched;
  - what `run_worker_tool` hands the Worker;
  - the detector screen and the block bound.
- **Revert** (`lex.py` +51/−2 and `search_scope.py` +48/−2 restored to `ca3d45c`: **99 lines
  removed, 4 restored**): the file fails at collection (the new names are missing). So, as the
  rules ask, two **stubs** were run: the old behaviour under the new names. S1 (the slimmer adds no
  description) fails 6 tests; S2 (the block never uses the variants) fails 3.
- **15 single-site mutants, all caught** (`python mut_p36.py`): S1 and S2, plus:
  - junk kept; no cap; a mid-word cut; no cut mark; whitespace not collapsed;
  - the gate always on; the adjacency variant keeping the false sentence; `_rows_described`
    reading the wrong key;
  - a currency-tripping wording; the section block given the variant; the clause order swapped;
  - the cap raised to 2,000; a bracket in the clause.

---

## 3. What I did NOT do

- No model call, seam draw, replay or live call. P3.4's acceptance (b) and the first-round effect
  on briefs are unmeasured.
- The rule is not in the research Manager, the planner, the research Workers or the
  parliament/Westminster prompts. That is decision 2. The parliament bot is Scotland-only by
  construction, and a default-Scotland rule is wrong for a UK Parliament bot.
- P3.14 not fixed: the quick-lookup Worker still never sees the filter block. The extent notes
  therefore still do not reach it, and with a filter set and a brief that omits the jurisdiction,
  that Worker would default to Scotland while the executor filters to another.
- The research Worker's "Note the territorial extent from the metadata (UK, Scotland, E&W)" (OUTPUT
  STRUCTURE) is left as it is. It is not a letter code of the API's, but it invites an extent where
  most rows carry none. A candidate for P3.4's research-mode follow-up.
- No ENABLING POWER block for search rows (decision 6). `executor.py`'s lookup cap is not pointed
  at `SEARCH_DESCRIPTION_CAP`: C and B edit that file.
- I did not grade the stored 6360 and 6378 turn-1 answers. That is agent E's check. No grader was
  edited.
- The UI's description of the jurisdiction filter (P3.4's row: "not checked") is still not checked.

---

## 4. Decisions for the user (recommendation first)

1. **P3.4's wording ("say so").**
   - (a) **Approve as built** (section 1.2): "say in your answer that this is the position in
     Scotland", which leaves the model to choose the phrasing.
   - (b) Script an opening, "In Scotland, ...". It is more uniform, but it reads oddly for an
     answer about a UK-wide Act.
   - (c) Script a closing line, "This answer is for Scotland; ask if you need another
     jurisdiction.", which is visible on every answer and reads as boilerplate.
2. **Which prompts carry the rule.**
   - (a) **The two booked prompts only, now** (as built). Book the research Manager and the Deep
     Research planner as a follow-up with its own Research-mode before-column, because a Manager
     edit moves every Research-mode first brief, the mode P3.2 and P3.3 are measured in.
   - (b) Also add it to the research Manager and the planner now, unmeasured.
   - (c) Also add it to the three research Workers. Not recommended: briefs already carry the
     jurisdiction.
3. **"The UK as a whole".**
   - (a) **Four parts, England, Wales, Scotland and Northern Ireland** (as built, the row's "all
     four"). It catches Welsh devolved legislation; the stored at-HEAD 6378 answers already treat
     Wales separately.
   - (b) Three legal jurisdictions (England and Wales, Scotland, Northern Ireland). Fewer branches,
     but a Welsh-only divergence would be missed.
4. **Merge order of D's two commits.**
   - (a) **Merge `e46f93b` (P3.4) alone, run P3.4's after-column, then merge `b48ad9f` (P3.6).**
     P3.6 changes every legislation Worker's Phase-1 input on every search, so merged first it
     would sit inside P3.4's after-column (Invariant 3). The commits touch disjoint files.
   - (b) Merge both and run the after-column with both, accepting the confound. P3.4's criterion
     (the jurisdiction named) is unlikely to move with P3.6, but that is unmeasured.
   - (c) Merge both and defer the after-column.
5. **P3.6 as built, including the `search_scope.py` clause change** (section 2.3; a file outside
   the brief's list, with the wording above).
   - (a) **Approve as built.**
   - (b) Ship the slimmer without the clause change. Not recommended: the block would state a false
     sentence on 58% of the results that carry it, and its route clause would forbid the dates.
   - (c) Defer P3.6 until a replay measures how the Worker uses descriptions. Its acceptance is
     deterministic and met, but its behavioural reach is every search.
6. **A new row: an ENABLING POWER block for a search row whose description quotes a recital**
   (P3.25 built the same for lookup records). By the product's own recital test, the rows shown in
   the dry run carry one for 401 distinct secondary instruments on 1,747 results (311 UK SIs, 42
   SSIs, 31 NI; 256 made before 1990). `retrieved_enabling` already counts such a description as
   support. **This corrects a premise:** P3.6's row (from P2.3) says that on the Scottish corpus it
   "adds no enabling-power coverage at all" (`lex_probe --enabling`: 0 of 28 SSIs, sampled from
   `/legislation/text`). Yet **212 distinct SSIs among the stored search API rows carry a recital in
   their description** ("The Scottish Ministers make the following Order in exercise of the powers
   conferred by ..."; 10 of 10 hand-read are genuine), and 742 UK SIs do. Command:
   `python recitals_p36.py`. The integrator should annotate P3.6's row (and P2.3's claim) with this.
   - (a) **Book it as a P3 row, measure first** (how many turns ask what an instrument was made
     under, where the row is shown and no lookup or text read follows).
   - (b) Build it now, in this batch's follow-up.
   - (c) No row: the prompt rule stands, and the Worker must look the instrument up.
