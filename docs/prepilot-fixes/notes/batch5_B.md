# Parallel batch 5, agent B: semantic review of open rows, part 1

Session 37, 2026-10-02. Branch `worktree-agent-aee384b2b39be397c`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard dde8b41a8344c388470c538169b769699c0efa7d` before any work.** Everything below is
checked at `dde8b41`; if another session has committed since, the anchors must be re-checked (the
script below does that).

**Spend: $0.** No model call, no API call of any kind, no server, no replay. No product, tool,
rubric or plan file edited; the only commit is this note. Full suite on `lexchat_test_b`:
**2135 passed** (`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_b
python -m pytest -q -p no:cacheprovider`, from `server_py/`).

This note quotes no lawyer's question or answer, no search term and no instrument id or title from
a session. Rubric variants, outputs that print matter text and the amendment script are in the
gitignored scratch (see the end). Commands run from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`, `PYTHONIOENCODING=utf-8`, and
`PYTHONPATH=.` for the scratch scripts; `$S` is the scratch folder.

**The rubrics were snapshotted first** (agent D may change them in parallel): `$S/rubrics/p32.json`
sha1 `7927e64…` and `$S/rubrics/p33.json` sha1 `5e5769a…`, the brief's values. Every grader number
below uses the snapshots.

## 1. One line per row

Checks named in each line; "(code)" means grepped or imported at `dde8b41`, "(evidence)" means
read from the stored replay files or the export.

| Row | Status | Premise at HEAD (what I checked) | Acceptance | Dependencies and overlaps | Proposed |
|---|---|---|---|---|---|
| **P0.4** `[~]` | `[~]` is right only if the re-export is still wanted | Code half present: `TranscriptMessageOut.deep_research`, `_ran_deep_research` (`routers/feedback.py`), the "Message deep research" CSV column (`client/src/pages/admin/sessionFeedbackExport.js`) (code). "Blocked until the FINAL PUSH" is **superseded**: `924d815` is in `v2026.09.1` and `main` (`git merge-base --is-ancestor`). **The flag cannot see the turns it was built for**: it reads the assistant message, and the 15 no-reply turns have none (export: 196 user turns, 15 with no assistant message after them, 2 with a blank one; `$S/p04_noreply.py`). The suggested `messages.research_mode`/`chat_mode` columns are NULL on every pre-pilot message (`9aa6d63`, 2026-09-22) (code) | Achievable but nearly empty: it can only re-confirm the 181 turns that have an assistant message, where the inference already measured perfectly | Same target visit as P0.7, which may reach the 15 through `request_timings` | M12; **B3** |
| **P0.7** `[ ]` | Right; blocked on read access to the target, not on a deploy | `RequestTiming.research_mode` from `9e69e4c` (2026-07-14), `chat_mode` from `05fbc0f` (2026-07-16), both before the pre-pilot; `total_cost_usd` present (code, `git log`). "The two cuts" is stale (three releases) | Achievable as booked | P0.6 (ticked); P0.4 (B3) | M10, M11; **B3** |
| **P3.2** `[ ]` (parked) | Right; parked on the pack, said in the row | `utils/openers.py`, `tools/provision_hints.py`, `seam_replay`, `evidence/scripts/p32_6406.json` exist (code, evidence). `stance` re-run: `wave4_b2_post` `p32_6406` 0 of 3, changes 2, 3, 3; `wave4_b4_post` 0 of 3, changes 1, 5, 1, both as the row records. **The 6345 guard reads differently by command:** `stance` prints FAIL on all three `wave4_b2_post` 6345 reps (its control is absolute: the turn-4 provision must be named) where the row and the hand-read record the guard as holding (it is booked relative: "no worse than its before-column", 0 of 3) | Consistent with its levers; not met; criterion (v) fails on P3.12's shape in each of the five measured columns, which no P3.2 lever addresses | Unstated: the pack (Reading 1, which also settles the control-turn conflict the `wave4_b4_post` hand-read leaves open), **P3.12** (criterion (v)). Ticked rows P4.13, P4.16 depend on it | M13; **B2**, **B4** |
| **P3.3** `[ ]` | Right; cannot be ticked while P3.2 is parked (user decision) | Manager clause (`prompts.py:437`, its example is "on one reading ...") and quick-lookup Worker clause (`:491`); `CASE_LAW_DOCTRINE_SENTENCE` (`utils/search_scope.py:2080`); summariser source rule (`agent/summarisation.py:51`, `:69`) (code). `interpret` re-run on `wave4_b2_post`: 6338 r1 PASS, r2 FAIL t3, r3 FAIL t2, t3; 6370 0 of 3; 6375 2 of 3; "failing: 6" of 9. **The row says "7 of 9 fail by hand" for this column; the hand-read's own counts (1, 0 and 2 pass) make it 6 of 9** (so does SESSION_LOG Session 35; history, not edited). `wave4_b4_post` (6370 only): 0 of 3 by command, 1 of 3 by hand | **Inconsistent with its own lever on 6338 turn 3** (B1). The 6370 criterion asks for readings given as readings, which the same clause produces | Unstated: P3.2 (its acceptance includes P3.2's), the pack (Readings 2 to 4), P3.17 (its 6338 failures are this row's). 6375's `wave4_b2_post` r1 failure is P3.18's shape (ticked; recorded on the row). P3.20 would change the code-emitted line 6375's criterion counts (agent C's row) | M1; **B1**, **B2** |
| **P3.4** `[ ]` | Right; unblocked since P3.1 | No default-jurisdiction rule in any prompt; `_JURISDICTION_EXTENT_NOTES` still names letter codes ("E+W+S+NI") and nothing states that most rows carry no extent (`prompts.py:542-558`) (code). "It does not work" is stale: P1.1 is ticked. 6360 and 6378 ran Conversational with no jurisdiction filter (`replay_set.json`), last replayed n=1 in `wave4_p37_reach` (evidence) | **Does not exercise its second half:** the extent-note correction travels in the filter block, which neither acceptance session sends and no quick-lookup Worker receives (P3.14) | P3.14 (the block's route); P3.3 (a doctrine asserted for a jurisdiction); the carried batch 1 item (the hybrid research Worker's jurisdiction line, unbooked) | M6; **B5** |
| **P3.6** `[ ]` | Right | `_slim_search_results` still drops `description` (`agent/tools/lex.py:9`) (code). **"The only `description` Phase 1 will ever see" no longer holds:** since P3.7, `lookup_legislation` returns `description[:600]` for every instrument a brief names by number (`agent/tools/executor.py:512`) (code). P2.3's 0 of 5,299 not re-run | Achievable; "phase1 summarisation calls unchanged over a replay directory" can be a $0 rebuild (re-slim the stored raw search responses, compare with the threshold), which the builder should say | P3.7 (overlap), P3.21 (the same field for commencement dates), P2.5 | M5 |
| **P3.12** `[ ]` | Right; measure-first stands | `section_search_note` (`utils/search_scope.py:316`), `discovery_budget.section_budget_blocks`, `replay_report depth` exist (code). LEX's provision count not re-probed (no API call) | Achievable as booked (6335 t7, n=3) | **P4.17** (ticked) explains this shape's negative and does not fix it; **P3.2's criterion (v)** fails on this shape; P5.4 (d); `tools/provision_hints.py` | M7; **B4** |
| **P3.14** `[ ]` | Right | Holds: `get_worker_system_prompt` now at `prompts.py:746`, early return at `:755`; built code with `{_year_to: 2026}` puts the block in the research, hybrid and case-law Worker prompts and in none of the three quick-lookup ones (`$S/p314_check.py`). **New:** the harness sends `year_to: 2026` for 6370, 6375 and `p32_6406` (every run file in `wave4_b2_post` and `wave4_b4_post`), so a fix moves the quick-lookup prompt on P3.3's and P3.2's measured sessions | Achievable; needs the drift probe or an inert-bound rule | P3.3, P3.2, P3.17 (prompt under measurement); P3.4 | M3, M4 |
| **P3.17** `[ ]` | Right | PHASE 2c (`_GENERAL_RULE_APPLICATION_PHASE`, `prompts.py:483`, in the quick-lookup Worker only, `:510`; `tests/test_general_rule_application.py`) (code). Still carries "That hedged sequence reading is new", corrected later in the row but not struck | **Inherits B1** (P3.3's 6338 criteria). With the turn-2 and turn-3 readings accepted it is met on stored evidence (B1) | "Depends on: P3.3" is inverted in practice: P3.3 cannot be ticked until this row's criteria pass. The pack (Reading 2 and its supplementary) | M2; **B1**, **B2** |
| **P3.19** `[ ]` | Right | **Confirmed** (code, `lex.py:470-618`): groups keyed on (instrument, effect); `changed_provisions` and `effected_by` built and sorted apart; `effected_by` cut at `_MAX_EFFECTING_PROVISIONS = 6` with no count (the changed list's cut has `changed_provisions_not_listed`). No consumer outside `lex.py` reads either list (the recorders read only counts). **Measured over every stored call** (`$S/p319_scope.py`): see M8 | **Buildable next at $0 as booked**; `tests/test_amendment_relations.py` (55 tests) pins today's shape | Depends on P3.5 (ticked); P3.21 depends on it. In `CACHEABLE_TOOLS`: the cache keys on the slimmed result, so a new shape misses old entries naturally (no version bump needed) | M8 |
| **P3.21** `[ ]` | Right | 0 of 538,565 stored change rows carry a date field (the only date-like key is `ai_explanation_timestamp`); 157 distinct commencing instruments (other than the subject) in the stored change rows, a stored lookup `description` for 1 of them (`$S/p321_premise.py`). `/legislation/lookup` does return `description` (`executor.py:512`) | Achievable; **missing the footer change** its own hop forces (below) | **P2.5/P4.18**: the currency clause, P3.5's clauses and four Worker-facing notes say the records carry no dates; P3.7 (the lookup call exists); P5.4 (c) (alternative source) | M9; **B6** |
| **P5.4** `[ ]` | Right; not blocked (dev machine) | No HTTP call to legislation.gov.uk anywhere in `server_py/src` (code). Its (a) premise (0 of 28 SSIs carry a recital) is P2.3's measurement, not re-run (API) | External, as booked | P2.3 (a), P3.21 (c), P3.12 (d), P5.3 | **B6** |

## 2. The five things the brief requires

### 2.1 P3.3's acceptance against its own lever, and P3.17's inherited criterion

**The conflict is real and is in the code.** The conversational Manager's clause
(`prompts.py:437`) says: what the text does not settle, "give it as a reading ('on one reading
...')". The booked 6338 turn-3 criterion fails "a hedged conclusion that they must be sequential".
Batch 4 D traced every turn-3 hedged sequence reading since the clause to the Manager (4 of 9
answers, all "on one reading", all beside the correct statement). The 6370 criterion, by contrast,
asks for exactly what the clause produces (readings given as readings), so the lever is right for
6370 and fails 6338 turn 3 by design.

**What each option does to the recorded verdicts.** By command: `interpret` over the four stored
6338 directories with three rubrics: the snapshot (`base`), and two scratch variants that exempt a
sentence carrying "on one/another reading" (a narrow pattern) from the turn-3 sequence item
(`b_t3n`), and additionally drop the turn-2 "newer Act as one of two readings" item (`b_t23n`).
Turn 3's required plain statement is still required in both, so a reading passes only beside it.

```
python $S/variants.py    # base; b_t3, b_t23 (generic hedge lexicon); b_t3n, b_t23n (narrow: "on/under one/a/another (possible) reading")
for v in base b_t3n b_t23n; do for d in wave4_p33_pre wave4_p33_post wave4_b1_post wave4_b2_post; do
  python -m tools.replay_report --dir $PREPILOT_EVIDENCE/replay/$d interpret --rubric $S/rubrics/p33_$v.json --session 6338; done; done
```

| 6338, reps passing | `wave4_p33_pre` | `wave4_p33_post` | `wave4_b1_post` | `wave4_b2_post` | P3.3 at `wave4_b2_post` (of 9 failing) |
|---|---|---|---|---|---|
| booked (`base`) | 0 of 3 | 0 of 3 | 0 of 3 | **1 of 3** | 6 |
| turn 3 accepts a reading (`b_t3n`) | 0 of 3 | 0 of 3 | 0 of 3 | **2 of 3** (r2) | 5 |
| turns 2 and 3 accept a reading (`b_t23n`) | 0 of 3 | 0 of 3 | 0 of 3 | **3 of 3** | 4 |

- `wave4_p33_pre`'s six unhedged sequence findings all still fail under `b_t3n` (the unhedged
  conclusion stays wrong). The **generic** hedge lexicon (`INTERP_HEDGE`, variant `b_t3`) also
  exempts one of them, a firm conclusion phrased with "implies"; no verdict moves, but a rubric
  change for this must use the narrow form.
- By the recorded hand-reads: identical. `wave4_b2_post` r2 fails only turn 3's hedged reading;
  r3 fails turn 2's alternative regime offered as one reading and turn 3's hedged reading
  (`handread_wave4_b2_post.md`, the 6338 section). The two earlier hedged readings batch 4 D found
  (`wave4_p33_post` r2, `wave4_b1_post` r1) use "would need to"/"should" forms the rubric does not
  match, and both reps fail on other turns, so no recorded verdict moves under any option.
- `wave4_b4_post` holds no 6338 rep: nothing moves there. Its 6370 verdicts (0 of 3 by command,
  1 of 3 by hand) are untouched by every option.
- **P3.17** (acceptance: P3.3's 6338 criteria, n=3) would be met on stored evidence, at $0, only
  under the turns-2-and-3 variant. **P3.3** stays not met under every option (6370, 6375, P3.2).
- **The pack asks about turn 3 only.** Its supplementary question (after Reading 2) covers the
  sequence reading; nothing in it asks whether turn 2's alternative regime may be offered as one
  reading. Without that, a Yes can only take P3.17 to 2 of 3.

Decision **B1** below.

### 2.2 The lawyer-blocked chain

Proposed sentence (decision **B2** says where it goes):

> **What waits on the lawyer pack (2026-10-02):** P3.2 (Reading 1, which also settles its control
> turn's open conflict), P3.3 (Readings 2 to 4, and P3.2's acceptance, which its own includes) and
> P3.17 (Reading 2 and its supplementary question) cannot be ticked until a lawyer answers
> `evidence/lawyer_pack/confirmation_pack.md` (ready, not sent; sending it is the user's action),
> and P3.2 alone is parked for new levers; nothing else waits on it: levers and measurements for
> P3.3's 6370 and 6375 criteria, the grader gaps, and every other open row (P3.12 and P3.19
> among them) can proceed, and an answer is applied first as a $0 re-grade of the stored columns.

It adds no `|` and two `**` (even). "Readings 2 to 4" makes the confirmation of P3.3's 6370 and
6375 readings a tick condition; P3.3's row says "The readings are to be confirmed by a lawyer" but
does not say it gates the tick. If the user does not want that, the phrase becomes "P3.2's
acceptance, which its own includes".

### 2.3 P3.19

**Premise confirmed** (M8 has the numbers). The defect is not 6338-specific: 64% of the groups the
slimmer emits over every stored change-record call cannot be read for which provision made which
change, and 30% have the effecting list cut with no count, against P3.5's own rule that a cut
list states its window.

**Acceptance buildable as booked, and next, at $0:** unit tests at the slimmer; the dry run
re-slims the 1,216 stored raw responses (`$S/p319_scope.py` already walks them and imports the
built slimmer); the output size before and after is a by-product. Three things for the builder:
- nothing outside `lex.py` reads `changed_provisions` or `effected_by` (the footer recorders read
  only counts: `by_other_legislation`, `provisions_commenced`), so no footer and no `replay_report`
  verdict over stored answers can move; the "no subcommand moves" item is a check, not a risk;
- `tests/test_amendment_relations.py` pins today's shape and will change with it (the revert rule
  still applies to the new tests);
- the local prompt cache keys on the slimmed output, so the new shape simply misses old entries;
  no cache-version bump is needed. (The allowlist comment says a slimmed change record is 1-23KB;
  the stored maximum is 49,050 characters.)

No decision needed.

### 2.4 P3.21 against P2.5/P4.18, and P3.12 against P4.17

**P3.21.** P2.5's currency clause ("nothing above has been checked against a commencement date"),
P3.5's footer clause ("those records carry no dates") and four Worker-facing notes
(`amendment_search_note`, `_relations_limb`, `_relation_currency_limb`, `_currency_limb`: "do not
state a commencement date ... from it") are true today and become false on a turn where P3.21's hop
retrieves a date. P4.18's third branch sits between them. This is P3.20's trap in another place,
and P3.21's row does not say it. The relationship to record (M9): those sentences change in the same
commit as the hop, gated in code on the hop's result, unchanged where the hop ran and found none,
and re-screened against every detector, as P4.18 did. P3.21 also overlaps P3.7 (whose lookup call
already returns `description`, capped at 600 characters) and P5.4 (c) (decision **B6**).

**P3.12 and P4.17.** P4.17 (ticked) explains the negative on a section-search-only turn and makes
nothing reachable; its own row says passing it does not tick P3.12, but P3.12's row does not say so
(M7). The larger relationship is with **P3.2**: its control criterion (v) has failed on P3.12's
shape in all five measured columns (`wave4_p32_pre`, `wave4_p33_post`, `wave4_b1_post`,
`wave4_b2_post`, `wave4_b4_post`, each recorded on P3.2's row as "P3.12's shape"), so P3.12 stands
between P3.2 and its acceptance whatever the lawyer answers (decision **B4**).

### 2.5 P0.4 and P0.7

**P0.4's re-export is no longer worth a row.** Its blocker changed (the code half shipped in
`v2026.09.1`), and its motive does not hold: the per-turn flag is read from the assistant message,
and the 15 turns it was meant for have no assistant message. What is left is a re-confirmation of
181 turns the inference already got right.

**P0.7 is still needed**: it is the only route to the recorded configuration (P0.5 and P0.6 rest on
reads), it needs read access only, and it may also reach the 15 no-reply turns (an errored request
still writes a timing row, per P0.7's row; joined by time, since those turns have no cost to join
on). Decision **B3**.

## 3. Mechanical amendments (M1-M13)

Each anchor occurs exactly once in `FIX_PLAN.md` at `dde8b41`, sits on one line, and the
replacement keeps the line's `|` count and adds an even number of `**` (total +18). Validated and
applied to a scratch copy by `$S/apply_b5_B.py` (bytes, CRLF kept; it asserts each anchor once,
refuses to overwrite its input, and checks line and row counts):

```
python $S/apply_b5_B.py docs/prepilot-fixes/FIX_PLAN.md --write $S/FIX_PLAN.applied.md   # from the repo root
```

Result: all 13 OK; lines 461 to 461; ledger rows 69 to 69; `**` 4479 to 4497. `plan_status` on the
amended copy: 46 of 69 rows, 8 of 14 buckets, unchanged. The JSON the script reads is
`$S/amendments_b5_B.json`; the text below is generated from it. M13 is a reading note on how
`stance`'s 6345 verdict relates to the booked guard; M4, M6, M7, M8, M9 and M12 record checked facts
and relationships, and none changes a status, an acceptance or a `Depends on`.

**M1 (P3.3).** Anchor (occurs once):

```text
NOT MET, 7 of 9 fail by hand (`wave4_b1_post` 6 of 9).**
```

Replacement:

```text
NOT MET, ~~7 of 9~~ 6 of 9 fail by hand (`wave4_b1_post` 6 of 9; corrected at batch 5: 1, 0 and 2 reps pass, and `interpret` prints 6 failing of 9).**
```

**M2 (P3.17).** Anchor (occurs once):

```text
That hedged sequence reading is new: no earlier stored rep offered it.
```

Replacement:

```text
~~That hedged sequence reading is new: no earlier stored rep offered it.~~ (Not new: two earlier reps offered it; corrected below, Session 36.)
```

**M3 (P3.14).** Anchor (occurs once):

```text
(`prompts.py:666`)
```

Replacement:

```text
(~~`prompts.py:666`~~ `prompts.py:746` at `dde8b41`, the early return at `:755`)
```

**M4 (P3.14).** Anchor (occurs once):

```text
**Evidence:** none yet — the measurement above is the first step. **Depends on:** — |
```

Replacement:

```text
**Evidence:** none yet — the measurement above is the first step. **Depends on:** — **Batch 5 B (2026-10-02, $0): the premise holds at `dde8b41`.** With `{_year_to: 2026}` the block reaches the research, hybrid and case-law Workers and none of the three quick-lookup prompts (`get_worker_system_prompt`, built code). **A fix moves the prompts P3.3 and P3.2 are measured on:** the replay harness sends the recorded `year_to: 2026` (`tools/replay.py` `_filters`; every 6370, 6375 and `p32_6406` run file in `wave4_b2_post` and `wave4_b4_post` carries it, while 6338 and 6345 carry no filter), so the block would appear in the quick-lookup Worker prompt on those Conversational turns. An upper bound at or after the current year excludes nothing (`replay_report` `_filters_could_bite` already treats it as inert), so either leave such a bound out of the block or take the Worker drift probe on those sessions (Verification protocol), and do not land the fix between two of P3.3's columns. Related: P3.4 (its extent notes travel in this block). |
```

**M5 (P3.6).** Anchor (occurs once):

```text
whatever this row adds is the only `description` Phase 1 will ever see.
```

Replacement:

```text
~~whatever this row adds is the only `description` Phase 1 will ever see.~~ Superseded by P3.7 (2026-09-24; checked at batch 5 against `agent/tools/executor.py`): `lookup_legislation` returns an instrument's `description`, capped at 600 characters, for every instrument a brief names by number; for an instrument found by search and not named, this row's `description` is still the only one Phase 1 would see. Related: P3.21 (the same field, read for a commencing instrument's date).
```

**M6 (P3.4).** Anchor (occurs once):

```text
the filter is currently the only lever a user has and it does not work.
```

Replacement:

```text
the filter is currently the only lever a user has and ~~it does not work~~ it works since P1.1 (ticked). **Batch 5 B (2026-10-02):** no prompt carries a default-jurisdiction rule and the letter-code extent notes are unchanged (`prompts.py` `_JURISDICTION_EXTENT_NOTES`, `dde8b41`); 6360 and 6378 ran Conversational with no jurisdiction filter (`evidence/replay_set.json`), so the notes reach neither acceptance session (they travel in the filter block, which no quick-lookup Worker receives, P3.14); both were last replayed n=1 in `wave4_p37_reach` (P3.7's reach check), not graded for this row.
```

**M7 (P3.12).** Anchor (occurs once):

```text
**Evidence:** 6335. **Depends on:** P3.1
```

Replacement:

```text
**Evidence:** 6335. **Depends on:** P3.1 **Related (batch 5 B, 2026-10-02):** P4.17 (ticked) puts a line on a section-search-only turn saying a provision missing from the results may still be in the instrument, which explains this shape's negative and does not make the paragraph reachable (P4.17's own row: passing it does not tick this one). P3.2's control criterion (v) has failed on this shape (a sub-unit of a provision LEX holds whole, called not held or not retrievable) in each of its five measured columns (P3.2's row), so this row stands between P3.2 and its acceptance whatever the lawyer answers. P5.4 (d) probes legislation.gov.uk's paragraph-level markup, and `tools/provision_hints.py` already cuts such sub-units in dev tooling (`docs/LEGAL_DATA_SOURCES.md` 2.2), a third candidate lever.
```

**M8 (P3.19).** Anchor (occurs once):

```text
**Evidence:** 6338. **Depends on:** P3.5 |
```

Replacement:

```text
**Evidence:** 6338. **Depends on:** P3.5 **Premise confirmed at `dde8b41` (batch 5 B, $0):** the slimmer still keys its groups on (instrument, effect) and sorts the two lists apart, and its `effected_by` cut at 6 carries no count where the `changed_provisions` cut does (`changed_provisions_not_listed`). Over every stored change-record call (1,216 `/amendment/` responses in 47 directories, the built slimmer re-run on each), 13,523 of the 20,991 groups it emits hold at least two changed and two effecting provisions, so which made which cannot be read, and 6,363 have the effecting list cut silently; 747 calls carry at least one group of the first kind and 436 one of the second; the slimmed output is a median 3,448 characters a call (max 49,050). Buildable next at $0 as booked; `tests/test_amendment_relations.py` pins today's shape and changes with it. |
```

**M9 (P3.21).** Anchor (occurs once):

```text
**Depends on:** P3.5, P3.19 (the same slimmer). Related: P3.6 |
```

Replacement:

```text
**Depends on:** P3.5, P3.19 (the same slimmer). Related: P3.6; P3.7 (`lookup_legislation` already calls `/legislation/lookup` and returns `description` capped at 600 characters, so the hop can reuse that call, once it is checked that the date falls inside the cap); P5.4 (c) (legislation.gov.uk's dated effects, an alternative source for the same date). **The wording this row must change (batch 5 B, checked in `utils/search_scope.py` at `dde8b41`):** P2.5's currency clause says nothing above has been checked against a commencement date; P3.5's footer clause and its Worker-facing notes say the change records carry no dates and forbid stating a commencement date from them (`amendment_search_note`, `_relations_limb`, `_relation_currency_limb`, `_currency_limb`, `_relations_footer_clause`, `_currency_footer_clause`); P4.18's third branch sits between them. On a turn where the hop retrieved a date those sentences become false, so they change in the same commit, gated in code on the hop's result (P3.20's pattern), stay as they are where the hop ran and found none, and are re-screened against every detector (`test_footer_trips_no_detector`, P4.18's method). **Measure-first needs the API:** no stored change row carries a date field (538,565 rows read; the only date-like key is `ai_explanation_timestamp`), and the stored evidence holds a `/legislation/lookup` `description` for 1 of the 157 distinct commencing instruments, other than the Act itself, that its change records name, so the share that state a date has to be read live (read-only, $0). |
```

**M10 (P0.7).** Anchor (occurs once):

```text
The columns date from `9e69e4c` (2026-07-14)
```

Replacement:

```text
~~The columns date from `9e69e4c` (2026-07-14)~~ `research_mode` dates from `9e69e4c` (2026-07-14) and `chat_mode` from `05fbc0f` (2026-07-16)
```

**M11 (P0.7).** Anchor (occurs once):

```text
It can go with the deploy of the two cuts.
```

Replacement:

```text
It can go with the deploy of ~~the two cuts~~ `v2026.09.3`, though it needs only read access to the target, not the deploy.
```

**M12 (P0.4).** Anchor (occurs once):

```text
Two more transcript columns from them would have settled P0.5 and P0.6 without reading any answer.
```

Replacement:

```text
Two more transcript columns from them would have settled P0.5 and P0.6 without reading any answer. **Batch 5 B (2026-10-02, $0): two premises checked.** (1) The FINAL PUSH note above is superseded: the code half (`924d815`) is on `main` since `v2026.09.1`, so the re-export waits on the target running a release, which has not been confirmed. (2) **The flag cannot see the turns it was built for:** it reads `research_plan` on the assistant message (`_ran_deep_research`), and the export's 15 turns with no reply have no assistant message at all (196 user turns in 62 sessions: 15 with none after them, 2 with a blank one), so a re-export can only re-confirm the 181 turns that have one, where the inference already measured perfectly. P0.7's `request_timings` query may reach the 15, joined by time (its row: an errored request still writes its row, with `chat_mode`). The two columns above are NULL on every pre-pilot message (added in `9aa6d63`, 2026-09-22), so they serve the pilot, not this corpus.
```

**M13 (P3.2).** Anchor (occurs once):

```text
Every turn the grader reads as holding no position is hand-read
```

Replacement:

```text
`stance` prints FAIL for every 6345 rep whose turn 4 does not name the provision the before-column checks, an absolute check; the guard is relative, so it is read from the turn-4 marks against the before-column's, not from the rep verdict (batch 5 B: `wave4_b2_post` prints 6345 FAIL 3 of 3 where the row records the guard as holding). Every turn the grader reads as holding no position is hand-read
```

## 4. Decisions for the user (B1-B6)

**B1. P3.3's 6338 turn-3 criterion fails the hedged reading P3.3's own clause asks for; P3.17
inherits it. What now?**
1. **(Recommended) Hold both until the lawyer answers, and pre-register the re-grade now.** Before
   the pack goes, add a second supplementary question for turn 2 (may the newer Act be offered as
   one reading beside the right one?); on Yes, apply option 2 as a narrow-hedge rubric change and
   re-grade the stored columns at $0 (`wave4_b2_post` 6338 to 3 of 3, which meets P3.17); on No,
   take option 3. Nothing moves now.
2. **Re-book now:** a reading flagged "on one reading", beside the plain statement that the Act
   sets no order, passes (turn 3, or turns 2 and 3). By command and by hand, `wave4_b2_post` 6338
   goes from 1 to 2 of 3 (or 3 of 3), and nothing else moves. This relaxes a booked criterion after
   seeing results, which the plan has refused before.
3. **Keep the criterion and sharpen the Manager's clause** (silence on a requirement is reported
   as silence, not filled with a reading). That needs about $0.40 for the drift probe, $1-2 for a
   seam A/B and then an after-column; no recorded verdict moves. It risks 6370, whose criterion
   wants exactly these readings.

**B2. Where does the "what waits on the lawyer pack" sentence (section 2.2) go?**
1. **(Recommended) At the top of the Ledger, plus matching `Depends on` entries:** P3.2 adds "the
   lawyer pack (Reading 1)"; P3.3 adds "P3.2 (its acceptance includes P3.2's), the lawyer pack
   (Readings 2 to 4)"; P3.17 replaces "P3.3" with "P3.3's lever (built); P3.3 in turn cannot be
   ticked until this row's criteria pass; the lawyer pack (Reading 2 and its supplementary)".
2. **At the top of the Ledger only**, with no row edits.
3. **On each of the three rows only**, with nothing at the top.

**B3. P0.4 and P0.7: keep, drop or merge?**
1. **(Recommended) Drop P0.4's re-export and widen P0.7.** Mark P0.4 `[-]` (the code half stays,
   for the pilot) and widen P0.7's acceptance to read the chat mode of the 15 no-reply turns from
   `request_timings`, joined by time, or to list them where the join is ambiguous. P0.7 stays open,
   needing read access only.
2. **Keep P0.4 `[~]`** and do its re-export on the same target visit as P0.7, as a cross-check of
   the 181 answered turns.
3. **Leave both as they are**, with only M10-M12 applied.

**B4. P3.2's control criterion (v) fails on P3.12's shape in every measured column. Record it?**
1. **(Recommended) Make it a dependency.** Add P3.12 to P3.2's `Depends on` (for criterion (v)),
   and add 6406's control turn to P3.12's evidence and acceptance, read from P3.2's after-columns.
   Then the one failure no P3.2 lever touches has an owner when P3.2 un-parks.
2. **Record the relationship only** (M7), with no change to either row's dependency or
   acceptance.
3. **Re-scope criterion (v)** so the not-held claim is graded under P3.12 instead. Not
   recommended: it relaxes a booked criterion after results.

**B5. P3.4's acceptance does not exercise its second half (the extent-note correction). Fix how?**
1. **(Recommended) Add a deterministic item and a before-column.** The deterministic item is a
   prompt test that no extent note names a letter code and that each says most rows carry no
   stated extent. Keep the replay item for the default rule, and measure 6360 and 6378 at HEAD
   first (n=3, Conversational as recorded). Say that the default rule must reach the
   conversational Manager and the quick-lookup Worker, which those sessions use.
2. **Split the extent-note correction into its own row** (Wave 3, deterministic), leaving P3.4 as
   the default-jurisdiction rule.
3. **Leave P3.4 as it is.**

**B6. P3.21's date hop against P5.4 (c), legislation.gov.uk's dated effects: which order?**
1. **(Recommended) Run the probes together, then choose.** Run P5.4 (c)'s probe alongside P3.21's
   measure-first (both read-only, $0, from the dev machine), and choose the date source on the
   numbers before building the hop.
2. **Build P3.21 on LEX regardless.** LEX is already whitelisted on the target and
   legislation.gov.uk is not; P5.4 (c) becomes a later comparison.
3. **Defer P3.21** until P5.4 reports.

## 5. Also found (for the integrator, no decision asked)

- **SESSION_LOG Session 35** says "P3.3 NOT met: 7 of 9 fail by hand" for `wave4_b2_post`; the
  counts beside it make it 6 of 9 (M1 corrects the plan; the log is history, so the correction
  belongs in the Session 37 entry).
- **Batch 4 A's open decision (the turn-3 pattern reads "must" only)** bears on B1. Under B1's
  option 1 with a No, or option 3, the pattern should also match the "should" and "would need
  to" forms, as two recorded reps show. No recorded verdict moves, because both reps fail
  elsewhere. Agent D may already be handling this.
- **6338 and 6345 run with no filter** in every stored directory, while 6370, 6375 and `p32_6406`
  run with `year_to: 2026` (the run files' `filters`). This matters only for P3.14 (M4).
- Agent C's rows touched here: P3.20 changes the code-emitted line P3.3's 6375 criterion counts.
  The research Worker's jurisdiction line (carried from batch 1, unbooked) overlaps P3.4 and P3.3.

## What I did NOT do

- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, any rubric, the pack or any code; the amendments
  are applied only to a scratch copy.
- No API call. Because of that, these were not re-measured: LEX's provision count (P3.12), the
  recital counts (P5.4, P2.3), and the date-bearing share of commencing instruments' descriptions
  (P3.21).
- P3.19 not built (not in this batch).
- No grader changed. The rubric variants live only in scratch and are not proposed as edits (that
  is B1, and agent D's area).
- P3.2's control-turn conflict was not resolved: it is the pack's Reading 1 part (2).

## Scratch

`$S` = `docs/prepilot-fixes/evidence/seam/batch5/B/` in this worktree (gitignored:
`git check-ignore -v` gives `.gitignore:113`), copied with `cp -r` to the main checkout's
`$PREPILOT_EVIDENCE/seam/batch5/B/` (see the reply for whether the copy succeeded). Files:
- `rubrics/` holds the snapshots and the variants (matter patterns: never commit);
- `variants.py`;
- `interpret_*.txt`, `stance_*.txt`, `b1_*.txt` (matter text in `b1_base_p33pre_sentences.txt`);
- `p319_scope.py` and `.out`, `p321_premise.py` and `.out`, `p314_check.py` and `.out`,
  `p04_noreply.py` and `.out`;
- `amendments_b5_B.json`, `apply_b5_B.py`, `m_section.md`, `FIX_PLAN.applied.md`;
- `pytest_full.out`.
