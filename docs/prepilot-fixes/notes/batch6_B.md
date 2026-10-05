# Parallel batch 6, agent B: P3.24 measured (negative commencement claims)

Session 38, 2026-10-05. Branch `worktree-agent-a7705dc90413ad439`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard 995ef3415ab3b359353fb455b217ab28223e6982` before any work.** Everything below is
based on `995ef34`.

**Spend: $0.** No model call, no API call of any kind (no LEX, National Archives or
legislation.gov.uk), no server, no replay pin/run/restore. **No product code changed:** the change is
`server_py/tools/replay_report.py` (a new subcommand), a new test file, and the registration in
`tests/test_search_scope.py::test_footer_trips_no_detector`. Full suite on `lexchat_test_b`: **2183
passed** (2162 + 21 new), `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b
python -m pytest -q -p no:cacheprovider` from `server_py/`.

This note quotes no lawyer's question or answer, no search term and no instrument id or title from a
session. Matches are cited by directory, session, rep and turn. The hand-read, which quotes matter
text, is in the gitignored scratch. Commands run from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and `PYTHONIOENCODING=utf-8`;
`$R` is `$PREPILOT_EVIDENCE/replay` and `$S` is `$PREPILOT_EVIDENCE/seam/batch6/B`.

## 1. Result in one paragraph

On the pinned model (`google/gemini-3.1-pro-preview`, every stored turn), the defect Thomas reports
on `glm-5.2:cloud` **does not appear in any directory taken after P3.5 and P2.5.** Over all 57
stored directories the detector grades **178 claims in 142 of 1,943 answered turns: 144 SUPPORTED,
32 UNSUPPORTED, 2 UNCLEAR**. All 32 unsupported claims sit in directories taken before P3.5/P2.5
(30) or in the Wave 2 re-baseline (2). The 34 `wave3_*`/`wave4_*` directories hold 69 claims in 907
answered turns, 68 SUPPORTED and 1 UNCLEAR (which the hand-read resolves as supported), **0
UNSUPPORTED**. On 6410 and 6378 on their own: 3 unsupported claims, all on 6410 and all before
P3.5; **0 in the 9 run files from `wave2` on**; 6378 never says "remains in force" in any of its 5
stored runs. The hand-read overturns **3 of the 178 verdicts** (none from UNSUPPORTED to SUPPORTED
or back). **The consequence for the booked acceptance:** a replay of 6410 and 6378 at n=3 on the
pinned model is predicted to pass with or without a lever, so on that model alone it cannot tell a
lever from no lever (decision 2).

## 2. What I built, and why it is shaped this way

`python -m tools.replay_report --dir <dir> negcurrency [--all] [--sessions 6410,6378] [--drops]
[--verbose]`. With `--all`, `--dir` is the replay root and every subdirectory is walked, with a
per-directory table. For each answered turn (footer stripped, as `currency` does), it lists every
sentence making one of five kinds of claim and grades it against **what the conversation retrieved**
(this turn and the earlier turns of the same run, the reason saying when an earlier turn decided it):

| Kind | Example shape (synthetic) | SUPPORTED when | UNSUPPORTED when |
|---|---|---|---|
| `not_yet` | "Sections 3 and 4 are not yet in force" | a change record for the instrument holds commencement relations **by another instrument**, listed in full, and none names the provision | no change record; or the one consulted holds no commencement relation (the era gap); or only the instrument's own commencement section was read (it names the mechanism, not its use); or the record lists the provision as commenced; or the whole instrument is denied while the record lists commencements of it |
| `partial` | "The Act is partially in force" | as `not_yet`, but the provisions it names are never read as denied (they are the ones that ARE in force) | as `not_yet` |
| `no_longer` | "The Order is no longer in force" | a removal relation naming the provision; or, for the whole instrument, a removal of the instrument itself or its title marker, for an instrument the sentence names | no removal relation and no marker |
| `not_in_force` | "Section 9 is not in force" | either of the two above | both unsupported |
| `continuing` | "The prohibition remains in force" | a commencement relation naming it and a complete record with no removal of it; "remains on the statute book": a complete record of removals, none of the instrument | no record, or the record shows it removed |

UNCLEAR is the remainder a reader must weigh: a truncated record, a record whose only commencement
relations are the instrument's own, a commencement provision fixing a calendar date, a `valid_date`,
a removal relation not tied to the sentence's subject.

Not claims, printed as drops with the reason: questions, quoted statutory text, conditional or
subordinate uses, hedged ones (may/might/could/would/appears/unclear; **not** "likely", which leans
on the absence as hard as the bare form), and the P2.5 disclaimer, read on its own clause. A
statement about the record ("not yet recorded as commenced") is not matched at all.

**Eleven corrections were made while building it, each found by reading a match or a drop**, and each
has a test that fails with it reverted (section 5):

1. **A self-referential `coming into force` relation is not a commencement.** An Act's own
   commencement section is listed against every provision it governs, including those it leaves to
   regulations; the first draft read such a group as "the record lists s. 1 as commenced" and graded
   a true negative (the row's Invariant 1 case, `wave3_p35`) as contradicted. 100 of the 518 stored
   "to" records holding any commencement relation hold only self-referential ones (26 ids: 24 SIs,
   where the self relation is the SI's own commencement, one EU regulation and one Act).
2. "Partially in force" is its own kind; read as `not_yet`, it graded the commenced provisions it
   names as denied.
3. Evidence is the conversation's: 7 follow-ups ("as noted, it is partially in force") were graded
   unsupported on their own turn's trace.
4. "likely" is not a hedge (3 sentences inferring "not yet in force" from an empty search).
5. The disclaimer guard reads the clause, not the sentence (2 sentences claimed in one clause and
   disclaimed in the next).
6. A provision written after another instrument's citation ("revoked by SI …, reg. 2(c)") or a
   title's year ("… Regulations 2013") is not the claim's subject.
7. A whole-instrument removal supports only the instrument the sentence names: read off every record
   in the turn, an unrelated instrument's revocation "supported" a sentence about another.
8. "This instrument" is named by the three sentences before it (a bullet heading, a count line, then
   the claim).
9. "No longer applies" is a `no_longer` claim (found by the coverage probe).
10. **The removal family is wider than the product's own** (`_REPEAL_EFFECT_TOKENS`): the feed also
   writes a removal as `omitted`, `rev (saving)`, `rev in pt (…)` and `ceases to have effect`. See
   finding F1.
11. A commencement provision without a change record lifts "not yet" only when it fixes a calendar
   date; otherwise it names the mechanism and the negative is still read from an absence.

## 3. Measurement

**Every directory:** `python -m tools.replay_report --dir $R negcurrency --all` (add `--verbose
--drops` for every match and drop; `$S/run_final_all.txt`). Directories with no claim are omitted
from the table; there are 57 in all.

| directory | answered | turns w/ claim | claims | SUPP | UNSUP | UNCLR |
|---|---|---|---|---|---|---|
| baseline | 222 | 6 | 8 | 0 | 8 | 0 |
| wave0_conv | 50 | 2 | 4 | 3 | 1 | 0 |
| wave1 | 153 | 3 | 4 | 0 | 4 | 0 |
| wave2 | 155 | 16 | 20 | 18 | 2 | 0 |
| wave2_p22 | 36 | 6 | 6 | 0 | 6 | 0 |
| wave2_p22_final | 36 | 6 | 10 | 0 | 10 | 0 |
| wave2_p23 | 29 | 1 | 1 | 0 | 1 | 0 |
| wave2_p24_final | 27 | 1 | 1 | 1 | 0 | 0 |
| wave2_p24_smoke | 9 | 1 | 1 | 1 | 0 | 0 |
| wave2_p25 | 42 | 12 | 18 | 18 | 0 | 0 |
| wave2_p25b | 7 | 1 | 1 | 1 | 0 | 0 |
| wave2_p27 | 36 | 9 | 10 | 10 | 0 | 0 |
| wave2_p27_pre | 36 | 11 | 12 | 12 | 0 | 0 |
| wave2_p27_smoke | 12 | 2 | 3 | 2 | 0 | 1 |
| wave2_p28 | 57 | 6 | 7 | 7 | 0 | 0 |
| wave2_p28_smoke | 19 | 2 | 3 | 3 | 0 | 0 |
| wave3_p31 | 18 | 3 | 3 | 3 | 0 | 0 |
| wave3_p311 | 13 | 2 | 2 | 2 | 0 | 0 |
| wave3_p31_pre | 18 | 3 | 3 | 3 | 0 | 0 |
| wave3_p31_smoke | 6 | 1 | 1 | 1 | 0 | 0 |
| wave3_p35 | 51 | 16 | 23 | 23 | 0 | 0 |
| wave3_p38 | 24 | 6 | 9 | 9 | 0 | 0 |
| wave4_b1_post | 78 | 1 | 1 | 1 | 0 | 0 |
| wave4_b2_post | 78 | 1 | 1 | 1 | 0 | 0 |
| wave4_p315_pre | 30 | 3 | 3 | 3 | 0 | 0 |
| wave4_p33_post | 78 | 1 | 1 | 1 | 0 | 0 |
| wave4_p33_pre | 33 | 1 | 1 | 1 | 0 | 0 |
| wave4_p37 | 30 | 5 | 5 | 5 | 0 | 0 |
| wave4_p37_pre | 30 | 3 | 3 | 3 | 0 | 0 |
| wave4_p37_reach | 12 | 2 | 2 | 1 | 0 | 1 |
| wave4_p37_reach_pre | 12 | 1 | 1 | 1 | 0 | 0 |
| wave4_p37b | 30 | 2 | 2 | 2 | 0 | 0 |
| wave4_p37c | 30 | 3 | 3 | 3 | 0 | 0 |
| wave4_p41_pre | 21 | 1 | 3 | 3 | 0 | 0 |
| wave4_p46_pre | 49 | 1 | 1 | 1 | 0 | 0 |
| wave4_p47 | 1 | 1 | 1 | 1 | 0 | 0 |
| **TOTAL (57 dirs)** | **1,943** | **142** | **178** | **144** | **32** | **2** |

Turns with an unsupported claim: **25 of 1,943**. Drops: 217. By kind (SUPP / UNSUP / UNCLR):
`not_yet` 15 (7 / 8 / 0), `partial` 61 (43 / 18 / 0), `no_longer` 95 (93 / 0 / 2), `not_in_force` 1
(0 / 1 / 0), `continuing` 6 (1 / 5 / 0). Of the 178, P2.5's `_currency_asserted` sees 5 (all
`continuing` or a Status line), confirming the blind spot the row describes.

**By era** (`python $S/eras.py`, which imports this worktree's built code):

| era | dirs | answered | claims | SUPP | UNSUP | UNCLR | turns w/ UNSUP |
|---|---|---|---|---|---|---|---|
| A: baseline, wave0_*, wave1, wave2_p21-p24 | 14 | 670 | 35 | 5 | 30 | 0 | 23 |
| B: wave2 re-baseline, wave2_p25-p28 | 9 | 366 | 74 | 71 | 2 | 1 | 2 |
| C: wave3_*, wave4_* | 34 | 907 | 69 | 68 | 0 | 1 | 0 |

Era A's 30 unsupported claims are all in directories taken before P3.5 (Sessions 2 to 7:
`baseline`, `wave0_conv`, `wave1`, `wave2_p22`, `wave2_p22_final`, `wave2_p23`); its `wave2_p24*`
directories (Session 14) hold none. Era B's 2 are in `wave2` (Session 16): 6385 r1 t1 (a
`continuing` claim read from a judgment) and 6411 r1 t1 (`partial`, read from a record with no
commencement relation).

**6410 and 6378 on their own:** `python -m tools.replay_report --dir $R negcurrency --all --sessions
6410,6378` (and each alone). 6410: 8 run files, 16 answered turns, 9 claims: 6 SUPPORTED, 3
UNSUPPORTED (`baseline` r1 t1; `wave1` r1 t1 twice), 0 UNCLEAR; 0 unsupported in its 6 run files
from `wave2` on. 6378: 5 run files, 10 answered turns, 1 claim (`wave4_p37_reach` r1 t1, UNCLEAR,
supported by hand), 0 unsupported. Thomas's shapes ("Not yet commenced" lists on 6410; "remains in
force" on 6378) are not reproduced by any stored run on the pinned model.

## 4. The hand-read (`$S/handread_p324.md`, gitignored)

Every UNSUPPORTED and UNCLEAR match was read (34), with its question, context and the conversation's
evidence (`$S/dossier_unsup_unclear.txt`, built by `$S/dossier.py` on this worktree's code); the 144
SUPPORTED were read as a listing (`$S/dossier_supported.txt`); the 217 drops were read; and a
coverage probe (`$S/coverage_probe.py`) printed 59 distinct sentences in a wider vocabulary that the
detector does not see.

- **Overturned: 3 of 178.** `wave0_conv` 6341 r1 t8, twice (one UNSUPPORTED, one SUPPORTED): a
  generic definition of why a text can be a stub, naming no provision, so not a claim at all.
  `wave4_p37_reach` 6378 r1 t1 (UNCLEAR): supported, because the instrument and its removal
  relation are named in the following sentence, which the detector does not look ahead to.
- **Agreed: 31 UNSUPPORTED and 1 UNCLEAR** (`wave2_p27_smoke` 6374 r1 t4, half supported: the
  record holds one of the two revocations the sentence cites). No SUPPORTED verdict was found
  unsupported and no UNSUPPORTED one supported.
- Several unsupported negatives are **true in fact** (unsupported is not false): the "partially in
  force" sentences on 6409 and 6410 before P3.5. Others are false in fact: the inference from no
  commencement regulations having been found to the remainder not being in force (6409 and 6410,
  before P3.5), which is P3.5's before-column.
- **Known misses** (coverage probe): 3 continuing claims worded with "valid" or "applicable" rather
  than "in force", all on 6385 or 6408 (`wave2_p24_ab`, `wave4_p46`, `wave1`). Not added: that
  vocabulary would pull in case-law validity and application statements. The drops held no missed
  claim.

## 5. Tests and revert proofs

`tests/test_negcurrency.py`, 21 tests on synthetic text ("Widget (Scotland) Act 1901",
`asp/1901/1`, `ssi/1901/3`). Run on a scratch copy of `server_py` by `$S/revert_b.py` (output
`$S/revert_b_out.txt`):

- **Whole change reverted** (the block, the parser and dispatch lines: **791 lines removed** from
  `replay_report.py`; and the registration: **30 lines** from `test_search_scope.py`):
  `test_negcurrency.py` fails at collection (ImportError, all 21 tests).
- **The registration with the detector reverted:** `test_footer_trips_no_detector` fails
  (ImportError). **The registration bites:** with the lookup clause reworded (scratch copy only) to
  "... and the provisions remain in force", the footer test fails on
  `assert negcurrency_claim(s)[0] is None`.
- **Nine targeted reverts, one line each (one is two lines)**, each failing the test written for it:
  self relations counted (1 test fails); `partial` folded into `not_yet` (3); removal family narrowed
  to the product's tokens (1); whole-instrument removal read off every record (1); earlier turns
  ignored (1); "likely" a hedge (1); disclaimer on the whole sentence (1); a commencement provision
  lifting "not yet" to UNCLEAR (1); the record-contradiction check removed (1).

**Registration:** `test_footer_trips_no_detector` now builds the whole footer with every clause at
once (search, both enabling branches, the change-record clause empty, found and truncated, the three
currency branches, and the lookup clause for not held and held without text) and asserts no
sentence of it is a claim. **It passes: no existing footer clause trips the detector**, so there is
no footer decision to put. The edit is confined to that test, after its last assertion. Agent C's
reworded lookup clause will be screened by it on merge (merge B before C, then run
`tests/test_search_scope.py`).

## 6. Findings beside the row (not acted on)

- **F1: the product under-counts removals.** `_REPEAL_EFFECT_TOKENS` (`lex.py`) counts
  repeal/revoke/revocation only. Over every stored change-record result (`python $S/removal_gap.py`):
  **639 of 1,435 calls** carry a removal effect it does not count (`omitted`, `ceases`/`ceased to have
  effect`, `entry omitted`, `rev …`), and in **156 calls (21 distinct instruments) the product's
  `repeal_or_revocation_relations` is 0 while a removal is present.** That count feeds
  `_currency_limb`, the P2.5 footer clause and P2.5's grader, so all three read "no repeal" where the
  record shows one. (6378's stored `wave4_p37_reach` turn is one: the model read the `omitted` group
  and was right; the product's count said 0.)
- **F2:** 841 of the 1,359 stored "to" change records (62%) hold no commencement relation at all;
  any negative read from one of them is this row's defect shape.
- **F3:** the product's `provisions_commenced`, and P2.5's `_currency_support`, count
  self-referential relations as commencements (100 records hold only those). For an SI that is its
  own commencement; for an Act it is the commencement section, which is not evidence that a
  provision has commenced. One Act among the 26 instruments; small, but the limb's "Commencement
  relations WERE retrieved for X" is then said of an Act none of whose provisions the record shows
  commenced.

## 7. What I did NOT do

No lever built (no prompt, limb or footer change); no replay; no edit to `search_scope.py`,
`lex.py`, FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md, TODO, the tracker, a rubric or the pack. F1 to
F3 are not fixed. The detector is not run on Thomas's glm answers (none are stored). The three known
misses were not added.

## 8. Decisions for the user

**Decision 1: the lever.**
- **(a) Recommended: both, the code line first.** A per-instrument line in `_currency_limb`, computed
  from the record: for an instrument whose record holds commencement relations by another
  instrument, a provision not among them may be stated as "not recorded as commenced"; for one whose
  record holds none, or which was not consulted, say no provision of it is shown commenced or
  uncommenced and do not state either. Plus one sentence beside `_IN_FORCE_RULE` (the three
  legislation Worker prompts and the conversational ones) pointing at it. Invariant 2, and the
  part that survives a change of model, which is where this defect lives.
- (b) The code line only. Cheapest to keep honest; relies on the model reading the block.
- (c) The prompt rule only. No per-instrument fact; the weakest under Invariant 2.
- (d) No lever until the defect is reproduced on a model we replay (see decision 2): on the pinned
  model there is nothing in 907 post-fix turns for a lever to move.

**Decision 2: the acceptance to book.** The row's: n=3 on 6410 and 6378, no unsupported negative or
continuing claim (graded by `negcurrency`, with the hand-read), true ones still stated.
- **(a) Recommended: run it on both models.** On `glm-5.2:cloud` (Thomas's), where it reproduces, as
  the discriminating test; on the pinned Gemini as the suppression and regression check (Invariant
  1: 6410's "partially in force" and the uncommenced remainder must still be stated). Needs a replay
  pin to the Ollama provider with `glm-5.2:cloud`, which no stored run has used.
- (b) The pinned model only, as booked. Predicted to pass with or without a lever (0 unsupported in
  the 9 post-P3.5 run files of these sessions), so it measures nothing about the lever.
- (c) glm only. Discriminating, but loses the pinned model's suppression check.
- (d) Widen the session set to the other sessions where `negcurrency` has found an unsupported
  claim (6341, 6363, 6374, 6385, 6409, 6411; 6341's is the generic definition): on Gemini all but
  6385 and 6411 (`wave2`) are pre-fix, so this adds cost, not signal, unless run on glm.

**Decision 3: the replay figure** (for decision 2). From `total_cost_usd` at the top of each stored
run file (equal to the sum of `turns[].timing.total_cost_usd`; `$S/replay_cost.txt`), in the two most
recent directories holding both sessions, `wave4_p37_reach` and `wave4_p37_reach_pre`: 6410 $0.124
and $0.106, 6378 $0.217 and $0.185. **n=3 of both on the pinned model: about $0.95**; at the
highest recorded cost of each (6410 $0.124, 6378 $0.312 in `wave1`), **$1.31**. Wall clock 0.7 to 3.0
minutes a run file. A glm run is not priced from stored data (none exists).
- **(a) Recommended: authorise up to $1.31 on the pinned model, and price glm separately** before it
  runs.
- (b) Authorise the pinned model only.
- (c) Defer the replay until the lever is chosen.

**Decision 4: F1 (removals under-counted).**
- **(a) Recommended: book a new row (P3), measure first:** widen `_REPEAL_EFFECT_TOKENS` to the
  measured effect strings, with the 156 calls as the dry-run set. It moves P2.5's grader and limb, so
  it needs a re-run of `currency` over every directory before and after.
- (b) Fold it into P4.20 (the change-record lists on the footer), which touches the same counts.
- (c) Record it in `docs/TODO.md` only.

**Decision 5: the detector's known limits** (two generic definitions read as claims, one deictic
tied forward, three "valid/applicable" misses).
- **(a) Recommended: accept, and hand-read every after-column** as this note did; the limits are 3
  of 178 verdicts plus 3 misses.
- (b) Add a generic-definition guard and look-ahead naming now, measured over every directory.
- (c) Add "remains valid/applicable" to the vocabulary (pulls in case-law validity statements).

## Scratch

Worktree scratch `docs/prepilot-fixes/evidence/seam/batch6/B/` (gitignored; checked with
`git check-ignore -v`), copied to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch6/B/`
with `cp -r`. It holds the hand-read, the dossiers, every run's output (`run1_all.txt` to
`run_final_all.txt`, the first drafts included), the block source and its inserter, `revert_b.py`,
`eras.py`, `removal_gap.py`, `coverage_probe.py` and `replay_cost.txt`.
