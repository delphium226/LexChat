# Pre-pilot defect fixes — plan

**Status:** in build. **Branch:** `fix/prepilot-defects` (branched from `main` at `eaaa4ec`).
**Read this file first** at the start of every session, then `SESSION_LOG.md` next to it for
what actually happened, then `evidence/` for the classification this plan is derived from.

Fixing the 14 failure buckets found by re-analysing all 62 pre-pilot sessions (11–21 Aug 2026,
13 lawyers, 377 messages). 25 sessions FAIL, 16 carry a DEFECT, 21 PASS.

Full analysis, with the evidence for each bucket:
<https://claude.ai/code/artifact/43d8e63d-1c9d-4460-907c-2d35c1fa3786>

---

## How to use this file

1. Read **Invariants** — they are the things a fix must not break, and two of them are
   counter-intuitive enough that a cold session will get them wrong without reading.
2. Find the first unticked row in the **Ledger**. Rows are ordered by wave; do not start a
   wave before its predecessor is ticked, and do not start a row whose `Depends on` is unticked.
3. Each row is **self-contained**: files, the change, the acceptance test, and the sessions that
   evidence it. You should not need to re-derive anything from the transcripts to execute a row.
4. Follow the **Verification protocol**. A row is not tickable until its acceptance test passes.
5. Append to `SESSION_LOG.md` before you finish. The *Surprises* line is the one that matters.
6. If reality diverges from the plan, follow the **Re-planning protocol** — amend this file in
   the same commit as the work, do not leave the plan stale.

---

## Invariants

These hold for every row. Breaking one is a worse outcome than leaving a bucket unfixed.

1. **Honest failure is the most-praised behaviour in the corpus and must survive every fix.**
   Three lawyers praised it unprompted, two of them at 5/5 confidence; CambeulW gave 5/5 in
   session 6374 *because* AILA said it could not find something. Every fix to B3 and B5 must
   make the negatives **true** — it must not make the tool more willing to guess. A fix that
   raises the answer rate by lowering the evidence bar is a regression even if the ledger row
   goes green.

2. **Code enforcement beats prompt obedience.** This is already the house style (Phase-2 nudges,
   the parliamentary search budget, the `local_prompt_cache` drafting override). Where a row
   offers a choice between "tell the model to" and "make it so", take the second. B3(b), B7 and
   B12's disclosure footer are all specified this way deliberately.

3. **Do not change retrieval and measure in the same step.** Wave 1 fixes the input to every
   other measurement — while `_matches_jurisdiction` returns `False` for every real extent
   value, no retrieval-quality number means anything. Baseline first (Wave 0), then Wave 1,
   then re-baseline before Wave 3.

4. **A single replay pass is not evidence.** The model is stochastic. Acceptance for any row
   whose test involves an LLM is **n=3, all three clean**. Rows marked *deterministic* have no
   model in the loop and need n=1.

5. **Additive and fail-soft, as everywhere else in this codebase.** No row here justifies a
   breaking change to a stored shape. New columns default; new fields are optional; a failure
   in a diagnostic must never fail the research run.

6. **The lawyers' own words are the ground truth, not the feedback scores.** Two sessions
   (6376, 6361) carry `Q7a = yes` with free text saying the opposite. Where a row cites a
   session, read the transcript, not the score.

---

## Data handling — read before adding evidence to this repo

`evidence/classification.json` holds session IDs, lawyer usernames, thread titles and my
diagnosis of each session. This matches the precedent already set in `docs/TODO.md`, which
names the same users and quotes their feedback.

**The raw transcript export is deliberately NOT committed.** It contains the lawyers' full
research questions — live Scottish Government casework. It lives at:

```
C:/Temp/aila-prepilot/pre-pilot sessions/session-transcripts-all-time-2026-09-14.csv
```

and can be regenerated at any time from **Admin Portal → Developer → Session transcripts
export** (all time). A session that needs the replay inputs reads it from there.

**Open question for the deploying organisation:** whether the replay set (question text, verbatim)
may be committed as a regression fixture. Until answered, keep it out of the repo and
regenerate locally. See `SESSION_LOG.md` Session 1.

---

## Verification protocol

Every row states its own acceptance test. Three kinds, and the distinction matters:

| Kind | What it means | n | Where it lives |
|---|---|---|---|
| **Deterministic** | No LLM. A unit test, or a static check over stored output. | 1 | `server_py/tests/` |
| **Replay** | Re-run the original session's question(s) through `/api/system/chat` and assert on the `audit` trace + answer. | 3 | `evidence/replay/` (gitignored output) |
| **External** | Answer comes from a third party, not from code. | — | `SESSION_LOG.md` |

**The replay harness is `/api/system/chat` with `emit_tool_details=True`**, which emits the
structured `audit` event (`delegations[] → tools[] → api_calls[]`, with `raw_result` alongside
`final_result`). Spec: `docs/api/AUDIT_TRACE.md`. It exists precisely so a harness can see what
was *retrieved*, not just what was answered — which is what most of these rows assert on.
Do **not** build a new harness against `/api/chat`; it does not emit tool events.

`request_timings.source` is already tagged `"eval"` for this endpoint, so replay traffic stays
separable from live traffic in the Efficiency and Cache tabs. Note the dashboards do not yet
filter on it, so a large replay sweep moves the headline numbers — expected, not a bug.

---

## Re-planning protocol

This plan is expected to change. Two rules:

- **Amend the plan in the same commit as the work that invalidated it.** A session that
  discovers a row is wrong edits the row, adds a `~~strikethrough~~` note saying what was
  believed and what is now known, and says so in `SESSION_LOG.md`. A stale plan is the specific
  failure mode this structure exists to prevent.
- **New findings become new rows, not scope creep inside an existing row.** If executing P1.1
  uncovers a second defect, add P1.5 rather than widening P1.1 — otherwise the ledger stops
  reflecting what was actually verified.

Wave 5 rows are **external** and have unknown lead times. Open them early and in parallel;
they are not blockers for anything in Waves 0–4.

---

## Ledger

Status: `[ ]` not started · `[~]` in progress · `[x]` done and accepted · `[-]` dropped (say why)

### Wave 0 — Baseline before any change

| | ID | Row |
|---|---|---|
| `[ ]` | **P0.1** | **Build the replay runner.** A script that takes a session's user turns in order and replays them through `/api/system/chat` with the session's recorded filters, capturing the `audit` event and the final answer to a JSON file per run. **Files:** new `server_py/tools/replay.py` (+ `evidence/replay/` gitignored). **Acceptance** *(deterministic)*: replaying session 6404 (a clean PASS) produces a trace containing at least one `search_legislation` call and a non-empty answer. **Depends on:** — |
| `[ ]` | **P0.2** | **Freeze the replay set.** Extract the 41 defect-carrying sessions from the CSV into a local, gitignored `replay_set.json`: session id, ordered user turns, recorded filter state, the bucket(s) it evidences. **Note:** filters are a per-session snapshot (see *What this cannot tell us* in the analysis) — record them, but treat a mismatch as a finding, not an error. **Acceptance** *(deterministic)*: 41 entries; every session in `classification.json` with verdict FAIL or DEFECT is present. **Depends on:** — |
| `[ ]` | **P0.3** | **Run the baseline, n=3.** Replay all 41 on current branch HEAD and record, per session, whether the original failure still reproduces. **This is the row that makes every later acceptance test meaningful.** Expect some not to reproduce — three weeks of commits landed between the pre-pilot and this branch. **Acceptance:** a `BASELINE.md` in this directory recording reproduce / does-not-reproduce / inconclusive per session, with the reason for every does-not-reproduce. **Depends on:** P0.1, P0.2 |

### Wave 1 — The proven code defects (deterministic, no model behaviour change)

| | ID | Row |
|---|---|---|
| `[ ]` | **P1.1** | **B2 — Fix the jurisdiction filter.** `_matches_jurisdiction` (`server_py/src/agent/tools/lex.py:44`) splits `extent` on `+` and tests single-letter tokens `E`/`W`/`S`/`NI`. The LEX API returns full territory names. Verified live: the six values the API emits are `['']` (68), `['Scotland']` (42), `['England','Wales']` (4), `['England','Wales','Scotland']` (3), `['United Kingdom']` (2), `['Northern Ireland']` (1) — **all six return False for every jurisdiction value**, so the filter discards 100% of results. Map the real vocabulary. Treat `['']` as unknown-and-include (as `[]` already is) — most SSIs carry it. `uk_wide` currently requires `tokens ⊇ {E,W,S,NI}` and is equally unreachable; decide what it means against `['United Kingdom']`. **Decide explicitly** that UK-wide and assimilated (`eur`) instruments are in scope for a Scotland filter — that is what CambeulW asked for in 6406 and it is the difference between a usable filter and a trap. **Acceptance** *(deterministic)*: unit test asserting True for each live extent value against its own territory, pinned to a fixture of the live vocabulary so an API change breaks the test not the product; plus a `jurisdiction=scotland` search for "Courts Reform (Scotland) Act 2014" returning `asp/2014/18`. **Evidence:** 6408 6384 6383 6382 6381 6396 6359 6407. **Depends on:** P0.3 |
| `[ ]` | **P1.2** | **B4 (filter half) — Stop the `current_only` filter pretending.** `_INACTIVE` (`executor.py:211–216`) tests for `{repealed, revoked, spent, expired, not in force}`; the API's `status` vocabulary is `final` and `revised` only, so nothing is ever excluded. The field means *which text version is held*, not in-force status, so this **cannot be fixed by extending the word list**. Two parts: (a) remove or relabel the filter so it does not promise currency it cannot deliver; (b) strip in-force assertions from answers — see P2.5 for the model-side half. **Do not** silently leave the toggle in the UI doing nothing. **Acceptance** *(deterministic)*: unit test pinning the live status vocabulary; a search with the filter on returns the same set as with it off, *or* the filter is gone. **Evidence:** 6378 6341 6411. **Depends on:** P0.3 |
| `[ ]` | **P1.3** | **B5 (data half) — Stop discarding what the search actually found.** Two changes in `executor.py`: (a) `_TYPE_CODES` (`lex.py:80`) has no `eur` entry, so `legislation_type` drops every assimilated EU regulation — confirmed present and retrievable (`eur/2009/1069` returns 10 sections); (b) `executor.py:227` sets `slimmed["total"] = len(results)` **after** post-filtering, destroying the API's real match count. Return `returned` / `total_matched` / `removed_by_filters` as separate fields so the model can tell "5 matched" from "172 matched and your filters removed all but 5". This is the D16 defect-2 fix, now with field evidence. **Acceptance** *(deterministic)*: unit test asserting the three counts are distinct and correct for a filtered search; `legislation_type=secondary` no longer drops an `eur/` result, or `eur` is deliberately excluded with the reason in a comment. **Evidence:** 6406 6408 + the whole of B5. **Depends on:** P0.3 |
| `[ ]` | **P1.4** | **B14 — Provision links must point at the provision.** Across all 62 transcripts, 9 of 293 section-labelled legislation.gov.uk links resolve to the Act's contents page. Build the URL from the provision identifier rather than letting the model compose it. HeatherE asked for exactly this in 6334. Lowest-effort row on this page and it directly serves the click-through verification the lawyers actually use. **Acceptance** *(deterministic)*: static check over any replay output — every link whose label names a section/regulation/article/schedule contains the matching path segment. **Evidence:** 6334 6409 6375 6341 6348. **Depends on:** P0.3 |
| `[ ]` | **P1.5** | **Re-baseline after Wave 1.** Re-run P0.3 on the Wave 1 HEAD. Wave 1 changes what every search returns, so the Wave 0 numbers no longer describe the system. **Acceptance:** `BASELINE.md` gains a second column. **Depends on:** P1.1–P1.4 |

### Wave 2 — Structural honesty (changes what the model may say, not what it can find)

| | ID | Row |
|---|---|---|
| `[ ]` | **P2.1** | **B1 — The Deep Research halt must stop being a legal finding.** `chat_loop` returns `"[Research halted: exceeded {max_turns} tool-call steps]"` as the worker's **assistant content** (`agent/openrouter_client.py:158`, `agent/ollama_client.py:85`, `max_turns=20`); `run_deep_research` (`agent_core.py:698`) treats that string as the step's findings and hands it to synthesis, which reports it as a Material Gap beside real legal findings. **10 of 23 DR sessions (43%).** Return the halt as structured metadata on the step result (`{complete: false, reason: "step_budget"}`); synthesis must not render it as a legal gap; the UI marks the step incomplete. **Read `request_timings.max_turns_halted` (already collected, `utils/stopwatch.py:177`, already aggregated at `routers/stats.py:673`) before changing the cap** — the cap question is separate from the presentation question and only one of them is urgent. **Acceptance** *(replay, n=3)*: 6406, 6382, 6408 produce no halt text in the report body. 6406 is the acceptance case — all four steps halted and the report cost $2.36 to say nothing. **Evidence:** 6406 6408 6382 6384 6409 6374 6407 6389 6357 6341. **Depends on:** P1.5 |
| `[ ]` | **P2.2** | **B5 — No bare negatives.** A zero-result answer must state what was searched, under which filters, and how many matches the filters removed. Also: `search_legislation` is the only search tool with **no zero-result nudge** — case law has one (`agent/agent_shared.py:565`), Hansard has one (`:720`), and the legislation branch at `:737` fires only `if id_pairs:`. Add the else branch. **Acceptance** *(replay, n=3)*: 6409 and 6367 name their search terms and active filters in the negative answer. **Invariant 1 applies** — the test is that the negative is *explained*, not that it becomes a positive. **Evidence:** 6367 6381 6409 6410 6384 6373 6365. **Depends on:** P1.3, P2.1 |
| `[ ]` | **P2.3** | **B3(b) — Forbid unverified "made under" assertions.** No tool exposes *made under*, *commences*, *amends*, *revokes* or *suspends*, so the model answers relationship questions from search-result adjacency. In 6340 it listed three real, correctly-cited SIs as made under s.117 Education (Scotland) Act 1962 — **the Act is a 404 in LEX** (`ukpga/1962/47`) and the three SIs are simply the top keyword hits for its title. Link-checking cannot catch this, which is what makes it the worst bucket. Until P5.1 answers whether the relation is retrievable: the model may assert an enabling-power, commencement or amendment relationship **only** where a retrieved preamble or provision states it, and must otherwise say the relationship could not be verified. Enforce in code (invariant 2), not by prompt alone. **Acceptance** *(replay, n=3)*: 6340's correct answer is "this Act is not held in the database, so I cannot list instruments made under it" — **any list of SIs is a failure regardless of citation quality**. Plus 6409, 6410, 6354. **Evidence:** 6340 6409 6410 6354 6383 6374 6345 6406 6408 6382 6411. **Depends on:** P2.2 |
| `[ ]` | **P2.4** | **B12 — Deterministic disclosure of the case-law corpus gap.** The National Archives corpus does not index the Court of Session or the Sheriff Courts. AILA discloses this well in 6341, 6385 and 6407 — and **not at all in 6375, where it mattered most** and produced a substantive error (English common interest privilege analysed as Scots law). Inconsistent disclosure is worse than none: users calibrate to the warning and are then not warned. Add a footer on any Scots-law case-law answer, in code. Separately, distinguish "absent from the index" from "does not exist" in the wording — in 6373 AILA questioned FrankieH's citation of SSI 2026/170 when the citation was right and the index was short. **Acceptance** *(replay, n=3)*: 6375 carries the disclosure; 6373 attributes the miss to the index, not to the lawyer. **Evidence:** 6373 6385 6363 6375 6340 6359 6409. **Depends on:** P2.2 |
| `[ ]` | **P2.5** | **B4 (model half) — Stop asserting in-force status.** Pairs with P1.2. There is no in-force signal in the tool surface, yet the model states currency confidently: in 6341 it said every provision cited was in force (ss.38–39 Shops Act are repealed) and then **invented an explanation** for the missing text. Remove the claim until there is a source for it. **Acceptance** *(replay, n=3)*: 6341 and 6411 make no in-force claim unsupported by a retrieved commencement source. **Evidence:** 6341 6411 6378. **Depends on:** P1.2, P2.2 |

### Wave 3 — Retrieval depth and reasoning (rate-measured; needs a settled baseline)

| | ID | Row |
|---|---|---|
| `[ ]` | **P3.1** | **B10 — Right Act, wrong depth.** 6 primary / 10 total. First, **verify a claim in our own docstring**: `_slim_search_results` says the raw search response carries "a ranked sections array that the model never uses". If real, Phase 2 is discarding the API's own statement of which sections matched and re-guessing in free text — the cheapest precision win available. **Confirm the live shape before building on it**; an unverified assumption about a response field is what made A2 dead on live data. Then allow subsection-level citation (6365: "it only ever cited full sections"), and relax the one-call-per-instrument rule where the question is scoped to a single Act. **Acceptance** *(replay, n=3)*: 6396 (right enactment, provisions not found), 6365, 6348 return the provision at the granularity asked for. **Evidence:** 6396 6365 6348 6369 6333 6380 6354 6347 6372 6385. **Depends on:** P1.5, P2.* |
| `[ ]` | **P3.2** | **B6 — Stop capitulating under challenge.** Pushback is currently treated as correction, so the answer tracks who pushed hardest. 6406 is the demonstration: AILA asserts fish oil is *not* a rendered fat and defends it over three turns, then reverses completely on pushback with a fresh citation — **having already reversed once earlier in the same session**. Both positions asserted with equal confidence and equal apparent grounding. On challenge: re-retrieve before re-answering, and require the revised answer to cite the provision that changed the conclusion. Remove agreement openers ("You are absolutely correct") from the register — they signal a resolution that has not happened. **Acceptance:** needs an **adversarial multi-turn rig that does not exist yet** — build it as part of this row. Replay 6406 turns 11–24 as a scripted challenge sequence; assert the position is either held with the same citation or changed with a new one, and never flips twice. **Evidence:** 6406 6345. **Depends on:** P3.1 |
| `[ ]` | **P3.3** | **B11 — Separate retrieval from interpretation.** Three sessions, all verified wrong or unhedged. 6338 applied the Interpretation and Legislative Reform (Scotland) Act 2010 to a 2009 Act, twice, unhedged — **ILRA s.1(1)(a) applies Part 1 only to Acts whose Bills received Royal Assent on or after Part 1 commenced** (verified at source); HeatherE was right and the correct instrument is the Scotland Act 1998 interpretation order. It was also wrong that ss.35A and 35ZA cannot run concurrently, reasoning from structure rather than text. Encode the distinction between "s.25 provides that…" (retrieval) and "on one reading, X" (advice) and hedge only the second. **Note the counter-pressure**: these users reward decisiveness when it is grounded, and CambeulW asked for neutrality only "for aspects which require a legal analysis" — a blanket caveat is a regression. Add an explicit rule that a doctrine is not asserted for a jurisdiction unless a source for that jurisdiction was retrieved, which also closes 6375. **Acceptance** *(replay, n=3)*: 6338 has a verifiable right answer, so it is a true accuracy test not a style check. Plus 6375, 6370. **Evidence:** 6338 6375 6370. **Depends on:** P3.1 |
| `[ ]` | **P3.4** | **B9 — Default jurisdiction.** Every user of this deployment is a Scottish Government lawyer, and there is no default-jurisdiction rule. 6378 asked about "the UK" and got an England-only answer with no flag; 6360 got the E&W 2007 Rules and reached the Scottish ones only on follow-up. Where the question names no jurisdiction: answer for Scotland and say so. Where it says "the UK": answer for all four and flag divergence rather than silently picking one. **Depends on P1.1** — the filter is currently the only lever a user has and it does not work. **Acceptance** *(replay, n=3)*: 6378 turn 1 and 6360 turn 1 name their jurisdiction explicitly. **Evidence:** 6360 6378. **Depends on:** P1.1, P3.1 |

### Wave 4 — Interaction (independently shippable, mostly frontend)

| | ID | Row |
|---|---|---|
| `[ ]` | **P4.1** | **B7 — The research-mode dead-end.** Carries the single worst user experience in the corpus: 6346 is the only 1/1 session, where MoniqueM changed the mode, said so, and was told four times she had not. She opened a fresh session, asked the identical question, and got a full answer first try — that recovery is the confirming case. **Code-checked and unchanged: the backend is not stale.** `researchMode` is sent on every request and the mode note is rebuilt per turn; the model anchors on its own earlier refusal, still in the conversation history, over the current system prompt. Three separable bugs: **(a)** the anchoring — inject a mode-change marker into the history when the resolved mode differs from the previous assistant turn's (needs the previous turn's mode, which the frontend has and discards — see D13); **(b)** the wrong control name — `prompts.py:649-650` says "'Legislation & Case Law' mode via the mode selector"; the real control is **Research filters → "Legislation & case law"**, and the transcripts show the model paraphrasing it to "Research mode", which is the *chat mode* control and does not lift the case-law block; **(c)** invented UI — in 6343 it told the user the control is "typically located at the top or side of the chat window". Strip every speculative UI description. Also: AlistairC clicked AILA's own suggestion chip in 6407 and was told "I cannot change the mode for you" — make the chip perform the switch or stop offering it. **Acceptance** *(replay, n=3)*: scripted two-turn sequence — refusal, mode change, same question; assert the second answer does not reference the old mode. **Evidence:** 6346 6343 6347 6350 6407. **Depends on:** P2.* |
| `[ ]` | **P4.2** | **B13 — Lost turns, blank replies, latency.** **15 user turns across 11 sessions never received a reply**; two assistant messages rendered blank — 6370 #8 **billed $0.0217** with nothing shown, 6363 #6 billed nothing. 6387 timed out on a follow-up. **n=2 on the blanks, so reproduce before fixing.** The billed-but-empty case is the informative one: content was generated and lost downstream. Eliminate in order: (1) a `<suggestions>` strip consuming the whole body — `utils/suggestions.py` takes the **last** block and also strips an *unterminated* trailing tag, which is exactly what a partial stream looks like; (2) a tool-call-only final message; (3) the `chat_loop` stream-retry guard re-raising after partial emission. Separately, for perceived latency (MoniqueM reported a 5.5-minute turn as "around 15 minutes"), add a coarse step counter — the `tool_call` / `api_call_start` events already exist behind `emit_tool_details` and cost nothing in retrieval terms. **Acceptance** *(deterministic)*: assert a non-empty body whenever recorded cost > 0. **Evidence:** 6387 6370 6363 6345 6335. **Depends on:** — (independent of the accuracy path) |
| `[ ]` | **P4.3** | **B8 — The sources rail and the answer disagree.** Both directions: 6378's correct instrument (SSI 2008/216) was **in the rail and absent from the answer** ("This legislation was cited in sources but not in the answer"), while 6372 quoted provisions as belonging to one instrument when they belong to another. 6335 and 6359 carry sources the lawyers checked and found irrelevant, which costs checking time and erodes the rail as a verification surface. Invert the existing `_source_is_used` check into a diagnostic — a source retrieved, kept and not referenced is a detectable condition — and surface it both to the model as a pre-answer check and to the rail as a cited/consulted distinction. **Acceptance** *(replay, n=3)*: 6378 contains SSI 2008/216 in the answer body; instrument the unused-source rate across the whole replay set (one observation was never a rate; there are now four). **Evidence:** 6378 6372 6335 6359 6367. **Depends on:** P3.1 |

### Wave 5 — External (open now, in parallel; unknown lead time)

| | ID | Row |
|---|---|---|
| `[ ]` | **P5.1** | **B3(a) — Ask the LEX team whether relationships are retrievable.** Does the API expose enabling-power, amendment, commencement or revocation relations in any form? This determines whether the largest bucket is **buildable or permanently a disclosure**, and P2.3 is the holding fix either way. Known from direct probing: `/legislation/search`, `/legislation/section/search` and `/legislation/text` are the only endpoints we call; `text` returns a record for `ssi/2025/119` with an **empty `text` field** while `section/search` returns nothing for it, so stub records exist and are indistinguishable from absence at the tool boundary — worth raising in the same conversation. **Acceptance** *(external)*: a recorded answer in `SESSION_LOG.md`, and either a new row or a note that P2.3 is permanent. **Depends on:** — |
| `[ ]` | **P5.2** | **B12 — The Scottish case-law corpus.** The Court of Session and Sheriff Courts are not in the National Archives corpus. In 6375 that stopped being a coverage gap and became a wrong answer. Also flagged by AlistairC (*Clark* absent, 6359), CambeulW (recency bias, 6363) and EmmaM. This is a product/procurement question, not an engineering one; P2.4 is the engineering half and is not blocked by it. **Record it as the top substantive content gap of the pre-pilot.** **Acceptance** *(external)*: a recorded decision. **Depends on:** — |
| `[ ]` | **P5.3** | **Corpus currency.** Verified absent from LEX in September 2026: Education (Scotland) Act 1962 (`ukpga/1962/47` → 404), SSI 2026/170 → 404, SSI 2025/119 (record exists, text empty), stub-only provisions for the Education (Scotland) Act 1945. Ask what the index's coverage rules and refresh cadence actually are, so B5's "absent from the index" wording can be accurate rather than generic. **Acceptance** *(external)*: a recorded answer. **Depends on:** — |

---

## Bucket → row index

Use this to get from a bucket in the analysis to the rows that close it.

| Bucket | Rows |
|---|---|
| B1 Deep Research halt | P2.1 |
| B2 Jurisdiction filter | P1.1 |
| B3 Relationship blindness | P2.3 (holding), P5.1 (decides) |
| B4 In-force status | P1.2 (filter), P2.5 (model) |
| B5 False negatives / silent substitution | P1.3 (data), P2.2 (behaviour) |
| B6 Capitulation under challenge | P3.2 |
| B7 Mode dead-end | P4.1 |
| B8 Sources rail | P4.3 |
| B9 Jurisdiction default | P3.4 |
| B10 Depth | P3.1 |
| B11 Interpretation | P3.3 |
| B12 Corpus gap | P2.4 (disclosure), P5.2 (corpus) |
| B13 Lost turns / blanks | P4.2 |
| B14 Link granularity | P1.4 |

---

## Merging back

`main` is the deployment branch and the target pulls `origin/main`, so **nothing here is pushed
to `main` until the wave it belongs to is accepted**. Waves are independently mergeable and
should be merged as they complete rather than held to the end — Wave 1 in particular is
deterministic, self-contained, and fixes a defect that silently destroys every filtered search.

The frontend build rule still applies: any change under `client/src/` needs `npm run build` and
a force-added `client/dist/` in the same commit (see the root `CLAUDE.md`).
