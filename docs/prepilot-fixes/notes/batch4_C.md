# Parallel batch 4, agent C: P4.18, the currency clause's contradiction

Branch `worktree-agent-aede07fe1701f1b08`. $0: no model call, no server, no replay pin, run or
restore. Every command below runs from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8`; `$C` is my scratch folder (see "Scratch" at the end).

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-3. With no commits of my
own I ran `git reset --hard e5c31ba52567496be4eb4d467e5b8ae621c116e0` before anything else.

## The row's acceptance, and whether it is met

> The currency clause never says no change record was consulted on a turn that consulted one,
> and still says no currency check was made on a turn that consulted none; the rebuild dry run
> (agent C's harness, product builders) over every stored directory takes the 27 contradictions
> to 0 and moves nothing else in the 21 `replay_report` subcommands that is not listed and read;
> the new wording trips no detector the old one did not (`test_footer_trips_no_detector`); unit
> tests at `_currency_footer_clause` fail with the change reverted.

**MET**, each limb below. Deterministic, n=1; the integrator ticks it at merge.

| limb | result | command |
|---|---|---|
| never says "no change record was consulted" on a consulting turn | 0 of 493 rebuilt footers carrying P3.5's clause | `python $C/p418_contra_after.py` |
| still says it on a turn that consulted none | kept on all 206 rebuilt footers whose turn consulted none; 0 of those footers changed | same |
| the contradictions go to 0 | stored 28 to 0 (splice); rebuilt 61 to 0 (rebuild) | same |
| moves nothing else | splice: 0 of 252 outputs change; rebuild: 0 of 294 against its control | `python $C/p417_diff.py $C/dry sp`; `… $C/dry rb rb0` |
| trips no detector the old wording did not | none of 101 compiled patterns and 6 sentence functions, clause and whole footer | `python $C/p418_detectors.py` |
| tests fail with the change reverted | 4 fail (16 lines removed) | section 5 |

**The count is 28, not 27.** The row's "27 of 455" was taken before `wave4_b2_post`, which added
20 footers carrying P3.5's clause and one contradiction (6375 r1 t2, a Deep Research step). Today,
over 56 directories, `python $PREPILOT_EVIDENCE/seam/batch3/C/p417_contra.py` prints
`'with relations clause': 475, 'BOTH': 28`.

## 1. The 28, measured first

`python $C/p418_list.py` (ids only; `--show` prints the two clauses, `--log` the rebuilt
currency and change-record rows):

| directory | turns (session r rep t turn) |
|---|---|
| `wave2` | 6341 r1 t6 |
| `wave2_p25` | 6341 r3 t6 |
| `wave2_p27` | 6341 r1 t4, r1 t5, r2 t2 |
| `wave2_p27_pre` | 6341 r3 t6 |
| `wave2_p27_smoke` | 6341 r1 t5 |
| `wave2_p28` | 6341 r1 t5, r1 t6, r2 t5, r2 t6, r3 t4, r3 t5 |
| `wave3_p31` | 6396 r3 t1 |
| `wave3_p31_pre` | 6396 r2 t1 |
| `wave4_b2_post` | 6375 r1 t2 (Deep Research) |
| `wave4_p315_pre` | p37_6373 r1 t2, r2 t2, r3 t2 |
| `wave4_p37b` | p37_6373 r1 t2, r2 t2, r2 t3, r3 t2, r3 t3 |
| `wave4_p37c` | p37_6373 r1 t2, r2 t2, r2 t3, r3 t2 |

17 fresh footers, 11 carried (the p37_6373 follow-ups). What each says, read in full:
- **10 of 28**: P3.5's clause says the records were "consulted directly, and those records list
  nothing in the direction consulted"; P2.5's then says "no change record was consulted for this
  answer". The records were empty. All 6341.
- **18 of 28**: P3.5's clause says "consulted directly; those records carry no dates", because
  the record held relations by another instrument (amendments, or, for the p37_6373 turns, the
  changes made BY the instrument looked up), none of them a commencement or a repeal; P2.5's
  clause says no record was consulted.

In every one of the 28 the rebuilt currency rows are `kind == "relations"` with `commenced == 0`
and `repeals == 0`, so `_currency_footer_clause` took its else branch. Two statements about one
check that cannot both be true, as batch 3's (f4) recorded.

## 2. The change (only inside `_currency_footer_clause`)

`server_py/src/utils/search_scope.py`: a third branch between "sourced" and "none consulted".
When a `kind == "relations"` row exists and none of them carries a commencement or repeal, the
clause now ends:

> Whether legislation is in force is not something this index reports, so nothing above has been
> checked against a commencement date; the recorded changes consulted list neither a commencement
> nor a repeal, so they do not answer that question either.

The other two branches are byte-identical: the sourced wording when any record holds a
commencement or repeal (so a mixed turn reads as before), and "and no change record was
consulted for this answer" when no relations row exists (a turn whose only currency evidence is a
title marker or a text-version date). The docstring records the third case. Nothing else in the
file, and no other file in `src/`, changed.

**Why this wording, screened before it was built** (`python $C/p418_candidates.py`; prototype
strings for choosing only, the measurement after uses the built function):
- my first built draft, "… list no commencement or repeal, so in-force status is not established
  from them either", tripped **`NEG_ASSERTED`** (its `no … commencement` limb) on all 61 rebuilt
  footers it changed, and `_CUR_DISCLOSED`, `_CUR_NEGATED_VERB` and `_CUR_SUBJECT_RE` too
  (`_CUR_DISCLOSED` reads the body without the footer, so that one is harmless, but the old
  clause trips none of them);
- "… so they do not establish whether it is in force" adds a second `IN_FORCE_CLAIM` match (the
  legacy counter `summary` reads) and `_CUR_DISCLOSED`;
- naming the instruments ("consulted for ssi/…") adds `LK_ANY_NUMBER`, `LK_PRIMARY_LID`,
  `LK_ACT_REF` and `_DERIV_NUMBERED` hits; `derivation_claims` stays empty, but the ids add
  nothing a lawyer lacks, because P3.5's clause just before this one names the same records;
- "list neither a commencement nor a repeal, so they do not answer that question either" adds
  nothing. Built.

## 3. Detectors, on the built clause

`python $C/p418_detectors.py` (output `$C/detectors_out.txt`). Every module-level compiled regex
in `tools.replay_report` and `tools.footer_echo` (101), plus `_currency_asserted` and the P3.5
commencement pair (`_CMC_CONTEXT` and `_CMC_DENIED`) per sentence, `_denial_is_attributed`,
`derivation_claims` (asserted and filtered) and `_names_search_terms`, run over the OLD clause
(as built at `e5c31ba`) and the NEW one, and over the whole rebuilt footer, on every stored turn
whose footer changes (61):
- tripped by the NEW clause and not the OLD: **none**;
- tripped by the NEW footer and not the OLD: **none**; by the OLD and not the NEW: **none**.
Synthetic logs, all branches (none consulted with a title marker or a valid date; consulted and
empty with one, four or no ids; sourced; mixed): the two unchanged branches are identical, the
new one trips nothing new. The footer stays one line with no `*` inside, so `ANSWER_FOOTER`,
`_without_footer` and P4.14's echo strip take it whole as before; no code outside
`search_scope.py` keys on the clause's text (grep of `src/` and `tools/`).

## 4. The dry run over all 56 directories

`python $C/p418_dryrun.py $C/dry` (output `$C/dryrun_out.txt`). Batch 3 C's harness, copied:
each turn's record rebuilt from the audit with the product's recorders (`$C/p418_rebuild.py`, a
copy of `p417_rebuild.py`), the footer rebuilt with the product's chain, once with
`_currency_footer_clause` as built at `e5c31ba` (its source taken from
`git show e5c31ba:server_py/src/utils/search_scope.py`, saved as `$C/ss_base.py`) and once as
built in this worktree (imported; the script asserts the module path is this worktree's). A turn
is edited only where the two differ: **61 turns**. Then the 21 subcommands of
`p417_dryrun.py`'s list (`summary` and the 20 others; `lost --require-label`; `interpret` and
`stance` without a rubric, as batch 3 ran them) over the base of every directory and each variant.
No exception in any output. Three variants:

| variant | what it edits | answers edited | outputs changed |
|---|---|---|---|
| `sp` (splice) | the OLD clause, built, replaced by the NEW one, built, inside the STORED footer, where OLD occurs exactly once | **28**, exactly the 28 | **0 of 252** against base |
| `rb` (batch 3's method) | the stored footer replaced by the whole rebuilt NEW footer | 61 | 7 of 294 against base |
| `rb0` (control for `rb`) | the same, with the rebuilt OLD footer | 46 (15 rebuild byte-equal to stored) | the same 7 of 189 |

`python $C/p417_diff.py $C/dry rb rb0`: **0 of 294 outputs differ.** Every move in `rb` comes
from replacing a stored footer with a rebuilt one, not from P4.18. Exit codes
(`python $C/p417_rc.py $C/dry sp|rb`): `sp` better 0, worse 0; `rb` better 1, worse 0, the same
as `rb0`.

**The 7 `rb` moves, each read; all are in `rb0` too** (`$C/diff_rb.txt`):
- `wave2_p27` `caselaw`: TWO_LINES 1 to 0 (6341 r2 t2), and `deadend` drops its finding on the
  same turn: the stored answer carries two footer lines and the rebuild writes one;
- `wave3_p35` `nosearch` (carried line 0 to 3) and `summary` (legacy in-force counter 3 to 30,
  bare negatives explained 36 to 39): stored footers there predate P2.5's clause and P2.8's
  carried line, so a rebuilt footer adds them;
- `wave4_p37` `negatives` (the `loose` cell of p37_6373 r3 t2, verdict PASS both sides),
  `nosearch` (lookup line to carried line) and `summary` (legacy in-force counter 5 to 8): that
  directory's footers came from P3.7's first code, as batch 3 recorded.

**`currency` (P2.5's own grader) and `commencements` (P3.5's) move in no variant**, on any
directory, exit codes included.

**The 33 turns `rb` edits beyond the 28** (`wave3_p35` 30, `wave4_p37` 3) are turns whose stored
footer never carried P2.5's clause. Read: for `wave4_p37` the rebuilt line is the same as the
`wave4_p37b` lines. For `wave3_p35` the rebuild is wrong in both variants, and not because of
this change: **all 41 stored `get_legislation_changes` results in `wave3_p35` predate P2.5's
counts** (`provisions_commenced` absent; every other directory has it on every call,
`python $C/p418_rawkeys.py`), so the recorder reads 0 commencements for records holding about
1,600 `coming into force` rows. Rebuilt with OLD they said "no change record was consulted";
rebuilt with NEW they say the records list neither. Neither text ever reached a lawyer, and the
product writes those counts today, so it cannot arise live. It is a limit of rebuilding from
that directory's raw results.

**Downstream:** an edited answer changes no later turn's footer through the history (P2.8's
carried line and P3.7's earlier-lookup clause read earlier footers): 0 in every variant.

**The headline, before and after** (`python $C/p418_contra_after.py`, output
`$C/contra_after_out.txt`; `--ids` lists the turns):

| | footers with P3.5's clause | carrying both statements |
|---|---|---|
| stored | 475 | **28** |
| stored, spliced with the NEW clause | 475 | **0** |
| rebuilt with OLD | 493 | 61 |
| rebuilt with NEW | 493 | **0** |

Rebuilt with NEW: the new wording appears on exactly 61 footers, every one on a turn that
consulted a record; "no change record was consulted" stays on 206, every one on a turn that
consulted none (OLD had it on 267 = 206 + 61). No footer of a turn that consulted no record
changed.

**Every changed footer was read** (`python $C/p418_read.py`, output `$C/read_out.txt`, which
prints instrument ids): the 28 spliced stored footers and the 33 rebuilt ones, each from P3.5's
clause to the end. The new sentence reads correctly after both P3.5 shapes ("list nothing in the
direction consulted" and "carry no dates"), before P3.7's lookup clause on the p37_6373 turns
and before the case-law clauses on 6375's Deep Research line. The one false reading is
`wave3_p35`'s, explained above.

## 5. Tests

`server_py/tests/test_in_force_status.py` (synthetic ids and titles only, "Widget Order 1901"):
- `test_a_consulted_record_with_no_commencement_is_not_called_unconsulted` (two cases: an empty
  record, a record holding only an amendment), from the product's slimmer and both recorders;
- `test_the_no_check_wording_stays_for_a_turn_that_consulted_no_record` (title marker; valid
  date);
- `test_a_sourced_record_keeps_its_wording_beside_an_empty_one`;
- `test_neither_footer_line_contradicts_p35s_clause_any_more`: the whole fresh line
  (`answer_scope_footer`) and the carried line (`carried_scope_footer`) carry P3.5's "consulted
  directly" and not "no change record was consulted";
- `test_the_detector_does_not_read_the_products_own_new_wording` extended with the new branch.

`server_py/tests/test_search_scope.py::test_footer_trips_no_detector` **extended, nothing
removed**: a third log (a record consulted, holding nothing) joins the two existing ones; for all
three, beside the existing `NEG_ASSERTED` and `derivation_claims` checks, it now asserts per
sentence no P3.5 commencement denial (`_CMC_CONTEXT` and `_CMC_DENIED`) and no
`_currency_asserted`, exactly one `IN_FORCE_CLAIM` match (the opening all branches share) and no
`_CUR_DISCLOSED`; and that the new branch does not say no record was consulted.

**Revert proof.** `python $C/p418_revert.py <scratch copy of server_py>` on a copy of this
worktree's `server_py` (bytes, CRLF; each anchor asserted to occur exactly once): **16 lines
removed** (the 15-line branch, and the flag line), after which the file differs from `e5c31ba`
only in the docstring paragraph. On the reverted copy, the two test files: **4 fail, 249 pass**
(both cases of the first test, the seam test, `test_footer_trips_no_detector`). The two tests
pinning unchanged behaviour pass on both, as they should. The scratch copy was removed after.

**Full suite** on `lexchat_test_c`: **2098 passed** (2093 + 5).

## What I did NOT do

- No model call, server, replay pin, run or restore; no rubric touched; no grader changed.
- Did not touch `_relations_footer_clause`, the recorders, `_currency_limb`, any prompt, or any
  other builder (agent B is adding one in parallel).
- Did not change the mixed case: one record with a commencement beside one that held nothing
  still reads "what was checked is the recorded changes for <the first>", naming only the sourced
  one. It is not a contradiction; extending it would move text on turns outside this row.
- Did not change the three-instrument cut on the sourced branch (`[:3]`) or P3.5's own.
- Did not run `footer_echo` or `summary_probe` on the variants (neither is among the 21, and the
  splice changes only footer text inside the footer).

## For the integrator to decide

- **Tick P4.18** if the merge re-check holds; the row text says 27 of 455, today's count is 28 of
  475 (the extra one is `wave4_b2_post`).
- **The wording names no instrument**, deliberately (section 2). If the user prefers the ids
  repeated, they add lookup and derivation pattern hits and must be re-screened.
- **The rebuild harness's limit:** `wave3_p35`'s raw results predate P2.5's counts, so any rebuild
  of that directory misstates currency in both variants. Worth recording beside batch 3's
  validation table.
- **Re-run against the merged tree** (from `server_py/`, with the env above, after copying my
  scratch out): `python <scratch>/p418_contra_after.py` should print `stored: BOTH 28`,
  `rebuilt NEW: BOTH 0`, `spliced: BOTH 0`, and 0 on both "must be 0" lines. Batch 3's
  `p417_contra.py` reads only stored footers, so it will still print 28 after the merge; the
  stored data does not change.

## Scratch

**The harness blocked my writes outside the worktree** (the Write tool refused the main
checkout's `evidence/seam/batch4/C/`), so all scratch is in this worktree's gitignored
`docs/prepilot-fixes/evidence/seam/batch4/C/` (checked with `git check-ignore -v`). Copy it out
before removing the worktree. Scripts: `p418_list.py`, `p418_rebuild.py`, `p418_dryrun.py`,
`p418_detectors.py`, `p418_candidates.py`, `p418_contra_after.py`, `p418_read.py`,
`p418_rawkeys.py`, `p418_revert.py`, copies of batch 3's `p417_contra.py`, `p417_diff.py`,
`p417_rc.py`, `p417_dryrun.py`, and `ss_base.py` (`search_scope.py` at `e5c31ba`). Outputs:
`list_before.txt`, `detectors_out.txt`, `dryrun_out.txt`, `diff_{sp,rb,rb0,rb_vs_rb0}.txt`,
`contra_after_out.txt`, `read_out.txt` (instrument ids), `dry/`. Batch 3's files were not edited.
