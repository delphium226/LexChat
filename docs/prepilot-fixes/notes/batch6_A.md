# Parallel batch 6, agent A: P3.19 built (which provision made which change)

**Base:** `995ef34` (the integrator's head; Fix Tracker v36). The worktree came up on `main`
(`a6b4a76`) with no commits, as in every earlier batch; I ran `git reset --hard 995ef34` before
anything else. **Spend: $0.** No model call, no server, no replay pin/run/restore, no call to LEX,
the National Archives or legislation.gov.uk: every number below is over stored evidence.
**Model:** none. Every count is a property of the stored `/amendment/` responses and the slimmer,
not of a model; the stored responses were recorded on the pinned Gemini replays.

Scratch (gitignored): `docs/prepilot-fixes/evidence/seam/batch6/A/` in the worktree, copied to the
same path in the main checkout. Every command below runs from `server_py/` with
`PYTHONPATH=. PYTHONIOENCODING=utf-8`, and `$A` is `../docs/prepilot-fixes/evidence/seam/batch6/A`.

## 1. What changed, and why

`_slim_amendment_results` (`server_py/src/agent/tools/lex.py`) kept each (instrument, effect)
group's `changed_provisions` and `effected_by` as two lists sorted apart, and cut `effected_by` at
`_MAX_EFFECTING_PROVISIONS = 6` with no count. A group with two or more of each could not say which
provision made which change. The row's case: the inserting Act's `inserted` group of 16 relations
listed 6 effecting provisions, and the one that made the insertion asked about was not among them.

**The new shape.** Each group carries `changes`, one entry per effecting provision, its changed
provisions in natural order; `changed_provisions` and `effected_by` are gone. Synthetic example
(the built code, before and after, on four rows):

```
before: count 4, changed_provisions ['s. 2A', 's. 7B', 's. 9ZA'],
        effected_by ['s. 4(3)', 's. 4(5)', 's. 6(2)', 'sch. 1 para. 3']
after:  count 4, changes [{'by': 's. 4(3)', 'changed': ['s. 2A']},
                          {'by': 's. 4(5)', 'changed': ['s. 7B']},
                          {'by': 's. 6(2)', 'changed': ['s. 9ZA']},
                          {'by': 'sch. 1 para. 3', 'changed': ['s. 9ZA']}]
```

- **The window is unchanged in its unit:** the first `_MAX_CHANGED_PROVISIONS` (60) *named*
  changed provisions in provision order, each now listed with **every** provision that changed it.
  So nothing the old output showed is hidden (checked: 0 of 183,426 changed-provision labels).
- **A cut list states its window:** `changes_not_listed` counts the relations a group leaves out
  (P3.5's rule; the old `changed_provisions_not_listed` is replaced by it).
- **A backstop**, `_MAX_CHANGES_LISTED = 120` relations per group, never reached in the stored
  corpus (its maximum inside the window is 92; one changed provision is changed by at most 20
  provisions). It is counted in `changes_not_listed` like the window.
- **An empty side is `null`, not dropped:** the old lists skipped a missing changed or effecting
  provision (113 and 48 relations in the stored corpus), so those relations appeared in `count` but
  in neither list. A null changed provision takes no window slot (as it took none before).
- Every other key of the output (counts, `effects`, `self`, the P2.5 fields, `related` order and
  its cap of 40) is byte-identical before and after (checked: 0 of 1,216 calls differ outside the
  per-group lists).
- **Consumers checked:** nothing outside `lex.py` reads `changed_provisions` or `effected_by`
  (grep over `server_py/src`, `server_py/tools`, `server_py/tests`): `agent_shared._extract_sources_inner`
  (the loop at `agent_shared.py:191`), `search_scope.record_relations` (`:790`) and
  `replay_report._consulted_changes` (`:1898`) read only a group's `legislation_id`, `self`, `url`
  and `type_of_effect`; the footer recorders read only top-level counts.
- Also edited: the comment over `CACHEABLE_TOOLS` in `services/local_prompt_cache.py`, which said a
  slimmed change record is 1-23 KB (it was already 49 KB before this change; now up to ~97 KB), and
  now records why no cache-version bump was made (section 6).

**How the shape was chosen (measure first, prototypes only, `$A/proto_shapes.py`):** four paired
shapes priced over every stored call against the built slimmer (total characters, all 1,216 calls):
one object per relation `{"changed", "by"}` x1.55; grouped by changed provision x1.55; grouped by
effecting provision x1.42; two-element arrays x1.22. I took grouping by effecting provision: the
cheapest self-describing form, and the way a commencement reads ("reg. 2 commenced ss. 2, 10 and
21" is one entry); arrays are cheaper but leave the model to remember which element is which.

**Two of my own intermediate builds were wrong, and the dry run caught both:** the first windowed
on 60 *relations*, which hid 1,420 changed-provision labels the old output showed (258 groups, 139
calls); the second windowed on changed provisions but let a null changed provision take a slot,
which hid 18 (18 groups, 9 calls). The built version hides 0. Both are pinned as mutants (section
3a).

## 2. Measure first: the premise, re-run before the build

`python $A/p319_scope.py` (batch 5 B's `p319_scope.py`, copied and repointed: its import assertion
now requires this worktree's `lex.py`; nothing else changed), on the code at `995ef34`:

```
/amendment/ calls with a list response: 1216 in 47 directories
groups: 20991; pairing lost (>=2 changed and >=2 effecting): 13523; effecting list cut at the cap of 6, silently: 6363
calls with at least one pairing-lost group: 747; with a silent cut: 436
slimmed output chars per call: median 3448, max 49050, min 428
```

Batch 5 B's numbers reproduce exactly. **One correction to the row's count:** the slimmer emits
**21,033** groups over those calls, not 20,991. B's script creates a group only when a row has a
changed or an effecting provision, so the 42 emitted groups whose rows name neither are missing
from its denominator (checked by counting `len(related)` over every call's built output, and the 42
groups with both old lists empty). The 13,523 and 6,363 stand. After the build the same script
(`$A/p319_scope_after.py`, the removed constant replaced by the literal 6, because its premise
counts are computed from the raw rows) prints the same premise counts and `median 3462, max 96861`.

## 3. Acceptance (the row's, deterministic, n=1)

### 3a. Unit tests at the slimmer, each failing with the change reverted: MET

`server_py/tests/test_amendment_relations.py`: **9 new tests** and **4 existing tests updated**
(they pinned `changed_provisions` / `effected_by` / `changed_provisions_not_listed`; their inputs are
unchanged and only the assertions moved to the new keys). The new tests use synthetic ids only
(`asp/1901/1`, `ssi/1901/3`, `ssi/1901/4`):

1. `test_every_relation_keeps_its_own_effecting_provision`
2. `test_an_effecting_provision_past_the_old_sixth_is_still_listed_with_its_change` (the row's
   shape: 16 relations, the two sides in opposite orders, the target made by the provision that
   sorts last)
3. `test_a_cut_list_of_changes_states_its_window`
4. `test_the_window_is_on_changed_provisions_and_each_keeps_every_provision_that_changed_it`
5. `test_a_change_with_no_named_provision_takes_no_slot_in_the_window`
6. `test_the_backstop_on_relations_listed_is_stated_too`
7. `test_one_provision_making_many_changes_is_one_entry`
8. `test_a_provision_the_record_does_not_name_is_null_not_dropped`
9. `test_every_deduplicated_row_is_listed_with_its_pair_or_counted` (the dry run's check, at the
   slimmer, on 158 synthetic rows with http/https twins across four groups)

**Full revert** (`python $A/make_revert.py`, run from the worktree root: a scratch copy of
`server_py` with `lex.py` restored to `995ef34`'s, plus one alias line so a test naming
`_MAX_CHANGES_LISTED` fails on its assertion, not on an AttributeError). **The revert removed 69
lines of the built `lex.py` and restored 20 (19 original lines and the alias).** Result over
`test_amendment_relations.py` and `test_in_force_status.py`: **13 failed, 197 passed**: all 9 new
tests and the 4 updated ones; every other test passes on both sides. (`$A/revert_result.txt`.)

Because a full revert fails the new tests on `KeyError: 'changes'`, which proves only the key,
**each half of the old defect was also put back inside the new shape**, one mutant at a time on the
scratch copy (`python $A/mutants.py`, each anchor asserted once; `$A/mutants_result.txt`):

| mutant (lines removed / added) | what it re-creates | new tests failing |
|---|---|---|
| `pairing_lost` (3 / 6) | the two sides sorted apart and re-zipped | 1, 2, 4, 5, 6, 8, 9 |
| `effecting_cut_at_6` (3 / 5) | the effecting side cut at six, silently | 2, 3, 4, 5, 6, 9 |
| `window_not_stated` (1 / 1) | the cut made but not counted | 3, 4, 5, 6 (and the updated cap test) |
| `window_on_relations` (1 / 1) | my first build's window | 4, 5, 6 |
| `no_backstop` (1 / 1) | no per-group backstop | 6 |
| `null_takes_a_slot` (1 / 1) | my second build's window | 5 |
| `empty_side_dropped` (1 / 1) | an empty side skipped, as the old lists did | 5, 8 |

Test 7 (one effecting provision, one entry) fails only under the full revert: it pins the grouping,
which no mutant above changes.

**Full suite** on `lexchat_test_a`: **2171 passed** (2162 at the base, plus the 9 new tests).

### 3b. Dry run over every stored change-record result, with the BUILT code: MET

`python $A/collect.py` (once: pickles every stored `get_legislation_changes` `/amendment/` list
response, 1,216 calls in 47 directories, 1,145 of them the last call of their tool record, i.e. the
one the slimmer ran on in production; the other 71 are the first call of an escalation), then
`python $A/dryrun.py`, which imports the built slimmer (asserting this worktree's file and the new
constant) and `995ef34`'s (`$A/lex_995ef34.py`, `git show`, unmodified), and checks every
relation, deduplicated exactly as the slimmer deduplicates, in every group the slimmer emits:

- **239,021 relations** in **21,033 groups**: **195,884 listed, each with the affecting provision
  its own API row names**, and **43,137 counted in `changes_not_listed`** (422 groups, 189 calls);
  listed + counted equals the group's relations in every group;
- **0** listed pairs that are not an API row's pair; **0** pairs listed twice; **0** groups where
  listed + counted differs from the relations; **0** calls whose output differs outside the
  per-group lists;
- **before**, a reader could attach an effecting provision to its change for **21,252** of those
  relations (a group with one changed or one effecting provision, the provision visible in the old
  lists); the other 217,769 sat in a group that could not be read for the pairing (13,523 groups)
  or behind the silent cut (6,363 groups);
- changed-provision labels visible: **183,426 before, 183,426 after, 0 hidden**; effecting-provision
  labels visible: **69,225 before, 147,051 after**;
- **what moves:** the slimmed output of **917 of the 1,216 calls** (846 of the 1,145 production
  tool results); the other 299 are empty change records, byte-identical. Every moved output was
  checked by the program above rather than read by hand (no output is answer text; section 3c covers
  what a grader reads).

**The row's own case** (`python $A/case6338.py`): the 8 stored 6338 change-record calls in 4
directories each carry the 16-relation `inserted` group. Before, the inserting provision the API
rows name was among the 6 listed effecting provisions in **0 of 8**; after, it is paired with the
section in **8 of 8**, all 16 relations listed, none cut.

### 3c. No `replay_report` subcommand moves that is not listed and read: MET (nothing moves)

`bash $A/grade.sh before` and `bash $A/grade.sh after`: the 16-subcommand exit-1 set (`halts
negatives derivations commencements currency scoperecord nosearch caselaw modes deadend siblings
scripted lookup drgaps blanks "lost --require-label"`) over `wave4_b4_post`, `wave4_b2_post` and
every directory holding 6338 or 6409 (`baseline wave0_conv wave1 wave2 wave4_b1_post
wave4_p33_post wave4_p33_pre wave2_p22 wave2_p22_final wave2_p25 wave2_p28 wave2_p28_smoke
wave3_p35`): 240 runs a side. `diff -r grade_before grade_after`: **identical, every output and
every exit code**; 169 exit 0 and 71 exit 1 on both sides (the older directories' pre-fix shapes,
and `commencements` on `wave4_b4_post` and `wave4_b2_post`, as recorded in Session 35/36). This was
expected and is now checked: `replay_report` reads stored `raw_result` and never imports `lex.py`
(its only product imports are `search_scope`, `citation_links`, `research_halt`,
`section_outline`, `instrument_lookup`, `openers`, and `executor` under `lookup --live`, which was
not run). The "before" side ran partly while I was editing `lex.py`; since no subcommand imports it,
that cannot have changed its output, and the byte-identical diff agrees.

## 4. Output size, before and after (`python $A/dryrun.py`, `python $A/proto_bounds2.py`)

| | median | p90 | p99 | max | calls > 52,428 | calls > 81,920 |
|---|---|---|---|---|---|---|
| every stored call, before | 3,448 | 25,727 | 37,229 | 49,050 | 0 | 0 |
| every stored call, after | 3,462 | 45,397 | 56,645 | 96,861 | 23 | 11 |
| production calls (1,145), before | 1,744 | 20,270 | 40,346 | 49,050 | 0 | 0 |
| production calls (1,145), after | 1,723 | 32,353 | 60,327 | 96,861 | 12 | 11 |

Per call, after over before: median x1.000, p90 x1.67, max x2.18. Total characters x1.43.
**The median does not grow; the long tail roughly doubles**, because the six-item cut no longer
hides the effecting side. 52,428 and 81,920 are `get_summarise_threshold()` for a 128K-token and a
200K-token model (10% of 4 characters a token); on the pinned Gemini (1M tokens) the threshold is
200,000 and no change record crosses it, but a 97K result uses 39% of a Worker's 250K context
budget, so later results in that run are summarised sooner. On a 128K model (the listed
`glm-5.1:cloud`; Thomas tests on `glm-5.2:cloud`, which `MODEL_LIST` does not list) 12 production
change records would now be summarised where none were, and summarisation is the stage that
mis-paired the 6338 insertion (it now has the pair in its input). Decision 1 offers a bound.

## 5. What the Worker prompts say about the shape (for the integrator)

Nothing in a prompt names `changed_provisions`, `effected_by` or the six-item cut, so **no wording
is false after this change**. Four places describe the output in general terms and do not mention
that each change now carries its effecting provision:

- `server_py/src/agent/tools/schemas.py:193-194` (the tool description): "Returns relations grouped
  by the other instrument, each with the provisions affected."
- `server_py/src/prompts.py:280` (`WORKER_SYSTEM_PROMPT`, the research Worker's tool list; the
  hybrid and quick-lookup Workers route to the tool without describing its output): "Returns the instruments involved and the
  provisions affected, grouped — but no dates, and no enabling power."
- `server_py/src/prompts.py:209`, `_IN_FORCE_RULE` (a): "that named provision was commenced by that
  named instrument" (still true; it could now cite the provision).
- `_RELATIONSHIP_RULE` (`prompts.py:165-170`) and `amendment_search_note`
  (`utils/search_scope.py:670-765`): nothing on the shape; the note's truncation sentence is about
  `window_complete` (the fetch), not about `changes_not_listed` (a group's window).

None was changed: each is model-facing text in every Worker payload, and changing it is a prompt
change with its own drift probe (decision 2).

## 6. The local prompt cache: no version bump needed (checked)

`get_legislation_changes` is in `CACHEABLE_TOOLS` (`services/local_prompt_cache.py:62`). The key is
`(content_hash, query_hash)`, and `content_hash` is the sha256 of `result` at the summarisation
seam (`agent_shared.py:1103`), which is the executor's own output (`raw_result = result`,
`agent_shared.py:742`, unmodified between there and the hash; the scope notes are appended later,
at `:1208`). The executor returns `json.dumps(slimmed)` with `window_complete` stamped
(`executor.py:418-428`). So a new shape hashes differently and misses every old row; nothing old is
served. `_CANON_VERSION` covers the query canonicalisation and the summariser's prompt, neither of
which changed. Batch 5 B's reading holds.

## 7. What I did NOT do

- No prompt, tool-description or scope-note wording changed (section 5; decision 2).
- No per-call bound built (decision 1).
- Nothing of P3.21 (the commencement-date hop on the same slimmer).
- No replay, no seam draw, no live call; nothing re-read from the API.
- No edit to FIX_PLAN.md, SESSION_LOG.md, CHANGELOG.md, CLAUDE.md, docs/TODO.md, the tracker, a
  batch brief, a rubric, the lawyer pack or a memory file. The row's count correction (section 2)
  and the tick are the integrator's to fold.
- `lex_probe` (it calls the API) and the `external-apis` skill were not touched; the skill's
  `/amendment/search` traps are unchanged by this row.

## 8. Decisions for the user

1. **Bound the long tail of the change-record output?** The median is unchanged; the p90 grows from
   25.7K to 45.4K characters and the maximum from 49K to 97K, and 12 production calls would now
   cross a 128K-token model's summarisation threshold (0 before).
   - **(a) Accept as built (recommended).** Every relation listed with its own pair and nothing the
     old output showed hidden; on the pinned model no change record is summarised. Measure the
     summarised share on the next after-column and on Thomas's model before bounding.
   - (b) A per-call budget of 600 listed relations shared across groups in output order (prototype,
     `$A/proto_bounds2.py`): max 55.6K, 1 call over 52,428; but **20,676 changed-provision labels the
     old output showed would be hidden, in 140 calls** (counted, not lost).
   - (c) A per-call budget of 400: max 44.7K, none over 52,428; 51,863 labels hidden in 218 calls.
   - (d) A budget of 800: max 63.6K, still 13 over 52,428; 6,639 labels hidden in 22 calls.

2. **Say in the Worker-facing wording that each change carries its effecting provision?**
   - **(a) Leave the wording as it is (recommended).** Nothing in it is false (section 5); the data
     now carries the pair, and the model and the summariser read the data.
   - (b) Add "and the provision that made each change" to the tool description and `prompts.py:280`,
     with a Worker first-round drift probe (about $0.40 at batch 2's price) before merge.
   - (c) As (b), and add a sentence to `amendment_search_note` when a group carries
     `changes_not_listed`. The note is Worker-facing, but a Worker can echo it into a report, so
     the sentence would be screened against every detector (`test_footer_trips_no_detector`'s
     method) before merge.

3. **Tick P3.19 at merge?** All three booked acceptance items pass at n=1 (sections 3a-3c).
   - **(a) Tick at merge (recommended)**, as P4.18 was: the acceptance is deterministic and booked
     that way.
   - (b) Hold the tick for an after-column showing the 6338 turn-2 pinpoint right in summaries,
     reports and answers; that is not the booked acceptance and costs a replay.

**For the integrator (no decision):** the row's "13,523 of the 20,991 groups" should read 21,033
groups (section 2); `tests/test_amendment_relations.py` now pins the paired shape; P3.21 builds on
this slimmer and should read `changes`, not the removed lists.
