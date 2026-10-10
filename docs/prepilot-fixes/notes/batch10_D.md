# Batch 10, agent D: P3.10 re-booked and P4.12 measured ($0, no product code)

**Base.** The worktree came up on `main` (`a6b4a76`), like every batch before it. I had made no commits, so I ran
`git reset --hard 7c3c6ac` (the `<INTEGRATOR_HEAD>`). This note is based on `7c3c6ac`. Its only commit is this file.

**Spend: $0.** No model call, no seam draw, no replay, no server, and no live call to any host.
**Tests: 2783 passed** (`python -m pytest -q -p no:cacheprovider` from `server_py/`, with
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d`). Nothing under `server_py/`
changed.

**Model.** Every stored replay ran on the pinned `google/gemini-3.1-pro-preview`, with
`google/gemini-3-flash-preview` as the summariser. Every number below comes from that model. Prices use P4.10's
$12 per million output tokens.

**Scratch.** All scratch is in `docs/prepilot-fixes/evidence/seam/batch10/D/` (gitignored by `.gitignore:113`,
`docs/prepilot-fixes/evidence/seam/`; checked with `git check-ignore -v`), copied to the main checkout's path of
the same name. The scripts import this worktree's built `tools/replay_report.py` and `src/utils/*`, and use this
worktree for `git merge-base`. **To re-run them on the merged tree, change the hard-coded path (`SERVER`,
`sys_path_server`, `REPO`) to point at the merged tree.** Each script reads all 63 replay directories under
`$PREPILOT_EVIDENCE/replay/`, so a new directory would change the counts.

**Shape note (lesson 2).** I built nothing, so there is no built shape that could differ from the brief's.

---

## 1. P3.10: dependent Deep Research steps

### 1.1 Recount, split by era (the Session 15 regex, unchanged)

Command (from the scratch folder): `python p310_recount.py --detail` → `p310_recount.out`. `DEP` and the halt test
are copied verbatim from batch 5 C's `p310_dependent.py`. Each run file is put in an era by its own
`runtime_state.git_head`, using `git merge-base --is-ancestor` against P2.7 (`a38ff98`, the discovery budget),
P3.1 (`d2f9b48`, the section cap) and P3.8 (`1243cdd`, the write-up round). Every run file has a `git_head`.

| era (run file's head) | plans | plans with a dependent step | dependent steps | halted | other steps | halted |
|---|---|---|---|---|---|---|
| before P2.7 | 124 | 29 | 34 | **10 (29%)** | 412 | 53 (13%) |
| P2.7 to P3.1 | 34 | 8 | 11 | 2 (18%) | 119 | 2 (2%) |
| P3.1 to P3.8 | 4 | 0 | 0 | - | 16 | 0 |
| **after P3.8 (HEAD)** | 52 | 8 | **12** | **0** | 188 | 4 (2%) |
| all 63 directories | 214 | 45 | 57 | 12 | 735 | 59 |

**Check: the directory totals reproduce batch 5 C (passes).** Over the directories batch 5 C read, the per-directory
rows are identical (197 plans, 53 dependent steps, 12 of them halted). The three newer directories add 17 plans:
`wave4_b8_sweep` 3, `wave4_b9_sweep1` 8, `wave4_b9_sweep2a` 6.

**The halt premise does not hold at HEAD.** After P3.8, 0 of 12 dependent steps halted. The 4 halted steps at HEAD
are other steps: three are in 6374 turn 2 (`wave3_p38` r1, `wave4_b8_sweep` r1) and one is in 6375 turn 2
(`wave4_p33_post` r1). P3.8 wrote up all four.

**Where the shape still occurs.** At HEAD, all 12 regex matches are in two turns: **6374 turn 4** (9 steps over 5 plans:
`wave3_p38` r1-r3, `wave4_b8_sweep` r1 and `wave4_b9_sweep1` r1) and **6383 turn 4** (3 steps over 3 plans, `wave3_p38`).
In those two turns the planner writes a dependent step in **8 of 8 plans**. 6382 was last replayed in `wave2_p21`,
before P2.7, so its rate at HEAD is unknown.

### 1.2 What the regex matched and dropped at HEAD (every match and drop read)

- **Matches: 12, all genuine.** Each one is a step that works on "the identified Orders" (9) or "the identified SSIs"
  (3) that an earlier step produced. I read every matched phrase and step text (`p310_detail.txt`).
- **Drops.** A broader screen (`BROAD`: identified, previous, earlier, above, step N, these, those, ...) hits 12 other
  steps 2+ at HEAD. I read all 12:
  - **1 is an instrument-list dependency the regex misses:** `wave3_p38` 6374 r2 t4 step 4. It reads "the identified"
    followed by the class's full title, so `identified Orders` is not adjacent. It is added to the table as
    `hand-list`.
  - **7 depend on provisions, not on a list.** They work on "the identified provisions" or "these duties" inside
    instruments the question already names (6365 turn 1 ×6 across `wave3_p311`, `wave4_p45`, `wave4_p47` and
    `wave4_p47b`; 6374 turn 2 ×1). This is a different shape from P3.10's. They are listed as `hand-provision` and
    kept out of P3.10's counts. None of them halted.
  - **4 are not dependent:** "those titled ...", and two "these concepts" steps in 6375.
- **The regex is still approximate, as the row says.** At HEAD it caught 12 of the 13 list-dependent steps that the
  hand-read found.

### 1.3 Each dependent step at HEAD: cost, rounds, halt, and list match

The table is in `p310_recount.out` (one row per step). Rounds are rebuilt with the built `replay_report._rounds`.
**A step's cost is not recorded anywhere** (a delegation has no cost field). "Cost~" is therefore the turn's
`total_cost_usd` split across its steps by duration. The synthesis's share is included, so it is an upper estimate.

| post-P3.8 steps | n | halted | median s | median rounds | median tools | median `search_legislation` | median section searches | median summarised | cost~ median |
|---|---|---|---|---|---|---|---|---|---|
| dependent (regex) | 12 | 0 | 65 | 8 | 15.5 | 3 | 6.5 | 0 | $0.19 |
| dependent (regex + the hand-read list drop) | 13 | 0 | 67 | 8 | 16 | 3 | 7 | 0 | $0.20 |
| other steps 2+ | 128 | 4 | 74 | 5 | 12 | 2 | 2 | 3 | $0.225 |

**At HEAD, a dependent step costs no more than other steps.** It is not slower (65 s against 74 s) and its estimated
cost is not higher. It does take more rounds (8 against 5) and more section searches (6.5 against 2), because it
works through a list one instrument at a time.

**But every dependent step rediscovers its list.** All 12 ran their own `search_legislation`: 62 calls in total,
median 3, range 1 to 18 (`wave3_p38` 6374 r1 step 4 made 18). In every case those searches returned the earlier
step's instruments again (the `rediscov` column). No brief named any instrument by number (`brief_ids` 0 in 12 of
12), so P3.7's routed lookup never ran on these lists (`lk` 0).

**List match** (`p310_recount.py` and `p310_listread.py`):
- **What counts as the list:** the instrument ids that the earlier steps' report **bodies** link or cite (the
  code-appended `[SEARCH SCOPE]` block is cut off, because its change-record and revoked-title lines name ids the
  model never listed), restricted to the class the step names (Orders → `uksi`, SSIs → `ssi`).
- **What the step worked on:** the ids in its own `search_legislation_sections`, `get_legislation_text`,
  `get_legislation_changes` and `lookup_legislation` arguments.
- **A grader drop, found and fixed in scratch (lesson 3).** The first version matched only the `type/year/number`
  form, so it missed a step-2 list written as "(SSI yyyy/n)" in prose, in 6383 r1. Plain-text `SSI`/`SI`
  citations are now matched. Every number here is after that fix.

| result | steps (of 12) | where |
|---|---|---|
| worked on every listed instrument, nothing added | 7 | `wave3_p38` 6374 r1 s3, r2 s3; 6383 r3 s3; `wave4_b8_sweep` 6374 s3, s4; `wave4_b9_sweep1` 6374 s3, s4 |
| worked on every listed instrument, **plus one no earlier step had found** | 1 | `wave3_p38` 6374 r1 s4: its own search found a further instrument of the class. Rediscovery gained one here. |
| **dropped instruments the earlier step listed** | **4** | `wave3_p38` 6374 r3 s3 and s4 (2 of 8 each), 6383 r1 s3 (1 of 3), 6383 r2 s3 (1 of 2) |

The hand-read of the drops (in the scratch folder only, because the text names a matter):
- In 6374 r3, step 2 said in its own words that two further instruments designate bodies that belong in the answer.
  Steps 3 and 4 re-ran their own searches, worked on six instruments, and never touched those two.
- In 6383 r1 and r2, step 3 re-derived the list with its own searches and got a shorter one.
- **In all three turns, the dropped instruments still reached the answer**, because the synthesis sees every step
  (`p310_answer_check.py`: 3 of 3). What they did not get is the dependent step's work: the commencement and
  amendment check, or the extraction.

**Conclusion at HEAD.** The defect is no longer a halt, and a dependent step is not dearer than other steps. It is
that the step **re-derives the list instead of being handed it**: 12 of 12 re-searched (62 searches), and the
re-derived list differed from the earlier step's in 5 of 12 steps (4 shorter, 1 longer). Under the regex plus the
hand-read drop it is 6 of 13 (the hand-read step also added one instrument).

### 1.4 The options, sized on the stored plans

Command: `python p310_options.py` → `p310_options.out`. It covers all 148 post-P3.8 steps 2+. P3.7's routing is
counted with the built `utils.instrument_lookup.extract_instrument_citations`.

- **(b-ids) The executor hands on the list, not the prose.** For each step 2+, `run_deep_research` would add one
  code-written line to the brief, naming the instruments the earlier steps' report bodies link. Steps already run in
  sequence and `step_findings` is in hand, so this is a small change in `_build_step_brief`.
  - Size: median 3 ids per step (p90 6, max 10), roughly 200 characters.
  - Interaction: P3.7 runs a lookup on every instrument a brief names by number, so this line would trigger up to
    `MAX_ROUTED_LOOKUPS` = 5 lookups per step. Over the 52 stored plans that is 375 lookups, about 750 LEX calls:
    $0 in model spend, but load and latency.
  - The cap of 5 is below the 6 to 8 instruments in 6374's list.
  - Text that sits beside it: the CONTEXT sentence, "Research ONLY this step's task — the other aspects are covered
    by separate steps". The new line must not contradict it.
- **(b-full) The executor hands on the findings.** The median is 9,816 characters of earlier report bodies per step
  2+ (p90 20,204, max 29,511). That fits the 250,000-character Worker budget. But it hands summaries and glosses
  forward as if they were findings (P3.16's risk), and it breaks the steps' isolation the most.
- **(a) The planner merges identify, verify and check into one step.** This is a prompt change (Invariant 2 prefers
  code). There is no planner seam: `seam_replay` offers `synthesis`, `worker` and `manager` only, so measuring it
  needs new tooling or replays. A merged step carries one 8-round P2.7 budget and P3.1's per-run cap across the
  whole list, and the before-P2.7 era shows large steps halting (29%).

**Pricing a replay acceptance:**
- **Full sessions:** the stored full-session costs are 6374 $1.71 to $2.14 and 6383 $0.68 to $2.29. The $2.29 rep
  includes a Worker runaway, $1.62 of it in turn 3. So n=3 of both sessions comes to **about $8 to $12**.
- **Turn 4 only:** the Deep Research turn costs a median of $0.69 (max $0.86). A scripted run of turn 4 alone would
  cost **about $4 to $5**.

---

## 2. P4.12: Manager-side empty or stalled completions

### 2.1 Recount (all 63 directories)

Commands, from `server_py/`:
- `python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/wave4_b9_sweep2a lostcost --all-dirs` → scratch
  `lostcost_all.out`
- `... lost --all-dirs` → `lost_all.out`

The per-call detail is from `python p412_manager.py` → `p412_manager.out`. It uses the built `lost_sites`,
`empty_completion_call_records`, `empty_mechanism`, `slow_call_location` and slot medians.

- **Scope:** 2,172 turns, 1,544 of them at schema v3 or later, so only those carry empty-completion records.
- **All sites:** 69 calls came back empty at least once; 19 were recovered and 50 were not.
- **The Manager:** 10 calls landed there, 8 unrecovered and 2 recovered (both sites inferred from the timeline).
- **Check (passes):** the row's (b) figures reproduce. There are 8 Manager (b) calls, 6 unrecovered, and after a (b)
  the Manager's retry answered 2 of 15 (`lostcost`, "manager after (b): 15 retries; answered 2; 2 on an inferred
  site"). No Manager (b) call has been added since batch 5 C's count over 57 directories.

| directory / session / rep / turn | mode | attempts (tokens) | react_turn | window | s per attempt | lawyer got | turn $ (slot) | excess $ | excess s |
|---|---|---|---|---|---|---|---|---|---|
| `wave2` 6343 r1 t2 | research | b (138), then answered | 1 | 138 s | ~69 | answer | 0.04 (0.06) | -0.01 | 117 |
| `wave2_p24_final` 6385 r2 t3 | conv. | bbb (134-158) | 2 | 395 s | ~132 | P4.2 fallback + reports | 0.05 (0.04) | 0.01 | 779 |
| `wave3_p38` 6374 r1 t1 | conv. | bbb (129-151) | 5 | 385 s | ~128 | fallback + reports | 0.31 (0.09) | 0.22 | 468 |
| `wave4_b2_post` 6345 r3 t4 | conv. | bbb (146-190) | 2 | 385 s | ~128 | fallback + reports | 0.42 (0.21) | 0.21 | 495 |
| `wave4_b2_post` p32_6406 r1 t7 | conv. | bbb (222-266) | 2 | 390 s | ~130 | fallback + reports | 0.56 (0.15) | 0.41 | 582 |
| **`wave4_b9_sweep2a` 6363 r1 t3** | conv. | **aaa (62,914 ×3)** | 1 | 1,040 s | ~347 | fallback + reports | **2.38 (0.03)** | **2.35** | **1,074** |
| **`wave4_p33_post` 6370 r1 t2** | conv. | **abb (62,914, 409, 417)** | 1 | 613 s | ~204 | fallback + reports | 0.86 (0.10) | 0.76 | 609 |
| `wave4_p33_post` p32_6406 r3 t3 | conv. | bbb (171-174) | 1 | 389 s | ~130 | fallback + reports | 0.06 (0.12) | -0.06 | 363 |
| `wave4_p37_reach` p37r_6374 r1 t2 | conv. | b (259), then answered | 1 | 137 s | ~68 | answer | 0.09 (0.16) | -0.07 | 101 |
| `wave4_p41_pre` p41_6346 r2 t2 | conv. | bbb (130-149) | 3 | 384 s | ~128 | fallback + reports | 0.15 (0.07) | 0.08 | 420 |

How to read the table:
- **"Window"** is the gap outside every delegation that the call's `react_turn` names.
- **"Excess"** is per turn, against the median of clean turns in the same slot. 6385 r2 t3 also had a Worker (b) in
  the same turn.

**(a) heavy empties on the Manager: 2 calls, both unrecovered, both conversational.**
- What they added: $3.11 and 1,683 s over their slots.
- The retry after a Manager (a) answered **0 of 3**. Across every site, the retry after an (a) answered 2 of 15.
- Both calls ran at heads after P4.10 (`42951b4`, `e0bf656`). After P4.10 there are 5 Manager calls in 585 non-Deep
  Research turns at schema v3 or later; before it, 5 in 842 with no (a) among them (`p412_rates.py`). The numbers are
  too small to claim a trend: 2 in 585 against 0 in 842.

**(b) idle timeouts on the Manager: 8 calls; 6 unrecovered (every one `bbb`), 2 recovered on attempt 2.**
- What the 6 unrecovered added: $0.87 and 3,107 s. Each attempt took about 128-132 s, the upstream's idle limit, as
  in P4.11.

**Every Manager empty came after a delegation (`react_turn` ≥ 1 in 10 of 10).** So all 8 unrecovered calls were served
P4.2's fallback **with the worker reports** (8 of 8, read off the answer's opening line). None was served the bare
`LOST_ANSWER_NOTICE`. Retrying cost the lawyer 6 to 18 minutes, and in the end gave them the same fallback.

**Stalled but answered.** A runaway that ends in an answer leaves no empty record (P4.10's watch item). On clean turns
at schema v3 or later, the longest Manager window is:
- **42 s** in conversational turns (1,091 turns; median 8 s, p99 21 s);
- **41 s** in research turns (284 turns);
- 126 s for the Deep Research synthesis (112 turns; one turn over 120 s).

No clean conversational or research turn shows a long Manager call. I found no Manager runaway that answered.

**Errors.** 16 turns end in a non-ok status, and all 16 are `needs_clarification` (the planner asking). None is a
Manager error.

### 2.2 The retry's yield by attempt number (every site)

Command: `python p412_retry_index.py`.

| after | next attempt answered | came back empty |
|---|---|---|
| a | attempt 2: 1 | 8 |
| aa | attempt 3: 1 | 4 |
| ab | attempt 3: 0 | 3 |
| **b** | **attempt 2: 3** | 12 |
| **bb** | **attempt 3: 0** | **11** |
| c / cc | 0 / 0 | 6 / 6 |
| d / dd | 13 / 1 | 1 / 0 |

**The third attempt after two idle timeouts never answered (0 of 11, every site).** All 3 (b) recoveries came on the
second attempt. An aside, outside P4.12: no retry after a clean-stop (c) ever answered (0 of 12). P4.10 keeps
retrying (c) as a light empty. It costs seconds, not dollars, and is not a decision here.

### 2.3 What each candidate lever would have changed on the 10 stored Manager calls

Command: `python p412_manager.py` (its lever section).
- Each attempt's dollars are its tokens × $12 per million.
- Each attempt's seconds are its window ÷ attempts.
- L3 assumes an (a) attempt under a 32,000-token cap stops at ~30,720 tokens, as every capped Worker (a) since P4.10
  did (`lostcost`: 30,718 to 30,724).

| lever | attempts removed | $ saved | s saved | recovered calls given up |
|---|---|---|---|---|
| **L1** no retry after a heavy empty (P4.10 (ii) on the Manager) | 4 | 1.52 | 1,102 | **0** |
| L2 no retry after an idle timeout (P4.11 on the Manager) | 13 | 0.03 | 1,894 | **2** (`wave2` 6343 r1 t2; p37r_6374 r1 t2) |
| **L2' one retry, not two, after an idle timeout** | 6 | ~0 | ~776 | **0** (the third attempt answered 0 of 11) |
| **L3** a 32,000-token output cap on Manager calls | 0 | ~1.55 on the 4 (a) attempts | about half of each (a) attempt | 0 stored |
| **L1 + L2' + L3 together** | 10 | **~2.30** | **~2,150 (36 min)** | **0** |

**The two recoveries L2 would give up**, at 6343 r1 t2 and p37r_6374 r1 t2, came after one delegation. They would have
become P4.2's fallback with the worker report instead of a composed answer.

**L1 + L2' + L3 against all 8 unrecovered episodes.** Together those episodes added $3.98 and 4,790 s. The combination
removes about 58% of the dollars and 45% of the seconds, and changes no outcome on the stored data. The combined
seconds are summed by hand from the script's per-attempt figures: L1's 1,102 s, plus L2''s 776 s on the six `bbb`
calls, plus L3's half of the two remaining (a) attempts (about 178 s for 6363 and about 104 s for 6370, using that
call's average attempt length). Each episode keeps
its first attempt, so the lawyer gets the same fallback sooner.

**Can L3 bind on a healthy Manager call?** Not on any stored clean turn.
- The longest clean Manager window, 42 s, is about 7,600 tokens at the ~181 tokens/s the stored runaways ran at
  (62,914 tokens in ~347 s).
- By cost alone, 100% of clean conversational turns and 96% of clean research turns are under the price of 32,000
  output tokens (`lostcost`'s last table).
- The 4% of research turns cannot be bounded by cost, but their Manager windows are ≤ 41 s.
- This assumes a stable throughput. That is stated, not measured per call.

**Where a no-retry rule could hurt.** If the Manager's reply is lost **before any usable worker report exists**
(`react_turn` 0, or only lost reports in hand), giving up the retry would mean showing the bare notice. No stored
episode has that shape (0 of 10), and the rule can be gated on a report being in hand (decision 5).

**Lever (i), the row's own: retry with benignly changed bytes. Not measured, deliberately ($0 brief).**
- It is the only candidate that could turn a lost Manager reply into a composed answer.
- None of the 10 Manager calls rebuilds on an existing seam. All are at `react_turn` ≥ 1, and `manager --first-round`
  draws round 1 only. It would need new Manager as-sent tooling.
- On the Worker, `worker --as-sent --at-rev recorded --date recorded` on the stored (b) payloads costs about $0.02 a
  healthy draw and $0.77 a runaway ($0.37 with `--max-tokens 32000`).

**Stale product comment (for the build, not changed here).** `server_py/src/utils/empty_completion.py`'s P4.10 block
says "no heavy empty was ever measured there" of the Manager, the planner and the synthesis. Two Manager (a) calls
are now measured.

---

## 3. What I did NOT do

- No product code, no grader change, no seam draw, no replay, no live call.
- I did not grade the depth or the correctness of any answer. I did not make a legal judgement on whether the
  instruments a dependent step dropped belong in its list; I read what the earlier step said about them.
- I did not measure the planner: its calls are outside the audit trace, and there is no planner seam.
- I did not measure the Deep Research synthesis's empties under P4.12: no (a) or (b) synthesis call is stored.
- I did not rebuild any Manager payload.
- I did not re-measure 6382, last replayed before P2.7.
- Nothing here needs a change to `replay_report.py`. **A suggestion for agent E or later:** `lostcost` does not print
  `react_turn` or seconds per attempt for a Manager call, and `p412_manager.py` shows both. That is optional
  tooling, not a fix.

## 4. Decisions for the integrator and the user

1. **P3.10's acceptance, re-booked.**
   - **(a) Recommended: book it on list match and rediscovery, with the halt kept only as a guard.** Replay n=3 on
     6374 turn 4 and 6383 turn 4 (Deep Research, pinned Gemini). It passes if:
     - every step that works on a list an earlier step produced works on every instrument of the named class that
       the earlier steps' report bodies list (before: 7 of 12 matched exactly, 4 dropped, 1 added; `p310_recount.py`
       plus a hand-read of every drop);
     - such a step's own `search_legislation` calls fall (before: 62 over 12 steps, median 3);
     - no step halts, and `sources_kept` per turn does not fall (`discovery --before`).

     About $4 to $5 as scripted turn-4 runs, or $8 to $12 as full sessions.
   - (b) Close P3.10 as not reproduced at HEAD (0 of 12 halted; the dropped instruments reach the answer through the
     synthesis), with a watch item on list mismatch.
   - (c) Keep the halt acceptance. Not recommended: it passes with no change.
2. **P3.10's lever.**
   - **(a) Recommended: the executor hands on the list in code (b-ids).** One code-written line per step 2+ in
     `_build_step_brief`, naming the instrument ids that the earlier steps' report bodies link. It is dry-run above
     (median 3 ids). It would also trigger up to 5 P3.7 lookups per step (about 750 LEX calls over the stored
     plans), and its wording goes to the user. Building it requires deciding whether it goes to every step 2+ or
     only to regex-flagged steps.
   - (b) The planner merges identify and filter into one step. This is a prompt change with no seam to measure it
     on, and merged steps run under one discovery budget.
   - (c) The executor hands on the full findings (median 9,816 characters). This carries the summariser-gloss risk
     forward.
3. **P4.12: extend P4.10's no-retry rule to the Manager?**
   - **(a) Recommended: yes for a heavy empty (L1) and with the 32,000-token cap (L3), and cut the idle-timeout retry
     from two to one (L2').** On the stored calls this saves about $2.30 and 36 minutes over 8 episodes and gives up
     no recovery.
   - (b) L1 and L3 only, leaving the Manager's (b) retry as it is.
   - (c) L1, L2 and L3: no retry after any slow empty. This saves about 900 s more than (a) (2,791 s against 1,878 s
     before L3), but gives up the 2 of 15 (b) recoveries, which would become fallbacks.
   - (d) Nothing, if the rate stays low: 10 Manager calls in 1,427 non-Deep Research v3 turns.
4. **P4.12's acceptance, booked before any build.**
   - **(a) Recommended: deterministic, on P4.10's and P4.11's pattern, with no replay and no seam draw.** Unit tests
     at each seam, each shown to fail with its change reverted, plus single-site mutants for every guard:
     - `should_retry_empty` with a Manager flag, for (a), (b) on the first and on the second attempt, (c) and (d);
     - both clients' `chat_loop` on a Manager call;
     - the cap on the Manager payload only;
     - a Manager heavy empty reaching P4.2's fallback after one attempt.

     Supporting figures, not pass conditions: the attempts it removes on the stored calls (§2.3), and the bound that
     the cap cannot bind on a clean Manager call (§2.3).
   - (b) The same, plus a Manager as-sent seam A/B on 6363 r1 t3. This needs new tooling, and a runaway draw costs
     about $0.77 uncapped.
5. **When there is no worker report, keep the Manager's retry?**
   - **(a) Recommended: yes.** Gate the no-retry rule on a non-lost worker report being in hand, so a reply lost
     before any research never falls to the bare notice. No stored episode has that shape.
   - (b) Apply the rule to every Manager call. This is simpler, and identical on the stored data.
6. **P4.12's scope on the ledger.**
   - **(a) Recommended: widen P4.12's title to "a lost Manager reply" (both mechanisms).** One lever in
     `should_retry_empty` covers both. Session 41's annotation already put the (a) evidence on this row.
   - (b) Book the Manager's heavy empty as a new row, per the re-planning protocol's "new findings become new rows".
7. **P4.12's lever (i), a benign-bytes retry: when?**
   - **(a) Recommended: defer.** Decide after decisions 3 to 5 are built, measuring the Worker half first
     (`worker --as-sent --at-rev recorded --date recorded`, capped) only if lost Manager replies still matter.
   - (b) Measure it now (paid seam draws plus new Manager tooling).
