# Parallel batch 1, Agent A: P4.13 and P4.14

Branch `worktree-agent-a9eef0199da67f750`, based on `01b66b0`. Deterministic code only,
$0 spent, no server, no replay. Every command below runs from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8`.

**Setup deviation:** the worktree was created from `main` (`b2a3fd8`), not from the fix
branch. It had no commits of mine, so I reset it to `01b66b0` before starting. Please
check that the other agents' worktrees are on `01b66b0` too.

## P4.13: the opener strip's coverage

**Change** (`src/utils/openers.py`): I added a new object alternative, `_MY_EARLIER` =
`my (earlier|previous|last|original) (statement|answer|response|reply|position|assessment)`.
It now follows the `bare` formula ("right/correct to challenge|question|query|push back
on|...") and the `thanks` formula ("Thank you for challenging|pressing|... [me] [on]").
Nothing else changed. A scoped agreement ("You are correct that X"), a plain "Yes, that
is correct." and a formula followed by a clause naming what was challenged ("...my
earlier statement that X") are still left as written, for the reason the module
docstring gives.

**Measured** with
`python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/baseline openers --all-dirs --export --strip`:

| | edits | left as written |
|---|---|---|
| before (`01b66b0`) | 46 (praise 16, bare 26, apology 4) | 8 |
| after | 47 (praise 16, bare 27, apology 4) | 7 |

This is over 1,708 answers that are not Deep Research. **There is one new edit, and I
read it:** `wave4_p33_post` p32_6406 r1, run-file turn 8, which is export turn 9 (the
FIX_PLAN row's "turn 9"). The first sentence was the formula alone. It was dropped,
and the answer now opens on its first content sentence, which carries a citation. The
edit is correct. No other answer changed. The 7 left as written are the 5 affirm
openers (a yes to a yes/no question, deliberately untouched) and 2 praise openers with
no clause to keep, as before.

**Population check** (a scratch scan, not committed, because it prints first
sentences): over all 1,915 stored answers including Deep Research and the export, I
listed every first sentence mentioning "my earlier/previous/last/original/prior/
initial/first" or "to challenge/question/query/push back/press", or opening "Thank you
for", and read them all (39 lines). The new object occurs at the start of only that
one answer. None of the "Thank you for providing the full title / the citation / the
clarification" openers (all in 6409 runs) matches the thanks formula, before or after. They
are not challenge-thanks, and they stay.

**Tests** (`tests/test_answer_openers.py`):
- 8 new forms, covering every noun and adjective at least once, in both formulas, and
  including the connector, colon and dangling-"However" shapes.
- 5 guards that stay as written: a clause after the object, an unlisted noun
  ("reading", "analysis"), "the earlier statement" (not "my"), and scoped agreement.

**Proven to fail with the change reverted:** a scratch pytest plugin swaps
`src.utils.openers` for its `01b66b0` copy. With it, all 8 new-form tests fail and the
5 guards pass, as intended (they pin behaviour that was already right).

**Acceptance (the row):** "deterministic; the dry run's new edits all read, and a test
per new form" (the brief adds "each failing with the change reverted"). **Met.** The
one new edit is read and correct, every new form has a test, and each of those tests
fails with the change reverted.

**Not done:** I did not add objects the brief did not list ("it", "conclusion",
"reasoning", "analysis", "reading"). None of them opens a stored answer after a
challenge formula, so adding them would be untested reach.

## P4.14: an echoed footer ahead of P1.6's link note

**Measured first** (scratch scan, then the committed instrument below). Over every
stored answer (54 replay directories plus the export, 1,915 answers), 22 answers
carry more than one `*Search scope:` line:

| directory | answers | shape (blocks from the first scope line) |
|---|---|---|
| `wave2_p22_final` | 18 (6409, all reps) | echo + footer, echo trailing: predates P3.5's strip, already handled by the current seam |
| `wave4_p33_post` | 2 (6338 r2 t2, 6345 r1 t2) | echo + P1.6 note + footer: **the row** |
| `wave0_conv` | 1 (6341 r1 t5) | echo + P1.6 note + footer: **the same shape, earlier** |
| `wave2_p27` | 1 (6341 r2 t2, Research mode) | echo + the model's own paragraph + footer |

`replay_report --dir <d> caselaw` agrees directory by directory (`TWO_LINES`
`wave0_conv` 1, `wave2_p22_final` 18, `wave2_p27` 1, `wave4_p33_post` 2, every other
directory 0). **Correction to the brief:** it said every directory other than
`wave4_p33_post` reads 0. Three older directories do not, and one of them
(`wave0_conv`) is this row's shape, so the defect is older than Session 32.

**Cause, confirmed in code:** `enforce_provision_links` appends `PROVISION_FOOTNOTE`
after the model's text (`citation_links.py`). `strip_answer_footer` then runs just
before the real footer and matches only a trailing run of scope lines
(`_ECHOED_FOOTER`, anchored at `\Z`), so an echo followed by the note is left in place.
The Deep Research path (`run_deep_research`) has the same order: suggestions strip,
then `enforce_provision_links`, then the late strip.

**Change** (`src/agent/agent_core.py`): on both paths, `strip_answer_footer` now also
runs right after the suggestions block is removed. At that point the echo is still the
end of the model's text, which is before anything code appends. The halt and lost
notices are prepended, so they do not matter here, and `restore_dropped_siblings`
inserts after a paragraph, never after a trailing footer. The strip function and
`_ECHOED_FOOTER` are unchanged, so P2.8's `_earlier_footers` (last line of the trailing
block) and the pinned trailing-only behaviour stay as they were. The late strip before
the real footer stays too. The footer is still appended last, so the case-law clause
stays last.

**Dry run, as a committed data-free instrument:** `python -m tools.footer_echo --dir
<replay dir> [--all-dirs] [--export] [--text]`. A stored answer does not carry the
model's own text, so the tool rebuilds it: it splits off the code footer and a trailing
P1.6 note (read as appended by code), then applies the product's own
`strip_answer_footer` in the order before P4.14 and in the order after it. It lists
every answer where the two differ (`--text` prints the text ahead of the footer; that
output quotes answers and stays out of the repo).

- `python -m tools.footer_echo --dir $PREPILOT_EVIDENCE/replay/baseline --all-dirs --export`:
  1,915 answers in 55 groups; more than one scope line **22 as stored, 4 rebuilt
  before P4.14, 1 after**. **P4.14 changes 3 answers**: `wave0_conv` 6341 r1 t5
  (2,558 to 2,036 chars), `wave4_p33_post` 6338 r2 t2 (2,759 to 1,732) and 6345 r1 t2
  (2,623 to 2,180).
- `python -m tools.footer_echo --dir $PREPILOT_EVIDENCE/replay/wave4_p33_post`: 78
  answers, **2 as stored, 2 before, 0 after**.

**I read all three edits (`--text`).** In each one, the copied scope line is the only
thing removed. The model's prose ends where it did, P1.6's note follows it, and the one
code footer (the stored answer's own last line) comes after that. None of the three
lost anything else. No other stored answer changes.

**The one left (not this row):** `wave2_p27` 6341 r2 t2. It is in Research mode, and
the model wrote a paragraph of its own after the copied line. The trailing-only strip
leaves it deliberately, and that is pinned:
`tests/test_search_scope.py::test_the_strip_cannot_eat_answer_text_that_follows_a_copied_footer`
asserts that a footer followed by text is returned unchanged. Removing an echoed line
anywhere would need that test's assertion changed (its intent, that no answer text is
lost, would still hold). That is a decision for the integrator or the user, not
something to fold in here. n=1.

**Tests:**
- `tests/test_echoed_footer.py` runs the real seams:
  - the Manager path with the echo at the end of the model's text, and with a
    suggestions block after the echo;
  - Deep Research synthesis with the same echo.
  Each asserts that exactly one scope line appears and that it is this turn's (P2.8's
  `_earlier_footers` reads it back from the last line). Each also asserts that the P1.6
  note survives ahead of it. The Manager cases assert that the case-law clause is last.
  A guard checks that prose after an echo survives.
- `tests/test_footer_echo_tool.py` covers the instrument.
- **Proven to fail with the change reverted:** the scratch plugin swaps
  `src.agent.agent_core` for its `01b66b0` copy. With it, the 3 seam tests fail (2
  scope lines against 1) and the guard passes (as intended).

**Acceptance (the row):** "deterministic; TWO_LINES 0 on this directory rebuilt
through the seam, and a test" (the brief adds "no other stored answer changed
unexpectedly"). **Met, on the rebuild:** `wave4_p33_post` rebuilt through the fixed
seam has 0 answers with more than one scope line (2 before). The seam tests fail with
the change reverted. The only other stored answer that changes is `wave0_conv` 6341 r1
t5, which has the same defect and gets the same correct edit. One caveat: the rebuild
reconstructs the model's text from the stored answer, because the audit does not keep
the Manager's raw reply. So "rebuilt through the seam" means the product's
`strip_answer_footer` applied in the seam's order, not a re-run of
`process_user_request`. The seam itself is covered by the unit tests.

## Suite and commits

- Full suite on `lexchat_test_a`: **2003 passed** (1983 at `01b66b0`, plus 13 opener, 4
  seam and 3 tool tests).
- Commits: P4.13 (`openers.py` plus tests), P4.14 (`agent_core.py`, `tools/footer_echo.py`
  and tests), and this note. Each staged diff was grepped for session ids, instrument
  ids and matter words before commit. All test text is synthetic (Widget Order 1901).
- Scratch only, not committed: the first-sentence scan, the first footer dry run (same
  numbers as the tool), and the revert plugin.

## For the integrator to decide

1. Whether to widen `strip_answer_footer` to remove a copied scope line anywhere in the
   answer. This would close `wave2_p27` 6341 r2 t2 and requires changing the assertion
   of the pinned `test_the_strip_cannot_eat_answer_text_that_follows_a_copied_footer`.
2. The FIX_PLAN rows' "seen 2 of 78 turns here and 0 in `wave4_p33_pre`" is right for
   that pair. The same shape is also in `wave0_conv` (1), and the `caselaw` TWO_LINES
   of `wave2_p22_final` (18) and `wave2_p27` (1) are older and different: the first is
   already handled by P3.5, the second is item 1.
3. `openers.py`'s docstring now records P4.13's one edit over the 1,708 answers.
