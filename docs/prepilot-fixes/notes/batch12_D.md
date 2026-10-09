# Batch 12, agent D: P4.3's lever R built, P4.23 and P4.24 measured, `lookup --routing` fixed ($0)

**Branch:** `worktree-agent-a4b3c8ac3bd05f62f`, based on `<INTEGRATOR_HEAD>` = `a99e4d4`. The worktree came
up on `main` (`a6b4a76`) with no commits of mine, so I ran `git reset --hard a99e4d4` first. No other
session's commit is in my base. **Spend $0**: no model call; **0 external calls** (0 LEX, 0
legislation.gov.uk, 0 National Archives, 0 SCTS, 0 OpenRouter). No server, no replay, no seam draw.
**Model:** every number comes from replays run on the pinned Gemini (`google/gemini-3.1-pro-preview`); none
is from `glm-5.2:cloud`. Nothing here depends on summarisation (every stored replay ran at the 8,000-character
fallback). **Counts include the two directories new since batch 11** (`wave4_b11_sweep`, `wave4_p331`): 64
post-P2.1 directories (all 66 but `baseline`, `wave1`), 1,853 answered turns rebuilt.

**Result in one line:** lever R measured first (prototype, then the built code, identical but for one false
re-admission the build removes): **P4.3 (iii) is 0 in every chat mode** (from 5 true removals under V4; batch
11 C's sixth was itself a false reference), with (i) and the re-booked (ii) unchanged and met. Built, with a
guard fix it needed and the `rail` grader changes it needs. `lookup --routing` fixed. P4.23 and P4.24
measured, not built. Decisions 1 to 6.

## 1. What I changed, function by function (the collision list asks for all of them)

**`server_py/src/agent/agent_core.py`:**
- `_source_is_used`: its token and name branches moved, unchanged, into the new `_source_is_named`; it now
  reads `excerpt or _source_is_named(...)`. Behaviour unchanged (the rail rebuild below is identical).
- **new** `_source_is_named(src, content)`: the keep test without the excerpt branch.
- `filter_worker_sources`: unchanged; followed by two **new** functions:
  - `retrieved_with_marks(source_accumulator, kept)`: every source a Worker run retrieved, private keys kept,
    each marked `_kept` (by identity, not equality), the accumulator not mutated;
  - `readmit_answer_sources(rail, retrieved, answer, research_mode)`: lever R (section 2).
- `run_worker_agent`: its source-filter block only; it now also sets `result["retrieved_sources"]`.
- `process_user_request`: a `retrieved_sources` list, extended after each `delegate_research`; R runs just
  before the source list is built, on `clean` (the answer before the scope footer).
- `run_deep_research`: the same, extended after each step; R runs on `_content` before the footer.
- `_build_step_brief` (agent B's) is untouched.

**`server_py/src/utils/source_naming.py`:** `_LONGER_TITLE` gains one alternative, `(commencement\b`, closed
or not (section 3).

**`server_py/tools/replay_report.py`** (`rail` and `lookup` only): `_RAIL_LONGER_TITLE` gains the same
alternative; `rail_turn` gains a `fallback` key (unvouched and not cited by the answer); `cmd_rail`'s fall-back
detector counts `fallback`, a new line counts answer-only sources, `--drops` labels them `ANSWER-ONLY`;
`_lookup_routing` reads each brief through `step_handover.without_handover_line`.

**Tests:** new `tests/test_rail_readmit.py` (29), new `tests/test_replay_lookup_routing.py` (4), 4 added to
`tests/test_replay_rail.py`.

**Where the built shape differs from the brief or the row (relay these):**
1. **R also needed the longer-title guard fixed** (section 3): without it, one stored answer quoting a
   truncated search query re-admits an Act it never cites. The fix is in the product's `source_naming` and
   in the `rail` reader alike.
2. **R is off on the parliamentary bots** (`_RAIL_FALLBACK_MODES`), as V4's change was: no stored replay ran
   on them (decision 4).
3. **R does not touch `sources_kept`** (the timing counter is recorded at the Worker seam, before R), so the
   fan-out denominator and Invariant 3's concern are unchanged by R itself; the rail (`audit.sources`) is what
   moves. R adds no text to any answer or block, so no detector screen applies (section 2.5).
4. **R adds bare-id-titled entries**: 437 of its 520 additions are change-record instruments titled with
   their id, which is P4.24's defect (section 6; decision 2).

## 2. P4.3 lever R

### 2.1 Measure first (the prototype)

`rb.py` rebuilds every stored answered turn's rail from its recorded raw tool results with a given tree's own
`_extract_sources_from_tool`, Worker-seam filter (against each report with the scope blocks stripped) and
`_is_duplicate_source` (batch 11 C's `rebuild.py`, extended). Three rebuilds: **pre-V4** (`024e396`, batch 11
C's `prev/`), **V4** (`a99e4d4`, `git archive`), and **V4 + R as a prototype** written from V4's own helpers
(a source retrieved this turn, not kept, whose instrument is not in the rail, that the answer, footer removed,
references by the keep test's token or name branch). `cmp_r.py` grades each against the pre-V4 rail with
`replay_report.rail_turn`. **Fidelity: the pre-V4 rebuild equals the stored rail (instrument-level set) on
1,852 of 1,853 answered turns**; every stored run predates V4, the two new directories included.

The prototype met the bar: (iii) 0 in every mode; 521 re-admitted, the reader agreeing on 521; the rail's
own noise unchanged. So I built it.

### 2.2 The hand-read: 1 of the 521 is false, and so was one of the six (iii) removals

I read all 35 non-Deep-Research re-admissions with every occurrence in the answer (`read_r.py`), and a seeded
sample of 40 of the 486 Deep Research ones (seed 12). **40 of 40 Deep Research and 34 of 35 others are real
namings**: SI numbers in lists, ids the synthesis copied from a step's scope block ("relations by another
instrument ... name ..."), a case linked by URL, an EU number, an Act linked by URL. **The one false re-admission**
is an Act (session 6409, `wave2_p22` rep 1 turn 7) whose title occurs in the answer only as the head of a
longer title, the third time inside a quoted, truncated search query whose parenthesis never closes
(in synthetic form, '"Widget Act 1901 (Commencement No. 1"'). The product's longer-title guard and the `rail` reader's both need a
closing parenthesis, so both read it as a naming. **That turn is also one of batch 11 C's six (iii) removals:
the true count under V4 was 5, not 6.**

### 2.3 The built code over every stored turn (`RB_R=built`, graded by the built `rail_turn`)

| report turns (post-P2.1, 64 dirs) | Conversational | Research | Deep Research |
|---|---|---|---|
| turns | 1,117 | 193 | 138 |
| **(iii)** answer-referenced sources gone from the rail, vs pre-V4: V4 / **V4+R** | 5 / **0** | 0 / **0** | 0 / **0** |
| retrieved this turn, the answer references it, not in the rail: V4 / V4+R | 11 / **0** | 23 / **0** | 444 / **0** |
| re-admitted by R (the reader agrees) | 11 (11) | 23 (23) | 444 (444) |
| rail sources: pre-V4 / V4 / V4+R | 2,641 / 2,077 / 2,088 | 655 / 724 / 747 | 1,190 / 1,296 / 1,740 |
| **(ii) re-booked**, unused by the answer with an excerpt (batch 11 C's category): V4+R | **170 / 2,088 (8.1%)** | 94 / 747 (12.6%) | 104 / 1,740 (6.0%) |
| no report and no answer references it: V4+R | 90 | 94 | 96 |
| reader-unused, all causes: V4+R | 333 (15.9%) | 94 (12.6%) | 116 (6.7%) |
| (i) fall-back delegations | 0 | 0 | 0 |
| report rails empty (P4.25): V4 / V4+R | 71 / 68 | 13 / 13 | 0 / 0 |

On failed turns R also re-admits 42 Deep Research sources (`report_mixed` 10, `no_report` 32), the reader
agreeing on all 42, and 0 elsewhere. **Built against prototype** (`built_vs_proto.py`): identical on 1,852 of
1,853 turns; the one difference is the false re-admission of 2.2, which the guard fix removes (521 to 520).
**The built rail without R equals V4's rail on 1,853 of 1,853 turns**, so the guard fix moves no Worker-seam
verdict. Re-run after removing three guards no input can bite (below): byte-identical (`cmp`).

**Checks:** (iii) 0 in each mode, passes. (i) 0, passes. (ii) as re-booked (the rail's own noise in
Conversational at or below 15%: 8.1%), passes. **P4.3's deterministic acceptance is met on the dry run.**

### 2.4 What R moves

- **Rails grow, mostly in Deep Research** (`r_sizes.py`): Conversational 11 turns gain 1 source each;
  Research 6 turns gain a median of 5 (max 6); **Deep Research 62 turns gain a median of 8 (max 18) on a rail
  of median 12**. 437 of the 520 additions carry a bare-id title (Deep Research 409 of 486), because a change
  record titles its instruments with their id (P4.24; decision 2).
- **The stored detector** would read every re-admitted source as unvouched (11 / 6 / 55 report turns flagged
  as fall-back). Hence the `rail` change (section 4): exempting answer-cited sources flags 0 turns on the
  built rails and the same 82 / 3 / 2 turns on the pre-V4 rails.
- **Not moved:** `sources_kept`, `source_filter_fallback`, the halt and lost reports' "N source(s) had been
  retrieved" (counted from the accumulator), any answer or block text.

### 2.5 Code texts beside it, and what I simplified

No prompt, tool result or lawyer-facing text names the rail (batch 11 C's grep, unchanged). R writes no text,
so the detector screens do not apply. The scope footer names searched instruments in code's words: R reads
the answer before the footer goes on, pinned by `test_the_manager_path_does_not_read_the_scope_footer` (a
mutant passing the footer in is caught). **`diagnose_suggestions`** (a log-only heuristic) reads
`has_sources` just above R, so a researched answer whose reports vouch for nothing can still read as a
clarifying question in the log; that is V4's, R does not change it, and I left the placement (not worth a
test of a log line). **Simplified before the mutants:** `readmit_answer_sources` first had an empty-answer
check, an empty-list check and a `_kept` skip; none can change an output (the name test fails on empty text,
an empty loop returns nothing, a kept source's instrument is in `rail_lids` and a kept case is a URL
duplicate), so a mutant could never catch them; removed.

## 3. The longer-title guard: an unclosed "(Commencement"

`guard_census.py`, the built V4 helpers: every legislation source each stored delegation retrieved, tested
by `title_named` against that delegation's report body and against the turn's answer, with the V4 guard and
with `(commencement\b` added. **53,768 title tests; 3 verdicts change, all in answers, none at the Worker
seam; all 3 read: the same truncated-search-query form (6409, `wave2_p22` reps 1 and 3), each a correct
change.** The `rail` reader got the same alternative: on the stored rails its verdict changes on 2 sources
(the same form), and nothing else (section 4).

## 4. The `rail` grader, on the stored rails (V4 head's grader against the built one)

`rail --all --exclude baseline,wave1 --drops`, both exit 1 (every stored directory predates V4, by design).
Every line that moves: Conversational reader-unused 1,100 to 1,102 (the 2 reader verdicts of section 3);
fall-back turns **82 / 3 / 2, unchanged** (87 in all); fall-back sources 845 to 840 and 877 to 872 (the 5
answer-cited ones, now on the new line "sources no report vouched for that the answer cites ... : 5", and
relabelled `ANSWER-ONLY` in `--drops`: exactly the 5 true (iii) cases); reader-only 580 to 579, token-only
16 to 17 (the same 2 verdicts). Nothing else. **Identity over all 66 directories** (`identity.py`, batch 11
C's, repointed: the 16 exit-1 graders, six others and `rail`, base `a99e4d4` against built): see section 9's
command; result in the addendum line at the end of this section.

## 5. `lookup --routing` reads each brief as the product routes it

Session 43's decision (batch 11 E's decision 6(a)). `routing_moves.py`: of 2,726 stored delegation briefs,
**9 carry the handover line, and all 9 move; each routes nothing once the line is excluded.** On each of the
9 the product made **0** `lookup_legislation` calls (`routing_check.py`), so the old grader overstated P3.7's
reach there by 3 to 5 ids a brief and the fixed one agrees with the product. Headline (`lookup --routing`
over all 66 directories): **419 to 410 routed briefs of 2,726; 16 to 15 sessions; 45 to 34 distinct ids.**
No brief without the line moves (by construction, and the census shows it). Check: passes.

## 6. P4.24 measured: bare-id and no-URL rail entries, and the made-under record

`p424.py` over every answered post-P2.1 turn. **Batch 10 C's figures reproduce on its 62 directories:** 808
bare-id-titled entries (its 807) and 438 with no URL (its 438). Every no-URL entry is also bare-id-titled.

| | stored rails (64 dirs) | built rails (V4 + R) |
|---|---|---|
| entries | 5,147 | 5,233 |
| bare-id title | 971 | **1,634** (437 of them re-admitted by R) |
| of which no URL | 577 | 590 |
| by series: ssi / uksi / asp / ukpga / eur / other | 428 / 81 / 112 / 108 / 242 / 0 | 699 / 241 / 199 / 245 / 240 / 10 |
| **a title from the same turn** (a search hit or a `lookup_legislation` result for the id) | 408 | 433 |
| else **the made-under record's title** (`made_under_instruments.title`) | 369 | **781** |
| else **an Act title the record resolved in a recital** (`powers[].act` by `act_id`) | 162 | 368 |
| none of these (EU 31, asp 12, Welsh 4, others 5) | 32 | 52 |

**Every SSI and UK SI bare-id entry has a title in the record: 509 of 509 stored, 940 of 940 built.** With
the same-turn titles and the record's Act titles, **1,582 of 1,634 built entries (96.8%) can be titled in code
without a call**; the 52 left are mostly EU instruments. The no-URL half needs no data: the id is the URL path
(`https://www.legislation.gov.uk/<id>`), which is P4.24's own lever. Observed, not measured further:
`_extract_sources_inner` has no branch for `lookup_legislation` or `find_instruments_made_under`, so an
instrument known only from a lookup or the made-under record never reaches the rail.

## 7. P4.23 measured: what a code linker would restore

`p423.py`, a prototype linker (scratch only, no product code) over every answered post-P2.1 turn with a
completed report: the instruments the completed reports link (scope blocks stripped) that the answer links
nowhere; whether the answer names each in words (the built `title_named`, longer-title guard included, or the
SI or EU number); and the answer's first plain-word mention outside any link, wrapped with the report's URL
verbatim.

| Conversational report turns (1,117) | |
|---|---|
| instruments the reports link / of which the answer links | 1,315 / 1,057 (80.4%) |
| dropped and not named in words (the proposition went too) | 130 |
| **dropped but named in words, linked nowhere** (batch 10 C: 110 on 62 directories) | **128** |
| of which the answer has a plain-word mention outside any link | 126 |
| A: the report has an instrument-level URL for it | 53 |
| B: the report has only provision URLs, and the answer names that provision beside the title | 19 |
| B: only provision URLs, the provision not named beside the title | 49 |
| the mention is inside a quotation or a code span (skipped) | 5 |

Research and Deep Research report turns: 0 named-unlinked (7 Deep Research instruments dropped, none named).
`report_mixed`: 3 Conversational, 2 Deep Research. **Variants, links in turns (`count423.py`, every
answered class):** A only, 54 in 50 turns; **A + B beside its provision, 74 in 67**; A + every B, 124 in 108
(+2 in 1 Deep Research turn).

**Read: all 114 proposed links of the first pass (110 on report turns, 4 on `report_mixed`), and of the
guarded pass every quoted, every "B beside its provision" and every EU-number row, and the one link the
nested-link mask moved.** With the guards below, every A and every "B beside its provision" link names the
right instrument at the right place. **What the read found, now
guards in the prototype:** (a) 5 mentions inside a quoted search term or a statutory quotation (a link there
would mislabel a search term, or render literally inside backticks); (b) a case-law link whose label holds
nested brackets ("[*X, Re Y Act 1901* [1902] EWHC 1](url)") is not matched by the product's `_MD_LINK`, so an
Act's title inside a case name read as a naming (the guarded pass masks such links, and the first mention
then falls on a real one); (c) **class B without its provision named links a whole-instrument mention to one
provision** ("The Act does not define X" linked to one section of it), which reads as a pinpoint the answer never made: the
row forbids a built instrument URL, so these 49 are either skipped or linked to the Act URL as P1.6's
demotion already does (decision 3); (d) the EU number form (16 links), absent from the first pass. The two
with no mention outside a link were not read further.

## 8. Tests, the revert, the mutants, the suite

- **Input forms no stored run contains, tested on synthetic input:** an unkept source whose instrument is in
  the rail under another URL (`http://.../id/` against `https://`); one instrument retrieved by two
  delegations; two cases with no id; the parliamentary modes; a retrieved entry that is not a dict (fail-soft);
  equal-but-distinct accumulator dicts (identity marking); "(Commencements ..." (the word boundary); a source
  named only in the scope footer.
- **Revert** (`mutants.py`, on a scratch copy, never the worktree): the three changed files back to `a99e4d4`,
  **124 lines removed** (7 restored). `test_rail_readmit.py` then fails at collection (it imports the new
  names); `test_replay_lookup_routing.py` 2 of 4 fail (the 2 that pass pin kept behaviour);
  `test_replay_rail.py` 4 of 24 fail (my 4); `test_rail_filter.py` 37 of 37 pass (V4, which R keeps).
- **Single-site mutants: 29 of 29 caught**, each by a failing test, none at collection (two regex mutants
  first failed at collection; I rewrote them well-formed and re-ran): R's parliamentary gate; `rail_lids` empty
  and built from every source; the seen-instrument guard and its fill; the URL dedupe against the rail and
  against its own output; the excerpt branch used instead; private keys kept; fail-soft removed;
  `retrieved_with_marks` by equality and mutating; `_source_is_used`'s excerpt branch and `_source_is_named`'s
  name branch; each wiring line (run_worker_agent, both collect lines, both extend lines, the footer read);
  the `(commencement` alternative and its `\b` (product and reader); the grader's `fallback`, answer-only
  tally, detector key, drops label; the routing read.
- **Full suite** on `lexchat_test_d`: **3,054 passed** (3,017 + 37).

## 9. Commands

From the scratch folder `$S = docs/prepilot-fixes/evidence/seam/batch12/D/` (gitignored, `.gitignore:113`),
`R=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `PYTHONIOENCODING=utf-8`. `prev/` is batch 11 C's
`024e396` copy, `v4/` is `git archive a99e4d4 server_py/src server_py/tools`. Scripts that import "the built
code" point at this worktree's `server_py` by path: to re-run on the merged tree, repoint (do not edit in place).

| number | command |
|---|---|
| rebuilds | `RB_SERVER_PY=$S/prev/server_py python rb.py $R rb_prev.jsonl`; `RB_SERVER_PY=$S/v4/server_py python rb.py $R rb_v4.jsonl`; `... RB_R=proto ... rb_v4proto.jsonl`; `RB_SERVER_PY=<worktree>/server_py RB_R=built python rb.py $R rb_built.jsonl` |
| the table of 2.3 | `GRADER_SERVER_PY=<worktree>/server_py python cmp_r.py $R rb_prev.jsonl rb_built.jsonl` (and `rb_v4.jsonl`) |
| built against prototype; rail without R against V4 | `python built_vs_proto.py rb_v4proto.jsonl rb_built.jsonl` |
| the hand-read | `python read_r.py $R rb_v4proto.jsonl nondr`; `... drsample:40:12` |
| R's growth | `python r_sizes.py` |
| the guard census | `python guard_census.py $R` |
| `rail` on the stored rails, both graders | `python -m tools.replay_report --dir $R rail --all --exclude baseline,wave1 --drops` from `$S/v4/server_py` and from the worktree's `server_py` |
| routing | `python -m tools.replay_report lookup --routing <66 dirs>` (both trees); `python routing_moves.py`; `python routing_check.py` |
| P4.24 | `python p424.py $R rb_built.jsonl` |
| P4.23 | `python p423.py $R rb_built.jsonl`; `python count423.py`; `python show423.py quoted|beside|notnamed|A|NOHIT` |
| revert and mutants | `python mutants.py` |
| identity | `python identity.py <worktree>` |
| suite | `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d python -m pytest -q` from `server_py/` |

## 10. What I did NOT do

- No P4.23 linker and no P4.24 title fill in product code: both measured only, as briefed.
- No client change (P4.25), no `stats.py` relabel, no change to the parliamentary bots' behaviour.
- Not read: the 2 P4.23 instruments with no mention outside a link; 446 of the 486 Deep Research
  re-admissions (40 sampled; the reader agrees on all 486).
- No replay, seam draw, model call or external call. No edit to any file rule 2 lists.

## 11. Decisions for the integrator and the user

**1. P4.3: tick it on this dry run?** (i) 0, (ii) as re-booked 8.1%, (iii) 0, all on the built code over
every stored post-P2.1 report turn; the row's acceptance is deterministic, n=1.
- **(a) Recommended:** tick P4.3 when R merges, with the next sweep re-graded on the same three as a regression
  check (as the row books), and `rail` joining the exit-1 set then (already decided).
- (b) Keep P4.3 `[~]` until a sweep runs on the merged code.

**2. R adds 437 bare-id-titled entries (Deep Research 409; a Deep Research rail gains a median of 8).**
- **(a) Recommended:** merge R together with P4.24's title fill (same-turn title, then the made-under record's
  title, then the record's Act title, and the URL from the id: 96.8% of built bare-id entries titled, no call),
  as one change; P4.24 built next by me or the next batch.
- (b) Merge R now; P4.24 follows.
- (c) Merge R for Conversational and Research only; the Deep Research half waits for P4.24.

**3. P4.23: which linker to build (measured, not built).**
- **(a) Recommended:** the instrument-level URL (A) plus a provision URL only where the answer names that
  provision beside the title: 74 links in 67 turns; never inside a quotation, a code span or a link (nested
  labels masked); P3.13's pattern, at the answer seam, after `restore_dropped_siblings`.
- (b) A only: 54 links in 50 turns.
- (c) (a) plus the 49 class-B mentions linked to the Act URL derived from the report's provision URL, as P1.6's
  demotion does: 124 in 108 turns; a built URL, which the row's lever excludes.
- (d) Thomas's prompt rule instead (about $3.25 for a seam A/B once its tooling gaps close).

**4. R on the parliamentary bots.**
- **(a) Recommended:** off (as built), with V4's fall-back, until a parliamentary replay exists.
- (b) On for one rule across bots, unmeasured.

**5. The longer-title guard's new "(Commencement" alternative (product and reader).**
- **(a) Recommended:** keep (as built): 3 stored verdicts move, all answers, all correct; 0 at the Worker seam.
- (b) Drop it and accept the one false re-admission.

**6. The two rail-source routes that do not exist** (`lookup_legislation`, `find_instruments_made_under` add
no rail source).
- **(a) Recommended:** a new P3 row to measure how often an answer cites an instrument known only from a
  lookup or the made-under record, before any build.
- (b) Fold into P4.24.
- (c) Leave it.

**Scratch:** the worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch12/D/`, copied with `cp -r` to
the main checkout's same path (counts in the reply). It holds the scripts, the rebuilds, the `.out` files and
the read files (`read_r_*.txt`, `p423.list`, `p424.list`, `rb_*.list`, `guard_census.list`), which quote
answers and stay gitignored. This note cites sessions by number and names no instrument.
