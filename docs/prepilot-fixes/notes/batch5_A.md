# Batch 5, agent A: `tools/plan_lint`, and a proposed mechanical fold (Session 37, 2026-10-02)

**Scope:** agent A's section of `PARALLEL_BATCH_5.md`: turn Session 36's structural probe into a
tested `python -m tools.plan_lint`, then write (not apply) a byte fold that takes its checks 2
(index coverage) and 3 (done marks) to 0 errors. **Spend: $0.** No model call, no server, no
`replay pin|run|restore`, no API call. No edit to `FIX_PLAN.md` or any other file the rules name.

**Base:** the worktree came up on `main` at `a6b4a76`, not on the integrator's head. It had no
commits, so I ran `git reset --hard dde8b41` before any work, as the brief says. Every number below
is on the plan at `dde8b41`.

**Agent C's note was not available** (C ran in parallel), so the fold places only the
uncontroversial rows and takes its placements from a table the integrator extends (below).

**Scratch:** the scripts and every output are in the worktree's gitignored
`docs/prepilot-fixes/evidence/seam/batch5/A/` (checked: `git check-ignore -v` names `.gitignore:113`,
`docs/prepilot-fixes/evidence/seam/`), copied at the end to
`$PREPILOT_EVIDENCE/seam/batch5/A/` with a plain `cp` (see the reply for whether it reached).

## Acceptance, stated before any claim

From the brief: `plan_lint` built and tested, each test failing with its check reverted; on the
plan at `dde8b41` it reports exactly the probe's findings (16 done-mark mismatches, 21 unindexed
rows, 3 dependency warnings) plus anything new, each listed; the fold on a scratch copy takes checks
2 and 3 to 0 errors and leaves `plan_status` unchanged (46 of 69, 8 of 14).

| Item | Check | Result |
|---|---|---|
| `plan_lint` built, 7 checks, a test per check | `pytest tests/test_plan_lint.py` | **met**: 25 tests pass |
| each test fails with its check reverted | `revert_checks.py` (below) | **met**: all 25 fail under at least one revert; every revert removed or changed lines |
| the probe's findings, exactly | `python -m tools.plan_lint` at `dde8b41` | **met**: the probe's 21 unindexed rows, its 16 done mismatches and its 3 dependency warnings are all reported; the new findings are listed below |
| fold takes checks 2 and 3 to 0 errors | `fold_b5_A.py` on a scratch copy | **check 3 met (21 to 0); check 2 NOT closed by my placements alone (21 to 13)**: the 13 left are the rows that need C's or the user's placement (expected residue). With stand-in placements for all 21 (dry run), both reach 0 |
| `plan_status` unchanged | `python -m tools.plan_status` on the scratch tree, before and after the fold, `diff -q` | **met**: byte-identical output, 46 of 69 rows, 8 of 14 buckets |

## What I built

**`server_py/tools/plan_status.py`** (refactor, no behaviour change): `_rows(text=None)` and
`_buckets(text=None)` take the plan's text when given (else read the file as before), and the
closure rule moved into `bucket_state(deps, status)`, which `main` now calls. This is so the lint
reuses plan_status's parsing instead of forking it. Check: `python -m tools.plan_status` output
before and after the refactor is byte-identical (`diff`, saved as `plan_status_before.txt` and
`plan_status_after_refactor.txt`). 19 insertions, 14 deletions.

**`server_py/tools/plan_lint.py`** (new). `python -m tools.plan_lint [--plan PATH] [--only
CHECK,...]`; exit 1 on any ERROR, warnings print and do not fail. One function per check:

1. `check_row_shape`: every ledger row (`| \`[?]\` |`) has exactly 3 cells, counting unescaped
   `|` as GFM does (inside a code span too; `\|` does not split; a trailing `|` is optional); a
   known status box; an id; a row `plan_status` reads (its `_ROW` needs the bold title straight
   after the id); ids unique. ERROR.
2. `check_index_coverage`: parses the "Bucket → row index" into entries by splitting each cell on
   commas outside parentheses; an entry is `Pn.m`, an optional parenthetical, an optional
   ` **done**`. **A row is "named" only as an entry's head.** A row in no line is an ERROR; a row
   named on two lines is an ERROR; an index id that is no row is an ERROR; an unparseable entry
   is an ERROR. **The `*(no bucket)*` line is the allowlist** (the brief's suggestion): a row that
   closes no bucket is named there; there is no second list. Two WARNINGs: a row that is only
   mentioned inside another entry's parenthetical, and an id inside a bucket line's parenthetical
   that is not an entry of that line, because `plan_status._buckets` reads EVERY id on a bucket
   line as a closure dependency (so a gloss that names an open row would hold the bucket open).
3. `check_done_marks`: under `DONE_MARK_CONVENTION = "every"` (decision 1), an entry carries
   `**done**` exactly when its row is `[x]`. Every entry is checked, bare ones (`P2.1`) and the
   `*(no bucket)*` line included. ERROR. `"none"` is supported for decision 1's other option.
4. `check_dependencies`: reads each `**Depends on:**` clause up to the cell's end, `Related:`, or the
   first bold run that is not a bold row id (`**P2.1**` in P4.3's clause is read); expands
   `P1.1–P1.4` and `P2.*` over the rows. An unknown id or a self-dependency is an ERROR; a ticked
   row depending on an unticked one is a WARNING unless the clause contains "ticked ahead"
   (decision 4 proposes that wording); a row with no clause is a WARNING (none at `dde8b41`).
5. `check_order_counts`: the FIRST `**Recommended order as at ...**` line only; each "N of M rows"
   and "K of M buckets" in it against `plan_status`'s numbers (via `_rows`, `_buckets`,
   `bucket_state`). WARNING.
6. `check_bold_parity`: every row line, and every other blank-line-separated paragraph outside a
   code fence, has an even `**` count (a per-LINE count is wrong outside the table: 18 lines
   there are odd on their own, each half of a bold run wrapped across a line break, and every
   paragraph they sit in is even). `ODD_LITERALS = {"P0.2": "\`**Key
   findings\`"}` excuses the one known odd literal by its exact text, on that row's line only.
   ERROR.
7. `check_encoding`: strict UTF-8 (ERROR, naming the byte, offset and line); a BOM, and mixed
   line endings, are WARNINGs.

## Findings on the plan at `dde8b41`

Command: from `server_py/`, `python -m tools.plan_lint` (output saved as `plan_lint_head.txt`).
**66 errors, 6 warnings; by check: shape 24, index 21, done 21, depends 0, order 0, bold 0,
encoding 0** (plus 3 dependency warnings, 3 index warnings).

Against the probe (`plan_probe.py`, run on the same tree, its output in the reply's scratch):

- **index: the probe's 21, exactly** (P0.1-P0.7, P1.5, P2.6, P3.6, P3.12, P3.14, P3.21, P3.22,
  P3.23, P4.4, P4.8, P4.9, P4.19, P5.3, P5.4).
- **done: the probe's 16, exactly, plus 5 new.** The probe's regex needed a parenthetical after
  the id, so it could not see bare entries; the 5 it missed are P2.1 (B1), P1.1 (B2), P4.1 (B7),
  P4.2 (B13), P1.4 (B14). 21 in all, every one a ticked row with no mark; no open row carries one.
- **depends: the probe's 3 warnings, exactly** (P3.16 and P3.18 on P3.3, P4.13 on P3.2). No
  unknown id. The probe's `[^|*]*` stopped at `P2.*` and at `**P2.1**`, so it read P3.1's and
  P4.1's `P2.*` and P4.3's `**P2.1**` as nothing; the lint reads them, and they add no finding
  (every P2 row is ticked; P4.3 is open).
- **order: no finding.** The top line ("end of Session 36") says 46 of 69 rows and 8 of 14
  buckets, which is what `plan_status` says.
- **bold: no finding** (P0.2's literal excused; without the excuse it is the only odd line).
- **encoding: no finding.** UTF-8, CRLF on all 461 lines, no BOM.

**New: shape, 24 errors.** 24 ledger rows have more than 3 cells: P0.4, P0.5, P1.1, P1.2, P1.3,
P1.4, P1.5, P2.1-P2.10, P3.1, P3.11, P4.1, P4.2, P5.1, P5.2, P5.3. 54 stray `|` in all: **31
outside a code span** (17 rows carry 1, P2.2, P2.3, P2.8, P2.9, P2.10, P4.1 and P4.2 carry 2: the
pattern is `**Depends on:** X | **DONE ...`, and `| |`, i.e. the row's history written into a 4th
and 5th cell) and **23 inside a code span** (P0.5 5, P2.7 1, P4.1 17: unescaped `|` in quoted
regexes and a usage string). Under the GFM table rule, a row with more cells than the header's 3
has the excess ignored, so on GitHub everything after the stray pipe in those 24 rows does not
render (for P1.1, P1.2 and others, that is the row's "DONE" record). I did not render the file to
confirm this ($0, no API call); it is the GFM spec's stated rule. Raw-text readers, which is how
sessions read the plan, are unaffected. Decision 2.

**New: index, 3 warnings.**
- P2.10 is named nowhere; it is mentioned only inside P2.8's parenthetical on B5
  ("carried-forward negatives; P2.10 folded in"). `plan_status` therefore already counts P2.10 as
  a B5 closure dependency (it is ticked, so nothing moves). Two warnings for it (not named; a
  parenthetical id on a bucket line).
- P4.5 is named nowhere; it is mentioned only inside P4.10's parenthetical on `*(no bucket)*`
  ("P4.5 keeps the labelling"). The probe counted both as indexed because it searched the index
  for any id. Decision 3.

## The fold (written, not applied)

`$PREPILOT_EVIDENCE/seam/batch5/A/fold_b5_A.py PLAN [--tools SERVER_PY] [--allow-bucket-change]
[--dry-run]`. It imports the BUILT `tools.plan_lint` and `tools.plan_status` from `--tools`
(default: the plan's own repo's `server_py`), prints the module paths and asserts them, so the
integrator repoints it at the merged tree with `--tools`, never by editing it.

1. **`PLACEMENTS`**, a table at the top: row → (index line key, gloss). Mine: P0.1 (the replay
   runner), P0.2 (the frozen replay set), P0.3 (the baseline), P0.4 (the exported Deep Research
   flag), P0.5 (the harness's chat mode), P0.6 (the harness's research type), P0.7 (both modes from
   the recorded requests), P1.5 (the Wave 1 re-baseline), all on `*(no bucket)*`: measurement and
   harness rows, which close no bucket. Each new entry is inserted before the first entry on its
   line whose id sorts after it (here, at the front of the `*(no bucket)*` line, in id order).
   A row already named on the target line is skipped (re-runnable); a row named on a different
   line aborts. **The integrator adds C's placements to this table and re-runs.**
2. **Done marks** under `CONVENTION = "every"`: ` **done**` added to every entry whose row is
   ticked, removed from any whose row is not (`"none"` removes all).

Guards (house style): CRLF throughout before and after; strict UTF-8; each index line found once
by key and round-tripped byte-for-byte through the parser before it is touched; no `|`, no `**`
and balanced brackets in a gloss; line count unchanged; the `**` delta asserted equal to 2 per mark
added minus 2 per mark removed. **Bucket closure is compared before and after with
`plan_status.bucket_state`: if any bucket's state moves, it refuses to write (exit 2) unless
`--allow-bucket-change`.** This matters for C's placements: placing an OPEN row on a CLOSED bucket's
line reopens that bucket in `plan_status` (tested: an open row on B4 moves B4 closed → partial and
8 → 7 of 14; refused).

**Run on a scratch copy** (`scratch/`: the plan at `dde8b41` plus copies of the built
`plan_status.py` and `plan_lint.py` and `classification.json`, laid out as the repo so
`python -m tools.plan_status` reads the copy):

| | before | after |
|---|---|---|
| `plan_lint --only index,done` | exit 1; index 21, done 21; 3 warnings | exit 1; **index 13, done 0**; 3 warnings |
| `plan_lint` (all checks) | 66 errors (shape 24, index 21, done 21), 6 warnings | 37 errors (shape 24, index 13), 6 warnings |
| `plan_status` | 46 of 69 rows, 8 of 14 buckets | identical output (`diff -q`) |

Fold output: placed 8; done marks +27 −0 (the 21 mismatches and the 6 newly placed ticked rows;
P0.4 is `[~]` and P0.7 `[ ]`, so unmarked); 11 index lines changed and no other line (`diff`: 22
lines, all in the index); `**` 4479 → 4533 (delta 54, even); 462 lines; CRLF 461 of 461.

**Expected residue of check 2 with my placements only: 13 rows**, for C or the user: P2.6, P3.6,
P3.12, P3.14, P3.21, P3.22, P3.23, P4.4, P4.8, P4.9, P4.19, P5.3, P5.4 (also in the script as
`UNPLACED`, for the record). **The integrator's run once all 21 are placed:** `fold_selftest.py`
case (a) places those 13 on `*(no bucket)*` as stand-ins (dry run, not a recommendation): placed
21, done +30, `plan_lint --only index,done` **0 errors**, `plan_status` 46 of 69 and 8 of 14.
Case (c): re-running the shipped table on a folded copy skips all 8 and changes nothing. Case (d):
decision 3's option (name P2.10 on B5 and P4.5 on `*(no bucket)*`) moves no bucket and clears the 3
index warnings.

## Tests

`server_py/tests/test_plan_lint.py`, 25 tests on a synthetic plan ("Fix the widget", "the
sprocket"; nothing from a session). **Reverts** (`revert_checks.py`: each function body replaced by
a no-op return in a scratch copy of the BUILT `plan_lint.py`, then the test file run against it):

| revert | lines removed | tests failing |
|---|---|---|
| `check_row_shape` | 35 | 3 |
| `check_index_coverage` | 43 | 6 |
| `check_done_marks` | 18 | 4 |
| `check_dependencies` | 27 | 2 |
| `check_order_counts` | 21 | 2 |
| `check_bold_parity` | 36 | 3 |
| `check_encoding` | 15 | 2 |
| `depends_clauses` | 10 | 4 |
| `dependency_ids` | 12 | 3 |
| `main` | 24 | 1 |
| escaped-`\|` handling (one line changed, none removed) | 0 | 1 |
| top-line-only reading (one line changed) | 0 | 1 |
| the "ticked ahead" exemption (one line changed) | 0 | 1 |

Every one of the 25 tests fails under at least one revert (the three one-line reverts cover the
three negative tests a no-op check cannot fail). `test_the_synthetic_plan_is_clean` fails under the
`depends_clauses` revert. **Full suite on `lexchat_test_a`: 2160 passed** (2135 at the batch-4
merge, plus these 25).

## Data handling

The tool prints row ids, line numbers, counts and index labels; it never prints row text. The
note cites rows, not sessions. The staged diff was grepped before the commit for session ids
(`\b6[34][0-9]{2}\b`), legislation ids (`(ukpga|asp|ssi|uksi|nisr|wsi)/<year>` and `<year>/<n>`)
and matter words (education, victims, witness, freedom of information, FOISA, acquiring,
compensation, housing, council tax): no hits.

## What I did NOT do

- Did not edit `FIX_PLAN.md` or apply the fold anywhere but a scratch copy.
- Did not place the 13 judgement rows, or choose between C's placements; did not fold check 1
  (decision 2), the dependency wording (decision 4) or the two referenced-only rows (decision 3).
- Did not change `plan_status`'s closure semantics (it still reads every id on a bucket line; the
  lint warns instead). Did not add `--plan` to `plan_status` (the scratch tree stands in).
- Did not render the plan on GitHub to confirm the dropped cells.

## Decisions for the integrator or the user

1. **Done-mark convention.** (a) **every** ticked row's index entry carries `**done**` (the
   fold adds 27 marks: 21 missing today plus 6 on the newly placed P0 rows and P1.5; each future
   tick then needs its index entry marked, which the lint enforces); (b) **none** (the fold removes
   the 14 marks there are; nothing to maintain, `plan_status`'s "waiting on" already says the
   same). **Recommend (a):** the marks are the index's existing practice (the index has 46
   entries, 35 of them on ticked rows, and 14 of those 35 are marked), the probe assumed it, a
   reader of the index sees what a bucket waits on without running a command, and the drift that
   made them unreliable (21 of the 35 unmarked) is now an exit 1 the next fold sees.
   Both are one constant (`DONE_MARK_CONVENTION` in the lint, `CONVENTION` in the fold).
2. **The 24 rows with extra cells (check 1).** (a) A $0 byte fold: replace each of the 31 stray
   separators outside a code span with a non-pipe separator inside the cell (for example `<br>`
   or " · "), and escape the 23 code-span pipes as `\|` (GFM renders `\|` as `|` inside a table
   cell; raw readers of P0.5's, P2.7's and P4.1's regexes would then see `\|`); (b) downgrade
   check 1's extra-cell finding to a WARNING; (c) leave it, and gate on
   `plan_lint --only index,done,depends,order,bold,encoding`. **Recommend (a)** as one separate
   mechanical commit (the row text is unchanged, only its separators), so `plan_lint` can exit 0.
3. **P2.10 and P4.5 are mentioned, not named.** (a) Name them: add `"P2.10": ("B5", "folded
   into P2.8")` and `"P4.5": (NO_BUCKET, "a lost report's label")` to `PLACEMENTS` (case (d): no
   bucket moves, the 3 warnings clear); (b) leave the warnings. **Recommend (a).**
4. **The three ticked rows on open rows.** Proposed: say why in each clause, in the wording the
   lint reads, with these anchors (each occurs once in `FIX_PLAN.md` at `dde8b41`):
   - P3.16: `**Depends on:** P3.3 **Session 33 (parallel batch 1, agent C)` → insert
     ` (ticked ahead of P3.3: user decision, Session 34)` after `P3.3` (SESSION_LOG Session 34's
     interim entry: "P3.16 ticked (user decision)");
   - P3.18: `**Depends on:** P3.3 **Session 33 (parallel batch 1, agent D)` → insert
     ` (ticked ahead of P3.3: its own acceptance met by hand, Session 33)` (Session 33 continued:
     "P3.18 DONE ... 3 of 3", "P3.18 ticked");
   - P4.13: `**Depends on:** P3.2 **DONE (Session 33, parallel batch 1, agent A` → insert
     ` (ticked ahead of P3.2: its deterministic acceptance met, Session 33)`.

   I read those reasons from SESSION_LOG, not from a user record; the integrator said all three
   were user decisions, so correct the wording if the user's record says otherwise. Each insertion
   adds no `**` and no `|`. Alternative: leave them as warnings (they do not fail the lint).
   **Recommend the insertions.**
5. **Where the 13 residue rows go** is agent C's / the user's call. One constraint to give C: a
   placement of an OPEN row on a CLOSED bucket's line (B1, B2, B4, B5, B7, B10, B13, B14 at
   `dde8b41`) reopens that bucket in `plan_status`; the fold refuses it unless that is the
   decision and `--allow-bucket-change` is passed.
