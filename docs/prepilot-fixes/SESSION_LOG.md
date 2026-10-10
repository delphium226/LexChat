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

---

## Session 24 — 2026-09-23 — P4.6 (the scripted negatives)

**Done:**
- **P4.6 is DONE.** Ledger 31 → **32 of 49 rows**; buckets unchanged at 8
  of 14. **B5 stays partial, now waiting on P3.7 and P4.7.**
- **The acceptance was re-chosen first and committed before any build**
  (`d860675`): scripted Research-mode turns under the research type the export
  or the reviewer's read gives. That was `legislation_only` for 6335 t1-4,
  6343, 6346, 6347 t1 and 6350 t1-2, and `case_law_only` for 6385 as the
  case-law line's smoke. It had four pass conditions and a contingency in case
  the before-column came back empty.
- **The fix** (`9ba8ee8`). Thomas's wording is in `WORKER_SYSTEM_PROMPT` (both
  lines), and the legislation Worker is told its tools search legislation only,
  so a question outside them is "not searched", never "not found". The
  case-law Worker's MANDATE line gets the same treatment, and so do its PHASE 4
  and STOP RULE, which restated the verdict. The hybrid and quick-lookup
  Workers never carried the lines and are untouched. It is pinned by
  `test_worker_scripted_negatives.py`.
- **Results** (all on the row and in `BASELINE.md`, *The scripted
  negatives*):
  - The before-column at HEAD is empty (0 in 49 turns).
  - The seam A/B over 37 stored payloads went from **32 of 32 reports to 0 of
    31**.
  - The replay after-column exits 0 on every grader. `negatives` went from 1
    to 0.
  - Links fell in 0 of 21 slots, and `sources_kept` in 1 (n=1, explained on
    the row).
- **Tests 1604 → 1641**, all green. On a scratch copy with `prompts.py` at
  HEAD, 8 of the pin test's 24 fail; with the tools at HEAD, 10 fail (2 of them
  the known git artefacts).
- **Instruments:**
  - `replay_report scripted [--before] [--reports]`.
  - `seam_replay worker --first-round`: the Worker's first round with its real
    tools offered, stopped at the first call. It is the only seam for a Worker
    that writes without searching.
  - `tools/seam_sweep.py`: the Worker seam over every stored delegation that
    showed a defect, both sides from one command.
  - `seam_replay worker --without-fix` now swaps the constant of the turn's own
    research type, in place.

**Surprises / deviations from FIX_PLAN:**
- **The before-column was empty, and P4.1 is why.** In every stored sweep the
  sentence came mostly from the Research-mode Manager delegating a case-law
  question to the legislation Worker, which then wrote it, often without a
  single tool call. Since P4.1 that Manager declines the question itself and
  delegates nothing. In the scripts, 39 of 49 turns delegated nothing. So the
  sentence can no longer reach a lawyer on the shape that produced most of it,
  and the replay could not discriminate. The seam carried the A/B, as booked.
- **The seam tool was wrong for this row in two ways, and one was mine to
  find.**
  - `--without-fix` always swapped `WORKER_SYSTEM_PROMPT` (the wrong Worker on
    a case-law turn), as the handover said.
  - It also replaced the WHOLE prompt with the bare literal, so the "without"
    side had lost the date line, the rules and the filter block as well as the
    change. The swap is now in place.
- **A scratch draw overstated a behaviour change, and the committed command
  corrected it.** My first scratch A/B had the fix making 6 no-search payloads
  search first against 0 before. Re-run through `seam_sweep`, the before side
  searched first on 5. It is draw noise at temperature 0 on this model
  (Session 22's hazard), not the fix. The published figures are the command's.
- **I miscounted once:** I wrote 15 zero-tool payloads, and the listing says
  16. Corrected before commit.

**Watch item (on the row, not a new row):** on a case-law brief, the
legislation Worker searches legislation first in about 1 payload in 6, on both
sides. What it then writes is not observable at the seam. At HEAD the Manager
declines those questions before delegating.

**State of the branch:** `fix/prepilot-defects`, pushed with this commit.
`main` is untouched at `c77e779`. **P4.6 is product code** (`prompts.py`
only). Unlike P0.6, it would need a cut to reach the target, and cuts go when
the user asks.

**Machine state:**
- no uvicorn running, no pin file, no worktrees; `tools.replay restore` was
  run;
- the dev box is on its normal settings;
- 41 replay directories (new: `wave4_p46_pre`, `wave4_p46`).

**Spend: $8.33.**
- Replays: $4.98 ($2.89 before, $2.09 after).
- Committed seam A/B: $1.56.
- Scratch seam A/B and probes: $1.79.

**Next action:** **P4.7** (the Deep Research synthesis's gap sentence, this
row's twin, which iterates on `seam_replay synthesis`), or **P3.7**.

**Open with the user (unchanged):**
- Deploy both cuts to the target: `pg_dump` first, then `git pull`,
  `stop_native.cmd` / `start_native.cmd`, `test_apis.ps1` and one real
  question. P0.7's query can go with it.
- Tell the eval-harness owner the audit event is schema v5. This session did
  not change it.
- Raise P4.5. This session's 6385 t4 before-run took 435 s and $0.91 with no
  empty completion recorded, so that was not a P4.5 episode.
- P5.2.
- Whether Thomas's review document should be committed.
- Whether P4.6 should go in the next cut.

---

## Session 24 — handover for Session 25 (2026-09-23)

Written at the user's request before a new session starts, so nothing learned
here depends on this session's context. Everything below is also on the rows
it concerns, or in `BASELINE.md`, *The scripted negatives*.

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 24 commits:
  - `d860675`: the acceptance, booked before any build;
  - `9ba8ee8`: the fix and the instruments;
  - `9f2a448`: the docs;
  - this handover.
- `main` is untouched at `c77e779`, the second cut. Rollback tags:
  `pre-prepilot-fixes-2026-09-23` and `pre-prepilot-fixes-2026-09-22`.
- **1641 tests green.**
- Ledger **32 of 49 rows, 8 of 14 buckets.** Partial: B5 (waiting on P3.7
  and P4.7) and B12 (waiting on P5.2). Run `python -m tools.plan_status`
  rather than trusting these figures.
- **Two Fixed rows are not on `main`:** P0.6 (harness only, needs no
  deployment) and **P4.6, which is product code** (`src/prompts.py` only: no
  config, schema, client or whitelist change). It reaches the target only in
  a cut, and cuts go when the user asks.

**Next work: P4.7 or P3.7** (the user's choice). Both close B5 with the other.

- **P4.7** is P4.6's Deep Research twin. `DEEP_RESEARCH_SYNTHESIS_PROMPT`
  (`prompts.py:1233`, the gap example at `:1257`) scripts *"No reported case
  law was found on X"* for every research type. Read its row in full; its
  evidence is thin and it says to measure first. Three things from this
  session carry over:
  1. **Book the acceptance on the row before building, and plan for an empty
     before-column.** P4.6's replay at HEAD reproduced nothing, because P4.1
     changed the path that produced the defect. Check the same for P4.7: does
     the Deep Research planner or synthesis still reach "case law not found"
     under 'Legislation only' since P4.1?
  2. **The synthesis seam is the cheap instrument** (`seam_replay synthesis`,
     about $0.11 a draw). Its `--without-fix` swaps the whole prompt for the
     constant at `--rev`; the default rev is `2d9ae11` (pre-P3.1), so pass
     `--rev` explicitly.
  3. **Scripts can set `chat_mode: "deep_research"` per turn.**
     `p41_6346_dr.json` is an example. Only the no-question-text rule applies
     to non-`p41_` scripts now.
- **P3.7** is deterministic (`/legislation/lookup`, the held/absent test).
  Read the `external-apis` skill and `/openapi.json` first.

**Instruments added this session (use them, don't rebuild):**
- `python -m tools.replay_report --dir <D> scripted [--before <D>]
  [--reports] [--session …]`
  - counts P4.6's three scripted lines in every Worker REPORT and every
    answer;
  - prints links, `sources_kept` and prose per turn, with the Invariant 1
    panel under `--before`;
  - exits 1 on any scripted line.
  - **It exits 1 on `baseline`, `wave1` and `wave2`**, which predate the fix
    and replayed the twelve in Research mode. That is the before-state, not a
    regression; it exits 0 on `wave0_conv`, `wave4_p41` and `wave3_p313`.
  - **Add it to the exit-1 set for any new sweep:** modes halts negatives
    derivations blanks scoperecord nosearch caselaw deadend **scripted**.
- `python -m tools.seam_replay worker --run <f> --turn N --first-round`:
  - replays the Worker's FIRST round with its real tools offered, stopping at
    the first call;
  - prints the calls it chose, or the report it wrote without searching.
  - It is the only seam for a Worker that writes without searching, and it is
    the probe Session 22's lesson asks for before any Worker prompt change.
- `python -m tools.seam_sweep --dirs … --turns SID:T1,T2 …
  [--without-fix --rev <sha>] [--out DIR] [--list]`:
  - the Worker seam over every stored rep-1 delegation whose report matched a
    defect, both sides from one command;
  - a zero-tool delegation is drawn at the first round.
  - Its `--report-matches` choices are `p46` and `any`; add a pattern for a
    new row.
- `seam_replay worker --without-fix` now swaps the constant of the turn's own
  research type, in place. It used to swap `WORKER_SYSTEM_PROMPT` always and
  replace the whole prompt with the bare literal.

**What this session established (all on rows; listed so none is lost):**
- **Since P4.1, the Research-mode Manager declines a case-law question under
  'Legislation only' itself and delegates nothing.** In the p46 scripts, 39 of
  49 turns delegated nothing. Every pre-P4.1 count of a Worker-written
  negative on these sessions measured a path that no longer runs.
- **Before P4.1, most of P4.6's sentences came from a legislation Worker given
  a case-law brief, often with no tool call at all.** In `wave2`, 10 of 22
  delegations over those five sessions made none.
- **With the fix, the legislation Worker says a source it cannot search was
  "not searched in this research".** That is true in 31 of 31 seam reports;
  the two remaining "database does not contain" sentences are true (the
  legislation index holds no judgments).
- **On a case-law brief, the legislation Worker searches legislation first in
  about 1 payload in 6, with or without the fix.** What it then writes is not
  observable at a seam. Watch item, not a row.
- **Seam draws at temperature 0 vary enough to fake an effect.** A scratch
  A/B showed the fix making 6 payloads search first against 0 before; the
  committed command's before side gave 5. Publish from a committed command,
  never from a scratch run.
- **6385 t4's before-run took 435 s and $0.91 with no empty completion.** It
  was a long case-law Worker run (7 tool calls, 11 LLM calls), not a P4.5
  episode. Do not count it for P4.5.
- **6346 t2 is not a question** (the lawyer's acknowledgement). Every replay
  answers it by asking for one, so do not grade it as a decline.
- **The case-law Worker read 3 judgments where it had read 4** (6385 t4, n=1),
  which is within its prompt's 1–3. It is the only `sources_kept` slot that
  fell.

**Hazards (carried forward, still live):**
- Line endings: tracked files are CRLF. Check bytes with Python. The Write
  tool writes LF, so normalise before committing (this session did so for
  `seam_sweep.py` and the two new test files).
- A Python script inside a bash heredoc mangles backslashes.
- Commit messages: put them in a file and use `-F <file>`.
- Ledger rows stay on ONE line with an even `**` count. An append helper must
  assert the row is found exactly once.
- Scratch-copy revert checks: the two `git show` tests fail in any non-git
  copy.
- **Seam and probe output can contain a lawyer's search terms** (the Worker
  echoes them as queries). Keep that output in the scratchpad. Before
  committing, grep the diff for the terms you saw.
- The API runs any chat mode it is sent. `replay pin` turns
  `research_mode_enabled` OFF.

**Machine state:**
- no uvicorn running, no pin file, no worktrees; `tools.replay restore` was
  run;
- dev box on its normal settings: model `google/gemini-3.1-pro-preview`,
  summarisation `google/gemini-3-flash-preview`, local prompt cache ON,
  `research_mode_enabled` ON;
- 41 replay directories; new: `wave4_p46_pre` (`d860675`) and `wave4_p46`
  (`9ba8ee8`);
- transcript export (never in the repo):
  `C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv`;
- Fix Tracker: <https://claude.ai/artifact/JtrwLwRZnRihfe8kHj3EaJ>, updated
  to **version 15** at the end of this session (P4.6 Fixed, and noted as not
  yet deployed). Source `docs/prepilot-fixes/summary-table.html`; update only
  when asked.

**Spend this session: $8.33.**

**Open with the user (unchanged unless they say otherwise):**
- Whether P4.6 goes in the next cut to `main`.
- Deploy both cuts to the target: `pg_dump` first (no backup has ever run
  there), then `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1` and one real question. It is still not confirmed
  that the first cut was ever pulled. P0.7's query can go with this.
- Tell whoever runs the lexchat-eval harness that the audit event is schema
  v5. This session did not change the schema.
- Raise P4.5: $4.89 of `wave3_p313`'s $5.65; about 62,912 reasoning tokens
  per empty completion.
- P5.2 (B12, external).
- Whether Thomas's review document should be committed.

**Addendum to the Session 25 handover (same day, after it was written): pre-flight for the next row.**
Both candidates were checked before writing the kick-off prompt, and the
results are on their rows:
- **P4.7** has no measured instance of its case-law half. That covers 149
  stored `legislation_only` Deep Research turns, and the pre-pilot answers of
  6365, 6405 and 6408 in the export. It needs re-scoping with the user.
- **P3.7**'s instruments are still 404 in LEX today, and so is the stub's
  section lookup. Its acceptance premise has moved since P2.4, so the
  before-column is to be measured at HEAD.

**Recommended next row: P3.7.** P4.7 is the alternative only after the user
decides its scope.

---

## Session 25 — 2026-09-24 — P3.7 (the held/absent test), and P4.7's scope decided

**Done:**
- **P4.7's scope was put to the user first, and decided: option (a).** Build
  the per-mode synthesis prompt as defence in depth, with a seam-only
  acceptance, as P4.6 was. It is recorded on the row and was not started.
- **P3.7 is DONE** (user decision on the result, on P3.1/P3.11's precedent).
  Ledger 32 → **33 of 50 rows**; buckets unchanged at 8 of 14. **B5 stays
  partial, now waiting on P3.15 (new) and P4.7.**
- **The acceptance was re-chosen and committed before any build**
  (`b694fac`), around definiteness. It comes with a new grader
  (`replay_report lookup`) and two scripts (`p37_6409`, `p37_6373`). The
  grader was checked against eight stored directories and corrected twice
  before its first use.
- **The fix** (`475ef57`, `0c91fb6`, `782a9e8`):
  - `lookup_legislation` reports held / held without text / not held.
  - Code runs it on every instrument a Worker's brief names by number,
    before the Worker's first round.
  - The outcome reaches the Manager in the worker block, and the lawyer in a
    code-written footer clause, which P2.8's carried line now restates on
    follow-ups.
  - No prompt changed.
- **Results** (all on the row and in `BASELINE.md`, *The held/absent test*):
  - Absent slots went from 0 of 12 to **11 of 12** in both runs on the fixed
    code. Delegated slots pass 21 of 21, and the misses are from-history
    follow-ups (P3.15).
  - Stub 6 of 6 throughout; the held Act was never reported absent; zero
    sentences questioning a citation in any run.
  - The exit-1 set exits 0 on both fixed runs.
- **Tests 1641 → 1698**, all green. That is 57 new: 48 product, 9 grader.
  Reverting one product file at a time on a scratch copy fails 12 / 2 / 1 / 2
  tests (executor / schemas / agent_core / agent_shared).
- **Instruments:**
  - `replay_report lookup [--answers] [--routing DIR… --live]`.
  - `seam_replay worker --first-round` now applies the routing to a stored
    brief; `--without-lookup` is the before side.
  - `nosearch` reads P3.7's two lookup lines.

**Surprises / deviations from FIX_PLAN:**
- **The before-column was not empty, but the defect had changed.** Nothing
  questions the citation any more (P2.2/P2.4). But 6373 t2 already said "does
  not hold" in 3 of 3 reps with no by-number probe behind it: the right
  words, unearned. And 6409 t9-11 mostly said only that the TEXT is not held.
- **At HEAD the Worker already probed the SSI by id.** It called
  `get_legislation_text` on an id it had guessed from a change record, and
  got a 404 that P2.4 annotates. So a lookup existed by accident, only on
  turns where the model thought of it.
- **The index holds a change record BY an instrument it does not hold.**
  `/amendment/search` returns 1 relation made by `ssi/2025/377` and 46 made
  by `ssi/2026/170`. The not-held sentence now names that call.
  - A first draft instead said "do not search for it again". On the
    first-round probe the Worker then wrote at once on 4 of 5 stored briefs,
    losing 6409's s.18 commencement.
  - The probe caught it for $0.13, before any replay.
- **A held instrument with the same number as the one asked about is a live
  hazard.** `uksi/2026/170` is held and is an unrelated planning instrument.
  - The routing looks it up when a Manager brief names it, and the survey
    found three such briefs in the corpus.
  - The block for a held instrument therefore names its title and says to
    check it is the one asked about. "Use it directly" was cut before any
    run.
  - In `wave4_p37` that held: the answer described it as unrelated.
- **The first acceptance run found three product defects, not one.**
  1. The Manager narrowed "not held" to "its text".
  2. The lookup-only footer said "no ranked search" on a turn that had
     searched within an instrument.
  3. That line pre-empted P2.8's carried search terms.

  Each was fixed and tested before the re-run.
- **The measuring instrument was wrong twice and the product right both
  times.**
  - `nosearch` did not know the lookup line.
  - `lookup` read "This index does not hold the instrument itself" as silence
    because the sentence names no number. That moved `wave4_p37c` from 8 to
    11 of 12.
  - After each fix every stored directory was re-graded and every changed
    row read. No verdict flipped anywhere else.
- **A commit made mid-run changed three run files' recorded head.**
  `wave4_p37_reach`'s 6360, 6378 and 6410 record `782a9e8` but ran against
  the `0c91fb6` server. The difference is footer-only, and the row says so.
  New hazard: do not commit while a replay whose head matters is running.
- **The `external-apis` skill is not tracked in git.** `.claude` is ignored.
  The skill was updated on this machine only (6 of 13 endpoints; the lookup
  facts).
- **My product commit message says "11" executor failures on revert.** That
  was measured before the memo-path test existed; it is 12 on the committed
  code. The row carries 12.

**State of the branch:** `fix/prepilot-defects`, pushed with this commit.
`main` is untouched at `c77e779`.
- **P3.7 is product code:** `agent_core`, `agent_shared`, the executor, the
  schema and `search_scope`, plus the new `utils/instrument_lookup.py`.
- No config, schema, client or whitelist change. The LEX base URL is
  unchanged: the two endpoints are on the same host.
- It reaches the target only in a cut, when the user asks.

**Machine state:**
- no uvicorn running, no pin file, no worktrees; `tools.replay restore` was
  run;
- the dev box is on its normal settings;
- 47 replay directories. New: `wave4_p37_pre`, `wave4_p37`, `wave4_p37b`,
  `wave4_p37c`, `wave4_p37_reach`, `wave4_p37_reach_pre`.

**Spend: $10.01.** Replays $9.18, committed seam $0.22, scratch seam probes
$0.47, scratch Manager A/B $0.14.

---

## Session 25 — handover for Session 26 (2026-09-24)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 25 commits:
  - `b694fac`: the acceptance;
  - `475ef57`: the fix;
  - `0c91fb6`: three defects from the first run;
  - `782a9e8`: the carried lookup;
  - this docs commit.
- `main` is untouched at `c77e779`. Rollback tags:
  `pre-prepilot-fixes-2026-09-23` and `pre-prepilot-fixes-2026-09-22`.
- **1698 tests green.**
- Ledger **33 of 50 rows, 8 of 14 buckets.** Partial: B5 (waiting on P3.15
  and P4.7) and B12 (waiting on P5.2). Run `python -m tools.plan_status`.
- **Three Fixed rows are not on `main`:**
  - P0.6 (harness only);
  - P4.6 (`prompts.py`);
  - P3.7 (code, listed above).

**Next work: P4.7, option (a)** (the user's decision this session).
- Put the pre-flight counts behind a command first, as its row says.
- Then iterate on `seam_replay synthesis`, passing `--rev` explicitly.
- P3.15 is measure-first and small.

**Instruments added this session (use them, don't rebuild):**
- `python -m tools.replay_report --dir <D> lookup [--answers]`:
  - grades P3.7's slots;
  - exits 1 on any failing graded slot. **It exits 1 on `wave4_p37b` and
    `wave4_p37c` because of the P3.15 residual: expected.**
- `lookup --routing DIR… [--live]`: which stored briefs the routing reaches,
  printing ids only.
- `seam_replay worker --first-round [--without-lookup]`.
- Add `lookup` to the exit-1 set for any sweep that replays 6409 or 6373.

**Hazards (carried forward, plus one new):**
- **New: do not commit while a replay is running.** The run files record the
  repo's head at write time, not the server's.
- Line endings, heredoc backslashes, `-F <file>`, one-line ledger rows: as
  before. Python in a bash heredoc bit twice this session. Both times it
  stopped at an assert before writing anything.
- Seam and probe output echoes the Worker's queries, and some graders echo
  the question. Keep that output in the scratchpad.

**Open with the user (unchanged unless they say otherwise):**
- Whether P4.6 and P3.7 go in the next cut to `main`.
- Deploy both cuts to the target: `pg_dump` first (no backup has ever run
  there), then `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1` and one real question.
  - It is still not confirmed that the first cut was ever pulled.
  - P0.7's query can go with the deploy.
  - **P3.7 calls two more LEX endpoints on the same host**, so the whitelist
    does not change.
- Tell whoever runs the lexchat-eval harness that the audit event is still
  schema v5. A new tool name, `lookup_legislation`, now appears in
  `delegations[].tools[]`, usually first; `AUDIT_TRACE.md` documents it.
- Raise P4.5: $4.89 of `wave3_p313`'s $5.65; about 62,912 reasoning tokens
  per empty completion.
- P5.2 (B12, external).
- Whether Thomas's review document should be committed.

**Addendum to Session 25 (same day, after the handover was written, at the user's request).**

**Recorded here so they are not lost:**
- **Watch item from the reach check (n=1, `wave4_p37_reach` against
  `wave4_p37_reach_pre`).** Links fell in 3 of 12 slots: 6378 t1 3 → 0,
  6378 t2 1 → 0, 6383 t1 2 → 1. None of those turns ran the lookup.
  - 6378 t1's brief named no instrument by number.
  - 6378 t2 answered from history with no delegation.
  - The only difference on 6378 t1 is that `lookup_legislation` is now in
    the tool list, offered and not called. n=1 cannot separate that from
    draw noise. If a later sweep shows links falling on turns that did NOT
    route, suspect the offered tool (Session 14 saw a context change move
    the quick-lookup Worker's format).
  - On the acceptance slots, 6409 export t10's links went 0.7 → 0.0
    (`wave4_p37c`, n=3).
- **The lookup-only footer line is gated on `scope_unknown`** (`782a9e8`),
  like P2.8's carried line. After a failed delegation or a peer consult the
  turn's searches are unknown, so "no ranked search was run" could be false.
  It was in a commit message only.
- **Where the unused scratch evidence went.** The first-round probe outputs
  and the scratch Manager A/B echo the Worker's and the lawyers' own search
  terms, so they were left in the session scratchpad and not committed.
  - Every number quoted from them is on P3.7's row, from the committed
    `seam_replay` command.
  - The scratch Manager A/B ($0.14) only guided the limb wording and is not
    quoted.

**Fix Tracker v16** (published to the same URL at the user's request):
- New **Fixed date** column: the first commit in which `FIX_PLAN.md` shows
  the row ticked `[x]`, from `git log --reverse --
  docs/prepilot-fixes/FIX_PLAN.md`.
  - It was checked against this log's session dates and agrees for every
    row.
  - It is the date a fix was accepted, not deployed, and the page says so.
  - Rows carry it as `fixed: "YYYY-MM-DD"`.
- P3.7 → Fixed (24 Sep 2026). P3.15 added (Verified, P3). The prose now
  covers P3.7 and "next: P4.7 (a)".
- The tracker's `fixed` values, 27 rows on 26 refs (P3.1 appears twice):
  - P1.1-P1.4: 14 Sep.
  - P1.6, P2.1, P2.2, P2.6, P4.4: 15 Sep.
  - P2.3, P2.5, P2.9, P3.5, P4.2: 16 Sep.
  - P2.4, P2.7, P2.8: 17 Sep.
  - P3.1: 18 Sep.
  - P3.8: 21 Sep.
  - P0.5, P3.11, P4.1: 22 Sep.
  - P0.6, P3.13, P4.6: 23 Sep.
  - P3.7: 24 Sep.
- **When a row is next ticked, add `fixed:` with that commit's date.** The
  page does not compute it.

**Fix Tracker v17 and v18** (same day, both at the user's request, same URL):
- **v17** (`5e77dea`): the table is ordered by **severity** (P1 first), then
  **status** (Fixed first), then **fixed date** (oldest first). Undated rows
  and ties keep plan order. It was status then severity. The divider rules
  fall between severity/status bands.
- **v18** (`89b7b3d`): the progress panel has a **By severity** group, one
  stacked bar each for P1/P2/P3 split by status, above a **By source** group.
  - It is computed from `ROWS`, so it needs no editing when rows change.
  - It reuses the page's validated status fills and order (no new colours),
    so the palette validation noted in the page's CSS still covers it.
  - At v18: P1 10 fixed of 13; P2 12 of 22; P3 5 of 15.
- Both were checked by rendering the page in a browser, light, dark and at
  390px.
  - The Playwright tool blocks `file:` URLs, so serve the directory first:
    `python -m http.server 8765 --bind 127.0.0.1` from
    `docs/prepilot-fixes/`, then stop it.
  - The quotes show as mojibake there only because that server sends no
    charset; the artifact host serves UTF-8.

**New hazard: `sed -i` in Git Bash rewrote the tracker's CRLF line endings to
LF.** It was caught by the byte check and normalised before commit. Edit
tracked files with the Edit tool or a Python byte script, not `sed -i`.

---

## Session 26 — 2026-09-24 — P4.7 (the Deep Research synthesis, per research type)

**Done:**
- **P4.7 is DONE** (option (a), the user's decision in Session 25). Ledger
  33 → **34 of 50 rows**; buckets unchanged at 8 of 14. **B5 stays partial,
  now waiting on P3.15 alone.**
- **The pre-flight went behind a command first**:
  `replay_report drgaps [--all-dirs] [--export] [--list] [--sentences]`
  (`09fb1ed`). It reproduces the scratch read (149 `legislation_only`
  syntheses, 20 turns matching a case-law word, 5 synthesis reports naming
  case law, all as excluded) and finds 0 case-law 'not found'. Its recall was
  checked on the export (6338, 6370 and 6407 fire, as the pre-flight said).
- **The seam's `--without-fix` confound was fixed before any A/B**
  (`09fb1ed`). The pinpoint block is now stripped only if `--rev` predates
  P3.1's builder. The prompt is built for the turn's research type, including
  at a revision whose prompt is per-type (that revision's `prompts.py` is
  executed in isolation). `_cfg_for` falls back to the audit's research type.
  `seam_sweep --synthesis p47 [--grade]` is the synthesis sweep.
- **The acceptance was re-chosen and committed before any product code**
  (`9cacde8`): seam-only, with four pass conditions and the empty-before
  contingency written down.
- **The fix** (`d304652`, then `158841d`):
  `get_deep_research_synthesis_prompt(research_mode)`.
  - It names what the type searched and did not, and carries Thomas's gap
    wording for every type.
  - Its sections come from `REPORT_SECTIONS`, moved to `prompts.py` as the one
    definition.
  - P2.5's rules and P3.1's pinpoint rule are kept for every type.
  - `research_mode` is passed explicitly from `run_deep_research` and by the
    seam tool.
- **Results** (all on the row and in `BASELINE.md`, *The Deep Research
  synthesis, per research type*):
  - `legislation_only` case-law 'not found' 1 → 0 (D17's own sentence, 6341
    t7).
  - All 6 hybrid true negatives survive; hybrid sections 0 → 8 of 8.
  - Links 594 → 691 and 182 → 208; pinpoints 24 → 24 and 15 → 17; Key
    findings 20/20 and 8/8.
  - Smoke `wave4_p47b`: every grader exits 0, depth DELIVERED.
- **Tests 1698 → 1795**, all green.

**Surprises / deviations from FIX_PLAN:**
- **The before column was NOT empty.** The replays hold no instance (0 in
  165 `legislation_only` Deep Research turns), but the seam at `9cacde8`
  wrote D17's sentence on 6341 t7 in 2 of 4 draws. Its stored report says
  the accurate thing, so the sentence is live in the prompt and the replay
  had simply not drawn it. The contingency was not needed.
- **The first wording failed Invariant 1 on the seam, and the committed
  command caught it.**
  - 6408 wrote bare-URL references (2 of 4 after-draws against 0 of 4).
  - 6407 dropped the **Key findings** label (2 of 4 against 0 of 4).
  - Three redraws a side confirmed each.
  - Two lines, for every type, fixed both. The after column was then
    redrawn in full at the new commit, and only that column is published.
- **The instrument was wrong four times, the product right each time:**
  - `drgaps` flagged an accurate exclusion before first use;
  - the sweep compared pinpoint spellings literally;
  - it read a did-not-complete gap as silence;
  - it could not see a judgment link with a bracketed year.
  Each changed row was re-read after re-grading. The last is a defect in
  `replay_report.MD_LINK` itself, left unchanged: **every grader that counts
  links with it undercounts judgment links.** That is a watch item.
- **My own slip, caught before it reached a number:** I first put
  `wave4_p41`/p41_6346_dr t2 in the `legislation_only` payload set from a
  4-character slice of its type. It ran hybrid. It was removed before any
  draw.
- **One observation the row did not ask for:** on a hybrid payload whose
  step 1 returned nothing, the before-draw said step 1 "found no" case law.
  That is a negative from a search that never completed, and the after-draw
  says the step "did not return findings". This is Thomas's second limb, and
  it is the only place this session saw it tested.

**State of the branch:** `fix/prepilot-defects`, pushed with this commit.
`main` is untouched at `c77e779`. **P4.7 is product code** (`prompts.py`,
`agent_core.py`): no config, schema, client or whitelist change. It reaches
the target only in a cut, when the user asks.

**Machine state:**
- no uvicorn running, no pin file, no worktrees; `tools.replay restore` was
  run;
- the dev box is on its normal settings;
- 49 replay directories. New: `wave4_p47` (6365 at `d304652`, the first
  wording) and `wave4_p47b` (6365 at `ac7878e`, whose product code is
  `158841d`'s).
- The seam draws are in the session scratchpad, not the repo (they echo
  lawyers' terms).

**Spend: $14.49 (seam sweeps $8.54, committed redraws $3.16, scratch probe $0.71, replays $2.08).**

---

## Session 26 — handover for Session 27 (2026-09-24)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 26 commits:
  - `09fb1ed`: the instruments (`drgaps`, the seam confound, the synthesis
    sweep);
  - `9cacde8`: the acceptance;
  - `d304652`: the fix;
  - `158841d`: the link and label lines;
  - `ac7878e`: the grader corrections;
  - this docs commit.
- `main` is untouched at `c77e779`. Rollback tags:
  `pre-prepilot-fixes-2026-09-23` and `pre-prepilot-fixes-2026-09-22`.
- **1795 tests green.**
- Ledger **34 of 50 rows, 8 of 14 buckets.** Partial: B5 (waiting on P3.15)
  and B12 (waiting on P5.2). Run `python -m tools.plan_status`.
- **Four Fixed rows are not on `main`:**
  - P0.6 (harness only);
  - P4.6 (`prompts.py`);
  - P3.7 (code);
  - P4.7 (`prompts.py`, `agent_core.py`).

**Next work: P3.15**, the last row B5 waits on. It is measure-first: count
the from-history absent slots over any sweep that replays 6409 or 6373 past
their lookup turn before building. Its lever is the conversational Manager's
NOT HELD rule, so Session 22's first-round probe applies. Otherwise the
unblocked Wave 3/4 rows stand as the recommended-order line lists them.

**Instruments added this session (use them, don't rebuild):**
- `python -m tools.replay_report --dir <D> drgaps [--all-dirs] [--export]
  [--list] [--sentences]`:
  - every answered Deep Research turn by research type;
  - exits 1 on a case-law 'not found' under a type with no case-law tool;
  - `--sentences` prints text, so keep that output in the scratchpad.
  - **It joins the exit-1 set for any sweep with Deep Research turns.**
- `python -m tools.seam_sweep --synthesis p47[_legislation or _hybrid] --out
  DIR [--without-fix --rev SHA]`, then `--grade DIR`:
  - the synthesis seam over fixed payloads;
  - `--rev` is required on the without side.
- `seam_replay synthesis --without-fix`:
  - the pinpoint block is stripped only if `--rev` predates it;
  - the prompt is built per type at a per-type revision.
- **Watch item:** `replay_report.MD_LINK` misses `[… [2011] EWCA Civ
  1089](url)`. Any link count it produces undercounts judgments.
  `seam_sweep.MD_LINK_NESTED` does not.

**Hazards (carried forward):** line endings (and `sed -i`), heredoc
backslashes, `-F <file>`, one-line ledger rows, not committing during a
replay, keeping seam output (which echoes lawyers' terms) in the scratchpad.
**New:**
- a background job started with a trailing `&` inside one Bash call dies
  with that shell; use the tool's background mode;
- never read a research type from a truncated string.

**Open with the user (unchanged unless they say otherwise):**
- Whether P4.6, P3.7 and P4.7 go in the next cut to `main`.
- Deploy both cuts to the target: `pg_dump` first (no backup has ever run
  there), then `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1` and one real question.
  - It is still not confirmed that the first cut was ever pulled.
  - P0.7's query can go with the deploy.
- Tell whoever runs the lexchat-eval harness:
  - the audit event is still schema v5;
  - `lookup_legislation` now appears in `delegations[].tools[]`;
  - a Deep Research report's section headings now follow its research type
    (a hybrid report has Statutory Framework and Key Cases).
- Raise P4.5: $4.89 of `wave3_p313`'s $5.65; about 62,912 reasoning tokens
  per empty completion. P4.7's prompt now reads an empty step as one that
  did not complete (on the seam, P4.5's own 6375 instance). The labelled
  lost-step report P4.5 proposes is still not built: note on its row.
- P5.2 (B12, external).
- Whether Thomas's review document should be committed.
- **The Fix Tracker has not been updated this session** (update only when
  asked). When it is, P4.7 becomes Fixed with `fixed: "2026-09-24"`.

**Addendum to Session 26 (same day, after the handover was written, at the user's request).**

**Fix Tracker v19** (published to the same URL at the user's request):
- P4.7 → Fixed, `fixed: "2026-09-24"`. It is added to the fixes waiting for
  the next release (P4.6, P3.7, P4.7).
- A plain-language note on P4.7 and how it was tested; the P3.7 note is now
  headed "Earlier". "Next" names P3.15 and keeps P4.5.
- The render was checked in a browser (served over `http.server`, as before):
  28 of 50 fixed. By severity: P1 11 of 13, P2 12 of 22, P3 5 of 15.

**Recorded here so they are not lost (the seam draws were in the session
scratchpad, which the next session cannot read):**
- **6357 t3's pinpoint loss at the first wording was draw noise.** The
  after-draw kept 0 of 3 pinpoints, and three redraws a side from
  `seam_replay` gave 0 of 3 in 2 of 3 draws on BOTH sides. At `158841d`,
  that payload's sweep draw keeps 3 of 3.
- **How the redraws were made.** From the committed command, three draws per
  payload per side, output to a scratch directory:
  `python -m tools.seam_replay synthesis --run <run.json> --turn N --reps 3
  --out <scratch> [--without-fix --rev 9cacde8]`.
  - Payloads: `wave2`/6408 t2, `wave2`/6407 t3, `wave4_p41_pre`/p41_6346_dr
    t2, `wave2`/6357 t3, `wave2_p28_smoke`/6341 t7, `wave2_p24_pre`/6375 r1 t2.
  - Grade the files with `seam_sweep.synthesis_grade` (or re-run the sweep).
  - Draws at temperature 0 are not byte-reproducible, so a re-run gives
    counts of the same order, not the same bytes.
- **The per-payload hybrid claim** ("all 6 payloads whose before-draw stated
  a case-law gap still state one") is read from `seam_sweep --synthesis p47
  --grade`: it prints each payload's before and after line with `cl-gap`.
  The command prints no pair table.
- **6375 r1's judgments were never lost.** The grade of the second wording
  (`158841d`) first showed that payload losing 6 judgment links. They were there all
  along, written `[... [2011] EWCA Civ 1](url)`, which `MD_LINK` cannot see.
  That is how the watch item was found.
- **Where each after column lives:** the first wording's in the sweep output
  graded at `ac7878e`, and the published one at `158841d`. The before column
  (`9cacde8`) is shared by both.

**Machine state (unchanged):** no uvicorn, no `http.server`, no pin file, no
worktrees; the dev box is on its normal settings; 49 replay directories.

**Addendum, continued: the next row decided (user decision, 2026-09-24).**
- **P4.5 next, as option (c).** Three options were put: (a) labelling only;
  (b) labelling plus the cost; (c) labelling now, with the cost booked as a
  new row. The user chose (c).
  - P4.5 is the LABELLING half: a lost worker or Deep Research step is
    reported as lost, in code, and the progress event stops saying "Step
    complete".
  - Its acceptance is deterministic. Scope and pre-flight are on its row.
- **New row P4.10:** the cost of a lost completion (about 63,000 reasoning
  tokens per empty attempt; turns of $2.40 and about 20 minutes).
  Measure-first; depends on P4.5. Candidate levers are listed on the row, and
  none is chosen.
  - Ledger: **51 rows**, still 34 done.
  - Recommended-order line added. The Fix Tracker does not list P4.10 yet
    (update it only when asked).
- **Start Session 27 from P4.5's row** (its USER DECISION paragraph), then
  its pre-flight: recount the lost-completion episodes over all 49
  directories with `replay_report blanks`.

**Fix Tracker v20** (same URL, at the user's request, after the P4.5 decision):
- P4.10 added: "Cut the cost and the wait of a lost reply", Verified, **P2**.
  - The severity is a first-pass judgement: the answer is still correct but
    the lawyer waits nearly 20 minutes. It is not a P1, because P4.5 carries
    the wrong-answer half.
- "Next" now says P4.5 (labelling), then P4.10 (cost, measure-first), then
  P3.15.
- Render-checked: 28 of 51 fixed; by severity P1 11 of 13, P2 12 of 23, P3 5
  of 15.
- No `fixed` dates changed.

**Nothing else is outstanding for Session 27.** It starts from P4.5's row
(the USER DECISION paragraph) and its pre-flight.

---

## Session 27 — 2026-09-24 — P4.5 (the lost step, labelled)

**Done:**
- **P4.5 is DONE** (option (c), the labelling half, the user's decision at
  the end of Session 26). Ledger 34 → **35 of 51 rows**; buckets unchanged
  at 8 of 14 (P4.5 is in no bucket's closure list).
- **The pre-flight went behind a command first** (`e25e678`):
  `replay_report --dir <D> lost [--all-dirs] [--list] [--require-label]`.
  - An `empty_completions` record has no delegation id, so the site is read
    off the outcome. Each turn is checked (unrecovered calls = lost sites);
    **0 untied** over all 49 directories.
  - It found every stored instance on P4.5's row with the right site and
    shape before any number was quoted.
  - **16 unrecovered calls in 929 schema-v3 turns (1.7%, Wilson 1.1-2.8%)**:
    research worker 11, Deep Research step 2, Manager 3, synthesis 0. This
    replaces Session 18's 8 in 342.
  - After **15 of 18** lost research-worker reports, a later delegation in
    the same turn returned findings (`637a882` added that count).
- **The acceptance was booked and committed before any product code**
  (`637a882`), with the audit decision: option (i), `delegations[].lost`,
  schema v6.
- **The fix** (`4dfce68`, then `ba04d7c`):
  - `run_worker_agent` labels a lost reply, ahead of the scope block, in
    every chat mode (`lost_worker_report`, a closed
    `[Research Incomplete — answer lost]` block);
  - the Manager path strips the block, keeps it out of P4.2's fallback, and
    prepends a lawyer notice only when no later delegation made the loss
    good;
  - Deep Research names a lost step in `incomplete_steps_note` (its own
    LOST STEPS paragraph) and always in the notice;
  - `progress_result` names each run's outcome on `tool_end`;
  - `seam_replay --apply-lost` rebuilds a recorded lost report through the
    product's builder.
- **Results** (on the row and in `BASELINE.md`, *The lost step, labelled*):
  - acceptance (a): 29 tests in `tests/test_lost_step.py`, each seam failing
    with its file reverted on a scratch copy;
  - acceptance (b): `lost --require-label` exits 1 on exactly the 15 stored
    directories holding a lost report, 0 on the other 34;
  - seam: 6373 r1 t3 (the lost step nothing made good) went from 4 of 4
    restating "not held" to 3 of 3 disclosing the loss; no payload drew a
    negative from a lost step on the after side;
  - smoke `wave4_p45` (6365, n=1): 13 checks exit 0, depth DELIVERED,
    schema 6.
- **Tests 1795 → 1839**, all green.

**Surprises / deviations from FIX_PLAN:**
- **The label must not forbid re-delegation, unlike the halt's.** The
  Manager already recovers that way (15 of 18), so the label permits one
  more call and the Manager-path notice is kept for a loss nothing made
  good. Emitting it always would have warned the lawyer on answers that
  rest on completed research.
- **The label must not deny a timeout.** 6409's failed attempts ended
  "Upstream idle timeout exceeded", so "NOT a timeout" (the halt's line)
  would have been false. The lost-step text never mentions a timeout.
- **The first wording failed on the seam.** All 4 after-draws on 6373 said
  the cause was "a lost reply from the database". `ba04d7c` names the
  model's reply and denies a database fault; 3 of 3 redraws then say so.
  The after column was redrawn in full at that commit.
- **The seam cannot reproduce the Jurisdiction & Status heading**
  (`wave3_p313` rep 2 t1: 0 heading on both sides, as in Session 22), so
  that finding is covered only by the label being applied in conversational
  mode, which a test pins.
- **My own slips, caught before they reached a number:** two Python edits
  run from bash heredocs mangled backslashes (both failed at an assertion or
  at import and were redone from files written with the Write tool); a
  multi-line replacement first failed on CRLF and wrote nothing.

**State of the branch:** `fix/prepilot-defects`, pushed with this commit.
`main` is untouched at `c77e779`. **P4.5 is product code**
(`agent_core.py`, `research_halt.py`, `search_scope.py`, `audit_trace.py`):
no config, DB schema, client or whitelist change, but an **audit schema
change (v6)** the eval harness owner must be told about. It reaches the
target only in a cut, when the user asks.

**Machine state:**
- no uvicorn running (stopped by PID), no pin file (`tools.replay restore`
  run), no worktrees; the dev box is on its normal settings;
- **50 replay directories**; new: `wave4_p45` (6365 at `ba04d7c`).
- The seam draws are in the session scratchpad, not the repo (they echo
  lawyers' terms).

**Spend: $1.91 (seam $0.88, smoke replay $1.03), plus about $0.002 of
model probes.**

---

## Session 27 — handover for Session 28 (2026-09-24)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 27 commits:
  - `e25e678`: the instrument (`replay_report lost`);
  - `637a882`: the acceptance, and `lost`'s re-delegation count;
  - `4dfce68`: the fix;
  - `ba04d7c`: the label's wording (whose reply was lost);
  - this docs commit.
- `main` is untouched at `c77e779`. Rollback tags:
  `pre-prepilot-fixes-2026-09-23` and `pre-prepilot-fixes-2026-09-22`.
- **1839 tests green.**
- Ledger **35 of 51 rows, 8 of 14 buckets.** Partial: B5 (waiting on P3.15)
  and B12 (waiting on P5.2). Run `python -m tools.plan_status`.
- **Five Fixed rows are not on `main`:**
  - P0.6 (harness only);
  - P4.6 (`prompts.py`);
  - P3.7 (code);
  - P4.7 (`prompts.py`, `agent_core.py`);
  - P4.5 (code, audit schema v6).

**Next work: P4.10** (the cost of a lost completion). It is measure-first
and now unblocked. `replay_report lost --list` names every episode; P4.10's
row asks for cost and wall clock per episode, which `lost` does not print
yet. Check whether the provider honours a reasoning cap on this model before
designing around one. **Then P3.15**, which B5 waits on alone.

**Instruments added this session (use them, don't rebuild):**
- `python -m tools.replay_report --dir <D> lost [--all-dirs] [--list]
  [--require-label]`:
  - provider calls empty at least once, recovered or not, and where each
    unrecovered one landed (worker / Deep Research step / Manager /
    synthesis), tied turn by turn;
  - `--list` prints ids, modes, shapes and whether the Manager redid it,
    and no text;
  - **`lost --require-label` joins the exit-1 set for every new
    directory.**
- `python -m tools.seam_replay synthesis|manager --run <f> --turn N
  --apply-lost`: a recorded lost report rebuilt through the product's
  builder, with the product's own source count, and the draw put through
  the answer seam's disclosure.

**Hazards (carried forward):** line endings (and `sed -i`), heredoc
backslashes (twice more this session), `-F <file>`, one-line ledger rows,
not committing during a replay, keeping seam output (which echoes lawyers'
terms) in the scratchpad, never reading an enum from a truncated string.
**New:** a Python replacement script must normalise CRLF to LF before
matching multi-line text, and restore CRLF on write.

**Open with the user (unchanged unless they say otherwise):**
- Whether P4.6, P3.7, P4.7 and P4.5 go in the next cut to `main`.
- Deploy both cuts to the target: `pg_dump` first (no backup has ever run
  there), then `git pull`, `stop_native.cmd` / `start_native.cmd`,
  `server_py\test_apis.ps1` and one real question.
  - It is still not confirmed that the first cut was ever pulled.
  - P0.7's query can go with the deploy.
- Tell whoever runs the lexchat-eval harness:
  - **the audit event is now schema v6**: `delegations[].lost` (null, or
    `{reason: "empty_completion", sources_retrieved}`); a delegation with it
    set is a lost reply, not a negative;
  - the `tool_end` event's `result` now names each worker's outcome;
  - `lookup_legislation` appears in `delegations[].tools[]`;
  - a Deep Research report's section headings follow its research type.
- Whether the chat UI should show a step's outcome (the progress event now
  carries it; showing it is a client change and a `client/dist` rebuild).
- P4.10 next or later; P3.15 after. P5.2 (external). Whether Thomas's
  review document should be committed.
- **The Fix Tracker has not been updated this session** (update only when
  asked). When it is, P4.5 becomes Fixed with `fixed: "2026-09-24"`.

**Addendum to Session 27 (same day, after the handover was written, at the user's request).**

**Release versioning (user decision: calendar versions, `vYYYY.MM.N`).**
- Built on **`main`** as `b2a3fd8`, pushed. This branch does not carry it until the next cut.
  - `VERSION` (repo root, `2026.09.2`): the last release the code contains.
  - `server_py/src/version.py`: `APP_VERSION` from `VERSION`; `APP_BUILD` from
    `git describe --tags --match "v[0-9]*"` (exact on a release, `-N-g<sha>` past one,
    `None` without git).
  - `/api/bot-info` returns `version` and `build`; the About box shows them; FastAPI's
    version is `VERSION`; the first log line is `[Startup] AILA <version> (build <build>)`.
    Live-checked on the dev box and in the browser.
  - `CHANGELOG.md`: 2026.09.1, 2026.09.2, and *Unreleased* (what is queued on this branch).
  - CLAUDE.md on `main` gains *Releases* and a deploy step 6 (confirm the version).
  - `tests/test_version.py`: fails if the nearest release tag is not `v` + `VERSION`
    (checked: a wrong `VERSION` fails 2 tests). 1583 tests green on `main`.
- **Tags, created locally and NOT pushed** (awaiting the user's go-ahead):
  `v2026.09.1` → `d8fd73b`, `v2026.09.2` → `c77e779`, annotated, dated to each merge.
- **The next cut must follow the release procedure** (in CLAUDE.md on `main`, and in
  FIX_PLAN's deployment note): merge; one commit on `main` bumping `VERSION` and moving the
  CHANGELOG's *Unreleased* into a dated section; `git tag -a`; push the tag explicitly.
- Open (in `docs/TODO.md` D19): push the tags; deploy by tag rather than the head of
  `main`; stamp the version on the audit event, `request_timings` and replay run files
  (after the next cut: `main` is audit v5, this branch v6); a pre-existing lint error in
  `useBotIdentity.js`. D20: whether the chat UI should show a step's outcome.

**Fix Tracker v21** (published to the same URL at the user's request):
- **New Version column**: the release each Fixed row is part of, `2026.09.1`, `2026.09.2`,
  or "Next release". Derived mechanically: a row belongs to the first release tag whose
  FIX_PLAN shows it `[x]`. 23 rows in 2026.09.1, 1 in 2026.09.2 (P3.13), and 6 queued (P0.6,
  P3.7, P4.6, P4.7, and both P4.5 rows). Data field `ver`, documented in the ROWS comment.
- P4.5's two rows → Fixed, `fixed: "2026-09-24"` (first ticked in `6bda956`).
- A plain-language P4.5 note; P4.7's becomes "Earlier"; "Next" names P4.10, then P3.15.
- `<meta charset="utf-8">` added: without it, `python -m http.server` served the page as
  Windows-1252 and every curly quote rendered as mojibake in the local render check. The
  file itself was clean UTF-8 and the published page was never affected.
- Render-checked: 30 of 51 fixed; by severity P1 12 of 13, P2 12 of 23, P3 6 of 15.

**Hazards met again:** Python run from a bash heredoc turned a regex's `\n` into a real
newline twice more (both failed before writing anything). Playwright may only write
screenshots under the repo (`.playwright-mcp/`, gitignored), not the scratchpad.

**Machine state:** no uvicorn, no `http.server`, no pin file, no worktrees; the dev box is on
its normal settings; the checkout is back on `fix/prepilot-defects`.

## Session 28 — 2026-09-24/25 — P4.10 (the cost of a lost completion)

**Measure first.** P4.10 had no lever chosen, and every candidate touched every
Worker call. So the session measured, probed and put the levers to the user
before booking anything.

**1. The instrument: `replay_report lostcost [--all-dirs]`** (`23ac8e4`).
- Classifies every empty-completion attempt by mechanism:
  - (a) reasoned to nothing, 10,000+ tokens;
  - (b) stream error or upstream idle timeout;
  - (c) clean stop with no reasoning;
  - (d) upstream rate limit, a mechanism nobody had separated before.
- Ties each call to where it landed:
  - an unrecovered call takes the site `lost_sites` gives it;
  - a recovered call is placed from the timeline when it is the turn's only
    slow call. That inference agrees with the tied site on 10 of 10 calls. The
    first version agreed on 13 of 14: it cannot split a turn with two slow
    calls, so it now refuses there.
- Prices each turn against the median of clean turns in its slot (same
  question hash, chat mode and research type).
- Also prints:
  - what the retry bought after each mechanism;
  - whether the Manager redid an unrecovered worker call;
  - (a) per chat mode, with a Fisher tail;
  - how long healthy worker calls run;
  - a cost-derived bound on whether an output cap could bind a healthy turn.
- Checked against every episode on the row before any number was quoted:
  - 6348 rep 2 t1: $2.40 and 1,133 s against a median of $0.07 and 34 s;
  - p313: $2.48 and $2.40;
  - 6383: $1.62, 768 s;
  - 6409: `bab`, $0.86;
  - 6346: 456 s and 233 s.
- The totals match `lost`: 34 calls, 18 recovered, 16 not, and 930 v3 turns
  now that `wave4_p45` is included.

**2. What it found** (the table is in BASELINE.md, "The cost of a lost
completion").
- (a) is 8 calls, and they carry all the cost: $12.38 and 7,073 s over the slot
  medians, against $156.55 for all v3 turns.
- Every (a) call was in the **conversational quick-lookup Worker**: 8 of 478
  runs there, 0 of 522 elsewhere (Fisher 0.0026). But 4 of the 8 are 6348, so
  5 sessions.
- The retry after (a) answered 2 times in 12. The Manager made good 6 of 6.
- (b) is a latency cost (median 371 s per turn), not a spend one.
- (d) the retry fixes (13 of 14).

**3. The probes.**
- `reasoning_probe`, committed: the output ceiling is 65,536 tokens. With no
  `reasoning` field the model reasons in the `high` range.
  `reasoning.max_tokens` lands on an effort level. A top-level `max_tokens`
  binds.
  - The first, scratch run had "default = high" byte for byte; the committed
    re-run did not (8,709 against 7,861). The docstring and the ledger say
    "the high range".
- `seam_replay worker --as-sent` is new. The old worker seam was a composition
  seam (one round, no tools, a "compose" message), which is not the call that
  failed.
  - The rebuild regroups rounds from tool timing and reproduces every stored
    (a) call's `react_turn`.
  - Both `wave3_p313` payloads rebuild to exactly their recorded
    `sent_chars`.
- Both p313 payloads ran away on 2026-09-24:
  - one empty, 370 s, $0.77;
  - one answered after 62,916 reasoning tokens, 310 s, $0.77. The cost is the
    runaway, and "empty" is how some runaways end.
- `max_tokens=16000`: empty at 15,360 tokens (96% of the cap), 93 s, $0.20.
  The cap bounds the failure; it does not cure it.
- Effort `medium` or `low` did not bound it: 3 of 4 empty on r2 t1.
- Spend on the pre-flight: $4.35.

**4. User decision:** lever (ii) plus a 32,000-token cap on Worker calls,
evidenced by a seam A/B plus unit tests, with no replay. Booked in `484f32f`
before any product code.

**5. The build** (`df95c09`):
- `worker_call` on both clients' `chat_loop`, forwarded through the recursion
  and P3.8's write-up;
- `run_worker_agent` passes it on its research loop only;
- OpenRouter adds `max_tokens: 32000` to a Worker call's payload;
- both clients skip the retry for a Worker call's heavy empty, which falls into
  P4.5's label;
- Ollama gets no cap;
- a length-cut report with content is logged.
- No audit shape change. `AUDIT_TRACE.md` notes that a single
  `attempt: 1, retried: false` record is now possible, and CLAUDE.md's
  stream-retry note says why Worker calls differ.

**6. Acceptance.**
- (a) PASSED: 16 tests, and each product file reverted alone fails them.
  - 49 test fakes across 10 files had no `**kwargs`. Two of them sat behind
    the halt write-up's fail-soft path, which turned the `TypeError` into a
    silent "no write-up" (`assert 0 == 1`), not a crash.
- (c) PASSED: the cap changed nothing where it could not bind. One flagged
  payload (p46_6385) proved to have two stable answers that both sides draw.
- **(b) NOT EVALUABLE:** on 2026-09-25 no draw ran away, 0 in 16 across all
  eight stored (a) payloads, lever-on or off. **User decision: keep P4.10
  `[~]` and redraw later.**
- Spend on the acceptance: $0.80. **Session total: $5.15.**

**Hazards met.**
- A fake `chat_loop` without `**kwargs` breaks the moment a real keyword is
  added. The halt write-up hides it (fail-soft).
- A seam's lever-off side must be drawn on the same day as its lever-on side:
  the failure's rate varies by day.
- The `Write` tool wrote LF into a new test file (299 bare LFs). It was
  normalised before the commit.

## Session 28 — handover for Session 29 (2026-09-25)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 28 commits:
  - `23ac8e4`: the instruments (`lostcost`, `--as-sent`);
  - `484f32f`: the acceptance, `reasoning_probe`, the BASELINE pre-flight;
  - `df95c09`: the fix;
  - this docs commit.
- `main` is untouched at `b2a3fd8`.
- **1872 tests green.**
- Ledger **35 of 52 rows** (P4.11 booked in the addendum below), **8 of 14
  buckets**, with **3 in progress**: P0.4, P5.2 and now **P4.10**.
- **Six Fixed-or-built rows are not on `main`:** P0.6, P4.6, P3.7, P4.7 and
  P4.5, plus P4.10 (built, not accepted).

**Next work.**
1. **Close P4.10's (b).** Redraw `wave3_p313`/6348 r2 t1 and r3 t3 at
   lever-off (`python -m tools.seam_replay worker --run <f> --turn N
   --as-sent`) until one runs away (about $0.02 a healthy draw, $0.77 a
   runaway). Then make three lever-on draws with `--max-tokens 32000` on that
   payload and apply (b) as booked on the row.
   - Draw both sides on the same day.
   - If the runaway never comes back, say so and put it to the user; do not
     re-scope on your own.
2. **Then P3.15**, which B5 waits on alone.

**Instruments added this session (use them, don't rebuild):**
- `python -m tools.replay_report --dir <D> lostcost [--all-dirs]
  [--out-price 12]`;
- `python -m tools.seam_replay worker --run <f> --turn N [--delegation N]
  --as-sent [--round N] [--max-tokens N] [--reasoning-effort E] [--reps N]
  [--out D]`: one attempt per rep, no retry, graded;
- `python -m tools.reasoning_probe [--limits] [CONFIG ...]`.

**Open with the user (carried forward, plus one):**
- Push the two release tags? Deploy by tag? (docs/TODO.md D19)
- Whether P0.6, P4.6, P3.7, P4.7, P4.5 (and P4.10 once accepted) go in the
  next cut: v2026.09.3, or v2026.10.1 in October.
- Deploy both cuts to the target: `pg_dump` first, then pull, restart,
  `test_apis.ps1`, one real question; P0.7's query with it.
- **Tell the lexchat-eval harness owner:**
  - schema v6 on the branch (`delegations[].lost`);
  - `tool_end`'s outcome wording;
  - `lookup_legislation` in `tools[]`;
  - Deep Research headings follow the research type;
  - **new:** a Worker's heavy empty now leaves one `attempt: 1,
    retried: false` record.
- D20 (show a step's outcome in the UI); P5.2 (external); Thomas's review
  document.
- ~~**The Fix Tracker has not been updated this session**~~ **Updated at the
  user's request, twice** (see the addenda below): v22 and v23.

**Machine state:** no uvicorn, no pin file, no worktrees, no replay run. The
dev box is on its normal settings (the seam and probe calls read
`app_settings` and change nothing). The seam draws' answers are in the
scratchpad only.

**Addendum to Session 28 (same day, before the session closed, at the user's
request: "make sure we're not going to lose anything").** Four things the
session knew that the handover did not say:

1. **P4.11 booked** as P4.10's residual: mechanism (b), the upstream idle
   timeout, is a latency cost that P4.10's lever does not touch.
   - The figures: 11 calls; +371 s median per affected turn; the retry
     answered 3 of 22.
   - Not retrying (b) on Worker calls was offered and not chosen.
   - The ledger is now **35 of 52 rows**. Order: the P4.10 redraw, then P3.15,
     then P4.11.
2. **A runaway can end in an answer, and then it is invisible** (a watch item,
   now on P4.10's row).
   - The r3 t3 draw on 2026-09-24 reasoned 62,916 tokens, then answered.
   - Such a call leaves no `empty_completions` record, so `lost` and
     `lostcost` cannot count it.
   - The 32,000-token cap turns it into a lost reply that the Manager
     re-delegates. That is the one quality consequence of the cap to read for
     when (b) is finally drawn on a runaway.
3. **Per-attempt durations**, from the delegation timelines and the seam
   draws:
   - an (a) attempt takes about 310-390 s;
   - a (b) attempt takes about 130-190 s. That is the upstream's own idle
     limit, which our 180 s read timeout cannot shorten.
4. **An unproven hypothesis, not evidence:** why (a) is confined to the
   quick-lookup Worker.
   - Its prompt packs several duties into "2-5 sentences": report the change
     relations first, add a clause on the sibling subsections, say what was
     searched.
   - A model that cannot satisfy all of them in that length may deliberate
     without end.
   - Nothing tests this. The counter-evidence is that effort `medium` and
     `low` still ran away on r2 t1. Do not act on it without a seam test.

**Kept out of the repo on purpose:** the seam draws' answer texts (they echo a
lawyer's terms) stayed in the session scratchpad and are gone with it. Every
number from them is in BASELINE.md, and the commands re-draw them.

**Second addendum to Session 28 (2026-09-25, at the user's request): the Fix
Tracker.**
- **v22** (`5e4d11b`): P4.10 went Verified to In progress, P4.11 was added
  (Verified, P2, a first-pass grade), with a plain-language P4.10 note, P4.5's
  note moved to "Earlier", and a new "Next" paragraph. It read 30 of 52 fixed.
- **v23** (`35c1dc8`): a **new status, Partial**, meaning a fix was attempted
  and deferred, to be revisited later (the user's definition).
  - It sits between In progress and Verified in the bar, legend, filters and
    sort order.
  - **P4.10 is Partial** (user decision): built, with its last check deferred.
  - **Only the user moves a row to Partial.** The ledger has no marker for it,
    so P4.10 stays `[~]` in FIX_PLAN. Step 7 of "How to use this file" now
    records the status mapping.
  - Its fill, validated with the dataviz skill's `validate_palette.js`: mauve
    `#c975b0` (light) and `#c65a9a` (dark), dark count ink `#0a1020`.
    - A violet of the same weight failed: it collapses into the navy Verified
      under protanopia (ΔE 5.4).
    - `#0f1830` ink gave 4.47:1, under the 4.5 floor.
    - The worst adjacent pair is unchanged (green/brown: 16.1 light, 9.2
      dark).
- Both versions were render-checked in light and dark before publishing, at the
  same URL: 30 of 52 fixed, 1 in progress, 1 partial.

## Session 29 — 2026-09-25 — P4.10's (b), closed; the date line

**Asked the user two questions before drawing.**
- **The comparison.** The booked (b) compares medians of three draws a side.
  That can pass only if two of the three lever-off draws run away; at Session
  28's rate both medians are healthy draws and tie. **User decision:**
  alternate lever-off and lever-on draws on one day until each side has a
  runaway, compare the runaways, and require healthy draws to match across
  sides.
- **The stop budget:** about $3 all-in.

**1. Why Session 28 drew nothing: the date line.**
- The first lever-off draw of r2 t1 reproduced Session 28's first draw byte
  for byte: 270 tokens, $0.0221, 4 s.
- `--as-sent` built the Worker prompt with `date.today()`. The recorded calls
  carried 23 September (the runs' `started_at`); the pre-flight's draws
  carried 24 September; Session 28's carried 25 September.
- With the date pinned back (a scratch wrapper at first, then the committed
  `--date`), the same payloads ran away again on the same day:
  - 25 September line: 11 of 11 draws answered, no reasoning (Session 28's
    ten, plus one);
  - 23 or 24 September line: 12 draws gave 4 runaways, 6 (b) and 2 answers.
- The r3 t3 runaway on the 24 September line reproduced the pre-flight's
  63,111 completion tokens exactly.
- The draws are not fully deterministic: r3 t3 on the 23 September line
  answered twice and timed out once.

**2. The instrument** (`d94867a`):
- `seam_replay worker --as-sent --date recorded` (or `--date YYYY-MM-DD`)
  replaces the date line and nothing else, and prints it. Its payloads are
  byte-identical to the wrapper's for all three payload/date pairs drawn.
- `as_sent_outcome` now uses the product's emptiness test: a capped runaway
  ended in a lone newline, which `chat_loop` counts as a heavy empty and the
  seam had called "answered". An empty draw is no longer graded.
- The help text says the lever-off side is the pre-P4.10 payload, since the
  product's Worker call now carries the cap.
- 3 tests new, 2 extended; each new one fails against the previous
  `seam_replay.py` on a scratch copy. **1875 pass.**

**3. (b) PASSED; P4.10 ticked `[x]`.**
- r2 t1 (23 September line): off 63,168 tokens, 338 s, $0.777, answered
  (2 links, MISSED); on 30,719 tokens, 163 s, $0.381, empty.
- r3 t3 (24 September line): off 63,111 tokens, 342 s, $0.764, answered
  (1 link, DELIVERED); on 30,720 tokens, 167 s, $0.382, empty (a).
- Healthy draws matched across sides on both payloads.
- **The watch item:** both uncapped runaways answered, and both capped ones
  came back empty. In the product that is one attempt, P4.5's label and a
  re-delegation. The two answers lost were one DELIVERED, one MISSED.
- The tracker still shows P4.10 as Partial. Moving it is the user's call.

**4. A P4.11 hint, written on its row.** (b) came only on the date lines that
could run away (6 of 12 against 0 of 11), each at 125-133 s. It may share
(a)'s cause. Not a measurement.

**Spend: $2.40** on 13 seam draws.

**Surprises.**
- The "rate varies by day" was the date line: a two-digit change in a
  25,000-character payload flips a stored payload between answering in 4 s and
  reasoning for six minutes.
- A capped runaway can emit one newline and `finish=stop`, not `length`, so
  P4.10's length-cut warning does not fire for it (correctly: it is empty).

**Hazards met.**
- `date.today()` inside a replayed prompt makes a "faithful" payload
  unfaithful the next day. Any seam that rebuilds a dated prompt has the same
  trap. Only `--as-sent` pins it so far.
- A draw that ends (b) costs $0 but about two minutes. Budget time, not
  money, for them.

## Session 29, continued — 2026-09-25 — P3.15 (NOT HELD from history), closed on the measurement

**The sweep the row asked for first** (user go-ahead: n=3, stop at ~$3).
- `wave4_p315_pre`: p37_6409 and p37_6373, n=3, at `2cb77e3`. $1.83, 30 of
  30 turns ok. Pin, fresh uvicorn, restore and server stop all done.
- The exit-1 set exits 0 on it. `lookup` exited 1 on one finding: a held Act
  "reported absent".

**1. That finding was the grader's** (`d37b517`).
- The answer was right. "This index does not hold this instrument" followed a
  bullet naming SSI 2025/377, under a heading naming the Act. The anaphor rule
  credited it to the slot's instrument, the Act.
- **First cut:** attribute the anaphor to the instrument named last. That
  dropped true anaphors that came after a link to the Act's sections (found by
  listing every sentence the change stopped counting).
- **Second cut:** only subordinate instruments move the referent, and an
  anaphor is never credited to an Act. Regraded over all 51 directories, only
  that verdict moved.
- Also new: `lookup` prints the absent slots by route (delegated / from
  history), the count the row asks for.

**2. The measurement.**
- This sweep: graded from-history slots 2 of 2, so the unfixed product met the
  booked acceptance.
- Pooled over three sweeps: from history 3 of 5, delegated 31 of 31.
- **User decision:** rebook as a seam A/B first.

**3. The seam could not reproduce the miss** (`8aed49c`).
- A from-history turn has no delegation, so the composition seam cannot draw
  it. `manager --first-round` draws the Manager's first round, its tools
  offered:
  - an answer is graded by `lookup`;
  - a delegation prints the numbers its brief names (the drift probe);
  - `--date` pins the Manager's date line too.
- Four miss payloads at 3 draws each, four passes at 1 each, current code,
  recorded date: **0 misses in 16**. The two graded 6409 misses delegated 6
  of 6 times; the 6373 ones answered and passed. $0.26.
- **User decision: close P3.15 on the measurement, with no product change**
  (the P3.1/P3.11 precedent). The code-written footer already states the
  definite line, and the miss narrows a true negative and never invents one.
  **B5 closes: 9 of 14 buckets, 37 of 52 rows.**

**Spend, Session 29: $4.49** ($2.40 P4.10 draws, $1.83 replay, $0.26 Manager
seam).

**Surprises.**
- A booked acceptance can be met by the unfixed product. It happened twice in
  one session (P4.10's medians, P3.15's n=3). A defect with a low base rate
  needs its acceptance checked against a pre-fix draw before the build.
- The live Manager answered two follow-ups from history that the seam, on the
  same bytes and date, delegated 6 of 6 times. The seam leaves out the
  learning-examples injection; whether that is the difference is not shown.

**Hazards met.**
- Python in a bash heredoc ate a backslash again (`split('\')`). Use `Path.name`.
- An anaphor rule has to be checked by listing the sentences it stops
  counting, not only the verdicts that move: the first cut moved one verdict
  correctly and silently stopped counting five true sentences.

## Session 29 — handover for Session 30 (2026-09-25)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 29 commits:
  - `d94867a`: `--as-sent --date`, whitespace is empty;
  - `2cb77e3`: P4.10 accepted (docs);
  - `d37b517`: the `lookup` anaphor fix and the by-route tally;
  - `8aed49c`: `manager --first-round`, with `--date`;
  - this docs commit (P3.15 closed, the handover).
- `main` is untouched at `b2a3fd8`.
- **1881 tests green.**
- Ledger **37 of 52 rows**, **9 of 14 buckets** (B5 closed). In progress:
  P0.4 and P5.2.
- **Not on `main`:** P0.6, P4.6, P3.7, P4.7, P4.5, P4.10 and P3.15 (P3.15
  has no product change: only tooling and docs).

**Next work.**
1. **P4.11** (measure-first). Its row carries this session's hint that (b)
   may be (a)'s deliberation with the upstream going idle. Test that first
   with `seam_replay worker --as-sent --date recorded` on the stored (b)
   Worker payloads (`replay_report lostcost --all-dirs` lists them).
2. Then the rows the open buckets wait on: P3.2 (B6), P3.3 (B11), P3.4 (B9)
   and P4.3 (B8). Read each row in full first.

**Instruments added this session (use them, don't rebuild):**
- `seam_replay worker --as-sent --date recorded|YYYY-MM-DD`: **always pass
  `--date recorded`** when redrawing a stored payload;
- `seam_replay manager --first-round [--date recorded] [--without-fix --rev R]`;
- `replay_report lookup` prints absent slots by route.

**Open with the user (carried forward):**
- **The Fix Tracker has not been updated this session.** P4.10 is `[x]` in
  the ledger but Partial on the tracker (the user's call); P3.15 would become
  Fixed (`fixed: "2026-09-25"`, `ver: "Next release"`) when the user asks.
- Push the two release tags? Deploy by tag? (docs/TODO.md D19)
- Whether P0.6, P4.6, P3.7, P4.7, P4.5, P4.10 and P3.15 go in the next cut:
  v2026.09.3, or v2026.10.1 in October.
- Deploy both cuts to the target: `pg_dump` first, then pull, restart,
  `test_apis.ps1`, one real question; P0.7's query with it.
- Tell the lexchat-eval harness owner:
  - schema v6 on the branch (`delegations[].lost`);
  - `tool_end`'s outcome wording;
  - `lookup_legislation` in `tools[]`;
  - Deep Research headings follow the research type;
  - a Worker's heavy empty leaves one `attempt: 1, retried: false` record.
- D20 (show a step's outcome in the UI); P5.2 (external); Thomas's review
  document.

**Machine state:** no uvicorn (stopped by PID), no pin file (restored), no
worktrees. The dev box is on its normal settings. The seam draws' texts and
the scratch wrapper are in the session scratchpad only; every number from
them is in BASELINE.md, and the commands re-draw them.

**Addendum to Session 29 (same day, at the user's request: "make sure we're
not going to lose any pertinent information", then "update the tracker").**
What the session knew that the handover above did not say:

1. **Which seams pin the date line, and what that means for earlier seam
   work.**
   - `worker --as-sent` and `manager --first-round` take `--date`.
   - `worker --first-round` silently ignored `--date` (its branch returns
     before the flag check). It now refuses it (this commit, with a test).
   - The composition seams (synthesis, worker, manager) already refused it,
     and draw with today's date line.
   - The seam A/Bs of P3.11, P3.13, P4.6 and P4.7 drew both sides on one day,
     so they are not confounded by it.
   - But a seam check of whether a recorded miss *reproduces*, drawn with
     today's date, is not a faithful redraw. The seam-against-live gaps of
     Sessions 19 and 22 may partly be this; that is untested.
   - P3.15's non-reproduction used `--date recorded`, so it is not this.
   - This supersedes "Only `--as-sent` pins it so far" in the first Session 29
     section.
2. **P3.15's drift probe, as far as it went.** Every delegation drawn on the
   before side named only the instrument its recorded turn was about
   (2025/377 on 6409, 2026/170 on 6373). No after side was drawn, because no
   product change was made.
3. **An unread observation, not a finding.** The held-Act slot (6409 export
   t2, 2025 asp 2 named by number) made no claim in 5 of 9 reps across
   `wave4_p37b`, `wave4_p37c` and `wave4_p315_pre` (1, 2 and 2): the Manager
   answered without delegating and said nothing about whether the Act is held.
   The grader allows it (`must_claim` is False for that slot). Nobody has read
   whether those answers were otherwise right.
4. **Machine state.**
   - 51 gitignored replay directories (`wave4_p315_pre` is new).
   - The scratch date wrapper and draw loops are superseded by `--date` and
     are gone with the scratchpad.
   - No uvicorn, no http.server, no pin file.
5. **Fix Tracker v24** was published at the user's request, to the same URL:
   - P4.10 moved from Partial to Fixed (user decision);
   - P3.15 Fixed;
   - both `fixed: "2026-09-25"`, `ver: "Next release"`;
   - 32 of 52 fixed, none Partial;
   - new notes on P4.10's check, the date line and the cost the cap trades;
     on P3.15's closure; and on the grader fix;
   - "Next" reads: P4.11, then P3.2, P3.3, P3.4 and P4.3;
   - render-checked once, in light, before publishing.

## Session 30 — 2026-09-25 — P4.11 (the latency of an upstream idle timeout)

**Free checks before any draw.**
- The records already mix (a) and (b) on identical bytes: 6369 `abb`, 6409
  `bab`, 6348 (`wave3_p311_conv`) `abb`.
- `worker --as-sent` rebuilt the Worker prompt with today's code. Of the 8
  Worker payloads to draw, it rebuilt 1 (6410) to its recorded `sent_chars`.
  The rest were off by 44-570 characters: the prompt changed under them.
- The recorded head's own `get_worker_system_prompt` rebuilt all 8, and
  P4.10's two. Every stored head predates `lookup_legislation`, so the tool
  list differed too.
- None of the 5 Manager (b) calls rebuilds on an existing seam (rounds 1, 1,
  2, 3 and 5).
- OpenRouter serves the model from Vertex and AI Studio (its public
  `/endpoints` listing).

**Asked the user before spending** (all four answered with the
recommendation): build `--at-rev recorded`; leave the Manager calls out; stop
at about $5; test the route only if (b) recurred.

**1. Tooling, each committed before its draws.**
- `1de4419`: `worker --as-sent --at-rev recorded|SHA`, which builds the prompt
  and tools with that revision's modules, as `_synthesis_prompt_at` already
  did. It is refused off `--as-sent` and on both first rounds.
- `866a2b3`: `lostcost` splits the retry yield by site, pooled over tied and
  inferred sites with the inferred share said. After a (b): Worker 1 in 14,
  Manager 2 in 8.
- `400d486`: `--provider SLUG` (OpenRouter's `provider.order`, no fallback).
  Every draw now prints the provider that served it.
- 9 tests. Each failed against the previous file on a scratch copy, or, for a
  refusal, with that refusal removed.

**2. Step 1: 32 draws, $1.67** (8 payloads, 3 on the recorded date line and 1
on today's).
- Recorded line: 19 (b), 2 (a) and 3 answers in 24. Every payload drew (b) at
  least once, at 123-149 s and $0.
- After a (b), the same bytes drew (b) again 11 times in 11.
- Today's line: 7 of 8 answered or called a tool in 3-8 s.
- The (a) draws came from 6369 and 6409, whose records mixed the two. 6409's
  was the recorded attempt's 62,915 tokens exactly.

**3. Step 2: the route, $1.53.**
- AI Studio drew (b) on both case-law payloads.
- On both steady-(b) legislation payloads (6373 and 6348), AI Studio ran away
  to 62,913 tokens and about 360 s. Vertex timed out at about 125 s on the
  same bytes.
- A draw with no routing field was served by "Google", i.e. Vertex.
- I stopped the driver when its remaining AI Studio draws (likely runaways)
  would have gone past $5. The four draws it cut were redrawn cheaply: 5
  draws, all (b), $0.

**4. User decision: lever (i).** Booked before any code (`d34c48e`):
deterministic unit tests at each seam, no replay and no seam draw, since no
payload changes.

**5. Built and accepted** (this commit).
- `is_idle_timeout` joins `is_heavy_empty` in `should_retry_empty`'s
  Worker-only exception.
- `tests/test_idle_timeout.py`: 9 tests. With `empty_completion.py` reverted,
  6 fail; with only the rule reverted, 5. The 3 guards each fail against an
  over-broad variant.
- P4.10's `[b_idle]` case is reversed; its old form fails against the fix.
- 1898 pass.
- `AUDIT_TRACE.md` and CLAUDE.md say so. No shape change.
- The "1 of 7" in `1de4419`'s help text and test comment corrected to "1 of
  8".

**6. P4.12 booked** (the residual; measure-first): the Manager's (b), and
whether a retry with changed bytes recovers.

**Spend, Session 30: $3.20.** The ~$2 more the user allowed was not used.

**Surprises.**
- (b) is not a flaky upstream: a stored (b) payload came back (b) again 11
  times in 11. One changed prompt line cured 7 of 8.
- The other route did not avoid (b). It turned (b) into (a) on the same bytes,
  which is the best evidence so far that on those payloads (b) is (a)'s
  deliberation, cut short by Vertex's idle limit.
- A stored payload older than the latest prompt change is not redrawn by
  `--as-sent` alone.

**Hazards met.**
- A background driver with a spend guard still overshoots by the draws in
  flight. A runaway-prone payload on a new route is about $0.77 a draw, so
  check the plan against the budget after each surprising draw, not only
  after the run.
- Stopping the driver's task killed its in-flight draws with it. No orphaned
  processes were left, but their outcomes and costs were lost, so they were
  redrawn.

## Session 30 — handover for Session 31 (2026-09-25)

**State.**
- Branch `fix/prepilot-defects`, pushed. Session 30 commits:
  - `1de4419`: `--at-rev`;
  - `866a2b3`: `lostcost` by site;
  - `400d486`: `--provider`;
  - `d34c48e`: the pre-flight and the booked acceptance;
  - this commit: P4.11 built and accepted, P4.12 booked, this log.
- `main` is untouched at `b2a3fd8`.
- **1898 tests green.**
- Ledger **38 of 53 rows** (P4.11 ticked, P4.12 new), **9 of 14 buckets**. In
  progress: P0.4 and P5.2.
- **Not on `main`:** P0.6, P4.6, P3.7, P4.7, P4.5, P4.10, P4.11 (product
  changes) and P3.15 (tooling and docs only).

**Next work.**
1. The rows the four open buckets wait on: P3.2 (B6), P3.3 (B11), P3.4 (B9)
   and P4.3 (B8). Read each row in full first.
2. P4.12, when the user wants it. Start with the Worker half: a seam lever
   for a benign change of bytes on `worker --as-sent`, drawn with `--at-rev
   recorded --date recorded` on the stored (b) payloads. Mind the runaway risk
   (6369, 6409), about $0.77 a draw.

**Instruments added this session (use them, don't rebuild):**
- `seam_replay worker --as-sent --at-rev recorded` (with `--date recorded`).
  **Check the dry run's `sent_chars` against the record before drawing.**
  It cannot restore P3.7's instrument-lookup block, which code appends to
  the brief and the audit does not record: a Worker payload from a head at
  or after `475ef57` whose brief named an instrument by number is not
  faithful even at its head (possibly why `wave4_p37_reach`/p37r_6374 r1 t2
  did not rebuild).
- `seam_replay worker --as-sent --provider google-vertex|google-ai-studio`.
- `replay_report lostcost`: the retry yield by site.

**Open with the user (carried forward):**
- The Fix Tracker has not been updated this session. P4.11 would become
  Fixed (`fixed: "2026-09-25"`, `ver: "Next release"`), and P4.12 is a new
  row. Update it only when asked.
- Push the two release tags? Deploy by tag? (docs/TODO.md D19)
- Whether P0.6, P4.6, P3.7, P4.7, P4.5, P4.10, P4.11 and P3.15 go in the next
  cut: v2026.09.3, or v2026.10.1 in October.
- Deploy both cuts to the target: `pg_dump` first, then pull, restart,
  `test_apis.ps1`, one real question; P0.7's query with it.
- Tell the lexchat-eval harness owner:
  - schema v6 on the branch (`delegations[].lost`);
  - `tool_end`'s outcome wording;
  - `lookup_legislation` in `tools[]`;
  - Deep Research headings follow the research type;
  - a Worker's heavy empty, **and now its upstream idle timeout**, leaves one
    `attempt: 1, retried: false` record.
- D20 (show a step's outcome in the UI); P5.2 (external); Thomas's review
  document.
- Session 29's unread observation (the held-Act slot made no claim in 5 of 9
  reps) is still unread.

**Machine state:** no uvicorn, no http.server, no pin file, no worktrees, no
seam processes. The dev box is on its normal settings. The draw drivers, their
logs and the answer texts are in the session scratchpad only. Every number
from them is in BASELINE.md, and the seam commands there re-draw them.

**Addendum to Session 30 (same day, at the user's request: "make sure we're
not going to lose any pertinent information", then "update the tracker").**
What the session knew that the handover above did not say:

1. **The Manager seam's numbers** (now also on P4.12's row).
   `manager --first-round --date recorded` rebuilt the two round-1 (b)
   payloads to:
   - 9,832 characters against a recorded 9,243 (`wave2`/6343 r1 t2);
   - 7,923 against 11,870 (`wave4_p37_reach`/p37r_6374 r1 t2).

   At their heads, as Worker calls, they rebuild to 12,744 (6343) and to
   9,004 with the brief alone or 12,791 with one round (p37r_6374). So
   neither call is placed by a seam.
2. **How far the Worker prompt drifted, per recorded head** (today's code
   against the record):
   - +393 characters at `2d9ae11` and `051472d`;
   - +44 at `8006db9`;
   - +570 at `2545184`;
   - +69 at `8dbae59`;
   - 0 at `b694fac` and `778d30a`.

   **`--without-fix --rev`'s literal swap (`_swap_worker_constant`) closed
   the gap on 6 of the 8 payloads, but not on the two at `8006db9`** (526 short):
   there, P2.4's not-held rule was appended outside the constant. So a
   `--without-fix` A/B whose before-side changed text outside the constant
   compares a partial prompt. `--at-rev` builds the whole prompt.
3. **Per-draw detail behind the BASELINE tables.**
   - Reproductions to the token: 6409's (a) at 62,915 (the recorded attempt
     2); 6410's (b) at 164 (the recorded (b)); 6385 `p24`'s second draw at
     141 (its recorded attempt 1). 6410 answered twice at 537 tokens, then
     timed out.
   - **The 29 (b) draws streamed 265-1,013 reasoning characters, but usage
     billed 0 reasoning tokens** (completion 68-257, `finish=error/None`).
     The 4 (a) draws billed every token as reasoning (57,812-76,656
     characters, `stop/STOP`). So "deliberation cut short" rests on the
     route contrast, not on the usage fields.
   - No rate limit in 43 draws run four at a time.
4. **Unread, not findings.** The quick answers on today's date line (links
   0-1) and 6410's recorded-line answers (2 links) were never graded for
   correctness. Their texts were in the scratchpad only.
5. **The draw driver**, in the scratchpad only; P4.12 will want one:
   - four lanes of two payloads, sequential within a payload;
   - one `seam_replay` subprocess per draw, its output parsed into one
     JSON line;
   - a spend guard checked before each draw, which cannot stop draws
     already in flight;
   - stopping the driver's task kills its in-flight subprocesses, and their
     results are lost.
6. **OpenRouter's routes** are now in the `external-apis` skill (not
   tracked: `.claude/` is ignored):
   - six endpoints: Vertex and AI Studio, each standard, flex and
     priority;
   - Vertex is the default;
   - the tiers are untested.
7. **Fix Tracker v25**, published at the user's request to the same URL:
   - P4.11 Verified to Fixed (`fixed: "2026-09-25"`, `ver: "Next release"`);
   - P4.12 added (Verified, P2);
   - new notes on P4.11's check, the cost accepted, the measuring fix and
     P4.12;
   - "Next" reads P3.2, P3.3, P3.4 and P4.3.

---

## Session 31 — 2026-09-28 — P3.2 (B6, capitulation under challenge): measured, acceptance re-scoped and booked, lever (c) tried on the seam

**Done:**
- **The row's diagnosis corrected, free.** 6406 has 24 messages, so the row's
  "turns 11-24" are MESSAGE numbers: user turns 6-12. The earlier reversal is
  turn 5. Read at source in LEX (`eur/2011/142`): the position AILA defended
  over turns 6-11 is contradicted by Annex I's definition, by Annex XIV Ch I
  Table 1 row 3 and above all by Annex X Ch II s.3(B), so **the reversal moved
  TOWARD the text** and the row's "held with the same citation" would pass a
  wrong answer. Turn 5's challenge was right too (Art 25(4) points to Annex
  XIV Ch V, which lists processed manure and blood products only). The
  lawyer's own complaint (Invariant 6) is that she had to tell it the answer
  and ask it to check again. **This is a reading of the text and is to be
  confirmed by a lawyer.** Same lawyer in 6370, whose feedback says she pushes
  because the bot takes a firm position on a point open to interpretation.
- **The acceptance re-scoped and booked before any product code** (`21ff5dd`,
  user decision): at most one position change in turns 6-12; a change must
  re-retrieve and cite a provision the previous position did not; no claim the
  text contradicts; no agreement opener on a challenge turn; control turn 5
  (the lawyer right) passes; 6345 x3 as the stubbornness guard. Script
  `evidence/scripts/p32_6406.json` (Conversational only; the two Deep Research
  turns replaced by turn 3's question). Budget $15; spent $7.88.
- **Four instruments, committed:**
  - `replay_report openers` (`944f831`): the first sentence of each answer,
    by kind (scoped / bare / praise / affirm / apology / thanks), with
    `--drops`. 42 openers in 1,580 replayed answers, 8 in the 179 pre-pilot
    answers. Read before quoting: no missed concession in the drops;
    `affirm` also catches a plain yes-answer (6409).
  - `tools/provision_hints.py dryrun` (`ae0baab`): what lever (c) would
    fetch. 31 of 180 user turns in 17 sessions name a provision; 29 of 41
    references resolve to one instrument; median 878 characters. **Its first
    draft made one wrong-instrument resolution** (6370: a regulation QUOTING
    another instrument's title); reading every resolution against its
    message found it, and the "of (the)" link rule and the quotation rule came
    from it. It also caught a citation that does not exist (6376's s.36(1)(i);
    the pre-pilot model had silently corrected it to s.36(2)(i)).
  - `replay_report stance` (`21ff5dd`): the booked acceptance as a command.
    Generic code; the patterns name a matter's law, so they live in the new
    gitignored `evidence/rubrics/p32.json`. Checked against a hand read of the
    five stored reps before use.
  - `seam_replay manager --hint` (`42d6210`): lever (c) on the Manager seam,
    and every Manager draw now prints its stance under the rubric.
- **Before-column at HEAD** (`wave4_p32_pre`, head `21ff5dd`, $7.54): the
  script n=3 and 6345 x3. **All six FAIL.** By `stance` the 6406 reps change
  position 1, 2, 0 times; **by the required hand-read 3, 3, 0.** Every other
  exit-1 subcommand exits 0 (`modes halts negatives derivations blanks
  scoperecord nosearch caselaw deadend scripted "lost --require-label"`).
- **Lever (c) tried on the Manager seam, and it does not work** (24 draws,
  $0.34, both sides the same day, on `wave4_p32_pre`'s run files). With the
  decisive passage handed over verbatim: turn 6 still denied 3 of 3 (3 of 3
  without); r3's turn 11 still denied 3 of 3 (its contradicted consequence 2 of
  3 without, 0 of 3 with); **no hinted draw cited the passage, 0 of 12**; r1's
  turn 11 opened with praise 3 of 3 with the hint, 0 of 3 without.

**Surprises / deviations from FIX_PLAN:**
- **The row had the defect backwards.** It treated the final reversal as the
  failure; at source it was the one move toward the text. The stable failure
  across every rep is the position changing three times in seven turns, the
  contradicted consequence, and agreement openers on turns the bot never
  checked. Session 29's lesson held in a new form: the booked acceptance as
  first written would have been PASSED by a stubborn wrong answer, and r3 at
  HEAD is exactly that product.
- **At HEAD the defect has a second face.** The stored reps (heads
  `0884b29`..`2d9ae11`) all flip at turns 11-12, 3 of 5 with no re-retrieval.
  At HEAD, 2 of 3 flip at turn 11 WITH a delegation, and r3 holds the
  contradicted consequence through the last challenge with a real argument
  (the Regulation's parallel wording). Invariant 1 cuts both ways here:
  capitulation and stubbornness are both present in the unfixed product.
- **The model has the text and argues past it.** The decisive passage was in
  the raw retrieval at turn 6 in 5 of 5 stored reps and the summariser dropped
  it in 4 of 5 (a scratch probe, not a committed command: `audit`
  `delegations[].tools[].raw_result` against `final_result`). That pointed at
  retrieval. The seam says otherwise: handed the passage, the Manager ignores
  it (0 of 12), as `wave2` turn 6's Worker did. Retrieval is not the binding
  constraint.
- **False "not held" claims recur**: at HEAD 2 of 3 reps say Annex XIV Ch V
  is not held or cannot be retrieved, and r1 turn 10 says Annex X Ch II is not
  held. LEX holds both, each Annex as ONE provision (89K and 28K characters).
  This is P3.12's shape (a part of a Schedule or Annex asked for by number),
  and it is evidence for that row.
- ~~**LEX's Annex text keeps some Chapter headings and drops others**
  (`CHAPTER V` survives in Annex XIV; Annex X and XIII Ch XI have none), so a
  named Annex chapter cannot always be cut out in code.~~ **RETRACTED in the
  addendum below: every heading is there, run into its title (`CHAPTER
  XIGeneral ...`); the cutter's word-boundary regex missed them.** An
  instrument error, found by the handover audit.
- **The grader under-reads, and the hand-read is load-bearing.** Its misses
  were fixed one pattern at a time, each from a sentence read by hand (bold
  markup, "process it into", conditionals, "cannot be classified as", "not
  held in this index"). What it still misses is an implicit switch: an answer
  that applies the fat-derivative rules to the oil without naming the
  category. That is why r1 grades 1 change by command and 3 by hand.
- **Found while answering the user's question about the "learning" feature,
  NOT booked (user decision pending):** `agent/learning.py`, called from
  `agent_core.py` on EVERY Manager call with no flag, injects up to 3
  highly-rated past answers ("Emulate their style") and 3 critique comments
  from ANY user whose question shares a keyword. The pre-pilot's one rating
  (1 in 181 answers, no comments) is a **5 on 6346's dead-end refusal**, the
  B7 defect P4.1 fixed; the query also pairs a question with ANY later answer
  in its chat; and it puts other users' question text into a lawyer's prompt
  with no drafting-mode exclusion. The dev DB holds no ratings, so no replay
  ever exercised it. Whether the target still holds that row is unknown.

**Every number above is behind a command**, re-run before this entry:
- `replay_report --dir evidence/replay/wave4_p32_pre stance` (exit 1, 6 of
  6), with `--also baseline wave1 wave2 --session 6406 p32_6406` for the
  stored reps (8 of 8);
- `replay_report --dir evidence/replay/baseline openers --all-dirs --export`;
- `python -m tools.provision_hints dryrun`;
- `seam_replay manager --run evidence/replay/wave4_p32_pre/p32_6406_rep{1,3}.json
  --turn {4,5,10} [--hint] --reps 3` (draws are not byte-deterministic);
- `plan_status` counts 53.
The hand-read counts (3, 3, 0) and the "0 of 12 cited" read are from the
answer texts, kept in the session scratchpad only.

**State:** branch `fix/prepilot-defects`, pushed. Session 31 commits:
`944f831`, `ae0baab`, `21ff5dd`, `42d6210`, and this one. `main` untouched at
`b2a3fd8`. **1927 tests green.** Ledger 38 of 53, 9 of 14 buckets, in
progress P0.4 and P5.2. **52 replay directories** (+`wave4_p32_pre`).

**Machine state:** no uvicorn, no http.server, no pin file (`replay restore`
run: model `google/gemini-3.1-pro-preview`, local prompt cache ON,
`research_mode_enabled` ON), no worktrees, no seam processes. The rubric
`evidence/rubrics/p32.json` is local and gitignored: **it is needed to
re-run `stance`**; its note says what it grades. The export transcripts,
the hand-read texts and the seam answers are in the scratchpad only.

**Spend:** $7.54 replay, $0.34 seam draws, one model probe. $7.88 of the
agreed $15.

## Session 31 — handover for Session 32 (2026-09-28)

**P3.2 needs the user's lever decision before any product code.** The
measured options, with what the evidence says about each:
- **(a) A disputing turn must re-delegate before the Manager answers**
  (code). At HEAD, 2 of 3 flips already re-delegated, so this alone would not
  have stopped them; it addresses the stored reps' no-retrieval flips.
- **(b) Strip bare/praise/affirm openers at the answer seam** (code; dry-run
  over every stored answer and read every edit first, as P3.13 did). Cheap
  and deterministic, but cosmetic: it cannot pass the acceptance alone
  (criteria i-iii and v), and must not be sold as the fix.
- **(c) The retrieval hint**: measured, not effective at the Manager seam
  (0 of 12 cited). Not recommended as the lever. Its dry-run tool stays useful
  as an instrument (it finds citations that do not exist).
- **(d) A prompt change**: the finding that the model argues past text it
  has points here. The measured failure is an interpretive point stated as
  settled, then abandoned. That is also P3.3's defect (same lawyer, 6370), and
  the Session 22 risk applies: run the first-delegation drift probe before and
  after, and compare links and citations.
- **(e) Take P3.2 and P3.3 together.** Session 31 took P3.2 alone at the
  user's choice. The evidence now says the lever is P3.3's ("separate
  retrieval from interpretation": say "on one reading" for an interpretive
  point, and cite the text for a retrieved one). Recommended to put to the
  user first.

**Instruments (use, don't rebuild):**
- `replay_report stance [--rubric R] [--also DIR ...] [--session ...]
  [--sentences]`. Hand-read every turn it grades "none" in the window
  (booked). The rubric is gitignored.
- `replay_report openers [--all-dirs] [--export] [--list] [--drops]`.
- `provision_hints dryrun [--session] [--list] [--show]`.
- `seam_replay manager --hint` (composition or `--first-round`).

**Open with the user:**
- **P3.2's lever** (above), and whether to take P3.3 with it.
- **The legal reading behind the rubric**: to be confirmed by a lawyer.
- ~~**The learning injection** (Surprises): book a row or a `docs/TODO.md`
  item?~~ **PARKED by the user (2026-09-28): `docs/TODO.md` D21**, with the
  findings. The user also raised standing instructions per AILA user (a
  "CLAUDE.md per user"): noted as D22, an idea, not scoped.
- **Carried from Session 30:** push the release tags? deploy by tag (D19);
  whether P0.6, P4.6, P3.7, P4.7, P4.5, P4.10, P4.11 and P3.15 go in the next
  cut (v2026.09.3 in September, else v2026.10.1); deploy both cuts to the
  target (`pg_dump` first, then pull, restart, `test_apis.ps1`, one real
  question, P0.7's query); tell the eval-harness owner (schema v6 on the
  branch, `tool_end` outcome wording, `lookup_legislation` in `tools[]`,
  Deep Research headings follow the research type, and the single `attempt:
  1, retried: false` record); P4.12; D20; P5.2; Thomas's document; the unread
  held-Act slot (Session 29) and P4.11's ungraded quick answers.
- The Fix Tracker was not updated this session (P3.2 is still open, so no
  row would move). Update it only when asked.

**Addendum to Session 31 (same day, at the user's request: "make sure we're
not going to lose any pertinent information", then "update the tracker").**
What the session knew that the entry and handover above did not say:

1. **Correction: "P3.2 alone" was the session's default, not a user
   decision.** Of the four decisions put to the user, three had a
   recommendation (the re-scoped acceptance, the Conversational-only script,
   the $15 stop); P3.2-alone-or-with-P3.3 did not. The user replied "go with
   your suggestion", and the session filled the gap with P3.2 alone. The
   handover's "(e) Take P3.2 and P3.3 together" is therefore still fully open.
2. **The pre-pilot transcript itself, hand-read:** the same three changes in
   turns 6-12 as the stored reps (deny at 6-7; the fat-derivative route
   applied to the oil at 8; deny again at 9, opening "You have correctly
   identified"; deny at 10-11; affirm at 12). Its final answer cites Annex X
   Ch II s.3(B), the passage the text turns on.
3. **Where the grader and the hand-read differ at HEAD** (`wave4_p32_pre`),
   so the acceptance run's hand-read knows what to look for:
   - r1 t8 and r2 t8 apply the Annex XIII Ch XI fat-derivative end point to
     the oil without naming the category: an implicit affirm (r2 t8 also
     denies: "both"). The grader reads both as none.
   - r1 t9 agrees CONDITIONALLY ("if it cannot be classified as ...") and
     keeps the denial: deny. Fixed in the rubric (a deny pattern for "cannot
     be classified as"), not by the code.
   - The false "not held" claims: r1 t10 (Annex X Ch II), r2 t5 (Annex XIV
     Ch V), r3 t5 ("unable to retrieve" Annex XIV Ch V). LEX holds both
     Annexes, each as one provision.
4. **A known weakness in booked criterion (ii).** A change must cite "a
   provision the previous position's answer did not"; the comparison is with
   the IMMEDIATELY previous position's answer only. r1 t11 changes citing the
   same Annex XIV table that t6 relied on, and counts as new against t9. Read
   every change's citation by hand in the acceptance run; if the user wants
   it, tighten the criterion to "not cited by any earlier answer in the
   window" BEFORE the after-run, never after it.
5. **Seam detail behind the lever (c) numbers** (answers were scratchpad
   only): the hinted draws were near-identical within a side (temperature 0);
   the hinted t6 draws added an unasked offer to search Scottish guidance;
   r3's hinted t11 draws argued the exclusion backwards (that an explicit
   exclusion from a category shows the excluded thing was never inside it),
   the same inversion `wave2` t11 made. Cost $0.014 a draw.
6. **Budget for the next 6406 run:** `p32_6406` reps took 8.7, 9.5 and 14.3
   minutes and cost $1.51, $1.58 and $2.30; 6345 reps 4.0-6.8 minutes and
   $0.53-0.86. So an n=3 after-column with its guard is about $7.50 and 45
   minutes, run serially.
7. **LEX facts learned** (also added to the `external-apis` skill, which is
   not tracked in git):
   - `/legislation/search` does not find EU measures by number and did not
     return the Scotland Act 1998 by exact title in its top 50; pre-1963 Acts
     have regnal-year ids, so a title-to-id resolver misses them.
     `/legislation/lookup` with `legislation_type: "eur"` returns the title of
     `eur/YEAR/NUMBER` (200) and is the reliable route.
   - An Annex of an EU instrument is ONE provision (`.../annex/XIV`, 89K
     characters for eur/2011/142), like a UK Schedule. **Its Chapter and
     Section headings are all present but run into their titles**
     (`CHAPTER XIGeneral ...`, `Section 3Specific requirements ...`; Annex
     XIV's `CHAPTER V RULES` happens to have a space). **This corrects the
     entry above, and the `ae0baab` commit message**, which said LEX drops
     some Chapter headings: the cutter's `\bCHAPTER\s+XI\b` needed a word
     boundary after the numeral and missed every run-together heading. Found
     by this audit when the claim was re-checked against the fetched text
     before being written into the skill. Fixed in `provision_hints`
     (`_ROMAN_END`) with a test. The dry run now reports 2 chapter cuts (was
     1) and 4 references over the cap (was 5); Annex XIII Ch XI (6406 msg 17)
     cuts to 1,206 characters. The lever (c) A/B is unaffected: its turns 5,
     6 and 11 cut no chapter. **The twentieth instrument trap, and the
     same shape as the sixth (a regex tuned on one rendering).**
   - Annex I definitions render as `‘term’ means ...;`, so a definitions cut
     by quoted term is reliable.
   - EU article uris are `/article/N` for eur/2009/1069 and eur/2011/142.
8. **The rubric exists only on this machine** (`docs/prepilot-fixes/
   evidence/rubrics/p32.json`, gitignored like `replay_set.json`). Without
   it, `stance` exits 2 and the seam prints no stance. Its `_note` states the
   proposition, the provisions it was verified against and the reading to be
   confirmed. Every pattern in it was added from a sentence read by hand; if it
   is lost, rebuild it from the stored runs with `--sentences`, and re-check
   it against the counts above (stored reps 3, 3, 3, 3, 4; HEAD 1, 2, 0 by
   command).
9. **Fix Tracker updated to v26 at the user's request** (below): P3.2 stays
   Verified (open), with its note rewritten; D21 and D22 are TODO items, not
   tracker rows.
10. **User decision (2026-09-28, after the addendum): take P3.2 and P3.3
    TOGETHER** (the handover's recommendation (e)). Session 32 starts there,
    measure-first: the lever is not chosen, and a combined acceptance is booked
    and committed before any product code. **6338 has never been replayed in
    the configuration its lawyer used** (Conversational, legislation and case
    law): `baseline`, `wave1` and `wave2` sent Research mode and legislation
    only, `wave0_conv` sent legislation only (before P0.6). 6370 (Conversational,
    legislation and case law) and 6375 (turn 1 Conversational, turn 2 Deep
    Research, legislation and case law) were replayed as recorded, at heads
    `0884b29`-`2d9ae11` (6375 also at `8006db9`/`051472d`/`4890573`).

---

## Session 32 — 2026-09-28/29 — P3.2 and P3.3 together: measured, the combined acceptance booked (interim entry)

**Interim, written before the lever work so the state survives an interruption; the full
entry and the handover for Session 33 follow at the end of the session.**

- **Decisions (2026-09-28).** The user took P3.2 and P3.3 together, measure-first. At the
  spend gate the user said "go with your suggestions". Two of the four points put to them
  carried a recommendation (the before-column spend: about $6, stop $9, session stop $30;
  6370 at n=3). **Two did not**, and the session filled them with its own recommendation,
  recorded here as the session's, accepted by the user's blanket approval, not as the
  user's own choice (Session 31 addendum item 1): P3.2's criterion (ii) tightened to "a
  provision no earlier answer in the window cited", and a code-emitted line counting
  toward 6375's Scots-law status requirement.
- **Law verified at source, free**: see the P3.3 row. The one new source is ILRA's
  explanatory note (para 10), fetched from LEX's explanatory-note endpoint, which the
  product does not call.
- **Instruments**: `replay_report interpret` and `hedges` (`ad38f2d`); the two decisions
  above (`0bc4f2c`). Tests 1928 -> 1946.
- **Before-column** (`wave4_p33_pre`, head `0bc4f2c`): 9 of 9 FAIL, $6.71 recorded. The
  run stalled overnight in 6375 rep 3's Deep Research turn (last server line 16:42, a
  summarisation call; the machine probably slept, nothing was logged after it). The
  replay process was killed the next morning and the same command resumed, skipping the
  8 finished reps. The stalled attempt's spend (turn 1 about $0.14, part of a Deep
  Research turn) is in no run file.
- **The rubric was extended while the before-column came in**, every change from a
  sentence read by hand, each re-checked against every stored rep and the pre-pilot
  answers (no stored or export grade moved). What changed: wrong-claim phrasings for
  6338 ("provided by", "defined by Schedule 1 to", the 1978 Act), sequencing
  conclusions (including a hedged "must be"), two over-broad exemptions narrowed (a
  "not explicitly" and a "whether" that suppressed real claims), and three 6370
  exemptions (statements about what the text does not say, a restatement of the
  Agriculture Regulations' reg 3(1), and reported judicial statements).
- **Found, not booked:** `negatives` fails 3 turns in 6370, a case-law-only negative with
  no index attribution (P3.7's lookup path runs no `search_legislation`, so only P2.4's
  case-law clause is in the footer). It exits 0 on every other HEAD directory.
- **Machine state:** server stopped, `replay restore` run (local prompt cache ON,
  `research_mode_enabled` ON), no pin file.

---

## Session 32, continued — 2026-09-29 — the levers built and measured; neither row met; six residual rows

**Done:**
- **Lever chosen (user decision):** one prompt clause plus two code lines, seam-tested before
  any paid replay. A fourth lever came out of the seam work and was added by user decision
  (the summariser source rule). All four are on the branch (`42951b4`) and **stay there after
  the after-column (user decision)**, with the residuals booked as rows.
  1. **Prompt:** one clause in the first CRITICAL RULE of the conversational Manager and in
     the quick-lookup Worker's MANDATE (not a new block: Sessions 14 and 22), plus a sentence
     in the Manager's approach step on disputed turns.
  2. **Summariser source rule** (`SUMMARY_SOURCE_RULE` in `summarise_prompt`) and the local
     prompt cache version bumped to v2.
  3. **Code, 6375:** `CASE_LAW_DOCTRINE_SENTENCE` after P2.4's coverage sentence.
  4. **Code, P3.2's register:** `utils/openers.py`, an unscoped agreement formula removed at
     the Manager's answer seam.
- **Instruments, committed:** `replay_report interpret` reads a list item's hedge from its
  lead-in line (`a4bef00`); `replay_report openers --strip` (the strip's dry run);
  `tools/summary_probe` (`count` free, `redraw` and `panel` paid). Tests 1946 -> 1981.
- **After-column** (`wave4_p33_post`, head `42951b4`, 15 reps, $17.17). **Neither row met.**
  P3.3 7 of 9 fail (6338 0 of 3, 6370 0 of 3, 6375 2 of 3); P3.2 0 of 3 by hand; the 6345
  guard holds; the decisiveness guard holds. Both rows carry the numbers. Six residual rows
  booked: **P3.16** (summariser glosses), **P3.17** (a general rule's application provision),
  **P3.18** (Deep Research synthesis), **P4.13** (opener strip coverage), **P4.14** (an
  echoed footer ahead of P1.6's note), **P4.15** (a case-law-only negative). Ledger 38 of 59;
  **B5 reopens as partial** (P4.15), so 8 of 14 buckets.

**Surprises / deviations:**
- **6338's wrong Act was written by the summariser, not by the Worker or the Manager.** The
  Worker never searched for an interpretation Act; its section-search result, summarised by
  the Flash model against the Worker's brief ("determine what interpretation legislation
  applies"), came back with a note naming one. 34 stored summaries, all 6338, five
  directories (`summary_probe count`). The Manager seam could not see it (it replays the
  report), which is why the prompt clause moved 6338 by nothing there.
- **A guard wording that stopped the additions multiplied false negatives.** The first rule
  ("use only the text; if it does not answer, say so") took additions to 0 but "the text does
  not contain" statements about sixfold and collapsed change-record summaries; a second
  ("summarise only what it contains") left 4 of 27 additions; the third ("leave out, without
  commenting") took 0 of 27 with no loss. Read as a band: the same prompt's own draws varied
  by several points on every measure.
- **The rule stopped Acts, not glosses, and a gloss reached the lawyer as a quotation.** In
  `p32_6406` r1 the summary of a section search carried a parenthetical interpretation that is
  in neither Regulation (checked in LEX over every provision), and that turn's answer (run-file turn 6, export turn
  7) told the lawyer the Annex said it. That is P3.16, and it is Invariant 1's worst case.
- **The Worker now retrieves the general rule, but by its definition.** Told not to say a
  general rule applies without retrieving what applies it, it fetched the interpretation Act's
  definitions schedule, not the section that says which Acts it covers. When it also fetched
  the older Order (r1 turn 2) it got the answer fully right at source. P3.17.
- **The hand-read overturned the command in both directions again.** `stance` passed
  `p32_6406` r2, which states the contradicted consequence in wording the rubric does not
  match, and read r1's explicit affirm at turn 7 as "none" (4 changes by hand, 3 by command).
  `interpret` over-counted 6370: a reported judicial statement (the case name sits between
  "Court" and the verb, so the exemption missed it), grounded retrieval with a citation, and
  "under this reading" (a hedge the lexicon lacks). The grader was not changed mid-run; the
  corrections are recorded by hand. Rule applied to both columns for 6370: a conclusion about
  what the Regulations "apply" to (the undefined word) is interpretation; "reg N requires X"
  is retrieval.
- **Two regressions the booking did not predict, both small.** `caselaw` TWO_LINES 2: the
  model echoed a footer, P1.6's link note was appended after it, and the trailing-only echo
  strip missed it (P4.14; possible since P1.6). `modes` 1: a Conversational answer with report
  headings (6375 r2 turn 1), n=1, not booked. `negatives` went from 3 to 5 turns (P4.15, plus
  one `p32_6406` turn that does not name its search terms).
- **The overnight stall.** The before-column's last rep hung in a summarisation call from
  16:42 until the machine woke; the same command resumed and skipped the finished reps.
- **Spend over the cap.** $6.71 before-column (plus the stalled attempt, unrecorded), about
  $2.4 Manager-seam A/B (84 draws), about $0.4 drift probe (48 first-round draws), about $3.5
  of summariser probes including **$1.80 spent by mistake** (a scratch script imported another
  whose module body ran its paid probe at 24 draws a slot), $17.17 after-column. **About
  $30.2 against the agreed $30**; the script's $6.94 against an estimated $5.40 was not
  re-checked before it started.

**Every number above is behind a command, except where marked:**
- `replay_report --dir evidence/replay/wave4_p33_pre interpret` and `... wave4_p33_post
  interpret [--sentences --drops]` (P3.3 grades); `... wave4_p33_post stance` (P3.2);
  `... hedges` on both directories (the guard); the exit-1 set on both.
- `python -m tools.summary_probe count` (34 before, 0 of 42 summarised 6338 results after);
  `summary_probe redraw --dir evidence/replay/wave4_p33_pre --session 6338` and
  `summary_probe panel` reproduce the rule's A/B (paid; the published figures are from the
  session's scratch draws of the same prompts, and are a band).
- `replay_report --dir evidence/replay/baseline openers --all-dirs --export --strip` (46 edits;
  it now reads 1,708 answers with `wave4_p33_post` added, and 8 left as written, the eighth
  being P4.13's gap).
- **Scratch-derived:** the Manager-seam A/B tallies (0 of 15 to 5 of 15 passing draws for
  6370) are `seam_replay manager` draws graded by `interpret_grade` in a scratch script; the
  drift-probe reading is `seam_replay manager --first-round --date recorded` output read by
  hand; the hand-read corrections are in the session scratchpad only (they name matters).
- `plan_status` counts 59.

**State:** branch `fix/prepilot-defects`, pushed; `main` untouched at `b2a3fd8`. Session 32
commits: `ad38f2d`, `0bc4f2c`, `cefb2e2`, `a4bef00`, `42951b4`, and this one. 1981 tests.

**Machine state:** server stopped, `replay restore` run (local prompt cache ON,
`research_mode_enabled` ON), no pin file, no worktrees. **54 replay directories**
(`wave4_p33_pre`, `wave4_p33_post`). Local and gitignored: `evidence/rubrics/p33.json` (now
with `summary_adds` and `self_ids` for 6338), `p32.json`, `replay_set.json`.

---

## Session 32 — handover for Session 33 (2026-09-29)

**Take next: P3.16, measure first.** It is upstream of both open rows: 6338's wrong Act and
6406's fabricated quotation both began in a summary. Start free: a detector over every stored
audit for text in `final_result` that is not in `raw_result` (parenthetical glosses, "by
definition", "which means", a named instrument), every match read. Then iterate the rule with
`summary_probe redraw`/`panel` (paid, about $1 a round), watching the "does not contain" count
as closely as the additions. Remember the cache version when the prompt changes.

**Then:** P3.17 (retrieve a general rule's application provision; drift probe if it is a
prompt change), P3.18 (the same rule in the Deep Research synthesis; `seam_replay synthesis`
first), P4.13 and P4.14 (small code, deterministic), and decide P4.15. Re-run P3.2 + P3.3's
after-column only when those move the seams.

**Instruments (use, don't rebuild):** `replay_report interpret` / `hedges` / `stance` /
`openers --strip`; `tools/summary_probe count|redraw|panel`; `seam_replay manager` (and
`--first-round --date recorded` for the drift probe). The rubrics are gitignored; `interpret`
exits 2 without `p33.json`.

**Known grader gaps, not fixed (to fix BEFORE the next after-column, never during):**
`interpret`'s reported-statement exemption misses "the High Court in <case> confirmed";
"under this reading" is not in `INTERP_HEDGE`; the 6370 rubric misses "becomes development to
which"; `stance`'s rubric misses the contradicted consequence worded as "cannot be processed
under the requirements of Chapter XI". List what each change stops or starts counting.

**Open with the user:**
- The legal readings behind both rubrics: to be confirmed by a lawyer.
- The Fix Tracker was not updated (update only when asked); if asked, P3.2 and P3.3 stay open
  and six rows are new.
- Carried from Session 31: the release tags (D19); which rows go in the next cut
  (v2026.10.1 now); deploying both cuts (`pg_dump` first); telling the eval-harness owner
  (schema v6, `tool_end` wording, `lookup_legislation`, Deep Research headings, the
  `retried: false` record); P4.12; D20; P5.2; Thomas's document; the unread held-Act slot and
  P4.11's ungraded quick answers.
- **New for the deploy:** the local prompt cache version is now v2 on the branch, so every
  cached summary becomes unreachable when this code reaches the target (intended: rows
  written before the source rule may carry additions and are shared across users).

**Addendum to Session 32 (same day, at the user's request: "make sure we're not going to lose
any pertinent information", then "update the tracker").** What the session knew that the entry
and handover above do not say:

1. **A number moved behind a command:** "the pre-pilot answers fail all three" came from a
   scratch conversion of the export. `replay_report --dir <any> interpret --export` now grades
   the export's own answers as pseudo-runs (rep 0) and reproduces it turn for turn (6338 t1-3
   wrong 1/1/2; 6370 t3 the "explicitly state" claim; 6375 both turns unmet). Test added;
   1982 tests.
2. **The three summariser rule wordings, so a later session does not re-try the bad ones**
   (the panel is 24 results from other sessions, 2 draws a side, seed 32; the "current" side is
   the prompt without any rule, and its own numbers moved between runs, which is the band):
   - A: "Use ONLY the legislation text below. Do not add anything that is not in it: no other
     legislation, no definitions and no rules of interpretation from your own knowledge, even
     where the research question asks for them. If the text does not answer part of the
     question, say that it does not." 6338 additions 0 of 27 (0 of 216 at 24 draws a slot);
     panel provisions 253 against 261, characters -7%, "does not contain" 46 against 7;
     change-record summaries collapsed (one from 7 provisions to 0).
   - B: "Summarise only what the text below contains. Do not add any legislation, definition
     or rule of interpretation that is not in it, even where the research question asks for
     one." 4 of 27; panel 321 against 270, -3%, 16 against 8.
   - C (shipped, `SUMMARY_SOURCE_RULE`): B plus ": leave out any part of the question the text
     does not cover, without commenting on it." 0 of 27 (26 of 27 without); panel 275 against
     242, -13%, 11 against 7. `summary_probe redraw` / `panel` compare C against no rule; to
     re-test A or B, edit `SUMMARY_SOURCE_RULE` in a scratch copy.
3. **The Manager-seam A/B, slot by slot** (3 draws a slot, 84 draws, $2.40, same day). The
   "before" side was drawn with `prompts.py` checked out at HEAD through the identical pipeline,
   NOT with `--without-fix`: on the Manager seam `--without-fix` also hands the bare report
   without P3.13's sibling linking, so it changes two things. Per slot, before -> after:
   6370 r1 t3/t5/t6 unhedged 20 -> 7, hedged 1 -> 11, passing draws 0/9 -> 3/9; 6370 r3 t3/t4
   9 -> 4, 0 -> 3, 0/6 -> 2/6; 6338 r1 t1-3 wrong 11 -> 12 (the report already asserts it),
   r2 t3 wrong 6 -> 3 and the required statement 0/3 -> 3/3; 6406 (script turns 4, 5, 7, 10 =
   export 5, 6, 8, 11) stances unchanged (r1 t6 deny 3/3, r3 t11 deny 3/3), control turn's
   openers bare -> scoped; 6345 t4 openers bare/apology/apology -> none/bare/bare.
4. **The drift probe, brief by brief** (`seam_replay manager --first-round --date recorded`,
   8 slots x 3 x 2 sides): every after-side brief names the same instrument or subject as
   before; 6348 names FOISA 3 of 3 (2 of 3 before); 6406 adds the implementing Regulation's
   number to the controlling one's; 6375 adds the Scottish environmental regulations; 6345
   drops the "concessionary travel" steer (its before-column went to that wrong Act).
5. **Observations not booked:**
   - 6345 `wave4_p33_post` r3 turn 4 asked the lawyer to name the Act after a scoped
     negative, rather than naming s.38.
   - 6370 after r2 turn 6 said it could not take a legal position on the interpretation. It
     set out both readings first, so it is not the blanket caveat the guard counts, but it is
     neutrality stated as a refusal; read whether lawyers want that before any row is written.
   - Change-record summaries mis-expand ids: one summary gave the interpretation Act's title
     to a different 2010 ASP number, and a `wave2` 6338 summary gave the inserting 2019 Act a
     2024 year. Both are the summariser adding to what the raw text carried: evidence for
     P3.16.
   - 6375's two passes rest on the code line; the report bodies still discuss the doctrines
     in the inter-governmental context. If the user wants the body itself neutral, that is a
     tighter acceptance, to be booked before a re-run.
   - The 6370 reading behind the rubric (the Regulations' reg 6(4), 6(6) and 7(5) point to
     their applying to proposed development generally, not only to EIA development) is in
     the gitignored rubric's `_note`, and is to be confirmed by a lawyer, like 6406's.
6. **Hazards met this session:** the console is cp1252, so any script printing LEX or answer
   text needs `PYTHONIOENCODING=utf-8`; psycopg2 is not installed (use asyncpg, as
   `seam_replay` does); a Monitor watch expires after 30 minutes (re-arm, or rely on the
   command's own completion notice); a sleeping machine stalls a replay mid-call (kill the
   client and re-run the SAME command: it skips finished reps); `replay run --max-spend`
   counts only the current invocation's spend; `seam_replay --out` is a DIRECTORY of
   `<sid>_t<N>_manager[_first]_rep<k>.md`; `p32_6406` run files number turns by the script
   (script turn k is export turn k+1 from k=3 on); the heredoc backslash trap hit three more
   times (nothing corrupted reached a commit).
7. **What the scratch scripts did, so they can be rebuilt** (the scratchpad goes with the
   session): a seam grader (each `.md` draw through `interpret_grade` and `stance_of`, the
   rubric's turn only); a slot table over two side directories; `panel.sh` / `drift.sh`
   (the slots above through `xargs -P 4`); the opener dry run and the summariser probe,
   both now committed (`openers --strip`, `tools/summary_probe`).
8. **The local rubric `evidence/rubrics/p33.json`** now also carries `summary_adds` and
   `self_ids` for 6338 (read by `summary_probe`). Every pattern in it came from a sentence read
   by hand; if it is lost, rebuild it from `wave4_p33_pre` and `wave4_p33_post` with
   `interpret --sentences --drops` and re-check the counts in the rows.
9. **The `external-apis` skill** (not tracked in git) gained a section on the
   explanatory-note endpoint and the two interpretation regimes the index holds.
10. **Fix Tracker updated to v27 at the user's request** (below).

**Second addendum to Session 32 (2026-09-29, at the user's request: set up the next piece of
work to run as parallel agents in a new session).** **Session 33 runs
`docs/prepilot-fixes/PARALLEL_BATCH_1.md`**, which supersedes "Take next: P3.16" in the handover
above: four agents in git worktrees (A: P4.13 + P4.14; B: the grader gaps; C: P3.16; D: P3.18),
the main session as integrator, one combined after-column put to the user first. Prepared and
verified this session:
- **Four test databases** `lexchat_test_a` .. `_d` (owner `lexuser`); two full suites ran
  concurrently on `_a` and `_b` and passed (1983). `TEST_DATABASE_URL` takes plain
  `postgresql://` (with `+asyncpg` every test errors).
- **`PREPILOT_EVIDENCE`**, honoured by `replay_report`, `seam_sweep`, `summary_probe` and
  `replay_set`, points a worktree at the main checkout's gitignored evidence. Proven from a
  scratch worktree with no `.env`: the graders reproduced the after-column, `summary_probe
  count` found 34, the suite passed on `_c`, and synthesis and Manager seam dry runs built their
  payloads. The worktree was removed; no directory junctions were used (a cleanup could delete
  through one).
- **`replay_report interpret --drafts`** grades `seam_replay` draw files against the rubric; it
  reproduces the Session 32 Manager-seam A/B from the saved draws (6370 0 of 15 to 5 of 15).
- **The Session 32 seam draws are kept** in the gitignored `evidence/seam/s32/` (`manager_ab/`,
  `drift_probe/`; new `.gitignore` line), so they outlive the session scratchpad.
- **Agent B's specifics** (they quote matters) are in the gitignored
  `evidence/rubrics/batch1_B_rubric_gaps.md`.
- **A correction:** the gloss in `wave4_p33_post` p32_6406 r1 and the answer quoting it are the
  SAME turn (run-file turn 6, export turn 7); the entry above and the P3.2/P3.16 rows said
  "turn 6's summary ... turn 7". Fixed in both files.


---

## Session 33 — 2026-09-29 — parallel batch 1: four agents merged (interim entry)

**Done:**
- **Ran `PARALLEL_BATCH_1.md` (user decision):** four background agents, each in a git worktree
  with its own test database (`lexchat_test_a`..`_d`) and `PREPILOT_EVIDENCE` pointing at the
  main checkout's evidence; this session integrated. Step 1's checks all held (head `01b66b0`,
  `main` at `b2a3fd8`, 54 replay directories, both rubrics, four test databases, nothing
  running; baseline suite 1983 on `lexchat_test`).
- **Merged in the order B, A, C, D, each `--no-ff`**, the full suite on `lexchat_test` after each:
  B `dc61bb7` (1984), A `445e655` (2004), C `2f32510` (2018), D `c4a5ded` (2029). For each, the
  integrator read the note and the diff, grepped the diff for instrument ids and matter words
  (the only hit: A's synthetic `uksi/1901/1` "Widget Order 1901" fixture), and re-ran its new
  tests with the product file(s) put back to `01b66b0`: B 1 fails, A 11, C 3, D 8, as each note
  claimed. The notes are committed at `docs/prepilot-fixes/notes/batch1_{A,B,C,D}.md`.
- **Agent B (grader gaps, $0):** five of six closed (one in code, `INTERP_HEDGE` reads "under
  a reading"; four patterns in the gitignored `p32.json`/`p33.json`, backed up first to
  `evidence/rubrics/backup_batch1/`); the sixth left to the hand-read by instruction. The only
  verdict that moved anywhere: `wave4_p33_post` p32_6406 r2, PASS to FAIL by `stance`, which is
  what Session 32's hand-read found. Booked before-columns still fail.
- **Agent A (P4.13 + P4.14, $0): both DONE, deterministic.** Numbers re-run by the integrator:
  `openers --all-dirs --export --strip` 47 edits and 7 left as written (46 and 8 before);
  `python -m tools.footer_echo --dir evidence/replay/wave4_p33_post` 2 two-line answers stored,
  0 after.
- **Agent C (P3.16, $2.905):** `summary_probe glosses`, a free detector: 221 glosses in 3,618
  stored summaries of legislation, 205 real by hand (re-run by the integrator: `python -m
  tools.summary_probe glosses`; `--dir wave4_p33_post --session 6406 6338` gives 2 in 81). A lever,
  `SUMMARY_GLOSS_RULE`, and the local prompt cache to v3 (`9ba4e1e`, separable). Acceptance not
  measured.
- **Agent D (P3.18, $3.93):** the synthesis-prompt rule plus a case-law reach sentence in the
  jurisdiction section; seam alignment assertions 5 of 12 to 0 of 5 (re-counted by the
  integrator from the saved draws). Acceptance not measured.
- **Ledger:** P4.13 and P4.14 ticked; P3.16 and P3.18 `[~]`; P3.2 and P3.3 annotated. 40 of 59
  rows, 8 of 14 buckets (`plan_status`; B6 now waits on P3.2 only).

**Surprises / deviations:**
- **Every worktree was created from `main` (`b2a3fd8`), not from the integrator's HEAD**, despite
  the brief. Each agent noticed and ran `git reset --hard 01b66b0` before any work; the
  integrator confirmed all four contained `01b66b0` before reviewing. For a later batch, tell
  each agent to check its base first.
- **Agent B's first grader-test run went to the default `lexchat_test`** (32 tests, about 1s)
  before it set `TEST_DATABASE_URL`; the integrator's baseline suite on the same database passed
  regardless.
- **The integrator's first revert check was a false pass:** `grep -v` with a regex that did not
  match left the line in place, so the test passed "with the change reverted". Redone with a
  byte-level script that counts the lines it removes (1), after which the test failed. Check that
  a revert removed something before reading its result.
- **The push after each merge was refused by the session's permission classifier**; the branch
  is merged locally and not yet pushed (the user's decision).
- **P4.14's defect is older than Session 32** (`wave0_conv` 6341 r1 t5, the same shape).
- **P3.18's claim starts in the hybrid research Worker**, not the synthesis (11 of 24 stored step
  reports); the synthesis rule filters it for Deep Research only.
- **C's lever narrows some summaries** (6406 r2 t5 8 provisions to 0, panel 6345 t4 17 to 2)
  while the panel's total rises (335 against 253): Invariant 1 is read at the after-column.

**Decisions put to the user (not taken):** whether C's lever and D's lever go into the combined
after-column; whether to book the Worker-side origin of P3.18 as a row; the 28 case-law summaries
applying English authority to Scotland (P3.18 or a new row); the two change-record id
mis-expansions; `wave2_p27` 6341 r2 t2 (a copied footer followed by the model's own paragraph);
Session 32's second 6370 `interpret` over-count (a statement with a retrieved citation read as an
unhedged reading), not in the gaps file.

**Spend so far:** $6.835 (C $2.905, D $3.93; A and B $0). The combined after-column is not yet
approved.

---

## Session 33, continued — 2026-09-29 — the combined after-column

**Done:**
- **Plan and figure put to the user before any spend** (user decision: carry both C's and D's
  levers; about $17-20, cap $22). The branch was pushed first (`2271826`; the user allowed the
  push after the classifier refused it). `main` untouched at `b2a3fd8`.
- **After-column `wave4_b1_post`** at head `2271826`, same shape as `wave4_p33_post`:
  `tools.replay run --session 6338 6370 6375 6345 --reps 3 --max-spend 14` ($9.90), then
  `--script evidence/scripts/p32_6406.json --reps 3 --max-spend 12` ($6.13): **$16.03, 15 reps,
  0 errored turns.** `replay check` first (the pinned model still served), `replay pin`, uvicorn
  fresh (PID 2696), a keep-awake helper holding `ES_SYSTEM_REQUIRED` (no setting changed), no
  commit while it ran; then `replay restore` (cache ON, `research_mode_enabled` ON, no pin file),
  the server stopped by PID, the helper stopped.
- **Graded, every match, drop and stance "none" hand-read** (results on the rows):
  - **P3.18 DONE:** 6375 3 of 3 (no alignment assertion in any rep; the code line on every
    turn; `drgaps` 0).
  - **P3.3 NOT MET, 6 of 9 fail:** 6338 0 of 3, each rep failing only on turn 1's regime (turn 2
    names the 1999 Order in 3 of 3, turn 3 right in 3 of 3, wrong-regime claims 1 against 3 and
    9); 6370 0 of 3 (unhedged readings about 6 against about 7 and about 21); 6375 3 of 3.
  - **P3.2 NOT MET, 0 of 3 by hand:** `stance` passed r1; the hand-read found the contradicted
    consequence at export turn 9. Changes by hand 1, 1, 3; contradicted claim 3 of 3; control
    fails 2 of 3; one bad opener. **6345's guard names s.38 for the first time** (1 of 3).
  - **P3.16 met by hand, not by command:** 1 gloss match on 6406/6338 in 86 summaries, read as
    a note, so 0 real; left `[~]` for the user.
  - **Guards held:** `hedges` 0 hedged retrieval statements in 326, 0 caveats; `caselaw`
    TWO_LINES 0 and `footer_echo` 0 as stored (P4.14 live); `sources_kept` per slot fell in 3 of
    15 slots against the booked before-columns (6 of 15 in Session 32's after-column); exit-1 set
    0 except `negatives` 2 (6370, P4.15; 5 in Session 32), `modes` 3 (6345 r2 turns 2-4, n=1)
    and `commencements` (no graded session in the directory, as before).
- **Ledger:** P3.18 ticked; 41 of 59 rows, 8 of 14 buckets (B11 now partial, waiting on P3.3,
  P3.16, P3.17).

**Surprises / deviations:**
- **6375 moved from 2 of 3 to 3 of 3, and 6338's remaining failure is one turn.** In every 6338
  rep turn 1 says the word is undefined and (r1, r3) points to the rules for Acts of that date
  without naming the Order; turn 2 then names it. The booked criterion is not relaxed.
- **`stance` passed a rep the hand-read fails again**, the other way from Session 32's r2: r1's
  contradicted consequence is worded so no pattern matches. The grader gaps found in this run
  (listed on P3.2 and P3.3) must be closed before the next after-column, never during.
- **A new opener verb:** "You are correct to highlight this" is an unscoped formula the strip
  does not list (P4.13 widened the object, not the verb).
- **The gloss detector's note filter misses "does not contain X; therefore, it does not
  provide Y"**, so its count on this directory is one higher than the hand-read.
- **`summary_probe count --dir` needs a path**, not a directory name (it read 0 results given
  `wave4_b1_post`; 581 given the path). `glosses --dir` takes either.
- **Spend under the figure:** $16.03 against about $17-20. Session total **$22.87** (agents
  $6.835, after-column $16.03) against about $27.

**Every number above is behind a command:** `replay_report --dir evidence/replay/wave4_b1_post
interpret [--session S --sentences --drops]`, `stance`, `hedges`, `openers`, `caselaw`, the
exit-1 set (`halts negatives derivations commencements currency scoperecord nosearch caselaw modes
deadend siblings scripted lookup drgaps blanks "lost --require-label"`); `replay_report --dir
<after> discovery --before evidence/replay/wave4_p33_pre --only 6338 6370 6375` and `--before
wave4_p32_pre --only 6345`; `summary_probe glosses --dir wave4_b1_post [--session 6406 6338]
--list`; `summary_probe count --dir <path>`; `tools.footer_echo --dir <path>`. The hand-read
corrections are in the session scratchpad only (they quote matters).

**State:** branch `fix/prepilot-defects`, pushed; `main` untouched at `b2a3fd8`. Session 33
commits: the four `--no-ff` merges (`dc61bb7`, `445e655`, `2f32510`, `c4a5ded`), `2271826`, and
this one. 2029 tests.

**Machine state:** server stopped, `replay restore` run, no pin file, keep-awake helper stopped.
**55 replay directories** (`wave4_b1_post` new). The four agent worktrees were removed after
their branches were merged (the branches `worktree-agent-*` remain locally).

---

## Session 33 — handover for Session 34 (2026-09-29)

**Take next: the user's decision.** Candidates, cheapest first:
1. **Close the grader gaps this run found** (free; before any further after-column): `stance`
   misses the contradicted consequence in two new wordings (r1 export t9, r2 export t7 of
   `wave4_b1_post` p32_6406); `interpret` reads a negated "do not explicitly state that they
   apply only to" as the contradicted claim, lacks "On your reading" as a hedge, misses "It
   returned decisions such as X, which notes" as a reported statement, and the 6338 rubric misses
   two regimes named side by side; `summary_probe glosses`'s note filter misses "does not
   contain X; therefore". Same method as agent B: before/after over every directory, the booked
   before-columns must still fail.
2. **P4.13's sibling:** add "highlight" (and read the other challenge verbs) to the opener strip;
   dry run over every stored answer, read every new edit.
3. **P3.17** (6338): turn 1 names no regime in 3 of 3; the lever is a retrieval of the general
   rule's application provision (drift probe if it is a prompt change).
4. **P3.2:** 0 of 3 through three sessions of levers. The model has the decisive text and argues
   past it (Session 31); the contradicted consequence recurred in 3 of 3. Whether the next lever
   is code (a disputing turn must re-delegate; a contradiction check against retrieved text) or a
   re-scoped acceptance is the user's call.
5. **P4.15**, a decision (unchanged).

**Decisions open with the user (from the batch notes):** whether to tick P3.16 (met by hand, 1
by command, the one match a note); whether to book the Worker-side origin of P3.18's claim (a
Research-mode answer on a hybrid Worker report); the 28 case-law summaries applying English
authority to Scotland; the two change-record id mis-expansions; `wave2_p27` 6341 r2 t2 (an echo
followed by the model's own paragraph); Session 32's second 6370 over-count (retrieval with a
citation read as a reading).

**Hazards met this session:** every worktree the Agent tool made came up on `main`, not HEAD
(each agent reset to `01b66b0`; tell agents to check first); a `grep -v` revert that removed
nothing gave a false "fails with the change reverted" (count the lines a revert removes); the
push is refused by the permission classifier unless the user allows it; `summary_probe count
--dir` takes a path.

**Carried, open with the user:** the legal readings behind the rubrics (a lawyer to confirm);
release tags and deploy by tag (D19); which rows go in the next cut (v2026.10.1); deploying both
cuts (`pg_dump` first; the local prompt cache is now **v3** on the branch, so every cached
summary becomes unreachable when it reaches the target, intended); telling the eval-harness owner
(schema v6 etc.); P4.12; D20; D21/D22; P5.2; Thomas's document. The Fix Tracker was not updated
(update only when asked; if asked, P4.13, P4.14 and P3.18 are Fixed, P3.16 is the user's call).

**Addendum to Session 33 (same day, at the user's request: the release, then "make sure we're not
going to lose any pertinent information", then "update the tracker").** What happened after the
handover above, and what it changes in it:

1. **Third cut = release `v2026.09.3` (user request).** `fix/prepilot-defects` merged to `main`
   (`1e30774`, `--no-ff`, clean, 2035 tests), then the release commit `a6b4a76` (`VERSION`
   2026.09.3, CHANGELOG *Unreleased* moved into a dated section written for this cut, the cut
   noted in CLAUDE.md), annotated tag `v2026.09.3`, `main` and the tag pushed. The two
   retroactive tags `v2026.09.1` and `v2026.09.2` were pushed too (user confirmed; D19's first
   item closed; `0b9f73b`). **Everything through Session 33 is on `main`**; nothing is "not on
   main" any more. The branch was fast-forwarded to `main` and now carries `VERSION`,
   `CHANGELOG.md` and CLAUDE.md's *Releases* section; FIX_PLAN's deployment note records the
   cut (`1b85ba6`). No client, dependency, config or whitelist change. **Replaces the handover's
   "which rows go in the next cut (v2026.10.1)":** the next cut is `v2026.10.1` (or
   `v2026.09.4` if cut in September) and holds only what is built after `a6b4a76`. **Deploying
   `v2026.09.3` to the target is the user's** (`pg_dump` first, pull, restart, `test_apis.ps1`);
   the local prompt cache moves to v3 there, and the eval-harness owner should be told of
   schema v6. D19's "stamp the version on the audit event" is now unblocked (both lines are v6).
2. **Test count on the branch is 2035** (the branch's 2029 plus `main`'s six versioning tests),
   not the 2029 the entry above gives.
3. **Preserved before the scratchpad goes (all gitignored, main checkout only):**
   - `evidence/rubrics/handread_wave4_b1_post.md`: the integrator's hand-read of the
     after-column, rep by rep and turn by turn, with the sentences that decided each verdict and
     the seven grader gaps. **Start the grader-gap work from its last section.**
   - `evidence/seam/batch1/scratchpad_s33/` (9.4 MB): the whole session scratchpad, including
     agent C's hand codes for the 440 unfiltered gloss matches (`list1.txt` with `codes1-4.txt`,
     the evidence behind "205 real of 221"), agent D's `grade.py`/`origin.py`/`intact.py` and
     `grade_final.txt`, agent B's rubric-edit and revert-proof scripts (`b/`), agent A's opener and
     footer scans, and the integrator's helpers: `keep_awake.py` (holds
     `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` every 60 s; changes no
     setting; stop it by its task), `revert_line.py` (removes marked lines at byte level and
     prints how many it removed: the fix for the false revert check), `turn_lines.py` (per turn:
     doctrine line, scope lines, links), `show_turns.py` (prints chosen run-file turns).
   - Agent draws: `evidence/seam/batch1/{C,D}/`; rubric backups:
     `evidence/rubrics/backup_batch1/`. 55 replay directories.
4. **Fix Tracker v28 published at the user's request** (same URL; source
   `docs/prepilot-fixes/summary-table.html`, byte-identical to the live body before the edit):
   P3.18, P4.13, P4.14 Fixed (`fixed: "2026-09-29"`, `ver: "2026.09.3"`); every former "Next
   release" row now `2026.09.3`; P3.16 In progress (the user's decision on ticking is still
   open); P3.2 and P3.3 stay Verified; a plain-language Session 33 note for Thomas naming no
   lawyer's topic. 36 of 59 fixed, 2 in progress, 17 verified, 4 to be verified. Render-checked
   once (`.playwright-mcp/tracker_v28.png`).
5. **Machine state unchanged:** no server, no pin file, no worktrees (the four
   `worktree-agent-*` branches remain locally; all merged, safe to delete).

**Second addendum to Session 33 (2026-10-01, at the user's request: a prompt to start the next piece of work as a safe multi-agent batch).** **Session 34 runs `docs/prepilot-fixes/PARALLEL_BATCH_2.md`**, which supersedes "Take next: the user's decision" in the handover above. Four agents in git worktrees: A, the grader gaps (the last section of the gitignored `evidence/rubrics/handread_wave4_b1_post.md`); B, the opener strip's verb gap (P4.16, to be booked); C, P3.17 ($3); D, P4.15's options and evidence for P3.2, with no product code. Merge order A, B, C, D. The brief carries batch 1's lessons for every agent (check the worktree base first; set `TEST_DATABASE_URL` before any pytest; prove a revert removed lines). Verified for it on 2026-10-01: head `a449327`, 2035 tests, 41 of 59 rows, 55 replay directories, test databases `_a` to `_d` present, `openers --all-dirs --export --strip` 47 edited and 9 left as written over 1,783 answers.

---

## Session 34 — 2026-10-01 — parallel batch 2: four agents merged (interim entry)

**Done:**
- **Ran `PARALLEL_BATCH_2.md` (user decision, both step-2 questions answered: launch all four;
  tick P3.16 once agent A's note-filter fix is merged).** Step 1's checks all held: head
  `578718f`, pushed, clean; `main` at `a6b4a76`; `plan_status` 41 of 59; 55 replay directories,
  both rubrics; test databases `lexchat_test_a` to `_d`; nothing running, no pin file, no
  worktrees (the four batch-1 `worktree-agent-*` branches remain, merged); baseline suite **2035**
  on `lexchat_test`.
- **Merged in the order A, B, C, D, each `--no-ff`**, the full suite on `lexchat_test` after each:
  A `2b1f7cb` (2037), B `c8a82e2` (2046), C `5b09ac8` (2077), D `5bb29d5` (2077). For each the
  integrator confirmed the branch contains `578718f`, read the note and the diff, grepped the diff
  for instrument ids and matter words (no hits: C's only match is its own test's list of id
  prefixes that the phase must not name), re-ran the new tests with the change reverted, counting
  the lines removed (A: 1 line, the hedge test fails; 2 lines, the gloss test fails; B: 1 line, 5
  fail and 39 pass; C: `prompts.py` back to `578718f`, 18 lines removed and 2 restored, 7 fail and
  24 guards pass; D: a note only), and re-ran a headline number. Notes:
  `docs/prepilot-fixes/notes/batch2_{A,B,C,D}.md`.
- **Agent A (grader gaps, $0): all seven items closed.** Two in code (`INTERP_HEDGE` reads
  "on/under your reading"; the glosses note filter recognises the supplied text before the marker
  and "it" after it), five in the gitignored rubrics (backed up first to
  `evidence/rubrics/backup_batch2/`). The only verdict that moved anywhere: `wave4_b1_post`
  p32_6406 r1, PASS to FAIL by `stance`, the hand-read's verdict. Re-run by the integrator on the
  merged branch: `interpret` `wave4_b1_post` 6 of 9 FAIL (6338 0 of 3, 6370 0 of 3, 6375 3 of 3),
  `wave4_p33_post` 7 of 9, `wave4_p33_pre` 9 of 9; `stance` `wave4_b1_post` p32_6406 0 of 3,
  changes 1, 1, 3; `wave4_p33_post` changes 4, 1, 2; `wave4_p32_pre` 6 of 6 FAIL; `glosses --dir
  wave4_b1_post --session 6406 6338` 0 in 86. **The command now agrees with every recorded
  hand-read verdict on those directories.**
- **Agent B (P4.16, $0): DONE, deterministic.** "highlight" added to the `bare` formula's verbs,
  the only challenge verb missing from the stored first sentences. Re-run by the integrator:
  `openers --all-dirs --export --strip` 48 edited and 8 left as written over 1,783 answers (47
  and 9 before).
- **Agent C (P3.17, $2.11 of $3): the seam located, a prompt lever built; acceptance not
  measured.** At turn 1 the regime is never searched for (9 of 9 stored first delegations). PHASE
  2c in the quick-lookup Worker prompt only; every Manager prompt byte-identical. Recounted by the
  integrator from the saved live reports: turn 1 names the right regime 4 of 5, turn 2 2 of 2,
  live turn-1 Worker costs $0.13-0.19 and 11-15 tool calls; `summary_probe count` over the three
  6338 directories 10, all in `wave4_p33_pre`.
- **Agent D (P4.15 options and P3.2 evidence, $0, a note only).** P4.15: 13 stored turns of the
  shape, 9 failing `negatives` (re-run by the integrator: 3, 5 and 2 failing turns); option (a),
  an attribution sentence in the case-law footer, recommended, not built. P3.2: the decisive
  passage on the 15 contradicted turns was in the raw retrieval on 15, the summaries on 7, a
  Worker report on 1; a must-re-delegate rule would have reached 0 of 15.
- **Ledger:** P4.16 booked in Wave 4 and ticked; P3.16 ticked (user decision); P3.2, P3.3,
  P3.17 and P4.15 annotated; B6's index line names P4.16. **43 of 60 rows, 8 of 14 buckets**
  (`plan_status`).

**Surprises / deviations:**
- **Every worktree again came up on `main` (`a6b4a76`)**, not the integrator's HEAD; every agent
  checked first, as briefed, and reset to `578718f`.
- **The branch push is refused by the permission classifier** after each merge, as in batch 1;
  the merges are local until the user allows the push.
- **FIX_PLAN.md's `**` count was already odd (4161) before this session**: P0.2's row carries a
  literal `` `**Key findings` `` in a code span. Left as it is; the fold script asserts its edits
  add an even number (they add 52).
- **Agent C found the turn-1 regime is never searched for**, not retrieved and dropped, so the
  row's code candidate cannot fire at turn 1; a prompt lever was the only one with a trigger.
- **Agent D corrected the P3.2 premise**: the decisive passage is in the summariser's input on
  every contradicted turn, but in the answering Manager's context on 1 of 15.
- **The integrator's first revert check matched nothing** (an LF anchor against a CRLF file); its
  assertion stopped it before a false pass, and it was redone line by line.
- **Agents A and D overlapped on the rubrics**: D's dry runs read `p33.json` while A edited it;
  D's comparisons are within one pass, so none is affected. C removed and recreated a `revert/`
  directory in the shared session scratchpad; no other file was lost.

**State:** branch `fix/prepilot-defects`, local head after this commit, **not pushed** (the
classifier); `main` untouched at `a6b4a76`. 2077 tests. No replay yet: the after-column is put to
the user with a figure first.

---

## Session 34, continued — 2026-10-01 — the decisions put to the user; the drift probe

**Done:**
- **Step 6 put to the user with a figure before any spend.** The after-column for P3.17's lever
  must carry the whole P3.3 and P3.2 set, because C edited a Worker prompt: 6338, 6370, 6375 and
  6345 x3 plus the `p32_6406` script x3, into a new `wave4_b2_post`, about $17 (`wave4_b1_post`
  was $16.03, plus about $0.10-0.15 a 6338 rep for the lever's extra Worker calls), cap $22.
  **User decisions:** not this session; P4.15 left undecided (neither (a) nor (c) built); draw the
  Manager first-delegation drift probe for P3.17 rather than rest on byte-identity; keep the branch
  local (no push).
- **Manager first-delegation drift probe drawn ($0.3897).** `seam_replay manager --run <slot>
  --turn 1 --first-round --date recorded --reps 3` over Session 32's 8 slots
  (`evidence/seam/s32/drift_probe/after/slots.txt`), the before side from a temporary detached
  worktree at `578718f` (removed after), the after side on the merged branch, both the same day.
  A `--dry-run` on 6338 first: 6,341 characters on both sides. Result: the payload is the same size
  on both sides in 8 of 8 slots; 48 of 48 draws delegated; the numbers each brief names are
  identical on both sides (6406 the same instrument number 3 of 3, the other seven none); no brief
  moved to another instrument. **Limit:** drawn without `--print`, so the brief text was not saved
  and the comparison is by delegation and numbers named, not brief by brief as in Session 32.
  Logs: gitignored `evidence/seam/batch2/integrator/drift/{before,after}/<session>.log`.
- **Cleanup:** the four agent worktrees removed (each clean and merged; the `worktree-agent-*`
  branches remain locally, as do batch 1's four). No server, no pin file, no replay this session.
- **Ledger:** P3.17 annotated with the probe; the recommended-order line moved to "end of
  Session 34" with the user's decisions. 43 of 60 rows, 8 of 14 buckets (`plan_status`).

**Surprises / deviations:**
- **No after-column, so no hand-read file** (`evidence/rubrics/handread_<dir>.md`) this session:
  there was nothing new to hand-read. The graders were re-run over the stored directories instead
  (interim entry above).
- **Spend:** agents $2.11 (C), drift probe $0.3897; **session total $2.50**.

**State:** branch `fix/prepilot-defects`, local head after this commit, **not pushed** (user
decision, after the classifier refused it; Session 34's commits are the four `--no-ff` merges
`2b1f7cb`, `c8a82e2`, `5b09ac8`, `5bb29d5` with their agents' commits, `afa2270` and this one);
`origin/fix/prepilot-defects` is still at `578718f`. `main` untouched at `a6b4a76`. 2077 tests.
The session scratchpad is copied to the gitignored `evidence/seam/batch2/scratchpad_s34/`.

---

## Session 34 — handover for Session 35 (2026-10-01)

**First, check the push.** The branch was left local at the user's decision: if Session 35 needs
it on origin, the user allows the push (branch only, never `main`).

**Take next: the user's decision.** Candidates:
1. **The after-column for P3.17's lever** (`wave4_b2_post`): 6338, 6370, 6375 and 6345 x3 with
   `--max-spend 14`, then `--script evidence/scripts/p32_6406.json --reps 3 --max-spend 12`; about
   $17, cap $22. Follow `PARALLEL_BATCH_1.md` step 6 (`replay check`, `replay pin`, uvicorn fresh,
   keep-awake helper `evidence/seam/batch1/scratchpad_s33/keep_awake.py`, no commit while it runs,
   re-run the SAME command if it stalls, `replay restore`, stop the server by its PID). Grade with
   the batch 2 graders, which now agree with every recorded hand-read verdict; still hand-read every
   `interpret` match and drop and every `stance` "none", and save it as
   `evidence/rubrics/handread_wave4_b2_post.md`. Expect some 6338 turn-1 misses: the live Worker
   named the right regime in 4 of 5 (`notes/batch2_C.md`). If P4.15's option is built first, the
   same column measures it on 6370 at no extra cost.
2. **P4.15:** (a) the footer sentence (recommended by D), (c) the grader correction, both, or
   neither (`notes/batch2_D.md` 1.6-1.7; the wording and its dry run are there). If (a): tests at
   `_case_law_body` proven to fail with the change reverted, and P2.8's round trip extended.
3. **P3.2's lever**, from D's evidence (`notes/batch2_D.md` part 2): the decisive passage is lost
   between retrieval and the answer at two seams (the summariser drops its words in 8 of 15
   contradicted turns, the Worker in 6 of the 7 where the summary kept them); a must-re-delegate
   rule would reach 0 of 15; a code check against retrieved text needs the raw result (median
   about 250K characters) as its reference. No lever is recommended beyond what those numbers
   support.

**Decisions open with the user (new this session):**
- whether to book D's 1.5 (in `legislation_only`, a turn that ran only section searches gets no
  footer: 8 stored turns, one asserting a negative), which is P2.8's deliberate silence;
- whether `wave4_p41_pre` 6346_dr r1 t2 (a negative about a decision's later history in a Deep
  Research synthesis, unattributed) needs more than a footer;
- A's `_plain` gap: a markdown link whose label carries `[...]` (a neutral citation's year) is not
  unwrapped, so rubric gaps written as `[^.]` stop at the URL (fixing it moves sentences in every
  grader);
- C's options: a code lever beside PHASE 2c (a forced "application" section search when a
  retrieved instrument's title marks it as interpretation legislation); the lever's cost (a
  turn-1 Worker 11-15 tool calls, $0.13-0.19, against $0.06-0.14 for the whole recorded turn);
  whether the research Workers get the phase too; the case-law-only conversational Worker also
  carries it (one shared prompt).

**Hazards met this session:** every worktree again came up on `main` (each agent checked and
reset, as briefed); the branch push is refused by the classifier; a byte-level revert anchor
written with LF matched nothing in a CRLF file (assert the anchor count before trusting a revert);
FIX_PLAN.md's `**` count was already odd before this session (P0.2 carries a literal
`` `**Key findings` ``), so check that edits ADD an even number rather than that the file total is
even; batch agents share the session scratchpad (C removed and recreated a `revert/` directory
there), so give each agent its own subdirectory next time; agent D's dry runs read `p33.json`
while agent A was editing it (comparisons within one pass were unaffected).

**Carried, open with the user (unchanged):** deploying `v2026.09.3` to the target (`pg_dump`
first, pull, restart, `test_apis.ps1`; the local prompt cache moves to v3 there, intended);
telling the eval-harness owner about schema v6; D19's remaining items (deploy by tag; stamp the
version on the audit event); the legal readings behind the rubrics (a lawyer to confirm); P4.12,
D20, D21/D22, P5.2, Thomas's document; from batch 1: the research Worker's jurisdiction line as a
row, the 28 case-law summaries applying English authority to Scotland, the two change-record id
mis-expansions, `wave2_p27` 6341 r2 t2. The Fix Tracker was not updated (update only when asked;
if asked: P4.16 Fixed 2026-10-01, P3.16 Fixed 2026-10-01, both "Next release").

**Machine state:** no server, no pin file, no replay run, no worktrees (eight merged
`worktree-agent-*` branches remain locally: batch 1's four and batch 2's four). Test databases
`lexchat_test_a` to `_d` remain.

**Addendum to Session 34 (same day, at the user's request: "help me decide", then "make sure we're
not going to lose any pertinent information", then "update the tracker").** This supersedes
"Take next: the user's decision" in the handover above. **Session 35 does, in this order:**

1. **The branch is pushed** (user decision: the target pulls `main`, so a branch push puts nothing
   on the production server, while leaving eleven commits on one machine risks losing them).
   Check `git status` against `origin/fix/prepilot-defects` first.
2. **Build P4.15's (a) and (c), $0, before any replay** (user decision). (a): the sentence in
   `_case_law_body` as agent D worded it (`notes/batch2_D.md` 1.6: "A search can miss a judgment
   the database holds, so one missing from its results may still exist, in this database or
   elsewhere: that is not proof of absence."), after `CASE_LAW_COVERAGE_SENTENCE`, only when the
   search ran (not on an errored one, as with the doctrine sentence); tests at `_case_law_body`
   proven to fail with the change reverted; P2.8's round trip extended; check it still trips only
   `NEG_BLAMED_INDEX` (`test_case_law_gap.py` pins the detector list). (c): one alternative in
   `NEG_BLAMED_INDEX` for the model's own "a search of <the|this|our> ... <database|index|corpus|
   collection> ... returned <no|zero> <results|judgments|matches|cases>"; D read all 64 sentences
   it newly matches. Re-run D's dry run on the built product (`evidence/seam/batch2/D/
   p415_dryrun.py`) and confirm the same 13 (a) and 9 (c) verdicts move and nothing else.
   **Why both:** (a) is the only option that changes what a lawyer reads, and it covers the 4
   turns outside the 6370 shape, one of them a Deep Research negative about a decision's later
   history (Invariant 1 in its plainest form); (c) corrects the model column, which has under-read
   that sentence form since P2.4, and graders are fixed before an after-column. Cost of (a): about
   160 characters on every case-law footer (204 stored answers would carry it).
3. **Then the after-column `wave4_b2_post`**, about $17, cap $22; **confirm the figure with the
   user before spending** (Session 34's handover gives the commands and the procedure). It
   measures P3.17 and P4.15 (6370 n=3) together and re-measures P3.3 and P3.2 (required: a Worker
   prompt changed). Expect some 6338 turn-1 misses (the live Worker named the right regime 4 of 5).
4. **P3.2 is PARKED** (user decision): no new lever until a lawyer confirms the rubric's reading
   of the regulation. Why: three levers failed; D's numbers rule out the next obvious ones (a
   must-re-delegate rule reaches 0 of 15 contradicted claims; the Manager handed the passage kept
   its position 6 of 6 in Session 31; a check against retrieved text needs matter-specific
   patterns to find the claim). Every lever tested the model's reading of a regulation whose
   ground truth is still "to be confirmed by a lawyer"; if confirmed, the next step may be to
   re-scope the acceptance rather than add plumbing. Asking a lawyer is the user's action, not a
   session's.
5. **P4.17 booked** (user decision, measure-first, not urgent): D's 1.5, a section-search-only
   turn in `legislation_only` gets no footer (8 stored turns, one asserting a negative). 43 of 61
   rows; B5 now waits on P4.15 and P4.17.

**The smaller items, decided the same way:** no separate row for the `wave4_p41_pre` Deep Research
turn ((a) covers it); `_plain`'s nested-bracket gap left alone (a rubric entry works round it, and
fixing it moves sentences in every grader); C's code lever and giving the research Workers PHASE
2c deferred until the after-column shows how often 6338 turn 1 still misses; the phase's 2-3x cost
on such a turn (about $0.15) accepted.

**Preserved before the session ends** (the check the user asked for): the four agent notes are
committed (`notes/batch2_{A,B,C,D}.md`); agents A, C and D's scratch scripts and outputs are in
the gitignored `evidence/seam/batch2/{A,C,D}/` (C's `scripts/` is the only copy of its draw
scripts; D's dry-run scripts are there), and agent B's (`verb_scan.py`, `full_diff.py`,
`show_edit.py`, `revert_plugin.py`) in the scratchpad copy below, with its before output in
`evidence/seam/batch2/B/`; the drift-probe logs in
`evidence/seam/batch2/integrator/drift/`; the whole session scratchpad (agent B's verb scan,
the integrator's fold and revert scripts, the pre-batch grader outputs) re-copied to
`evidence/seam/batch2/scratchpad_s34/` after this addendum; rubric backups in
`evidence/rubrics/backup_batch2/`. The agents' transcripts are not kept; everything they found
is in their notes. FIX_PLAN carries the decisions on P3.2, P3.17, P4.15 and the order line.

**Fix Tracker v29** published at the user's request (same URL; the repo source was byte-identical
to the live body before the edit): P3.16 Fixed and P4.16 added as Fixed (both `fixed:
"2026-10-01"`, `ver: "Next release"`), P4.17 added (Verified, P2), the lede and the In-progress
note updated, a plain-language Session 34 note for Thomas naming no lawyer's topic, and the
"Next" paragraph rewritten. 38 of 61 fixed, 1 in progress, 18 verified, 4 to be verified.
Render-checked once (`.playwright-mcp/tracker_v29.png`; the only console error is a local
favicon 404).

**Second addendum to Session 34 (2026-10-01, at the user's request: a prompt to start the next
piece of work as a safe multi-agent batch).** **Session 35 runs
`docs/prepilot-fixes/PARALLEL_BATCH_3.md`**, which turns the addendum above into a brief:
- four $0 agents in git worktrees:
  - A, P4.15's grader correction (c);
  - B, P4.15's footer sentence (a), with the couplings it must keep (the detector-list test, P2.8's
    carried-line round trip, `test_echoed_footer.py:126`, P4.14's echo strip, `CASE_LAW_CODE`);
  - C, P4.17 measured with options;
  - D, a confirmation pack for a lawyer on the readings behind the P3.2 and P3.3 rubrics (gitignored);
- merge order A, B, C, D;
- then the after-column `wave4_b2_post` (about $17, cap $22, `--max-spend 12` then `10`), with
  the figure confirmed with the user first.

Found while writing it: the `ATTR` default in agent D's `p415_dryrun.py` is an earlier wording
that tripped `NEG_LIMITS` and `NEG_TERMS`. The final sentence reaches the script only through
`P415_ATTR`, so the brief has the build pass it from the built constant. Also recorded there:
P3.3 cannot be ticked even if its three sessions pass, because its booked acceptance includes
P3.2's, which is parked; that goes to the user. New lesson in the brief: agents write scratch
only under `evidence/seam/batch3/<letter>/`, never to the shared session scratchpad, and no agent
edits a rubric in this batch.

---

## Session 35 — 2026-10-01 — parallel batch 3: four agents merged (interim entry)

**Done:**
- **Ran `PARALLEL_BATCH_3.md` (user decision: launch all four as set out).** Step 1's checks all
  held: head `72dc84e`, equal to `origin/fix/prepilot-defects`, clean; `main` at `a6b4a76`;
  `plan_status` 43 of 61; 55 replay directories, the latest `wave4_b1_post`; rubric sha1s
  `e14b762…` (`p32.json`) and `dce6d2f…` (`p33.json`); test databases `lexchat_test_a` to `_d`;
  no python process, no pin file, no worktrees; baseline suite **2077** on `lexchat_test`.
- **Merged in the order A, B, C, D, each `--no-ff`**, the full suite on `lexchat_test` after each
  and the branch pushed after each: A `8fcc2fc` (2090), B `b95de6e` (2093), C `25c8a69` (2093), D
  `c2deeec` (2093). For each the integrator confirmed the branch contains `72dc84e`, read the note
  and the diff, grepped the added lines for instrument ids and matter words (no hits; A's comment
  names session 6370, as the file's other comments name sessions), re-ran the new tests with the
  change reverted on a scratch worktree with a script asserting the anchor count (A: 15 lines
  removed, `replay_report.py` then identical to `72dc84e`, 6 fail; B: the one `tail` line put back,
  11 fail and 72 pass; C and D: notes only), and re-ran a headline number. Notes:
  `docs/prepilot-fixes/notes/batch3_{A,B,C,D}.md`.
- **Agent A (P4.15 (c), $0): MET.** `negatives` re-run with A's grader: `wave4_p33_pre` 0 failing
  (model column 14), `wave4_p33_post` 1 (`p32_6406` r1 t4; model 21), `wave4_b1_post` 0 (model
  19); `wave2_p22_final` byte-identical to the grader at `72dc84e`.
- **Agent B (P4.15 (a), $0): MET.** D's dry run re-run through B's wrapper on B's branch: 204
  answers patched, 6 outputs differ, all `negatives`, exactly 13 verdicts FAIL to PASS on `index`.
- **Step 5, D's dry run on the built product with (a) and (c)** (`run_dryrun.py` from the merged
  tree, `P415_ATTR` from the built constant, D's coverage sentence asserted equal to the
  product's): against the stored grading at `72dc84e`, exactly **13** verdicts FAIL to PASS
  (`wave4_p33_pre` 3, `wave4_p33_post` 4, `wave4_b1_post` 2, `wave2_p24_ab` 2, `wave4_p41_pre` 1,
  `wave4_p46_pre` 1); `negatives` exits 1 to 0 on those directories but `wave4_p33_post`, which
  stays at 1 (`p32_6406` r1 t4, P4.17's shape); the model column moves only in A's four
  directories; against (c) alone, (a) moves only the 3 files holding the 4 turns outside the
  shape. As D's note predicted.
- **Agent C (P4.17, $0, a note only).** Re-run by the integrator (`p417_shape.py`): 88 turns ran a
  lookup or section search and no `search_legislation`; 11 carry no footer, 8 since P3.7;
  `negatives` FAIL on 2 of them. C recommends option (d), a scope line naming the turn's section
  searches, built after (a), and proposes an acceptance; not booked (the user's decision). Found:
  P2.5's currency clause contradicts P3.5's on 27 of 455 stored footers.
- **Agent D (lawyer confirmation pack, $0).** `evidence/lawyer_pack/confirmation_pack.md`: four
  readings, four yes/no questions, 18 links. Integrator checks: every link is a string inside a
  stored tool's `api_calls` (18 of 18, 460 run files walked); the pack shares no 6-word run with
  any lawyer-written field of the transcript export (1,507 user messages, rating comments and
  feedback free text) except 17 instrument titles.
- **Ledger:** P4.15, P4.17, P3.2 and P3.3 annotated (26 `**` added, even). 43 of 61 rows
  (`plan_status`).

**Surprises / deviations:**
- **The pack's folder was not gitignored**, though the brief said it was (`.gitignore` covered
  only `replay/`, `rubrics/`, `seam/` and `replay_set.json`). D left it untracked and reported
  it; the integrator added `docs/prepilot-fixes/evidence/lawyer_pack/` (`b35035b`) before any
  other commit.
- **Agent A could not write outside its worktree** (the harness blocked it), so its scratch was in
  the worktree's own gitignored `evidence/seam/batch3/A/`; the integrator copied it to the main
  checkout before removing the worktree. C did the copy itself; 4 of C's files and 2 of D's were
  still only in the worktrees and were copied too (D's second copy of the pack is byte-identical).
- **Every worktree again came up on `main` (`a6b4a76`)**; every agent checked first, as briefed,
  and reset to `72dc84e` (a `git worktree list` taken minutes after launch already showed them
  there).
- **The integrator's first revert anchor for A matched nothing** (a `$`-anchored grep on CRLF
  lines returned no line numbers); the anchor-count assertion stopped it (it reported the empty
  anchor's count) before any write, and it was redone by line number.
- **A used `[^.\n]` gaps, not the brief's `[^.]`**: stricter (a gap also stops at a line break),
  and the pattern D measured, so the moves are exactly D's.

**State:** branch `fix/prepilot-defects`, pushed after each merge; `main` untouched at `a6b4a76`.
2093 tests. No replay yet: the after-column `wave4_b2_post` is put to the user with a figure first.
Agent worktrees removed; their branches remain locally (merged).

---

## Session 35, continued — 2026-10-01 — the after-column `wave4_b2_post`; P4.15 ticked

**Done:**
- **Step 6 put to the user with the figure before any spend** (about $17, cap $22). The user
  asked for help deciding; the session recommended running now rather than holding for P4.17's
  (d) (no saving: P3.3 needs another column once P3.2 un-parks, and (d) can ride on it; (d) is
  the user's call on P2.8's trade and would add a third change to the column); the user chose to
  run it.
- **Procedure:** `replay check` (pinned `google/gemini-3.1-pro-preview` served, probe $0.0011),
  `replay pin`, uvicorn started fresh from `server_py/` (PID 11228, build
  `v2026.09.3-28-g0527c48`), the keep-awake helper (PID 6760); `replay run --session 6338 6370
  6375 6345 --reps 3 --max-spend 12` **$11.29**, then `--script …/p32_6406.json --reps 3
  --max-spend 10` **$5.70**: **$16.99 recorded**, 15 run files, no stall, no commit while either
  ran. Then `replay restore` (model, summariser, local prompt cache and research mode back as
  saved), both processes stopped by PID, no python process left, port 8000 free, no pin file.
- **Graded**, every `interpret` match and drop and every `stance` "none" read by hand; saved to
  the gitignored `evidence/rubrics/handread_wave4_b2_post.md`:
  - **P4.15 MET and TICKED.** `negatives` 32 turns, 0 failing (6370 n=3: 15, 0, model column
    12). The 3 footer-only credits are case-law misses the absence sentence fits; (c)'s 16 new
    matches in the directory each report what a named search returned.
  - **P3.17 NOT met: 1 of 3 by hand** (command 2 of 3). Turn 1 names the 1999 Order in 3 of 3
    (0 of 3 in `wave4_b1_post`). r3 turn 2 offers the 2010 Act as a reading for the inserted
    section; r2 and r3 turn 3 offer "on one reading, the consultation must precede the laying of
    the draft plan", which the booked criterion fails and the rubric misses. 6338 cost $0.57,
    $0.35, $0.59 a rep (mean $0.50) against $0.34.
  - **P3.3 NOT met: 7 of 9 fail by hand** (6338 1 of 3; 6370 0 of 3, about 15 unhedged readings by
    hand against about 6; 6375 2 of 3, r1's Deep Research synthesis states the doctrines are
    highly persuasive across the UK jurisdictions). Not tickable in any case while P3.2 is parked.
  - **P3.2 (parked, re-measured): 0 of 3 by hand**; changes 2, 3, 3; contradicted consequence 3 of
    3; control fails 2 of 3. 6345 guard holds (re-retrieved 3 of 3, s.38 0 of 3).
  - **Guards:** `hedges` 0 in 333, 0 caveats; exit-1 set 0 except `commencements` (no graded
    session); `caselaw` TWO_LINES 0; `footer_echo` 0; `openers` 4, all scoped; `lost` 3, all
    labelled; `summary_probe count` 0 in 656; `glosses` 0 in 108; `sources_kept` per slot fell in
    3 of 11 (6370 t4-t6) against `wave4_p33_pre`, 0 of 4 for 6345 against `wave4_p32_pre`.
- **Ledger:** P4.15 ticked; P3.17, P3.3, P3.2 and P4.17 annotated; B5's index line marks P4.15
  done; the recommended-order line moved to "end of Session 35". **44 of 61 rows**, 8 of 14
  buckets (`plan_status`). B5 now waits on P4.17 only.

**Surprises / deviations:**
- **The pin file is `server_py/tools/.replay_pin_state.json`** (`STATE_PATH` in
  `tools/replay.py`), not `server_py/.replay_pin_state.json` as `PARALLEL_BATCH_3.md` and earlier
  handovers say. Step 1's "no pin file" check looked in the wrong place; the pin's saved previous
  state (local cache and research mode on) shows no stale pin was active. Check `tools/` next time.
- **PHASE 2c moved turn 1 and opened a new failure at turn 3.** Turn 1 went from 0 of 3 to 3 of 3,
  but a hedged "the consultation must precede" reading appeared in 2 of 3 turn-3 answers; no
  earlier stored rep had it. n=3, so whether the phase caused it is not established.
- **PHASE 2c cost more than estimated:** $0.16 a rep more than `wave4_b1_post` (estimate $0.10-0.15);
  turn 1 alone up to $0.30.
- **All three 6338 reps name a 2024 Act as inserting s.35ZA**, where the rubric's reading and the
  lawyer pack say the 2019 Act; stored change records carry an insertion into s.35ZA by the 2024
  Act. Not resolved; flagged for the pack.
- **6375 r1 regressed** (2 of 3 against 3 of 3): a Deep Research synthesis repeating the
  alignment claim P3.18 targeted.
- **The graders were wrong in both directions again**: `interpret` passed two hedged sequence
  readings and read an agreement as a hedge; `stance` read a negated sentence as affirm.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2093 tests. Machine on its normal settings.

---

## Session 35 — handover for Session 36 (2026-10-01)

**Take next: the user's decision.** Candidates, in the order the session would take them:
1. **Close the four grader gaps** in `handread_wave4_b2_post.md` ("Grader gaps found"), $0, before
   any further after-column: `interpret` 6338's hedged sequence reading and the "overlap" framing;
   `interpret` 6370's "As you suggest" agreement and four firm readings in drops; `stance`'s
   negated affirm and the two missed contradicted consequences. Judge each change by whether its
   verdicts move toward this hand-read (6338 1 of 3, 6370 0 of 3, 6375 2 of 3, P3.2 changes 2, 3,
   3), never by pass rate. A batch-style agent fits (rubric files are the user's to allow).
2. **P4.17's (d)** (`notes/batch3_C.md` section 8): build after (a), which is now in; full clause
   set or bare; instruments by id or citation label; whether to book C's (f4), P2.5's currency
   clause contradicting P3.5's on 27 of 455 stored footers.
3. **P3.17's next step**, from this column: turn 1 is now right 3 of 3; the failures moved to turn 2
   (an alternative regime offered as a reading) and turn 3 (a hedged sequence reading). C's
   deferred code lever and the research Workers' phase were waiting on this result; the cost is
   $0.50 a 6338 rep.
4. **The lawyer pack** (`evidence/lawyer_pack/confirmation_pack.md`): before it is sent, add the
   s.35ZA insertion point as an unclear item (the answers and the change records name a 2024 Act;
   the reading says 2019) and confirm the cover note's promise (D's item 7). Sending it is the
   user's action, and P3.2 un-parks only on an answer.

**Decisions open with the user (new this session):**
- D's pack points: the 6406 animal by-product category (it may re-scope P3.2's contradicted
  list); 6370's reg 2(10); 6375's classification against the rubric; the links' `/id/` form; the
  older-source s.55 link; the cover note's promise.
- C's (f4), P2.5's contradicting currency clause (27 stored footers).
- Whether the hedged sequence reading at 6338 turn 3 (a reading offered beside the right one)
  should fail, as booked, or be re-scoped once a lawyer confirms the reading (the pack asks it).

**Hazards met this session:** the pin file is in `server_py/tools/`, not `server_py/`; a
`$`-anchored grep on CRLF lines finds nothing (the revert script's anchor assertion caught it);
the harness blocked agent A from writing outside its worktree (scratch copied out by the
integrator before the worktree was removed: check each worktree's `evidence/seam/batch3/` before
removing it); the lawyer pack's folder was not gitignored until `b35035b`; every worktree again
came up on `main`.

**Carried, open with the user (unchanged):** deploying `v2026.09.3` to the target (`pg_dump`
first, pull, restart, `test_apis.ps1`; the local prompt cache moves to v3 there, intended);
telling the eval-harness owner about schema v6; D19's remaining items (deploy by tag; stamp the
version on the audit event); P4.12, D20, D21/D22, P5.2, Thomas's document; from batch 1: the
research Worker's jurisdiction line as a row, the 28 case-law summaries applying English
authority to Scotland, the two change-record id mis-expansions, `wave2_p27` 6341 r2 t2; which rows
go in the next cut (`v2026.10.1`: P3.16, P4.16 and now P4.15 are fixed since `v2026.09.3`). The Fix
Tracker was not updated (update only when asked; if asked: P4.15 Fixed 2026-10-01, "Next
release").

**Machine state:** no server, no pin file (`server_py/tools/.replay_pin_state.json` absent), no
replay running, no worktrees (twelve merged `worktree-agent-*` branches and `batch3-B` remain
locally). Test databases `lexchat_test_a` to `_d` remain. 56 replay directories, the latest
`wave4_b2_post`. The session scratchpad is copied to the gitignored
`evidence/seam/batch3/scratchpad_s35/`.
**Addendum to Session 35 (2026-10-01, at the user's request: "make sure we're not going to lose
any pertinent information", then "update the tracker").**
- **CHANGELOG.md's *Unreleased* section filled in.** It still said "Nothing yet" although three
  product changes have landed on the branch since `v2026.09.3` (`git log a6b4a76..HEAD --
  server_py/src client/src`: P4.16 `faf7521`, P3.17's PHASE 2c `6b110f1`, P4.15 (a) `88ca517`);
  Session 34 had not recorded P4.16 either. Now listed, with P3.16's tick (its code is already in
  `v2026.09.3`) and P4.15 (c) as tooling, so the next cut moves them into its dated section.
- **`PARALLEL_BATCH_3.md`'s pin path corrected in place** (`server_py/tools/.replay_pin_state.json`),
  so the next batch brief copied from it does not repeat the wrong check.
- **Fix Tracker v30** published at the user's request (same URL; the repo source was
  byte-identical to the live body before the edit: Artifact read, then a Read of all 1106 lines of
  the saved file): P4.15 Fixed (`fixed: "2026-10-01"`, `ver: "Next release"`, its label no longer
  limited to turns with no legislation search, since the sentence is on every case-law line); the
  lede names three rows waiting for the next release (P3.16, P4.16, P4.15); four plain-language
  Session 35 paragraphs for Thomas naming no lawyer's topic (P4.15 fixed; P3.17 re-run, not yet
  fixed; P3.2 and P3.3 re-checked; questions for a lawyer prepared, P4.17 measured); "Next"
  rewritten. 39 of 61 fixed. Render-checked once (`.playwright-mcp/tracker_v30.png`; the only
  console error is the local favicon 404).
- Preserved: the session scratchpad re-copied to `evidence/seam/batch3/scratchpad_s35/` after this
  addendum (grading outputs in its `grade/`, the run logs, uvicorn logs, the fold, revert, pack
  verification and tracker scripts). Agent notes are committed; agent scratch is in
  `evidence/seam/batch3/{A,B,C,D}/`; the hand-read is `evidence/rubrics/handread_wave4_b2_post.md`;
  the pack is `evidence/lawyer_pack/confirmation_pack.md`.
**Second addendum to Session 35 (2026-10-02, at the user's request: a prompt to start the next
piece of work as a safe multi-agent batch).** Four decisions put to the user first, all answered
as recommended:
1. **P4.17: build agent C's option (d) with the full clause set** (instruments by id, as C's
   prototype and P3.5's clause; confirmable at launch). **Its acceptance is BOOKED** on the row,
   from `notes/batch3_C.md` section 8.
2. **P3.17: measure first, $0** (where the turn-2 alternative regime and the turn-3 hedged
   sequence reading arise; options; nothing built).
3. **The four grader gaps are fixed before any further after-column; one agent may edit the
   gitignored rubrics, with backups first.**
4. **P4.18 booked** (new row, Wave 4): P2.5's currency clause says no change record was consulted
   on a footer whose P3.5 clause says one was (27 of 455 stored footers, `p417_contra.py`);
   deterministic acceptance; fixed in the batch. **B4's index line gains it, so B4 reopens:
   `plan_status` 44 of 62 rows, 7 of 14 buckets.**

**`docs/prepilot-fixes/PARALLEL_BATCH_4.md` written** (the brief for Session 36): four $0 agents
in worktrees (A, the four grader gaps with rubric edits; B, P4.17 (d) plus its grader line; C,
P4.18; D, P3.17 measured with options plus the s.35ZA insertion point, with free read-only LEX
GETs, added to the gitignored pack as an unclear point), merge A, C, B, D; then an after-column
`wave4_b4_post` for P4.17's live item (6370 x3 plus the `p32_6406` script x3, about $8.50, cap
$12), figure confirmed with the user first. New lessons carried into it: the pin file's real path;
the harness may block writes outside a worktree (copy scratch out before removing it); a dry run
must import the built code; check a gitignored folder with `git check-ignore` before writing
matter text into it. The FIX_PLAN recommended-order line's *Take next* now points at the brief.

---

## Session 36 — 2026-10-02 — parallel batch 4: four agents merged (interim entry)

**Done:**
- **Ran `PARALLEL_BATCH_4.md` (user decision: launch all four as set out; B names instruments by
  id).** Step 1's checks all held: head `e5c31ba`, equal to `origin/fix/prepilot-defects`, clean;
  `main` at `a6b4a76`; `plan_status` 44 of 62, 7 of 14 buckets; 56 replay directories, the latest
  `wave4_b2_post`; rubric sha1s `e14b762…` (`p32.json`) and `dce6d2f…` (`p33.json`); test
  databases `lexchat_test_a` to `_d`; no python process, port 8000 free, no pin file in
  `server_py/tools/` (or `server_py/`), no worktrees; baseline suite **2093** on `lexchat_test`.
- **Merged in the order A, C, B, D, each `--no-ff`**, the full suite on `lexchat_test` after each
  and the branch pushed after each: A `308bfed` (2095), C `7b41ead` (2100), B `4002473` (2135), D
  `482b6b1` (2135). For each the integrator confirmed the branch contains `e5c31ba`, read the
  note and the diff, grepped the added lines for instrument ids and the matter words (no hits;
  only synthetic `ssi/1901/*` and `uksi/1902/7`), re-ran the new tests with the change reverted on
  a scratch worktree (anchors taken from the diff's hunks, each asserted once): A 17 lines, the
  file then equal to `e5c31ba`, 2 fail; C 16 lines, equal but for the docstring, 4 fail; B the
  wiring 12 lines (6 fail), the builder 84 lines net (all 35 fail at import), the grader 108 lines
  (3 fail); D a note only. Each agent's full suite re-run on `lexchat_test` (A 2095, C 2098, B
  2128). Notes: `docs/prepilot-fixes/notes/batch4_{A,B,C,D}.md`.
- **Agent A (the four grader gaps, $0): MET.** Re-run by the integrator: `interpret` on
  `wave4_b2_post` gives 6338 r1 PASS, r2 FAIL (t3), r3 FAIL (t2, t3), 6370 0 of 3, 6375 2 of 3;
  `stance` gives `p32_6406` 0 of 3, changes 2, 3, 3, the contradicted consequence on r1 t9, r2 t8
  and t9, r3 t8 and t9; `wave4_b1_post` 6 of 9, `wave4_p33_post` 7 of 9, `wave4_p33_pre` 9 of 9.
  A's before/installed outputs differ in one verdict (6338 r2) and two change counts. Rubrics
  backed up to `evidence/rubrics/backup_batch4/`; now `p32.json` `7927e64…`, `p33.json`
  `7e3091e…`.
- **Agent C (P4.18, $0): MET and TICKED.** Re-run on the merged tree
  (`evidence/seam/batch4/integrator/c/p418_contra_after.py`, C's script with its worktree
  assertion pointed at the main checkout): rebuilt contradictions 61 to 0, spliced stored footers
  28 to 0, both must-be-0 lines 0. The count was 28 of 475, not the row's 27 of 455
  (`wave4_b2_post` added one).
- **Agent B (P4.17 (d), $0): items (1) and (2) MET; (3) waits for the after-column.** Re-run on
  the merged tree (`seam/batch4/B/p417b_dryrun.py` into `dry_merged`): 37 edits on exactly the 37
  turns of the shape; 23 of 484 outputs move, all in batch 3 C's 5.3 table or the new
  `sectionscope` line; exits 17 better, 0 worse; downstream 0 outside the shape; couplings 37 of
  37. `sectionscope` over all 56 stored directories: 37 MISSING, 0 MISATTRIBUTED. On the merged
  tree no section line carries P4.18's contradiction (the one that did now has C's wording).
- **Agent D (P3.17 measured, the s.35ZA point, $0 plus 16 read-only LEX requests): a note
  only.** The turn-3 hedged sequence reading is added by the Manager (4 of 9 answers since P3.3's
  clause; the Worker report neutral 9 of 9), always as "on one reading"; before the clause it was
  an unhedged conclusion 3 of 3. Turn 2's alternative regime first appears in the Manager's
  answer. Recommends option (1), waiting for the lawyer with one supplementary question, and
  booking a new row for the change-record pinpoint loss (`_slim_amendment_results` drops the
  pairing of changed and effecting provisions). **s.35ZA: the 2024 Act inserted the whole section
  (its s.6(2)); the 2019 Act did not.** Re-checked by the integrator from D's recorded responses.
  The pack edit (one 11-line note in Reading 2) applied to the gitignored pack (sha1 `2250272c…`
  to `3fb21af4…`); `verify_pack_links.py` 20 URLs, 0 not found; `verify_pack_quotes.py` output
  identical to the original pack's (17 runs, all instrument titles).
- **Ledger:** P4.18 ticked; P4.17, P3.17, P3.3 and P3.2 annotated; B4's index line marks P4.18
  done; the recommended-order line moved to "Session 36, interim" (26 `**` added, even). **45 of
  62 rows, 8 of 14 buckets** (B4 closed again). CHANGELOG *Unreleased*: P4.17's line, P4.18's
  wording, and A's and B's grader changes as tooling.

**Surprises / deviations:**
- **Every worktree again came up on `main` (`a6b4a76`)**; every agent checked first and reset to
  `e5c31ba`.
- **The harness blocked the Write tool outside every worktree** (all four agents). A and B copied
  their scratch out with `cp`; C and D left it in the worktree; the integrator copied each to
  `evidence/seam/batch4/<L>/` and compared file counts (A 162, B 2,047 plus `__pycache__`, C
  1,940, D 43) before removing the worktrees. D's pack edit was applied by the integrator.
- **C's dry-run module asserts it imports C's own worktree**, so its re-run on the merged tree
  needed a copy with that constant repointed (in `seam/batch4/integrator/c/`); B's scripts import
  from the working directory and ran unchanged.
- **D's LEX requests were POSTs, not the brief's GETs**: the search and lookup endpoints take a
  JSON body by POST (as the product calls them) and write nothing.
- **The hedged sequence reading was not new in `wave4_b2_post`**: two earlier reps offered it and
  their hand-reads graded it clean (no rep verdict moves). The Session 35 entry above, its handover
  and the hand-read said otherwise; recorded on P3.17, and the hand-read file is annotated.
- **The inserting Act was wrong in the record**: the rubric's `_note`, the pack's table and
  question part (2), and the `external-apis` skill say 2019; the LEX change record and the 2024
  Act's own text say 2024. Not corrected yet (the user's decision).

**State:** branch `fix/prepilot-defects` at `482b6b1` plus this commit, pushed; `main` untouched
at `a6b4a76`. 2135 tests. No replay yet: the after-column `wave4_b4_post` is put to the user with
a figure first.

---

## Session 36, continued — 2026-10-02 — the after-column `wave4_b4_post`; P4.17 ticked

**Done:**
- **Four decisions put to the user in one question, all answered as recommended:** run the
  after-column (about $8.50, cap $12); correct the inserting Act to 2024 in all four places; book
  the change-record pinpoint loss as **P3.19 (B3)**; add D's supplementary question to the pack.
- **Procedure:** `replay check` (pinned `google/gemini-3.1-pro-preview` served, probe $0.0010),
  `replay pin` (the pin file at `server_py/tools/.replay_pin_state.json`), uvicorn started fresh
  with PowerShell `Start-Process -PassThru` (PID 17308, build `v2026.09.3-40-g10d7444`), the
  keep-awake helper (PID 17628); `replay run --session 6370 --reps 3 --max-spend 4` **$2.38**, then
  `--script …/p32_6406.json --reps 3 --max-spend 8` **$7.50** (rep 3 alone $3.68): **$9.88
  recorded**, under the $10 stop point; 51 answered turns, no stall (a monitor watched for 15
  minutes without log growth), no commit while either ran. Then `replay restore` (model,
  summariser, local prompt cache and research mode back as saved), both processes stopped by PID;
  no python process, port 8000 free, no pin file.
- **Graded** (`grade_b4.sh` in the session scratchpad: the 16-subcommand exit-1 set, `interpret`,
  `stance`, `hedges`, `openers`, `discovery`, `footer_echo`, `summary_probe count`, and the same
  exit-1 set over `wave4_b2_post` with today's graders), every `interpret` match and drop, every
  `stance` "none" and every negative on a turn of P4.17's shape read by hand; saved to the
  gitignored `evidence/rubrics/handread_wave4_b4_post.md`:
  - **P4.17 MET and TICKED.** `sectionscope`: 4 turns of the shape (all 6370), 4 of 4 carry the
    line, 0 MISSING, 0 MISATTRIBUTED. Every negative there PASSES and is a case-law miss the
    absence sentence attributes; the three "does not state / define / contain" claims match P3.3's
    verified reading. Exit-1 set equal to the before-column except `derivations` 0 to 1, an
    over-read ("applications made under section 33"). B5 closed.
  - **P4.18 live:** 0 of 51 scope lines carry both statements; the new branch did not fire.
  - **P3.3, 6370: 1 of 3 by hand** (r3 passes, the first 6370 rep to pass in any column; command
    0 of 3); unhedged readings about 4 (command 13). Not tickable.
  - **P3.2 (parked): 0 of 3**; changes by hand 1 (3), 5, 1; contradicted consequence 3 of 3;
    control r3 a false "not held", r1 conflicting with r2 on what Annex XIV Chapter V lists.
  - **Guards:** `hedges` 0 in 211, 0 caveats; `caselaw` TWO_LINES 0; `footer_echo` 0; `lost` all
    labelled; `halts` 0; `summary_probe count` 0 in 234; `openers` 8 in 51 (5 scoped, an apology
    on a control turn, one "bare" with a concession tail, one "Yes, exactly." with no delegation);
    `discovery` against `wave4_b2_post`: `sources_kept` per slot fell in 4 of 6 (6370) and 6 of 11
    (`p32_6406`) slots, per-rep totals flat.
- **The inserting-Act corrections** (`fix_2024.py`, each anchor asserted once, each file backed
  up first to `evidence/rubrics/backup_batch4/p33.after_batch4_A.json` and
  `evidence/seam/batch4/integrator/`): the rubric `_note` (grading byte-identical on four
  directories after it); the pack's summary, quoted reading, key, table row (now the 2024 Act's
  s.6(2)) and question part (2), D's note rewritten as a correction note; the `external-apis`
  skill's example. The pack's supplementary question added after Reading 2, and its cover's "How
  to answer" says so. Pack checks: 19 URLs, 0 not found; quotes unchanged (17 titles).
- **Ledger:** P4.17 ticked; P3.19 booked (B3 reopens); P3.3, P3.2 and P3.17 annotated; B5's line
  marks P4.17 done; the recommended-order line moved to "end of Session 36". **46 of 69 rows, 8 of
  14 buckets** (`plan_status`). CHANGELOG *Unreleased*: P4.17's line no longer says its live check
  is to run.

**Surprises / deviations:**
- **Another session committed to this branch while the after-column ran** (four docs-only
  commits, `0d72d7c` to `eeb87f0`, 10:24 to 11:09, pushed): a legal data sources map
  (`docs/LEGAL_DATA_SOURCES.md`, a CLAUDE.md pointer), a fix for a cp1252 byte that had made
  FIX_PLAN.md invalid UTF-8, and **six new rows** (P3.20 to P3.23, P4.19, P5.4). It left P3.19 to
  this session's uncommitted booking. No product code changed, so the after-column measured
  `10d7444` as intended. Found only because `plan_status` printed 69 rows where 63 were expected;
  the order line was corrected before commit. Check `git log` before every fold.
- **The after-column cost $9.88 against $8.50 estimated**: script rep 3 alone $3.68 (b2_post's
  reps $1.44 to $2.38).
- **6370 r3 is the first 6370 rep to pass P3.3's criterion in any column.**
- **The graders were wrong in both directions again**, after agent A's fixes: `derivations` read
  an application "made under section 33" as a derivation claim; `interpret` missed "a third
  reading" and "the alternative reading" as hedges; `stance` missed two affirms and read three
  denies as none.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2135 tests. Machine on its normal settings.

---

## Session 36 — handover for Session 37 (2026-10-02)

**Take next: the user's decision.** Candidates, in the order the session would take them:
1. **P3.19** ($0, deterministic, a batch-sized row): make `_slim_amendment_results` keep each
   relation's changed/effecting pair; measure first over every stored change-record result (how
   many groups lose a pairing that matters; output size per call), as the row says.
2. **Send the lawyer pack** (`evidence/lawyer_pack/confirmation_pack.md`, sha1 recorded in the
   hand-read; four readings, a correction note on s.35ZA, a supplementary question on Reading 2).
   Sending it is the user's action; P3.2 un-parks and P3.17's option (1) resolves only on an answer.
   Confirm the cover note's promise first (batch 3 D's item 7).
3. **The new grader gaps** in `handread_wave4_b4_post.md` before any further after-column:
   `derivations` (an application made under a section); `INTERP_HEDGE` ("third", "alternative"
   reading); 6370's restatement and "does not settle" over-counts (known since b2_post); `stance`'s
   two missed affirms and three denies read as none. Agent A's two open decisions stand: the 6338
   turn-3 pattern reads "must" only (extend to "should precede"?); keep the r2 export t7 implicit
   affirm entry?
4. The six rows another session booked today (P3.20 to P3.23, P4.19, P5.4; see their rows and
   `docs/LEGAL_DATA_SOURCES.md`).

**Decisions open with the user (new this session):**
- Agent A's two grader decisions (above).
- P4.17's line exposes a substitution on p37_6373 (a UK SI searched for the Scottish SI the lawyer
  cited; batch 4 B's note section 4): book or not.
- The control turn's conflict on what Annex XIV Chapter V lists (`wave4_b4_post` r1 against r2),
  unresolved; it bears on P3.2's control criterion.
- Which rows go in the next cut (`v2026.10.1`): P3.16, P4.16, P4.15, P4.18 and P4.17 are fixed
  since `v2026.09.3`.

**Hazards met this session:** the harness blocked the Write tool outside every worktree (copy each
agent's `evidence/seam/batch4/<L>/` out before removing it); batch 4 C's dry-run module asserts its
own worktree path (a repointed copy is in `seam/batch4/integrator/c/`); another session committed
to the branch mid-session (`git log` before a fold; `plan_status` row count as a check); every
worktree again came up on `main`.

**Carried, open with the user (unchanged):** deploying `v2026.09.3` to the target (`pg_dump`
first, pull, restart, `test_apis.ps1`; the local prompt cache moves to v3 there, intended);
telling the eval-harness owner about schema v6; D19's remaining items (deploy by tag; stamp the
version on the audit event); P4.12, D20, D21/D22, P5.2, Thomas's document; from batch 1: the
research Worker's jurisdiction line as a row, the 28 case-law summaries applying English
authority to Scotland, `wave2_p27` 6341 r2 t2; and one of the two "change-record id
mis-expansions" carried from Session 33 is not one (batch 4 D: that summary gave the right year).
The Fix Tracker was not updated (update only when asked; if asked: P4.18 and P4.17 Fixed
2026-10-02, "Next release"; P3.19 and the six new rows added).

**Machine state:** no server, no pin file (`server_py/tools/.replay_pin_state.json` absent), no
replay running, no worktrees (the four `worktree-agent-*` branches of batch 4 remain locally,
merged). Test databases `lexchat_test_a` to `_d` remain. 57 replay directories, the latest
`wave4_b4_post`. The session scratchpad is copied to the gitignored
`evidence/seam/batch4/scratchpad_s36/`.
**Addendum to Session 36 (2026-10-02, at the user's request: "make sure we're not going to lose
any pertinent information", then "update the tracker").**
- Checked: working tree clean and pushed; the session scratchpad's copy in
  `evidence/seam/batch4/scratchpad_s36/` identical to the scratchpad (134 files).
- Two gaps closed. **(1)** The two `/amendment/section/search` traps batch 4 D found (exact
  provision URL only; a relation with a null `changed_provision_url` is unreachable from the
  changed side) added to the `external-apis` skill's endpoint table (the skill is under the
  gitignored `.claude/`, so the edit is local). **(2)** The handover above says the pack's sha1 is
  in the hand-read; it was not. Now recorded there: `confirmation_pack.md` sha1 `10da6f9d…`
  (15,341 bytes), with its earlier states.
- **Fix Tracker v31** published at the user's request (same URL; the repo source was identical to
  the live body before the edit: Artifact read, then a Read of all 1,132 lines of the saved file):
  P4.17 and P4.18 Fixed (`fixed: "2026-10-02"`, `ver: "Next release"`; P4.18 is a new tracker row,
  P3); seven rows added, all Verified: P3.19 (P1), P3.20, P3.21, P3.23 and P4.19 (P2), P5.4 (P3),
  and Thomas's action-6 row "Order case-law results by relevance" is now P3.22 (To be verified to
  Verified, P3 to P2, since the review found every case-law search returned the newest 50, not the
  most relevant). The lede names five rows waiting for the next release; four plain-language
  Session 36 paragraphs for Thomas naming no lawyer's topic; "Next" rewritten. 41 of 68 fixed.
  Render-checked once over a local server (`.playwright-mcp/tracker_v31.png`; the only console
  error is the local favicon 404).
**Second addendum to Session 36 (2026-10-02, at the user's request: "is it worth reviewing the plan
to make sure it's still internally consistent", then a prompt for the next session as a safe
multi-agent batch). This addendum supersedes the handover's "Take next".**
- **A structural probe of FIX_PLAN.md** (read-only, $0; saved as the gitignored
  `evidence/seam/batch4/scratchpad_s36/plan_probe.py`, run from the repo root) at `3ca9edb`: 69 rows,
  46 ticked, and `plan_status`'s counts are right (it reads ticks). But **16 ticked rows are not
  marked `**done**` in the Bucket index** (P1.2, P1.3, P1.6, P2.2, P2.5, P2.7, P3.8, P3.15, P3.16,
  P3.18, P4.10, P4.11, P4.13, P4.14, P4.16, P5.1); **21 rows are named in no index line** (P0.1-P0.7,
  P1.5, P2.6, P3.6, P3.12, P3.14, P3.21, P3.22, P3.23, P4.4, P4.8, P4.9, P4.19, P5.3, P5.4; some on
  purpose); **3 ticked rows depend on open rows** (P3.16 and P3.18 on P3.3, P4.13 on P3.2); 17
  recommended-order lines.
- **Semantic inconsistencies, known from this session:** P3.3's booked 6338 turn-3 criterion fails
  the hedged reading P3.3's own clause produces (batch 4 D), and P3.17 inherits it; P3.2, P3.3 and
  P3.17 all wait on the lawyer pack, stated nowhere in one place; the six rows booked on 2026-10-02
  overlap existing rows with no stated relationship (P3.20 and P5.2; P3.21 and P2.5/P4.18; P3.23 and
  P1.3/P2.2; and P3.12 against P4.17).
- **User decision: review the plan for consistency first, in Session 37, as a $0 parallel batch.**
  `docs/prepilot-fixes/PARALLEL_BATCH_5.md` written: agent A `tools/plan_lint` (the probe as a
  tested tool) and an unapplied mechanical fold; B and C a semantic pass over the 23 open rows
  (split by theme) and the cross-documents (CLAUDE.md, CHANGELOG, the tracker's ROWS, TODO, the
  batch-4 brief), proposing amendments as anchored text or numbered decisions; optional D the
  `wave4_b4_post` grader gaps (the user decides at launch, with batch 4 A's two open decisions).
  Merge A, D, B, C; the integrator applies only mechanical edits and what the user approves. The
  FIX_PLAN recommended-order line's *Take next* now points at it.
- **Fix Tracker v32** at the user's request: the "Next" paragraph and the stamp say the next step is
  a consistency review of the plan; no row changed.

---

## Session 37 — 2026-10-02 — parallel batch 5: the plan reviewed for consistency ($0)

**Done:**
- **Ran `PARALLEL_BATCH_5.md` (user decision at launch: A, B and C as set out, D included; batch 4
  A's decisions (i) extend the 6338 turn-3 pattern to "should precede" / "would need to conclude
  before", (ii) keep the `p32_6406` r2 export t7 implicit-affirm entry).** Step 1's checks all
  held: head `dde8b41`, equal to `origin/fix/prepilot-defects`, clean; `main` at `a6b4a76`;
  `plan_status` 46 of 69, 8 of 14; `plan_probe.py` reproduced the brief's findings exactly (16
  done-mark mismatches, 21 unindexed rows, 3 dependency warnings, 17 order lines); rubric sha1s
  `7927e64…` and `5e5769a…`, pack `10da6f9d…`; 57 replay directories; test databases `_a` to `_d`;
  no pin file, no worktrees, port 8000 free; baseline suite **2135** on `lexchat_test`.
- **Merged in the order A, D, B, C, each `--no-ff`**, the full suite on `lexchat_test` after each
  and the branch pushed after each: A `4444c31` (2160), D `0cddbf0` (2162), B `0b92be6` (2162), C
  `14498ba` (2162). For each the integrator confirmed the branch contains `dde8b41`, read the note
  and the diff, and grepped the added lines for instrument ids and the matter words (session ids
  only; the one instrument id is D's synthetic `ssi/1901/3`). Notes:
  `docs/prepilot-fixes/notes/batch5_{A,B,C,D}.md`.
- **Agent A (`tools/plan_lint`, $0): MET.** Seven checks, one function each (shape, index, done,
  depends, order, bold, encoding), 25 tests; `plan_status` refactored to share its parsing (output
  byte-identical). The integrator's own revert (`scratchpad_s37/a/revert_a.py`: each of the nine
  check functions' bodies replaced by a no-op on a scratch worktree) fails 2, 3, 6, 4, 2, 2, 3, 4
  and 3 tests, A's counts exactly. On the merged tree before any fold: 66 errors (shape 24, index
  21, done 21), 6 warnings, exit 1. **New findings beyond the probe:** 5 done-marks the probe's
  regex could not see (bare entries), and 24 ledger rows with more than three table cells (31
  stray separators, 23 unescaped pipes in code spans), whose excess GitHub drops.
- **Agent D (the `wave4_b4_post` grader gaps, $0): MET but for one byte.** `derivation_claims` no
  longer reads an application made under a section as a derivation claim; `INTERP_HEDGE` reads a
  numbered or contrasted reading as a hedge; the rest are rubric edits (backups in
  `evidence/rubrics/backup_batch5/`; now `p32.json` `31379ecf…`, `p33.json` `0031831b…`).
  Integrator's revert on a scratch worktree (three hunks from the diff, 20 lines): the file then
  equals `dde8b41`'s and exactly the two new tests fail. **Re-run on the merged tree:**
  `derivations` 0 of 51 on `wave4_b4_post`; 6370 r1 FAIL, r2 FAIL, r3 PASS (unhedged 1, 3, 0, the
  hand-read's about 4); `p32_6406` 0 of 3, changes 1, 5, 1, contradicted at t9 in each. No rep
  verdict moved on the other five named directories. **`hedges` is not byte-identical over the 57
  directories:** `wave4_b4_post`'s interpretive hedges per 1,000 words reads 3.2 where it read 3.1
  (the gap-2 fix); every guard column is identical. Decision (i) newly catches 2 sentences, both on
  reps that already fail elsewhere.
- **Agents B and C (semantic review of the 23 open rows and the cross-documents, $0): MET.** Three
  premises spot-checked each against the code, all holding: B on P3.19 (`lex.py:540-557`, the
  effecting list cut at 6 with no count), P3.14 (`get_worker_system_prompt` at `prompts.py:746`, the
  early return at `:755`) and P3.6 (`lookup_legislation` returns `description[:600]`,
  `executor.py:512`); C on P3.23 (`"total": len(entries)`), P4.19 (a bare `client.get` and
  `caselaw.py`'s own `AsyncClient`, neither through `_request_with_retry`) and X4
  (`AUDIT_SCHEMA_VERSION = 6` on `main` and the branch, against CLAUDE.md's "v5"). The integrator
  also counted the LEX endpoints the code calls (six), confirming C's X2.
- **Mechanical amendments** (`fold_mech_s37.py`, `2a870fb`): 28 of the 30 B and C proposed (B M1-M3,
  M5-M8, M10-M13; C M1-M17), each anchor asserted once, 461 lines kept, 44 bold markers added; `plan_lint`
  and `plan_status` unchanged. B's M4 and M9 add build requirements and were put to the user.
- **Twenty-three decisions put to the user in six questions, every one taken as recommended:**
  - A1 every ticked row carries a done mark; A2 a byte fold of the stray pipes; A3 P2.10 and P4.5
    named as entries; A4 ticked-ahead reasons on P3.16, P3.18 and P4.13.
  - B1 P3.3's 6338 turn-3 criterion held until the lawyer answers, with a second supplementary
    question (turn 2's newer Act offered as one reading) added to the pack; on Yes to both, a $0
    re-grade with a narrow "on one/another reading" rubric change (by command and by hand-read
    `wave4_b2_post` 6338 goes 1 to 3 of 3, which meets P3.17's criteria; nothing else moves).
  - B2 the lawyer-pack sentence above the Ledger and in the three rows' Depends on; B3 P0.4 dropped,
    P0.7 widened to the 15 no-reply turns; B4 P3.12 a dependency of P3.2 (criterion (v)); B5 P3.4's
    acceptance widened (a deterministic prompt test, a before-column, reach to the quick-lookup
    Worker); B6 P3.21's measure-first and P5.4 (c)'s probe run together; B's M4 and M9 applied.
  - C1 P5.2 decided (Scottish case law from SCTS, subject to its reply) and ticked; C2 one case-law
    build (P4.19, P3.23, P3.9, then P3.22, with a ground truth booked first); C3 the National
    Archives licence booked as `docs/TODO.md` D23, blocking nothing; C4 P3.22 on B12; C5 P4.8's strip
    to be built now, acceptance "0 in every directory after the build"; C6 and C7 P3.10's and P4.3's
    acceptances to be re-booked before any build; C8 C's placements; C9 CLAUDE.md fixed on the branch.
  - D1 the `hedges` value accepted; D2 enrolling 6370's five hedged drops booked as a grader item
    before the next after-column; D3 and D4 the two extra rubric entries kept.
- **Applied** (`c845052`, `a243de3`): `decisions_s37.py` (27 edits, 42 bold markers added, one 2-line
  paragraph); A's fold, repointed in a copy with the placements added (23 rows placed, 33 done marks,
  66 bold markers); `shape_fold_s37.py` (24 rows, 31 separators to " · ", 23 code-span pipes escaped, the
  row text otherwise unchanged, checked character by character); the top order line. **`plan_lint`
  exits 0 with 0 warnings; `plan_status` 47 of 69 rows, 8 of 14 buckets** (P5.2 ticked; P0.4
  `[-]`, still in the denominator). CLAUDE.md X1-X5, `docs/TODO.md` D19 and D23,
  `docs/LEGAL_DATA_SOURCES.md` X10, and CHANGELOG *Unreleased* (plan_lint and D's grader changes, as
  tooling). Suite 2162.
- **Gitignored evidence:** the lawyer pack's second supplementary question (`10da6f9d…` to
  `d26bb016…`, 15,941 bytes; `verify_pack_quotes.py` output identical to Session 36's, so it quotes
  no lawyer's text; the before copy is in `seam/batch5/integrator/`); the hand-read's gap-2 line
  corrected (D's item 5). Agents' scratch in `evidence/seam/batch5/{A,B,C,D}/` (41, 49, 22 and 572
  files, each identical to its worktree's copy before removal).

**Surprises / deviations:**
- **Every worktree again came up on `main` (`a6b4a76`)**; every agent checked first and reset.
- **The harness let every agent copy its scratch to the main checkout with `cp`** this time.
- **`plan_status` reads the Bucket index, not only the ticks** (agent C): a B-line names the rows a
  bucket waits on, so an open row placed on a closed bucket's line reopens it, and the `*(no
  bucket)*` line is ignored. The brief's "it reads ticks, not the index" (`PARALLEL_BATCH_5.md`
  "Where things stand") is half right; A's fold refuses a placement that moves a bucket.
- **The plan's index named two rows only inside another entry's brackets** (P2.10, P4.5), and the
  probe counted them indexed.
- **SESSION_LOG Session 35 says P3.3 was "7 of 9 fail by hand" on `wave4_b2_post`; it was 6 of 9**
  (its own counts, and `interpret` prints 6 failing of 9; agent B). Corrected on P3.3's row; the log
  above is history and is not edited.
- **History not edited:** `PARALLEL_BATCH_4.md`'s "Open with the user" says three rows wait for the
  cut (five do) and two change-record id mis-expansions (one); recorded here only (agent C, X8, X9).
- **C5's "build the strip now" was not built in this session**: the batch carries no product code.
  It is the second item to take next.
- **The Fix Tracker was not updated** (only when asked). If asked: P5.2 Fixed 2026-10-02 ("Next
  release"; it is a decision, not a product change); P0.4 is not on the tracker; the page's
  "Every Fixed row is merged to main" is false for the five "Next release" rows, and "P5.2 is
  waiting on an external decision" is now stale (agent C, X6, X7).

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2162 tests. Session spend $0.

---

## Session 37 — handover for Session 38 (2026-10-02)

**Take next, in this order:**
1. **P3.19** ($0, deterministic; batch 5 B confirmed the premise and that it is buildable as booked):
   make `_slim_amendment_results` keep each relation's changed/effecting pairing. Over every stored
   change-record call (1,216 responses, 47 directories) 13,523 of 20,991 emitted groups lose the
   pairing and 6,363 cut the effecting list with no count; median output 3,448 characters a call.
   `tests/test_amendment_relations.py` pins today's shape and changes with it; B's
   `evidence/seam/batch5/B/p319_scope.py` already walks the stored responses with the built slimmer.
2. **P4.8's strip** ($0, deterministic, user decision C5): strip the result label at the Manager
   return in `agent_core.py` (never a router), unit test failing with the change reverted; the bar
   is 0 in every replay directory taken after the build.
3. **Send the lawyer pack** (the user's action): `evidence/lawyer_pack/confirmation_pack.md`, sha1
   `d26bb016…`, now with two supplementary questions on Reading 2. Confirm the cover note's promise
   first (batch 3 D's item 7). On an answer: P3.2 un-parks; a Yes to both supplementaries is applied
   as a $0 re-grade of the stored 6338 columns.
4. Then the case-law build (P4.19, P3.23, P3.9; P3.22 measured last, its ground truth booked first),
   or P3.21 with P5.4 (c)'s probe. Rows to re-book before any build: P3.10, P4.3; P3.4 has its new
   acceptance.

**Before the next after-column:** enrol 6370's five hedged readings in the `p33.json` rubric
(decision D2), measured first over every directory.

**Use `python -m tools.plan_lint` after every FIX_PLAN fold**: it exits 1 on a row missing from the
index, a ticked row without a done mark, a stray table pipe, odd bold, or a non-UTF-8 byte. Its order
check warns when the top line's counts lag `plan_status`.

**Decisions open with the user (carried):** which rows go in the next cut (`v2026.10.1`: P3.16,
P4.16, P4.15, P4.18, P4.17, and now P5.2); P4.17's line exposes a substitution on p37_6373 (book or
not); the control turn's conflict on what Annex XIV Chapter V lists (the pack's Reading 1 part (2)
answers it); deploying `v2026.09.3` to the target (`pg_dump` first, pull, restart, `test_apis.ps1`);
telling the eval-harness owner about schema v6; D19 (deploy by tag; stamping the version, now
unblocked); D23 (the National Archives licence); sending SCTS the note (P3.20's prerequisite);
P4.12, D20, D21/D22, Thomas's document; from batch 1, the research Worker's jurisdiction line as a
row, the 28 case-law summaries applying English authority to Scotland, `wave2_p27` 6341 r2 t2.

**Machine state:** no server, no pin file, no replay running, no worktrees (the four batch 5
`worktree-agent-*` branches remain locally, merged). Test databases `lexchat_test_a` to `_d`
remain. 57 replay directories, the latest `wave4_b4_post`. Rubrics `p32.json` `31379ecf…`,
`p33.json` `0031831b…`. The session scratchpad is copied to the gitignored
`evidence/seam/batch5/scratchpad_s37/`.
**Addendum to Session 37 (2026-10-02, at the user's request: "make sure we're not going to lose any
pertinent information", then "update the tracker").**
- Checked: working tree clean and pushed (`65f1bf3`); the session scratchpad's copy in
  `evidence/seam/batch5/scratchpad_s37/` identical to the scratchpad (38 files).
- Two gaps closed in the local-only skills (`.claude/` is gitignored, so these edits are not in
  the repo). **repo-map:** `plan_status` and `plan_lint` added (what each reads, the index-membership
  rule, "run it after every FIX_PLAN fold"), and `lex_probe`'s "(we call 3)" corrected to six of the
  13 endpoints. **external-apis:** `/legislation/section/lookup` marked as called since P3.7 (it said
  "we only ever query-search sections"), with the six-called, seven-unused count.
- **Fix Tracker v33** published at the user's request (same URL; the repo source was identical to
  the live body before the edit: Artifact read, then a Read of all 1,179 lines of the saved file).
  P5.2 Fixed (`fixed: "2026-10-02"`, `ver: "Next release"`; its label now says it is the decision,
  and that the build is P3.20); the lede names six rows waiting for the next release; the Fixed
  status note no longer says every Fixed row is on `main` (C's X6) and the In-progress note no
  longer says P5.2 waits on an external decision (X7; no row is in progress now); three
  plain-language Session 37 paragraphs for Thomas naming no lawyer's topic; "Next" rewritten (P3.19,
  P4.8, the lawyer pack); P0.4 recorded as dropped in the "Not listed" line; the stamp. 42 of 68
  fixed. Script syntax-checked with Node; no render check (data and text only).
**Second addendum to Session 37 (2026-10-05, at the user's request: "tackle things in order of
priority, unless there's dependencies", then "park items with dependencies on the lawyer pack; note
them as blocked, state the reason as part of the description"). This supersedes the Session 38
handover's "Take next".**
- The open P1 rows are P3.2, P3.17 and P3.19 (tracker `ROWS`, against the FIX_PLAN ledger). P3.17
  and P3.2 wait on the lawyer pack (P3.2 also on P3.12, a P2 row, for its criterion (v)); P3.19 waits
  on nothing.
- **P3.2, P3.3 and P3.17 parked as BLOCKED on the lawyer pack** (`blocked_s37.py`, each anchor
  asserted once): a BLOCKED note with the reason at the head of each row, a sentence added to the
  lawyer-pack paragraph above the Ledger, the tracker's Blocked status recorded in "How to use this
  file" step 7, and a new top order line. `plan_lint` 0 errors, 0 warnings; `plan_status` 47 of 69
  rows, 8 of 14 buckets (unchanged: the rows stay `[ ]`).
- **Take next, by severity:** P3.19 (P1, $0); then P3.12 (P2, ahead of other P2 rows because P3.2
  needs it; measure first at $0, its 6335 n=3 replay priced to the user first); then P4.8 (P3, $0);
  then the remaining P2 rows. Sending the pack is the user's action and unblocks all three.
- **Fix Tracker v34** (same URL): a new **Blocked** status, after Verified, with the reason ending
  each row's fix text (P3.2 and P3.17 are P1, P3.3 is P2). Its amber fill was the user's choice
  among three options: about 25 candidates were run through the dataviz validator over all pairs
  (a bar skips empty statuses, so Blocked can sit beside any fill); only an amber clears every pair
  in both themes (a brick red collapses into the In-progress brown under protanopia, ΔE 3.2). Two
  costs accepted and recorded in the page's CSS: the light fill is 2.24:1 on the page (labels, the
  legend and the table carry it, as for To be verified), and the dark fill sits above the dark
  lightness band (L 0.81 against 0.67). Rendered once over a local server
  (`.playwright-mcp/tracker_v34.png`; the only console error is the local favicon 404); the
  "Next" paragraph, a dated note for Thomas and the stamp updated. 42 of 68 fixed, 3 blocked.
**Third addendum to Session 37 (2026-10-05, at the user's request: "analyze [Thomas's] feedback
and determine if we already know about the issues", then "book them, and replan our next work
items according to the severity"). This supersedes the second addendum's "Take next".**
- **Thomas's retest of `v2026.09.3` (30 September, on `glm-5.2:cloud`)** was supplied by the user
  and saved, gitignored, as `evidence/seam/thomas_s37/2026-09-30-evals-developer-report.md`.
  **Five problems he had raised on 23 September had no row: his 23 September report and email
  points never reached this plan** (only his 10 September review was mapped). Each was checked
  against the code at HEAD and the 57 stored replay directories (`thomas_census.py`,
  `thomas_census2.py`, `extent_census.py` beside it), and all five are real:
  - **P3.24 (tracker P1):** "not yet commenced" or "remains in force" read from an absence of
    commencement relations. P2.5's `_currency_asserted` skips negatives by design, so no grader
    can see the first shape ("remains in force" it counts; both phrasings tested). Not yet measured
    on the pinned model; measure first.
  - **P3.25 (P2):** the conversational Worker's prompt forbids `get_legislation_text`, yet the tool
    is offered and the prompt elsewhere relies on its results; 143 of 1,314 answered conversational
    turns call it on the pinned model.
  - **P4.20 (P3):** P3.5's and P2.5's footer clauses name different change-record lists; 109 of 423
    stored footers carrying both name different instruments, 36 more differ only in order. Not
    what P4.18 fixed.
  - **P4.21 (P2):** P3.7's lookup clause says a not-held instrument is "not a sign that the
    citation is wrong", which a lookup cannot establish; 69 stored answers carry it.
  - **P4.22 (P3):** `_TOOL_BLOCK` strips an `[ENABLING POWER]` named inside a sentence; 4 stored
    Worker reports on the pinned model name it inline (one left "an explicit `` block").
  - **P3.26 (P3):** an extent value `_TERRITORY_ALIASES` does not know is dropped under a
    jurisdiction filter, against the function's own rule; latent, 0 of 36,343 stored search rows.
    Filed by him under P3.4; it is P1.1's code, booked in Wave 3 so as not to reopen Wave 1.
  - Already known, evidence added: TODO B6 (his 12 of 12 reproduction, in `docs/TODO.md`), P4.3
    (6354, on its row). P3.3/P3.17, P3.9/P3.22, P3.10, the summary counts and the £ scan were
    already rows or held items; his "fixed since 23 September" agrees with the ledger.
- **Booked** (`thomas_book.py`, then A's fold with six placements: P3.24 and P4.22 on B3, which
  stays partial; the rest on the no-bucket line): six ledger rows, a section "External review —
  Thomas, 30 September 2026" mapping every point, P4.3's evidence, and a new top order line.
  `plan_lint` 0 errors, 0 warnings; `plan_status` **47 of 75 rows, 8 of 14 buckets**.
- **Replanned by severity** (the user's rule; within a severity: a row a higher one needs first,
  then $0 deterministic before a paid replay, outside parties last): **P1: P3.19, then P3.24**
  (measure first). **P2:** P3.12 (P3.2 needs it); P4.21 and P3.25; the case-law build (P4.19, P3.23,
  P3.9, then P3.22); P3.21 with P5.4 (c); P3.4; P3.6; P4.3, P3.10, P4.12; P3.20 last (SCTS).
  **P3:** P4.8, P4.20, P4.22, P3.26, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6. P3.2, P3.3
  and P3.17 stay Blocked on the lawyer pack.
- **Fix Tracker v35:** the six rows (source T, Thomas ref "30 Sep", explained in References), a
  dated note for Thomas, "Next" in severity order, the stamp. 74 tracker rows: 42 Fixed, 26
  Verified, 3 Blocked, 3 To be verified. Script syntax-checked with Node.
- **Lesson, recorded in the new FIX_PLAN section:** an external report that is not saved and
  mapped here in the session that receives it is lost to the plan. Also: `evidence/` itself is
  not gitignored, only its listed subfolders (`git check-ignore` caught `evidence/external/` before
  matter text was written there).
**Fourth addendum to Session 37 (2026-10-05, at the user's request: "provide a prompt to kick off the next piece of work ... a safe, multi-agent approach").** `docs/prepilot-fixes/PARALLEL_BATCH_6.md` written: four $0 agents in git worktrees, taken in the severity order above: A builds P3.19 (P1); B measures P3.24 (P1) with a new `replay_report` detector for negative commencement and currency claims, registered in `test_footer_trips_no_detector`, no product code; C rewords P4.21's lookup clause (P2), the exact sentence put to the user before merge; D measures P3.12 and P3.25 (P2) and gives options. Merge A, B, C, D (B before C so C's footer is screened against B's detector). No replay; levers and replay figures go to the user. FIX_PLAN's top order line points at it.
- **Fix Tracker v36** (2026-10-05, at the user's request; same URL; the live body was identical to the repo source before the edit): no row changed; "Next" now describes batch 6 (P3.19 built, P3.24 measured, P4.21 reworded with its sentence shown to the user first, P3.12 and P3.25 measured, $0), then the rest by severity; the stamp. Script syntax-checked with Node.

---

## Session 38 — 2026-10-05 — parallel batch 6: P3.19 and P4.21 built, P3.24, P3.12 and P3.25 measured ($0)

**Done:**
- **Ran `PARALLEL_BATCH_6.md` (user decision at launch: A, B, C and D as set out).** Step 1's checks
  held at `cb04aeb`: equal to `origin`; `main` at `a6b4a76`; `plan_status` 47 of 75, 8 of 14;
  `plan_lint` 0 errors, 0 warnings; rubric sha1s `31379ecf…` and `0031831b…`, pack `d26bb016…`; 57
  replay directories; `lexchat_test` and `_a` to `_d` present; no python process, port 8000 free, no
  pin file, no worktrees; baseline suite **2162**. **Another session committed `995ef34` during the
  checks** (Fix Tracker v36, `summary-table.html` and one SESSION_LOG line, pushed); it was the
  uncommitted tracker edit seen at the start, and `<INTEGRATOR_HEAD>` was `995ef34`.
- **Merged in the order A, B, C, D, each `--no-ff`**, the full suite on `lexchat_test` after each and
  the branch pushed after each: A `8a1182c` (2171), B `e93d529` (2192), C `c782c1e` (2195), D
  `d4c16d1` (2195). For each the integrator confirmed the branch contains `995ef34`, read the note and
  the diff, and grepped the added lines for instrument ids and the matter words (session ids only;
  the instrument ids are synthetic: `ssi/1902/4`, `uksi/1899/2`, `uksi/1901/9`; D's "Annex X" and
  "Chapter Y" are generic placeholders). Notes: `docs/prepilot-fixes/notes/batch6_{A,B,C,D}.md`.
  Every agent's scratch was compared with its main-checkout copy before the worktree was removed (A
  748, B 46, C 277, D 20 files; all identical).
- **Agent A (P3.19, built): MET, ticked (user decision).** `_slim_amendment_results` lists each
  group's relations as `changes`, one entry per effecting provision, so every listed change keeps
  the provision that made it; the window is still the first 60 changed provisions, a 120-relation
  backstop, `changes_not_listed` counts what is left out. Integrator's revert on a scratch worktree
  (`hunk_anchors.py` + `revert_check.py`, four `lex.py` hunks, 69 lines removed): 13 tests fail, A's
  figure. The dry run (`seam/batch6/A/dryrun.py`, repointed in a copy in the scratchpad) on the merged
  tree is byte-identical to A's: 1,216 calls, 195,884 relations listed each with its own affecting
  provision, 43,137 counted, 0 invented, 0 hidden; median size 3,448 to 3,462, max 49,050 to 96,861.
- **Agent B (P3.24, measured; tooling): MET.** `replay_report negcurrency` and 21 tests; registered
  in `test_footer_trips_no_detector`. Integrator's revert: the three `replay_report.py` hunks remove
  791 lines (collection then fails at import); each of `negcurrency_claim`, `_evidence`, `_verdict`
  and `_turn` stubbed fails 20, 16, 14 and 16 of the 22 tests (`scratchpad_s38/revB/revert_b.py`).
  Re-run on the merged tree: 178 claims in 142 of 1,943 turns, 144 / 32 / 2 (B's totals); 6410 9
  claims (6 / 3 / 0), 6378 1 (UNCLEAR, supported by B's hand-read). **All 32 unsupported claims
  predate P3.5 or are in `wave2`; 0 in the 907 `wave3`/`wave4` turns: on the pinned Gemini the defect
  is not reproduced after P3.5.**
- **Agent C (P4.21, built): MET, ticked; wording R1 approved by the user before merge** ("… is not
  held in this index, which is incomplete; that does not show whether the number is accurate."). The
  user also chose to leave the three model-facing sites as they are. Integrator's revert (two
  `search_scope.py` hunks, 13 lines removed): the 3 tests C named fail. **The merge conflicted in
  `test_footer_trips_no_detector`** (B and C each appended a block, as the brief foresaw): resolved by
  hand (`resolve_c.py`), both blocks kept and B's `negcurrency_claim` added to C's per-sentence loop;
  the test passes. Re-run on the merged tree: C's `p421_dryrun.py rebuild`, run from a copy at
  `seam/batch6/Cx/`, produced 29 files byte-identical to C's `rebuilt/`; `replay_report lookup` is
  identical on stored and rebuilt `wave4_p37c` (exit 1, P3.15's residual) and `wave4_p315_pre`.
- **Agent D (P3.12 and P3.25, measured; note only): MET.** Re-derived on the merged tree from D's
  scripts: 63 of 5,128 section searches name a schedule paragraph (10 turns, 3 sessions); 143 of
  1,314 conversational turns make 247 `get_legislation_text` calls (29 of 483 after P3.7). **New
  finding: `get_legislation_text` has never returned a schedule or annex** (LEX's `include_schedules`
  defaults to false; `executor.py:533` sends only `legislation_id`, checked by the integrator).
- **Twelve decisions put to the user in three questions, plus C's two before its merge.** All as
  recommended except P3.24's acceptance and spend:
  - **P3.24:** lever both, the code line in `_currency_limb` first, then a rule beside
    `_IN_FORCE_RULE`; acceptance n=3 on 6410 and 6378 **on the pinned Gemini only** (not glm), up to
    **$1.31** authorised; the removal under-count booked as **P3.28** (P3), measure first; the
    detector's limits accepted, every after-column hand-read.
  - **P3.12, P3.25:** `include_schedules` booked as **P3.27** (tracker P1); P3.12's lever is the code
    route (a live LEX payload probe first); P3.25's is to remove the tool from the conversational
    Worker in code and route the recital and `valid_date` through `lookup_legislation`; their replays
    priced after the probe and the builds, one sweep.
  - **P3.19:** tick at merge; output size accepted as built, counted on the next after-column;
    Worker-facing wording left.
- **Applied** (`2018136`): `fold_s38.py` (P3.19 and P4.21 ticked and annotated, P3.24, P3.12 and P3.25
  annotated, P3.27 and P3.28 added after P3.26, Bucket index: two done marks, P3.28 beside P3.24 on
  B3, P3.27 beside P3.26 on the no-bucket line) and `order_s38.py` (the top order line); 92 bold
  markers added. **`plan_lint` 0 errors, 0 warnings; `plan_status` 49 of 77 rows, 8 of 14 buckets**
  (B3 stays partial, now on P3.24, P3.28 and P4.22). CHANGELOG *Unreleased*: P4.21 and P3.19 as
  product changes, `negcurrency` as tooling. Suite **2195**.

**Surprises / deviations:**
- **Every worktree again came up on `main` (`a6b4a76`)**; every agent checked and reset to `995ef34`.
- **P3.24's defect does not reproduce on the pinned model after P3.5**, so its booked Gemini
  acceptance can only check that true negatives survive; the user kept it Gemini-only.
- **A's "`replay_report` never imports `lex.py`" is true of the graders, not of the file:**
  `_lookup_routing` (the live path of `lookup`) imports the executor, which imports `lex.py`. It is not
  in the exit-1 set and was not run. P3.19's row says so.
- **Git Bash's `grep -iF` aborts (exit 134)** on this machine; the matter-word grep moved to Python
  (`scratchpad_s38/matter_grep.py`). A `$(grep -c …)` over it silently printed blanks first.
- **`git worktree remove` fails with "Permission denied" while the shell's cwd is inside the
  worktree**, and the harness refuses `rm -rf` of the shell's own cwd; run both from the main checkout.
- **The Fix Tracker was not updated** (only when asked). If asked: P3.19 and P4.21 Fixed
  2026-10-05, "Next release"; P3.27 (P1) and P3.28 (P3) are new tracker rows.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2195 tests. Session spend $0.

---

## Session 38 — handover for Session 39 (2026-10-05)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 38"):**
1. **P3.24's lever** (P1, $0 build): a per-instrument line in `_currency_limb`, computed from the
   change record (a provision may be called "not recorded as commenced" only where the record holds
   commencement relations by another instrument; otherwise state neither), then one sentence beside
   `_IN_FORCE_RULE` on the three legislation Worker prompts and the conversational ones. Screen the
   line against every detector (`test_footer_trips_no_detector`, which now holds `negcurrency`). Then
   its acceptance: n=3 on 6410 and 6378 **on the pinned Gemini, up to $1.31 (authorised)**, graded by
   `negcurrency` and a hand-read; true negatives still stated. Read B's note sections 6 and 8 first,
   and F3 (self-referential relations counted as commencements, noted, not booked).
2. **P3.27** (P1, measure first, $0): which stored whole-text reads were of an instrument with a
   schedule or annex, and what each answer said. It shares P3.12's live LEX payload probe (no model
   spend, but a LEX call: say so before running it).
3. **P2:** P3.12's probe and code route, then P3.25 (remove the tool from the conversational Worker in
   code; route recital and `valid_date` through `lookup_legislation`, which needs `valid_date` passed
   on); their replays priced together (D's estimate about $5.50). Then the case-law build (P4.19, P3.23,
   P3.9, then P3.22), P3.21 (reads P3.19's `changes` now) with P5.4 (c)'s probe, P3.4, P3.6, P4.3,
   P3.10, P4.12, P3.20 last.
4. **P3:** P4.8, P4.20, P4.22, P3.26, P3.28, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6.

**Before the next after-column:** count change records summarised (P3.19's long tail, user decision);
enrol 6370's five hedged readings in `p33.json` (batch 5 D2); hand-read `negcurrency`'s matches.

**Decisions open with the user (carried):** sending the lawyer pack (unblocks P3.2, P3.3, P3.17);
sending SCTS the note (P3.20); D23 (the National Archives licence); deploying `v2026.09.3` to the
target; telling the eval-harness owner about schema v6; D19; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, and now P3.19 and P4.21); P4.12, D20,
D21/D22; batch 1's three items; the p37_6373 substitution P4.17 exposes; the Fix Tracker (P3.19 and
P4.21 Fixed, P3.27 and P3.28 new) when asked.

**Machine state:** no server, no pin file, no replay running, no worktrees (the four batch 6
`worktree-agent-*` branches remain locally, merged, beside the earlier twenty). Test databases
`lexchat_test_a` to `_d` remain. 57 replay directories. Rubrics unchanged (`31379ecf…`, `0031831b…`).
Agents' scratch in `evidence/seam/batch6/{A,B,C,D}/`, the integrator's C rebuild in `batch6/Cx/`, and
the session scratchpad in `batch6/scratchpad_s38/`.
**Addendum to Session 38 (2026-10-05, at the user's request: "make sure we're not going to lose any
pertinent information", "update the tracker", then "provide a prompt to kick off the next piece of
work ... a safe, multi-agent approach"). This supersedes the Session 39 handover's "Take next" only in
pointing at the brief; its content stands.**
- **Preserved:** the batch 6 notes, the FIX_PLAN fold, the CHANGELOG and the log were committed and
  pushed (`3e5a00b`); every agent's scratch and the session scratchpad are in the gitignored
  `evidence/seam/batch6/` (A 748, B 46, C 277, D 20 files; `scratchpad_s38` 44). Three findings that
  live in no committed file were written where the next session reads them: **CLAUDE.md** gained one
  sentence (LEX's `/legislation/text` takes `include_schedules`, never sent; P3.27); the local
  **external-apis** skill (gitignored `.claude/`) gained the `include_schedules` trap, the Schedule
  as one provision, the removal effect wordings (P3.28), P3.19's new `changes` shape and the 62% of
  "to" records holding no commencement relation; the local **repo-map** skill gained
  `replay_report negcurrency`.
- **Fix Tracker v37** (same URL; the live body was identical to the repo source before the edit: the
  Artifact read, then a Read of all 1,268 lines of the saved file): P3.19 and P4.21 Fixed
  (`fixed: "2026-10-05"`, `ver: "Next release"`); P3.27 (P1) and P3.28 (P3) added as Verified; the lede
  names eight rows waiting for the next release; three plain-language notes for Thomas (the two
  fixes, P3.24's measurement, P3.12/P3.25 and the schedule gap) naming no lawyer's topic; the P3.7 note
  points to P4.21's rewording; "Next" and the stamp. 76 rows: 44 Fixed, 26 Verified, 3 Blocked, 3 To
  be verified. Script syntax-checked with Node; no render check (data and text only).
- **`docs/prepilot-fixes/PARALLEL_BATCH_7.md` written: the brief for Session 39.** Four agents in
  worktrees at $0 model spend, by severity: **A** builds P3.24's decided lever (the per-instrument line
  in `_currency_limb`, then the sentence beside `_IN_FORCE_RULE`); **B** measures P3.27 over stored
  evidence and runs the live LEX probe P3.12 needs, with P3.12's ground truth (up to 300 GETs, only if
  the user agrees at launch); **C** builds P3.25 (the tool out of the conversational Worker, recital
  and `valid_date` through `lookup_legislation`); **D** builds P4.19, P3.23 and P3.9, in the decided
  order (up to 60 National Archives GETs for their live checks, only if agreed). **Merge A, B, then
  P3.24's authorised replay (`wave4_b7_p324`, 6410 and 6378 n=3, up to $1.31, pinned Gemini; it is
  also the after-column that counts P3.19's summarised change records), then C, D**, so the replay
  measures A's lever alone. P3.12's build waits on B's probe (the dependency exception). FIX_PLAN's
  top order line points at the brief (`plan_lint` 0, 0).
---

## Session 39 — 2026-10-05 — parallel batch 7: P3.24, P4.19, P3.23 and P3.9 done; P3.25 built; P3.27 measured and P3.12 probed ($1.24)

**Done:**
- **Ran `PARALLEL_BATCH_7.md` (user decisions at launch: A, B, C and D as set out; B up to 300 LEX
  calls and D up to 60 National Archives calls, both agreed; P3.24's replay between the A/B and C/D
  merges).** Step 1's checks held at `6011b4f`: equal to `origin`; `main` at `a6b4a76`;
  `plan_status` 49 of 77, 8 of 14; `plan_lint` 0, 0; rubric sha1s `31379ecf…` and `0031831b…`; 57
  replay directories; `lexchat_test` and `_a` to `_d` present; no python process, port 8000 free, no
  pin file, no worktrees; baseline suite **2195**. `<INTEGRATOR_HEAD>` was `6011b4f`; no other
  session committed during the batch (checked before every merge and the fold).
- **Every worktree came up on `main` (`a6b4a76`) again**; each agent reset to `6011b4f`.
- **Reviews** (each: the branch contains `6011b4f`, the note and the diff read, the added lines
  grepped with `matter_grep.py` and an id grep, the scratch compared with its main-checkout copy
  before the worktree was removed, the revert run on a scratch worktree, one headline number re-run
  on the merged tree):
  - **A (P3.24's lever):** grep clean; product revert 234 lines, 21 fail; tooling revert 28 lines, 2
    fail; the integrator's F3 mutant (`self` relations counted as by another instrument) 3 fail; the
    line census identical on A's code and on the merged tree (710 delegations, 1,427 lines; 0 differ
    outside the commencement part). **A found the Worker-facing block (`_relation_currency_limb`)
    still told the Worker every `coming into force` relation, its own included, "ARE its own
    commencement and you may state them".** Put to the user before the replay: **extend P3.24 now**
    (decided); A built it as a further commit (`f758c3a`: 535 of 1,435 stored change-record calls
    move, nothing else in them; revert 73 lines, 8 fail). A's three other decisions taken as built
    (the prompt sentence states the rule in the record's own terms, because the Worker never sees
    `_currency_limb`; "state neither" where no record was consulted; the 12-instrument cap). Scratch
    144 = 144.
  - **B (P3.27 measured, P3.12's probe; note only):** grep clean (generic "Annex X" only); two stored
    figures re-run identically from the main-checkout copy (580 calls, 60 instruments with text; 126
    pairs in 98 turns on 27 instruments, 25 need pairs). 156 live LEX calls (POST, as LEX's read
    endpoints are; 4 GETs to `/legislation/proxy`). Scratch 197 = 197.
  - **C (P3.25):** grep clean (`uksi/1901/9` synthetic); full revert 309 lines, collection fails; the
    integrator's six single-site mutants (tool list ignores chat mode, lookup drops `valid_date`, no
    code lookup, recorder ignores the lookup's date, no lookup recital, prompt swap off) fail 4, 3,
    4, 3, 4 and 1. Scratch 121 = 121.
  - **D (P4.19, P3.23, P3.9):** grep clean (fixtures "Widget Co v Example Ltd", `[1901] EWCA Civ 1`);
    no other reader of a case-law `total` (the two in `search_scope.py` are legislation, keyed on
    `total_matched` first); full revert 298 lines, two test files fail at import; P4.19's revert alone
    fails 6 of 8; the integrator's ten-a-page mutant (P3.23) 4, old-date-form mutant (P3.9) 4. 36 live
    National Archives calls. Scratch 152 = 152.
- **Merged A (`5269ca9`, 2223), B (`cc26fe9`, 2223)**, pushed after each.
- **P3.24's acceptance replay (`wave4_b7_p324`):** `replay check` (served, probe $0.0010), `replay
  pin`, uvicorn started fresh with PowerShell `Start-Process -PassThru` (PID 1236, build
  `v2026.09.3-82-gcc26fe9`), the keep-awake helper (PID 14424); `replay run --session 6410 6378
  --reps 3 --max-spend 1.31` **$1.24 recorded**, 12 turns answered, no stall, no commit while it ran;
  then `replay restore`, both processes stopped by PID; no python process, port 8000 free, no pin
  file. **Graded:** the 16-subcommand exit-1 set all 0; `footer_echo` 0; `negcurrency` 2 claims, both
  SUPPORTED, 0 unsupported (`--all` on a leaf directory reads 0 turns: run it without `--all`); P3.19's
  count 27 change-record calls, 0 summarised (largest raw 4,097 characters; `wave4_p37_reach` 10 and
  0). **Hand-read** (gitignored `evidence/rubrics/handread_wave4_b7_p324.md`): no unsupported negative
  or continuing claim in 12 turns; 6410's true negative stated in 2 of 3. **Ticked at the user's
  decision ("tick, note the call")**, with three watch items on the row (below).
- **Merged C (`c909460`, 2303)** after the restore. A's sentence reaches the conversational prompt
  through C's copy, which names `get_legislation_text` 0 times (`prompt_check.py`). C's route census
  re-run on the merged tree with the new directory excluded: every footer, lookup and route figure
  identical to C's (254 footers; SI recital 3 of 3, `valid_date` 68 of 68); only the Manager-facing
  block counts differ, which A's line moves. **Merged D (`9ff8d0a`, 2339)**; D's dry run identical
  (1,253 calls; 88 date moves, 123 totals, 781 notes, 0 unexpected).
- **Decisions put to the user** (one before C's merge, then three calls of four, all as recommended):
  - **C1 (before merge):** P2.5's existing currency clause on 254 more conversational footers: keep.
  - **P3.24:** tick, with the watch items noted.
  - **P3.27:** send `include_schedules: true` and the unflagged call, with an exact code line naming
    what the text carries or that the index holds none; no size bound at first; one build with
    P3.12, P3.27 first; the 6374 guard (Invariant 1) added to the acceptance.
  - **P3.12:** the route by `/legislation/section/lookup` and `uri`; annex chapters by `_cut_annex`;
    a paragraph cut only where its `Section N)` line is unique and the next headed paragraph is N+1;
    the ground truth as a `DepthReq` in `DEPTH_TRUTH`.
  - **P3.25:** acceptance booked as C proposed, run in one sweep with P3.12's; the shared tool
    description and P2.7's stop message left.
  - **D:** retry timeouts and transport errors (kept); correct the `last` link's page size in all
    four places; **P3.9 ticked with its acceptance generalised**; D4 to D6 as built.
- **Applied** (`5778b28`): `fold_s39.py` (P3.24, P4.19, P3.23 and P3.9 ticked and annotated; P3.27,
  P3.12, P3.25 and P3.22 annotated; P3.23's premise and P3.9's named-judgment clause struck through
  and corrected; four done marks; the top order line; 60 bold markers added). **`plan_lint` 0
  errors, 0 warnings; `plan_status` 53 of 77 rows, 8 of 14 buckets** (B3 now waits on P3.28 and
  P4.22; B12 on P3.22 and P3.20). `docs/LEGAL_DATA_SOURCES.md` section 4 corrected; CHANGELOG
  *Unreleased*: P3.24, P3.25, P3.9, P3.23 and P4.19 as product changes, the grader and probe as
  tooling. Suite **2339**.

**Surprises / deviations:**
- **The brief's lever was half a lever.** The Worker never sees `_currency_limb` (it is appended to
  the report after the Worker writes), and the Worker-facing block said the opposite of the new line
  for an instrument's own relations. Caught by agent A, extended before the replay at the user's
  decision; without it the replay would have measured a Worker and a Manager told contradictory
  things on 6378.
- **`negcurrency` was blind to P3.19's shape** (it read `changed_provisions` only), so on any
  directory after P3.19 a negative the record contradicts would have graded SUPPORTED. Fixed by A
  before the replay; byte-identical on all stored data.
- **P3.23's row was wrong about its own data source:** the feed's `last` link counts at ten a page
  regardless of `per_page`; every "about 26,000" figure was five times too high. Corrected on P3.23,
  P3.22, `LEGAL_DATA_SOURCES.md` and the skill.
- **P3.9's named judgment no longer discriminates** (the corpus moved): it is on the court-filtered
  undated first page today. The acceptance was generalised (user decision).
- **LEX's read endpoints are POST, not GET** (B); `GET /legislation/proxy/<provision path>` returns
  legislation.gov.uk's page for exactly one paragraph or annex chapter, through LEX's host.
- **P3.24's replay checks suppression, not the defect, on this model**, as predicted at booking. Its
  three watch items: 6378 r2 t1's "now apply only in" three nations (a continuing claim
  `negcurrency` misses; true in substance); 6378 r1 t1 reading commencement from SIs' own relations;
  6410 naming the uncommenced remainder in 0 of 3 (1 of 5 before).
- **C's dry run picks up every replay directory**, so the new `wave4_b7_p324` added stored lookup
  payloads and shifted two footer counts; re-run with it excluded (`p325_dryrun_57.py` in the
  scratchpad) to compare like with like.
- **`git worktree remove --force` on a scratch worktree left an empty directory** when the shell's cwd
  had been inside it; `rmdir` from outside cleared it.
- **The Fix Tracker was not updated** (only when asked). If asked: P3.24, P4.19, P3.23 and P3.9 Fixed
  2026-10-05, "Next release".

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2339 tests. Session spend **$1.24** (P3.24's replay; agents $0).

---

## Session 39 — handover for Session 40 (2026-10-05)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 39"):**
1. **P3.27 then P3.12, one build, two commits** (P1, $0 build). Read `notes/batch7_B.md` first: it
   holds the probe, the cut rules and the payload sizes. P3.27: send `include_schedules: true` on
   `get_legislation_text`, make the unflagged call too, and append a code line (built from the raw
   responses, after summarisation, `enabling_power_note`'s pattern) naming the schedules and annexes
   the text carries, or saying the index holds none; screen it against every detector. P3.12: in
   `run_worker_tool`, when a section-search query names a schedule or annex unit the results lack,
   fetch it by `/legislation/section/lookup` and `uri`, cut annex chapters with `_cut_annex` and a
   paragraph only where its `Section N)` line is unique and the next headed paragraph is N+1, else
   label the span or summarise the whole schedule; dry-run over all 5,128 stored section searches.
   Put P3.12's ground truth into `DEPTH_TRUTH` as a `DepthReq` for 6335 turn 7 (the text is in the
   gitignored `evidence/seam/batch7/B/p312_truth.txt`; regexes over the statutory words only).
2. **Then one replay sweep for P3.27, P3.12 and P3.25**, priced to the user first (about $5.50 to $7):
   P3.25's booked table (`p37_6409` n=3, 6340 n=3 Conversational, `p37r_6374` and `p37r_6383` n=1,
   `p32_6406` cut after export turn 5 n=3, shared with P3.12), 6335 n=3 (P3.12, recorded modes), and
   6374's guard (P3.27). Remember C's named risk on 6340.
3. **P2:** P3.22 (the case-law build's last step: its paced $0 measure-first under the published
   1,000 per five minutes, a before-column, the build flipping `CASE_LAW_RESULT_ORDER` and the
   nudge's "most relevant", the after-column; book the 6363 and 6359 ground truth first), P3.21 with
   P5.4 (c)'s probe, P3.4, P3.6, P4.3, P3.10, P4.12, P3.20 last.
4. **P3:** P4.8, P4.20, P4.22, P3.26, P3.28, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6.

**Watch items carried:** P3.24's three (on its row); `negcurrency` does not match "now apply" or
"still applies" (batch 6 B's valid/applicable gap); B's F3 is now closed in both the Manager's line
and the Worker's block, but `provisions_commenced` and P2.5's `_currency_support` still count self
relations (unchanged, not booked).

**Decisions open with the user (carried):** sending the lawyer pack (unblocks P3.2, P3.3, P3.17);
sending SCTS the note (P3.20); D23 (the National Archives licence); deploying `v2026.09.3` to the
target; telling the eval-harness owner about schema v6; D19; which rows go in the next cut
(`v2026.10.1`: P3.16, P4.16, P4.15, P4.18, P4.17, P5.2, P3.19, P4.21, and now P3.24, P4.19, P3.23,
P3.9); P4.12, D20, D21/D22; batch 1's three items; the p37_6373 substitution P4.17 exposes; the Fix
Tracker (P3.24, P4.19, P3.23, P3.9 Fixed) when asked.

**Machine state:** no server, no pin file, no replay running, no worktrees (the four batch 7
branches were deleted after merging; the 24 earlier `worktree-agent-*` branches and `batch3-B`
remain locally). Test databases `lexchat_test_a` to `_d` remain. **58 replay directories** (new:
`wave4_b7_p324`). Rubrics unchanged (`31379ecf…`, `0031831b…`); new gitignored hand-read
`rubrics/handread_wave4_b7_p324.md`. Agents' scratch in `evidence/seam/batch7/{A,B,C,D}/`, the
session scratchpad in `batch7/scratchpad_s39/`.
**Addendum to Session 39 (2026-10-06, at the user's request: "make sure we're not going to lose any
pertinent information", "update the tracker", then "provide a prompt to kick off the next piece of
work ... a safe, multi-agent approach"). This supersedes the Session 40 handover's "Take next" only in
pointing at the brief; its content stands.**
- **Preserved:** every Session 39 commit was pushed (`a5f740e` and before); the four agents' scratch
  is in the gitignored `evidence/seam/batch7/{A,B,C,D}/` (144, 197, 121, 152 files) and the session
  scratchpad in `batch7/scratchpad_s39/` (99 files, including the three CRLF-safe mutant runners
  moved out of `C:/Temp`); P3.24's hand-read is `evidence/rubrics/handread_wave4_b7_p324.md`.
  Findings that lived in no committed file were written where the next session reads them:
  **CLAUDE.md** gained three short additions (the live LEX probe and the P3.27/P3.12 decision beside
  the `include_schedules` sentence; a case-law bullet on the `last` link's ten-a-page count, the date
  form and the retries; a Worker bullet on P3.24's commencement split, the fact that the Worker never
  sees `worker_scope_block`, and P3.25's tool removal); the local **external-apis** skill (gitignored
  `.claude/`) gained the probe findings (POST read endpoints, `/legislation/proxy` per provision,
  `include_schedules` appending 60 of 60, the section lookup's completeness, the cut rules) and the
  case-law corrections; the local **repo-map** skill gained the Session 39 functions and an
  `instrument_lookup.py` row. **P3.25 is now `[~]`** (built, its replay booked), so `plan_status`
  reads 53 of 77 rows, 1 in progress, 8 of 14 buckets.
- **Fix Tracker v38** (same URL; the live body was identical to the repo source before the edit:
  the Artifact read, then a Read of all 1,302 lines of the saved file): P3.24, P4.19, P3.23 and P3.9
  Fixed (`fixed: "2026-10-05"`, the date `5778b28` first shows them ticked; `ver: "Next release"`);
  P3.25 In progress; the lede names twelve rows waiting for the next release; the In-progress note
  names P3.25; four plain-language notes for Thomas (P3.24; the three case-law fixes; P3.25; P3.27
  and P3.12 measured and chosen), naming no lawyer's topic; "Next" and the stamp. 76 rows: 48 Fixed,
  1 In progress, 21 Verified, 3 Blocked, 3 To be verified. Script syntax-checked with Node; no
  render check (data and text only).
- **`docs/prepilot-fixes/PARALLEL_BATCH_8.md` written: the brief for Session 40.** Four agents in
  worktrees at $0 model spend: **A** builds P3.27 then P3.12 (one build, two commits, as decided);
  **B** builds the acceptance sweep's instruments (P3.12's `DEPTH_TRUTH` entry, a `p32_6406` script
  cut after export turn 5, the 6374 guard and P3.27's schedule check made gradeable) and prices the
  sweep from stored costs; **C** measures P3.22 (a paced live re-run of every stored case-law query
  under both orderings, up to 1,300 National Archives calls if the user agrees, and the 6363 and 6359
  ground truth); **D** measures P3.21 with P5.4 (c)'s probe (up to 300 LEX and 300 legislation.gov.uk
  calls if agreed). **Merge A, B, then the sweep for P3.27, P3.12 and P3.25 (priced to the user
  first, about $5.50 to $7, run only on their go-ahead), then C, D.** One correction found while
  writing it: `_cut_annex` lives in the dev tool `tools/provision_hints.py`, not in `lex.py`, so A
  must give the cut a product home. FIX_PLAN's top order line points at the brief.

---

## Session 40 — 2026-10-06 — parallel batch 8: P3.25 done; P3.27 and P3.12 built, their replay not met; P3.22 and P3.21 measured and decided ($9.55)

**Done:**
- **Ran `PARALLEL_BATCH_8.md` (user decisions at launch: A, B, C and D as set out; B up to 40 LEX
  calls, C up to 1,300 National Archives calls, D up to 300 LEX and 300 legislation.gov.uk calls, all
  agreed; merge order A, B, the priced sweep on the user's go-ahead, then C, D).** Step 1's checks held at
  `87ceeff`: equal to `origin`; `main` at `a6b4a76`; `plan_status` 53 of 77, 1 in progress, 8 of 14;
  `plan_lint` 0, 0; rubric sha1s `31379ecf…` and `0031831b…`; 58 replay directories; the five test
  databases; no python process, port 8000 free, no pin file, no worktrees; baseline suite **2339**.
  `<INTEGRATOR_HEAD>` was `87ceeff`; no other session committed during the batch (checked before every
  merge and the fold).
- **The four agents were cut off once when the session's process ended (about an hour in), and resumed
  from their transcripts in their worktrees**; each recounted its call log before going on (the caps
  covered calls made before the stop). The whole session ran on 2026-10-06 (checked against commit and
  file times at the user's request).
- **Every worktree came up on `main` (`a6b4a76`) again**; each agent reset to its base.
- **Reviews** (each: the base contained, the note and diff read, the added lines grepped with
  `matter_grep.py` and an id grep, the scratch compared with its main-checkout copy before removal, one
  headline number re-run on the merged tree; for A, A2 and B the revert on a scratch worktree and the
  integrator's own mutants):
  - **A (P3.27, P3.12):** grep clean (generic "Annex"); revert 1,026 product lines, collection fails;
    of the integrator's three mutants **two survived** (the lookup-failure fallback accepting a heading
    met twice; a bracket in the id or url reaching a block header). Sent back: two tests added in
    `f3af75a`, and one of them found a real defect (schedule labels from LEX's uris not cleaned), fixed.
    The user approved both wordings before merge and chose to **extend the trigger to an unlabelled
    "the Schedule"** (A's decision 1), built in `1d1876e` (the integrator's mutant fails 2). Dry run
    re-run on the merged tree: 22 / 33 / 5 lines, x1.96 and x1.94. Scratch 97 = 97.
  - **B (instruments):** grep clean (P3.12's Act inside `DEPTH_TRUTH` only); revert 399 lines, 19 of 22
    fail; the integrator's three mutants all caught. The integrator's screen of A's BUILT wording with
    B's `sched_clause_class` found A's code-stated true negatives read SILENT, not INDEX; B's worktree was
    gone, so a fresh agent **B2** fixed it (`68f5611`: four phrasings read as index statements, and A's
    two block markers added to `cmd_corpus`'s leak list; 0 stored verdicts move). The user decided:
    silent 6374 turns report SILENT; `depth` needs each paragraph cited with its facts. Re-run on the
    merged tree: `wave3_p38_pre` 6335 t7 PARTIAL, SHALLOW, SHALLOW; 6374 guard 7 / 12 / 17 of 36; the
    price $7.29 / $12.16. Scratch 222 = 222 (B), 20 = 20 (B2). B's rubric copied to
    `evidence/rubrics/p327.json` (sha1 `5a14e273…`).
  - **C (P3.22):** grep clean; census re-run identically (1,257 calls, 612 tuples, 35 dated, 245 all
    zero); call log 1,241 calls, one host. Scratch 1,279 = 1,279.
  - **D (P3.21, P5.4 (c)):** grep clean; census re-run identically (1,462 change-record calls, 157
    commencing instruments, 993 hops, cap 5 = 74%). Scratch 509 = 509.
- **Merged A (`35ed6d7`, 2386), B with B2 (`68fd879`, 2414)**; the branch push was refused by the
  permission classifier and **pushed on the user's go-ahead**.
- **The acceptance sweep (`wave4_b8_sweep`, user decision: the booked set plus full 6374 and 6389 n=1,
  cap $12.20):** `replay check` (served), `replay pin`, uvicorn started fresh with PowerShell
  `Start-Process -PassThru` (PID 14504, build `v2026.09.3-103-g68fd879`), the keep-awake helper (PID
  12648). `--max-spend` is per command, so the cap was enforced across the seven commands by a running
  total (`sweep_total.py`); command 5 stopped at its own cap after `p37r_6374` ($0.82, a lost-completion
  episode) and `p37r_6383` was run as 5b. **16 run files, $9.55 recorded.** Then `replay restore`, both
  processes stopped by PID; no python process, port 8000 free, no pin file. No commit while it ran.
- **Graded** (hand-read: gitignored `evidence/rubrics/handread_wave4_b8_sweep.md`): the exit-1 set 0
  except `negatives` 1 (`p37r_6383` r1 t2, P2.2's limits column; the stored reps pass), `commencements`
  1 (it never grades scripted runs: a blind spot) and `modes` 1 (2 of 67 answers research-shaped by an
  echoed report label, as in stored 6406 directories); `negcurrency` 0 unsupported in 67 turns;
  `footer_echo` 0.
  - **P3.12:** the route fired in every rep; **6335 t7 DELIVERED 0 of 3** (PARTIAL 3): paragraph 42 at
    depth 3 of 3 (0 of 7 before); reps 1-2 named Schedule B1 alone and got the whole Schedule summarised;
    rep 3 named "paragraphs 42 43 44", which the parser read as 42, and the answer said falsely that the
    index had not returned 43 and 44. **Criterion (v) met 3 of 3 by hand** (6406's annex chapter cut and
    handed over in 3 of 3; `schedules` OK 12).
  - **P3.27:** **the 6374 guard FAILS 4 of 4**: the Worker was told the true negative in code on every
    step, kept searching the Order, hit P3.1's cap, and the cap's "may still be in it" won. 6389 made no
    whole-text call (P3.12's route fetched both schedules).
  - **P3.25:** 0 whole-text calls in a quick-lookup turn; 6409's list delivered 3 of 3 by hand; 6340 0
    derivations, but the stored Conversational rep asserted none either (every stored derivation is
    Research mode), and all three answers are true.
- **Merged C (`fcfd267`, 2423) and D (`23a16cf`, 2442)** after the restore, pushed.
- **Decisions put to the user** (seven calls, all as recommended except where noted): A's and A2's
  wordings approved; the trigger extension; no Manager limb before the sweep; the audit records sizes;
  **two sweep-found fixes built now, re-run next session**; **P3.25 ticked with 6340's criterion
  amended to suppression**; P3.22 relevance with the note flipped, the before-column n=3, the rubric
  adopted and 6363's Tier 1 added to the lawyer pack, P3.29 booked; one GET of the published spec; P3.21
  the feed through LEX's proxy, one feed per change record, 6411 on the negative branch, self-commencing
  Acts out; P5.4 (c) no new row; A2's route bound fixed next session, P3.27's line not yet treated as
  established, the ascending-only paragraph run.
- **The spec GET** (one, user-agreed): `public_api.yml` v0.6.0 (200, 22,590 bytes): `order` enum `date`,
  `updated`, `transformation` (and `-` forms), default `-date`; no "relevance" anywhere.
- **A2 (the two fixes):** grep clean; revert 290 lines, 25 fail; of the integrator's three mutants two
  caught, one survivor (the refusal's own bracket cleaning: harmless in a JSON tool result); merged
  (`342ab50`, 2482), pushed. The parser reads the sweep's query as 42, 43, 44 on the merged tree.
- **The lawyer pack** gained a further question after Reading 4 (reference 6363: the proposed list of
  authorities, the three the corpus lacks named, Scottish authority invited); the cover note says so.
- **Applied** (`e499232`): `fold_s40.py` (P3.25 ticked; P3.27, P3.12, P3.22, P3.21, P5.4 annotated;
  new P3.29; two index entries; the top order line; 68 bold markers added). **`plan_lint` 0 errors, 0
  warnings; `plan_status` 54 of 78 rows, 0 in progress, 8 of 14 buckets.** CHANGELOG *Unreleased*:
  schedules and annexes (P3.27, P3.12, A2's fixes) and tooling; `docs/LEGAL_DATA_SOURCES.md`
  (commencement dates, schedules, relevance order). Suite **2482**.

**Surprises / deviations:**
- **The code-stated negative was right and still lost.** P3.27's and P3.12's lines told the Worker the
  truth on every step of 6374, and P3.1's cap note, a second code text for the same instrument, said a
  provision "may still be in it". Batch 7's lesson again, one level down: check every code text that
  speaks of the same instrument, not only the one being built.
- **A dry run cannot see a query form no stored run used.** The space-separated paragraph list appeared
  first in the sweep.
- **6340's booked bar was set from Research-mode runs** but booked in Conversational mode, where the
  before-column never met it either. Read a booked bar against the before-column in the same mode.
- **`commencements` has never graded a scripted run** (`p37_6409` here and on `wave4_p37c`); P3.25's
  6409 criterion was a hand-read.
- **A2's finding:** P3.12's per-run bound is checked before the fetch's `await`, so a batched round can
  exceed it (6 reads against 5) and fetch one instrument twice. Extra LEX calls only.
- **Costs ran above the stored figures** (6335 $1.55 against a $0.98 single-rep estimate; `p37r_6374`
  $0.82 against about $0.21 with a lost-completion episode) but the sweep stayed under its cap.
- **Removals blocked by the harness's safety check:** an `rm` on a shell-variable path and an `rmdir`
  under `C:\Temp` (a session working directory); neither was needed. `git worktree remove` could not
  delete `C:\Temp\b8_revA`, `b8_revA2` or `b8_revA3` (the shell had been inside them): git no longer
  tracks them; they are disposable copies for the user to delete.
- **The Fix Tracker was not updated** (only when asked). If asked: P3.25 Fixed 2026-10-06, "Next
  release"; P3.29 a new row (P3).

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at
`a6b4a76`. 2482 tests. Session spend **$9.55** (the sweep; agents $0).

---

## Session 40 — handover for Session 41 (2026-10-06)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 40"):**
1. **P1: the re-run for P3.27 and P3.12** (A2's two fixes are merged): 6335 n=3 (P3.12: `depth` on t7,
   each paragraph cited with its facts), `p37r_6374` n=1 and full 6374 n=1 (P3.27's guard:
   `replay_report schedules --session 6374`, SILENT reported). About $4 to $5 at this sweep's costs:
   **price it to the user first**, cap the running total (`--max-spend` is per command). Before it, the
   small commit the user booked: reserve P3.12's per-run slot before the fetch's `await` (A2's finding),
   with a test. Hand-read every 6374 verdict and every 6335 t7 verdict. P3.27's flag cost on a
   schedule-bearing whole text is still unmeasured (6389 made no whole-text read).
2. **P2:** P3.22 (its before-column first: 6363 and 6359 n=3 each at a head without P3.22, graded on
   C's gitignored rubric `evidence/seam/batch8/C/rubric_p322_6363_6359.md`, about $9.65 a column,
   priced first; then the build: `order=relevance` with `per_page=50`, the note's three order
   statements flipped without "ranked"; then the after-column); P3.21's build (the feed through LEX's
   proxy, one per change record, 2 pages, 8 s, fail-soft, a made-date check; then 6409 and 6411 n=3);
   P3.4, P3.6, P4.3, P3.10, P4.12, P3.20 last.
3. **P3:** P4.8, P4.20, P4.22, P3.26, P3.28, P3.29, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6.

**Watch items carried:** P3.24's three (on its row); `negcurrency`'s "now apply" gap; `negatives` on
`p37r_6383` t2 (one rep); the research-shaped echo on 6406 (2 of 67); 6409's lost SSI date (P3.21);
`commencements` blind to scripted runs.

**Decisions open with the user (carried):** sending the lawyer pack (now five questions; unblocks
P3.2, P3.3, P3.17, and confirms P3.22's 6363 list); sending SCTS the note (P3.20); D23; deploying
`v2026.09.3`; telling the eval-harness owner about schema v6; D19; the next cut (`v2026.10.1`: P3.16,
P4.16, P4.15, P4.18, P4.17, P5.2, P3.19, P4.21, P3.24, P4.19, P3.23, P3.9, and now P3.25); P4.12,
D20, D21/D22; batch 1's three items; the p37_6373 substitution; the Fix Tracker when asked.

**Machine state:** no server, no pin file, no replay running; no registered worktrees (the batch 8
agent branches remain locally, merged); `C:\Temp\b8_revA`, `b8_revA2`, `b8_revA3` are untracked
disposable directories. **59 replay directories** (new: `wave4_b8_sweep`, 16 files). Rubrics:
`p32.json` and `p33.json` unchanged; new `p327.json` (sha1 `5a14e273…`) and the hand-read
`handread_wave4_b8_sweep.md`. Agents' scratch in `evidence/seam/batch8/{A,A2,B,B2,C,D}/`, the session
scratchpad in `batch8/scratchpad_s40/`.

**Addendum to Session 40 (2026-10-06, at the user's request: "make sure we're not going to lose any
pertinent information", "update the tracker", then "provide a prompt to kick off the next piece of
work ... a safe, multi-agent approach"). This supersedes the Session 41 handover's "Take next" only in
pointing at the brief; its content stands.**
- **Preserved:** every Session 40 commit was pushed (`f3068cf` and before); agents' scratch in the
  gitignored `evidence/seam/batch8/{A,A2,B,B2,C,D}/`, the session scratchpad in
  `batch8/scratchpad_s40/` (109 files, including `sweep_total.py`, `route_trace.py`,
  `screen_A_wording.py` and the three mutant runners); the hand-read
  `evidence/rubrics/handread_wave4_b8_sweep.md`; B's rubric `evidence/rubrics/p327.json`; the lawyer
  pack's new 6363 question. Findings that lived in no committed file were written where the next
  session reads them: **CLAUDE.md** gained three additions (P3.27/P3.12 built and the lesson that a
  code-stated fact loses to a contradicting code text about the same instrument; P3.22's decision;
  P3.21's decision); **`docs/api/AUDIT_TRACE.md`** gained a note on P3.27/P3.12's new `api_calls`
  (`-without-schedules`, `-provision-list`, `-text-with-schedules`, recorded by size), result keys and
  blocks (no schema change; tell the eval-harness owner); **FIX_PLAN's Verification protocol** says
  `--max-spend` is per command; the local `external-apis` and `repo-map` skills were updated.
- **P3.27 and P3.12 set `[~]`** (built, their re-run booked: P3.25's precedent), so `plan_status`
  reads 54 of 78 rows, 2 in progress, 8 of 14 buckets; `plan_lint` 0 errors, 0 warnings.
- **Fix Tracker v39** (same URL; the live body was identical to the repo source before the edit: the
  Artifact read, then a Read of all 1,341 lines of the saved file): P3.25 Fixed (`fixed:
  "2026-10-06"`, the date `e499232` first shows it ticked; `ver: "Next release"`); P3.27 and P3.12 In
  progress; new row P3.29 (P3, Verified); the lede names thirteen rows waiting for the next release;
  the In-progress note; three plain-language notes for Thomas (P3.25; P3.27 and P3.12 built, not yet
  passed, and the two causes fixed; P3.22 and P3.21 chosen, P3.29), naming no lawyer's topic; "Next"
  and the stamp. 77 rows: 49 Fixed, 2 In progress, 20 Verified, 3 Blocked, 3 To be verified. Script
  syntax-checked with Node; no render check (data and text only).
- **`docs/prepilot-fixes/PARALLEL_BATCH_9.md` written: the brief for Session 41.** Five agents in
  worktrees at $0 model spend: **A** reserves P3.12's per-run slot before the fetch's await; **B**
  builds P3.22; **C** builds P3.21; **D** builds P3.4 then P3.6; **E** builds the graders for P3.22,
  P3.21 and P3.4, P3.4's scripts, the confound check, and prices the sweeps. **Merge A, E, then sweep 1
  (P3.27/P3.12's re-run and P3.22's and P3.4's before-columns, priced to the user first), then B, C,
  then sweep 2 (P3.22's and P3.21's after-columns, priced first; one sweep or two by E's confound
  check), then D** (P3.4's after-column priced, this session or next). FIX_PLAN's top order line points
  at the brief.

---

## Session 41 — 2026-10-06 to 2026-10-08 — parallel batch 9: P3.27, P3.21, P3.4 and P3.6 done; P3.12 and P3.22 not met ($29.40)

**Done:**
- **Ran `PARALLEL_BATCH_9.md` (user decisions at launch: A, B, C, D and E as set out; B up to 20 National
  Archives calls and C up to 40 LEX calls, both agreed; merge order A, E, sweep 1, B, C, sweep 2, D, sweep 3
  only if wanted).** Step 1's checks held at `ca3d45c` (one commit past `749b97c`: Fix Tracker v41, tracker
  instructions only): equal to `origin`; `main` at `a6b4a76`; `plan_status` 54 of 78, 2 in progress, 8 of 14;
  `plan_lint` 0, 0; rubric sha1s `31379ecf…`, `0031831b…`, `5a14e273…`; 59 replay directories;
  `lexchat_test_e` created; no python process, port 8000 free, no pin file; baseline suite **2482**.
  `<INTEGRATOR_HEAD>` was `ca3d45c`; no other session committed (checked before every merge and the fold).
- **Every worktree came up on `main` (`a6b4a76`) again**; each agent reset to its base.
- **The user paused the session once (2026-10-07), after C's merge, and resumed on 2026-10-08**; state was
  re-verified before going on (head equal to `origin`, nothing running).
- **Reviews** (each: the base contained, the note and diff read, the added lines grepped with
  `matter_grep.py` and an id grep, the integrator's revert on a scratch worktree and at least three
  single-site mutants of its own, the built wording screened with `b9_screen.py`, the full suite on
  `lexchat_test`, the scratch compared with its main-checkout copy, one headline number re-run on the merged
  tree):
  - **A (P3.12's slot):** revert 65 lines, 7 of 8 fail; the integrator's 4th mutant (a finished failed read
    re-fetched) survived, so A was sent back: a test for it, and (user decision) the provision-list bound
    raised to 8 as its own constant (`e543ca1`, `9483c45`); re-checked: revert 74 lines, 8 fail, 4 of 4
    mutants caught. Merged `3c7cfa0` (2493); A's sweep dry run identical on the merged tree (23 firing calls,
    22 list reads = live). Scratch 125 = 125. The branch push was refused by the permission classifier and
    **pushed on the user's go-ahead, which covered every later clean merge this session.**
  - **E (graders):** revert 1,171 lines; the integrator's mutant on `--negative-allows-supported` survived
    (the option untested), so E was sent back (`2e4e5ef`, 5 cases); re-checked 4 of 4. Merged `3daf7a6`
    (2550); `jurisdiction --all-dirs` re-run: FAIL 8, PASS 5 (= E). Rubrics copied: `evidence/rubrics/p322.json`
    (sha1 `863955e0…`) and `p34.json` (`f0232e9d…`). Scratch 513 = 513.
  - **B (P3.22):** revert 85 lines; the integrator's 5 mutants caught (one equivalent, the integrator's
    error); screen 0 trips. Merged `e0bf656` after sweep 1 (2566); B's dry run re-run: 0 unexpected moves,
    first three changed on 269 of 356 tuples. Scratch 246 = 246. 10 National Archives calls.
  - **C (P3.21):** C's output shape differed from the brief in one respect (`commencement_dates` a dict with
    `status`), relayed to E before E finished. Revert 830 lines; of the integrator's 4 mutants 2 caught and 2
    provably equivalent (the slimmer never emits such an entry); screen: no variant rises. Merged `d695086`
    after sweep 2a (2623); C's acceptance dry run re-run after the pause: 6409 62/62, 6411 absent 8/8.
    Scratch 66 = 66. 35 LEX calls.
  - **D (P3.4, P3.6):** reverts 63 and 99 lines; the integrator's screen found one new trip ("possibly cut
    short" in the description clause matches `SCHED_LIMIT`), so D was sent back (`a344f20`: "possibly
    truncated", user decision); the integrator's rstrip mutant then caught. P3.4's commit merged alone
    (`6805422`, 2754) ahead of sweep 3, then the rest (`c914333`, 2783); P3.6's dry run re-run on the merged
    tree: 0 of 6,521 cross 8,000 (largest 4,643). Scratch 35 = 35.
- **Decisions put to the user** (nine calls, all as recommended except the two cap raises, which the user
  set): A's bound to 8; the AUDIT_TRACE sentence; B's wording, the probe's checks on the product's request,
  the 10 unfetched calls left; C's wording (with the failure sentence), made-date handling, the static
  texts, the cap 8, the description-versus-feed date watched; D's wording, two prompts and four parts,
  "truncated", P3.4 then sweep 3 then P3.6, P3.30 booked; E's 6411 reading (fail only unsupported),
  `p37_6409` for 2b, the 2a/2b split, 6360 at n=3, the footer test left, the `negcurrency` and
  `authorities` grader fixes booked; the 8,000-character finding recorded in CLAUDE.md only; the ticks.
- **Sweeps** (pinned Gemini; `replay check`, `replay pin`, uvicorn fresh with `Start-Process -PassThru`,
  the keep-awake helper, the running total with `sweep_total.py` after every command, `replay restore`,
  both processes stopped by PID, no commit while a replay ran):
  - **`wave4_b9_sweep1`** (head `3daf7a6`), 17 files, **$14.47 of $24**: P3.27/P3.12's re-run, P3.22's and
    P3.4's before-columns.
  - **`wave4_b9_sweep2a`** (head `e0bf656`), 6 files, **$12.39** (cap $13 raised by the user to $17 after
    6363 r1 cost $4.745 to a Manager runaway).
  - **`wave4_b9_sweep2b`** (head `d695086`), 6 files, **$1.45 of $3**.
  - **`wave4_b9_sweep3`** (head `6805422`), 7 files, **$1.09** (cap $1.50, plus one 6378 rep on the user's
    decision).
- **Graded and hand-read** (gitignored `evidence/rubrics/handread_wave4_b9_sweep1.md`, with sweep 3 as an
  addendum, and `handread_wave4_b9_sweep2.md`):
  - **P3.27 ticked** (user, with a watch item): the 6374 guard FAIL 0, PASS 2, SILENT 1 (Session 40: FAIL 4
    of 4); both P3.1 refusals on the Order carried A2's code-read list; one answer conjoins the limit with the
    index fact.
  - **P3.12 not met:** 6335 t7 0 of 3; no brief named paragraphs 42-44, so the whole 92,066-character
    Schedule was summarised for the question; r2 called the summarised provisions "not retrieved".
  - **P3.22 not met** (user: keep built, `[~]`): lead and carrier held; two 6363 authorities in fewer runs
    (query choice by hand); one genuine item-3 failure; 3 grader surname false positives.
  - **P3.21 ticked:** `p37_6409` dates both commencing instruments 3 of 3 (before 0 of 35 for the second),
    with the limiting qualification 3 of 3 and the source in the footer; 6411 3 of 3 on its branch.
  - **P3.4 ticked** (user rule: tick if a fourth 6378 rep passed; it did): 6360 0 to 3 of 3; 6378 3 of 3
    answered; every first brief names the jurisdiction and adds no instrument.
  - **P3.6 ticked at merge** (deterministic).
  - The exit-1 set on every sweep: 0 except `commencements` (no graded session; never grades a scripted run)
    and `modes` (3 of 72 and 7 of 39 research-shaped by formatting; no guessed mode).
- **Applied** (`7daed79`): `fold_s41.py` (four rows ticked, P3.22 to `[~]`, P3.12, P2.3, P3.24 and P4.12
  annotated, new **P3.30**, four Bucket-index done marks, the top order line; 68 bold markers added).
  **`plan_lint` 0 errors, 0 warnings; `plan_status` 58 of 79 rows, 2 in progress, 9 of 14 buckets (B9
  closed).** CHANGELOG *Unreleased*; `docs/LEGAL_DATA_SOURCES.md`, `docs/api/AUDIT_TRACE.md` and CLAUDE.md
  corrected (`docs_s41.py`). Suite **2783**.

**Surprises / deviations:**
- **P3.12's gap moved upstream.** The parser and slot fixes held, but no brief in three reps named the
  paragraphs, so the route had nothing to cut and summarised a 92K Schedule; and the block's own caution
  ("the summary is not the statutory text") was read once as "not retrieved".
- **A grader matched a surname, not an authority.** `authorities` read a different, retrieved judgment
  sharing the out-of-corpus authority's surname as that authority named as if read (3 false FAILs).
- **A before/after bar on retrieval counts mixes ordering with query choice.** P3.22's drops traced to the
  Worker issuing different searches; the same query under both orderings is the clean measure.
- **Every stored replay was summarised at the 8,000-character fallback** (batch 9 D): the context-length
  cache is cold at replay time. Every summariser measurement to date ran at 8,000.
- **212 SSIs carry a recital in their search-row description**, against P2.3's "0 of 28" (a `/legislation/text`
  sample). P3.6 now shows it; P3.30 books its use.
- **The Manager runaway (P4.12) cost $2.70 extra in one rep**; the per-command cap stopped the command, and
  the running total let the user decide.
- **The brief's shape for C was a value; C built a dict.** The relay to E before E finished kept the grader
  right.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at `a6b4a76`.
2783 tests. Session spend **$29.40** (the four sweeps; agents $0; three `replay check` probes about $0.003).

---

## Session 41 — handover for Session 42 (2026-10-08)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 41"):**
1. **P1: P3.12's lever, measure first ($0).** Over the stored route calls (`wave4_b8_sweep`,
   `wave4_b9_sweep1`): when a fetched unit is too large to hand over whole, what a heading list plus a
   query-matched cut would hand over instead of one summary, and a rewording of the summary tail so a summary
   is never read as not retrieved (a seam probe on `wave4_b9_sweep1` 6335 r2 t7 first). Then 6335 n=3, priced
   to the user.
2. **P2:** P3.22's per-query check ($0, a few National Archives calls, with the user's agreement: do sweep
   1's queries that returned the two dropped authorities still return them under relevance?) and the
   `authorities` surname fix before any further P3.22 column; P4.3, P3.10 (each re-booked first), P4.12, P3.4's
   research-mode follow-up (the research Manager and planner, with their own before-column), P3.20 last.
3. **P3:** the `negcurrency` section-search shape fix (before P3.24's watch items are next measured), P4.8,
   P4.20, P4.22, P3.26, P3.28, P3.29, P3.30, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6.

**Watch items carried:** P3.27's conjoined limit clause (6374 DR t4); P3.21's omitted "wholly" (one rep) and
a description's date beside the feed's (book a row only on a contradiction); P3.4's lost 6378 rep; the
research-shaped formatting in 2a (7 of 39); P3.24's three; `commencements` blind to scripted runs.

**Decisions open with the user (carried):** sending the lawyer pack (unblocks P3.2, P3.3, P3.17; confirms
P3.22's 6363 list); sending SCTS the note (P3.20); D23; deploying `v2026.09.3`; telling the eval-harness
owner about schema v6 and the new `api_calls` (P3.27/P3.12, P3.21) and request keys (P3.22) in
`AUDIT_TRACE.md`; D19; the next cut (`v2026.10.1`: the thirteen rows already "Next release" plus P3.27,
P3.21, P3.4 and P3.6); P4.12, D20, D21/D22; batch 1's three items; the p37_6373 substitution; the Fix
Tracker when asked (if asked: P3.27, P3.21, P3.4 and P3.6 Fixed, `fixed` 2026-10-08, "Next release"; P3.22
In progress; new row P3.30, P3, `added` 2026-10-08).

**Machine state:** no server, no pin file, no replay running. **63 replay directories** (new:
`wave4_b9_sweep1` 17 files, `wave4_b9_sweep2a` 6, `wave4_b9_sweep2b` 6, `wave4_b9_sweep3` 7). Rubrics: new
`p322.json` and `p34.json`, the hand-reads `handread_wave4_b9_sweep1.md` and `handread_wave4_b9_sweep2.md`.
Agents' scratch in `evidence/seam/batch9/{A,B,C,D,E}/`, the session scratchpad in
`batch9/scratchpad_s41/`. Agent worktrees removed after their merges.

**Addendum to Session 41 (2026-10-08, at the user's request: "make sure we're not going to lose any pertinent
information", "update the tracker", then "provide a prompt to kick off the next piece of work ... a safe,
multi-agent approach"). This supersedes the Session 42 handover's "Take next" only in pointing at the brief;
its content stands.**
- **Preserved:** findings that lived only in agents' notes were written onto the rows a future session reads
  (`preserve_s41.py`): **P3.14** (with P3.4 the quick-lookup Worker defaults to Scotland but still never sees the
  filter block, so a non-Scotland filter with a brief omitting the jurisdiction would answer for Scotland while
  the executor filters to the other territory); **P3.16** (the summariser also writes commencement dates its
  source lacks: `wave4_p37_pre` 6409 r2 t2, stored 6411 summaries); **P3.4** (the research Worker's "Note the
  territorial extent from the metadata" left for the research-mode follow-up; the UI's filter description
  unchecked); **P3.22** (batch 9 B's correction of batch 8 C's "52 tuples (123 stored calls)": 82 calls; the 10
  `wave4_b8_sweep` calls left undry-run); **P2.5** (its `_CURRENCY_CLAUSE` trips `IN_FORCE_CLAIM` and
  `_currency_asserted`, a pre-existing grader false positive); **P3.6** (`cmd_corpus`'s stale label); and in
  `docs/LEGAL_DATA_SOURCES.md` the provenance finding (1,780 of 7,189 distinct stored search rows carry
  `provenance_source: llm_ocr`, `provenance_model: gpt-5-mini`). `plan_lint` 0 errors, 0 warnings.
- **Fix Tracker v42** (same URL; the live body was identical to the repo source apart from the publish
  wrapper: the Artifact read, then a Read of all 1,394 lines of the saved file): P3.27, P3.21, P3.4 (both rows)
  and P3.6 Fixed (`fixed: "2026-10-08"`, the date `7daed79` first shows them ticked; `ver: "Next release"`);
  P3.22 In progress; new row P3.30 (P3, Verified, `added: "2026-10-08"`); the lede names seventeen rows
  waiting for the next release; the In-progress note; two plain-language notes for Thomas (four fixes; P3.12 and
  P3.22 built and not yet passed, P3.30), naming no lawyer's topic; "Next"; `AS_AT` "8th Oct 2026, 11:45am" and
  `UPDATED`. 78 rows: 54 Fixed, 2 In progress, 16 Verified, 3 Blocked, 3 To be verified. Script syntax-checked
  with Node; no render check (data and text only).
- **`docs/prepilot-fixes/PARALLEL_BATCH_10.md` written: the brief for Session 42.** Five agents in worktrees at
  $0 model spend: **A** measures, then builds, P3.12's decided lever; **B** P3.22's per-query retrieval check
  (live National Archives calls only if agreed, cap 150); **C** P4.3 measured and re-booked; **D** P3.10
  re-booked and P4.12 measured; **E** the `authorities` and `negcurrency` grader fixes and the sweep priced.
  **Merge E, A, then P3.12's re-run (6335 n=3, priced to the user first), then B, C, D.** FIX_PLAN's top order
  line points at the brief. The session scratchpad was re-copied to `evidence/seam/batch9/scratchpad_s41/`.

---

## Session 42 — 2026-10-08 — parallel batch 10: P3.12's lever built (re-run n=1, not met); P3.22 item 1 re-booked and met; P4.3, P3.10 and P4.12 re-booked ($1.17)

**Done:**
- **Ran `PARALLEL_BATCH_10.md` (user decisions at launch: A, B, C, D and E as set out; B up to 150 National
  Archives calls, agreed; merge order E, A, the sweep on the user's go-ahead, then B, C, D; the branch pushed
  after each clean merge).** Step 1's checks held at `7c3c6ac`: equal to `origin`; `main` at `a6b4a76`;
  `plan_status` 58 of 79, 2 in progress, 9 of 14; `plan_lint` 0, 0; the five rubric sha1s; 63 replay
  directories; the six test databases; no python process, port 8000 free, no pin file; baseline suite **2783**.
  `<INTEGRATOR_HEAD>` was `7c3c6ac`; no other session committed (checked before every merge and the fold).
- **Every worktree came up on `main` (`a6b4a76`) again**; each agent reset to its base.
- **Reviews** (each: the base contained, the note and diff read, the added lines grepped with
  `matter_grep.py`, the full suite on `lexchat_test`, the scratch compared with its main-checkout copy, one
  headline number re-run on the main checkout from a copy of the agent's script; for A and E also the
  integrator's revert on a scratch worktree, four single-site mutants of its own and, for A, the built wording
  screened):
  - **B (P3.22, notes only):** 134 National Archives calls (cap 150). `analyze.py` re-run from a copy:
    identical. Scratch 163 = 163. B also found an `authorities` gap (a link label holding a bracketed citation
    is not read as a link), relayed to E on the user's decision.
  - **D (P3.10, P4.12, notes only):** `p412_manager.py` and `p310_recount.py` re-run from repointed copies:
    identical. Scratch 27 = 27.
  - **C (P4.3, notes only):** `census.py`, `agg.py unused` and `dryrun_filter.py` re-run with
    `P43_SERVER_PY` on the main checkout: identical. Scratch 52 = 52.
  - **E (graders):** revert 225 lines (20 of 28 fail); of the integrator's 4 mutants the empty-words guard in
    `_p322_is_cited_judgment` survived, so E was sent back (`dc6b630`, a letterless-citation test); then 4 of 4
    caught, revert 21 of 29 fail. Merged `0444cac` (2812). Headline re-run on the merged tree: item 3 FAILs,
    sweep 1 0, sweep 2a 2 (r2 t6, r3 t7) = E. Scratch 203 = 203. E ran one pytest without
    `TEST_DATABASE_URL` (a 2-second create/drop on `lexchat_test`, no suite running then).
  - **A (P3.12):** revert 185 lines (23 fail); of the integrator's 4 mutants the "-ies" length guard in
    `_word_stems` survived, so A was sent back (`95603c2`). The integrator's screen (`b10_screenA.py`, built
    code, 28 texts) found 0 detector trips but two wording defects on an unlabelled unit ("the retrieved the
    Schedule"; a lower-case "the Schedule runs to" opening a sentence); **the user approved the wording with
    those two fixes** (`59e854e`), kept the MATCHED tail's last sentence, and took the bound, the fallback and
    the matched words as built. Re-checked: 4 of 4 mutants caught, revert 187 lines (24 fail), screen 0 trips.
    Merged `8b4469c` (2833). Headline re-run on the merged tree (`dryrun_b10.py` + `compare_b10.py` from a
    copy): identical, 16 of 16 MATCHED calls with 42-44 clean and byte-equal. Scratch 92 = 92.
- **Seam before the sweep (user decision; $0.1767):** the default `seam_replay worker` draw has no output cap
  and `chat_loop` retries an empty up to 3 times, which the integrator first priced wrongly as capped; the user
  chose one draw each, then the second only under $0.30. `seam_6335_r2_matched.json` DELIVERED 2 of 2;
  `seam_6335_r2_tail.json` PARTIAL 2 of 2; no draw called the Schedule not retrieved.
- **The sweep (`wave4_b10_sweep`, head `8b4469c`, build `v2026.09.3-160-g8b4469c`, cap $1.90):** `replay
  check` ($0.000984), `replay pin`, uvicorn (PID 19312) and the keep-awake helper (PID 3256) by
  `Start-Process -PassThru`. **Rep 1 cost $0.99** (turn 1 $0.50: a Worker heavy empty capped by P4.10 at
  30,719 tokens, re-delegated; turn 7 $0.12), so a second such rep could pass the cap: the replay process was
  stopped at rep 2 turn 1 (the server cancelled the request) and the user chose to stop there. `replay
  restore`, both processes stopped by PID; no pin file, no python process, port 8000 free.
- **Graded and hand-read** (gitignored `evidence/rubrics/handread_wave4_b10_sweep.md`): the exit-1 set 0
  except `commencements` (no graded session); `schedules` OK 2; `negcurrency`, `footer_echo`, `halts`, `lost`
  0. **P3.12 not met:** rep 1's turn 7 SHALLOW, not DELIVERED by hand; the route handed the headings and
  42-44 verbatim, and the Worker wrote 43(6) alone under a broad brief; no "not retrieved".
- **Merged B `7e2339b`, C `ad5e064`, D `4fa0bb8`** (notes only; `git diff 8b4469c HEAD -- server_py` empty).
  All agent and scratch worktrees removed.
- **Decisions put to the user** (seven calls; all as recommended except where noted): A's wording with two
  fixes; the seam draws, then the corrected seam pricing (one each, then decide); the sweep at $1.90, then stop
  after rep 1; B's gap relayed to E; P3.22's item 1 re-booked and met on the existing columns; **P3.22 stays
  `[~]` until item 3 passes (the user's choice over ticking with a new row)**; the carrier watch line,
  `commencements`' title scope left, `p322.json` unchanged; P3.12 seam-first on rep 1's payload next; P4.3's
  deterministic bar and V4, the link half split out (P4.23), the `rail` grader, a display row (P4.24), the
  failed-turn rail as a watch on P4.5; P3.10's list-match bar and the ids lever; P4.12's L1 + L2' + L3 (gated),
  a deterministic bar, the title widened, lever (i) deferred.
- **Applied** (`64f0dec`): `fold_s42.py` (P3.12, P3.22, P4.3, P3.10, P4.12, P3.24, P3.6, P4.5 and P3.21
  annotated; P4.12's title widened; new **P4.23** and **P4.24**; the Bucket index; the top order line; 90 bold
  markers added). **`plan_lint` 0 errors, 0 warnings; `plan_status` 58 of 81 rows, 2 in progress, 9 of 14
  buckets.** CHANGELOG *Unreleased*; `docs/LEGAL_DATA_SOURCES.md` and CLAUDE.md (`docs_s42.py`);
  `docs/api/AUDIT_TRACE.md` unchanged (no new api call or shape). Suite **2833**.

**Surprises / deviations:**
- **P3.12's gap moved again, from retrieval to composition.** The route now hands paragraphs 42-44 verbatim
  (first time live), and the Worker wrote one sub-paragraph of them under a broad brief; on the seam the same
  new block delivered 2 of 2. Whether it is the draw or the payload is Session 43's first question.
- **The reworded summary tail alone removes "not retrieved"** (seam 0 of 4, live 0 of 1).
- **The default Worker seam is uncapped and retried** (no `max_tokens`, `chat_loop`'s three attempts): a
  runaway draw can cost about $2.30, not the $0.37 a capped `--as-sent` draw costs. Priced to the user before
  drawing.
- **A rep can cost 1.6 times the stored maximum** from a capped Worker runaway alone ($0.99 against $0.61):
  the per-command cap covered it only because the process was stopped by hand between reps.
- **P3.22's drops were query choice, settled by same-query pairs** (134 calls), and a second genuine item-3
  failure was hidden by a grader that could not read a bracketed citation inside a link label.
- **P4.3's unused-source rate is mostly one fall-back line**, not the model declining to cite; **P3.10's halt
  premise no longer holds** (0 of 12), but every dependent step re-derives its list.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at `a6b4a76`.
2833 tests. Session spend **$1.17** (seams $0.18, the sweep's rep 1 $0.99, the probe $0.001; rep 2's turn-1
spend unrecorded, a few cents). Agents $0 in model spend; 134 National Archives calls (B).

---

## Session 42 — handover for Session 43 (2026-10-08)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 42"):**
1. **P1: P3.12, seam-first.** Redraw `wave4_b10_sweep/6335_rep1.json` turn 7 (the Worker delegation;
   `seam_replay worker --run <file> --turn 7 --delegation <n> --reps 1`, about $0.05 a draw, uncapped: price it
   at the runaway case, about $2.30) to tell whether 43(6)-only is the draw or the payload; compare with
   `seam_6335_r2_matched.json` (DELIVERED 2 of 2). Then a $0 lever if the payload is the cause (for example the
   block naming the paragraphs it carries, or the brief), then 6335 n=3 priced (stored reps $0.57-0.99).
2. **P2:** P4.12's build (L1 + L2' + L3, gated; deterministic) and P4.3's V4 build with the `rail` grader
   (deterministic), both $0; P3.10's ids line (wording to the user) then its replay (about $4-5, priced
   first); P4.23 measure first ($0); P3.22's item 3 (measure first: is naming an out-of-corpus authority as if
   read a prompt, a summary or a link-label shape?); P3.4's research-mode follow-up; P3.20 last.
3. **P3:** P4.24, P4.8, P4.20, P4.22, P3.26, P3.28, P3.29, P3.30, P3.14, P4.9, P5.4's other leads, P0.7, TODO
   B6.

**Watch items carried:** P3.12's turn-1 Worker runaway in `wave4_b10_sweep` rep 1 ($0.38); P3.22's carrier
out of the first three on 6 of 14 queries; the failed-turn rail (P4.5); `commencements`' title scope (read
export turn 7 by hand); `negcurrency`'s definitional false positive (`wave0_conv` 6341 r1 t8); and Session 41's
(P3.27's conjoined limit clause, P3.21's omitted "wholly", P3.4's lost 6378 rep, P3.24's three).

**Decisions open with the user (carried):** sending the lawyer pack (unblocks P3.2, P3.3, P3.17; confirms
P3.22's 6363 list); sending SCTS the note (P3.20); D23; deploying `v2026.09.3`; telling the eval-harness owner
about schema v6 and the new `api_calls` and request keys; D19; the next cut (`v2026.10.1`: the seventeen rows
already "Next release"); D20, D21/D22; batch 1's three items; the p37_6373 substitution; the Fix Tracker when
asked (if asked: new rows P4.23, P2, and P4.24, P3, both `added` 2026-10-08, Verified; no row's status changes:
P3.12 and P3.22 stay In progress).

**Machine state:** no server, no pin file, no replay running, no worktree but the main checkout. **64 replay
directories** (new: `wave4_b10_sweep`, 1 file). Rubrics unchanged; hand-read `handread_wave4_b10_sweep.md`.
Agents' scratch in `evidence/seam/batch10/{A,B,C,D,E}/`, the session scratchpad in
`batch10/scratchpad_s42/` (integrator tools: `review_branch.sh`, `grade_b8.sh`, `route_trace.py` (now prints
the heading-list label), `b10_mutA.py`, `b10_mutE.py`, `b10_screenA.py`, `fold_s42.py`, `docs_s42.py`,
`s42_decisions.md`).

**Addendum to Session 42 (2026-10-08, at the user's request: "make sure we're not going to lose any pertinent
information" and "update the tracker"). The handover above stands.**
- **Preserved** (`preserve_s42.py`): findings that lived only in agents' notes or the integrator's scratch,
  written onto the rows a future session reads: **P3.12** (`depth --seams` strips the whole PROVISION FETCHED BY
  CODE block, so read the handover with `route_trace.py` in `scratchpad_s42/`; `corpus`'s leak markers match the
  block's literal opener and closer; A's seam payloads; the two live summarised calls on a 161,434-character
  schedule with no saved lookup; the brief-plus-query matching option); **P3.10** (P3.7's `MAX_ROUTED_LOOKUPS` = 5
  is below the 6-8 instruments of 6374's list; about 750 LEX calls over the stored plans; the CONTEXT sentence the
  ids line must not contradict; the regex's missed form); **P4.3** (the synthetic input forms in
  `notes/batch10_C.md` section 4; V4 changes what `turns_source_fallback` counts; C's `reader.py`); **P4.12** (no
  retry after a clean-stop (c) empty ever answered, 0 of 12, not booked; `lostcost` prints no `react_turn`);
  **P4.23** (6354 on Gemini kept 0 of 6, n=1); **P3.22** (the shared `MD_LINK` keeps the bracketed-label gap for
  every other grader; `p322.json` has no `parties`/`citations`); **P3.24** (the definitional false positive is
  not fixed); and in the **Verification protocol** a third seam lesson: the default Worker seam draw is uncapped
  and retried (about $2.30 a runaway), and a hot sweep is stopped by stopping `replay run` between reps.
  `plan_lint` 0 errors, 0 warnings; `plan_status` 58 of 81, 9 of 14.
- **Fix Tracker v43** (same URL; the live body was identical to the repo source apart from the publish wrapper:
  the Artifact read, then a Read of all 1,425 lines of the saved file): new rows **P4.23** (P2, Verified, src
  T & R, Thomas ref 7, `added: "2026-09-18"`, the day his action 7 was first listed here, by the T & R rule) and
  **P4.24** (P3, Verified, `added: "2026-10-08"`); **P4.3** re-labelled to the rail half (src R, no Thomas ref,
  since action 7 moved to P4.23); **P3.10** and **P4.12** re-labelled to their re-booked levers; the In-progress
  note; three plain-language Session 42 notes for Thomas, naming no lawyer's topic; "Next"; `AS_AT` "8th Oct
  2026, 3:05pm" and `UPDATED`. 80 rows: 54 Fixed, 2 In progress, 18 Verified, 3 Blocked, 3 To be verified. The
  script passes `node --check` (no layout change, so no render check). Source edited by `tracker_v43.py`.

**Second addendum to Session 42 (2026-10-08): SCTS's permission.** The user reports that SCTS agreed, by phone, to our use of its judgments search; no conditions were given, and none of the other questions (rate or volume, change notice, attribution, date reliability) was answered. So P3.20's note-to-SCTS prerequisite is met and the carried decision "sending SCTS the note" is closed. **User decisions:** P3.20's measure-first step runs in Session 43 as a $0 parallel agent beside P3.12's seam check (a few capped live SCTS calls only if agreed at launch), the build after it; the whitelist request for `api.pa.web.scotcourts.gov.uk` and `www.scotcourts.gov.uk` was drafted for the user to send. Recorded on P3.20, FIX_PLAN's top order line and `docs/LEGAL_DATA_SOURCES.md` §3. The Fix Tracker's P3.20 and "Next" still say it waits on SCTS: correct them at the next tracker update.

**Third addendum to Session 42 (2026-10-08): the user's actions carried into Session 43.** (1) Ask SCTS for a one-line email confirming the permission given by phone (only the user's account records it today); save it under the gitignored evidence and cite it on P3.20 when it arrives. (2) Send the whitelist request for `api.pa.web.scotcourts.gov.uk` and `www.scotcourts.gov.uk` (HTTPS 443 outbound) to the target's administrator; the draft is `evidence/seam/batch10/scratchpad_s42/whitelist_request_scts.md` (gitignored, local). When the hosts are open, P3.20's build adds them to `NETWORK_AND_DEPENDENCIES.md` and `server_py/test_apis.ps1`. Carried as before: the lawyer pack; D23 (the National Archives licence); deploying `v2026.09.3`; telling the eval-harness owner; D19; the next cut. **Fix Tracker v44** (same URL, at the user's request): P3.20's row says SCTS has agreed; a dated note; "Next" now runs P3.20's first measurement beside P3.12; the stamp. 80 rows, no status change.

**Fourth addendum to Session 42 (2026-10-08, at the user's request: "provide a prompt to kick off the next piece of work ... a safe, multi-agent approach").** `docs/prepilot-fixes/PARALLEL_BATCH_11.md` written: the brief for Session 43. Five $0 agents in worktrees: **A** P3.12 (why rep 1's Worker wrote 43(6) alone; a candidate lever only if the integrator's seam draw on rep 1's payload points at the payload); **B** P4.12 built (L1 + L2' + L3, gated; deterministic); **C** P4.3's V4 and the `rail` grader (deterministic; merged after the sweep, since V4 changes `sources_kept`); **D** P3.20 measured (SCTS calls only if agreed, cap 150, at least 1 s apart); **E** P3.10's ids line, its two turn-4 scripts, the grading script and the sweep priced. Paid steps, each priced to the user first: P3.12's seam draw at the start, and one sweep (6335 n=3 and P3.10's scripts n=3) after B, A and E merge. FIX_PLAN's top order line points at the brief. `plan_lint` 0, 0.

**Fifth addendum to Session 42 (2026-10-08, at the user's request): a knowledge graph of legislation studied; P3.31 and P5.5 booked.** The user asked whether a stored graph of the relations between instruments would improve the legislation bot. **Verdict: not a general graph.** The one- and two-hop relations a question needs are already fetched live (P3.5, P3.21, P3.7), a stored copy adds a staleness risk of the B5 kind, and the published evidence for graph retrieval on statute questions is thin. The one relation with no live route is **made-under**, and the reverse question ("which SIs were made under s.N", 6340) needs a scan of every SI. **i.AI's Lex Graph was evaluated locally** (edge lists only; the pickled `core.zip` was not loaded) **and rejected as a base**: a 2025-05-02 snapshot ending at 2022, about 4,900 UKSIs and 1,075 SSIs against LEX's 220,000 instruments, "amendment" edges that are every citation in a footnote (12% point to an older instrument), and no enabling-power edge. Its code (MIT, archived) needs TNA's invitation-only dump; its parser runs on single live files, but its reference finder fed an SI preamble got 1 of 3 sampled right, and cannot match a "(Scotland) Act" title. The full numbers are on P3.31. **User decisions:** (1) **P3.31 booked as an experiment** (tracker P3): measure first ($0), then an extractor hand-checked on a sample, then a plain PostgreSQL table; if it does not improve the measured turns it goes `[-]` and another direction is taken (P3.30, P5.5). (2) **P5.5 booked: the user chases TNA's Legislation Data Team (data.legislation@nationalarchives.gov.uk) for the invitation-only bulk data and SPARQL**, both 401 on 2026-10-08; carried as a user action. P5.4's lead (a) gains a first look (recital present in 3 of 3 sampled; read `/made/data.xml`, since a revoked SI's revised XML dots it out) and stays open. Neither row is in batch 11; the handover above stands. `docs/LEGAL_DATA_SOURCES.md` updated. Fix Tracker not updated (not asked). `plan_lint` 0, 0; 58 of 83 rows.

**Sixth addendum to Session 42 (2026-10-08, at the user's request: "proceed with the experiment here"): P3.31 Steps 1 and 2.** $0 model spend; about 10,500 paced, read-only legislation.gov.uk reads from the dev machine (direct, so LEX's shared limit was not drawn on; the LEX proxy was checked to return an as-made XML byte for byte). **Step 1 GO:** 3 sessions, 6 turns, all reverse made-under questions, all three sessions FAIL. **Step 2:** new `tools/madeunder_probe.py` + 14 tests. On s.95 of the Social Security (Scotland) Act 2018 the store finds 37 of 37 SSIs with none wrong (hand-read; recall audited against legislation.gov.uk's loose text search), against 4 in the product's best stored run and 9 for legislation.gov.uk's exact-phrase search. On s.117 of the Education (Scotland) Act 1962, 0 of the 949 readable 1962-81 scans; 58% of those scans are image only, so 6340 stays open until OCR. Numbers and the parser findings are on P3.31. **Surprises:** pre-1987 SIs exist on legislation.gov.uk only as PDF scans, and most have no text layer; a revoked instrument's XML elides the preamble; legislation.gov.uk's own loose text search plus a preamble read per hit is a working live route at about 90 calls a question. **User decisions carried:** Step 3's scope (store contents, delivery to the target and refresh, OCR, the acceptance replay's price); installing Tesseract. P3.31 is `[~]`. Fix Tracker not updated (not asked).

**Seventh addendum to Session 42 (2026-10-08, evening): P3.31 raised to P1 and Step 3 built.** User decisions: severity P1; scope SSIs from 1999 (UK SIs from 1987 only after acceptance); a committed snapshot loaded into Postgres and refreshed daily through LEX's proxy; OCR deferred; the acceptance replay priced first. Built at $0: the `find_instruments_made_under` Worker tool, the store and its daily refresh, the forward-question fallback to a stored recital, the Manager limb and footer clause, the prompt rule; snapshot of 11,451 SSIs (448 KB). 2,945 tests pass. Details on P3.31. **Surprises:** the full suite jammed for half an hour, twice, because the forward fallback made existing unit tests open real DB connections from throwaway event loops (one left idle in transaction, blocking teardown's DROP TABLE); the lookup now waits until the record is loaded, and the suite runs in 25 s. asyncpg refused a date string even inside a CAST (CLAUDE.md's backup-restore trap, again). The Bash tool's heredocs turned a regex `\b` into a backspace byte twice; regex edits now go through a file. **Carried:** the acceptance replay (about $6.50, cap $10), awaiting the user's approval; P5.5; Tesseract. Fix Tracker not updated (not asked).

**Eighth addendum to Session 42 (2026-10-08, night): P3.31's acceptance MET and the row ticked.** User-approved replay at a $10 cap, `wave4_p331`, $5.54 (6383 n=3 $1.80, 6382 n=3 $2.86, 6340 n=3 $0.15, 6409 n=1 $0.73), on a port-8001 server at `7031642` (the port-8000 server and the existing pin belong to another session and were left alone; no `restore` run). Reverse made-under: the tool on 13 of 13 turns, the true count stated on every list-type turn, 37 of 37 on the Deep Research turn 3 of 3, and 6382's compound question answered (17 of the 37 carry a pound sign); forward: SSI 2024/311 confirmed 3 of 3; 0 of 13 made-under claims unverified; guards clean. New `tools/madeunder_grade.py`; P2.3's `retrieved_enabling` now reads the record's two routes (without it, 13 correct claims graded unverified). 2,946 tests pass. **Surprises:** the grader gap above; 2 of 3 6382 runs lost a Deep Research step to an empty completion (P4.12's shape, labelled correctly). **Carried:** UK SIs from 1987 (about 70,000 reads, 7 to 8 hours) on the user's decision; P5.5; Tesseract; whether to cut. 59 of 83 rows; B3 now has no open row but P3.28 and P4.22. Fix Tracker not updated (not asked).

**Session 42 addendum, 2026-10-09 (morning): data improvements booked; the tracker gains a Type column.** At the user's request, the suggestions that followed P3.31 are booked as P3.32 to P3.37, each typed "Data Improvement" on the tracker: an SI's own dates and procedure (P3.32), revocation of listed instruments (P3.33), a definitions index (P3.34, measure first), pre-1987 SIs (P3.35, Blocked on P5.5 or OCR), judgments citing a provision (P3.36, Blocked on D23's licence and SCTS's terms), and a general citation graph (P3.37, not recommended now). **Correction to what the user was told:** P3.32 was described as needing no extra harvest; the data is in the files the harvest downloads, but the harvester keeps only the title and recital, so it needs a further pass. The UK SI harvest for P3.31 runs on (about 80% at 07:20). Tracker v45: a Type column for every row (Bug, Issue, Feature, Data Improvement, Measurement), P3.31 Fixed, P5.5 and the six new rows added. 59 of 89 rows.


---

## Session 43 — 2026-10-08/09 — parallel batch 11: P4.12 done; P3.12, P3.10 and P4.3 built, not met; P3.20 measured and designed ($7.09)

**Done:**
- **Ran `PARALLEL_BATCH_11.md` (user decisions at launch: A, B, C, D and E as set out; D up to 150 SCTS calls,
  agreed; P3.12's two seam draws, agreed; merge order B, A, E, the sweep on the user's go-ahead, C, D; the
  branch pushed after each clean merge).** Step 1's checks held at `024e396`: equal to `origin`; `main` at
  `a6b4a76`; `plan_status` 58 of 81, 2 in progress, 9 of 14; `plan_lint` 0, 0; the five rubric sha1s; 64 replay
  directories; the six test databases; no python process, port 8000 free, no pin file; baseline suite **2833**.
  `<INTEGRATOR_HEAD>` was `024e396`. Every worktree came up on `main` again; each agent reset to its base.
- **P3.12's seam first ($0.0865):** `wave4_b10_sweep` rep 1's turn-7 payload as recorded, NOT DELIVERED 2 of 2
  (SHALLOW, PARTIAL): the payload was the cause; relayed to A, which then built its candidate.
- **Reviews** (each: the base contained, the note and diff read, the added lines grepped with `matter_grep.py`,
  the full suite on `lexchat_test`, a headline re-run from a copy of the agent's script, the scratch compared):
  - **A (P3.12):** revert 46 lines, 10 fail; the integrator's 5 mutants caught (the empty-number filter, the
    8-character cap, the singular branch, fail-soft, the route guard); the built wording screened, 0 trips over
    44 texts, rendered for "Schedule 5" and "the Schedule"; suite 2838; `dryrun_b11` + `compare_b11` identical
    (265 firing calls, 17 move in the tail only), and identical again on the merged tree; scratch 57 = 57. Seam
    on A's payloads ($0.1298): rep 1 with the tail DELIVERED 1 of 2; r2 1 of 1. **The user approved the
    wording as built.**
  - **B (P4.12):** revert 145 lines, 33 of 84 fail; the integrator's 8 mutants caught (the retry count, the
    `>=` boundary, the fail-soft helper, the gate in `should_retry_empty` and in `agent_core`, the cap, the idle
    counter, the Ollama forwarding); `worker_reports` excludes lost reports, so the gate is sound; suite 2872;
    `p412_dryrun` identical (10 attempts removed, about $2.30 and 36 minutes, 0 recoveries given up); scratch
    25 = 25. Merged `663bb7c` (2872); **ticked at the user's confirmation**.
  - **E (P3.10):** wiring revert 25 lines, 5 fail; the integrator's 8 mutants caught (the titled-form window,
    the 15-id cap, the dedupe, the body cut, the emptiness check, the gate, the lookup exclusion, the
    line-start anchor); the built line screened, 0 trips; suite 2856; `dryrun_p310` identical, and on the merged
    tree; scratch 31 = 31. **The user approved the wording and shape** (flagged steps only, not read by P3.7).
  - **C (P4.3):** the integrator's 9 mutants caught (the title and token length floors, the trailing
    boundary, the longer-title guard, the comma cleaning, the legislation fall-back guard, the `sub` token, the
    case look-ahead, the empty-text guard); suite 2890; scratch 407 = 407; after its merge `rebuild.py` on the
    merged tree gave 1,797 of 1,797 rows identical to C's.
  - **D (P3.20, notes only):** 134 SCTS calls (cap 150), every one through its door, all 200; nothing under
    `server_py/`; matter hits at FIX_PLAN's level; scratch 260 = 260.
- **Merged** B `663bb7c`, A `e958fad` (2877), E `9632b53` (2900), each `--no-ff` and pushed; after the sweep
  C `bccdb47` (3007, with the other session's P3.31 tests) and D `7b7c38b`, pushed. `git diff 9632b53 HEAD --
  server_py/src` held C's change and the other session's P3.31 work only; `agent_core.py`'s hunks were C's.
- **The sweep (`wave4_b11_sweep`, served by `9632b53`, build `v2026.09.3-185-g9632b53`; cap $7.50, raised to
  $9.00 by the user when `--max-spend` stopped `p310_6374` at n=2):** `replay check` ($0.001092), `replay pin`,
  uvicorn PID 18040 and the keep-awake helper PID 12372 by `Start-Process -PassThru`. 6335 n=3 $1.95;
  `p310_6374` n=3 $3.16; `p310_6383` n=3 $1.76; **$6.87**. 7 empty completions, all rate limits, all
  recovered. `replay restore`, PID 18040 stopped; no pin file, port 8000 free. Hand-read: gitignored
  `evidence/rubrics/handread_wave4_b11_sweep.md`. **P3.12 0 of 3** (rep 2 cited the right text under the
  wrong paragraph numbers); **P3.10** 7 of 7 lined steps cover their list with no search of their own, 6383 3 of
  3, but a gate miss on 6374 rep 2 dropped an instrument; `derivations`' one exit read as a false positive.
- **Decisions put to the user** (seven calls; all as recommended except the SCTS email: "nothing further"
  beyond the written confirmation already carried): the launch; A's and E's wording; the 6374 script (turn 4
  alone); the sweep and its cap; P4.12's tick; P3.20's design (two lists in `search_case_law`, the any-term
  fallback, `AdditionalDate` as the date of decision, a per-request cap and concurrency limit, no pypdf, the
  acceptance with controls, the grader in the build); P3.12 next (measure first at the seam); P3.10 next (the
  line on every step 2+); B's two choices kept; E's `lookup --routing` fix; P4.3's (ii) re-booked as the rail's
  own noise (met), lever R next for (iii), and C's smaller choices (new row **P4.25**).
- **Applied:** `fold_s43.py` (P3.12, P4.12 ticked, P4.3 and P3.10 to `[~]`, P3.20, new P4.25, the Bucket index,
  the top order line; 86 bold markers added) and the counts. **`plan_lint` 0 errors, 0 warnings;
  `plan_status` 60 of 90 rows, 4 in progress, 9 of 14 buckets.** `docs_s43.py`: CHANGELOG *Unreleased*,
  `AUDIT_TRACE.md` (the Manager's records under P4.12), CLAUDE.md (the LLM stream retry paragraph; P3.10's
  handover and P4.3's rail filter), `docs/LEGAL_DATA_SOURCES.md` §3 (D's re-probe and the date measurement).

**Surprises / deviations:**
- **Another session worked in the same checkout overnight.** It booked and built **P3.31** (raised to P1,
  ticked on its own sweep `wave4_p331` on a separate port-8001 server), booked P3.32 to P3.37 and P5.5, and
  published Fix Tracker v45, committing between this session's merges (`a6cee16`, `074a3f1..beffefc`, `20cd3a3`,
  `f429b27`). It left this session's server and pin alone, and no merge conflicted (it also edited
  `replay_report.py`, C's file; git merged them). **The `git_head` of `p310_6374_rep3` and `p310_6383_rep1-3`
  reads `beffefc`, the checkout's head when they ran; the code that served them is `9632b53`.**
- **A named tail moved the seam and not the live runs** (seam 1 of 2, live 0 of 3), and **one live Worker
  cited the right text under the wrong paragraph numbers**: P3.12's gap is now composition under a broad brief.
- **The P3.10 line worked wherever it fired** (7 of 7 steps worked on exactly the list, no search of their
  own); the only miss was a step the regex gate did not recognise.
- **V4 overshot P4.3's (ii)** because naming in words adds real sources the Manager then drops (P4.23's
  defect); re-booked on the rail's own noise.
- **`p310_6374` reps cost about 1.35 times their stored turn 4** (tool volume, no runaway), so the per-command
  cap stopped at n=2; the user raised the sweep cap.
- **SCTS:** a leading `+` is AND; rows can repeat; `additionalDate` is sound (36 of 40), and 2026-10-02's
  date "errors" were publication-year citations.

**State:** branch `fix/prepilot-defects`, pushed (head after this commit); `main` untouched at `a6b4a76`. 3007
tests. Session spend **$7.09** (P3.12 seams $0.2163, the sweep $6.87, the probe $0.001). Agents $0 in model
spend; 134 SCTS calls (D).

---

## Session 43 — handover for Session 44 (2026-10-09)

**Take next, by severity (FIX_PLAN's top order line, "end of Session 43"):**
1. **P1: P3.12, measure first at the seam** (about $0.20, priced to the user; the default Worker seam is
   uncapped, so price at the runaway case): A's `evidence/seam/batch11/A/seam_b11_rep1_r2brief.json` (rep 1 with
   r2's narrow brief, no lever) and `wave4_b11_sweep/6335_rep{1,2,3}.json` turn 7, to separate the brief, the
   block and the quick-lookup Worker's 2-5-sentence budget, and to size the wrong-pinpoint rate (rep 2). The
   candidates (not decided): code-written paragraph lines at the answer seam (P3.13's pattern); the concision
   rule relaxed for a code-fetched unit. (P3.31, raised to P1, was ticked by the other session.)
2. **P2:** P3.10's line on every step 2+ (user decision), then 6374 n=3 (about $3.20, priced first); P4.3's
   lever R (measure first, $0); **P3.20's build** (the design decided on its row, D's note section 5; its
   acceptance 6375 n=3 + 6370, 6380 n=1, about $4.90 to $8 and about 135 SCTS calls, priced first); P4.23
   (measure first); P3.22's item 3; P3.4's research-mode follow-up.
3. **P3:** `replay_report lookup --routing` read through `without_handover_line` (user decision); P4.24, P4.25,
   P4.8, P4.20, P4.22, P3.26, P3.28, P3.29, P3.30, P3.14, P4.9, P5.4's other leads, P0.7, TODO B6; P3.32 to
   P3.37 as their rows say.

**Watch items carried:** the wrong-pinpoint composition (P3.12, rep 2); `derivations` reading a description of
searches as a claim (`p310_6383` r3); `p310_6374`'s cost; a clean-stop (c) Manager empty still retried (P4.12,
unbooked); `source_filter_fallback`'s Efficiency-tab text to relabel (P4.3); `rail` to join the exit-1 set after
the next sweep (P4.3); and Session 42's (P3.22's carrier, the failed-turn rail, `commencements`' title scope,
`negcurrency`'s definitional false positive, P3.27, P3.21, P3.4, P3.24).

**Decisions open with the user (carried):** the written confirmation from SCTS; the whitelist request for
`api.pa.web.scotcourts.gov.uk` and `www.scotcourts.gov.uk`; the lawyer pack (unblocks P3.2, P3.3, P3.17); D23;
deploying `v2026.09.3`; telling the eval-harness owner about schema v6, the new `api_calls` and request keys,
and P4.12's Manager records; D19; the next cut (`v2026.10.1`); D20, D21/D22; batch 1's three items; the
p37_6373 substitution; the Fix Tracker when asked (if asked: P4.12 Fixed, `fixed` 2026-10-08, "Next release";
P3.10 and P4.3 In progress; new row P4.25, P3, Verified, `added` 2026-10-09; P3.20's text measured and designed;
the other session's v45 is the base).

**Machine state:** no server, no pin file, no replay running, no worktree but the main checkout. **66 replay
directories** (new: `wave4_b11_sweep`, 9 files; and the other session's `wave4_p331`). Hand-read
`handread_wave4_b11_sweep.md`. Agents' scratch in `evidence/seam/batch11/{A,B,C,D,E}/`, the session scratchpad
in `batch11/scratchpad_s43/` (integrator tools: `review_branch.sh`, `grade_b8.sh`, `route_trace.py`,
`s43_mut{A,B,C,E}.py`, `s43_screen{A,E}.py`, `dump_t7.py`, `r2s4.py`, `fold_s43.py`, `docs_s43.py`,
`s43_decisions.md`).

**Session 42 addendum, 2026-10-09 (midday): P3.31's UK SI extension done.** The overnight harvest tried about 108,400 UK SI numbers 1987-2026; the record now holds 86,744 instruments, 68,780 with parsed powers (snapshot `2026-10-09.1`, 4.2 MB, committed), and the daily refresh reads `new/uksi`. A hand-check of 200 UK SIs found 199 with the right Act and four with incomplete or misfiled provisions, all fixed. **Surprises:** the offline re-parse step had been throwing away every anaphor the fetch resolved, including 67 SSIs in the snapshot committed on 8 October (not deployed); caught by its flag counts, fixed and pinned by a test. UK SIs before 2020 lean heavily on "that section" pointing back to a European Communities Act designation (4,429 instruments under s.2). legislation.gov.uk publishes about 40% of 1987-2008 UK SI numbers not at all (local instruments). 3,017 tests pass. Fix Tracker not updated (P3.31's tracker label still says UK SIs are being added).

**Session 42 addendum, 2026-10-09 (afternoon): a second round of data improvements booked, P3.38 to P3.44** (user decision; each typed "Data Improvement" on the tracker): recent instruments LEX does not hold read from legislation.gov.uk (P3.38) and point-in-time versions (P3.39), recommended first; explanatory and policy notes (P3.40), provision-level amendments (P3.41) and provision-level extent (P3.42); statutory guidance, measure first (P3.43); the Welsh and NI series, low priority (P3.44). All measure first, $0. 60 of 97 rows (Session 43's batch 11 ran beside this work on the same branch; its top order line now names the second round). Tracker v46.

**Session 42 addendum, 2026-10-09 (afternoon, later): the data improvements mapped onto the open rows** (user decision). P5.4 ticked (every lead answered or carried: (a) by P3.31's harvest, (b) by P3.39, (c) at P3.21, (d) by P3.12's route; no whitelist entry needed). P3.30 re-scoped onto the made-under record (only search-result rows remain). Data routes noted on P4.24 (titles from the record), P3.12 (exact schedule paragraphs through the proxy) and P3.28 (removals by effect type). P3.26 paired with P3.42. P4.22 raised to P2, because P3.31 makes enabling-power blocks common. 61 of 97 rows. Fix Tracker not updated (P5.4's status and P4.22's severity change there when the user asks).

**Session 42 addendum, 2026-10-09 (afternoon, last): data-improvement batch 1 written and booked** (user decision, after asking whether to re-plan with the data improvements in mind). `DATA_IMPROVEMENT_BATCH_1.md`: four $0 notes-only agents (A: P3.38, P3.39; B: P3.41, P3.28, up to 60 LEX calls if agreed; C: P3.34, P3.43; D: the shared harvest for P3.32, P3.33 and P3.42 with P3.26, P3.12's paragraph route, P3.30 and P4.24, up to 200 legislation.gov.uk reads if agreed). It reuses batch 11's rules, lessons and setup by reference, writes no product code, and may run beside a defect batch. Booked on Session 43's order line. The re-plan stops there by design: the defect queue's by-severity order is unchanged until the measurements say where the data rows belong.

---

## Handover for Session 44 (merged, 2026-10-09) — read this one

**Two sessions worked this branch on 8-9 October** in one checkout: Session 43 ran batch 11 (its entry and handover above), and a second session, recorded as Session 42's addenda, built **P3.31** (the made-under record, raised to P1, done; extended to UK SIs 1987-2026, 86,744 instruments) and booked the data improvements **P3.32 to P3.44**, ticked **P5.4**, raised **P4.22** to P2 and mapped the data routes onto open rows (its addenda above, after Session 43's handover). **At the user's request the two strands are merged here, and from Session 44 one session works the branch at a time.** This handover supersedes Session 43's "Take next" list and the addenda's booking of `DATA_IMPROVEMENT_BATCH_1.md`; their watch items and carried decisions stand.

**Take next: run `docs/prepilot-fixes/PARALLEL_BATCH_12.md`** (seven agents, all $0; the integrator's paid steps each priced first: P3.12's seams about $0.20, P3.10's 6374 n=3 about $3.20, P3.20's acceptance about $4.90 to $8). By severity: **P1** P3.12 (measure first at the seam; the exact-paragraph route probed); **P2** P3.10's line on every step 2+, P3.20's build, P4.3's lever R, P4.23, P3.22's item 3, P3.4's follow-up, P4.22; the data measurements (P3.34, P3.38 to P3.43, the shared harvest for P3.32, P3.33 and P3.42 with P3.26, P3.28, P3.30, P4.24) beside them, notes only. **P3** the rest, after.

**State:** branch `fix/prepilot-defects` pushed; `main` at `a6b4a76`; `plan_status` 61 of 97, 4 in progress, 9 of 14; `plan_lint` 0; 3,017 tests; 66 replay directories; no server, no pin, no worktree but the main checkout. **Fix Tracker v47** (P5.4 Fixed, P4.22 at P2, the re-plan note, Next = batch 12). **The second session's working scripts** (harvest, re-parse, title, snapshot, smoke, tracker and plan scripts; the Lex Graph probes) are in the gitignored `evidence/seam/madeunder_s42b/`; the harvest files in `evidence/madeunder/`. **Lasting docs updated for P3.31:** CHANGELOG *Unreleased*, CLAUDE.md (the Worker notes), `docs/LEGAL_DATA_SOURCES.md` (the enabling-power gap), and the local `external-apis` (legislation.gov.uk routes) and `repo-map` skills.

**Carried, the user's:** SCTS's written confirmation and whitelist request; the lawyer pack; D23; P5.5 (the National Archives' bulk data); deploying `v2026.09.3`; the eval-harness owner; D19; the next cut (`v2026.10.1`, which would now also carry P3.31 and P4.12); Tesseract (P3.35); and Session 43's other carried items.

## Session 44 — 2026-10-09 — parallel batch 12: P3.10, P3.20, P3.22, P4.3, P4.22 and P4.24 done; P3.12 built, not met; the data rows sized ($14.11)

**Done:**
- **Ran `PARALLEL_BATCH_12.md` (user decisions at launch: A to G as set out; live reads A up to 20, C up to 40
  SCTS, G up to 60 LEX and 200 legislation.gov.uk, agreed; P3.12's seam draws, agreed; merge order B, A, E, C,
  D, F, G, the branch pushed after each clean merge).** The session was opened with a stale prompt for batch 1
  (Session 33's); the state check found batch 1 merged on 2026-09-29 and the user redirected to batch 12. Step
  1's checks held at `a99e4d4`: equal to `origin`; `main` at `a6b4a76`; `plan_status` 61 of 97, 4 in progress, 9
  of 14; `plan_lint` 0, 0; 66 replay directories; no python process, port 8000 free, no pin file; test databases
  `_f` and `_g` created; baseline suite **3,017** (`python -m pytest -q`). Every worktree came up on `main`
  again; each agent reset to `a99e4d4`. The shared brief sections (batch 11's rules, lessons and setup with the
  substitutions, batch 12's lessons and decisions, the data-improvement sections) were generated verbatim into
  the gitignored `evidence/seam/batch12/briefs/` and each agent read them from there.
- **P3.12's seams ($0.9909 in all; `seam_replay worker`, outputs in the gitignored
  `evidence/seam/batch12/integrator/`):**
  - **Default seam (4 draws, $0.1866):** every draw named 43 and 44, 3 of 4 named 42, so the stored shortfall
    did not reproduce.
  - **`--as-sent --at-rev recorded --date recorded --max-tokens 32000` (8 draws, $0.3677):** 42 dropped on rep 1
    and rep 3 (44 too on rep 3), rep 2 delivered 2 of 2. Two pairs were byte-identical (provider reuse), so the
    effective n was 4. Rep 3 with only " for Scotland" removed from the brief gave every sub-paragraph of 42-44
    (1 answer, 1 tool call).
  - **A's Worker-prompt sentence W1 swapped into the same payloads, plus rep 1 without " for Scotland" and a
    first-round probe (12 calls, $0.4366):** W1 fixed rep 3 in 1 of 2 and left rep 1 unchanged (2 identical);
    rep 1 without the phrase gave every sub-paragraph; the first round was unchanged (2 searches both sides).
  - **The user chose code lines at the answer seam (P3.13's pattern); W1 was reverted.**
- **Reviews** (each: the base contained; the note and diff read; added lines grepped with `review_branch.sh`;
  my own single-site mutants, one per guard, on the agent's worktree and test database; the full suite on
  `lexchat_test` after each merge):
  - **B (P3.10):** revert 29 lines, 7 fail; integrator mutants 6 of 7, the survivor (the cap boundary,
    `more > 0` to `more > 1`) then caught by a test of mine (`6f4660d`). The user's two changes applied
    (`57ce30c`): the limit folded into the condition, the cap 15 to 40; screened with the built code, 0 trips
    over 13 renderings. Suite 3,015 (the gate's 2 tests went with it).
  - **E (P4.22, then P3.4's follow-up and the hybrid line):** revert 32 lines, 23 of 29 fail; integrator
    mutants 10 of 10 on `_bare_tag`, then 6 of 6 on the P3.4 commits. Merged in two parts (`ddda3d0` at `8ad6ba3`;
    `16227f1`). Suites 3,044 and 3,304.
  - **C (P3.20):** integrator mutants 12 of 14; the survivors (a reported total below the rows; real fetches
    counted toward the PDF cap) got tests from C (`b5cbc3f`). Synthetic "Widget" fixtures only. Merged `df43d1c`,
    suite 3,163.
  - **A (P3.12):** integrator mutants 9 of 10; the survivor (the restatement threshold, 0.6 to 0.95) got a
    boundary test from A (`8ed478b`), which also catches 0.3. Merged `f971ff2`, suite 3,216.
  - **D (P4.3 lever R, then P4.24):** integrator mutants 10 of 10 on R and 10 of 10 on P4.24. The merge
    conflicted in `run_worker_agent` (A's handed-paragraph recorder and D's lookup-title wrapper around the same
    `run_worker_tool` call); resolved by keeping both, D's `_run_tool` wrapping `_run_tool_inner`, which records
    A's paragraphs. Merged `ab12a88`, suite **3,379**.
  - **F and G (notes only):** diffs touch only the note; G's logs hold 47 LEX and 155 legislation.gov.uk calls,
    A's 12 (10 LEX proxy, 2 direct), C's 27 SCTS. F's census check re-run (9 of 9 present). Merged `9d9d686`,
    `3291b4d`.
- **The sweeps (pinned Gemini; `replay check`, `replay pin`, uvicorn and the keep-awake helper by
  `Start-Process -PassThru`; `replay restore` and both processes stopped after each block; no commit while a
  replay ran):**
  - **P3.10, `wave4_b12_p310` (6374 n=3 scripted, served by `57ce30c`, $3.0394):** by hand, every dependent
    step covers its list (3 of 3), 0 own searches, 0 halts, `sources_kept` 25.7 against 22.2; Orders cited per
    answer 9, 10, 9. **Ticked.** Watch item: discovery steps stopped searching too (mean 0.14 against 7.8).
  - **P3.20, `wave4_b12_p320` (6375 n=3, 6370 and 6380 n=1, served by `df43d1c` with `SCTS_CASELAW_ENABLED=true`
    added to the dev box's `server_py/.env` and removed after, $5.4538, 108 SCTS calls):** `replay_report scts`
    cites a returned Scottish judgment in 3 of 3 reps (5 of 6 turns), OLD_SENTENCE 0; controls clean; the
    exit-1 graders pass. English authority by hand: reps 1 and 3 pass, rep 2 borderline (recorded on P3.3).
    **Ticked; deploys only after the whitelist.** The background command exited 1 although both logs show every
    run written and ok (not traced).
  - **P3.4's after-column, `wave4_b12_p34r` (Research mode, scripts `p46_6335` and `p46_6385` n=3, `p46_6350`
    n=1, served by `16227f1`, $2.8420):** E's grader 15 of 26 PASS (before 0 of 36 by hand); delegated turns 15
    of 16, every brief naming Scotland; the 10 failures are follow-ups answered from the conversation. **Met on
    delegated turns (user decision).**
  - **P3.12, `wave4_b12_p312` (6335 n=3, served by `16227f1`, $1.7811):** DELIVERED 0 of 3 by hand (`depth`
    PARTIAL 3). The line fired in reps 1 and 3 and put 44 back, quoting 44(1)'s conditions of application, not
    44(5); rep 2 cited "Paragraphs 40-43" and never reached 43(5) or 43(6).
- **Decisions put to the user** (all as recommended): the launch; the P3.12 draws twice and the lever; P3.10's
  wording, cap, scope, run and tick; E's words, the summariser row, P3.22's split, P3.4's build, wording,
  consulted scope, hybrid line, run and bar; C's wording, settings, run and tick; P4.3 merged with P4.24 and
  ticked; A's option B, the sub-paragraph follow-up, run and other items; F's and G's rows; the smaller items.
- **Folded into FIX_PLAN.md** (byte script `fold_s44.py` in the session scratch; LF kept, as the file is LF in
  index and tree): ticked **P3.10, P3.20, P3.22, P4.3, P4.22, P4.24**; annotated P3.12, P3.4, P3.3, P4.23,
  P3.38, P3.39, P3.34, P3.28, P3.26, P3.33, P3.32, P3.42; dropped **P3.30, P3.41, P3.43** (P3.41 moved to the
  no-bucket line: a dropped row in a bucket keeps it open under `bucket_state`); new rows **P3.45** (P1),
  **P3.46**, **P4.26**, **P4.27**; the bucket index; a new top order line. `plan_lint` 0, 0; `plan_status` **67
  of 101, 1 in progress, 9 of 14** (B8 now partial).
- **Spend: $14.11** (seams $0.9909; sweeps $3.0394 + $5.4538 + $2.8420 + $1.7811; three `replay check` probes
  $0.0033). Agents $0 in model spend.

**Surprises:**
- **The default Worker seam does not reproduce a composition shortfall that `--as-sent` does** (P3.12: 0 of 4
  against 2 of 3 payloads). For a Worker-facing lever, draw `--as-sent --at-rev recorded --date recorded`.
- **A brief phrase the Manager writes by rule (" for Scotland", P3.4) narrowed the Worker's report**, and a
  Worker-side sentence only half undid it.
- **The restored line can quote the wrong sub-paragraph**: "the opening operative sub-paragraph" took 44(1)'s
  conditions of application, because only a bare "This paragraph applies to X." is skipped.
- **A mutant harness that names a missing test file reports every mutant CAUGHT** (pytest exits non-zero on the
  path). Check the control run passes before reading any verdict (it happened here on D's first run).
- **Text reads keep the body in `full_text`; `legislation.text` is always empty** (F's first pass read every
  stored text as empty). Read `full_text` in any grader of `get_legislation_text` results.
- **A summariser invents case citations** (50 of 5,615 stored summaries; P3.45, P1).

## Session 44 — handover for Session 45 (2026-10-09)

**One session works the branch at a time.** Read this handover, then FIX_PLAN's top order line ("end of Session
44"). A brief for the next batch is not written yet; write it from the order line if the user asks for a
parallel batch.

**Take next, by severity:**
1. **P1: P3.45** (the summariser's invented case citations): measure first ($0) over every stored summary, then
   the code check (drop or flag a citation the raw source lacks).
2. **P1: P3.12:** skip an application line with conditions as well as a bare one (the 44(1) case); then the
   sub-paragraph line for a partly cited paragraph (prototype 2 of 4 to DELIVERED), measured first; hand over the
   paragraphs that cut when another named one fails; widen `depth`'s 42 pattern; then 6335 n=3 (about $1.80),
   priced first. Iterate at `--as-sent` for anything Worker-facing.
3. **P2:** P3.38's build (trigger and acceptance on its row; the regnal-id 404 and the exact-paragraph route
   noted there); P4.23's linker (decided on its row); P3.46's code note (wording to the user); P3.28 (both
   levers); P3.34's corpus-wide definition search, measured first.
4. **P3:** P3.26 with "N.I."; P3.33 after P3.28; P4.24's search-hit heading title; P4.25, P4.26, P4.27; and
   the rest of the order line.

**State:** branch `fix/prepilot-defects` pushed (this handover's commit); `main` at `a6b4a76`; `plan_status` 67
of 101, 1 in progress, 9 of 14; `plan_lint` 0; **3,379 tests**; **70 replay directories** (`wave4_b12_p310`,
`_p320`, `_p34r`, `_p312` new); no server, no pin, the dev box's `.env` restored (no `SCTS_CASELAW_ENABLED`);
the seven agent worktrees under `.claude/worktrees/` are merged and can be removed. Integrator scratch
(mutant scripts, the fold, the decision record `s44_decisions.md`, suites) is copied to the gitignored
`evidence/seam/batch12/scratchpad_s44/`; draws and grades are in `evidence/seam/batch12/integrator/`.

**Watch items:** P3.10's discovery steps that stop searching; P3.4's follow-up turns that do not restate the
jurisdiction; P3.20's rep 2 (on P3.3); P4.3's three bars re-graded on the next sweep; `rail` to join the exit-1
set after it.

**Carried, the user's:** the SCTS whitelist request (P3.20 is built but off until both hosts are whitelisted;
then `NETWORK_AND_DEPENDENCIES.md`, `test_apis.ps1`, the offline bundle's pdfplumber and the lasting docs) and
SCTS's written confirmation; the lawyer pack (P3.2, P3.3, P3.17); D23; P5.5; deploying `v2026.09.3`; the
eval-harness owner; D19; the next cut (`v2026.10.1`, which would now carry P3.31, P4.12 and this batch); Tesseract
(P3.35); the Fix Tracker (v47 is the base; not updated this session).

**Addendum to Session 44 (2026-10-09, evening, at the user's request: "make sure we're not going to lose any
pertinent information ... update the tracker ... provide a prompt to kick off the next piece of work").**
- **Session 45 runs `docs/prepilot-fixes/PARALLEL_BATCH_13.md`**, which supersedes "A brief for the next batch is not
  written yet" in the handover above. Seven $0 agents: A P3.45 (P1), B P3.12 (P1), C P3.38's build, D P4.23's
  linker, E P3.46, F P3.28 then P3.26, G P3.34's measurement (notes only). Merge order A, B, C, D, E, F, G.
- **Lasting docs updated for batch 12:** CHANGELOG *Unreleased* (P3.4's research-mode rule and the hybrid line,
  P3.10, P3.12's lines, P3.20, P3.22, P4.3's lever R, P4.22, P4.24); CLAUDE.md's Worker notes (P3.10, P4.3 with
  P4.24, P3.12's answer seam, P3.20 in the case-law notes, the external-API count); `docs/LEGAL_DATA_SOURCES.md`
  (SCTS in the table of what we call, and §3); `docs/api/AUDIT_TRACE.md` (P3.20's `api_calls` and `raw_result`
  keys); the local `external-apis` and `repo-map` skills.
- **The hand-reads behind every Session 44 number** are in the gitignored `evidence/rubrics/handread_batch12.md`;
  the session's scripts (mutants, fold, docs, tracker, the brief generator `mkcommon.py`) in
  `evidence/seam/batch12/scratchpad_s44/`.
- **Fix Tracker v48** (user request; repo source byte-identical to the live body before the edit, all 1,570 lines
  read; `tracker_v48.py`): P3.10, P3.20, P3.22, P4.3, P4.22, P4.24 Fixed (`fixed: "2026-10-09"`, Next release; the
  lede now lists twenty-six Next-release rows); P3.45 (P1), P3.46, P4.26, P4.27 added (Verified); P3.30, P3.41,
  P3.43 removed and named in the Not-listed line (the tracker has no Dropped status); P3.32, P3.39, P3.42 marked
  parked in their text; P3.12 the only In-progress row; a plain-language note and "Next"; AS_AT "9th Oct 2026,
  7:05pm". 97 rows: 63 Fixed, 1 In progress, 23 Verified, 5 Blocked, 5 To be verified. `node --check` only.
- **For the user:** P3.12's tracker severity is P2 while the briefs since batch 11 have called it P1; left as P2.

## Session 45 — 2026-10-09/10 — parallel batch 13: P3.45, P4.23 and P3.26 done; P3.12 DELIVERED 2 of 3; P3.38, P3.46 and P3.28 built ($1.95)

**Done:**
- **Ran `PARALLEL_BATCH_13.md` (user decisions at launch: A to G as set out; live reads C up to 40 LEX proxy and G
  up to 30 LEX, agreed; merge order A, B, C, D, E, F, G; the branch pushed after each clean merge).** Step 1's
  checks held at `1889abb`: equal to `origin`; `main` at `a6b4a76`; `plan_status` 67 of 101, 1 in progress, 9 of
  14; `plan_lint` 0, 0; 70 replay directories; no python process, port 8000 free, no pin file; test databases
  `lexchat_test_a` to `_g` present; baseline suite **3,379** (`python -m pytest -q`). The shared brief sections
  (batch 11's rules, lessons and setup with batch 13's substitutions, batch 12's and batch 13's lessons, the
  decided list, the batch table and each agent's section) were generated by `mkcommon13.py` into the gitignored
  `evidence/seam/batch13/briefs/`; each agent read them from there.
- **The first launch failed: the disk was full.** C: had 4.6 GB free and each worktree takes about 1.7 GB (the
  tracked `binaries/offline_dependencies.zip.part*`). The seven batch 12 worktrees were removed (merged, clean,
  their scratch already in the main checkout bar one `.pyc`; `wt_diff.py`) and the seven stub branches the failed
  launch left at `main` deleted; 16 GB free, 4.9 GB with the seven new worktrees. Every worktree came up on
  `main`; each agent reset to `1889abb`.
- **Reviews** (each: the base contained; the note and diff read; added lines grepped with `review_branch.sh`; my
  own single-site mutants, one per guard, with the control run first, on the agent's worktree and test database;
  new wording rendered with the built code and screened with `b9_screen`; the full suite on `lexchat_test` after
  each merge):
  - **A (P3.45):** integrator mutants 13 of 15; the two survivors (a later sentence of a list item dropped the
    whole item; the outer fail-soft) got tests from A (`27fb782`), then 15 of 15. Dry run re-run: 37 of 5,808
    summaries move, `diffs.txt` identical; the first diffs read (authorities the search never returned).
  - **B (P3.12):** integrator mutants 14 of 15; the survivor (the sub-paragraph line's position) got a test from B
    (`a622ad6`); B1 built at the user's decision (`52a8f3c`); then 20 of 20 including five on B1's guards. The
    partial-cut clause screened, 0 trips.
  - **C (P3.38):** integrator mutants 18 of 18; 20 live proxy calls in the log (200, 404, 502). Screen over 117
    built renderings: 0 trips on the answer detectors; the schedule detectors match "index lacks" and "did not
    complete", which `schedules` reads only in clauses naming the unit asked about (caveat). C5 and C6 applied by C
    at the user's decision (`c45eb81`).
  - **D (P4.23):** integrator mutants 15 of 15; `dry423.py` re-run: 79 links in 71 turns, list identical.
  - **E (P3.46):** integrator mutants 16 of 16; the note screened over 13 built renderings, 0 trips.
  - **F (P3.28, P3.26):** integrator mutants 13 of 13; the graders fall back to the old token count on the new
    shape (0 verdicts move).
  - **G (P3.34):** note only; 23 LEX calls in the log, all 200.
- **Merged** A `b32bc73` (3,458), B `b46681e` (3,536), C `e6e592b` (3,621), D `2a936fd` (3,700), E `0e4f77a`
  (3,780), F `84f0313` (3,872; conflict in `search_scope.py`'s imports, C's beside F's, both kept), G `ed7d722`
  (3,872). **Not pushed:** the push after A's merge was denied by the auto-mode classifier although the user had
  agreed; the branch is ahead of `origin` by this session's commits until the user pushes.
- **Decisions put to the user** (`evidence/seam/batch13/integrator/decision_sheet.md`): every agent's recommended
  option (A1-A5, B2-B4, C1-C4, C7-C8, D1-D6, E2-E3, E5, F2-F7, G1-G6); B1 paragraph 44's line quotes (5) then (1);
  the wording approved (B's clause, C's texts with C5 and C6, E's note, F's sentences); of the paid steps only
  6335 n=3; P3.28 kept in progress until F2.
- **P3.12, `wave4_b13_p312` (6335 n=3, served by `ed7d722`, $1.95; `replay check`, `replay pin`, uvicorn
  restarted after the pin, the keep-awake helper, `replay restore`, both processes stopped):** `depth` DELIVERED
  2, PARTIAL 1; by hand reps 2 and 3 DELIVERED, rep 1 PARTIAL (paragraph 44 named by number without its words, so
  no line). Exit-1 set clean (`commencements` exits 1 with no graded session in the directory, as for
  `wave4_b12_p312`); `schedules` OK 4 of 4. Hand-read in the gitignored `evidence/rubrics/handread_batch13.md`.
- **Folded into FIX_PLAN.md** (`fold_s45.py`; LF kept): ticked **P3.45, P4.23, P3.26**; **P3.28, P3.38, P3.46**
  to `[~]`; annotated P3.12 and P3.34; new row **P3.47**; the bucket index; a new top order line. `plan_lint` 0,
  0; `plan_status` **70 of 102, 4 in progress, 9 of 14**.
- **Lasting docs:** CHANGELOG *Unreleased* (P3.45, P3.28, P3.26, P3.38, P3.12's batch 13 lines, P4.23, P3.46, the
  tooling); CLAUDE.md's Worker notes (P4.23, P3.45, P3.38, P3.28 with P3.26, P3.12's bullet, P3.46 in the case-law
  notes); TODO D19 (P3.45's `citations_removed` audit field for schema v7).
- **Spend: $1.95** (the sweep) and $0.0012 (one `replay check` probe). Agents $0 in model spend.

**Surprises:**
- **The disk filled at seven worktrees.** Each is about 1.7 GB, most of it the tracked offline-dependency zip
  parts; remove merged worktrees before a batch.
- **The push the user agreed at launch was denied by the auto-mode classifier.** Ask before relying on a push in
  a long session, or have the user add a permission rule.
- **A restored line can only put back a paragraph the answer leaves unnamed.** Rep 1 named paragraph 44 by number
  ("an interim moratorium begins under paragraph 44") without its words, so the restore treated it as cited.
- **The schedule detectors in `b9_screen` fire on any sentence**, where `schedules` grades only clauses naming the
  unit asked about: read a screen trip against the grader's own gate before calling it a defect.

## Session 45 — handover for Session 46 (2026-10-10)

**One session works the branch at a time.** Read this handover, then FIX_PLAN's top order line ("end of Session
45"). No brief for the next batch is written; write one from the order line if the user asks for a parallel
batch. **First: confirm with the user that the branch has been pushed** (this session's commits were not, the
push being denied by the classifier); `git status -sb` shows how far ahead it is.

**Take next, by severity:**
1. **P1: P3.12:** measure the paragraph the answer names by number without its words (B4: rep 1's shape), then
   6335 n=3 (about $1.80), priced first; P3.38's exact-paragraph route as its own build at this seam (C8, reusing
   `agent/tools/published_text.py`).
2. **P2:** P3.38's acceptance (`p37_6409`, `p37_6373`, 6410, `p37r_6383` n=3, about $3.60, up to $5.40; hand-read
   first); P3.46's acceptance (6359, 6363 n=3, about $9.50, up to $13.50); P3.34's build (the code tool decided on
   its row; wording to the user); P3.28's F2: the Worker prompts' `_IN_FORCE_RULE` (b) replaced by F's class-aware
   rule (`notes/batch13_F.md`, decision 2) after a first-round probe and one `--as-sent` seam draw (a few cents to
   about $0.40), then tick P3.28.
3. **P3:** P3.47 (tracker severity for the user); P3.33 (P3.28's classes); `negcurrency`'s removal rule aligned
   (F5); and the rest of the order line.

**State:** branch `fix/prepilot-defects` at this handover's commit, **not pushed**; `main` at `a6b4a76`;
`plan_status` 70 of 102, 4 in progress, 9 of 14; `plan_lint` 0; **3,872 tests**; **71 replay directories**
(`wave4_b13_p312` new); no server, no pin, the dev box's `.env` unchanged. The seven batch 13 worktrees under
`.claude/worktrees/` are merged; their scratch is in the main checkout's `evidence/seam/batch13/<letter>/`; they
can be removed (and should be before another batch: disk). Integrator scratch (mutant scripts, screens, the
fold, the decision record `s45_decisions.md`, suites, the sweep log) is copied to the gitignored
`evidence/seam/batch13/scratchpad_s45/`; the decision sheet is in `evidence/seam/batch13/integrator/`.

**Watch items:** P3.10's discovery steps that stop searching; P3.4's follow-up turns; P3.20's rep 2 (on P3.3);
P4.23 re-graded on the next sweep; reps 2 and 3 of `wave4_b13_p312` attribute Part A1 rules to the
administration moratorium (outside P3.12's criterion).

**Carried, the user's:** pushing the branch; the SCTS whitelist request (P3.20 built, off until both hosts are
whitelisted) and SCTS's written confirmation; the lawyer pack (P3.2, P3.3, P3.17); D23; P5.5; deploying
`v2026.09.3`; the eval-harness owner; D19 (now with P3.45's audit field); the next cut (`v2026.10.1`, which would
carry P3.31, P4.12, batch 12's six rows and this batch's three); Tesseract (P3.35); P3.12's tracker severity (P2
on the tracker, P1 in the briefs); P3.47's tracker severity; the Fix Tracker (v48 is the base; not updated this
session).

**Addendum to Session 45 (2026-10-10, after the user added a 70 GB F: drive).** The seven batch 13 worktrees were
removed (merged, clean, every scratch file already in the main checkout: `wt_diff.py`), and
`C:\Projects\LexChat\.claude\worktrees` is now a directory junction to `F:\LexChat-worktrees`, so an agent's worktree
(about 1.7 GB, mostly the tracked offline-dependency zip parts) is written to F:. Tested with a throwaway
`git worktree add` through the junction (1.6 GB on F:, C: unchanged; `pytest` ran from it, 85 passed) and removed.
This supersedes the handover's "remove the worktrees before another batch: disk"; merged worktrees should still be
removed with `git worktree remove`. C: has about 22 GB free. The branch is still not pushed.
