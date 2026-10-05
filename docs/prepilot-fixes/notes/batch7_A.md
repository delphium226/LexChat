# Parallel batch 7, agent A: P3.24's lever built (the per-instrument commencement line)

Session 39, 2026-10-05. Branch `worktree-agent-a1ccdb1d80445769e`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard 6011b4fe0ba669cd68e225ac349c35f70f5fc724` before any work.** Everything below is
based on `6011b4f`.

**Spend: $0.** No model call, no external call of any kind, no server, no replay pin/run/restore.
Full suite on `lexchat_test_a`: **2216 passed** (2195 + 21 new), from `server_py/`:
`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_a python -m pytest -q -p no:cacheprovider`.

This note quotes no lawyer's text, search term, instrument id or title from a session. Commands run
from `server_py/` with `PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and
`PYTHONIOENCODING=utf-8`; `$S` is the gitignored scratch `docs/prepilot-fixes/evidence/seam/batch7/A`.

## 1. What changed, and why

**Code line first (Invariant 2), as decided on P3.24's row.**

- **Recorder** (`search_scope.record_currency`, the `get_legislation_changes` branch, called on the
  raw result like every recorder at that seam). The entry keeps P2.5's `commenced`, `orders` and
  `repeals` byte for byte and adds, from `_commencement_split`: `commenced_by_other` (the `coming into
  force` relations in groups with `self: false`), `commenced_self` (batch 6 B's F3: the instrument's
  own commencement provision acting on itself), `commenced_listed_in_full` (no group cut by
  `changes_not_listed` or the older `changed_provisions_not_listed`, none hidden by the 40-instrument
  cap, i.e. listed relations >= `provisions_commenced`, and `window_complete` not false) and
  `direction`. It reads both group shapes so a stored result rebuilds through it.
- **The line** (`_currency_limb` -> `_commencement_lines`). P2.5's sentence "Commencement relations
  WERE retrieved for X — a provision-level statement about those … is supported" is replaced (it
  counted self relations, F3) by one line per instrument whose change record the step consulted, in
  order of consultation. Cases, computed from the record:

  | case | when | what the line permits |
  |---|---|---|
  | `other_full` | relations by another instrument, all listed | a listed provision as commenced by the instrument named; one not listed as "not recorded as commenced", citing the record |
  | `other_cut` | relations by another instrument, not all listed | the listed ones only; not whether an unlisted one has been commenced |
  | `self_only` | only the instrument's own (`self: true`) | nothing either way, from this record |
  | `unlisted` | a count, no commencement group listed | nothing either way, from it |
  | `none` | no commencement relation (empty record, amendments or `Commencement Order` rows only) | nothing either way, from it |
  | `by` | only the changes it makes TO other legislation consulted | the other legislation's provisions it lists as commenced; nothing about its own |

  Then a closing line: for any instrument not named, this step consulted no change record, so do not
  state whether its provisions have been commenced (or, with no record at all, one sentence saying
  so). Where one instrument is consulted twice (memo hit) its line takes the call that shows most;
  `to` and `by` on one instrument give one line carrying both facts. Beyond 12 instruments the rest
  share one line that permits nothing. The repeal sentence, the title-marker and `valid_date`
  sentences, the closing Status paragraph, the repeal count (`_REPEAL_EFFECT_TOKENS`, P3.28) and the
  footer clauses (P4.20) are untouched.
- **The prompt sentence** (`prompts._COMMENCEMENT_RECORD_RULE`), inserted inside `_IN_FORCE_RULE`
  straight after its `Commencement Order` bullet, so it reaches exactly the three Worker prompts that
  carry the rule (`WORKER_SYSTEM_PROMPT`, `_HYBRID`, `_CONVERSATIONAL`) and no other. The exact text:

  > - (a) counts only a relation made by ANOTHER instrument (`self: false`), never a `self: true` one, which is the instrument's own commencement provision and says how its provisions come into force, not whether they have; and a provision the record does not list may be called "not recorded as commenced" only when its relations by another instrument are all listed, so with only `self: true` relations, none, a list cut short, or no change record consulted, do not state whether a provision has been commenced.

  **It does not point at the line, and that is a correction of the brief, checked in the code:** the
  Worker never sees `_currency_limb`. `worker_scope_block` is appended to the Worker's report after
  the Worker has written it (`agent_core.run_worker_agent`, `result["content"] + _scope`, ~line 442);
  its readers are the Manager and the Deep Research synthesis. A sentence pointing the Worker at the
  line would point at nothing, so the sentence states the same rule in the terms of the record the
  Worker does see (`self: false/true`, a cut list). It also corrects the rule's own bullet (a), which
  said any `coming into force` relation means "that named provision was commenced by that named
  instrument", self relations included (F3 in the prompt). Decision 2.

- **Tooling, needed for this row's acceptance** (`replay_report.negcurrency_evidence`). The grader
  read only the pre-P3.19 group field `changed_provisions`. On a record in P3.19's `changes` shape it
  saw no provision, so a sentence denying a provision the record lists as commenced was graded
  **SUPPORTED** (`python $S/nc_shape_probe.py .`: before, `('…is not yet in force.', 'not_yet',
  'SUPPORTED', 'the record carries 2 commencement relation(s), listed in full, and not this')`;
  after, `UNSUPPORTED, 'the record lists s. 1 as commenced'`). It also ignored the new cut marker
  `changes_not_listed`. **`wave4_b7_p324` is the first stored directory in the new shape**, so without
  this the integrator's `negcurrency` on the acceptance replay would have run flattering. It now reads
  both shapes and both markers (`_nc_changed_provisions`).

## 2. Measurement with the built code

The dry run imports the worktree's built code and asserts the import path; the before column is
`6011b4f`'s `search_scope.py`, extracted with `git show` into `$S/old/`.

```
python $S/collect.py                       # every stored delegation that consulted a change record
python $S/rebuild.py new <server_py>       # the product's recorders over each tool's raw_result, in order
python $S/rebuild.py old                   # the same with 6011b4f's search_scope.py
python $S/census.py <server_py> [--list]   # $S/census_final.txt, $S/census_list.txt (ids: gitignored)
```

- **481 run files, 710 delegations that consulted a change record, 1,435 change-record calls** (B's
  1,435), **1,427 instrument lines** (delegation x instrument). Every stored record is in the old
  group shape; none is truncated in the audit; `window_complete` is true on all 1,435; 490 calls hit
  the 40-instrument cap; 41 lack `provisions_commenced` (all `wave3_p35`, before P2.5).
- **Everything in the limb outside the commencement part is byte-identical old vs new: 0 of 710
  differ.**
- **Cases, per instrument line:** `other_full` 253, `other_cut` 165, `self_only` 74, `unlisted` 25,
  `none` 840, `by` 70.
- **Before -> after, per instrument line:**

  | before (6011b4f) | after | n |
  |---|---|---|
  | "WERE retrieved" | `other_full` | 218 |
  | "WERE retrieved" | `other_cut` | 165 |
  | "WERE retrieved" | `self_only` | 73 |
  | "WERE retrieved" | `by` | 52 |
  | "WERE retrieved" | `unlisted` | 25 |
  | "WERE retrieved" | `none` (its `by` record had the commencements; the line now carries that as "also consulted") | 1 |
  | (no sentence) | `none` | 839 |
  | (no sentence) | `other_full` | 35 |
  | (no sentence) | `by` | 18 |
  | (no sentence) | `self_only` | 1 |

  So **73 instrument lines that told the Manager "Commencement relations WERE retrieved … a
  provision-level statement … is supported" for an instrument whose only commencement relations are
  its own now say the record permits nothing either way** (F3), and 165 that said the same of a cut
  list now permit only the listed provisions. The 36 `(no sentence) -> other_full/self_only` lines
  are all `wave3_p35`, whose stored records predate P2.5's counts (P4.18's row records the same
  limit): the old code read 0, the new derives the count from `effects`. The product writes the
  counts today.
- **Instruments per delegation:** 1: 407, 2: 132, 3: 72, 4: 36, 5: 25, 6: 19, 7: 11, 8: 2, 9: 1,
  10: 3, 11: 1, 14: 1. One delegation exceeds the 12-line cap.
- **Length of the limb** (it rides on every legislation Worker report to the Manager): median 1,160
  -> 1,580 characters, max 1,601 -> 3,661.
- **The acceptance sessions, by stored directory** (counts of instrument lines; `census_list.txt`):
  6410 is `other_full` everywhere from `wave2` on (`wave2` 2, `wave3_p35` 6, `wave4_p37_reach` 2 and
  one `by`, `wave4_p37_reach_pre` 2), so its true negatives stay stateable. 6378 is `self_only` and
  `none` (`wave2` 4 and 3, `wave4_p37_reach` 3 and 2, `wave4_p37_reach_pre` 0 and 1; one run file each, and its other two stored run files consulted no
  change record): this is the
  session where the line changes the Manager's guidance, from "WERE retrieved … supported" to
  "nothing either way from this record".

**Invariant 1, every SUPPORTED claim on the stored answers** (`python $S/supported_check.py
<server_py> --list`, output `$S/supported_check.txt`). For each claim `negcurrency` grades SUPPORTED,
the instruments its verdict rested on (the verdict's own record selection, re-derived) are looked up
in the line the built code writes for every delegation of that turn and of the conversation's
earlier turns. **144 SUPPORTED claims (B's 144): the 50 that rest on commencement (7 `not_yet`, 43
`partial`) are all PERMITTED, each instrument in the `other_full` case; the 94 that rest on a removal
(93 `no_longer`, 1 "remains on the statute book") are outside the line, whose wording speaks only to
commencement, and the repeal and title-marker sentences they rely on are byte-identical. 0 NOT
PERMITTED.**

**Detector screen** (`python $S/screen.py .`, `$S/screen_out.txt`): every case's line (11 variants:
the six cases, `by` with no commencements, `to` and `by` on one instrument, no record, the overflow,
and the closing line) and the prompt sentence, split into sentences as the graders do, against
`NOT_FOUND`, `NEG_ASSERTED`, `NEG_TERMS`, `NEG_LIMITS`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`,
`IN_FORCE_CLAIM`, the three halt detectors, `OPENER_VOCAB`, `_CUR_DISCLOSED`, `ANSWER_FOOTER`,
`NEGATIVE_EXPLAINED`, P3.5's commencement denial, `_currency_asserted`, `negcurrency_claim`,
`derivation_claims` (and its near-misses) and the two product footer strippers: **0 trips.** Two
sentences (the `other_full` permission and the prompt sentence) contain "not recorded as commenced",
the wording the brief prescribes, which is in `negcurrency`'s DROP vocabulary (`not a claim shape`),
never graded as a claim; B's note says this statement about the record is the intended form. My
first two drafts tripped `NEG_ASSERTED`/`NOT_FOUND` ("no provision", "no commencement relation", "no
record consulted") and `negcurrency` ("uncommenced"), each found by this screen; the wording was
changed until none did.

**Graders unchanged on stored data:** `python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay
negcurrency --all --verbose --drops` on the built tree is **byte-identical** to batch 6 B's
`seam/batch6/B/run_final_all.txt` (178 claims in 142 of 1,943 turns, 144 / 32 / 2, 217 drops). Batch
6 A's 16-subcommand exit-1 set over `wave4_p37_reach`, `wave4_p37_reach_pre` and `wave4_b4_post`,
built `replay_report.py` against `6011b4f`'s (`bash $S/grade16.sh`; the base copy was placed beside
the built one for the run and removed): **48 outputs identical**; exit 1 on `wave4_p37_reach
derivations` and `wave4_b4_post commencements` on both sides (pre-existing). No grader imports
`search_scope` or `prompts`.

## 3. Tests and revert proofs

`tests/test_commencement_line.py`, 21 tests on synthetic instruments (`asp/1901/1`, `ssi/1901/3`),
built through the product's slimmer and recorders: the recorder's new fields (split, cut list, the
older stored shape, groups beyond the cap); every case of the line (`other_full`, `other_cut`,
`self_only`, `none` x3: empty record, amendments only, `Commencement Order` only; `unlisted`; no
record consulted; the closing line; `by`; `to` + `by`; one line per instrument and the best call; the
overflow); the line reaching `worker_scope_block`; the prompt sentence in exactly the three prompts
that carry `_IN_FORCE_RULE`, between its `Commencement Order` bullet and the next; and the grader
reading P3.19's shape and cut marker. **Updated:** `test_in_force_status.py::test_the_limb_names_what
_was_retrieved_when_something_was` (asserted P2.5's removed sentence; now asserts the new line) and
`test_search_scope.py::test_footer_trips_no_detector` (extended after its last assertion: every line
variant and the prompt sentence against every detector listed above; nothing removed).

Revert proofs on scratch copies of `server_py` (`python $S/revert_a.py <server_py> 6011b4f`, output
`$S/revert_a_out.txt`; the copies were deleted afterwards, the script rebuilds them):

- control (built code copied): 330 passed over the five affected files.
- **product reverted** (`search_scope.py` and `prompts.py` to `6011b4f`: **234 lines removed**, 211
  and 23, 9 restored): **21 fail** (19 in the new file, the updated limb test, the footer screen).
- **tooling reverted** (`replay_report.py` to `6011b4f`: **28 lines removed**, 3 restored): **2 fail**.
- **nine mutants, one site each** (anchor asserted once in the CRLF-normalised text): recorder field
  removed (12 fail); self counted as another instrument, F3 put back (3); cut markers ignored (4); line
  not appended to the limb (15); direction ignored (2); every case read as `other_full` (10); prompt
  sentence defined but not in the rule (1); grader reads only the old shape (1); grader ignores the
  new cut marker (1).

## 4. For the integrator's hand-read of `wave4_b7_p324` (words to read for)

- **6410** (`other_full` in every stored directory from `wave2` on). Read that the uncommenced
  remainder **is still stated** (Invariant 1): either in the line's form, "not recorded as commenced"
  with the change record cited, or as "not yet in force/commenced" resting on a record listed in full
  (which `negcurrency` grades SUPPORTED). A fail is the remainder dropped, a provision the record lists
  as commenced called uncommenced, or "not yet in force" for a provision while the record's list was
  cut. Watch for the line's own bookkeeping echoed into the answer ("one line per instrument", "this
  step consulted no change record", "what a line does not permit"): the strip removes the block, not an
  echo.
- **6378** (`self_only` and `none`). Read for any provision of those instruments called
  "commenced", "in force", "not yet commenced", "uncommenced" or "remains in force" on the strength of
  the change record. The permitted forms are "the record does not show either way" or P2.5's "in-force
  status was not verified". A removal read from the record is still right: 6378's removal is written
  `omitted`, which the product's count misses (P3.28), so the limb carries no repeal sentence for it,
  and the model's own reading of the `omitted` group is not contradicted by the line.
- **`negcurrency` on `wave4_b7_p324` needs this branch's grader fix** (section 1): merge A before
  grading, and grade with the merged tree.

## 5. Findings beside the build (not acted on)

- **F-A1: the Worker-facing change-record block still carries F3.** `amendment_search_note` ->
  `_relation_currency_limb` tells the Worker, on the tool result itself, "N relation(s) are `coming
  into force` and name a provision of this legislation: those ARE its own commencement and you may
  state them", with N = `provisions_commenced`, self relations included. On a `self_only` record (74
  stored instrument lines; 6378 in 2 of its 5 stored run files, `none` in a third) the Worker is invited to state as commenced
  what the Manager's line now says the record cannot show. The new prompt sentence contradicts that
  block in the Worker's own context. Decision 1.
- **F-A2:** `_currency_footer_clause` names a record as "checked" from `commenced`, self relations
  included (F3 in the lawyer's footer). P4.20's territory; not touched.
- **F-A3:** the `not consulted` and overflow cases forbid stating any commencement, which also covers
  a date the instrument's own text fixes (P2.5's limb already limits currency to what it lists; B's
  grader reads such a date as UNCLEAR, not supported). Decision 3.
- **F-A4:** I wrote three scratch files to the session scratchpad before noticing rule 10, then moved
  them into `$S/moved_from_session_scratchpad/`; in doing so I also moved four of the integrator's
  files there (`dbs.py`, `matter_grep.py`, `review_branch.sh`, `rows/`) and moved them straight back,
  unopened and unchanged (a `mv` keeps them byte for byte). Worth a glance.

## 6. What I did NOT do

No replay and no model call (the acceptance is the integrator's, n=3 on 6410 and 6378, pinned Gemini,
up to $1.31). No change to `_relation_currency_limb`, `amendment_search_note`, the repeal count, any
footer clause, the Manager prompts or the Deep Research synthesis prompt. No edit to FIX_PLAN,
SESSION_LOG, CHANGELOG, CLAUDE.md, TODO, the tracker, a rubric or the pack. Not pushed, not merged.

## 7. Decisions for the user

**Decision 1: the Worker-facing block (F-A1).**
- **(a) Recommended: extend P3.24 now, before its replay ($0, small):** make `_relation_currency_limb`
  count `coming into force` relations by another instrument apart from the instrument's own, so the
  Worker's tool result says what the Manager's line says. Otherwise the replay on 6378 measures a
  Worker told "you may state them" and a Manager told "nothing either way".
- (b) Book it as a new row and run the replay on A's lever as built, so the replay measures exactly
  the decided lever (Invariant 3).
- (c) Leave it: the prompt sentence already qualifies (a) for the Worker.

**Decision 2: the prompt sentence does not point at the line, because the Worker never sees it.**
- **(a) Recommended: accept as built:** the sentence states the rule in the record's own terms
  (`self: false/true`, a cut list), which is what the Worker reads.
- (b) Also add one sentence to the Manager prompts and the Deep Research synthesis prompt, the agents
  that do read the line, pointing at it (new prompt text, its own screen and probe).
- (c) Add a literal pointer to the Worker sentence anyway (it would point at text the Worker never
  receives).

**Decision 3: a commencement date fixed in the instrument's own text, where no change record was
consulted (F-A3).**
- **(a) Recommended: keep as built** (the user's decision: "otherwise neither commenced nor
  uncommenced is stated"), and read for it in the replay's hand-read.
- (b) Add an exception to the closing line: a commencement provision that fixes a calendar date may
  be quoted for that date, never for whether an appointed day has been appointed.

**Decision 4: the 12-instrument cap.**
- **(a) Recommended: keep:** 1 of 710 stored delegations exceeds it, and the overflow line permits
  nothing, which is true of a record it does not describe.
- (b) No cap: every instrument its own line (the 14-instrument delegation's limb would grow by about
  400 characters).

## Scratch

Worktree scratch `docs/prepilot-fixes/evidence/seam/batch7/A/` (gitignored, checked with
`git check-ignore -v`: `.gitignore:113 docs/prepilot-fixes/evidence/seam/`), copied to
`C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch7/A/` with `cp -r`. It holds the
collector and its pickle (`deleg.pkl`), the old-code copy (`old/`), the rebuilt limbs, the census and
its listing (instrument ids: never commit), the supported-claim check, the screen, the grader probe,
`negcurrency_all_after.txt`, `grade16.sh` and its two output directories, `revert_a.py` and its output,
and the splice/reword scripts and block source used to edit `search_scope.py` with CRLF kept.

## 8. Extension: the Worker-facing change-record block (user decision, relayed by the integrator)

**Decided:** Decision 1 (a), extend P3.24 before its replay; Decisions 2, 3 and 4 accepted as built
(the prompt sentence as built; "state neither" kept where no record was consulted; the 12-instrument
cap kept). Built as a new commit, `f758c3a`, on top of `bc82672`.

**What changed.** In `amendment_search_note` -> `_relation_currency_limb` (the block the Worker reads
on every `get_legislation_changes` result), P2.5's sentence "N relation(s) are `coming into force` and
name a provision of this legislation: those ARE its own commencement and you may state them, citing
the instrument against each", which counted the instrument's own `self: true` relations (F3, F-A1
above), is replaced by `_relation_commencement_bits`, built from `_commencement_split`, the same split
the Manager's line uses. The "NO relation here is a `coming into force` relation" branch (Invariant
1's honest failure), the `Commencement Order` and repeal branches and the closing sentence are
byte-identical. The exact new Worker-facing wording, per case (N, X and Y are the counts):

- **made by another instrument** (always first when there are any):
  > X `coming into force` relation(s) were made by another instrument and name a provision of this legislation: you may state each of those provisions as commenced, citing the instrument against it.

  then, if all are listed:
  > They are all listed here, so a provision of this legislation not among them may be called not recorded as commenced, citing this record.

  or, if not:
  > The commencement relations are not all listed here, so a provision not listed may be in the part not shown: do not state whether it has been commenced.
- **the instrument's own** (`self: true`; alone, or after the above on a mixed record):
  > Y `coming into force` relation(s) are marked `self: true`: this legislation's own commencement provision acting on itself, which says how its provisions come into force, not whether they have. Read that provision itself for any date it fixes, and do not state from these relations alone whether a provision has been commenced.
- **a count with no commencement group listed** (the groups cut at the 40-instrument cap):
  > N relation(s) are `coming into force`, but their groups are not listed here, so which provisions they name, and who made them, is not shown: do not state from this record whether a provision has been commenced.
- **direction "by"** (changes this legislation makes to other legislation):
  > N relation(s) are `coming into force`: this legislation commencing provisions of the legislation named against each. You may state those, citing it; they do not show whether this legislation's own provisions have been commenced.

**How it treats an SI.** An SI's self relations are, in practice, its own commencement regulation
("these Regulations come into force on …"), so the SI usually is in force from a fixed day. The
record carries no date and does not say which kind of provision it is, so the wording neither calls
the SI commenced nor uncommenced from the relation. It sends the Worker to the provision itself ("Read
that provision itself for any date it fixes"). For an SI that is where the date is; for an Act's
appointed-day section it is where the Worker learns the provision names a mechanism, not its use. The
same wording serves both, because it describes what the relation is, not what the instrument is. One
consequence to watch in the hand-read: an SI whose record holds only self relations (B's F3: 24 of
the 26 such ids were SIs) now gets no "you may state them" for its own commencement. Its commencement
date remains stateable from its own text, and P2.5's `valid_date` and Status rules are unchanged.
(Decision 3, accepted as built, keeps "state neither" in the Manager's line where no record was
consulted. This Worker wording only ever applies where a record WAS consulted, and it points at the
text.)

**Dry run with the built code over every stored change-record result**
(`python $S/worker_block_dryrun.py <server_py> [--list --examples]`; output
`$S/worker_block_dryrun.txt`, full listing and one before/after example per case in
`$S/worker_block_dryrun_list.txt`, ids gitignored). The product calls `amendment_search_note(args,
raw_result)` on every such result, and so does the script. The before column is `6011b4f`'s
`search_scope.py` (the first commit did not touch this function), loaded beside the built one:

| case | calls | block moved |
|---|---|---|
| by another instrument, all listed | 122 | 122 |
| by another instrument, all listed, plus self | 96 | 96 |
| by another instrument, not all listed | 156 | 156 |
| by another instrument, not all listed, plus self | 9 | 9 |
| self only | 73 | 73 |
| a count, no group listed | 26 | 26 |
| direction "by" | 53 | 53 |
| no `coming into force` relation, empty record, or error | 860 | 0 |
| no count (pre-P2.5 stored shape, `wave3_p35`) | 40 | 0 |
| **total** | **1,435** | **535** |

**In all 535, the block moved only in the replaced sentence:** with the old sentence removed from the
before text and the new sentences removed from the after text, 0 of 535 differ. Nothing else in the
tool result moves: the slimmer (`lex.py`) is untouched, and the block is the only appended text this
function builds. The 73 "self only" calls are the ones where P2.5 told the Worker "those ARE its own
commencement and you may state them" about relations that are the instrument's own commencement
provision; 6378 is among them.

**Detector screen.** Every variant above (by another instrument, all listed and cut; self only; a
count with no group; "by", alone and on an instrument also consulted "to"; mixed) is screened in
`test_footer_trips_no_detector`, against the same detectors as section 2: **0 trips** (`python
$S/screen.py .`, `$S/screen_out2.txt`). The one draft that touched a detector's vocabulary, "Not all
of the commencement relations are listed", was in `negcurrency`'s drop vocabulary. It was reworded to
"The commencement relations are not all listed". The only remaining drop-vocabulary sentence is "may
be called not recorded as commenced", the prescribed form. **No grader re-run was needed:** no grader
imports `search_scope`, and graders read stored answers and results, which this change cannot
rewrite. Text it adds can reach a grader only through a future answer that echoes it, and that is
what the screen covers.

**Tests and revert proofs.** Seven new tests in `tests/test_commencement_line.py`:
- by another instrument (all listed);
- the cut list;
- self relations, for an Act id and an SI id;
- a mixed record;
- a count with no group;
- "by";
- the honest-failure branch kept.

`test_in_force_status.py::test_a_retrieved_commencement_is_still_permitted` asserted the removed
"you may state them"; it now asserts "you may state each of those provisions as commenced" (Invariant
1's suppression check, kept). `test_footer_trips_no_detector` now also screens the seven Worker
variants.

Revert proofs on scratch copies (`python $S/revert_ext.py <server_py> bc82672`,
`$S/revert_ext_out.txt`; copies deleted afterwards):
- control: 337 passed over the five affected files;
- **`search_scope.py` reverted to `bc82672` (73 lines removed, 5 restored): 8 fail.** These are 6 of
  the 7 new tests, the updated permission test and the footer screen. The seventh new test, the
  honest-failure branch, pins unchanged behaviour and passes on the revert by design;
- four single-site mutants:
  - self relations counted as by another instrument: 2 fail;
  - a cut list read as complete: 1;
  - direction ignored: 1;
  - P2.5's sentence put back: 7.

**Full suite on `lexchat_test_a`: 2223 passed** (2216 + 7).

**Still not done:** no replay, no model or external call, no change to the `Commencement Order` or
repeal branches, the closing sentence, the slimmer, the footer clauses or any prompt. F-A2 (the
lawyer footer counting self relations) remains P4.20's.
