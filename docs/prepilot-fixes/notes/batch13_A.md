# Batch 13, agent A: P3.45 (P1), the summariser's case citations

Base: `1889abb`. The worktree came up on `main` (`a6b4a76`) with no commits of its own; I ran
`git reset --hard 1889abb` first. Branch: this worktree's branch, commits `0dc712f` and `069ae80`.
$0 model spend, 0 live calls of any kind.

**Built shape, for the integrator to relay:** a new module `server_py/src/utils/summary_citations.py`
and one wrapper, `summarisation.check_summary_citations`, called at every return of
`summarise_for_query` that carries a model-written summary and on the local-cache-hit branch of
`run_worker_tool`. It only removes text; it writes no word a lawyer or the Worker reads, so there
is no wording to approve (decision 1 is about the action, not words).

## 1. What I found (measure first, $0)

Every command runs from the worktree's `server_py/` with `PYTHONIOENCODING=utf-8`; the scripts
are in the gitignored scratch (`evidence/seam/batch13/A/`), and every one imports the BUILT module
(each asserts it imports this worktree's code).

**Scope.** 70 replay directories, 577 run files, **5,808 summarised tool results**
(`summarised: true`; 5,615 in batch 12 E's 66 directories). No stored result is a local-cache
hit (every replay ran with the cache forced off).

**The scan** (`python ../docs/prepilot-fixes/evidence/seam/batch13/A/p345_scan.py
C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay ../docs/prepilot-fixes/evidence/seam/batch13/A/scan2`):
6,412 case citations in 1,020 summaries; **83 the raw source does not hold, in 47 summaries**
(46 neutral citations, 36 law reports, 1 Find Case Law URL). 14 of the 83 are the research
question's own citation echoed (one session, P4.1's directories); with the delegation brief as the
summariser's query, as the product passes it, **69 citations in 37 summaries** remain. By the
detector's name test: 56 cases the source never names, 11 the source names with a citation it
does not give, 2 with no readable name.

**Where they reached an answer** (the citation string in the same turn's answer): 12 of the 69, in
6341 (4, `wave2_p27_pre` rep 1 t2), 6363 (3: `wave1` rep 1 t1 and t4, `wave4_b9_sweep2a` rep 1
t1), 6411 (4: `wave2` rep 1 t1, `wave2_p25b` rep 2 t1) and 6348 (1, `wave3_p31_pre` rep 2 t4):
the four sessions batch 12 E named.

**By era.** 32 of the 37 summaries are in directories from before P3.3's source rule (Session 32)
and 5 after it (`wave4_b1_post`, `wave4_b2_post`, `wave4_b9_sweep1` x2, `wave4_b9_sweep2a`): 32 in
3,977 summarised results against 5 in 1,831 (my split by directory name). Of the 5 post-rule
summaries, 1 brought in a case the source never names (and it reached the answer, 6363). The other
4 carry only an unsourced citation: 3 for a case the source names, 1 a duplicate of a held
citation with another year. The rules lowered the rate; they did not stop it.

**The detector, validated both ways (hand-read; aids `p345_validate.py`, `p345_held.py`):**
- *Direction 1, every removal read against its raw text.* The first built pass called 7 citations
  unheld that the source holds in another written form (synthetic examples): "[1901] UKSC1" (no
  space), "EWCA Civ. 2" (a dot), "EWCA (Civ) 2", a stray "[" before the number, a series
  abbreviated differently ("[1901] 2 All 3" for "[1901] 2 All ER 3"), a volume report without its
  year, and a search query's own text with the opening bracket missing ("1901] UKSC 4"). Each form
  is now read, each with a test, and none of the 7 moves. In the final pass, 0 of the 69 is held
  by the source in any form I could find. Two are arguable: a summary that misspelt the source's
  court code (UKTT for UKFTT), and one that corrected the source's own garbled page number. Both
  are citation-only removals: the case name stays.
- *Direction 2, holds.* 6,343 citations held (5,745 by neutral-citation key, 576 by report text, 8
  by a looser report form, 14 by the brief). I read all 22 loose holds and a seeded sample of 40
  plain ones (seed 345), and 0 were wrongly held.
- *Names.* For each of the 56 removals of a case "the source never names", every distinctive word
  of the name was checked against the raw text by hand (`dry2/validate.txt`), and every one is
  absent.

**Names without a citation (measured, not built):** 24 "X v Y" mentions in summaries whose source
does not name the case. By hand: 12 are the summariser's own additions, 5 sit in a note saying
the text does not contain such a case, and 7 echo cases the brief named. See decision 2.

## 2. What I built, and why

**The action follows the measurement** (`strip_unsourced_citations`, records per removal):
- **The source names the case, but not this citation** (11 + 2 no-name): the citation alone goes.
  The case is the source's; the citation was the summariser's (a wrong number, a law report the
  source never gives, a wrong court or year).
- **The source never names the case** (56): the case was brought in by the summariser, so the
  passage carrying it goes. Dropping only the citation would leave an invented authority named but
  uncited, and the Worker would cite it from training. What goes:
  - the list item with its nested lines;
  - the block under a bold or heading line that is the case itself;
  - otherwise, the sentence. A sentence that introduces a list ("... the test derived from X:")
    takes the list with it.
  - A heading whose whole section went goes too, with a one-line italic note under it. This is the
    6411 change-record summary's invented "Case Law Search Results" heading.
  - In a one-line list of authorities that also holds cases the source names, only the invented
    case and its citation go ("case"; no stored summary has this shape).
- **Kept:** a citation the brief carries; every byte of a summary with nothing unheld; the
  product's appended blocks ("[CITATION URLS", "[MANDATORY NEXT STEP", "[CHANGE RECORD", which
  are boundaries); held citations.
- **Fail-soft and idempotent:** any error returns the summary unchanged. A second pass changes
  nothing.

**Where it runs (every function named):**
- `src/utils/summary_citations.py` (new): `find_citations`, `source_text`, `SourceIndex`
  (`held`, `word_held`, `_split_held`, `_in_norm`), `name_before`, `_reference_name`,
  `name_words`, `name_held`, `unsourced_citations`, `strip_unsourced_citations` and its private
  helpers.
- `src/agent/summarisation.py`: new `check_summary_citations(summary, source, query)`.
  `summarise_for_query` applies it at its four summary returns: single chunk, consolidated, the
  combined partials, and the partials after a failed consolidation. The raw-text fallback is
  returned as before.
- `src/agent/agent_shared.py`: `run_worker_tool`, the local-cache-hit branch only (2 lines). A
  stored summary is checked against this request's raw result before the Worker sees it, so rows
  written before the check, or under another brief, are served checked. A fresh summary is stored
  already checked.
- The schedule route's summary (`agent_shared`, the PROVISION FETCHED BY CODE path) goes through
  `summarise_for_query`, so it is checked against the unit text it summarised. No stored run
  records that unit's raw text separately, so it is tested only through `summarise_for_query`.
- `tools/summary_probe.py`: `redraw --citations` (new `CITATION_KEYS`, `citation_check`,
  `_citation_slots`; `--session` is now optional at parse time and required in code for the
  rubric mode). It re-summarises the stored summaries that carry an unheld citation and puts each
  draw through the product's check. It is paid; I priced it and did not run it.

**Not touched:** `_CANON_VERSION` (no bump needed: a hit is re-checked). There is no new audit
field and no log line above INFO naming a citation: INFO logs the count, the actions and the
characters removed; the citations themselves go to DEBUG only.

**Other code that reads summaries.** No other code text speaks of these citations, so the check
contradicts none. `replay_report`'s `_p322_turn_retrieval` (`authorities`, agent E's subcommand)
falls back to `final_result` when a case-law raw result is not JSON. After this change, a citation
the summariser invented no longer counts as retrieved there, which is the right direction.
`summary_probe glosses` and `cmcdates` read summaries too; a removal can only take text away from
what they read.

## 3. The dry run with the BUILT code (every stored summary)

`python ../docs/prepilot-fixes/evidence/seam/batch13/A/p345_dryrun.py
C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay ../docs/prepilot-fixes/evidence/seam/batch13/A/dry10`
(final_result against raw_result, the delegation brief as the query). Stored `final_result` also
carries the appended blocks, so this is a superset of the product's input.

**37 of 5,808 summaries move; 69 removals** (13 citation, 48 item, 2 block, 6 sentence); 15,702
characters. By tool: `get_legislation_changes` 25, `search_case_law` 21,
`search_legislation_sections` 13, `get_case_law_text` 10. Every changed summary is in
`dry10/diffs.txt` (405 lines), and I read every diff:

| Location (dir, run, turn) | Removals | Reached answer |
|---|---|---|
| baseline 6359 r1 t2; t7 | citation; block x2 | 0 |
| baseline 6363 r1 t4 | item | 0 |
| baseline 6375 r1 t2 (2 tools); r2 t2 | item x2, item; item | 0 |
| wave1 6359 r1 t2 | item x4 | 0 |
| wave1 6363 r1 t1; t4 | item; item | 1; 1 |
| wave1 6375 r1 t2 | citation | 0 |
| wave2 6363 r1 t1 (2 tools); t3 | item; citation x2; citation | 0 |
| wave2 6370 r1 t3 | item x3 (and the emptied heading) | 0 |
| wave2 6411 r1 t1 | item x5 (and the emptied heading) | 2 |
| wave2_p24 6375 r3 t2 (2 tools) | citation; citation | 0 |
| wave2_p24_final 6375 r3 t2 | item | 0 |
| wave2_p24_pre 6375 r2 t2 (2 tools) | item; citation | 0 |
| wave2_p25 / _p25_smoke / _p25b (r1, r2, r3) 6411 t1 | item x4 each (and the emptied heading) | 2 (r2) |
| wave2_p27_pre 6341 r1 t2 | item x4 | 4 |
| wave3_p31_pre 6348 r2 t4 | sentence (and the 3-item list it introduces) | 1 |
| wave4_b1_post 6375 r1 t2 | citation (a duplicate of a held citation with another year) | 0 |
| wave4_b2_post 6375 r1 t1 | citation (arguable: the source's own page is garbled) | 0 |
| wave4_b9_sweep1 6359 r2 t7; 6363 r1 t4 | citation; citation | 0 |
| wave4_b9_sweep2a 6363 r1 t1 | item | 1 |
| wave4_p33_pre 6370 r2 t1; r3 t1 | sentence x2; sentence x2 | 0 |
| wave4_p33_pre 6375 r3 t2 | item | 0 |
| wave4_p41 6346 r2 t3; r3 t3 | sentence; citation (a garbled URL) | 0 |

Every rendered line left behind reads cleanly: no empty bracket, no broken emphasis, no doubled
blank line. Grep the `+` lines of `dry10/diffs.txt` to see them.

**What else moves (Invariant 1)** (`lost_held.py`): 5 held citations went out with a removed
passage. In 4 the summary still carries the same citation elsewhere. 1 is lost from the summary:
`wave4_p33_pre` 6375 r3 t2, a held case named only inside the parenthetical "referenced in ..." of
an invented item. The product's appended nudge does not list it either. The 2 arguable
citation-only removals are above.

Provision references (`lost_provisions.py`, summary_probe's `PROVISION` pattern): 13 references in
7 summaries are no longer in the cleaned summary. 12 of them are not in the raw text either: they
are the summariser's own, inside invented case passages (6411's invented case-law list, 6348's
removed sentence). 1 is in the raw: `wave2` 6411 r1 t1, a provision named only inside an invented
case's item. Every other removal is case-law text the source does not hold.

**Forms no stored run contains, tested on synthetic input:**
- a local-cache hit;
- the combined-partials and failed-consolidation returns;
- unbracketed Scottish reports ("1901 SC 10");
- a URL inside a markdown link;
- a one-line list of authorities mixing held and invented cases;
- a reference name ("Reference by ...") the source holds;
- an acronym party ("WCL" for the initials of a source name);
- a sentence-ending abbreviation inside a name;
- a long bold line that is a sentence, not a heading.

## 4. Tests, revert proof and mutants

- `tests/test_summary_citations.py`, 77 tests, synthetic fixtures only ("Widget Co v Example Ltd",
  `ssi/1901/3`).
- **Full suite on `lexchat_test_a`: 3,456 passed** (3,379 at base + 77).
- **Revert proof on a scratch copy** (`revert_proof.py`; output `revert_proof_final.txt`):
  - R1, the whole change reverted: 29 wiring lines and the 728-line module removed. Collection
    error, as expected for a missing module.
  - R2, the wiring alone reverted (29 lines): 6 failed.
  - R3, the entry point stubbed to return the summary unchanged: 37 failed.
- **Single-site mutants** (`mutants.py`; output `mutants_final.txt`): the control passes 77 of 77,
  then **54 of 54 mutants are caught**, one per guard and cleaning step. They cover:
  - each citation form read;
  - the no-prefix guard;
  - the brief echo (neutral citation and report);
  - the JSON decode;
  - the acronym, case and stop-word rules;
  - the side-complete rule and the office phrase;
  - each name-reading stop (bracket depth, prose after "v", "in", a label, a sentence end);
  - the reference name;
  - item children and a blank line inside an item;
  - block and boundary ends;
  - the emptied-heading rule and its limit;
  - the introduced list;
  - the closing emphasis;
  - the abbreviation guard;
  - the case segment and its left edge;
  - each tidy step (link, parens, comma, empty emphasis, space before closing emphasis, trailing
    separator, list marker);
  - the contentless line and the blank-run collapse;
  - each of the four `summarise_for_query` returns and the cache hit;
  - fail-soft;
  - the probe's two counters.

  The first run caught 47 of 51. The 4 survivors (acronym, abbreviation, the segment's left edge,
  a long bold line) each got a test that now catches them; one fix also came out of it (a
  sentence end before a name no longer joins the name).

## 5. Pricing an acceptance (not run)

The row's acceptance is deterministic: the dry run over every stored summary, every change read,
and the tests failing with the change reverted. **That is met** (sections 3 and 4).
`summary_probe` without changes cannot show the effect: its `redraw` draws the prompt directly and
never passes through `summarise_for_query`. Hence `--citations`. All estimates below are from
`--dry-run`, using its own price model (`_PRICE_IN`, `_PRICE_OUT`, 1,500 output tokens a call):
- **Seam, recommended scope:** `python -m tools.summary_probe redraw --citations --side with
  --reps 3 --max-raw 150000 --dir <all 70> --out <evidence path>`. 25 slots, 75 calls, **about
  $0.52**. The summariser is the dev box's `google/gemini-3-flash-preview`; book it at $1 for
  headroom. It measures, on fresh draws with today's prompt, how often a draw carries an unheld
  citation, and that the check leaves 0 unheld and every held citation. Every draw must be read
  for removals the stored shapes did not show.
- Seam, the four answer sessions only (`--session 6341 6348 6363 6411`): 12 slots, 45 calls, about
  $0.50. Seam, every slot including the two 969K judgments: 32 slots, 147 calls, about $1.99.
- **Replays** of 6341, 6348, 6363 and 6411, n=3: about $16.60 at their stored means (2.49, 0.64,
  2.31 and 0.11 a run) and $32.50 at their stored maxima (`replay_costs.py`). This is weak
  evidence: the defect is 37 in 5,808 summaries (5 in 1,831 after the source rule), so a replay
  may never draw one.

## 6. What I did NOT do

- No model call, seam draw, replay or live call. The `--citations` redraw is built and priced, not
  run.
- Bare "X v Y" names without a citation are measured (section 1), not acted on (decision 2).
- No audit field. The removals are visible only in the logs (decision 4).
- No `_CANON_VERSION` bump.
- No edit to FIX_PLAN, SESSION_LOG, the tracker, CLAUDE.md, CHANGELOG, any rubric or any memory
  file.
- No change to `replay_report` (B and E own its subcommands).

## 7. Decisions for the user (recommendation first)

1. **What the check does with an unheld citation.**
   - (a) **Remove it as built**: the citation alone where the source names the case, the passage
     where it does not. This is code enforcement (Invariant 2). It removes the 12 that reached
     answers, and it loses one held citation inside an invented passage.
   - (b) Remove the citation only, always. Nothing held is ever lost, but 56 invented authorities
     stay named and uncited, and the Worker can cite them from training.
   - (c) Flag instead of removing: a code note after the citation saying the retrieved text does
     not contain it. The Worker still reads the case, and the wording reaches it, so the wording
     would need your approval and a detector screen. Prompt obedience, against Invariant 2.
2. **Case names written without a citation** (24 measured: 12 the summariser's additions, 5
   "does not contain" notes, 7 echoes of the brief).
   - (a) **Book it as a follow-up row, measured here.** Build it only after a name-only detector
     is validated on these 24 and on the held names (622 by the scan), because a name has no
     number to anchor it.
   - (b) Extend this check to bare names now, with the same name rules. It would remove the 5
     negative notes too.
   - (c) Leave it.
3. **Acceptance.**
   - (a) **Tick on the deterministic acceptance** the row states (met: section 3 and 4). Then,
     optionally, the seam `redraw --citations` at about $0.52 (book $1) as a fresh-draw check,
     priced to you before it runs.
   - (b) Require the seam draw before ticking.
   - (c) Require replays of the four answer sessions, n=3 (about $16.60 to $32.50). This is weak
     evidence for so rare a defect.
4. **Making the removals visible to the harness.**
   - (a) **Logs only now** (INFO count, DEBUG citations, as built), with an additive audit field
     booked for the next schema change: per tool, `citations_removed` with the action. A future
     sweep could then count the rate without re-deriving it.
   - (b) Add the audit field now (schema v7, `docs/api/AUDIT_TRACE.md` and the audit tests). This
     touches files outside this brief.
5. **The one held citation lost, the one held provision reference lost, and the 2 arguable
   citation-only removals.**
   - (a) **Accept**: the lost case and the lost provision reference are named only inside the
     summariser's own invented passages ("referenced in ..."; an invented case's item), and both
     arguable removals leave the case name.
   - (b) Keep a passage whose held citation appears nowhere else in the summary, and remove only
     the invented citation there. The invented case then stays named.
