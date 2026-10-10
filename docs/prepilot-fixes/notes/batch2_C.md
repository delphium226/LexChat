# Parallel batch 2, agent C: P3.17 (a general rule's application provision)

Session 34, 2026-10-01. Branch `worktree-agent-a2050b9e7537fe878`. **The worktree came up on
`main` (`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard 578718f23309e89330d9920cbc8b3512d744042d` before any work.** Seam and live-Worker
draws only; no server, no replay, rubrics untouched.

This note gives counts and locations. It quotes no answer or report text and names no instrument
from the session, because the draws name a matter. Three general-rule instruments recur, so they
are lettered:

- **R**: the older interpretation order the booked criteria require turns 1 and 2 to name;
- **N**: the newer Scottish interpretation Act;
- **U**: the UK interpretation Act.

All draws and the scratch scripts that made them are in the gitignored
`evidence/seam/batch2/C/` (`scripts/` holds every script named below; `scripts/` is the only copy).

## The row's acceptance, and whether it is met

**Acceptance (FIX_PLAN P3.17):** P3.3's 6338 criteria, n=3, in the lawyer's configuration
(Conversational, legislation and case law). Per rep: turns 1 and 2 name R; no turn asserts that N or
U governs the Act asked about or the inserted section; turn 3 says the Act sets no order.

**Not met, and not measured.** It is a replay criterion, and the after-column is the integrator's.
The seam and live-Worker evidence below supports putting the lever into that after-column, with the
cost noted under "What the lever costs".

## Step 1 (free): where the regime is lost at turn 1

Over every stored 6338 rep in the lawyer's configuration (`wave4_p33_pre`, `wave4_p33_post`,
`wave4_b1_post`, 3 reps each), turns 1 and 2, split by stage. Produced by
`python scripts/seam_locate.py` (tags each brief, tool call, raw result, summary, report and answer
for R/N/U), the provisions listing in this note's last section, and
`python -m tools.summary_probe count --dir <the three paths>`.

**Turn 1: never searched for.**

- **Brief:** the first delegation brief names only the Act asked about in **9 of 9** reps. It asks for
  the word's definition in that Act.
- **Worker search and retrieval:** the Worker searches that Act, sends a section search for the word
  (and, in 6 of 9, for "interpretation"), finds the word undefined and writes its report. **No general
  interpretation legislation is searched in any of the 9 first delegations.**
- **Summaries:** in `wave4_p33_pre` (before Session 32's source rule) the summariser wrote N or U into
  6 turn-1 summaries whose raw text lacks it (4 more at turn 2; 10 in all, matching
  `summary_probe count`). In `wave4_p33_post` and `wave4_b1_post`, no turn-1 summary carries a regime
  except in the one delegation that retrieved one.
- **Report and answer:**
  - `wave4_p33_pre`: N asserted in 2 of 3 answers. One of those (r1) came from a report naming no
    regime, so the Manager added it.
  - `wave4_p33_post`: r2's Manager re-delegated for N's definition. That Worker retrieved N's
    definitions schedule and not its application section, and the answer asserted N (the P3.17 shape).
    r1 and r3 named no regime.
  - `wave4_b1_post`: 0 of 3 name a regime. r1 and r3 point to "the general rules" for Acts of that date
    without naming one; that is the Manager holding back under P3.3's rule, as designed.

So the regime is not retrieved and dropped, and not retrieved and left unnamed. **At turn 1 it is
never retrieved**:

- the Manager scopes the brief to the Act (its prompt's own example brief is "Find the definition of
  X in Act Y");
- the quick-lookup Worker is told "Do not broaden the scope".

The row's first candidate (code that fires when a Worker cites a general-rule instrument) would
not fire at turn 1, because no such instrument is cited there.

**Where a regime was retrieved (turn 2, and r2's second turn-1 delegation), the row's diagnosis holds
exactly:**

- **Section searches of N for the word itself:** 5, in 5 turns. They returned N's definitions schedule
  and **never** its application section (0 of 5). Listing: provisions named in each raw result,
  scratch one-liner over the run files; the integrator can re-derive it with `seam_locate.py`.
- **Section searches of N for "application", "application of this Part" or "commencement":** 3, in
  2 turns. They returned the application section **3 of 3** times.
- **Turns where N was retrieved by the word only:** `wave4_p33_post` r2 t1, r3 t2; `wave4_b1_post`
  r2 t2. A wrong-regime claim was made in **3 of 3**. The last is Agent A's item 5, the side-by-side
  claim.
- **Turns with an application query:** `wave4_p33_post` r1 t2 and `wave4_b1_post` r3 t2. Both were
  **right, 2 of 2**.
- R is small, so any query returns all of it. Every turn that searched R named it.

## The lever

**I chose a prompt lever. A code lever is possible, and choosing between them is for the integrator.**
Invariant 2 prefers code. The turn-1 failure, though, has no deterministic trigger before the Worker
writes, and code cannot see "the word is undefined in this Act" until then. A code step that retrieves
a regime would also have to know which regime applies to which instrument and date, which is law
written into code. The row offered the prompt sentence as its second candidate.

**`server_py/src/prompts.py`:** one new phase in `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` (the
quick-lookup Worker, which the lawyer's configuration uses at every turn), held in a new constant
`_GENERAL_RULE_APPLICATION_PHASE` (+18 lines), and one changed line:

- **PHASE 2c**, conditional: "only when the brief asks what a word or phrase means in an instrument
  that does not define it, or asks which general legislation, such as an interpretation Act, gives it
  a meaning". It tells the Worker to:
  - find the general interpretation legislation that applies;
  - retrieve that legislation's application provision, by a section search with the query
    "application", as well as its definition;
  - say it applies only if that provision covers the instrument;
  - if the provision excludes the instrument, say so and find what does apply;
  - if no application provision was retrieved, say it was not checked.

  **It names no instrument and no year** (a test enforces this). Which legislation applies is left to
  retrieval.
- "SYNTHESISE IMMEDIATELY: After Phase 2" becomes "After Phase 2 (and 2b or 2c where they apply)".

**What it reaches (free, `python scripts/manager_identity.py`):**

- **The Worker:** only the conversational Worker prompt changes, for all three research types. The
  research and Deep Research Worker prompts are byte-identical to HEAD in all 12 configurations.
- **The Manager:** every Manager system prompt is byte-identical to HEAD (18 of 18:
  3 research types x 3 chat modes x chips on/off).

## The seam evidence (2026-10-01, every draw the same day)

**1. Worker seam, as sent.** Each stored turn-1 first-delegation Worker call (`wave4_p33_post` and
`wave4_b1_post`) is rebuilt as `chat_loop` sent it: every recorded round, the recorded date, the real
tools offered, then the next round drawn. Script: `python scripts/ab_worker_last.py <before|after> N`.

- **Sides:** before is HEAD's prompt, through `seam_replay`'s own revision loader; after is the
  working tree. HEAD's conversational Worker prompt is identical to the one recorded at `42951b4` and
  `2271826` (`scripts/cmp_prompt.py`), so the before side is the payload actually sent; its sizes
  match `seam_replay worker --as-sent --at-rev recorded --date recorded --dry-run`.
- **Payloads:** 6 slots give 5 distinct payloads, because `wave4_b1_post` r1 and r2 are
  byte-identical. Each was drawn 2 times a side, with b1 r1 drawn once more on the before side.
- **Before: 10 of 10 draws answered** with the report as recorded and searched nothing further.
- **After: 10 of 10 draws searched for general interpretation legislation** in the next round. The
  first search named N in 10 of 10, R in 2 and U in 1.

The seam stops at that round, so step 2 shows what the search then retrieves.

**2. Live Worker draws.** The product's own `run_worker_agent` (OpenRouter binding), run on the
recorded brief, with:

- live LEX and live summarisation (summariser `google/gemini-3-flash-preview`);
- the local prompt cache and the memo OFF, so nothing was written to any database;
- the recorded date line.

Script: `python scripts/live_worker.py after <turn> N <slot>`. **After side only**: the before side's
turn-1 behaviour is 9 of 9 stored and 10 of 10 on the seam above. Graded by hand against the booked
criteria.

| turn | runs | report names R | report asserts N or U governs | application query used |
|---|---|---|---|---|
| 1 (both recorded turn-1 briefs) | 5 | **4 of 5** | **0 of 5** | 4 of 5 |
| 2 (briefs of the two recorded turns that asserted the wrong regime) | 2 | **2 of 2** | **0 of 2** | 2 of 2 |

- **The one turn-1 miss (`p33post_r1` run 1):**
  - It retrieved N's application section and U's application section for the devolved Acts, and
    said correctly that neither applies.
  - It then stopped without finding R. That is the honest outcome, and Invariant 1 holds, but the run
    fails "name R".
- **The run without an application query** (`b1post_r3`) still named R, from R's full text.
- Cited provisions checked against the raw results (the two application sections; R's article and
  schedule): they are in what was retrieved.

**3. Manager seam on the live reports.** The 4 first live turn-1 reports were each substituted into a
copy of their stored run file (`scripts/mk_mgr_fixtures.py`, gitignored copies), then run through
`seam_replay manager --turn 1 --reps 2` (no `--date`: the composition seam does not take it).

- R is named in **6 of 8** answers: every draw from the 3 reports that named it.
- A wrong regime is asserted in **0 of 8**.
- **Seam artefact, not a product finding:** both draws on `b1post_r1` say the research hit an error
  or was truncated, and one draw on `b1post_r2` stops mid-sentence. `worker_result_for_manager` hands
  over the whole report (`scripts/check_wrfm.py`), so this is the Manager's refused tool call being
  narrated. All three still name R.

**4. Drift.**

- **Manager first-delegation probe: not drawn.** Its payload is byte-identical before and after (see
  "What it reaches"), so the probe would have drawn identical bytes twice. **The integrator should
  decide whether that proof meets the rule ("any edit to a Manager or Worker prompt needs the
  first-delegation drift probe"), or draw it ($0.40).**
- **The Worker-side equivalent was drawn instead:** the Worker's first round on the first brief of
  the same 8 drift-probe slots, all Conversational at turn 1, so all receive the edit. 3 draws a side,
  the same day, with the P3.7 lookup block rebuilt live. Script:
  `python scripts/worker_drift.py <before|after> 3`.
  - **No first-round call moved to another instrument in any slot.**
  - One slot's draw 1 made 1 call instead of 4; its first instrument was unchanged.
  - One slot's query wording changed slightly; same subject.
  - 6338's first round is unchanged, since the phase fires only after the Act is found not to define
    the word.

**A seam pass is not a live pass.** The live Worker draws come closest. They do not include:

- the Manager's own turn-1 brief under the full conversation;
- turn 2's brief as it would be written after a turn 1 that already names R;
- turn 3.

## What the lever costs

- **More tool calls and more cost per turn:** the live turn-1 Worker made **11-15 tool calls**
  (recorded 3-4) and cost **$0.128-0.193** per Worker run. The recorded whole turn 1, Manager
  included, cost $0.063-0.136 (`timing.total_cost_usd`). Wall time was not recorded for the live
  runs.
- **Wasted calls:** one run section-searched two unrelated instruments that its search had returned.
- **Untested panel:** the phase fires on any Conversational question about what a word means where
  the instrument does not define it. I did not test other sessions' definition questions.
- **The case-law-only conversational Worker also receives the phase**, though it has no legislation
  tools. It shares the one quick-lookup prompt, which already names legislation tools in its Phase 2.

## Tests

`server_py/tests/test_general_rule_application.py`, **31 tests**. They check:

- PHASE 2c is in the quick-lookup Worker for each research type;
- it asks for the application provision with the query "application";
- it states the three outcomes;
- it is conditional;
- it names no instrument or year;
- the synthesis step waits for it;
- the research and Deep Research Workers do not carry it (6 tests);
- no Manager prompt carries it (18 tests).

**Revert proof, on a scratch copy of `server_py`:**

- `prompts.py` was replaced with `578718f`'s by `scripts/do_revert.py`, which **removed 18 lines and
  restored 2**, and confirms the file then equals HEAD.
- With that revert, **7 failed and 24 passed**. The 24 that pass are the no-regression guards (6
  Worker, 18 Manager), which pass by design on both sides.

**Full suite on `lexchat_test_c`: 2066 passed** (2035 + 31).

## Spend: $2.11 against $3 (stopped with $0.89 unspent)

| step | printed cost |
|---|---|
| Worker seam, before side (11 draws) | $0.2725 |
| Worker seam, after side (10 draws) | $0.1686 |
| Worker first-round drift probe (48 draws) | $0.5236 |
| Live Worker, turn 1 (5 runs) | $0.8176 |
| Live Worker, turn 2 (2 runs) | $0.1677 |
| Manager seam (8 draws; one draw printed $0.0000, estimated at $0.02) | $0.1386 + ~$0.02 |
| **Total** | **~$2.11** |

## What I did NOT do

- No replay, no server, no rubric edit, no after-column.
- No Manager first-delegation drift probe draws. The payload was proven byte-identical instead; see
  Drift.
- No code lever.
- No change to the research Workers.
- No live before-side Worker draws.
- No test on other sessions' definition questions.
- Turn 3 not drawn.

## For the integrator to decide

1. **Whether the seam evidence is enough to put PHASE 2c into the next after-column.** My reading: yes.
   - Turn 1 moves from "never searched" (9 of 9 stored; 10 of 10 seam before) to "searched" (10 of 10
     seam after).
   - Live turn-1 reports name R in 4 of 5, with 0 wrong-regime claims in 7 live reports.
   - The criterion is n=3, all clean, and 1 of 5 live reports still misses R, so expect a rep to fail
     turn 1 at some rate.
2. **Whether byte-identity satisfies the Manager drift-probe rule** for a Worker-only edit.
3. **Whether to also build a code lever:** a deterministic "application" section search whenever a
   section search hits an instrument whose title marks it as interpretation legislation (generic, no
   law in code). It would make the application provision certain once such an instrument is found.
   It would not fix turn 1 on its own.
4. **The cost per turn** (about 2-3x on this turn), and whether the phase should also go into the
   research Workers (the hybrid research Worker carried P3.18's claim in batch 1).
5. **Hazard:** the session scratchpad directory is shared by the batch's agents. Other agents' files
   are at its root, and I removed and recreated a `revert/` directory in it. Use per-agent
   subdirectories.

## Location of the numbers

- **Step 1:** `scripts/seam_locate.py`; `python -m tools.summary_probe count --dir
  $PREPILOT_EVIDENCE/replay/wave4_p33_pre $PREPILOT_EVIDENCE/replay/wave4_p33_post
  $PREPILOT_EVIDENCE/replay/wave4_b1_post` (10, all in `wave4_p33_pre`).
- **Provisions returned by each regime section search:** a one-off listing over the run files' raw
  results; reproduce with `seam_locate.py`'s loader.
- **Draws:**
  - `seam/batch2/C/{before,after}/<slot>/draw*.json`;
  - `seam/batch2/C/live/after/t{1,2}/<slot>/run*.json`;
  - `seam/batch2/C/mgr_draws/`;
  - `seam/batch2/C/drift/{before,after}/<session>/`.
