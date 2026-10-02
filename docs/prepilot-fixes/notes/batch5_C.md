# Parallel batch 5, agent C: open rows part 2, bucket placement, cross-document consistency

Branch `worktree-agent-af3168d5944c83a3c`. **$0**: no model call, no server, no replay pin, run
or restore, no API call of any kind. A note only: no product code, no tool, no FIX_PLAN or other
tracked-document edit. Every command runs from `server_py/` (or the repo root where shown) with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and `PYTHONIOENCODING=utf-8`;
`$C` is my scratch folder (section 8).

**Base.** The worktree came up on `main` (`a6b4a76`), as in batches 1-4. With no commits of my own
I ran `git reset --hard dde8b41a8344c388470c538169b769699c0efa7d` first. The note is based on
`dde8b41`; `origin/fix/prepilot-defects` was `dde8b41` and `origin/main` `a6b4a76` when checked.

**Tests:** full suite on `lexchat_test_c`, **2135 passed** (`python -m pytest -q`), before the
note's commit. No new test: no code changed.

**One correction to the brief before anything else.** The integrator's note says `plan_status`
counts bucket closure from the rows' ticks, not from the index. That is half right.
`tools/plan_status.py` `_buckets()` reads each `| B<n> ... |` index line to learn **which rows a
bucket waits on**, then reads those rows' ticks. The `*(no bucket)*` line does not match its
regex (`^\| (B\d+)`) and is ignored. So **placing an open row on a CLOSED bucket's line reopens
that bucket in `plan_status`**; placing an open row on a partial bucket's line changes nothing now
but makes the bucket's closure wait on it; placing a ticked row anywhere changes nothing. The same
half-truth is in `PARALLEL_BATCH_5.md` (X13). Every placement below is checked against this with
`$C/placement_sim.py`, which imports `plan_status`'s own readers.

---

## 1. The eleven rows

Checks named per line. "Holds" means the reference was found at HEAD as the row states it.

| Row | Premise still true at HEAD? (what I checked) | Acceptance | Dependencies and overlaps | Status |
|---|---|---|---|---|
| **P3.9** case-law date filter | **Holds.** `executor.py:567-626`: `date_from`/`date_to` are sent raw (:572-575), intersected with the user's `_date_from`/`_date_to` (:583-589), then `client.get` (:600); no `from_date_0/1/2`. Live behaviour not re-probed ($0). **Scale is stale:** now 88 of 1,257 stored calls set a date, 61 of them on P4.1's scripted 6346 replays (M1); still 0 of 481 run files set a user date. **The working date form is undocumented** (`LEGAL_DATA_SOURCES.md` §4), which the row does not say (M2). | Achievable, deterministic, n=1; consistent with its lever. | Same call as P3.22, P3.23, P4.19 (C2). "Reject an impossible interval" is the case-law twin of `TODO.md` D16 defect 1, parked for legislation (M2). Once built, P5.3's open question (TNA date coverage) becomes measurable; nothing books that. The stored `wave4_p41*` dated calls are a ready before-column. | `[ ]` right; no blocker. |
| **P3.10** dependent Deep Research steps | **Code holds:** `_build_step_brief` (`agent_core.py:1118`) passes title, detail, scope note and question, never earlier findings; `prompts.py:1139` ("independently researchable") and `:1145` (the ordering rule). **The halt premise does not carry to HEAD.** Re-running the Session 15 regex (`SESSION_LOG.md` line 2923ff) reproduces the row's numbers **exactly** over the directories that existed then (136 plans, 34 dependent, 12 of 42 halted, 53 of 452 others), but the one post-P3.1 directory with dependent steps, `wave3_p38` (6374, 6383, n=3), has **0 of 8** dependent steps halted (others 1 of 25). 6382 was last replayed in `wave2_p21` (M8). | "Step halt rate falls without `sources_kept` falling" can pass **vacuously** if the HEAD before-column has no halts, as P2.1's 6384 did (C6). | Depends P2.7 (done). Overlaps P3.8 (write-up at the cap), P2.1, P4.7 and P3.18 (the synthesis that reads the steps), Thomas action 3. | `[ ]` right; needs a premise re-check before any build (C6). |
| **P3.20** SCTS case law | **Holds.** `tests/test_case_law_gap.py` exists; the "not covered" wording is at `search_scope.py:2063` and in the zero-result note in `agent_shared.py` (the `search_case_law` branch, ~:767); `pdfplumber==0.11.10` at `requirements.txt:21` with the "NOT in the current offline bundle" note at :6; `TODO.md` T3, `docs/NETWORK_AND_DEPENDENCIES.md` and `server_py/test_apis.ps1` exist. §3's numbers agree with the row. **One nuance:** §3 extracted the PDFs with `pypdf`, which is not in `requirements.txt`; the product would use `pdfplumber`, untried on them (M13). | Achievable; deterministic + replay n=3. Its 6375 criterion ("no English authority as Scots law") is also graded by **P3.18 (done)** and P3.3; 6375's primary bucket is B11 (M14). | Depends P5.2 (the user's decision), P2.4 (done); also, unstated as dependencies but listed as prerequisites: SCTS's reply, the target's whitelist, T3. **Contradicts the Re-planning protocol's "Wave 5 rows ... are not blockers for anything in Waves 0-4"** (M11). P5.2 does not name P3.20 back (M15). | `[ ]` right; blocked on the user, SCTS and the target owner, and says so. |
| **P3.22** relevance ordering | **Holds** for the code: no `order`, no `per_page` in the params (`executor.py:569-589`). Live claims not re-probed. **Measure-first scale is stale** (569 calls; now 1,257 stored calls, 612 distinct tuples) and the probe itself (~1,224 requests) must be paced under the published limit (M3). **Missed effect:** the Phase-2 nudge names `results[:3]` as "the 1-3 most relevant cases", which under the default order are the three newest; 506 of 1,257 stored calls returned more than three results, against 123 that filled the page, so ordering matters well beyond the window (M3). **Its "not in a bucket" reason is half right:** 6363's frozen diagnosis is "recency bias in the case-law corpus", classified **B12**, which is partial, so B12 is a placement that reopens nothing (C4). Also note Session 15 recorded that part of 6363's failure was P4.5's empty-report trap (`SESSION_LOG.md` ~2961). | Achievable. **The replay bar is non-regression only** ("no fewer ... than before") with no booked ground truth of the authorities, so it can pass while 6363's complaint stands (C2). | Same call as P3.9/P3.23/P4.19; P3.23's window wording names the ordering; `detect_appellate_decisions` reads the same set (row says). | `[ ]` right; no blocker. |
| **P3.23** case-law total | **Holds:** `executor.py:623-628` returns `"total": len(entries)`; `_parse_case_law_atom` (`caselaw.py:126`) reads entries only, no `last` link. **Measured scale: about one call in ten** - of 1,257 stored calls, 123 filled the 50-row page, 658 returned 1-49 (the whole set at the default page size) and 472 none (M4). | Achievable, deterministic. **Trap:** `agent_shared.py` keys the zero-result note and the Phase-2 nudge on `total`; a `last`-link figure is an upper bound and need not be 0 for an empty page, so those must stay keyed on the shown count, as P1.3 kept `returned` apart from `total_matched` (M4). | Overlaps P1.3 (field shape: `returned` / `total_matched`) and P2.2 (the window statement); the lawyer-facing case-law line (`_case_law_body`, P2.4/P4.15) is pinned by `test_case_law_gap.py` and read by every grader if it changes. | `[ ]` right; no blocker. |
| **P4.3** sources rail | **Holds:** `_source_is_used` (`agent_core.py:482`) and the fall-back-to-all at :411-416. The "instrument" half already exists: `replay_report` counts `sources_unused` and `turns_source_fallback` (:550-551). **Its 6378 criterion already passes at n=1 in every run since `wave2`** (the named instrument in 2 of 2 answers in `wave2`, `wave4_p37_reach_pre`, `wave4_p37_reach`; 0 of 2 in `baseline`, `wave1`; `$C/p43_before.py`) (M16). | The 6378 half would pass before any build; the rate half has no bar; the link half (Thomas 7) has no bar (C7). | Depends P3.1, P2.1 (both done): unblocked. Overlaps P3.13 (the Manager drops what the Worker wrote), the P2.4 A/B observation (case-law links lost), Thomas 7. **B8 waits on it alone and is the primary bucket of 4 sessions**, the largest still-open weight. | `[ ]` right. |
| **P4.8** result label | **Holds:** `RESEARCH_RESULT_PREFIX` (`agent_core.py:662`, applied :681); no strip at the Manager return (the only other hits are the "NEVER WRITE A PLACEHOLDER" lines in `prompts.py:894`, `:1019`). **Recount:** the same 7 instances in 1,943 answered turns over 57 directories, all at the start of the answer, **all Research-mode replays of P0.5's twelve sessions**, whose lawyers used Conversational mode; 0 in any Conversational or Deep Research turn (M6). | "0 over the next full sweep": none has run since `wave2` and none is planned (C5). | Same shape as P2.1's marker strip; the seam the row names is right (one return behind `/api/chat` and `/api/consult`). | `[ ]` right. |
| **P4.9** mode change in the thread | **Holds:** `messages.research_mode`/`chat_mode` (`models.py:93-94`), returned by `routers/chats.py` (:60-61, :198), read in `useChat.js:289`; no in-thread marker anywhere in `client/src`. | Deterministic, but **the client has no test runner** (`client/package.json` has no `test` script), so the check method is unstated (M17). | Depends P4.1 (done). Overlaps `TODO.md` D20 (the other display-only client change; one `client/dist` rebuild can carry both). | `[ ]` right. |
| **P4.12** Manager idle timeout | **Re-measured** (`replay_report --dir … lostcost --all-dirs`, 57 directories): 8 Manager (b) calls, **6 unrecovered** (the row: 5 and 3 at 51 directories); after a (b) the Manager's retry answered 2 of 15. Three new unrecovered calls, in `wave4_b2_post` and `wave4_p33_post` (M7). | "To be chosen with the lever and booked here before any build": consistent with measure-first. | Depends P4.11 (done). Overlaps P4.2 (the fallback that serves the unrecovered call) and P4.5 (labelling). | `[ ]` right; the rate doubled, which is the row's own trigger for revisiting option (ii). |
| **P4.19** case-law 429 retry | **Holds:** both calls bypass the helper: `executor.py:600` and `caselaw.py:186-189` (`_fetch_judgment_text` opens its own `AsyncClient`). The acceptance's "a 400 still returns immediately" holds by construction (400 is not in `_RETRY_STATUS`). **Unstated side effect:** the helper also retries a timeout or transport error up to three times (M5). | Achievable, deterministic. | Same call as P3.9/P3.22/P3.23. P3.22's own measure-first needs the same limit respected (M3). | `[ ]` right; preventive, says so. |
| **P5.2** Scottish case law | **Holds:** the TNA gap facts are consistent with `search_scope.py`'s coverage sentence and P4.4's removed filter; the SCTS facts agree with `LEGAL_DATA_SOURCES.md` §3. **Its acceptance ("a recorded decision") is still unmet**: no decision is recorded. | Achievable only by the user. | P3.20 depends on it and says so; P5.2 does not name P3.20 (M15). B12 lists both. | **`[~]` is right** until the user decides (C1). |

---

## 2. P3.20 against P5.2 (must-cover 1)

They are not duplicates: P5.2 is the decision (where Scottish case law comes from), P3.20 the build
on SCTS. What is wrong is the plumbing: P5.2 does not point at P3.20 (M15), the Re-planning
protocol says no Wave 5 row blocks Waves 0-4 (now false, M11), and the Wave 5 intro says the
questions are open only because nobody sent them (M12). The substantive choice is **C1**.
**P5.2 stays `[~]`** until the user records the decision; it should not be ticked on the finding
of a source alone, because its acceptance is a decision.

## 3. P3.22 and P3.23 against P1.3/P2.2, and against P3.9; one build? (must-cover 2)

**Against P1.3/P2.2.** P3.23 is P1.3's count fix and P2.2's window statement for the case-law
tool, which neither touched. Two things carry over and are not on the row: use P1.3's split
(shown and total kept apart, so the zero-result branch cannot read an upper bound as a match),
and if the lawyer-facing case-law line changes, re-run the graders that read footers (P2.2 found a
footer of its own tripping `NEG_ASSERTED`). P3.22 has no legislation twin (LEX search has its own
ranking). Unlike P2.2's legislation case (783 of 783 searches windowed), the case-law window binds
on about **1 call in 10** (123 of 1,257), so P3.23 is real but small; P3.22's effect is wider than
its row says, because the Phase-2 nudge's "most relevant" three are the newest three on every list
longer than three (506 of 1,257).

**Against P3.9.** All three change one branch of `executor.py` (`search_case_law`), and P4.19
wraps the same call. Invariant 3 bites on P3.9 (it changes results, but only on dated calls) and
P3.22 (it changes every list of more than three); P3.23 changes what the model is told, not what
it is given; P4.19 changes nothing unless a 429 or timeout occurs.

**One build, four commits, one measured change** is my recommendation (**C2**): P4.19, P3.23
(stating today's order truthfully, "newest first"), P3.9; then P3.22's $0 measure-first (paced),
a replay before-column at that head, P3.22 itself (which flips P3.23's wording to the relevance
order), and the after-column. Only P3.22 is replay-measured, and its before-column contains the
other three, which is what Invariant 3 asks. **C3** (the National Archives licence) is a
prerequisite question for all four that the plan does not record anywhere.

## 4. Bucket placement for the 21 unindexed rows (must-cover 3)

`$C/placement_sim.py` (imports `tools/plan_status.py`'s `_rows`/`_buckets`) gives the status
effect. "Uncontroversial" = the row's own text or its kind decides it; "judgement" = mine.

| Row | Proposed index line | Label (house style) | Reason | Kind | `plan_status` effect |
|---|---|---|---|---|---|
| P0.1 | *(no bucket)* | (the replay runner) | Measurement infrastructure | uncontroversial | none |
| P0.2 | *(no bucket)* | (the frozen replay set) | Measurement | uncontroversial | none |
| P0.3 | *(no bucket)* | (the Wave 0 baseline) | Measurement | uncontroversial | none |
| P0.4 | *(no bucket)* | (the Deep Research flag in the export; post-push) | Measurement; B13 would reopen (CLOSED to partial) | uncontroversial | none (B13 alt would CHANGE) |
| P0.5 | *(no bucket)* | (the harness's chat mode, from evidence) | Measurement | uncontroversial | none |
| P0.6 | *(no bucket)* | (the harness's research type: unknown, never a default) | Measurement | uncontroversial | none |
| P0.7 | *(no bucket)* | (the research type and chat mode from the target's request log) | Measurement; needs the target; B7 would reopen | uncontroversial | none (B7 alt would CHANGE) |
| P1.5 | *(no bucket)* | (the Wave 1 re-baseline) | Measurement | uncontroversial | none |
| P2.6 | **B1** | (the reformat retry on a halted worker) | It laundered a halt into a finished-looking report: B1's defect at a second site; ticked | judgement | none (B1 stays CLOSED) |
| P3.6 | *(no bucket)* | (the dated `description` at Phase 1) | A capability, as P3.21 argues for itself; B3 is partial, so B3 would change nothing now but its closure would wait on P3.6 | judgement | none (B3 alt: no change now) |
| P3.12 | *(no bucket)* | (a Schedule paragraph asked for by number; P3.8's residual) | Its parent P3.8 is on the no-bucket line; B10 or B5 would reopen | judgement | none (B10/B5 alt would CHANGE) |
| P3.14 | *(no bucket)* | (the quick-lookup Worker's filter block; an awareness gap) | B5's shape but no session evidence yet; B5 would reopen | judgement | none (B5 alt would CHANGE) |
| P3.21 | *(no bucket)* | (the commencement date by a second hop; not B4's defect) | The row's own text says so | uncontroversial | none (B4 alt would CHANGE) |
| P3.22 | **B12** (recommended; C4) or *(no bucket)* | (case-law ranking: 6363's recency complaint) | 6363's frozen diagnosis is recency bias and is classified B12, which is partial; the row's stated reason (B5 would reopen) does not apply to B12 | **judgement, a decision (C4)** | none now (B12 partial to partial), but B12's closure would also wait on P3.22 |
| P3.23 | *(no bucket)* | (case-law total and window; P2.2's shape) | The row's own text; no session behind it | uncontroversial | none (B5 alt would CHANGE) |
| P4.4 | **B12** | (the all-English court filter, removed) | Its trap was B12's (every option non-Scottish); `LEGAL_DATA_SOURCES.md` already lists it under the Scottish case-law gap; ticked | judgement | none (B12 stays partial) |
| P4.8 | *(no bucket)* | (the Manager's result label in an answer) | Cosmetic; its evidence session's B8 is unrelated | uncontroversial | none |
| P4.9 | *(no bucket)* | (a mode change shown in the thread; P4.1's display residual) | Display only; B7 would reopen | judgement | none (B7 alt would CHANGE) |
| P4.19 | *(no bucket)* | (case-law calls retried on a 429) | Preventive; no session | uncontroversial | none |
| P5.3 | **B5** | (corpus currency, answered; set P2.2's coverage wording) | Its answer set B5's wording (its row says so); ticked | judgement | none (B5 stays CLOSED) |
| P5.4 | *(no bucket)* | (probe legislation.gov.uk; its rows carry the buckets) | The row's own text | uncontroversial | none |

**No proposed placement changes any bucket's status today.** The only recommended placement that
changes a future closure is P3.22 to B12 (C4). Every alternative marked CHANGE would reopen a
closed bucket and is not recommended (C8).

## 5. Mechanical amendments to FIX_PLAN.md (M1-M17)

Each anchor is an exact substring of one current line and occurs exactly once; each replacement
adds an even number of `**` (0 or 2 or 4), no `|`, no newline. **Checked:**
`python $C/amendments.py docs/prepilot-fixes/FIX_PLAN.md --apply $C/FIX_PLAN.amended.md` (from
the repo root) prints OK for all 17; the amended copy keeps 461 lines and 69 ledger rows, all CRLF,
and a copy of `plan_status` pointed at it (`$C/plan_status_amended.py`) still gives 46 of 69 rows
and 8 of 14 buckets. **`amendments.py` holds the byte-exact strings; the text below is the same,
for reading.** (The file's `**` total is odd before and after - 4,479 - because of a `**` inside
a code span on P0.2's line, `` `**Key findings` ``; not a defect, but a naive parity check will
flag it. For agent A.)

- **M1** (P3.9) anchor: `Scale: 19 of 569 replayed `search_case_law` calls set a date (3%, all 6385), and no replayed session set the user date filter.` →
  `Scale: ~~19 of 569 replayed `search_case_law` calls set a date (3%, all 6385)~~ **88 of 1,257 stored calls over 22 directories set a date (2026-10-02, batch 5 C, `caselaw_census.py`): 27 on 6385 and 61 on P4.1's scripted 6346 replays (`wave4_p41`, `wave4_p41_pre`, `wave4_p41_dr_v1`), which are a stored before-column for this row**; and no replayed session set the user date filter (0 of 481 run files).`
- **M2** (P3.9) anchor: `reject an impossible interval, and add a live check to `lex_probe`.` →
  `reject an impossible interval (the case-law twin of `docs/TODO.md` D16 defect 1, which stays parked for legislation), and add a live check to `lex_probe`. **The working date form is not in the published API spec** (`public_api.yml` documents no date parameter; `docs/LEGAL_DATA_SOURCES.md` section 4), so say so in the code, as P3.22 does for `order=relevance`.`
- **M3** (P3.22) anchor: `under both orderings at `per_page=50`; report the overlap, and` →
  `under both orderings at `per_page=50` (**at 2026-10-02: 1,257 stored calls, 612 distinct query, court and date tuples over 22 directories, so about 1,224 requests for both orderings, to be paced under the published 1,000 per five minutes, P4.19**); report the overlap of the set and of the first three (**the Phase-2 nudge in `agent_shared.py` names `results[:3]` as the most relevant cases, and under the default order they are the three newest: 506 of the 1,257 stored calls returned more than three results, against 123 that filled the 50-row page**), and`
- **M4** (P3.23) anchor: `so a negative drawn from it says what was searched.` →
  `so a negative drawn from it says what was searched. **Two constraints, found 2026-10-02 (batch 5 C):** (1) `agent_shared.py` keys the zero-result note and the Phase-2 nudge on `total`, and a `last`-link figure is an upper bound that need not be 0 for an empty first page, so keep those keyed on the shown count, as P1.3 kept `returned` apart from `total_matched` for legislation; (2) the measured scale is about one call in ten: of 1,257 stored calls, 123 filled the 50-row page, 658 returned 1 to 49 (the whole matching set at the default page size) and 472 returned none (`caselaw_census.py`).`
- **M5** (P4.19) anchor: `backs off on 429/502/503/504.` →
  `backs off on 429/502/503/504. **Note (batch 5 C):** the helper also retries a timeout or transport error up to three times, which neither call does today, so say in the tests whether that is wanted at the case-law calls' 15 s timeout; and `_fetch_judgment_text` opens its own client, so it needs one passed in or built for the helper.`
- **M6** (P4.8) anchor: `**Evidence:** 6335. **Depends on:** — **Research-type caveat` →
  `**Evidence:** 6335. **Recounted 2026-10-02 (batch 5 C, `label_leak_census.py`, 57 directories, 1,943 answered turns): still the same 7, each at the start of the answer, and each a Research-mode replay of one of P0.5's twelve sessions (6333, 6343, 6350, 6335), whose lawyers used Conversational mode; 0 in any Conversational or Deep Research turn. No full sweep has run since `wave2`, so the acceptance's next full sweep has not happened.** **Depends on:** — **Research-type caveat`
- **M7** (P4.12) anchor: `after a (b), the Manager's retry answered 2 of 8 (both on inferred sites).` →
  `after a (b), the Manager's retry answered 2 of 8 (both on inferred sites). **Recounted 2026-10-02 (batch 5 C, the same command over 57 directories): 8 Manager (b) calls, 6 unrecovered; after a (b) the Manager's retry answered 2 of 15. The three new unrecovered calls are in `wave4_b2_post` (6345 r3 t4, `p32_6406` r1 t7) and `wave4_p33_post` (`p32_6406` r3 t3).**`
- **M8** (P3.10) anchor: `**Evidence:** 6382 6383 6374 6409 6341. **Depends on:** P2.7` →
  `**Evidence:** 6382 6383 6374 6409 6341. **Re-counted 2026-10-02 (batch 5 C, `p310_dependent.py`, the Session 15 regex from `SESSION_LOG.md`): over the directories that existed at Session 15 it reproduces exactly (136 plans, 34 with a dependent step, 12 of 42 dependent steps halted, 53 of 452 others). The one later directory holding dependent steps after P3.1, `wave3_p38` (6374 and 6383, n=3), has 0 of 8 dependent steps halted (other steps 1 of 25); 6382 was last replayed in `wave2_p21`. The halt premise is not yet re-established at HEAD.** **Depends on:** P2.7`
- **M9** (External review table) anchor: `| 6 Case-law date filtering and ordering | New **P3.9** (dates, verified live); ordering held below |` →
  `| 6 Case-law date filtering and ordering | New **P3.9** (dates, verified live); ordering ~~held below~~ verified 2026-10-02 and booked as **P3.22** |`
- **M10** (Merging back) anchor: `**Nothing is pushed to `main` until the whole plan is concluded (user decision, 2026-09-15).**` →
  `~~**Nothing is pushed to `main` until the whole plan is concluded (user decision, 2026-09-15).**~~ **Superseded by the user (2026-09-22, then 2026-09-24 for release numbers): the branch is cut to `main` when the user asks. Three cuts so far, the last release `v2026.09.3`; see the deployment note above the Ledger and CLAUDE.md *Releases*. The two paragraphs below record the 2026-09-15 policy and are history.**`
- **M11** (Re-planning protocol) anchor: `they are not blockers for anything in Waves 0–4.` →
  `they are not blockers for anything in Waves 0–4, **except P3.20 (Wave 3), which builds what P5.2 decides (booked 2026-10-02)**.`
- **M12** (Wave 5 intro) anchor: `them, which is the only reason they are still open.` →
  `them~~, which is the only reason they are still open~~. **As at 2026-10-02: P5.1 and P5.3 are answered; P5.2 waits on the user's decision now that a source is found (its row); P5.4 is a probe we run ourselves, not a question to send.**`
- **M13** (P3.20) anchor: `PDFs whose text extracts cleanly, Open Government Licence.` →
  `PDFs whose text extracts cleanly (measured with `pypdf`, which is not in `requirements.txt`; the product's `pdfplumber` is untried on them), Open Government Licence.`
- **M14** (P3.20) anchor: `**Evidence:** 6375 6359. **Depends on:** P5.2, P2.4 |` →
  `**Evidence:** 6375 6359. **Depends on:** P5.2, P2.4. **Related:** P3.18 (done) and P3.3 also grade 6375 on English authority presented as Scots law, and 6375's primary bucket is B11; P4.19's retry and P3.23's shown-versus-total split are the shapes to copy for this tool. |`
- **M15** (P5.2) anchor: ``Full detail, request shape and a reproduce command: `docs/LEGAL_DATA_SOURCES.md` §3.`` →
  ``Full detail, request shape and a reproduce command: `docs/LEGAL_DATA_SOURCES.md` §3. **The build it leads to is booked as P3.20 (2026-10-02), which depends on this row's decision.**``
- **M16** (P4.3) anchor: `**Evidence:** 6378 6372 6335 6359 6367.` →
  `**Evidence:** 6378 6372 6335 6359 6367. **Checked 2026-10-02 (batch 5 C, `p43_before.py`): the acceptance's 6378 instrument is already in the answer body in 2 of 2 answered turns of each run taken since `wave2` (`wave2`, `wave4_p37_reach_pre`, `wave4_p37_reach`; n=1 each), against 0 of 2 in `baseline` and `wave1`, so that half would pass before any build.**`
- **M17** (P4.9) anchor: `rows without stamps (pre-column) render none.` →
  `rows without stamps (pre-column) render none. **Note (batch 5 C, 2026-10-02):** `client/package.json` has no `test` script and the client has no test runner, so say how this is checked (a pure helper exercised by a Node assertion script, or a recorded render check as the tracker's was). Related: `docs/TODO.md` D20 (a step's outcome in the chat UI) is the other display-only client change, and one `client/dist` rebuild can carry both.`

M10-M12 restate decisions already recorded elsewhere (the deployment note, CLAUDE.md, P3.20's
row); the integrator may class them as semantic. The rest add verified facts or relationships and
change no premise, acceptance or status. **Conditional, not mechanical:** if the user takes C4
(B12), P3.22's sentence beginning `**Not in a bucket's closure list:** 6363 is not classified to
a retrieval-ranking bucket` needs replacing, and C1, C5, C6, C7 each carry the row text that
would follow.

## 6. Cross-document statements that are now false (X1-X13; nothing edited)

| # | File | Exact current text | The true text |
|---|---|---|---|
| X1 | `CLAUDE.md` :22 (fix/prepilot-defects paragraph; also on `main`) | "One finding from that work is load-bearing enough to state here: **`_matches_jurisdiction` (`agent/tools/lex.py`) drops every legislation search result whose `extent` is *stated* whenever a jurisdiction filter is set, and keeps only those whose extent is missing.**" and "Until P1.1 lands, any measurement taken with a jurisdiction filter active is measuring an arbitrary unknown-extent subset, not retrieval quality." | Past tense: it **did**, until P1.1 (2026-09-14, on `main` since `v2026.09.1`); the function now applies the "applies in" rule (`lex.py:148ff`). Measurements taken before P1.1 (the Wave 0 baseline) measured that subset. |
| X2 | `CLAUDE.md` :24 | "Still unused: three explanatory-note endpoints." | Seven of the 13 are unused: the three explanatory-note endpoints, `/amendment/section/search`, `/legislation/proxy/{id}`, `/api/stats` and `/healthcheck` (code grep: six endpoints called; the `external-apis` skill's table lists the rest). |
| X3 | `CLAUDE.md` :237 (*Releases*) | "`v2026.09.1` (`d8fd73b`) and `v2026.09.2` (`c77e779`) are the two pre-pilot cuts, tagged retroactively." | Three pre-pilot cuts: `v2026.09.1` (`d8fd73b`) and `v2026.09.2` (`c77e779`), tagged retroactively, and `v2026.09.3` (`a6b4a76`), tagged at the cut. |
| X4 | `CLAUDE.md` :244 (*Releases*) | "Stamping the version on the audit event and on `request_timings` waits until after the next cut, because `main`'s audit schema is v5 while the branch's is v6, and bumping it on `main` would create two different v6s." | Both carry `AUDIT_SCHEMA_VERSION = 6` since `v2026.09.3` (`audit_trace.py:77` on `main` and the branch); `TODO.md` D19 already says "Unblocked 2026-09-29". It is a pending decision, not a blocked one. |
| X5 | `CLAUDE.md` :61 (outside the two named sections; flagged because CLAUDE.md loads every session) | "strips the API response to `legislation_id`, `title`, `url`, `status`, `year`, and `extent` only." | `status` is emitted as `text_version` since P2.5 (`lex.py:70`). |
| X6 | `summary-table.html` :421 (the Fixed definition) | "Every Fixed row is merged to <code>main</code> for deployment to the target" | Every Fixed row **with a version** is merged; the five "Next release" rows (P3.16, P4.15, P4.16, P4.17, P4.18) are on the fix branch only. |
| X7 | `summary-table.html` :422 (imprecise rather than false) | "P5.2 is waiting on an external decision." | P5.2 waits on the user's decision (a source was found 2026-10-02); the external step is SCTS's confirmation before P3.20 is built. |
| X8 | `PARALLEL_BATCH_4.md` "Open with the user" | "which rows go in the next cut (`v2026.10.1`; P3.16, P4.16 and P4.15 are "Next release");" | Five: P3.16, P4.16, P4.15, P4.18 and P4.17. |
| X9 | `PARALLEL_BATCH_4.md` "Open with the user" | "the two change-record id mis-expansions;" | One: batch 4 D showed the other summary gave the right year (Session 36 handover). |
| X10 | `docs/LEGAL_DATA_SOURCES.md` §2.2 | "**P2.2**: negative answers state what was searched and that 2026 coverage is under 5%" | "under 10% of instruments made in 2026" (`search_scope.py:138`, `:2523`). P5.3's ticked row repeats "under 5%" (history; P2.2's row has it right). |
| X11 | `docs/TODO.md` D19, first paragraph (stale) | "a *Releases* section in CLAUDE.md (on `main` only until the next cut)" | The branch has carried it since the third cut's fast-forward. |
| X12 | `PARALLEL_BATCH_5.md` :68 (and Session 36's second addendum, history) | "`plan_status`'s counts are right (it reads ticks, not the index)." | Row counts read ticks; bucket counts read the index's B-lines for membership and the ticks for state; the `*(no bucket)*` line is ignored. |
| X13 | `FIX_PLAN.md` itself | the Merging back policy, the Wave 5 intro, the Re-planning protocol's Wave 5 sentence, Thomas table row 6 | M9-M12 above. |

**Checked and consistent (no false statement found):**
- `CHANGELOG.md` *Unreleased* lists all five rows fixed since `v2026.09.3` (P4.15, P4.17, P4.18,
  P4.16, P3.16 as "already in 2026.09.3, ticked since"), and every product file changed since the
  tag (`git diff --stat v2026.09.3 HEAD -- server_py/src client/src`: `agent_core.py`,
  `prompts.py`, `openers.py`, `search_scope.py`) maps to an entry (P4.17, P3.17's lever, P4.16,
  P4.15/P4.18). Nit only: P4.16 (B6) sits under the "Interpretation" heading.
- `summary-table.html` `ROWS` (68 rows, 41 Fixed): every Fixed ref is `[x]` and every `[x]` ref
  is Fixed; P5.2 In progress matches `[~]`; every open ref is Verified; every Fixed row's `fixed`
  equals the date of the first commit showing it `[x]`, and every `ver` equals the first release
  tag whose FIX_PLAN shows it `[x]` (`$C/tracker_check.py`, 0 mismatches beyond the next line).
  The one flagged line, `P2.3 "To be verified"`, is Thomas's held enabling-power item, whose ref
  is where it went; not an inconsistency. Ticked rows absent from the tracker: P0.1-P0.3, P1.5,
  P2.10 (folded), P5.1, P5.3; open row absent: **P0.4 `[~]`** (an omission, the user's call).
- `docs/TODO.md`: D16's "no `year_from <= year_to` check" still true (no such check in
  `executor.py`); B6 still open (`routers/research.py:82` still a generic 502), matching the
  tracker's Verified; D20's "about line 213" is `useChat.js:215`; D21's injection is at
  `agent_core.py:710`; D22 is an idea, as recorded. T3 still open.
- `CLAUDE.md`'s third-cut line (merge `1e30774`, 41 of 59, 8 of 14) and tags agree with git.

## 7. Decisions for the user (C1-C9)

**C1. P5.2 and P3.20: how the decision and the build relate.**
- **(a) Recommended.** The user records P5.2's decision ("Scottish case law from SCTS, subject to
  SCTS's reply") and P5.2 is ticked on it; the note to SCTS becomes the user's action, like the
  lawyer pack, and stays a P3.20 prerequisite. B12 then waits on P3.20 alone (status unchanged).
- **(b)** Keep P5.2 `[~]` until SCTS replies, so P5.2 means "decided and confirmed"; P3.20 waits
  on it. More conservative; the lead time is unknown.
- **(c)** Fold P5.2 into P3.20 and mark P5.2 `[-]`. Not recommended: the plan keeps decisions and
  builds apart everywhere else.

**C2. P3.9, P3.22, P3.23 and P4.19: one build or four, and in what order.**
- **(a) Recommended.** One session, four commits: P4.19, P3.23 (stating today's order, newest
  first), P3.9; then P3.22's paced $0 measure-first, a replay before-column at that head, P3.22
  (flipping P3.23's wording), the after-column. Only P3.22 is replay-measured, and its
  before-column contains the other three (Invariant 3). Book a ground truth of the authorities
  6363 and 6359 need first, so P3.22's bar is not non-regression only.
- **(b)** Four separate rows in four sessions, each measured alone. Same content, slower.
- **(c)** P3.22 first (the visible gain), then the others; P3.22's before-column must then be
  retaken after them, or P3.22's measure misses their effect.

**C3. The National Archives licence is recorded nowhere in the plan or `TODO.md`.**
`LEGAL_DATA_SOURCES.md` §4: TNA's Open Justice Licence excludes "computational analysis",
including "building services or products using AI or large language models"; a free licence is
required and no application is on record. Four open rows build further on that feed.
- **(a) Recommended.** Book it as an external item (a `TODO.md` entry or a Wave 5 row: apply for
  the free licence), the user's or the organisation's action, noted on P3.9, P3.22, P3.23 and
  P4.19 without blocking them.
- **(b)** Make the four rows depend on it, so nothing more is built on the feed until it is
  granted.
- **(c)** Leave it in `LEGAL_DATA_SOURCES.md` only.

**C4. Where P3.22 sits in the Bucket index.**
- **(a) Recommended.** B12, as "(case-law ranking: 6363's recency complaint)": 6363's frozen
  diagnosis is recency bias and is classified B12, which is partial, so nothing reopens; B12's
  closure then also waits on P3.22, which stops B12 counting 6363 closed when SCTS lands (SCTS
  does not change the National Archives' ordering). P3.22's "not in a bucket" sentence is
  replaced to say so. **Caveat:** Session 15 recorded (from Thomas) that 6363's "no foundational
  authority" answer was P4.5's empty-report trap, filed under recency; the lawyer's recency
  complaint itself stands, and P3.22 is the only row that addresses it.
- **(b)** *(no bucket)*, as P3.22's row says now; B12 could close with 6363's complaint untouched.

**C5. P4.8 (the result label): build now or keep waiting for a full sweep.**
- **(a) Recommended.** Build the deterministic strip at the Manager return now ($0; P2.1's
  precedent, Invariant 2), and replace "a count of 0 over the next full sweep" with "0 in every
  directory taken after the build": no full sweep has run since `wave2`.
- **(b)** Keep it measure-first until a full sweep exists.
- **(c)** Park it while Research chat mode stays off on the target: all 7 instances are
  Research-mode replays of sessions whose lawyers used Conversational mode.

**C6. P3.10's halt premise at HEAD.**
- **(a) Recommended.** Keep the row open but rebook its acceptance before any build, on what a
  dependent step costs and whether its list matches the earlier step's, not on the halt rate
  alone, which can now pass vacuously (0 of 8 at `wave3_p38`).
- **(b)** Park it until a sweep at HEAD shows dependent steps halting again.
- **(c)** Build option (a) of the row (the planner merges dependent steps) as written.

**C7. P4.3's acceptance.**
- **(a) Recommended.** Book a measurable acceptance before building, as P3.2/P3.3 did: an
  unused-source rate on report turns with a bar, and a links-retained count (Thomas 7, measured
  as P2.4's A/B was); keep 6378 as a regression check, since it already passes.
- **(b)** Keep it as written; the 6378 half passes without code and the rate has no bar.
- **(c)** Split the link-retention half (Thomas 7) into its own row.

**C8. The bucket placements in section 4.**
- **(a) Recommended.** Accept the table: three ticked rows join a bucket (P2.6 to B1, P4.4 to B12,
  P5.3 to B5), P3.22 per C4, everything else on the no-bucket line; no bucket's status changes.
- **(b)** Put each residual into its parent's bucket (P3.12 to B10, P3.14 and P3.23 to B5, P4.9 to
  B7, P0.7 to B7, P0.4 to B13): reopens B5, B7, B10 and B13 in `plan_status`.
- **(c)** Put the ticked rows on the no-bucket line too, keeping bucket lines for the rows that
  close them by design.

**C9. Where X1-X5 (CLAUDE.md) are fixed.** The same false text is on `main` (the files differ by
one line).
- **(a) Recommended.** On the branch now (the integrator's path); `main` gets it at the next cut.
- **(b)** On `main` directly (unrelated work commits straight to `main`), then merged into the
  branch.
- **(c)** Both, now.

## 8. Numbers, commands, scratch

Scratch: the worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch5/C/`
(`git check-ignore -v` → `.gitignore:113`), **copied with a shell `cp -r` to
`C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch5/C/`** (it worked: 21 files in
each, before this note's final edit; the note itself is committed, not copied).
Scripts print counts and session/rep/turn keys only; `p43_before.py` takes the instrument id on
the command line so no committed file holds it.

| Number | Command (`R` = `C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`) |
|---|---|
| 46 of 69 rows, 8 of 14 buckets | `python -m tools.plan_status` |
| 1,257 case-law calls, 88 dated, 123 / 658 / 472 / 4 (50 / 1-49 / 0 / raw not JSON), 506 over three, 612 distinct tuples, 22 directories | `python $C/caselaw_census.py R` |
| dated calls by session (6385 27, 6346 scripts 61) | `python $C/caselaw_by_session.py R` |
| 0 of 481 run files with a user date filter | `python $C/user_date_filter.py R` |
| label: 7 in 1,943 answered turns, all Research mode | `python $C/label_leak_census.py R` |
| P3.10: 136 / 34 / 12 of 42 / 53 of 452; `wave3_p38` 0 of 8 | `python $C/p310_dependent.py R` |
| P4.3: 6378 instrument in answers per run | `python $C/p43_before.py R 6378 <the row's SSI id>` |
| P4.12: 8 Manager (b), 6 unrecovered, retry 2 of 15 | `python -m tools.replay_report --dir R/wave4_b4_post lostcost --all-dirs` |
| tracker against ticks, dates and tags: 0 mismatches (P2.3's held item explained) | `python $C/tracker_check.py` (repo root) |
| placement effects | `python $C/placement_sim.py` (from `server_py/`) |
| M1-M17 anchors and the amended copy | `python $C/amendments.py docs/prepilot-fixes/FIX_PLAN.md --apply $C/FIX_PLAN.amended.md` (repo root); `python $C/plan_status_amended.py` |
| 2135 tests | `TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_c python -m pytest -q` |

Matches read: no answer text. The 7 label turns and the 6378 answers were counted by script
(keys and counts only); one classification entry was read (6363's diagnosis, quoted in section 1
without its matter); and the code sites named in section 1.

## 9. What I did not do

- No edit to `FIX_PLAN.md`, `SESSION_LOG.md`, `CHANGELOG.md`, `CLAUDE.md`, `summary-table.html`,
  `docs/TODO.md`, `LEGAL_DATA_SOURCES.md`, any `PARALLEL_BATCH_*.md`, a rubric or a memory file.
  Nothing pushed or merged; `main` untouched.
- No live probe: P3.9's, P3.22's and P3.23's live claims (the feed's date form, default order,
  the page-size reset, the `last` link) are taken from their rows and §4, not re-checked.
- Rows outside my list (agent B's) not reviewed, beyond the bucket placements for all 21.
- History (ticked rows' annotations, old recommended-order lines) not re-read or amended, except
  where a ticked row's statement contradicts a current document (P5.3, noted under X10, no
  amendment proposed).
