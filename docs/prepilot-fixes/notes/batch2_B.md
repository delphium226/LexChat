# Parallel batch 2, Agent B: P4.16, the opener strip's verb gap

Branch `worktree-agent-a9f4ac5a7d2483c67`, based on `578718f`. Deterministic code only,
**$0 spent**, no server, no replay, no rubric touched. Every command below runs from
`server_py/` with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8`.

**Setup deviation (as in batch 1):** the worktree came up on `main` (`a6b4a76`), not on
`578718f`. It had no commits, so I ran `git reset --hard 578718f` before any work.

## The change

`src/utils/openers.py`, `_FORMULAS`, the `bare` formula: **"highlight" added to the verb
list** (challenge, question, query, push back on, press on, flag, raise, **highlight**, pick
up on). One line of the pattern, plus the module docstring recording P4.16 and its one edit.
The object list, the `praise` formula (which already has "highlight" as "You highlight a
... point") and the `thanks` formula (which already has "highlighting") are unchanged.
Scoped agreement ("You are correct that X", and "to note/say/point out/observe") and the
affirm openers ("Yes, that is correct.") are untouched: `_SCOPED` and the affirm rule are
not edited, and the guards below pin a clause after "highlight that" staying as written.

## Why "highlight" and nothing else: the verbs actually found

A scratch scan (scratchpad only, not committed; it prints first sentences) read the first
sentence of **every** stored answer: all 55 replay directories, Deep Research included, plus
the pre-pilot export, **1,993 answers**. It listed every first sentence opening
"You are/You're [degree] right/correct to <verb>", every first sentence with
"right/correct to <verb>" anywhere, and every "Thank you for <verb>" opener. I read all of
them.

- **Opening "You are ... right/correct to <verb>": 4 answers, 2 verbs.**
  - `baseline` 6406 r3 t11: "You are entirely correct to challenge that, and ..." (already
    stripped).
  - `wave4_p33_post` p32_6406 r1 t8: "You are correct to challenge my earlier statement."
    (P4.13's edit).
  - export 6370 t6: "You are absolutely right to challenge this, and ..." (already
    stripped).
  - `wave4_b1_post` p32_6406 r2 t4: **"You are correct to highlight this."** (this row).

  So the only challenge verb not already listed is **"highlight"**.
- **"right/correct to <verb>" elsewhere in the first sentence: 2**, neither an opener: one
  ends a retraction sentence with "you are right to challenge it" (`wave4_p32_pre`
  p32_6406 r2 t10; correctly not an opener, the strip only reads the start), and one is
  a party's legal "right to" something (export 6350, not agreement).
- **"Thank you for <verb>": 21 openers, all in 6409 runs**: "providing" (10), "the
  citation / full citation / full title / clarification" (10), "confirming" (1). Every one
  thanks the lawyer for a citation or a title. None is a challenge-thanks, so the `thanks`
  formula's verb list needs nothing (the same finding as batch 1's P4.13 scan).
- `openers --drops` filtered to "you are/you're ... right/correct": 2 uncounted sentences,
  the retraction above and "On one reading, you are correct:" (it does not open with the
  formula, so the strip, which reads only the start, leaves it; it is qualified agreement,
  rightly left).

## Measured

`python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/baseline openers --all-dirs --export --strip`

| | answers | edited | left as written |
|---|---|---|---|
| before (`578718f`) | 1,783 | 47 (praise 16, bare 27, apology 4) | 9 |
| after | 1,783 | **48** (praise 16, **bare 28**, apology 4) | **8** |

The before figures equal the brief's (47 and 9 at `a449327`). The diff of the two full
outputs is exactly two lines: the `LEFT bare wave4_b1_post p32_6406 r2 t4` line became an
`EDIT bare` line, and the total.

**No other stored answer changed:** a scratch script ran the `578718f` strip and the new
strip over all 1,993 answers (Deep Research and the export included) and compared the full
`(answer, kind)` output: **1 differs**, the one above.

**The one new edit, read in full:** `wave4_b1_post` p32_6406 r2, run-file turn 4 (export
turn 5, as the brief has it), Conversational. The first sentence was the formula alone,
"You are correct to highlight this.", with no link or number. It is dropped; the answer
now opens on its next sentence, which says what could not be verified (an honest-failure
statement, which stays). The rest of the answer is byte-identical (1,947 to 1,912 chars,
the new text is an exact suffix of the old). No "However" was left dangling. **Correct.**
(Its content names the matter, so it is not quoted here.)

The 8 left as written are as before less this one: 5 affirm openers (a yes to a yes/no
question, deliberately untouched) and 3 praise openers with no clause to keep.

## Tests

`tests/test_answer_openers.py`:
- `test_a_highlighting_formula_goes`, **5 new forms**: the stored shape (formula alone,
  dropped), "that" with a comma-and connector, "my earlier statement" with a dangling
  "However", "the point" with a colon, "this point" with a dash.
- `test_a_highlight_with_content_is_left`, **4 guards**: "highlight that <clause>" (what was
  highlighted is the content: left), an unlisted object ("this distinction"), a qualifier
  carrying a number ("this in section 4"), and the formula with nothing after it.

All text synthetic ("the Order", "widget").

**Proven to fail with the change reverted:** a scratch pytest plugin reads the working
`openers.py`, replaces `flag|raise|highlight|pick` with `flag|raise|pick` at byte level,
**asserts it made 1 replacement and changed 1 line**, and loads that copy as
`src.utils.openers`. With it: **all 5 new-form tests fail; the 4 guards and the other 35
tests pass** (the guards pin behaviour that was already right). Without it: 44 passed.

**Full suite on `lexchat_test_b`: 2044 passed** (2035 at `578718f` plus these 9).

## Acceptance (P4.16, as the brief states it)

"Deterministic. Every new edit read and correct; a test per new verb, each failing with the
change reverted; no other stored answer changed." **Met:** one new verb, one new edit, read
and correct; 5 tests for it, each failing with the 1-line revert; the old and new strip
agree on every other stored answer (1,992 of 1,993).

## Not done

- No verb added that does not occur ("point out" and "note" are already scoped; "spot",
  "catch", "correct" do not open any stored answer in this formula). Adding them would be
  untested reach, as batch 1 decided for objects.
- "You are right/correct in highlighting ..." does not occur; not added.
- No FIX_PLAN, SESSION_LOG, tracker or rubric edit.

## For the integrator

1. Book P4.16 in FIX_PLAN (the row does not exist on the branch yet) with this acceptance
   and result.
2. After the merge, `openers --all-dirs --export --strip` reads **48 edited, 8 left** over
   1,783 answers; quote that, not 47/9, as the new reference.
3. Scratch kept outside the repo (session scratchpad): `verb_scan.py` and its output,
   `full_diff.py`, `show_edit.py`, `revert_plugin.py`. The before output is at
   `$PREPILOT_EVIDENCE/seam/batch2/B/openers_before.txt` (gitignored; it quotes answers).
