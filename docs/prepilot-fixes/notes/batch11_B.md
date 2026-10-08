# Batch 11, agent B: P4.12 built (L1 + L2' + L3, gated; $0, deterministic acceptance)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every batch before. I had no commits, so I ran
`git reset --hard 024e396` (the `<INTEGRATOR_HEAD>`). This note and both product commits are based on `024e396`.

**Spend: $0.** No model call, no seam draw, no replay, no server, and no live call to any host (0 calls).
**Tests: 2872 passed** (`python -m pytest -q -p no:cacheprovider` from `server_py/`, with
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b`); 2833 at the base, plus 39 new.

**Model.** Every stored replay read here ran on the pinned `google/gemini-3.1-pro-preview`. The dollar figures use
P4.10's $12 per million output tokens.

**Scratch.** `docs/prepilot-fixes/evidence/seam/batch11/B/` in this worktree (gitignored by `.gitignore:113`,
`docs/prepilot-fixes/evidence/seam/`, checked with `git check-ignore -v`), copied to the main checkout's path of the
same name. The scripts import this worktree's built code by a hard-coded path (`SERVER`, `WT`): **to re-run them on
the merged tree, repoint that path in a copy.** They read every replay directory under `$PREPILOT_EVIDENCE/replay/`
(64 now, one more than batch 10 D saw), so a new directory changes the counts.

## 0. What was built, and where it differs from the brief

Commits: `3d774e2` (product and tests), `6b5224f` (three more Ollama tests), and a third that drops one test which
no product mutant could fail and adds this note.

On a **Manager** call only, that is the `chat_loop_fn` call in `process_user_request`:
- **L1:** a heavy empty (P4.10's `is_heavy_empty`) is not retried.
- **L2':** an upstream idle timeout is retried once, not twice.
- **L3:** the payload carries `max_tokens` = `WORKER_MAX_OUTPUT_TOKENS` (32,000). This applies on OpenRouter only,
  as for the Worker. Ollama takes the flag but not the cap.
- **Gated:** L1 and L2' apply only while a usable worker report is in hand. With none in hand, every retry is kept.

**Unchanged:** the planner (`draft_research_plan`), the Deep Research synthesis, the A4 reformat, the Worker
(`run_worker_agent`) and `matters.py`'s direct `chat_loop` call. Each of the first four is pinned by a test that
fails when a mutant makes it pass the flag.

**How the call knows a report is in hand: a flag from the Manager loop, not a guess.**
- `chat_loop` (both clients) takes two new keyword arguments: `manager_call: bool` and
  `manager_report_in_hand: Callable[[], bool]`.
- `process_user_request` passes `manager_call=True, manager_report_in_hand=lambda: bool(worker_reports)`.
- `worker_reports` is the very list P4.2's fallback reads: reports that are completed, non-empty and not lost.
  So the gate is open exactly when the fallback would show research rather than the bare `LOST_ANSWER_NOTICE`, and
  the two cannot disagree.
- The callable is read when the empty arrives, not when the Manager starts. A report that lands during round 0's
  tool call is in hand for round 1's empty.
- `empty_completion.report_in_hand_now` makes the read fail-soft: no callable, a non-callable, or a callable that
  raises all read as "no report in hand", which keeps today's retries.

**Where the built shape is more specific than the brief (for the integrator to relay):**
1. **L2' counts idle timeouts, not attempts.** A Manager call retries an idle timeout only if no earlier attempt of
   that call was one (`MANAGER_IDLE_TIMEOUT_RETRIES = 1`; `should_retry_empty(..., earlier_idle_timeouts=N)`; the
   clients keep the count). This differs from "no retry on attempt 2" only after a rate limit or a clean stop on
   attempt 1, followed by an idle timeout. There the idle timeout is the call's first and keeps its retry. No stored
   call has that shape (decision 2).
2. **The cap (L3) is on every Manager call; only L1 and L2' are gated**, as the user's decision reads ("gated so the
   Manager keeps its retry"). See decision 1.
3. **The flags are also forwarded through `research_halt.run_halt_writeup`** (P3.8's step-cap round), as P4.10 did
   for `worker_call`. So a Manager loop that reaches 20 rounds has its write-up round governed like its other rounds.
4. **The watch log for a capped call that was still writing** now covers a Manager call too ("Manager call reached
   the 32000-token output cap ... the answer may be cut"). This is log-only.

**Every function changed (collision note).**
- `agent/agent_core.py`: `process_user_request` only. That is its Manager `chat_loop_fn(...)` call (two keyword
  arguments and a comment) and the comment above P4.2's fallback. Nothing in `run_worker_agent`, `_build_step_brief`
  or `run_deep_research`.
- `agent/openrouter_client.py`: `chat_loop`.
- `agent/ollama_client.py`: `chat_loop`.
- `utils/empty_completion.py`:
  - `should_retry_empty`: new keyword arguments, all defaulted;
  - new `report_in_hand_now` and `MANAGER_IDLE_TIMEOUT_RETRIES`;
  - the P4.10 comment block corrected: "no heavy empty was ever measured there" is struck, and two Manager heavy
    empties are now recorded;
  - a P4.12 comment block.
- `utils/research_halt.py`: `run_halt_writeup` (two keyword arguments, forwarded).
- Tests:
  - new `tests/test_manager_lost_cost.py` (39 tests);
  - `tests/test_research_halt.py`: one explicit-signature fake (`_halting_chat_loop`) takes the two new arguments.
    It was the only fake in the suite that broke.

**No new lawyer-facing text.** The fallback header and `LOST_ANSWER_NOTICE` are unchanged. The only new string is
a log warning. The gate keeps the notice's own claim true: it says the model was empty "on every attempt", and it is
shown only when no report is in hand, which is exactly when all three attempts are still made. So nothing needed
screening against the detectors.

## 1. Measure first: D's measurement re-run (built helpers, this worktree)

Command, from `server_py/`: `python ../docs/prepilot-fixes/evidence/seam/batch11/B/p412_manager_b11.py` →
`p412_manager_b11.out`. This is D's `p412_manager.py`, copied and repointed to this worktree, with nothing else
changed. `diff` against D's stored `p412_manager.out` shows exactly two differences:
- the directory count, 63 → 64;
- the conversational clean-turn count, 1,091 → 1,096 (`wave4_b10_sweep`, one file).

Everything else is identical:
- the same 10 Manager-site calls (2 recovered, 8 unrecovered);
- the same per-call mechanisms;
- the same lever figures.

**The cap cannot bind on any stored clean Manager call (D's bound), confirmed over 64 directories.**
- The longest clean Manager window is 42 s in conversational turns (1,096 turns, p99 21 s) and 41 s in research
  turns (284 turns). Both are unchanged by the new directory.
- 42 s is about 7,600 tokens at the stored runaways' rate (~181 tokens/s), under a quarter of 32,000.
- This assumes a stable throughput. That is stated, not measured per call, as in D's note.

## 2. Dry run with the BUILT retry decision over the 10 stored Manager calls

Command, from `server_py/`: `python ../docs/prepilot-fixes/evidence/seam/batch11/B/p412_dryrun.py` →
`p412_dryrun.out`.

The script:
- builds D's 10 calls with D's own code (copied into `p412_dryrun_base.py`);
- imports `src.utils.empty_completion` from this worktree, and asserts both that it does and that
  `MANAGER_IDLE_TIMEOUT_RETRIES` exists;
- feeds each stored attempt's record (the same keys `build_probe` writes, so the record is the probe) to the built
  `should_retry_empty(manager_call=True, report_in_hand=..., earlier_idle_timeouts=...)`;
- counts a report as in hand when a delegation that ended before the call's Manager window has a non-empty report
  and `lost` null. That is the stored equivalent of `worker_reports`.

Rows are in the order of D's table (`notes/batch10_D.md` section 2.1), which names each call.

| # | recorded attempts | reports in hand | built attempts | removed | outcome |
|---|---|---|---|---|---|
| 1 | b, then answered | 1 | 2 of 2 | 0 | answer, unchanged |
| 2 | bbb | 1 | 2 of 3 | 1 (~132 s) | the same fallback with reports, sooner |
| 3 | bbb | 5 | 2 of 3 | 1 (~128 s) | the same fallback, sooner |
| 4 | bbb | 2 | 2 of 3 | 1 (~128 s) | the same fallback, sooner |
| 5 | bbb | 1 | 2 of 3 | 1 (~130 s) | the same fallback, sooner |
| 6 | aaa | 1 | 1 of 3 | 2 (~$1.51, ~693 s) | the same fallback, sooner |
| 7 | abb | 1 | 1 of 3 | 2 (~$0.01, ~409 s) | the same fallback, sooner |
| 8 | bbb | 1 | 2 of 3 | 1 (~130 s) | the same fallback, sooner |
| 9 | b, then answered | 1 | 2 of 2 | 0 | answer, unchanged |
| 10 | bbb | 3 | 2 of 3 | 1 (~128 s) | the same fallback, sooner |

**Totals:**
- 10 attempts removed, about $1.53 and 1,878 s, before L3.
- L3 on the 2 heavy attempts still made (calls 6 and 7, each capped at about 30,720 tokens): about $0.77 and 282 s
  more.
- **L1 + L2' + L3 together: about $2.30 and 2,160 s (36 minutes). This matches D's estimate ($2.30, about 2,150 s).**

**Checks, all pass:**
- **0 recoveries are given up.** Both recovered calls (1 and 9) answered on attempt 2, after one idle timeout, and
  L2' keeps that attempt.
- Every unrecovered call keeps its outcome: the fallback with the same reports.
- The gate was open on all 10 calls (at least 1 report in hand). That agrees with D's finding that every
  unrecovered call got the fallback with reports, not the bare notice.

**Input forms no stored run contains, tested on synthetic input instead:**
- a Manager empty with no report in hand: none at round 0, and none where only lost or empty reports are in hand;
- a rate limit or a clean stop followed by an idle timeout (`(d)`/`(c)` → `(b)`);
- an idle timeout followed by a heavy empty (`ba`);
- a Manager heavy empty on Ollama;
- a capped Manager answer that is still writing;
- a Manager loop that reaches the step cap.

**Not covered by the rule, and not stored on the Manager:** our own `httpx` read timeout (180 s, no response).
That is a raised exception, not an empty completion, and its retry is unchanged.

## 3. Acceptance (deterministic): tests at each seam, the revert and the mutants

The tests are in `tests/test_manager_lost_cost.py` (39). By seam:
- **`should_retry_empty` with a Manager flag, per mechanism:**
  - (a) is not retried with a report in hand, and is retried without one;
  - (b) on attempt 1 is retried;
  - (b) on attempt 2 is not retried with a report, and is retried without one;
  - the count is of idle timeouts, not attempts;
  - (c) and (d) are retried;
  - the last attempt is never retried;
  - the Worker's rules are unchanged;
  - the heavy threshold is P4.10's.
- **`report_in_hand_now`:** fail-soft.
- **OpenRouter `chat_loop` on a Manager call:**
  - the cap is present with or without a report, and on the Manager payload only;
  - a heavy empty takes 1 request with a report and 2 without;
  - idle, idle takes 2 requests with a report (records `(1, retried) (2, not retried)`) and 3 without;
  - idle, then an answer, is kept;
  - rate limit, idle, answer takes 3 requests;
  - a clean stop is retried;
  - the gate is read when the empty arrives (the report lands during round 0's tool call);
  - a gate that raises keeps the retries;
  - the flags reach the step-cap write-up;
  - a capped Manager answer is logged, and a plain call's cut answer is not.
- **Ollama `chat_loop`:**
  - heavy and idle follow the gate;
  - the count is of idle timeouts;
  - the flags are forwarded through the recursion and the write-up;
  - there is no cap.
- **Who passes it:**
  - `process_user_request` passes `manager_call=True` and a live gate (False, then True after a completed report);
  - a lost report and an empty report do not open the gate;
  - the planner, the synthesis, and the Worker with its reformat do not pass it.
- **End to end:** the real OpenRouter loop under `process_user_request`.
  - A heavy empty after a delegation reaches P4.2's fallback after one attempt. That is 2 requests in all (round 0,
    then one attempt), both capped, with one `react_turn: 1, retried: false` record.
  - Two idle timeouts reach the fallback after two attempts.
  - A reply lost before any research keeps all three attempts and then gets the bare notice (records
    `[True, True, False]`).
  - A heavy empty before any research can still recover.

**Revert.** Command (scratch folder): `python mutants.py` → `mutants.out`. It works on a scratch copy of
`server_py` (`scratch_srv/`), resets the files for each case and asserts that each anchor occurs exactly once.

The full revert sets the five product files back to `024e396`. It **removes 145 added lines and restores 21**
(`git diff --numstat 024e396 HEAD -- server_py/src`: 14/4, 23/2, 37/8, 65/7, 6/0). Under it, 33 of the 39 new tests
fail. The 6 that pass pin what must not change, and each fails against an over-broad mutant:
- the Worker's rules: `ec_worker_first_dropped`;
- the planner, the synthesis and the Worker do not pass the flag: `ac_planner_passes`, `ac_synthesis_passes`,
  `ac_worker_passes`;
- a reply lost before research keeps its retries: `ac_gate_true`, `or_gate_always_open`, `ec_gate_dropped`.

Per-file reverts:

| file reverted | new tests failing |
|---|---|
| `empty_completion.py` | fails at import (4 collection errors; the clients import `report_in_hand_now`), hence the mutants below |
| `openrouter_client.py` | 19 |
| `ollama_client.py` | 6 |
| `agent_core.py` | 4 |
| `research_halt.py` | 2 (plus P4.10's own write-up test) |

**Single-site mutants: 40, every one caught** (0 survived; the only line marked SURVIVED in `mutants.out` is the
unmutated baseline, `none`, 112 passed; `mutants.out` and `mutants_synthesis.out` list the failing tests for each):
- **every guard:**
  - L1 removed;
  - L2' removed, `>=` changed to `>`, and the constant set to 0;
  - the gate dropped, and the gate without `manager_call`;
  - the Worker branch dropped;
  - the last-attempt bound;
- **`report_in_hand_now`:** returns True on raise; a non-callable read as its truth value; the value ignored;
- **each client** (12 in OpenRouter, 8 in Ollama, which has no cap or cut-log):
  - the cap Worker-only, and the cap on every call (OpenRouter);
  - the flag not passed to the decision;
  - the gate always open (both), and never open (OpenRouter);
  - the counter never incremented, and incremented on every empty;
  - recursion without the flag, and without the gate;
  - the write-up without the flag, and without the gate;
  - the cut-log Worker-only (OpenRouter);
- **`research_halt`:** the flag dropped, and the gate dropped;
- **`agent_core`:**
  - the flag off;
  - the gate always True;
  - the gate evaluated once at the start;
  - the gate reading `manager_inputs` (which includes lost reports);
  - the planner, the synthesis and the Worker passing the flag.

**Check: the full suite on `lexchat_test_b` passes, 2872 passed** (`pytest_full.out`).

## 4. What the audit trace records, and whether `AUDIT_TRACE.md` needs a sentence

There is no shape change. `empty_completions[]` records keep their keys.

What changes is when a Manager call stops, with a report in hand:
- **heavy empty:** one record, `attempt: 1, retried: false`;
- **two idle timeouts:** `attempt: 1, retried: true`, then `attempt: 2, retried: false`.

With no report in hand, a Manager call leaves up to three records, as before.

**Check: the recorders read the new shapes.** `replay_report.empty_completion_call_records` groups both new shapes
into one unrecovered call (checked on synthetic records: `[('a', False)]`, `[('bb', False)]`). `lostcost`'s retry
yield counts only `retried: true` records, and `lost_sites` reads the answer's fallback opener, which is unchanged.

**Yes, `AUDIT_TRACE.md` needs a sentence.** Its `empty_completions` bullet now says that every non-Worker call
("the Manager, planner, synthesis") still retries both, and that is no longer true of the Manager. Proposed, for
the integrator, to follow the P4.11 sentence:

> **Since FIX_PLAN P4.12 (again no shape change), the Manager's own call follows suit while a usable worker report
> is in hand** (a delegation in the request returned a report that was not lost): its heavy empty is not retried
> (a single `attempt: 1, retried: false` record), and an upstream idle timeout is retried once, not twice (the
> second carries `retried: false`, so a Manager call can end at `attempt: 2`). With no report in hand the Manager
> keeps all three attempts. The planner and the Deep Research synthesis still retry every empty. A Manager call's
> payload also carries `max_tokens: 32000` on OpenRouter, which the trace does not record.

**The same staleness is in `CLAUDE.md`** (the "LLM stream retry" bullet: "A rate limit, and every non-Worker call,
keep the retry"). That is the integrator's file, so I have not edited it.

## 5. Other code texts beside this change

- **`agent_core.run_worker_agent`'s comment** ("The Manager, planner, synthesis and the A4 reformat do not pass
  it") is about `worker_call`, and is still true. It is unchanged, so I did not touch agent C's or E's function.
- **The P4.11 comment** in `empty_completion.py` says "on a Worker call only" of the no-retry rule. That stays
  true of the Worker's rule, and the new P4.12 block below it states the Manager's.
- **The P4.2 fallback comment** in `process_user_request` said "`chat_loop` has already retried three times". It
  now says "up to three attempts; since P4.12 fewer after a heavy empty or an idle timeout with a worker report in
  hand".
- Nothing contradicts the new rule.

## 6. What I did NOT do

- No seam draw, no replay, no server and no live call. The acceptance is deterministic by the user's decision.
- I did not build the row's lever (i), a retry with benignly changed bytes. It is deferred by the user's decision.
- I did not change the retry after a clean-stop (c) empty (D's aside: 0 of 12 ever answered). It is not booked.
- I did not touch the planner, the Deep Research synthesis, the A4 reformat or the Worker. I did not touch
  `run_worker_agent` or `_build_step_brief` (agents C and E).
- I did not edit `AUDIT_TRACE.md`, `CLAUDE.md`, `FIX_PLAN.md`, `SESSION_LOG.md` or the CHANGELOG.
- I did not measure a per-call throughput to tighten D's bound. The bound is on windows and a stated rate.

## 7. Decisions for the integrator and the user

1. **The cap (L3) on a Manager call before any report is in hand.**
   - **(a) Recommended: keep it ungated, as built.** No stored clean Manager call comes near it (42 s, about 7,600
     tokens), and a runaway with no report in hand is still retried, now at up to $0.38 an attempt instead of
     about $0.76.
   - (b) Gate the cap like L1 and L2'. An uncapped round-0 runaway that would have answered at about 62,900 tokens
     could then still answer, at about twice the cost. No stored Manager runaway answered.
2. **L2''s count.**
   - **(a) Recommended: count idle timeouts, as built.** A (b) that follows a rate limit or a clean stop is the
     call's first idle timeout and keeps its one retry, which is the measured case (all 3 (b) recoveries came on the
     retry after a first (b)).
   - (b) Count attempts: no idle-timeout retry from attempt 2 onwards. It is simpler, but it would give up that
     retry after a (d) or (c). No stored call tells the two apart.
3. **The audit and CLAUDE.md wording.**
   - **(a) Recommended: add the sentence in section 4 to `AUDIT_TRACE.md`'s `empty_completions` bullet, and
     correct `CLAUDE.md`'s "every non-Worker call" line to name the Manager's P4.12 rule.**
   - (b) Leave both until the next cut. A harness reading `attempt < attempts_max` on a Manager record would then
     have no written explanation.
4. **Ticking P4.12.**
   - **(a) Recommended: tick at merge, once the integrator's own revert and mutants agree.** The booked acceptance
     is deterministic, and every part of it passes here (section 3).
   - (b) Keep it `[~]` until a live Manager empty is observed under the rule. Such an empty is rare: 10 in 64
     directories.
5. **D's aside: no retry after a clean-stop (c) empty has ever answered (0 of 12).**
   - **(a) Recommended: leave it unbooked, as a watch item.** It costs seconds, not dollars.
   - (b) Book a row to stop retrying (c) on the Manager and the Worker.
