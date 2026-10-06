# Parallel batch 9, agent E: the sweeps' instruments, and the sweeps priced ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. With no commits of
mine I ran `git reset --hard ca3d45ca0e4705123aa23ed0c7fc0c1ab9a77918` (the integrator's head). This
note is based on `ca3d45c`. Branch `worktree-agent-a49b77e0987e5a26c`; commits `f5fd843`, `f9d48fa`,
`236c7ef`, `922234a` and this note's.

**Spend: $0.** No model call, no server, no replay pin/run/restore, **no external call of any kind**
(none was authorised). **Model:** every stored run read here ran on the pinned
`google/gemini-3.1-pro-preview`; nothing below comes from `glm-5.2:cloud`.

**Scratch:** gitignored `docs/prepilot-fixes/evidence/seam/batch9/E/` (`git check-ignore -v` gives
`.gitignore:113`), copied to the main checkout's same path at the end. Every command runs from
`server_py/` with `PYTHONIOENCODING=utf-8`, `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`,
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_e`;
`E=$PREPILOT_EVIDENCE/replay`, `S=../docs/prepilot-fixes/evidence/seam/batch9/E`. My scratch re-runs of
the stored grading are one script: `bash $S/grade_stored.sh` (from `server_py/`).

**Rubrics for the integrator to copy to `evidence/rubrics/`:** `$S/p322.json` (sha1 `863955e0…`) and
`$S/p34.json` (sha1 `f0232e9d…`). Both are the commands' defaults once copied.

**Shapes built to (the integrator's two messages):** agent C's P3.21 shape **as built** (`36ddcee`,
its `test_the_output_shape`): `commencement_dates` a dict (`status`, `relations`, `dated`, `refused`,
… or `status` and `reason`), absent when no hop ran; a dated `changes` entry carries `in_force` and
`qualification`, and an entry whose provisions take different dates is split, so one `by` repeats.
A string status, a list or a `{provision: date}` map in `in_force` are read too. Agent D's P3.6 (a
search row keeps `description`, cut to 600) and agent B's P3.22 (`api_calls[].request` carries
`order` and `per_page`) are read as described in sections 2 and 1.

---

## 1. What changed (tooling only; nothing under `server_py/src/`)

`server_py/tools/replay_report.py`: **insertions only** (1,171 lines added, 0 removed or changed;
`python $S/names_check.py`: 55 new top-level names, none existed in the base, none defined twice).
Three subcommands:

1. **`authorities`** (P3.22, batch 8 C's bar). Per run, from a gitignored rubric: each in-corpus
   authority **retrieved** (in a `search_case_law` result), **read** (`get_case_law_text`) and
   **cited** (in an answer, footer removed), matched by neutral citation **and** by Find Case Law URL
   merged into one key (a law report such as "[1901] AC 52" is never a key); item 2's lead authority;
   item 3, every answer naming an out-of-corpus authority graded **per answer**: PASS when one of its
   sentences is SECOND_HAND (a citing word and the judgment it came through: a citation, a rubric
   authority or "the retrieved judgments", in the sentence or the two before) or NOT_HELD; EARLIER
   when none is but an earlier answer of the run was (reported, not failed); FAIL otherwise or on a
   LINKED sentence (a Find Case Law link labelled with the out-of-corpus name). A source phrase whose
   object is the authority itself ("as set out in X") is not second-hand. Item 4, the carrier
   retrieved by the last of its need turns in every run that answered one. `--before DIR…` compares
   items 1-2 by run counts (rates where the counts differ). Prints every match (by `ncn`/`url`) and
   every drop (named but not cited by citation or URL; other judgments cited; every classified
   sentence), and per run the case-law requests by `order/per_page` (B's `request.order`). Exits 1 on
   an item-3/item-4 FAIL or a `--before` regression.
2. **`cmcdates`** (P3.21). Every commencement date an answer states: a date (day month year, month
   and year, ISO, d/m/y) with a commencement cue in its own stretch of the sentence (between the
   neighbouring dates), or in a table row under a heading with the cue, unless the words just before
   it make it another event's date (Royal Assent, made, laid, "as of", "up to", today). Graded
   against what the **same conversation** retrieved (this turn and earlier ones): **SUPPORTED** (a
   source states that date for an instrument or provision the sentence names, or the three lines
   before, or the turn's question); **UNCLEAR** (the date retrieved but for something else, or for
   provisions the source does not list); **UNSUPPORTED** (no source shown to the Worker states it);
   **SUPPORTED_RAW_ONLY** (only a search row's description in the API response the tool did not pass
   on states it: every stored run before P3.6; reported, not failed, so before- and after-columns stay
   comparable). Sources: C's `changes[].in_force`; descriptions (`lookup_legislation`, a whole text's
   `legislation.description`, a search row's `description`); retrieved text (whole texts, section
   rows in **both** stored shapes). **A summary supports nothing** unless the raw result it summarised
   carries the same date. Also per turn: whether a commencement question got a SUPPORTED date where a
   relevant date was retrieved; for sessions in `COMMENCEMENT_TRUTH`, each known commencing instrument
   dated or not; C's hop status per change record; and the negative branch (`CMCDATE_NEGATIVE_BRANCH =
   {"6411"}`: any claim fails, or with `--negative-allows-supported` only a claim that is not
   SUPPORTED). Exits 1 on UNSUPPORTED or a negative-branch failure.
3. **`jurisdiction`** (P3.4 (b)). The graded turn (rubric `turns`, default 1, export turns for a
   script) names its jurisdiction: `scotland` (PASS on an explicit "Scotland/Scottish/Scots"; IMPLICIT,
   reported, when Scotland appears only in an instrument title, a link label or an institution; FAIL
   otherwise) or `uk_all` (all four nations named, "Great Britain" and "across the UK" expanded, AND a
   divergence or sameness flag; a bare "UK-wide Regulations" is not a flag). The expectation comes from
   the rubric or, where it gives none, from the question ("the UK" means uk_all). `--sentences` prints
   every sentence naming a nation, EXPLICIT or IMPLICIT.

Also: `server_py/tests/test_replay_batch9.py` (52 tests, synthetic), and the scripts
`docs/prepilot-fixes/evidence/scripts/p34_6378.json` and `p34_6360.json` (export turn 1,
Conversational under `legislation_only`; ids and indices only). Confirmed from the recorded evidence
(`python $S/check_scripts.py <worktree>/server_py`): both turn 1s are Conversational under
`legislation_only` by the feedback snapshot in `replay_set.json`, neither has a read in
`research_mode_reads.json`, neither carries a jurisdiction filter; `replay_set.scripted_session`
builds both (no network).

## 2. Item 1: P3.22's grader over the stored 6363 and 6359 directories

`python -m tools.replay_report --dir $E/baseline authorities --rubric $S/p322.json --also $E/wave1 $E/wave2`
(`$S/auth_stored.txt`; the rubric is batch 8 C's, one authority per row, roles below, names only in
the gitignored rubric).

| Item | 6363 (3 runs) | 6359 (3 runs) |
|---|---|---|
| 1, in-corpus authorities retrieved / read / cited (runs) | lead 3/3/3; others 2/2/2, 1/1/1, 3/2/2, 3/2/2, 3/3/3, 3/3/2 | the two Supreme Court cases 0/0/0 each; the carrier 3/3/3 |
| 2, the lead Supreme Court judgment retrieved | 3 of 3 | — |
| 3, out-of-corpus authority named | baseline t1 PASS x2, t5 EARLIER x2; wave1 t1 **FAIL**, t4 **FAIL**; wave2 t5 PASS x2 | baseline t6 PASS, t7 EARLIER; wave1 t6 PASS, t7 EARLIER; wave2 t6 **FAIL**, t7 **FAIL** |
| 4, the carrier by turn 7 | — | PASS 3 of 3 |

**Checks.** Item 1's per-turn retrieval agrees exactly with batch 8 C's independent count in
`rubric_check.txt` (the lead in 5 turns; the others 3, 1, 3, 4, 5, 4 turns; the carrier 8; the two
Supreme Court cases 0). **Hand-read: every item-3 verdict agrees with my reading** of the whole
answers (`$S/dump_clark.txt`, `$S/dump_6363_ooc.txt`): the four FAILs present an out-of-corpus
authority's test as if read, with no word that it came through another judgment or is not held; the
EARLIER turns state a principle by the authority's name after an earlier answer had said which
retrieved judgment cites it. Two first-draft errors were found on these answers and fixed before the
numbers above: a law report read as a carrier key (it is the out-of-corpus authority's own report),
and "as set out in X" read as second-hand. Every case-law request in these runs sent no `order`
(`none/- x18…x28`).

**What the stored columns can and cannot stand for.** They are one rep each at three heads of 14-18
September (`0884b29`, `6a5eeea`, `2d9ae11`): `baseline` predates P1.1, and all three predate the
case-law build (P4.19, P3.23, P3.9), P0.6, P4.1, P3.7, P3.13, P3.25, P3.27/P3.12 and everything since.
Their research type is right (the session filter carried `legislation_and_case_law`). They show
what the newest-first ordering returned and how the model named authorities then; they are **not**
P3.22's before-column (the user booked n=3 at a head without P3.22 and with the case-law build), and
must not be read against an after-column at today's head (Invariant 3).

## 3. Item 2: P3.21's grader over every stored 6409 and 6411 directory

`python -m tools.replay_report --dir $E/baseline cmcdates --all-dirs --session 6409 6411 --drops`
(`$S/cmcdates_stored.txt`; 59 directories globbed, so a new one changes the counts; 35 6409 runs:
17 full-session and 18 `p37_6409`; 11 6411 runs including two in `wave2_p25_smoke`).

**56 claims: SUPPORTED 50, SUPPORTED_RAW_ONLY 0, UNCLEAR 0, UNSUPPORTED 6.** Every claim listed with
its sentence in `$S/claims_stored.txt`. **Hand-read, all 56 agree with my reading:**

- The 47 SUPPORTED 6409 claims state one commencing instrument's date, each tied to that instrument's
  own `description` (a `lookup_legislation` record or a whole text's metadata) retrieved in the same
  turn or earlier; all true.
- **4 UNSUPPORTED on 6409, all true findings.** `wave4_p37` r1 t2 computes a self-commencement date
  from a Royal Assent date the same answer gives (and other runs give a different assent date).
  `wave4_p37_pre` r2 t2 states three dates **that only the summariser's text carried**: no retrieved
  source states them, and two attribute a commencement to the wrong date and provisions. This is
  P3.16's class (the summariser writing from training), now reaching commencement dates.
- **6411:** two UNSUPPORTED (the Royal Assent date, which only summaries state; the Act's own
  section ties it to the day of passing and states no date) and two SUPPORTED (the main appointed
  day, **stated by the Commencement Order's own article**, read by a section search).
- Per run: the first commencing instrument is dated in 30 of 35 6409 runs, **the second in 0 of 35**
  (no stored source states its date: LEX holds no record of it; P3.21's feed is the route), so P3.21's
  "both instruments" bar fails in every stored run (`python $S/per_run_6409.py $S/cmcdates_stored.txt`).
- **6411's negative branch as booked: 8 PASS, 3 FAIL** (`wave1`, `wave2`, one `wave2_p25_smoke` file);
  with `--negative-allows-supported`, 9 PASS, 2 FAIL (decision 2).
- Commencement questions: asked with a relevant date retrieved 114 turns, dated 25, not dated 89;
  asked with none retrieved 105 (3 of them stating a date).
- The drops (`--drops`) are every dated sentence not graded, with why: **10**, all read: 3 Royal
  Assent dates, 3 "up to" and 2 "as of" search dates, 1 today's date, 1 index sampling date. None is a
  commencement claim.

**Three first-draft errors found on these runs and fixed:** section-search results in the
`{"results": …}` shape were not read (4,748 of 5,314 stored section searches have it; the list shape
only 566: `python $S/sections_shape.py`), so the Commencement Order's article was invisible;
summaries counted as sources; and "up to <month year>" dates were claims.

**Not graded by any stored run:** C's feed dates, a split entry, the hop's statuses and P3.6's shown
descriptions. They are tested on synthetic input that mirrors C's own output-shape test (no stored run
contains these forms). **`commencements` still never grades a scripted run** (unchanged: it is in
the exit-1 set); `cmcdates` grades `p37_6409` through `from_turn`.

**`test_footer_trips_no_detector`: not edited, deliberately.** No product text trips the claim
detector today (`test_product_wording_states_no_commencement_date`: the currency limb with a
text-version date, the footer clause and P3.24's commencement lines, all with dates in them where
they carry one). C's gated wording **does** state dates; an echo of it is graded against the feed date
it came from (`test_an_echoed_feed_date_is_supported`), so a blanket "must not trip" assertion in the
shared test would be wrong for it and would collide with B's and C's additions there (decision 4).

## 4. Item 3: P3.4's scripts and check over the stored turn-1 answers

`python -m tools.replay_report --dir $E/baseline jurisdiction --rubric $S/p34.json --all-dirs --sentences`
(`$S/jx_stored.txt`). **13 turn-1 answers: 6360 FAIL 5 of 5** ("names no jurisdiction": each answers
under a UK statute and the rules that do not apply in Scotland); **6378 PASS 5, FAIL 3**: FAIL at
`baseline` and `wave1` (a revoked UK-wide regulation, no nation named) and `wave4_p37_reach_pre`
(all four named, England's position not flagged); PASS at `wave2`, `wave4_b7_p324` r1-3 and
`wave4_p37_reach` (all four, divergence flagged in words). **Hand-read: 13 of 13 agree** (every
sentence printed). One first-draft error fixed: "UK-wide" naming a revoked instrument had counted as
a sameness flag.

**Read the bar against the before-column (the lesson):** 6378 already passes in 5 of the 6 stored
reps since 18 September, so its after-column can only show the rule holding, not moving; 6360 is the
row's live test.

## 5. Item 4: the confound check

`python $S/confound.py` (`$S/confound.txt`, every directory). **Both directions are present:**
- stored 6363/6359: `wave2` 6363 r1 calls `get_legislation_changes` 6 times in its Deep Research turn
  1, **2 of them with a commencement by another instrument**, which is P3.21's hop trigger;
- stored 6409/6411: **every 6411 run calls `search_case_law`** (9 of 9 `_rep` files; 6411 runs
  under `legislation_and_case_law`); no 6409 run does (`legislation_only`).

**So P3.22's and P3.21's after-columns must be separate sweeps:** 2a with B merged and C not (6363,
6359), then merge C and run 2b (6409, 6411). Residual: 2b's 6411 runs with B's ordering and the stored
6411 before-column without it; 6411's criterion is about dates, not case law (decision 3).

## 6. Item 5: the sweeps priced

`python $S/inventory.py` then `python $S/price.py` (`$S/price.txt`): recorded `total_cost_usd` of
every stored rep in the recorded mode (a turn-1 script: each stored rep's turn-1 cost), median and
maximum, x n. `wave4_b8_sweep` is used where it has the run (6335; 6374's median; `p37r_6374`'s
maximum is its $0.82 lost-completion rep). **Cap per command = n x the recorded maximum of one rep**,
rounded up: `--max-spend` is checked between reps only, so the command runs all n reps while each
costs no more than that and stops early when they run hot; an n=1 command cannot be stopped, so check
its recorded maximum fits what remains before starting it. Invariant 4 from
`evidence/classification.json`: 6335, 6374, 6359, 6378, 6409, 6411 are FAIL; **6363 and 6360 are
DEFECT** (6363 is n=3 by the user's booking).

### Sweep 1 (head = Session 40 + A + E), `O=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay/wave4_b9_sweep1`

| Run | n | Inv. 4 | Median / rep | Max / rep | n x med | n x max | Grades |
|---|---|---|---|---|---|---|---|
| `6335` session (Conversational; t6-7 legislation and case law) | 3 | FAIL | $0.489 | $0.597 | $1.47 | $1.79 | P3.12: `depth` 6335 t7; `schedules` |
| `p37r_6374` script | 1 | FAIL, booked n=1 | $0.239 | $0.822 | $0.24 | $0.82 | P3.27's guard on export t3 |
| `6374` session (conv, DR, conv, DR) | 1 | FAIL, booked n=1 | $2.137 (b8) | $3.601 | $2.14 | $3.60 | P3.27's guard on DR t2, t4 |
| `6363` session (DR t1, t5) | 3 | DEFECT, booked n=3 | $2.011 | $2.124 | $6.03 | $6.37 | P3.22 before: `authorities` |
| `6359` session (Conversational x8) | 3 | FAIL | $1.130 | $1.486 | $3.39 | $4.46 | P3.22 before: `authorities` |
| `p34_6378` script (t1) | 3 | FAIL | $0.208 | $0.348 | $0.62 | $1.04 | P3.4 before: `jurisdiction` |
| `p34_6360` script (t1) | 1 | DEFECT | $0.071 | $0.086 | $0.07 | $0.09 | P3.4 before: `jurisdiction` |
| **Total** | | | | | **$13.96** | **$18.18** | |

6363's and 6359's stored reps are from 14-18 September heads; batch 8 C's allowance (one session's
cost grew about 1.5x between the earliest and latest heads) puts them at up to $9.56 and $6.69, **the
sweep at up to about $23.60**. Optional: `p34_6360` at n=3 as the row's acceptance text says (+$0.17
at maxima; decision 5).

```
python -m tools.replay run --session 6335 --reps 3 --out-dir $O --max-spend 1.80
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p37r_6374.json --reps 1 --out-dir $O --max-spend 0.90
python -m tools.replay run --session 6374 --reps 1 --out-dir $O --max-spend 3.70
python -m tools.replay run --session 6363 --reps 3 --out-dir $O --max-spend 6.40
python -m tools.replay run --session 6359 --reps 3 --out-dir $O --max-spend 4.50
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p34_6378.json --reps 3 --out-dir $O --max-spend 1.10
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p34_6360.json --reps 1 --out-dir $O --max-spend 0.10
```
P1 first (6335, the two 6374 runs), then P3.22's before-column, then P3.4's.

**Hand-reads sweep 1 needs:** the exit-1 set, `modes`, `negcurrency` (no `--all`), `footer_echo`; for
P3.12 `depth --answers --drops` (6335 t7, every verdict and drop) and `schedules --rubric
<p327.json> --session 6374 6335 --drops` (every 6374 slot), `route_trace.py`; for P3.22
`authorities` (every item-3 answer and its sentences; item 1/2 counts are the before-column for 2a;
confirm `none/-` orderings); for P3.4 `jurisdiction --sentences` (every verdict).

### Sweep 2a (head + B, not C): P3.22's after-column, `O=…/replay/wave4_b9_sweep2a`

| Run | n | Median / rep | Max / rep | n x med | n x max |
|---|---|---|---|---|---|
| `6363` | 3 | $2.011 | $2.124 | $6.03 | $6.37 |
| `6359` | 3 | $1.130 | $1.486 | $3.39 | $4.46 |
| **Total** | | | | **$9.42** | **$10.83** (up to about $16.25 at the 1.5x allowance) |

```
python -m tools.replay run --session 6363 --reps 3 --out-dir $O --max-spend 6.40
python -m tools.replay run --session 6359 --reps 3 --out-dir $O --max-spend 4.50
```
Grade: `python -m tools.replay_report --dir $O authorities --before $E/wave4_b9_sweep1` (items 1-2
against sweep 1; every request should read `relevance/50`), plus the exit-1 set. Hand-read every
item-3 answer, and each authority whose run count fell.

### Sweep 2b (head + B + C): P3.21's after-column, `O=…/replay/wave4_b9_sweep2b`

| Run | n | Median / rep | Max / rep | n x med | n x max |
|---|---|---|---|---|---|
| `p37_6409` script (recommended, decision 1) | 3 | $0.377 | $0.522 | $1.13 | $1.57 |
| `6411` session | 3 | $0.108 | $0.133 | $0.32 | $0.40 |
| **Total** | | | | **$1.45** | **$1.96** |
| *Alternative: full `6409` session in place of the script* | *3* | *$0.958* | *$1.910* | *$2.87* | *$5.73* |
| *Or the script plus full `6409` n=1* | *+1* | | | *+$0.96* | *+$1.91* |

```
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p37_6409.json --reps 3 --out-dir $O --max-spend 1.60
python -m tools.replay run --session 6411 --reps 3 --out-dir $O --max-spend 0.40
```
C's hop adds LEX proxy calls (no model cost) and at most a few hundred characters a change record
(batch 8 D: median 0, p90 156); every stored `p37_6409` run makes 3-9 change-record calls, each with
the hop's trigger (`confound.txt`), so the hop reaches the script. Grade: `python -m tools.replay_report
--dir $O cmcdates --session 6409 6411 --drops` (hand-read every claim, each turn's hop status and the
"commencing instruments" line: both must be DATED with source and qualification; the before-column is
`wave4_b8_sweep`'s `p37_6409`, at the head without A, and the stored 6411 runs); `commencements` does
not grade the script: read its turns by hand.

### Sweep 3 (P3.4's after-column; on D's merge order: its prompt commit `e46f93b` alone, before P3.6's `b48ad9f`), `O=…/replay/wave4_b9_sweep3`

| Run | n | Median / rep | Max / rep | n x med | n x max |
|---|---|---|---|---|---|
| `p34_6378` | 3 | $0.208 | $0.348 | $0.62 | $1.04 |
| `p34_6360` | 1 (or 3) | $0.071 | $0.086 | $0.07 | $0.09 ($0.26 at n=3) |
| **Total** | | | | **$0.69** | **$1.13** |

```
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p34_6378.json --reps 3 --out-dir $O --max-spend 1.10
python -m tools.replay run --script ../docs/prepilot-fixes/evidence/scripts/p34_6360.json --reps 1 --out-dir $O --max-spend 0.10
```
Grade: `jurisdiction --sentences` on sweep 1 and sweep 3; hand-read every verdict, and the delegation
brief of each turn (D's prompt reaches the conversational Manager's first round: P3.13's lesson).

**All four sweeps: $25.52 at medians, $32.10 at recorded maxima** (sweep 1 $13.96 / $18.18, 2a $9.42 /
$10.83, 2b $1.45 / $1.96, 3 $0.69 / $1.13), more at the allowance for 6363 and 6359.

## 7. Tests, revert, mutants, identity, suite

- **52 tests** in `server_py/tests/test_replay_batch9.py`, all synthetic.
- **Full revert** (`replay_report.py` back to `ca3d45c`: 1,171 lines removed) on a scratch copy
  (`$S/rev/`, never the worktree): **50 failed, 2 passed**; the 2 are the script checks, which do not
  read `replay_report` (`python $S/mutants.py <worktree>`, `$S/mutants.txt`).
- **66 single-site mutants, each anchor asserted to occur exactly once (CRLF kept): 66 caught, 0
  survive.** One per guard and cleaning step: the law-report exclusion, the division in the key, the
  `/id/` URL form, LINKED, NOT_HELD, the source-phrase object guard, the window carrier, "the …
  judgments", a citing word alone, EARLIER, LINKED per answer, the carrier's need-turn bound and
  reach, the named-only drop, the rubric keys in "others", `--before`'s rates, both FAIL tallies, the
  row's NCN field, the request ordering; another event's date, the Royal Assent claim, "up to", the
  per-date stretch (cue and provisions, both directions), the cue itself, the table heading and its
  reset, summaries (excluded, upgraded by their raw result), both section shapes, window and question
  naming, the provisions over-claim, the tie by provisions, the `in_force` map, the `by` direction,
  C's dict status and its counts, the negative branch and its option, UNSUPPORTED failing, relevant
  dates only, the conversation carry-over, the two notes, date validity, the instrument "retrieved"
  flag, the raw-only class (graded, for something else, counted as retrieved, shown and API rows);
  the title, institution and link-label masking (masked and reported), GB and "across the UK", the
  bare "UK-wide", the question's expectation, the graded turns, IMPLICIT, other-nations-only, the
  flag requirement. Two survived the first run (the per-date cue stretch, link-label masking); a test
  was added for each. A de-duplication of a shown description against the API's copy was later
  removed as wrong (a date past P3.6's cut was never seen), with its test changed to say so.
- **Existing graders unchanged:** `python $S/identity.py <worktree>` runs the 16 exit-1 graders and
  `negcurrency` (without `--all`) with the base and the built module over all 59 directories:
  **1,003 of 1,003 outputs and exits identical** (`$S/identity.txt`). By construction too: the diff
  is insertions only and adds no name the base had.
- **Full suite on `lexchat_test_e`: 2534 passed** (2482 + 52), after the last code change.
- **Data handling:** every staged diff screened with `$S/matter_grep.py` (case names, topic words,
  session instrument ids, citations outside 1899-1902): 0 hits at each commit; three comments and one
  test string replaced with synthetic ones before the first commit.

## 8. Found on the way, not fixed (other graders; listed for the integrator)

1. **`negcurrency` reads section-search results only in the list shape** (`negcurrency_evidence`,
   `isinstance(o, list)`), so a commencement provision retrieved by section search in the
   `{"results": …}` shape (4,748 of 5,314 stored section searches, from `wave0_conv` on) never reaches
   its `cmc_provisions`. Its UNCLEAR branches on an instrument's own commencement provision are
   therefore blind on almost every directory since September. Not touched (decision 6).
2. **`cmd_corpus`'s label "<- _slim_search_results strips it (P3.6)" goes stale on D's merge**
   (integrator's note); not touched, to keep the exit-1 set's output identical.
3. **The integrator's note that stored runs carry a search row's description in `raw_result`:** in
   the runs I read it is in `api_calls[].response` only; `raw_result` is the slimmed list without it
   (`python $S/peek2.py <dir/file>`). The grader reads both, so this changes nothing; D's count of 32
   turns may rest on the API response.
4. **Summarised change records and case-law searches state commencement dates the records do not
   carry** (6411's stored runs; `$S/scan_sources.py`), a P3.16-class leak into exactly the date P3.21
   supplies.

## 9. What I did NOT do

- No product code; no model call, server, replay or external call.
- No edit to FIX_PLAN, SESSION_LOG, the tracker, CHANGELOG, CLAUDE.md, any existing rubric, the lawyer
  pack, `test_search_scope.py` or memory; the rubrics are in my scratch for the integrator to copy.
- No change to `commencements`' blind spot for scripted runs, `negcurrency`, or `cmd_corpus`.
- Not pushed, not merged.

## 10. Decisions for the user (or the integrator)

1. **P3.21's after-column form.**
   1. **(Recommended) `p37_6409` n=3 ($1.13 at medians, up to $1.57):** 18 stored reps in the same form
      (the latest at the head without A) are its before-column, every stored rep reaches the hop's
      trigger, and its turns ask about both commencing instruments.
   2. Full `6409` n=3 ($2.87, up to $5.73): adds the Deep Research turn and the "made yet?" turns, but
      its 17 stored reps are all from before P3.7, so the before-column is a different product.
   3. The script n=3 plus full `6409` n=1 (+$0.96, up to +$1.91): the script decides; the full run is
      a look at the Deep Research path.
2. **6411's negative branch.** On the stored runs the model can read the Commencement Order's own
   article, which states the appointed day (2 of 11 runs state it, SUPPORTED and true).
   1. **(Recommended) Fail only a date that is not SUPPORTED** (`--negative-allows-supported`): the
      negative branch was set because neither the feed nor the description dates 6411's Act's change
      record, not because no source states a date; failing a true, retrieved date pushes toward
      suppression (Invariant 1). Stored: 9 PASS, 2 FAIL.
   2. **As booked, fail any date stated.** Stored: 8 PASS, 3 FAIL.
3. **Sweep 2's split.**
   1. **(Recommended) Two sweeps, 2a (B) then 2b (B + C), as the brief says:** the confound runs both
      ways; accept that 2b's 6411 runs under B's ordering while its stored before-column did not.
   2. Add 6411 n=3 to sweep 2a as a before-column at head + B (+$0.32, up to $0.40), so 2b's 6411
      differs from it by C alone.
4. **Registering `cmcdates` in `test_footer_trips_no_detector`.**
   1. **(Recommended) Leave the shared test alone:** no product text states a date today (pinned in my
      test); C's wording states dates by design and is graded SUPPORTED against its own record. When C
      merges, the integrator runs `cd_claims` over C's new sentences and checks each date is one the
      record carries (`test_an_echoed_feed_date_is_supported` is the pattern).
   2. Add a blanket "states no date" assertion there: it would fail on C's wording, by design.
5. **`p34_6360`'s n.** 6360 is DEFECT (Invariant 4: n=1); P3.4's acceptance text says n=3.
   1. **(Recommended) n=3 in both columns (+$0.17 a column at maxima):** the row's own booking, and
      6360 is the session the change has to move.
   2. n=1 per Invariant 4.
6. **`negcurrency`'s section-search shape gap** (section 8.1).
   1. **(Recommended) Fix it in a separate tooling commit before P3.24's next measurement**, with an
      identity run listing every verdict that moves (it is not in the exit-1 set).
   2. Leave it and note the gap on P3.24's row.

## Follow-up (integrator)

**The gap.** The integrator's mutant in `cmd_cmcdates` survived all 52 tests. It changed
`not (args.negative_allows_supported and v == "SUPPORTED")` to `not (args.negative_allows_supported)`.
No test ran `--negative-allows-supported`, so under that option an UNCLEAR or SUPPORTED_RAW_ONLY
claim on the negative branch could pass, and nothing would notice.

**Closed** with one parametrised test, `test_the_negative_branch_with_and_without_the_option`. It
has 5 cases on a synthetic negative-branch session (`CMCDATE_NEGATIVE_BRANCH` monkeypatched), and
each case runs once without the option and once with it:

| Case | Verdict | Exit without the option | Exit with it |
|---|---|---|---|
| a date the source states | SUPPORTED | 1 | 0 |
| a date stated for another instrument | UNCLEAR | 1 | 1 |
| a date only in an unseen API response | SUPPORTED_RAW_ONLY | 1 | 1 |
| a date no source states | UNSUPPORTED | 1 | 1 |
| no date stated | none | 0 | 0 |

**Mutants** (`python $S/mutants.py <worktree>`; every anchor asserted to occur exactly once, CRLF
kept). **68 mutants, 0 survive.** The three that bear on the option:

| Mutant | Tests failed | Which |
|---|---|---|
| The integrator's (the option passes every verdict) | 2 | the UNCLEAR and SUPPORTED_RAW_ONLY cases |
| Mine on the option's argparse wiring (`action="store_false"`) | 2 | |
| The earlier "option ignored" mutant | 2 | |

The full revert fails 55 of 57 tests.

**Tests:** 57 in the file. **Full suite on `lexchat_test_e`: 2539 passed.**
