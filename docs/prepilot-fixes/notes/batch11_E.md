# Batch 11, agent E: P3.10 built (the handover line), its scripts and grader, the sweep priced ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every batch. I had made no commits, so I ran
`git reset --hard 024e396` (the `<INTEGRATOR_HEAD>`). This note and the branch are based on `024e396`.

**Spend: $0.** No model call, no seam draw, no replay, no server, **no live call to any host** (0 calls).
**Tests: 2856 passed** (2833 at the base + 23 new; `python -m pytest -q -p no:cacheprovider` from `server_py/`,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_e`; `pytest_full.out` in scratch).

**Model.** Every stored run read here ran on the pinned `google/gemini-3.1-pro-preview` (summariser
`google/gemini-3-flash-preview`), summarised at the 8,000-character fallback. Every number below is from that model.

**Scratch.** `docs/prepilot-fixes/evidence/seam/batch11/E/` (gitignored by `.gitignore:113`, checked with
`git check-ignore -v`), copied with `cp -r` to the main checkout's path of the same name (file counts in section 8).
The scripts import THIS worktree's built code (`agent-a07a04ab5043febe1/server_py`); to re-run one on the merged
tree, pass the tree (`dryrun_p310.py <server_py>`, `p310_grade.py --server <server_py>`) or edit `sys_path_server`
and `REPO` in the repointed `p310_recount.py`. They read all 64 replay directories; a new directory changes counts.

**Functions changed (collision note):** in `agent_core.py`, **`_build_step_brief`** (a new optional parameter
`earlier_reports`, and the line) and **`run_deep_research`** (the one call to `_build_step_brief`). No import was
added at the top of `agent_core.py` (the import is inside `_build_step_brief`), so the import block B and C touch is
untouched. In `utils/instrument_lookup.py`, **`routed_lookup_block`** (the extraction reads the brief through
`without_handover_line`). New: `utils/step_handover.py`, `tests/test_step_handover.py`.

**Built shape against the brief (lesson: say so first).**
- The line goes **only to steps the gate flags** (the Session 15 pattern plus the one form batch 10 D found it
  missing), not every step 2+. Both were measured (section 2); the other option is a one-line change.
- **The line is excluded from P3.7's routed lookups** (section 3).
- **No class filter in the product.** The line names every instrument the earlier bodies cite (the parent Act
  included, one per stored line); the Worker is told to work on those "of the kind the task names". The grader
  keeps D's class filter.
- The id extraction is **P3.7's own `extract_instrument_citations`**, not D's grading regex. It reads more: 10 ids
  over 10 stored steps that D's `ids_in` misses ("SR yyyy/n" and "No." citations), none the other way.
- The body cut is the product's **`strip_scope_blocks`**, not D's "text before the first `[SEARCH SCOPE`". On the
  stored reports the two give the same ids (0 ids only in D's).

---

## 1. What was built, and why

`_build_step_brief(step, approved_plan, user_query, earlier_reports=None)`; `run_deep_research` passes the reports
of the steps already run (`[f["content"] for f in step_findings]`, i.e. exactly what the synthesis later reads).
For a step the gate flags, and when the earlier bodies cite at least one instrument, one line is added after SCOPE
and before the CONTEXT sentence, which stays the brief's last word. Step 1 never gets one (no earlier reports). A
lost step's content is its label (no ids); a halted step written up hands on its partial findings' ids.

**The wording (built; it goes to the user before merge):**

> EARLIER STEPS' INSTRUMENTS: the reports of the earlier steps of this plan cite these instruments, by
> legislation_id: uksi/1901/4, ssi/1902/30. Where this task works on instruments an earlier step identified, they
> are among these: work on each one of the kind the task names, by its legislation_id, rather than finding the
> list again. Look further only if the task asks for more than the earlier steps reported.

Past 15 ids the list reads "… uksi/1924/15 and 3 more." (no stored line comes near: max 9 gated, 10 ungated).

**How it meets the CONTEXT sentence** ("Research ONLY this step's task — the other aspects are covered by
separate steps"): the line is conditional ("Where this task works on …"), so it widens no step's task, and it sits
before CONTEXT, which stays last. "Among these" because the list is every cited instrument, the parent Act
included, not only the ones the task means.

**Other code texts that speak of the same instruments (lesson), read for contradictions:** P3.7's lookup block
(only for instruments the step's own text names; the line's are not looked up, section 3), the Worker scope block
(appended after the Worker writes; the line is cut from nothing, it is in the brief), P3.1's per-instrument section
cap (3 rounds an instrument; a dependent step works through 6-9 instruments, as it already did), P2.7's discovery
budget (the line lowers the need for it). None contradicts the line. One case to know: if an earlier body cites an
instrument the index does not hold, the line hands it on and is not looked up; a retrieval by its id then 404s and
P2.4's not-held record states it (`_not_held_limb`). No stored line names such an instrument.

**Side effects on two other consumers of the brief** (not changes I made, consequences of the brief changing): the
summariser receives the Worker's brief as its query, so a flagged step's summaries are asked against a brief that
names the list; and a Deep Research step's local-prompt-cache key is its brief (`_cache_key_query` is empty in Deep
Research), so a flagged step's key now includes the ids. Both reach only the 13 of 148 stored steps the gate flags.
Every stored replay ran with the local cache off.

## 2. Every step 2+, or only flagged steps (measured over the 148 stored post-P3.8 steps 2+)

Command (from the scratch folder): `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence python
dryrun_p310.py` → `dryrun_p310.out`, per-step listing `dryrun_p310.txt` (ids only; scratch). Built code.

**Input-form check (passes):** all 148 stored briefs are rebuilt byte-equal by the built `_build_step_brief` with
no earlier reports, and in all 148 the built brief with the earlier reports equals the stored brief with the line
inserted before CONTEXT. Batch 10 D's recount re-runs identically on 64 directories from my repointed copy
(`p310_recount.py`, the era table onward byte-equal; `wave4_b10_sweep` holds no plan).

| | flagged only (built) | every step 2+ |
|---|---|---|
| steps given a line (of 148) | **13** | 128 |
| list-dependent steps covered (regex 12 + hand 1) | **13 of 13** | 13 of 13 |
| provision-dependent steps given a line (hand, 7) | 0 | 7 |
| other steps given a line | **0** | 108 |
| ids per line, median / p90 / max | 6 / 7 / 9 | 3 / 6 / 10 |
| line characters, median / max | 477 / 521 | 427 / 528 |

The 20 steps 2+ with no line under "every step" are those whose earlier bodies cite no instrument (all 18 steps of
the `p41_6346_dr` plans but two, and one 6375 step).

**On the 13 flagged steps the line covers batch 10 D's class list in 13 of 13** (`gated_lines.py` →
`gated_lines.out`); the ids outside the step's class are 13, one parent Act a line.

**The gate's matches, read (every one):** 12 by the Session 15 pattern and 1 by the added form (the hand-found
step), exactly D's 13 list-dependent steps. The gate matches none of the 7 provision-dependent steps and no other
step. The added form is bounded to one sentence and 80 characters and to instrument classes (orders, regulations,
instruments, SSIs, SIs, rules); "the identified provisions" stays out (tested).

**Recommendation: flagged only (built).** It changes behaviour where the defect is and nowhere else: the other 135
steps' briefs, summariser queries and cache keys are byte-identical, so no other row's before-column moves
(Invariant 3), and the sweep (6374 and 6383 turn 4 only) cannot measure a change to the 108 other steps. A
dependent step the gate misses runs exactly as today. The cost is the gate's approximation: a planner wording no
stored plan used would be missed (the regex has missed forms before).

**Input forms no stored run contains, tested on synthetic input:** more than 15 ids (the cap and "and N more"); an
`eur` id on a line; a lost earlier step (label plus scope block: no ids); a halted step written up (its findings'
ids handed on); an earlier report that echoed an instrument-lookup block (stripped, its id not handed on); the
label quoted inside the question (not stripped from P3.7's view); a malformed step (no line, no raise).

## 3. The line and P3.7's routed lookups (decided: excluded; each option measured)

`run_worker_agent` looks up every instrument its brief names by number, at most `MAX_ROUTED_LOOKUPS` = 5, before
round 1. Same command as section 2; "added" = lookups the new brief triggers that the recorded brief did not; LEX
calls estimated at up to 2 a lookup (held: lookup + section lookup) after the per-request memo (an id looked up
earlier in the same turn is a memo hit).

| option | flagged only: lookups added / distinct per turn / LEX calls | every step 2+ |
|---|---|---|
| accept (the line read, cap 5 shared with the step's text) | 61 / 36 / up to 72 | 385 / 155 / up to 310 |
| raise the cap for the line (every id on it) | 81 / 46 / up to 92 | 422 / 176 / up to 352 |
| **exclude (built)** | **0 / 0 / 0** | 0 / 0 / 0 |

(Batch 10 D's "375 lookups, about 750 LEX calls" was the every-step, accept case without the memo; my 385 counts
lookups added over the recorded brief's own, in the same extraction, which is why the two differ slightly.)

**Exclude, because:** the ids come from the earlier steps' reports, which came from the index, so a held/absent
test adds no fact the step lacks; under accept the cap covers 5 of a 6-9 instrument list, and the first of the 5 is
the parent Act, so the Worker would get a held block for an arbitrary part of the list, which is P3.10's own defect
(working on part of the list) invited by code; and each held lookup would add a "Looked up by number …" limb to the
step's scope block, which the synthesis reads. Built so: the routing reads `without_handover_line(brief)`, which
removes only a line the label opens. **Check (passes): over all 148 stored briefs the extraction with the line
excluded equals the recorded extraction.** An instrument the step's own text names is still looked up (tested
through `run_worker_agent`).

**A grader that reads briefs will now see the line:** `replay_report lookup --routing` runs
`extract_instrument_citations` over every stored brief (`tools/replay_report.py:7538`), so on a run with the change
it would count the line's ids as routed (it overstates P3.7's reach). It should read the brief through
`step_handover.without_handover_line`. That file is agent C's; it is decision 6. `seam_replay worker --dry-run`
rebuilds the routed block with the built `routed_lookup_block`, so it agrees with the product.

## 4. The wording screen (built code)

Command (from `server_py/`): `python <scratch>/screen_p310.py` → `screen_p310.out`: every answer-reading detector
(`b9_screen.screen`, whole and per sentence, copied from the integrator's scratch) over the line rendered for one
`ukpga`, `ssi`, `uksi`, `asp`, `eur` and `nisr` id, a mixed list, a list at the cap, and lists 1 and 7 past it.
**First draft: 10 trips, all `NEGATIVE_EXPLAINED` on "searching for"** (an echo would have read to that grader as
a negative naming its search). Reworded ("rather than finding the list again. Look further only if …"): **0 trips
over 10 texts.** The full built brief for a synthetic step is printed there and read. The line holds no square
bracket (it is a brief line, not a `[…]` block), so the tool-block strippers do not apply to it.

## 5. Tests, the revert and the mutants

`tests/test_step_handover.py`, 23 tests, at the seams: the gate (`works_on_earlier_list`), the body cut and the id
extraction (`handed_on_ids`), the line (`handover_line`: wording, cap, emptiness), `_build_step_brief` (position,
the other steps unchanged byte for byte), `run_deep_research` (step 2's brief carries step 1's body ids and not its
scope block's), and P3.7 (`without_handover_line`; `run_worker_agent` looks up the step's own instrument and not the
line's).

Command (from the scratch folder): `TEST_DATABASE_URL=… python mutants.py` → `mutants.out` (each case on a fresh
copy of `server_py` in `mut/`, removed after; anchors asserted to occur once, CRLF kept).
- **Full revert** (`agent_core.py` and `instrument_lookup.py` back to `024e396`: **25 added lines removed**, plus the
  149-line `step_handover.py` deleted): the test file fails at import (1 error).
- **Wiring revert** (the 25 lines only, module kept): **5 tests fail**.
- **23 single-site mutants, 23 caught, 0 survived:** the body cut removed; the id extraction narrowed to the id form;
  the dedupe removed; the cap lowered to 5; the cap not applied; the "more" threshold at 0; the "more" count dropped;
  the emptiness guard removed; the gate always true; the added form dropped; the Session 15 pattern dropped; the
  added form's sentence bound, its 80-character bound, its class list (provisions admitted; Orders dropped); the
  gate's no-raise guard; the brief's gate bypassed; an empty line appended; the line after CONTEXT; no earlier
  reports passed by the executor; the line read by P3.7's extractor; the strip's line-start anchor; the strip
  removing only the label. (No class filter exists in the product, so none was mutated.)

## 6. The scripts and the grader

**Scripts** (tracked, ids and indices only): `evidence/scripts/p310_6374.json` and `p310_6383.json`, each the
export's turn 4 alone, `deep_research` under `legislation_only`.
- **Turn mapping checked against the export** (`check_scripts.py` → `check_scripts.out`, the product's own
  `load_sessions` + `load_script` + `scripted_session`, no network): export turn 4 of both sessions carries the Deep
  Research marker (`dr_marker`) and `legislation_only` from the feedback snapshot; turns 1-3 are conversational. The
  stored full-session runs number the same turn 4. Each script builds to one turn (`deep_research_turns` [1]) whose
  question equals the export's turn 4; verdict FAIL (so `replay run`'s default is 3 reps; pass `--reps 3` anyway).
- **A risk in the 6374 script (decision 4):** export turn 4 names a section but not its Act; only turns 1-3 named
  it (read by hand in scratch, `t4_selfcontained.out`; no text here). The planner's NO SPECULATION rule says to
  ask when no Act is named, so a turn-4-only planner may return a clarification (no plan, no evidence; it costs
  only the unrecorded planner call). 6383's turn 4 is self-contained. Also, alone, turn 4 gets no mode-change
  marker (the stored full sessions' planner had one: turn 3 was conversational). A variant, turns 1 and 4, is in
  my scratch (`p310_6374h.json`, builds offline to 2 turns, DR on turn 2).

**The grader:** `p310_grade.py` (scratch), from D's `p310_recount.py` repointed. Usage: `python p310_grade.py --dir
$PREPILOT_EVIDENCE/replay/wave4_b11_sweep [--before …] [--detail <scratch file>] [--server <tree>/server_py]`. It
pairs a scripted run with its base through `script.base` / `script.turns[k].from_turn` (so the scripted turn 1, or
the variant's turn 2, is export turn 4), grades each dependent step (D's definitions: the Session 15 pattern or
the added form; the class list from the earlier BODIES, by D's `ids_in` and P3.7's extractor together; worked on =
the retrieval tools' arguments), and prints the four bars: (1) every dependent step COVERS; (2) own
`search_legislation` per dependent step falls (mean and median); (3) no halted step; (4) `sources_kept` per base
does not fall. It also says whether each step's brief carried the line and whether the line lacked any listed id.
- **`replay_report discovery --before` cannot grade bar (4) on these runs:** it pairs on `session_id` and turn
  number, and a scripted run's are `p310_6374` and 1, so it would print "no session shared". The grader prints the
  comparison itself. (A grader gap in agent C's file; decision 6.)
- **Self-test (passes):** on scripted-shaped copies of `wave3_p38` 6374 r1 and 6383 r1 turn 4
  (`make_fake_after.py` → `fake_after/`, deleted after; `p310_grade_selftest.out`) it reproduces D's per-step
  verdicts. Its before-column (the 8 stored post-P3.8 turn 4s) reads: 13 dependent steps, 9 COVER, 4 DROP, 2 add one;
  own `search_legislation` 65 over 13 (mean 5.0, median 3); 0 halted; `sources_kept` mean 22.2 (6374, n=5) and 9.0
  (6383, n=3). (D's 7 + 1 + 4 over its 12 regex steps, plus the hand-found step, which covers and adds one.)
- **What the before-column cannot separate (decision 5):** it ran with turns 1-3 as history and at older heads
  (6383's only post-P3.8 runs are `wave3_p38`), so bars (2) and (4) compare more than the line. Bar (1) is read
  within each run and needs no before-column.

## 7. Price of the sweep (no spend; stored costs only)

Command (scratch): `python price.py` → `price.out`. Turn costs are the run files' `timing.total_cost_usd`. **The
Deep Research planner call is not in any run file's cost** (the plan endpoint emits no timing): by token estimate
about $0.01-0.05 a turn (not measured), and `sweep_total.py` does not see it.

| command (from `server_py/`, the server up and pinned) | per rep, stored post-P3.8 | n=3 median | n=3 at each rep's stored max |
|---|---|---|---|
| `python -m tools.replay run --session 6335 --reps 3 --out-dir $PREPILOT_EVIDENCE/replay/wave4_b11_sweep --max-spend 1.25` | $0.466-0.610 (6 clean reps, median $0.57); $0.989 (`wave4_b10_sweep`, a capped Worker runaway) | **$1.71** | $2.97 |
| `python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p310_6374.json --reps 3 --out-dir … --max-spend 1.75` | turn 4 $0.616-0.862 (n=5, median $0.767) + planner | **$2.30** (+~$0.10) | $2.59 (+~$0.15) |
| `python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p310_6383.json --reps 3 --out-dir … --max-spend 1.30` | turn 4 $0.349-0.634 (n=3, median $0.527) + planner | **$1.58** (+~$0.10) | $1.90 (+~$0.15) |
| **sweep** | | **about $5.60 (+ ~$0.30 planner)** | **$7.46 (+ ~$0.45)** |

**Order, P1 first:** 6335 (P3.12, P1), then `p310_6374` (check rep 1's status: a clarification means decision 4),
then `p310_6383`.

**`--max-spend` is checked before each run, so a command can spend its cap plus one rep.** The caps above let two
typical reps through and stop before rep 3 if either of the first two ran hot (6335: 2 × $0.61 = $1.22 < $1.25;
6374: 2 × $0.862 = $1.72 < $1.75; 6383: 2 × $0.634 = $1.27 < $1.30). Bound per command = cap + one rep at its
runaway case.

**Runaway exposure (price at the runaway case):**
- **Worker** heavy empty: capped by P4.10 at 32,000 output tokens, about $0.38, not retried; in 6335 the Manager
  re-delegates (`wave4_b10_sweep` rep 1's turn 1 cost $0.50 so); in Deep Research the step is lost, not redone.
- **Manager** (6335's turns): after agent B's L1 + L3 merge (before the sweep), capped and not retried, about $0.38;
  before it, uncapped and retried up to 3 times, about $2.30.
- **Deep Research synthesis and planner:** not Worker calls, so uncapped and retried up to 3 times on an empty, up
  to about $2.30 each (P4.10's runaway, about $0.76 an attempt), unless B's change also covers them (its brief names
  the Manager only). Stored: 1 empty completion in 52 post-P3.8 Deep Research turns (0 tokens, recovered on retry).
- Per-rep worst, realistic (one capped Worker runaway): 6335 about $1.37 (with a capped Manager runaway too);
  6374 turn 4 about $1.24; 6383 about $1.01. With a synthesis runaway on top: about $3.5 and $3.3.
- **Bounds per command:** 6335 ≤ $1.25 + $1.37 = $2.62; 6374 ≤ $1.75 + $1.24 = $2.99 (tail $5.25); 6383 ≤ $1.30 +
  $1.01 = $2.31 (tail $4.60). **Realistic sweep bound about $7.90**; agree a sweep cap with the user and keep the
  running total by hand (`sweep_total.py`), stopping `replay run` between reps if one more could pass it.
- With the 6374 variant (decision 4 b): add turn 1, $0.31-0.63 a rep (stored), so about +$0.9 to +$1.9 for n=3.
- A clean before-column at the pre-merge head (decision 5 b): the two scripts again, about +$3.9 median.

## 8. What I did NOT do

- No model call, seam draw, replay, server or live call; no edit to `replay_report.py` (C's), FIX_PLAN, the log,
  the tracker, CHANGELOG, CLAUDE.md or any rubric.
- I did not measure the line's effect on the Worker: that is the sweep's job, and no seam draw was authorised.
- I did not measure the planner (no planner seam), nor whether a turn-4-only planner asks for clarification.
- I did not hand-read any answer for depth or correctness; I read every gate match and every dry-run line's ids.
- I did not commit the variant script; it is in my scratch.
- Scratch: copied with `cp -r` to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch11/E/`: **31 files
  on both sides** (`find E -type f | wc -l`). `fake_after/` (copies of two stored run files) and `mut/` were deleted
  after use; `make_fake_after.py` and `mutants.py` rebuild them.

## 9. Decisions for the user (each self-contained; my recommendation first)

1. **The line's wording (it goes to every flagged Deep Research step's Worker).**
   - **(a) Recommended: approve as built** (quoted in section 1): conditional, ends on what to do, 0 detector trips.
   - (b) Drop the condition ("Where this task works on …") and say "Work on each one of the kind the task names",
     since only flagged steps get the line; firmer, but wrong for a step the gate flags in error.
   - (c) Reword (the user's text), re-screened before merge.
2. **Which steps get the line.**
   - **(a) Recommended: only steps the gate flags (built).** 13 of 148 stored steps 2+, exactly the 13
     list-dependent ones; no other step's brief changes.
   - (b) Every step 2+: 128 of 148 get a line (108 other steps and the 7 provision-dependent ones), conditional
     wording carrying it; unmeasured on those steps by this sweep.
3. **The line and P3.7's routed lookups.**
   - **(a) Recommended: exclude the line from the lookups (built).** 0 lookups added; the step's own instruments
     still looked up.
   - (b) Accept: the line read with the brief, cap 5 shared: +61 lookups on the stored plans (36 distinct a turn,
     up to 72 LEX calls); covers 5 of 6-9 listed instruments, the parent Act first.
   - (c) Raise the cap for the line: +81 lookups (46 distinct a turn, up to 92 LEX calls); every listed
     instrument gets a held block and its title.
4. **The 6374 script.**
   - **(a) Recommended: turn 4 alone, as booked, and stop after rep 1 if the planner asks for clarification**
     (the cost of finding out is one unrecorded planner call).
   - (b) Turns 1 and 4 (`p310_6374h.json` in my scratch; turn 1 names the Act): +$0.31-0.63 a rep.
   - (c) The full session: turn 2 is also Deep Research, about +$1.1 a rep.
5. **The before-column for bars (2) and (4).**
   - **(a) Recommended: the stored post-P3.8 full-session turn 4s** (free), with the confounds stated (history,
     older heads); bar (1) needs no before-column.
   - (b) Also run both scripts n=3 at the head before E merges (about +$3.9) for a clean before-column.
6. **Two grader gaps in `replay_report.py` (agent C's file), found here.**
   - **(a) Recommended: the integrator (or C, after its merge) makes `lookup --routing` read each brief through
     `step_handover.without_handover_line`,** and grades P3.10 with `p310_grade.py`, not `discovery --before`
     (which cannot pair scripted runs with full sessions).
   - (b) Leave both, and note on P3.10's row that `--routing` overstates P3.7's reach on runs after the merge.
7. **The sweep.**
   - **(a) Recommended: run it as priced, P1 first (6335, p310_6374, p310_6383), with the per-command caps above and
     a sweep cap of about $7.50** (median about $5.60 plus the unrecorded planner calls).
   - (b) Run 6335 only now; P3.10's scripts after decisions 1-5.
   - (c) Defer.
