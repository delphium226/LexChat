# Parallel batch 8, agent A2: two fixes from the integrator's sweep ($0, no external call)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 23a16cf` (the integrator's merged head, holding A's and B's
work) and confirmed it with `git merge-base --is-ancestor 23a16cf HEAD`. This note is based on
`23a16cf`.

**Branch** `batch8-A2` (made at `23a16cf`; the worktree's own branch
`worktree-agent-aa937ffeda27eb63f` points at the same head). Three commits:

- `2e48920` fix 1: a paragraph run joined by spaces is read whole (P3.12's parser);
- `4af28fb` fix 2: P3.1's cap says what a complete code-read provision list holds;
- this note.

**Spend.** $0. No model call, no external call of any kind, no server, no replay. Every LEX
response used below is one of batch 7 B's saved live payloads (`evidence/seam/batch7/B/raw/`),
served through an httpx `MockTransport`. The full suite ran with `HTTP_PROXY`/`HTTPS_PROXY` set
to a closed local port, so an accidental outbound call would have failed. Every stored run file
read here ran on the pinned `google/gemini-3.1-pro-preview`; no number comes from
`glm-5.2:cloud`.

**Scratch.** Everything is in the gitignored `docs/prepilot-fixes/evidence/seam/batch8/A2/`
(`git check-ignore -v` gives `.gitignore:113`). Commands below run from that folder with
`PYTHONIOENCODING=utf-8`. Each dry-run script asserts that it imports the tree it was pointed at;
`make_prev_tree.py` builds `prev/server_py` (this worktree with the four product files I touch
restored to `23a16cf`), so "before" and "after" are both BUILT code. To re-run on the merged tree,
copy the scripts and repoint `WT` (or set `DRYRUN_WT`), not the code paths.

**Full suite** on `lexchat_test_a`, outbound HTTP blocked, before the last code commit:
**2482 passed** (the merged head gives 2442; fix 1 adds 18 tests, fix 2 adds 22).
Command: `python -m pytest -q -p no:cacheprovider` from `server_py/` (`pytest_full_fix2.txt`).

---

## 1. Fix 1: the paragraph parser (commit `2e48920`)

### 1.1 What changed, and why

`schedule_units._paragraphs` split a paragraph list only at commas, "&" and "and". The sweep's
Worker wrote a schedule's paragraphs as "paragraphs N N+1 N+2" (spaces only), the parser read N
alone, the route cut one paragraph, and the answer then said, falsely, that the index had not
returned the other two.

- `_PARA_RX` now also takes a further number joined by spaces alone (`_SPACE_PNUM`). It is read
  only as a whole token, so it is never:
  - the start of a longer number, a year or a citation ("1901", "1901/12", "4.5", "10:30");
  - the day of a date ("1 April", "12 March": any month name, abbreviated or not);
  - a count ("14 days", weeks, months, years, hours, minutes, "5 per cent", "5%").
- `_space_run` reads such a run, with a range inside it ("12 13 to 15"), **only while it
  ascends**: a number not above the one before it ends the run. So "paragraph 4 2" reads 4, and
  "paragraph 4 5 6 3" reads 4, 5, 6.
- "Part 2", "Schedule 3" and any word end the run (the alternative needs a digit next).
- The cap (`_MAX_PARAGRAPHS`, 4) is unchanged, and `_expand_range` is the old range code, moved
  into a function so both paths share it.

### 1.2 Measured first

`python survey_para.py` (output `survey_para.txt`, scratch: it prints query fragments): every
stored section-search query, 5,314 calls, has 65 occurrences of a paragraph word followed by a
number, in 30 distinct fragments. The space-only form occurs in 9 calls, all naming the same three
paragraphs on P3.12's turn. Every other form already parsed.

### 1.3 Dry run with the built code (both sides)

- **The parse.** `python parse_diff.py` (`parse_diff.txt`): `named_units` of the built tree
  against the base tree over all 5,314 stored section searches.
  - **9 calls change, all from one paragraph to three.** Nothing other than the paragraph tuple
    moves in any call (asserted: 0).
  - By directory: `wave0_conv` 2, `wave1` 3, `wave2` 2, `wave3_p38_pre` 1, `wave4_b8_sweep` 1.
    With the sweep excluded (`--exclude wave4_b8_sweep`): 5,149 calls, 8 change.
  - By chat mode: conversational 3, research 6. None is a memo hit.
- **The route.** `dryrun_p312.py` (A's script, copied unchanged) on both trees, then
  `python compare_route.py` (`compare_route.txt`).
  - 257 firing calls on both trees, the same outcome counts; **8 blocks change**. The ninth
    changed call has the unit in its results, so the route stays silent there.
  - Each of the 8 goes from one clean paragraph cut (1,130 characters) to three clean cuts
    (4,659 characters, under the 8,000 verbatim threshold), each labelled "Paragraph N of
    Schedule X, cut at its own heading and the next one:".

### 1.4 Tests (`tests/test_schedules.py`)

- the run is read: six queries, including a range inside the run, sub-paragraph brackets, a
  lettered paragraph, and the cap;
- a number after a paragraph that is not one is not read: eleven queries (a year, a citation,
  "Part 2", two dates, a count, "per cent", "%", a decimal, a descending number, a run that stops
  descending);
- the route cuts every paragraph of a run joined by spaces (two clean cuts, nothing between).

**Revert:** restoring `schedule_units.py` to `23a16cf` removes **39 lines**; 8 tests fail.

**Single-site mutants** (`python mutants.py spec_fix1.json`, `mutants_fix1.txt`): six, each
fails 1 to 9 tests.

| Mutant | Fails |
|---|---|
| the space alternative removed from the regex | 8 |
| the run not parsed | 9 |
| no ascending check | 2 |
| no date or count guard | 3 |
| no whole-token guard | 3 |
| a range inside a run not expanded | 1 |

**Met.** Check: the 9 stored calls now parse to three paragraphs and nothing else moves (passes);
the 8 route blocks now cut all three (passes).

---

## 2. Fix 2: the cap's text against a code-known negative (commit `4af28fb`)

### 2.1 What changed, and why

On 6374's guard, the Worker was told in code, correctly, that the index holds no schedule or annex
for the Order (P3.27's none-held line and P3.12's "none of them is a schedule or an annex: the
Schedule is not one of them"). It kept searching the Order, hit P3.1's cap of 3 section-search
rounds, and the cap's text won: "If a provision you need was not among them, your report must say
that it was not retrieved because searching within this instrument was cut short by a limit" in
the refusal, "Provisions this step did not retrieve may still be in it" in the limb.

**Who reads what.** The Worker reads the refusal (its tool result). The Manager and the Deep
Research synthesis read the limb (`worker_scope_block`, appended after the Worker writes). The
lawyer reads the footer. All three are changed, each for its reader.

**The condition.** An instrument whose provision list code has read **in this worker run, in
full**: A's per-run `provision_fetches` holds an outcome with `status` "ok", `complete` true and
at least one row (`schedule_units.provision_list_facts`). Anything else (a list cut short, a
failed list, "held without text", a list not yet read or still in flight in the same round, a list
for another instrument) returns None, and every text is byte-identical to before.

- **`agent_shared`.**
  - `provision_fetch_key(args)` is the one key both the route (which fills the dict) and the cap
    (which reads it) use, so an id and a URL agree. A's route used the same expression inline.
  - `held_provision_list(fetches, args)` gives the facts, fail-soft.
  - At the refusal, `run_worker_tool` passes them to `record_section_budget_stop` and
    `section_stop_message`.
- **`discovery_budget.section_stop_message(..., held=)`.** With facts, the refusal keeps its
  `notice`, `searched: false` and `legislation_id`, gains `provision_list`, and its `instruction`
  is replaced (2.2). Without, the old message, byte for byte (pinned by a literal in the tests).
- **`search_scope`.**
  - `record_section_budget_stop(..., held=)` adds `provisions` and `units` to the stop entry
    only when given (the footer needs them).
  - `_section_budget_limb` gives each such instrument (at most 4) its own sentences. The other
    instruments keep P3.1's text, unchanged, built from their rows only.
  - `_section_budget_footer_clause` keeps P3.1's clause unchanged and adds one sentence per such
    instrument (at most 3).
- **`schedule_units`.** `provision_list_facts`, `provision_list_sentence`, and `_held_clause`,
  which `unit_absent_line` now uses too: the same words (A's dry run re-run on the built tree: 0
  of 257 blocks change against fix 1's tree, `route_fix2_vs_fix1.txt`).

Additive and fail-soft (Invariant 5): every new function returns None or "" on a bad input, and a
broken fact falls back to the old text, never to silence.

### 2.2 The exact wording (every variant)

`<id>` is the instrument as the call spelled it (brackets made round), `<N>` the number of
provisions in the list, `<k>` the refused calls on it, `<limit>` 3. `<held>` is one of:

- `none of them is a schedule or an annex`;
- `its schedules and annexes among them are <names>` (at most 8 names, then `and <M> more`).

**The refusal** (Worker-facing tool result; `notice`, `searched` and `legislation_id` unchanged):

- `provision_list`: `Code has already read the index's complete provision list for <id> in this
  step: the index holds <N> provisions for <id>, and <held>.`
- `instruction`: `Do not call search_legislation_sections for this legislation_id again in this
  step. Work from the provisions your earlier searches of it returned, then write your report. The
  index holds only the <N> provisions in that list for <id>, so this limit kept nothing outside
  that list from you: if your report speaks of a provision outside that list, say what the index
  holds for <id>, and do not put it down to this limit. If a provision you need is in that list
  and your earlier searches did not return it, say that searching within this instrument was cut
  short by a limit before it was reached, and name it. State what the index holds, never that the
  instrument itself lacks a provision.`

**The limb** (Manager- and synthesis-facing, inside the stripped scope block), per instrument:

`Searching within <id> was stopped by this step's limit of <limit> rounds of section searches on
one instrument, and <k> further section search(es) it asked for (was|were) not run. Before that,
code had read the index's complete provision list for <id>: the index holds <N> provisions for
<id>, and <held>. The index holds only those <N> provisions for <id>, so the limit kept nothing
outside that list from this step: if the answer you write speaks of a provision of <id> outside
that list, it must say what the index holds for <id>, and must not put it down to the limit.
Provisions in that list that this step did not retrieve may still bear on the question: if the
answer reports one of them as absent or unretrieved, it MUST also say that searching within the
instrument was stopped by a limit before it finished.`

- With no limit recorded, the first clause reads `stopped by this step's limit on section
  searches on one instrument`.
- With other refused instruments in the same step, P3.1's sentence for them comes first,
  unchanged, and names only them.

**The footer** (lawyer-facing), after P3.1's clause, which is unchanged, per instrument:

` For <id>, the index's complete list of provisions had been read before that cap was reached: the
index holds <N> provisions for <id>, and <held>, so the cap did not cause any provision outside
that list to be missed.`

The footer is pooled over the turn: in the dry run, one stop with no list moved only because
another step of the same turn had one (2.3).

**Checks on the wording (all pass):**

- Every variant (refusal fields, limb and footer sentence, in each `<held>` form, plus the
  no-limit limb: 13 texts) is in `test_footer_trips_no_detector`, against every detector the test
  holds. They are also screened by `python screen_fix2.py` (`screen_fix2.txt`: 15 texts, 0
  failing), which prints each one in full.
- `replay_report.sched_clause_class`, per clause as `sched_unit_clauses` reads it:
  - no new text has a LIMIT or OFFER clause about a schedule or annex;
  - every none-held variant reads INDEX;
  - the inventory variants read "" (they state what is held, not a negative).
- No `[` or `]` in any of them.
- Drafting traps the screen rules out: "not … index" in one sentence (`NEG_BLAMED_INDEX`), "no
  provision" (`NEG_ASSERTED`), "in the index" after a search verb (`NEG_BLAMED_INDEX`'s second
  alternative, which spans sentences), "point", "right" and "exactly" (`OPENER_VOCAB`), and
  "cut short" or "limit" in a clause that names a schedule (`SCHED_LIMIT`).

**What the integrator should read for in the re-run:** on 6374's guard, whether the answer states
"the index holds 3 provisions for the Order, and none of them is a schedule" (or its own words for
that) and no longer puts the Schedule down to a limit; and on any step that hits the cap on an
instrument with schedules, that a listed but unretrieved provision is still put down to the limit.

### 2.3 Dry run with the built code (both trees)

**Count first.** `python count_stops.py` (`count_stops.txt`): **23 stored section-budget stops**
in 8 directories, 8 of them in the sweep. `python peek_stops.py` (`peek_stops.txt`): **5 stops had
a live complete code read of that instrument earlier in the same delegation**, all in the sweep (4
on 6374's Order, 3 provisions; 1 on an SI with 46 provisions and 8 schedules). Before the sweep,
no stored run had A's route.

**The dry run.** `DRYRUN_OUT=fix2_new.json python dryrun_fix2.py`, then the same with
`DRYRUN_WT=prev/server_py DRYRUN_OUT=fix2_prev.json`, then `python compare_fix2.py`
(`compare_fix2.txt`).

- For each stop, the delegation's earlier section searches pass through that tree's own
  `schedule_route_block`, as `run_worker_tool` passes them. Memo hits and refused calls are
  skipped, because the route does not run for them. The provision list comes from B's saved
  lookups, with a 503 where none is saved (18 lookups served).
- At the stop, the tree computes what the product computes: the refusal, the record, the
  delegation's limb and the turn's footer clause.

The results:

- **14 of 23 stops move.**
  - **13 are on an instrument with a complete list,** and in each the refusal, the limb and the
    footer all move: 5 read live in the sweep (above), and 8 where the dry run's route simulation
    read the list in older runs. Those 8 are 3 on P3.12's Act (674 provisions), 4 on P3.2's
    regulation (56 provisions, 16 annexes) and 1 on 6374's Order.
  - **1 moves its footer clause only:** a stop with no list, in a turn where another step had
    one. The footer is per turn; its refusal and limb do not move.
- **9 do not move** (no complete list read in that delegation before the stop).
- **Asserted:** nothing moves on an instrument without a complete code-read list, except that
  pooled footer, and every stop with one moves in all three texts (0 exceptions).
- The script does not model concurrency inside one round (calls run in order).

The texts the sweep's 6374 stop would now carry are in `screen_fix2.txt` (synthetic) and, for
the real instrument, in `fix2_new.json` (scratch).

**On a synthetic run:** `test_a_worker_run_carries_the_list_to_its_block` runs `run_worker_agent`
end to end. The route reads a 3-provision list on the first section search naming "the Schedule";
the fourth round's refusal carries `provision_list`, and the report's block carries the held limb
and not "may still be in it".

### 2.4 Tests (`tests/test_section_budget.py` part 8, and the screen in `test_search_scope.py`)

- Without a complete list, the stop, the limb and the clause are exactly as before: literal
  strings, and four unusable `held` values.
- A complete list is what the stop states (none held and inventory): the old sentence is gone, and
  a listed provision is still the limit's.
- Only a complete list with rows establishes anything: nine outcomes.
- The stop reads the list the route read in this run, through `run_worker_tool`: parametrised so
  that the route gets an id and the cap a URL, and the other way round; one fetch per run; the
  record carries the facts.
- A list cut short, failed, held without text, absent, or for another instrument changes nothing:
  six cases, through `run_worker_tool`.
- The limb states the list for that instrument and keeps P3.1's text for the rest (mixed case),
  with INDEX and never LIMIT.
- The footer adds the sentence. The footer is still one line, stripped whole, and read back by
  `_earlier_footers`.
- End to end through `run_worker_agent`.
- The detector screen, extended.

**Revert:** restoring `agent_shared.py`, `discovery_budget.py` and `search_scope.py` to `23a16cf`
and `schedule_units.py` to `2e48920` removes **251 lines**; 17 tests fail.

**Single-site mutants** (`python mutants.py spec_fix2.json`, `mutants_fix2.txt`): eleven, each
fails 1 to 6 tests.

| Mutant | Fails |
|---|---|
| the refusal never reads the list | 3 |
| the cap's key not canonical | 1 |
| a short list called complete | 2 |
| an empty list establishes something | 1 |
| the stop message ignores `held` | 5 |
| the record drops the facts | 6 |
| the limb's held text unused | 3 |
| the limb keeps the old text for a held instrument | 3 |
| the footer sentence dropped | 1 |
| held schedules said to be none | 2 |
| the route's key not shared | 1 |

Two first survived (the key mutants), because the seam test spelled the instrument the same way at
both ends. I parametrised it over both spellings, and both now fail.

**Met, deterministically.** Check: stops on an instrument with a complete code-read list carry the
list's facts in all three texts, and every other stop is byte-identical (passes, above). Whether
the Worker and the Manager now carry the true negative is the re-run's question.

---

## 3. Found on the way (not fixed): the route's per-run bound is not safe under batching

In the sweep, one Deep Research step (6374, turn 4, step 3) shows **6 code provision-list reads in
one ReAct round**, on 6 instruments, against `MAX_PROVISION_FETCHES` = 5 (`peek_stops.txt`; the
six section searches that made them start within 6 ms of each other).

`schedule_route_block` checks `len(fetches)` and `lid not in fetches` before its `await`, and
writes the dict after it. So concurrent section searches in one round all pass the check:

- the bound can be exceeded by a round's batch;
- the per-run memo can fetch one instrument twice in a round.

It costs only extra LEX calls (never a wrong text), but it is a defect in A's bound. It is not
fixed here: it is outside my two fixes (decision 2).

## 4. What I did NOT do

- No live call to any host, no model call, no replay, no server. Whether the Worker and the
  Manager now carry the true negative is unmeasured: that is the re-run.
- I did not edit FIX_PLAN, SESSION_LOG, CHANGELOG, CLAUDE.md, `replay_report.py`, a rubric or a
  memory file, and I did not push or merge.
- I did not extend fix 2 to P3.27's whole-text none-held line (decision 3), and I did not fix
  section 3.
- `plan_status` and `plan_lint` were not run: nothing they read changed.

## 5. Decisions for the user

1. **Fix 2's wording** (section 2.2; the footer sentence is lawyer-facing).
   1. **(Recommended) Approve as built.** All three readers get the code-established fact, and
      P3.1's limit text stays for listed provisions the step did not reach.
   2. **Approve the refusal and the limb, drop the footer sentence.** The lawyer then sees only
      P3.1's clause, which is true but does not say the list was read in full.
2. **The route's per-run bound under batching** (section 3).
   1. **(Recommended) Fix it in a small commit next session:** reserve the instrument's slot
      before the `await`, so the bound and the memo hold within a round.
   2. **Leave it.** The cost is a few extra LEX calls per batched round, and no text is wrong.
3. **Fix 2 reads only P3.12's provision list.** P3.27's whole-text line on a research Worker's
   `get_legislation_text` read also establishes "no schedule or annex text", but not a provision
   count.
   1. **(Recommended) Leave it, and measure in the re-run.** In the sweep, all 4 stops on 6374's
      Order came after the route had read its list, so fix 2 already covers the case observed.
   2. **Also treat a P3.27 none-held read as established** for the cap's text, with its own
      wording and dry run.
4. **Fix 1 reads a space-only run only while it ascends** ("paragraph 4 2" reads 4).
   1. **(Recommended) Keep it.** It is what stops a stray number or a date joining the run, and no
      stored query lists paragraphs in descending order.
   2. **Accept any order,** relying on the token guards alone.
