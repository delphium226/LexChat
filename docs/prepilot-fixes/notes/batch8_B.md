# Parallel batch 8, agent B: the sweep's instruments, and the sweep priced ($0; 3 live LEX calls)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 87ceeff1f3478cec38d9edf6d7010b78d16d8436` (the integrator's
head). This note is based on `87ceeff`. The run was interrupted once (the integrator's session
ended) and resumed from the same worktree; nothing was lost.

**What this is.** Tooling and one replay script for the acceptance sweep of P3.27, P3.12 and
P3.25, and the sweep priced from recorded costs. **No product code** (nothing under
`server_py/src/` changed). Model spend **$0**: no model call, no server, no replay.

**Live calls (the user agreed at launch: up to 40, paced, logged, cap in code).** **3 calls**, all
`POST /legislation/section/lookup` to LEX, all status 200, 9,171 bytes, at least 0.6 s apart
(`lexcall.py` copied from batch 7 B with `CAP = 40`; log `probe_log.jsonl`). No other host.

**Model.** Every stored run file read here ran on the pinned `google/gemini-3.1-pro-preview`. No
number below comes from `glm-5.2:cloud`.

**Scratch.** Gitignored `docs/prepilot-fixes/evidence/seam/batch8/B/` (`git check-ignore -v`
gives `.gitignore:113`), copied to the main checkout's same path. Commands run from `server_py/`
with `PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`E=$PREPILOT_EVIDENCE/replay`, `S=../docs/prepilot-fixes/evidence/seam/batch8/B`.

---

## 1. What changed

All in `server_py/tools/replay_report.py` (395 lines added, 5 changed), plus a new test file and a
new script:

1. **`DepthReq` gains two optional fields**, both off by default: `span` (how many sentences or
   list lines after the citing one the `near` window takes; default 1, the old window exactly) and
   `unless` (a pattern that disqualifies a deep match whose own sentence carries it). `depth_counts`
   does not count a disqualified match as at depth.
2. **`DEPTH_TRUTH["6335"]`**: P3.12's ground truth for turn 7, three `DepthReq`s over the
   statutory words of the three paragraphs (batch 7 B's live cut, `seam/batch7/B/p312_truth.txt`):
   - para 42: the paragraph cited and, within 2 lines, no winding-up resolution or order;
   - para 43: the paragraph cited and, within 4 lines, enforcing security AND legal process AND
     the administrator's consent or the court's permission (all three);
   - para 44: the paragraph cited and, within 2 lines, the interim moratorium's trigger (an
     administration application made, or a notice of intention to appoint filed).
   A citation counts in any form (`paragraph 43`, `para. 43(2)`, `paras 42-44`, a list, LEX's own
   `Section 43 of Schedule B1`); the Schedule named alone is the coarse citation; a citation in a
   sentence saying it was not retrieved (`unless`) does not count. Statute words only, the
   standing `DEPTH_TRUTH` exception.
3. **`replay_report schedules`** (new): what each answer says about a schedule or annex unit, from
   a gitignored rubric (`evidence/rubrics/p327.json` by default; mine is
   `$S/p327.json`: **the integrator copies it there**, a new file). It grades P3.27's check (a held
   unit called "not held", "not retrievable" or "not in the text" FAILS) and 6374's Invariant 1
   guard (a unit LEX does not hold: PASS on an index statement, FAIL on a limit blamed or an offer
   to fetch it). Classified per clause, not per sentence (section 3). Options `--also`,
   `--all-dirs`, `--session`, `--drops`, `--chars`; exits 1 on any FAIL. Scripted runs map back to
   export turns through `from_turn`.
4. **`docs/prepilot-fixes/evidence/scripts/p32c_6406.json`** (tracked; base session and turn
   indices only): `p32_6406` cut after export turn 5, `from_turn` 1, 3, 4, 5, Conversational under
   `legislation_only`, verdict FAIL.
5. **`server_py/tests/test_replay_schedules.py`**: 22 tests (section 6).

## 2. Item 1: P3.12's ground truth, graded over every stored 6335 directory

**Turn numbering checked.** Every stored unscripted 6335 run file runs export turns 1-7 in order,
so run turn 7 is export turn 7 (`python $S/q_inv.py 6335` over `$S/inventory.json`, built by
`python $S/inventory.py $E`). The scripted `p46_6335` runs export turns 1-4 only and is not graded
(its `session_id` is not in `DEPTH_TRUTH`). A fresh `replay run --session 6335` today sends every
turn Conversational, turns 6-7 under `legislation_and_case_law` (P0.6's reviewer read;
`cd server_py && python $S/sessmodes.py 6335`). **No stored rep ran in exactly that configuration**:
`wave0_conv` is Conversational with turns 6-7 under `legislation_only`; the rest ran in Research mode.

`for d in baseline wave0_conv wave1 wave2 wave3_p38_pre; do python -m tools.replay_report --dir $E/$d depth --answers --drops; done`

| Directory | Mode | Verdict | Para 42 / 43 / 44 | Hand-read |
|---|---|---|---|---|
| `baseline` r1 | research | SHALLOW | coarse / coarse / coarse | a clarifying question naming the Schedule; nothing delivered. Agrees. |
| `wave0_conv` r1 | conversational | PARTIAL | coarse / coarse / **deep** | para 44's trigger stated correctly; 42 and 43 named, then "the search ... was cut short by a system limit". Agrees: the lawyer did not get 42-43. |
| `wave1` r1 | research | SHALLOW | coarse x3 | "unable to retrieve"; the citing sentence says the search "returned no results" (disqualified by `unless`). Agrees. |
| `wave2` r1 | research | MISSED | missed x3 | the step-cap halt notice (1,234 characters); no Schedule named. Agrees. |
| `wave3_p38_pre` r1 | research | PARTIAL | coarse / coarse / **deep** | para 44 reached as a cross-reference inside Part A1 (the notice-of-intention limb). Agrees with P3.12's row ("only as a cross-reference"). |
| `wave3_p38_pre` r2 | research | SHALLOW | coarse x3 | "paragraphs 42, 43, and 44 ... were not retrieved because searching ... was cut short by a limit"; para 44 named without its trigger. Agrees. |
| `wave3_p38_pre` r3 | research | SHALLOW | coarse x3 | the same negative as r2. Agrees. |

**DELIVERED 0 of 7: the before-column fails everywhere the lawyer did not get the paragraphs**,
including reps 2 and 3 of `wave3_p38_pre`. I read every `--drops` sentence (77 lines,
`$S/depth_6335_drops.txt`): none states paragraph 42's or 43's substance.

**`depth` is unchanged for every other session**: `cd $S/rev/server_py && python ../../depth_identity.py $E`
runs `depth --answers --drops --seams` with the head's and the built module over all 58
directories: 53 identical; the 5 that differ are exactly the five holding 6335, and differ only in
the 6335 rows and the totals that include them (`$S/depth_identity.txt`).

## 3. Items 3 and 4: `schedules`, the 6374 guard and P3.27's check

**The rubric** (`$S/p327.json`, gitignored): 6374's unit is any un-numbered "schedule(s)" (its
Offices Orders), **not held**; 6335's is P3.12's Schedule (named, or paragraphs 42-44), held;
6406's is any annex of its regulations, held; 6389's is its Act's and Regulations' numbered
schedules, held. Held / not held come from batch 7 B's live probe, plus **my 3 live calls**: the
three later Offices Orders each return 2-4 articles and **no schedule or annex provision** from
`/section/lookup` (`python $S/probe_orders.py`, `$S/probe_orders.txt`), so every 6374 negative about
those Orders' schedules is true, not only the 1999 Order's.

**Classes, per clause** (a sentence split at `;`, a spaced dash, or a comma before
and/but/while/though/meaning/furthermore and the like; a later clause with an anaphor counts as
about the unit; link URLs removed first): OFFER > LIMIT > INDEX > TEXT > NEG, or none. Why per
clause: batch 7 B's 5 "limit" answers on 6374 were found by a sentence-level test ("Schedule" and
"limit" in one sentence); **by hand 3 of those 5 blame the limit for something else** (step 2 or the
search for later Orders) and state the index for the Schedule itself.

**Where `NEG_ASSERTED` fits and where it does not.** It is reused as one source of negatives, but
not alone: (a) it misses "not held in *this* index", "missing from the database", "lacked",
"not in the text", "was not returned", "unavailable in", each in a stored answer; (b) its
"no <noun>" alternative reads "contains no provisions for X" (the law) as a research negative, so
here such a match counts only with a search noun or a found-type verb; (c) it has no idea of
attribution, which both checks turn on. A bare "does not contain" is not a negative here at all:
an answer saying an annex chapter "does not contain any provision permitting" something is the
right reading on P3.2's control turn, not a retrieval failure. "Cannot verify" counts only beside the index or the
text (`wave4_b4_post` r3 export 8 refuses to answer from memory; it is not a negative about the
annex).

### 3.1 The 6374 guard, every stored directory

`python -m tools.replay_report --dir $E/baseline schedules --rubric $S/p327.json --all-dirs --session 6374 --drops`
(`$S/sched_6374.txt`; 58 directories, the count includes any new one).

**36 slots (turns whose answer mentions the Schedule): PASS 12, FAIL 7, SILENT 17.** I read every
slot and every clause:

- **The 7 FAILs are all right.** Export turn 3 (conversational): `wave2_p23` r1 ("could not
  immediately retrieve ... during this quick search"), r2 ("wasn't fully retrieved in this initial
  search" and "Would you like me to pull the full Schedule"), `wave2_p27` r3 ("would require a
  deeper look"). Export turn 4 (Deep Research): `wave2_p27` r1 and r2 ("did not complete due to an
  internal limit"), `wave3_p38` r3 ("cut short by a limit"). Export turn 2 (Deep Research):
  `wave3_p38` r1 ("not retrieved due to the research limit").
- **The 12 PASSes all state the index** ("not held in this legislation index", "missing from the
  retrieved database", "the database lacked"); none blames a limit for the Schedule.
- **The 17 SILENTs** mention the Schedule in passing (that it lists further items) and say
  nothing about what is held. Reported, not failed (decision 2).
- Batch 7 B counted 16 turns, 5 blaming a limit. Mine differ because B's pairs only covered turns
  that read the Order's whole text: 2 of B's 5 are FAILs here; 3 are PASSes by hand (above); and 5
  FAILs here were outside B's pairs.
- By export turn, a statement about the Schedule appears in 2 of 16 stored reps at turn 2, 7 of 16
  at turn 3 (0 of 2 in `p37r_6374`) and 10 of 16 at turn 4.

### 3.2 P3.27's check, every stored directory of its need sessions

`python -m tools.replay_report --dir $E/baseline schedules --rubric $S/p327.json --all-dirs --session 6335 6406 6389 --drops`
(`$S/sched_held.txt`). **217 slots: 6335 FAIL 1, LIMIT 3, OK 2, SILENT 1; 6406 FAIL 12, LIMIT 2,
OK 191; 6389 OK 5.**

- **On batch 7 B's 23 hand-read need turns the command gives B's hand-read exactly:** the 12 FAILs
  are B's 7 "not held in this index" plus B's 5 "could not be retrieved"; the 2 LIMITs are B's 2
  "cut short by a limit"; the other 9 carry no negative (B's premise, unread-content, clarifying,
  halt, delivered and not-addressed turns).
- **Outside B's 23**: 1 more FAIL, `wave4_p33_post` r2 export 5 ("not available in the legislation
  index"), a false negative by hand (LEX holds the annex). 3 more LIMITs (`wave0_conv` 6335 t7;
  `wave4_b1_post` r2 export 4 and export 5): true of the run. Note
  `wave4_b1_post` r2 export 5 says the chapter's text "was not returned by the index in this
  search (just as it was excluded by search limits previously)": LIMIT wins in that clause, so it
  is reported, not failed. P3.2's own control reading (`stance`) is stricter there.
- **Drops read**: every clause about a unit that the command left unclassified was screened for
  research words (`$S/drops_negwords.txt`); the ones that look negative are readings of the law
  (a substance "not listed in" a schedule, an annex chapter that "does not contain any provision
  permitting ...", "the research did not retrieve any provision in [an annex] that addresses X"),
  correctly not counted.
- What this check does **not** catch: an answer that states a schedule's content it never read
  (batch 7 B's two "asserted unread" turns read OK here). That is P3.16's class; `summary_probe`
  and the hand-read cover it.

## 4. Item 2: the cut script and `stance`'s control reading

`p32c_6406` runs export turns 1, 3, 4, 5, so **the control turn (export 5) is run turn 4, the last
turn**. Over all 15 stored `p32_6406` reps, export turn 5 is run turn 4 in every one, and
`stance`'s control verdict there is **identical** when each rep is truncated to its first 4 turns and
given the cut script (15 of 15: 6 pass, 9 fail):
`cd server_py && python $S/cut_check.py $E $PREPILOT_EVIDENCE/rubrics/p32.json ../docs/prepilot-fixes/evidence/scripts/p32c_6406.json`.
`stance` keys its rubric on the script's `base`, so it grades the cut run without change.

**Read only the control column (C/F at t5) for P3.12's criterion (v).** The cut run's overall
`stance` PASS/FAIL also counts an opener on export turn 5 (a challenge turn) and any contradicted
claim in turns 1-5, and it never sees P3.2's window (6-12): 2 of the 15 truncated reps pass the
control and fail on an opener alone. `schedules` grades the same turn for P3.27's wording (a held annex called not held).

## 5. Item 5: the sweep, priced

`python $S/price.py` (reads `$S/inventory.json`). Recorded `total_cost_usd` of every stored rep in
the recorded mode; for the cut script, the sum of each stored `p32_6406` rep's first 4 run turns.
Invariant 4 from `evidence/classification.json`: **6335, 6340, 6374, 6383, 6406 and 6409 are FAIL;
6389 is DEFECT.**

| # | Run | n | Mode as sent | Grades | Stored reps | Median / rep | Max / rep | n x median | n x max |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `6335` session | 3 (FAIL) | Conversational; t6-7 legislation and case law | P3.12: `depth` 6335 t7 DELIVERED 3 of 3; `schedules` (the held Schedule called not held = FAIL) | 1 (wave0_conv) | $0.326 | $0.326 (any mode $1.141) | $0.98 | $0.98 ($3.42) |
| 2 | `p32c_6406` script | 3 (FAIL) | Conversational | P3.12 criterion (v) and P3.25: `stance` control column at t5; `schedules` 6406 | 15 (first 4 turns) | $0.647 | $1.503 | $1.94 | $4.51 |
| 3 | `p37_6409` script | 3 (FAIL) | Conversational | P3.25: no `get_legislation_text` in a quick-lookup delegation; `commencements`, `lookup` | 15 | $0.406 | $0.522 | $1.22 | $1.57 |
| 4 | `6340` session | 3 (FAIL) | Conversational, legislation and case law | P3.25: `derivations` SUPPORTED in every rep (C's named risk) | 1 (wave0_conv) | $0.067 | $0.067 (any mode $1.442) | $0.20 | $0.20 ($4.33) |
| 5 | `p37r_6374` + `p37r_6383` scripts | 1 each (booked n=1 though FAIL; decision 3) | Conversational | P3.25: `derivations` clean; `schedules` 6374 guard on export turn 3 | 2 + 2 | $0.214 + $0.296 | $0.239 + $0.301 | $0.51 | $0.54 |
| 6 | `6374` session | 1 (decision 1) | conv, **DR**, conv, **DR** | P3.27's guard where P3.27's line can reach it (Deep Research turns 2 and 4) | 16 | $1.719 | $3.601 | $1.72 | $3.60 |
| 7 | `6389` session | 1 (DEFECT) | Deep Research | P3.27's lever on a need turn (the only need session whose recorded mode reads whole texts) | 5 | $0.720 | $0.766 | $0.72 | $0.77 |

- **Booked set (rows 1-5): $4.85 at medians, $7.80 at recorded maxima.** This is the brief's
  "about $5.50 to $7" with 6335 priced in its recorded Conversational mode.
- **With rows 6 and 7 (recommended, decision 1): $7.29 at medians, $12.16 at recorded maxima**
  ($18.73 if rows 1 and 4, each priced from one Conversational rep, cost as much as their dearest
  Research-mode rep). Add $3.44 at medians (+$7.20 max) for 6374 at n=3.
- **Why rows 6 and 7.** P3.25 took `get_legislation_text` from the quick-lookup Worker, so on the
  booked set **P3.27's change can reach no turn**: 6335, 6406 and the `p37*` scripts all run
  Conversational. Only P3.12's route reaches them. 6374's limit-blaming answers that P3.27's line
  should correct are 4 of 7 on its Deep Research turns (2 and 4), which `p37r_6374` (turns 1 and 3)
  does not run; 6389 is P3.27's only need session in a whole-text mode (Deep Research).
- **Costs may rise on the after-column**: P3.27 sends `include_schedules`, so a whole-text read of
  an instrument with schedules grows (batch 7 B: summariser input x1.96 over the stored reads;
  6389's two instruments x1.37 and x1.73). 6374's Orders hold no schedules, so its reads do not
  grow. `--max-spend` is checked between reps, so a command can overshoot by one rep.

**Commands, in order** (from `server_py/`, after `replay check`, `replay pin` and a fresh uvicorn;
`O=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b8_sweep`,
`SC=../docs/prepilot-fixes/evidence/scripts`; `--reps` is explicit on every line because the
default is 3 for any FAIL base, which would triple rows 5 and 6):

```
python -m tools.replay run --session 6335 --reps 3 --out-dir $O --max-spend 3.50
python -m tools.replay run --script $SC/p32c_6406.json --reps 3 --out-dir $O --max-spend 4.60
python -m tools.replay run --script $SC/p37_6409.json --reps 3 --out-dir $O --max-spend 1.60
python -m tools.replay run --session 6340 --reps 3 --out-dir $O --max-spend 1.50
python -m tools.replay run --script $SC/p37r_6374.json $SC/p37r_6383.json --reps 1 --out-dir $O --max-spend 0.60
python -m tools.replay run --session 6374 --reps 1 --out-dir $O --max-spend 3.70
python -m tools.replay run --session 6389 --reps 1 --out-dir $O --max-spend 1.50
```

Rows 1-2 first: they carry P3.12, the decisive and least certain result. If the user takes only the
booked set, stop after the fifth command. The `--max-spend` figures are per command (the cap does
not carry across commands); the integrator should keep a running total against the figure the user
agrees.

**Grading and hand-reads the sweep needs** (all over `$O`, run without `--all` where a command
walks subdirectories):

- the exit-1 set and `modes` (as every sweep);
- `depth --answers --drops`: 6335 t7 **DELIVERED in 3 of 3**; hand-read every verdict and every drop
  (the regexes accept the substance in any wording but need each paragraph cited, decision 4);
- `schedules --rubric <p327.json> --drops`: every slot; **hand-read every FAIL, LIMIT, UNATTRIBUTED
  and SILENT** on 6335, 6406, 6374 and 6389 (6374's guard: 0 FAIL, and an index statement on the
  turns that make a statement);
- `stance --session p32c_6406 --sentences`: the control column (C/F at t5) for criterion (v);
  hand-read each control answer (the rubric's control patterns are narrower than `schedules`);
- `derivations` (6340: a SUPPORTED derivation in every rep, 0 unverified; `p37r_*` clean),
  `lookup` and `commencements` (`p37_6409`), and the audit check that no quick-lookup delegation
  ran `get_legislation_text`;
- `negcurrency` (without `--all`), `footer_echo`, and the summarised counts for
  `get_legislation_text` (the flag's cost on rows 6 and 7).

## 6. Tests and reverts

`server_py/tests/test_replay_schedules.py`, **22 tests**, synthetic except the 6335 entry's
statute words: the two `DepthReq` fields (span widens the window, the default is the old window
byte for byte, `unless` disqualifies in the verdict and in `depth_counts`); 6335's entry (all three
delivered, a bulleted para 43, named-but-not-retrieved is SHALLOW, para 43 needs all three facts,
para 44 alone is PARTIAL, range and LEX-rendered citations, no prompt names the graded paragraphs);
every clause class, legal negatives not read as research, clause attribution, anaphor and link
handling; every verdict; the command on synthetic run files (guard PASS and FAIL, a held annex
FAIL on a scripted run mapped to its export turn, a session outside the rubric, CLI wiring); the
cut script and `stance`'s control on its last run turn.

**Proven to fail with the change reverted** (`python $S/mutants.py`, on the scratch copy `$S/rev/`,
never the worktree; output `$S/mutants.txt`):

- **Full revert** (`replay_report.py` back to `87ceeff`: the diff's 395 added lines removed and 5
  restored): **19 failed, 3 passed.** The 3 that pass do not depend on `replay_report`: the two
  cut-script tests fail when the script is removed (2 failed, run by hand on the copy), and the
  prompt guard checks the product's prompts (it is a guard, and passes at head).
- **18 single-site mutants, each anchor asserted to occur exactly once (CRLF kept), each fails 1 to
  6 tests**: span ignored; `unless` ignored in the verdict; `unless` ignored in `depth_counts`; the
  6335 entry removed; para 43 with one fact; range citations not read; LIMIT checked after INDEX;
  the legal "no <noun>" filter off; "cannot verify" without the index; no clause split; no anaphor
  rule; link URLs kept; a held LIMIT failed; a not-held OFFER passed; the export-turn mapping off;
  the command exiting 0 on a FAIL; "research limit" not a limit; "unavailable" not a negative. Two
  mutants survived the first draft (para 43 one fact; LIMIT after INDEX); a test was added for
  each and both now fail.
- **Full suite on `lexchat_test_b`: 2361 passed** (2339 + 22).

**Data handling.** The staged diff was grepped with `scratchpad_s39/matter_grep.py` (28 words):
the only hits are "Annex" in generic test wording ("Gadget Annex", "the Annexes") after I replaced
two matter-flavoured annex numbers with synthetic ones (`$S/synth.py`); the only instrument id is
P3.12's Act inside `DEPTH_TRUTH` (the standing exception). Session ids only otherwise.

## 7. What I did NOT do

- No product code, no model call, no server, no replay; 3 live LEX calls only.
- I did not run the sweep, or measure whether A's wording moves any grader: **A's exact text is not
  known to me.** `schedules` reads an echoed "the index holds no schedules or annexes for this
  instrument" (or "has no schedules ... in this index") as INDEX (a test pins the second form). **The
  integrator should run `sched_clause_class` over A's final line and labels before the sweep**: if A's
  wording is a negative not in these forms it reads as SILENT, not PASS, and the guard would
  under-read; if A's cut-block label carries "not retrieved" or a limit word, an echo would read as a
  FAIL on a held unit.
- I did not copy the rubric into `evidence/rubrics/` (outside my folder); it is `$S/p327.json`.
- I did not edit FIX_PLAN, SESSION_LOG, the tracker, CHANGELOG, any existing rubric, the lawyer pack
  or memory; I did not run `plan_status` or `plan_lint` (nothing they read changed).
- I did not push or merge.

**Claims checked.** P3.12's "reps 2 and 3 of `wave3_p38_pre` say the text was not retrieved": holds
(both SHALLOW, the sentence read). Batch 7 B's "16 turns of 6374 ... 5 blaming a limit": the 16 and
the 5 re-derive from B's `pairs.json` (`$S/b7_6374_turns.py`), but by hand 3 of the 5 blame the
limit for something else (3.1). B's "LEX holds no text for 6374's Order's Schedule": holds, and now
also for the three later Orders (live). C's P3.25 prices: `p37_6409` median $0.406 over 15 reps
(C: $0.378 from `wave4_p37c` alone); the 6406 cut $0.647 median, $1.503 max (C: the same).

---

## 8. Decisions for the user

1. **Which runs the sweep holds.**
   1. **(Recommended) The booked set plus full 6374 n=1 and 6389 n=1: $7.29 at medians, up to about
      $12.20 at recorded maxima.** The two additions are the only runs where P3.27's own change can
      act (Deep Research reads whole texts; the Conversational Worker no longer does).
   2. **The booked set only: $4.85 at medians, up to $7.80.** P3.27 is then measured only through
      P3.12's route and its guard only on 6374's Conversational turn 3, where P3.27's line never
      reaches the Worker.
   3. **The booked set plus full 6374 at n=3 and 6389 n=1: about $10.70 at medians, up to about
      $19.40.** Invariant 4 to the letter for 6374 (FAIL), at three times the cost of the guard.
2. **What the 6374 guard requires of a silent turn** (17 of 36 stored slots mention the Schedule
   and say nothing about what is held).
   1. **(Recommended) Report SILENT, fail only a limit blamed or an offer to fetch it**, and read
      that no turn that made a statement lost its index attribution (12 PASS before).
   2. **Fail a silent turn too.** Strictly "the answer still says the index holds no text for it";
      the stored before-column would fail 17 of 36 slots that make no wrong statement.
3. **`p37r_6374` and `p37r_6383` at n=1** although both bases are FAIL (booked by the user for
   P3.25 as reach checks).
   1. **(Recommended) Keep n=1 as booked**: they check `derivations` stays clean, a deterministic
      symptom.
   2. **n=3** (+$1.02 at medians).
4. **How strict `depth` is on 6335 turn 7.**
   1. **(Recommended) As built: each paragraph cited by number, with its facts nearby.** Lawyers
      cite; the existing `DEPTH_TRUTH` entries require the provision at depth plus its facts.
   2. **The facts alone suffice** (an answer delivering all three paragraphs' substance under "Schedule
      B1" with no paragraph numbers would pass). Kinder to a prose answer; weaker as a citation check.

---

## Follow-up (batch 8 B2)

**Base.** Agent B's worktree was gone, so B2 worked in a fresh worktree. It came up on `main`
(`a6b4a76`), as every batch's has; with no commits made, I ran
`git reset --hard worktree-agent-ab3e470cc7c4b6d25` (B's head `2f73bb3`, on the integrator's
`87ceeff`; `git merge-base --is-ancestor 87ceeff… HEAD` passes). **$0**: no model call, no external
call, no server, no replay. **No product code** (nothing under `server_py/src/`). Two changes, both
in `server_py/tools/replay_report.py` (33 lines added, 9 changed), plus 6 tests appended to
`server_py/tests/test_replay_schedules.py`. Scratch: gitignored
`docs/prepilot-fixes/evidence/seam/batch8/B2/` (`git check-ignore -v` gives `.gitignore:113`),
copied to the main checkout's same path. Commands below run from `server_py/` with the batch's
`PREPILOT_EVIDENCE`, `PYTHONIOENCODING=utf-8` and `TEST_DATABASE_URL=…/lexchat_test_b`;
`$B2=../docs/prepilot-fixes/evidence/seam/batch8/B2`.

### Fix 1: P3.12's true-negative lines read INDEX, not SILENT

**The defect (the integrator's finding, reproduced).** Agent A's absent-unit and no-text lines put the
index in one clause and the unit in the next, split at ", and" or ", so" by `_SCHED_CLAUSE`. The unit
clause ("and none of them is a schedule or an annex: Schedule 2 is not one of them"; "so it holds
none for Schedule 2 either") named no index, so it classed '' and an echo read **SILENT** on 6374's
guard where it should read **PASS**. The inventory variant of the same line ("its schedules and
annexes among them are Schedule 1 and Schedule 3: Schedule 2 is not one of them") had the same fault.

**The change.** `SCHED_INDEX_NEG` gains four alternatives and one widening:
- `none of (them|these|those|which|its provisions|the provisions) … (is|are) (a|an) schedule(s)/annex(es)`;
- `(schedule|annex)[ <label>] is not one of them`: the unit must be the subject, so an anaphor
  clause such as "and theft is not one of them" after "the Schedule lists five offences" does not
  count. **"was not among them" is excluded on purpose**: that is P3.12's OPEN line ("code fetched
  only the first N provisions … and Schedule 2 was not among them"), which says nothing about what
  is held;
- `holds none for`;
- `(database|index|corpus|collection) … without (its|the|any) [up to 3 words] text`;
- the index-subject verb `holds no` widened to `holds no(ne)`.

**The screen of A's BUILT wording** (A's `server_py/src/utils/schedule_units.py`, taken with
`git show worktree-agent-a5655c6d5f4d0102d:server_py/src/utils/schedule_units.py` into the
gitignored scratch and imported from there; `python $B2/screen.py`, output `$B2/screen_before.txt`
at B's head and `$B2/screen_after.txt` after). Each string goes through `sched_unit_clauses` with a
generic unit mention and with each of the four rubric mentions:

| Group | Strings | Before | After |
|---|---|---|---|
| Held-unit wording: P3.27 variants 1, 3, 4 (one heading, two, preceded, no heading, boundary unknown, "and N more"); P3.12 block headers (2 leads x 3 tails x 4 reasons = 24); the closer; 5 piece labels; the OPEN (cut-short) line; the fetch-failed line | 38 | all '' | **all ''** |
| A's true negatives: P3.27 none-held; absent, none is a schedule; absent, with inventory; listed, no text; instrument without text | 5 | INDEX, '', '', INDEX, '' | **all INDEX** (no other class) |
| Synthetic echoes ("none of them is a schedule", "holds none for the Schedule", "holds … without its provision text", "holds no schedule or annex text", …) | 6 | 1 INDEX, 5 '' | **all INDEX** |

**What it moves in the stored answers: nothing.**
`python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/baseline schedules --rubric <B's p327.json> --all-dirs --session 6374 6335 6406 6389 --drops`
before (`$B2/sched_before.txt`) and after (`$B2/sched_after.txt`): **1,493 lines each, byte-identical**
(`diff` exits 0), so no verdict and no clause class moved: 253 graded slots, 20 failing; 6374 FAIL 7,
PASS 12, SILENT 17; 6335 FAIL 1, LIMIT 3, OK 2, SILENT 1; 6406 FAIL 12, LIMIT 2, OK 191; 6389 OK 5
(B's figures, re-derived). Why none moves: **no stored answer sentence matches any new alternative**
(`python $B2/scan_new_alts.py`: 485 run files, 1,953 answers, 33,629 sentences, 0 matches for each of
the five; the same scan finds 295 sentences matching the whole `SCHED_INDEX_NEG`, so it reads them).
The new forms are A's wording, which no stored run has seen.

### Fix 2: `corpus`'s leak check knows the new blocks

The marker tuple inside `cmd_corpus` is lifted to a module constant `CORPUS_LEAK_MARKERS` (same
five markers, same order) and gains `[SCHEDULES AND ANNEXES`, `[PROVISION FETCHED BY CODE` and the
closer `[/PROVISION FETCHED BY CODE]` (listed separately: a model can echo the closer alone, and
`[PROVISION…` does not match `[/PROVISION…`). Stored answers carrying any of the three: **0 of 1,955
answered turns over 58 directories** (inline count over every run file under
`$PREPILOT_EVIDENCE/replay`), so no `corpus` LEAKED count moves.

### Tests, revert and mutants

6 tests appended (synthetic; A's strings verbatim with `ssi/1901/3`): A's 5 true negatives read
INDEX; 6 echoes read INDEX; A's 36 held-unit strings class '' (a guard); "theft is not one of them"
after a Schedule clause stays '' (a guard); `cmd_schedules` PASSes a 6374-style echo and reports no
SILENT; `cmd_corpus` counts 3 leaks in 4 synthetic answers (one per new marker).

`python $B2/mutants.py <worktree>` (scratch copy `$B2/rev/`, never the worktree; output
`$B2/mutants.txt`; every anchor asserted once, CRLF kept):
- **Full revert** (`replay_report.py` back to `2f73bb3`: the 33 added lines removed, 9 restored):
  **4 failed, 2 passed**. The 2 that pass are the two guards (held wording, the legal "one of them"),
  which pass at B's head by design; M6 and M7 show they check behaviour.
- **10 single-site mutants, each fails 1 or 2 tests, none survives**: M1 the "none of them" alternative
  removed (2); M2 "is not one of them" removed (1); M3 "holds none for" removed (2); M4 "index …
  without its text" removed (1); M5 `holds no(ne)` back to `holds no` (1); M6 "was not among them"
  also read as INDEX, i.e. the OPEN line (1, the held guard); M7 "is not one of them" without the
  unit as subject (1, the legal guard); M8, M9, M10 each new corpus marker dropped (1 each).

**Full suite on `lexchat_test_b`: 2367 passed** (2361 + 6; `python -m pytest -q -p no:cacheprovider`).

**Data handling.** Staged diff grepped with `scratchpad_s39/matter_grep.py`; the instrument id in the
tests is the synthetic `ssi/1901/3`, the units are "Schedule 1-3", "Annex IV" and "Widget Order 1901".

**Not done.** No product code; A's module was read from a scratch copy only. No sweep, no replay. I did
not copy B's rubric into `evidence/rubrics/` and did not edit FIX_PLAN, SESSION_LOG, CHANGELOG,
CLAUDE.md, any rubric or memory. Not pushed, not merged.
