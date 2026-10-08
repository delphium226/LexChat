# Batch 10, agent C: P4.3 measured and re-booked ($0, no product code)

**Branch:** `worktree-agent-aa8f83b2a0df5d6d5`, based on `<INTEGRATOR_HEAD>` = `7c3c6ac`. The worktree
came up on `main` (`a6b4a76`) with no commits of mine, so I ran `git reset --hard 7c3c6ac` first.
**Nothing under `server_py/` changed.** This note is the only committed file. **Spend $0**: no model
call, no external call of any kind (0 LEX, 0 National Archives, 0 OpenRouter). `seam_replay manager
--dry-run` was run to size payloads; it builds the payload and returns before any model call.
**Model:** every number below comes from replays run on the pinned Gemini
(`google/gemini-3.1-pro-preview`, summariser `google/gemini-3-flash-preview`), the model of all 63
directories. None is from Thomas's `glm-5.2:cloud`.

## 1. What I found, in short

1. **The unused-source rate is mostly one line of code, not the model declining to cite.** When the
   Worker-seam filter (`run_worker_agent`, the `_source_is_used` list comprehension) keeps nothing, it
   falls back to the WHOLE accumulator: every Phase-1 search hit goes into the rail. The product's
   own counter (`timing.source_filter_fallback`) is set on **90 of 1,393 post-P2.1 report turns
   (6%)**, and those 90 turns hold **879 of the 1,321 unused sources (67%)**. Without them, the rate
   is **442 of 3,394 (13%)**. Over `wave4_*` alone it is 34 of 713 turns holding 271 of 458 (59%).
   Without them the rate is 187 of 1,505 (12%). The fall-back turns are negatives and "not held"
   answers where the Worker cites nothing by URL or id: 6409 (43 turns) and 6373 (35), then 6383 (3),
   6343 and 6410 (2 each), and 6350, 6357, 6372, 6408 and 6340 (1 each).
2. **The stored grader overstates the rate.** `replay_report`'s `src_unused`
   (`_source_cited`) counts 1,838 of 4,320 post-P2.1 report-turn sources as uncited. A careful-reader
   test counts 1,321. The 293 sources in the gap are linked in the answer by URL. The grader misses
   them because the audit strips `_lid`, and a section search rewrites `cite` from the bare id to
   "Title, s.N". **The grader reproduces BASELINE.md's B8 split exactly** (57 turns, 622 sources, 489
   uncited, 9 citing none, on `baseline`'s 41 files at `0884b29`), so the 79% there was this grader's
   number, with this bias.
3. **The built `_source_is_used`, used as an answer-seam "consulted, not cited" flag, would mislabel
   28% of what it flags** (520 of 1,832). There are three reasons. At the answer seam it never sees
   `_lid`, because `run_worker_agent` drops `_`-keys before the Manager's accumulator. It has no title
   test. And its `sub` token (a section heading) marks unrelated sources as cited: all 6 of its
   "cited" verdicts that a reader would refuse are this case, 5 of them read.
4. **The Manager's link drop is a conversational-mode effect, and mostly whole propositions.** The
   research Manager keeps 869 of 869 distinct report legislation URLs, and the Deep Research synthesis
   1,189 of 1,214. The conversational Manager keeps **1,416 of 1,828 (77%) post-P2.1** and **900 of
   1,112 (81%) over `wave4_*`**; per turn the median is 1.00. Of the 412 URLs it drops, at most 84 are
   provisions the answer still names in words (an upper bound: 1 of 3 spot-checked was real). At
   instrument level, **110 instruments (29 over `wave4_*`, all 29 read and all real)** are named in the
   answer in words and linked nowhere, although the report linked them. Those are Thomas's "retained
   proposition without its URL".
5. **6378's P4.3 shape occurs 0 times since `wave2`.** The row's SSI reaches the answer body in 17 of
   19 answered post-P2.1 turns (by id, or by title in 1). The 2 misses are not this row's defect. One
   is a P4.5 lost-reply turn, disclosed as lost. In the other the Worker never retrieved the
   instrument, and the rail does not carry it either.
6. **The levers, dry-run with the built code.** Dropping the fall-back (V1) takes the conversational
   unused rate from 42% to 14%, and the `wave4_*` rate from 31% to 14%. It also removes 31 sources
   the answer names in words, on 18 turns. Keeping a source the REPORT names in words (V4, an estimate,
   not built code) gives the same rate with 6 such removals. An answer-seam filter (V2) is unusable:
   half of what it removes, the answer names.

The brief's shape matched: no deviation in what I was asked to build, because nothing was built.

## 2. Method

**Directories.** All 63, 539 run files. **Pre-P2.1, excluded from every rate:** `baseline` (65 files,
heads `0884b29` and `bc8e7a4`; `git merge-base --is-ancestor 4d3f4c1 <head>` exits 1 for both) and
`wave1` (41 files, head `6a5eeea`, which is not in this repository's history; it is P1.5's sweep of
2026-09-15, before P2.1's `4d3f4c1`). **Post-P2.1:** 61 directories, 433 files (`223293e`,
`2d9ae11` and `fdb2f3c` checked as descendants of `4d3f4c1`). `wave2_p21` records `7a1c79b`, but P2.1
was loaded (SESSION_LOG, Session 6 provenance note), so it is included. The post-P2.1 pool spans
many revisions, so I also give `wave4_*` (28 directories) as the slice closest to HEAD.

**Turn classes (post-P2.1).** A *report turn* is answered (status not error or clarification,
non-empty answer), has at least one delegation, and EVERY delegation completed: no halt, no lost
reply, no error, and a non-empty report. There are 1,404 report turns, 1,393 of them with sources.
The other classes: 58 mixed (some delegation halted or lost), 23 no report, 292 with no delegation,
13 unanswered. Chat mode is the audit's `chat_mode` (what the server ran). Research type is the
turn's, then the audit's, then the run filter's.

**Answer body.** `replay_report._without_footer` (the code scope line). For the Manager-link measure,
P3.13's code-written "Also in s.N" notes are also removed.

**Three verdicts per rail source:**
- **grader** = `replay_report._source_cited` (the stored `src_unused`);
- **built** = `agent_core._source_is_used` with the excerpt branch off and `_lid` restored from the
  URL (the product's token test, as a rail flag would run it if `_lid` were carried);
- **reader** = a careful-reader stand-in, which I hand-validated. It finds the instrument's id in
  any legislation URL in the answer (an exact id, so no prefix collision), its title (normalised; not
  as the head of a longer instrument title such as "... Act 2025 (Commencement No. 1) Regulations"),
  its SI number ("YYYY/N"), its EU number ("N/YYYY") or the old-SI form "YYYY No. N"; for a case, its
  URL, neutral citation or full title.

**Validating the reader (every disagreement class read, by sampling):**
- product says cited, reader says not: 12 read before the fixes. Three reader gaps were fixed: a comma
  before the year, EU numbers, and an old SI with a malformed URL. The 6 that remain are all the `sub`
  false positive; 5 read.
- reader-only references: 25 read. 23 are real mentions in words. 2 were a title inside a longer
  title; a guard was added, which dropped 17 matches corpus-wide.
- all three say unused: 30 read, and all 30 are unreferenced. They are mostly Phase-1 hits on negative
  turns, excerpt-kept case hits in Deep Research, and change-record instruments.
- false negatives bounded (`shortforms.py`): of 1,321 unused, 21 have a short-form candidate. 16 of
  those are "the YYYY Act" matching a Commencement Regulations title, which names the parent Act, not
  the source. Of the 3 I read, 1 is a real short-form reference ("the 2018 Act" for the Act itself).

## 3. Numbers

### 3.1 Unused-source rate on report turns (reader), post-P2.1

| slice | all post-P2.1 | `wave4_*` | pre-P2.1 (excluded) |
|---|---|---|---|
| all report turns | 1,321 / 4,320 (31%) | 458 / 1,794 (26%) | 1,544 / 2,071 (75%) |
| Conversational | 1,083 / 2,587 (42%), 1,083 turns | 425 / 1,378 (31%), 654 turns | 832 / 1,002 (83%) |
| Research | 109 / 655 (17%), 183 turns | 0 / 35 (0%), 20 turns | 300 / 434 (69%) |
| Deep Research | 129 / 1,078 (12%), 127 turns | 33 / 381 (9%), 39 turns | 412 / 635 (65%) |
| `legislation_only` | 1,169 / 3,193 (37%) | 352 / 978 (36%) | |
| `legislation_and_case_law` | 140 / 1,062 (13%) | 106 / 801 (13%) | |
| `case_law_only` | 12 / 65 (18%) | 0 / 15 | |
| by built test (same turns) | 1,591 (37%) | 602 (34%) | |
| by the stored grader | 1,838 (43%) | 801 (45%) | |

By source kind (post-P2.1, reader): Act 16%, Case 18%, SI 50%, Statute 28%. Report turns citing none of
their rail: 130 Conversational, 3 Research, 1 Deep Research. Mixed turns: 195 of 449 unused (43%).
No-report turns: 99 of 148 (67%). **Per directory** (Conversational, `perdir.py`) the rate runs from 3%
to 90%, and the spread is session mix. Directories holding 6409 or 6373 negatives sit at 51-90%.
Without their fall-back turns, every directory is 0-35%.

### 3.2 Where the unused sources come from (post-P2.1 report turns; `wave4_*` in brackets)

| | Conv. | DR | Research | all |
|---|---|---|---|---|
| (a) search hit only, no report cited it (fall-back and the like) | 839 (268) | 17 (0) | 15 (0) | **871 (268)** |
| (b) retrieved (excerpt), no report cited it | 85 (59) | 96 (33) | 94 (0) | 275 (92) |
| (c) a report cited it, the answer did not | 159 (98) | 16 (0) | 0 (0) | **175 (98)** |

The product's fall-back counter: 90 turns (85 Conversational, 3 Research, 2 Deep Research), 926
sources, 879 of them unused. **So a pre-answer check addressed to the model can reach (c) at most, 13%
of the unused (175 of 1,321).** The rest the Worker never cited either.

### 3.3 Links: Worker report to answer (report turns, Manager path; Deep Research separate)

| | Conversational, post-P2.1 | Conversational, `wave4_*` | Research, post-P2.1 | DR synthesis, post-P2.1 |
|---|---|---|---|---|
| turns (with report links) | 1,084 (916) | 655 (550) | 193 (180) | 127 |
| distinct legislation URLs kept | 1,416 / 1,828 (77%) | 900 / 1,112 (81%) | 869 / 869 | 1,189 / 1,214 (98%) |
| distinct case-law URLs kept | 131 / 184 (71%) | 87 / 107 (81%) | 15 / 15 | 310 / 310 |
| instruments linked in report and in answer | 1,012 / 1,241 (82%) | 639 / 743 (86%) | 501 / 501 | 566 / 573 |
| instruments named in words, linked nowhere | **110** | **29** | 0 | 0 |
| answer keeps none of the report's links | 166 turns | 63 turns | 0 | |
| per-turn share kept (p25 / median / p75) | 0.50 / 1.00 / 1.00 | 0.67 / 1.00 / 1.00 | 1 / 1 / 1 | |

The Conversational drops, post-P2.1 (`links2.py`): 412 distinct URLs. 159 are instrument URLs. 169 are
provision URLs whose provision the answer does not name, so the proposition went with the link. 84 are
provision URLs whose provision the answer still names in words. That 84 is an upper bound: of 3
spot-checked, one was a search-term listing, one named the same number in another instrument, and
one was real. `wave4_*`: 212, split 82 / 108 / 22. Link instances (Thomas counted instances): 1,936 in
the reports and 1,824 in the answers, post-P2.1.

**I read 14 of the 166 keep-none turns** (`keepnone.py`, seed 3). Every one keeps the report's
propositions in plain words. 12 carry no link at all. 2 link the instrument's base URL where the report
linked a section. Several are follow-up turns restating an earlier answer. 152 of the 166 have no link
of any kind. 6354, Thomas's session, was replayed on Gemini once since P2.1 (`wave2`, t1). It kept 0
of 6 distinct report URLs and named 1 instrument in words, unlinked (n=1). Thomas's 15 of 41 and 40 of
55 are on `glm-5.2:cloud`, and nothing here measures that model.

### 3.4 6378 (the regression check)

`p43_6378.py <R> 6378 <the row's SSI id>` (the id goes on the command line, as in batch 5 C). 15 run
files, 23 answered turns. Before P2.1: 0 of 4 name it. Since `wave2`: **17 of 19**, of which 16 by id
and 1 by title only (`wave4_b7_p324` r1 t2). Misses: `wave4_b9_sweep3` p34 r3 (both delegations lost,
P4.5 label in the answer; the rail still carries the instrument) and `wave4_b9_sweep1` p34 r1 (never
retrieved, and not in the rail; this is P3.4's "lost 6378 rep"). **P4.3's shape, in the rail and
absent from a completed answer: 0 of 19.** Check: passes.

### 3.5 Rail display (found in passing)

Of 4,917 post-P2.1 answered-turn rail entries, **807 are titled with a bare id** and **438 have no
URL** (437 both). They come from `_extract_sources_inner`: change-record groups take `title: rel_lid`,
and a section search with no earlier search hit takes `title: data.get("title") or lid` and
`url: data.get("url") or ""`.

## 4. Dry runs of the candidate levers (built code)

`dryrun_filter.py` rebuilds each delegation's Worker-seam rail from its recorded raw tool results with
the built `agent_shared._extract_sources_from_tool`, filters it with the built `_source_is_used`
against the report (agent blocks stripped), and merges it with the built `_is_duplicate_source`.
**Fidelity: 1,403 of 1,404 post-P2.1 report turns rebuild to the stored rail as a set** (`rebuild_diff.py`:
136 differ in order only and 21 in an enriched `cite` only, both from tool completion order; 1 differs
in members). Every turn whose rail moves under V1 or V2 is listed in `dryrun_moves.tsv` (394 turns).

| lever (post-P2.1 report turns) | Conversational | Research | Deep Research |
|---|---|---|---|
| unused now (reader) | 1,083 / 2,587 (42%) | 106 / 643 (16%) | 129 / 1,078 (12%) |
| **V1** no fall-back (built): unused after | 236 / 1,712 (14%) | 91 / 628 (14%) | 112 / 1,058 (11%) |
| V1: sources removed that the answer names | 28 | 0 | 3 |
| V1: turns left with an empty rail | 84 | 3 | 0 |
| **V4** (ESTIMATE, reader test as the keep rule; not built) | 244 / 1,742 (14%) | 91 / 628 | 112 / 1,061 |
| V4: removed that the answer names / empty rails | 6 / 65 | 0 / 3 | 0 / 0 |
| **V2** answer-seam filter (built test): removed / of which named | 270 / 135 | 111 / 20 | 185 / 67 |
| **V3** answer-seam flag (built, as the seam sees it): flagged / wrongly | 1,514 / 433 | 126 / 20 | 192 / 67 |

The same run over `wave4_*` (714 report turns, all rebuilt): Conversational unused 425 of 1,378 (31%),
then 154 of 1,089 (14%) under V1 and 157 of 1,105 (14%) under V4. V1 removes 18 sources the answer
names, V4 removes 5. V1 leaves 34 turns with an empty rail, V4 26. Deep Research is 33 of 381 (9%)
and Research 0 of 35 under every variant.

**What the V1 removals the answer names are** (31 sources, 18 turns, all read by key; 1 turn, 6340 r3
t1, read in full). These are negative turns. The answer names an instrument in words (an Act whose
change record was read, or an SI listed in a "not held" or enabling-power negative), and the Worker's
report named it the same way, never by URL or id. That is why its filter kept nothing and fell back.
V4's 6 left are rail entries titled with a bare id: the answer names them by title, and the rail
entry does not carry the title.

**Input forms no stored run contains** (test them on synthetic input at build time):
- a rail id that is a prefix of another's (`ssi/1901/3` against `ssi/1901/31`): the built substring
  test would match it, and there are 0 cases in the stored data;
- a report naming an instrument only by a short form ("the 1901 Act", an acronym): 1 real case among
  21 candidates;
- a case cited by party name alone, with no citation and no link;
- a Welsh-language title.

The forms that are present and must be tested include the comma before a year ("Widget Act, 1901"),
EU numbers written "N/YYYY", the old-SI "1901 No. 3", and a title inside a longer title.

**The other code texts beside a rail change.** The row's sentence that a source "cited in sources but
not in the answer" is a condition (FIX_PLAN) is not product text. The P2.2 comment in `run_worker_agent`
says the scope block is appended AFTER filtering so that it does not suppress "P4.3's
`turns_source_fallback` signal". V1 and V4 remove the fall-back that this signal counts, so
`replay_report`'s `turns_source_fallback` would then count only turns whose rail the answer never
names. No lawyer-facing text names the rail.

## 5. Thomas's prompt rule: what a seam A/B would cost, and which payloads

**Payloads** (`ab_payloads.py`, manifest `ab_payloads.tsv`): `wave4_*` Conversational report turns on
the Manager path, recorded on the pinned Gemini. **NU** 26 turns in 9 sessions, where the answer names
an instrument that the report linked and links it nowhere. **KN** 44 turns in 10 sessions, where the
answer keeps none of the report's links. **OK** 19 controls, one per session, where the answer kept
every link. **Sizes** (`ab_sizes.py`, `seam_replay manager --dry-run`, no model call):
- composition payload median 16,393 characters, maximum 31,322;
- first-round payload median 12,834 characters.

**Draws.** The composition seam with tools offered (P3.13: tool-free, it passed a payload the live
Manager failed), plus the first-round brief-drift guard. In P3.13, a CITATION PRESERVATION clause in
the conversational Manager's prompt moved its first delegation brief and sent a run to the wrong Act,
and Thomas's rule is the same kind of clause. At temperature 0, count payloads, not draws.

**Price,** from recorded Manager-seam costs: SESSION_LOG, "about $2.4" for 84 composition draws (about
$0.03 each) and "about $0.4" for 48 first-round draws (about $0.008 each):
- 24 payloads (8 NU, 8 KN, 8 OK), 2 composition draws a side and 1 first-round draw a side: 96 + 48
  draws, **about $3.25** (cap $5);
- all 89 payloads, 1 of each a side: **about $6.75**.

**Not possible today, three instrument gaps** (tool changes for the integrator or E; I changed nothing):
1. `seam_replay manager` (composition) refuses `--date`. `manager_head` takes `on_date`, but
   `manager_messages` does not pass it through, so only `--first-round` can draw `--date recorded`.
2. There is no body-only rule swap. `--without-fix` swaps `_MANAGER_CONV_BODY` for the one at `--rev`
   AND hands over the bare report without P3.13's linker, so an A/B built on it changes two things.
   It needs a `--rule-file` (or a body-only swap) that leaves `worker_result_for_manager` in place.
3. There is no link-retention grader. `siblings` measures sibling subsections only; `caselaw` counts
   case-law URLs in the answer only; `MD_LINK` misses a label containing a bracketed year. The logic
   of `census.py` and `links2.py` (distinct report URLs kept, instruments named in words but unlinked)
   would become a `replay_report links` subcommand.

## 6. What I did NOT do

- No product code, and no change under `server_py/` (so no unit tests, reverts or mutants apply). No
  seam draw, no model call, no external call.
- No grader edit (agent E owns `replay_report.py` this batch). The grader changes I propose are
  decisions 4 and 3.3.
- I did not price or run a replay. I did not read every one of the 1,321 unused sources or the 394
  moved turns: the samples, and what each showed, are in section 2.
- I did not measure `glm-5.2:cloud`.
- I did not touch FIX_PLAN, SESSION_LOG or any other file that rule 2 lists.

## 7. Decisions for the integrator and the user

**1. P4.3's re-booked acceptance (the rail half).**
- **(a) Recommended:** a deterministic acceptance at $0, n=1 (as P3.6's was), run with the built code
  over every stored post-P2.1 report turn: (i) 0 report turns whose rail is the Worker's unfiltered
  fall-back (from 90); (ii) the unused-source rate on report turns, by the reader test booked as a
  grader, at or below 15% in each chat mode (from 42% / 16% / 12%, Conversational / Research / Deep
  Research; `wave4_*` 31% / 0% / 9%); (iii) 0 sources the answer names removed from the rail. Then the
  next sweep's report turns are re-graded on the same three items, with no dedicated replay. 6378 stays
  as the regression check: the row's SSI in the body of every completed report turn.
- (b) A replay acceptance, n=3 on the sessions with the most fall-back turns (6409, 6373, 6383). It is
  more realistic, but it pays for what the dry run already shows, because the filter's inputs (raw
  results and report) are stored.
- (c) Keep the row as written: the 6378 half passes, and the rate has no bar.

**2. The rail lever.**
- **(a) Recommended:** at the Worker seam, drop the fall-back-to-all, and also keep a source the
  report NAMES (title, SI or EU number; V4). Also drop the legislation `sub` token from the keep test.
  Estimated effect: 42% to 14% Conversational, with 6 named sources lost against V1's 31 and 68 empty
  rails against 87. It is code (Invariant 2), and it needs a title test with synthetic cases for the
  forms in section 4.
- (b) V1 alone, already dry-run with the built code: the same rate, but 31 sources the answer names
  leave the rail on 18 turns, and 87 turns get an empty rail.
- (c) The row's original cited/consulted flag at the answer seam (V3). It needs `_lid` carried to the
  answer seam, `sub` dropped, a title test, and a client change (a `client/dist` rebuild; the client
  has no test runner). As built it mislabels 28% of what it flags.
- (d) (a) now, and (c) later as its own row, if the lawyers want "consulted" sources shown.

In every option, an empty rail falls on a negative answer whose rail the answer never names, and the
code scope line still states what was searched. Whether that is acceptable to the lawyers is the
user's call (Invariant 1: it does not lower any evidence bar).

**3. The link half (Thomas's action 7).**
- **(a) Recommended:** split it into its own row (batch 5 C7 (c)) with the lever measured first: a
  code linker at the answer seam (P3.13's pattern). It would link the answer's first plain-word mention
  of an instrument the report linked, using the report's URL verbatim and never building one. The
  ceiling is 110 instruments post-P2.1, and 29 over `wave4_*`, all 29 read and real. A $0 dry run
  follows the build.
- (b) Thomas's prompt rule in `_MANAGER_CONV_BODY`, measured by the seam A/B in section 5 (about
  $3.25 after the three tool changes), with the first-round drift guard, because of P3.13's precedent.
- (c) Keep both halves in P4.3, with a links bar: Conversational distinct report URLs kept at or above
  81% (`wave4_*`), and instruments named in words but unlinked at or below the before-column on the
  same payloads.
- (d) No link lever: on the pinned Gemini the per-turn median keeps every link, and the large losses
  were measured on `glm-5.2:cloud`.

**4. The stored grader (`src_unused`, `turns_source_fallback`).**
- **(a) Recommended:** a new `replay_report rail` subcommand on the reader test, validated both ways
  with `--drops`, and the old counters labelled as the token test's. It would reproduce 1,321 of 4,320
  here.
- (b) Patch `_source_cited` to derive the id from the URL. That fixes the 293 misses but not the 301
  mentions in words.
- (c) Leave it, and quote it only with the bias stated (43% against 31%).

**5. Rail entries with a bare-id title (807) or no URL (438).**
- **(a) Recommended:** book a new P3 row (display; the rail as a verification surface). Fill the title
  from any search hit for the same id, and the URL from the id.
- (b) Fold it into P4.3's lever. That is scope creep, against the Re-planning protocol.
- (c) Leave it.

**6. The rail on failed turns** (lost or halted: 148 sources on 23 no-report turns and 449 on 58 mixed
turns, post-P2.1; for example, the 6378 lost turn shows 5 retrieved instruments under "no completed
research stands behind what follows").
- **(a) Recommended:** record it on P4.5's row as a watch item, and decide it with decision 2's lever.
- (b) Empty the rail when every delegation was lost or halted.
- (c) A new row.

## 8. Commands

Run from the scratch folder `$C` = `docs/prepilot-fixes/evidence/seam/batch10/C/` (copied to the main
checkout), with `R=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`, `PYTHONIOENCODING=utf-8`.
Run `census.py` first, because the rest read its two `.jsonl` files. **The scripts import this
worktree's `server_py` by default. To re-run them on the merged tree, set
`P43_SERVER_PY=C:/Projects/LexChat/server_py`; do not edit them** (`census.py` and `dryrun_filter.py`
assert the path they imported from). `reader.py` is a verbatim copy of `census.py` lines 34-135.

| number | command |
|---|---|
| recorded heads, modes, models per directory | `python heads.py R` |
| P2.1 ancestry | `git merge-base --is-ancestor 4d3f4c1 <head>` for each recorded head (repo root) |
| 539 run files, per-turn and per-source rows | `python census.py R` |
| BASELINE B8 split reproduced: 57 / 622 / 489 / 9 | `python repro41.py R` |
| verdict agreement: 2,708 / 1,609 / 301 / 293 / 6 | `python agg.py verdicts` |
| section 3.1 tables | `python agg.py unused` |
| section 3.2 split | `python agg.py split`; fall-back counter: `python fallback.py R` |
| per directory | `python perdir.py R` |
| section 3.3 links | `python agg.py links`; drops split and instances: `python links2.py R [--show N]` |
| keep-none sample (14) | `python keepnone.py R 14 3` |
| named in words, unlinked (29 over `wave4_*`) | `python nu_read.py R wave4_` |
| reader samples | `python disagree.py R TTF 12`, `FFT 25 7`, `FFF 30 11` |
| reader false-negative bound (21) | `python shortforms.py R 20` |
| 6378: 17 of 19 since `wave2` | `python p43_6378.py R 6378 <the row's SSI id>` |
| rail shapes: 807 / 438 | `python src_shapes.py R` (all rows), then the post-P2.1 count from `census_sources.jsonl` |
| dry run V1-V4 (all; `wave4_*`) | `python dryrun_filter.py R`; `python dryrun_filter.py R wave4_` |
| rebuild fidelity 1,403 of 1,404 | `python rebuild_diff.py R` |
| A/B payloads and sizes | `python ab_payloads.py`; `python ab_sizes.py` (`--dry-run` only) |
| suite | `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c python -m pytest -q` (from `server_py/`): **2783 passed** |

**Scratch:** the worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch10/C/`
(`git check-ignore -v` gives `.gitignore:113`). It holds the scripts, the `.jsonl` census, the
`.out` files, the hand-read files `read_*.txt` (they quote answers: gitignored only), `dryrun_moves*.tsv`
and `ab_*.tsv`. It is copied with `cp -r` to the main checkout's same path. The file counts on both
sides are in the integrator reply. No matter text is in this note: sessions are cited by number,
instruments only as "the row's SSI".
