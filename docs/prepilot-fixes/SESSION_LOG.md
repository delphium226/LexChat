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
  metric cannot ask whether a URL was ever *returned by a tool*. Provision URLs that no tool
  returned went **327/327 (100%) → 26/136 (19%)**. Before P1.4 the prompt *told* the model to
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
- **Compare with `replay_report compare --before <baseline> --after <dir>`**, which defaults to
  rep 1 on both sides. Do not compare directories whole.

**Decision after the sweep (user, 2026-09-15):** **no wave-by-wave merging.** The branch is completed in full and pushed to `main` once, at the end. This reverses the original policy in *Merging back* and in the root `CLAUDE.md`, both now amended, along with the standing memory note. The accepted consequence: the target keeps running the pre-pilot code — including B2 — until that push. A later session must not push a finished wave early on its own judgement.

**Next action:** **P1.6** (cheapest row on the page, deterministic acceptance, no replay needed), then **P2.1** with the rewritten acceptance — and read its cap note before touching
`max_turns`. P1.6 is available in parallel and is the cheapest row on the page. Note that **no
session in the Wave 1 column is recorded as fixed**: it is n=1, and Wave 0's repetitions overturned
three of nine negative verdicts, so any row claiming a fix still needs n=3.
