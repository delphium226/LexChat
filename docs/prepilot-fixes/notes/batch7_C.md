# Parallel batch 7, agent C: P3.25 built ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 6011b4fe0ba669cd68e225ac349c35f70f5fc724` (the integrator's
head). Everything below is based on `6011b4f`; another session may have committed since.

**What this is.** The decided build for P3.25 (user, 2026-10-05): the conversational (quick-lookup)
Worker is no longer offered `get_legislation_text`, in code, and the two things only that tool
supplied, an SI's own recital (P2.3's permitted branch) and `valid_date` (P2.5's (d)), now come
through `lookup_legislation`. Spend **$0**: no model call, no server, no replay, and **no external
call of any kind** (every lookup below is rebuilt from stored LEX responses, with httpx stubbed).
Every number comes from the 57 stored replay directories, all on the pinned
`google/gemini-3.1-pro-preview`; none comes from `glm-5.2:cloud`.

**Commits** (branch `worktree-agent-a269cb7e55f93841e`): `ece80d1` (product, tooling, tests,
`AUDIT_TRACE.md`) and the commit adding this note.

**Scratch.** `docs/prepilot-fixes/evidence/seam/batch7/C/` (gitignored: `git check-ignore -v`
gives `.gitignore:113`), copied with `cp -r` to the main checkout's same path. Commands below run
from the repo root with `PYTHONIOENCODING=utf-8`, `S=docs/prepilot-fixes/evidence/seam/batch7/C`,
`E=$PREPILOT_EVIDENCE/replay`. `$S/head/server_py` is `git archive 6011b4f server_py/src
server_py/tools` (the before side). Scripts that import `server_py` from their own location
(`p325_identity.py`, `p325_fields.py`) read the main checkout's code when run from there, i.e. the
merged tree; the others take the code path as an argument.

---

## 1. What changed, and why

**(1) The tool list depends on the chat mode** (`schemas.py`). `get_worker_tools(research_mode,
chat_mode=None)` drops `QUICK_LOOKUP_WITHHELD_TOOLS = ("get_legislation_text",)` where
`is_quick_lookup_worker(research_mode, chat_mode)` holds: chat mode `conversational` and a research
type other than the two parliamentary ones. That is exactly the test `get_worker_system_prompt`
applies to choose `WORKER_SYSTEM_PROMPT_CONVERSATIONAL`, so the narrowed list and that prompt always
go together (a test checks the two agree over 6 research types x 5 chat modes). `run_worker_agent`
passes `cfg["_chat_mode"]`. In the quick-lookup Worker's executor, a call to the withheld tool made
anyway (its name survives in one shared tool description, decision 3) is answered in code with
`withheld_tool_result` (`{"tool", "run": false, "note"}`, no `results` key) and never reaches LEX.

**(2) The lookup passes on `valid_date`, and the recorders read the lookup** (`executor.py`,
`search_scope.py`, `agent_shared.py`).
- The lookup result gains `valid_date` (from LEX's `/legislation/lookup` record).
- **The 600-character `description` cap is kept, checked:** of the 8 stored text records carrying a
  recital, 7 carry it in `description` (D's figure), and **each of those 7 descriptions is 600
  characters or fewer in whole**, the recital starting before character 600 in all 7; the eighth has
  it only in `full_text`, which no lookup returns. Over the 14 instruments with a stored LEX lookup
  payload, the longest description is 686 characters (median 289); none carries a recital.
  `python $S/p325_fields.py $E`.
- `valid_date` on the lookup record equals the text record's in **9 of 9** stored pairs (10 pairs;
  in the tenth neither has one), and `description` is identical in **10 of 10**. It is present on 11
  of 11 `revised` records and 0 of 3 `final` ones, and never equals the enactment date. Same command.
- `record_currency` gains a `lookup_legislation` branch: a `valid_date` row (tagged `via:
  lookup_legislation`) for a **held** record only (a stub has no held text for the date to describe).
  It is a new branch beside `get_legislation_text`'s; agent A's `get_legislation_changes` branch and
  `_currency_limb` are untouched.
- `record_enabling_power` gains a lookup branch that records **only the permitting row** (`stated:
  True`, for a secondary instrument whose description carries a recital). A lookup is not a read of
  the instrument, so a lookup with no recital records nothing; the section search, which is the
  read, already records the instrument as looked at. Kept, a not-stated row would have added P2.3's
  lawyer clause to turns that only looked an SI up.
- `lookup_enabling_note` builds the permitting `[ENABLING POWER …]` block from a lookup, naming its
  source as "the index record lookup_legislation returned for <id>" (because it can arrive appended
  to a section search, where "this record" would read as the ranked sections). The block for a whole
  text is factored into `_enabling_stated_block` and is **byte-identical** to P2.3's (pinned by a
  test). `run_worker_tool` appends it to a lookup's result when there is a recital, and records the
  lookup's currency (the name gate at the recorder call gains `LOOKUP_TOOL`).
- `parse_lookup_result` now uses `raw_decode`, because a lookup's result can carry that block and
  `routed_lookup_block` (P3.7) parses the result as returned: with `json.loads` the instrument would
  silently drop out of the brief block (a mutant shows it).

**(3) A code lookup for an SI the quick-lookup Worker section-searches** (`instrument_lookup.py`,
`agent_core.py`). `section_search_lookup` fires before the first `search_legislation_sections` of
each statutory instrument (`_is_secondary`) in a quick-lookup run, at most
`MAX_SECTION_LOOKUPS = MAX_ROUTED_LOOKUPS = 5` a run. It runs `lookup_legislation` through the
Worker's own executor (P3.7's precedent: the audit, the memo and the scope record see it; its
arguments are P3.7's routed ones, so the memo serves both), and the section search's result gets
the recital block appended when the record has one, through a new `result_suffix` argument of
`run_worker_tool` (default `""`, appended last, so the memo, the context budget and the audit's
`final_result` see what the model sees). Fail-soft: a failed lookup leaves the search as it was.
**Its HELD outcome is taken back out of the step's scope record**: this lookup is a route to the
recital and the date, not P3.7's held/absent test, and kept, it put P3.7's "Looked up by number"
line on the Manager's report for 164 of 1,169 stored quick-lookup delegations (dry run below); a
stub or not-held outcome is kept (those are what P3.7's line and footer exist to state). The Worker
is shown only the recital, when there is one: a block on every SI it searches within would be the
kind of noise Session 14 measured moving this Worker's output format.

**(4) The conversational prompt** (`prompts.py`, the only prompt that moves). Three line edits,
shown by `cd server_py && python ../$S/p325_identity.py`:
- PHASE 2: "Do NOT fall back to `get_legislation_text`." removed (the tool is not there to fall back
  to).
- Its copy of `_ENABLING_POWER_RULE`: "arrives in a `get_legislation_text` result" becomes "arrives in
  a `lookup_legislation` result for some instruments and not others (code also looks up each
  statutory instrument you search within)".
- Its copy of `_IN_FORCE_RULE` (d): "the `valid_date` on a `get_legislation_text` response" becomes
  "the `valid_date` on a `lookup_legislation` result".

The shared constants are **not edited** (agent A owns `_IN_FORCE_RULE`): the conversational prompt
takes a copy through `_quick_lookup_route`, which swaps each anchor only if it occurs exactly once
and otherwise leaves the rule as it was (Invariant 5); a test fails if any withheld tool name is
left in the prompt. **Merge note for the integrator:** if agent A edits `_IN_FORCE_RULE`'s (d) line,
the swap silently stops and `test_the_quick_lookup_prompt_names_no_tool_its_worker_is_not_offered`
fails; and if A appends a new rule to the conversational prompt's composition line (its last line,
`… + _quick_lookup_route(_IN_FORCE_RULE)`), that one line conflicts and is resolved by hand.

**Which calls this prompt edit drives** (lesson (1) of Session 22): every model call of a
quick-lookup Worker in Conversational mode, for all three non-parliamentary research types (the
case-law-only one included, whose list never had the tool), i.e. its first round (tool choice),
every later round, its P3.8 write-up round at the step cap (same messages), and any `seam_replay
worker` rebuild of such a turn. It drives no Manager, planner, synthesis or research-Worker call.
The edit names `lookup_legislation` in a prompt for the first time (P3.7 deliberately named it in
none); whether that moves the first-round tool choice is unmeasured ($0 batch) and is in the
acceptance (section 4).

**Tooling.** `seam_replay` and `seam_sweep` build a conversational Worker's list as the product
does (`worker_tools_for`, which calls an older revision's one-argument `get_worker_tools` the old
way). `replay_report`'s `retrieved_enabling` (P2.3's `derivations`) and `negcurrency_evidence`
(batch 6 B's) read a lookup record, because the quick-lookup Worker's recital and date now arrive
there: unread, a claim the product permits would grade as unverified. `AUDIT_TRACE.md` documents the
lookup's `valid_date`, its block and the code lookup (no shape change).

---

## 2. What it moves, measured with the built code

### 2.1 The research Workers are byte-identical

`cd server_py && python ../$S/p325_identity.py` (imports the worktree's code, reads `6011b4f` from
git): **30 of 35** research type x chat mode combinations give a byte-identical tool list (JSON) and
Worker prompt; the 5 that move are exactly the conversational ones (legislation only, legislation
and case law, case law only (prompt only), `drafting`, blank). `WORKER_SYSTEM_PROMPT`, `_HYBRID`,
`_CASE_LAW`, both parliamentary Worker prompts, `_ENABLING_POWER_RULE`, `_IN_FORCE_RULE`,
`_RELATIONSHIP_RULE` and all four tool lists are identical. **Passes.**

### 2.2 What the new route supplies in place of each stored call (D's 143 turns, 247 calls)

`python $S/p325_dryrun.py --code server_py --replay $E --out $S/dry_built.jsonl`, then
`python $S/p325_compare.py $S/dry_head.jsonl $S/dry_built.jsonl` (the `m1_` lines). For each
quick-lookup `get_legislation_text` call: what the text supplied, and what a lookup of the same id
supplies through the built executor and recorders. The LEX record is a stored lookup payload of
that id where one exists (71 calls), else the stored text record's own `legislation` object (136;
justified by the 10 of 10 / 9 of 9 equality above), else none (1 call on an Act; and the 39 errored
calls, which returned no record); no network call.

| Class | Calls | Text: recital | Lookup: recital | Text: `valid_date` | Lookup: `valid_date` | Route |
|---|---|---|---|---|---|---|
| SI | 222 (39 errored "not found") | 3, all in `description` | **3 of 3** | 68 | **68 of 68** | code, when the Worker searches within the SI |
| EU | 20 | 0 | 0 | 20 | 20 of 20 | the Worker's own lookup only |
| Act | 5 | 1, in `full_text` only | 0 | 4 | 4 of 4 | the Worker's own lookup only |

- 143 turns, all answered; 24 of the 183 readable SI calls were stubs (the lookup says
  `held_without_text`).
- **Nothing the product used is lost.** The one recital the lookup cannot carry is on an Act, and the
  product never builds an enabling-power block or record for primary legislation (`_is_secondary`),
  so it was never used; it is D's "1 of 8".
- **The route is conditional.** The code lookup fires only when the Worker searches within the SI.
  133 of D's 208 successful calls went straight from a search to the whole text; without the tool
  the Worker must search within the instrument to read anything, but whether it does on 6340's turn
  is a replay question (section 4).
- The 39 errored calls were the tool used as a held/absent probe, all before P3.7; P3.7's routed
  lookup now answers that question for an instrument named by number.

### 2.3 Every output that moves, over every stored delegation

Same two commands; the before side is `--code $S/head/server_py --out $S/dry_head.jsonl`. Per
delegation, the product's recorders are run over each stored raw result in recorded order and the
built `worker_scope_block` is compared; per turn, the lawyer footer (fresh, else section-only, else
lookup-only, else case-law; P2.8's carried line needs the history and is not rebuilt). Every stored
lookup is rebuilt through each side's own executor. **Fidelity check:** the head's executor rebuilds
all **333 of 333** stored lookup results byte for byte, and the built one differs from them only by
`valid_date` (present in 244): `python $S/p325_rebuild_check.py $S/head/server_py server_py $E`.

| Population | Delegations / turns | What moves |
|---|---|---|
| Research (every non-conversational) | 1,040 / 630 | Worker-visible: **0**. Manager-facing block: the currency limb gains a `valid_date` in **3** delegations (a lookup the Worker or P3.7 ran). Lawyer footer: **0 of 630**. |
| Quick-lookup, no whole-text call | 1,169 / 1,178 (1,171 answered) | 382 code lookups in 285 delegations (131 of them with no stored record, in 93 delegations). Worker-visible recital blocks: **0** measured. Block: the currency limb gains a `valid_date` in **325**; "Looked up by number": **0** (HELD pruned). Lawyer footer: **254 turns (252 answered) gain P2.5's existing currency clause**, nothing else moves. |
| Quick-lookup turns that called the tool | 196 / 143 | Counterfactual only (each call replaced by a lookup of its id, since what the Worker would do instead cannot be known at $0): 3 recital blocks shown; footers: 60 lose P2.3's "not verified" enabling clause (19 of them while gaining P3.7's stub clause) and 5 more gain the stub clause alone, 65 in all. The 60 are an artefact of the counterfactual: a Worker that searches within the SI instead records it as looked at, and the clause stays. |

- **The lawyer-facing move is one existing clause on more answers.** The added text is, verbatim,
  P2.5/P4.18's " Whether legislation is in force is not something this index reports, so nothing
  above has been checked against a commencement date and no change record was consulted for this
  answer." It appears because the clause's gate is "any currency row in the turn", and a
  `valid_date` from a code lookup is one. **Checked by byte comparison: in all 254 the built footer
  is the head footer with exactly that clause inserted**, and in no other way different (the 65
  other moved footers are all in the counterfactual row); the `--list` output is in
  `$S/compare_list.txt`. No new wording reaches a lawyer. **Upper bound:** a further **75** quick-lookup turns made a code
  lookup with no stored record and have no currency clause today, so 254 to 329 of 1,178 (decision
  1).
- **What could not be measured:** 49 distinct SIs were section-searched in stored quick-lookup turns
  with no stored record of them (20 SSIs, 17 UK SIs 1990+, 5 NI, 2 Welsh, **5 UK SIs before 1990**,
  the class where P2.3 found 72% carry a recital). The Worker-visible recital block can therefore
  appear on up to 5 instruments in the stored turns; a LEX probe would settle it, and none was made.
- **LEX load:** about 2 extra LEX calls per code lookup (lookup plus the text check), 382 lookups
  over 1,169 quick-lookup delegations before the memo, against 247 whole-text calls removed (all in
  the 196 delegations that made them).

### 2.4 The graders

`python $S/p325_graders.py $S/head/server_py server_py $E`: `derivations`, `negcurrency --all` and
`currency` over all 57 directories with the head's and the built `replay_report`: **171 of 171
identical** (no stored lookup record carries a recital or, before this change, a `valid_date`).
**Passes.** The two new branches only change a reading of after-columns taken on the built code.

---

## 3. Tests

**80 new tests** in `server_py/tests/test_quick_lookup_tools.py` (synthetic "Widget Order 1901",
`uksi/1901/9`, `ssi/1901/3`): the quick-lookup list lacks the tool for both legislation research
types and keeps everything else; every other research type x chat mode gets exactly the list it had;
the narrowed list goes with the conversational prompt and only with it; the conversational prompt
names no withheld tool and both swaps took, while the research prompts keep the shared rules; the
lookup carries `valid_date`; `record_currency` reads it from a held lookup and from nothing else;
`record_enabling_power` records the recital from a lookup and nothing without one; the lookup block
quotes the recital, names its source and is stripped by `strip_scope_blocks`; the whole-text block
is byte-identical; a lookup result carrying the block still parses and still briefs; through
`run_worker_tool` a lookup records both and shows the block; the code lookup fires once for a
section-searched SI and not for an Act, an unparseable id, a discovery search, a change record or a
lookup, and is bounded; an SI without a recital shows the Worker nothing; through `run_worker_agent`
the quick-lookup Worker gets the recital with its section search, the HELD row is pruned, a stub is
kept, a lookup the Worker asks for itself is kept, a research Worker's section search runs exactly
as before (no LEX lookup), a withheld call makes no LEX call, a failed code lookup leaves the search
as it was; the two graders read a lookup record; the seam tools build the product's list.

**Full suite on `lexchat_test_c`: 2275 passed** (2195 + 80).

**Proven to fail with the change reverted** (`python $S/p325_revert.py <worktree root>`, on a
scratch copy; output in `$S/revert_result.txt`):
- **Full revert:** the 11 changed files back to `6011b4f`, **338 added lines removed**: collection
  fails at import (1 error), as expected.
- **18 mutants on the built code, one at a time** (each anchor asserted to occur exactly once, CRLF
  kept), each failing at least one test: tool list ignores the chat mode (4 fail); withheld tool is
  run (1); no code lookup before a section search (2); `section_search_lookup` does nothing (4);
  HELD row not pruned (1); `result_suffix` not appended (1); no `valid_date` on the lookup (3);
  `record_currency` ignores a lookup (3); `run_worker_tool` does not record a lookup's currency (2);
  `record_enabling_power` ignores a lookup (3); no lookup block (4); `run_worker_tool` shows no block
  on a lookup (1); lookup parse back to `json.loads` (2); prompt swaps not applied (1); PHASE 2
  prohibition put back (1); seam tools ignore the chat mode (1); `derivations` grader ignores a
  lookup (1); `negcurrency` grader ignores a lookup (1).

**Data handling.** The staged diff was grepped with `scratchpad_s38/matter_grep.py` (28 words): the
only hits are `uksi/` (every id synthetic: `uksi/1901/9`, `ssi/1901/3`, `ukpga/1899/2`,
`asp/1901/1`) and "annex" (a generic word in a comment). Session ids only (6340, and in this note
6409, 6374, 6383, 6406).

---

## 4. The acceptance, booked as a proposal (the user decides)

**Deterministic (met on this branch):** the 80 tests above, each proven failing with its seam
mutated; the research Workers byte-identical (2.1); the dry run over every stored input (2.3) with
every move listed.

**Replay** (pinned Gemini, each turn in its recorded mode), graded per turn:

| Run | n | What it must show | Recorded cost per rep (pinned Gemini) |
|---|---|---|---|
| `p37_6409` | 3 | No quick-lookup delegation runs `get_legislation_text` (audit); the commenced-section list still delivered (`commencements`, and `lookup` passing as at `wave4_p37c`); 18 of D's 32 substantive whole-text uses were this list | median $0.378 (`wave4_p37c`), range $0.342-0.423 over 15 reps |
| 6340, Conversational | 3 | The suppression check: P2.3's permitted branch still asserts a SUPPORTED derivation in every rep (`derivations`, now reading the lookup record), 0 unverified | $0.067 (`wave0_conv`, the one stored rep in that mode) |
| `p37r_6374`, `p37r_6383` | 1 each | `derivations` exits 0 (or only P2.3's known 6374 class residual); no `get_legislation_text` in a quick-lookup delegation | $0.189-0.239 and $0.291-0.301 |
| `p32_6406`, cut after export turn 5 | 3 | Shared with P3.12 (criterion (v): no false "not held" from a hollow whole-text read) | the first four run turns: median $0.647 a rep over 15 stored reps, max $1.502 |

Plus on every run: the exit-1 set and `modes`; the count of `lookup_legislation` calls per
quick-lookup turn against the stored before-column (the prompt now names the tool); and a hand-read
of every answer whose footer gained the currency clause.

**Figure:** about **$3.80** at the recorded medians (6409 $1.13, 6340 $0.20, 6374 $0.21, 6383
$0.30, 6406 cut $1.94), up to about **$6.50** at the recorded maxima (6406's cut alone up to $4.51).
`python $S/p325_costs.py $E` lists the recorded rep costs; the cut's per-turn figures come from each
stored rep's `turns[].timing.total_cost_usd`. Run in one sweep with P3.12's
(as decided), which shares the 6406 cut.

**The risk to say in advance:** 6340's stored Conversational rep went from a search straight to the
whole text. If the new Worker answers from the search rows without searching within the SI, no code
lookup fires and it cannot state the enabling power. That is the honest direction (Invariant 1 is
about not guessing), but it would fail the suppression check, and the fix would then be to fire the
code lookup on an SI the Worker's search rows return as well (decision 2, option (c)).

---

## 5. What I did NOT do

- No model call, no seam draw, no replay, no server, no LEX or other external call. The 49 SIs with
  no stored record are unmeasured, and so is the first-round effect of naming `lookup_legislation`.
- I did not edit `_IN_FORCE_RULE`, `_currency_limb` or the `get_legislation_changes` branch of
  `record_currency` (agent A's), nor `executor.py`'s `search_case_law` branch (agent D's), nor
  FIX_PLAN, SESSION_LOG, the tracker, any rubric, the lawyer pack, CHANGELOG or memory.
- I did not change the shared `search_legislation_sections` description, which says "Use this
  INSTEAD of get_legislation_text", nor P2.7's discovery-budget stop message, which names the tool;
  both reach the quick-lookup Worker (decision 3).
- I did not route EU regulations or Acts through the code lookup (their `valid_date`, 24 of the 247
  calls, now needs the Worker's own lookup).
- I did not run `plan_status` or `plan_lint` (nothing they read changed).
- I did not push or merge.

**Claims checked:** P3.25's premise (prompt and tool list; held at `6011b4f`); D's 247 calls in 143
turns (re-derived: 247 and 143, all answered; 1,314 answered conversational turns = 1,171 + 143);
D's 7 of 8 recitals in `description` (held, and all 7 within 600 characters); D's "LEX's lookup
record carries `valid_date`" (held: 11 of 11 revised records, 244 of 333 stored lookups).

---

## 6. Decisions for the user

1. **The lawyer's footer gains P2.5's existing currency clause on more Conversational answers.**
   Routing `valid_date` through the lookup makes the clause's gate ("any currency evidence in the
   turn") fire on 254 to 329 of 1,178 stored quick-lookup turns that never called the whole text.
   The wording is unchanged and true there; the turns that did call it keep it.
   1. **(Recommended) Keep it as built.** P2.5's own docstring says the clause was meant for every
      turn that searched the index; this is closer to that, at one existing sentence per answer.
   2. **Gate it on currency evidence not taken from a lookup.** Footers stay as they are on those
      turns, but the 61 stored turns that had the clause through the whole text's `valid_date` lose
      it (measured: `optB_` lines of `p325_compare.py`).
   3. **Do not record `valid_date` from the code lookup at all** (only from a lookup the Worker
      asks for). Nothing moves for a lawyer, and the Manager loses the date on 325 delegations.
2. **P3.25's acceptance.**
   1. **(Recommended) As in section 4, in one sweep with P3.12's**: about $3.80 for P3.25's part (up
      to about $6.50), the 6406 cut shared.
   2. **6409 and 6340 only first** (about $1.33): the two sessions whose substantive use this row
      could break, then the rest with P3.12.
   3. **If 6340 fails the suppression check, also fire the code lookup on SIs the Worker's search
      rows return** (bounded like P3.7), then re-run 6340 only.
3. **Two shared texts still name the withheld tool**: the `search_legislation_sections` description
   ("Use this INSTEAD of get_legislation_text", every legislation Worker) and P2.7's stop message
   (7 stored quick-lookup stops name it).
   1. **(Recommended) Leave both.** A call made anyway is answered in code without a LEX call, and
      editing the description changes every research Worker's tool list, which this row keeps
      byte-identical.
   2. **Give the quick-lookup list its own copy of the description and the stop message a
      mode-aware sentence.** Cleaner for the model; moves the shared stop message's text.
