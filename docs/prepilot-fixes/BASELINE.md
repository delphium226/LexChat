# Baseline — does the pre-pilot failure still happen?

**FIX_PLAN row P0.3.** Every acceptance test in Waves 1–4 is a comparison against this file.
Without it a row that goes green cannot be distinguished from a failure that stopped occurring
on its own, and three weeks of commits landed between the pre-pilot (11–21 Aug 2026) and this
branch.

| | |
|---|---|
| **Run date** | 2026-09-14 |
| **Branch / HEAD** | `fix/prepilot-defects` @ `bc8e7a4` (Wave 0 only — no product code changed) |
| **Model** | `google/gemini-3.1-pro-preview` via OpenRouter, pinned in `app_settings → provider.openrouter` |
| **Summarisation model** | `google/gemini-3-flash-preview` — **not pinned**, see *Known confounds* |
| **Feature flags** | `local_prompt_cache` **OFF**; `tool_memo`, `prompt_caching`, `suggested_questions` ON |
| **Sessions** | 41 (25 FAIL, 16 DEFECT), 155 user turns, 20 of them Deep Research |
| **Repetitions** | n=1 over all 41, then n=3 on the 12 sessions the first pass did not settle — **complete** |
| **Spend** | **$61.28** total: $37.62 for the n=1 pass (6.0 h) + $23.66 for 24 targeted reps |
| **Harness** | `server_py/tools/replay.py` → `/api/system/chat`, `audit` trace captured per turn |
| **Raw output** | `evidence/replay/baseline/` (gitignored — lawyers' verbatim casework questions) |

Reproduce this file's numbers with:

```
python -m tools.replay_report --dir ../docs/prepilot-fixes/evidence/replay/baseline summary
```

---

## Wave 1 re-baseline (FIX_PLAN P1.5) — the second column

| | Wave 0 | Wave 1 |
|---|---|---|
| **Run date** | 2026-09-14 | **2026-09-15** |
| **HEAD** | `bc8e7a4` (no product code changed) | **`4c8878c`** — Waves 0+1. Run files record `6a5eeea`, which was rewritten mid-sweep by the ServerLogs purge: same tree minus those logs, **no product code touched during the sweep** (verified by diff). |
| **Model** | `google/gemini-3.1-pro-preview`, pinned | same, pinned; **0 mismatches** |
| **Scope** | 41 sessions, 155 turns | **identical** — 41 / 155, 0 errored turns |
| **Repetitions** | n=1, then n=3 on 12 unsettled | **n=1** — see *What this column cannot settle* |
| **Spend / wall clock** | $37.62 / 6.0 h | **$27.22 / 3.7 h** |

Reproduce with:

```
python -m tools.replay_report compare --before <baseline rep-1 only> --after ../docs/prepilot-fixes/evidence/replay/wave1
```

**The rep-1 restriction is load-bearing.** The baseline directory holds 65 run files (the n=1 pass
plus 24 targeted repetitions); a Wave 1 sweep holds 41. Comparing the directories whole inflates
every Wave 0 figure by roughly half — 2,354 searches against 1,531, before any code is measured.
`compare` restricts both sides to rep 1 and sums totals over the sessions present in both.

### What Wave 1 did

| | Wave 0 | Wave 1 | |
|---|---|---|---|
| searches emptied by filters | 351 / 1,531 | **3 / 790** | **−99%** |
| filters demonstrably bit | 478 | **10** | −98% |
| rows lost to filters (floor) | 2,147 | **37** | −98% |
| `total` not passed to the model | 1,010 | **0** | **−100%** |
| `search_legislation` calls | 1,531 | **790** | −48% |
| worker delegations | 278 | **197** | −29% |
| spend / wall clock | $37.62 / 6.0 h | **$27.22 / 3.7 h** | −28% / −38% |

**B2 and B5 are closed.** All 13 jurisdiction-filtered sessions went to zero emptied searches. The
only residual — 3 in 6357 — is `legislation_type=primary` correctly excluding SSIs, checked row by
row: the dropped rows are `ssi/2022/54` and siblings, which a primary-only filter is meant to drop.

**The defect cost money and time, not just results.** Search volume nearly halved and the sweep ran
2.3 hours faster for the *same 155 turns*. When every search came back empty the model kept
reformulating and retrying; with the filter working it finds what it needs and stops. Clearest
cases: 6396 **172 searches → 1**, 6381 **80 → 6**, 6374 166 → 41, 6383 163 → 26, 6357 93 → 14
($1.47 → $0.41, 18.9 min → 4.9 min). FIX_PLAN scoped B2 purely as lost results; it was also a
latency and cost defect.

### B14 — the metric says regression, the truth is the opposite

`bad_links` went **20 → 32** and reads as P1.4 backfiring. It is not. That metric asks whether a
link points at the *granularity* its label names. It cannot ask the question that matters: **was
this provision URL ever returned by a tool, or did the model build it by appending `/section/{n}`
to an Act's base URI?**

| | Wave 0 | Wave 1 |
|---|---|---|
| provision URLs cited | 327 | 136 |
| **manufactured — never returned by any tool** | **327 (100%)** | **26 (19%)** |

100% is not a rounding artefact. Before P1.4 the Worker prompt *instructed* the model to append
`/section/{number}`, so every provision URL in the corpus was invented. Most carried the right
number, so the old checker scored them **good** — a URL pointing at a provision the system never
retrieved, resolving to a real page, reading to a lawyer as a verified citation. That is more
dangerous than a link which merely misses its provision, and it is what P1.4 actually fixed.

The 32 flagged links are the residue of honesty: forbidden from inventing a URL and lacking a
retrieved one, the model now links the Act's contents page while naming a section. 6348 is the
clean case — **zero** provision-level URLs were returned by any tool in that run, yet it cites
FOISA ss.36 and 55. **The bad link is a symptom of citing an unretrieved provision**, which the
manufactured URL previously concealed. Measured by the new `provision_links_manufactured` signal.

**The residual 19% is a live defect**, not noise: the model still disobeys where it holds only an
Act-level URL (6365 appends `/section/21` and `/section/22` to `asp/2000/1`). Invariant 2 says
replace the instruction with enforcement — new row **P1.6**.

### What did not improve, and what got worse

| | Wave 0 | Wave 1 | |
|---|---|---|---|
| unsupported in-force claims | 27 | **30** | **+11%** |
| runs with a halted worker | 10 | 10 | = |
| runs showing halt text | 9 | 6 | −33% |
| **turns halted with NO mention** | 2 | **5** | **+150%** |
| turns citing none of their sources | 62 | 59 | −5% |
| billed-but-empty turns | 4 | 2 | −50% |

**B4 did not fall, and that settles P1.5's open question: P2.5's scope does not shrink.** The
hypothesis was that P1.2 removed the prompt line causing the in-force claims, so a sharp fall would
shrink P2.5 before it is written. It rose. The mechanism is in P2.5's row: three sites in
`prompts.py` still *instruct* the Worker to state in-force status (line 111: *"note … if the
legislation is in force"*), and the only metadata it has is LEX's `status`, vocabulary
`final`/`revised`, meaning *which text version is held*. P1.2 removed the filter's constraint
block; the instruction survived it. Nearly every claim still reads *"currently in force (status:
revised)"*.

**The halt total is unchanged but redistributed, and silent halts more than doubled.** Halt text
shown fell 9 → 6 while halts disclosed to nobody rose 2 → 5 — the exact trade P2.1's rewritten
acceptance guards against, occurring here with **no code change at all**, which is what makes it
stochastic rather than progress. Per session the movement is large in both directions: 6396 4 halts
→ 0 and 6408 3 → 0, against 6409 0 → 3 and 6383 0 → 1.

**Cap pressure rose** — p90 tool calls per delegation 15 → 20 (the p90 delegation now sits *at* the
cap), and delegations at or over 20 went 6.3% → 11.2%. Fixing retrieval generates Phase-2 work
where an emptied search was simply retried. Recorded in P2.1: **the cap decision must not be taken
on the Wave 0 numbers.**

### Sessions whose verdict changed, and why

- **6381 — now answers, and the cause was B2.** Wave 0 said *"I am unable to locate the Victims and
  Witnesses (Scotland) Act 2014"* three times: honest failure, correct under Invariant 1, and
  caused by the filter emptying 30 of 80 searches. Wave 1 finds it and answers from `asp/2014/1`,
  one delegation per turn instead of six. **A cause removed, not a new fix** — and not a lowered
  evidence bar: the Act cited is the right one.
- **6396 — a B10 case resolved by fixing B2.** Wave 0 spent 16 delegations and 172 searches, halted
  four workers, and answered from a superseded **1984** Order. Wave 1 retrieves the correct modern
  instrument (Cattle Identification (Scotland) Regulations 2007, `ssi/2007/174`) in **one**
  delegation and one search, $0.04 against $1.11. Suggests part of B10 is downstream of B2 —
  relevant to P3.1's scope.
- **6407 — cost collapsed, links got worse.** $5.99 → $0.50 and both billed-but-empty turns gone,
  but it now carries 19 of the 32 flagged links (Schedule/paragraph citations pointing at
  `asp/2016/10`). The single largest contributor to the B14 count.
- **6340 — a different failure again.** Wave 0 rep1 was a 69-char non-answer for $0.02; Wave 1 runs
  29 searches for $1.44 and halts a worker. A third distinct failure mode across four runs.
- **6370 — both billed-but-empty turns gone** (2 → 0). Not attributable: P4.2 is unbuilt.

### What this column cannot settle

1. **It is n=1.** Wave 0's repetitions overturned three of nine *does-not-reproduce* verdicts, so
   **no session here may be recorded as fixed on this evidence.** The mechanical B2/B5 numbers are
   safe — filter arithmetic is deterministic given the searches made — but *which* searches the
   model makes is stochastic, so rates are firmer than absolute counts and any per-session verdict
   needs n=3.
2. **Three detectors were corrected mid-sweep** — B14's title-year false positives, B1's blind
   paraphrase matching, B8's two-conditions-in-one. Both columns above are computed with the
   corrected instrument; the *original* Wave 0 publication over-counted B14 six-fold and
   under-counted halt disclosures. See the Correction sections below.
3. **Wave 0's confounds all still apply** — unpinned summarisation model, re-drafted Deep Research
   plans, local cache off, no documents or matter context, inferred Deep Research turns.

---

## Headline

**34 of 41 sessions still reproduce their original failure. 7 do not. None are left inconclusive.**

### The repetitions changed the answer, and that is the most important result here

The first pass said 29 reproduce / 9 do not / 3 inconclusive. Running n=3 on the twelve
unsettled sessions **overturned three of the nine "does not reproduce" verdicts**:

| Session | n=1 said | n=3 found |
|---|---|---|
| **6357** | no halt | halt in **2 of 3** reps (2 workers halted in rep2, 3 in rep3) |
| **6389** | no halt | halt in **1 of 3** reps |
| **6396** | answered the question | halted workers in **2 of 3** reps (4 in one) |

A single clean draw is not evidence that a defect is gone — Invariant 4 says so, and this is
the measurement that proves it on this corpus. **No `does not reproduce` verdict in this file
rests on fewer than three runs**, and any future row that claims a fix worked must clear the
same bar. Three of the twelve also showed a *different* failure on each rep (6340: a truncated
non-answer, then a bare negative, then a halt), so "which failure" is stochastic even where
"fails" is not.

The three defects Wave 1 targets are all confirmed present and measurable, and two of them are
**worse than the transcripts suggested**, because the transcripts could only show what the lawyer
saw. The trace shows what the tool did.

| Bucket | Row | Baseline | Verdict |
|---|---|---|---|
| **B2** jurisdiction filter | P1.1 | **351 of 974** searches under a jurisdiction filter returned **nothing** to the model (36%); **478** (49%) demonstrably lost rows; **0 of 557** searches lost anything with the filter off | **Confirmed, cause isolated** |
| **B5** count destroyed | P1.3 | **1,010 of 1,531** searches reported a `total` that was not the API's | **Confirmed, and independent of the filters** |
| **B14** provision links | P1.4 | ~~88 of 376 (23.4%)~~ **20 of 376** provision-labelled links (5.3%) miss their provision — see *Correction* below | **Confirmed, but six-fold smaller than first published** |
| **B1** research halt | P2.1 | **10 of 41** runs had a halted worker; ~~7~~ **9** showed halt text (the detector was blind to a third of the wordings — see *Halt detector* below); **2 halted silently**, telling the lawyer nothing | **Confirmed, and worse than counted** |
| **B4** in-force claims | P2.5 | **27** unsupported in-force assertions across 41 runs | **Confirmed** |
| **B8** sources rail | P4.3 | 1,222 of 1,387 kept sources (88%) never cited; 62 turns cited none of theirs — but **more than half of that is a shadow of B1/B3**, see *B8 split* below. On turns that actually produced a report: **489 of 622 (79%), 9 turns** | **Confirmed, but two conditions were being counted as one** |
| **B13** lost/blank turns | P4.2 | **5 turns** billed >$0 and returned an empty body (a fifth appeared in 6406 rep3) | **Confirmed** |

---

## B2 — the jurisdiction filter, measured from both sides

The single most useful thing the `audit` trace does: a `search_legislation` tool record holds the
LEX response in `api_calls[].response` **and** the text the model received in `final_result`. Both
counts, one record, no inference.

```
api total=97  results=20   ->   final_result {"results": [], "total": 0}
```

| | runs | searches | returned nothing | demonstrably lost rows | rows lost (floor) |
|---|---|---|---|---|---|
| `jurisdiction` set | 13 | 974 | **351 (36%)** | 478 (49%) | ≥2,147 |
| `legislation_type` set | 2 | 128 | 69 | 84 | ≥394 |
| neither set | 28 | 557 | **0** | **0** | 0 |

Zero loss with the filters off is the attribution: the filters are the entire cause.

### The plan's headline needs one correction, and it makes the defect worse

`FIX_PLAN` and `CLAUDE.md` both say `_matches_jurisdiction` "discards 100% of legislation search
results whenever a jurisdiction filter is set." Measured, it is sharper than that:

> Of the **1,009 result rows that survived** a jurisdiction filter across the whole baseline,
> **every single one had `extent: []`** — a *missing* extent. Not one row carrying a real extent
> value survived.

`_matches_jurisdiction` opens with `if not extent: return True`, so rows whose territory is unknown
pass, and every row whose territory is *stated* — including `['Scotland']` under
`jurisdiction=scotland` — is dropped. The API emits eight distinct extent values across this
corpus (`['Scotland']`, `['England','Wales','Scotland']`, `['United Kingdom']`, `['']` and so on);
the filter admits only the ninth, which is the absence of one.

**This is why 13 sessions ran with it and nobody reported a broken filter.** A filter that returns
nothing looks broken. This one returns a plausible, non-empty result set composed entirely of
unknown-territory items — in 6354 a Scotland-filtered search returned the *Building Materials and
Housing Act 1945*. It fails selectively, not closed.

**P1.1 must therefore fix two things, not one:** map the real vocabulary, *and* decide what
`extent: []` means. Treating unknown as "include" is what currently makes the failure invisible.

---

## B5 — the count, and why it is a separate row from B2

`executor.py:227` sets `slimmed["total"] = len(results)` after truncating to 5. The model is told
"5 matched" when the API said 189. **1,010 of 1,531 searches** misreport it, including **438 of
557 with no jurisdiction or type filter at all** — so this is not a side-effect of B2 and P1.3
does not become unnecessary if P1.1 lands first.

**Measurement note for whoever executes P1.3.** `executor.py` also caps every search to
`results[:5]` *after* filtering. That cap is deliberate slimming, not a defect, and a "rows lost"
figure that ignores it attributes ordinary truncation to the filters and overstates B2 several-fold
— it did in this file's first draft. `replay_report.RESULT_CAP` encodes it: a search returning
exactly 5 is cap-bound and is counted as evidence of nothing.

---

## B1 — the halt is not confined to Deep Research

**10 of 41 runs** hit the 20-step cap; **7 showed halt text to the lawyer.**

The purest case is **6383 turn 1**, a *conversational* turn whose entire answer to the lawyer was:

```
[Research halted: exceeded 20 tool-call steps]
```

That is the raw internal string, unmodified, as the whole reply. `chat_loop` returns the halt as
the worker's assistant content, so it escapes through a plain Manager delegation as well as
through `run_deep_research` — **a fix at the `run_deep_research` site alone leaves that path
open.** See the amended P2.1.

Where the halt does *not* surface raw, it surfaces as invention. 6340 told the lawyer the agent
"exceeded its operational limits (timed out)" — it hit a step cap, not a timeout — and supplied a
cause: *"a broad enabling power has generated a very large volume of statutory instruments over
several decades."* The Act in question is a 404 in LEX. **Invariant 1 bites here:** this reads as
honest failure and is not one.

### How close is normal work to the cap?

| tool calls per worker delegation (n=250, cap=20) | |
|---|---|
| median | **5** |
| p90 | 16 |
| max | **41** |
| at 18 or more | 23 (9%) |

The median worker is nowhere near the cap; the tail runs well past it. Raising the cap would
change behaviour for ~9% of delegations and nothing else — useful input to P2.1's deferred
question, which should still be decided from `request_timings.max_turns_halted`, not from here.

---

## Halt detector — it was blind to a third of the disclosures, and to a worse failure

`HALT_PARAPHRASE` required near-exact wording ("operational limit", "research was halted").
The model does not paraphrase to a script. Across the whole baseline, **17 turns had a halted
worker and the detector flagged 9**; widened and re-validated, it flags **14**. What it had
been missing:

- *"exceeded its **processing** limits (timed out)"* — 6335 t7
- *"**timed out** while searching"* — 6341 t5, 6345 t4
- *"exceeded the maximum **permitted steps**"* — 6340 rep3
- *"Research Step 2 (…) **was halted** by the system"* — 6389 rep3, where an intervening
  clause defeated `research (?:process )?was halted`

On the rep-1 pass the corrected count is **9 runs showing halt text, not 7**.

### The failure nobody named: the silent halt

**2 turns in the rep-1 pass (3 across all 65 runs) halted a worker, returned a normal-looking
report, and never mentioned it.** 6396 rep1 halted **four** workers and the answer says nothing.
The lawyer is handed an incomplete answer with no signal that it is incomplete — which under
Invariant 1 is worse than the halt text leaking, because a visible halt at least tells them to
distrust it. Counted separately as `halts_undisclosed`; a turn with an *empty* body is B13 and
is deliberately not double-booked here.

**This changes what P2.1 may be accepted on.** "No halt text in the answer" is satisfied by a
silent halt, so the trivially-passing implementation of that row is to suppress the message —
the worse outcome. The row has been rewritten accordingly.

Note also that **6383 turn 1's halt never appears in any delegation report** — the raw string
was the whole answer, via the conversational path — so an acceptance check that inspects only
`delegations[].report` is blind to the corpus's starkest case.

---

## B8 split — most of the uncited sources belong to turns that never answered

The 88% is true but it answers a different question from the one P4.3 asks. Splitting the
136 source-carrying turns by whether they produced a report at all (>=1,200 chars):

| | turns | sources kept | uncited | turns citing none |
|---|---|---|---|---|
| produced a report | 57 | 622 | **489 (79%)** | **9** |
| no report — halt, disclosure, truncation | 79 | 765 | 733 (96%) | 53 |
| combined (as first published) | 136 | 1,387 | 1,222 (88%) | 62 |

**765 of the 1,387 kept sources hang off turns that never produced a report**, and 53 of
the 62 turns citing none of theirs are failures of other buckets. They are not the model
consulting a source and declining to cite it; they are B1 halts and B3 false negatives with
the rail left showing whatever the Worker had accumulated. The rail is at its most
misleading precisely when the answer failed — **6341 turn 5 shows 40 sources behind a
333-character message saying the agent timed out.**

Two consequences:

- **B8 is real but smaller than published.** A completed report leaves 79% of its retrieved
  sources uncited, which is still worth P4.3. The headline was not wrong, it was two
  conditions added together.
- **P4.3 cannot be measured before P2.1.** Fixing the halt removes a large share of the 88%
  without touching the sources rail, so a P4.3 number taken now will move for reasons that
  have nothing to do with P4.3. This dependency is not in the plan and has been added.

---

## Correction — B14 was over-counted six-fold (found 2026-09-15, during P1.5)

**This file first published 88 of 376 (23.4%). The true figure is 20 of 376 (5.3%).**
The error was in the measuring instrument, not the data, and it is the fourth of its
kind in this work — the same signature as the other three: *a number that disagreed with
what the code said should happen.*

`replay_report.PROVISION_LABEL` matches the word "regulations" followed by digits. That
fires on the **name of every SI ever cited**: "The Sale of Tobacco ... Regulations 2013"
was read as "regulation 2013", and the checker then demanded `/regulation/2013` in the
URL. **73 of the 88 flagged links were this false positive**, and many of them were links
that were entirely correct — `.../uksi/2020/791/regulation/2`, labelled "…Regulations
2020", was counted as missing its provision.

Two changes fix it: a year-like number (four digits, 1200–2099) is never a provision
number, and the checker now walks **every** candidate in a label rather than the first,
so "The X Regulations 2013, regulation 2" is still checked against `/regulation/2`. That
second half also *adds* true positives the old first-match logic hid, which is why the
corrected count is 20 and not the 15 that simply removing false positives would give.

| | first published | corrected |
|---|---|---|
| all links, rep-1 pass | 88 / 376 (23.4%) | **20 / 376 (5.3%)** |
| 6406 | 43 / 61 | **16 / 61** |
| 6389 | 13 / 18 | **0 / 18** |
| 6375 | 11 / 15 | **3 / 15** |
| 6341 | 10 / 53 | **0 / 53** |

**B14 is still real** — 20 links do miss their provision, and 16 of the 20 are in 6406 —
but it was never the 23% bucket this file claimed, and P1.4's "7× the transcript rate"
headline was an artefact. **P1.4's acceptance is unaffected**: it passed on
`tests/test_search_result_shape.py`, which tests the product, not this detector.

The uncomfortable part is that `tests/test_replay_tooling.py` already pinned
`test_bad_link_*` and those tests passed throughout, because they were written against
synthetic labels that never contained an SI's real title. **A detector can be pinned by a
green test and still be wrong on every real input.** The new tests use the verbatim
strings that were mis-flagged.

---

## B13 — four billed-but-empty turns, and one suspect eliminated

| session | turn | billed | `token` events |
|---|---|---|---|
| 6370 | 2 | $0.0602 | **none** |
| 6370 | 3 | $0.0764 | **none** |
| 6407 | 1 | $0.0420 | **none** |
| 6407 | 2 | $0.0371 | **none** |

All four ran real research first — 6370 turn 2 made 5 tool calls, 5 API calls and produced a
976-char Worker report citing SSI 2017/114 — then returned an empty body, with `status: ok` and
`audit.error: null`.

**None of the four emitted a single `token` event.** P4.2 lists a `<suggestions>` strip consuming
the whole body as its first suspect; that requires a body to strip, and there was never one. The
evidence points at the plan's suspect (2), a tool-call-only final message. Suspect (3), the
stream-retry guard re-raising, is not supported — no error event was emitted on any of the four.

**P4.2's acceptance test cannot assert on a specific turn.** The plan cites 6370 message #8; the
replay blanked at turns 2 and 3, and the pre-pilot's turn 2 answered normally. The invariant the
row already states — non-empty body whenever recorded cost > 0 — is the assertion that survives.

---

## Per-session verdicts

`R` reproduces · `N` does not reproduce · `?` inconclusive. Sessions marked **n=3** were re-run
three times because a single draw does not settle them (Invariant 4).

| Session | | Bucket | | What the replay did |
|---|---|---|---|---|
| 6333 | DEFECT | B10 | R | Still needed three prompts to surface the rest of s.91 |
| 6334 | DEFECT | B14 | **N** *(n=3)* | 0 of 4 links wrong — the defect this session names did not occur |
| 6335 | FAIL | B8 | R | 5 of 11 sources uncited; the 3 dropped turns did not recur |
| 6338 | FAIL | B11 | R | Applied ILRA 2010 to the 2009 Act again, unhedged. The s.35A/35ZA error did **not** recur — it now says the two are not expressly prohibited from running concurrently |
| 6340 | FAIL | B3 | **N** *(n=3)* | Did **not** fabricate the SI list. Returned a truncated non-answer instead — a different failure, and in an earlier run a halt |
| 6341 | FAIL | B4 | R | 3 unsupported in-force claims; halt text shown |
| 6343 | FAIL | B7 | R | Invented UI again: *"via the mode selection or settings menu in your interface"* |
| 6345 | FAIL | B3 | R | Same wrong Act (Transport (Scotland) Act 2005 s.40) three times. Did **not** capitulate when challenged — halted instead |
| 6346 | FAIL | B7 | R | Refused four more times after the lawyer said she had changed the mode. The corpus's worst session, intact |
| 6347 | DEFECT | B7 | R | Mode deflection on turn 1 |
| 6348 | DEFECT | B10 | R | s.36(2) surfaced only when asked for by name |
| 6350 | DEFECT | B7 | **R — worse** | Pre-pilot recovered once the filter was reset; this time *"I have reset the filter"* still produced nothing |
| 6354 | FAIL | B3 | R | SSI 2022/356 still missed; 2 of 3 searches emptied by the jurisdiction filter |
| 6357 | DEFECT | B1 | **R** *(n=3, 2/3)* | **n=1 said no halt and was wrong.** rep2 halted 2 workers and showed the text, rep3 halted 3 and showed it twice. Compounded by a filter failure that worsens across reps — 53, 65 then 79 searches emptied, `legislation_type=primary` blocking every SSI, so it never reached s.85 |
| 6359 | FAIL | B8 | **R — worse** | Now cites *Clark v Harney Westwood and Riegels* [2021] IRLR 528 with a specific report citation. Clark is **absent from the corpus** — apparent fabrication, where the pre-pilot merely cited irrelevant cases |
| 6360 | DEFECT | B9 | R | E&W answer first, Scottish rules only on follow-up |
| 6363 | DEFECT | B12 | R | Recency bias intact — cites 2026 authorities, misses the foundational ones. No blank message this time |
| 6365 | DEFECT | B10 | **N** *(n=3)* | Found the Public Finance and Accountability (Scotland) Act 2000 in the first answer |
| 6367 | FAIL | B5 | **R** *(n=3)* | rep3 states outright that *"the legislation does not prescribe fixed calendar dates for these duties"* — the original defect verbatim in substance. All three reps answer from the Water Industry (Scotland) Act 2002 rather than the Public Finance and Accountability (Scotland) Act 2000, where the deadlines are |
| 6369 | DEFECT | B10 | R | Purpose test still surfaced only after repeated prompting |
| 6370 | DEFECT | B11 | R **+ B13** | Two blank billed turns; *"You are entirely correct"* capitulation openers intact |
| 6372 | DEFECT | B8 | **N** *(n=3)* | Clean on every mechanical signal in all three reps, and all three open by asking which jurisdiction is meant rather than guessing. **Caveat: the misattribution itself is not machine-checkable** — confirming it needs a lawyer to check Rule 35.8 against the instrument cited |
| 6373 | FAIL | B12 | R | Questioned the lawyer's citation twice — *"Could you verify the citation?"*, *"Could you check if the year or the SI number might be different?"* — rather than stating an index limit |
| 6374 | FAIL | B3 | R | Orders in Council under s.126(8) still not retrieved; halt text shown |
| 6375 | FAIL | B11 | **R** *(n=3)* | Bad provision links in every rep — ~~11/15, 10/19, 15/16~~ **3/15, 3/19, 9/16** (corrected detector). The B11 doctrine question (English common interest privilege analysed as Scots law) still needs a lawyer's read, but the session fails on B14 regardless |
| 6378 | FAIL | B8 | R | A UK question answered England-only; SSI 2008/216 still absent from the answer |
| 6380 | DEFECT | B10 | R | Legitimate expectations reached only after a clarifying exchange |
| 6381 | FAIL | B5 | **N** *(n=3)* | **Improved** — now says plainly *"I am unable to locate the Victims and Witnesses (Scotland) Act 2014"* three times instead of answering silently from adjacent statutes. But the non-retrieval is now caused by the filter: 30 of 80 searches emptied |
| 6382 | FAIL | B1 | R | Still zero of the 33 SSIs under s.95; halt text shown. Presentation improved — the report is no longer *only* the halt message |
| 6383 | FAIL | B3 | **R — worst case** | Turn 1's entire answer was the raw string `[Research halted: exceeded 20 tool-call steps]` |
| 6384 | FAIL | B1 | R | *"I am currently unable to retrieve the Courts Reform (Scotland) Act 2014"* — verbatim reproduction. It is in LEX |
| 6385 | FAIL | B12 | R | English authorities only, no Scots-corpus disclosure |
| 6387 | DEFECT | B13 | **N** *(n=3)* | No timeout; all three turns answered |
| 6389 | DEFECT | B1 | **R** *(n=3, 1/3)* | **n=1 said no halt and was wrong** — rep3 halted a worker. Marginal but real; ~~also 13–14 bad provision links per rep~~ **no bad provision links in any rep** — those were all title-year false positives |
| 6396 | FAIL | B10 | **R** *(n=3, 2/3)* | **n=1 said it answered and was wrong.** rep1 halted **four** workers, rep3 halted two; filters emptied 32/172, 6/23 and 16/73 searches across the three. rep2 answered cleanly, which is what a single draw would have recorded |
| 6406 | FAIL | B1 | **N** *(n=3)* | **0 of 4 steps halted** on both Deep Research turns, against 4 of 4 in the pre-pilot. $0.72 and 14,090 chars against $2.36 and a report with no findings |
| 6407 | DEFECT | B1 | R **+ B13** | Two blank billed turns; halt text shown. The most expensive run in the sweep at $5.99 / 50 min |
| 6408 | FAIL | B1 | R | 52 of 92 searches emptied by filters; turn 3 explains the step cap to the lawyer |
| 6409 | FAIL | B3 | R | Commencement SSIs still invisible — *"No commencement regulations have been made yet"* |
| 6410 | FAIL | B3 | R | Same false negative, verbatim. The Care Reform (Scotland) Act 2025 (Commencement No.1) Regulations 2025 exist |
| 6411 | FAIL | B4 | R | Unsupported in-force assertion |

### Why the seven does-not-reproduce

Four are genuine improvements, each confirmed over three runs rather than one:

- **6406** — 0 of 4 Deep Research steps halted in **all three** reps, against 4 of 4 in the
  pre-pilot. The clearest recovery in the corpus.
- **6365** — every rep names the Public Finance and Accountability (Scotland) Act 2000 in its
  opening summary, the Act the pre-pilot reached only when pointed at it.
- **6387** — no timeout in any rep; all three turns answered each time.
- **6334** — no bad provision links in any rep. Note this is *before* P1.4, so it is model
  variance rather than a fix.

Three are **not** improvements, and reading the headline count alone would get this wrong:

- **6340** stopped fabricating the SI list, but produced a different failure on each of the three
  runs — a truncated non-answer, a bare negative, then a halted worker. "Does not reproduce" here
  means "does not reproduce *this* defect", not "works".
- **6381** now discloses plainly that it cannot find the Victims and Witnesses (Scotland) Act 2014
  — in all three reps, which is exactly the honest failure Invariant 1 protects. But the
  underlying retrieval got **worse**, not better: the filter emptied 30 of 80, 26 of 49 and 31 of
  66 searches across the reps. The lawyer is told the truth about a failure that B2 caused.
- **6372** is clean on every signal this harness can compute, but the defect it was classified for
  — provisions attributed to the wrong instrument — is not machine-checkable. It is recorded as
  does-not-reproduce on mechanical grounds only.

**No attribution is claimed for the four genuine recoveries.** The worker context budget and the
Phase-2 fan-out tuning both landed between the pre-pilot and this branch and both reduce tool-call
counts, but separating them from model variance would need its own experiment — and 6396 is a
caution against assuming a recovery is real, since one of its three reps looked like one.

## Known confounds

1. **The summarisation model is not pinned.** The pre-pilot's value is unrecoverable — no
   per-message column records it and that database is not on this machine. Everything here ran on
   `google/gemini-3-flash-preview`. Recorded in `runtime_state` on every run file.
2. **Deep Research plans are re-drafted, not replayed.** The approved plans live in
   `messages.research_plan` on the pre-pilot deployment. Each of the 20 Deep Research turns ran a
   freshly drafted plan, so those turns carry planner stochasticity the originals did not. The
   drafted plan is saved in every run file.
3. **The local prompt cache was off.** Correct for independent repetitions; it means these runs do
   not reflect the cache-hit behaviour a live user would see.
4. **Documents and matter context are not replayed** — both load from `chat_id`, and the pre-pilot
   chats do not exist here.
5. **Which turn ran Deep Research is inferred**, not read from stored state — see P0.4. The
   inference reconciles exactly with the exported thread-level mode on all 62 sessions, but it is
   read off the answer and so is structurally blind to a Deep Research turn that produced none.
6. **n=1 for the 29 sessions the first pass settled.** A verdict of *reproduces* on a single draw
   is safe — the defect was observed. A verdict of *does not reproduce* is not, which is why every
   `N` above was re-run three times, and why three of them flipped.

---

## Cost

| | |
|---|---|
| n=1 over 41 sessions, 155 turns | **$37.62** |
| targeted n=3 on 12 sessions (24 further runs) | **$23.66** |
| **total** | **$61.28** |
| wall clock, serial | ~9 h |
| most expensive run | 6407 — $5.99, 50 min |

Against FIX_PLAN's original ~$50 for a blanket n=3/n=1 pass, the targeted policy landed at $61.28
and bought something the blanket policy would not have: three corrected verdicts, because the
repetitions went to the sessions where the answer was actually in doubt.

Replay costs about **2.3× the pre-pilot's recorded spend** for the same work. The recorded figure
covers only the saved assistant message; a replay also pays for the Deep Research planner call,
which saves no message and is therefore absent from the export. FIX_PLAN's original ~$50 estimate
for a blanket n=3/n=1 pass would have been ~$140 in practice.

Runs are serial by design. Three parallel Deep Research runs fan out to a shared, rate-limited LEX
API; `_request_with_retry` backs off on 429 and eventually returns the error, which would appear
in the trace as a degraded retrieval — a failure reproducing when it did not. A corrupted baseline
costs more than the hours saved.
