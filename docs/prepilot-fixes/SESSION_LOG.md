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
PUSHED**. Whole-plan-then-one-push stands. **1125 tests green** (1130 after the
handover's `discovery` tests). Ledger:
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

**Added at the handover: P2.7's pre-flight.** It was done at the user's
request so that the P2.7 session re-derives nothing.
- **New command: `replay_report discovery`.** It prints discovery calls per
  worker run, halted and completed, and what a budget of N would have
  blocked. It is a measurement, so it always exits 0. It has 5 tests, taking
  the suite to 1130.
- **Its first real data corrected it twice before anything was published:**
  - `wave1` showed 0 halted runs, because audit schema v1 has no `halted`
    field. It now falls back to the report marker, as `halts` does, and labels
    that count a floor.
  - Its repeat count keyed on tool + resource + query, which hid 6335's shape.
    It now also prints production's tool + resource key.
- **A Session 13 claim corrected.** 6341 halts in **5 of 6** reps (2 of 3 in
  `wave2_p25`, 3 of 3 in `wave2_p28`), not in every rep. It is struck through
  in `BASELINE.md` and in P2.7's row.
- **The facts themselves** (code seams, the stop-message hazard, the
  distribution, evidence and costs, open design questions) are in P2.7's
  FIX_PLAN row, under *"PRE-FLIGHT FACTS … verified at `adc8929`"*. They are
  not repeated here.

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

---

## Session 15 — 2026-09-17 — P2.7 (the legislation discovery budget), and Wave 2 closed

**Done:**
- **P2.7 built and accepted.** A legislation Worker now gets **8 ReAct rounds
  in which `search_legislation` may run**, per worker run
  (`src/utils/discovery_budget.py`). **Wave 2 is complete (10 of 10)**, so
  **P3.1 (the keystone) and P4.1 are unblocked** — both depend on `P2.*`.
- **Acceptance: halted worker runs 15 → 2, halted turns 12 → 2, and
  `sources_kept` per rep ROSE in both sessions** (6341 57.7 → 59.3, 6374 35.0
  → 35.7). `wave2_p27` at head `bbb5416`, n=3 on 6341 and 6374, against a
  like-for-like HEAD before-column `wave2_p27_pre` at `7a98e60`.
- **New row P3.8** — the same-resource retrieval shape — **placed in Wave 3,
  not Wave 2**, because P3.1 and P4.1 depend on `P2.*` and a P2 row would
  re-block the keystone. It also carries the observation that a halted worker
  discards every finding it had.
- **New tooling.** `replay_report discovery` now prints search ROUNDS per run
  (rebuilt from `started_at`), refused calls, a K table, and
  **`--before DIR --only S`**, this row's pass bar (halts and `sources_kept`
  per turn slot). `_ran()` keeps a refused call out of every count of searches
  that ran, at seven sites.
- **66 new tests** (1130 → 1196). Proven to fail without the fix: 14 with the
  wiring removed, 20 with the functions stubbed, 3 more with the instrument
  guard removed. The rest guard the parliamentary paths, silence, over-reach
  and fail-soft.
- **Spend: $30.84** ($13.58 before, $3.69 smoke, $13.57 acceptance) and about
  3h 20m of replay, against the row's ~$25 and 3-3.5h.
- **Ledger (`plan_status`): 24 of 36 rows; 6 of 14 buckets closed, 2 partial.**
  P2.7 maps to no bucket, so no bucket count moved, exactly as the handover
  said.

**The design, and the decisions put to the user before building.**
- **The unit is ROUNDS, not calls, and this is the row's real finding.** The
  cap counts rounds and the model batches: 6341 completes delegations that
  issue 9-21 searches in 6-16 rounds. Over the post-P3.5 pool, halted runs
  search in a median of **14 rounds** (min 6) and completed ones in **2** (p90
  5, max 9), so **K=8 stops 11 of 13 halted and 1 of 149 completed**, where the
  best call budget (N=10) stops 8 of 13 and **9** of 149 — and the nine are
  6341 delegations that finished.
- **A memo-served search is charged**, so the check runs BEFORE the memo
  lookup: 57 of the 81 memo hits on halted runs repeat the same step's own
  search. By round, a Deep Research step reusing an earlier step's search pays
  at most one round.
- **`search_case_law` is not budgeted**; no halted run ever issued one.
- **The lawyer gets one clause inside the existing footer line**, and the agent
  gets a stop that is explicitly NOT the parliamentary one (which says to
  answer that "no relevant records were found" — the bare negative P2.2
  exists to stop).
- All four were put to the user with the numbers, and all four recommendations
  were taken.

**Surprises / deviations from FIX_PLAN:**

- **The handover's unit was wrong, and only the round distribution showed it.**
  Fitting N issued calls looked reasonable on the row's own table; the same
  data split by round separates halted from completed runs almost cleanly
  (median 14 vs 2). The pre-flight had every number needed to see this and
  drew the per-call table instead. **Where a budget and a cap count different
  things, measure in the cap's unit.**

- **The budget's effect is attributable on ONE of the two sessions, and the
  write-up says so.** 6341: the budget fired in all three reps (4, 3, 3
  refusals), halts 5, 2, 3 → **0, 0, 0**. 6374: **one refusal in three reps**,
  halts 3, 1, 1 → 1, 1, 0 — inside the noise. Invariant 4's *n=3, all clean* is
  carried by 6341 alone. Reporting "halts 15 → 2" without that split would
  claim twice the evidence there is.

- **The two halts that remain are the ones the row predicted it could not
  touch.** Both are 6374 turn 4 step 3, at **6 and 8 search rounds** — at or
  under the budget, so it never fired — with their 20 rounds spent on
  retrieval (13 section searches and 10 same-resource repeats in one). That is
  P3.8's shape, and it is why P3.8 exists.

- **A prose drop that looks like Invariant 1 and is not.** 6374 turn 2 shrank
  in all three reps (6,640/9,263/8,786 → 5,914/5,507/6,643) with `sources_kept`
  8.0 → 4.0. **No refusal ever fired on that turn.** Its Deep Research plan was
  drafted with 4 steps rather than 3 (34 searches → 12, 36 section searches →
  23): the planner stochasticity the replay configuration records as a
  confound for every replayed DR turn. Checking the refusal count per turn is
  what separated it from an effect.

- **A noise floor had to be measured before the pass bar could be read.**
  `sources_kept` per turn slot "fell" in 3 of 8 slots between `wave2_p25` and
  `wave2_p28` — two 6341 sweeps differing only by P2.8, which does not touch a
  researched turn. After the budget it fell in 2 of 8 and 2 of 4. **Build the
  comparison, then measure what it reads on a pair where nothing changed**,
  before quoting it on the pair where something did.

- **`caselaw` exits 1 on the acceptance, and the cause is the model writing
  its own footer.** 6341 rep 2 turn 2 carries two `*Search scope:` lines; the
  first is the model's imitation, mid-answer ("among 8 searches in total"; "no
  filters were applied"), which `strip_answer_footer`'s end-anchor cannot
  reach. **It is not from the budget**: that turn had no refusal, no limb, and
  its "8 searches" is its own 8 calls — the collision with K=8 is a
  coincidence, and checking the turn's refusal count is what showed it. Base
  rate **1 in 513 answered turns since P3.5's echo strip (95% Wilson
  0.03-1.10%)**; the only other instance is `wave2_p22_final`, which predates
  the strip and has 18. Booked to the footer family. **If it recurs, its row
  goes in Wave 4** — a P2 row would re-block P3.1 and P4.1.

- **`derivations` exits 1 before AND after, with the same count.** 2 UNVERIFIED
  claims on 6374, P2.3's residual shape, also present in `wave2_p23` and
  `wave3_p35`. Running the exit-1 set on the **before** directory is what made
  that a known quantity instead of a scare at the end.

- **The smoke run earned its keep on a cosmetic defect.** The worker limb
  printed `""shop" means"` and `""meaning of \"shop\""`: the model quotes and
  backslash-escapes its own queries. Fixed with the footer's own clean-up, and
  the acceptance ran on the commit that includes it.

- **A model sentence about a budget stop trips `HALT_PARAPHRASE`** ("a system
  limit"), which `summary` and `compare` count as halt language. They run only
  over full sweeps, and `halts` is unaffected because a halted turn always
  carries P2.1's code notice. Worth remembering at the next full sweep.

- **P4.5 gained a seventh instance**, in the before-column:
  `wave2_p27_pre/6374 r3 t4`, a Deep Research step whose report is its scope
  block alone after three empty completions. The synthesis covered the gap
  from the other steps and asserted nothing false, so the trap did not close
  on the lawyer. Running count: **7 unrecovered provider calls in 250 answered
  turns (95% Wilson 1.4-5.7%)**.

**Decisions taken this session (all four put to the user, all four accepted):**
- **8 search rounds**, counted per worker run, memo hits included.
- **`search_case_law` unbudgeted**, with no case-law budget on `case_law_only`.
- **One clause in the lawyer's existing footer line**, not a prepended notice
  (a budget stop still produced a report, so a halt-style banner overstates it)
  and not agent-only (P2.2 measured instruction-only at 56%).
- **The section-search shape becomes its own row (P3.8), not this one.**
- Two more taken without asking, and stated here: the legislation efficiency
  profile gets a `budget_blocked` **indicator band only** (no breach rule, the
  reformat band's reasoning — a budget stop is the designed outcome of a broad
  question); and the parliamentary branch now also tests `"remaining" in
  search_budget`, so a parliamentary tool name hallucinated under a legislation
  budget is not a `KeyError`.

**How this session worked, for whoever repeats it.**
- **Start the paid before-column first, then build while it runs.** The server
  loads modules at startup, so edits to `src/` do not reach a running sweep,
  and `replay.py` stamps `git_head` once at the start. The pre-measurement and
  the whole build overlapped.
- **To count ReAct rounds from a run file**, group a delegation's tools by
  `started_at` with a gap of ~1s: the calls of one round start together and
  rounds are separated by an LLM call. Checked against the halt metadata: the
  rebuilt count equals the halt metadata on **58 of 58** halted runs, across
  all ten directories that have one. `replay_report discovery` prints that agreement
  every time, so a drift in the method shows up where it is used.
- **Watch the server log during a sweep** for `no ReAct round` — the budget's
  fail-open path. Thirty minutes of silence on a live sweep is the evidence
  that a ContextVar written in `chat_loop` reaches the tool tasks.
- **The heredoc backslash trap, avoided this time**: every edit carrying
  backslashes or CRLF files went through the Write/Edit tools or a Python
  script operating on bytes. `FIX_PLAN.md`, `SESSION_LOG.md` and `BASELINE.md`
  are all CRLF; `Path.write_text` would rewrite the whole file.
- **Replay timings, measured this session:** 6341 $2.25-2.96 and 13-21 min per
  rep; 6374 $1.43-2.67 and 8-17 min.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1196 tests green.** Ledger:
**24 of 36 rows, 6 of 14 buckets closed, 2 partial**. **Wave 2 is complete.**

**Machine state a new session inherits:**
- **No uvicorn running**, and the dev box is **restored** (`moonshotai/kimi-k3`,
  local prompt cache ON, no pin file). Re-pin before any measurement.
- **Twenty gitignored replay directories.** The three new ones:
  - `wave2_p27_pre`: head `7a98e60`, 6341 ×3 and 6374 ×3. The before-column.
  - `wave2_p27_smoke`: head `a38ff98`, n=1 on both.
  - `wave2_p27`: head `bbb5416`, n=3 on both. **The acceptance.**
- **New command surface:** `discovery` gains `--before DIR`, search rounds, a
  K table and a refused-calls line. It still always exits 0.

**Next action:**
1. **P3.1** (B10, right Act wrong depth) is the keystone and is now unblocked.
   Its row says to verify `_slim_search_results`'s docstring claim about the
   ranked sections array **against a live response** before building on it.
2. **P3.8** is deliberately parked behind P3.1: measure the same-resource shape
   again after Phase 2 changes, with `discovery --all`.
3. **P4.5** has a rate (7 in 250, 1.4-5.7%) and a measured false negative that
   reached a lawyer; its fix must cover the Deep Research synthesis.
4. **Still with the user:** **P5.2**, which is what B12 waits on.

**Added at the handover (2026-09-18).** Before the next session, what this
session knew was checked against what had been written down. Five gaps, all
closed in `FIX_PLAN.md` except the last:
- **P2.1's halt residual, recounted over every post-P2.1 directory: 1 FAIL in
  42 halted turns.** Its row said "1 in 24", counted over six directories;
  `wave2_p22` and `wave2_p28_smoke` add 4 halted turns it never included, and
  P2.7's three directories add 14, all passing.
- **P4.5's own row now carries the new count** (7 in 250, 1.4-5.7%) and the new
  instance (`wave2_p27_pre/6374 r3 t4`). It had been written only on P2.7's row
  and in `BASELINE.md`, where a P4.5 session would not look.
- **"Booked to the footer family" was not yet true.** The model-written footer
  (TWO_LINES, 1 in 513) had been recorded only on P2.7's row. It is now on
  P2.8's row as well.
- **P2.3's row notes that its 6374 residual recurs** at the same 2 claims in
  both P2.7 directories, so a future `derivations` exit 1 on 6374 is read as
  that residual.
- **The `repo-map` skill gained `discovery_budget.py` and `search_scope.py`.**
  The second had been missing since P2.2, although every Wave 2 row wrote into
  it. Note that `.claude/` is gitignored, so the skill lives on this machine
  only.

**One question nobody has decided, now on the recommended-order line:
Invariant 3 says "re-baseline before Wave 3", and no row holds that
re-baseline.** The last full sweep is `wave1`, taken before every Wave 2 row.
P3.1's own acceptance is per-session and depends only on P1.5, so it can
proceed without one. Whether it should is the user's call, and it should be
made before P3.1 is built, not during it.

---

## Session 15, continued — 2026-09-18 — Thomas's external review folded in; the Fix Tracker

**Done:**
- **Thomas's review mapped and folded in.** He sent nine proposed actions
  (`2026-09-10-lexchat-developer-actions.md`, reviewed against `main`). Every
  action now has a place: four new rows (**P3.9**, **P3.10**, **P4.6**,
  **P4.7**), notes on P3.4, P3.8, P4.1, P4.3 and P4.5, `docs/TODO.md` **B6**
  (action 8, outside the plan), and four items held as *to be verified* in the
  plan's new **External review** section, which also maps all nine.
- **The Fix Tracker**: a one-line-per-fix table shared with Thomas, published as
  a private page, <https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>. Source:
  `docs/prepilot-fixes/summary-table.html` (a `ROWS` array at the top of its
  script). **Update it only when the user asks**, normally at the end of a
  session (FIX_PLAN "How to use this file", step 7).
- **Ledger: 24 of 40 rows** (4 added). B5 now also waits on P4.6 and P4.7. No new
  row is in Wave 2, so P3.1 stays unblocked.
- No product code changed. No replay spend.

**How each new number was measured — the scripts were throwaway, so the method
is recorded here in full.** Directories are under
`docs/prepilot-fixes/evidence/replay/`.
- **P3.9, the case-law date filter (live, read-only, 2026-09-18).** `GET
  https://caselaw.nationalarchives.gov.uk/atom.xml` with `query=Evans`,
  `court=ewca/crim`, reading each `<entry><published>`. With no dates, with
  `date_from=2025-01-01&date_to=2025-12-31` (what `executor.py` sends), and with
  `from_date`/`to_date`: the same 50 entries, 2024-2026, first 2026-07-17. With
  `from_date_0=1&from_date_1=1&from_date_2=2025&to_date_0=31&to_date_1=12&to_date_2=2025`:
  19 entries, all 2025. Scale: `search_case_law` tool records whose `args` carry
  `date_from` or `date_to`, over every directory: 19 of 569 (all 6385); no run
  file's `filters` sets a date.
- **P3.10, dependent plan steps.** For every turn with a `plan`, steps 2..n
  whose `title + " " + detail` matches (case-insensitive)
  `\b(identified (in|by|above|earlier)|(from|in) (step|the previous|the earlier|step \d)|previous(ly)? (step|identified)|those (instruments|regulations|orders|acts)|these (instruments|regulations|orders|acts)|the (instruments|regulations|orders|SSIs|Acts) (identified|found|located)|identified SSIs|identified (instruments|regulations|orders))\b`.
  A step's halt is its delegation's `halted`, or `[Research halted` in its
  report (schema v1), joined on the step number. Over every directory: 136
  plans, **34** with a dependent step; dependent steps 42, halted 12 (29%);
  other steps 452, halted 53 (12%).
- **P4.6, the scripted negative.** `available database does not contain
  information`, case-insensitive, on `replay_report._without_footer(answer)`:
  22 answered turns in each of `baseline` (of 190 legislation_only) and `wave1`
  (of 122), none of them calling `search_case_law`. Over every other directory,
  `(available )?database does not contain information`: 34 of 482 answered
  turns (6340, 6341). The case-law Worker's own scripted line is `prompts.py:253`.
- **P4.5, 6363.** In `baseline/6363` rep 1 turn 5, Deep Research step 1's tools
  include a `raw_result` containing *Wheat* and its `report` is empty (0 chars);
  step 2 is empty too; `wave1/6363` rep 1 turn 5 step 1 is empty as well.
- **P3.4, the filter note.** `prompts._JURISDICTION_EXTENT_NOTES["scotland"]`
  begins *"Prioritise legislation where extent includes S or E+W+S+NI"*.

**Surprises / deviations from FIX_PLAN:**

- **The same issue had been raised before and lost.** Thomas's action 2 is
  `docs/TODO.md` **D17**, from an external review in August, with a better fix
  (a per-mode synthesis prompt, which also stops Holyrood Deep Research reports
  being told to write an in-force section). Memory recorded D16 and D17 as
  "folded into the fix plan" when the freeze lifted. **D17 never was**, and
  neither were **four of D16's items** (see the open question on the
  recommended-order line). D17 is now P4.7. **Lesson: a "folded in" claim is
  checked by grepping the plan for the item, not by remembering it.**

- **A prompt instructs a defect our plan had read as model behaviour, a third
  time.** `prompts.py:180` scripts *"The available database does not contain
  information on this specific issue"*, and the model says it verbatim in 22
  turns per full sweep. P4.1's handover item (1) met the sentence and treated it
  as behaviour. P2.5 recorded this pattern as a lesson; it still took an
  outside reader to apply it here.

- **Our classification missed three things Thomas found.** 6365 and 6405 (graded
  PASS) carry a "no case law found" in legislation-only answers, and 6363's
  "no foundational authority" is P4.5's empty-report trap, which we had filed
  under corpus recency (B12). **A frozen classification is evidence, not
  ground truth.**

- **An instrument error at the handover, in the unflattering direction.** P3.10
  was first published as "14 of 136 plans"; the regex behind that count missed
  "the identified SSIs", while the halt rates beside it used a broader one.
  Re-run with one regex, it is **34 of 136**. Caught by re-running every number
  before writing the method down. Corrected with a strikethrough on the row.

- **A filter that silently does nothing, found by a live probe, not by
  transcripts.** P3.9 is B2's shape again (the jurisdiction filter), and like B2
  no pre-pilot session revealed it; a three-request probe did. Session 5's
  method lesson — probe the live API before reading transcripts — applies to the
  case-law API as much as to LEX.

**Decisions taken this session (the user's):**
- The table's columns: Source (T / R / T & R), Fix, Status, Plan ref, Thomas ref.
- Status values: Fixed / In progress / Verified / To be verified. **No "Not
  recommended"**: proposals we would argue against are "To be verified".
- The table is an artifact, **updated when the user asks**, normally at the end
  of a session.
- Thomas's suggestions go into the plan where applicable (done).

**Open with the user:**
1. Re-baseline before Wave 3 (Invariant 3), or not.
2. Whether D16's four unplanned items become rows.
3. Whether Thomas's document (and his two companion notes) should be committed
   to the repo. It paraphrases lawyers' questions at about the level of detail
   this plan already carries.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. 1196 tests green. No server running; the dev box is restored.

**Next action:** settle the two open questions, then **P3.1** (the keystone).
Of the new rows, **P3.9** is the cheapest (deterministic, the fix is known) and
blocks nothing.

---

## Session 16 — 2026-09-18 — the Wave 2 re-baseline, and P3.1 (B10, right Act wrong depth)

**Done:**
- **Both open questions decided by the user at the start.** (1) Re-baseline:
  yes, at HEAD `2d9ae11`, before any P3.1 code. (2) D16: only the
  one-call-per-Act rule is taken, folded into P3.1; the year window,
  over-fetching and the title check stay parked in `docs/TODO.md` D16 (whose
  claim that the year window "sits in row P2.2" was false and is struck).
- **`wave2`, the Wave 2 re-baseline**: n=1 over all 41 sessions, $29.55, 4.0 h,
  0 mismatches, 0 errored turns. Written up in `BASELINE.md`, *The Wave 2
  re-baseline*. It is the Wave 3 baseline.
- **P3.1 built and accepted, with two residuals booked by the user.** 6396 0/3
  -> 3/3, 6365 0/3 -> 3/3, 6348 turn 1 0/3 -> 1/3 (`wave3_p31`, n=3 at
  `779bfb2`, $3.34). New row **P3.11** for 6348's residual.
- **New instrument, `replay_report depth`**, committed before any sweep
  (`fd5213c`), with three later fixes (`03a4c66` the head column, `00a0c8a`
  the strict readout, `19504eb` the `rail_sources` rename).
- **Tests 1196 -> 1334** (138 new, 97 of them P3.1's product tests). Proven to
  fail without the fix on a scratch copy of `server_py/`: 33 fail with the
  wiring removed, 37 with the functions stubbed; of those, 6 and 9 fail only
  incidentally (a removed dict key; a stubbed `""` that is not JSON; a stub
  that does not warn). The rest of the 97 pass in both, by design: P1.6/B14
  safety for pinpoint labels, the ranked-array decision pins, the
  no-prompt-names-a-graded-provision guard, silence, over-reach and
  fail-soft.
- **Ledger (`plan_status`): 25 of 41 rows; 6 of 14 buckets closed, 3 partial**
  (B10 now partial, waiting on P3.11). Primary bucket closed for 18 of 41
  sessions, partial for 11.

**What the measurement said before anything was built.**
- **Retrieval was complete in 9 of 9 HEAD runs.** Every provision the three
  lawyers wanted arrived with all its subsections, in one section search for
  6348 and 6396. Depth was lost after retrieval, at three seams: the Worker's
  write-up, the Deep Research synthesis, and the chat Manager's rewrite.
- **A prompt taught the defect, the fourth time** (P2.5, P2.4, P4.6 before it):
  every legislation Worker's citation example was a whole-section label, and
  the quick-lookup Worker was told to cite "Act + section".
- **The ranked sections array would have steered Phase 2 the wrong way.** It
  ranks against the title search the prompt prescribes: it omits FOISA s.36
  and SSI 2007/174 Sch 1. The row called it "the cheapest precision win
  available"; for these sessions it was neither.

**Decisions taken (all put to the user, all recommendations taken except the
last):**
- Ranked array: not used; docstring says why.
- Depth: prompts at all three seams, code only if the smoke run showed a seam
  still flattening. It did (the synthesis), and the user chose the
  **pinpoint block** over a repair call.
- One-call rule: **relaxed to three and capped in code** (3 ReAct rounds per
  instrument per worker run), the user's choice over my recommendation to
  leave it.
- n=3 kept for the acceptance after the user asked why (Invariant 4's
  promotion clause: 6365 flipped DELIVERED/SHALLOW across baseline reps with no
  code change).
- Booking: DONE, with 6348's turn 1 as **P3.11** and the wrong-pinpoint rate as
  a watch item.
- Taken without asking, and stated here: the quick-lookup Worker keeps its
  one-call phrasing (the code cap applies to it anyway); the research Manager
  prompt is unchanged (6348's depth was lost in the Worker's report, not the
  pass-through).

**Surprises / deviations from FIX_PLAN:**

- **The row's premise was the wrong layer.** P3.1 was written as a Phase 2
  change (use the ranked array, relax the one-call rule). Measured, Phase 2 was
  already complete in every acceptance run; the loss was in composition. Only
  the pre-measurement showed this, and it is the fourth row whose defect a
  prompt instructed.

- **The first grader was lenient, and HEAD is what showed it.** "At subsection
  depth at least once" was met on two of 6365's anchors by amendment notes
  (*"substituted Section 57(7)(a)"*) while every timeline claim linked the bare
  section. A strict readout (N of M references at depth) now prints beside the
  verdict and separates the runs cleanly: delivered 50-95%, the lawyer's
  complaint 0%, HEAD 0-17%.

- **My own first prompt examples would have contaminated the acceptance.** They
  used "Sch 1 para 1(2)" (6396's exact answer) and "s.21(2)" (a 6365 anchor): a
  model copying the example's FORMAT could land on the graded provision by
  accident. Caught on review before any spend; a test now pins it.

- **The first smoke run earned its keep twice.** 6365's synthesis rewrote every
  link label to the bare section despite the new prompt sentence (which met the
  user's condition for code), and 6348's rule was gated on "the answer turns on
  one section" when 6348's first answer cites six provisions in two Acts, so it
  never fired. Both fixed before the paid n=3.

- **A new failure mode the fix exposes: a wrong pinpoint.** 6365 rep 2 cites
  s.57(1) for the interim-report period (s.57(3)(a)), three times, from a step
  Worker's report. A whole-section citation was coarse but right; a wrong
  subsection reads as verified, and P1.6 cannot catch it because the URL is
  right. 3 of 34 timeline pinpoints after, 0 of 20 before. Watch item.

- **Three instrument errors of my own, all caught before publishing.** (1) A
  scratch prose count of -62% across Wave 2 was mine: I joined each session's
  answers before stripping the end-anchored footer, which then ate every later
  turn; recomputed per answer it is +22%. (2) The depth panel's source column
  was named `sources_kept` but counted the rail's list, not
  `timing.sources_kept` (6365: 3.3 -> 2.7 against 8.3 -> 8.0); renamed
  `rail_sources` before either number was written up. (3) The wrong-pinpoint
  checker flagged `s.57(3a)` and a correct `s.21(1)`; both read by hand.

- **Two re-baseline numbers are not what `compare` prints.** In-force claims
  "30 -> 61" is the old detector reading P2.5's own footer (P2.5's `currency`
  grader: 43 -> 3); `nosearch`'s one UNQUALIFIED (6363 t5) is P2.5's required
  disclaimer on a turn that does carry P2.4's case-law line.

- **The heredoc backslash trap bit twice more**, once as a literal backspace
  byte in a regex (`\b` became 0x08) and once as a carriage return in a Windows
  path. Both caught by checking bytes rather than trusting a passing test.

**How this session worked, for whoever repeats it.**
- **Seed rep 1 from a full sweep.** Copy the three sessions' `wave2` files into
  the pre-measurement directory; `replay run` skips files that exist, so
  `--reps 3` then runs reps 2-3 only. The acceptance seeded 6348's rep 1 from
  the second smoke run the same way (same commit, same configuration).
- **Find the seam before designing.** For each run: grade the worker reports
  (joined) and the answer separately with `depth_verdict`, and check the raw
  API responses for the target provisions with their subsections. That split
  (retrieved / in the report / in the answer) is what located every loss.
- **Grade each run as it lands.** A monitor on `-> <sid>_repN.json` lines lets
  a broken change be stopped after one run instead of nine; it replaced a
  separate smoke run for the synthesis change.
- **When the user says pause, stop the server too.** Stopping the replay client
  does not stop a request the server is already running.
- **The fail-without-fix recipe, with this row's exact substitutions** (the
  script went with the session; this is what it did). Copy `src`, `tests`,
  `tools`, `pytest.ini` and `.env` from `server_py/` to two scratch copies, then:
  - *wiring removed*: `elif section_budget_blocks(...)` -> `elif False:` in
    `agent_shared.py`; the `_section_budget_limb` call and the
    `_section_budget_footer_clause` line out of `search_scope.py`; the
    `pinpoint_block` line out of `agent_core.py`; the `_PINPOINT_BLOCK` strip
    out of `strip_scope_blocks`; `"size": 10` -> `"limit": 10`; the section keys
    out of `new_search_budget`; and `src/prompts.py` replaced by
    `git show 2d9ae11:server_py/src/prompts.py`;
  - *functions stubbed*: `section_budget_blocks` -> `False`,
    `section_stop_message` / `instrument_key` / `_section_budget_limb` /
    `_section_budget_footer_clause` / `pinpoint_block` -> `""`,
    `record_section_budget_stop` -> `None`.

  Run the row's test files in each copy and diff the PASSED/FAILED sets: a test
  that passes in BOTH copies is a guard by design, and the report must say which.
- **Facts established live this session** (2026-09-18), recorded here and in the
  `external-apis` skill (which is gitignored, so this is the durable copy):
  `/legislation/search` reads `limit`, `/legislation/section/search` reads
  `size` and ignores `limit`; `/legislation/section/lookup` returns every
  provision of an instrument with its text (FOISA 83 items / 177 KB, WI(S)A 98 /
  283 KB, SSI 2007/174 24 / 55 KB, 0.1-0.2 s each), which is the route to a
  provision BY NUMBER; `number` is `None` for any non-integer provision id
  (inserted sections, dotted rules, Parts, one malformed uri), while the `uri`
  keeps the real id; a regulation's `provision_type` is `section`, and a
  schedule paragraph's text is rendered `Section 1)`. The acceptance ground
  truth (FOISA s.36, WI(S)A ss.45 and 57, PFA(S)A ss.21 and 22, SSI 2007/174
  Sch 1 para 1) was read from the live text and is encoded in `DEPTH_TRUTH`.
- **Replay timings, measured this session:** 6348 $0.54-0.58 and ~4 min per
  rep (4 turns); 6365 $0.61-0.79 and ~4-5 min (Deep Research); 6396
  $0.06-0.08 and ~1 min.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1334 tests green.** Ledger: **25
of 41 rows, 6 of 14 buckets closed, 3 partial.**

**Machine state a new session inherits:**
- **No uvicorn running**, and the dev box is **restored** (`moonshotai/kimi-k3`,
  local prompt cache ON, no pin file).
- **Five new replay directories**, twenty-five in all: `wave2` (the full
  re-baseline, `2d9ae11`), `wave3_p31_pre` (the before-column),
  `wave3_p31_smoke` (`d2f9b48`), `wave3_p31_smoke2` (`779bfb2`, 6348 only;
  stopped by the user) and `wave3_p31` (the acceptance). `wave2` is a full
  sweep and may be fed to `compare`; the others may not.

**Next action:**
1. **P3.8** is the natural next: P3.1 already installed a per-instrument cap on
   section searches, so it is a measurement against `wave2` on the sessions that
   looped (6335, 6338, 6382, 6374 turn 4), plus the halted worker's lost
   findings.
2. **P3.2, P3.3, P3.4 and P4.3** are unblocked by P3.1.
3. **P3.11** (6348's residual) is small and measured: a code-side subsection
   outline, n=3 on 6348 alone (~$1.70).
4. **Still with the user:** P5.2 (B12); and, carried from Session 15 and not
   yet decided, whether Thomas's review document (and his two companion notes)
   should be committed to the repo.

---

## Session 17 — 2026-09-21 — `seam_replay`: iterate on a seam, not a session

**Done:** the user asked whether testing could cost less on OpenRouter, so
before starting P3.8 this session built `tools/seam_replay.py` and validated it
for **$0.35**. No product behaviour changed; `agent_core.build_synthesis_messages`
was extracted so the product and the harness share one definition of the Deep
Research synthesis payload. 14 new tests (1334 -> 1348).

**Where the money goes, measured over `wave2`** ($29.55, 41 sessions, 155
turns): Deep Research turns are **20 turns and 48% of spend** ($0.71 each);
conversational 87 turns / 30% ($0.10); research 48 turns / 22% ($0.14). **14
turns carry 45%** of a sweep and **8 sessions carry 53%**; the cheapest 77
turns cost $4.16 between them. That shape is why the answer is "stop replaying
whole sessions to test a prompt", not "use a cheaper model".

**What the tool does.** It rebuilds ONE seam's input from a stored run file —
the synthesis (plan, step findings, halts) or the Worker's composition (the
brief plus that delegation's recorded tool results) — and makes the single
model call, with no server. Measured: **Worker $0.03 a draw against $0.55 for
a 6348 replay; synthesis $0.11 against $0.61-0.79 for the turn.** Everything
upstream is frozen, so it cannot test retrieval and cannot produce an
acceptance. `--without-fix` rebuilds the seam at an older revision (prompt
constant read out of git, pinpoint block stripped), `--dry-run` builds the
payload and calls nothing.

**Surprises:**

- **The validation found a property of P3.1's own fix.** `pinpoint_block` reads
  only markdown **link labels**, so it fires solely because the Worker prompt
  change made the steps write pinpoints inside links. Links whose label carries
  a subsection, per 6365 run: **0, 0, 1 before the fix and in the smoke run;
  15, 31, 50 in the three acceptance runs**, where the block fired with 4-5
  URLs. The two halves of P3.1 are coupled — the block cannot help a Worker
  that cites in bold. A future row that changes how Workers cite must re-check
  this, and a cheap improvement is to harvest pinpoints from prose next to a
  link to the same section.
- **The A/B I expected to run could not be run on the fixture I expected.** The
  flattening happened in the smoke run, whose findings carry no pinpointed
  links at all — so with or without the block that payload is identical. On
  the acceptance fixture (where the block fires) both sides DELIVERED at n=1:
  with rich pinpointed findings the old prompt keeps them too. Read together
  with the run files, that says the Worker prompt change did most of the work
  and the block is insurance. Not re-litigated: P3.1 is accepted and the
  acceptance stands on the full replays.
- **The Worker seam reproduced 6348's failure immediately:** SHALLOW in 4 of 4
  draws (2 current, 2 pre-P3.1), which agrees with the acceptance's 1-in-3 and
  is now P3.11's before-column, measured for $0.12 instead of $1.65.
- **My "a few cents, 20-50x cheaper" estimate was optimistic for the synthesis
  seam**: its payload is ~40K chars, so a call is $0.11 and the saving is
  5-8x, not 20x. The Worker seam is the 18x one. Quote the measured numbers.

**One lever that cannot be audited from our data, checked this session.**
`cached_prompt_tokens` is **0 on every run file**, and that is not evidence
that provider prompt caching is failing: OpenRouter reports a cache discount
only for Anthropic models, so any implicit Gemini saving is already inside the
billed price and invisible to us. Whether the replay traffic is being
discounted therefore cannot be read off a sweep; it would need a deliberate
paid experiment (the same call twice, timed inside and outside the implicit
cache window). Not run.

**Other levers, recorded not built** (in FIX_PLAN's *Verification protocol*):
replay only up to the graded turn; exclude Deep Research sessions from a row
that cannot touch them; reuse run files when `git diff <rev> HEAD --
server_py/src` is empty; a cheap model for plumbing smokes only. **Not** a
cheaper model for graded runs (it is the model the pre-pilot ran on), **not**
the local prompt cache inside a sweep (reps stop being independent), **not**
n below the invariant.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. 1348 tests green. Ledger unchanged: **25 of 41 rows**.

**Machine state:** no server running; dev box restored (`moonshotai/kimi-k3`,
cache ON). `tools.replay pin` was used for the four validation calls and
restored afterwards.

**Next action:** **P3.8** (measure with `discovery --all` against `wave2`,
then its acceptance), or **P3.11**, whose before-column is already measured
and whose iterate loop is now $0.03 a draw.

## Session 18 — 2026-09-21 — P3.8 (the same-resource loop, and the halted worker's lost findings)

**Done:**
- **The user chose P3.8 before P3.11** (put to them with the costs at the
  start; P3.11 stays next, its before-column already measured on the seam).
- **Measured first, at HEAD, before building** (`wave3_p38_pre`, head
  `b7f9f96`, 6335 n=3, $2.52, 19 min): **P3.1's cap already removes 6335's
  halt** — turn 7 halted in 1 of 1 at `wave2` and in **0 of 3** now, with 3
  section searches per rep where `wave2` made 18 (17 on one resource, 10
  exact repeats); the section budget refused a fourth in reps 2 and 3 and
  the worker wrote its report. The turn's prose went 627 -> 2,933 chars per
  rep, from *"could you narrow this down?"* to an answer.
- **The write-up round built** (Thomas's action 3): at the step cap
  `chat_loop` in both providers makes ONE more call with no tools and
  `halt_writeup_instruction` appended (`utils/research_halt.run_halt_writeup`),
  bounded by `_final_round` and fail-soft to the pre-P3.8 halt. The halt keeps
  its status (`halted.written_up`, audit schema **v4**) and P2.1 keeps its
  disclosure: the worker's agent-addressed header now says the findings are
  PARTIAL and sits above them, the lawyer's notice is unchanged, and
  `incomplete_steps_note` tells the synthesis the findings are partial rather
  than missing.
- **Acceptance:** **PASSED** (`wave3_p38`, head `1243cdd`, n=3 on 6374 and 6383, **$9.60**, 77 min). **One worker run halted in the six runs — 6374 rep 1, turn 2, Deep Research step 3 — and it wrote up:** `written_up: true`, 20 rounds, 27 tool calls, a 5,490-char partial report with 10 provision links, **10 of 10 tool-returned and 10 of 10 reaching the answer** beneath P2.1's notice; the synthesis's own BLUF says that part of the research *"did not complete due to an internal limit on tool-call rounds"*, every negative in the write-up names the limit as the reason, and no agent-facing header text leaked. `halts` 1 halted turn, 0 failing; every exit-1 subcommand exits 0. Sources per rep: 6374 42.0 (45.0 at `wave2`, n=1; 35.7 at `wave2_p27`), 6383 14.0 (12.0); `sources_kept` fell in 1 of 4 slots for 6374 and 0 of 4 for 6383, inside the 3-of-8 floor. **Coverage stated honestly, as P2.1's 6384 was:** 6383 halted in 0 of 3, so its live condition is vacuous; the round is evidenced live by one run and on the seam by four draws.
- **Instruments.** `replay_report halts` prints `wrote` (written-up / halted
  runs per turn) and a total; `discovery` prints the section-search rounds on
  one instrument (max per run) and the count of runs above P3.1's cap of 3;
  `seam_replay worker` on a HALTED fixture closes with the product's own
  instruction, so a draw there IS the write-up round.
- **Tests 1348 -> 1376** (28 new, in `tests/test_halt_writeup.py`; the
  chat-loop ones run the REAL loops on a mocked transport). Proven to fail
  without the fix on a scratch copy of `server_py/`: **13 with the wiring
  removed, 16 with the functions stubbed**; 10 pass in both by design
  (silence, fail-soft, P2.1's text unchanged, the instrument). Two P2.1
  assertions now expect `written_up: False` on a halt that arrives without
  the key.
- **Two new rows, both measure-first:** **P4.8** (the `[Research Agent
  Result]` label leaking into an answer: 2 of 21 turns in the before-column
  against 0 of 930 since `wave1`) and **P3.12** (a paragraph of a Schedule
  asked for by number where LEX holds the Schedule as one provision — why
  6335 looped; see Surprises).
- **Spend: $12.58** ($2.52 before-column, $0.21 + $0.25 seam draws,
  $9.60 acceptance).
- **Ledger (`plan_status`): 26 of 43 rows; 6 of 14 buckets closed, 3 partial (P3.8 maps to no bucket, so no bucket moved).**

**Surprises / deviations from FIX_PLAN:**

- **The row's first half was already done, and it was only ever a fifth of
  the problem.** Counted with one method over every replay directory (1,542
  worker runs, 100 halted; `replay_report discovery`, the new section-rounds
  line): an instrument section-searched in more than 3 rounds — the shape
  P3.1's cap stops — is in **19 of the 100 halted runs** (and 23 of 1,442
  completed). The other 81 are the discovery flail P2.7 removed, or
  retrieval-bound runs neither budget touches: `wave2_p27/6374 r1 t4 step 3`
  at 2 section rounds on one instrument, 6365 step 3 at 1. That is why the
  write-up round is not optional even with both budgets in place — a halt
  still happens, just rarely, and until now it threw away everything.

- **Why 6335 looped, found by probing, not by reading the model.** It
  searched the Insolvency Act 1986 eighteen times for *"Schedule B1 paragraph
  43"* and got Part A1 sections every time. `/legislation/section/lookup`
  returns **674 provisions for the Act and Schedule B1 is ONE of them** — no
  paragraph rows exist, and the paragraph query never ranks the Schedule
  into the top 10 (a topical query at `size` 20 does). The model was asking
  for a granularity the index does not have. The cap now stops it; the lawyer
  still does not get paragraphs 42-44, and that residual is **P3.12**, not a
  widening of this row.

- **A `sources_kept` fall that is B7, not this row.** The pass bar reads
  "fell in 3 of 7 turn slots" for 6335 (noise floor 3 of 8), and all three
  are turns 4-6, where the lawyer repeats one case-law question in
  legislation-only mode. At `wave2` the Manager delegated every repeat and
  a Worker searched statute for case law; at HEAD it answers two of the
  three repeats without re-delegating ("as previously noted ... switch to
  Legislation & Case Law mode"). Worker runs per rep 7 -> 5 is that. Checking
  per-turn delegation counts is what separated it from an effect, as it did
  for 6374 turn 2 at P2.7.

- **The tool-result label leaks.** 6335 rep 3's turns 3 and 5 open with the
  literal `[Research Agent Result]`. Counted over 1,088 turns: 7, five of
  them in `baseline`/`wave1`, then 0 in 930 until these 2. Cosmetic, the
  same class as the raw halt marker P2.1 strips, and now **P4.8**.

- **Two seam draws for $0.21 settled the design before a line was written.**
  Fed 6335's halted retrievals to a tool-free composition call: both drew a
  structured partial report whose every link a tool had returned, and both
  said the Schedule B1 paragraphs were not retrieved rather than inventing
  them. The seam tool then took the product's instruction for halted
  fixtures, so the four acceptance draws (6335 t7, 6374 r2 t4 step 3; $0.25)
  are the round the product makes: 49 links, 49 tool-returned, every
  negative of the *"not retrieved because the limit was reached"* shape, no
  timeout language.

- **The instruction's first draft would have tripped a detector if echoed.**
  "Do not describe this stop as a timeout" contains the word `HALT_AS_TIMEOUT`
  matches outside a negation. Reworded to "not a time limit, not an error"
  before any spend, and a test now runs both detectors over the instruction
  and the header.

- **P1.6 rewrote my own test fixture.** Three tests failed because the
  fixture's provision links were ones no tool had returned, and the product
  unlinked them — the B14 fix doing its job on a fake. The fixture is now
  link-free and says why.

- **A halt without `written_up` is normalised to `False`, and two P2.1
  assertions moved.** Every halt now states whether the write-up produced
  anything, so a stubbed or pre-v4 halt gains the key. The alternative — only
  adding it when present — would have left the trace ambiguous exactly where
  a harness needs it least.

- **Seam-tool halted delegations: the `--delegation` index is the list
  position, not the step number.** They coincide in 6374 r2 t4 (step 3 is
  the third delegation); check before drawing on a fixture where they may
  not.

- **The halt the acceptance caught is the shape neither budget touches, and
  the round salvaged it.** 6374 rep 1's halt was on turn 2, step 3 (not turn
  4, where `wave2_p27` halted it): 8 search rounds (P2.7 refused one), 10
  section searches over several instruments with no instrument above 3
  rounds (P3.1's cap never fired), 6 change lookups — retrieval-bound. Its
  write-up carried 10 tool-returned links into the answer, and the synthesis
  wrote the limit into its own BLUF unprompted. 6374 halted 1 of 3 here
  against 2 of 3 at `wave2_p27` and 0 of 1 at `wave2`: halting is
  stochastic on this session and the count is not a trend.

- **6383 did not halt in 3 of 3, so its live condition is vacuous** — the
  same honesty P2.1 recorded for 6384. It is still the right session to have
  run: it is the row's evidence session that halted most recently
  (`wave3_p35`), and it now costs $0.68-0.95 per normal rep.

- **A $1.62 conversational turn, and it is P4.2's mechanism, not this
  row's.** 6383 rep 1 turn 3 took 768 s: two completions of ~58,000
  reasoning characters each that emitted no content (`finish_reason=stop`),
  retried and recovered on the third attempt for a 1,429-char answer. The
  bounded retry worked; the cost of a thinking model thinking to nothing is
  what it is. Recorded on P4.2/P4.5's family, with 6374 rep 1 turn 1 (three
  empty completions with `finish_reason=error`, covered by P4.2's
  report-fallback): **P4.5's running count is now 8 unrecovered provider
  calls in 329 answered turns (95% Wilson 1.2-4.7%)** over the 16 schema-v3
  directories (the earlier 7-in-250 was the ten P2.4/P2.7/P2.8 directories;
  P3.1's four add 46 turns with 0, this row's two add 33 with 1).

- **`derivations` exits 0 on a 6374 sweep for the first time.** Every earlier
  6374 directory carried P2.3's residual (2 UNVERIFIED claims); `wave3_p38`
  carries 0 in three reps. Not claimed as a fix — nothing here touched it
  and the residual was itself stochastic — but the handover's "exits 1 on
  any 6374 sweep" is no longer a rule.

- **The write-up round's cost, measured live:** about 20 s between the cap
  and the written-up log line, on a 27-tool context; the run's total was
  $1.90 against $1.71-2.08 for the two reps that did not halt.

**Decisions taken this session:**
- Put to the user: P3.8 before P3.11 (taken).
- Taken without asking, and stated here: the Manager's own loop gets the
  write-up round too (it is the same `chat_loop`, and 6383 turn 1's raw
  marker as the entire answer is the case it improves); the lawyer's notice
  is not reworded (it was validated at P2.1 and "treat the coverage below as
  partial" is true of a write-up); the A4 reformat stays skipped on a halt
  (the write-up carries the Worker's OUTPUT STRUCTURE rule and the header is
  prepended by code); the audit schema version is bumped to 4 for a key added
  inside an existing object, because the spec says any shape change bumps it;
  6374 and 6383 are the acceptance sessions because they are the two P3.8
  evidence sessions that still halted after P2.7 (6335 no longer does).

**How this session worked, for whoever repeats it.**
- **Start the paid before-column, then build while it runs** (Session 15's
  pattern). The server loads modules at startup, so edits do not reach a
  running sweep; the commit before the acceptance sweep is what stamps the
  head. Stop the old server before starting the acceptance one.
- **Prototype the round on the seam first.** `python -m tools.seam_replay
  worker --run evidence/replay/wave2/6335_rep1.json --turn 7 --reps 2` is
  the write-up round for 6335's halted delegation; `--run
  .../wave2_p27/6374_rep2.json --turn 4 --delegation 3` is 6374's.
- **Test a control-flow change in the loop against the real loop.**
  `test_stream_retry.py`'s MockTransport harness, with the request payloads
  recorded, is enough to assert "one more request, no `tools` key, the
  instruction last, the tool results still in front of it" — and to drive the
  model-calls-a-tool-anyway, empty-completion, HTTP-500 and cancel paths.
- **The fail-without-fix recipe, this row's substitutions** (script went
  with the session): *wiring removed* — `writeup = "" if _final_round else`
  -> `if True else` in both clients, `writeup=_writeup,` -> `writeup="",` in
  `agent_core.py`, the `written_up` branch of `incomplete_steps_note` and
  the halted branch of `seam_replay.worker_messages` -> `if False:`;
  *functions stubbed* — `halt_writeup_instruction` and `run_halt_writeup`
  return `""`, `halt_worker_report` discards `writeup`, the same two
  `if False:`. Run `tests/test_halt_writeup.py` in each and diff the sets.
- **Numbers behind commands:** the section-rounds count is `replay_report
  --dir baseline discovery --also <every other directory>`; the pass bar is
  `discovery --before wave2 --only 6335`; the write-up count is `halts`.
- **Replay timings, measured this session:** 6335 $0.69-0.94 and 5-8 min per
  rep (7 turns); 6374 $1.71-2.08 and 11-20 min per rep; 6383 $0.68-2.29 and 5-18 min, where the $2.29 rep is the one whose turn 3 spent two ~5-minute attempts producing nothing (see Surprises).

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1376 tests green.** Ledger:
**26 of 43 rows; 6 of 14 buckets closed, 3 partial (P3.8 maps to no bucket, so no bucket moved).**

**Machine state a new session inherits:**
- **No uvicorn running**, and the dev box is **restored** (`moonshotai/kimi-k3`,
  local prompt cache ON, no pin file). Re-pin before any measurement.
- **Twenty-seven gitignored replay directories.** The two new ones:
  `wave3_p38_pre` (head `b7f9f96`, 6335 x3, the before-column) and
  `wave3_p38` (head `1243cdd`, 6374 x3 and 6383 x3, the acceptance).
- Seam draws for this row are in the session's scratchpad only (not
  evidence; the run files are).

**Next action:**
1. **P3.11** (6348's residual): before-column already measured on the seam
   (SHALLOW 4 of 4); iterate the subsection outline at $0.03 a draw, then n=3
   on 6348 (~$1.70).
2. **P3.12** (schedule paragraphs) and **P4.8** (the label leak) are
   measure-first rows opened here; neither blocks anything.
3. **P3.2, P3.3, P3.4 and P4.3** remain unblocked by P3.1.
4. **Still with the user:** P5.2 (B12); whether Thomas's review document
   should be committed to the repo; and whether the Fix Tracker should be
   updated for P3.8 (it is updated only when asked).

**Added at the handover (2026-09-21, same day).** What this session knew was checked
against what had been written down before the next session starts. Closed:
- **P4.5's own row now carries the refreshed count** (8 in 329, 1.2-4.7%) and both
  P4.2 events from the acceptance sweep, where a P4.5 session will look for them
  (Session 15's lesson: a count written only on another row's line is lost).
- **P2.1's row carries the recount** (1 FAIL in 43 halted turns) and says what P3.8
  changed in a halted report and what it did not (the disclosure).
- **P2.3's row records that its 6374 residual did not recur** in `wave3_p38`, so a
  `derivations` exit 1 on 6374 is read as a possibility, not expected as a rule.
- **The Verification protocol's seam section says that a halted fixture IS the
  write-up round** on the Worker seam.
- **The `external-apis` skill records the Schedule-as-one-provision fact** (674
  provisions for `ukpga/1986/45`, Schedule B1 one row, no paragraph rows) next to
  the `section/lookup` entry. The skill is gitignored, so P3.12's row is the
  durable copy.
- **`docs/TODO.md` D18** records the user's question about making the step cap a
  tunable setting and the answer given: yes, as a startup `.env` value with the
  other three trip limits moved in the same change, never an Admin Portal toggle,
  and only after the replay run files stamp the value; deferred until the plan
  concludes.
- **The Fix Tracker is updated** (user request): P3.8 Fixed; P3.12 and P4.8 added
  as Verified (open rows with confirmed evidence), republished to the same URL.
Not in the repo, by design: the six seam draws and the two grading scripts live in
the session scratchpad; the run files (`wave3_p38_pre`, `wave3_p38`) are the evidence.

---

## Session 19 — 2026-09-21 — P3.11 (B10 residual: one subsection cited without its siblings)

**Done:**
- **P3.11 built and measured; the acceptance is NOT met and the row is not
  ticked.** 6348 turn 1 delivers s.36(2) with its substance in **2 of 3**
  (`wave3_p311`, head `84b8da5`, n=3, $1.40) against 0 of 3 before P3.1 and
  1 of 3 at P3.1's acceptance; the bar is 3 of 3. The outline is kept — it
  did the work in both delivering reps — and the miss is diagnosed (below).
  **What to do with it is the user's decision**, set out on the row and the
  recommended-order line. B10 stays partial.
- **Measured before building, and the row's caveat was the wrong way round.**
  The section search returns s.36 with both subsections in every stored run
  (P3.1 measured that); **the summariser keeps s.36(2) in 1 of the 11
  turn-1 summaries** (`baseline` only). "Summaries keep subsection numbers,
  so the outline is salience" is true of the subsections a summary mentions
  and false of the one it drops. So the fix is P1.6's pattern for P1.6's
  reason: the summariser cannot discard what it never saw.
- **The fix:** `utils/section_outline.py` — one line per numbered subsection
  of each provision with two or more, opening words with paragraphs folded
  in, labelled from the URL segment; appended in `run_worker_tool` on the
  SUMMARISED path only, after P1.6's URL block and before P2.2's scope note,
  outside the local-cache summary. Schedules skipped (P3.12), bounded at
  300 / 12 / 6,000 chars, stripped from answers whole and as a stray header,
  `[SECTION OUTLINE` on `scoperecord`'s leak list. No prompt change.
- **Two instruments first.** `seam_replay --from-raw` rebuilds each
  summarised result's appended blocks from its recorded `raw_result` through
  `agent_shared.summarised_result_blocks`, the product's own builder — the
  seam replays `final_result`, so without it this row's fix could not reach
  the seam. `replay_report depth --seams` grades a requirement at the
  summarised text the Worker was shown, the report and the answer, and says
  which subsections the summaries mention; it is what puts the 1-of-11
  behind a command.
- **Seam A/B, $0.31:** `wave3_p31_pre/6348 r1 t1` recorded SHALLOW (Session
  17's 4 of 4) → `--from-raw` DELIVERED; `wave3_p31/6348 r2 t1` recorded
  SHALLOW → DELIVERED; and the live miss's own payload (`wave3_p311 r3 t1`,
  outline present) → DELIVERED. Every link tool-returned; the block never
  echoed.
- **Tests 1376 -> 1419** (43 new). Proven to fail without the fix
  on a scratch copy of `server_py/`: **9 with the wiring removed, 20 with
  the functions stubbed**; 15 pass in both by design (silence, fail-soft,
  the unsummarised path, the guards).
- **Ledger (`plan_status`): unchanged at 26 of 43 rows; 6 of 14 buckets
  closed, 3 partial.**

**Surprises / deviations from FIX_PLAN:**

- **The summariser, not the Worker, drops the sibling.** The row and the
  handover both said "the summary keeps the subsection numbers" and located
  the loss in the Worker's write-up. Graded seam by seam, the summary
  mentions s.36(2) in 1 of 11 runs; the Worker's write-up was faithful to a
  summary that had already lost it. Session 16's split (retrieved / report /
  answer) had no "summary" column; `depth --seams` now has one, and it is
  the first thing to run on the next composition row.

- **The one miss is the shape the outline cannot reach.** Rep 3's Worker was
  shown s.36(2) twice — its summary kept it (the only `wave3_p311` summary
  that did) and the outline listed it — and wrote *"Section 36(1)
  (Confidentiality)"* alone in a 6,942-char, two-Act report. The same recorded
  payload replayed on the seam DELIVERED. So after this row the residual is
  the live loop's final write-up not obeying P3.1's rule with the sibling in
  front of it: obedience, not information. Invariant 2's next step is a
  code-emitted sibling line at the report seam; that puts code-written
  statute text into the lawyer's report and was not built on my own
  judgement (see Decisions).

- **A seam pass is not a live pass.** Three of three payloads DELIVERED on the
  seam (two fixtures and the miss itself); two of three reps did live. The
  seam composes in one tool-free round from the recorded results; the live
  Worker composes at the end of its own ReAct history. The tool's docstring
  said "an approximation"; this is the measured size of it for one row.

- **Temperature 0 makes a seam "rep" one sample.** The pinned provider config
  runs at temperature 0, and the two `--from-raw` draws on each fixture came
  back byte-identical. Session 17's four draws varied because they were two
  payloads. Quote draws per payload, not draws.

- **The seam tool could not test the row as built.** Session 17's tool
  replays `final_result`; a block the product appends from the raw result
  is invisible to it. `--from-raw` is the first seam option that changes the
  payload rather than the prompt, and it uses the product's builder so the
  two cannot drift.

- **The outline is as large as the summary it follows.** On FOISA (long
  sections) the 6,000-char cap is reached on nearly every summarised search
  (`depth --seams`: median 6,097 over `wave3_p31_pre`'s 36 searches, 6,248
  over `wave3_p311`'s 7). Charged to the context budget like every append;
  not a measured problem; recorded as a watch item rather than trimmed
  blind (rep 1's draw used s.29's outline, which a 4,000 cap would cut).

- **Links per answer fell in 4 of 4 turn slots against both before-columns**
  (5.3 -> 4.0, 5.3 -> 3.0, 6.0 -> 5.0, 5.3 -> 3.7). Two causes, neither
  settled: rep 3's turn 2 is a Manager clarification with no delegation (0
  links, 0 sources — also the `sources_kept` fall, 2 of 4 slots, floor 3 of
  8), and rep 1 wrote four sibling notes in prose at turn 1 with 3 links
  where P3.1's reps carried 4–7. A Worker holding the outline may write
  siblings as notes in place of links. n=3; a watch item, not a finding.

- **The readout learnt four ways a summary writes a subsection, three of
  them from this row's own runs**: `36(1)`; a bare `(1)` under a `Section
  36` heading; a numbered `1.` list (`wave3_p311 r2`); a bulleted bold
  heading with bulleted bold subsections (`wave3_p311 r3`). Each time the
  first version printed "none" for a summary that had listed (1). The
  1-of-11 was checked both ways before it was written down; the sweep's
  count (1 of 3, rep 3) came from the fourth fix.

- **The block's first rendering copied LEX's paragraph markers (`a)`).**
  Folded as `(a)`, the citation form, before any draw. A test pins it.

- **My own stray-header test was wrong, not the strip.** It put a close
  marker after the stray header, so the whole-block regex correctly ate the
  span between them. The pinpoint block's precedent test has no close
  marker; mirrored.

- **`_attribute_instrument` needs the Act named.** A `--seams` test whose
  synthetic report said "Section 36(1) only." graded MISSED, not coarse: the
  grader attributes a provision to an instrument by the nearest mention, and
  there was none. Worth knowing when reading a "missed" on a short summary.

- **The prompt-reader test fails on any scratch copy.** `seam_replay`'s
  `_prompt_constant_at("HEAD", …)` runs `git show` from the file's
  grandparent, and a scratch copy is not a repository — so the
  fail-without-fix diff shows one extra failure in both copies that is
  incidental (10 and 21 raw; 9 and 20 attributable).

- **The heredoc backslash trap, twice more**, both in byte-level regex edits
  (`\s` reaching Python as a single backslash). Both scripts rewritten with
  the Write tool; check the bytes of any regex edited through a heredoc.

- **The outline did not raise the wrong-pinpoint rate in the one 6365 rep run**
  ($0.92, optional): DELIVERED at the highest depth ratios recorded for the
  session (s.57 19 of 19 references at depth against 60–95% at `wave3_p31`),
  and the four watched timeline claims are pinned correctly (interim →
  s.57(3), where `wave3_p31` rep 2 wrote s.57(1)). n=1; it says the rate did
  not rise in this sample, nothing more.

**Decisions taken this session:**
- **Put to the user, not taken: what to do with 2 of 3.** (a) Iterate — a
  code-emitted sibling line at the report seam (where the report pinpoints
  s.N(k), the run's outline holds other subsections of s.N and the report
  mentions none, append their opening words under the citation; P2.1/P2.5's
  pattern, verbatim statute, Invariant 1 safe); design questions are
  placement and how many notes a report may gain; one more acceptance ≈
  $1.40 plus seam draws. (b) P3.1's precedent — DONE with the residual as a
  new row. (c) Leave it open at 2 of 3. No further 6348 reps were run on my
  own judgement: the bar is n=3 all clean, and running until it passes is
  not measurement.
- Taken without asking, and stated here: the outline is appended on the
  summarised path only (P1.6's reasoning: the unsummarised result has the
  text in full); Schedules are skipped rather than outlined by paragraph
  (P3.12's territory, and a subsection outline of one would mislabel sibling
  sub-paragraphs); the label comes from the URL segment (a copied `Section
  4)` would make the Worker write s.4(1) for reg. 4(1) — the wrong-pinpoint
  shape); no prompt change (the block's own header instructs, and the seam
  delivered with the block alone); the 6,000-char cap kept; the outline is
  kept in the product although the row is not ticked (it moved 1 of 3 to 2
  of 3, every exit-1 subcommand passes, and the miss is not its doing).
- Taken without asking, and stated here: the optional 6365 smoke was run
  (n=1, $0.92) because the brief invited it and an outline that names
  subsections with their opening words could plausibly move the
  wrong-pinpoint rate either way.

**How this session worked, for whoever repeats it.**
- **Grade seam by seam before designing** — `replay_report --dir <d> depth
  --seams` over every directory that holds the session. The column that
  moved the design was the summaries', which no earlier session printed.
- **Give the seam tool the block first, then draw.** `python -m
  tools.seam_replay worker --run
  ../docs/prepilot-fixes/evidence/replay/wave3_p31_pre/6348_rep1.json
  --turn 1 --dry-run`, then the same with `--from-raw`: the payload line
  says how many results carry an outline. Draw with `--reps 1` — at
  temperature 0 a second draw of one payload is the first again.
- **When a live rep misses, replay its own payload on the seam** (`--run
  wave3_p311/6348_rep3.json --turn 1`, as recorded): if the seam delivers,
  the miss is the loop's write-up, not the context.
- **The fail-without-fix recipe, this row's substitutions** (script went with
  the session): *wiring removed* — `result += summarised_result_blocks(name,
  raw_result)` -> `result += provision_url_block(raw_result)` in
  `agent_shared.py`; the `_OUTLINE_BLOCK.subn` line -> `n3 = 0` and
  `|SECTION OUTLINE` out of `_TOOL_BLOCK` in `search_scope.py`; `if
  from_raw:` -> `if False:` in `seam_replay.py`. *Functions stubbed* —
  `subsection_outline` redefined to return `""` at the end of its module;
  `_OUTLINE_BLOCK = re.compile(r"(?!x)x")`; `rebuilt_result` redefined to
  return the recorded result. Run `tests/test_section_outline.py` and
  `tests/test_seam_replay.py` in each and diff the sets.
- **Numbers behind commands:** the 1-of-11 is `depth --seams` over the seven
  6348 directories; the acceptance is `depth` on `wave3_p311`; the pass bar
  is `depth --before wave3_p31` and `discovery --before wave3_p31 --only
  6348`; the outline sizes are the last line of `depth --seams`.
- **Replay timings, measured this session:** 6348 $0.38–0.53 and 3–4.5 min
  per rep (4 turns); 6365 $0.92 and 7.4 min (one Deep Research turn).

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1419 tests green.** Ledger:
**26 of 43 rows; 6 of 14 buckets closed, 3 partial** (unchanged; P3.11 open).

**Machine state a new session inherits:**
- **No uvicorn running**, and the dev box is **restored** (`moonshotai/kimi-k3`,
  local prompt cache ON, no pin file). Re-pin before any measurement.
- **Twenty-eight gitignored replay directories.** The new one: `wave3_p311`
  (head `84b8da5` for `src/`; 6348 ×3 and 6365 ×1).
- Seam draws for this row are in the session's scratchpad only (not
  evidence; the run files are).

**Next action:**
1. **The P3.11 decision** (above) is the first thing to put to the user; the
   row and the recommended-order line carry the three options and the
   candidate's design questions.
2. **P3.12** (schedule paragraphs) and **P4.8** (the label leak) are
   measure-first rows; neither blocks anything. **P3.2, P3.3, P3.4 and P4.3**
   remain unblocked.
3. **Still with the user:** P5.2 (B12); whether Thomas's review document
   should be committed; whether the Fix Tracker should be updated (P3.11
   would show as Built / not accepted; it is updated only when asked).


**Added at the handover (2026-09-21, same day).** What this session knew was checked
against what had been written down. Closed:
- **P3.1's own row carries the watch-item re-read** (the 6365 smoke: 0 of 4 watched
  claims wrong, n=1), where a session reading that row will look for it.
- **P4.5's row carries the refreshed count** (`wave3_p311`: 13 answered turns, 0 empty
  completions; 8 in 342).
- **The Verification protocol's seam section says what `--from-raw` is for, that one
  payload is one sample at temperature 0, and that a seam pass is not a live pass**
  (this row's live miss delivered when its own payload was replayed there).
- **The P3.11 decision is on the row and on the recommended-order line**, with the
  candidate's design questions and its cost, so the next session does not have to
  re-derive it from this log.
Not in the repo, by design: the seven seam draws and the grading scripts live in the
session scratchpad; the run files (`wave3_p311`) are the evidence. The Fix Tracker was
not updated (it is updated only when asked; P3.11 would show as Built / not accepted).

## Session 19, continued — 2026-09-22 — the chat-mode default, and P0.5

**Done:**
- **Twelve replayed sessions have run in the wrong chat mode since the
  baseline, and a new row (P0.5) holds the fix, to be done first, in a new
  session (user decision).** Found while running the app for the user and
  answering *"why would some turns be Research if the flag was off during
  the pre-pilot?"*
- **The mechanism.** `replay_set.py` takes a non-Deep-Research turn's mode
  from the feedback snapshot's `Filter: Chat mode` and otherwise from
  `DEFAULT_CHAT_MODE = "research"`. The export's mode field is blank for the
  15 sessions run on 11–13 August (6332–6351), before the field existed, and
  their snapshot is blank too. So all 48 "Research" turns in every sweep
  carry `chat_mode_source: "default"` — a guess, set when the harness was
  built (`bc8e7a4`) and documented only in a docstring.
- **The evidence.** The research Worker's report headings appear in 0 of 38
  recorded pre-pilot answers of those sessions and 0 of 64 of the 24 sessions
  recorded as Conversational; in the replay's Research-mode answers they
  appear in 39 of 48 (`baseline`) and 42 of 48 (`wave2`), and in its
  Conversational-mode answers 0 of 87. 6348's four pre-pilot answers: none,
  about 700 chars each; every replay of 6348: all four, 3,500+ chars.
- **Recorded where a session will look:** the P0.5 row (the twelve sessions,
  the rows they touch, the three steps and their cost); the
  recommended-order line; a *Chat mode per turn* row in the Replay
  configuration table; a mode caveat appended to P3.1, P3.8, P3.11, P4.1 and
  P4.6; `BASELINE.md`, *The chat-mode default*; memory.
- **The Fix Tracker updated (user request):** P3.11 to In progress (built,
  2 of 3, pending the Conversational-mode re-run); P0.5 listed as the one
  measurement row on the tracker, because it qualifies other rows.
- The app was run for the user (uvicorn on 8000, login, frontend served) and
  stopped; no paid turn was sent. Spend unchanged at $2.63.

**Surprises:**

- **A harness default is a claim about the data, and this one went unchecked
  for nineteen sessions.** Session 12 recorded "a replay cannot test what the
  export never recorded" for `research_mode`; the same export gap in
  `chat_mode` was filled with a value instead of flagged, and it happened to
  be the value that runs the more capable Worker. Every before/after on those
  sessions is internally consistent and externally wrong.
- **The shape of an answer is a mode detector.** The research Worker's
  OUTPUT STRUCTURE headings pass through the Manager and never appear in a
  conversational answer (0 of 151 recorded and replayed conversational
  answers). That is the instrument P0.5 asks for, and it is the same trick
  `dr_marker` already uses for Deep Research.
- **The feature flag is a UI gate only.** `research_mode_enabled` is read by
  the Developer tab's storage and by the frontend (Sidebar hides the option,
  App.jsx bounces a stored preference); nothing in `agent_request.py`,
  `system.py` or `ai.py` checks it, so any API caller runs Research with it
  off. Not a row unless the user wants it to be a real switch (the seam would
  be `build_request_config`).
- **P3.11's numbers are of the wrong Worker.** The lawyer met the quick-lookup
  Worker, which has no "say what the other subsections provide" rule; the
  outline itself is appended in both modes. The row's decision is deferred
  behind P0.5.

**Machine state a new session inherits:** no uvicorn running; dev box
restored (`moonshotai/kimi-k3`, local prompt cache ON, no pin file); 28 replay
directories; nothing pushed.

**Next action (the new session):** P0.5, steps (1) to (3) in order, then
P3.11's decision on the Conversational-mode numbers.

---
## Session 20 — 2026-09-22 — P0.5 (the chat-mode default), and five rows re-checked

**Done:**
- **P0.5 is DONE, all three steps, $8.42.** The twelve sessions now have a
  Conversational-mode replay, every turn of every run file carries a chat
  mode that is evidence rather than a default, and the table the row rested
  on is behind a command.
- **(1) Instrument.** `replay_set.answer_shape` reads a turn's mode off its
  recorded answer the way `dr_marker` already did: `deep_research` |
  `research` | `conversational` | `None` (no text to read).
  `_resolve_modes` resolves in that precedence — DR marker, then a recorded
  `Filter: Chat mode` snapshot, then the answer marker, then, for a turn that
  got no reply, **the nearest answered non-Deep-Research turn of its own
  session** (`neighbour`), preferring the one before. Deep Research is
  excluded as a neighbour: it is one-shot and the frontend reverts, so a DR
  neighbour says nothing about the turn beside it, and copying one would
  replay an unasked-for $0.71 turn. Sources over the 62 sessions: `snapshot`
  108, `conversational_marker` 52, `dr_marker` 27, `neighbour` 9.
  `DEFAULT_CHAT_MODE` is now `conversational` and is **unreachable here**.
- **The snapshot still wins where the export recorded one**, so the 29
  snapshot-carrying sessions read byte-identical to every sweep already
  taken, and `mode_report` checks the marker against it: **0 disagreements,
  both directions, 108 turns.** That is what earns the marker the right to
  decide the turns where the field is blank.
- **`replay_report modes`** prints per-turn mode and evidence, the
  ran-as × answer-shape cross-tab that *is* P0.5's table, and the export's
  own answers; it **exits 1** on a guessed mode or a conversational turn that
  answered like the research Worker, so it joins the exit-1 set. Tests
  **1419 → 1442**; 15 of the 22 new ones proven to fail on scratch copies of
  `server_py/` with the derivation reverted (3), the resolver stubbed (7),
  the marker stubbed (6) or `modes`' graders removed (6). The 7 that stay
  green in all four are invariants that hold in both worlds by design.
- **(2) Replay.** `wave0_conv`, head `223293e`, n=1, 50 turns, **$3.84**
  against a $6 estimate. `modes` exits 0 and **0 of 48 conversational turns
  produced a research-shaped answer**, against 42 of 48 in `wave2`. Every
  exit-1 subcommand 0 except `caselaw` (the pre-P2.4 before-column shape, by
  design). Re-measured with the corrected marker over every directory:
  `baseline` 39 of 48, `wave1` 41 of 48, `wave2` 42 of 48, Conversational
  0 of 87 in all three.
- **(3) Three re-checks, each written on its own row.**
  - **P2.1 / P3.8 halts on 6335, 6338, 6340: ZERO.** 7 worker runs, 0 halted,
    against 3 of 14 at `baseline` and 1 of 11 at `wave2`. The quick-lookup
    Worker issues a median of 1 discovery call and 2 retrievals, nowhere near
    the 20-round cap. Neither ticked row is undermined — both rest on wider
    evidence and the halt machinery is mode-blind — but those three sessions
    cannot evidence a halt rate at all in the mode their lawyers used.
  - **P4.1 / B7 reproduces, for the first time in any sweep, and displaces
    the defect it was confused with.** See *Surprises*.
  - **P3.1's 6348 half and P3.11: 1 of 3 at HEAD, 0 of 3 at `2d9ae11`**
    (`wave0_conv_6348` $3.09, `wave0_conv_6348_pre` $1.49). The user asked
    for the before-column the row did not require, and it is what makes this
    readable: the outline moves 6348 by the same one step in both modes.
- **Ledger 26 → 27 of 46** (two new rows: **P0.6**, the research-mode
  default; **P3.13**, the Manager seam). 6 of 14 buckets closed, 3 partial.
- **Dev box restored** (`replay restore`), A/B worktree removed.

**Surprises / deviations from FIX_PLAN:**

- **B5's false negative and B7's deflection are one defect in two modes, and
  only one of them ever reached a lawyer.** In Research mode 6346 and 6347
  delegate to a Worker that makes zero tool calls and writes *"The available
  database does not contain information on this specific issue"* under a
  Summary Answer heading. In Conversational mode that shape is **gone** —
  `nosearch` reports 0 delegations with zero tool calls and `negatives`
  **exits 0** — and what appears instead is B7: 6346, the corpus's only 1/1
  session, deflects on **5 of 5** turns against 0 of 5 in Research mode. So
  the standing "known exit on 6346/6347, not a regression" note in P4.1 and
  in Session 16's instrument note **was an artefact of the wrong mode**, and
  the note is now wrong as written. Two defects had been booked where there
  is one, seen through two prompts.
- **P4.6's scripted sentence was never seen by a lawyer.** It appears in
  **0 of 179** pre-pilot answers and 0 of 50 `wave0_conv` turns, against 20
  of 50 in `wave2`. The line lives in `WORKER_SYSTEM_PROMPT` and not in
  `WORKER_SYSTEM_PROMPT_CONVERSATIONAL`, and the Research flag was off on the
  target throughout. The row stays valid — the line is live and fires the
  moment Research mode is enabled, which is the point of a pilot — but it is
  a forward-looking fix, not a reproduction, and its headline counts are
  replay artefacts of the P0.5 default.
- **P3.11's loss moved one seam down when the mode was right.** P3.11
  diagnosed the summariser (1 of 11 Research-mode summaries kept s.36(2)).
  In Conversational mode the summariser keeps it in 2 of 3 and **rep 3 loses
  it at the MANAGER**: the Worker's report says *"A related exemption in
  s.36(2) applies to information obtained from another person where
  disclosure would constitute an actionable breach of confidence"* and the
  answer keeps s.36(1) and s.50(5) and deletes that sentence. **This
  mis-scopes P3.11's option (a)** — a code-emitted sibling line at the report
  seam cannot help a Manager that deletes the sentence. Opened as **P3.13**,
  measure-first. The outline is not the constraint: non-empty for 14 of 14
  section searches, median 6,176 chars, so it reaches the quick-lookup
  Worker; that Worker simply has no rule telling it to use it.
- **The prompts make the marker structural, not lucky.**
  `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` says *"Do NOT use formal report
  headers (BLUF, Detailed Analysis, References, etc.)"* while
  `WORKER_SYSTEM_PROMPT`'s OUTPUT STRUCTURE demands them. The same comparison
  confirms P3.11's caveat: P3.1's sibling rule is in the research Worker's
  OUTPUT STRUCTURE item 2 and has **no counterpart** in the quick-lookup
  prompt.
- **The instrument was wrong twice, both times in code written this session,
  and both were caught by a count that did not add up.** (a) `tr.prepilot`
  was built *after* the chat call, so the three early returns in the Deep
  Research branch wrote none, and `mode_rows` read the empty block as
  *the lawyer got no reply* — manufacturing B13 evidence out of an instrument
  gap (6347 turn 2). Found because the Deep Research count read 1 where the
  set says 2. (b) The published marker matched its phrases **in prose**:
  `Statutory Framework` fired on a planner asking *"would you like to search
  for the statutory framework discussed in this case"*.
- **Anchoring that regex took three attempts, and the first two passed for
  the wrong reason.** The Worker emits at least five heading forms
  (`### 1. Summary Answer (BLUF)` 253, `2. **Detailed Analysis:**` 76,
  `**References:**` 35, `### Jurisdiction & Status` 18,
  `### **1. Summary Answer (BLUF)**`). Two drafts enumerated them in a fixed
  order, each missed one, and each still reproduced every published count —
  because `\bBLUF\b` is unanchored and was quietly carrying them. The final
  form requires the line to open with markup and then consumes a run of it,
  and it reproduces the counts **without** BLUF. **A regex that agrees with
  its predecessor on the corpus has not been validated; check the mechanism
  it is supposed to be matching.**
- **State the 0 precisely: the report headings are in 0 of the 152
  non-Deep-Research pre-pilot answers and 27 of 27 Deep Research ones.**
  `DEEP_RESEARCH_SYNTHESIS_PROMPT` asks for a report structure too, so
  `dr_marker`'s precedence is load-bearing. The published "0 of 38 / 0 of 64"
  was over non-DR answers all along, but nothing said so.
- **`research_mode` is the same defect and does NOT yield to the same trick
  (P0.6).** `Filter: Research mode` is blank for exactly the twelve. The
  obvious signal — "the answer cites a neutral citation, so case law was in
  the tool set" — is **wrong**: a deflection quotes the case name the lawyer
  asked about, and all three of 6346's answers match it while refusing to
  search. The real distinction is substantive content *from* the judgment,
  which is a human read. Nearly written up as a derivation before being
  checked.
- **The transcripts hold P4.1 bug (a)'s contrast case, which no replay can
  produce.** In 6347 and 6350 the lawyer changed the research filter
  mid-session and it **worked** (6347 answers 2–4 discuss the holding in
  *Graham Andrew Evans v R* [2025] EWCA Crim 1150); in 6346 the lawyer
  changed it, said so, and was told three times it had not. Also: the
  pre-pilot's own wording was *"switch to **Research mode** using the mode
  selector"* (6343 answer 3) — the chat-mode control — where HEAD says
  *"'Legislation & Case Law' mode"*. Both wrong, differently; fix against
  what HEAD emits.
- **The most expensive turn on this branch, and it is not a loop.**
  `wave0_conv_6348/6348_rep2` turn 1: **$2.40 and 1,133 seconds**, against
  $0.07 and 33s for rep 1 of the same turn. 2 delegations, 5 tool calls, no
  halt — but **3 `empty_completions`**, two retried and one not. Booked on
  P4.5, which does not currently say its failure mode is also a cost and
  latency defect. It is also the one rep of three that delivered P3.11's
  subsection; at n=1 that is coincidence and should not be read as signal.

**How this session worked, for whoever repeats it.**
- **A/B against an old commit with the NEW instrument.** Session 14's
  worktree recipe, plus one step it does not mention: the worktree's
  `tools/replay_set.py` is the OLD one, so a replay from it would have sent
  6348 in Research mode again — the very bug. `replay.py`, `replay_set.py`
  and `replay_report.py` were copied from HEAD into the worktree, leaving
  `src/` at `2d9ae11`. The product is the before-column; the measuring
  instrument must not be. `git_head` still reads `2d9ae11` from the
  worktree's own checkout, which is the right label.
- **Do not run `replay pin` from the worktree.** The DB is shared and already
  pinned; a second `pin` would stash the pinned state as the "previous" one.
  Run `check` to confirm, then `run`.
- **Grade with one script over one directory:** `bash grade.sh <dir>` runs
  `modes halts negatives derivations blanks scoperecord nosearch caselaw` and
  prints each exit code.
- **`depth --seams` is the first thing to run on a composition row**, and it
  earned that again here: it is what showed rep 3's loss was at the Manager,
  which no answer-level grade could have told apart from rep 1's.

**State of the branch:** `fix/prepilot-defects`, no upstream, **NOTHING
PUSHED**. Whole-plan-then-one-push stands. **1442 tests green.** Ledger:
**27 of 46 rows, 6 of 14 buckets closed, 3 partial.**

**Machine state a new session inherits:**
- **No uvicorn running.** Dev box **restored**: `google/gemini-3.1-pro-preview`
  and local prompt cache ON. **Note for the handover: the stashed model was
  `google/gemini-3.1-pro-preview`, not the `moonshotai/kimi-k3` Session 19
  recorded** — so either that restore did not take or something changed it
  since. The user chose to restore as stashed.
- **Three new replay directories, 31 in all:** `wave0_conv` (head `223293e`,
  the twelve, n=1, Conversational — the missing before-column);
  `wave0_conv_6348` (head `8bbcfb9`, 6348 ×3, Conversational, HEAD);
  `wave0_conv_6348_pre` (head `2d9ae11`, 6348 ×3, Conversational, pre-P3.1).
- **New command:** `replay_report modes`. Run it on any new sweep before
  quoting a number from it.

**Spend:** $8.42 this session ($3.84 `wave0_conv`, $3.09 `wave0_conv_6348`,
$1.49 `wave0_conv_6348_pre`), plus about $0.004 of model probes.

**Next action:** **P4.1** — B7 now reproduces and `wave0_conv` is its
before-column; read P0.6 first, because bug (a)'s contrast case is in the
transcripts and not in any replay. Then **P3.11's decision**, whose option (a)
needs re-scoping onto **P3.13**'s seam, and **P4.6's re-baseline**.

**Open with the user:** P3.11's decision (now unblocked, options changed);
P5.2 (B12); whether Thomas's review document should be committed; and whether
the Fix Tracker should be updated (P0.5 → Done, P3.11 → still In progress,
plus P0.6 and P3.13 as new rows).

---

## Session 20, continued — 2026-09-22 — P3.11's decision, and P3.13 measured

**Done:**
- **The user settled P3.11: option (d), and the acceptance bar moves to
  CONVERSATIONAL mode** — the mode 6348's lawyer used — so the row is graded
  against `wave0_conv_6348`'s 1 of 3, not the Research-mode 2 of 3.
- **Option (d) built: the quick-lookup Worker now carries P3.1's sibling
  rule.** P3.1 put it in the research Workers only;
  `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` never had it, which is the one step
  between 2 of 3 (Research) and 1 of 3 (Conversational). Same wording, plus a
  clause reconciling it with that prompt's own "2-5 sentences" cap. No code
  change — P3.11's outline already reached this Worker (14 of 14 section
  searches); it had no instruction to use it.
- **Seam A/B, $0.15:** both recorded-SHALLOW payloads DELIVERED with the rule.
- **Acceptance (`wave3_p311_conv`, head `8dbae59`, n=3, $1.63): 1 of 3,
  unchanged — but the Worker seam closed.** The Worker report carries s.36(2)
  in **3 of 3** (2 of 3 before) and the Manager drops it in **2 of those 3**.
- **New instrument, and it is P3.13's metric:** `depth --seams` now ends with
  a tally of WHERE each requirement was lost — attributed to the last seam
  that still had it at depth, split by the mode the turn RAN in — and `depth
  --also` pools directories for the rate. 5 tests. **Tests 1443 → 1448.**
- **P3.13 measured the day it was opened, free, over run files already held.**
  Pooled over 103 graded (requirement, turn) observations in 10 directories:
  56 carried; of the 47 losses, **summariser 24, manager 12, worker 11**.

**Surprises / deviations from FIX_PLAN:**

- **I asserted a conclusion from a turn-level slice and the measurement
  refuted it.** After seeing 3 of 5 deep Worker reports flattened on 6348
  turn 1, I told the user "P3.13 is no longer a speculative row; it is the
  whole of what remains of B10". The pooled tally says otherwise: **the
  summariser is the largest seam (24 of 47 losses)**, exactly as P3.11
  originally diagnosed, and in **Research mode the Manager never drops it at
  all (0 of 11)**. Even within 6348's own conversational set the split is
  summariser 10, manager 3, worker 1 — so 3-of-5 does not generalise across
  the session it came from, let alone the corpus. The free measurement was
  available before the claim; I made the claim first.
- **The Deep Research half is the bigger share of the Manager losses and is
  not this row's.** All 48 `deep_research` observations are **one session,
  6365**, so "9 of 15" is a single-session figure, not a rate; and that seam
  is the DR synthesis, not the conversational Manager — P4.7/P3.10's
  territory. P3.13 should be re-scoped to the conversational Manager alone
  (3 of 21 losses), which is much smaller than P3.11's residual made it look.
- **A test caught a prompt regression I would otherwise have shipped.** The
  first draft of the rule added a fifth OUTPUT bullet;
  `test_the_chat_worker_gets_the_rule_as_a_clause_not_a_block` failed, because
  P2.4 had measured that more structure in this prompt moves the Worker to
  bullets (0 of 9 → 5 of 9) and drops case-law links reaching the answer (7 of
  15 → 2 of 13). Folded into the existing citation bullet instead — and the
  clause form is also shorter (1,111 vs 1,349 chars on rep 1).
- **Invariant 1 still took a hit.** Against `wave0_conv_6348`: prose fell in 3
  of 4 turn slots and **links in 3 of 4** (turn 1 3.0 → 2.0). Session 19 saw
  the same from the outline itself. The sibling instruction costs links; the
  clause form reduced but did not remove it.
- **Process error: I committed on a red suite.** I chained
  `pytest -q | tail && git commit`, and `tail`'s exit code masked pytest's, so
  the commit landed with `test_the_chat_worker_gets_the_rule...` failing. Found
  immediately, fixed, amended. **Check `${PIPESTATUS[0]}`, or do not pipe the
  test run.**
- **A second empty-completion cost outlier, same shape as this morning's.**
  `wave3_p311_conv/6348_rep3` turn 2: **$0.90 and 713 seconds**, 3
  `empty_completions`, retry exhausted. Two in one session; both are on P4.5,
  which still frames its failure mode as correctness only.

**Every published number was re-derived from scratch before the handover.**
A throwaway script re-computed all 35 figures this session put into
`FIX_PLAN.md`, `BASELINE.md` and the log — one method, over every relevant
directory and over the export — and all 35 reproduced. One did NOT before that
check: P4.1's bug counts were eyeballed at 4 -> 13 and 4 -> 14 and are 5 -> 14
and 5 -> 15. The three regexes are now on the row so the next session needs no
script. **Do this before a handover, not after a claim.**

**Two findings made at the handover itself, both verified at `5b3fd1a`:**
- **P4.1's bug (b) is four prompt sites, not one, and its line reference is
  stale.** `prompts.py:649-650` now holds `_filter_constraint_block_for_mode`;
  the real sites are `:27`, `:390`, `:439` and `:779`, and **two of them name a
  different control from the other two while both are live in Conversational
  mode**. That is why the pre-pilot said "switch to Research mode" and
  `wave0_conv` says "'Legislation & Case Law' mode". Recorded on the row.
- **The conversational Worker never receives the ACTIVE RESEARCH FILTERS
  block** — `get_worker_system_prompt`'s conversational branch returns early,
  before the append. Awareness gap, not enforcement (the filters are applied in
  `executor.py` regardless), and it bit no measurement here because the twelve
  sessions carry no filter. New row **P3.14**.

**Spend:** $1.78 more ($1.63 acceptance, $0.15 seam) — **$10.20 for the
session.**

**Machine state:** no uvicorn running; dev box restored
(`google/gemini-3.1-pro-preview`, local prompt cache ON). **32 replay
directories** (+`wave3_p311_conv`). Branch `fix/prepilot-defects`, **nothing
pushed**, 1448 tests green, ledger 27 of 46.

**Disposition (user decision, at the end of the session): P3.11 is BOOKED
DONE, and B10 stays open behind P3.13.** P3.1's precedent: the seam the row
targeted is closed (the Worker states the sibling in 3 of 3), the residual is
the Manager seam, and the 1-of-3 at the answer is carried as a named
dependency rather than booked as a pass. The rule is kept — it costs nothing
at runtime and closes the asymmetry P3.1 left behind — and its measured price,
links down in 3 of 4 turn slots, is on P3.13's watch list. Ledger **27 → 28 of
46**; B10 re-points from P3.11 to P3.13 and reads `partial ... waiting on
P3.13`.

**Next action:** **P4.1**, the strongest open row on the page — B7 reproduced
for the first time, `wave0_conv` is its before-column, and two of its three
bugs are visible verbatim. Read **P0.6** first: bug (a) turns on the
research-mode filter, still a harness default on exactly these sessions, and
the contrast case it needs is in the transcripts rather than in any replay.

---

## Session 21 — 2026-09-22 — P4.1 (B7, the research-mode dead-end), and the mode 6346 actually ran in

**Done:**
- **P4.1 is DONE, all three bugs and Thomas's action 9, $6.77.** B7 closes;
  ledger 28 → 29 of 48 (one new row, P4.9), 7 of 14 buckets closed.
- **Step 1, the harness (the row's prerequisite B):** `research_mode` is now
  per TURN (`replay_set.Turn.research_mode` / `research_mode_source`,
  `replay.TurnResult` likewise, sent per request), the replayed history is
  stamped with the modes each reply ran under — exactly as the client now
  stamps a saved message — and `replay run --script` builds a sequence from an
  exported session's turns **by index**, so no question text is committed
  (`docs/prepilot-fixes/evidence/scripts/`, three scripts, pinned by a test).
  `replay_report deadend` grades the row's three regexes verbatim plus every
  turn from a research-type change onward, and `--before` puts an older
  directory beside it. `research_mode_enabled` joins the pinned flags, OFF,
  as it was on the target (P0.5); until this row no prompt read it.
- **Bug (a), the marker (`utils/mode_change.py`).** Every saved assistant
  message now carries `research_mode` / `chat_mode` (additive `messages`
  columns, echoed on the `result` event, saved by `useChat.js`, returned by
  every `MessageOut`), and `process_user_request` and the Deep Research
  planner prefix a `[SYSTEM NOTICE …]` onto the user's turn when this
  request's modes differ from the previous reply's. In-band on the user turn,
  not a mid-history system message, so it survives every provider's role
  rules. An unstamped history yields no marker — today's behaviour. Recorded
  as `mode_change` on the audit event (**schema v5**) and on the planner's
  JSON (the plan endpoint emits no audit event).
- **Bug (b), one control name.** `CASE_LAW_OUT_OF_SCOPE_RULE` names the
  research type as the UI does — the Filters button, Research filters >
  Research type, 'Legislation only' / 'Legislation & case law' — and is
  carried by the mode note in BOTH chat modes (the research-mode Manager used
  to get "direct the user to switch mode" and no note at all). The
  conversational Manager's pointer to Research mode is **substituted out**
  when the mode is not offered (`_research_mode_enabled`, the chips pattern);
  the quick-lookup Worker no longer sends anyone to a mode (still four OUTPUT
  bullets, P2.4); the planner's legislation-only note says the same. Control
  names live in `utils/mode_change.py`, taken from `Sidebar.jsx`, `App.jsx`
  and `ResearchFiltersModal.jsx`; `test_mode_change.py` forbids every manager,
  worker and planner prompt naming anything else.
- **Bug (c):** the rule forbids describing the interface; tests forbid the
  phrases the lawyers saw. **Action 9:** `extract_suggestions` drops any chip
  that offers to change a mode or filter (`is_mode_switch_offer`); every
  chips block says so.
- **Acceptance — the scripted sequence, n=3, in both modes, before and
  after.** `python -m tools.replay_report --dir <D> deadend --all-reps
  [--before <D>]`:

  | directory | product | sequence | turns from the change onward | clean | markers | wrong control | switch/restart |
  |---|---|---|---|---|---|---|---|
  | `wave4_p41_pre` | `0a5d813` (pre-fix) | 6346 ×3 + 6343 ×3, Conversational | 9 | **8** | 0 (cannot see it) | 6 of 6 turn-1 deflections | 7 |
  | `wave4_p41_pre` | `0a5d813` | 6346 ×3, Deep Research | 3 | 3 | 0 | 0 | 0 |
  | `wave4_p41` | `9aa6d63` / `73ce944` | 6346 ×3 + 6343 ×3, Conversational | 9 | **9** | 6 of 6 | **0** | **0** |
  | `wave4_p41` | `73ce944` | 6346 ×3, Deep Research | 3 | 3 | 3 of 3 | 0 | 0 |

  `deadend` exits **0** on `wave4_p41` and every other exit-1 subcommand
  (`modes halts negatives derivations blanks scoperecord nosearch caselaw`)
  exits 0 on it too. **Invariant 1 held:** over the nine post-change
  conversational turns, links 7 → 8 and `sources_kept` 12 → 17, before →
  after (re-derived by one script over both directories).
- **The row's wording metric, on its own before-column.** The four evidence
  sessions in Conversational mode, rep 1, 18 answered turns each side
  (`deadend --dir wave4_p41_conv --session 6343 6346 6347 6350 --before
  wave0_conv`): switch/restart **14 → 0**, wrong control **15 → 0**, invented
  UI **2 → 0**; `wave4_p41_conv` head `9aa6d63`, n=1, $0.57, every exit-1
  subcommand 0. The Session 16 instrument note is corrected on the row:
  `negatives` exits 0 on `wave0_conv`, `wave4_p41_conv` and `wave4_p41`.
- **P0.5 residual found and built: five blank-model answers are the Deep
  Research planner's clarifications, and three of them are 6346's.** The
  client saves a clarification with no model; every other assistant message
  carries the backend's. `answer_shape` read all five as conversational (no
  report headings), so `wave0_conv` replayed 6346 in Conversational mode when
  its lawyer was in Deep Research throughout — her turn 4 says so. New source
  `planner_marker` (`replay_set._resolve_modes`), which also serves as a
  neighbour for the unanswered turns beside it (nothing completed, so the
  client did not revert). Sources over the 62 sessions: snapshot 108,
  conversational_marker **47** (was 52), dr_marker 27, planner_marker 5,
  neighbour 9; no default; 0 snapshot disagreements. `reconciliation_report`
  now counts only `dr_marker`, because the exporter's `Session mode` reads
  `messages.research_plan`, which a clarification never writes.
- **Tests 1448 → 1524**, all green (`pytest -q` redirected to a file, exit
  code checked, not piped).

**Surprises / deviations from FIX_PLAN:**

- **Bug (a) as the row diagnosed it does NOT reproduce, and the row's
  "code-checked, not a hypothesis" was an inference.** With the research type
  really changed between turns, the PRE-FIX product answered from case law in
  **11 of 12** post-change turns across both modes (8 of 9 Conversational, 3
  of 3 Deep Research), with no marker and the refusal still in the history.
  The twelfth is a P4.5 episode: 456 s, 3 empty completions, the P4.2
  fallback served — and its "please switch to Research mode for a fuller
  search" is the quick-lookup Worker's own OUTPUT bullet (bug (b)'s fourth
  site), not anchoring. So the marker is verified to **fire** (9 of 9 changes
  seen, 3 of 3 on the planner) and is defence in depth; it is not what closed
  those turns. **What 6346's transcript most likely records is bug (b) alone:**
  the planner told her she was in "research mode 'Legislation Only'", she
  said she would "change the research mode", was told to "confirm once you
  have changed the research mode", and her turn 4 reads "It is in deep
  research mode" — the CHAT-mode control, which she had already been using,
  and which does not add case law. Invariant 6: her words say which control
  she changed. The row's acceptance stands as written and passes; the
  diagnosis on the row is corrected.
- **6346 was never a Conversational session.** All three of its answers are
  planner clarifications (blank model), so `wave0_conv`'s 5-of-5 deflection
  count for this row was measured in the wrong mode. The corrected replay set
  sends 6346 as Deep Research; the Deep Research script is the row's
  acceptance in the mode she used, and its turn 1 — the planner declining
  under 'Legislation only' — now names the Filters button in 3 of 3.
- **The first Deep Research after-run could not show its own marker.**
  `/api/research/plan` emits no audit event and `run_deep_research` never
  reads the history, so `mode_change` was absent from every DR turn and
  `deadend` reported "no marker" on a product that had injected one. Fixed on
  the instrument's side of the seam: the planner returns `mode_change` on its
  JSON, the execution records the change it saw on the audit, the harness
  reads the planner's; re-run at `73ce944` ($1.40; the first run is kept as
  `wave4_p41_dr_v1`, identical product code, $0.98). **Session 20's lesson a
  third time: the instrument was wrong before the product was.**
- **Two more P4.5 episodes**, both on this row's sessions: `wave4_p41_pre`
  6346 rep 2 turn 2 (3 empty completions, 456 s, $0.15, fallback served) and
  `wave4_p41` 6346_dr rep 2 turn 2 (1, retried, 233 s, $0.37). Booked on P4.5.
- **Old-mode references in the after-column are the correct deflection.**
  `deadend`'s `old_mode` regex fires on 'Legislation only' by design, so it
  counts 9 in `wave4_p41` and 14 in `wave4_p41_conv` — every one on an
  unchanged turn stating the current type. It is a finding only on a turn
  from a change onward, where it is 0.

**How this session worked, for whoever repeats it.**
- Two servers, two ports: HEAD on 8000, the `0a5d813` worktree on 8001 with
  `.env` and the three `tools/` files copied from HEAD (`--base-url` selects).
  Sweeps still ran **serially**. Do not `pin` from the worktree.
- `replay run --script <json>` for a sequence the pre-pilot never ran; the
  script names the base session and turn indexes only.
- After changing product code that the trace reports on, **restart the
  server before the acceptance run** — the DR re-run exists because I did not.

**State of the branch:** `fix/prepilot-defects`, **NOTHING PUSHED**, 1524
tests green, ledger 29 of 48, 7 of 14 buckets closed (B7 joins), 3 partial.

**Machine state a new session inherits:** no uvicorn running; dev box
**restored** (`replay restore`: model `google/gemini-3.1-pro-preview`, local
prompt cache ON, `research_mode_enabled` ON); worktree removed. **36 replay
directories** (+`wave4_p41`, `wave4_p41_pre`, `wave4_p41_conv`,
`wave4_p41_dr_v1`).

**Spend:** $6.77 ($2.54 `wave4_p41`, $2.68 `wave4_p41_pre`, $0.57
`wave4_p41_conv`, $0.98 `wave4_p41_dr_v1`) plus one model probe.

**Next action:** **P3.13** (the conversational Manager seam, measured, 3 of
21) or **P0.6** (now a small row: the per-turn field exists, it needs
`unknown` and the human read). Then **P4.6**'s re-baseline.

**Open with the user:** P5.2 (B12, external); whether Thomas's review
document should be committed; whether the Fix Tracker should be updated
(P4.1 → Done, B7 closed, P4.9 new); and whether the diagnosis correction
above changes anything for the pilot's user guidance — the control lawyers
need is the Filters button, and no answer had ever named it.

---

## Session 21, continued — 2026-09-22/23 — the first cut to `main`, and the tracker

**Done (user decisions):**
- **The branch was cut to `main`** (user decision, 2026-09-22), superseding the 2026-09-15 rule that nothing goes to `main` until the plan concludes. Later cuts go only when the user asks. This is recorded in CLAUDE.md, in FIX_PLAN's deployment note above the Ledger, and in memory.
- **Rollback tag `pre-prepilot-fixes-2026-09-22`** (annotated, pushed) is on `6ada6d1`, the commit the target was running. That was `origin/main`, not local `main`, which was one docs commit ahead. Roll back on the target with `git checkout pre-prepilot-fixes-2026-09-22` and a restart. The new `messages` columns are additive, so the old code ignores them.
- **Merge `d8fd73b`** (`--no-ff`) was pushed as `6ada6d1..d8fd73b`. `origin/main` was a strict ancestor, so there were no conflicts.
- **`fix/prepilot-defects` pushed for the first time**, tracking `origin`, at `b91b7ec`. It stays the working branch.
- Checked before merging: no new env vars, no new Python packages and no new whitelist hosts. `client/dist` is the current build. The two `messages` columns are created at startup.
- **CLAUDE.md's mode-controls note is corrected.** It still said the model anchored on its refusal, the diagnosis this session disproved.
- **Fix Tracker updated at the user's request:** P4.1 → Fixed, P4.9 added, the Fixed status reworded to say what was merged, and the notes rewritten for Session 21.

**NOT done — needs the target, and is not recorded as done anywhere:**
- The target has not been confirmed to have pulled `d8fd73b`. Deploy with `git pull`, `stop_native.cmd`, `start_native.cmd`, then `server_py	est_apis.ps1` and one real question.
- **A `pg_dump` before pulling was recommended and not taken.** `install_backup_task.ps1` has never run, so no backup exists on the target.
- **Tell whoever runs the lexchat-eval harness that the audit event is now schema v5.** The change is additive (top-level `mode_change`).

**Consequence for measurement:** a replay directory taken before 2026-09-22 measured a system the target had never run. After the target pulls, replays of HEAD measure the deployed system plus whatever the branch has gained since `2eaeff0`.

---

## Session 22 — 2026-09-23 — P3.13 (B10, the conversational Manager seam)

**Done:**
- **P3.13 BUILT, acceptance NOT MET: 6348 turn 1 DELIVERED in 1 of 3**
  (`wave3_p313`, head `778d30a`, n=3, $5.65), unchanged from
  `wave3_p311_conv`. Not ticked. The next step is the user's decision; there
  are three options on the row. B10 stays partial. Ledger unchanged at 29 of
  48 rows, 7 of 14 buckets.
- **The acceptance was stated on the row before the replay** (3 of 3; links
  not lower in more than 1 of 4 slots; `sources_kept` inside the noise floor;
  exit-1 set 0). It was committed with the product change in `778d30a`.
- **Measured before building, free, and it named the mechanism.** New
  `replay_report siblings`: over 1,060 non-Deep-Research delegations in 36
  directories, where the answer keeps one subsection of a section, the
  conversational Manager keeps a sibling written as a link 58 of 60 times and
  one written as plain text 70 of 104. The research Manager keeps 441 of 441
  either way. In every flattened 6348 answer, s.36(2) was the report's one
  unlinked provision.
- **Built (`778d30a`):** `citation_links.link_sibling_pinpoints` via
  `agent_core.worker_result_for_manager`, for the conversational Manager
  only, plus one clause in its existing CITATION PRESERVATION bullet.
  **Instrument:** `seam_replay manager`. **Tests 1524 → 1559.** Each half was
  proven to fail its own tests on scratch copies: wiring removed, linker
  stubbed, clause removed.
- **Dev box restored** (`replay restore`: model `google/gemini-3.1-pro-preview`,
  local prompt cache ON, `research_mode_enabled` ON). Server stopped.

**Surprises / deviations from FIX_PLAN:**

- **The tool-free Manager seam predicted a pass the product did not deliver,
  and I built on it.** Tool-free, link plus clause recovered 3 of 3 recorded
  Manager losses. Rep 1 of the acceptance then flattened s.36(2) with the fix
  live (the linker fired on two siblings). Its payload DELIVERED in 3 of 3
  tool-free draws and failed in 3 of 3 once the Manager was offered its
  tools, as the live call is. Re-drawn with tools, the fix is 1 of 3 on the
  losses, not 3 of 3. The seam now offers the tools by default. **This is the
  second time a seam has passed what live failed** (P3.11's rep 3 was the
  first, at the Worker seam). Neither form of the Manager seam is exact: each
  matched the live outcome on 5 of 6 recorded payloads. Take the harsher one.
- **Linking alone was not enough, because the Manager also edits the sibling
  out as off-topic.** The question is about legal advice privilege, which is
  s.36(1). On the tool-free seam the link recovered 1 of 3 and the clause 2 of
  3. Both halves are kept because together they did better, and neither costs
  links.
- **The first draft of the linker made a wrong-instrument link, and reading
  every edit is what found it.** A research-mode report listing Use Classes
  Orders would have handed the 1963 Order's s.2(2) the 1950 Order's s.2 URL:
  a real page for the wrong instrument, which is Invariant 1's worst case. All
  188 distinct edits over the corpus were read before any wiring. The
  instrument rule and a test came from that reading.
- **Rep 2 was lost to P4.5, not to this row, and it broke the conversational
  format.** The first worker lost its final completion three times, each
  attempt about 62,912 completion tokens with no content ($2.48, 1,171 s).
  The Manager was handed a bodiless report, only the scope block, whose
  text addresses the research Worker's "Jurisdiction & Status section". It
  wrote that heading, and turns 3 and 4 repeated it: `modes` exits 1, the
  first such answers in 128 conversational turns. The same payload on the
  seam wrote no heading in 4 of 4 draws, with or without the fix. Rep 3
  turn 3 was a second episode ($2.40, 1,120 s). Booked on P4.5.
- **`--max-spend` is checked between reps, not within one.** The run was
  capped at $4 and recorded $5.65.

**How this session worked, for whoever repeats it.**
- `python -m tools.seam_replay manager --run <run.json> --turn N`
  (`--without-fix --rev <sha>` for the before-column; `--no-tools` for the
  tool-free draw).
- `python -m tools.replay_report --dir <D> siblings --all-dirs [--exclude NAME] [--list]`.
- Before wiring a code change that rewrites what a model is handed, dry-run
  it over every stored report and read the edits.

**Every published number was re-derived before the handover** by one command
or one scratch script over the saved draws. The scratch script regrades every
seam draw with `replay_report.depth_verdict`. `siblings` reproduces 58/60 and
70/104. `depth --seams`, `depth --before` and `discovery --before` give the
acceptance and Invariant 1 figures, and `plan_status` counts 48 rows.

**State of the branch:** `fix/prepilot-defects`. `778d30a` (product) and the
handover commit are pushed to the branch, and nothing went to `main`. 1559
tests green.

**Machine state:** no uvicorn running, the dev box is restored and there are
no worktrees. **37 replay directories** (+`wave3_p313`).

**Spend:** $5.65 for `wave3_p313`, $4.89 of it two P4.5 turns. About $1 for
64 seam draws; not every draw's cost was captured, and the printed ones range
$0.007–$0.030.

**Next action:** the user's decision on P3.13. (i), a code-written sibling
at the answer seam, is recommended, and its design questions are placement
and clutter. Otherwise take **P0.6**, then **P4.6**. Consider raising
**P4.5**.

**Open with the user:** P3.13's decision; whether the target has pulled
`d8fd73b` and restarted; whether a `pg_dump` was taken there first (no backup
has ever run on the target); telling whoever runs the eval harness that the
audit event is schema v5; P5.2 (B12, external); whether Thomas's review
document should be committed; whether the Fix Tracker should be updated.

---

## Session 22, continued — 2026-09-23 — P3.13 option (i): the answer seam; P3.13 DONE, B10 closed

**Done:**
- **The user chose option (i):** keep the linking, keep the row open, and put
  a dropped sibling back in code after the answer is written. The design
  choices were stated and taken by this session: verbatim Worker clause, after
  the citing paragraph, "Also in s.N:", at most 3 notes, conversational
  Manager only.
- **Built:** `citation_links.restore_dropped_siblings` (`66598f3`). Then the
  prompt clause was taken out and plain-text citations accepted (`ebd3efa`).
  `seam_replay manager` applies the restore. **Tests 1559 → 1577.** The
  restore stubbed fails 5 tests; unwired, it fails 1 (the integration test).
- **ACCEPTED:** `wave3_p313c` (head `ebd3efa`, n=3, $1.01). 6348 turn 1
  DELIVERED in 3 of 3, delivered by turn 2 in 3 of 3, Manager losses 0, every
  exit-1 subcommand 0. Links fell in 1 of 4 slots; `sources_kept` fell in 0.
  **P3.13 ticked; B10 CLOSED; ledger 30 of 48, 8 of 14 buckets.**

**Surprises / deviations:**
- **The first dry-run's notes were not fit to show a lawyer, and only
  reading them showed it.** 29 notes, three kinds of fault: a list cut
  mid-parenthesis (6374), restatements of the kept subsection, and
  near-duplicates of an answer sentence (6409). Each became a guard. After
  that there were 15 notes, all read.
- **The prompt clause cost retrieval, which no metric on this row watched.**
  `wave3_p313b` rep 1 went to the Economic Crime and Corporate Transparency
  Act 2023 and never searched FOISA. Its first brief was the lawyer's words
  nearly verbatim. That brief form appeared in 3 of 6 runs with the clause
  and 0 of 10 before. The first brief is written before any tool result, so
  the clause was the only change of ours that could reach it. A first-round
  probe agreed: 2 of 4 briefs did not name FOI with the clause, 0 of 4
  without. The clause is out, and `prompts.py` is identical to `57cfae6`.
  **A prompt change can move a call the fix never meant to touch; probe
  every call the edited prompt drives, not only the one it targets.**
- **With the clause gone, the Manager dropped s.36(2) in all 3 acceptance
  answers, and the code restored all 3.** The number is the code's. Invariant
  2 says that is the right outcome, and the row now says it plainly.
- **Correction:** `ebd3efa`'s commit message says the verbatim brief
  appeared "0 of 11 before". It is 0 of 10 (re-derived by an exact prefix
  match; the test docstring is corrected).

**Every published number was re-derived by a command or script before the
handover:** `depth --seams` / `--before`, `discovery --before`, the grade
loop, the dry-run (623 turns with the restore's own sweeps excluded, 647 with
them), the brief counts, the FOISA-less count (1 of 33) and `plan_status` (48
rows).

**Machine state:** no uvicorn running; dev box restored; **39 replay
directories** (+`wave3_p313b`, `wave3_p313c`). Branch pushed; nothing to
`main`.

**Spend (continued):** $2.18 in sweeps ($1.17 + $1.01), plus about 25 seam
and probe draws. **Session 22 total:** about $8.8 in sweeps, plus about $1.5
of seam draws.

**Next action:** **P0.6**, then **P4.6**'s re-baseline. Raise **P4.5**.

**Open with the user:**
- whether the Fix Tracker should be updated (P3.13 → Fixed, B10 closed);
- whether this branch should be cut to `main`;
- the target's pull and backup, the eval-harness schema v5, P5.2, and
  Thomas's document (all unchanged).

---

## Session 22, continued further — 2026-09-23 — the second cut to `main`, and the tracker

**Done (user decisions, both asked for):**
- **The Fix Tracker was updated and republished to the same URL.** P3.13 is
  now Fixed (25 Fixed rows), the release wording covers both cuts, and the
  notes lead with P3.13 in plain terms, including the prompt instruction that
  was tried and taken back out.
- **The second cut went to `main`.** This commit records it and is the branch
  head being merged (`--no-ff`). The pre-merge `main`, `d8fd73b` (the first
  cut's merge commit), is tagged `pre-prepilot-fixes-2026-09-23` and pushed.
- **Checked before merging:** the only product files that change against
  `origin/main` are `server_py/src/agent/agent_core.py` and
  `server_py/src/utils/citation_links.py`. `prompts.py` nets to no change.
  There is no config, `.env`, dependency, `client/` (so `client/dist` is
  current), schema or new-host change. `origin/main` held nothing the branch
  lacks except the first cut's own merge commit, so the merge is clean.

**NOT done — needs the target:**
- pull, then `stop_native.cmd` / `start_native.cmd`, then `server_py\test_apis.ps1`
  and one real question;
- a `pg_dump` first (still no backup has ever run there);
- confirmation that the first cut (`d8fd73b`) was ever pulled.

**Rollback on the target:** `git checkout pre-prepilot-fixes-2026-09-23` and
a restart returns it to the first cut; `pre-prepilot-fixes-2026-09-22`
returns it to before both.

---

## Session 22 — handover for Session 23 (2026-09-23)

Written at the user's request before a new session starts, so nothing learned
here depends on this session's context. Everything below is also on the rows
it concerns.

**State.**
- Branch `fix/prepilot-defects`, pushed. `main` is at `c77e779`, the second
  cut (user decision). Rollback tags: `pre-prepilot-fixes-2026-09-23` (first
  cut only) and `pre-prepilot-fixes-2026-09-22` (before both).
- **1578 tests green.**
- Ledger **30 of 48 rows, 8 of 14 buckets closed.** Partial: B5 (waiting on
  P3.7, P4.6, P4.7) and B12 (waiting on P5.2).
- Run `python -m tools.plan_status` rather than trusting these figures.

**Next work:** **P0.6** (read its row IN FULL: the research-mode field is
blank for the same twelve sessions and is NOT derivable from the answers; the
fix is to record `unknown` plus a human read), then **P4.6**'s re-baseline.
Consider raising **P4.5**:
- two episodes cost $4.89 of `wave3_p313`'s $5.65;
- each empty completion is about 62,912 reasoning tokens;
- a bodiless worker report made the Manager write a research-report heading
  into a conversational answer.

**Machine state:**
- no uvicorn running; no pin file; no worktrees;
- dev box on its normal settings: model `google/gemini-3.1-pro-preview`,
  summarisation `google/gemini-3-flash-preview`, local prompt cache ON,
  `research_mode_enabled` ON;
- **39 replay directories** (gitignored), this session's being `wave3_p313`
  (link + clause, 1 of 3), `wave3_p313b` (+ restore, 2 of 3) and
  `wave3_p313c` (the acceptance, 3 of 3).
- Transcript export (never in the repo):
  `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`.
- Fix Tracker: <https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ> (source
  `docs/prepilot-fixes/summary-table.html`; update only when asked).

**Instruments added this session:**
- `python -m tools.seam_replay manager --run <run.json> --turn N [--without-fix --rev <sha>] [--no-tools]`:
  the Manager's composition from a run file. It offers the Manager its tools
  by default, because the tool-free form passed a payload the live Manager
  failed.
- `python -m tools.replay_report --dir <D> siblings [--also DIR… | --all-dirs] [--exclude NAME…] [--list] [--dry-run [--show]]`:
  how often the Manager keeps a sibling written as a link against plain text,
  plus a dry-run of P3.13's code over every stored run.

**Hazards met this session (add to the ones already in the brief):**
- **Python inside a bash heredoc still mangles backslashes**, three more times
  here. Every such failure asserted before writing, so nothing was corrupted.
  For any edit containing `\s`, `\(` or `\n`, use the Edit tool, or write
  the script to a file with the Write tool and run it.
- **`git merge -F -` is not supported**: the message must be in a file.
- **Scratch-copy revert checks:** `test_the_prompt_reader_finds_a_real_constant`
  and `test_the_manager_body_reader_finds_the_constant` fail in any copy that
  is not a git checkout (they call `git show`). That is an artefact, not a
  signal.
- **Seam draws at temperature 0 are not byte-deterministic** on the pinned
  model (1,466 vs 1,488 chars for one payload), so count payloads, and
  expect a close outcome to flip between draws.

**Open with the user (unchanged unless they say otherwise):**
- On the target: the first cut (`d8fd73b`) has never been confirmed pulled,
  and no `pg_dump` has ever been taken there. Deploy both cuts with a
  `pg_dump`, `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1`, and one real question.
- Tell whoever runs the eval harness that the audit event is schema v5. This
  session did not change the schema.
- P5.2 (B12, external).
- Whether Thomas's review document should be committed.

---

## Session 23 — 2026-09-23 — P0.6 (the research-type default)

**Done:**
- **P0.6 is DONE, deterministic, $0, no replay.** Ledger 30 → **31 of 49
  rows** (one new row, P0.7); buckets unchanged at 8 of 14, because P0.6 is
  measurement.
- **The human read.** I read all 50 turns of the twelve from the export in
  the scratchpad (the export never entered the repo). The read is committed as
  `docs/prepilot-fixes/evidence/research_mode_reads.json`: one entry per
  turn, with value, `source: reviewer`, basis (`answer`, `lawyer`,
  `bracketed`) and a neutral note. Totals: **26 `legislation_only`, 10
  `legislation_and_case_law`, 6 `case_law_included`, 8 `unknown`**.
  `classification.json` is untouched.
- **Two pre-pilot facts made a read possible. Neither was on the row, and
  both were checked in code at `f8fe9ec`, the last `main` commit before the
  first of the twelve.**
  (1) The research type was **one saved preference per user**
  (`users.research_mode`, default `legislation_only`), written only when the
  Research filters modal was applied, and restored on every chat and login. A
  change is therefore an event, and a lawyer's turns between two equal reads
  are bracketed.
  (2) Each type left behaviour in the answers. The legislation-only Manager
  declined every case-law question in these sessions. The hybrid Manager note
  told the Worker to ALSO search case law, so hybrid answers report case-law
  results nobody asked for (6338 three times out of three), in the
  `search_case_law` description's own coverage wording (6340, 6341 t4). The
  case-law-only Manager was told to say so when asked about legislation.
- **The harness** (`replay_set._resolve_research_modes`) sends `snapshot`,
  `reviewer` and `reviewer_partial` (`case_law_included`, sent as
  `legislation_and_case_law`) values, or else `unknown`. It never writes
  `default`. `Session.research_mode` is None where the export is blank. The
  worker and synthesis seams in `seam_replay` now use the turn's type.
- **`replay_report modes`** prints the research type each turn sent and what
  that rests on. It names the unknown turns and the case-law-only turns, and
  it exits 1 on a `default` label or on a type that the read rules out. The
  export half prints the same provenance over all 62 sessions: snapshot 130,
  reviewer 36, reviewer_partial 6, unknown 24 (16 of these in PASS sessions
  that are never replayed).
- **Tests 1578 → 1603**, all green (`pytest -q` redirected to a file, exit
  code checked). On scratch copies:
  - with the three tool files at HEAD, all 25 new tests and the amended
    deadend test fail;
  - with the resolver stubbed back to the default, 7 fail;
  - without the `modes` graders, 4 fail;
  - with the seam back on the session filter, 1 fails.
  The two `git show` tests were not in the files run.

**Surprises / deviations from FIX_PLAN:**
- **The default was not just unlabelled; it was wrong on 16 of the 50
  turns.** Those are 6335 t6–7, 6338 t1–3, 6340 t1, 6341 t1–5, 6347 t2–4 and
  6350 t3–4, and every sweep sent them without the case-law tool the lawyer
  had. Over the 39 directories that is 14 directories and 153 turn-runs; rep
  1 of `baseline`, `wave1`, `wave2` and `wave0_conv` carries 16 each. The
  brief expected the P4.6 counts on these sessions to be artefacts of the
  chat mode; they are artefacts of the research type too.
- **P4.6's acceptance needs re-choosing before it is built.** Its sessions
  6340 and 6341 t1–5 ran hybrid, and `WORKER_SYSTEM_PROMPT_HYBRID` carries
  none of P4.6's three scripted lines (checked in the prompt text). The
  acceptance as written ("6340 and 6341 carry none of the scripted
  sentences") would now pass whatever the fix did. This is recorded on the
  row.
- **Design point (a) went against the brief's recommendation.** An `unknown`
  turn sends the nearest read in its own session, not `legislation_only`.
  The global default would have introduced a type change nobody made:
  6341 t6–8 would drop case law after t5, and P4.1's marker would fire on
  it. The label is `unknown` either way, and 6348 sends exactly what it sent
  before. Point (b) follows the brief: `unknown` is named and does not fail.
- **`modes` now exits 1 on older directories.** The exit is new on exactly
  four: `wave0_conv`, `wave3_p313b`, `wave3_p313c` and `wave4_p41_conv`. The
  other 18 that exit 1 already did so on chat mode. P4.1's acceptance
  directory still exits 0. Earlier statements that every exit-1 subcommand
  was 0 on those four were true of the instrument at the time.
- **The data-handling test caught my own notes twice.** Two notes named
  judgments the lawyer had typed into a question in 6350, and the five-word
  check tripped on the case names. The rule applies to public case names
  too, so the notes now use neutral citations.
- **The row's trap was worth recording, and it has a companion.** A neutral
  citation alone is not evidence, and neither is a case-law negative alone:
  P4.1's handover item (5) has a legislation-only replay claiming case-law
  results. The reads use three things instead: the negative arriving
  unprompted and repeatedly, the coverage wording that only the case-law tool
  carried, and 2026 judgments.
- **A chat-mode question I did not act on.** The 6335 lawyer's feedback says
  that after being pointed to "research mode" at t3 they switched to it.
  t4–t5 have no saved reply, and P0.5 reads their chat mode from a neighbour
  as conversational. The Research flag was off, so this may have been Deep
  Research. P0.7's timing rows would settle it, because an errored request
  still writes one.

**How this session worked, for whoever repeats it.**
- The transcript dump and every script that read the export stayed in the
  scratchpad. Notes were written from the dump, and the leak test checked
  them against the export.
- Every published figure was re-derived by one throwaway script over all 39
  directories, using the `replay_report` functions. It is also behind
  `modes` and pinned by `test_replay_research_reads.py`. ~~To get the
  directory table, run `modes` per directory.~~ Added at the handover:
  `modes --all-dirs` prints that table and its totals.

**State of the branch:** `fix/prepilot-defects`, pushed with this commit.
1603 tests green. Ledger **31 of 49 rows, 8 of 14 buckets**, partial B5
(P3.7, P4.6, P4.7) and B12 (P5.2). `main` is untouched at `c77e779`.

**Machine state:** no uvicorn, no pin file, no worktrees, dev box on its
normal settings (no replay was run). The local gitignored `replay_set.json`
was re-frozen with the reads.

**Spend:** $0.

**Next action:** **P4.6**. Re-choose its acceptance from Research-mode turns
whose type is `legislation_only`, taken from the export or a reviewer's read,
then build Thomas's wording. Raise **P4.5** with the user. **P0.7** needs the
target and can go with the deploy.

**Open with the user:** deploy both cuts to the target: `pg_dump` first, then
`git pull`, `stop_native.cmd` / `start_native.cmd`, `test_apis.ps1` and one
real question. P0.7's read-only `request_timings` query can go with that
deploy. Tell the eval-harness owner the audit event is schema v5. P5.2.
Whether Thomas's review document should be committed.

---

## Session 23 — handover for Session 24 (2026-09-23)

Written at the user's request before a new session starts, so nothing learned
here depends on this session's context. Everything below is also on the rows
it concerns.

**State.**
- Branch `fix/prepilot-defects`, pushed. `main` is untouched at `c77e779`,
  the second cut. Rollback tags: `pre-prepilot-fixes-2026-09-23` (first cut
  only) and `pre-prepilot-fixes-2026-09-22` (before both). Cuts go to `main`
  only when the user asks.
- **1604 tests green.**
- Ledger **31 of 49 rows, 8 of 14 buckets closed.** Partial: B5 (waiting on
  P3.7, P4.6, P4.7) and B12 (waiting on P5.2). Run `python -m
  tools.plan_status` rather than trusting these figures.
- P0.6 is a harness-only change: no product code moved. It needs no
  deployment, and it is the one Fixed row not on `main`.

**Next work: P4.6.** Read its row in full, including the P0.6 caveat at the
end. **Re-choose its acceptance before building anything.** Its evidence
sessions 6340 t1 and 6341 t1–5 ran as `legislation_and_case_law`.
`WORKER_SYSTEM_PROMPT_HYBRID` carries none of P4.6's three scripted lines,
which are in `WORKER_SYSTEM_PROMPT` (the sentence and the retry line) and in
`WORKER_SYSTEM_PROMPT_CASE_LAW` (the case-law line). The acceptance as written
would therefore pass whatever the fix did. Take the replacement from
Research-mode turns whose type is `legislation_only`, by the export or a
reviewer's read (`replay_report modes` shows which), and use `case_law_only`
turns for the third line. The replay harness now sends the reviewer's reads,
so 6340 and 6341 replay as hybrid. Remember that the Research flag was OFF on
the target, so P4.6 is a forward-looking fix: 0 of 179 pre-pilot answers
carry its sentence. Session 14's lesson applies: compare link and
`sources_kept` counts as well as the row's metric.

**Also:**
- **P0.7 (new) needs the target.** It is one read-only `SELECT` of
  `request_timings` for 11–22 August (the query is on the row), exported to
  CSV and joined to the export on `created_at` + `total_cost_usd`. That
  would replace P0.6's human read with the recorded research type and chat
  mode, and would settle 6335 t4–5's chat mode. It can go with the deploy.
- **Raise P4.5 with the user.** It cost $4.89 of `wave3_p313`'s $5.65, each
  empty completion is about 62,912 reasoning tokens, and a bodiless report
  made the Manager write a report heading into a conversational answer.

**What this session established (all on rows; listed so none is lost):**
- **The export's `Filter:` columns are blank for the twelve because the
  feedback form began recording the filters in force only at `e008985`**
  (13 August, 13:24), and the target had not pulled it by 6350 (14:24).
- **At the pre-pilot the research type was one saved preference per user**
  (`users.research_mode`, default `legislation_only`). It was set only
  through the Research filters modal and restored on every chat and login.
  So a change is an event, and turns between two equal reads of one lawyer
  are bracketed.
- **Until `bab9642` (13 August, 15:24) the research-type pill was hidden in
  Conversational mode**, although the type was in force and editable. All
  twelve sessions ran with it invisible on screen. This is on P4.9 and is
  context for B7's user guidance.
- **Behavioural signatures of each type in the pre-pilot answers** (prompts
  at `f8fe9ec`):
  - legislation-only Manager: declines every case-law question;
  - hybrid Manager: briefs the Worker to ALSO search case law, so answers
    volunteer case-law negatives in the `search_case_law` description's
    coverage wording;
  - case-law-only Manager: told to say so when asked about legislation;
  - a 2026 judgment can only have come from the tool;
  - a neutral citation alone is not evidence, and nor is a single case-law
    negative.
- **The default was wrong on 16 of the twelve's 50 turns** (list on P0.6).
  14 of 39 directories are affected, 153 turn-runs; rep 1 of `baseline`,
  `wave1`, `wave2` and `wave0_conv` carries 16 each.
- **The target's `request_timings` records `research_mode` and `chat_mode`
  per chat request** (since `9e69e4c`). An errored request still writes its
  row. The planner endpoint wrote none at the pre-pilot.

**Instruments added this session:**
- `python -m tools.replay_report --dir <D> modes`: now also prints the
  research type each turn sent, what it rests on (export / reviewer /
  reviewer_partial / script / unknown / default / unrecorded), and names the
  unknown and case-law-only turns. It exits 1 on a `default` label or a type
  the reviewer's read rules out. It is still in the exit-1 set.
- `modes --all-dirs`: the census over every directory beside `--dir`
  (informational, exits 0).
- `replay_set.load_research_reads` / `evidence/research_mode_reads.json`:
  the reviewer's reads, validated. `test_replay_research_reads.py` fails if
  a note repeats five words of a session's questions.

**Expect these, and do not treat them as regressions:**
- `modes` exits 1 on every pre-P0.6 directory holding an affected turn or a
  `default` label: 22 in all, of which 4 are new (`wave0_conv`,
  `wave3_p313b`, `wave3_p313c`, `wave4_p41_conv`).
- A FRESH sweep of the twelve sends the reviewer's reads. It is no longer
  like-for-like with any earlier directory on the 16 turns: they now carry
  the case-law tool, so expect case-law searches, cost and `caselaw` /
  scope-line output on them. Before comparing against an old directory, use
  `--session`, or name the turns.

**Hazards (carried forward, still live):**
- Line endings: tracked files are CRLF. Check bytes with Python, not
  `grep $'\r'`. The Write tool writes LF, so normalise before committing.
- A Python script inside a bash heredoc mangles backslashes. Use the Edit
  tool, or write the script to a file.
- `git commit -F -` / `git merge -F -`: put the message in a file.
- Ledger rows stay on ONE line with an even `**` count. Many ticked rows
  have no closing ` |`, so an append helper must handle both shapes.
- The data-handling test covers public case names too, where they are
  written the way a lawyer typed them.
- Scratch-copy revert checks: `test_the_prompt_reader_finds_a_real_constant`
  and `test_the_manager_body_reader_finds_the_constant` fail in any non-git
  copy.
- Seam draws at temperature 0 are not byte-deterministic.

**Machine state:**
- no uvicorn running, no pin file, no worktrees;
- dev box on its normal settings: model `google/gemini-3.1-pro-preview`,
  summarisation `google/gemini-3-flash-preview`, local prompt cache ON,
  `research_mode_enabled` ON;
- 39 replay directories; none added this session;
- the local gitignored `replay_set.json` was re-frozen with the reads;
- transcript export (never in the repo):
  `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`;
- Fix Tracker: <https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ> (source
  `docs/prepilot-fixes/summary-table.html`; update only when asked;
  updated at the end of this session).

**Open with the user (unchanged unless they say otherwise):**
- Deploy both cuts to the target: `pg_dump` first (no backup has ever run
  there), then `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1` and one real question. It is still not
  confirmed that the first cut (`d8fd73b`) was ever pulled. P0.7's query can
  go with this.
- Tell whoever runs the lexchat-eval harness that the audit event is schema
  v5. This session did not change the schema.
- P5.2 (B12, external).
- Whether Thomas's review document should be committed.
