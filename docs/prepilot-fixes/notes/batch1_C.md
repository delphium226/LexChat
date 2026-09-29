# Parallel batch 1, agent C: P3.16 (the summariser's glosses)

Branch `worktree-agent-a08a77a8fc7633231`, based on `01b66b0`. **The worktree was created from
`main` (`b2a3fd8`), not from the integrator's head; it was reset to `01b66b0` before any work.**
Commits: `66ebd0e` (detector), `d8c0c53` (redraw/panel instruments), `9ba4e1e` (the lever,
separable), and this note. Spend **$2.905 of $3**. Full suite on `lexchat_test_c`: **1997
passed** (1983 before, plus 14 new).

**Acceptance (the row), stated before any claim:** "the detector's count after is 0 on a fresh
sweep of 6406 and 6338 (n=3), and `panel` keeps at least as many provisions with no rise in
negatives." **NOT MET: not yet measured.** The sweep is the integrator's. What the seam shows
is below. The panel half holds on aggregate for the lever (provisions 335 against 253, negatives
12 against 13), but with the per-slot losses listed in step 2.

All commands run from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and `PYTHONIOENCODING=utf-8`.

## Step 1 (free): the detector

**Invocation (committed, data-free, honours PREPILOT_EVIDENCE):**

    python -m tools.summary_probe glosses [--dir D ...] [--session S ...] [--list] [--ids]

`--dir` takes names under `replay/` or paths, and defaults to every directory. `--session`
matches the script base, so `6406` covers the `p32_6406_*` files. For the after-column:
`python -m tools.summary_probe glosses --dir <after-dir> --session 6406 6338`, where the count to
read is the `GLOSSES:` figure. `--list` prints every match with its text, so it goes to the
console only.

**What it counts.** A gloss marker (`GLOSS_MARKERS`: by definition, which means, this/that
means, meaning that, i.e., that is, in other words, by extension, by implication, implicitly,
implies, implying, effectively, thus, therefore, hence, it follows, necessarily, suggests,
suggesting) in the summariser's own text, meaning `final_result` cut at the first code-appended
block (URLs, outline, scope notes, nudges). The window is up to 6 words before the marker and 10
after, inside its sentence and narrowed to its parenthetical. It counts as a gloss when under 50%
of the window's word trigrams occur, in order, in the raw text. Support has to be local because
every word of the known instance, and the phrase "by definition" itself, occur somewhere in its
271K raw text. The following are excluded:
- a title whose year is an id year in the raw text (section results carry ids, not titles);
- a consequent that is about the summary itself ("... therefore, not summarised here");
- "information/evidence suggests" (a statutory condition);
- "effectively" as an adverb of manner.

Only summaries from `search_legislation_sections`, `get_legislation_text` and
`get_legislation_changes` are counted. Case-law summaries are listed as CASE and not counted.
Memo hits are skipped. `--ids` separately lists a change record's id given an adjacent title of
another year.

**Every match was read by hand**, as the unfiltered first listing (440 lines: 438 marker matches
plus 2 ids; scratch coding, gitignored scratchpad only):

| family | matches | the summariser's own inference or characterisation | paraphrase of the text | note about the text supplied | the court's own reasoning | summariser applies a judgment to the question |
|---|---|---|---|---|---|---|
| legislation | 274 | 206 | 37 | 31 | - | - |
| case law | 164 | - | - | - | 136 | 28 |

The filters were then fixed from that read. Each drop was checked against the codes: they drop
29 of the 31 notes, 23 of the 37 paraphrases, 5 case-law lines and **1 of the 206 real glosses**
(a sentence that runs on into a parenthetical note, so its consequent reads as a note). No match
was added.

**Final counts, over every stored audit (54 directories):**
`python -m tools.summary_probe glosses`
- **221 glosses in 3,618 summaries of legislation** (in 169 run-file turns). **By the hand codes,
  205 are real (93%), 14 paraphrase and 2 notes.**
- 2 ids given a title of another year, both real: `wave4_p33_post` 6345 r2 t3 and `wave4_p45`
  6365 r1 t1.
- 159 case-law matches listed, not counted: 131 are the court's reasoning; 28 apply an English
  judgment to the question's jurisdiction or statute. The 28 are relevant to P3.3/P3.18 and are
  not in this row.
- By marker: therefore 103, effectively 29, by extension 18, this means 14, thus 12, i.e. 11,
  suggests 8, suggesting 6, implies 6, implying 4, by implication 4, necessarily 3, implicitly 3,
  by definition 1.
- By tool: section search 181, change records 35, legislation text 6.
- Real glosses by session (the 206 hand codes on the unfiltered list): 6341 88, 6348 41,
  6406 17, 6369 11, 6345 9; 18 other sessions have 1 to 5 each.

**False-positive shape, of the counted 221:**
- 14 paraphrases: "i.e." restating the text's own cross-reference (7); "effectively" where the
  text itself characterises the provision (3); "therefore" restating (2); "this means" or
  "suggests" rendering a definition (2).
- 2 scoping notes.

**Misses (not measured):** a gloss worded with no marker. Parentheticals with no marker are not
counted: 8,183 of them carry a word the raw text lacks, overwhelmingly paraphrase (scratch count,
not behind a committed command). The id check cannot see a wrong title of the right year, or an
id written "type YYYY/N" with a space. The Session 32 addendum's two cases are one of each, so
they are **not** among the 2.

**Rates.**
- By directory, from the default output: `wave4_p33_post` (under the source rule) has 4 in 189;
  `wave4_p33_pre` 3 in 73; `baseline` 27 in 523.
- **The acceptance sessions** (`glosses --session 6406 6338`) have 21 in 424 summaries across
  all directories: `baseline` 9 in 139, `wave1` 2 in 60, `wave2` 3 in 53, `wave4_p32_pre` 4 in 75,
  `wave4_p33_pre` 1 in 12, and **`wave4_p33_post` 2 in 81, both 6406**. Those two are p32_6406
  r1 run-file t6, the known instance and flagged, and r3 t7 (an "effectively" gloss). 6338 has 0
  in `wave4_p33_post`.
- **The rate survives the source rule, so a lever was warranted.**

## Step 2 (paid): the lever

**Plan and estimates were written here before each draw** (`--dry-run` prices input characters
/ 4 at $0.50 a million tokens plus 1,500 output tokens at $3 a million). Actual costs came in
at 60-95% of the estimates. Every draw was made on 2026-09-29 with
google/gemini-3-flash-preview at temperature 0. Draws saved under
`$PREPILOT_EVIDENCE/seam/batch1/C/` (gitignored), with each run's console output as `<name>.txt`
beside it.

**Wording D** ("State what each provision says; do not add your own reading of what it means,
what it includes or excludes, or what follows from it.") was drawn on both sides against the
current prompt. The current prompt is the "without rule" side: the source rule, no gloss rule.

| draw | command (plus `--rule gloss`) | D | current prompt | cost |
|---|---|---|---|---|
| 10 small gloss slots of 6406/6338, 3 a side | `redraw --glosses --dir wave4_p33_post wave4_p33_pre wave4_p32_pre wave2 wave1 baseline --session 6406 6338 --reps 3 --max-raw 140000` | glosses 2, provisions 167, negatives 7 | glosses 2, provisions 163, negatives 15 | $0.562 |
| the 2 post-rule 6406 slots, 3 a side | `redraw --glosses --dir wave4_p33_post --session 6406 --reps 3` | 0, 46, 1 | 1, 43, 6 | $0.405 |
| panel, 24 other-session results, 2 a side | `panel --exclude 6338 6406 --out .../panel_D` | provisions 349, negatives 12, glosses 1 | 253, 13, 1 | $0.715 |

The first two draws were not saved (`--out` came after them). Their gloss counts predate
three note shapes added later, so they may include notes.

**D FAILED the panel:** `wave3_p38` 6383 t1 `get_legislation_text` returned the bare word
"Summary:" in 2 of 2 draws; the current prompt gave 24 provisions. The brief was a
filter-style question. D was dropped.

**Wording E, the lever (`9ba4e1e`):** "Do not add conclusions of your own either: where the text
does not itself say that a provision includes, excludes or leads to something, leave that out
rather than inferring it." This follows the shipped source rule's "leave out" shape. It was drawn
on the with-rule side only (`--side with`) and set against the same day's current-prompt draws
above:

| draw | E | current prompt, same day | cost |
|---|---|---|---|
| panel (`panel --exclude 6338 6406 --side with --out .../panel_E`) | **provisions 335, chars 99,459, negatives 12, glosses 0** | 253, 92,021, 13, 1 (read: a note shape, so 0 real) | $0.383 |
| 2 post-rule 6406 slots (`... --side with --out .../redraw_big_E`) | **glosses 0 of 6**, provisions 51, negatives 5 | 1 of 6 (unsaved), 43, 6 | $0.192 |
| 10 small slots (`... --max-raw 140000 --side with --out .../redraw_small_E`) | glosses 5, **all 5 read as notes** (the detector was widened, so 0), provisions 145, negatives 13 | 2 (unsaved), 163, 15 | $0.287 |
| 6338 Act additions, Session 32's 9 slots (`redraw --dir wave4_p33_pre --session 6338 --rule gloss --side with --reps 3 --out .../adds6338_E`) | **additions 0 of 27**, provisions 30, negatives 12 | not drawn (Session 32's C: 0 of 27) | $0.160 |
| 2 post-rule 6406 slots, current prompt, saved (`... --side without --out .../redraw_big_HEAD`) | - | **glosses 3 of 6**: the recorded gloss itself in 2 of 3 at r1 t6; an "effectively" gloss in 1 of 3 at r3 t7; provisions 44, negatives 2 | $0.201 |

**Hand-read of E:**
- At the known slot, E renders the provision that carried the gloss in the text's own terms in
  3 of 3 draws. I found no unmarked form of the gloss in E's draws.
- The r3 slot keeps a false "the text does not contain" note in E's draws. That is P3.12's
  shape, and the current prompt had 6 negatives on the same slot.

**Per-slot losses under E**, read, so the band is not hidden by the totals:
- panel 6345 t4: 17 provisions to 2 (2 of 2 draws). The draws keep one directly relevant
  subsection and drop three related provisions.
- panel 6365 t1 section search: 15 to 10.
- panel 6365 change record (`wave4_p45`): 14 to 0, with 2 negatives. The current prompt also
  declared no provisions in 1 of its 2 draws.
- panel 6341 t6: characters 1,988 to 605.
- small 6406 r2 t5: 8 provisions to 0. E names one article plus a note in 3 of 3.
- small 6338 `wave2` change record: 29 to 19, with 3 negatives against 1.

Slots that gained: 6341 t7 (1 to 13), both 6365 change records in `wave4_p47b` (9 to 32 and
55 to 92), 6383 t2 (17 to 40), and the D collapse slot (restored to 24).

**Rule 5.** Three tests in `tests/test_summary_source_rule.py` fail with the lever reverted on a
scratch copy of `summarisation.py` and `local_prompt_cache.py`:
- the rule in the prompt, after the source rule and before the text;
- the probe's without-side drops exactly that rule;
- the cache version is v3.

All of the probe's own tests pass either way, so `66ebd0e` and `d8c0c53` stand without the
lever. `_CANON_VERSION` is **v3**.

## Does the seam evidence support the after-column?

**Yes, with caveats.**

For:
- At the one place the defect is known to recur, the current prompt reproduces the recorded
  gloss in 2 of 3 draws, and 3 of 6 across both post-rule slots.
- E gives 0 of 6 there. It gives 0 real glosses in all 111 of its draws.
- The panel holds on aggregate, and 6338's additions stay at 0 of 27.

Against:
- The discriminating sample is 6 draws a side.
- E narrows some summaries, including 2 slots in the acceptance sessions (the small set's
  provisions fall 163 to 145).
- Negatives are not reduced on aggregate.

**If it goes in:** the after-column's per-slot links and `sources_kept` rule (P2.4) should be
read for 6406 and 6338 with that narrowing in mind.

## What I did not do

- No replay, no server, no `replay pin/run/restore`, and no rubric edit.
- No fix to the misses listed in step 1.
- No count of the 28 case-law applications as a row.
- `redraw` does not reproduce `summarise_for_query`'s consolidation pass (it runs only when
  the joined partials exceed a chunk).
- The panel draws in `panel_D` were saved before a fix to `_save`. Two results of one turn
  share a label, so 4 panel files were overwritten, and in `redraw_small_E` one of the two
  6338 r1 t2 slots was overwritten. The in-run totals above are authoritative. Files are now
  prefixed with the slot index.

## For the integrator to decide

1. Whether `9ba4e1e` (the lever, separable) goes into the combined after-column.
2. The deploy note: cache v3 makes every cached summary unreachable, as v2 did.
3. Whether the 28 case-law applications of English authority to the question's jurisdiction
   (the 6375 shape) belong to P3.18 or a new row.
4. Whether the id-title check's two real mis-expansions need a row. They are change-record
   summaries, P3.16's evidence item.
