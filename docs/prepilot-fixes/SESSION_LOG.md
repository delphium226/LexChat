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

**State of the branch:** `fix/prepilot-defects`. Waves 0 and 1 complete plus P1.5, P1.6,
P2.1 and P2.6; P0.4 half done; P2.7 opened. 634 tests green, tree clean. **Nothing
pushed** — the whole-plan-then-one-push policy (Session 4, user) stands, and the target
still runs the pre-pilot code.

**Machine state a new session inherits:**
- **No uvicorn running** — stopped deliberately. Start a fresh one before any live work:
  Python loads modules at import, so a surviving server serves stale code.
- **Dev box restored** — `moonshotai/kimi-k3`, local prompt cache ON,
  `tools/.replay_pin_state.json` gone, as it should be after a successful `restore`.
  **Re-pin before any measurement.**
- Three gitignored replay directories now: `baseline/` (65 files), `wave1/` (41) and
  **`wave2_p21/` (12 — four sessions × three reps, P2.1's acceptance, NOT a full sweep)**.
  A Wave 2 sweep needs a **new** directory; `replay.py run` silently skips existing files.
- **Do not compare `wave2_p21/` against `wave1/` with `compare`** — it is 4 sessions
  against 41 and every total would be nonsense. Use `replay_report --dir <dir> halts` for
  it, which grades per halted turn and is what its acceptance is stated in.
- **Provenance notes on `wave2_p21/`, recorded rather than hidden:** the files say
  `git_head: 7a1c79b` (P1.6's commit) because P2.1 was loaded by the server but committed
  minutes later as `4d3f4c1`; **P2.6 is NOT in those runs** (written after the server
  started — visible as `report_reformat_retries: 1` on halted turns); and a cosmetic
  plural-agreement fix to the notice landed mid-sweep, so runs naming more than one halted
  step read "was … it" where HEAD reads "were … they". None changes a graded condition.
- **Wave 5 is drafted and unsent** (`WAVE5_QUESTIONS.md`). It needs a human. P5.1 first.

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

| series | held (20-point samples) |
|---|---|
| ASP 2025 / 2026 | **100%** |
| SSI 2025 | 85% |
| **SSI 2026** | **5%** |
| **UK SI 2026** | **0%** |
| UKPGA 1962 | 60% |

**This sets B5's wording, which is what the row was for.** On these numbers a "not found"
for a 2026 SSI is *far* more likely a coverage gap than an absence in law, and a negative
that does not say so comes close to telling a lawyer the instrument does not exist.
P2.2 now has a number to write against.

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

**Next action:** ~~P2.2~~ — **see the P5.1 answer above first; it changes what Wave 2 and Wave 3 contain.** Then **P2.2** (B5, no bare negatives) — its `Depends on: P1.3, P2.1` is now
satisfied, and this session amended it to cover the negative drawn from an **incomplete**
search as well as from a filtered one. Note P2.3 depends on P2.2 and on P5.1's answer, so
sending the Wave 5 questions before starting P2.2 is worth the five minutes. **P2.7** is
available in parallel and is well-evidenced; **P2.5** is the other unblocked Wave 2 row and
its scope did not shrink (B4 rose 27 → 30 at P1.5). Do the **P0.4 re-export** before the
next full sweep if target access appears.
