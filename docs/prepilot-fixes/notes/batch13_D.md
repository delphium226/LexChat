# Batch 13, agent D: P4.23's answer-seam linker built ($0)

**Branch:** `worktree-agent-adfc9405f677593c3`, based on `<INTEGRATOR_HEAD>` = `1889abb`; the product change and
tests are commit `4513e3a`, this note the commit after it (the dry run re-run on `4513e3a`: identical, `dry_final`). The worktree came up on
`main` (`a6b4a76`) with no commits of mine, so I ran `git reset --hard 1889abb` first. No other session's commit is
in my base. **Spend $0**: no model call; **0 external calls** (0 LEX, 0 legislation.gov.uk, 0 National Archives, 0
SCTS, 0 OpenRouter). No server, no replay, no seam draw. **Model:** every stored answer read here ran on the pinned
Gemini (`google/gemini-3.1-pro-preview`); none is from `glm-5.2:cloud`. Nothing here depends on summarisation.
**Counts** are over every post-P2.1 directory (all 70 but `baseline`, `wave1`: 68), and separately over the 64 that
batch 12 D's prototype read, to compare like with like.

**Result in one line:** the linker is built at the conversational Manager's answer seam as decided (the report's
instrument URL; a provision URL only where the answer names that provision beside the mention; batch 12 D's guards
plus five more), and the dry run with the BUILT code over every stored Conversational answered turn adds **79 links
in 71 turns** (68 directories). On the prototype's 64 directories it adds **78 in 70**: **all 74 of the prototype's
links** (67 at the same mention with the same URL, 7 with the same URL at an earlier mention, the title instead of
the SI number) and **4 more**, every one read and right. Guard drops: 55 (50 provision not named beside the mention,
5 quoted). No grader verdict that any exit-1 subcommand reads moves; R re-admits the same sources. Tests 79, revert
276 lines, mutants 58 of 58, suite **3,458 passed**. Decisions 1 to 6.

## 1. What I changed, function by function

**`server_py/src/utils/citation_links.py`** (all new; nothing existing changed but `__all__`):
- constants `_MD_LINK_NESTED`, `_BARE_URL`, `_RESTORED_NOTE`, `_BELOW_INSTRUMENT`, `_VERSION_TAIL`,
  `_INSTRUMENT_PATH`, `_PIN_WORDS`, `_URL_SEGMENTS`, `_BESIDE_CHARS` (100), `_SI_NAME`, `_EU_NAME`;
- `instrument_key(url)`: the instrument a legislation.gov.uk URL is for (`type/year/number`, lower case; strips
  `/id/`, the scheme, `www.`, a provision path, an EU annex, `/contents`, `/made`, `/enacted`, a point-in-time date;
  knows both regnal forms);
- `_below_instrument(url)`, `_links_at(text)` (markdown links incl. nested-bracket labels, then bare URLs, in text
  order), `_title_pattern(title)`, `_first_mention(...)`, `_provision_beside(...)`, `_guard(...)`;
- `plan_instrument_links(answer, reports, sources, titles)` -> `(edits, drops)`: the planner, used by the dry run;
- `link_named_instruments(answer, reports, sources, titles)` -> `(answer, links added)`: applies the plan,
  idempotent, fail-soft.

**`server_py/src/utils/source_naming.py`:** two new public helpers, `nameable_title(title)` and
`heads_longer_title(following)` (wrapping the existing `_BARE_LID`, `MIN_TITLE_CHARS` and `_LONGER_TITLE`). No
existing function changed.

**`server_py/src/agent/agent_core.py`:** the import, and in **`process_user_request`** one call,
`link_named_instruments(clean, manager_inputs, retrieved_sources, retrieved_titles)`, inside the existing
conversational block (`_chat_mode == "conversational" and not answer_failed`), gated on
`research_mode not in _RAIL_FALLBACK_MODES`. No other function touched: `run_deep_research`,
`worker_result_for_manager`, `run_worker_agent`, `readmit_answer_sources`, `title_rail_sources`, P3.13's
`restore_dropped_siblings` and `link_sibling_pinpoints`, and **`utils/paragraph_restore.py` (agent B's) are
unchanged**.

**Tests:** new `server_py/tests/test_instrument_links.py` (79).

**Where the built shape differs from the prototype (`evidence/seam/batch12/D/p423.py`); relay these:**
1. **Lookup titles** (`retrieved_titles`, P4.24's) name an instrument too: +2 links (6374, 6409), both read, right
   (an Act known to the turn only by a change record's id, named by its title).
2. **A title as written** (`_title_pattern`): every punctuation mark of the title is a token, so a hyphen or "etc."
   no longer defeats it (the prototype's 2 `NOHIT`s): +2 links (6338, 6406), both read, right.
3. **The earliest mention wins across routes**, the longest at one place: 7 prototype links (6383 t3 x2, 6373 t2,
   6409 t3 x4) move from the SI number in brackets to the full title just before it, same URL, read, right.
4. **Class B picks the provision URL the answer names** among all the report's provision URLs for the instrument,
   and only when exactly one is named (two named: dropped); every segment must be named (`/schedule/2/paragraph/3`
   needs "Schedule 2" and "paragraph 3"); a segment an answer cannot name (part, chapter, annex) is never beside.
   The prototype read only the report's first URL's first segment. Moves 0 stored links.
5. **Five guards beyond batch 12 D's three**, each 0 drops in the stored answers and each tested on synthetic input:
   a mention inside a `[...]` block (an echoed scope block: a `[` or `]` added there would stop the strippers); an
   emphasis mark inside the span ("**Widget** Order 1901" would cut the pair); a fenced code block; two
   instruments at one mention; two provisions beside one mention.
6. **The quotation guard reads the line with links masked**, so a quote mark inside a link label or URL no longer
   counts. Moves 0.
7. **A restored note's link counts as the answer linking the instrument**, as the prototype read it (its
   `ans_lids` read the whole answer), and a mention inside a note is never linked (as the prototype's mask).
8. The label leaves out a leading "the" ("the [Widget Order 1901](...)"); cosmetic.
9. **Off on the parliamentary bots** (`_RAIL_FALLBACK_MODES`, as lever R): no stored replay ran on them (decision 3).
10. **Halted (partial) reports are read too** (`manager_inputs` holds every report handed to the Manager); over the
    stored turns this adds nothing (the completed-only run gives the same 78 on the 64 directories).

## 2. Where it sits in the answer seam, and what each step reads

In `process_user_request`, conversational chat mode, an answer that did not fail, in this order:

1. `extract_suggestions`, `strip_answer_footer`, `strip_agreement_opener` (unchanged);
2. **P3.13 `restore_dropped_siblings`** reads the answer's section links and plain pinpoints and the reports: it
   runs before the linker, so it never sees a link the linker adds (a linker before it would have changed what it
   reads: `test_a_restored_note_that_links_the_instrument_counts_as_linking_it` fails on that order, mutant
   "before P3.13's restore");
3. **P3.12 `restore_dropped_paragraphs`**, then `misattributed_paragraphs` (logging): read before the linker too;
4. **P4.23 `link_named_instruments`** (new) reads the answer with both restores' notes in it: a note
   (`\n\nAlso in ...`, the opening both restores write, pinned by a test that renders P3.12's line with
   `paragraph_restore.render_line`) is masked, so its words are never linked, and a link in it counts as the
   answer's; it reads the reports as handed to the Manager (`manager_inputs`, scope blocks stripped), every source
   the turn retrieved (`retrieved_sources`, lever R's list) and every lookup's title (`retrieved_titles`);
5. **P1.6 `enforce_provision_links`** reads every link, the linker's included: a class-B link to a provision URL no
   tool returned is demoted with the † marker like any other (tested; in practice the reports' links were already
   enforced at the Worker seam, and `summary`'s MANUFACTURED count stays 0 on every changed directory);
6. the scope-block strip and the lost and halt disclosures (unchanged);
7. **P4.3 lever R `readmit_answer_sources`** reads the linked answer: `_source_is_named`'s token branch now sees the
   added URL, so an instrument the rail knew only by a change record's bare id, named in the answer by a lookup's
   title, is re-admitted (tested synthetically). Over the 71 stored turns the linker changes, R re-admits 1 source
   before and the same 1 after: 0 turns move;
8. **P4.24 `title_rail_sources`** reads the rail, not the answer: unaffected; then the footers.

**Collision with agent B:** my mask depends on P3.12's line opening `\n\nAlso in `. If B changes that opening,
`test_a_restored_schedule_paragraph_line_is_never_linked` fails at the merge, by design.

## 3. The dry run with the BUILT code

`dry423.py` (scratch) imports this worktree's `server_py` (asserted), rebuilds each turn's inputs as the product
builds them (`agent_shared._extract_sources_from_tool` over every delegation's raw results for `retrieved_sources`;
`instrument_lookup.parse_lookup_result` for the lookup titles; every delegation's stored report), reads the stored
answer without the scope footer (`replay_report._without_footer`), and calls `plan_instrument_links` and
`link_named_instruments`; it asserts a second pass adds nothing (idempotent) on every turn.

| Conversational answered turns | 64 directories (the prototype's) | 68 directories (every post-P2.1) |
|---|---|---|
| turns read | 1,350 | 1,382 |
| **links added (class A / class B)** | **78 (55 / 23) in 70 turns** | **79 (56 / 23) in 71 turns** |
| prototype (batch 12 D) | 74 in 67 | - |
| guard drops: provision not named beside it | 50 | 50 |
| guard drops: quoted | 5 | 5 |
| guard drops: bracketed, emphasis, two instruments, two provisions | 0 | 0 |

By turn class (`replay_report.rail_turn`): 77 on report turns, 2 on `report_mixed`. The 68th-directory link
(`wave4_b12_p312` 6335 rep 3 t1) is read and right. **Every one of the 79 is listed with its context in the gitignored
`dry_all.list`**; the 74 the prototype also made were all read in batch 12 (section 7 of `notes/batch12_D.md`), and
`cmp423.py` / `cmp_url.py` show each is the same instrument, and the same mention or (7) an earlier one, with the
same URL. **Read here:** the 4 new links, the 7 moved mentions, the 68th directory's link and the 3 window-only class B
links (decision 2).

**Links by session** (A / B): 6409 26/1, 6383 7/0, 6406 3/4, 6375 0/6, 6338 3/3, 6373 4/0, 6335 3/1, 6370 2/2,
6369 0/3, 6374 1/2, 6410 3/0, 6411 2/0, 6354 1/0, 6380 1/0, 6381 0/1.
**Guard drops by session:** quoted 5 (6409 rep 1 t5 and rep 3 t2 in `wave2_p22`; 6370 t6 in `wave4_b4_post`,
`wave4_p33_post`, `wave4_p33_pre`); provision not named beside it 50 (6406 11, 6409 9, 6348 8, 6375 7, 6335 4, 6370 4,
6373 3, 6396 3, 6345 1).

**Input forms no stored run contains, tested on synthetic input** (`test_instrument_links.py`): an echoed `[...]`
block, a multi-line one; an emphasis pair cut by the title; a fenced code block; curly quotation marks; an unclosed
quote on an earlier line (must NOT block); two instruments sharing one title; two provisions named beside one
mention; a schedule paragraph URL (both segments needed); a schedule part and an EU annex (never beside); the
100-character boundary on both sides of it; "section 50" against `/section/5`; an old SI "YYYY No. N"; an EU
"Regulation (EU) No N/YYYY"; "SSI 1901/31" against `ssi/1901/3`; a hyphen and either apostrophe in a title; a title
inside a longer word run on either side; two titles of one instrument at one place (the longer is the label); a
bare-id or short title; a source with no `_lid`; a report URL only inside a scope block; a bare report URL with a
trailing full stop; a bare URL before and after a markdown link in a report; an instrument the answer links by a
provision URL, by a bare URL, by another spelling; another host; a nested-bracket case label holding a title; a P3.13
note and a P3.12 line; an error inside the planner (fail-soft); non-string reports and non-dict sources.

## 4. What the linker moves downstream (checked with the built code, in memory, no file copied)

- **Every `replay_report` subcommand (33), before and after, on the 59 run files the linker changes, in 30
  directories** (`graders423.py`: `Path.glob` and `Path.read_text` patched in memory): **no verdict and no exit code
  moves** except one: `rail` on `wave4_b9_sweep1` goes from exit 1 to 0 (its 2 Conversational report turns: unused by
  the reader test 1 of 6 to 0 of 6, because the answer now cites a bare-id-titled rail source by its URL). What
  moves otherwise: link counts (`summary`'s provision links rise; its MANUFACTURED count stays 0 and its
  wrong-granularity count is unchanged in every directory); answer lengths (`caselaw`, `scripted`); `lookup`'s links
  column (1 row, verdict unchanged); the quoted sentence text in `negcurrency` and `cmcdates` (verdicts unchanged);
  `cmcdates`' display flag "source named" on 2 claims, because `_CD_SOURCE_WORDS` reads "legislation.gov.uk" in the
  added URL (no verdict reads the flag; decision 5); `rail`'s token-test counts.
- **`rail --all` over all 68 directories** (stored rails): Conversational unused by the reader test 1,110 to 1,108
  (41.1% both), by the token test 1,554 to 1,486; Research and Deep Research unchanged.
- **Every module-level regex in `replay_report`** (`sweep423.py`), match counts before and after on the 71 turns:
  `NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_INDEX`, `NEG_LIMITS`, `NEG_TERMS`, the `HALT_*` patterns, `OPENER_VOCAB` and
  `SCHED_LIMIT` move on 0; `derivation_claims`, `_currency_asserted`, `negcurrency_claim` and `sched_clause_class`
  move on 0. The movers are link and URL patterns, `_STANCE_CLAUSE` (it splits on brackets; `stance`'s output did not
  move), `_DERIV_SRC`/`_DERIV_NUMBERED`, `_CUR_LEGISLATION_NOUN`, `_NC_PARTITIVE`, `_CD_*` and `LK_*`, each read by
  a subcommand whose output is covered above.
- **Text:** the linker writes no words, only `[`, `](url)`; no code text about an instrument is added, so none can
  contradict another.

## 5. Tests, the revert, the mutants, the suite

- **`tests/test_instrument_links.py`: 79 tests**, pass.
- **Revert** (`mutants.py`, on a scratch copy, never the worktree): the three product files back to `1889abb`,
  **276 lines removed** (0 restored): the new file fails at collection (it imports the new names); the seam's
  neighbouring files (`test_manager_siblings`, `test_rail_readmit`, `test_citation_links`, `test_paragraph_restore`,
  `test_rail_filter`, `test_rail_titles`: 232 tests) pass with and without the change. **Stub** (`link_named_instruments`
  returns the answer unchanged): 29 of 79 fail.
- **Single-site mutants: 58 of 58 caught** (control run first, 311 passed; every named test file asserted to exist):
  the instrument key (version tail, provision cut, shape check, regnal form, annex); `_below_instrument`; the nested
  link pattern, bare URLs, text order (twice); the title pattern (leading "the", apostrophe, lookbehind, lookahead,
  punctuation tokens); the mention (nameable title, longer-title head, SI number, old SI form, EU number, number
  boundary, masked spans, first not last, longest at one place); beside (window 99 and 101, all segments, unnameable
  kinds, number boundary); every guard (straight, curly, backtick, fence, line not whole text, bracket, emphasis);
  the planner (answer-linked, restored notes, scope blocks, trailing punctuation, lookup titles, URL keying, first
  instrument URL, one provision, B never to an unnamed provision, clashes, guarded mentions); the reverse-order
  application; fail-soft; `nameable_title` (length, bare id) and `heads_longer_title`; the wiring (removed,
  parliamentary gate, lookup titles, out of the conversational block, after P1.6 with the gates kept, before
  P3.13). Nine mutants survived the first two passes; each got a test (text order, lookbehind, lookahead, longest
  label, unnameable kind, provision number boundary, quote over the line not the text, fail-soft, and the P3.13
  order) before the final run. One wiring test I first wrote (a lost answer is left alone) was vacuous (the
  fallback is the reports, links intact, so the linker has nothing to do either way) and was removed.
- **Full suite** on `lexchat_test_d`: **3,458 passed** (3,379 + 79).

## 6. Pricing an acceptance (n=3, the sessions with the most links)

The row books a deterministic acceptance ("booked with the lever's measurement"); the dry run above is it. A paid
n=3 replay would show the wiring fire on fresh answers. Stored cost per run (`price423.py`, `price423b.py`):

| session | links (dry run) | stored runs carrying >= 1 | cost per run, mean / max | n=3 |
|---|---|---|---|---|
| 6409 (whole) | 27 | 10 of 16 whole runs | $0.94 / $1.46 | $2.82 / $4.38 |
| 6383 (whole) | 7 | 4 of 18 | $0.82 / $2.29 | $2.46 / $6.87 |
| 6406 (the 11-turn script) | 7 | 7 of 18 | $1.90 / $3.68 | $5.70 / $11.04 |
| 6338 (whole) | 6 | 5 of 14 | $0.36 / $0.59 | $1.08 / $1.77 |
| 6410 (whole) | 3 | 3 of 9 | $0.10 / $0.13 | $0.30 / $0.39 |

The top three by links (6409, 6383, 6406): **about $11 at the stored means, $22 at the stored maxima.** The top three
by the share of runs that carry a link at a low cost (6409, 6338, 6410): **about $4.20, $6.54 at the maxima.** The
figures are whole-session costs (6409's include its Deep Research turns); the 6406 row is its 11-turn script.
Prices are at the stored runs' costs on the pinned Gemini; per FIX_PLAN, price at the runaway case before running.

## 7. Commands

From the scratch folder `$S = docs/prepilot-fixes/evidence/seam/batch13/D/` (gitignored, `.gitignore:113`),
`R=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `PYTHONIOENCODING=utf-8`,
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`. Scripts import this worktree's `server_py` by
path: to re-run on the merged tree, repoint `WT` (do not edit in place).

| number | command |
|---|---|
| the dry run, 68 directories | `python dry423.py $R dry_all` |
| the dry run, the prototype's 64, completed reports only | `python dry423.py $R dry64c --completed-only --dirs64` (and `--no-lookup-titles`) |
| built against prototype | `python cmp423.py dry_all.list`; `python cmp_url.py dry_all.list` |
| class B in the mention's sentence | `python bsentence.py` |
| every subcommand before/after | `python graders423.py $R dry_all.list`; one in full: `... --show <dir> <sub>`; `rail --all`: `--show ALL rail` |
| every regex, R before/after | `python sweep423.py $R` |
| granularity | `python granularity.py dry_all.list`; `python granularity2.py` |
| URL shapes | `cd server_py && python ../docs/prepilot-fixes/evidence/seam/batch13/D/suffix_census.py` |
| price | `python price423.py dry_all.list`; `python price423b.py 6409,6406,6338,6383,6410` |
| revert and mutants | `python mutants.py` |
| suite | `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d python -m pytest -q` from `server_py/` |

## 8. What I did NOT do

- No replay, seam draw, model call or external call; no edit to any file rule 2 lists; no change to
  `paragraph_restore.py`, `replay_report.py` or any grader.
- No Deep Research or Research-mode linker (0 named-unlinked there in batch 12 D's measurement), no Thomas prompt rule.
- Not re-read: the 67 links identical to the prototype's (read in batch 12).

## 9. Decisions for the integrator and the user

**1. P4.23's acceptance: tick on this dry run, or pay for a replay?**
- **(a) Recommended:** tick on the deterministic dry run (the row books a deterministic acceptance): 79 links in 71
  turns, the prototype's 74 all reproduced and every new or moved one read, 0 grader verdicts moved, 58 of 58
  mutants; the next sweep re-graded as a regression check (`rail`, `summary`'s link counts).
- (b) Also replay 6409, 6338 and 6410 n=3 (about $4.20; $6.54 at the stored maxima) to see the wiring fire live.
- (c) Replay the three sessions with the most links, 6409, 6383 and 6406, n=3 (about $11; $22 at the maxima).

**2. Class B's "beside": the 100-character window, or the mention's own sentence?** 20 of the 23 class-B links name
the provision in the mention's sentence; 3 only in the window (6381 t3 and 6375 rep 1 t1 in `wave2_p24_smoke`, both
read in batch 12; 6338 rep 3 t1, new): the next sentence or the next list item names the provision.
- **(a) Recommended:** keep the window, as decided and hand-read (each names the provision the lawyer reads next).
- (b) The same sentence only: 76 links; the 3 become drops.

**3. The parliamentary bots.**
- **(a) Recommended:** off (as built, the same gate as lever R) until a parliamentary replay exists.
- (b) On for every bot, unmeasured.

**4. A restored note that links the instrument.**
- **(a) Recommended:** counts as the answer linking it, so the body's plain mention is not linked again (as built
  and as batch 12 D measured).
- (b) Link the body's mention as well; the note's link is code's, not the Manager's.

**5. `cmcdates`' "source named" flag reads a link's URL as naming legislation.gov.uk** (2 claims after the linker;
already true of any linked sentence before it; display only).
- **(a) Recommended:** leave it, recorded here; mask link URLs in `_CD_SOURCE_WORDS` the next time `cmcdates` is
  touched.
- (b) Fix it now (a one-line grader change, a separate commit by whoever owns `replay_report` this batch).

**6. The two additions beyond the prototype (lookup titles; titles as written):** +4 links, all read and right.
- **(a) Recommended:** keep.
- (b) Drop them for the prototype's exact rule (the 4 become unlinked mentions).

**Scratch:** the worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch13/D/`, copied with `cp -r` to the main
checkout's same path (counts in the reply). It holds the scripts, the `.out` files and the read files (`dry*.list`,
`graders423.out`, `rail_all.out`, `sweep423.out`, `mutants.stdout`), which quote answers and stay gitignored. This
note cites sessions by number and names no instrument.
