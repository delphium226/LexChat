# Parallel batch 9, agent A: P3.12's per-run slot, reserved before the await ($0, no external call)

**Branch:** `worktree-agent-af47b226aecd2d96c`. **Base:** `<INTEGRATOR_HEAD>` = `ca3d45c`. The worktree came
up on `main` (`a6b4a76`) with no commits, so I ran `git reset --hard ca3d45c` before anything else, as
the lessons say. No other commit reached my branch while I worked.

**Commits:**

- `7be6482` fix(prepilot): P3.12's per-run slot reserved before the fetch's await (batch 9 A);
- this note.

**Spend:** $0. No model call, no live call to any host, no server, no replay.
**Tests:** full suite **2490 passed** on `lexchat_test_a` (base 2482, plus 8 new).
**Scratch:** my worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch9/A/`, copied at the end to
`C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch9/A/`. Every script below is there, and every
command runs from that folder unless it says `server_py/`.

---

## 1. What changed, and why

**The defect** (batch 8 A2, section 3). `chat_loop` runs one ReAct round's tool calls as concurrent tasks
(`asyncio.create_task` for each, then `asyncio.gather`). `schedule_route_block` checked its per-run bound
(`len(fetches) >= MAX_PROVISION_FETCHES`) and its memo (`lid not in fetches`) before
`await fetch_provision_list(...)`, and wrote `fetches[lid]` after it. So every call of a batched round
passed the check:

- the bound could be exceeded (Session 40's sweep: 6 list reads against 5 in one Deep Research step);
- one instrument could be read twice in a round.

The fallback (`fetch_text_with_schedules`, after a failed list) had the same shape:
`if "text" not in outcome` before the await, the write after it.

**The change** (`server_py/src/agent/agent_shared.py` only; `agent_core.py` unchanged).

- **New `_fetch_once(holder, key, fetch, bound=None)`.**
  - It reserves the slot before the await, and counts it against `bound`: the check and the
    reservation run with no await between them.
  - While the read is in flight, `holder[key]` holds an `asyncio.Future`. Every other call for that key
    waits on it through `asyncio.shield`, so a waiter cancelled mid-read cannot cancel the shared Future
    and take the result from the others.
  - A value `fetch()` returns is recorded in the slot. That includes `{"status": "failed"}`, exactly as
    today: it counts against the bound, is not read again, and the fallback runs from it.
  - A read that raises releases the slot (nothing established, nothing counted), wakes its waiters with
    None (they append nothing), and re-raises. `fetch_provision_list` and `fetch_text_with_schedules`
    catch every `Exception`, so the only thing that raises is a `BaseException`: a cancelled round.
- **The route** reads the list through `_fetch_once(fetches, lid, ..., bound=MAX_PROVISION_FETCHES)`,
  and returns "" on None (refused by the bound, or the read it waited on was abandoned). That is the
  same "" a bound refusal returned before.
- **The fallback** reads the whole text through `_fetch_once(outcome, "text", ...)`, so a round's calls
  on one failed instrument share one `/legislation/text` read too.
- **Docstrings:** `schedule_route_block` and `run_worker_tool`'s `provision_fetches` say that a slot
  holds a Future while its read is in flight.

**Who reads the dict** (grep over `server_py/src`: `provision_fetches`, `held_provision_list`,
`provision_list_facts`). Only two readers:

- the route, which fills it;
- A2's `held_provision_list`, at P3.1's refusal in `run_worker_tool`.

`held_provision_list` passes the slot to `schedule_units.provision_list_facts`. That function returns
None for anything that is not a dict with `status` "ok", `complete` true and at least one row. So:

| Slot state | What P3.1's cap text reads |
|---|---|
| a read in flight (a Future) | None: P3.1's refusal, limb and footer exactly as before (test 4) |
| a released slot (key absent) | None |
| a failed read (`{"status": "failed", ...}`) | None |
| a complete list | its facts, after the slot is replaced by the outcome (test 4; A2's own tests, which mutant s9 breaks) |

Nothing else in `src` or `tools/` iterates the dict. In `tools/replay_report.py` the route's
`-provision-list` api calls are not read at all; only `cmd_corpus`'s leak list names the block.

**Calls made one at a time read exactly what they read before.** No call ever finds a slot in flight,
and every slot ends as the same outcome dict. This is checked by the dry run's sequential mode
(section 2) and test 7.

**The audit trace.** In a round with several calls on one instrument, the single `-provision-list`
call (and any `-text-with-schedules` call) is recorded under the tool record of the call that made the
read, whichever reached the route first. The other calls carry the block with no api call. A later
round's memoised use already looked like that. No schema change.

**No text the product writes is new or reworded**, so no detector screen applies. The texts beside this
one, for the same instrument:

- P3.12's block and lines: unchanged.
- A2's refusal, limb and footer: unchanged on a complete slot, byte-identical otherwise (test 4).
- P3.27's `schedules_note`: another tool.
- P4.17's section-search line and P3.1's cap: unchanged.

None of them contradicts another because of this change. The one text effect, a call the bound now
refuses in a batched round, is in section 2.4 and decision 1.

---

## 2. Measured first, then the dry run with the built code

### 2.1 How a stored round is found

The audit records no round number. Each tool record has `started_at` and `duration_s`.

`python gaps.py` reads every consecutive pair of calls inside one delegation: 16,016 gaps in 2,490
delegations, none without `started_at`.

| Gap | Count |
|---|---|
| 0 to 0.01 s | 5,835 |
| 0.04 to 0.174 s | 13 |
| 1.753 s or more | 10,168 |
| anything between | 0 |

The 13 middle gaps fit P3.25's code lookup, which the quick-lookup Worker awaits before a search
starts its record. So a gap above 1.0 s starts a new round.

**Check (passes):** in every delegation, no round starts before the previous round's last call ended
(`round_order_violations` 0 in every run of `dryrun_slot.py`).

### 2.2 The counts

Over all 59 replay directories, `wave4_b8_sweep` included; none excluded.

| Rounds | Count |
|---|---|
| all rounds | 12,631 |
| with a section search | 3,671 |
| **with more than one section search** | **978** |
| in which the route fires | 228 (47 of them with more than one section search) |
| in which the route fires on more than one call | 12 |

The route fires on 257 calls in all.

### 2.3 The dry run

`dryrun_slot.py` is A2's `dryrun_p312.py` pattern, copied and repointed.

- `DRYRUN_WT` names the tree, and the script asserts every module came from it.
- Every stored delegation is replayed round by round. Each round's firing calls are run through that
  tree's `schedule_route_block`, concurrently with `asyncio.gather` as `chat_loop` runs them.
- Only calls the route runs for are replayed: not memo hits, not refused calls. A call whose query
  names no missing unit returns "" before any await, so it cannot touch the dict.
- The tree's own `fetch_provision_list` is served batch 7 B's saved live `/section/lookup` payloads
  through an httpx MockTransport whose handler yields, as a real read does. An instrument with no saved
  payload gets a 503, and the fallback text also 503s.
- The summariser is stubbed, the threshold is 8,000, and the context budget is not modelled.

Three timing modes:

- `seq`: every call awaited in turn.
- `model`: each call reaches the route at its stored start offset in the round, plus its stored
  duration, less the route's own recorded calls. A list is answered after batch 7 B's recorded elapsed
  time for it (150 ms if none), a text after 400 ms. All times are scaled by 0.05.
- `burst`: the whole round reaches the route at once, the worst case for the race.

Commands:

- old code: `DRYRUN_WT=<scratch>/prev DRYRUN_MODE=<m> DRYRUN_OUT=prev_<m>.json python dryrun_slot.py`,
  where `prev/` is `git archive ca3d45c server_py/src`;
- built code: the same with `DRYRUN_WT=<worktree>/server_py DRYRUN_OUT=new_<m>.json`;
- comparison: `python compare_slot.py > compare_slot.txt`.

`sh run_committed.sh` re-ran the built side on the committed tree (`7be6482`): calls, rounds and mock
calls are identical to the run taken before the commit, in all three modes (`run_committed.txt`).

**List reads over the corpus:**

| Mode | Old code (`ca3d45c`) | Built code |
|---|---|---|
| seq | 172 | 172 |
| model | 174 | 172 |
| burst | 175 | 172 |

Text reads are 1 in every cell.

**Every round whose read count changes** (`compare_slot.txt`):

| Round (dir, run, turn, delegation, round) | Calls fired | Instruments | Old reads | Built reads | Modes |
|---|---|---|---|---|---|
| `wave4_b8_sweep`, 6374 rep 1, turn 4, delegation 2 (Deep Research step 3), round 2 | 6 | 6 | 6 | 5 | model, burst |
| `wave4_p32_pre`, p32_6406 rep 2, turn 9, delegation 0, round 1 | 2 | 1 | 2 | 1 | model, burst |
| `baseline`, 6406 rep 1, turn 7, delegation 0, round 2 | 2 | 1 | 2 | 1 | burst only |

In `seq` mode no round moves: 0 of 228 rounds, 0 of 257 blocks.

**The built code under concurrency equals the built code one call at a time.** `new_seq` against
`new_model` and against `new_burst`: 0 rounds and 0 blocks move.

**The 12 rounds in which the route fires on more than one call.** Reads shown as seq/model/burst,
from `python multi_rounds.py > multi_rounds.txt`.

| Round | Calls | Instruments | Old | Built | Live recorded |
|---|---|---|---|---|---|
| baseline, 6406 r1, t7, d0, r2 | 2 | 1 | 1/1/2 | 1/1/1 | 0 |
| wave1, 6335 r1, t7, d1, r2 | 3 | 1 | 0/0/0 | 0/0/0 | 0 |
| wave2_p22_final, 6367 r2, t1, d3, r4 | 2 | 2 | 2/2/2 | 2/2/2 | 0 |
| wave2_p23, 6374 r1, t3, d0, r1 | 5 | 5 | 5/5/5 | 5/5/5 | 0 |
| wave2_p23, 6374 r2, t4, d2, r1 | 3 | 3 | 3/3/3 | 3/3/3 | 0 |
| wave2_p27_pre, 6374 r1, t4, d2, r1 | 5 | 5 | 5/5/5 | 5/5/5 | 0 |
| wave2_p27_pre, 6374 r2, t4, d2, r1 | 5 | 5 | 5/5/5 | 5/5/5 | 0 |
| wave2_p27, 6374 r3, t4, d2, r2 | 4 | 4 | 4/4/4 | 4/4/4 | 0 |
| wave2, 6369 r1, t5, d0, r6 | 2 | 2 | 2/2/2 | 2/2/2 | 0 |
| wave4_b8_sweep, 6374 r1, t4, d2, r2 | 6 | 6 | 5/6/6 | 5/5/5 | 6 |
| wave4_p32_pre, p32_6406 r2, t9, d0, r1 | 2 | 1 | 1/2/2 | 1/1/1 | 0 |
| wave4_p32_pre, p32_6406 r2, t9, d0, r2 | 2 | 1 | 0/0/0 | 0/0/0 | 0 |

"Live recorded" is 0 wherever the route did not exist when the run was made. A 0 in the old and built
columns is a round whose instrument an earlier round had already read.

**Check of the concurrency model against live (passes).** In the sweep, the only directory where the
route ran live, the old code in `model` mode makes the same list reads per round as the run recorded:
18 of 18 rounds (`compare_slot.txt`, last section).

### 2.4 Does any output text move?

**With the saved payloads alone, no.** 0 of 257 firing calls' blocks move, in any mode.

That 0 hides one move, in the sweep's round. Five of its six instruments have no saved payload (batch 7
B never read them), so both trees get a 503. Their queries name "the Schedule" with no label, and on a
failed list the route appends nothing, in either tree.

**Reconstruction.** `python sweep_blocks.py` (`sweep_blocks.txt`) lists the sweep's 22 recorded list
reads, and writes `synth_lookups.json`: for each of the 5 unsaved instruments whose live block was the
none-held line, a synthetic list with the recorded number of non-schedule rows (2 to 4). That line
depends only on the count and on the schedule and annex inventory.

Then `sh run_sweep.sh`, then `python compare_sweep.py > compare_sweep.txt`:

- **The reconstruction holds.** The old code's simulated block headers equal the live ones in 23 of 23
  firing calls in `model` and `burst`, with 22 list reads, as recorded.
- **Exactly one block moves.** With the built code, the sweep's step-3 round makes 5 reads, and the
  sixth call (tool 7) loses its none-held line (205 characters) and gets nothing.
- **That is the bound refusing the sixth instrument, as specified.** The old code run one call at a
  time also refuses it: `seq` mode's simulated header for tool 7 is empty against the live 205
  characters, the only seq mismatch.

So the answer is: **one block in the stored corpus moves, by design.** It is the call the bound now
refuses, where the race had let it through. Every other block is byte-identical.

**Which call is refused depends on which search returns last.**

- In the model, tool 7 arrives last. It is not the instrument of P3.27's 6374 guard: that one is tool 2,
  batch 7 B's saved 3-provision list, which arrived first.
- But that same step later hit P3.1's cap on the guard's instrument (tool 11 refused; tools 2, 8, 10 and
  11 are on it).
- So in a re-run where the guard's instrument returns last, A2's fix 2 would have no list for it in that
  step, and P3.1's old "may still be in it" text would come back. This is decision 1.

`python per_run_instruments.py > per_run_instruments.txt` counts the distinct instruments the route fires
on per worker run, over all stored runs:

| Instruments | Runs |
|---|---|
| 1 | 131 |
| 2 | 3 |
| 3 | 2 |
| 4 | 1 |
| 5 | 2 |
| 6 | 3 |

All 3 runs over the bound are 6374 (`wave2_p23` r1 t3; `wave2_p27_pre` r1 t4 step 3; `wave4_b8_sweep`
r1 t4 step 3). In the two older ones the sixth instrument came in a later round, so both trees refuse it.

**A detector for the sweep hand-read.** `python bound_refusals.py <replay dir>` lists every firing call
that got no block and no read of its own because the run had already read 5 lists.

- Over all 59 directories: 0.
- On a copy of the sweep's 6374 rep 1 with tool 7's read and block removed (the built code's shape;
  `python bound_refusals_check.py`, `bound_refusals_check.txt`): exactly that call.

---

## 3. Tests (`server_py/tests/test_schedules.py`, a new "batch 9 A" part at the end)

All synthetic (`ssi/1901/3` and other `ssi/1901/N`, "Widget Order 1901"). A yielding stub of
`_request_with_retry` makes the calls of a gathered round overlap, and each async test runs under a 10 s
deadline, so a call left waiting on a slot fails instead of hanging.

1. `test_a_round_of_searches_on_one_instrument_makes_one_fetch`: three gathered calls on one instrument
   make one list read; each output equals the one it gives alone; the slot ends as the outcome.
2. `test_a_round_on_more_instruments_than_the_bound_fetches_only_the_bound`: n+1 instruments gathered
   make n reads; the last call is refused (""), as today; the dict holds n.
3. `test_a_failed_list_and_its_fallback_text_are_fetched_once_for_a_round`: a 503 list makes one list
   read and one text read for three gathered calls, with outputs equal to the sequential one. The failed
   outcome is recorded (it counts against the bound, and a new instrument is then refused), and
   `held_provision_list` is None.
4. `test_an_in_flight_slot_is_counted_and_is_never_a_complete_list` (A2's reader): while a read is held
   in flight, the slot is reserved and counted, `held_provision_list` and `provision_list_facts` are
   None, and P3.1's refusal through `run_worker_tool` equals `section_stop_message(...)` with no
   `provision_list`. After the read, the facts are those of the complete list.
5. `test_a_cancelled_read_releases_its_slot_and_its_waiters_get_nothing`: the owner cancelled mid-read
   raises `CancelledError`; its waiter returns "" without hanging; the dict is empty; a later call reads
   again.
6. `test_a_waiter_cancelled_mid_read_costs_no_other_call_its_result`: the owner and another waiter still
   get their blocks from the one read.
7. `test_calls_one_at_a_time_read_what_they_read_before`: the sequential case (cut, whole, absent,
   annex chapter, a second and third instrument); every slot ends as a plain outcome.
8. `test_a_gathered_round_through_run_worker_tool_reads_one_list`: the real path, two section searches
   of one round through `run_worker_tool`.

**Revert.** Restoring `agent_shared.py` to `ca3d45c` on a scratch copy removes **65 lines** (and
restores 14). **7 of the 8 tests fail**, each on behaviour: extra reads, an empty dict where a
reservation should be, a waiter hanging until the deadline. Test 7 passes on both by design: the old
sequential behaviour is the specification, and the dry run's `seq` mode is the corpus evidence for it.

**Single-site mutants.** `python spec_slot.py`, then `python mutants.py spec_slot.json`
(`mutants_slot.txt`; A2's runner, copied, with a deadline and the failing names). Each mutant runs
`test_schedules.py`, `test_section_budget.py` and `test_search_scope.py`.

| # | Mutant | Fails |
|---|---|---|
| s0 | full revert | 7 |
| s1 | slot reserved after the await | 7 |
| s2 | a call finding a read in flight does not wait | 5 |
| s3 | the wait not shielded | 1 (test 6) |
| s4 | a raised read keeps its slot | 1 (test 5) |
| s5 | a raised read never wakes its waiters | 1 (test 5, by the deadline) |
| s6 | a cancelled read swallowed | 1 (test 5) |
| s7 | the bound ignored in the helper | 3 |
| s8 | the bound counts only finished reads | 1 (test 2) |
| s9 | the slot keeps the Future after the read | 9, A2's three among them |
| s10 | the waiters never resolved | 4 (by the deadline) |
| s11 | the route passes no bound | 3 |
| s12 | a refused or abandoned slot not checked | 4 |
| s13 | the fallback text not shared | 1 (test 3) |
| s14 | `whole or ""` cleaning removed | **0: survives, equivalent** |

s14 survives because `cut_unit_from_text` opens with `text = full_text or ""` (`schedule_units.py`
line 640). The caller's `or ""` repeats it, as the old line `outcome.get("text") or ""` did; it was kept
to keep the call the same as before.

**Full suite:** `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_a python
-m pytest -q` in `server_py/`: **2490 passed**.

---

## 4. Input forms no stored run contains, tested on synthetic input

- A failed list read inside a batched round: every live list read on record returned 200, and the dry
  run's failures are the mock's 503s (test 3).
- A text fallback shared by a round: the corpus makes 1 text read in all (test 3).
- A cancelled read (a user abort mid-round), and a cancelled waiter (tests 5 and 6).
- P3.1's refusal reading a slot whose read is in flight (test 4). This cannot happen within one round,
  because P3.1 counts rounds and so refuses every call on an instrument in a round or none. It is tested
  at the seam.
- More instruments in one round than the bound: one stored round, reconstructed (section 2.4), and
  test 2.

## 5. What I did NOT do

- No live call, no model call, no server, no replay.
- I did not change the bound's value (decision 1), or `agent_core.py`.
- I did not edit `docs/api/AUDIT_TRACE.md` (decision 2), `FIX_PLAN.md`, `SESSION_LOG.md`, `CHANGELOG.md`,
  `CLAUDE.md`, `tools/replay_report.py`, a rubric or a memory file. No grader change is needed: the
  product writes no new text, and no grader reads the route's api calls.
- I did not push or merge.
- `plan_status` (54 of 78, 2 in progress, 8 of 14 buckets) and `plan_lint` (0 errors, 0 warnings) are
  unchanged; I changed nothing they read.

## 6. Decisions for the integrator or the user

1. **The per-run bound of 5 now holds inside a batched round**, so on 6374's Deep Research step 3 (six
   instruments in one round, the shape in 3 of the 142 stored runs where the route fires on an
   instrument) one call loses its block where the race let it through. If that call is the guard's
   instrument, A2's fix 2 has no list for it in that step.
   1. **(Recommended) Raise the provision-list bound to 8** before sweep 1, as its own constant rather
      than P3.7's `MAX_ROUTED_LOOKUPS`. With 8, no stored run reaches the bound (the most is 6), and the
      sweep's round makes the 6 reads it made live, with no block moving against the live run in
      `model` or `burst` (`sh run_bound8.sh`, `run_bound8.txt`). It is one line, and tests 2 and the
      existing bound test follow the constant.
   2. **Keep 5 as built,** and in sweep 1 run `bound_refusals.py` on the 6374 runs and say whether the
      refused instrument was the guard's. That risks a confound in the P1 re-run.
   3. **Keep 5 and have code say on a refused call that the per-run limit stopped the fetch.** That is
      new lawyer-reachable wording, a "limit" sentence beside a schedule, which `SCHED_LIMIT` reads; it
      needs the detector screen and the user's approval.
2. **The audit trace documentation.**
   1. **(Recommended) At the fold, add one sentence to `docs/api/AUDIT_TRACE.md`'s P3.27/P3.12 note:**
      one `-provision-list` read per instrument per worker run, recorded under the tool call that made
      it, including within a round. A harness counting reads per tool call would otherwise be surprised.
   2. **Leave it.** The shape is the one a memoised later round already had.
