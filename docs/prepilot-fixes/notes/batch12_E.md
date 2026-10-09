# Parallel batch 12, agent E: P3.22's item 3, P3.4's research-mode follow-up, P4.22

Session 44, 2026-10-09. Based on `<INTEGRATOR_HEAD>` = `a99e4d4`. The worktree came up on `main`
(`a6b4a76`) with no commits of mine, so I ran `git reset --hard a99e4d4` first. **$0 in model
spend, 0 live calls.** No server, no replay, no seam draw.

**Shapes that differ from the brief, first:**
- **P4.22 is built in a third shape, not either of the row's two.** The row offers "strip a block,
  not a mention, or tell the Worker not to name the blocks". Built: a bare tag a sentence names
  (`an [ENABLING POWER] block`) becomes its own words without brackets or backticks
  (`an enabling power block`); a bare tag used as a label is still deleted (now with its backticks
  and one following space); every code-written block and closer is stripped exactly as before. The
  words the lawyer would now read are the model's own, unbracketed: decision 1.
- **P3.22 item 3 measured a defect the item does not name:** the summariser writes case citations
  its source does not hold, and some reach answers (section 2.4). Proposed as a new row (decision 4).

Scripts and outputs are in the gitignored `docs/prepilot-fixes/evidence/seam/batch12/E/`
(abbreviated `E/` below). Every command runs from the worktree root unless it says `cd server_py`,
with `PYTHONIOENCODING=utf-8` and `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`;
`<RP>` is `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`. **Counts include all 66
replay directories** (559 run files).

---

## 1. P4.22: the answer cleaner deleted a tag a sentence named

### 1.1 Measure first (clean)

| Number | Command |
|---|---|
| 2,710 Worker reports and 2,227 stored answers scanned; the BUILT `strip_scope_blocks` removes from reports 1,944 worker `[SEARCH SCOPE — …]` blocks, **5 inline `[ENABLING POWER]` mentions** and 1 line-start `[ENABLING POWER]` label; from stored answers nothing (they are stored after the strip) | `python E/p422_census.py server_py <RP> E` |
| No other tag name (`SEARCH SCOPE`, `CHANGE RECORD`, `CURRENCY`, `PINPOINTS TO KEEP`, `SECTION OUTLINE`, `PROVISION FETCHED BY CODE`) is named in brackets inside a sentence in any stored report; no stored report or answer names any tag in capitals without brackets | same; `python E/p422_unbracketed.py <RP>` |
| **3 stored answers carry the hole** (an empty code span, "contain an `` block"): `wave2_p23` 6383 r1 t4, `wave3_p38` 6383 r1 t4, `wave4_b11_sweep` `p310_6383` r1 t1. The other 2 mentions (`wave2` 6382 r1 t1 and 6383 r1 t4, both Deep Research) were reworded by the synthesis. No other hole shape (a double space before "block"/"note", empty brackets) in any of the 2,227 answers | `python E/p422_holes.py <RP>` |
| P3.31's exposure: delegations whose tool results carried an `[ENABLING POWER` block, **207 of 2,692 (7.7%) outside `wave4_p331`, 28 of 34 (82%) in it** (473 against 131 blocks; in `wave4_p331`, 24 made-under list blocks, 72 permitting, 35 not-stated). Inline mentions: 5 in the 207 before P3.31 (2.4%), 0 in the 28 after; the one line-start label is in `wave4_p331` 6383 r2 t4 | `python E/p422_exposure.py <RP>` |
| The model already writes the block's name unbracketed: "enabling power block(s)" 12 times in 10 stored answers and 14 times in reports | `python E/p422_unbracketed.py <RP>` (the "change record notes" hits are the verb, read and discarded) |

All five inline mentions are on the pinned Gemini, all in made-under questions (6382, 6383), four
of them Thomas's. The fifth (`wave4_b11_sweep` `p310_6383` r1 t1) is new since his census. The
line-start label (`*[ENABLING POWER] Coverage note: …*`) was stripped to `* Coverage note: …*`, a
bullet with a stray asterisk; it did not reach the answer. **Read each one by hand.**

### 1.2 The change (`server_py/src/utils/search_scope.py`)

`_BARE_TAG` matches a bare tag (`[NAME]`, nothing after the name, optional backticks on both sides,
one optional following space) for the seven names `_TOOL_BLOCK` strips without a dash. `_bare_tag`
returns the name in lower case plus the following space where the tag sits **inside a sentence**:
the text before it on its line ends in a letter, a digit, `(` or `,`, and the next character is a
lower-case letter, `.`, `,`, `;`, `:`, `)`, a line end or the text's end. Otherwise (line start, after
a sentence's end, before a capital or a link's `(`) it returns `""`. `strip_scope_blocks` runs it after
the four whole-block passes and before `_TOOL_BLOCK`, and counts it. **Code never writes a bare tag**
(every opener in `src/` carries ` —` and text, every closer a `/`; checked with
`grep -rnoE "\[/?(SEARCH SCOPE|ENABLING POWER|…)[^a-z]{0,4}" src/`), so a bare tag is always a model's.
`SCHEDULES AND ANNEXES` is left out: `_TOOL_BLOCK` strips it only with its dash.

Other code texts on the same block: `prompts.py`'s ENABLING POWER rule teaches the bracketed name
("an [ENABLING POWER] block", the likely source of the mentions; decision 2); `made_under_note`'s
and `instrument_lookup`'s docstrings (a block with brackets is still stripped). None contradicts.
Readers of the strip's output: `agent_core` (answer and Deep Research report), `step_handover`
(ids only, unaffected), and graders through `[0]` (no caller uses the count but for logging).

### 1.3 Dry run with the BUILT code, every stored report and answer

`python E/p422_dryrun.py server_py E/old_sp <RP> E` (the old strip from `git show a99e4d4:` in a
scratch copy, asserted to lack `_BARE_TAG`): 66 directories, 2,710 reports, 4,438 answer texts (the
answer and the audit's copy). **6 outputs move, all reports; 0 answers; 0 strip counts.** Each
changed line, read:

| Run | Before (old strip) | After |
|---|---|---|
| `wave2` 6382 r1 t1 report 2 | "… as no  block was retrieved …" | "… as no enabling power block was retrieved …" |
| `wave2` 6383 r1 t4 report 2 | "… does not contain an  block or preamble." | "… an enabling power block or preamble." |
| `wave2_p23` 6383 r1 t4 report 2 | "… contain an `` block or preamble." | "… an enabling power block or preamble." |
| `wave3_p38` 6383 r1 t4 report 1 | "… provides an explicit `` block quoting the preamble." | "… an explicit enabling power block quoting …" |
| `wave4_b11_sweep` `p310_6383` r1 t1 report 1 | "… recital (an `` block)." | "… recital (an enabling power block)." |
| `wave4_p331` 6383 r2 t4 report 0 | "* Coverage note: …*" | "*Coverage note: …*" |

**Forms no stored run contains, tested synthetically:** the other six names; a tag after `(` or `,`;
before closing punctuation, a line end or the text's end; before a capital mid-line (a label); after
a sentence's end; a lower-case tag; a one-sided backtick; a tag before a link's `(`; a full header
named inline; a stray closer; a bare `SCHEDULES AND ANNEXES` (unchanged).

### 1.4 Screen

`python E/p422_verdicts.py server_py E/p422_dryrun_moved.json`: **0 verdict changes** on the 6 moved
lines over `HALT_PARAPHRASE`, `NOT_FOUND`, `NEG_ASSERTED`, `NEG_TERMS`, `NEG_LIMITS`,
`NEG_BLAMED_INDEX`, `OPENER_VOCAB`, `SCHED_LIMIT`, `MD_LINK`, `derivation_claims`,
`_currency_asserted`, `negcurrency_claim`, `sched_clause_class` (`NEG_ASSERTED` and
`derivation_claims` match on both sides; only the matched text changes). Synthetic renders, 7 names
by 8 forms (`python E/p422_screen.py server_py E/p422_dryrun_moved.json`, output `E/p422_screen.txt`):
one moves a detector. "so no [PROVISION FETCHED BY CODE] was given" now reads "so no provision
fetched by code was given", which `NOT_FOUND` and `NEG_ASSERTED` match where the hole did not. That
is the model's own negative becoming visible, which a careful reader would also call a negative.
Rendered, the words read as sentences for every name ("does not contain an change record block"
shows the article is the model's, not ours).

### 1.5 Tests, revert, mutants, suite

- `server_py/tests/test_strip_mentions.py`, 29 tests (synthetic text only).
- **Revert** (the old `search_scope.py` in a scratch copy: **32 added lines removed, 1 restored**):
  **23 of 29 fail**. The 6 that pass are the unchanged-behaviour guards (a whole block, a closer, a
  full header inline, a bare `SCHEDULES AND ANNEXES`, a tag before a link, a one-sided backtick).
- **20 single-site mutants, 19 caught** (`python E/p422_mutants.py`, output `E/p422_mutants.txt`):
  each half of the "before" test (letters, `(`, `,`, the emptiness guard), each half of the "after"
  test (text's end, line end, lower case, `.`, `)`), the trailing space kept for a mention and
  dropped for a label, `lower()`, the backtick backreference, `re.I`, one name dropped, the pass
  moved after `_TOOL_BLOCK`, the count, the pass removed, the label branch removed. **M20 survives
  and is equivalent:** the `nxt != ""` guard on the punctuation set can only matter for `""`, which
  the first clause already accepts. (The first draft had no guard, and M5, "text's end" dropped,
  survived because `"" in ".,;:)"` is true in Python; the guard makes that clause the one that decides.)
- **Full suite on `lexchat_test_e`: 3,046 passed** (3,017 + 29).

### 1.6 Acceptance

*Deterministic: unit tests for a block and for an inline mention, each failing with the change
reverted; a dry run over every stored report and answer, every changed one listed and read.*
- Inline mention: **met** (its tests fail on revert).
- Block: **met for a line-start label** (its tests fail on revert). A code-written block's own test
  cannot fail on revert, because its handling did not change; it guards non-regression, and
  mutants M16 and M18 show that it depends on the pass order.
- Dry run: **met**: 6 changed outputs, all listed and read above; 0 answers.

**Not merged until the user approves the words (decision 1).**

---

## 2. P3.22 item 3: an out-of-corpus leading case named as if read

### 2.1 The grader over every stored instance

`cd server_py; python -m tools.replay_report --dir <RP>/wave2 authorities --all-dirs`: every stored run
of 6359 and 6363 is 18 runs (9 each, in `baseline`, `wave1`, `wave2`, `wave4_b9_sweep1`,
`wave4_b9_sweep2a`), with 25 answer-turns that name an out-of-corpus rubric authority. **Grader:
PASS 14, EARLIER 5, FAIL 6.** A wider pattern (any party surname or the report citation;
`python E/p322_item3_dump.py <RP> <rubric> E/p322_item3_dump.txt`) finds 29 turns. The 4 extra are
not instances: 3 name an in-corpus EAT judgment sharing a surname, and 1 is a footer listing the query.

### 2.2 By hand (gitignored `E/p322_item3_handread.md`)

The rule I applied (the brief says "as if read"): PASS where the **first** statement of the
authority's holding is tied to a retrieved judgment that cites or applies it (in that sentence or the
one before), or the answer says the judgment is not held; EARLIER where it is not, but an earlier
answer in the run did that; FAIL otherwise, or LINKED (its name on another judgment's link).

| | Hand PASS / EARLIER / FAIL | Grader | Disagreements |
|---|---|---|---|
| 6359 (18 answer-turns) | 9 / 4 / 5 | 10 / 4 / 4 | `sweep1` r3 t6: the holding is stated on the authority's own terms first, and the carrier "applied" it a paragraph later. The grader passes it on the later sentence. Its twin, `sweep2a` r2 t6 ("applied this principle"), FAILs only because the grader cannot read the anaphor. |
| 6363 (7) | 2 / 1 / 4 | 4 / 1 / 2 | `wave2` r1 t5 and `sweep2a` r1 t1: Deep Research reports that state the holding first in a key-findings bullet or a case-list entry, and tie it to a retrieved judgment only later in the body |
| **All 25** | **11 / 5 / 9** | 14 / 5 / 6 | 3, every one the same shape (holding first, tie later) |

**By column:** `wave4_b9_sweep1` (before, default order): 1 FAIL by hand (grader 0). `wave4_b9_sweep2a`
(after, relevance): 3 FAIL by hand (grader 2). The stored `wave1` has 2 and `wave2` 3. **Item 3 is
not an ordering effect:** the carrier is retrieved in 9 of 9 runs of 6359. In 6359 the out-of-corpus
authority comes in through the lawyer's own question ("are you familiar with …"). In 6363 it comes
through retrieved judgments that cite it, and through summaries (2.4). None of the 18 answers in 6359
says the database does not hold the judgment. One says what it does hold. Eight open "Yes, both
cases …" or "I am familiar with both cases".

### 2.3 Beyond the rubric

`cd server_py; python ../E/p322_lawreports.py . <RP> ../E/p322_lawreports.txt`: of 2,226 answers, 51
answer-turns name an authority by a law report only (no neutral citation, no Find Case Law link), in
8 sessions. By hand, outside 6359 and 6363: 6343's is an in-corpus judgment the lawyer named by its
report (not an instance); 6375's are tied to a retrieved tribunal decision in 6 of 7; **6411 names a
Court of Session case (which the National Archives' collection does not hold), 6341 three authorities
and 6348 one, none of which appears in any tool's raw result in its run** (`python E/p322_provenance.py <RP>`).

### 2.4 The summariser writes citations its source does not hold (new)

`python E/p322_provenance2.py <RP>`: in 6411, 6341 and 6348 the authorities first appear in a
**summarised legislation result** (`get_legislation_changes`, `search_legislation_sections`), not in
its raw text. In 6411 the summary of a change record carries a section headed as case-law search
results. The Worker then reported that "a search for case law … returned" them.

`cd server_py; python ../E/p322_summariser_citations.py . <RP> ../E/p322_summariser_citations.txt`:
of 5,615 summarised tool results, **50 carry a case citation that their raw result lacks** (the raw
JSON decoded; a report citation split by words in the source counted as present; citations echoed
from the question, brief or args excluded: 9 more results). A first pass without decoding reported
78, because the raw text holds `\n` escapes. **Validated by hand on 8**
(`python E/p322_rawcheck.py …`). `python ../E/p322_summariser_classify.py …` sorts the 40 that name
the case:

| Class | Results | By tool |
|---|---|---|
| The source never names the case: the summary brought it in | 26 (+2 by hand of the 4 "partly"; on 4 of the 26 the classifier could not extract a name to check, so they rest on the citation alone) | `search_case_law` 15, `get_legislation_changes` 6 (6411, all 6 runs), `search_legislation_sections` 4, `get_case_law_text` 1 |
| The source names the case; the summary gives a citation the source does not (a law report turned into a neutral citation, sometimes the wrong one; a summary headed with a different neutral citation from the judgment's own URL) | 10 (+2) | `get_case_law_text` 9, `search_case_law` 1 |

The sessions are 6341, 6343, 6346, 6348, 6359, 6363, 6370, 6375 and 6411, on the summariser
`google/gemini-3-flash-preview` and at the 8,000-character fallback. **Reached answers in 6341, 6348,
6411 and 6363.** A lawyer cannot tell, which is P1 on the tracker's scale. It is a summariser defect,
so the case law the Worker reports can come from no tool at all. Decision 4.

### 2.5 Sizing a code lever

`python E/p322_named_case_queries.py <RP> E/p322_named_case_queries.txt`: 54 stored `search_case_law`
calls name a case ("A v B"): 9 returned it, 30 did not (20 for 6359's out-of-corpus authority, 8 for
6363's), 15 returned nothing. **Every item-3 instance in 6359 followed a search that named the
authority and did not return it.** That is the moment code could say so (decision 3). Caution: one
query's case may be in the collection under another title, so the wording can only say "not returned
by this search".

---

## 3. P3.4's research-mode follow-up

### 3.1 The before-column for the research Manager and the Deep Research planner

`cd server_py; python ../E/p34_latest_turn1.py . <RP> ../E/p34_latest_turn1.txt`: for each session, the
latest stored run whose Research or Deep Research turns name no jurisdiction (in that question or any
earlier one): **8 sessions, 18 turns**, filter none on every one. I excluded 6347 t1 by hand, because
it names an EWCA judgment. Of the 17, **by hand 2 PASS** (6363 t1 and 6406 t2, both Deep Research)
**and 15 FAIL**: 8 name England and Wales (honestly) and never Scotland, 1 names Great Britain but not
Northern Ireland on a "the UK" question (6389), and 6 name no jurisdiction. The BUILT `jx_verdict`
agrees except on 6335 t2, which it passes on an incidental Scottish carve-out. **The first brief or plan
names a nation in 0 of 18.** In the conversational after-column (`wave4_b9_sweep3`), every first
brief did. The heads are mixed (`2d9ae11`, `9ba8ee8`, `e0bf656`, `68fd879`). The research prompts did
not change at P3.4, so these turns stand as their before-column. Corpus-wide, every directory and
rep (`python ../E/p34_research_before.py . <RP> ../E/p34_research_before_all.txt`): Research 152
turns, PASS 33, FAIL 119; Deep Research 34, PASS 21, FAIL 13; the first brief or plan names a nation
in 16 of 186.

### 3.2 The research Worker's "Note the territorial extent from the metadata (UK, Scotland, E&W)"

`python E/p34_extent_claims.py <RP> E/p34_extent_claims.txt`: 1,134 research-Worker reports, 1,016
with a Jurisdiction & Status section. Extent claims mapped to an instrument: **757, of which 685 have
a search row with a stated extent, 71 only rows with none, and 1 instrument was not searched**. 534
were unmapped (an instrument outside that delegation's rows, a case-law claim, or a title not
matched). Of the 71, by hand: 19 say the metadata gives none, 10 cite the instrument's own extent
provision, 14 follow a "(Scotland)" title, and **28 state an extent with no source** (5 of them say
first that the metadata has none). 6341 accounts for most. **In the recent columns (`wave4_b9_*`,
`wave4_b10_sweep`, `wave4_b11_sweep`, `wave4_p331`): 55 mapped, all with a stated extent, 0 without**
(`… E/p34_extent_claims_recent.txt wave4_b9_sweep1 … wave4_p331`). The line invites an unsourced
extent, mostly in the older runs.

### 3.3 The UI's description of the jurisdiction filter (read, not changed)

`client/src/constants/research.js` `JURISDICTION_OPTIONS` gives labels only. `ResearchFiltersModal.jsx`
shows one note, the case-law coverage note (true). **Nothing tells the lawyer** (a) that the filter
keeps law that *applies in* the nation, UK-wide law included (`lex._JURISDICTION_ACCEPTS`); (b) that
it keeps the rows with no stated extent (57.8% of stored API rows), except "UK-wide only", which
removes them; (c) that it narrows legislation searches only. Separately, `DataSourcesModal.jsx` says
the Legislation API "provides comprehensive coverage across all four nations", which is at odds with
the scope footer ("an index that is known to be incomplete …").

---

## 4. What I did NOT do

- No model call, seam draw, replay or live call. Nothing in section 2 or 3 was rebuilt or replayed.
- P3.22: no product change; `replay_report authorities` not edited (decision 5); the rubric not edited.
- The summariser finding: not fixed and not booked (the integrator books rows); its counts are by a
  heuristic validated on 8 results, not every one.
- P3.4: no prompt or UI change; the research Manager and planner rule is not built.
- P4.22: no prompt change; the stored answers' three holes are history and are not rewritten.
- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, any rubric, the tracker or any memory file.

## 5. Decisions for the user (recommendation first)

1. **P4.22's words: what a sentence's mention of a block becomes.**
   - (a) **The model's own words, unbracketed and in lower case** ("an enabling power block"; as
     built). We add no words, and the model already writes it this way in 10 stored answers.
   - (b) A phrase per tag ("enabling power statement", "change record", …), absorbing a following
     "block"/"note". Reads better to a lawyer, but we would be writing words into its sentence.
   - (c) Delete as before, but take the backticks and the double space with the tag. No jargon,
     but "contain an block" is still a hole.
2. **The prompt that teaches the bracketed name.**
   - (a) **Leave `prompts.py`'s "[ENABLING POWER] block" as it is**: the strip now handles a
     mention, and a prompt edit reaches every Worker call (P3.13's lesson).
   - (b) Reword it unbracketed, measured first with a first-round probe.
3. **P3.22 item 3.**
   - (a) **Split item 3 into a new row** (answer seam: an out-of-corpus authority named as if read;
     bar = the first-statement rule above, hand-read) and tick P3.22 on items 1, 2 and 4, which are
     met. Ordering cannot pass item 3, and both columns fail it.
   - (b) Keep P3.22 `[~]` until item 3 passes.
   - (c) Accept the grader's rule and the current rate.

   Lever for the new row, if (a): **a code-written note in `search_case_law`'s result when the query
   names a case that no returned title matches** (P3.7's held/absent pattern, "not returned by this
   search"; wording to you), or a code line at the answer seam (P3.13's pattern), or a prompt rule.
4. **The summariser writes case citations its source does not hold (2.4).**
   - (a) **Book a new row at P1, measured here**; its first lever is code: drop or flag a citation
     the summary carries and the source does not (the census's own test, on the raw text before it
     is summarised).
   - (b) Fold it into decision 3's new row.
   - (c) Note only.
5. **The `authorities` grader** (tooling): (a) **teach it the first-statement rule and the anaphor**
   ("applied this principle"), validated against this hand-read; (b) leave it.
6. **P3.4's follow-up.**
   - (a) **Build the default rule into the research Manager and the Deep Research planner** (the
     conversational wording, approved), then a Research-mode after-column on 6335, 6350 and 6385
     (priced first).
   - (b) As (a), and also reword the OUTPUT STRUCTURE line to "the extent where the metadata states
     one; where it states none, say so" (Worker-facing wording to you).
   - (c) Defer.
7. **The UI.** (a) **One line under the Jurisdiction filter** saying what it keeps (law that applies
   in the nation, UK-wide included; results with no stated extent kept, except "UK-wide only"; case
   law not filtered), and correct "comprehensive coverage" in the data-sources box (wording to you;
   a client build); (b) leave.
