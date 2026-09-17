# Pre-pilot defect fixes — session log

Append-only, newest last. One entry per session. Read `FIX_PLAN.md` first, then this file for
what actually happened.

The **Surprises / deviations** line is the one that matters — it is where a cold-starting
session learns that reality diverged from the plan.

## Entry template

```markdown
## Session N — <date> — <ledger rows attempted>
**Done:** …
**Surprises / deviations from FIX_PLAN:** …
**State of the branch:** <commit sha>, tests <green|N failing>
**Next action:** <the single next thing>
```

---

## Session 1 — 2026-09-14 — Re-analysis and plan

**Done:**
- Re-analysed all **62** pre-pilot sessions (11–21 Aug 2026, 13 lawyers, 377 messages) from the
  all-time transcript export, classifying each on the transcript rather than the feedback score:
  **25 FAIL, 16 DEFECT, 21 PASS**. Derived 14 failure buckets bottom-up, then reconciled against
  the existing P1–P10 list in `docs/TODO.md`.
- Verified the disputed law at source where a lawyer contested an answer: ILRA 2010 s.1(1)(a)
  scope, Education (Scotland) Act 1962 s.117, SSI 2025/119 reg 2 and its appointed day, SSI
  2008/216 and SSI 2022/356 presence and search rank, and all six contested case citations
  against the National Archives feed.
- Committed the pre-existing P1–P10 analysis to `main` (`eaaa4ec`) so this branch has a base to
  reconcile against, then branched `fix/prepilot-defects` from it.
- Wrote `FIX_PLAN.md` (invariants, ledger, verification protocol, re-planning protocol) and
  froze `evidence/classification.json`.
- Published the full analysis:
  <https://claude.ai/code/artifact/43d8e63d-1c9d-4460-907c-2d35c1fa3786>

**Surprises / deviations from FIX_PLAN:**
- **Three of the fourteen buckets are code defects, not model behaviour, and they were found by
  running the shipped functions against the live API rather than by reading transcripts.** The
  largest — `_matches_jurisdiction` — **discards 100% of legislation search results** whenever a
  jurisdiction filter is set. It expects `"E+W+S+NI"` single-letter tokens; the API returns
  `['Scotland']`, `['']`, `['England','Wales','Scotland']`, `['United Kingdom']`. All six live
  extent values return `False` for all five jurisdiction values. 15 of 62 sessions ran with this
  set. **Read the transcripts second; probe the API first** — fourteen sessions of lawyer
  evidence did not identify this and a five-line script did.
- **B2 has zero primary allocations and that is the finding, not an omission.** The bug never
  presents as itself — the lawyer sees "not in the legislation database", a halted report, or a
  wrong Act, and nothing in the answer mentions a filter. Any future bucket with a high
  secondary count and no primary deserves the same suspicion.
- **`current_only` is a total no-op and cannot be fixed by extending the word list.** The
  `status` field it reads means *which text version is held* (`final` / `revised`), not in-force
  status. 42 of 62 sessions ran with this filter on believing it did something. This reframes
  B4 from "tune the filter" to "we have no in-force signal at all", which is why P1.2 and P2.5
  are split.
- **B6 (capitulation under challenge) was not in P1–P10 at all** and I rank it critical. In 6406
  AILA asserts a position over three turns, reverses completely on pushback with a fresh
  citation, and had already reversed once earlier in the same session. For a tool whose users
  are trained to probe, an answer that tracks who pushed hardest is worse than one that is
  simply wrong.
- **B3 is bigger than P1 framed it.** P1 called the confident false negatives the headline; the
  false negatives are a *symptom*. The cause is that no tool exposes *made under* / *commences*
  / *amends*, so the model answers relationship questions from search adjacency. 6340 is the
  proof: three real, correctly-cited SIs asserted to be made under s.117 of an Act that is a
  404 in LEX. Link-checking — the only verification the sources rail supports — cannot catch it.
- **The feedback form's `Q7a` column has false positives.** 6376 and 6361 both answer "referred
  incorrectly: yes" with free text saying the opposite. Classify on transcripts; the scores are
  a reading order, not a verdict.
- **The raw transcript CSV is deliberately not committed** — it contains the lawyers' live
  casework questions. `classification.json` is committed because it matches the precedent
  already set in `docs/TODO.md`, which names the same users and quotes them. **Open question
  for the deploying organisation: whether the verbatim replay set may be committed as a
  regression fixture.** Until answered it is regenerated locally from the Developer-tab export.
  This blocks nothing — P0.2 writes it to a gitignored path.

**Decisions taken before kickoff (user, 2026-09-14):**
- **Replay model pinned to `google/gemini-3.1-pro-preview`.** All 176 pre-pilot assistant
  messages ran on it; the dev box is currently on `moonshotai/kimi-k3`, which would have
  measured a different system. **Confirm it is still served before the first replay** — it is a
  preview model. If withdrawn, stop and re-decide rather than substituting.
- **n=3 on the 25 FAIL sessions, n=1 on the 16 DEFECTs** (~$50 per baseline pass against ~$82).
  Ambiguous DEFECT replays get promoted to n=3.
- Still open, blocking nothing: whether the verbatim replay set may be committed as a fixture.

**Also corrected this session:** the standing memory note saying there is no OpenRouter key on
the dev machine is **wrong** — there is one, in the local DB (`app_settings` →
`provider.openrouter`, `active_provider = openrouter`), not in `.env`. Memory updated.

**State of the branch:** `fix/prepilot-defects` at the plan commit, branched from `main` at
`eaaa4ec`. No code changed yet. Test suite untouched.

**Next action:** P0.1 — build the replay runner against `/api/system/chat` with
`emit_tool_details=True`. Do **not** start Wave 1 before P0.3 has recorded a baseline; three
weeks of commits landed between the pre-pilot and this branch, and some failures will not
reproduce.

## Session 2 — 2026-09-14 — P0.1, P0.2, P0.3 (Wave 0)

**Done:**
- **The P0.1 gate passed: `google/gemini-3.1-pro-preview` is still served.** In the OpenRouter
  catalogue and answering a live tool-calling probe as its own id. No substitution needed, so the
  baseline sits on the model all 176 pre-pilot assistant messages ran on. `replay.py check` re-runs
  the probe.
- **P0.1** — built `server_py/tools/replay.py` (+ `replay_set.py`, `replay_report.py`) and
  `tests/test_replay_tooling.py`. Acceptance passed: 6404 replayed to a 6,653-char answer
  (pre-pilot 6,757) over 4 delegations with 8 `search_legislation` calls, on the pinned model.
- **P0.2** — froze the 41-session replay set. Acceptance passed, plus three independent
  cross-checks against the frozen analysis that all matched exactly: 10 of 23 Deep Research
  sessions mentioning the step cap, 15 unanswered turns across 11 sessions, and zero session-mode
  reconciliation conflicts.
- **P0.3** — ran the baseline and wrote `BASELINE.md`. **29 of 41 reproduce, 9 do not, 3
  inconclusive.** $37.62 and 6.0 h for the n=1 pass over 155 turns on `bc8e7a4`. Targeted n=3 on
  the 12 unsettled sessions launched after it.
- Amended `FIX_PLAN.md` (P0.1–P0.4, P1.1, P1.3, P1.4, P2.1, P2.6, P4.2, the whole *Replay
  configuration* table) and the `_matches_jurisdiction` paragraph in the root `CLAUDE.md`.

**Surprises / deviations from FIX_PLAN:**

- **The model pins in the DATABASE, not the request body.** `system.py:129` resolves
  `provider_config.get("model") or body.model`, so the `app_settings` row always wins and
  `body.model` never fires. Sending the model in the body and assuming it took would have measured
  `moonshotai/kimi-k3` for the entire baseline, silently. Every run file now asserts
  `audit["model"]` against the pin.

- **Chat mode is a property of the TURN, not the session, and the export does not say which.**
  Deep Research is one-shot (`useChat.js::onDeepResearchComplete` reverts to conversational), so a
  `deep_research` session ran one DR turn among several conversational ones — and **not the
  first**: 6409 turn 6 of 11, 6406 turns 2 **and** 3 of 12, 6341 turn 7 of 8. Only **20 of 155**
  turns are Deep Research. Replaying whole sessions in one mode would have measured a system nobody
  used, at several times the cost. The stored signal (`messages.research_plan`) is not in the export
  and the pre-pilot DB is not on this machine, so it is reconstructed from the `**Key findings`
  block only `DEEP_RESEARCH_SYNTHESIS_PROMPT` asks for — 23/23 known-DR sessions, 0/24 known-non-DR,
  0/15 blank-mode. **New row P0.4** replaces the inference with the stored flag, because reading it
  off the answer is structurally blind to a DR turn that produced no answer, which is B13 itself.

- **B2 does not fail closed, it fails *selectively*, and that is why nobody reported it.**
  `_matches_jurisdiction` opens `if not extent: return True`. Of the **1,009 rows that survived** a
  jurisdiction filter across the baseline, **every one had `extent: []`**; not one carrying a real
  extent value survived. A Scotland filter drops `['Scotland']` and keeps the unknowns — 6354
  returned the *Building Materials and Housing Act 1945* under `jurisdiction=scotland`. So the
  filter hands back a plausible non-empty result set that is simply wrong, rather than an obviously
  empty one. **P1.1 has two jobs, not one:** map the vocabulary *and* decide what `extent: []`
  means. This corrects the headline in both `FIX_PLAN` and `CLAUDE.md`.

- **The halt is not confined to Deep Research.** `chat_loop` returns it as the worker's assistant
  content, so it escapes through a plain Manager delegation too — confirmed in 6340 (standard
  `research` mode) and, most starkly, **6383 turn 1, a conversational turn whose entire answer to
  the lawyer was the raw string `[Research halted: exceeded 20 tool-call steps]`.** A fix at the
  `run_deep_research` site alone leaves that path open. P2.1 amended.

- **A halt answer can look like honest failure and not be one.** 6340 told the lawyer the agent
  "exceeded its operational limits (timed out)" — it hit a step cap — and invented a cause: *"a
  broad enabling power has generated a very large volume of statutory instruments over several
  decades"*, for an Act that is a **404 in LEX**. Invariant 1 requires the disclosure to be *true*,
  not merely non-legal.

- **New row P2.6** — the A4 reformat retry fires on halted workers, spending an LLM call to turn
  "no findings" into a well-formed empty report (*"Jurisdiction & Status: Not applicable"*), and
  scoring it as a prompt-adherence failure in the Efficiency tab.

- **Three of the nine non-reproductions are not improvements**, and reading the count alone would
  get this wrong: 6357 swapped a halt for a filter failure, 6381 now discloses honestly but
  retrieves *worse* (the cause is B2), and 6340 swapped fabrication for a truncated non-answer.

- **6406, P2.1's named acceptance case, no longer halts** — 0 of 4 steps against 4 of 4, $0.72
  against $2.36. But 6382 and 6384 (the row's other two) still halt and still leak the text, so the
  row keeps two of its three cases. The margin is thin: median tool calls per delegation is 5, but
  9% of delegations reach 18+ against a cap of 20, and the max was 41.

- **B13 reproduced and eliminated its own first suspect.** 4 billed-but-empty turns (6370 ×2,
  6407 ×2), all `status: ok`, `audit.error: null`, after real research — 6370 turn 2 made 5 tool
  calls and produced a 976-char Worker report citing SSI 2017/114. **None emitted a single `token`
  event**, so there was never a body for the `<suggestions>` strip to consume. P4.2's acceptance
  also cannot name a turn: the plan cites 6370 #8, the replay blanked at turns 2 and 3.

- **Two measurement traps in my own instrument, both caught by a number disagreeing with what the
  code said should happen.** (1) `json.loads` on `final_result` raises "Extra data" because the
  Phase-2 nudge is appended after the JSON — which silently marked every *productive* search
  unmeasurable and left the metric describing only the empty ones. (2) `executor.py` caps searches
  to `results[:5]` **after** filtering, so a naive "rows discarded" figure counts ordinary
  truncation as filter loss; it overstated B2 several-fold in this file's first draft. Both are now
  pinned by tests (`RESULT_CAP`, `test_the_phase_2_nudge_does_not_break_the_count`).

- **Cost: FIX_PLAN's ~$50 was ~2.3× light.** Replay costs about 2.3× the pre-pilot's recorded
  spend, because that figure covers only the saved assistant message and not the Deep Research
  planner call (which saves no message). A blanket n=3/n=1 pass prices at ~$140.

**Decisions taken this session (user):**
- **Repetitions: n=1 over all 41, then reps 2–3 only where the first pass was ambiguous or
  disagreed with the classification.** Replaces the blanket n=3-on-FAIL policy.
- **Summarisation model left at `google/gemini-3-flash-preview` and recorded, not pinned** — the
  pre-pilot's value is unrecoverable, and inventing one would be a silent confound either way.

**State of the branch:** `fix/prepilot-defects`, Wave 0 complete bar the in-flight n=3 reps.
**No product code has been changed** — everything so far is measurement. Tests: 455 existing + 30
new, all passing.

**Housekeeping owed:** the dev box is still **pinned** to `google/gemini-3.1-pro-preview` with
`local_prompt_cache_enabled = false`. Run `python -m tools.replay restore` (from `server_py/`) once
the n=3 reps finish, or unrelated work will silently run on the replay configuration.

**Next action:** when the n=3 reps land, add their column to `BASELINE.md`, restore the dev box,
then start **P1.1** — and answer the `extent: []` question, not just the vocabulary one.

## Session 3 — 2026-09-14 — P0.3 completed, Wave 1 (P1.1–P1.4)

**Done:**
- **Finished the baseline.** Targeted n=3 on the 12 unsettled sessions: 24 runs, $23.66.
  **Total baseline spend $61.28.** `BASELINE.md` now carries the final verdicts.
- **Wave 1 complete: P1.1, P1.2, P1.3, P1.4 all fixed and accepted.** 528 tests passing
  (71 new across three files). Frontend rebuilt, `client/dist/` force-added.
- Restored the dev box (`moonshotai/kimi-k3`, local prompt cache back ON).

**Surprises / deviations from FIX_PLAN:**

- **The repetitions overturned three verdicts, and that is the headline result of P0.3.** The
  n=1 pass said 29 reproduce / 9 do not / 3 inconclusive. n=3 on the twelve unsettled sessions
  moved it to **34 / 7 / 0**, by flipping three `does not reproduce` calls:
  **6357** (no halt at n=1; halts in 2 of 3 reps), **6389** (1 of 3), **6396** (n=1 said it
  answered the question; rep1 halted **four** workers and rep3 halted two — rep2 was the clean
  draw a single pass would have banked). Invariant 4 is not a formality: a third of the negative
  verdicts in this corpus were wrong on one sample. Any later row claiming a fix works must clear
  the same bar.
- **"Which failure" is stochastic even where "fails" is not.** 6340 produced a different defect on
  each of three runs: a truncated non-answer, a bare negative, then a halted worker. A row whose
  acceptance test asserts on one symptom can pass while the session is still broken.
- **P1.2 was much more than a dead toggle, and this is the most consequential finding of the
  session.** `current_only` did not merely fail to filter — it made an affirmative claim in two
  places. The UI pill read *"In force as at <today>"*, and `build_filter_constraint_block`
  injected *"Status: In-force legislation only. Do not cite or rely on repealed or
  not-yet-in-force legislation"* into the system prompt. **42 of 62 pre-pilot sessions ran with
  that on, so this is the proximate cause of bucket B4** — in 6341 the model said every provision
  cited was in force because the system had told it the results were current. Removing it should
  make P2.5 substantially easier; re-measure the in-force claim rate at P1.5 before writing P2.5,
  because part of that bucket may already be gone.
- **P1.4's cause was our own prompt, not the model.** `WORKER_SYSTEM_PROMPT` said *"IF you are
  citing a specific section, you MUST manually append `/section/{number}` to the Base URI"* —
  while the LEX section endpoint was already returning the exact provision URL in `uri`, buried in
  a raw passthrough alongside `created_at` and five null `provenance_*` fields. The model was
  obeying an instruction to guess. Worth generalising: **before treating a defect as model
  behaviour, check whether a prompt instructs it.** Two of Wave 1's four rows were this.
- **`['']` had to be treated as unknown-and-include, and the data forced it.** Matching territory
  names alone (the obvious fix) would have dropped **40% of Scottish material**, because 2,009
  Scottish SIs carry `['']`. The obvious fix was a new trap. The id-prefix tie-break
  (`nisr/`, `wsi/`) is what makes admitting unknowns safe — it removes the last 1,017 wrong
  admissions at zero cost in false negatives.
- **A third measurement trap in my own instrument**, after the two in Session 2: `results[:5]` in
  `executor.py` truncates *after* filtering, so a naive "rows discarded" count attributes ordinary
  truncation to the filters. It overstated B2 several-fold in BASELINE.md's first draft. Now named
  `_MAX_SEARCH_RESULTS` in the product and `RESULT_CAP` in the harness, with tests on both sides.
  The pattern across all three: **a number that disagrees with what the code says should happen is
  usually the instrument, not the finding.**

**Decisions taken this session (user):**
- **Jurisdiction filter means "applies in", not "made for"** — Scottish-extent + UK-wide +
  unknown-extent, minus other-jurisdiction id prefixes. Scored over 17,560 real result rows it
  drops 0% of Scottish material and admits 0 clearly non-Scottish rows, against the old code's
  97.5% dropped. Pinned by `test_uk_wide_instruments_are_in_scope_for_a_devolved_filter`.
- **`current_only` removed outright**, not relabelled.

**Judgement call, now RESOLVED (user chose option C, 2026-09-15).** ~~The justification I first
gave for keeping the request field — that removing it would break clients "on validation" — was
**wrong**: `AgentRequestBase` does not set `extra="forbid"`, so pydantic ignores unknown keys.
Removing the field breaks nothing.~~ What was actually at stake was only the external contract:
`audit["filters"]["current_only"]` is read by lexchat-eval, and `AUDIT_TRACE.md` tells consumers
to assert on `schema_version`, so dropping the key means bumping to v2 and telling that repo.

Settled as: **request field removed; audit key kept, always `null`; schema stays v1.** A `null`
there reads as "this filter no longer exists" and is strictly safer than a `KeyError` for a
consumer indexing it directly. A schema bump is worth spending on a batch of changes rather than
one field — **P2.1 is the natural moment**, since making the halt structured metadata changes the
trace shape anyway. `docs/api/AUDIT_TRACE.md` was stale on this (it still documented `current_only`
as a live filter) and has been corrected.

**State of the branch:** `fix/prepilot-defects` @ `302585e`. Waves 0 and 1 complete, **529 tests
passing, working tree clean, 8 commits unpushed — nothing on `main`.**

**Machine state a new session inherits (all deliberate, nothing owed):**
- Dev box **restored**: `moonshotai/kimi-k3`, `google/gemini-3-flash-preview`, local prompt cache
  **ON**. P1.5 must re-pin before measuring — `tools/.replay_pin_state.json` is gone, as it should
  be after a successful `restore`.
- **No uvicorn is running**, deliberately. The Wave 0 process was killed rather than left up:
  Python loads modules at import, so a server surviving from this session would have served
  **pre-Wave-1 code**, and a replay against it would have recorded old behaviour as the Wave 1
  result. Start a fresh one.
- `evidence/replay/baseline/` holds all 65 Wave 0 run files (gitignored). Do **not** write the
  re-baseline into that directory — `replay.py run` skips existing files and would silently do
  nothing. Use `evidence/replay/wave1/`.

**Next action:** **P1.5 — re-baseline on the Wave 1 HEAD.** The full runbook is in the P1.5 ledger
row, including the three traps above. ~$38, ~6 h. Then Wave 2 from P2.1 — **whose acceptance test
needs rewriting before it is used**, because 6406 stopped halting (0/4 steps in all three reps) and
asserting "no halt text" on a session that no longer halts would pass without the fix. 6382 and
6384 still halt and still leak the text, so they are the cases to keep; 6383 turn 1 is the
strongest, having shown the raw `[Research halted: exceeded 20 tool-call steps]` string as its
entire answer.

## Session 4 — 2026-09-15 — P1.5 (re-baseline), plus five instrument corrections

**Done:**
- **P1.5 complete.** Re-ran the full replay set on the Wave 1 HEAD: 41 sessions, 155 turns,
  **$27.22 / 3.7 h** against Wave 0's $37.62 / 6.0 h. Zero model mismatches, zero errored turns,
  and no product code changed during the sweep (verified by diff). `BASELINE.md` has its second
  column.
- **B2 and B5 are closed.** Searches emptied by filters **351/1,531 → 3/790**; `total` misreported
  **1,010 → 0**. All 13 jurisdiction-filtered sessions went to zero; the 3 residuals in 6357 are
  `legislation_type=primary` correctly excluding SSIs, checked row by row.
- Built `replay_report compare` for wave-over-wave reads, and added `halts_undisclosed` and
  `provision_links_manufactured` signals. 560+ tests passing.
- Purged 20 accidentally-committed pre-pilot server logs from branch history (user decision) and
  fixed `.gitignore`.
- New row **P1.6**; **P2.1's acceptance rewritten**; P2.5, P4.2 and P4.3 amended.

**Surprises / deviations from FIX_PLAN:**

- **B2 was a cost and latency defect, not only a retrieval one, and the plan never said so.**
  Searches fell 1,531 → 790 and delegations 278 → 197 *for the same 155 turns*, and the sweep ran
  2.3 hours faster. An emptied search made the model reformulate and retry: 6396 went **172
  searches → 1**, 6381 **80 → 6**, 6357 93 → 14 ($1.47 → $0.41). The filter was not just hiding
  results, it was driving the model to flail.

- **Five measurement traps this session, after three in Sessions 2–3 — and three of the five
  numbers `BASELINE.md` published were wrong.** In order found: (1) comparing a 65-file baseline
  against a 41-file sweep inflates every Wave 0 figure by half; (2) `bad_links` read an SI's title
  year ("Regulations 2013") as a provision number — **73 of the 88 were false positives**, B14 was
  20/376, not 88/376; (3) B8's 88% added together report turns (79%) and turns that never answered
  (96%), where the rail hangs off B1 halts — **6341 turn 5 shows 40 sources behind a 333-char
  "timed out" message**; (4) `HALT_PARAPHRASE` caught **9 of 14** real halt disclosures; (5)
  `compare` summed each directory whole, so a skipped session would have read as an improvement.
  **The pattern is now unmistakable: in this work the instrument is wrong more often than the
  product.** Every one was caught by a number disagreeing with what the code said should happen.

- **`test_bad_link_*` was green throughout**, and FIX_PLAN calls it "P1.4's stated acceptance
  check". It was written against synthetic labels that never contained a real SI title. **A
  detector can be pinned by a passing test and still be wrong on every real input.**

- **P2.1's acceptance test was not merely broken, it was harmful.** "Produce no halt text" is
  satisfied by saying nothing — and **2 turns in the Wave 0 rep-1 pass already halt silently**
  (5 in Wave 1), returning a normal-looking report with no signal that it is incomplete. 6396 rep1
  halted **four** workers and never mentions it. Under Invariant 1 that is worse than the text
  leaking. The trivially-passing implementation of the old row was the worse product. Rewritten to
  assert the answer *does* disclose, that the reason is **true** (a step cap, not "timed out"),
  and that the halt is structured metadata. Also: **6383 turn 1's halt never appears in any
  delegation report**, so a check reading only `delegations[].report` is blind to the starkest case
  in the corpus.

- **B14's "regression" is the opposite of what it looks like.** `bad_links` rose 20 → 32, but the
  metric cannot ask whether a URL was ever *returned by a tool*. ~~Provision URLs that no tool
  returned went **327/327 (100%) → 26/136 (19%)**.~~ **[Corrected in Session 5 — that signal read
  only `final_result`, i.e. the SUMMARISED text, so every URL the summariser ate scored as
  manufactured. True figures: manufactured 29 → 0, reconstructed 293 → 26. See Session 5 and
  BASELINE's second *Correction*. The conclusion below still holds; the magnitude does not.]** Before P1.4 the prompt *told* the model to
  append `/section/{number}`, so every provision URL was invented — and most carried the right
  number, so the checker scored them **good**. A manufactured URL resolves to a real page and reads
  as a verified citation. The 32 flagged links are the residue of honesty: with no retrieved URL
  and forbidden from inventing one, the model links the Act's contents page. **In 6348, zero
  provision URLs were returned by any tool yet it cites FOISA ss.36 and 55** — so a bad link is now
  a *symptom of citing an unretrieved provision*, which the manufactured URL used to conceal.

- **B4 rose 27 → 30, so P2.5's scope does NOT shrink** — the question P1.5 was asked to settle.
  P1.2 removed the filter's constraint block, but three sites in `prompts.py` still *instruct* the
  Worker to state in-force status (line 111), and the only metadata is LEX's `status`
  (`final`/`revised` = which text version is held). Nearly every claim reads *"currently in force
  (status: revised)"* — the model is faithfully reporting the field it was pointed at. **Third
  instance of: before treating a defect as model behaviour, check whether a prompt instructs it.**
  The obvious fix is a trap — "Jurisdiction & Status" is mandatory in `_REPORT_SECTIONS`, so
  telling the model to omit it spends an A4 reformat call re-adding the heading.

- **Fixing retrieval increased pressure on the 20-step cap.** p90 tool calls per delegation 15 → 20
  (the p90 delegation now sits *at* the cap); at-or-over-cap 6.3% → 11.2%, while total delegations
  fell 29%. A search that returns results generates Phase-2 work where an emptied search was just
  retried. The cap question was parked behind a metric measured against a broken filter — Invariant
  3 one level up. Recorded in P2.1; **still not a reason to bump 20 → 30 reflexively**, which would
  mask the failure P2.1 exists to make honest.

- **Two sessions changed verdict for the right reason, and both are P1.1's.** 6381 said *"I am
  unable to locate the Victims and Witnesses (Scotland) Act 2014"* three times in Wave 0 — honest
  failure caused by the filter — and now answers from the correct `asp/2014/1`. 6396 spent 16
  delegations and 172 searches to answer from a superseded **1984** Order; it now retrieves the
  correct 2007 Regulations in one delegation for $0.04. **Part of B10 may be downstream of B2** —
  relevant to P3.1's scope.

- **B13 is not confined to 6370/6407.** 6338 turn 2 blanked after 2 delegations and real API calls
  (330 s, $0.40, `status: ok`, no `token` event). Researched the empty-answer question: `chat_loop`
  **never reads `finish_reason`**, so an empty stream becomes an empty answer with no error. Google
  has *reproduced* a Gemini 3 streaming + function-calling bug ending `finish_reason=STOP` with
  empty text after a tool executes; Gemini's `MALFORMED_FUNCTION_CALL` is silently normalised to
  `stop` with empty content. Recorded in P4.2 as a lead, not a diagnosis — **the first move there
  is a diagnostic (capture `finish_reason`/`native_finish_reason`), not a fix.**

- **A data-handling breach, found and purged.** Commit `302585e` had swept in 20 pre-pilot server
  logs carrying **211 unredacted Worker delegation briefs** naming live casework topics. `.gitignore`
  has `*.log`, which does not match `..._agent.log.2026-08-18` — the date is the extension. Tool
  args were correctly redacted; the Manager's delegation brief is one of the two sites `CLAUDE.md`
  records as deliberately un-redacted. Purged from history (unpushed, `main` untouched), local
  copies kept outside the repo, `.gitignore` fixed with both patterns.

**Decisions taken this session (user):**
- Purge the committed server logs from branch history rather than untrack them going forward.
- Read the sweep session-by-session as planned; record the cap findings in P2.1's row.

**State of the branch:** `fix/prepilot-defects`, Waves 0 and 1 complete plus P1.5. Tests green.
Dev box **restored** (`moonshotai/kimi-k3`, local prompt cache ON) — `tools/.replay_pin_state.json`
is gone, as it should be after a successful `restore`.

**Machine state a new session inherits:**
- **No uvicorn running** — killed deliberately, same reason as Session 3: Python loads modules at
  import, so a server surviving this session would serve pre-Wave-2 code.
- `evidence/replay/baseline/` (65 files) and `evidence/replay/wave1/` (41 files), both gitignored.
  A Wave 2 sweep needs a **new** directory; `replay.py run` silently skips existing files.
- **Compare with `replay_report compare --before <baseline dir> --after <dir>`**, pointing at the
  **real** directories: it restricts both sides to rep 1 itself. Do not hand-build a filtered copy
  and do not compare directories whole — the baseline holds 65 files to a sweep's 41, which
  inflates every Wave 0 figure by roughly half.
- **The 20 purged pre-pilot server logs are preserved outside the repo** at
  `C:/Temp/aila-prepilot/ServerLogs-backup/` (24 files). They were removed from branch history
  because 8 of them carried 211 unredacted Worker delegation briefs naming live casework.
  **Do not re-commit them**; `.gitignore` now blocks both `*.log.*` and `server_py/ServerLogs/`.
- **Run files record `git_head: 6a5eeea`, which no longer resolves.** That commit was rewritten
  by the log purge mid-sweep and is now `4c8878c` — same tree minus the logs. Product code was
  verified unchanged across the sweep, so the measurement stands; the SHA is simply stale.

**Decision after the sweep (user, 2026-09-15):** **no wave-by-wave merging.** The branch is completed in full and pushed to `main` once, at the end. This reverses the original policy in *Merging back* and in the root `CLAUDE.md`, both now amended, along with the standing memory note. The accepted consequence: the target keeps running the pre-pilot code — including B2 — until that push. A later session must not push a finished wave early on its own judgement.

**Next action:** **P1.6** (cheapest row on the page, deterministic acceptance, no replay needed), then **P2.1** with the rewritten acceptance — and read its cap note before touching
`max_turns`. P1.6 is available in parallel and is the cheapest row on the page. Note that **no
session in the Wave 1 column is recorded as fixed**: it is n=1, and Wave 0's repetitions overturned
three of nine negative verdicts, so any row claiming a fix still needs n=3.

---

## Session 5 — 2026-09-15 — P1.6, P2.1, P2.6, P4.4, P0.4 (code half), all of Wave 5, and four instrument corrections

**Done:**
- **P1.6 complete.** `src/utils/citation_links.py`, wired at four seams. **(a) the cause** —
  `provision_url_block` appends the retrieval's own provision URLs *after* summarisation
  (same trick as the Phase-2 nudge: the summariser cannot eat what it never saw);
  **(b) the guarantee** — `enforce_provision_links` at the worker-report seam, the
  Manager's final-answer seam and the DR synthesis seam, against a **request-scoped** set
  of every legislation.gov.uk URL any tool returned, harvested from `raw_result`. A
  provision URL absent from that set is demoted to the Act when the Act *was* retrieved,
  unlinked otherwise, marked with one footnote.
- **P2.1 complete, acceptance passed.** The halt now travels as structure
  (`chat_loop` returns `{"halted": {reason, limit, steps}}`), a halted worker hands back a
  statement addressed to the agent that reads it, and **code** — not a prompt — strips
  every raw marker and prepends a disclosure at both the Manager and DR seams, naming the
  plan steps where it knows them. `AUDIT_SCHEMA_VERSION` → **2** with
  `delegations[].halted`; spec updated. Replay n=3 on 6382, 6384, 6383, 6340:
  **12 runs, $8.63, 7 halted turns, 0 failing**, and no invented cause in any of them.
- **The cap stays at 20**, decided on the completed sweep as the row required — and the
  row's own figures were the wrong counter. See *Surprises*.
- **P2.6 complete** — the A4 reformat retry no longer fires on a halted worker, keyed on
  P2.1's `result["halted"]` (which is why it depended on P2.1 rather than duplicating its
  detection). Narrow by design: an unhalted malformed report still gets its retry.
- **P0.4's code half done, row left `[~]`** — per-turn `deep_research` on the transcript
  export + CSV column, `client/dist/` rebuilt. The re-export stays blocked on target access.
- **New row P2.7** — the legislation bot has no discovery budget; only the parliamentary
  modes get one. Opened off P2.1's cap evidence.
- **Wave 5 opened, and P5.1 ANSWERED without sending it.** All three questions drafted
  (`WAVE5_QUESTIONS.md`) — then P5.1 turned out to be answerable from here: the API
  publishes an OpenAPI spec and we call 3 of its 13 endpoints. **B3 is buildable, not
  permanently a disclosure.** Full answer below; new rows **P3.5** and **P3.6**; P2.3
  narrowed to enabling power alone. **P5.3 answered the same way** — the index refreshes
  daily and is current, but 2026 secondary legislation is only ~5% held, which is what
  B5's negative must say. **P5.2's facts established** — the National Archives gap is
  verified as TOTAL (the Court of Session is not in its taxonomy) and, worse, a Scots-law
  query returns 50 English judgments rather than nothing. Its decision is the
  organisation's, so the row stays `[~]`.
- **634 tests** (564 → 634). Dev box restored, no uvicorn left running.

**Surprises / deviations from FIX_PLAN:**

- **P1.6's premise was the instrument, not the product — ninth trap in five sessions, and
  the first to *invert* a headline.** The row said 19% of provision URLs are "the model
  disobeying … for provisions no tool retrieved", citing 6365's `/section/21` and
  `/section/22` on `asp/2000/1`. **Both were retrieved.** They sit in the `raw_result` of
  two summarised `search_legislation_sections` calls (32K/34K raw → 3.6K/3.9K summarised).
  `_urls_returned_by_tools` read only `final_result`, which **is** the summarised text
  whenever summarisation fires — and **70% of section searches are summarised**, the
  summary keeping the section numbers and dropping every URL. Corrected there are **three**
  outcomes: shown **5 → 110**, reconstructed **293 → 26**, **manufactured 29 → 0**. So
  `provision_links_manufactured == 0` — the row's own acceptance — **was already true at
  Wave 1**, and P1.4 achieved more than was published.

- **"100%" should have been read as an artefact on sight.** P1.4's row even argued it away
  ("100% is not a rounding artefact"). Explaining a suspicious number instead of
  distrusting it is how it survived a whole session.

- **A fix can be invisible to the metric that grades it.** P1.6's block is appended after
  summarisation, so `final_result` becomes prose plus a bracketed block — not JSON. The
  detector parsed `final_result` as JSON, so post-fix it would have found nothing there and
  gone on scoring every link `reconstructed`. Caught while writing the test, and there is
  now a test asserting exactly this. **Applied forward at P2.1:** `HALT_AS_TIMEOUT` carries
  negative lookbehinds so P2.1's own notice ("it is **not** a timeout") cannot match itself.

- **P2.1's cap figures counted tool calls against a cap on ReAct *rounds*.** A round issues
  several tool calls in parallel and the Worker prompt instructs batching, so the two are
  different quantities: **6341 turn 6 made 45 tool calls in 13 rounds**. On the completed
  41-session sweep using `react_turns_max` — the counter the cap acts on, on every run file,
  and the one the row itself said to read — **p90 17 → 13** and **at-cap 7.8% → 7.2%**.
  Pressure **fell**; it did not nearly double. The mid-sweep sample made it worse: the 11
  outstanding sessions were the halt-heavy ones the row named.

- **The turns that hit the cap are looping, not starved**, which settles the cap question:
  **26% redundant tool calls against a 15% base rate**, with 6409 turn 7 spending **25
  Phase-1 searches for 0 retrievals**. More rounds buys more of the same and would mask the
  failure P2.1 exists to make honest. → **P2.7**.

- **6409 turn 7 is the worst case in the corpus, worse than 6340.** 25 searches, 0
  retrievals, worker hit the cap, and the entire answer was *"The research agent could not
  locate [the SSI] in the legislation database."* A step cap rendered as a **negative
  retrieval finding** — an *untrue* honest failure, the one thing Invariant 1 cannot
  survive. It is why the notice denies that reading explicitly rather than just describing
  the cap. 6335 turn 7 carries a second invented cause, so the speculation is a pattern.

- **The acceptance coverage is thinner than "4 sessions × 3 reps" sounds, and the write-up
  says so.** Only **6340 and 6382** halted in 3 of 3 reps and so give full n=3 evidence;
  6383 halted in 1 of 3 and **6384 in 0 of 3**. And **6383 turn 1 — the row's named
  "strongest case" — did not halt in any rep**; the halt moved to turn 4. Grading is
  therefore per halted **turn** over the directory, never per named session.

- **The model's prose came along, which was not assumed.** The disclosure is code-emitted
  precisely so it need not depend on the model — but all 7 halted turns *also* stated the
  true reason in the model's own words, and 6383 rep 1 added its own *"this is not a
  negative result or evidence that the material does not exist"*. That is the
  per-occurrence instruction in the worker's replacement report working, and the reason it
  lives in the tool result rather than in a system prompt.

- **One residual, booked to P2.2 rather than widened into P2.1.** 6382 rep 2 still opens
  with *"no SSIs … were found that contain the '£' symbol"* — drawn from the two steps that
  halted. P2.1 makes the contradiction visible (the notice says in terms that this is not a
  finding of absence, and the BLUF is hedged) but does not prevent it. A negative must state
  the limits it was reached under, and **a halted step is one of those limits**.

- **A large per-session drop that is NOT evidence of a fix.** 6384 turn 1 went from 14
  Phase-1 searches to 1–2; 6383 turn 1 from a halt at 20 rounds to 2–6. Tempting to credit
  P1.6 and wrong to: its block only fires *after* a summarised section retrieval, and 6384
  turn 1 made two retrievals in Wave 1. Before-side is n=1. Recorded as variance so a later
  session does not read it as a fix.

- **The UI half of P2.1 is satisfied by the text, and a badge would be worse.**
  `research_incomplete` has no DB column, so a badge would vanish on reload while the
  prepended notice — which lives in `messages.content` — persists. A marker that disappears
  on reload teaches the lawyer that its absence means complete.

**Decisions taken this session:**
- Keep the prompt's "do not append `/section/{number}`" instruction *and* enforce it in
  code — the same belt-and-braces as the unconditional `<suggestions>` strip.
- Keep `provision_links_manufactured` meaning "never retrieved anywhere" and add
  `provision_links_reconstructed` alongside, rather than redefining the existing name. A
  redefined metric under the same name silently invalidates every earlier reading of it.
- Disclose a halt **unconditionally**, with no detector deciding whether the model already
  disclosed it well enough. On this work the detectors have been wrong more often than the
  product, and a false negative there is a lawyer relying on a partial answer.

### P5.1 — ANSWERED, and mostly without the LEX team (recorded answer, this row's acceptance)

The row was written as a question to ask. Four fifths of it was answerable from here,
because **the LEX API publishes an OpenAPI spec at `/openapi.json`** and nobody had looked.
It documents **13 endpoints. We call 3.** Reproduce with `python -m tools.lex_probe`.

| question | answer |
|---|---|
| **Q2 amendment relations** | **YES** — `/amendment/search`, `/amendment/section/search`. Provision-to-provision, resolvable URL on both sides, and a **`search_amended` flag that carries the direction** |
| **Q3 commencement** | **YES** — `type_of_effect`: 246 "coming into force", 43 "Commencement Order" over 1,358 sampled rows |
| **Q4 repeal / revocation** | **YES** — 62 "repealed", 30 "words repealed", 6 "revoked", 3 "words revoked", 3 "repealed in part" |
| **Q5 the route** | `/openapi.json`. There was never a hidden route — there was a published spec we had not read |
| **Q1 enabling power** | **NO route found.** Not in `/legislation/lookup`'s fields; explanatory notes are **Act-level** (404 for `ssi/2020/295`), so they cannot say what an SI was made under |

**So B3 — the largest bucket — is BUILDABLE, not permanently a disclosure**, for four of
its five relations. That inverts the row's stated stakes ("this determines whether the
largest bucket is buildable or permanently a disclosure"). P2.3 narrows to enabling power
alone; the rest becomes **P3.5**, a retrieval row.

**And `description` is thrown away by our own slimmer.** It states relationships in prose
**with the date** — *"These Regulations bring sections 31 and 36 and schedules 5 and 10 of
the Social Security (Scotland) Act 2018 into force on 8 October 2020."* — and 5 of 10
sampled results carried commencement, amendment or enabling-power language there. The
comment in `lex.py` calls it "verbose and redundant once Phase 2 retrieves actual section
text": true of the text, **false of the relationships**, which no section text states. It
is also the only observed route to an enabling power. → **P3.6**, with the warning that the
original reason for stripping it was real (~10–16K per result, and removing it is what kept
Phase 1 under the summarisation threshold), so it must come back capped, not reverted.

**Two of my own claims in this row were wrong, and both were read-the-wrong-field errors —
the same class as the eight instrument traps before them.**

- ~~"`/legislation/text` returns a record for `ssi/2025/119` with an empty `text` field"~~ —
  the response is `{legislation, full_text}`. The `text` key sits on the nested object and
  is **empty for everything**, including `asp/2018/9`, which returns **130,476 characters**
  of `full_text`. Reading it as the text says the entire corpus is a stub.
- ~~"a stub record is indistinguishable from absence at the tool boundary"~~ — it is
  **explicitly signalled**: `full_text` is the literal sentence *"No text content available
  for this legislation."* and `/legislation/section/lookup` returns **404** where a held
  instrument returns 200. Absent is different again (`/legislation/lookup` → flat 404 for
  `ukpga/1962/47`). **Three states, all distinguishable.** What remains worth asking is
  whether that sentinel is a stable contract — branching on a magic string is fragile.

**Five narrower questions remain for the LEX team** (`WAVE5_QUESTIONS.md`), led by enabling
power and by the fact that **a commencement row carries no date** — the relation is
retrievable, the date is not, which lands directly on P2.5.

**The wider lesson, and it is the ninth and tenth instrument error of this work in a
different guise:** two sessions of planning treated "does the API expose relationships?" as
an external question with unknown lead time. It was a `GET /openapi.json` away. **Before
opening an external row, check whether the system can be asked directly.**

### P5.3 — ANSWERED, and the answer is the opposite of the question (recorded answer)

`GET /api/stats` and `GET /healthcheck` are public, and coverage is directly measurable by
sampling `/legislation/lookup`. `python -m tools.lex_probe --coverage`.

**The index refreshes DAILY and is current.** Ingestion runs land ~02:00–02:30 UTC; the
newest `created_at` in a 1,162-record sample was **today, 2026-09-15T02:17**. Corpus:
**220,022** instruments, 2,107,361 provisions, **2,580,915 amendments**. The row was
written to ask "how stale is it". It isn't stale.

**The real problem is per-instrument gaps, and for 2026 they are severe:**

| series | held (20-point samples) | **corrected, 60-point (Session 6)** |
|---|---|---|
| ASP 2025 / 2026 | **100%** | 100% |
| SSI 2025 | 85% | **87%** |
| **SSI 2026** | ~~**5%**~~ | **2%** |
| **UK SI 2026** | ~~**0%**~~ | **2%**, and ≥27 held instruments found by search |
| UKPGA 1962 | 60% | (not re-sampled) |

**This sets B5's wording, which is what the row was for.** On these numbers a "not found"
for a 2026 SSI is *far* more likely a coverage gap than an absence in law, and a negative
that does not say so comes close to telling a lawyer the instrument does not exist.
P2.2 now has a number to write against.

**Corrected 2026-09-15 (Session 6), by the cross-check this very section prescribes.**
"UK SI 2026 **0%**" is the number to retire. It reads as *"nothing made in 2026 is in the
index"*, and that is false: `/legislation/search` returns **27 distinct `uksi/2026/*`
instruments**, spread from `/3` to `/856`, and **all 12 spot-checked resolve on
`/legislation/lookup`**. A 60-point census puts the rate at ~2% — low single digits, not
nothing, which is exactly what a 0/20 sample of a ~2% series looks like. The two readings
never disagreed; the *wording* of the headline did. So the product string P2.2 writes says
**"under 5%"** and never "none": a lawyer told none stops looking, and the eleventh
instrument error would have been published in front of users rather than in a document.

All three original claims re-verified. `ukpga/1962/47` is absent — **but as a
per-instrument gap, not a date cliff**: `/41`, `/42`, `/45`, `/50`, `/51` and `/55` are all
held. "We don't hold pre-19xx" would be the wrong story to tell a lawyer.

**A method warning, because it cost two wrong conclusions inside this probe.** Point
lookups are a bad census instrument. Twelve misses across `ssi/2026/{1..250}` read as "no
2026 SSIs at all"; a 20-point UK SI 2026 sample returning nothing read as "nothing from
2026" — while `uksi/2026/772` was in the index the whole time and had been created a week
earlier. In a series with ~20% coverage a sparse sample of absences proves nothing.
**Cross-check a lookup census against `/legislation/search`.** Both errors were caught the
usual way: a number disagreeing with something else the system said.

**And one finding belongs to P5.2.** `/healthcheck` reports case-law collections in the
vector store — **`caselaw` 69,970 points, `caselaw_section` 4,723,735, `caselaw_summary`
61,107** — while `/openapi.json` exposes **no case-law endpoint**. A case-law corpus exists
inside a system we already call, and we reach case law through the National Archives
instead. **That may turn B12 from a procurement question into an API request**, which is a
materially different piece of work. Recorded in P5.2; still needs a human to ask.

### P5.2 — facts established, decision still the organisation's (recorded)

The row rested on an asserted gap. It is now measured, and it is worse than "thin".

- `atom.xml?court=csoh` and `?court=csih` → **HTTP 400, "csoh is not one of the available
  choices"**. The Court of Session is not a court in the National Archives' taxonomy.
- `atom.xml?query=Court of Session` → **200 with 50 results, not one of them Scottish**:
  20 EWHC, 11 UKFTT, 5 EWFC, 4 UKSC, 3 UKUT, 3 EWCA, 2 EWCOP, 1 EAT.

**That second line is the finding.** A Scots-law case-law question does not come back
empty; it comes back with fifty English judgments that mention Scotland, and the model
answers from them. That is 6375 exactly — English common-interest privilege analysed as
Scots law. **An empty result is a disclosure; a full one of the wrong jurisdiction is a
trap**, which is why P2.4 matters more than an ordinary coverage gap and why its footer can
now say something precise and verifiable instead of "may be incomplete".

**Every court AILA can filter on is non-Scottish** — 14 options in both the tool schema and
the UI filter, none Scottish. The codes are correct and the schema already warns against
inventing others, so this is not a defect to fix; it is the product gap, visible to every
user on every research query.

**And the lead from P5.3 holds up.** `/healthcheck` reports `caselaw` **69,970**,
`caselaw_section` **4,723,735**, `caselaw_summary` **61,107** points; `/openapi.json`
exposes **no case-law endpoint**; and the four conventional mirror names (`/caselaw/search`,
`/caselaw/lookup`, `/caselaw/text`, `/caselaw/section/search`) all **404**. The corpus exists
inside a system we already call and is unreachable through its published contract. **So the
first move is a free question to the LEX team, not a procurement exercise** — if it covers
the Court of Session this is an API request; if it mirrors TNA, nothing changes.

**Left open deliberately.** The row's acceptance is *a recorded decision*, and that is the
organisation's to take, so P5.2 is `[~]` not `[x]`. `WAVE5_QUESTIONS.md` now states it as
three steps in order: ask LEX; if no, put the procurement question to the product owner;
either way record it, because a "no" makes **P2.4 permanent rather than interim**.

### P4.4 — the case-law court filter removed (user decision, acted on this session)

Raised by the user off the back of P5.2, and the evidence supported it three ways.

- **Nobody used it.** Zero of the 41 replayed sessions set a court, against
  `current_only` at 29 and `jurisdiction` at 13. Only 11 of 62 sessions touched case law.
- **It was a trap for this audience.** All 14 options English, Welsh or UK-wide, against a
  corpus with no Scottish courts in it. Choosing one guaranteed the wrong jurisdiction.
- **It overrode the model**, and this is the part that made it a defect rather than dead
  weight. `executor.py` applied `_court` *after* the model's own `court` argument and
  clobbered it — a court chosen three turns earlier beating live per-query judgement, which
  is the B2/B4 stale-filter failure again. The date filters beside it *intersect*
  (`max`/`min`); court did not.

**The capability stayed; only the control went.** `search_case_law` keeps its `court`
parameter, which is the whole reason the filter was redundant — the model already narrows
by court when a question calls for it. Two tests pin that specifically, because deleting
the tool parameter too is the obvious wrong reading of this change.

Retired on **P1.2's precedent exactly**: field removed outright, pydantic ignores rather
than rejects (verified live — a stale client still gets a 200), `audit["filters"]["court"]`
kept as a permanent null, `AUDIT_SCHEMA_VERSION` **not** bumped.

**What was deliberately kept**, and why it matters: the session-feedback **export column**
and the stored historical `filters` rows, because pre-pilot snapshots recorded real values
and an export that dropped them would misrepresent what those sessions ran under; `court`
in the replay harness for the same reason; and **the jurisdiction panel's Scotland/NI
note** — *"Case law database covers E&W and UK-wide courts only"* — which is the true
statement the court list was quietly contradicting. Removed from the **write** allowlist,
though: storing a value for a control that no longer exists would put a false claim in a
record an admin reads.

**And what it does not fix.** Removing a misleading control does not put the Court of
Session in the corpus. P2.4 is still required and P5.2's question still stands.

### Case-law coverage, mapped — and one claim made and retracted

Asked what the case-law corpus actually covers, so it was measured rather than inferred.

**42 court codes**, scraped from the National Archives' own search facet: 17 England &
Wales (High Court ×11 divisions, Court of Appeal ×2, Crown, County, Family, Court of
Protection) and the rest UK-wide tribunals (UKSC, Privy Council, Upper Tribunal ×4,
First-tier ×10, EAT, SIAC, IPT, legacy tax/information tribunals). **Not one Scottish or
Northern Irish court.**

**But "no Scottish case law" is false, and P2.4 must not say it.** `court=uksc` returns
*Daly v His Majesty's Advocate (Scotland)*, *ABC v Principal Reporter and another
(Scotland)* and *X v Lord Advocate* — **Scottish appeals that reached the UK Supreme Court
are indexed.** What is missing is the **Court of Session (Inner and Outer House), Sheriff
Appeal Court, Sheriff Courts and High Court of Justiciary**, which is where the
overwhelming majority of Scots law is made. The blunt wording would make a lawyer distrust
a sound UKSC result; the precise wording also tells them where the one real Scottish route
is. P2.4 and P5.2 both amended to say it that way.

**A claim made and retracted in the same session — the fourth instrument error today, and
the first caught before it was written down.** I told the user "coverage effectively starts
around 2001; 1–5 judgments a year through the 1980s". That came from sorting the Atom feed
ascending and reading the oldest entries, which establishes that **a tail exists** and says
nothing about **density**. On checking, 1990–1994 filled a 50-result page — not a handful.
The feed caps at 50 for *every* window and neither the feed nor the search page exposes a
total, so **there is no census instrument available from outside** and the temporal floor is
**unmeasured**. Judgments do exist back to **1965**; that is all that is established.

**Consequences.** No row was created for it — a row asserting a floor I cannot measure
would be exactly the failure this log keeps recording. Instead it is now **question 3 to the
National Archives** in `WAVE5_QUESTIONS.md`: is the corpus comprehensive from a particular
year, with a selected set before it? CambeulW's recency-bias complaint (6363) may well be
sound, and **if it is, it affects English research too, not only Scots** — which nothing in
the plan currently covers.

**State of the branch:** `fix/prepilot-defects`, 17 commits this session (`eb5e921` →
`763566e`). **643 tests green, tree clean, NOTHING PUSHED** — the whole-plan-then-one-push
policy (Session 4, user) stands, so the target still runs the pre-pilot code including the
jurisdiction-filter defect. Ledger: Waves 0 and 1 complete; **P1.6, P2.1, P2.6, P4.4, P5.1
and P5.3 done**; P0.4 and P5.2 at `[~]`; **P2.7, P3.5 and P3.6 opened this session**.

**Machine state a new session inherits:**
- **No uvicorn running** — stopped deliberately. Start a fresh one before any live work:
  Python loads modules at import, so a surviving server serves stale code. (This session
  proved the point: P2.6 was written after the acceptance server started and is therefore
  absent from `wave2_p21/`.)
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON,
  `tools/.replay_pin_state.json` gone, as it should be after a successful `restore`.
  **Re-pin before any measurement.**
- **Three gitignored replay directories:** `baseline/` (65 files), `wave1/` (41) and
  **`wave2_p21/` (12 — four sessions × three reps, P2.1's acceptance only, NOT a sweep)**.
  A Wave 2 sweep needs a **new** directory; `replay.py run` silently skips existing files.
- **Do NOT feed `wave2_p21/` to `replay_report compare`** — 4 sessions against 41 makes
  every total nonsense. Read it with `replay_report --dir <dir> halts`, which grades per
  halted turn and is the form P2.1's acceptance is stated in.
- **Provenance on `wave2_p21/`, recorded rather than hidden:** files say `git_head:
  7a1c79b` (P1.6's commit) because P2.1 was loaded by the server but committed minutes
  later as `4d3f4c1`; **P2.6 is NOT in those runs** (visible as `report_reformat_retries: 1`
  on halted turns); and a cosmetic plural fix landed mid-sweep, so multi-step notices read
  "was … it" where HEAD reads "were … they". None changes a graded condition.
- **`tools/lex_probe.py` is new** — re-runs P5.1's and P5.3's evidence
  (`--surface`, `--coverage`). Use it before trusting any claim in those rows.

**User knowledge recorded 2026-09-15, and it redirects P5.2.** The user recalls that **LEX
used to expose case law via the API and has since disabled access**, and that **Scottish
courts were not represented in that data anyway**. Recollection, not verified — but
consistent with the probe, which found populated `caselaw` collections behind
`/healthcheck` and no endpoint, and which cannot distinguish "disabled" from "never
exposed". **Consequence: do not plan around re-enabling the LEX route.** The LEX question
shrinks to a one-line confirmation and P5.2's real subject becomes **finding an alternative
case-law API**. Candidates, none assessed: **BAILII** (`ScotCS`/`ScotHC`/`ScotSC` — the
obvious technical fit, **but its terms restrict automated access, so read them before
designing anything**), the **Scottish Courts and Tribunals Service** (`scotcourts.gov.uk`,
check for a feed), and the commercial providers (a licence cost). Whatever is chosen must
clear the internet-restricted target's whitelist.

**Two standing hazards for whoever picks this up:**
1. **Ten instrument errors across five sessions**, four of them today, and one caught only
   because a second instrument disagreed. **A number that disagrees with what the code says
   should happen is the instrument until proven otherwise**, and a sparse sample of
   absences proves nothing about a corpus. Cross-check every census against a second route.
2. **Two claims were published and later retracted this session** — B14's "100% manufactured"
   and case law's "coverage starts ~2001". Both were confidently stated from one instrument.
   Before writing a number into `BASELINE.md` or a row, ask what would falsify it.

**What still needs a human, and nothing in the repo can do it:**
- **Send Wave 5.** `WAVE5_QUESTIONS.md` — P5.1 and P5.3 are answered but carry short
  residual lists; **P5.2 is the live one** and step 1 (ask the LEX team whether their
  case-law corpus is reachable and covers the Court of Session) is free and gates the rest.
- **P0.4's re-export is NOT available before the final push** (established 2026-09-15). The pre-pilot
  data lives only on the target, the new column lives only on this branch, no backup exists to
  restore locally, and the branch does not reach the target until the plan concludes. It is a
  **post-push** activity; confound 5 persists for the remaining pre-merge sweeps and must not be
  treated as a blocker for P2.2 or any Wave 2 acceptance.

**Next action:** ~~P2.2~~ — **see the P5.1 answer above first; it changes what Wave 2 and Wave 3 contain.** Then **P2.2** (B5, no bare negatives) — its `Depends on: P1.3, P2.1` is now
satisfied, and this session amended it to cover the negative drawn from an **incomplete**
search as well as from a filtered one. Note P2.3 depends on P2.2 and on P5.1's answer, so
sending the Wave 5 questions before starting P2.2 is worth the five minutes. **P2.7** is
available in parallel and is well-evidenced; **P2.5** is the other unblocked Wave 2 row and
its scope did not shrink (B4 rose 27 → 30 at P1.5). Do the **P0.4 re-export** before the
next full sweep if target access appears.

---

## Session 6 — 2026-09-15 — P2.2 (B5, no bare negatives), plus P3.7 opened and six instrument corrections

**Done:**
- **P2.2 complete, acceptance passed with one stated residual.** `src/utils/search_scope.py`,
  wired at three seams. Replay n=3 on 6409 and 6367 (`evidence/replay/wave2_p22_final/`,
  $5.32): **21 turns asserting a negative, 19 explained (90%)**, against **2 of 10 (20%)**
  on the same sessions in Wave 1.
- **New rows P3.7 and P2.8.** P3.7 — `/legislation/lookup`, the deterministic held/absent test. Four of the
  corpus's negatives ask "is this instrument, named by number, in the index?" and are
  answered by ranked keyword search, which cannot answer it.
- **P5.3's "UK SI 2026 ~0% held" retracted** and corrected to ~2%. It read as "nothing from
  2026 is held", and that is false.
- **711 tests** (643 → 711). `AUDIT_TRACE.md` amended.

**The row's premise was 0.5% of the bucket, and the measurement said so before any code was
written.** P2.2 was written against the missing zero-result nudge on `search_legislation` —
genuinely the only search tool without one. Post-Wave-1 that branch fires on **4 of 790**
searches, while **783 of 783** measurable searches are *windowed* (5 rows shown of a median
**141** ranked candidates), and **not one of the 44 measured bare negatives followed an empty
search**. Every one was drawn from a result set that had results, just not the wanted one.
Building only what the row described would have moved none of the forty-four and could still
have gone green on a loose detector.

**Surprises / deviations from FIX_PLAN:**

- **A fix at the tool seam does not reach the agent that writes the answer, and the first
  acceptance run is what proved it.** The Worker sees tool results; the **Manager sees only
  the worker's report** and the **DR synthesis only the step findings**. 6367 rep 1 carried
  the scope block in the Worker's context **27 times**, three of its four worker reports
  carried no scope language at all, and the answer told the lawyer that a search *"confirms"*
  that no SSIs prescribe the detail — the exact overclaim the block forbids. This is P2.1's
  "a fix at one site leaves the others open" in a second place, and it is why
  `worker_scope_block` exists: the facts are carried across the boundary in code, the same
  shape as `provision_url_block`.

- **Carrying the facts to the right reader got 56%, not 100% — so the disclosure became
  code.** Instruction-only moved explained negatives from 20% to 56%; the remaining 44% still
  told a lawyer something was not found without saying what had been looked for. Invariant 2
  arriving exactly on schedule. `answer_scope_footer` is one lawyer-facing line emitted on
  every researched answer.

- **The mechanical acceptance is now circular, and the write-up says so.** The footer
  satisfies all three conditions by construction, so `replay_report negatives` prints a second
  **model column** graded with the footer stripped off. **That column is unstable and must not
  be quoted as a result:** it swung **56% → 4%** between two sweeps the model could not
  distinguish, since the footer is appended after the model has finished writing. n=3 cannot
  produce that swing legitimately.

- **A product change corrupted the instrument measuring it — a new failure mode here.** The
  footer says *"anything reported above as not found was not found in this index"*, which
  trips `NEG_ASSERTED`. Selecting the denominator on the full answer therefore enrolled every
  researched turn, including purely positive ones: 23 → 34 negatives, and the model column
  crushed to 14%. **The denominator is a fact about what the model wrote**, so it is now taken
  from the footer-stripped prose. Worth generalising: every later row that emits text into an
  answer must ask what its own words do to the detectors already reading them.

- **Six instrument errors in one row, five of them under-reads.** (1) The first
  `NEG_ASSERTED` scored **61 of 153 turns, 100% failing**, by counting *"no winding-up order
  may be made, except by the company's directors"* — a correct statement of retrieved law — as
  a bare negative; grading those would have pushed the model to hedge findings it had actually
  retrieved, the regression Invariant 1 exists to prevent. (2)+(3) `terms` demanded "searched"
  adjacent to "for", then demanded quotation marks; *"A search of the legislation index for
  commencement regulations did not return any results"* names its terms perfectly well.
  Patching twice failed twice, so it was rebuilt as **sentence-level co-occurrence** rather
  than a guess at phrasings. (4) `index` was defeated by a 158-character instrument title —
  and note the general trap: **every commencement SSI's title contains a full stop
  ("Commencement No. 1"), so any sentence window keyed on `.` cannot cross the titles this
  corpus is about.** (5) `limits` demanded the model recite an **inert** `year_to = 2026` that
  excluded nothing; it is now `n/a` where no filter could have bitten. Every correction was
  re-validated against Wave 1, which moved only 44/44 → 44/38 failing.

- **The footer's first rendering exposed two defects unit tests had not.** It printed
  `""Water Industry Commission for Scotland""` (the model quotes its own query; wrapping it
  again doubles the quotes, and the quoted and unquoted forms listed as two searches), and
  *"filters in force: years any-2026"* — **telling a lawyer a constraint was in force that was
  not**. An overstated limit invites re-running a search that was never narrowed. The
  lawyer-facing line now names only filters that could actually have excluded something; the
  agent-facing block still reports every parameter, deliberately.

- **The two remaining failures are the same shape, and they became a row (P2.8).** Both are
  turns with **zero delegations** — a negative carried forward from an earlier turn (*"As noted
  in the previous search, SSI 2025/377 is not currently available…"*). No search ran, so no
  footer fired: the footer is per-turn and a conversation is not. **2 of 21 negative turns, and
  the rate will be higher in real use than in a replay**, because a lawyer follows up more than
  a script does. Booked as **P2.8** rather than a note, per the re-planning protocol — it is
  measured, reproducible and has a known mechanism. Note what NOT to do: emitting the footer on
  every turn regardless would describe searches that did not happen, which is a worse lie than
  silence.

- **P5.3's coverage headline was wrong in the direction that matters.** "UK SI 2026 ~0% held"
  reads as *"nothing made in 2026 is in the index"*. `/legislation/search` returns **27
  distinct `uksi/2026/*`** instruments and **all 12 spot-checked resolve on lookup**; a
  60-point census puts it at ~2%. Low single digits, not nothing — so the product string says
  **"under 5%"** and never "none", because a lawyer told "none" stops looking. Caught by the
  cross-check P5.3's own method warning prescribes, applied to P5.3's own headline.

- **The replacement coverage figure was falsified the next day, by the same command.** "Under
  5%" went into the product string from one 60-point sample of SSI 2026 (1/60). Re-running
  `lex_probe --coverage` on 16 Sep returned **5/60 — 8%**. That is ordinary noise at n=60 and
  it is enough to make a claim false in a string a government lawyer reads. **Every coverage
  figure in the product is now a bound chosen to survive the spread** ("roughly 85%", "under
  10%"), not the last number measured, and a test pins the hedging words. The general rule,
  which cost two corrections in two days to learn: **a sampled rate quoted at a user needs a
  bound, not a point estimate** — and widen the bound rather than chase the sample.

- **The probe now runs its own cross-check instead of recommending one.** `lex_probe
  --coverage` was still executing the 20-point census that produced the retracted headline, so
  a future session re-running the documented command would have got the wrong number back.
  Samples are 60 points, and the `/legislation/search` cross-check that caught the error runs
  every time. Same principle applied to `replay_report negatives`, which now prints the search
  shape (790 calls, 4 zero-result, 783/783 windowed, median 141) — those numbers decided this
  row's design and had existed only in throwaway scripts. **A number with no command behind it
  cannot be checked by the next session.** Note the count was `785` in the first write-up and
  is `790`: the script skipped turns with empty answers.

- **Verified at source, and it settles 6373 and 6409 turns 9-11:** `ssi/2026/170` and
  `ssi/2025/377` are **both 404 in LEX**, `ssi/2025/119` is held. FrankieH's citation was right
  and AILA asked her to check it. Across 23 opportunities in the acceptance sweep, **no run
  blamed a lawyer's citation** (Wave 1: 2 of 10 on these two sessions, 3 of 44 overall).

**Decisions taken this session:**
- **The footer is unconditional on any turn that searched**, not gated on a detector that
  decides the answer contains a negative. A prose detector in the *product* fails silently —
  an unrecognised phrasing means no footer and no signal — and that is the trap this work has
  hit eleven times. The cost is a line of provenance on answers that found what they were
  looking for. **This is the decision most open to being overruled.**
- **Keep `NOT_FOUND` and `NEGATIVE_EXPLAINED` untouched** and report `bare_negatives`
  alongside the new conditions, rather than retightening a metric in place — the rule set when
  `provision_links_reconstructed` was added beside `provision_links_manufactured`.
- **`/legislation/lookup` is a new row, not scope creep into P2.2.** P2.2 can only make a
  negative honest; P3.7 is the only thing that can make it definite.

**State of the branch:** `fix/prepilot-defects`. **711 tests green, NOTHING PUSHED** — the
whole-plan-then-one-push policy stands, so the target still runs the pre-pilot code. Ledger:
Waves 0 and 1 complete; **P1.6, P2.1, P2.2, P2.6, P4.4, P5.1 and P5.3 done**; P0.4 and P5.2 at
`[~]`; **P2.8 and P3.7 opened this session**.

**Machine state a new session inherits:**
- **No uvicorn running** — stopped at the end of the session. Start a fresh one before any
  live work: Python loads modules at import, so a surviving server serves stale code. **This
  session proved the point three times over**: three sweeps were aborted and restarted because
  wording changed after the server booted, and it is far cheaper to restart than to publish an
  acceptance against code that is not HEAD.
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON, no pin file.
  **Re-pin before any measurement.**
- **Five gitignored replay directories:** `baseline/` (65), `wave1/` (41), `wave2_p21/` (12),
  **`wave2_p22/` (6 — P2.2's instruction-only sweep, the 56% column)** and
  **`wave2_p22_final/` (6 — P2.2's acceptance, the 90% column)**. Neither Wave 2 directory is a
  sweep; do **not** feed them to `replay_report compare`. Read them with `replay_report --dir
  <dir> negatives` (and `halts` for P2.1).
- **`wave2_p22/` was run against code without the footer** and is kept deliberately: it is the
  only measurement of what the instruction achieves on its own, and the row's argument for the
  footer rests on it.

**Spend this session: ~$11.4** on replay — $4.97 (instruction-only acceptance), $5.32 (final
acceptance), $0.52 (a single 6367 probe run), plus ~$0.6 of aborted partial sweeps. **Three
sweeps were aborted and restarted** because wording changed after the server had booted; each
abort cost a few minutes and a few dollars, and each was cheaper than publishing an acceptance
against code that was not HEAD. Budget for that when planning a row whose fix is a string.

**Next action:** **P2.4** is the cheapest — P5.2's probe already wrote its exact wording, and
this session verified the two citations it turns on. **P2.3** is the one that matters, because
it unblocks **P3.5** (`/amendment/search`), the highest-value row on the page. **P2.7** is
available in parallel. **P0.4's re-export remains post-push** and blocks nothing.

---

## Session 7 — 2026-09-16 — P2.3 (B3b, unverified "made under"), plus a P2.2 defect fixed

**Done:**
- **P2.3 complete, acceptance passed.** Turns asserting an **unverified** derivation
  fell **12 of 28 (43%) → 2 of 29 (7%)**; unverified claims 18 → 3; and **both
  survivors carry a code-emitted line saying so, where none of the twelve before
  them did.** `evidence/replay/wave2_p23/`, n=3 on 6340/6374/6382/6383, 12 runs,
  **$7.10**, 1 h 5 m, zero model mismatches.
- **P3.5 is now unblocked** — the highest-value row on the page.
- **764 tests** (712 → 764). New tooling: `lex_probe --enabling`,
  `replay_report derivations` (with `--drops`).

**Two of the three findings handed to this row did not hold, and one decided the
design.**

- **The "retrieved preamble" route EXISTS.** The handover recorded it as absent,
  on the strength of `/legislation/text` for `ssi/2020/295` returning 545 chars
  of `full_text` opening at "Section 1) Citation and commencement". That is right
  about `full_text` and right about that instrument, and **the conclusion drawn
  from it is wrong**: the recital lives in `legislation.description`, and
  `get_legislation_text` returns the response unslimmed. **6340 rep 1 had already
  been using it** — it read `uksi/1979/766`'s preamble verbatim and reported its
  enabling powers correctly. The one turn in the whole corpus that makes a
  *supported* derivation claim is in the session the row was written against.
- **So P3.6 is not a prerequisite**, and the decision is recorded rather than
  assumed. P3.6 moves the same field to Phase 1 — worth having for commencement
  dates and for cheapness, not for reachability.
- **But the rule is a near-total prohibition and now says so in the product.**
  `lex_probe --enabling` (new, 103 instruments, 2026-09-16): `uksi` pre-1990
  **18/25**, `uksi` 1990-2009 **0/25**, `uksi` 2010+ **0/25**, `ssi` 1990-2009
  **0/13**, `ssi` 2010+ **0/15**. **Zero for Scottish instruments in either
  era** — the corpus these lawyers work in. Over the whole post-Wave-1 replay
  corpus (**38.8M chars of raw retrieval, 2,504 tool results**) only **12
  results carried an instrument preamble**, covering **6 distinct instruments,
  every one in session 6340**. ~~33M chars, 1,907 results, exactly two recitals~~
  — **corrected below, and it is the fifteenth instrument error.**

**Surprises / deviations from FIX_PLAN:**

- **B3(b) is a defect surface Wave 1 OPENED, and the baseline column proves it
  rather than flattering it.** `baseline/` scores **0 of 222** answered turns
  asserting a derivation — which looks like a perfect before-column and is
  nothing of the kind. Pre-Wave-1 the jurisdiction filter emptied the searches,
  so there was nothing retrieved to derive from and 6382/6383's answers are all
  negatives. Fixing retrieval is what gave the model instruments to make claims
  about. **A wave-over-wave number can improve because the system got worse.**

- **"A provision" cannot be a permitted route, and measuring it is what showed
  that.** The row allowed a claim supported by "a retrieved preamble, provision
  or `description`". 6374 produced what looked like the middle case — it said
  *"Both confirm the Orders are made under section 126(8)"*, and s.126(8),
  retrieved, does say offices may be "specified in an Order in Council made under
  this subsection". A screen for that fired on **11 of the 12** before-column
  unverified turns, because generic regulation-making boilerplate is in
  essentially every enabling Act, so the signal is present whenever the parent
  Act was retrieved at all. It could not separate 6374's short sound inference
  from 6383's *"Over 130 instruments explicitly cite section 95 in their
  preamble"*. **Deleted, with the reasoning left in place of the code, and the
  ROW narrowed instead: a provision states the CLASS, never the INSTANCE.** Only
  a preamble or a `description` names an individual instrument.

- **The same full-stop trap, twice more, and the acceptance run is what found
  both.** SESSION_LOG already records it for `NEG_BLAMED_INDEX`. (1) The sentence
  splitter cut *"For example, S.I. 1963/2111 was made under section 69(4) of the
  National Insurance Act 1946"* into `"For example, S."`, `"I."`, `"1963/2111 was
  made under …"` — the fragment keeping the predicate had lost its instrument.
  (2) With the sentence intact, *"Commencement **No.** 1"* then tripped `\bno\b`
  and the claim was filtered as negated. Both are **under-reads that would have
  scored the acceptance run's three supported claims as no claims at all**, in
  the row whose job is to count them. **Fourteen instrument errors across seven
  sessions now.**

- **Every correction was re-validated against all four historical directories and
  not one before-column number moved.** That is the check that none of them was
  tuned to pass, and it is cheap — four commands.

- **Invariant 1 held in both directions, and that was the real risk of this row.**
  A prohibition on asserting a relation invites the model to hedge things it
  actually retrieved. It did not: **answers grew in 8 of the 10 turn slots**,
  6383's conversational turns roughly doubling (548→1,377, 604→1,380, 614→1,570
  chars) because the model now explains the gap instead of asserting across it.
  6382 still delivers the substantive finding it was asked for (SSI 2019/29
  carries the "£" symbol in regs 11-13; four others do not) while saying the
  enabling power cannot be confirmed. And 6340 asserts **supported** derivations
  in all three reps, now phrased *"explicitly states it was made under …"* — the
  attribution the block asks for.

- **The best answers now explain the mechanism, not just the limit.** *"The
  reason it did not appear in the initial search is that our legislation index
  does not record the enabling powers … instruments that only cite the enabling
  power in their preamble (which is not indexed) were missed."* That tells a
  lawyer what to do next, which a bare limit does not.

- **A review before the sweep found the fix wired to the rare route.** The
  enabling-power record was on `get_legislation_text` only — 32 calls across the
  corpus against **628** `search_legislation_sections` calls — so the report
  block and the lawyer-facing clause would have been silent on almost every turn
  where a claim can arise, including most of 6383's. Both routes are recorded
  now; only `get_legislation_text` can ever set `stated`, because a preamble is
  not a ranked provision.

- **The strip needed widening, and that was a live defect**: `[ENABLING POWER …]`
  is not `[SEARCH SCOPE …]`, and `_TOOL_BLOCK` matched only the latter. Without
  the change an agent-facing block would have rendered to a lawyer. Found by
  writing the test, not by the sweep.

- **P2.2's footer had a defect this sweep put in front of a lawyer.**
  `answer_scope_footer` stripped only the OUTER quotes from a query, so the
  model's own field syntax rendered as `"Education (Scotland) Act 1962" 117"` —
  unbalanced, and reading as two searches where there was one. Fixed and pinned;
  the change is display-only and post-acceptance, and the detectors grade
  footer-stripped prose, so it does not disturb the numbers above.

- **The sweep was aborted once and restarted, deliberately.** A pre-sweep review
  changed product code after the server had booted. The change was checked and
  found immaterial to these four sessions — every `get_legislation_text` call in
  them returns 200 — and the sweep was restarted anyway, for one file and about a
  minute, because "the acceptance ran against HEAD" should not need an argument
  about materiality to be true. Session 6 aborted three sweeps for the same
  reason.

- **New row P2.9, and it is a defect in a shipped fix.** `run_worker_tool` returns
  early on a **tool-memo hit** and that path does not call `record_search`. The memo
  is per-REQUEST; `search_log` is per-WORKER-RUN. So when a Deep Research step
  repeats a search an earlier step already made, that query never enters its own
  run's record and is therefore absent from `worker_scope_block` and from the
  lawyer-facing `answer_scope_footer` — **P2.2's disclosure under-reports what was
  searched.** Measured over all four post-Wave-1 directories: 23% of
  `search_legislation` calls are memo hits, and **78 of 358 worker runs (22%) lose
  at least one query from their own record — 150 distinct queries across 47
  turns.** Found while wiring P2.3's record alongside it; deliberately NOT fixed
  here, because the one-line fix moves P2.2's published footer contents and needs
  its own before/after. P2.3's `record_enabling_power` is called on both paths.

- **A published number of my own was wrong, and putting the numbers behind a
  command is what caught it — the fifteenth instrument error.** I wrote "33M chars
  of raw retrieval, 1,907 tool results, exactly **two** instrument-level recitals,
  both in 6340". Two errors: the counts silently **omitted `wave2_p21`** while
  claiming to describe the whole post-Wave-1 corpus, and the screen that produced
  "two" required `Act <year>` to follow the phrase, which misses the 1963 form
  *"Whereas the Treasury has determined under section 69(4) of the National
  Insurance Act 1946(a) …"*. The true figures are **38.8M chars over 2,504 tool
  results, 12 results carrying an instrument preamble, covering 6 distinct
  instruments — every one of them in session 6340**. The qualitative claim
  survives and is **stronger**. Corrected in all four places it was published.

- **`replay_report corpus` is new, and exists because of the above.** Session 6's
  rule — *a number with no command behind it cannot be checked by the next
  session* — and P2.3 published six such numbers out of throwaway scripts: raw
  retrieval volume, how many preambles it ever contained, whether `description`
  survives slimming (**0 of 7,399 search rows**), which route the Worker actually
  uses to touch an instrument, and what the memo costs P2.2's record. The scripts
  were in a scratch directory that does not survive the session. They are one
  command now.

**Decisions taken this session:**
- **P3.6 is NOT a prerequisite for P2.3** — the permitted branch is already
  reachable through `get_legislation_text`. Recorded in the row so the ordering
  is not re-derived.
- **The permitted branch is narrowed from three routes to two** (preamble or
  `description`, never "a provision"), on the 11-of-12 measurement above.
- **The lawyer-facing clause is gated on a STRUCTURAL fact** — did this turn
  retrieve an instrument — and never on a prose detector deciding whether the
  answer contains a derivation claim. A prose detector in the product fails
  silently. The measured cost is one gap: **12 of 13** before-column claim-turns
  retrieved an instrument, so a turn naming instruments from search rows alone
  gets no clause. Closing it would fire the clause on nearly every legislation
  turn for an 8% gain. **Left as a limitation.**
- **The known under-read is stated, not patched**: an anaphoric subject (*"It is
  made under powers including section 95"*) is not counted, because admitting
  `it` as an instrument reference would be unboundedly over-broad. It under-reads
  before and after equally.

**State of the branch:** `fix/prepilot-defects`. **764 tests green, NOTHING
PUSHED** — the whole-plan-then-one-push policy stands, so the target still runs
the pre-pilot code. Ledger: Waves 0 and 1 complete; **P1.6, P2.1, P2.2, P2.3,
P2.6, P4.4, P5.1 and P5.3 done**; P0.4 and P5.2 at `[~]`; **P2.9 opened this
session**. **P3.5 is unblocked and is the row to take next.**

**Machine state a new session inherits:**
- **No uvicorn running** — stopped at the end of the session. Start a fresh one
  before any live work; this session restarted once for exactly that reason.
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON, no pin
  file. **Re-pin before any measurement.**
- **Six gitignored replay directories:** `baseline/` (65), `wave1/` (41),
  `wave2_p21/` (12), `wave2_p22/` (6), `wave2_p22_final/` (6) and
  **`wave2_p23/` (12 — P2.3's acceptance)**. None of the wave2 dirs is a sweep;
  do **not** feed them to `replay_report compare`. Read them with
  `replay_report --dir <dir> derivations` (`--drops` for the both-directions
  audit), `negatives` for P2.2, `halts` for P2.1, and **`corpus`** for the
  retrieval shape every P2.3 number was drawn from.

**Spend this session: ~$7.2** on replay — $7.10 for the acceptance plus ~$0.1 of
the aborted restart. Cheaper than Session 6 because the four sessions are short;
6374 is the expensive one at ~$1.30 a rep (two Deep Research turns).

**Next action:** **P3.5** (`/amendment/search`) — unblocked by this row and the
highest-value row on the page, with its design notes already written from P5.1's
probe. **P2.4** remains the cheapest; **P2.7** and **P2.8** are available in
parallel. **P5.2 is the live external one** and the LEX-team question is free.

---

## Session 8 — 2026-09-16 — P3.5 (B3, the relationship retrieved), plus a P2.2 defect fixed

**Done:**
- **P3.5 complete, acceptance passed.** Turns delivering the commencement
  relation went **0 of 8 → 24 of 24**; flat false negatives **6 of 8 → 0**;
  tool calls per answered turn **10.4 → 4.4**. `evidence/replay/wave3_p35/`,
  n=3 on 6409/6410/6383, 9 runs, **$4.10**, 37 min, zero model mismatches.
- **`/amendment/search` is the fourth LEX endpoint AILA calls**, as the
  `get_legislation_changes` worker tool. B3 — the largest bucket — is retrieved
  rather than disclosed.
- **833 tests** (764 → 833). New tooling: `lex_probe --commencement`,
  `replay_report commencements` (with `--drops`).

**Three of the facts handed to this row did not survive contact with the feed,
and two of them change what the tool reports.**

- **35% of rows are `http`/`https` duplicates of ONE relation**, and the API's
  own `id` embeds the scheme, so a dedupe keyed on it removes nothing. 6,738
  rows over eight instruments → 4,363 distinct, and it is concentrated in the
  Scottish material: `asp/2025/2` 71 rows for 36 relations, `asp/2018/9` 956 for
  484, `asp/2014/18` 607 for 309, while `ukpga/1998/46`, `asp/2000/1` and
  `ukpga/1981/67` have none at all. **The handover's "15 commencements by
  `ssi/2025/119`" is that double count** — it is 8 by SSI, seven by
  `ssi/2025/119` and one by `ssi/2025/377`. A tool that counted rows would have
  told a lawyer roughly double.
- **The cap can be fetched past, cheaply, so the tool does that rather than
  stating a window.** Over the legislation_ids the replay corpus actually
  touched (272 at the last run): median 12 relation rows, p90 870, **13 (4.8%) over 2,000** — and
  every one of those completes at 20,000 (largest 5,185 rows / 5.3 MB / 2.3 s).
  So the row's "either fetch past the cap or state the window" resolves to the
  first, with the second kept for a bind never observed.
- **`type_of_effect: null` is labelled, not dropped**, decided explicitly as the
  row asked. The row still records that an instrument changed a provision, so
  dropping it would make the tool the reason a relation went missing — the one
  thing a slimmer must never be.

**Surprises / deviations from FIX_PLAN:**

- **The change graph knows about instruments the text index does not hold.**
  `ssi/2025/377` is a **404 on `/legislation/text`** — it is the instrument 6409
  was asked three times to re-check, and P2.2's module docstring records the
  404 — yet `/amendment/search` returns it commencing s. 18 of `asp/2025/2`. So
  a relation can be retrieved for an instrument whose text cannot be. The
  acceptance answers say so explicitly: *"SSI 2025/377 (the exact title is not
  currently held in the index, but it is recorded as bringing section 18 into
  force)"*.

- **The before-column is zero in every wave, and P2.2 is why it looks different
  rather than better.** `baseline/` 0 of 8, `wave1/` 0 of 8,
  `wave2_p22_final/` 0 of 18. What P2.2 changed was the **shape** of the
  failure: the flat *"No commencement regulations have been made yet"* became
  *"A search of the legislation index … did not return any results"* — honest,
  properly scoped, and still not the answer. That is why the headline metric is
  **delivered**, a fact check against an external ground truth needing no prose
  classification, and the false/limited/silent split below it is diagnosis.

- **Picking the denominator was the hard part, and the first draft got it
  wrong in the flattering direction.** Grading every answered turn scored six of
  `wave1`'s eighteen as correct — including **6409 turn 8, whose entire question
  is "SSI 2025/119"**. Repeating back an instrument the lawyer supplied is not a
  retrieved relation. In scope now means the *question* asks about commencement
  and does not itself name one of the graded instruments.

- **One detector correction, and the scoping of it is the whole lesson.** 6410
  rep 2 turn 2 named `ssi/2025/388` and added *"no further commencement
  regulations have been found"* — true, sourced, and exactly the answer the row
  exists to produce. A denial of the **remainder** is not a denial of existence.
  But `wave2_p22` 6409 rep 3 turn 6 says *"no commencement regulations bringing
  **further** sections into force were identified"*, where the qualifier attaches
  to *sections* and the sentence is a flat denial. **A bare `\bfurther\b` would
  have dropped it and moved a BEFORE-column number to make the after-column look
  better.** The exclusion is scoped to the noun phrase and requires the turn to
  name a real instrument; re-run over all six historical directories, **not one
  before-column number moved.**

- **Invariant 1 held in both directions, which was this row's real risk.** A
  retrieved relation invites over-claiming where P2.3's prohibition invited
  hedging. Answers **grew in 13 of 17 matched turn slots**, no scope block
  leaked in any of 51 answers, and P2.3 did not regress (1 of 51 turns asserts
  an unverified derivation, against 2 of 29 in its own acceptance). The four
  slots that shrank are the model no longer padding a non-answer — and **6409
  turn 10 stopped questioning a correct citation**, which is P2.4's exact
  failure, going from *"Are you certain of the SSI number and year?"* to
  confirming it against the change record.

- **P2.5 is answerable today, and one rep proved it unprompted.** The relation
  carries no date, and the tool block tells the model to retrieve the commencing
  instrument if the question turns on one. 6409 rep 2 did exactly that: it
  called `get_legislation_text` on `ssi/2025/119` and reported *"these sections
  came into force on 10 May 2025"*, which is verbatim in that record's
  `description`. P2.5 is now about making that hop reliable, not about finding a
  route.

- **A P2.2 defect this sweep exposed, and it was on half of all turns.** The
  footer is prose, so `strip_scope_blocks` leaves it alone — correctly. It then
  travels into the next turn's history, the model reproduces it verbatim, and
  the code appends its own. **18 of 36 answered turns in `wave2_p22_final` carry
  it twice (50%)**, against **0 of 51** after the fix. Found by reading a smoke
  run rather than by any detector, because every detector already strips from
  the first footer to the end of the answer.

- **The sweep was aborted once and restarted, deliberately — the fourth time in
  three sessions.** A pre-sweep review changed product code (a distinct id per
  HTTP call, a guard on the window stamp) after the server had booted. Neither
  change can fire for these three sessions — no instrument among them is
  cap-bound and every response is the expected shape — and the sweep was
  restarted anyway, costing about $1.50 and fifteen minutes, because "the
  acceptance ran against HEAD" should not need an argument about materiality.

- **Two bash-level own goals worth recording, because both wrote invisible
  damage.** Generating Python with regexes inside a **non-raw** string wrote
  literal backspace characters (`\x08`) where `\b` was intended — eight of them,
  in a detector, silently making `\bno\b` into `no`. It showed up as the
  detector reading **zero** denials in `wave1` where six exist. Checked for with
  `sum(1 for c in s if ord(c) < 9 or 13 < ord(c) < 32)` and now zero across every
  file touched.

- **A published number of my own was wrong, and putting it behind a command is
  what caught it — the same pattern as Session 7's.** I wrote "31% duplicates
  over 6,266 rows". The script that produced it asked for `size=2000`, which
  **truncated `ukpga/2010/15` at 2,000 of its 2,472 rows** — so the measurement
  that justified escalating past the cap had itself been capped. The true figure
  over the full data is **35% over 6,738 rows (4,363 relations)**. It is now
  printed by `lex_probe --commencement`, which is how it was found, and the
  qualitative claim is unchanged and slightly stronger.
- **And the Invariant 1 comparison had the same shape of error.** Its first
  version selected the before-column on "has a ground truth", which let `wave1`'s
  **6382** into a comparison whose after-column has no 6382 at all, moving the
  tool-rate from 10.4 to 13.4. It compares the **shared sessions** now. Two
  populations are not a before and an after.

**Decisions taken this session:**
- **One tool, not two.** `/amendment/section/search` narrows the same data from a
  `provision_id`, and the instrument-level endpoint already returns
  provision-level rows on both sides, so it is a filter over data already held.
  Every acceptance session is instrument-level. Recorded rather than left
  unasked.
- **No `type_of_effect` filter argument.** The `effects` histogram plus the
  grouping makes narrowing unnecessary, and a wrong effect string would return
  nothing — a silent false negative, which is the failure mode Invariant 1
  forbids.
- **Provision labels, not provision URLs.** 45-70 KB on the large Acts against
  3.7 KB on `asp/2025/2`, for a citation form a commencement answer does not use.
  Measured cost: **1 of 51 turns** carries a P1.6 dagger.
- **Unclassified for phase**, like `get_member_info`. Counting it Phase 2 would
  raise `phase2_retrieval_calls` without raising `sources_kept` and move every
  efficiency number published in Waves 0-2, against which later rows are
  measured. Still counted in `worker_tool_calls` and still keyed for redundancy.
- **Keyed for redundancy on `legislation_id` + `direction`**, because the two
  directions are different questions (`asp/2025/2` returns 36 one way and 143 the
  other) and `max_redundant_tool_calls` is 0 on this profile.
- **Admitted to `CACHEABLE_TOOLS`** after the check the allowlist exists to
  force: a `legislation_id` and a direction in, published statutory data out, no
  user content on either side.

**State of the branch:** `fix/prepilot-defects`. **833 tests green, NOTHING
PUSHED** — the whole-plan-then-one-push policy stands, so the target still runs
the pre-pilot code. Ledger: Waves 0 and 1 complete; **P1.6, P2.1, P2.2, P2.3,
P2.6, P3.5, P4.4, P5.1 and P5.3 done**; P0.4 and P5.2 at `[~]`.

**Machine state a new session inherits:**
- **No uvicorn running** — stopped at the end of the session. Start a fresh one
  before any live work; this session restarted three times for exactly that
  reason.
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON, no pin
  file. **Re-pin before any measurement.**
- **Seven gitignored replay directories:** `baseline/` (65), `wave1/` (41),
  `wave2_p21/` (12), `wave2_p22/` (6), `wave2_p22_final/` (6), `wave2_p23/` (12)
  and **`wave3_p35/` (9 — P3.5's acceptance)**. None of the wave2/wave3 dirs is a
  sweep; do **not** feed them to `replay_report compare`. Read them with
  `replay_report --dir <dir>` plus `commencements` (P3.5, `--drops` for the
  both-directions audit and **`--before <dir>` for the Invariant 1 check** —
  did the answers shrink to buy the number, compared over the sessions the two
  directories SHARE), `derivations` (P2.3), `negatives` (P2.2), `halts` (P2.1)
  and `corpus` (retrieval shape, block leaks, duplicated footers, P1.6 daggers).
- **`python -m tools.plan_status`** prints where the ledger stands — by wave, by
  bucket, and weighted by the sessions each bucket was the primary diagnosis
  for. Added at the end of this session because the progress view was being
  re-derived by hand, and a summary in prose goes stale the moment a row is
  ticked. It reads `FIX_PLAN.md` and `classification.json` live and costs
  nothing.

**Spend this session: ~$5.8** on replay — $4.10 for the acceptance, ~$1.5 for the
aborted first attempt, $0.07 for the smoke run and ~$0.1 of probes. The LEX
probing itself is free.

**Next action:** **P2.5** is the row this one most changed — the commencement
date is reachable by a second hop that one acceptance rep made unprompted, so
that row is now about reliability rather than discovery. **P2.4** is still the
cheapest and now has fresh evidence (6409 turn 10). **P2.9**, **P2.7**, **P2.8**,
**P3.6** and **P3.7** are all open. **P5.2 is the live external one** and the
LEX-team question is free.

---

## Session 9 — 2026-09-16 — P2.5 (B4, in-force status), plus a P3.5 trap closed

**Done:**
- **P2.5 complete, acceptance passed.** Turns asserting currency with no
  commencement relation retrieved went **7 of 24 to 0 of 42**; assertions
  citing a text version as the evidence **13 to 0**. P3.5's win survived
  intact (the commencement relation still delivered in **6 of 6** in-scope
  turns), and **18 of 24 matched turn slots grew**.
- **B4 closes**, and with it the last partial bucket in Wave 2 apart from B5.
- **A trap P3.5 left open is closed**: `Commencement Order` is not the subject's
  commencement, and `ukpga/1998/46` has 29 of them and no `coming into force`
  row at all.
- **957 tests** (939 → 957). New tooling: `lex_probe --inforce [--full]`,
  `replay_report currency` (with `--drops` and `--before`).

**Three of the six facts written into this row at the end of Session 8 did not
survive measurement, and two of them changed the build.**

- **`ukpga/1998/46` does NOT have "857 relations and zero commencement rows".**
  It has **29 `Commencement Order` relations**. Session 8's probe filtered
  `type_of_effect == "coming into force"` exactly, which is right for the
  question P3.5 asked and hid this one. **The handover's conclusion survives for
  a better reason than it gave, and the difference is a trap:** across the
  **1,355** such relations the corpus produces, `changed_provision` is one of
  **eight placeholder values** (`specified amended provision(s)` 1,068, `None`
  199, `C/O` 73, `specified provision(s)` 11, four variants, one `Act`) and
  never a provision of the subject — against 5,180 distinct real provisions over
  19,031 `coming into force` rows. The row means *another Act's commencement
  order brought into force an amendment TO the subject*: `ssi/2001/81`, the
  Adults with Incapacity (Scotland) Act 2000 (Commencement No. 1) Order 2001,
  appears against `ukpga/1963/41` because `asp/2000/4` substituted words in its
  s. 90(1). `uksi/1999/1075` is the *Road Traffic (NHS Charges) Act 1999*
  Commencement Order and appears against the **Scotland Act 1998**. P3.5's block
  invites the model to state any relation the record lists, citing the
  instrument named against it — so left merged, the fix for 6411's unsourced
  *"the Scotland Act 1998 (Commencement) Order 1998"* would have been a
  **differently-sourced wrong answer**.
- **The `status` vocabulary is three values, not two**: `final` 60.3%, `revised`
  38.8%, **`stub` 0.9%** over 15,160 model-visible search rows. P1.2's row and
  its test docstring both said two. The conclusion is unchanged and slightly
  stronger.
- **The title marker is a flag, not a date route.** 258 of 15,160 rows (1.7%),
  43 distinct titles, and a date on **8 of the 258**. It is **asymmetric** —
  present means not in force, absent means nothing — and the first draft of this
  row's own detector used it symmetrically, grading 6411's *"Yes, the Scotland
  Act 1998 is in force"* as SOURCED because an unrelated repeal-marked row
  ranked on the same page.

**Surprises / deviations from FIX_PLAN:**

- **The fix provoked its own evasion, and the second smoke run caught it.** With
  "in force" prohibited, the model came back with *"Yes, the Scotland Act 1998
  IS IN OPERATION and remains a fundamental pillar of the UK constitution"*,
  sourced to a 2026 UKSC judgment that *"confirms its ACTIVE STATUS"*. Same
  proposition, different words — and the second half is **6411's original
  diagnosis verbatim**: *determined in-force status by reference to case law*.
  The rule now prohibits the proposition rather than a form of words, names the
  paraphrases, and forbids inferring currency from a judgment. A detector blind
  to the evasion its own fix causes would have read zero and published it.

- **The site with no instruction was the site with the defect.** The row warned
  against assuming P2.3's and P3.5's three-prompt symmetry. That was right about
  the Status *lines* — three different sites, two worker prompts and the DR
  synthesis — and wrong about the *rule*: `WORKER_SYSTEM_PROMPT_CONVERSATIONAL`
  had no in-force instruction at all, and `get_worker_system_prompt` returns it
  whenever `_chat_mode == "conversational"`, **which is the mode 6411 ran in**.

- **And quick-lookup mode never called the route, which is P3.5's gap.** P3.5
  appended `_RELATIONSHIP_RULE` to all three worker prompts but gave a PHASE 2b
  only to `WORKER_SYSTEM_PROMPT`. The conversational prompt's phases name four
  tools, say "keep it tight" and explicitly forbid one fallback — so the model
  follows the phases. Asked *"Is the Scotland Act 1998 in force?"* it made four
  calls, none of them `get_legislation_changes`, and then wrote that the answer
  *"would require retrieving its specific change records"*. It knew the route
  and the prompt had routed it away. A conditional PHASE 2b fixed it in one
  call.

- **A fourth lead, chased and closed so the next session need not.** The effect
  STRING does carry dates — `saved (6.5.1999)`, `amended (1.7.1999)`,
  `repealed (1.1.1996)` — so P3.5's flat *"there is no DATE on any relation"*
  reads wrong. Over all 272 corpus legislation_ids in both directions:
  **552 of 89,465 relations (0.6%) embed a date, and 0 of the 19,031 `coming
  into force` rows do.** P3.5's statement stands exactly where it matters and
  the second hop is still required.

- **The instrument was wrong EIGHT times, in both directions, and every one was
  found by reading output rather than by trusting a number.** (1) The title
  marker used symmetrically, grading 6411's claim as SOURCED off an unrelated
  repeal-marked row on the same search page. (2) `_CUR_ASSERT`'s Status-bullet
  branch matches a sentence merely *starting* with "In force", so **"In-force
  status: not verified"** — the sentence the fix produces — scored as the defect;
  `_CUR_NEGATED` catches the no-colon form and misses that one because its
  character class excludes `:`. (3) The first guard for that matched any negated
  establishment verb anywhere, which would have dropped *"While we cannot verify
  every provision, the Act is currently in force"* — a false negative in the
  flattering direction. (4) A **bare section heading** — `*   **In-Force
  Status:**` — read as an assertion, because `_sentences` splits by line.
  (5) The distance windows between subject and negation were set from a sample
  and a 95-character parenthetical list broke them. (6) `_CUR_SUBORDINATE` had
  no adverb slot where `_CUR_ASSERT` has one, so *"To determine if a specific
  section is currently in force…"* counted — two patterns that must agree about
  a phrase, only one of which knew about adverbs. (7) Adding that slot then
  over-corrected and swallowed a concessive clause followed by a main-clause
  assertion; **the comma settles it** — the trigger and the phrase must be in
  the same clause. (8) An infinitival purpose clause, *"To establish exactly
  which provisions are currently in force today, you would need to consult the
  specific commencement orders"*, counted because no trigger word appears in it
  — and adding `which` to the trigger list would have suppressed *"the
  provisions which are currently in force include ss. 1-5"*, so that guard is
  the shape too.

  **Five of the eight were found by reading the after-column of a live run**,
  where the model wrote exactly what the product now asks for and the detector
  called it the failure. **The last four all ran in that direction**, so the
  after-column has been pessimistic rather than flattering — safer, and no less
  wrong. After every correction, re-run over all seven historical directories:
  **not one before-column number moved.**

- **The acceptance needed a second directory, and the reason is worth stating.**
  6411 obeyed the rule's *"report what the change record holds"* clause in **1
  of 3** reps: reps 1 (218 chars) and 3 (713) each had 29 repeal relations in
  hand and reported none, while rep 2 (380) did. The conversational worker
  prompt demands "2-5 sentences of concise prose" and concision won. The bar in
  the row was already met — the defect was 0 in all three — but 6411 is this
  row's headline session and leaving it thinner than the material supports is
  the inverse of Invariant 1. One line on the conversational PHASE 2b plus a
  **$0.90** re-run (`wave2_p25b`) moved it to **2 of 3 reporting the repeals and
  a mean of 741 chars against wave1's 480** — and rep 1 went and fetched the
  actual Scotland Act 1998 (Commencement) Order 1998 with a real URL. So the
  acceptance is `wave2_p25` for 6341/6409 and `wave2_p25b` for 6411; both are
  0 unsupported and 0 text-version.

- **A blank Deep Research report, and it did NOT recur.** 6383 rep 1 in
  `wave2_p25` returned a report whose **body was empty** — the lawyer saw the
  scope footer and nothing else — with `status: ok`, no error, 30 tool calls,
  three intact step reports (4,836 / 5,777 / 7,190 chars) and 219 commencement
  relations retrieved. First blank in 218 answered turns across eight replay
  directories. **The cause is an empty provider completion at the synthesis
  call**: the request went out at `tools=0, msgs=2, ~21421 chars` and the task
  finished **9 seconds later**, and `strip_scope_blocks` never fired — checkable,
  because it logs when it does and the log carries no such line. **The re-run
  produced a proper 2,278-char report**, so P2.5's longer synthesis prompt is
  not implicated. Two gaps it exposed are recorded against **P4.2** (B13), not
  here: `chat_loop`'s stream retry only fires while nothing has been emitted and
  cannot see a successful 200 carrying no content chunks, and
  `run_deep_research` never checks that the synthesis produced anything before
  footering it and returning.

- **The sweep's two phases record different `git_head` values and the product
  code was identical.** Phase 1 says `c302f00`, phase 2 `843dee0`, because
  detector fixes were committed between them and `replay.py` reads HEAD at run
  start. `git diff --stat c302f00 93c1fbd -- src/ client/` is **empty** and the
  server was started once at `c302f00` and never restarted, so the executing
  product code did not change. Recorded so a later session does not read the
  discrepancy as two different systems.

- **One 6m19s silence was a slow stream, not a hang.** 6383 turn 2 completed at
  **378.6s**, the slowest turn of the sweep. Worth knowing before killing a
  sweep that looks stalled: the `read=180.0` timeout resets per chunk, and the
  log only writes on completion events.

- **The old detector undercounts by 30% and is left byte-identical.**
  `IN_FORCE_CLAIM` produced the published 27 → 30 series. It requires
  "is/are/remains/currently in force" and so catches none of the bare Status
  bullets that are the purest form of the defect — `In force (revised).` (6341
  ×3, 6384 ×6, 6389 ×3), `Status: Revised (In force).` (6406 ×4). Properly
  counted `wave1` is **43 turns / 66 assertions**, not 30 / 34. Widening it
  would have moved a number already in `BASELINE.md`, so `cmd_currency` prints
  both.

- **A published figure of mine was wrong within the session, and the command is
  what caught it.** I wrote the title-marker rate as "256 of 12,640 (2.0%), 42
  titles" from a one-off script that walked five of the seven replay
  directories. `lex_probe --inforce` walks all seven and reads **258 of 15,160
  (1.7%), 43 titles**. Same shape as Session 7's and Session 8's retractions:
  the figure behind the command wins.

- **`wave3_p35` already showed the shape this row wants, and that is not this
  fix.** P3.5's own acceptance sessions read 0 unsupported / 4 sourced, because
  the question routes the Worker to the change record. Two of those four still
  cited a text version (*"SSI 2020/475 is in force (status: revised)"*), which
  is the residual this row removes.

- **Two findings this row does NOT own, recorded so they are not re-found.**
  **(a) The zero-tool-call negative (now row P2.10).** 6341 rep 2 turn 2
  asserted a negative having made **no tool call at all**, so
  `answer_scope_footer` attached nothing (it is gated on having searched) and
  `worker_scope_block` was silent (`if not log: return ""`). First instance in
  209 answered turns across five directories, and the same turn answered
  normally in reps 1 and 3 — so n=1 and possibly stochastic. **The check, which
  P2.10 needs before anyone builds for it:**

      python - <<'EOF'
      import json, glob, sys; sys.path.insert(0, '.')
      import tools.replay_report as R
      for d in ('wave1','wave2_p22_final','wave2_p23','wave3_p35','wave2_p25'):
          hits = []
          for p in sorted(glob.glob(f'../docs/prepilot-fixes/evidence/replay/{d}/*.json')):
              x = json.load(open(p, encoding='utf-8'))
              for t in x['turns']:
                  a = t.get('answer') or ''
                  if not a.strip():
                      continue
                  n = sum(len(dg.get('tools') or [])
                          for dg in (t.get('audit') or {}).get('delegations') or [])
                  if n == 0 and R.NOT_FOUND.search(R._without_footer(a)):
                      hits.append(f"{x['session_id']}r{x.get('rep',1)}t{t['turn']}")
          print(d, len(hits), hits)
      EOF

  **(b) A meta-question about the index answered from training knowledge, and no
  row owns it.** 6341 turn 8 asks *"what do you mean when you say legislation is
  noted as a stub"* and the answer explains stub records, which instruments tend
  to be stubs and what to consult instead — none of it retrieved, all of it
  plausible, and one clause ("Statutory Instruments that were revoked or
  superseded before the database was comprehensively populated") is a guess
  about LEX's coverage presented as fact. It is not B4 (no currency claim), not
  B5 (no negative asserted) and not B3(b). **The nearest owner is P2.7's
  no-speculation family**; flagged there rather than given a row, because one
  turn is not a rate. Same shape as `section_search_note`'s reason for existing:
  6335 turn 7 invented *"the database is having difficulty parsing the Schedule
  B1 structure."*

**Decisions taken this session:**
- **Rename the field rather than instruct around it.** `status` reaches the model
  as `text_version`. 48 of `wave1`'s 66 assertions quote the text version as
  their evidence; the model was not inventing a source. `extract_sources` reads
  the new key with a `status` fallback, so the Sources rail is byte-identical
  and no frontend rebuild is needed (checked: nothing in `client/src` reads it).
- **Keep the mandatory section, change what it may say.** Telling the model to
  omit "Jurisdiction & Status" makes `_report_needs_reformat` judge the report
  malformed and spends an A4 reformat call re-adding the heading — the trap the
  row flagged.
- **`_currency_limb` speaks even when its step found nothing** — the opposite
  gate from `_enabling_limb` and `_relations_limb`. A step that established
  nothing about currency is exactly the step whose report says "all cited
  legislation is currently in force", and the agent writing that sentence has
  seen no tool result. Measured cost: 873 characters on every legislation
  worker report.
- **`valid_date` is the substitution that keeps this inside Invariant 1.**
  `2026-03-11` for the Scotland Act 1998 — the date the held revised text is up
  to date to, available on the 18% of turns that reach Phase 3 and rising under
  P3.5. Not an in-force date, and the honest thing a Status line can say
  instead of nothing.
- **Only a retrieved `coming into force` relation counts as support** for an
  affirmative assertion in the instrument. A repeal relation and a title marker
  are collected and printed but do not count: both support only a negative, and
  *"the Act remains in force except ss. 38-39, repealed by uksi/2014/486"* would
  otherwise score SOURCED off the repeal while the overclaim sits in the other
  half of the sentence.
- **The title-marker limb was dropped from the lawyer-facing footer** after the
  first smoke run put *"the index's own title for uksi/2024/697 marks it as
  repealed"* on an answer about the Scotland Act 1998. The marker is recorded
  per search ROW; filtering it to cited instruments needs a prose detector,
  which this module refuses to put in the product. It still reaches the model
  twice.

**State of the branch:** `fix/prepilot-defects`. **957 tests green,
NOTHING PUSHED** — the whole-plan-then-one-push policy stands, so the target
still runs the pre-pilot code. Ledger: Waves 0 and 1 complete; **P1.6, P2.1,
P2.2, P2.3, P2.5, P2.6, P3.5, P4.4, P5.1 and P5.3 done**; P0.4 and P5.2 at
`[~]`. **B4 is closed.**

**Machine state a new session inherits:**
- **No uvicorn running** — stopped at the end of the session. Start a fresh one
  before any live work.
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON, no pin
  file. **Re-pin before any measurement.**
- **Ten gitignored replay directories:** `baseline/` (65), `wave1/` (41),
  `wave2_p21/` (12), `wave2_p22/` (6), `wave2_p22_final/` (6), `wave2_p23/`
  (12), `wave3_p35/` (9), **`wave2_p25/` (8 — P2.5's acceptance)** and **`wave2_p25b/` (4 — 6411 re-run on the strengthened prompt, plus the 6383 blank-report re-test)** and **`wave2_p25_smoke/` (2 — the two smoke runs, kept because they are the primary evidence for the footer and paraphrase findings)**.
  None of the per-row dirs is a sweep; do **not** feed them to `replay_report
  compare`. Read them with `replay_report --dir <dir>` plus `currency` (P2.5,
  `--drops` for the both-directions audit and `--before <dir>` for Invariant 1),
  `commencements` (P3.5), `derivations` (P2.3), `negatives` (P2.2), `halts`
  (P2.1) and `corpus`.
- **`replay_report currency --unasked` was added during the handover audit,
  because `BASELINE.md` quoted a number with no command behind it.** It measures
  the cost of `_currency_limb` speaking unconditionally: turns carrying a
  currency disclaimer whose question never mentioned currency. Putting it behind
  a command immediately corrected the figure — I had published **3 of 8 turns in
  6341 rep 1**, scoped to one rep; over the whole directory it is **10 of 30
  (33%)**, and only **1 of the 11 turns that DID ask** carries a disclaimer,
  because the rest got a sourced answer. Third time this session that a figure
  moved the moment a command was put behind it.
- **The smoke runs are kept**, at `evidence/replay/wave2_p25_smoke/`
  (`6411_smoke1.json` pre-paraphrase-fix, `6411_smoke2.json` post-PHASE-2b).
  They are the primary evidence for two findings quoted verbatim above — the
  footer naming an unrelated repealed instrument, and the *"is in operation …
  active status"* evasion — and both would otherwise have lived only in a
  scratch directory.
- **Two things about the report tool that cost me time this session, both now
  true of the code.** (a) **`replay_report`, `lex_probe` and `plan_status` now
  force UTF-8 on stdout.** On this box a redirected stdout is cp1252, so
  printing a replay answer containing a character the model happened to use
  raised `UnicodeEncodeError` **partway through** — which makes redirected
  output look TRUNCATED rather than failed, with the exit code the only tell.
  `currency --drops --before … > out.txt` hit it on a 101-row drops list.
  (b) **`halts`, `negatives` and `derivations` exit 1 when findings exist**
  (`return 0 if bad == 0 else 1`); `summary`, `session`, `baseline`, `compare`,
  `commencements`, `currency` and `corpus` always exit 0. That is deliberate and
  not a bug — do not "fix" it — but a shell check of the form
  `cmd > /dev/null && echo OK` reports those three as failures, which is how I
  briefly mis-read a clean run as broken.
- **`python -m tools.plan_status`** prints where the ledger stands.

**Spend this session: ~$12.4** on replay — $9.76 for the acceptance,
$0.26 for two smoke runs, and a few cents of probes. The LEX probing is free.

**Next action:** **P2.4** is the cheapest open row and its evidence has only
grown (P3.5's sweep produced 6409 turn 10; this session's did not touch it).
**P2.9** is still a one-line fix to a measured P2.2 defect and still moves
P2.2's published numbers. **P2.7**, **P2.8**, **P3.6** and **P3.7** are open;
**Wave 4** is 9 sessions, mostly frontend, independently shippable, and nothing
depends on it. **P5.2 is the live external one** and the LEX-team question is
still free and still unasked.

---

## Session 10 — 2026-09-16 — P4.2 (B13, lost turns and blank replies), both halves

**Done:**
- **P4.2 complete, acceptance passed, B13 closes.** The cause is an **empty
  provider completion the code could not see**. The diagnostic landed first, as
  the row required; the fix is a bounded retry plus two labelled fallbacks.
- **The latency half is built too** — a step count and an elapsed clock in the
  status line, derived entirely client-side from data already arriving.
- **998 tests** (963 → 998). New tooling: `replay_report blanks`. Audit trace
  goes to **schema v3** (`empty_completions[]`); `AUDIT_TRACE.md` and `CLAUDE.md`
  updated in the same commits.
- **Spend: ~$0.27** — one live smoke turn to verify the status line. The
  acceptance is deterministic and needed no replay sweep.

**The row's own evidence list was the thing that was wrong this time, and that is
a new place for it to be wrong.**

Eighteen instrument corrections over nine sessions have all been in *detectors*.
This one was in the **handover**: the row said "4 billed-but-empty turns (6370
×2, 6407 ×2)". Counted over all ten replay directories there are **nine
blank-body turns, eight of them billed** — and **6406, 6359 and 6374 appear
nowhere in the row's evidence list**. 8 in 616 turns (1.3%), six sessions, three
chat modes. The correction did not change the fix, but it doubled the measured
base rate, and a row scoped against 6370/6407 would have been accepted on a
directory that never contained most of the defect.

**Surprises / deviations from FIX_PLAN:**

- **6383's synthesis call declared NO tools, and that changed the shape of the
  fix.** The handover flagged this as a question to decide. Eight of the nine
  blanks follow tool execution, matching the public reports of streaming +
  function calling returning an empty final message — so the obvious guard is
  "retry an empty completion *after a tool ran*". 6383 is the counter-example:
  `agent_core.py` passes `[]` and `_no_tools_executor`, and the log reads
  `tools=0, msgs=2, ~21421 chars`. A guard scoped to tool-call turns would have
  missed the worst instance in the corpus — a $0.45 Deep Research report with 30
  tool calls and 219 commencement relations behind an empty body. **The retry
  keys on an empty completion, full stop.** It is also *stochastic*, not
  deterministic: the same payload produced 9,190 / 6,503 / 7,490 / 8,672 chars on
  four prior runs and 2,278 on the re-run, failing once in six. That is the
  condition a bounded retry answers, so the answer to the row's "is a bounded
  retry sufficient" is yes, with the fallbacks for the residual.

- **One of the four mechanisms is OURS, and it was found by writing the
  diagnostic rather than by reasoning about it.** OpenRouter reports a mid-stream
  failure as an `error` object on the SSE stream. `chat_loop` read only `usage`
  and `choices` — **nothing looked at `error`** — so a mid-stream failure ended
  indistinguishable from an ordinary empty completion: `status: ok`, no error,
  full billing. That is a parser gap, not a provider bug. The row's framing ("the
  fix may not be ours") was half right: the retry is the answer either way, but
  one of the four ways in is a line we never read.

- **P2.2 changed what this failure looks like on screen, and a detector written
  before it would score the worst case as fine.** A blank turn is no longer an
  empty string: 6383 rep 1 turn 4's `answer` is **1,293 characters**, all of it
  the code-emitted scope footer, with nothing above it. `blank_verdict` grades
  `_without_footer(answer)` for that reason. Seven of the eight billed blanks
  predate the footer and have `answer == ""`; the one that does not is the one
  the row cares most about.

- **The reasoning-token mechanism cannot be ruled out from stored data, and that
  is why the diagnostic exists.** A thinking model that spends its whole
  completion on reasoning emits no content and is billed for it — the identical
  signature. Run files record only aggregate `llm_calls` and `total_cost_usd`, no
  per-call token counts, so nothing in eight sessions of stored evidence
  separates it from a lost answer. `reasoning_chars` now does. Neither
  `delta.reasoning` nor `delta.reasoning_content` was read anywhere in `src/`
  before this.

- **There is no frontend test runner in this repo** (no vitest, no jest, no
  `npm test`), so the latency half has no unit test and was verified live through
  Playwright instead: the line read *"Researching · 13 steps · 1m 01s"*, advanced
  on both figures, tracked Researching → Analysing findings → Typing, and cleared
  on completion. The same turn returned a full research report with no
  `EmptyCompletion` warnings and no tracebacks, which exercises the backend half
  end to end. Worth knowing before anyone plans a frontend row (Wave 4 is mostly
  frontend): a UI change here is verified by driving it or not at all.

- **`replay_report blanks` joins the three subcommands that exit 1 on findings.**
  `halts`, `negatives` and `derivations` already do; `blanks` is an acceptance
  assertion of the same kind, so it does too. The other seven always exit 0. A
  shell check of the form `cmd > /dev/null && echo OK` reports all four as
  failures — deliberate, still not a bug.

**Decisions taken this session:**
- **A tool-call-only message is never retried.** No content with a tool call is
  the normal ReAct shape; treating it as empty would re-run the turn's research
  and double its cost. `is_empty_completion` requires *both* to be absent.
- **The discarded attempt's cost is banked; `llm_calls` is deliberately not
  incremented.** Under-reporting the spend would hide the very thing that makes a
  blank turn a defect rather than a slow one. `llm_calls` is left alone because
  the pre-existing timeout retry does not count its abandoned attempts either,
  and moving that counter would shift a metric other rows' numbers were measured
  against.
- **Both fallbacks are labelled as fallbacks (Invariant 1).** Research the
  answering step never used is not an answer. The whole complaint in this bucket
  is that a lawyer could not tell a lost answer from a finished one, so the
  fallback opens by naming the failure, states what has and has not been done to
  the material below, and reorders nothing. `run_deep_research` sets
  `synthesis_failed`; the Manager sets `answer_failed`.
- **The Manager keeps its worker reports.** Two lines in `manager_tool_executor`,
  read only on the failure path. Discarding a completed research report to show
  "something went wrong" would throw away retrieval the lawyer paid for, which is
  the complaint this bucket is about.
- **Audit schema bumped to v3 deliberately.** `AUDIT_TRACE.md` says the version
  is incremented on *any* change to the shape, so an additive key still bumps it.
  `empty_completions` is `[]` on a healthy request — present and empty, so a
  consumer can tell "nothing was lost" from "this trace predates the field"
  without reading `schema_version`.
- **No denominator on the step counter.** "Step 3 of 8" is a claim about how much
  is left, and outside Deep Research nothing knows the total — the model decides
  how many retrievals a question needs as it goes. Invariant 1 applies to
  progress claims as much as to legal ones.
- **Elapsed is derived from `run.startedAt`, not counted up in the interval**, so
  a re-render, a chat switch or a backgrounded tab cannot reset or skew it. It
  includes queue wait, which is the wait the lawyer actually experiences.

**State of the branch:** `fix/prepilot-defects`. **998 tests green, NOTHING
PUSHED** — the whole-plan-then-one-push policy stands, so the target still runs
the pre-pilot code. Ledger: **19 of 34 rows, 6 of 14 buckets closed** (B1, B2,
B3, B4, **B13**, B14). Waves 0 and 1 complete; **P1.6, P2.1, P2.2, P2.3, P2.5,
P2.6, P3.5, P4.2, P4.4, P5.1 and P5.3 done**; P0.4 and P5.2 at `[~]`.

**Machine state a new session inherits:**
- **No uvicorn running** — started for the live smoke, stopped at the end.
- **Dev box untouched and unpinned** — still `moonshotai/kimi-k3`, local prompt
  cache ON, no pin file. **The smoke turn ran on that configuration on purpose:**
  it was a smoke, not a measurement, so the pin was neither needed nor wanted.
  **Re-pin before anything that produces a number.**
- **Still ten replay directories** — this row added none, and needed none. Its
  acceptance reads the existing ones.
- **`python -m tools.replay_report --dir <dir> blanks`** is the new command.
  `blank_verdict` is unit-tested in `tests/test_replay_tooling.py`; the product
  fix is in `tests/test_empty_completion.py` (28 tests).

**Next action:** unchanged from Session 9's advice, minus this row. **P2.4** is
the cheapest open row and B12's other half. **P2.9** is still a one-line fix that
moves P2.2's published numbers and needs its own before/after. **P2.10** is
measure-before-building with the command already written. **P2.7**, **P2.8**,
**P3.6** and **P3.7** are open and unblocked. **P3.1 is the keystone** — the
largest unfixed bucket, with P3.2, P3.3, P3.4 and P4.3 all behind it — and
finishing Wave 2 is the critical path to it. **P5.2 is the live external one**
and the LEX-team question is still free and still unasked.

---

## Session 11 — 2026-09-16 — P2.9 (B5, the memo-served search missing from the record)

**Done:**
- **P2.9 complete, acceptance passed.** A memo-served search now enters its own
  worker run's record. B5 drops to waiting on **P2.8 and P3.7** only.
- **1009 tests** (998 → 1009). New tooling: `replay_report scoperecord`.
- **No spend.** The acceptance is deterministic and the before-column is measured
  over existing run files.

**The row's published numbers were computed on a denominator that included two
directories where the feature does not exist.**

The row said "23% of `search_legislation` calls are memo hits (359 of 1,497), and
78 of 358 worker runs (22%) lose at least one query — 150 distinct queries across
47 turns", measured over `wave1` + `wave2_p21` + `wave2_p22_final` + `wave2_p23`.
**`wave1` and `wave2_p21` predate P2.2 and carry no scope block at all** — 182 and
56 worker runs respectively. A run with no block cannot lose anything from it, so
those runs belong outside the denominator, not inside it. Over the six directories
that do have a block: **277 of 1,189 searches (23%) missing, in 86 of 259 runs
(33%)**. The memo-hit rate was right; the loss rate was deflated by a third.

**Surprises / deviations from FIX_PLAN:**

- **The identity is the finding, and it is stronger than the row claimed.**
  `issued − recorded == memo hits` holds **exactly, per run, with zero exceptions
  across all 259 runs and all six directories**. Nothing other than a memo hit eats
  the record. That is what makes a one-line fix the whole answer rather than one
  fix among several — and it is checkable, so if a later session sees the identity
  break, something new is wrong.

- **The defect is not a short count, and its worst case is in the session
  Invariant 1 is built on.** 11 of the 86 lossy runs made **every** one of their
  searches via the memo, so their block carries no searched-for line at all —
  while still carrying the instruction that a negative *"MUST quote the search
  terms above"*. **The disclosure contradicted itself.** The measured case is 6374
  rep 1 turn 2: the step searched for `"Scotland Act 1998"`, its block does not say
  so because an earlier step searched for it first, and **6374 is the session
  CambeulW scored 5/5 *because* AILA said it could not find something**. The
  mechanism that earns that trust was telling the model to quote terms it had
  withheld. Neither the row nor P2.3's NOTE anticipated this case; both described
  a count running short.

- **`record_search` does not self-gate on the tool name and `record_currency`
  does.** The three recorders already on the memo path (`record_enabling_power`,
  `record_relations`, `record_currency`) are called unconditionally because each
  dispatches on `name` internally. `record_search` does not — its two call sites on
  the non-memo path gate it, so the memo path is the third gate, not a fourth
  unconditional call. Adding it unconditionally would have logged every memoised
  retrieval as a search of the index, inflating the exact count this row exists to
  correct. There is a test for that direction.

- **My own detector was wrong, in the alarming direction, and the command caught
  it.** The first `scope_record_gap` inferred block-absence from `recorded == 0`.
  That cannot distinguish a **pre-P2.2 run** (no block exists) from an **all-memo
  run** (a block exists and records nothing) — identical on the count alone. It
  reported `wave1` as 13 runs "with a scope block" losing 100% of their searches,
  and put corpus-wide loss at **1,127 queries across 277 runs**, roughly four times
  the truth. Keying on the block **marker** (`[/SEARCH SCOPE]`) settles it, and is
  pinned by a test that states both halves. Fourth published figure in three
  sessions to move once a command was put behind it; second this session.

- **The after-column is by construction and deliberately not bought.** The row's
  acceptance is *(deterministic)*, and the fix makes `issued == recorded`
  identically — there is no rate left to estimate. `scoperecord` exits 0 on any
  directory produced after this commit, and **no such directory exists yet**, so
  the next sweep any row runs is the first observation. Spending on a sweep to
  confirm an arithmetic identity would have bought nothing.

**Decisions taken this session:**
- **Gate on the tool name, mirroring the non-memo path exactly.** Parity is the
  rule this path has followed three times already (sources, URLs, enabling power,
  relations, currency): the memo saves the API call, not the provenance.
- **`recorded == 0` is the honest reading for an all-memo run**, not a null. The
  block exists and it recorded no search; that is a real state and it is the worst
  one in the bucket.
- **`scoperecord` exits 1 when the record is incomplete**, joining `halts`,
  `negatives`, `derivations` and `blanks`. A pre-P2.2 directory exits 0 because it
  has nothing countable — not a pass, an absence, and the output says so on its
  first line.
- **`replay_report negatives` re-run over all six post-P2.2 directories and
  recorded as unchanged.** It must be: the fix touches product code, not the
  detector. Run anyway, because that is the check that catches an accidental
  detector edit.

**State of the branch:** `fix/prepilot-defects`. **1009 tests green, NOTHING
PUSHED**. Ledger: **20 of 34 rows, 6 of 14 buckets closed**. **Wave 2 is 6 of 10**;
the four open rows are **P2.4, P2.7, P2.8, P2.10**, and Wave 2 is the gate on
**P3.1**, which gates P3.2, P3.3, P3.4 and P4.3.

**Machine state a new session inherits:**
- **No uvicorn running.**
- **Dev box untouched and unpinned** — `moonshotai/kimi-k3`, local prompt cache ON,
  no pin file. **Re-pin before anything that produces a number.**
- **Still ten replay directories.** This row added none and needed none.
- **`python -m tools.replay_report --dir <dir> scoperecord`** is the new command.
  `scope_record_gap` is unit-tested in `tests/test_replay_tooling.py`; the product
  fix is in `tests/test_search_scope.py` (five tests, three of which fail without
  the fix).

**Next action:** **P2.10** is the cheapest — it is a *measurement*, not a build,
and the command is already written in Session 9's notes; it may well resolve to
"not a rate, do not build". Then **P2.4**, **P2.7**, **P2.8** to finish Wave 2 and
unblock P3.1. **P5.2 is still the live external one**, still free, still unasked,
and B12 cannot close without it.

---

## Session 12 — 2026-09-17 — P2.10 measured, NOT built, decision pending; three findings for P4.1 and P2.2

> **CORRECTED LATER IN THIS SESSION: THREE CLAIMS BELOW ARE WRONG. Read this block first.**
>
> **The measurement used the wrong detector.** `replay_report` has **two** regexes
> for "asserts a negative":
> - `NOT_FOUND` (line ~88) is the **P0.3 baseline** detector. It feeds only
>   `analyse_run` → `summary` / `baseline` / `compare`.
> - `NEG_ASSERTED` (line ~151) is **P2.2's acceptance detector**, behind
>   `replay_report negatives`.
>
> Session 9's P2.10 script used `NOT_FOUND`, and I copied it. **For any question
> about asserted negatives, use `NEG_ASSERTED`.** Re-run with it over all ten
> directories:
>
> | | with `NOT_FOUND` (wrong) | with `NEG_ASSERTED` (right) |
> |---|---|---|
> | answered turns asserting a negative | — | **210 of 608** |
> | **(A)** no delegation, asserts a negative | 1 | **5** |
> | **(B)** Worker delegated, zero tools, asserts a negative | 3 of 14 | **12 of 14** |
>
> **The five (A) turns are two defects, not one**:
> - **Four are P2.8's defect**: a no-delegation turn restates an earlier turn's
>   negative, so no footer fires. They are `wave2_p22_final/6409 r1 t11` and
>   `r3 t4` (P2.8's own cited turns), plus `wave2_p25/6341 r2 t2` and `r3 t2`.
>   **6341 did it in 2 of 3 reps**; Session 9's "reps 1 and 3 answered normally"
>   came from the narrower detector.
> - **One is P2.7's speculation family**: `wave1/6341 r1 t8`, the *"what is a
>   stub"* meta-question answered from training knowledge.
>
> **Corrections to the entry below:**
> 1. ~~P2.10 is n=1 and should be closed without building~~ → **P2.10 is P2.8.**
>    Same mechanism (no search this turn, so no footer), same fix candidate
>    (carry the earlier scope forward), 4 instances over 2 sessions. The
>    recommendation is now: **fold P2.10 into P2.8 and build P2.8.** The user has
>    been told. The next session confirms the fold before ticking P2.10.
> 2. ~~Finding 3: P2.2's detector is blind to "The available database does not
>    contain information…", so P2.2's published numbers never saw it~~ →
>    **false.** `NEG_ASSERTED` matches that sentence, so P2.2's acceptance
>    numbers were never blind to it. Only `NOT_FOUND` misses it, which means the
>    P0.3/P1.5 `summary`/`compare` bare-negative counts under-read that phrasing.
>    Those counts were superseded by `negatives`. Nothing to fix.
> 3. ~~(B): 3 of 14 assert a negative~~ → **12 of 14.**
>
> **Findings 1 and 4 stand.** Finding 1: the replay cannot test P4.1's anchoring,
> because the export has no research mode. Finding 4: the (B) turns differ between
> sweeps.
>
> **One further fact P2.8 needs, verified at HEAD.** The previous turn's footer
> is **already in the conversation history**. `replay.py:496` appends `tr.answer`,
> footer included. The live frontend saves the full result content and sends it
> back. `strip_answer_footer`'s `_ECHOED_FOOTER`
> (`utils/search_scope.py:1602`) already recognises a trailing
> `*Search scope: …*` line, because P3.5 found the model echoing it.

**Done:**
- **P2.10's measurement, over all ten replay directories.** ~~Its own defect is
  **n=1 in 608 answered turns**.~~ **WRONG DETECTOR: it is 4 (see the correction above).** Session 9 counted it over five directories and
  209 turns; the count did not grow.
- **P2.10 is NOT ticked.** My recommendation is to close it as measured and not
  built (reasoning below). **That is the user's decision and it has not been
  made.** The next session should ask before ticking it.
- **No code changed. No spend.** Documentation only: this entry, P2.10's and
  P4.1's rows, and a `BASELINE.md` section.

**The measurement split into two different defects, and the first version
conflated them.** "A turn that asserts a negative having made zero tool calls"
fires on four turns. Three of the four are a different shape from the one the row
describes:

| shape | turns | what it is |
|---|---|---|
| **(A)** 0 delegations, asserts a negative | **1** — `wave2_p25/6341 r2 t2` | **P2.10's defect.** The Manager answers from history, cites a search made in an earlier turn, and gets no footer. |
| **(B)** at least one delegation, **zero** tool calls | **14** — 4 sessions (6343, 6346, 6347, 6350), in `baseline` and `wave1` only | **Not P2.10's.** A case-law question under `legislation_only`, so the Worker has no case-law tool, searches nothing, and reports a negative. |
| of (B), final answer matched by `NOT_FOUND` | 3 (all 6350) | see finding 3 |

Reproduce with the following script. There is deliberately no subcommand yet. If
P2.10 is built, promote this to `replay_report` first, because the A/B split is
exactly the kind of rule an ad-hoc script gets wrong:

    python - <<'EOF'
    import json, glob, sys; sys.path.insert(0, '.')
    import tools.replay_report as R
    dirs = ('baseline','wave1','wave2_p21','wave2_p22','wave2_p22_final',
            'wave2_p23','wave3_p35','wave2_p25','wave2_p25b','wave2_p25_smoke')
    A, B, ans = [], [], 0
    for d in dirs:
        for p in sorted(glob.glob(f'../docs/prepilot-fixes/evidence/replay/{d}/*.json')):
            x = json.load(open(p, encoding='utf-8'))
            for t in x['turns']:
                a = t.get('answer') or ''
                if not a.strip():
                    continue
                ans += 1
                dgs = (t.get('audit') or {}).get('delegations') or []
                n = sum(len(g.get('tools') or []) for g in dgs)
                neg = bool(R.NOT_FOUND.search(R._without_footer(a)))
                tag = f"{d}/{x['session_id']}r{x.get('rep',1)}t{t['turn']}"
                if not dgs and neg: A.append(tag)
                if dgs and n == 0: B.append((tag, neg))
    print(ans, 'answered'); print('A', len(A), A); print('B', len(B), B)
    EOF

(Run from `server_py/`. Expected: 608 answered, A = 1, B = 14.)

~~**Why I recommend closing P2.10 without building.**~~ **(Superseded: fold P2.10 into P2.8. See the correction above.)** At 1 in 608 (0.16%) it is not
a rate. It is also stochastic: the same turn answered normally in reps 1 and 3.
The row allows two fixes. The first is to carry the previous turn's scope forward,
which means new cross-turn state. The second is to fire the footer on a turn that
asserts a negative, which puts a prose detector in the product, and
`search_scope.py` refuses that by design. Neither is justified at this rate. **The
case for building anyway** is that the one instance is a real negative shown to a
lawyer with no disclosure. That trade is the user's to make.

**Surprises / findings. Three of them belong to other rows.**

- **1. The replay cannot test P4.1's anchoring bug, and the reason is in the data,
  not the harness logic.** (B)'s 14 turns cover **four of P4.1's five evidence
  sessions** (6343, 6346, 6347, 6350). It is tempting to read them as P4.1's
  before-column. They are not. **The transcript export records NO research mode
  for these sessions:** `Filter: Research mode` and `Session mode` are blank on
  every row of 6346 and 6350. `replay_set.py` reads the mode once per session from
  the first row (`head.get("Filter: Research mode")`) and falls back to
  `DEFAULT_RESEARCH_MODE = "legislation_only"`. So every replayed turn ran under
  `legislation_only`, including *"I have changed the mode, please proceed"*.
  **In the replay the mode never changed, so a refusal on those turns is correct
  about the tool set.** P4.1's bug (a) is that the model anchors on its earlier
  refusal *after* a real mode change, and no stored run file can show that. Two
  consequences for whoever builds P4.1:
  - its acceptance must be the scripted two-turn sequence the row already names.
    It cannot be a corpus replay.
  - **the harness sends one `research_mode` per session**, so that scripted
    sequence needs a per-turn mode that `replay.py` does not support today.
    Budget for adding it.

- **2. What (B) does measure is the wording of the refusal, which is P4.1's (b)
  and (c) and a B5-shaped false negative.** All 14 Worker reports open *"The
  available database does not contain information on this specific issue."* That
  is a claim about the **corpus**. The truth is a claim about the **tool set**: no
  case-law tool is loaded in this mode. The sentence is false in the way B5 cares
  about. 6350's Manager then told the lawyer to switch to *"Legislation & Case Law"
  mode*, which is P4.1(b)'s wrong control name.

- ~~**3. P2.2's `NOT_FOUND` detector is blind to that sentence.**~~ **(FALSE. `NOT_FOUND` is not P2.2's detector; `NEG_ASSERTED` is, and it matches. See the correction above.)**
  `NOT_FOUND.search("The available database does not contain information on this
  specific issue.")` is **False**. So is the tool-set variant (*"…do not contain
  case law"*). *"The research agent returned no results"* is **True**, and that
  phrase is why exactly 3 of the 14 counted: 6350's Manager wrapped the report in
  it. **The blind spot runs in the flattering direction.** A negative about the
  corpus that `replay_report negatives` never grades is a negative P2.2's
  published numbers never saw. **I did not fix it.** Widening `NOT_FOUND` moves
  P2.2's published before and after columns, so it needs its own before/after,
  for the same reason P2.9 did. It is not yet a row. The owner is P2.2's detector
  family, and the nearest open row is **P2.8**. Flag it there, or give it a row,
  before anyone relies on the negatives rate again.

- **4. A correction to something I told the user this session.** I said (B)
  "reproduces in both `baseline` and `wave1` — same sessions, same turns". The
  sessions are the same. **The turns are not.** 6346 t4/t5, 6347 t1 and 6350
  t3/t4 recur in both sweeps. 6346 t2 and 6350 t2 are `baseline`-only. 6346 t3
  and 6343 t2 are `wave1`-only. Whether a given turn searches is stochastic; the
  refusal pattern for the session is not.

**Decisions taken this session:**
- **P2.10 left unticked.** Closing a row on a measurement is within the row's own
  terms ("a measured rate first, then a unit test pinning whichever fix is
  chosen"). Choosing *no* fix is still a choice with a defensible alternative, so
  it waits for the user.
- **The `NOT_FOUND` blind spot is recorded, not fixed.** Same reasoning as P2.9:
  any change to a published instrument needs its own before/after.
- **No `zerotool` subcommand.** The script is recorded verbatim above, as Session 9
  recorded this row's first check. Promote it before building.

**State of the branch:** `fix/prepilot-defects`, **73 commits, no upstream, NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1009 tests green.** Ledger unchanged
by this entry: **20 of 34 rows, 6 of 14 buckets.** Wave 2 open rows: **P2.4,
P2.7, P2.8, P2.10**. P2.10 is awaiting a decision, not work.

**Machine state a new session inherits:**
- **No uvicorn running.**
- **Dev box unpinned**: `moonshotai/kimi-k3`, local prompt cache ON, no pin
  file. **Re-pin before anything that produces a number.**
- **Ten replay directories, unchanged.**
- **The dev DB holds one smoke-test chat** (id 19, admin, *"What does section 1
  of the Scotland Act 1998 say?"*) from Session 10's live check of the status
  line. It is harmless and was left in place.
- **`.playwright-mcp/`** at the repo root holds page snapshots from that same
  check. It is gitignored (`.gitignore:91`) and safe to delete.

**Next action:**
1. **Ask the user about P2.10**: close it as measured, or build the carry-forward.
2. **P2.4, P2.7, P2.8** finish Wave 2, which unblocks **P3.1** and behind it
   P3.2, P3.3, P3.4 and P4.3. When reading **P2.8**, weigh finding 3 above: it may
   be the right home for the `NOT_FOUND` blind spot.
3. **P4.1 depends on `P2.*`**, so it is blocked until Wave 2 closes. Findings 1 and
   2 are its handover. Its acceptance needs a per-turn `research_mode` in
   `replay.py`.
4. **P5.2 still needs the user**: the LEX-team question is free and unasked, and
   B12 cannot close without it.

---

## Session 13 — 2026-09-17 — P2.8 (B5, the negative carried forward), with P2.10 folded in

**Done:**
- **The fold was confirmed with the user first.** P2.10 is P2.8, and both are
  ticked in the same commit.
- **P2.8 built and accepted.** B5 now waits on **P3.7** only.
  - A reply that ran no search now restates the earlier searches in a scope
    line labelled as earlier (`carried_scope_footer`).
  - Acceptance: n=3 on 6409 and 6341 (`wave2_p28`). UNQUALIFIED went 4 → 0,
    MISATTRIBUTED 0, and `negatives` has no FAIL rows in either session.
- **New tooling.**
  - `replay_report nosearch`: Session 12's A/B script, promoted, with
    `NEG_ASSERTED`. It reproduces the corrected figures exactly.
  - `nosearch --before --only`: Invariant 1 graded on the prose with the footer
    removed.
- **Three instrument corrections**, in `blanks` (two) and `scoperecord` (one).
  None moved a published number.
- **New row P4.5**, measure-first: a worker whose final completion is lost.
- **1051 tests** (1009 → 1051).
- **Spend: $13.65.** Smoke $3.35 (24 min), acceptance $10.30 (82 min), against
  an estimate of about $11 and 75 minutes.
- **Ledger: 22 of 35 rows** (one row added), **6 of 14 buckets**.

**The design, and the two places it departs from the row's wording.**
- **The earlier scope comes out of the history, not the request config.** The
  code-emitted footer is already in every earlier assistant message. The live
  frontend sends saved `content` back unchanged, and nothing trims the history.
  So no new request state and no frontend change were needed.
- **The gate is structural and never reads the answer.** It fires when all four
  hold: this turn recorded no search (either search tool); no delegation raised;
  no peer was consulted; an earlier reply ends in a fresh footer. "Restate only
  when the answer repeats a negative" would be a prose detector in the product,
  which `search_scope.py` refuses.

**Surprises / deviations from FIX_PLAN:**

- **P2.10's evidence is two defects, and P2.8 fixes only one.** 6341 runs under
  `legislation_only`, and **no run of it has ever called a case-law tool**. Yet
  its turn 2 tells the lawyer the agent *"conducted a comprehensive search
  across both the legislation and case law databases"*. The carried line fixes
  what P2.8 is about: a restated negative with no scope beside it. It qualifies
  the legislation searches and, correctly, says nothing about case law.
  `negatives` then PASSES the turn, because it cannot tell which corpus a
  negative is about. **That PASS says nothing about the case-law claim**, which
  is still false. It is recorded as item (5) on P4.1's row, next to Session 12's
  finding 2, which is the same shape.

- **The structural gate caught a negative the detector misses.** 6341 rep 1
  turn 2 says the search *"returned no general case law interpretations"*.
  `NEG_ASSERTED` does not enrol it, because "general" is not in its adjective
  list. The line fired anyway. A product gated on that regex would have left the
  turn bare. This is the first measured case for the module's refusal to gate on
  prose.
  - **It is one of two verified `NEG_ASSERTED` under-reads, and neither is
    fixed.** The other is *"is not yet indexed in the legislation database"*
    (`wave2_p22_final/6409 r2 t11`), which misses because the regex allows
    `not (currently)? indexed in the`, but not "yet". Both were checked by
    running the regex on the exact sentences. A third sentence, *"found no
    records of case law"*, does match.
  - **Consequence: every `negatives` denominator in `BASELINE.md` is a slight
    under-read.** Widening the regex moves published before- and after-columns,
    so it needs its own before/after, the same reasoning as P2.9. It is not yet
    a row. Take it up only if a row's acceptance turns on a phrasing like
    these.

- **The before-column the handover named for 6409 is confounded.** Against
  `wave2_p22_final`, 6409's negatives per rep fall 7.0 → 4.0 and tool calls
  94 → 35. **That is P3.5, which landed in between**, not this fix. The
  like-for-like before is `wave3_p35` (n=3, post-P3.5): negatives 4.0 → 4.0,
  tool calls 35.7 → 34.7, 7 of 11 prose slots longer. Reported both ways in
  `BASELINE.md`.

- **The first directory to exercise two code paths broke two instruments, in
  the flattering direction.** `wave2_p28` is the first schema-v3 directory with
  an empty completion in it, and the first after P2.9.
  - `blanks` read three failed attempts at one call as *"recovered by retry 2,
    NOT recovered 1"*.
  - `blanks` also called the clean v3 smoke directory "pre-v3", because it
    tested the list's truthiness rather than the key's presence.
  - `scoperecord` printed `identity … : False` on a complete record.

  All three are fixed and tested, and no historical number moved. In every case
  the code had never met real data of the shape it was written for. **The
  lesson generalises: the first directory after a fix exercises instrument
  branches that have never run, so read those branches' output before trusting
  it.**

- **P4.2 has a hole at the worker seam, and it is the reasoning-token
  mechanism.** In 6409 rep 3 turn 11, one worker call came back empty three
  times.
  - One of those attempts spent **62,915 completion tokens** (29,350 reasoning
    characters) and returned no content. That is the first stored instance of
    the mechanism P4.2 could not rule out. It made a $0.86 turn.
  - P4.2's fallbacks sit at the Manager and Deep Research seams only. So the
    worker handed back a report consisting of its scope block alone: a search
    record with no findings, which reads as "searched, found nothing".
  - The Manager re-delegated here, and the answer was sound. B13's invariant
    held, so **B13 stays closed**. The mechanism is new row **P4.5**,
    measure-first, per the re-planning protocol.

- **I did not run `halts` on the acceptance directory, and it exits 1.** This
  was found afterwards, while comparing P2.4 and P2.7 for the user.
  - **The failure.** `wave2_p28/6341 r1 t7` is a Deep Research synthesis whose
    four steps all halted. Its prose says *"the research steps timed out due to
    internal limits"*, directly beneath P2.1's code notice saying it is not a
    timeout. It is the first such failure in 24 post-P2.1 halted turns, on a
    path P2.8 does not touch. It is recorded on P2.1's row as a residual to
    recount, not a new row.
  - **The process fix.** On any new sweep, run every exit-1 subcommand:
    `halts`, `negatives`, `derivations`, `blanks`, `scoperecord` and
    `nosearch`, not only the row's own.

- **P2.7's evidence has moved.** 6409 has not halted in the 6 reps since P3.5,
  because the relation it flailed for is now retrievable. 6341's broad "every
  definition of shop" question halts in every rep of `wave2_p25` and
  `wave2_p28`, including all four Deep Research steps of r1 t7. P2.7's row now
  says to derive its budget from the post-P3.5 directories, and to replay 6341
  rather than 6409.

- **The unit tests fail without the fix, split as P2.9's were.**
  - With the wiring removed, 1 of 29 fails: the end-to-end positive. The other
    four end-to-end tests guard against over-reach (a first turn, a searched
    turn, a failed delegation, a peer consult) and pass either way.
  - With the function stubbed to return `""`, 8 of 29 fail. The other 21 are
    silence or over-reach guards.

**Decisions taken this session:**
- **P2.10 folded into P2.8**: the user's decision, confirmed before any work.
- **Hazard 1 (`wave1/6341 r1 t8`) is acceptable noise, not a false attribution.**
  The line opens *"no search of the legislation index was run for this reply"*,
  labels every term as earlier, claims no dependency, and scopes its not-found
  clause to *"those searches"*. Live, on the stub question (smoke 6341 turn 8),
  it tells the lawyer that nothing was looked up for that answer. That is true,
  and it is the disclosure a training-knowledge answer lacked.
- **Silent when the turn's searches are unknown.** That covers a failed
  delegation (its search record went with it) and a peer consult (the peer's
  searches are not in our record). "No search was run" could be false in either.
- **Silent after a within-instrument search.** Either search tool counts as
  searching. A `search_legislation_sections`-only turn gets no fresh footer, and
  "no search was run" would be false there. This is a recorded residual.
- **Manager path only.** The Deep Research synthesis sees the step findings and
  never the conversation, so it cannot restate an earlier turn's negative.
- **A carried line is never read back as a source of searches.** That is what
  stops chaining. Terms are listed newest first. An exact count is given only
  where one is knowable; across several replies an unlisted query may repeat a
  listed one, so the line says "further queries" without a number.
- **A retrieval-only turn keeps its own P2.3/P3.5/P2.5 clauses on the carried
  line.** They are gated on that turn's own records, so they are true by
  construction. Such a turn previously showed no footer at all.
- **The clutter is accepted, and the user confirmed it.** The line fired on 15
  of 57 answered turns, 2 of them negatives. Historically it is 4 of 27 (95% CI
  6–33%), in three directories. That is P2.2's trade, extended to follow-ups.
  **The user decided at the end of this session to keep it as built.** Do not
  reopen it without new evidence.
- **Two residuals, recorded rather than built.**
  - A turn that only searched *within* an instrument stays silent (see above).
  - A turn that retrieved text or relations without searching, **with no
    searched turn before it**, still shows no footer at all. Its P2.3/P3.5/P2.5
    clauses therefore never reach the lawyer. This predates this row:
    `answer_scope_footer` returns `""` without a search. The carried line only
    covers such a turn when an earlier reply searched.
- **Code committed before the paid sweep** (`2545184`), so the run files name
  the exact product code they measured. The tooling commits followed the sweep.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1051 tests green.** Ledger:
**22 of 35 rows, 6 of 14 buckets**, primary bucket closed for 18 of 41
sessions. Wave 2's open rows: **P2.4, P2.7**.

**Machine state a new session inherits:**
- **No uvicorn running.** It was started for the sweeps and stopped afterwards.
- **Dev box restored**: `moonshotai/kimi-k3`, local prompt cache ON, no pin
  file.
- **Twelve replay directories.** New this session: `wave2_p28_smoke` (2 runs)
  and `wave2_p28` (6 runs). `wave2_p28` is the first directory produced after
  P2.9, P4.2 and P2.8.
- **New commands:**
  - `replay_report --dir <dir> nosearch [--all] [--answers]`
  - `nosearch --before DIR --only SESSION…`

  `nosearch` also prints the carried line's measured cost: the "no-search turns
  after a searched turn … of which negative" line. It joins the subcommands that **exit 1 on findings**: `halts`,
  `negatives`, `derivations`, `blanks` and `scoperecord`.

**Next action:**
1. **P2.4 or P2.7** finishes Wave 2, which unblocks **P3.1** and, behind it,
   P3.2, P3.3, P3.4 and P4.3. P2.4 is still the cheaper. Note that 6341's false
   case-law claim (P4.1 item 5) sits right next to P2.4's disclosure.
2. **P4.5** is measure-first. `blanks` now reports unrecovered calls correctly;
   count them over the next directories before building.
3. ~~The clutter decision is the user's to overrule.~~ **Decided: kept as
   built** (user, end of Session 13). Nothing to do.
4. **Still with the user, and not blocking:**
   - **P5.2**: the LEX-team question in `WAVE5_QUESTIONS.md` is free and still
     unasked. B12 cannot close without it; P2.4 can be built without it.
   - **An alternative Scottish case-law supplier** has not been researched.
     BAILII's terms restrict automated access, so that is the organisation's
     question before anyone designs against it.
5. ~~Proposed next row: P2.4 … the user has not chosen~~ **The user chose
   P2.4 next** (end of Session 13). P2.4's row carries pre-flight facts
   verified at `6d9b129`: where the existing gap wording lives, the
   before-column, SSI 2026/170 still absent, and four design hazards. The most
   dangerous hazard is that P2.8's carried-line parse reads only the **last**
   footer line. **P2.7 follows**, with its evidence moved to 6341.

---

## Session 14 — 2026-09-17 — P2.4 (B12, the case-law corpus gap), both halves

**Done:**
- **The gate was stated to the user at the start, with no objection:** the
  disclosure fires on any turn that called `search_case_law`. That is the
  row's recommendation (i).
- **P2.4 built and accepted.** Any turn that searched case law now carries, in
  code, what the corpus holds for Scotland. **B12 stays open**: it also needs
  **P5.2**, which is with the user.
  - Acceptance: n=3 on 6375, 6373 and 6385 (`wave2_p24_final`, head
    `051472d`). **15 of 15 turns that searched case law carry the
    disclosure**, including all three of 6375's Deep Research turns (before:
    1 of 5 at HEAD, 0 of 3 on the Deep Research turn). **6373: 0 of 6 turn
    slots question the citation** (before: 2 of 6). Every exit-1 subcommand
    passes.
- **The 6373 half was measured before any of it was built**
  (`wave2_p24_pre`, n=3 at HEAD `4890573`). It was still live: 2 of 6 turn
  slots questioned a correct citation.
- **New tooling.** `replay_report caselaw` grades with a code/model split and
  with a stricter detector than `SCOTS_CASELAW_GAP`. `--drops` and
  `--all --answers` do the both-directions audit. `--before DIR --only S`
  checks Invariant 1.
- **One A/B**, which took back part of the fix (see Surprises).
- **1125 tests** (1051 → 1125, 74 new). They were proven to fail without the
  fix, on the final code: 19 of the 74 with the wiring removed, 26 with the
  functions stubbed. The rest guard silence and over-reach, or test the
  instrument.
- **Spend: $16.63** across five directories, against the row's estimate of
  about $5.30. See the table in `BASELINE.md`. The extra went on the HEAD
  pre-measurement ($3.87), on adding 6385, on the A/B ($0.49), and on
  re-running the whole acceptance after the fix ($5.20).
- **Ledger (`plan_status`): 23 of 35 rows; 6 of 14 buckets closed, 2 partial
  (B5 on P3.7, B12 on P5.2).** The primary bucket is closed for 18 of 41
  sessions and partial for 5.

**The design.**
- **One line, always.** The case-law statement is a clause inside the
  legislation line, whether that line is fresh (P2.2) or carried (P2.8). It
  stands alone only when neither exists, which covers every `case_law_only`
  turn. Both the Manager and the Deep Research seams fall back to it. This
  makes the handover's hazards 3 and 4 impossible rather than merely
  handled: P2.8's last-line parse still sees its own line, and `corpus` never
  counts two.
- **The wording** is the verified fact: *"It holds Scottish appeals decided by
  the UK Supreme Court, but not the decisions of the Court of Session (Inner
  or Outer House), the Sheriff Appeal Court, the Sheriff Courts or the High
  Court of Justiciary, so judgments it returns for a Scottish question may
  come from courts outside Scotland."*
  - It does not say "Privy Council", "comprehensively" or "no Scottish case
    law".
  - It avoids "does not index" and "no judgments", both of which trip
    `NEG_ASSERTED`.
- **The record** is `record_case_law_search`. It is self-gated and runs on the
  memo path too. It marks an errored search as not `ok`, so the line says
  "attempted … returned an error" rather than "searched".
- **The record stays out of `worker_scope_block`.** A case-law-only step would
  otherwise get a block demanding "the search terms above" with none above,
  which is P2.9's defect again.
- **The prompt-side statements now agree with the code.** They are the
  case-law Worker, the hybrid Worker, the Scotland filter note, the tool
  description and the zero-result note. None says "comprehensively", and none
  claims the Privy Council as a Scottish route.

**Surprises / deviations from FIX_PLAN:**

- **6373's half was live, and it was the WORKER's, triggered by a structural
  event.**
  - At HEAD, all three Worker reports blamed FrankieH's correct citation:
    *"It is possible the citation contains an error"*, *"please verify the
    year and SSI number"* and *"It appears there may be a confusion with …
    SSI 2021/170"*.
  - Each report was written straight after `get_legislation_text` returned
    `Legislation not found: ssi/2026/170`. The model reads a direct not-found
    as proof the id is wrong. The twelve pre-P2.4 directories hold 36 such
    results, 31 of them in the two sessions where a citation was questioned
    (6409 and 6373).
  - The Manager relayed the blame in 2 of 3 reps. One of those was a
    substitution (*"It is possible you are referring to the 2021
    Regulations"*) that `NEG_BLAMED_USER` misses. It is the only such miss in
    the corpus.
  - So the fix was built at three seams, in code where it could be:
    `not_held_note` on the not-found result, `_not_held_limb` in the worker
    block, and a one-line rule in both legislation Manager prompts.

- **The code note did not change the Worker, and in the acceptance it never
  fired.**
  - In the smoke run the Worker read the note and still wrote *"there may be
    a typo in the citation … please verify"*. The Manager filtered it, so the
    lawyer saw nothing wrong.
  - In neither n=3 sweep did any 6373 run call `get_legislation_text`. The
    pass therefore comes from the prompt rules. The note is a tested seam
    whose effect on the model is unmeasured.

- **A prompt fix cost the lawyer case links, and only an A/B showed it.**
  - The same rule, as a block appended to the four Worker prompts, gave a
    clean 6373 (0 of 6 slots blamed at either level).
  - But in 6385 the chat-mode Worker switched to bullet lists: 0 of 9 reports
    before, 5 of 9 after. The chat-mode Manager rewrites bullets and drops
    the link wrapped round each case name. Case-law links reaching the answer
    went **7 of 15 → 2 of 13**.
  - Measured as an A/B at n=3 (`wave2_p24_ab` at `6806fa0`, without the block;
    `wave2_p24` at `8006db9`, with it). The only runtime difference between
    the two commits is that block.
  - Fixed by giving the chat-mode Worker the rule as one clause inside its
    existing OUTPUT bullet. That bullet is also where its blame phrasing came
    from (*"try a fuller search in Research mode"*). The three research-mode
    Workers keep the block, and 6375's research path linked more cases with
    it, not fewer.
  - **The acceptance was re-run in full on the final code**
    (`wave2_p24_final`), because 6373 and 6375's turn 1 use that prompt.
    `wave2_p24` is kept as the A/B's "with" side and must not be read as the
    acceptance.
  - Worker-level blame on the final code is 1 of 6 slots (*"… or check the
    citation"*, filtered by the Manager). With the block it was 0 of 6, and at
    HEAD it was 3 of 6. n=6 cannot separate the first two.
  - **The Manager dropping links from a rewritten report is pre-existing.** In
    the A/B's "without" side, 1 of 3 turn-1 answers lost both links from a
    prose report. It is a candidate for P4.3 (B8, sources) and has not been
    built.

- **P4.5 closed its trap on a lawyer for the first time, in the
  pre-measurement.**
  - In `wave2_p24_pre/6375 r3 t2`, Deep Research step 1 ran three
    `search_case_law` calls that returned 4, 43 and 31 judgments, including
    *Berezovsky v Hine*.
  - Its final completion then came back empty three times, so its report is
    `""`.
  - The synthesis told the lawyer *"Step 1 found no results"*.
  - Four more followed in this session's sweeps. The running count, from
    `blanks`, is **6 unrecovered provider calls in 166 answered turns**
    across the seven schema-v3 directories (95% Wilson interval 1.7–7.7%).
    Five were in workers. One was a Manager call, covered by P4.2's labelled
    fallback, and the case-law line still reached that answer. Four of the six
    ended in *"Upstream idle timeout exceeded"*. Recorded on P4.5's row.

- **`SCOTS_CASELAW_GAP` over-reads, and my replacement's first version did
  too.**
  - The old detector fires on a court's bare name. Over the twelve pre-P2.4
    directories it hits 26 turns, 22 of which searched no case law; only one
    of those 22 (`wave1/6408 r1 t3`) states the gap.
  - My detector at first counted *"the Rules of the Court of Session 1994 …
    do not contain an explicit provision"* (`baseline/6372 r3 t2`).
    `--answers` over case-law turns could not see that turn, because it
    searched no case law. `--all --answers` found it. A court's name inside an
    instrument title is now masked.
  - Also corrected before publishing: a claim in the FIX_PLAN row that none of
    the 22 was a real statement.
  - **And a census, a third time.** The code comment and both drafts said
    the corpus held "40 not-found results, 32 of them in 6409 and 6373".
    That count silently included `wave2_p24_pre`, and even then the split
    was 35. Over the twelve pre-P2.4 directories it is **36, 31 of them**.
    The comment was fixed after the acceptance (comment only; the run files
    still name `051472d` truthfully).
  - **So the instrument was wrong three times this session, and every time
    in the direction of a cleaner story.** Each was caught by re-running a
    command over every directory instead of the ones in view. That is
    Session 13's lesson again: read the output of a branch that has never
    met real data.
  - One known over-read is left in place. 6341 and 6348 say *"the available
    database does not contain information on Scottish case law"* on 6 turns
    with no case-law search. That can only move the all-turns column, never
    the acceptance.

- **The pre-measurement paid for itself twice.** It showed 6373's half was
  live and located its trigger. It also gave 6375 a like-for-like
  before-column; the handover had only `baseline` and `wave1`, both of which
  predate P2.2. It cost $3.87.

- **Costs ran over the row's estimate.** 6375 ran at $0.70–1.49 and 6.7–9.3
  minutes per rep, against $0.94 and 6–7 minutes.

**Decisions taken this session:**
- **The gate:** any turn that called `search_case_law` (row recommendation
  (i); the user was told and did not object). A retrieval by URL alone does
  not count, and there is a test for that.
- **The case-law line is not suppressed by `scope_unknown`.** It claims only
  the case-law searches this turn recorded, and those ran.
- **No carried case-law line.** A no-search follow-up in a case-law session
  gets nothing. The pass bar is "every turn that searched case law". This is a
  recorded residual.
- **Not a lawyer-facing "not held" clause.** "Is this instrument held" is
  P3.7's, and a footer cannot stop the prose questioning a citation.
- **The research-mode Worker prompts keep the rule as a block, and the
  chat-mode Worker gets it as a clause**, per the A/B.
- **`SCOTS_CASELAW_GAP` and `NEG_BLAMED_USER` are left unchanged.** Both
  publish numbers. **From P2.4 on, `compare`'s `scots_gap_disclosures` counts
  the code's line.**
- **The line fires on English-law case-law questions too.** It adds ~420
  characters to each 6385 answer (XL Bully cases), and a 6375 Deep Research
  line runs to ~1,800 characters with every clause present. This extends
  P2.2's and P2.8's clutter trade, and the only structural alternative (a
  jurisdiction filter) misses 6375, which ran with none. The user was told
  the gate but was not asked about this cost separately, so **it is the
  decision from this row most open to being overruled.**
- **Product code was committed before each paid sweep**, so every run file
  names its code: `6806fa0` (smoke and A/B), `8006db9` (`wave2_p24`) and
  `051472d` (`wave2_p24_final`).

**How this session worked, for whoever repeats it.** The scratch scripts that
did these went with the session.
- **Run every exit-1 check on a directory**, from `server_py/`:
  ```
  for c in halts negatives derivations blanks scoperecord nosearch caselaw; do
    python -m tools.replay_report --dir ../docs/prepilot-fixes/evidence/replay/DIR $c > /dev/null
    echo "$c $?"
  done
  ```
  Exit 1 means findings. A directory from before P2.4 exits 1 on `caselaw` by
  design, because its UNDISCLOSED rows are the before-column.
- **Measure the before-column at HEAD.** Pin, start a server on HEAD, replay
  into `<row>_pre`, then build. Source edits made while that server runs do
  not reach it, because modules load at startup. Commit before starting the
  post-fix server.
- **To A/B an earlier commit without touching the working tree:**
  1. `git worktree add --detach C:/Temp/<name> <sha>`.
  2. Copy `server_py/.env` in. It is gitignored, and the server needs it.
  3. From the worktree's `server_py/`, run `tools.replay pin`, then uvicorn,
     then `tools.replay run --out-dir <absolute path into the main tree's
     evidence/replay/>`, then `tools.replay restore`.
  4. Delete the copied `.env`, then `git worktree remove --force`.

  The run files name `<sha>`, because `replay.py` reads `git_head` from its own
  checkout.
- **To prove the tests fail without the fix:** copy `server_py/` to a scratch
  directory, and apply string substitutions there. One run removes the wiring;
  the other stubs the functions to return `""`. Then run the row's test files
  in that copy, so the working tree is never touched.
- **To stop a server started with `&`:** the task tool cannot see it. Get the
  PID from `netstat -ano | grep ":8000 " | grep LISTEN`, then run
  `taskkill //PID <pid> //F`.
- **The heredoc backslash trap bit again.** A `python - <<'EOF'` edit whose
  string literal held `"\\n\\n"` did not match `src/prompts.py`, which is
  CRLF on disk (`read_text`/`write_text` preserve CRLF on Windows). The Edit
  tool made the same change cleanly.
- **Replay timings, measured this session:**
  - 6375: $0.70–1.78 and 7–11 min per rep.
  - 6373: $0.14–0.29 and 1–8 min.
  - 6385: $0.14–0.24 and 1.5–15 min; one rep stalled on upstream idle
    timeouts.

  For P2.7, budget 6341 from `wave2_p28`: $2.1–2.8 and 14–21 min per rep.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1125 tests green.** Ledger:
**23 of 35 rows, 6 of 14 buckets closed, 2 partial**. B12 waits on P5.2
alone. Wave 2's only open row is **P2.7**.

**Machine state a new session inherits:**
- **No uvicorn running.** The dev box is **restored** (`moonshotai/kimi-k3`,
  local prompt cache ON, no pin file).
- **Five new replay directories**, seventeen in all:
  - `wave2_p24_pre`: HEAD `4890573`, 6375 ×3 and 6373 ×3. The like-for-like
    before-column.
  - `wave2_p24_smoke`: `6806fa0`, n=1 on 6375, 6373 and 6385.
  - `wave2_p24`: `8006db9`, n=3 on all three. The A/B's "with" side, **not**
    the acceptance.
  - `wave2_p24_ab`: `6806fa0`, 6385 ×3. The A/B's "without" side.
  - `wave2_p24_final`: `051472d`, n=3 on all three. **The acceptance.**
- **New command:** `replay_report --dir <dir> caselaw [--all] [--answers]
  [--drops] [--before DIR --only S…]`. It joins the exit-1 set: `halts`,
  `negatives`, `derivations`, `blanks`, `scoperecord`, `nosearch`,
  `caselaw`.

**Next action:**
1. **P2.7** is Wave 2's last open row, and it is the critical path to
   **P3.1**. Its evidence is 6341 (see its row). **Read the Session 14 note at the
   end of its row first:** prompt rules move the discovery count (P2.4 cut
   6373's turn-2/3 tool calls from 35 to 14), so derive the budget from
   directories produced at `051472d` or later, or say which prompt the
   distribution was measured under.
2. **P4.5** now has a measured false negative that reached a lawyer, plus a
   rate (6 in 166, 1.7–7.7%). The candidate fix must cover the Deep Research synthesis
   as well as the Manager.
3. **Still with the user:** **P5.2** (the LEX question in
   `WAVE5_QUESTIONS.md`) is what B12 now waits on. An alternative Scottish
   case-law supplier is also still unresearched.
