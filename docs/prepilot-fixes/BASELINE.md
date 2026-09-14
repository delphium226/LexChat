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
| **Repetitions** | n=1 over all 41, then n=3 on the 12 sessions the first pass did not settle |
| **Spend** | **$37.62** for the n=1 pass (6.0 h wall clock, serial). See *Cost*. |
| **Harness** | `server_py/tools/replay.py` → `/api/system/chat`, `audit` trace captured per turn |
| **Raw output** | `evidence/replay/baseline/` (gitignored — lawyers' verbatim casework questions) |

Reproduce this file's numbers with:

```
python -m tools.replay_report --dir ../docs/prepilot-fixes/evidence/replay/baseline summary
```

---

## Headline

**29 of 41 sessions still reproduce their original failure. 9 do not. 3 are inconclusive.**

The three defects Wave 1 targets are all confirmed present and measurable, and two of them are
**worse than the transcripts suggested**, because the transcripts could only show what the lawyer
saw. The trace shows what the tool did.

| Bucket | Row | Baseline | Verdict |
|---|---|---|---|
| **B2** jurisdiction filter | P1.1 | **351 of 974** searches under a jurisdiction filter returned **nothing** to the model (36%); **478** (49%) demonstrably lost rows; **0 of 557** searches lost anything with the filter off | **Confirmed, cause isolated** |
| **B5** count destroyed | P1.3 | **1,010 of 1,531** searches reported a `total` that was not the API's | **Confirmed, and independent of the filters** |
| **B14** provision links | P1.4 | **88 of 376** provision-labelled links (23.4%) miss their provision | **Confirmed, 7× the transcript rate** |
| **B1** research halt | P2.1 | **10 of 41** runs had a halted worker; **7** showed halt text to the lawyer | **Confirmed** |
| **B4** in-force claims | P2.5 | **27** unsupported in-force assertions across 41 runs | **Confirmed** |
| **B8** sources rail | P4.3 | **1,222 of 1,387** kept sources (88%) never cited; **62 turns** cited none of theirs | **Confirmed, now a rate** |
| **B13** lost/blank turns | P4.2 | **4 turns** billed >$0 and returned an empty body | **Confirmed** |

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
| 6357 | DEFECT | B1 | **N** *(n=3)* | No halt. Replaced by a filter failure — 53 of 93 searches emptied, `legislation_type=primary` blocking every SSI, so it never reached s.85 at all |
| 6359 | FAIL | B8 | **R — worse** | Now cites *Clark v Harney Westwood and Riegels* [2021] IRLR 528 with a specific report citation. Clark is **absent from the corpus** — apparent fabrication, where the pre-pilot merely cited irrelevant cases |
| 6360 | DEFECT | B9 | R | E&W answer first, Scottish rules only on follow-up |
| 6363 | DEFECT | B12 | R | Recency bias intact — cites 2026 authorities, misses the foundational ones. No blank message this time |
| 6365 | DEFECT | B10 | **N** *(n=3)* | Found the Public Finance and Accountability (Scotland) Act 2000 in the first answer |
| 6367 | FAIL | B5 | **?** *(n=3)* | Answers from the right body of law; whether the statutory deadlines are stated needs a legal read |
| 6369 | DEFECT | B10 | R | Purpose test still surfaced only after repeated prompting |
| 6370 | DEFECT | B11 | R **+ B13** | Two blank billed turns; *"You are entirely correct"* capitulation openers intact |
| 6372 | DEFECT | B8 | **?** *(n=3)* | Cites Rule 35.8 to the Court of Session Rules 1994; provenance needs checking |
| 6373 | FAIL | B12 | R | Questioned the lawyer's citation twice — *"Could you verify the citation?"*, *"Could you check if the year or the SI number might be different?"* — rather than stating an index limit |
| 6374 | FAIL | B3 | R | Orders in Council under s.126(8) still not retrieved; halt text shown |
| 6375 | FAIL | B11 | **?** *(n=3)* | 11 of 15 provision links wrong. Whether English common interest privilege is again analysed as Scots law needs a legal read |
| 6378 | FAIL | B8 | R | A UK question answered England-only; SSI 2008/216 still absent from the answer |
| 6380 | DEFECT | B10 | R | Legitimate expectations reached only after a clarifying exchange |
| 6381 | FAIL | B5 | **N** *(n=3)* | **Improved** — now says plainly *"I am unable to locate the Victims and Witnesses (Scotland) Act 2014"* three times instead of answering silently from adjacent statutes. But the non-retrieval is now caused by the filter: 30 of 80 searches emptied |
| 6382 | FAIL | B1 | R | Still zero of the 33 SSIs under s.95; halt text shown. Presentation improved — the report is no longer *only* the halt message |
| 6383 | FAIL | B3 | **R — worst case** | Turn 1's entire answer was the raw string `[Research halted: exceeded 20 tool-call steps]` |
| 6384 | FAIL | B1 | R | *"I am currently unable to retrieve the Courts Reform (Scotland) Act 2014"* — verbatim reproduction. It is in LEX |
| 6385 | FAIL | B12 | R | English authorities only, no Scots-corpus disclosure |
| 6387 | DEFECT | B13 | **N** *(n=3)* | No timeout; all three turns answered |
| 6389 | DEFECT | B1 | **N** *(n=3)* | No halt text in the report |
| 6396 | FAIL | B10 | **N** *(n=3)* | Answered the question — 14 days, Article 16 — where the pre-pilot could not find the provisions. 32 of 172 searches still emptied by filters |
| 6406 | FAIL | B1 | **N** *(n=3)* | **0 of 4 steps halted** on both Deep Research turns, against 4 of 4 in the pre-pilot. $0.72 and 14,090 chars against $2.36 and a report with no findings |
| 6407 | DEFECT | B1 | R **+ B13** | Two blank billed turns; halt text shown. The most expensive run in the sweep at $5.99 / 50 min |
| 6408 | FAIL | B1 | R | 52 of 92 searches emptied by filters; turn 3 explains the step cap to the lawyer |
| 6409 | FAIL | B3 | R | Commencement SSIs still invisible — *"No commencement regulations have been made yet"* |
| 6410 | FAIL | B3 | R | Same false negative, verbatim. The Care Reform (Scotland) Act 2025 (Commencement No.1) Regulations 2025 exist |
| 6411 | FAIL | B4 | R | Unsupported in-force assertion |

### Why the nine does-not-reproduce

Six are genuine improvements attributable to work that landed between the pre-pilot and this
branch — most plausibly the worker context budget and the Phase-2 fan-out tuning, both of which
reduce tool-call counts and therefore halts (6406, 6389, 6396, 6365, 6387, 6334). **No attribution
is claimed**: separating those commits from model variance would need its own experiment, and
these are single draws until the n=3 reps land.

Three are **not** improvements and must not be read as such:

- **6357** swapped a halt for a filter failure. The lawyer is no better off.
- **6381** discloses the failure honestly now, which is exactly what Invariant 1 protects — but the
  underlying retrieval got worse, not better, and the cause is B2.
- **6340** stopped fabricating and started returning a truncated non-answer, which is a different
  defect in the same session.

---

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
6. **n=1 for most sessions.** Only the 12 unsettled sessions were repeated. A verdict of
   *reproduces* on a single draw is safe (the defect was observed); a verdict of *does not
   reproduce* on a single draw is not, which is why every `N` above is in the n=3 set.

---

## Cost

| | |
|---|---|
| n=1 over 41 sessions, 155 turns | **$37.62** |
| targeted n=3 on 12 sessions (24 further runs) | see `SESSION_LOG.md` |
| wall clock, serial | 6.0 h |
| most expensive run | 6407 — $5.99, 50 min |

Replay costs about **2.3× the pre-pilot's recorded spend** for the same work. The recorded figure
covers only the saved assistant message; a replay also pays for the Deep Research planner call,
which saves no message and is therefore absent from the export. FIX_PLAN's original ~$50 estimate
for a blanket n=3/n=1 pass would have been ~$140 in practice.

Runs are serial by design. Three parallel Deep Research runs fan out to a shared, rate-limited LEX
API; `_request_with_retry` backs off on 429 and eventually returns the error, which would appear
in the trace as a degraded retrieval — a failure reproducing when it did not. A corrupted baseline
costs more than the hours saved.
