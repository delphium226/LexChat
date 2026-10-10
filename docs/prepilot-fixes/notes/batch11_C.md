# Batch 11, agent C: P4.3 built (V4 at the Worker seam) and the `replay_report rail` grader ($0)

**Branch:** `worktree-agent-a7664938b0d307c28`, based on `<INTEGRATOR_HEAD>` = `024e396`. The worktree came up
on `main` (`a6b4a76`) with no commits of mine, so I ran `git reset --hard 024e396` first. No other session's
commit is in my base. **Spend $0**: no model call, no external call of any kind (0 LEX, 0 National Archives,
0 OpenRouter, 0 SCTS). No server, no replay, no seam draw. **Model:** every number comes from replays run on
the pinned Gemini (`google/gemini-3.1-pro-preview`); none is from `glm-5.2:cloud`. Every stored replay was
summarised at the 8,000-character fallback; nothing here depends on summarisation.

**Result in one line:** built as briefed and dry-run with the built code over every stored post-P2.1 report
turn: **(i) met** (0 fall-back rails, from 90 turns); **(ii) not met in Conversational** (16.1%, from 42.1%;
Research 13.0%, Deep Research 10.2%); **(iii) not met** (6 sources the answer names leave the rail, all from
the conversation history or the code scope block, none named by the Worker's report). Decisions 1 and 2.

## 1. What I built, and where the built shape differs from the brief

**Product.** Functions changed in `server_py/src/agent/agent_core.py` (the collision list asks for all of them):
- `_source_is_used`: tokens are now boundary-aware (`token_in`); a legislation source's `sub` is no longer a
  token (a case's `sub`, its neutral citation, and the parliamentary kinds' `sub` stay); a source the text
  names in words is kept (`named_in`). The excerpt branch is unchanged.
- **new** `filter_worker_sources(source_accumulator, content, research_mode) -> (kept, kept_nothing)` and the
  constant `_RAIL_FALLBACK_MODES`.
- `run_worker_agent`: only its source-filter block (it now calls `filter_worker_sources`) and the P2.2 comment
  on the scope block's ordering (it named `turns_source_fallback`; it now names the timing counter).
- one import line (`from ..utils.source_naming import is_legislation, named_in, token_in`), placed between the
  `search_scope` and `suggestions` imports.

New module `server_py/src/utils/source_naming.py` (`token_in`, `norm_text`, `norm_title`, `title_named`,
`named_in`, `is_legislation`, the case-appeal guard `_names_other_judgment`, the number forms `_number_named`).
Nothing else under `server_py/src` changed (no prompt, no tool result, no lawyer-facing text, no stored shape).

**Where the built shape differs from the brief (relay these):**
1. **The fall-back is dropped on the legislation bot only.** `parliamentary_records` and `westminster_records`
   keep it: no stored replay ran on either bot, so dropping theirs would be unmeasured (decision 3).
2. **Two guards the brief did not list, both found by validating the keep test against the reader:**
   - every token must stand alone. An id that prefixes another (`ssi/1901/3` in `ssi/1901/31`) has 0 stored
     cases, but **a neutral citation that prefixes another does**: "[YYYY] EAT 1" inside "[YYYY] EAT 12" read
     as cited for 10 stored post-P2.1 rail entries, by the old token test and by batch 10 C's reader alike;
   - **a case named by its parties is not the source when the same sentence cites another judgment of those
     parties.** The Worker is nudged (A2) to cite the appeal; its first-instance search hit shares the title.
     50 of the 52 case-title keeps on stored reports were this, every one read (section 4).
3. **The EU number is "N/YYYY" only, as briefed.** Of 500 stored EU sources from 2015 on, 0 reports write the
   post-2015 "YYYY/N" form without "N/YYYY" (`forms_census.py`), so it was not added.
4. **`source_filter_fallback` keeps its trigger**: it is set when the Worker-seam filter keeps nothing, as
   before, though the rail no longer falls back. So the Efficiency tab's "Source-filter fallback rate" and its
   breach line ("answer cited no retrieved source") keep counting the same condition; only the label is now a
   misnomer on the legislation bot (decision 4).

**Tooling (`server_py/tools/replay_report.py`, mine alone this batch):**
- new subcommand **`rail`** (`--all`, `--exclude`, `--drops`, `--chars`): per chat mode, report turns' rail
  sources, the reader-unused count and rate, the token test's count, the fall-back turns (a report turn holding a
  source with no excerpt that no completed report references, by the reader or the token test), the turns citing
  none, the detector against the product's own counter, and the bar. **Exit 1** if any fall-back turn or any
  chat mode's rate is over 15% (inclusive bar: 15.0% passes). It is not in the exit-1 set (decision 6).
- the reader is batch 10 C's `reader.py` ported verbatim (`rail_reader`) **but for three fixes**, each found by
  validating it against the built keep test: a neutral citation or bare id must not run on into a longer one
  (`_rail_ends_clear`); a regnal-year id has four segments (`ukpga/edw7/1/3`; read as three, every Act of one
  session "cited" every other); a case's parties followed by another judgment's citation name that judgment
  (`_rail_case_title_named`). It shares no code with the product's keep test, deliberately.
- the old counters are relabelled as the token test's: the `summary` totals lines, `compare`'s two rows, the
  `baseline` note, the `RunSignals` comments and `_source_cited`'s docstring (it mirrors the token test as it was
  before P4.3, kept unchanged so stored counts stay comparable). **`turns_source_fallback`'s meaning change** is
  stated at the field and at the counting site: it counted the fall-back before P4.3 and now counts only rails
  the answer cites by no token; `rail` grades the fall-back. Keys (`src_unused`, `src_fallbk`) are unchanged.

## 2. The acceptance, dry-run with the built code ($0, n=1, deterministic)

**Method.** `rebuild.py` rebuilds every answered turn's rail from its recorded raw tool results with a given
`server_py`'s own `_extract_sources_from_tool`, Worker-seam filter (against the report with the scope blocks
stripped, the text the product filters on) and `_is_duplicate_source`; once with the integrator head's code
(`git archive 024e396`, `prev/`) and once with the built code. `compare_v4.py` grades both with the BUILT
`replay_report.rail_turn`. Identity is instrument-level (the legislation id, else the URL), because the rail
dedupes on the exact URL string and a change record's `http://.../id/...` URL and a search hit's `https://`
URL for one instrument are two strings. **Fidelity: the base rebuild equals the stored rail on 1,407 of 1,407
post-P2.1 report turns** (as a set). Scope: 62 directories (all 64 but `baseline` and `wave1`, pre-P2.1),
434 run files, including `wave4_b10_sweep`.

| report turns (post-P2.1) | Conversational | Research | Deep Research |
|---|---|---|---|
| turns | 1,087 | 193 | 127 |
| **(i)** delegations falling back to all: before / after | 86 / **0** | 3 / **0** | 2 / **0** |
| (i) turns with a fall-back delegation, before | 85 | 3 | 2 |
| (i) `rail` detector's fall-back turns: before / after | 82 / **0** | 3 / **0** | 2 / **0** |
| **(ii)** reader-unused, before | 1,092 / 2,593 (42.1%) | 109 / 655 (16.6%) | 130 / 1,078 (12.1%) |
| **(ii)** reader-unused, after | **325 / 2,022 (16.1%)** | **94 / 724 (13.0%)** | **116 / 1,139 (10.2%)** |
| sources removed / added | 853 / 282 | 15 / 84 | 18 / 72 |
| added that the answer references | 202 | 84 | 68 |
| **(iii)** removed that the answer references | **6** | 0 | 0 |
| rails emptied | 65 | 3 | 0 |
| turns whose rail moves | 291 | 49 | 31 |
| retrieved this turn, the answer references it, not in the rail: before / after | 208 / 12 | 107 / 23 | 475 / 408 |

`wave4_*` alone (`compare_v4.py <R> wave4_`): Conversational 435 / 1,385 (31.4%) to 213 / 1,274 (16.7%);
Research 0 / 35 to 0 / 44; Deep Research 34 / 381 (8.9%) to 35 / 394 (8.9%); 5 of the 6 (iii) removals.

**(i) MET.** Check: 0 delegations take the fall-back and `rail`'s detector finds 0 fall-back turns in the
built rails, from 91 delegations on 90 turns (the product counter's 90) and 87 detector turns.

**(ii) NOT MET in Conversational (16.1% against 15%); met in Research and Deep Research.** Why it misses: V4
**adds** sources, which batch 10 C's estimate (14%) could not see, because it intersected V4 with the stored
rail. A source the report names in words that the old token test missed is now kept even where the old filter
kept something else: 282 in Conversational, of which the answer references 202 (a gain) and 80 not. The 325
unused after: 164 retrieved (excerpt) and not mentioned by the answer; 81 the report cites by token and the
answer drops; 80 the report names in words and the answer drops. **161 of the 325 are the conversational
Manager dropping what its Worker vouched for**, which is P4.23's defect, not the rail's. Measured variants (from
the built helpers, not built product code; `RB_VARIANT`):
- *narrow* (the name test only where the token test keeps nothing; no additions): 245 / 1,740 (14.1%),
  94 / 640 (14.7%), 112 / 1,060 (10.6%), the same 6 (iii) removals, and the rail misses 796 answer-referenced
  retrieved sources (the base's 790), against the built V4's 443;
- *noexcerpt* (V4, and an excerpt alone no longer keeps a source): 236 / 1,928 (12.2%), 0 / 630, 16 / 1,034,
  but 14 (iii) removals.

**(iii) NOT MET: 6 sources the answer references leave the rail**, all Conversational, on 6373 (4 turns, one
SSI) and 6409 (2 turns, the Act). Every one read (`why_removed.py`, `where_named.py`): the Worker's report body
never names the instrument (no token, no title, no number); the answer names it because earlier turns' answers
linked it (the history) or because the code scope block appended to the report lists it ("Relations by another
instrument were retrieved and name ..."). Before V4 each was in the rail only by the fall-back. A prototype
(**R**, not built: at the answer seam, re-admit a source this turn retrieved that the ANSWER references by the
built keep test) takes (iii) to 0 and re-admits 12 / 23 / 408 sources, every one of which the reader agrees
the answer references (decision 2). It needs code in `process_user_request` and `run_deep_research`, which
are B's and E's files this batch.

**Also moved (watch items):**
- **Failed turns (P4.5's watch):** `report_mixed` Conversational 8 turns move (15 removed, 13 added, 0 removed
  that the answer references); Deep Research 11 (70 removed, 29 added, 0); `no_report` 0.
- **The fan-out denominator (`sources_kept`; P3.10's acceptance reads it):** non-DR sum 3,545 to 3,037, Deep
  Research 2,487 to 2,572; fan-out breaches 12 to 11; mean phase-2 per kept source 0.862 to 0.794
  (`fanout.py`; the base rebuild's kept count equals the stored `sources_kept` on 1,784 of 1,785 turns).
- **6378 (the regression check):** none of its turns is among the (iii) removals; its SSI stays in the rail
  wherever the answer names it. The check itself reads the answer body, which V4 does not touch.

## 3. Tests: the forms, the revert, the mutants

`server_py/tests/test_rail_filter.py` (37, the product seam) and `server_py/tests/test_replay_rail.py` (20, the
grader). Every input form in `notes/batch10_C.md` section 4 has a synthetic test ("Widget Order 1901",
`ssi/1901/3`, "Widget Co v Example Ltd"):

| form | stored post-P2.1 cases (`forms_census.py`, `keep_vs_reader.py`) | test |
|---|---|---|
| an id that prefixes another | 0 legislation; 13 neutral citations | `test_an_id_that_prefixes_another...`, `..._neutral_citation_that_prefixes...` |
| a short form ("the 1901 Act") | 21 candidates (batch 10 C) | `test_a_short_form_is_not_a_naming` |
| a case by party name alone | 2 (ambiguous between two judgments of one pair) | `test_a_case_named_by_its_parties_alone_is_kept`, the appeal tests |
| a Welsh title | 33 sources, 1 named in its report | `test_a_welsh_title_is_named_and_not_as_the_head...` |
| a comma before the year | present | `test_a_comma_before_the_year_still_names_the_title` |
| SI "YYYY/N", EU "N/YYYY", old SI "YYYY No. N" | 419 keeps by SI number, 0 by EU number; 4 rail entries whose id is a printed old-SI number | `test_an_si_number...`, `test_an_eu_number...`, `test_an_old_si...` (2) |
| a title inside a longer title | present | `test_a_title_inside_a_longer_title...`, `test_each_instrument_word...` |

**Revert** (`mutants.py`, on a scratch copy, never the worktree): 657 lines removed (54 added lines of
`agent_core.py`, 397 of `replay_report.py`, `source_naming.py`'s 206 deleted). The product file then fails at
collection (it imports the new names); the grader file fails 20 of 20. So the product tests were also run
against the **old behaviour with the new names stubbed** (the old `_source_is_used`, a `filter_worker_sources`
that re-states the old fall-back): **20 of 37 fail**; the 17 that pass test the new helpers directly or pin
behaviour the change keeps (the excerpt branch, a case's and a parliamentary `sub`, the parliamentary fall-back).

**Single-site mutants: 70, all caught** (`mutants.out`), one for every guard and cleaning step: the 6- and
8-character floors, both boundary sides, the side test, the empty-text guards, each `norm_text` step (lower case,
each curly quote, commas, emphasis, space collapse, line breaks kept), the leading "the", the bare-id exclusion,
the title boundary, the longer-title guard and its year and "scheme" alternatives, the case lookahead (its
sentence stops, its 100-character length, its URL branch, both own-citation-missing branches, cases not getting
the legislation guard), every number-form lookbehind and lookahead, the SI-type check, the old-SI path and its
cite fallback, `is_legislation`'s kind branch, the excerpt branch, the `sub` choice both ways, the old substring
test, the fall-back both ways, the list copy, both wiring lines in `run_worker_agent`, and the grader's three
fixes, sentence stops, bar edge, fall-back fail, unvouched conditions, scope-block and footer stripping, turn
classes, `--exclude` and `--drops`. **The first run left 6 survivors and 3 bad anchors**; I added tests for the
6 (None text in `token_in` and `named_in`, emphasis inside a title, a leading "the", the lookahead length as a
literal, a case with no URL of its own) and removed one step that could not fail: `norm_text`'s hard-space
replace, which `_SPACES` already covered.

**Full suite** on `lexchat_test_c`: **2890 passed** (2833 + 57).

## 4. The grader, validated both ways

- **Port against batch 10 C's census** (`port_identity.py`, every source of every turn, all 64 directories):
  turn classes 2,172 of 2,172 identical; reader verdicts 7,283 of 7,298 identical. The 15 that move are the two
  intended fixes: 13 neutral citations running on into a longer one (10 post-P2.1; 9 windows read, the rest are
  run-ons by construction), 2 case titles followed by the appeal's citation (both pre-P2.1). The regnal fix moves
  no answer-level verdict.
- **The built keep test against the reader, on the same report text** (`keep_vs_reader.py`): 35,341 non-excerpt
  accumulator sources: token keep and reader agree 549, name keep and reader agree 600 (181 by title, 419 by
  SI number), both no 34,192, **0 disagreements** (36 before the regnal fix, every one the reader wrong). They
  share their method, so I also read: a seeded sample of 35 name keeps taken before the appeal guard (20 title,
  15 SI number; every legislation one a real naming, 2 needing the occurrence the guard accepted, not the first;
  the case ones led to the next item); and all 52 case-title keeps, which is how the appeal guard was found (50
  were the other judgment; 2 name the parties with no citation, ambiguous between two judgments, kept).
- **On the stored rails** (`rail --all --exclude baseline,wave1 --drops`): the token test's disagreements with
  the reader, **all 16 token-only read**: 6 a section heading (`sub`) and 10 a neutral citation running on, every
  one a false "cited". **Reader-only 524** (url 243, title 174, eu-number 65, si-number 40, id-text 2): a seeded
  sample of 22 read, 21 real references, 1 a prose list of searched ids in an answer (arguably not a citation).
- **The fall-back detector against the product's counter** on stored report turns: both 87, counter only 3,
  detector only 0, neither 1,306. The 3 are fall-back rails whose every source the report names by SI number
  (`counter_only.py`): no source on them is unvouched, and V4 keeps all of them.
- **`rail` on the stored post-P2.1 rails** (the before column, from the grader): Conversational 1,093 / 2,594
  (42.1%), Research 109 / 655 (16.6%), Deep Research 130 / 1,078 (12.1%); 87 fall-back turns (877 sources);
  token test 1,840 / 4,327 (43%); exit 1.

## 5. The identity run (16 exit-1 graders and 6 others, all 64 directories, base against built)

`identity.py` (batch 10 E's, repointed: the base is `replay_report.py` at `024e396`, run from a scratch copy so
its imports resolve; the built one is this worktree's): the 16 exit-1 graders, `negcurrency --drops`, `corpus`,
`commencements --drops --answers`, `authorities` (rubric `p322.json`), `summary` and `baseline`, over all 64
directories: **1,288 identical, 120 differ, 0 of them in the exit-1 set** and 0 in the four other graders.
The 120 are `summary` (64) and `baseline` (56): every changed line is a relabelled one ("consulted-not-cited
by the token test", "turns citing NONE of their sources by the token test (the rail fallback before P4.3)",
"unused sources (token test)"), with **every count on it unchanged and no line added or removed**
(`moves_check.py`: 120 pairs, 0 other differences). Only the intended moves. Check: passes.

## 6. Other checks

**An empty rail renders** (the client has no test runner; I read `client/src/App.jsx` and
`components/SourcesRail.jsx`, `ChatMessage.jsx`). A reply with no `sources` gets no "Sources (N)" button
(`sourcesCount > 0`). The rail shows `activeSources`: the explicitly selected message's sources, else **the
latest earlier assistant message that has sources**, and that earlier message's button is highlighted
(`latestSourceMsgId`). Only when no message in the chat has sources does it show "No sources yet" and "Sources
will appear here as the research agent cites legislation and case law." So a turn whose rail V4 empties shows
the previous turn's sources, highlighted against the previous answer, as a no-delegation turn already does.
V4 adds 68 such report turns in the stored set (decision 5). Nothing crashes on an empty list.

**Code texts beside the change.** No prompt, tool result or lawyer-facing text names the rail (grep of `src`).
The halt and lost reports say "N source(s) had been retrieved": agent-facing, counted from the accumulator,
unchanged. `worker_scope_block` still lists the instruments section-searched and is still appended after the
filter, so it cannot vouch for a source (pinned by `test_the_block_does_not_mark_a_source_as_cited`, which
passes). No new product wording, so no detector screen applies.

## 7. What I did NOT do

- No answer-seam change (R), no client change, no change to `stats.py`'s label: each is outside my files.
- No replay, seam draw or model call; no live call. No change to the parliamentary bots' behaviour.
- I did not read every one of the 853 + 15 + 18 removed or 438 added sources: the keep test agrees with the
  reader on all of them, and the samples read and what each showed are in section 4. The moved turns are listed
  in the gitignored `v4_moves.tsv` (390 turns, ids and keys only).
- I did not edit FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md or any file rule 2 lists.

## 8. Decisions for the integrator and the user

**1. P4.3's bar (ii) in Conversational (built V4: 16.1%; Research 13.0%, Deep Research 10.2%).**
- **(a) Recommended:** keep V4 as built and re-book (ii) for Conversational at the share of rail sources no
  completed report vouches for and no answer references (the rail's own noise: the 164 retrieved-but-unmentioned,
  8.1%), with the 161 the Manager drops counted under P4.23. The additions put 354 answer-referenced sources into
  rails that lacked them.
- (b) Build the *narrow* variant instead: 14.1% meets the bar as booked, but the rail keeps missing 796
  answer-referenced sources it retrieved (V4: 443).
- (c) Keep the bar and reach it by also dropping excerpt-only sources (12.2%), at 14 (iii) removals.
- (d) Keep the bar as booked and leave P4.3 open on 16.1%.

**2. Bar (iii): 6 answer-named sources leave the rail (all named only by the history or the code scope block).**
- **(a) Recommended:** build R next (after B's and E's merges, since it touches `process_user_request` and
  `run_deep_research`): re-admit a source this turn retrieved when the answer references it. (iii) goes to 0
  and the answer-referenced sources missing from the rail go from 443 to 0, including 408 in Deep Research.
- (b) Re-book (iii) to count only sources the turn's Worker reports name, with these 6 listed as its known
  exceptions, and book R as a new row.
- (c) Accept the 6 and close (iii) as met in spirit.

**3. The parliamentary bots' fall-back.**
- **(a) Recommended:** keep it (as built) until a parliamentary replay exists to measure the change on.
- (b) Drop it there too, unmeasured, for one rule across bots.

**4. `source_filter_fallback` and the Efficiency tab.**
- **(a) Recommended:** keep the trigger (as built) and relabel the KPI and breach text in `stats.py` and
  `config.py` to "the Worker vouched for none of its sources" in a later change.
- (b) Record the literal fall-back instead: the KPI reads 0 forever on the legislation bot and the breach stops.

**5. A turn whose rail is emptied shows the previous turn's sources (client behaviour, 68 more report turns).**
- **(a) Recommended:** a new P3 row for the client: show "This answer cites no source" for the selected turn
  rather than an earlier turn's list; until then a watch item on P4.3.
- (b) Leave it: it is the existing behaviour for every turn with no delegation.

**6. `rail` and the exit-1 set.**
- **(a) Recommended:** add it after the next sweep re-grades on the merged code (every stored directory before
  V4 exits 1, by design).
- (b) Add it now and record the known exits.

**7. The Deep Research rail misses 408 instruments the synthesis names (before V4: 475).** They are retrieved
(mostly change-record instruments the scope block lists) but no step report names them.
- **(a) Recommended:** fold into decision 2's R, which re-admits them.
- (b) A new row on its own.

## 9. Commands

From the scratch folder `$C = docs/prepilot-fixes/evidence/seam/batch11/C/` (copied to the main checkout),
`R=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `PYTHONIOENCODING=utf-8`. The scripts import this
worktree's `server_py` and assert it; to re-run on the merged tree set `P43_SERVER_PY` (and `RB_SERVER_PY` for
`rebuild.py`) to `C:/Projects/LexChat/server_py`; do not edit them. `prev/` is `git archive 024e396 server_py/src
server_py/tools`, untarred.

| number | command |
|---|---|
| stored before-column, the bar, the detector against the counter | `python -m tools.replay_report --dir $R rail --all --exclude baseline,wave1 [--drops]` (from `server_py/`) |
| port identity (7,283 / 7,298; 15 intended moves) | `python port_identity.py $R` |
| counter-only fall-back turns (3) | `python counter_only.py $R` |
| keep test against reader (0 disagreements; named keeps) | `python keep_vs_reader.py $R` |
| base and built rebuilds | `RB_SERVER_PY=$C/prev/server_py python rebuild.py $R rebuilt_base.jsonl`; `RB_SERVER_PY=<worktree>/server_py python rebuild.py $R rebuilt_built.jsonl` |
| the acceptance table, R, the moves list | `python compare_v4.py $R` (`$R wave4_` for the slice) |
| variants | `RB_VARIANT=narrow|noexcerpt RB_SERVER_PY=<worktree>/server_py python rebuild.py $R rebuilt_<v>.jsonl`, then `AFTER=rebuilt_<v>.jsonl python compare_v4.py $R` |
| the six (iii) removals, read | `python why_removed.py $R compare_v4.out`; `python where_named.py $R <dir> <file> <turn> <id>` |
| fan-out denominator | `python fanout.py $R` |
| stored input forms | `python forms_census.py $R` |
| token-only and reader-only reads | `python token_only.py $R rail_stored_post21_drops.out`; `python sample_reader_only.py $R rail_stored_post21_drops.out 43` |
| revert and 70 mutants | `python mutants.py` |
| identity (base against built graders) | `python identity.py <worktree>`, then `python moves_check.py` |
| suite | `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c python -m pytest -q` (from `server_py/`): **2890 passed** |

**Scratch:** the worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch11/C/` (`git check-ignore -v`
gives `.gitignore:113`), copied with `cp -r` to the main checkout's same path. It holds the scripts, the rebuilds,
the `.out` files, `v4_moves*.tsv`, and the read files (`why_removed.out`, `where_named.out`, `named_keeps.txt`,
`named_sample.txt`, `sample_reader_only.txt`, `keep_vs_reader_list.txt`), which quote answers and reports and stay
gitignored. No matter text is in this note: sessions are cited by number, instruments not at all.
