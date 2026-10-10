# Batch 6, agent C: P4.21, the lookup footer's "not a sign that the citation is wrong" (Session 38, 2026-10-05)

## The sentence, for the user before merge

A lawyer reads this. It is the clause P3.7's code appends to the answer's `*Search scope: …*`
footer whenever a lookup finds that an instrument named by number is not held. Shown with a
synthetic id.

**Built (recommended, R1):**

> SSI 1901/3 was looked up by its number and is not held in this index, which is incomplete; that
> does not show whether the number is accurate.

Plural: "SSI 1901/3 and SSI 1902/4 were looked up by their numbers and are not held in this index,
which is incomplete; that does not show whether the numbers are accurate."

**Was:**

> SSI 1901/3 was looked up by its number and is not held in this index; that is a gap in the index,
> not a sign that the citation is wrong.

**Alternatives screened** (each passed every check below; none built):

- **R2 (shortest):** "SSI 1901/3 was looked up by its number and is not held in this index; a lookup
  cannot show whether the number is accurate."
- **R3 (adds the base rate):** "SSI 1901/3 was looked up by its number and is not held in this index,
  which is incomplete, recent instruments least of all; that does not show whether the number is
  accurate."

**Screened and rejected:** the brief's own phrasing, "…a lookup cannot show whether the number is
**right**", and a two-sentence version ("That shows only what this index holds, which is
incomplete; it does not show whether the number is right."). Both add a match the old clause does
not have: `OPENER_VOCAB` (the capitulation-opener grader) matches "right". The two-sentence version
also gives the sentence splitters a second sentence (`_OP_END`, `_STANCE_SENT`). The footer is
stripped before either grader reads an answer, so neither match would have changed a verdict.
Choosing "accurate" means the claim of "no new match" holds without relying on the strip.

**Why R1:** it states only what the lookup established (looked up by its number; not held in this
index). It gives the one true general fact, that the index is incomplete (`LEX_COVERAGE_SENTENCE`),
without saying that this is why this instrument is missing. It also says the result settles nothing
about the number. So it neither vouches for the citation (Thomas's point) nor asks the lawyer to
check it (P2.4's defect). R2 is shorter, but without "which is incomplete" a lawyer is left with
only the doubt. R3 adds "recent instruments least of all", a house phrase that is true in
aggregate. It is also a second claim the lawyer cannot check from the answer.

**Base:** the worktree came up on `main` at `a6b4a76`, not on the integrator's head. It had no
commits, so I ran `git reset --hard 995ef34` before any work. Everything here is based on `995ef34`.
**Spend: $0.** No model call, no server, no `replay pin|run|restore`, and no call to LEX, the
National Archives or legislation.gov.uk. **Model:** the clause is written by code, so it does not
depend on the model. Every stored answer re-screened here ran on the pinned Gemini. Thomas's figure
(9 of 35 answers, on `glm-5.2:cloud`) cannot be checked here.

## Acceptance (P4.21's row), stated before any claim

| Check | Result |
|---|---|
| New wording in a unit test that fails with the change reverted | **Passes.** 3 tests fail on the reverted copy (below) |
| Every stored footer rebuilt and re-screened against every detector | **Passes.** 69 of 69 clauses rebuilt by the built code; 140 of 140 grader runs byte-identical before and after |
| P3.7's and P2.4's citation-blame readouts unchanged (`lookup`, before/after, over the directories holding the two sessions) | **Passes.** All 18 directories `SAME` |

## What changed

- `server_py/src/utils/search_scope.py`, `_lookup_footer_clause`. The not-held branch now ends
  ", which is incomplete; that does not show whether the number is (numbers are) accurate.". This is
  3 code lines in place of 2, plus an 11-line docstring paragraph giving the reason. The opening up
  to "not held in this index" is unchanged, so `_EARLIER_LOOKUP` still parses an earlier footer in
  either wording. Answers stored before deploy carry the old wording, and a follow-up reads them
  from history. The "held without text" branch is unchanged.
- `server_py/tests/test_instrument_lookup.py`:
  - P3.7's pinned-wording assertion is updated (one line, which already named the session's
    instrument id; the id is unchanged).
  - Three new tests, synthetic ids only:
    - `test_p421_the_not_held_clause_states_what_the_lookup_established` pins the exact sentence,
      singular and plural, with no "citation", "not a sign" or "gap in the index".
    - `test_p421_the_clause_neither_blames_the_citation_nor_concedes` checks `LK_BLAME`,
      `NEG_BLAMED_USER`, `OPENER_VOCAB`, and that `_lk_classify` never returns "blame".
    - `test_p421_an_earlier_footer_in_either_wording_is_read_back_and_restated_new` checks that the
      old and the new footer both round-trip through `_earlier_lookups`, and that a restatement of
      an old footer comes out in the new wording.
- `server_py/tests/test_search_scope.py::test_footer_trips_no_detector`: **one appended block
  (15 lines, one of them blank) at the end of the function**, nothing above it touched. It builds the lookup clause
  (both branches) and asserts `NEG_ASSERTED`, `derivation_claims`, `IN_FORCE_CLAIM`, P3.5's
  commencement denial and `_currency_asserted` per sentence. The clause's docstring has said since
  P3.7 that it is "pinned by `test_footer_trips_no_detector`", but it was not in that test: its
  detector check lived in `test_instrument_lookup.py` (`NEG_ASSERTED` and `LK_FOOTER` only). Now it
  is in that test. **For the integrator:** Agent B registers its new detector in the same function.
  If B adds its check as a loop over named clauses, add `lookup_clause` to it. Then re-run the test.
  The clause names no commencement and no currency, so I expect it to pass.

## Numbers, each with its command

All are run from `server_py/` of the worktree with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence PYTHONIOENCODING=utf-8`. Scripts
are in `$PREPILOT_EVIDENCE/seam/batch6/C/`.

1. **Census:** `python ../docs/prepilot-fixes/evidence/seam/batch6/C/p421_dryrun.py capture`, run
   **before** the change against the built (old) code.
   - **69** stored answers carry "not a sign that the citation is wrong", with 69 occurrences.
     **All 69 are in the code footer and 0 are in the model's prose.** This confirms the row's 69.
   - They fall in 5 directories: `wave4_p315_pre` 16, `wave4_p37` 16, `wave4_p37_reach` 1,
     `wave4_p37b` 15 and `wave4_p37c` 21.
   - Each clause was rebuilt from its labels by the built `_lookup_footer_clause`, and each rebuild
     was found **verbatim** in the stored answer: 69 of 69, with 0 not rebuildable and 0
     unaccounted.
   - 82 answers carry "looked up by". The other 13 carry only the held-without-text clause.
2. **Rebuild:** `… p421_dryrun.py rebuild`, run **after** the change against the built (new) code.
   - 69 answers and 69 clauses were replaced. The audit event's own copy of the answer
     (`audit.answer`, 69) was replaced too, although no grader reads it.
   - The script asserts that the old phrase is absent from every rebuilt file.
   - Rebuilt copies of the 5 directories are in `seam/batch6/C/rebuilt/`.
3. **Re-screen:** `… p421_rescreen.py`. It runs 28 commands per directory: every `replay_report`
   subcommand that takes only `--dir` (`summary`, `halts`, `negatives`, `derivations`,
   `commencements`, `currency`, `scoperecord`, `nosearch`, `caselaw`, `discovery`, `depth`, `modes`,
   `deadend`, `siblings`, `scripted`, `lookup`, `lookup --answers`, `drgaps`, `blanks`,
   `lost --require-label`, `lostcost`, `openers`, `stance`, `interpret`, `hedges`, `corpus`,
   `sectionscope`), plus `tools.footer_echo`.
   - Each runs on the stored and on the rebuilt copy of each of the 5 directories. **140 of 140 are
     identical in exit code and output** (the directory path is normalised).
   - The existing exit-1s are unchanged and are not new:
     - `lookup` on `wave4_p37`, `p37b` and `p37c` (P3.15's residual);
     - `commencements` on four directories;
     - `sectionscope` on three;
     - `nosearch` on `wave4_p37`;
     - `derivations` on `wave4_p37_reach` (P2.3's known exit, recorded on P3.7's row).
4. **Clause screen:** `… p421_screen.py` (output in `p421_screen.out`).
   - It runs every module-level compiled pattern in `tools/replay_report.py` (103) and the function
     detectors over each candidate, for 1, 2 and 3 labels. The function detectors are:
     - `derivation_claims` and `_currency_asserted`;
     - `_lk_classify` and the commencement denial;
     - `caselaw_gap_statements`, `_names_search_terms` and `_scripted_counts`.
   - **R1, R2 and R3 match nothing that the old clause does not match.** The rejected two have the
     extra matches listed above.
   - For every candidate it also asserts three things:
     - `_without_footer` strips both footer shapes (the fresh footer and the lookup-only one);
     - `_ECHOED_FOOTER` matches them;
     - `_earlier_lookups` round-trips the labels.
   - The screen's candidates are prototypes. The dry run (items 1 to 3) uses only the built code.
5. **Citation blame:** `… p421_blame.py` (output in `p421_blame.out`).
   - It covers every directory holding either of the two sessions P3.7's grader reads: 18
     directories.
   - It reports, before and after: `lookup`'s blame sentences, its "questions the citation" FAILs,
     absent slots passing, footer-lookup flags, and `NEG_BLAMED_USER` on the footer-stripped prose
     and on the full answer.
   - **All 18 are `SAME`.** The 4 rebuilt directories that hold those sessions read 12/12, 8/12,
     11/12 and 11/12 absent passing, with 0 blame both before and after. The blame that exists is
     pre-fix and unchanged: `wave1` 1 blame sentence; `NEG_BLAMED_USER` in `baseline` 2, `wave1` 3,
     `wave2_p24_pre` 1.

**Tests:**
- 204 pass in `test_instrument_lookup.py`, `test_search_scope.py` and `test_section_scope.py`.
- **Full suite: 2165 passed** on `lexchat_test_c` (2162 plus the 3 new tests).
- **Revert:** `p421_revert.py` runs on a scratch copy of `server_py` (`seam/batch6/C/revert_copy/`).
  It is a byte-level CRLF edit and asserts its anchor once. **It removed the 3 product code lines and
  restored the 2 old ones.** Three tests then fail:
  - `test_the_footer_states_not_held_and_stub_and_is_silent_on_held`;
  - `test_p421_the_not_held_clause_states_what_the_lookup_established`;
  - `test_p421_an_earlier_footer_in_either_wording_is_read_back_and_restated_new`.
- The other new tests are guards, not proofs: the old wording passes them too.

## Step (1): every product site that says a not-held result tells you something about the citation

The rest of `grep -n citation src` was read too. Those lines are about citation format, links or
case NCNs, not about a not-held result.

| Site | Reader | What it says | Accurate? |
|---|---|---|---|
| `search_scope.py` `_lookup_footer_clause` | **lawyer** (footer) | was: "a gap in the index, not a sign that the citation is wrong" | **No.** It is a default, not a finding. **Changed.** |
| `agent/tools/schemas.py:117-118` (`lookup_legislation` description) | model | "'not_held' (… say it is not held in this index; that is a gap in the index, not evidence that the citation is wrong)" | "not evidence that the citation is wrong" is **true**: no lookup result is evidence of that. "that is a gap in the index" asserts the cause, which is the same default in a milder form. **Left (step 5),** see decision 2. |
| `utils/instrument_lookup.py:260-261` (routed lookup block, appended to the Worker's brief) | model | "That is a gap in the index: it does not mean the instrument does not exist, and **it is not an error in the citation**." | The last clause is the **same default** as the footer, model-facing. **Left,** see decision 2. |
| `search_scope.py:2273-2276` `_not_held_limb` (worker block) | model (Manager, synthesis) | "That is the index's gap, not an error in the user's citation: do not ask the user to check …" | Same default, model-facing. **Left,** see decision 2. |
| `search_scope.py:2234-2245` `not_held_note` (on a by-id 404) | model | "a fact about the index, not about the law and not about the user's citation … Do NOT write that the citation may be wrong" | True as stated, and an instruction. Left. |
| `search_scope.py:2345-2351` `_lookup_limb`; `:1848-1852` worker-block rule; `:152-159` `_REPORTING_RULE` | model | "Never suggest an error in the user's citation"; "attribute the miss to the search or the index, never to the user's citation" | Instructions, not claims. Left. |
| `prompts.py:85`, `:440` (NOT HELD IS NOT A WRONG CITATION), `:236`, `:519` | model | "never ask the user to check… a correct citation is often not held" | The rule's **title** asserts; its body is an instruction plus a true base rate. Left. |

**Has the model-facing default reached the lawyer?** I checked with `… p421_prose.py`. It runs a
6-alternative pattern over the footer-stripped prose of every stored answer in all 57 directories:
"not an error in the citation", "not a sign that", "citation is correct/accurate/…", "does not mean
the citation", "no evidence that the citation", "gap in the index, not".
- **2 answers match**, one each in `wave2_p24_final` and `wave4_p37`, both in the same session. I
  hand-read both: the sentences are in the gitignored `p421_prose_sentences.txt`.
- Each says that the index's absence "is not evidence that the citation is incorrect" or "does not
  mean your citation is incorrect". Both are true. Neither says the citation is right.
- The pattern is narrow, so this is a lower bound and not a rate.

## What I did NOT do

- I did not change `schemas.py`, `instrument_lookup.py`, `_not_held_limb` or any prompt. They are
  model-facing, and they are what holds P2.4's fix. Changing them changes model behaviour, which can
  only be measured by a paid seam or replay. That is decision 2.
- I did not change the held-without-text clause, P2.4's `not_held_note` or any grader.
- No replay, no seam draw, and no live call.
- I did not edit FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md, TODO, the tracker, the batch brief, any
  rubric, the lawyer pack or memory. P4.21's row is left `[ ]` for the integrator, after the user
  decides on the sentence.
- I did not measure Thomas's glm-5.2 answers.

## Scratch

- The worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch6/C/` was checked with
  `git check-ignore -v`, which reports `.gitignore:113`.
- At the end it was copied with `cp -r` to
  `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch6/C/`.
- It contains:
  - the scripts `p421_dryrun.py`, `p421_screen.py`, `p421_rescreen.py`, `p421_blame.py`,
    `p421_prose.py` and `p421_revert.py`;
  - their outputs (`*.out`, and `p421_capture.json`, which holds footer clauses with instrument
    labels);
  - `rebuilt/` (the 5 rebuilt directories, with matter text, gitignored);
  - `revert_copy/`.
- The scripts find the worktree from their own path. Run from the main checkout's copy, they import
  the main checkout's code. To re-run them against the merged tree, repoint them (`WT`); do not edit
  them in place.

## Decisions for the user

1. **The sentence a lawyer reads when a lookup finds an instrument not held.**
   - **(a) R1, as built (recommended):** "…is not held in this index, which is incomplete; that does
     not show whether the number is accurate." It is neutral both ways and gives the true general
     reason.
   - (b) R2: "…is not held in this index; a lookup cannot show whether the number is accurate."
     This is the shortest, but with no context for the lawyer's doubt.
   - (c) R3: R1 plus "recent instruments least of all". It is more informative and adds a second
     claim.
   - (d) Keep the old wording. That leaves Thomas's point (P4.21) open.
2. **The three model-facing sites that still assert the same default** ("not an error in the
   citation": the routed lookup block, `_not_held_limb`, and the tool description's "that is a gap
   in the index").
   - **(a) Leave them (recommended).** They are what stopped the model blaming correct citations
     (P2.4, P3.7). The model's prose turned that into vouching in 2 stored answers, both in the
     accurate "not evidence"/"does not mean" form. Changing them needs a paid measurement.
   - (b) Reword them now to R1's standard ("does not show an error in the citation") and price a
     Worker seam A/B on the two sessions before merge.
   - (c) Book them as a new measure-first row (a P4.21 residual), leaving this merge
     lawyer-facing only.
