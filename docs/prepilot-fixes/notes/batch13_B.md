# Parallel batch 13, agent B: P3.12, the application line skipped, the sub-paragraph line, the partial cut, and `depth`'s "wind up" ($0)

**Base.** The worktree came up on `main` (`a6b4a76`) with no commits; I ran `git reset --hard 1889abb` (the
integrator's HEAD) before anything else. Everything here is based on `1889abb`. No commit I did not make appeared.

**Spend $0; live calls 0; model calls 0.** No server, no replay, no seam draw (not even `--dry-run`: no Worker
payload changes in this batch, see section 8).

**Commits (branch `worktree-agent-a3c5cea60c60b0773`):** `7b8edc9` (the four items, with tests), `31e727e` (a bound
on the sub-paragraph range reader, with tests), and this note.

**Functions changed or added (batch 12's lesson: name every one).**
- `server_py/src/utils/paragraph_restore.py`: new `_APPLIES`, `_QUALIFIES`, `_is_application`, `_application_run`,
  `_operative`, `cited_in_part`, `uncited_excerpt`, `_FIRST_SUB`, `_MORE_SUBS`, `_SUB_OF`, `_sub_list`, `_citations`,
  `SUB_LINE_WITH_BARE`, `_BOILERPLATE_SUBS`, `_MAX_SUB_RANGE`; changed `excerpt` (the skip rule), `render_line` (takes
  an optional excerpt), `restore_dropped_paragraphs` (the sub-paragraph line); removed `_BARE_APPLIES` (subsumed).
- `server_py/src/utils/schedule_units.py`: `cut_pieces` gains `whole_limit=None` (default: unchanged behaviour).
- `server_py/src/agent/agent_shared.py`: **one call changed in `schedule_route_block`**, `cut_pieces(unit, text,
  whole_limit=threshold)` (item 3 needs the verbatim threshold, which only the route knows). This is outside the two
  files the brief names; no other agent's section names `schedule_route_block`. **No change in
  `agent_core.process_user_request`** (D's collision point): the sub-paragraph line is inside
  `restore_dropped_paragraphs`, which the seam already calls.
- `server_py/tools/replay_report.py`: `_P312_WINDING_UP` only (`depth`'s paragraph-42 fact). Nothing in `authorities`.

**Built shape differs from the brief in four ways** (for the integrator to relay): item 3 is a keyword on
`cut_pieces` plus that one call in the route; item 2 carries two guards the brief did not name, found by the
measurement (a cap on how much of the paragraph the answer may already cite, and boilerplate words set aside in the
restatement test, sections 2.2 and 2.3); and item 2's reach is a setting (`SUB_LINE_WITH_BARE`, decision 2).

---

## 1. Item 1: the application line with conditions is skipped as a bare one is

**What changed.** `excerpt` skipped only a leading bare "This paragraph applies to X." line. It now skips the whole
**leading run** of application lines, bare or with conditions ("This paragraph applies where ... and— (a) ... (b)
...", "This paragraph also applies from the time when ...", openings `applies to / where / if / in / from / for /
while / during / when / until / so far as`, with `also` or `only`), and a sub-paragraph that only qualifies one of
those ("Sub-paragraph (2) has effect ... only if ..." where (2) was skipped). An operative use of the verb ("This
paragraph applies the provisions of ...") is not skipped; a qualifier of an operative sub-paragraph is not skipped;
an application line after the first operative one stays (only the leading run goes); a paragraph that is nothing but
application lines keeps them (as the bare case did).

**Dry run with the BUILT code** (`dryrun_b13.py` against the pre-batch module `pr_old.py`, `git show
1889abb:...`; all **70** replay directories, every turn whose Worker was handed a FETCHED block plus every 6335 turn
7: 39 turns read, 8 with exactly cut paragraphs; answers already carrying P3.12's lines (`wave4_b12_p312` reps 1 and
3) have them taken out first, so the line is recomputed as the product would write it):
- **Distinct handed paragraphs in the corpus: 3** (paragraphs 42, 43, 44 of the row's Schedule). **1 changes:
  paragraph 44**, whose excerpt went from its sub-paragraph (1) (the conditions of application, 259 characters) to
  (5) and (6) (431): the sub-paragraph that applies paragraphs 42 and 43, and the one on an administrative receiver.
  Paragraphs 42 and 43 open with the bare form already skipped: unchanged.
- **Stored lines that change: the paragraph-44 line in 5 stored answers** (`wave4_b10_sweep` rep 1, `wave4_b11_sweep`
  reps 2 and 3, `wave4_b12_p312` reps 1 and 3), 376 -> 548 characters each; and in 3 stored seam draws
  (`batch12/integrator/assent/rep3` x2, `swap/swap_rep3` r1). Nothing else moves. `depth` for 44: deep before and
  after on every one.
- **Read by hand (the line on `wave4_b10_sweep` rep 1, `handread_restored.txt`):** the line now gives what the
  interim moratorium does, and not when it runs. **`depth` reads 44 as deep because (6) contains "when the
  administration application is made"**, which is about an administrative receiver, not the trigger. So the decided
  change trades "when" (old line) for "what" (new line); neither line alone states both. Decision 1 offers a
  variant, rendered, that gives both within the 450-character cap.

**Forms no stored run contains, tested on synthetic input:** three application lines and a qualifier before the
rule (the shape of paragraph 44, built as `INTERIM`); every opening in the list; a qualifier of an operative
sub-paragraph; a qualifier with no application line before it; a qualifier naming an application line and an
operative one; an application line after the rule; "applies the provisions of"; a paragraph of application lines
alone.

## 2. Item 2: the sub-paragraph line for a paragraph the answer cites only in part

### 2.1 Measured first (`measure_subs.py`, `measure_subs.txt`)

Over the 16 answers with handed paragraphs (8 stored answers, 8 stored seam draws of 6335 turn 7), with this
batch's citation reader (`_citations`: "43(6)", "para 42(2)-(3)", "paragraph 42(2) and (3)", "para 43(2)-(3) and
(6)", "sub-paragraph (6) of paragraph 43", item brackets "(6)(a)" read as (6)):
- **V1** (every citation of the paragraph names a sub-paragraph): 12 candidates; 2 cite more than half of the
  paragraph's operative sub-paragraphs (both seam draws citing 43(1)-(6)), 10 give a line.
- **V2 only** (the answer also names the paragraph whole, e.g. "paragraphs 42 and 43 ... 43(6)"): 9 candidates; 1
  over half, 8 give a line.
- **What it adds:** for 43 cited at (6) (or (5) and (6)), its (2) and (3), 360 characters (enforcing security;
  repossessing goods); for 44 cited at (1) and (5), its (6), 314; for 44 cited at (4), its (5) and (6), 431; for 42
  cited at (2) and (3), its (4), 297.

Two guards came out of reading these: **(a) the half guard.** Two seam draws cite 43(1)-(6); without a cap they got
43(6A), (7) and (8) (the interpretation line), 302 characters of marginal text. The line now needs the answer to cite
**at most half** of the paragraph's operative sub-paragraphs (`cited_in_part`). **(b) boilerplate.** On
`wave4_b12_p312` rep 1 the 60% restatement test (A's paragraph-line rule, applied per sub-paragraph) dropped 43(2)
because the answer's 43(6) sentence repeated the two exceptions that close five of 43's limbs word for word. A word
in **three or more** of the paragraph's sub-paragraphs is now set aside in that test (`_BOILERPLATE_SUBS`), unless
nothing is left.

### 2.2 What was built (in `restore_dropped_paragraphs`)

For each handed paragraph the answer cites: if (`SUB_LINE_WITH_BARE` or every citation names a sub-paragraph) and
the answer cites at most half of its operative sub-paragraphs, one line carries **its operative sub-paragraphs the
answer does not cite**, whole and in order, within `MAX_EXCERPT_CHARS` (450), leaving out application lines and their
qualifiers (anywhere), an unnumbered piece, and a sub-paragraph the answer already says. It goes after the answer
paragraph holding the paragraph's **first** citation, shares the 3-line cap with the paragraph lines (either kind
first), and needs the unit mentioned, as the paragraph line does. **The template is unchanged** (`render_line` with
the excerpt passed in). The log line ("Restored N dropped schedule paragraph(s)") now counts both kinds.

### 2.3 Dry run with the BUILT code (`setting_b13.py`, `setting_b13.txt`; `dryrun_all.txt` lists every line)

`depth` verdict (42/43/44: d deep, c coarse) on every 6335 turn 7 with handed paragraphs:

| Answer | As written | Pre-batch restore | Built, setting on (default) | Built, setting off |
|---|---|---|---|---|
| `wave4_b10_sweep` rep 1 | SHALLOW ccc | PARTIAL dcd | **DELIVERED ddd** | **DELIVERED ddd** |
| `wave4_b11_sweep` rep 1 | PARTIAL ccd | PARTIAL dcd | **DELIVERED ddd** | **DELIVERED ddd** |
| `wave4_b11_sweep` rep 2 | PARTIAL dcc | PARTIAL dcd | PARTIAL dcd | PARTIAL dcd |
| `wave4_b11_sweep` rep 3 | SHALLOW ccc | PARTIAL dcd | **DELIVERED ddd** | **DELIVERED ddd** |
| `wave4_b12_p312` rep 1 | SHALLOW ccc | PARTIAL ccd | PARTIAL **cdd** | PARTIAL ccd |
| `wave4_b12_p312` rep 2 | PARTIAL ccd | PARTIAL ccd | PARTIAL ccd | PARTIAL ccd |
| `wave4_b12_p312` rep 3 | SHALLOW ccc | PARTIAL ccd | PARTIAL **cdd** | PARTIAL ccd |
| `wave4_b8_sweep` rep 3 | PARTIAL dcc | PARTIAL dcc | PARTIAL dcc | PARTIAL dcc |
| 8 stored seam draws | 2 DELIVERED | 6 | **8** | 7 |

**Stored live answers DELIVERED by `depth`: 0 of 8 (pre-batch) -> 3 of 8**, either setting; seam draws 6 -> 8 (on) or
7 (off). What remains, read: `wave4_b12_p312` reps 1 and 3 name paragraph 42 whole ("paragraph 42", "paragraphs 42
and 43") without its words, which neither line reaches (decision 4); rep 2 cites "Paragraphs 40–43", a range, read as
42 and 43 cited whole; `wave4_b11_sweep` rep 2 is the known wrong pinpoint (43's words under "paragraph 42"; reported,
not changed); `wave4_b8_sweep` rep 3 had paragraph 42 alone handed.

Read by hand (`handread_restored.txt`, `wave4_b10_sweep` rep 1 and `wave4_b12_p312` rep 3): each line lands after the
paragraph citing the provision, before the case-law paragraph; none repeats the answer; 43's line gives the two limbs
the answer did not state. **By hand, 44 is not fully delivered on any of them** (section 1: what, not when).
`misattributed_paragraphs` on the restored answers (`misattr_b13.txt`): the same one flag before and after (the known
case), no new flag from a line.

**Forms no stored run contains, tested on synthetic input:** "sub-paragraph(s) (N) [and (M)] of paragraph P"; "P(4)
and (5)", "P(4), (5)", "P(2) to (3)"; a long range "(1)-(14)" (read as its two ends; a range is expanded only when it
ascends by at most 12); a descending range; a lettered end "(6)-(6A)"; an item bracket "(6)(a)"; an empty list piece
("6, 7, and 8"); "7(4) and 8(1) and (2)" (the trailing (2) is 8's, not 7's); an application line cited alone (not an
operative one cited); an unnumbered opening; a paragraph with no sub-paragraphs; the line in a matched block; the
setting off; the cap with either kind first; the unit not mentioned; every uncited sub-paragraph already said.

## 3. Item 3: the paragraphs that cut are handed over when another named one does not

**What changed.** `cut_pieces(unit, text, whole_limit=None)`: where some named paragraphs cut and another does not,
**and the whole schedule is longer than `whole_limit`**, the ones that cut are returned (CUT) and the reason names the
rest. `schedule_route_block` passes its verbatim threshold. Below the limit the whole schedule still goes verbatim, as
before, so an un-headed paragraph named beside a headed one is not lost (it is in the whole text). With no named
paragraph cut, nothing changes (whole, then summarised). The `_paragraphs` misread itself ("para 43, 130", 130 a
section) is **not** changed (batch 12 A's option 1, recommended there: the partial cut makes the misread harmless).

**Dry run with the BUILT code** (`partial_cut_b13.py`, `partial_cut_b13.txt`; every stored section search naming
schedule paragraphs in all 70 directories, at the 8,000 fallback every stored replay ran at): **67 requests; 1
moves**: the `wave1` "paragraph 43, 130" call, from the whole Schedule summarised (92,066 characters) to paragraph 43
cut verbatim (1,450) with the reason. The 5 requests on other instruments name one paragraph each, so a partial cut
cannot arise; 61 are unchanged.

**New Worker-facing wording (to the user before merge),** appended to the reason inside the FETCHED block's header,
after "Below is the part of it this search named, labelled.":
- one: "Paragraph 30 has no single heading of its own in it to cut at**, so it is not among the parts below.**"
- several: "Paragraphs 30 and 31 have no single heading of their own in it to cut at**, so they are not among the parts
  below.**"

Rendered in the header for a labelled unit and an unlabelled one, from the provision list and from the text
fallback (`screen_b13.txt`), e.g.: "[PROVISION FETCHED BY CODE — the index holds Schedule 2 of ssi/1901/3 as one
provision (url: ...). This search's results left it out, so code fetched it from the index's provision list. Below is
the part of it this search named, labelled. Paragraph 30 has no single heading of its own in it to cut at, so it is
not among the parts below.]" The reader `handed_paragraphs` reads such a block as a named cut (tested), so the answer
seam's lines apply to it.

## 4. Item 4: `depth` reads "wind up"

`_P312_WINDING_UP` now reads `wind(?:ing)?[- ]?up`. **Over every stored 6335 turn-7 text (`wind_up_b13.py`: 70
texts, answers, reports and every seam draw under `seam/`, more than batch 12 A's 48 because the glob now takes the
integrator's batch 12 draws), 1 moves**: `batch12/integrator/r2brief` rep 1, PARTIAL -> DELIVERED, the hand verdict
(`handread_batch12.md`). "wound up" is still not read (tested as coarse).

## 5. Screens (BUILT code)

`screen_b13.py` (the integrator's `b9_screen`, every answer-reading detector, whole and per sentence) over 21 texts:
10 synthetic line variants (both kinds; labelled and unlabelled unit; with and without a URL; heading only; lettered;
application lines skipped), the 3 distinct lines the dry run adds to stored answers, and the partial-cut reason
alone and in its header (8). **1 trip, `OPENER_VOCAB` on a word inside paragraph 43's statutory text** (the same
non-trip batch 12 A recorded: that detector reads only an answer's first sentence and a line is never first, tested
for the sub-paragraph line too). The template and the new reason trip nothing. The product test
`test_every_line_variant_trips_no_detector` now covers both new variants, and `test_search_scope`'s wording screen the
partial-cut reason and headers.

## 6. Tests, revert, mutants

- **Tests:** `test_paragraph_restore.py` 115 (was 51), `test_schedules.py` +3, `test_replay_schedules.py` +6 (and
  `import pytest`), `test_search_scope.py`'s screen extended. Two existing tests changed on purpose: the application
  line with limbs is now skipped (`test_an_application_line_with_conditions_is_skipped_as_a_bare_one_is`), and a
  pinpoint "para 1(2)" now gets the sub-paragraph line, so that case cites "1(2)-(3)".
- **Full suite on `lexchat_test_b`: 3,450 passed** (`pytest_full.txt`).
- **Revert** (`revert_b13.py`; the four product files put back from `1889abb`, which removes **246 added and 19
  removed lines**, `git diff --numstat 1889abb -- server_py/src server_py/tools`): **64 of 418 fail** in the five
  test files; per item: `paragraph_restore.py` alone 58; `schedule_units.py` and `agent_shared.py` 4; `agent_shared.py`
  alone 1; `replay_report.py` alone 2. Every failure is behavioural (no import error).
- **Single-site mutants** (`mutants_b13.py`, one per guard and cleaning step, control 418 passed first): **50 of 50
  caught** (`mutants_b13.txt`): the skip rule (8: each opening class, "also", the operative verb, qualifier never /
  always, the lone-application keep, leading-only, no skip), the sub-paragraph line (23: the line, the setting both
  ways, the half guard `<=`/`<`/none, each emptiness guard, cited sub-paragraphs, application lines, unnumbered
  pieces, the restatement guard and its threshold both ways, boilerplate none / at two / no fallback, the cap, the
  empty excerpt, the position (end; last citation), the excerpt passed in, the unit check, the shared cap), the
  citation reader (11: sub-of form, span skip, further sub-paragraphs never / after any piece, ranges as bare, the
  empty piece, range expansion, its bound, descending, lettered end, item brackets), the partial cut (7: never, limit
  ignored, inclusive, nothing cut, the reason, its plural, the route's argument), the grader (1). One mutant (c7)
  first failed at collection (an empty `if` body) and was rewritten to a behavioural one; it is caught.
  `_BARE_APPLIES` and two `and skipped` checks were removed as restatements of other conditions (they could not be
  mutated to a different behaviour).

## 7. Where it sits, and the other code texts beside it

- **The answer seam, in order:** P3.13's `restore_dropped_siblings`, then P3.12's `restore_dropped_paragraphs` (now
  both line kinds), `misattributed_paragraphs` (logging, reads the restored answer), then P1.6's
  `enforce_provision_links`, then P4.3's lever R and P4.24's titles. Unchanged. **For agent D:** every line quotes
  statute in double quotes, and some quoted statute names an Act (paragraph 42's line names another Act in its
  sub-paragraph (4)); D's quotation guard must cover these lines, or the linker will link inside a quotation.
  Lever R's `_source_is_named` reads the answer too: a quoted Act name could re-admit a source the turn retrieved
  (pre-existing with batch 12's paragraph line; not measured here).
- **P3.13's "Also in s.N:"** never writes for a schedule URL, so the two restores never speak of the same provision.
- **The Worker-facing FETCHED tails** (batch 10 A, batch 11 A) are unchanged; only the reason gains its clause. The
  partial-cut header says "Below is the part of it this search named" and then that a named paragraph is not among
  the parts: consistent. No code text says the uncut paragraph is not held.
- **Observed, not changed:** for an unlabelled unit with no URL the line reads "Also in The Schedule, paragraph 7"
  (the capital mid-sentence is batch 12's `render_line`; with a URL it is inside the link, "[The Schedule](...)").

## 8. Price of the acceptance (the integrator's run)

**6335 n=3, about $1.80** (stored n=3 columns: `wave4_b12_p312` $1.78, `wave4_b11_sweep` $1.95, `wave4_b9_sweep1`
$1.75; the dearest stored rep $0.99, a capped runaway, so up to about $3). No seam draw is needed first: every change
is code that runs after the model has written (items 1, 2), or on retrieval (item 3, which moves only the stored
`wave1` call), and the dry runs apply the BUILT functions to the stored answers exactly as the product would. A draw
cannot show the live rate of the sub-paragraph line or of bare-cited paragraphs; only the sweep does.

**What to expect, on the dry run:** where the Manager cites 43 by (5)/(6) the line now adds its security and
repossession limbs (3 stored answers to DELIVERED by `depth`); where it names 42 whole without its words (`wave4_b12_p312`
reps 1 and 3) or misnumbers, the turn stays PARTIAL; 44 reads deep by `depth` but by hand lacks "when it runs"
unless decision 1(b) is taken.

## 9. What I did NOT do

- No change to `_paragraphs` (the "para 43, 130" misread itself); no exact-paragraph route (booked under P3.38, agent
  C's row); no line for a paragraph cited whole without its words (decision 4); no research-mode or Deep Research
  seam (batch 12's decision 13.5 stands); no change to the line's template, the 450 cap or the 3-line cap.
- No model call, no live call, no seam draw, no replay, no server. No edit to FIX_PLAN, SESSION_LOG, the tracker,
  CLAUDE.md or any rubric.
- I did not re-run the suite at `1889abb` to confirm its count (the integrator's 3,379); per-file counts above.

## 10. Decisions for the user

1. **What the paragraph-44 line carries, now that conditions are skipped** (the decided change gives the rule and
   not when it runs).
   1. **(Recommended) Rule first, then the skipped conditions if they fit:** the first operative sub-paragraph(s),
      then the leading application line(s) in what is left of the 450. On paragraph 44 this gives (5) then (1), 376
      characters: what the interim moratorium does and the first of the cases in which it runs; (2) and (4), the
      notice cases, do not fit. Not built; a small change to `excerpt`, screened and mutated before merge.
   2. **As built:** (5) and (6), 548 characters a line; by hand the trigger is missing (`depth` reads it deep only
      because (6) mentions an application).
   3. **Revert item 1:** quote (1) again (the trigger, not the rule).
2. **`SUB_LINE_WITH_BARE`: the sub-paragraph line also where the answer names the paragraph whole elsewhere.**
   1. **(Recommended) On (built):** 8 of 8 seam draws DELIVERED against 7, and 43 to depth on `wave4_b12_p312` reps 1
      and 3, which name 43 whole and pinpoint 43(6); the per-sub-paragraph restatement test keeps it from repeating
      what the answer says.
   2. **Off:** only where every citation names a sub-paragraph; the same 3 stored answers move to DELIVERED.
3. **The partial cut's new clause** (Worker-facing): ", so it is not among the parts below." / ", so they are not
   among the parts below."
   1. **(Recommended) As built.**
   2. **Also say the rest was retrieved:** "... it is not among the parts below, though code retrieved the whole of
      <unit>." Longer; one more sentence to screen.
4. **A paragraph the answer names whole without its words** (paragraph 42 on `wave4_b12_p312` reps 1 and 3; 42 and 43
   on rep 2's "Paragraphs 40–43"), the shape left after this batch.
   1. **(Recommended) Measure it first in the next batch:** how many stored answers name a handed paragraph whole and
      state none of its words (the restatement test inverted), and what a line would add; then decide.
   2. **Leave it**, and judge P3.12 on the sweep with this batch's lines.
5. **The acceptance run** (the integrator's, priced first): **6335 n=3, about $1.80** (up to about $3 with a capped
   runaway), after decisions 1 and 2. The hand-read decides; `depth` overstates 44 (section 1).

---

**Scratch** (gitignored, `docs/prepilot-fixes/evidence/seam/batch13/B/`, copied to the main checkout at the end):
`dryrun_b13.py` / `dryrun_item1.txt` / `dryrun_all.txt` / `dryrun_lines.json`, `measure_subs.py/.txt`,
`setting_b13.py/.txt`, `partial_cut_b13.py/.txt`, `wind_up_b13.py/.txt`, `screen_b13.py/.txt` (with `b9_screen.py`),
`misattr_b13.py/.txt`, `mutants_b13.py/.txt`, `revert_b13.py/.txt` (with `old/`, the four pre-batch files),
`pr_old.py`, `cite_forms.py/.txt`, `handread_restored.txt`, `pytest_full.txt`, the commit messages. They quote
statutory and answer text; nothing of it is in this note.

**Data handling.** This note names no question, brief, search term or case name, and quotes no statutory text of a
session's instrument (paragraph numbers are the row's, as FIX_PLAN gives them; the synthetic renderings use the
tests' "Widget" schedule). The staged diffs were grepped for session numbers, instrument ids and matter words before
each commit; the only hits are the `DEPTH_TRUTH["6335"]` tests in `test_replay_schedules.py`, the standing exception,
beside that file's existing ones.

**Integrator review (2026-10-09):** a surviving mutant (the sub-paragraph line's break searched from 0, not from the first citation) is now caught by `test_the_subparagraph_line_lands_after_the_answer_paragraph_citing_it` (citation in the second answer paragraph; fails under the mutant, passes on the built code; harness `s24`, 1 failed of 419); full suite on `lexchat_test_b` **3,451 passed**.

## 11. B1 built (user decision, 2026-10-09): the rule first, then the conditions

**User decisions relayed by the integrator:** B1 as recommended (built here); B2 on, as built; B3 kept as built; B4
measured in the next batch; the partial-cut clause approved as built.

**The rule (`excerpt`, `utils/paragraph_restore.py`; the line template unchanged).** Whole sub-paragraphs within
`MAX_EXCERPT_CHARS`, in this order: the first operative sub-paragraph (none fits: the heading only, as before);
then the leading application lines that carry conditions, in order, while they fit, stopping at the first that does
not (a bare "This paragraph [also] applies to X." line is never carried, as batch 12 A decided; a qualifier is
carried only beside every line it qualifies); then the further operative sub-paragraphs, in order, while they fit.
`_BARE_APPLIES` is back for the bare test. The sub-paragraph line (`uncited_excerpt`) is unchanged.

**Rendered (synthetic, BUILT code, `screen_b1.txt`):**
> Also in [Schedule 5](http://www.legislation.gov.uk/ssi/1901/3/schedule/5), paragraph 2 (Widget fees): "(2) The fee is set by the Minister. (1) This paragraph applies where a licence is sought and— (a) the dealer is new, or (b) the licence has lapsed."

**Dry run with the BUILT code** (`dryrun_b1.py` against the module at `a622ad6`, all 70 replay directories,
`dryrun_b1.txt`): 1 of the 3 distinct handed paragraphs changes, **paragraph 44: (5) and (6), 431 characters ->
(5) then (1), 376** (what the interim moratorium does, then the first case in which it runs; its notice cases (2)
and (4) do not fit). **The paragraph-44 line changes in 5 stored answers** (`wave4_b10_sweep` rep 1,
`wave4_b11_sweep` reps 2 and 3, `wave4_b12_p312` reps 1 and 3) and 3 stored seam draws; nothing else moves; `depth`
verdicts unchanged on every one (44 deep before and after; now the trigger is in the line itself). Paragraphs 42 and
43 open with the bare form: unchanged. Screen (`screen_b1.py`, 21 texts): the same single `OPENER_VOCAB` non-trip
inside paragraph 43's statute as section 5; the new 44 line and both synthetic variants trip nothing.

**Tests:** five excerpt tests rewritten to the new order (conditions after the rule; every opening; the leading run;
`INTERIM` at the cap and uncapped) and six added (conditions stop at the first that does not fit; a further rule
still follows; a qualifier only beside its line; a bare "also applies to" line; an empty paragraph; a first rule over
the cap with a later one that fits). **Mutants (control 425 passed first): 59 of 59 caught** (`mutants_b1.txt`),
the 8 new ones: conditions never carried; a bare line carried; the bare "also" form carried; a qualifier without its
line; conditions not stopping; no further rule after them; the empty guard; a first rule over the cap. (Mutant a8
was rewritten to the new code: `run = 0`.) **Full suite on `lexchat_test_b`: 3,457 passed.**
