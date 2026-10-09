# Batch 13, agent F: P3.28 (removals by effect type), then P3.26 (unknown extent token, "N.I.")

**Session 45, 2026-10-09. Product change, $0, 0 live calls, 0 model calls.**

**Base.** The worktree came up on `main` (`a6b4a76`) with no commits; I ran `git reset --hard 1889abb` (the
integrator HEAD) before anything else. This note is based on `1889abb`. No unexpected commit appeared on the
branch while I worked.

**Commits** (branch `worktree-agent-ad7a5693e9bbe0eb4`): `7a9793a` (the build), `edd1ee1` (tests for the
qualified class's dedupe and cap), `7756fe0` (classifier: two dead exclusions dropped, words before part), and
this note.

**Functions changed** (batch 13's rule): `agent/tools/lex.py`: `_slim_amendment_results` (group creation and the
counts), `_matches_jurisdiction`, `_TERRITORY_ALIASES` (two entries), new constants `_KNOWN_TERRITORY_TOKENS` and
`_FOUR_NATIONS`; removed `_REPEAL_EFFECT_TOKENS` and `_effect_is_repeal`. `utils/search_scope.py`:
`_relation_currency_limb` (its repeal sentence moved out), new `_relation_removal_bits`, `record_currency` (the
`get_legislation_changes` branch), `_currency_limb`, `_currency_footer_clause` (the `sourced` gate only). New
module `utils/removal_effects.py`. Nothing in `executor.py`, `schemas.py`, `prompts.py` or any grader.

**Built shape, where it differs from the brief** (relay this):
1. The slimmer no longer writes `repeal_or_revocation_relations`. It writes three counts,
   `provision_removal_relations` (whole or in part), `words_only_removal_relations` and
   `qualified_removal_relations`, and marks each removal group `removal: provision | provision_in_part |
   words_only | qualified` (plus `qualifier` on a qualified one), only on removal groups, as
   `commences_this_legislation` is only on a `Commencement Order`. Kept beside the new counts, the old key would
   hand the Worker two disagreeing repeal counts in one result. (Decision 4.)
2. **A fifth qualifier**, beyond the decided prospective / temporary / conditional and G's "for specified
   purposes": **"for part of the United Kingdom only"**, an effect carrying a territory code ("repealed (S)",
   "repealed (EW)", "repealed in part (S)"). 6 LEX types, 24 relations; G's rule counted them as whole or part
   removals, which says "no longer in force" of a provision repealed for England and Wales only. (Decision 3.)
3. **Words before part** where an effect names both, and two of G's exclusions ("expiry of", "functions cease")
   dropped: no stored type is affected by either (below).
4. P3.26 also treats the four nations named one by one ("E+W+S+N.I.") as UK-wide, so the UK-wide filter keeps
   it (G's dry run found that filter dropping it). (Decision 6.)
5. The classifier is a shared util (`utils/removal_effects.py`, no agent-package import) so `search_scope` and a
   later P3.33 can reuse it; `search_scope` reads the slimmer's counts and, for a result stored before P3.28
   (`seam_replay --from-raw`), classifies the stored effect histogram instead.

---

## 1. P3.28: what changed and why

The change record counted a relation as a repeal when its effect string held "repeal", "revok" or "revoc", and
both the Worker's block (`_relation_currency_limb`) and the Manager's limb (`_currency_limb`) said of every such
relation that the named provision "is no longer in force". Batch 12 G measured both errors: missed families
("omitted", "removed", "deleted", "ceases to have effect", "rev ...") and over-claims ("words repealed",
"repealed (prosp.)", "power to repeal conferred"). The build classifies each relation by its effect type and
words each class on its own; "no longer in force" is said only of whole or partial provision removals.

**The classifier against G's hand rule** (`vs_g.py`, run from `server_py/`): over G's two vocabularies (2,063
LEX types, 713 feed types), the built classes differ from G's on **6 LEX types (24 relations) and 2 feed types
(15 relations), every one a territorial qualifier** (item 2 above), and on nothing else. Relations by built
class, LEX side: provision 2,753, in part 200, words only 2,365, qualified 121, not a removal 42,617.

## 2. The dry run, with the BUILT code (every stored change record)

`dry.py` runs once with `1889abb`'s tree (`git archive 1889abb server_py/src` into `F/old/`) and once with the
built tree, over **all 70 replay directories** (the brief's 64, plus 6; the counts include every one);
`dry_diff.py` compares them. Command: `python dry.py <tree>/server_py dry_<old|new>.jsonl --expect old|new`,
then `python dry_diff.py`.

- **Calls:** 1,760 stored `get_legislation_changes` calls; 1,415 carry their API rows and were re-slimmed by
  each tree (the other 345 were memo or cache hits). **The count moves on 585 calls**: 0 to a provision removal
  on 153 (138 of them direction "to"), a provision count to 0 on 6 (all "to"), and 62 more stay at 0 provision
  removals but now carry words-only or qualified ones.
- **Distinct records (190 id-direction pairs):** old count summed 2,025; built provision 2,954, words only
  2,365, qualified 121. **86 records move; 24 go from 0 to a provision removal (23 "to", 1 "by"); 2 go from a
  count to 0 (both "to", one words-only, one "power to amend or revoke conferred")**, which are G's 23 and 2.
  Every moving record is listed in the gitignored `dry_diff.txt`.
- **The stored result rebuilds exactly:** for every one of the 1,415 calls, the stored count equals the old
  tree's re-slim, and the new tree's classification of the STORED histogram (the fallback path) equals its
  re-slim. 0 differences of either kind.
- **Worker blocks:** 1,055 of 1,760 move, **only in the removal sentences** (0 move anywhere else, checked by
  stripping the exact old and new sentences: `limbcheck.py`). By shape: old repeal sentence to provision and
  words-only sentences 610; to all three 107; to provision only 49; to words-only only 9 (the over-claim
  removed); no old sentence to provision and words-only 177; to provision only 31 (the false-negative shape);
  to words-only only 72.
- **Manager limbs (per delegation):** 613 of 2,789 move, again only in the removal lines (0 elsewhere, so
  P3.24's commencement lines are untouched): old repeal line to provision and words-only lines 455, to all
  three 91, to provision only 4, to words-only only 7; no old line to provision and words-only 31, to provision
  only 16, to words-only only 9.
- **Lawyer footers (per turn):** 74 of 2,299 move: 22 go from P4.18's "the recorded changes consulted list
  neither a commencement nor a repeal" (false for each: the record removed something) to the sourced branch,
  52 stay sourced with a different instrument list. No wording changed in the footer, only its gate.
- **Re-run after commit `7756fe0`:** `dry_new.jsonl` byte-identical to the first built run (`cmp`), so the
  classifier refinement moves nothing stored.

**The 12 false-negative sentences' inputs** (`dry_fn.txt`, from G's `p328_negs.txt` list of the run-turns where
they fall: 6375 t2, scripted 6406 t1, scripted 6383 t1; 18 run-turns). Every one of the **65 change-record
calls** to the moving instruments in those turns was handed no removal sentence by the old code, and is handed
"N relation(s) remove a provision, wholly or in part ... no longer in force" by the built code (65 of 65); in
every one of the 48 moved Manager limbs of those turns, the provision line names each moving instrument its
delegation consulted (65 of 65 pairs; 0 named by the old line). Whether the Worker and Manager then stop
denying the removal is a model question: the acceptance replay, priced below.

## 3. Graders and recorders that read the count (batch 7 A's lesson)

- `replay_report currency` (`_currency_support`) and `negcurrency` (`negcurrency_evidence`) read
  `repeal_or_revocation_relations` from each stored `raw_result` and fall back to the old token count over the
  `effects` histogram when it is absent. **On the new shape they therefore read exactly the count they read
  before.** `grader_check.py` grades every stored turn with a re-slimmed change record twice, its records
  re-slimmed by the old slimmer and by the built one, everything else equal: **624 turns, 181 claim sentences:
  `_currency_support` differs in 0, `negcurrency_evidence` in 0, `negcurrency_verdict` in 0.** No grader is
  changed and no verdict moves, on stored runs or on a future run with the same retrieval and answer.
- `negcurrency`'s own removal rule (`_nc_is_removal`) is not the product's new one: it counts "words repealed"
  and misses "removed" and "deleted". Not changed (decision 5).
- Stale references to the removed names: a comment in `tools/replay_report.py` (near line 3064, "Wider than the
  product's own `_REPEAL_EFFECT_TOKENS`") and older notes. I left `replay_report.py` alone (B and E edit it).

## 4. Every other code text about the same instrument (batch 8's lesson)

- The CHANGE RECORD header ("you MAY state a relation listed here, citing the instrument named against it"),
  its empty-record sentence, its whole-Act closing, `_relations_limb`, `_commencement_lines` (P3.24), the title
  marker line and `currency_note`: none contradicts the new sentences (0 moved text outside the removal lines).
- **`prompts._IN_FORCE_RULE` (b) contradicts them:** "(b) a repeal or revocation relation from
  `get_legislation_changes` — that named provision is no longer in force." A "words repealed" or "repealed
  (prosp.)" relation is a repeal relation by its own string, so the Worker's standing rule says the provision
  is out of force while the block now says the text is amended, or only with the qualifier. Not changed: the
  file is outside my brief, and a Worker-prompt edit reaches every Worker call (P3.13's lesson) and wants a
  first-round probe and a seam draw, which cost money. Proposed text and its screen in decision 2.
- The DR synthesis's "report ONLY a commencement, repeal or revocation that a step finding attributes to a
  retrieved change record": consistent.

## 5. The wording, every value class (for the user's approval)

Rendered by the built code (`screen.py` writes every combination, one and several, to `screen_out.txt`).

**Worker-facing, in the change-record block** (`_relation_removal_bits`; one sentence per class present, then
the date sentence). With one of each class present, in order:

> 1 relation(s) remove a provision, wholly or in part (their groups are marked `removal: provision` or
> `removal: provision_in_part`): those establish that the named provision, or the part of it removed, is no
> longer in force, and you may state them the same way.
>
> 1 relation(s) remove words or entries only (marked `removal: words_only`): each amends the text of the named
> provision, which stays, so state it as the text amended, never as a provision removed.
>
> 1 relation(s) remove something with a qualification in their effect (marked `removal: qualified`, with a
> `qualifier`: prospective, temporary, conditional, for specified purposes, or for part of the United Kingdom
> only): state each only with its qualification, never as a provision removed outright.
>
> The record gives no date for these removals either.

(The last ends "." instead of " either." where P3.21's hop dated a commencement.) Only removals: the first
sentence and the date sentence. Only words-only: the second and the date sentence. Only qualified: the third and
the date sentence. Mixed: each present class in this order. None: nothing (the old sentence was also absent). Several
relations: the number changes ("7 relation(s) ..."); nothing else does. The `qualifier` values the Worker sees
are `prospective`, `temporary`, `conditional`, `for specified purposes`, `for part of the United Kingdom only`.

Replaced: "N relation(s) are repeals or revocations: those establish that the named provision is no longer in
force, and you may state them the same way. The record gives no date for them either."

**Manager-facing, in the report's scope block** (`_currency_limb`; one line per class present, instruments
listed up to 6 per line):

> Relations removing a provision wholly or in part (repealed, revoked, omitted or ceasing to have effect, for
> example) were retrieved for ssi/1901/3, asp/1901/9 — a statement that those provisions, or the parts
> removed, are no longer in force is supported, again without a date.
>
> Relations removing words or entries only were retrieved for ssi/1901/3, asp/1901/9: each amends the text of
> the provision it names, which stays, so state it as the text amended, never as a provision removed.
>
> Removals with a qualification in their effect (prospective, temporary, conditional, for specified purposes,
> or for part of the United Kingdom only) were retrieved for ssi/1901/3, asp/1901/9: state each only with its
> qualification, never as a provision removed outright.

(One instrument: the list holds one id. "again without a date" becomes "without a date" where dated, as before.)
Replaced: "Repeal or revocation relations were retrieved for X — a statement that those provisions are no longer
in force is supported, again without a date."

**Lawyer-facing:** no new wording. The footer's sourced branch ("what was checked is the recorded changes for
X, which name the instruments involved provision by provision but carry no dates.") now also takes a record
whose only removals are words-only or qualified, and no longer takes one whose only "repeal" is a power
conferred, which gets P4.18's "the recorded changes consulted list neither a commencement nor a repeal".

**Screen** (every detector `test_footer_trips_no_detector` uses, sentence by sentence; `screen.py`, pinned by
`test_the_new_sentences_trip_nothing_the_old_one_did_not`): the words-only, qualified and date sentences trip
**nothing**; the provision sentence (Worker and Manager) trips `negcurrency_claim` as `no_longer` and nothing
else, **exactly as the two sentences it replaces do** (it is the sentence that permits that claim). The footer
branches are P2.5's and P4.18's, unchanged.

## 6. P3.26

`_matches_jurisdiction`: only the tokens that name a territory decide; one that matches admits the row; if every
token is recognised and none matches, the row is excluded (P1.1); **otherwise (no extent, or an unrecognised
token) the unknown rule applies** (id prefix, and `uk_wide` admits no unknown). `"n.i."` and `"n.i"` map to NI;
E+W+S+NI counts as UK.

- **P1.1's scoring unchanged:** every stored `search_legislation` row in all 70 directories (39,448 rows, the
  `baseline` directory among them; 9 distinct extent values, 122 distinct extent-and-id-prefix pairs), under
  each of the five filters, with each tree: **0 verdicts move** (`dry_diff.py`). The live-vocabulary table in
  `test_p326_moves_no_verdict_on_the_live_vocabulary` was checked against `1889abb`'s function
  (`p326_old_table.py`): identical for all 10 values.
- **What moves (inputs no stored run contains, tested on synthetic input):** `["N.I."]` is now kept under a
  Northern Ireland filter (was dropped under all five); `["E+W+S+N.I."]` under Northern Ireland and UK-wide;
  `["E+W+S+NI"]` under UK-wide; an unrecognised value such as `["Atlantis"]` or `["England", "Atlantis"]` is now
  admitted under the four territorial filters (subject to the id prefix) and still refused under UK-wide.

## 7. Tests, revert and mutants

- **Tests:** new `tests/test_removal_effects.py` (79), 7 new test functions (13 cases) in
  `tests/test_jurisdiction_filter.py` (42 to 55); 3,379 + 79 + 13 = 3,471; edited:
  `test_in_force_status.py` (imports `classify_removal` for the two old `_effect_is_repeal` tests; the slimmer
  test reads `provision_removal_relations`), `test_commencement_dates.py` (its repeal fixture now puts
  "repealed" in the effect histogram, as the slimmer does; the date sentence's new words; the limb regex).
- **Full suite on `lexchat_test_f`: 3,471 passed** (`python -m pytest -q`, from `server_py/`).
- **Full revert** (`revert.py`, on the scratch copy): putting `1889abb`'s `lex.py` and `search_scope.py` back
  **removes 171 lines** (72 and 99) and restores 49; with the new module kept, 13 of 79 in
  `test_removal_effects.py`, 10 of 55 in `test_jurisdiction_filter.py`, 1 in `test_in_force_status.py` and 4 in
  `test_commencement_dates.py` fail; removing the module too, both new files fail at import (148 lines).
- **Single-site mutants** (`mutants.py`, on `F/mut/server_py`, control passing before and after, 444 tests):
  **56 of 58 caught.** One per exclusion, family, qualifier, ordering, pattern, count, guard, gate, cap and
  dedupe in the classifier, the slimmer, the Worker block, the log, the limb, the footer gate and P3.26. The two
  survivors are equivalent: `removal_counts`'s non-dict guard (the `except` returns the same zeros), and
  `known = set(tokens & _KNOWN_TERRITORY_TOKENS)` against `set(tokens)` (an unrecognised token is in no accept
  set and not in the four nations). The first run found three untested guards (a non-integer count on a removal
  type; "expiry of" and "functions cease", which no stored type reaches; the words-or-part order): tests were
  added for the first and third, and the two dead alternatives removed (`7756fe0`).

## 8. Price of P3.28's acceptance (not run)

The row's acceptance is deterministic and is met above (decision 1 is the wording). A replay would show whether
the 12 false-negative sentences stop. Stored per-turn cost, pinned Gemini (`price.py`, `turns[].timing`):

| turn | runs | mean | max | n=3 mean | n=3 at max | n=3 at 1.6x max (runaway) |
|---|---|---|---|---|---|---|
| 6375 t1-t2 (the whole session; t2 needs t1) | 30 (6 since 1 Oct) | $1.40 since 1 Oct ($1.28 all) | $1.80 | $4.20 | $5.40 | $8.64 |
| scripted 6406 t1 (a one-turn cut of `p32c_6406`, not yet written; the 4-turn script costs $0.62-1.21) | 3 | $0.18 | $0.22 | $0.54 | $0.66 | $1.06 |
| scripted 6383 t1 (`p310_6383`, one turn, Deep Research) | 3 | $0.59 | $0.69 | $1.77 | $2.07 | $3.31 |
| **all three** | | | | **$6.51** | **$8.13** | **$13.01** |

n=1 each: $2.17 mean, $2.71 at max. All three sessions are classified FAIL, so Invariant 4 asks n=3. Graded by
hand (the sentences denying a removal of the moving instruments) with `replay_report negcurrency` beside it.

## 9. What I did not do

- No replay, seam draw, server, live call or model call. No edit to `prompts.py`, any grader or any doc the
  integrator owns. The one-turn 6406 script is not written (tracked `evidence/scripts/`; integrator's call).
- I did not literally re-run `replay_report currency` over every directory before and after: the grader and the
  stored files are both unchanged, so its output is identical by construction; `grader_check.py` is the check
  that covers the new shape.
- P3.33 (waits for this row) not started; it can call `removal_effects.classify_removal` ("revocation of
  earlier commencing SSI" is already excluded as not the subject).

## 10. Scratch

Worktree `docs/prepilot-fixes/evidence/seam/batch13/F/` (gitignored: `git check-ignore -v` gives
`.gitignore:113`), copied to the main checkout's same path at the end. Scripts: `dry.py`, `dry_diff.py`,
`limbcheck.py`, `grader_check.py`, `screen.py`, `screen_prompt.py`, `vs_g.py`, `p326_old_table.py`,
`mutants.py`, `revert.py`, `price.py`, the three test-edit scripts and the commit messages. Outputs:
`dry_diff.txt` and `dry_fn.txt` (they name instruments and runs: gitignored only), `screen_out.txt`,
`grader_check.txt`, `mutants.txt`, `revert.txt`. Removed before the copy, to save disk, and reproducible: the
two code trees (`git archive 1889abb server_py/src | tar -x -C F/old`; `git archive HEAD server_py/src
server_py/tests server_py/tools server_py/pytest.ini | tar -x -C F/mut`) and the two 7-8 MB dry-run outputs
(`dry.py`, about a minute each).

---

## Decisions for the user

1. **The wording (section 5).**
   (a) **Recommended:** approve as built: the three Worker sentences and three Manager lines, one per class
   present, "no longer in force" only in the provision one. (b) Split whole from part removals in the Worker
   sentence ("N remove a provision; M remove part of one") so a part removal never reads as the provision.
   (c) Shorten the qualified sentence to name only the qualifier the record carries (one more code path).
2. **`_IN_FORCE_RULE` (b) in the Worker prompts contradicts the new block for words-only and qualified
   removals.**
   (a) **Recommended:** replace it with "(b) a removal from `get_legislation_changes` whose group is marked
   `removal: provision` or `removal: provision_in_part` — that named provision, or the part removed, is no
   longer in force. A group marked `removal: words_only` amends the provision's text and does not remove the
   provision; one marked `removal: qualified` may be stated only with its `qualifier`." (screened: trips
   `negcurrency` `no_longer` only, as the current (b) does), after a first-round probe and one `--as-sent` seam
   draw on a 6375 t2 payload (a few cents to about $0.40). (b) Leave the prompt; the per-occurrence block
   is more specific and arrives later in the context. (c) Fold it into P3.33.
3. **Territorial effects ("repealed (S)", "repealed (EW)": 6 types, 24 relations).**
   (a) **Recommended:** keep them qualified ("for part of the United Kingdom only"), so a repeal for England
   and Wales is never stated as the provision out of force. (b) Count them as whole or part removals, as G's
   rule and the decided list had it.
4. **The old count key.**
   (a) **Recommended:** as built: `repeal_or_revocation_relations` no longer written, three counts in its place;
   the graders, which fall back to the old token count over the histogram, read new runs exactly as before.
   (b) Keep the old key, narrowed to provision removals (the graders would then read a different count on new
   runs). (c) Keep it with its old meaning beside the new counts (two disagreeing repeal counts in one result).
5. **`negcurrency`'s own removal rule** (`_nc_is_removal`: counts "words repealed", misses "removed" and
   "deleted").
   (a) **Recommended:** leave it now (0 verdicts move); book aligning it with `classify_removal` for after the
   wording is approved, with its own both-ways read. (b) Align it in this batch.
6. **P3.26's four nations as UK-wide.**
   (a) **Recommended:** keep (no stored row moves; "E+W+S+N.I." is the United Kingdom). (b) Drop it and keep
   P3.26 to the unknown token and "N.I." only.
7. **P3.28's acceptance replay.**
   (a) **Recommended:** none now: the deterministic acceptance is met; replay 6375 at n=3 ($4.20, up to $8.64)
   with the next sweep that touches 6375, graded by hand for the removal denials. (b) All three at n=3: $6.51
   mean, $8.13 at the stored maximum, up to about $13 at the runaway margin (needs a one-turn 6406 script).
   (c) n=1 each: $2.17 mean, $2.71 at the maximum.
