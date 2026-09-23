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
cd server_py && python -m tools.replay_report compare \
    --before ../docs/prepilot-fixes/evidence/replay/baseline \
    --after  ../docs/prepilot-fixes/evidence/replay/wave1
```

Point it at the **real** directories — `compare` restricts both sides to rep 1 itself, so there is no need to build a filtered copy of the baseline (and doing so by hand is how the denominator trap below gets re-introduced).

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
link points at the *granularity* its label names. It cannot ask the question that matters: **where
did this provision URL come from?**

> **Corrected 2026-09-15 during P1.6 — the ninth instrument trap, and it was reading a third of
> the answer.** This section originally reported one number, "manufactured 327 (100%) → 26 (19%)",
> computed by asking whether the URL appeared in the tool's `final_result`. But `final_result` is
> the **summarised** text whenever summarisation fired, and **70% of section searches are
> summarised** — the summary keeps the section numbers and drops every URL. A provision URL the
> retrieval genuinely returned therefore scored as manufactured, because the model had to rebuild
> it. The corrected reading needs **three** outcomes, not two. Both are computed from the same run
> files; nothing was re-run.

| | Wave 0 | Wave 1 | |
|---|---|---|---|
| provision URLs cited | 327 | 136 | |
| **shown** — copied from the text the model was handed | 5 (1.5%) | **110 (81%)** | the healthy case |
| **reconstructed** — the tool returned it, the summariser dropped it | 293 (90%) | 26 (19%) | substantiated, but guessed |
| **manufactured** — no tool returned it anywhere | **29 (9%)** | **0** | the citation is unsupported |

Read this way P1.4 did **more** than was published, not less. Before it, the Worker prompt
*instructed* the model to append `/section/{number}` and the unslimmed 24K response was summarised
87% of the time, so essentially every provision URL in the corpus was composed rather than copied —
and most carried the right number, so the old checker scored them **good**. Slimming the payload
(median 24.5K → 18K, summarisation 87% → 70%) is what moved 81% of citations to a URL the model was
actually shown, and **manufactured URLs to zero**.

The 32 flagged links are the residue of honesty: forbidden from inventing a URL and lacking a
retrieved one, the model now links the Act's contents page while naming a section. 6348 is the
clean case — **zero** provision-level URLs were returned by any tool in that run, yet it cites
FOISA ss.36 and 55. **A bad link is now a symptom of citing an unretrieved provision**, which the
manufactured URL previously concealed.

**What remains is the mechanism, and it is what P1.6 fixes.** 19% of cited provision links are
still *rebuilt* rather than copied. They happen to be right today — every one of the 26 matches a
provision the run genuinely retrieved, 6365's `asp/2000/1/section/21` and `/section/22` among them
— and nothing made them so. ~~The residual 19% is the model disobeying where it holds only an
Act-level URL.~~ It is not disobedience: the model was never shown the URL. Invariant 2 says
replace the instruction with enforcement — **P1.6**, which hands the URLs back after summarisation
and enforces provenance at the answer seam. The signal to watch on the next sweep is
`provision_links_reconstructed`, not `provision_links_manufactured`.

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
| **B14** provision links | P1.4 | ~~88 of 376 (23.4%)~~ **20 of 376** provision-labelled links (5.3%) miss their provision — see *Correction* below. Separately, **29 of 327 cited provision URLs (9%) were returned by no tool at all** (~~327 of 327~~ — see the second *Correction*); Wave 1 takes that to **0** | **Confirmed, but six-fold smaller than first published; the provenance half is closed** |
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

## B5 — what a negative was actually drawn from (P2.2)

Measured over the **Wave 1** directory, which is the before-column for P2.2.
Reproduce with `python -m tools.replay_report --dir <dir> negatives`.

**The row's premise is real and is 0.5% of the problem.** P2.2 was written against
the missing zero-result nudge on `search_legislation` — the only search tool
without one. That branch exists and is fixed, but:

| | Wave 1 |
|---|---|
| `search_legislation` calls | 790 |
| … that returned **0 results** to the model | **4** (1 empty from the API, 3 emptied by filters) |
| … that were **windowed** (fewer rows shown than the API matched) | **783 of 783** measurable |
| rows shown per call | 5 |
| matches the API reported | median **141**, p90 185, max 220 |
| turns asserting a research negative | **44** |
| … that followed a zero-result search | **0** |

So **every** bare negative in the corpus was drawn from a search that returned
results — just not the wanted one. A fix confined to the empty branch would have
moved none of the forty-four. "No commencement regulations have been made" —
seven of the forty-four, verbatim, across 6409 and 6410 — is a conclusion of law
drawn from the top 5 of a median 141 ranked matches, and nothing in the tool
result told the model that is what it was holding.

### The detector, and the artefact it started as

The first `NEG_ASSERTED` scored **61 of 153 turns, 61 failing — 100%**, which
under this file's own standing hazard is an artefact until proven otherwise. It
was one: it could not tell a **research** negative from a **legal** one, and was
counting *"no winding-up order may be made, except by the company's directors"*
(6335 t2) and *"'sale of goods' does not include the sale of meals"* (6341 t4) —
both correct statements of retrieved law. Grading those as bare negatives would
have pushed the model to hedge findings it had actually retrieved, which is the
regression Invariant 1 exists to prevent and which P3.3's row warns about from
the other side.

Tightened to require the *research* as the subject, the count is **44 turns**,
a strict superset of the 17 the older `NOT_FOUND` screen found. The single
commonest negative in the corpus turns out to be one `NOT_FOUND` never saw:

> **"The available database does not contain information on this specific issue."**
> — 27 occurrences across 21 turns, in the BLUF, with no query, no filter and no
> statement of what the database is short of.

`NOT_FOUND` and `NEGATIVE_EXPLAINED` are deliberately **left alone**, still
reported as `bare_negatives`, because retightening a metric in place silently
invalidates every earlier reading of it — the rule set when
`provision_links_manufactured` was kept and `provision_links_reconstructed`
added beside it.

### Before-column: 0 of 44 explained

Three conditions, each a distinct failure in the corpus: does the answer say
**what was searched**, does it name the **limits** it ran under, is the miss
attributed to the **index** rather than to the law or to the lawyer.

| condition | turns satisfying it, of 44 |
|---|---|
| names its search terms | **6** |
| names a filter, a year window, or that the search was ranked | **5** |
| attributes the miss to the index/search | 31 |
| **all three, and blames nobody's citation** | **0** |
| blames the *lawyer's* citation (an outright fail) | **3** |

Each condition is individually reachable, so 0/44 on the conjunction is a
property of the product and not a dead detector. The three that blame the lawyer
are the worst of the set and are all now verifiable as wrong at source: 6373
questioned FrankieH's `SSI 2026/170` and 6409 questioned `SSI 2025/377` three
times — **both citations are correct and both instruments are a 404 in LEX**
(checked 2026-09-15). The tool asked the lawyer to disprove a gap in its own
index.

**6373 turn 2 is the whole bucket in one screen** (`negatives --answers`). Seven
searches, including the bare id both ways, and then this, entire:

```
queries run:
    Social Security (Up-rating) (Miscellaneous Amendments) (Scotland) Regulations 2026
    Social Security (Up-rating) (Miscellaneous Amendments) (Scotland) Regulations
    SSI 2026/170
    ssi/2026/170
    "polygamous marriages" "Social Security"
    "Social Security (Up-rating) (Miscellaneous Amendments) (Scotland) Regulations"
    polygamous marriages
filters: {'research_mode': 'legislation_only', 'year_to': 2026, 'current_only': True}

The Social Security (Up-rating) (Miscellaneous Amendments) (Scotland)
Regulations 2026 (SSI 2026/170) could not be found in the legislation database.

Could you confirm the year or the SI number?
```

Every one of those seven searches came back with rows — LEX ranks the whole
corpus against the wording, so a query for a non-existent statute still returns
185 results — and none held the instrument. The research was diligent, the
conclusion was right, and the sentence the lawyer got was wrong in the only way
that matters: it put the doubt on their citation instead of on the index. **Note
also what no tool could do here.** `POST /legislation/lookup` answers "is
`ssi/2026/170` held?" with a 200 or a 404 and we never call it — P3.7.


### After — the acceptance, and what it cost to find out

`evidence/replay/wave2_p22_final/` (n=3 on 6409 and 6367, $5.32). Graded per
TURN with `replay_report --dir <dir> negatives`, which also prints the search
shape this section's numbers come from:

```
Search shape: 790 search_legislation call(s); 4 returned ZERO results;
              783/783 measurable were WINDOWED (median 141 candidates
              ranked, p90 185, max 220).
```

| | Wave 1 (n=1) | instruction only (n=3) | **+ code footer (n=3)** |
|---|---|---|---|
| turns asserting a negative | 10 | 23 | 21 |
| **explained — the row's bar** | **2 (20%)** | 13 (56%) | **19 (90%)** |
| names its search terms | 20% | 82% | 90% |
| attributes the miss to the index | 40% | 60% | 95% |
| **blames the lawyer's citation** | **2 of 10** | **0** | **0** |
| model's own prose explains it | 20% | 56% | 4% |

**The middle column is the interesting one, because it is the fix the row asked
for and it was not enough.** Carrying the scope to the agent that writes the
answer — the Manager and the Deep Research synthesis, neither of which had ever
seen a tool result — took explained negatives from 20% to 56%. The other 44% told
a lawyer something was not found without saying what had been looked for. That is
Invariant 2 arriving on schedule: the instruction reached the right reader and
was still only sometimes obeyed, so the disclosure became code.

**Two failures remain and they are the same shape.** Both are turns with **zero
delegations** — a negative carried forward from an earlier turn's research
(*"As noted in the previous search, SSI 2025/377 is not currently available in
the legislation database"*). No search ran, so no footer was emitted. The footer
is per-turn; a conversation is not. Recorded as a limitation rather than fixed,
because restating the full scope on every follow-up would be noise.

**The model-only column is not trustworthy and is printed anyway.** It swung
**56% → 4%** between two sweeps the model could not tell apart: the only change
was the footer, which is appended after the model has finished writing. n=3
cannot produce that swing legitimately, so the column is unstable — a reading of
the prose (`negatives --answers`) is the real check. What it does not affect is
the verdict column, which is what the lawyer actually sees.

**Two more instrument errors, and one of them was self-inflicted.** The footer's
own words — *"anything reported above as not found was not found in this
index"* — trip `NEG_ASSERTED`, so selecting the denominator on the full answer
enrolled every researched turn including purely positive ones (23 → 34, model
column crushed to 14%). **A product change corrupting the instrument measuring
it** is a new failure mode for this work and the reason the denominator is now
taken from the model's prose with the footer stripped. Separately, `terms`
required quotation marks and so scored *"A search of the legislation index for
commencement regulations did not return any results"* as naming nothing; the
correction moved the before-side too (44/41 failing → 44/38), which is the check
that it was not tuned to pass.

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

## B1 — what a halted turn actually said, before and after (P2.1)

The before-column is the Wave 1 sweep, graded per **turn** rather than per run
(`python -m tools.replay_report --dir <dir> halts`). A session's failure lives in
one turn of four, and a run-level total hides which.

**11 turns halted. 2 of them were disclosed acceptably.**

| | Wave 1 | |
|---|---|---|
| turns whose worker hit the step cap | 11 | |
| **said nothing at all** | **6** | the silent halt — the failure the rewritten acceptance exists for. One of the 6 produced no answer at all, which is B13; `halts_undisclosed` excludes it and so reports 5 |
| mentioned it | 5 | |
|   … of which called it a **timeout** | 2 | false: a timeout implies a retry might work; a cap says it will not |
|   … of which printed the **raw marker** as the answer | 1 | 6383 turn 1, 46 characters |
| carried the halt as **structured metadata** | 0 | no field existed |

The two wrong disclosures are not cosmetic. 6340 told the lawyer the agent had
*"exceeded its operational limits (timed out)"* and then supplied a cause for the
missing findings — *"a broad enabling power has generated a very large volume of
statutory instruments over several decades"* — about an Act that **404s in LEX**.
A step cap had become a finding about the state of the statute book.

**The starkest case is 6409 turn 7, and it is worse than 6340.** The worker ran
**25 Phase-1 searches and 0 retrievals**, hit the cap, and the lawyer was told:

> *"The research agent could not locate 'The Social Security (Amendment)
> (Scotland) Act 2025 (Commencement No. 1 and Saving and Transitional
> Provisions) Regulations 2025' in the legislation database."*

That is the whole answer. A step cap rendered as a **negative retrieval
finding**, with no hint the research was cut off — an *untrue* honest failure,
which is the one thing Invariant 1 cannot survive. A lawyer who has learned to
trust this tool's negatives takes it at face value. It is why the code-emitted
notice denies the reading explicitly ("it is **not** a finding that the material
does not exist") rather than merely describing the cap.

**And 6340 is not the only invented cause.** 6335 turn 7 produced the same two-part
failure: *"The initial search **timed out**"* — it hit the cap — followed by
*"It is possible the database is having difficulty parsing the Schedule B1
structure."* Two of the five disclosures in the corpus invented a technical
cause for the missing findings, which is why the worker's replacement report
carries an explicit **"Do NOT state or speculate about why material was not
found — you do not know"** rather than relying on the manager prompt's general
no-speculation rule.

### After

Every condition except "no invented cause" is mechanical and is graded by the
same command; the fifth is a reading of the prose, printed by `--answers`.

**Which turns halted is stochastic, and the write-up says what actually halted
rather than what was expected to.** 6383 turn 1 — the row's named "strongest
case", where Wave 0 returned the raw marker as the entire 46-character answer —
did **not** halt in this sweep: it ran conversational, answered in 27s, and the
halt moved to turn 4's Deep Research plan. That is Invariant 4 working as
intended, and it is why the grading is per halted TURN over the whole directory
rather than per named session. **6383 halted in only 1 of its 3 reps** (rep 2's
deepest loop was 12 rounds of 20, rep 3's 16) — the other two are legitimate
non-contributing runs, neither a pass nor a fail. Whether a session halts is
itself a coin toss, which is a second reason the cap is better described as a
tail than as a ceiling the work now sits against.

**A large per-session drop that is NOT evidence of a fix, recorded so it is not
later read as one.** 6384 turn 1 went from **14 Phase-1 searches and 2
retrievals** in Wave 1 to **1-2 searches and 2-3 retrievals** here; 6383 turn 1
from 10 searches / 11 retrievals / 7 redundant (and a halt at 20 rounds) to
1-2 / 2-5 / 0-3 (2-6 rounds). Tempting to attribute to P1.6, and it should not
be: P1.6's citation-URL block only fires *after* a summarised section retrieval,
and 6384 turn 1 made two retrievals in Wave 1 — the block could have fired twice
at most, which cannot explain a 14 → 2 collapse in *searching*. The before-side
is n=1, and Wave 0 → Wave 1 already showed swings of this size from variance
alone (6396: 172 searches → 1). **Most likely variance.** The next full sweep
can settle it; a per-session claim on n=1 cannot.

The three 6340 replays are the clearest read, because 6340 is the session that
produced the invented cause. All three now open with the code-emitted notice, and
**none of the three invents a cause** — the enabling-power sentence is gone
entirely, replaced by the model correctly reporting that it was stopped before it
could compile the list.

> **⚠ This answer is incomplete.** One research step reached a fixed internal
> limit of 20 tool-call rounds and was stopped before it finished. This is a
> limit on how much work one research step may do — it is **not** a timeout, and
> it is **not** a finding that the material does not exist. Treat the coverage
> below as partial, and consider asking again with a narrower question.

**Result: 12 runs, $8.63, 7 halted turns, 0 failing.** Every halted turn
disclosed the halt, none leaked the raw marker, none called it a timeout, all
carried the structured metadata — and reading the prose for the fifth condition,
**none invented a cause**. 6340's *"a broad enabling power has generated a very
large volume of statutory instruments over several decades"* is gone from all
three of its replays, replaced by *"it reached an internal limit on the amount
of work a single research step can perform"*.

| session | reps | halted in | verdict |
|---|---|---|---|
| **6340** | 3 | **3 of 3** | full n=3, all clean |
| **6382** | 3 | **3 of 3** | full n=3, all clean |
| 6383 | 3 | 1 of 3 | the one halt clean; 2 non-contributing |
| 6384 | 3 | 0 of 3 | never halted — contributes nothing |

Invariant 4 asks for *n=3, all three clean* on a FAIL session. **6340 and 6382
give exactly that.** 6383 and 6384 mostly stopped halting, so their condition is
vacuous rather than passed — stated plainly here because "four sessions × three
reps" would read as four times the evidence it is.

**The model's own prose came along, which was not assumed.** The disclosure is
code-emitted precisely so it does not depend on the model, but in all 7 turns the
model *also* stated the true reason in its own words, and 6383 rep 1 carries a
"Research Limitation" bullet of its own saying the step *"did not complete … due
to an internal system limit"* and that *"this is not a negative result or
evidence that the material does not exist"*. That is the per-occurrence
instruction in the worker's replacement report doing its job, and it is why the
instruction is carried in the tool result rather than added to a system prompt.

Two things about the notice are deliberate and were argued over:

- **It is prepended, not appended.** A warning read after the findings have been
  relied on is not a warning.
- **It claims only the step cap.** Not "the material does not exist", not "this
  timed out", not a reason for the absence. Invariant 1 requires the disclosure
  to be *true*, and the only thing known at that seam is that a limit was hit.

**The sources rail is untouched by this row and still disagrees.** 6340's halted
turn shows **16 sources** behind an answer with no findings — real retrievals,
kept by the excerpt branch of `_source_is_used`, not a fallback list. The lawyer
is now told the answer is partial, which is an improvement on the Wave 0 reading
(*"6341 turn 5 shows 40 sources behind a 333-char 'timed out' message"*), but the
rail still implies those sources were used. That is **B8 / P4.3**, and P2.1
narrows it rather than closing it.

**Two measurement notes, recorded rather than hidden.** (1) A cosmetic
plural-agreement fix to the notice landed *after* the sweep started, so runs
naming more than one halted step read "…and **was** stopped before **it**
finished" where HEAD now reads "were … they" (6382 rep 1 shows it). It changes
no graded condition — `HALT_PARAPHRASE` matches the opening clause — but the
measured tree and HEAD differ by that string. (2) The `wave2_p21/` run files
record `git_head: 7a1c79b`, which is P1.6's commit. P2.1 was complete and loaded
by the server when the sweep started but was committed as `4d3f4c1` a few minutes
later; **P2.6 was written after the server started and is therefore NOT in these
runs** — visible in the files as `report_reformat_retries: 1` on halted turns,
which P2.6 takes to 0. P2.6 cannot change the answer text, because P2.1 overwrites
the report after the reformat runs.

---

## The step cap — measured on the completed sweep, and the earlier reading was the wrong counter

**Decision (P2.1, 2026-09-15): `max_turns` stays at 20.** Recorded here because the
row asked for it to be decided on the finished Wave 1 sweep rather than on the
mid-sweep figures, and because the mid-sweep figures pointed the other way.

### The earlier reading counted tool calls against a cap on rounds

P2.1's row recorded *"p90 tool calls per delegation 15 → 20 — the 90th-percentile
delegation now sits AT the cap"* and *"at-or-over-cap 6.3% → 11.2%"*, concluding that
**fixing retrieval nearly doubled the share of delegations hitting the ceiling.**

`max_turns` caps **ReAct rounds** — recursions of `chat_loop`, one LLM call each. A
single round issues as many tool calls as the model asks for, executed in parallel by
`asyncio.gather`, and the Worker prompt explicitly instructs batching ("exactly one
call per `legislation_id`"). So tool calls per delegation and rounds are different
quantities, and comparing the first against the number 20 overstates cap proximity —
most on the largest delegations, where batching does the most work:

| | tool calls in the biggest delegation | `react_turns_max` | halted? |
|---|---|---|---|
| 6341 turn 6 | 45 | **13** | no |
| 6341 turn 5 | 31 | **17** | no |
| 6374 turn 2 | 24 | **19** | no |
| 6408 turn 2 | 20 | **10** | no |

Of the 15 Wave 1 turns whose biggest delegation made ≥20 tool calls, 4 never came
near the cap. `request_timings.react_turns_max` is the counter the cap actually acts
on, it is on every run file, and P2.1's row said to read
`request_timings.max_turns_halted` before changing the cap. Both were available.

### On the completed sweep, cap pressure FELL

41 sessions, 153 measurable turns, rep-1 like-for-like:

| | Wave 0 | Wave 1 | |
|---|---|---|---|
| `react_turns_max` median | 3 | 3 | = |
| p75 | 7 | 6 | |
| **p90** | 17 | **13** | **−24%** |
| p95 | 20 | 20 | = |
| **turns at the cap** | 12 (7.8%) | **11 (7.2%)** | −0.6pp |
| turns at 15–19 (near, not at) | 5 (3.3%) | 4 (2.6%) | |
| tool calls per delegation, p90 | 18 | 17 | |
| delegations ≥20 tool calls | 22 (7.9%) | 19 (9.6%) | denominator fell 29% |

The distribution is sharply bimodal: over 90% of turns finish inside 14 rounds, and a
7–8% tail runs to the ceiling. Wave 1 moved the body of the distribution *down* — the
model stopped re-searching against emptied results — and left the tail where it was.

### The turns that hit the cap are looping, not starved

This is the evidence that settles it. Across the 11 halted turns of the Wave 1 sweep:

| session · turn | tool calls | redundant | Phase 1 | Phase 2 | sources |
|---|---|---|---|---|---|
| 6335 · 7 | 26 | **22** | 2 | 24 | 2 |
| 6338 · 2 | 27 | **19** | 4 | 23 | 4 |
| 6382 · 1 | 53 | **24** | 13 | 40 | 24 |
| 6409 · 6 | 23 | 0 | **22** | **1** | 3 |
| 6409 · 7 | 25 | 0 | **25** | **0** | 18 |

**26% of tool calls on halted turns are redundant, against a 15% base rate** over all
turns. Two failure shapes, both visible: *repeat retrieval* (6335 spending 22 of 26
calls re-fetching) and *discovery flail* (6409 turn 7 running 25 searches and
retrieving nothing at all). Neither is a run that was nearly finished. Raising 20 → 30
would add cost and latency to the 7% and buy more of the same, while **masking** the
failure P2.1 exists to make honest.

What it does justify is a different fix, opened as **P2.7**: `run_worker_agent` gives
`search_budget` only to the parliamentary modes, so nothing stops a legislation Worker
searching indefinitely. The parliamentary budget exists for exactly 6409's shape.

---

## Correction — the provenance signal was blind to summarisation (found 2026-09-15, during P1.6)

**This file first published "provision URLs never returned by a tool: 327 of 327 (100%) →
26 of 136 (19%)". The true figures are 29 → 0 manufactured, with 293 → 26 reconstructed.**
Ninth instrument error in five sessions, and the same signature as the other eight: *a
number that disagreed with what the code said should happen.* Here the disagreement was
loud — 100% is not a rate a real system produces, and it should have been read as a
detector artefact the moment it was written down.

`replay_report._urls_returned_by_tools` built its "returned by a tool" set from each tool
record's **`final_result`**. That field is the tool's output *as the model received it* —
which, whenever summarisation fired, is prose. The summariser keeps the section numbers
and drops every URL, and **70% of `search_legislation_sections` calls are summarised**
(87% before P1.4 slimmed the payload). So the URL the API returned was absent from
`final_result` by construction, and every citation built from it counted as manufactured.
`raw_result` sits in the same record, unclipped, and was never read.

Three outcomes, not two:

| | what happened | what it means |
|---|---|---|
| **shown** | the URL was in the text handed to the model | copied verbatim — the healthy case |
| **reconstructed** | the tool returned it; the summariser dropped it; the model rebuilt it | the provision *was* retrieved, so the citation is substantiated — but the link was guessed |
| **manufactured** | no tool returned it anywhere | the provision was never retrieved; the citation is unsupported |

Verified on the run files: 6365's `asp/2000/1/section/21` and `/section/22` — the two URLs
P1.6's row was opened to fix, described there as "for provisions no tool retrieved" —
appear in the `raw_result` of two summarised `search_legislation_sections` calls on
`asp/2000/1` (32K and 34K raw, 3.6K and 3.9K summarised). They were retrieved. The model
rebuilt the link because the summary it was given had no URL in it.

The detector now reads `raw_result` for provenance and scans `final_result` as **text**
for what the model saw. The text scan matters twice over: P1.6 appends its citation-URL
block after summarisation, so `final_result` becomes prose plus a bracketed block — not
JSON — and a parse-first detector would have reported the fix as changing nothing.

**What this does not change.** Every other number in this file: the split is computed from
the same run files, and `bad_links`, B2, B5, B1 and B8 never consulted this set. **What it
does change** is the reading of P1.4, which achieved more than was published, and the
premise of P1.6, which is a mechanism fix rather than a live-wrong-answer fix.

There was **no test at all** over this detector — `tests/test_replay_tooling.py` covered
`bad_links` and the filter arithmetic and stopped there. That is the same lesson as the
B14 correction above, one notch worse: a detector pinned by a green test can be wrong on
every real input, and a detector pinned by nothing will be. Seven tests now cover it,
including one asserting that P1.6's own block counts as *shown*.

---

## B13 — ~~four~~ **eight** billed-but-empty turns, and what they turned out to be (P4.2)

~~Four billed-but-empty turns, all in `baseline`.~~ **An undercount, corrected when
P4.2 was built (Session 10). There are NINE blank-body turns across the ten replay
directories, EIGHT of them billed** — and three of the nine (6406, 6359, 6374) were
not in the ledger row's evidence list at all.

| turn | dir | mode | delegations | worker tools | cost |
|---|---|---|---|---|---|
| 6370 r1 t2 | baseline | conversational | 1 | 5 | $0.0602 |
| 6370 r1 t3 | baseline | conversational | 2 | 8 | $0.0764 |
| 6406 r3 t7 | baseline | conversational | 1 | 6 | $0.1056 |
| 6407 r1 t1 | baseline | conversational | 1 | 3 | $0.0420 |
| 6407 r1 t2 | baseline | conversational | 1 | 3 | $0.0371 |
| 6338 r1 t2 | wave1 | research | 2 | 27 | $0.3996 |
| 6359 r1 t2 | wave1 | conversational | 1 | 4 | $0.0809 |
| 6383 r1 t4 | wave2_p25 | deep_research | 3 | 30 | $0.4518 |
| 6374 r3 t3 | wave2_p23 | conversational | **0** | **0** | **$0** |

**8 billed blanks in 616 turns (1.3%)**, six sessions, three chat modes, every one
`status: ok` with `audit.error: null` and not one `token` event. Reproduce with:

    python -m tools.replay_report --dir evidence/replay/<dir> blanks

**Cost is `timing.total_cost_usd`.** There is no `cost_usd` key on a run file, and
reading one grades every turn as free — the instrument failing silent in the
flattering direction.

### The three things the table settles

**Zero `token` events on all nine** kills two of the row's four suspects
universally, not just for the baseline four: there was never a body for the
`<suggestions>` strip to consume, and no error event for the stream-retry guard to
have re-raised.

**Suspect (2) — "a tool-call-only final message" — is right about eight and wrong
as a rule.** 6383's own synthesis call declared **no tools at all** (`agent_core.py`
passes `[]` and `_no_tools_executor`; the log reads `tools=0, msgs=2, ~21421
chars`). So the failure is not confined to tool-call turns, and this is the finding
that shaped the fix: a guard scoped to "after a tool ran" would have missed the
worst instance in the corpus. **It is also stochastic, not deterministic** — 6383's
DR turn produced 9,190 / 6,503 / 7,490 / 8,672 chars on four prior runs and 2,278 on
the re-run, so the same payload succeeded five times and failed once. That is
precisely the condition a bounded retry answers.

**6374 r3 t3 is a different animal and is excluded.** 0 delegations, 0 tools, $0 —
the one turn where nothing ran, rather than something running and the answer being
lost. The invariant is worded against **cost**, not against blankness, for exactly
this reason.

### The cause, and the part of it that was ours

**An empty provider completion that the code could not see.** `chat_loop`
accumulated `delta.content` and `delta.tool_calls` and read neither `finish_reason`
nor `native_finish_reason`; an empty stream became `{"role": "assistant", "content":
""}` and was returned as the answer with `status: ok` and full billing. The existing
stream retry could not catch it — it fires on an *exception* raised while nothing has
been emitted, and a clean 200 carrying no content raises nothing.

Four mechanisms produce that signature and the stored evidence cannot tell them
apart, which is why this row could never name a cause. They are distinguishable at
the seam, so the diagnostic landed first (as the row required) and captures all
four: `completion_tokens` (~0 = the provider returned nothing), `reasoning_chars`
(> 0 with no content = the model spent the completion on thinking tokens),
`stream_error` / `finish_reason: "error"` with `native_finish_reason` (a mid-stream
failure), and otherwise the model choosing to say nothing.

**The `error` payload is the one that was ours.** OpenRouter reports a mid-stream
failure as an `error` object on the SSE stream. Nothing in `chat_loop` read it — it
looked only at `usage` and `choices` — so such a stream ended indistinguishable from
an ordinary empty completion. That is a parser gap, not a provider bug, and it is
now captured.

All of it is surfaced as **audit schema v3's `empty_completions[]`**, `[]` on a
healthy request, with `retried: true` marking an attempt the retry recovered from.
A directory can therefore show zero violations **and** a non-zero rate of the
underlying provider fault — which is the whole reason the diagnostic was built
before the fix.

### The fix, and the line Invariant 1 draws through it

A bounded retry in both clients on any empty completion; a tool-call-only message is
never retried (that is the normal ReAct shape, and replaying it re-runs the turn's
research). The abandoned attempt's cost is banked — under-reporting it would hide
the very spend that makes a blank turn a defect rather than a slow one.

For the residual, two fallbacks: Deep Research to the step findings (6383 had three
intact reports of 4,836 / 5,777 / 7,190 chars sitting behind its empty body), the
Manager to the worker reports it already holds, or a plain notice where there are
none. **Both are labelled as fallbacks.** Research the answering step never used is
not an answer, and the entire complaint in this bucket is that the lawyer could not
tell a lost answer from a finished one — so the fallback opens by naming the
failure, says what has and has not been done to the material below, and reorders
nothing.

### The detector, and why it grades the body rather than the answer

**Since P2.2 a blank turn is not an empty string.** 6383 rep 1 turn 4's `answer` is
**1,293 characters** — entirely the code-emitted scope footer, with nothing above
it. That is what the lawyer saw. A detector grading `answer` scores it as fine;
`blank_verdict` grades `_without_footer(answer)`.

Validated in both directions across all ten directories. It finds exactly the 8
billed blanks and the 1 free blank counted by hand, and the shortest bodies it
leaves alone are real content — a 46-char halt marker, 50-char clarifying questions
("Which jurisdiction have you changed the filter to?"). No before-column number
anywhere else moved.

### The latency half

6387's timeout did not reproduce. What survives is MoniqueM reporting a 5.5-minute
turn as "around 15 minutes" — the status line changes wording as the agent works,
but nothing accumulates, so there is no anchor, and an unanchored wait is
systematically over-estimated.

A step count and an elapsed clock now sit in the status line, both derived
client-side from data already arriving (`tool_start` events, the run's existing
`startedAt`): no new SSE events, no backend change, nothing added to retrieval.
**No denominator, deliberately** — outside Deep Research nothing knows the total, so
"step 3 of 8" would be a claim about how much is left. Live-verified through a real
research turn: *"Researching · 13 steps · 1m 01s"*, advancing on both figures,
tracking Researching → Analysing findings → Typing, and clearing on completion.

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

---

## B3(b) — what an enabling-power claim was actually drawn from (P2.3)

Measured with `python -m tools.replay_report --dir <dir> derivations`, which also
prints every near-miss under `--drops`.

**A derivation claim is not a citation, and the whole row turns on the
difference.** *"Under section 91 of the Act, Ministers must consult"* is correct
legal writing about a retrieved provision. *"SSI 2018/273 was made under section
91"* is the B3 claim — an assertion about a relation **no endpoint we call
returns**. A detector that cannot tell them apart grades correct writing as a
defect and pushes the model to hedge what it retrieved, which is the regression
Invariant 1 exists to prevent.

### Where the enabling power actually is retrievable

The handover into this row recorded that the "retrieved preamble" route does not
exist, on the strength of `/legislation/text` for `ssi/2020/295`: 545 characters
of `full_text` opening at *"Section 1) Citation and commencement"*, with no
recital anywhere. That is correct about `full_text`, correct about that
instrument, and **the conclusion drawn from it is wrong**. The recital arrives in
`legislation.description`, and `get_legislation_text` returns the response
unslimmed.

`python -m tools.lex_probe --enabling`, 103 instruments, sampled 2026-09-16:

| series / era | sampled | held | carry a recital |
|---|---|---|---|
| `uksi` pre-1990 | 25 | 25 | **18 (72%)** |
| `uksi` 1990–2009 | 25 | 25 | 0 |
| `uksi` 2010+ | 25 | 25 | 0 |
| `ssi` 1990–2009 | 13 | 13 | **0** |
| `ssi` 2010+ | 15 | 15 | **0** |

One further instrument carried it in `full_text` and not in `description`, which
is why the product checks both: a rule that misses a real recital forbids a claim
the material supports, and nothing downstream would flag that.

So the permitted branch of P2.3's rule is **live**, and for the Scottish corpus
these lawyers work in it is **empty**. The rule is a near-total prohibition, and
the product says so rather than dressing it as a conditional. Over the whole
post-Wave-1 replay corpus — **38.8M characters of raw retrieval across 2,504
tool results** — only **12 results carried an instrument preamble**, covering
**6 distinct instruments, every one of them in session 6340** (all pre-1990 UK
SIs). Reproduce with `replay_report --dir <dir> corpus`.

~~33M characters across 1,907 tool results, exactly two recitals, both in
6340.~~ **Corrected 2026-09-16, after the numbers were put behind a command.**
Two errors, and they are the reason the command exists: the character and result
counts silently **omitted `wave2_p21`** while claiming to cover the whole
post-Wave-1 corpus, and the recital screen used to produce "two" required the
phrase to be followed by `Act <year>`, which misses the 1963 form — *"Whereas the
Treasury has determined under section 69(4) of the National Insurance Act 1946(a)
…"*. The qualitative claim survives and is stronger: still one session, and now
six instruments rather than two.

**This also settles P3.6's ordering:** it is not a prerequisite. P3.6 would put
the same `description` on *search* rows at Phase 1, which is worth having for
commencement dates and for cheapness, but it adds no enabling-power reach that
`get_legislation_text` does not already have — and on the Scottish corpus it adds
none at all.

### Before-column

`baseline/` records **0 of 222** answered turns asserting a derivation, and that
is not a good score. Pre-Wave-1 the jurisdiction filter emptied the searches, so
there was nothing retrieved to derive from: 6382 and 6383's baseline answers are
all negatives. **B3(b) is a defect surface Wave 1 opened** — fixing retrieval is
what gave the model instruments to make claims about.

Post-Wave-1, over `wave1/` + `wave2_p21/` + `wave2_p22_final/` (219 answered
turns):

| | turns | claims |
|---|---|---|
| assert a derivation | **13** | **20** |
| … with **no** enabling-power text retrieved | **12** | **18** |
| … supported by a retrieved recital | 1 | 2 |

The single supported turn is **6340 rep 1**, which read `uksi/1979/766`'s
preamble verbatim and reported its enabling powers correctly. The one turn in the
corpus that gets this right is in the session the row was written against.

The heaviest failures are 6383's, and they assert knowledge of a document part
the tool boundary never returns:

> **"Over 130 instruments explicitly cite section 95 in their preamble"**
> — 6383 rep 2 turn 4

> **"A search of the legislative database for instruments containing the preamble
> phrase _'in exercise of the powers conferred by section 95 of the Social
> Security (Scotland) Act 2018'_ returns over 130 matches."**
> — 6383 rep 3 turn 4

No search we run matches preamble text, and `description` is stripped from every
search row before the model sees it. The second sentence describes a search that
cannot have happened.

### The detector, and the four corrections it needed

It was an artefact twice before it was right, and then twice more in the
acceptance run itself. All four are in `replay_report.py` rather than quietly
replaced, because on this work **the measuring instrument has been wrong more
often than the product**.

1. **69 of 155 turns.** A regex alternation that reduced to a bare `\bis` —
   `r"\bis|are|was|were\s+enabled by"` groups as `\bis` OR `are` OR … — plus an
   instrument screen the bare word "regulations" satisfied.
2. **1 turn.** Over-corrected by compiling that screen case-sensitively, so it
   missed every claim opening *"Several SSIs …"* — including the largest in the
   corpus.
3. **The full-stop trap, second face.** The sentence splitter cut *"For example,
   S.I. 1963/2111 was made under section 69(4) of the National Insurance Act
   1946"* into `"For example, S."`, `"I."`, `"1963/2111 was made under …"`; the
   fragment that kept the predicate had lost its instrument. Abbreviation dots
   are masked before the split now.
4. **The full-stop trap, third face.** With the sentence intact, *"Commencement
   **No.** 1"* then tripped `\bno\b` and the claim was filtered as negated —
   and that phrase is in the title of every commencement instrument this corpus
   is about. `\bno\b(?!\s*\.)` now.

Corrections 3 and 4 were found by the **first acceptance run**, where they would
have scored a turn making three supported claims as making none. Both are
under-reads, and every correction was re-validated against `baseline/`, `wave1/`,
`wave2_p21/` and `wave2_p22_final/`: **not one before-column number moved**,
which is the check that none of them was tuned to pass.

**Validated in both directions.** `derivations --drops` prints every sentence in
the same vocabulary that was *not* counted, and all of them were read. The one
that matters most is 6383 turn 2:

> *"However, the agent could not retrieve the preamble to definitively confirm if
> it was made under section 95 of the Social Security (Scotland) Act 2018."*

That is the **right** answer — the exact sentence this row exists to produce —
and a detector that counted it would reward the defect and punish the fix.

**One known under-read, stated rather than patched:** an anaphoric subject
(*"It is made under powers including section 95"*, 6383 rep 1 turn 1) is not
counted, because admitting `it` as an instrument reference would be unboundedly
over-broad. It under-reads the before and after columns equally.

### After — the acceptance

`evidence/replay/wave2_p23/` (n=3 on 6340, 6374, 6382 and 6383; 12 runs, **$7.10**,
1 h 5 m, zero model mismatches). Graded per TURN with `replay_report --dir <dir>
derivations`.

| | before (`wave1` + `wave2_p21`) | **after (`wave2_p23`)** |
|---|---|---|
| answered turns | 28 | 29 |
| turns asserting a derivation | 13 | **5** |
| claims asserted | 20 | **10** |
| **turns asserting an UNVERIFIED derivation** | **12 (43%)** | **2 (7%)** |
| unverified claims | 18 | **3** |
| … carrying a disclosure that it is unverified | **0** | **2 (both)** |
| turns asserting a SUPPORTED derivation | 1 | 3 |
| median answer length | 796 chars | 2,786 chars |

**The sessions that carried the bucket went to zero.** 6383 — 7 of the 13
before-column claim-turns, across 12 turns in three reps — asserts **no**
unverified derivation at all, and neither does 6382 in any rep. What replaced the
claim is the point:

> *"Yes, several Scottish Statutory Instruments (SSIs) **have been made under the
> enabling powers of section 95** … **Over 130 instruments explicitly cite section
> 95 in their preamble**."* — 6383, before

> *"… it **could not be verified** whether any specific Scottish Statutory
> Instruments (SSIs) have been made under this section … the retrieved texts
> **lack enabling power recitals**."* — 6383 turn 4, after

**Invariant 1 held in both directions, which was the real risk.** The answers did
not shrink to buy the number — per turn they grew in 8 of the 10 turn slots, and
6383's three conversational turns roughly doubled (548 → 1,377; 604 → 1,380; 614
→ 1,570 chars) because the model now explains the gap instead of asserting across
it. 6382 still reports the substantive finding it was asked for (SSI 2019/29
carries the "£" symbol in regs 11–13, four other SSIs do not) and separately says
the enabling power cannot be confirmed. And **6340, the only session that
exercises the permitted branch, asserts supported derivations in all three reps** —
now phrased *"explicitly states it was made under …"*, which is the attribution
the block asks for.

**The best answers explain the mechanism, not just the limit.** Several now tell
the lawyer what to do next:

> *"The reason it did not appear in the initial search is that our legislation
> index does not record the enabling powers (the 'made under' relationship) for
> statutory instruments. Because the initial search relied on finding 'section
> 95' in the indexed text, instruments that only cite the enabling power in their
> preamble (which is not indexed) were missed."*

**The two residuals are both 6374, and they are the mild shape.** Both are
class-level — *"various Orders in Council made under section 126(8)(b)"*, *"several
Statutory Instruments have been made under this power"* — where the parent Act's
own s.126(8) does say offices may be "specified in an Order in Council made under
this subsection". The instance-level link is inferred rather than retrieved, so
the mechanical verdict is correct, and **both now carry the code-emitted line
saying the derivation is unverified**, which none of the twelve before them did.
6374 rep 3 asserts nothing at all.

**Validated in both directions on the after-column too.** `derivations --drops`
prints **72** sentences in the same vocabulary that were not counted; all were
read and all are correct drops — overwhelmingly explicit *"could not be
verified"* statements, plus statements of law about a class (*"regulations made
under section 95 are subject to the affirmative procedure"*). Nothing in the
after-column is a claim the detector missed.

**One known gap, measured rather than asserted.** The lawyer-facing clause is
gated on the turn having retrieved an instrument. **12 of the 13 before-column
claim-turns did**, so the gate covers the bucket — but a turn that names
instruments from search rows alone and retrieves none of them gets no clause
(6383 rep 2 turn 3 in `wave2_p21`, 1 of 13). Closing it would mean firing the
clause on any turn whose search returned an SI, which is most legislation turns,
for an 8% gain. Left as a limitation.

**A P2.2 defect this sweep exposed, and fixed.** `answer_scope_footer` stripped
only the OUTER quotes from a query, so the model's own field syntax rendered to
the lawyer as `"Education (Scotland) Act 1962" 117"` — unbalanced, and reading as
two searches where there was one. Every quote character is removed before
re-quoting now; the exact queries are in the audit trace.

---

## B3 — the commencement relation, retrieved (P3.5)

Measured with `python -m tools.replay_report --dir <dir> commencements`, whose
ground truth is re-printed live by `python -m tools.lex_probe --commencement`.

**This row is graded against an external fact, and that is unusual here on
purpose.** Every other acceptance in this plan grades what an answer says about
its own limits. P3.5 grades whether a specific true thing reached the lawyer, and
it can, because the thing is small, checkable and independent of the model:
`asp/2025/2` has eight provisions commenced by SSI and `asp/2025/9` has twenty,
and both sessions were told *"No commencement regulations have been made yet."*

### What the change record actually holds

| session | Act | rows | distinct relations | coming into force | by the Act itself | by another instrument |
|---|---|---|---|---|---|---|
| 6409 | `asp/2025/2` | 71 | **36** | 36 | 28 | **8** — 7 by `ssi/2025/119`, 1 by `ssi/2025/377` |
| 6410 | `asp/2025/9` | 100 | **60** | 60 | 40 | **20** — all by `ssi/2025/388` |
| 6382/6383 | `asp/2018/9` | 956 | **484** | 184 | 0 | **184** — 58 by `ssi/2018/298`, 33 by `ssi/2019/269`, 26 by `ssi/2020/295`, 23 by `ssi/2018/393`, and six more |

Three things in that table are the design of the tool rather than decoration.

**The row counts are roughly double the relation counts**, because the feed
returns the same relation twice — once with `http://` URLs and once with
`https://` — and the API's own `id` embeds the scheme, so the twins are not equal
by id and a dedupe keyed on it removes nothing. Measured over **6,738 rows on
eight instruments in both directions: 4,363 distinct, 2,375 duplicates (35%)**,
and it is concentrated in exactly the Scottish material this corpus is about
(`asp/2014/18` 607 -> 309) while `ukpga/1998/46`, `asp/2000/1` and
`ukpga/1981/67` have none at all. ~~"71 rows, 15 of them commencements by
`ssi/2025/119`"~~ — **that figure, carried into this row by the handover, is the
double count.** The truth is 36 relations, 8 by an SSI, seven by `ssi/2025/119`
and one by `ssi/2025/377` — the instrument the LEX **text** index 404s on, and
whose number 6409 was asked three times to re-check. The change graph knows about
instruments the text index does not hold.

**Most of `asp/2025/2`'s commencements are the Act commencing itself.** 28 of the
36 are `asp/2025/2` acting on its own sections under its own s. 27, which is not
commencement by regulation and is the literal question 6409 asked. A tool that
does not separate the two answers that question wrongly, in the direction that
looks most convincing.

**There is no date on any of it**, confirmed again here. "s. 9 was commenced by
`ssi/2025/119`" is retrievable; "on 10 May 2025" is not, and needs a second hop
into that instrument — see the last section below, where the model made it.

### Before-column

The denominator is structural: a turn is in scope when its **question** asks
about commencement and does not itself name one of the instruments being graded.
Picking it was the hard part. The first draft graded every answered turn and
scored six of `wave1`'s eighteen as correct — including 6409 turn 8, whose entire
question is *"SSI 2025/119"*. Repeating back an instrument the lawyer supplied is
not a retrieved relation, and counting it would have shown a before-column that
already half-passes.

| | answered | in scope | **delivered the relation** | denied one exists | blamed a stated limit | said neither |
|---|---|---|---|---|---|---|
| `baseline/` | 18 | 8 | **0** | 4 | 0 | 4 |
| `wave1/` | 18 | 8 | **0** | 6 | 1 | 1 |
| `wave2_p22_final/` (n=3, under P2.2) | 33 | 18 | **0** | 5 | 0 | 13 |

**Zero in every column that matters, across three waves.** What P2.2 changed was
the *shape* of the failure, not the outcome: the flat *"No commencement
regulations have been made yet"* became *"A search of the legislation index for
commencement regulations did not return any results"* — honest, properly scoped,
and still not the answer. That is why `delivered` is the headline and the prose
split below it is diagnosis: `delivered` needs no prose classification at all and
so cannot be a detector artefact.

The discovery loop underneath it is the other half of the cost. **6409 turn 6 ran
41 `search_legislation` calls** hunting a commencement instrument by title —
`"…(Commencement"`, `title:"…" AND title:"Commencement"`, `"appointed day"`,
`"day appointed"`, `"comes into force"` — and the Deep Research run halted at the
step cap with nothing. Turn 7 ran 25 more. One `/amendment/search` call answers
both.

### After — the acceptance

`evidence/replay/wave3_p35/` (n=3 on 6409, 6410 and 6383; 9 runs, **$4.10**,
37 min, zero model mismatches, all at `head=16696ce`).

| | before (`wave1`) | **after (`wave3_p35`)** |
|---|---|---|
| answered turns in the graded sessions | 17 | 51 |
| … that consulted the change record | 0 | **31** |
| in scope | 8 | 24 |
| **delivered the relation** | **0** | **24 (100%)** |
| denied one exists, naming none | **6** | **0** |
| blamed a stated limit | 1 | 0 |
| said neither | 1 | 0 |
| tool calls per answered turn | 10.4 | **4.4** |

> *"No commencement regulations have been made yet for the Care Reform (Scotland)
> Act 2025."* — 6410, before

> *"The Care Reform (Scotland) Act 2025 (Commencement No. 1) Regulations 2025
> (SSI 2025/388) have brought several sections into force, including sections 1,
> 9–11, 13, 14, 16, 18, 20–25, 31–34, and 36."* — 6410, after

**Invariant 1 held in both directions, which was this row's real risk.** A
retrieved relation invites over-claiming. It did not happen: answers **grew in 13
of the 17 matched turn slots** (6410 t2 87 -> 900 chars; 6409 t5 147 -> 944; 6409
t11 205 -> 1,175), **no scope block leaked in any of the 51 answers**, and
**P2.3 did not regress** — 1 of 51 turns asserts an unverified derivation,
against 2 of 29 in P2.3's own acceptance.

**The four turns that shrank are the model no longer padding a non-answer**, and
one of them lands on a different bucket entirely. 6409 turn 10 went from

> *"The research agent could not find … (SSI 2025/377) in the legislation
> database. Are you certain of the SSI number and year …?"*

— which is **P2.4's exact failure**, questioning a citation that was right — to

> *"That aligns with the legislative change records, which confirm that SSI
> 2025/377 brings section 18 … into force."*

### One detector correction, found by the acceptance run

6410 rep 2 turn 2 named `ssi/2025/388` and added *"Based on the recorded changes
to the Act, no further commencement regulations have been found"*. That is true,
sourced, and exactly the answer this row exists to produce — the record holds one
commencing instrument — and the first draft graded it as the defect.

**The exclusion is scoped to the noun phrase, and that is load-bearing.**
`wave2_p22` 6409 rep 3 turn 6 says *"no commencement regulations bringing
**further** sections into force were identified"*, where the qualifier attaches to
*sections* and the sentence is a flat denial that any commencing regulation was
found. A bare `\bfurther\b` anywhere in the sentence would have dropped it —
**moving a before-column number to make the after-column look better**, which is
the precise trap this work keeps recording. Re-run over all six historical
directories after the correction: **not one before-column number moved.**

**Validated in both directions.** `commencements --drops` prints **134**
commencement-vocabulary sentences that were not graded as denials; all were read.
They are retrieved positives (*"Sections 2, 9, 17, 20, 21, 22, and 23 were
brought into force by SSI 2025/119"*) and true statements about what is still
uncommenced (*"The remaining sections of the Act are not yet recorded as having
been commenced"*). Nothing in the after-column is a denial the detector missed.

### An unlooked-for result: P2.5 becomes answerable by a second hop

The relation carries no date and the tool block says so in terms, telling the
model to retrieve the commencing instrument if the question turns on one. **6409
rep 2 did exactly that, unprompted**: it called `get_legislation_text` on
`ssi/2025/119` and reported *"these sections came into force on 10 May 2025"* —
which is in that record's `description`, verbatim. So P2.5's missing commencement
date is reachable today, by the two-step the block already describes; what it
needs is to be made reliable rather than discovered.

### A P2.2 defect this sweep exposed, and fixed

The scope footer is prose, so `strip_scope_blocks` leaves it alone — correctly.
It then travels into the next turn's history, the model reproduces it verbatim,
and the code appends its own. Measured: **18 of 36 answered turns in
`wave2_p22_final` carry the footer twice (50%)**, against **0 of 51** after the
fix. Display-only and it moves no measured number — `ANSWER_FOOTER` is dot-all
and anchored to the end, so every detector already stripped from the first footer
through to the last.

### Two numbers of my own that were wrong, and the commands that caught them

~~31% duplicates over 6,266 rows.~~ The script that produced that asked for
`size=2000`, which **truncated `ukpga/2010/15` at 2,000 of its 2,472 rows** — so
the measurement justifying an escalation past the cap had itself been capped.
The figure over the full data is **35% over 6,738 rows (4,363 relations)**, and
it is printed by `lex_probe --commencement` now, which is how it was found.

~~Tool calls per answered turn 10.4 -> 4.4.~~ Right, but the first version of the
command that reproduces it selected the before-column on "has a ground truth",
which let `wave1`'s **6382** into a comparison whose after-column contains no
6382 — reading 13.4 -> 4.4. `commencements --before` compares the **shared
sessions** now, and reads 10.4 -> 4.4. Two populations are not a before and an
after.

**Reproduce everything above with four commands:**

    python -m tools.lex_probe --commencement
    python -m tools.replay_report --dir <dir> commencements [--drops]
    python -m tools.replay_report --dir wave3_p35 commencements --before wave1
    python -m tools.replay_report --dir <dir> corpus

---

## B4 — in-force status, and the four things that look like it (P2.5)

Measured with `python -m tools.replay_report --dir <dir> currency`, whose ground
truth about the tool surface is re-printed live by
`python -m tools.lex_probe --inforce [--full]`.

**The model was not inventing a source. It was quoting the only field that
looked like one.** Of the 66 in-force assertion sentences in `wave1`, **48 cite
a text version as the evidence** — *"is currently in force (revised)"*, *"Status:
Revised (In force)"*, *"currently in force, with statuses recorded as either
final or revised"*. P1.2 had already removed the two places the product asserted
currency outright (the *"In force as at <today>"* pill and the system-prompt line
*"Status: In-force legislation only"*), and the re-baseline measured claims going
**27 → 30**, not down. Three prompt sites still instructed the claim, and
"Jurisdiction & Status" is a mandatory report section.

### What the tool surface actually reports, and it is nothing

Four near-misses, each of which a model can mistake for a currency signal. Every
figure below is printed by `lex_probe --inforce`.

| signal | where | what it establishes | coverage |
|---|---|---|---|
| `status` → `text_version` | every `search_legislation` row | which text version is held | 100% of rows, **0% currency content** |
| a `(repealed …)` marker in the **title** | a `search_legislation` row | that instrument is repealed or revoked | **258 of 15,160 rows (1.7%)**, 43 distinct titles; a date on **8 of the 258** |
| `coming into force` | `get_legislation_changes` | that **provision** was commenced by that instrument | 19,031 of 89,465 relations, over 101 of 272 legislation_ids |
| the repeal / revocation family | `get_legislation_changes` | that **provision** is no longer in force | 2,957 `repealed` + 1,182 `words repealed` + 525 `revoked` + 376 `word repealed` + 210 `repealed in part` + 194 `repeal` + a tail |
| `Commencement Order` | `get_legislation_changes` | **NOT the subject's commencement.** See below. | 1,355 relations over 53 legislation_ids |
| `valid_date` | `/legislation/text` | the date the held revised text is up to date to | present on the 18% of turns that reach Phase 3; `None` on some instruments (`ssi/2025/119`) |

**Not one of them establishes that an Act as a whole is in force as at today**,
and that is the specific claim the corpus is full of: *"All referenced
legislation is currently in force"* (6341), *"Yes, the Scotland Act 1998 is in
force"* (6411), *"All cited legislation is currently in force"* (6363, 6375),
*"The identified provisions are currently in force"* (6365).

**`status` has three values, not the two the plan recorded.** Over all 15,160
model-visible search rows: `final` 60.3%, `revised` 38.8%, **`stub` 0.9%**. The
conclusion is unchanged and slightly stronger — all three record which text
version legislation.gov.uk holds. P1.2's row and
`tests/test_current_only_removed.py`'s docstring are corrected.

### `Commencement Order` is a different relation, and it is the trap P3.5 left

The handover into this row said `ukpga/1998/46` — 6411's Scotland Act 1998 —
"returns 857 relations and ZERO `coming into force` rows". That is true of the
exact string and it is **not** true that the change record holds no commencement
material: there are **29 `Commencement Order` relations**. Session 8's probe
filtered `type_of_effect == "coming into force"`, which is right for the question
P3.5 asked and hid this one.

**The two are not the same relation, and the discriminator is mechanical.**

| | relations | `changed_provision` |
|---|---|---|
| `coming into force` | 19,031 | **5,180 distinct real provisions** (`s. 9`, `reg. 2`, `Sch. 6 para. 11`) |
| `Commencement Order` | 1,355 | **8 values, every one a placeholder**: `specified amended provision(s)` 1,068, `None` 199, `C/O` 73, `specified provision(s)` 11, plus four casing/typo variants and one `Act` |

A `Commencement Order` row means *another Act's commencement order brought into
force an amendment **to** the subject*. `ssi/2001/81` — the Adults with
Incapacity (Scotland) Act 2000 (Commencement No. 1) Order 2001 — appears against
`ukpga/1963/41` because `asp/2000/4` substituted words in its s. 90(1) and that
order commenced the substitution. `uksi/1999/1075` is the *Road Traffic (NHS
Charges) Act 1999* Commencement Order and appears against the **Scotland Act
1998** for the same reason.

**This matters because P3.5's block invites the model to state any relation the
record lists, citing the instrument named against it.** Left merged, the fix for
6411's unsourced *"the Scotland Act 1998 (Commencement) Order 1998"* would have
been a **differently-sourced wrong answer** — a named SSI, retrieved, cited, and
about a different Act. `asp/2000/4` carries both classes (35 real, 14
placeholder), so the split is not academic.

### Two leads chased and closed, so the next session need not

**The date is in the effect string — but never where it matters.** `saved
(6.5.1999)`, `amended (1.7.1999)`, `repealed (1.1.1996)`: the `type_of_effect`
string does sometimes carry a date, so P3.5's flat *"there is no DATE on any
relation"* reads wrong. Measured over all 272 corpus legislation_ids in both
directions: **552 of 89,465 relations (0.6%) embed a date, and 0 of the 19,031
`coming into force` rows do.** P3.5's statement stands exactly where it matters
and the second hop into the commencing instrument is still the only route to a
commencement date.

**The title marker is a flag, not a date route.** The row's unmeasured lead (5)
was that some titles carry the repeal *and its date* — *"Shops (Early Closing
Days) Act 1965 (repealed 1.12.1994)"*. Measured: **258 of 15,160 rows carry a
marker (1.7%, 43 distinct titles) and only 8 of the 258 carry a date.** It is
worth reading and it is **asymmetric** — present means not in force, absent means
nothing at all — which is exactly the shape a Status line needs, and which the
first draft of this row's own detector got wrong in the flattering direction.

### The instrument, and why the old one is left alone

`IN_FORCE_CLAIM` produced the published 27 → 30 series and is **byte-identical
after this row**. It also **undercounts turns by 30%**: it requires
"is/are/remains/currently in force" and so catches none of the bare Status
bullets that are the purest form of the defect — `In force (revised).` (6341 ×3,
6384 ×6, 6389 ×3), `Status: Revised (In force).` (6406 ×4), `Status: Revised (In
Force).` (6335). `cmd_currency` prints both instruments so the old series stays
comparable and the new one is the real picture.

The new one grades per TURN on **one prose test against one structural fact read
off the audit trace**, so the headline cannot be moved by a wording change in the
product — which is what happened to P2.2's denominator.

**`SOURCED` beside `UNSUPPORTED` is the suppression check, and for this row it is
as important as the headline.** P3.5 made commencement and repeal retrievable; a
fix that simply forbade the claim would drive `unsupported` to zero by driving
`sourced` there too, and Invariant 1 read in the inverse direction says that is a
regression.

**Support for an affirmative assertion is a retrieved `coming into force`
relation and nothing else.** The repeal relation and the title marker are
collected and printed but do not count: both can support only a *negative*, and
an answer reading *"the Act remains in force except ss. 38-39, repealed by
uksi/2014/486"* would otherwise score SOURCED off the repeal while the overclaim
sits in the other half of the sentence.

### Before-column

Every historical directory, on the new instrument (`baseline/` and `wave1/` are
sweeps; the rest are per-row acceptance sets and are not comparable to each
other):

| | answered | **unsupported** | sourced | assertion sentences | … citing a text version | old `IN_FORCE_CLAIM` |
|---|---|---|---|---|---|---|
| `baseline/` | 222 | **54** | 0 | 68 | 30 | 41 turns / 54 sentences |
| `wave1/` | 153 | **43** | 0 | 66 | **48** | 30 / 34 |
| `wave2_p21/` | 30 | 7 | 0 | 23 | 15 | 6 / 12 |
| `wave2_p22/` | 36 | 4 | 0 | 4 | 3 | 4 / 4 |
| `wave2_p22_final/` | 36 | 5 | 0 | 5 | 2 | 5 / 5 |
| `wave2_p23/` | 29 | 10 | 0 | 18 | 14 | 10 / 16 |
| `wave3_p35/` | 51 | **0** | **4** | 5 | 2 | 3 / 4 |

**`wave3_p35` is the interesting row and it is not this fix.** P3.5's own
acceptance sessions already show the shape P2.5 wants — zero unsupported, four
sourced — because the question they ask routes the Worker to the change record.
Two of those four still cite a text version (*"SSI 2020/475 is in force (status:
revised); SSI 2019/269 is in force (status: final)"*, said of instruments for
which no commencement relation was retrieved), which is the residual this row
removes.

`sourced` is 0 in every pre-P3.5 directory for a structural reason:
`get_legislation_changes` did not exist.

### After — the acceptance

`evidence/replay/wave2_p25/` — 6341 and 6411 at n=3 (the row's two named
sessions) and **6409 and 6383 at n=1, which are in the sweep for one reason: the
suppression check.** 6341 asks definition questions and 6411's Act has no
`coming into force` relation at all, so `sourced` is legitimately 0 on both —
and a fix that drove the defect to zero by silencing answers the material
supports would look identical on those two. 8 runs, 42 answered turns,
**$9.76**, ~2 h, zero model mismatches, zero errored turns.

| | before (`wave1`, same four sessions) | **after (`wave2_p25`)** |
|---|---|---|
| answered turns | 24 | 42 |
| **asserts currency with NO commencement relation retrieved** | **7** | **0** |
| asserts currency with a record in hand (`sourced`) | 0 | **1** |
| assertion sentences | 16 | **1** |
| **… citing a text version as the evidence** | **13** | **0** |
| commencement-date sentences | 2 | 0 |
| turns matching the old `IN_FORCE_CLAIM` | 3 | 1 |

> *"**Status:** The Scotland Act 1998 is currently in force (revised status)."*
> — 6374, before (the same signature 6341 and 6411 carried)

> *"**Shops Act 1934:** No change records were retrieved for this instrument.
> In-force status was not verified — the legislation index does not report it,
> and no commencement or repeal record was retrieved. Verification would require
> consulting a fully updated statute book."*
> — 6341, after

> *"**The Health Protection (Coronavirus, Wearing of Face Coverings in a Relevant
> Place) (England) Regulations 2020:** The index title marks this instrument as
> "(revoked)", and the change record confirms a revocation relation,
> establishing that it is no longer in force."*
> — 6341, after: both of the retrievable negative signals, used together

The one turn still matching the old detector is 6409 t6, and it is the `sourced`
one — an in-force statement made with 72 commencement relations in hand. **That
is the old instrument being unable to tell a sourced statement from an
unsupported one**, which is the whole reason the new one grades against a
structural fact.

**The suppression check passes, and it is the number this row could most easily
have faked.** Graded with `replay_report commencements` over the same directory:

| | `wave1` | `wave3_p35` (P3.5) | **`wave2_p25`** |
|---|---|---|---|
| in scope | 8 | 24 | 6 |
| **delivered the commencement relation** | **0** | **24** | **6 (100%)** |
| denied one exists, naming none | 6 | 0 | **0** |

P3.5's win survives intact. Nothing about the currency prohibition stopped the
model naming `ssi/2025/119` and the provisions it commenced.

**Invariant 1: 18 of 24 matched turn slots grew**, tool calls per answered turn
15.5 → 15.2. The six that shrank were each read, and **none is currency
suppression**:

| slot | before → after | what happened |
|---|---|---|
| 6341 t2 | 4,016 → 1,581 | declined to re-research a near-duplicate question and redirected on mode — correctly, the session is `legislation_only` and the question asked for case law |
| 6383 t4 | 9,190 → 1,293 | **a blank Deep Research report.** See below; the cause is an empty provider completion, not this fix |
| 6409 t7 | 378 → 236 | **shorter and strictly better** — *"could not locate … in the legislation database"* (a false negative; the instrument exists) became *"That instrument is SSI 2025/119 … brought sections 2, 9, 17, 20, 21, 22, and 23 into force"*. P2.4's failure, removed |
| 6409 t8, t9, t10 | 277/146/286 → 57/57/134 | the Manager asking *"what specific information do you need about SSI 2025/119?"* to a bare citation. **Behaviour that predates this row** — `wave3_p35` asked the identical question at t8 in all three reps and at t10 in rep 1 |

### The cost side, stated rather than buried

**10 of the 30 turns whose question never mentioned currency carry a currency
disclaimer anyway (33%)** — `python -m tools.replay_report --dir
evidence/replay/wave2_p25 currency --unasked`. ~~3 of 8 turns in 6341 rep 1~~:
that was one rep, quoted before the measure had a command behind it, and the
directory-wide figure is the one to use.

That is `_currency_limb` speaking on every step that touched legislation, and it
is the intended trade rather than noise: "Jurisdiction & Status" is a mandatory
section that has to say *something*, and what it said before was *"All
referenced legislation is currently in force"* about a session citing an Act
whose ss. 38-39 are repealed. It is still a change to answers nobody asked for,
so it is measured and recorded rather than assumed away.

**The shape of the 10 is the reassuring part**: all of them are 6341, the
session where nothing was retrievable, and only **1 of the 11 turns that DID ask
about currency** carries a disclaimer — because the rest got a sourced answer
instead. The disclaimer appears where the record is empty, which is where it
belongs.

**The limb costs 873 characters on every legislation worker report**, and the
`search_legislation` clause is one sentence for the same reason: it rides on 790
searches in a full sweep, and `test_a_long_query_is_capped_not_dropped` bounds
the whole block at 2,000 characters — which the first draft broke.

On 6341 rep 1 against `wave1` rep 1: cost $2.09 → $2.24 (+7%), tool calls
198 → 180, mean answer 4,205 → 6,245 chars.

### A blank Deep Research report, and it is not this fix

6383 rep 1 turn 4 returned a report whose **body was empty** — the lawyer saw
the scope footer and nothing else — with `status: ok`, no error, 30 tool calls,
three intact step reports (4,836 / 5,777 / 7,190 chars) and 219 commencement
relations retrieved. **First blank in 218 answered turns across eight replay
directories**, and 6383's DR turn produced 9,190 / 6,503 / 7,490 / 8,672 chars
on the four prior runs.

**The cause is an empty provider completion at the synthesis call.** The request
went out at `tools=0, msgs=2, ~21421 chars` and the task finished **9 seconds
later**; `strip_scope_blocks` never fired, which is checkable because it logs
when it does and the log carries no such line. Two gaps follow, and both are
`P4.2`'s (bucket B13) rather than this row's: `chat_loop`'s stream retry only
fires while nothing has been emitted and cannot see a successful 200 carrying no
content chunks, and `run_deep_research` never checks that the synthesis produced
anything before footering it and returning.

### The instrument was wrong seven times, in both directions

Every one was found by reading output rather than by trusting a number, and after
each correction all seven historical directories were re-measured: **not one
before-column number moved.**

1. **The title marker used symmetrically.** It is asymmetric — present means not
   in force, absent means nothing — and the first draft graded 6411's *"Yes, the
   Scotland Act 1998 is in force"* as SOURCED because an unrelated repeal-marked
   row ranked on the same search page.
2. **A sentence merely starting with "In force" read as a claim**, so *"In-force
   status: not verified"* — the sentence the fix produces — scored as the defect.
   `_CUR_NEGATED` catches the no-colon form and misses that one, because its
   character class excludes `:`.
3. **The first guard for that was too broad**, matching any negated
   establishment verb anywhere, which would have dropped *"While we cannot
   verify every provision, the Act is currently in force"* — a false negative in
   the flattering direction.
4. **A bare section heading** — `*   **In-Force Status:**` — read as an
   assertion, because `_sentences` splits by line and the content is on the
   lines below.
5. **The distance windows between subject and negation were set from a sample**,
   and a 95-character parenthetical list broke them.
6. **`_CUR_SUBORDINATE` had no adverb slot** where `_CUR_ASSERT` has one, so
   *"To determine if a specific section is currently in force, we would need
   to …"* was graded as an assertion. Two patterns that must agree about a
   phrase, only one of which knew about adverbs.
7. **Adding that slot then over-corrected** and swallowed a concessive clause
   followed by a main-clause assertion. The comma settles it: the trigger and
   the phrase have to be in the same clause.

Items 2, 4 and 5 were found by reading the after-column of the acceptance run's
**first rep**, where the model wrote exactly what the product now asks for and
the detector called it the failure. Items 1, 3 and 7 were found by the
both-directions audit over the historical corpus.

**Reproduce everything above with three commands:**

    python -m tools.lex_probe --inforce [--full]
    python -m tools.replay_report --dir <dir> currency [--drops] [--before <dir>]
    python -m tools.replay_report --dir <dir> commencements

### The second directory, and why the row needed one

`evidence/replay/wave2_p25b/` — 6411 at n=3 plus one 6383, **$0.90**.

6411's acceptance bar was met in the main sweep (0 unsupported, n=3), but its
answers did not grow: mean 437 chars against `wave1`'s 480, and **1 of 3 reps
obeyed the rule's *"if you DID call `get_legislation_changes`, report what it
holds"* clause.** Reps 1 (218 chars) and 3 (713) each had **29 repeal relations
in hand and reported none**; rep 2 (380) did. The conversational worker prompt
demands "2-5 sentences of concise prose" and concision won.

That is not a failure of the row's stated bar, and leaving it would have been a
failure of Invariant 1 read in the inverse direction — 6411 is this row's
headline session. One line was added to the conversational PHASE 2b requiring
the model to report what the route returned before reporting what it does not
establish, and 6411 re-run:

| | `wave1` | `wave2_p25` | **`wave2_p25b`** |
|---|---|---|---|
| unsupported | 1 of 1 | 0 of 3 | **0 of 3** |
| citing a text version | 1 | 0 | **0** |
| reports the retrieved repeals | — | 1 of 3 | **2 of 3** |
| mean answer chars | 480 | 437 | **741** |

> *"The official change record lists 857 changes made to the Act by other
> legislation, including 29 repeals. While the legislation database does not
> provide a definitive in-force flag for the Act as a whole, it does list
> [The Scotland Act 1998 (Commencement) Order 1998](…/uksi/1998/3178)."*
> — 6411, after the strengthening: the record reported, the limit stated, and
> the commencement order **retrieved** rather than recalled

The pre-pilot answer to this question named "the Scotland Act 1998
(Commencement) Order 1998" and a date, neither retrieved. The same instrument is
now cited with a URL the tool returned.

**And the blank report did not recur.** 6383's Deep Research turn produced a
proper 2,278-char report on the re-run, against 0 in `wave2_p25`. So the blank
was an empty provider completion and P2.5's longer synthesis prompt is not
implicated — which is what the re-run was for, and is cheaper than an argument
about it.

---

## B5 — the searches the record never mentioned (P2.9)

`search_log` is per-WORKER-RUN; the tool memo is per-REQUEST. A Deep Research step
repeating a search an earlier step already made was served from the memo, and the
memo branch of `run_worker_tool` never called `record_search` — so that query never
entered its own run's record.

### Before-column

    python -m tools.replay_report --dir evidence/replay/<dir> scoperecord

Over the **six** directories that have a scope block (`wave2_p22`,
`wave2_p22_final`, `wave2_p23`, `wave3_p35`, `wave2_p25`, `wave2_p25b`):

| | |
|---|---|
| worker runs with a scope block | **259** |
| `search_legislation` calls issued | **1,189** |
| of which memo hits | **277 (23%)** |
| recorded in the run's own block | **912** |
| **missing from the record** | **277 (23%)** |
| runs losing ≥1 query | **86 (33%)** |
| runs recording **no** search at all | **11** |
| `issued − recorded == memo hits` | **True, per run, 0 exceptions** |

**That identity is the finding.** It holds in aggregate and in every single one of
the 259 runs, across six independently-produced directories. Nothing other than a
memo hit eats the record — which is what makes a one-line fix the whole answer
rather than one fix among several.

~~`wave1` + `wave2_p21`: 359 of 1,497 memo hits, 78 of 358 runs losing a query.~~
**Those two directories predate P2.2 and carry no scope block at all** (182 and 56
worker runs), so they cannot lose anything and must be excluded rather than
counted. Including them deflated the loss rate from 33% to 22%.

### The defect is not a short count

**11 of the 86 lossy runs made every one of their searches via the memo.** Their
block therefore carries no searched-for line at all — while still carrying the
instruction that a negative *"MUST quote the search terms above"*. There were none
above. This is 6374 rep 1 turn 2, and what its worker actually handed the Manager:

> `[SEARCH SCOPE — what this research step actually did]`
> `Searched within 1 instrument(s) for specific provisions: ukpga/1998/46 …`
> `Filters in force for the whole step: jurisdiction=scotland, years any-2026.`
> `NONE of this can establish that something does not exist. If any part of the`
> `answer you write reports something as not found, it MUST quote the search terms`
> `above …`

The step had searched for `"Scotland Act 1998"`. The record does not say so,
because an earlier step had searched for it first.

**6374 is the session Invariant 1 is built on** — CambeulW scored it 5/5 *because*
AILA said it could not find something. The disclosure that earns that trust was
instructing the model to quote terms it had withheld.

### After

By construction, not by sweep. Every search a run issues is now recorded, so
`scoperecord` exits 0 on any directory produced after the fix — and no such
directory exists yet, so the next sweep any row runs is the first observation.
The behaviour is pinned by five unit tests, **three of which fail without the
fix**; the other two guard the opposite direction (a memoised
`get_legislation_text` must not be logged as a search of the index, and the
non-memo path must still record exactly once now that a third call site exists).

`replay_report negatives` re-run over all six post-P2.2 directories: unchanged, as
it must be — the fix touches product code, not the detector.

### One instrument correction, caught the usual way

The first version of `scope_record_gap` inferred block-absence from `recorded == 0`.
That cannot tell a **pre-P2.2 run** (no block exists) from an **all-memo run** (a
block exists and records nothing) — they look identical on the count alone. It
reported `wave1` as 13 runs "with a scope block" losing 100% of their searches, and
put the corpus-wide loss at 1,127 queries across 277 runs, roughly four times the
truth. Keying on the block **marker** settles it, and is pinned by a test.

That is the fourth published figure in three sessions to move the moment a command
was put behind it, and the second this session — the row's own numbers were the
first.

---

## B5 / B7 — negatives from turns that searched nothing (P2.10 → folded into P2.8)

Measured over all ten replay directories: **608 answered turns, 210 of them
asserting a negative**, graded with `NEG_ASSERTED`, the detector behind
`replay_report negatives`.

| shape | turns | owner |
|---|---|---|
| **(A)** no delegation, answer asserts a negative | **5** | 4 are **P2.8**, 1 is **P2.7** |
| **(B)** Worker delegated to, **zero** tool calls | **14** (6343, 6346, 6347, 6350) | **P4.1** (B7) |
| of (B), answer asserts a negative | **12** | — |

**(A), the four that are P2.8's defect.** In each, an earlier turn's negative is
restated, no search runs on this turn, and so no footer fires:
`wave2_p22_final/6409 r1 t11` and `r3 t4`, and `wave2_p25/6341 r2 t2` and `r3 t2`.
The defect recurs across reps in both sessions (2 of 3 in each), so it is a rate
and not noise. P2.10 described 6341 and P2.8 described 6409. They are one defect.

**(A), the fifth.** `wave1/6341 r1 t8` answers *"what do you mean by a stub"* from
training knowledge. It relies on no earlier search, so it belongs to P2.7's
speculation family, not P2.8. A carry-forward fix must not attach an earlier scope
to a turn like this one.

### ~~n=1 in 608~~: the first count used the wrong detector

`replay_report` holds **two** regexes for "asserts a negative":

- `NOT_FOUND` is the **P0.3 baseline** detector. It feeds `summary`, `baseline`
  and `compare`.
- `NEG_ASSERTED` is **P2.2's acceptance** detector. It feeds `negatives`.

Session 9's P2.10 check used `NOT_FOUND`, and Session 12 copied it. That produced
1 instance where the correct count is 5, and 3 of 14 where it is 12. A
consequence claimed at the time, that *"P2.2's published numbers were blind to
'The available database does not contain information…'"*, was **false**:
`NEG_ASSERTED` matches that sentence. Only the P0.3/P1.5 `compare`
bare-negative counts under-read it, and `negatives` has since replaced them.
**For any question about asserted negatives, use `NEG_ASSERTED`.**

### Why (B) cannot measure P4.1's anchoring bug

All 14 (B) turns are case-law questions asked under `legislation_only`. The
transcript export records **no research mode** for these sessions: `Filter:
Research mode` and `Session mode` are blank on every row. `replay_set.py` reads
the mode once per session and falls back to `legislation_only`. So in the replay
the mode never changed, even on turns where the lawyer says *"I have changed the
mode, please proceed"*. Those refusals are correct about the tool set, and none of
them shows the anchoring P4.1 describes.

What (B) does show is the **wording** of the refusal. *"The available database
does not contain information on this specific issue"* is a claim about the
corpus, when the true statement is about the tool set.

The split above is now a command, and it reproduces these figures exactly
(608 / 210 / A 5 / B 14 of which 12):

    python -m tools.replay_report --dir evidence/replay/<dir> nosearch

---

## B5 — the negative carried forward (P2.8, with P2.10 folded in)

P2.2's scope footer is emitted per turn, from that turn's searches. A follow-up
answered from the history runs no search, so it got no footer, even when it
restated an earlier negative.

### Before

`nosearch` grades a turn **UNQUALIFIED** when four things hold: it ran no
legislation search, an earlier answered turn did, its prose asserts a negative
(`NEG_ASSERTED`, footer removed), and it carries no scope statement.

| dir | session | UNQUALIFIED | `negatives` FAIL with `queries = 0` |
|---|---|---|---|
| `wave2_p22_final` | 6409 | 2 (r1 t11, r3 t4) | 2 |
| `wave2_p25` | 6341 | 2 (r2 t2, r3 t2) | 2 |

These are the only `queries = 0` FAIL rows in any post-P2.2 directory. `baseline`
and `wave1` list UNQUALIFIED turns too, but carry no footer at all, so the
command reports them and exits 0 (an absence, not a pass).

### The fix

`carried_scope_footer` (`utils/search_scope.py`) reads the code-emitted fresh
footers back out of the conversation history, and restates their search terms
as earlier searches:

> *Search scope: no search of the legislation index was run for this reply.
> Earlier in this conversation it was searched for "SSI 2025/377", "…" (further
> queries not listed); no jurisdiction, type or date filter narrowed it. Each
> was a ranked search of an index that is known to be incomplete, so a result
> reported as not found in those searches was not found in this index, which is
> not the same as being absent from the law.*

It fires when all four of these hold:
- this turn recorded no search (either search tool);
- no delegation raised;
- no peer was consulted;
- an earlier assistant message ends in a fresh footer.

**It never reads the answer.** The line keeps the footer's single-line shape, so
`_without_footer` strips it before the model's prose is graded, and
`_ECHOED_FOOTER` strips it when the model copies it back. A carried line is never
read as a source of searches, so turns neither stack nor chain. It is on the
Manager path only: the Deep Research synthesis never sees the conversation.

### After (`wave2_p28`, n=3 on both sessions)

| | before | after |
|---|---|---|
| 6409 `negatives`: turns / FAIL | 21 / 2 (`wave2_p22_final`) | **12 / 0** |
| 6341 `negatives`: turns / FAIL | 17 / 2 (`wave2_p25`) | **17 / 0** |
| UNQUALIFIED | 4 | **0** |
| MISATTRIBUTED (a scope statement for a search the turn did not run) | 0 | **0** |
| no-search turns after a searched turn carrying the line | — | **15 of 15** |

The defect's shape still occurs, in 1 of 3 reps of each session (6409 r1 t11,
6341 r2 t2), and now reaches the lawyer qualified. **The `model` column is
"no" on both**, so the pass is the code's, exactly as with P2.2: 1 of 29
negatives is explained by the prose alone.

6409 r1 t11, as the lawyer now sees it:

> As I mentioned previously, the full text of The Social Security (Amendment)
> (Scotland) Act 2025 (Commencement No. 2) Regulations 2025 (SSI 2025/377) is
> not currently held in the legislation database. […]
>
> *Search scope: no search of the legislation index was run for this reply.
> Earlier in this conversation it was searched for "Social Security (Amendment)
> (Scotland) Act 2025 (Commencement No. 2) Regulations 2025", "SSI 2025/377" …*

### Invariant 1, graded on the prose

`_invariant_one` compares whole answers, and this fix lengthens answers by
construction. So `nosearch --before DIR --only SESSION` compares the prose with
the footer removed, over shared sessions only.

| | before | after |
|---|---|---|
| **6341** vs `wave2_p25` (n=3 / n=3): negatives per rep | 5.7 | 5.7 |
| no-search turns per rep | 1.7 | 1.7 |
| worker tool calls per rep | 184.0 | 187.0 |
| turn slots whose prose grew | — | 3 of 8 |
| **6409** vs `wave3_p35` (n=3 / n=3): negatives per rep | 4.0 | 4.0 |
| no-search turns per rep | 4.7 | 3.3 |
| worker tool calls per rep | 35.7 | 34.7 |
| turn slots whose prose grew | — | 7 of 11 |

**6409's before-column is `wave3_p35`, not `wave2_p22_final`.** Against the
directory the handover named, 6409's negatives per rep fall 7.0 → 4.0 and tool
calls 94 → 35. That is **P3.5**, which landed in between and made 6409's
commencement relation retrievable (0 of 8 → 24 of 24). It is not this fix.

6341's largest drop in prose length is its Deep Research turn (12,839 → 9,570
chars). That path is untouched by this row and its synthesis never sees the
history, so about 25% is sweep-to-sweep noise, not an effect.

### The cost, stated

The gate cannot tell a restated negative from a clarifying question, so the
line fires on both. Over the three footered directories that have any such
turns, **27 no-search turns follow a searched turn, and 4 carry a negative**
(95% Wilson interval 6–33%):

| dir | no-search turns after a searched turn | of which negative |
|---|---|---|
| `wave2_p22_final` | 4 | 2 |
| `wave3_p35` | 14 | 0 |
| `wave2_p25` | 9 | 2 |
| **`wave2_p28` (after)** | **15** | **2** |

Printed by `nosearch` on its "no-search turns after a searched turn" line.
~~Over the four post-P2.2 directories~~ was a miscount in the first draft of
this section: `wave2_p23`, `wave2_p25b` and `wave2_p25_smoke` have none.

In this sweep the line fired on 15 of 57 answered turns. The 13 without a
negative are clarifying questions and positive follow-ups, each now carrying
~500 characters of scope line under an answer that can be as short as 61
characters. That is P2.2's trade, extended to follow-ups. **Kept as built by
the user's decision (2026-09-17).** The only structural narrowing available, a
reply-length cut, would miss short restated negatives: 6409 r1 t11 is 463
characters of prose.

### What the gate caught that a detector would not

6341 rep 1 turn 2 restates *"The agent's search returned no general case law
interpretations"*. `NEG_ASSERTED` does not enrol it, because "general" is not in
its adjective list. It carries the line anyway. That is the measured case for
gating on structure rather than on prose.

### What it does not fix

6341 runs under `legislation_only`. **No case-law tool is loaded, and none was
called in any of its runs.** Its restated negative is about case law, and rep 2
turn 2 says the agent *"conducted a comprehensive search across both the
legislation and case law databases"*. That search never happened.

The carried line qualifies the legislation searches and says nothing about case
law, which is correct. `negatives` passes the turn on that legislation
qualification alone, because it cannot tell which corpus a negative is about.
The false case-law claim is P4.1's, handover item (5).

### Free observations: the first directory after P2.9 and P4.2

- **`scoperecord` exits 0.** 57 worker runs, 348 searches, 70 of them memo hits
  (20%), and all 348 recorded. P2.9's after-column is now observed, not only
  true by construction.
- **`blanks` exits 0.** No billed blank in 57 turns.
- **One provider call was not recovered.** `audit.empty_completions` holds three
  attempts at one worker call, all empty (6409 r3 t11).
  - Attempts 1 and 3: `finish_reason=error`, *"Upstream idle timeout
    exceeded"*, 160 completion tokens.
  - **Attempt 2: `finish_reason=stop`, 62,915 completion tokens, 29,350
    reasoning characters, no content.** This is the first stored instance of the
    reasoning-token mechanism P4.2 could not rule out.
  - That turn cost $0.86, in a $1.44 run.
  - The worker handed the Manager a report consisting only of its scope block.
    The Manager re-delegated, so the lawyer's answer was sound, but the
    mechanism is a false-negative trap. It is now row **P4.5**.

- **`halts` exits 1: 5 halted turns, 1 failing, all in 6341.** Rep 1 turn 7
  is a Deep Research synthesis whose four steps all halted. Its prose says
  *"the research steps timed out due to internal limits"*, beneath the code
  notice saying the halt is not a timeout. It is the first such failure in 24
  halted turns since P2.1, and it is recorded on P2.1's row. This check was run
  after the fact: it was left out of the first pass over this directory.
- **6409 has stopped halting; 6341 has not.** 6409 has 0 halted turns in the 6
  reps since P3.5, and 6341 halts in ~~every rep of `wave2_p25` and `wave2_p28`~~
  **5 of 6 reps: 2 of 3 in `wave2_p25`, 3 of 3 in `wave2_p28`** (corrected at the
  end of Session 14 with `halts`; `wave2_p25` rep 2 has no halted turn).
  That moves P2.7's evidence, which is recorded on its row.

### Three instrument corrections

All three were found by the first directory to exercise the code paths
concerned. **No published number moved**: `blanks` still counts 8 billed blanks
across the historical directories, and `scoperecord`'s identity is still True on
all six pre-fix directories.

1. **`blanks` counted attempt records as calls.** A call that fails three times
   leaves three records, the first two marked `retried: true`. `blanks`
   reported *"recovered by retry 2, NOT recovered 1"* for one call that
   recovered from nothing. That flatters the provider. The command now groups
   records into calls (`empty_completion_calls`) and reports attempts
   separately.
2. **`blanks` called a clean v3 directory pre-v3.** It tested whether
   `empty_completions` was non-empty. P4.2 made the field present-and-empty on a
   healthy turn precisely so the two cases differ, so the command now tests
   whether the key is present.
3. **`scoperecord` printed `identity … : False` on a complete record.** After
   P2.9, memo hits are recorded rather than lost, so `issued − recorded` is 0 and
   is not equal to the memo count. The identity is now printed only when
   something is missing.

### Spend

| | |
|---|---|
| smoke, n=1 | $3.35, 24 min |
| acceptance, n=3 | **$10.30**, 82 min |
| total | **$13.65** |

Estimated beforehand at about $11 and 75 minutes for the n=3 sweep.

## B12 — the case-law corpus gap, disclosed in code (P2.4)

The National Archives' Find Case Law holds Scottish appeals decided by the UK
Supreme Court. It holds no decision of the Court of Session, the Sheriff
Appeal Court, the Sheriff Courts or the High Court of Justiciary. A Scots-law
query does not come back empty: it comes back with English judgments. The one
note the code already emitted fired only on an empty result.

### The instrument, first

`SCOTS_CASELAW_GAP` (behind `summary` and `compare`) cannot grade this row.

- **It over-reads.** It fires on the bare name of a Scottish court. Over the
  twelve pre-P2.4 directories it fires on 26 answered turns. 22 of them never
  searched case law, and only one of those 22 (`wave1/6408 r1 t3`) states the
  gap. The rest are things like *"Rule 35.8 of the Rules of the Court of
  Session 1994"*, *"the Clerk of the Sheriff Appeal Court"* and *"sheriff
  court jurisdiction"*.
- **After P2.4 it is satisfied by construction**, because the code's line names
  the Court of Session.

It is left unchanged, because `summary` and `compare` publish its count. **From
P2.4 on, `compare`'s `scots_gap_disclosures` counts the code's line.** That is
true to what the lawyer sees, but it is not a measurement of the model.

**`replay_report caselaw` is the acceptance.** It grades with
`caselaw_gap_statements`, which needs three things in one sentence: a named
Scottish court, a named corpus, and a stated limit. A court's name inside an
instrument title is masked. The command reports three things:
- **disclosed**, graded on the full answer;
- **code**, meaning the code's line is present;
- **model**, graded on the prose with the footer removed.

**Validated both ways over all fourteen directories.**
- `--drops` lists every sentence that names a Scottish court and was not
  counted. None of them states the gap: they are court rules, court clerks, a
  "Scottish Case Law" heading, and a suggestion to switch mode.
- `--all --answers` lists every sentence that was counted, on every turn.
  - **The first version of the detector over-read once**: *"the Rules of the
    Court of Session 1994 … do not contain an explicit provision"*
    (`baseline/6372 r3 t2`). A check over case-law turns only could not have
    found it, because that turn searched no case law.
  - **One known over-read remains, and is left.** 6341 and 6348 say *"the
    available database does not contain information on Scottish case law"*
    on 6 turns with no case-law search. That can only move the all-turns
    column, never the acceptance, which reads only turns that searched case
    law.

### Before

Turns that searched case law, and whether the answer stated the gap:

| dir | session | case-law turns | disclosed | of which by the model |
|---|---|---|---|---|
| `baseline` + `wave1` | 6375 | 7 | **0** | 0 |
| `baseline` + `wave1` | 6385 | 6 | **0** | 0 |
| `baseline` + `wave1` | 6363 | 8 | **0** | 0 |
| `baseline` + `wave1` | all | 52 | 4 | 4 (6370 ×3, 6407 ×1) |
| **`wave2_p24_pre`** (HEAD `4890573`, n=3) | 6375 | 5 | **1** | 1 (a conversational turn) |

**The like-for-like before-column is `wave2_p24_pre`**, which this session ran
at HEAD. `baseline` and `wave1` both predate P2.2. **6375's Deep Research turn
disclosed in 0 of 3 reps at HEAD**, although it made 16–24 `search_case_law`
calls in each.

### The fix

A turn that called `search_case_law` gets this sentence, in code:

> *It holds Scottish appeals decided by the UK Supreme Court, but not the
> decisions of the Court of Session (Inner or Outer House), the Sheriff Appeal
> Court, the Sheriff Courts or the High Court of Justiciary, so judgments it
> returns for a Scottish question may come from courts outside Scotland.*

It is preceded by *"For this reply the case-law database (the National
Archives' Find Case Law) was searched for "…", "…""*.
- **It is always one line.** The sentence is a clause inside the legislation
  line when there is one, fresh or carried.
- **It stands alone only when there is no legislation line**, as on every
  `case_law_only` turn:
  > *Search scope: for this reply the case-law database (the National
  > Archives' Find Case Law) was searched for "XL bully". It holds Scottish
  > appeals decided by the UK Supreme Court, but not …*
- **P2.8's parse and `corpus`'s duplicate counter are unaffected.** P2.8's
  parse reads only the last line, and `corpus` counts two lines as a
  duplicate. With one line, neither is disturbed.

### After (`wave2_p24_final`, head `051472d`, n=3 on 6375, 6373 and 6385)

| | before | after |
|---|---|---|
| 6375: case-law turns disclosing | 1 of 5 (`wave2_p24_pre`) | **6 of 6** |
| 6375: Deep Research turns disclosing | 0 of 3 | **3 of 3** |
| 6385 (`case_law_only`): case-law turns disclosing | 0 of 6 (`baseline`+`wave1`) | **9 of 9** |
| UNDISCLOSED / MISATTRIBUTED / TWO_LINES | 4 / 0 / 0 (`wave2_p24_pre`) | **0 / 0 / 0** |
| gap stated in the model's own prose (case-law turns) | 1 of 5 | 0 of 15 |

**The pass is the code's.** The model column did not rise. Across this
session's four post-fix sweeps, the model stated the gap on 1 of 44 case-law
turns (`wave2_p24/6375 r3 t2`).

**Every exit-1 subcommand passes on `wave2_p24_final`:**
- `halts`: 0 halted turns.
- `negatives`: 10 turns, 0 failing.
- `derivations`: 0 claims.
- `blanks`: 0 violations.
- `scoperecord`: complete.
- `nosearch`: 0 UNQUALIFIED, 0 MISATTRIBUTED.
- `caselaw`: 0 findings.

### The 6373 half: a not-held instrument is not a wrong citation

FrankieH cited SSI 2026/170, correctly. LEX still 404s it (checked
2026-09-17). **It was measured at HEAD before any change**
(`wave2_p24_pre`):

| | `baseline` | `wave1` | **`wave2_p24_pre`** | smoke | `wave2_p24` (block) | **`wave2_p24_final`** |
|---|---|---|---|---|---|---|
| turn-2/3 slots | 2 | 2 | 6 | 2 | 6 | 6 |
| answer questions the citation | 2 | 1 | **2** | 0 | 0 | **0** |
| Worker report questions it | 2 | 0 | **3** | ≥1 | 0 | **1** |

The Worker column is a narrow regex, so it is a floor: it misses the smoke's
*"I suggest checking the exact title or citation"*. The HEAD answer column is 1
by `NEG_BLAMED_USER` plus one substitution the detector misses: *"It is
possible you are referring to the … 2021 (SSI 2021/170)"*. That is the only
such miss anywhere in the corpus.

**The trigger was structural.** Every HEAD Worker report that blamed the
citation came straight after `get_legislation_text` returned
`Legislation not found: ssi/2026/170`. The twelve pre-P2.4 directories hold
36 such results, 31 of them in 6409 and 6373. The draft of this line said
"40, 32 of them": that count had silently included `wave2_p24_pre`, and even
then the right split is 35.

**The fix, in three places:**
- a code note on that not-found result (`not_held_note`);
- a line in the worker block (`_not_held_limb`);
- a one-line rule in both legislation Manager prompts, the three research
  Worker prompts, and the chat Worker's OUTPUT bullet.

**`negatives` on `wave2_p24_final`:** 6373 has 6 negative turns and 0
failing. The earlier `wave2_p24` sweep also had 0 failing, on 5 negative
turns.

**The code note never fired in either n=3 sweep.** No 6373 run called
`get_legislation_text`. The note fired only in the smoke run, and the Worker
ignored it there, although the Manager filtered the result. **So the pass
comes from the prompt rules, and the note's effect on the model is
unmeasured.**

### The A/B that took part of the fix back

The rule was first appended as a block to all four Worker prompts. On 6385,
that changed the chat-mode Worker's format.

| 6385, n=3 each | `wave2_p24_ab` (`6806fa0`, no Worker rule) | `wave2_p24` (`8006db9`, block) | `wave2_p24_final` (`051472d`, clause) |
|---|---|---|---|
| Worker reports in bullets | 0 of 9 | **5 of 9** | 2 of 9 |
| case-law links reaching the answer | 7 of 15 | **2 of 13** | 7 of 13 |

The only runtime difference between `6806fa0` and `8006db9` is that block. The
chat-mode Manager rewrites a bulleted report and drops the link wrapped round
each case name.
- **The chat-mode Worker now carries the rule as one clause** inside its
  existing OUTPUT bullet. That bullet is also where its blame phrasing came
  from: *"… try a fuller search in Research mode"*.
- **The research Workers keep the block.** 6375's research path linked more
  cases with it, not fewer.
- **Links dropped by the Manager are also pre-existing.** In `wave2_p24_ab`,
  1 of 3 turn-1 answers lost both links from a prose report.

### Invariant 1, graded on the prose

Shared sessions only. `caselaw --before` and `nosearch --before` do the
comparison.

| | before | after (`wave2_p24_final`) |
|---|---|---|
| **6375** vs `wave2_p24_pre` (n=3/n=3): prose length, t1 / t2 | 1,639 / 11,721 | 1,784 / 13,885 |
| case-law judgments linked per rep | 5.7 | 10.0 |
| UKSC judgments linked per rep | 0.7 | 1.0 |
| … of which Scottish appeals | 0.0 | 0.0 |
| **6373** vs `wave2_p24_pre`: negatives per rep | 1.3 | 2.0 |
| prose length, t1 / t2 / t3 | 890 / 428 / 320 | 919 / 310 / 304 |
| worker tool calls per rep | 15.0 | 8.7 |
| **6385** vs `baseline` / `wave1` (n=1 each): case-law links per rep | 4.0 / 3.0 | 2.3 (and 2.3 in `wave2_p24_ab`) |

- **6375 holds on every measure.** No Scottish UKSC appeal is cited in any
  post-P2.2 run of 6375. `baseline` rep 3 cited *Christian Institute v Lord
  Advocate* [2016] UKSC 51. At HEAD it was retrieved in 2 of 3 reps and cited
  in none; after, it was retrieved in 3 of 3 and cited in none. That predates
  this row.
- **6373's shorter turns 2 and 3 are the removed blame and substitution.**
  - On turns 2 and 3, tool calls fell from 35 to 14. Six of the 35 were
    retrievals by id of the not-held instrument, or section searches of the
    substitute 2021 Regulations. None of those happen now.
  - The rest of the drop is fewer re-searches for an instrument the index does
    not hold.
  - Every answer still says plainly that the instrument is not held, and
    negatives per rep rose.
- **6385's fall in links against `baseline` is not this change.** It is 2.3 per
  rep with and without any Worker rule. The before-columns are n=1 and predate
  P2.2.

### The cost, stated

The line fires on every turn that searched case law, whatever the question's
jurisdiction. 6385 asks about English XL Bully cases, and each of its answers
now carries ~420 characters about Scottish courts. A 6375 Deep Research answer
carries the case-law clause after the legislation line and its P2.3, P3.5 and
P2.5 clauses, so the whole line runs to ~1,800 characters. This is the P2.2 and
P2.8 trade: the product never gates on reading the question.

### Free observations

- **P4.5 closed its trap on a lawyer.**
  - In `wave2_p24_pre/6375 r3 t2`, Deep Research step 1 ran three case-law
    searches that returned 4, 43 and 31 judgments.
  - Its final completion was then empty three times, so the step report was
    `""`.
  - The synthesis said *"Step 1 found no results"*.
- **Running count of unrecovered provider calls, from `blanks`: 6 in 166
  answered turns** (95% Wilson interval 1.7–7.7%), across the seven schema-v3
  directories. Five were in workers, and one was a Manager call covered by
  P4.2's fallback. Four of the six ended in *"Upstream idle timeout
  exceeded"*. Recorded on P4.5's row.

### Spend

| directory | head | runs | spend |
|---|---|---|---|
| `wave2_p24_pre` | `4890573` | 6373 ×3, 6375 ×3 | $3.87 |
| `wave2_p24_smoke` | `6806fa0` | 6373, 6375, 6385 ×1 | $1.76 |
| `wave2_p24` (A/B "with") | `8006db9` | all three ×3 | $5.31 |
| `wave2_p24_ab` (A/B "without") | `6806fa0` | 6385 ×3 | $0.49 |
| **`wave2_p24_final`** (acceptance) | `051472d` | all three ×3 | **$5.20** |
| **total** | | | **$16.63** |

The row estimated about $4 for n=3 plus $1.30 for the smoke run. 6375 ran at
$0.70–1.78 and 7.3–11.2 minutes per rep, against an estimate of $0.94 and 6–7
minutes.

---

## The discovery budget (P2.7)

`run_worker_agent` gave a search budget only to the parliamentary modes. A
legislation Worker could therefore search until `chat_loop`'s 20-round step cap
stopped it — and a halted worker writes **no findings at all**, so every
retrieval it paid for is lost to the answer.

### The unit is rounds, and that is the finding this row turns on

The row's pre-flight fitted a budget of N **issued calls**. That is the wrong
unit, and the data says so in two directions.

- **The cap counts rounds, and the model batches.** 6341's broad question
  ("every statutory definition of shop in Scots law") completes delegations that
  issue 9-21 searches in 6-16 rounds. A call budget cuts those exactly as hard
  as it cuts a flail.
- **Search rounds separate the two groups; calls do not.** Per worker run, over
  the post-P3.5 pool (`wave3_p35`, `wave2_p25`, `wave2_p28`; 162 runs):

| per worker run | halted (13) | completed (149) |
|---|---|---|
| `search_legislation` issued | median 12, max 24 | median 2, p90 7, max 21 |
| **rounds in which it searched** | **median 14, min 6** | **median 2, p90 5, max 9** |

  A budget of **8 search rounds** stops 11 of 13 halted runs and 1 of 149
  completed. The best call budget (N=10) stops 8 of 13 and 9 of 149, and the
  nine it stops are 6341 delegations that finished.

- **Memo hits count, and that decision came from the same data.** 57 of the 81
  memo hits on halted runs repeat a search the same step had already made
  (6383: 5 issued, 9 repeats). So the legislation check runs BEFORE the memo
  lookup, unlike the parliamentary one. Charging by round keeps the cost to a
  Deep Research step that legitimately reuses an earlier step's search at one
  round.

- **`search_case_law` is not budgeted** (user decision): no halted run in any
  directory issued one, and completed 6375 steps use up to 9 case-law rounds.

Checked on the other pools at K=8: `wave2_p21`+`wave2_p23` 10 of 14 halted and
0 of 99 completed; the P2.2-era directories (6409's flail) 14 of 14 and 6 of
113; the five P2.4 directories, which have no halts, 0 of 115 completed.

### Before — measured at HEAD, because no 6341 run existed at a post-P2.4 head

`wave2_p27_pre`, head `7a98e60`, n=3 on 6341 and 6374, **$13.58**. Both
sessions halt in **3 of 3 reps**: 12 halted turns, 15 halted worker runs. All 12
were disclosed correctly (`halts` 0 failing) — P2.1 is doing its job; what the
halts cost is the research thrown away.

| per worker run, at HEAD | halted (15) | completed (45) |
|---|---|---|
| `search_legislation` issued | median 14, max 32 | median 4, max 20 |
| rounds in which it searched | median 13, min 8 | median 3, max 11 |

K=8 would stop 14 of the 15 halted runs and 4 of 45 completed — and those four
ran to 14-18 rounds, within six of the cap.

### After (`wave2_p27`, head `bbb5416`, n=3 on both, $13.57)

| | before | after |
|---|---|---|
| **halted worker runs** | **15** | **2** |
| halted turns | 12 | 2 |
| 6341: halted runs / rep | 3.3 | **0.0** |
| 6341: turns at the step cap / rep | 2.7 | **0.0** |
| 6374: halted runs / rep | 1.7 | 0.7 |
| 6341: **sources kept / rep** | 57.7 | **59.3** |
| 6374: **sources kept / rep** | 35.0 | **35.7** |
| 6341: search rounds / rep | 67.3 | 54.0 |
| 6374: search rounds / rep | 47.3 | 29.3 |
| 6341: retrieval calls / rep | 92.0 | 99.3 |
| 6374: retrieval calls / rep | 69.0 | 72.0 |
| turns asserting a negative, failing | 19, **0** | 24, **0** |

**Attribution is not uniform, and the write-up says so.** The budget fired in
all three 6341 reps (4, 3 and 3 refusals) and its halted runs went 5, 2, 3 ->
**0, 0, 0**. In 6374 it fired **once in three reps**, and its halts went 3, 1, 1
-> 1, 1, 0: movement inside the noise, not this fix. Invariant 4 asks for n=3
all clean on a FAIL session; **6341 gives exactly that**, and 6374 does not
contribute the same weight.

**The two halts that remain are not discovery-bound, which is the honest
limit of this row.** Both are 6374 turn 4, Deep Research step 3, at **6 and 8
search rounds** — at or under the budget, so it never fired on them. Their 20
rounds went on retrieval: 8 section searches and 6 change lookups in one; 13
section searches, 4 text retrievals and 10 same-resource repeats in the other.
That is the shape **P3.8** was opened for, and no discovery budget can touch it.

### Invariant 1, graded on the prose with the footer removed

`sources_kept` per rep **rose** in both sessions. Per turn slot it fell in 2 of
8 (6341) and 2 of 4 (6374) — **against a noise floor of 3 of 8**, measured
between `wave2_p25` and `wave2_p28`, two sweeps of 6341 that differ only by
P2.8, which does not touch a researched turn.

6341's prose grew in 5 of 8 slots, and its Deep Research turn nearly doubled
(6,784 -> 13,389 characters) because the steps now finish and write findings
instead of halting. 6374's shrank in 3 of 4, and its turn 2 is the one to
explain: it dropped in all three reps (6,640/9,263/8,786 -> 5,914/5,507/6,643).
**No refusal ever fired on that turn in either sweep.** Its Deep Research plan
was drafted differently (3 steps per rep before, 4 after; 34 searches -> 12,
36 section searches -> 23), which is the planner stochasticity the replay
configuration already records as a confound for every replayed DR turn.

### What the lawyer is told, and what the model then said

The clause fired on **7 of 7** stopped turns, with the right count in each
("one research step ... 1 further search"; "2 research steps ... 2 further
searches"). In **5 of those 7** the model also stated the limit in its own
prose, unprompted by any system rule:

> *Searching was cut short by a limit on how much one step may search, so the
> text for the Protection of Workers ... could not be verified.*

Nothing manufactured a negative out of a stop: `negatives` grades 24 turns
asserting a negative and **0 failing**, and `nosearch` reports 0 UNQUALIFIED and
0 MISATTRIBUTED.

### Every exit-1 subcommand, and the two that exit 1

`halts` **0 failing** (and 0 halted turns), `negatives` 0 failing, `blanks` 0
violations and 0 unrecovered calls, `scoperecord` complete, `nosearch` 0/0.
Two exit 1, and neither is this row's:

- **`derivations`: 2 UNVERIFIED claims, both 6374, and the count is identical
  before (2) and after (2).** It is P2.3's residual shape — "made under section
  126(8)" with no preamble retrieved — and it is present in `wave2_p23` and
  `wave3_p35` too.
- **`caselaw`: 1 TWO_LINES, 6341 rep 2 turn 2.** The answer carries two
  `*Search scope:` lines, and **the first is the model's own imitation**, written
  mid-answer ("among 8 searches in total"; "no filters were applied" — not the
  code's wording), so `strip_answer_footer`, which is anchored to the end, cannot
  reach it. **It is not from the budget:** that turn recorded no refusal, its
  worker report carries no limb, and its "8 searches" is the 8 searches it
  actually made, not the budget's 8 rounds. Base rate over every directory since
  P3.5 added the echo strip: **1 in 513 answered turns (95% Wilson 0.03-1.10%)**;
  the only other instance is `wave2_p22_final`, which predates that strip and has
  18. Recorded against the footer family (P2.2/P2.8), not here. **If it recurs,
  the new row belongs in Wave 4** — a P2 row would re-block P3.1 and P4.1, which
  depend on `P2.*`.

### Free observations

- **The budget bound as designed:** 11 refusals in 10 of 60 worker runs, and no
  completed run in the after-directory exceeds 8 search rounds.
- **No fail-open in live traffic:** across both sweeps the server logged no
  "no ReAct round" warning and no budget error, so the ContextVar reached every
  tool call `chat_loop` made.
- **P4.5's running count is now 7 unrecovered provider calls in 250 answered
  turns** (95% Wilson **1.4-5.7%**) over the ten schema-v3 directories: the one
  new instance is `wave2_p27_pre/6374 rep 3 turn 4`, a Deep Research step whose
  report is its scope block alone. The synthesis covered the gap from the other
  steps and asserted nothing false about it, so the trap did not close on the
  lawyer this time.
- **A model sentence about a budget stop trips `HALT_PARAPHRASE`** ("a system
  limit"), which `summary` and `compare` count as halt language. Those run only
  over full sweeps; `halts` is unaffected, because a halted turn always carries
  P2.1's code notice. Worth remembering at the next full sweep.

### Spend

| | | |
|---|---|---|
| `wave2_p27_pre` (before, head `7a98e60`) | 6 runs | $13.58 |
| `wave2_p27_smoke` (n=1, head `a38ff98`) | 2 runs | $3.69 |
| **`wave2_p27`** (acceptance, head `bbb5416`) | 6 runs | **$13.57** |
| **total** | | **$30.84** |

Against the row's estimate of about $25. 6341 ran at $2.25-2.96 and 13-21
minutes per rep; 6374 at $1.43-2.67 and 8-17 minutes.

## The Wave 2 re-baseline (`wave2`, before Wave 3)

Invariant 3 says to re-baseline before Wave 3, and no ledger row held one. The
user decided at the start of Session 16 to take it **at HEAD `2d9ae11`, before
any P3.1 product code**: n=1 over all 41 sessions, like-for-like with `wave1`
(P1.5). This is the baseline for the rest of Wave 3.

**41 runs, 155 turns, $29.55, 4.0 hours, 0 model mismatches, 0 errored turns**
(one turn asked for clarification: 6347 turn 2). Against `wave1`'s $27.22 and
3.7 hours: x1.09 on cost.

### Wave 1 to Wave 2, rep 1 like-for-like

`replay_report compare --before wave1 --after wave2`, with two lines replaced
by the grader that owns them (see below).

| | `wave1` | `wave2` | row |
|---|---|---|---|
| `search_legislation` calls | 790 | 613 | |
| searches the filters emptied | 3 | 3 | P1.1 |
| provision URLs cited | 136 | 676 | |
| ... reconstructed after summarisation | 26 | **0** | P1.6 |
| ... manufactured (never retrieved) | 0 | 0 | P1.4 |
| ... wrong granularity (Act link, provision label) | 32 | 12 | P1.4 |
| runs with a halted worker | 10 | **2** | P2.1, P2.7 |
| halted turns that never said so | 5 | **0** | P2.1 |
| unsupported in-force claims (`currency`) | 43 | **3** | P2.5 |
| ... citing a text version as the evidence | 48 | **0** | P2.5 |
| sources cited in the answer | 201 | 257 | |
| empty answers | 2 | 0 | P4.2 |
| model prose, footer stripped per answer | 316,661 | 387,085 chars | |

Model prose grew 22% and fell in 39 of 155 turn slots, so nothing on this page
was bought by shortening answers (Invariant 1).

### Three numbers not to quote as printed

- **`compare`'s "unsupported in-force claims 30 -> 61" is circular.** It runs
  the old `IN_FORCE_CLAIM` over the whole answer, and P2.5's own lawyer-facing
  disclaimer trips it. P2.5's grader, `currency`, reads the model's prose:
  UNSUPPORTED 43 -> 3, assertion sentences 66 -> 4, the old detector on the
  prose alone 30 -> 6 turns. The same shape as the `HALT_PARAPHRASE` hazard
  recorded at P2.7.
- **"sources kept 612 -> 443" is mostly one session's rail noise.** 6363 went
  135 -> 33, and 104 of its 135 were never cited. Sources the answers actually
  cite rose 201 -> 257. `sources_kept` fell in 19 sessions and rose in 15.
- **A first scratch figure of -62% prose was my script, not the product.** It
  joined each session's answers before stripping the footer, and the footer
  pattern is end-anchored, so from the first footer on it ate every later turn.
  That bites only post-P2.2 runs, which is why it looked like a regression.
  Recomputed per answer: +22%.

### Every exit-1 subcommand

`halts`, `derivations`, `blanks`, `scoperecord` and `caselaw` pass. Two exit 1,
and neither is a Wave 2 regression:

- **`negatives`: 7 FAILs, all 6346 (5) and 6347 (2).** These are B7's mode
  dead-end sessions (P4.1): delegations that made zero tool calls, whose
  negative is about the research mode, not the statute book. `wave1` has 6 in
  the same two sessions.
- **`nosearch`: 1 UNQUALIFIED, 6363 turn 5, and it is an over-read.** The
  "negative" is P2.5's required disclaimer (*"in-force status ... was not
  verified, as no commencement, repeal, or revocation records were
  retrieved"*), and the turn does carry P2.4's case-law scope line; `nosearch`
  recognises only the legislation footer. Recorded, not fixed here.

## B10 — the provision at the depth asked for (P3.1)

### The instrument, built and validated before any sweep

`replay_report depth` grades each turn against a ground truth checked against
the live LEX text on 2026-09-18, with each bar taken from the lawyer's own
feedback: 6396 needs SSI 2007/174 Sch 1 para 1(2) (36 hours / 20 days); 6365
needs Water Industry (Scotland) Act 2002 ss.45 and 57 and Public Finance and
Accountability (Scotland) Act 2000 ss.21 and 22 each cited at subsection depth;
6348 needs FOISA s.36(2) with its substance before the lawyer asked for it (turn
1). Verdicts DELIVERED / PARTIAL / SHALLOW / MISSED, on the answer with the scope
footer stripped (the footer quotes search terms and would otherwise satisfy
6348 by construction).

Validated both ways: the **original pre-pilot answers** grade MISSED / SHALLOW /
SHALLOW, exactly as the three lawyers described them, and `--drops` over
`baseline` and `wave1` shows no under-read. HEAD then showed the verdict's
"at least once" bar is lenient (two of 6365's anchors were met only by amendment
notes), so a strict per-requirement readout ("N of M references at depth") is
printed beside it.

### Before: measured at HEAD, and where the depth goes

`wave3_p31_pre`, n=3 at `2d9ae11` (rep 1 from `wave2`): **0 of 9 runs deliver.**

| | HEAD | the target provision, retrieved? | where the depth was lost |
|---|---|---|---|
| 6396 | SHALLOW 3/3 | Sch 1 in full, one section search | Worker cites "Schedule 1"; chat Manager drops the provision (2 of 3) |
| 6365 | PARTIAL 2, SHALLOW 1; 0-17% at depth | all four sections, every subsection | the synthesis flattens (rep 2: s.57 4/20 in the steps, 0/10 in the report) |
| 6348 t1 | SHALLOW 3/3 | s.36, both subsections, one section search | the Worker describes s.36(1) only |

**Retrieval was complete in 9 of 9 runs**, and the summaries keep subsection
numbers. So B10 in this acceptance set is a composition failure, not a Phase 2
one, and a prompt taught it: every legislation Worker's citation example was a
whole-section label, and the quick-lookup Worker was told to cite "Act +
section".

### The ranked sections array: real, measured, not used

Every `search_legislation` result carries `sections: [{number, provision_type,
score}]`. It ranks provisions against the search query, which the Worker prompt
makes the Act's title:

- FOISA's title search ranks ss.70, 76, 3 and Sch 4, and **omits s.36**;
- SSI 2007/174's topical search ranks reg 1, Sch 5, Sch 3 and reg 2, and **omits
  Sch 1**, which holds the answer;
- over stored runs it held the provision the answer later cited 219 of 331 times
  (66%) for topical queries and 130 of 232 (56%) for title-only ones.

An empty `number` is any non-integer id: inserted sections (131A, 99B), dotted
court rules (3.45.13), Parts, and one malformed LEX uri. Not used (user
decision); `_slim_search_results`' docstring now says why.

### After (`wave3_p31`, head `779bfb2`, n=3, $3.34)

| | HEAD (`wave3_p31_pre`) | after (`wave3_p31`) |
|---|---|---|
| 6396 | 0/3 | **3/3** |
| 6365 | 0/3 | **3/3** |
| 6365 references at subsection depth, per anchor | 0-17% | 60-95% |
| 6348, turn 1 | 0/3 | **1/3** |
| 6348, by turn 2 | 2/3 | 3/3 |

6348's rep 1 is the second smoke run's, on the same commit and configuration.
The synthesis fix (the pinpoint block) is what moved 6365: in its three runs the
report kept the steps' pinpoints (`s.57(3)`, `s.21(2)`, `s.45(1)(c)`), where
the first smoke run, on the prompt change alone, flattened every link label.

### Invariant 1, and every exit-1 subcommand

- `discovery --before`: `sources_kept` per rep 6348 4.3 -> 5.0, 6365 8.3 ->
  8.0, 6396 1.0 -> 1.0; fell in **2 of 6** turn slots, inside the 3-of-8 noise
  floor.
- `depth --before`: prose and links each fell in 1 of 6 slots (6348 turn 2);
  links per rep rose (6365 35.0 -> 42.7, 6396 0.3 -> 2.0). Its source column is
  `rail_sources` (the rail's list), a different count from `sources_kept`.
- `halts`, `negatives`, `derivations`, `blanks`, `scoperecord`, `nosearch` and
  `caselaw` all pass, before and after.
- The section budget never fired (these sessions do not loop); P2.7's fired
  twice in 6365 rep 3, and its clause reached the footer. No fail-open warning.

### The residuals

- **6348 turn 1 at 1 of 3** becomes **P3.11** (user decision). In both misses
  the Worker cited s.36(1) and never mentioned s.36(2), which it had retrieved.
- **A new failure mode the fix exposes: a wrong pinpoint.** 6365 rep 2 cites
  s.57(1) for the interim-report period, which is s.57(3)(a), three times, from
  a step Worker's report. On the four timeline claims (6 months, 9 months, 30
  September, true and fair view) the pinpoints are right 31 times and wrong 3 in
  `wave3_p31`, against 20 right and 0 wrong in `baseline` and `wave1`. A wrong
  pinpoint reads as verified, and P1.6 cannot catch it because the URL is right.
  Two apparent wrong pinpoints were the checker's own error (`s.57(3a)` is
  s.57(3)(a); `s.21(1)` was cited for the audit requirement, correctly).

### Spend

| | | |
|---|---|---|
| `wave2` (the full re-baseline, head `2d9ae11`) | 41 runs | $29.55 |
| `wave3_p31_pre` (reps 2-3 at HEAD) | 6 runs | $2.52 |
| `wave3_p31_smoke` (head `d2f9b48`) | 3 runs | $1.30 |
| `wave3_p31_smoke2` (head `779bfb2`, stopped by the user after 6348) | 1 run | $0.58 |
| **`wave3_p31`** (acceptance, head `779bfb2`) | 8 runs | **$3.34** |
| **total** | | **$37.29** |

Plus at most $0.76 unrecorded: the interrupted 6365 run in `wave3_p31_smoke2`.
P3.1 alone cost $7.74, against the handover's $12-15.

## P3.8 — the same-resource loop, and the halted worker's lost findings

The row had two halves. The first — a worker that keeps section-searching the
instruments it already has until the 20-round cap stops it — was bounded by
P3.1's cap of 3 section-search rounds per instrument, installed after `wave2`.
The second is independent of any budget: a halted worker wrote **no findings at
all** (`halt_worker_report` replaced its content), so every retrieval it had
paid for was lost to the answer while its sources still reached the rail.

### The first half, measured at HEAD before anything was built

`wave3_p38_pre`, head `b7f9f96`, 6335 n=3, **$2.52, 19 min**. 6335 turn 7 is the
row's canonical shape and the only halt among the row's evidence sessions in
`wave2` (`replay_report --dir wave2 discovery --runs`).

| 6335 turn 7 | `wave2` (before P3.1, n=1) | HEAD (n=3) |
|---|---|---|
| halted | **1 of 1** | **0 of 3** |
| ReAct rounds | 20 | finished |
| section searches that ran | 18 (17 on one resource, 10 exact repeats) | 3, 3, 3 |
| section searches the P3.1 cap refused | — | 0, 1, 1 |
| prose, footer stripped | 627 chars (*"could you narrow this down?"*) | 2,933 per rep |

(`replay_report --dir wave3_p38_pre discovery --before wave2 --only 6335`;
halts 0, `halts` 0 failing.)

**`sources_kept` fell in 3 of 7 turn slots against a noise floor of 3 of 8,
and none of the three is a researched turn.** They are turns 4-6, where the
lawyer repeats one case-law question in legislation-only mode: at `wave2` the
Manager delegated every repeat (a Worker searched statute for case law and
reported the database holds none), at HEAD it answers two of the three repeats
without re-delegating and tells the lawyer to switch mode. Worker runs per rep
7 -> 5 is the same fact. That is B7's shape (P4.1), not this row's.

### How much of the halt problem the first half ever was

Counted with one method over **every replay directory** (25 directories,
1,542 worker runs, 100 halted): the rounds in which each instrument was
section-searched, per run, rebuilt from `started_at` as `discovery` does
(memo hits count — the cap is checked before the memo; refused calls do not).

| max section-search rounds on ONE instrument, per run | halted (100) | completed (1,442) |
|---|---|---|
| median / p90 / max | 1 / 6 / 18 | 1 / 2 / 7 |
| **more than 3 (P3.1's cap fires)** | **19** | 23 |

`replay_report --dir baseline discovery --also <every other directory>`. So the
same-resource shape was **a fifth of historical halts**. The other 81 are the
discovery flail P2.7 removed and retrieval-bound runs that neither budget
touches — `wave2_p27/6374 r1 t4 step 3` halted at 2 section rounds on one
instrument, 6365 step 3 (`wave2`, `wave3_p31_pre`) at 1 — which is why the
second half is built even with both budgets in place.

### Why 6335 looped (probed live, 2026-09-21)

The worker asked eighteen times for *"Schedule B1 paragraph 43"* and the
section search returned Part A1 sections (A16, A20, A21, 233B) every time.
`POST /legislation/section/lookup` for `ukpga/1986/45` returns **674
provisions, of which Schedule B1 is ONE** (`.../schedule/B1`): the index has no
paragraph rows to return, and the paragraph query never ranks the Schedule into
the top 10 (a topical query at `size` 20 does). The model was asking for a
granularity the index does not have. The cap now stops it; the lawyer still
does not get paragraphs 42-44 (all three HEAD reps reach paragraph 44 only as a
cross-reference inside the Part A1 sections). New row **P3.12**.

### The second half: prototyped on the seam, then built

Before any code, two tool-free draws from `wave2/6335 t7`'s recorded
retrievals ($0.21): both a structured partial report, every link one a tool had
returned, both stating the Schedule B1 paragraphs were not retrieved. Then
built: at the cap `chat_loop` makes ONE more call with no tools and
`halt_writeup_instruction` appended; `halted.written_up` (audit v4) says whether
it produced anything; the worker keeps the findings under P2.1's header, which
now says PARTIAL; the lawyer's notice is unchanged.

**Seam acceptance** (the product's instruction, via `seam_replay worker` on a
halted fixture):

| fixture | draws | chars | links | links tool-returned | negatives | timeout / marker |
|---|---|---|---|---|---|---|
| `wave2/6335 r1 t7` | 2 | 3,973 / 4,769 | 4 / 12 | **16 of 16** | all *"not retrieved because the limit was reached"* | none |
| `wave2_p27/6374 r2 t4 step 3` | 2 | 4,737 / 4,729 | 17 / 16 | **33 of 33** | same shape | none |

$0.25 for the four. Every negative sentence in the four draws names the limit
as the reason; none asserts absence.

### Replay acceptance (`wave3_p38`, head `1243cdd`, n=3 on 6374 and 6383)

| | `wave2` (n=1) | `wave2_p27` (n=3) | **`wave3_p38`** (n=3) |
|---|---|---|---|
| 6374 halted worker runs / rep | 0.0 | 0.7 | **0.3** (rep 1, turn 2, step 3) |
| 6374 halted runs written up | — | — (the design did not exist) | **1 of 1** |
| 6374 sources kept / rep | 45.0 | 35.7 | 42.0 |
| 6374 `sources_kept` fell, per turn slot | | | 1 of 4 vs `wave2`, 1 of 4 vs `wave2_p27` (floor 3 of 8) |
| 6383 halted worker runs / rep | 0.0 | (not in that sweep) | **0.0** — condition vacuous |
| 6383 sources kept / rep | 12.0 | | 14.0 (fell in 0 of 4 slots) |
| `halts` | | | 1 halted turn, **0 failing**; `wrote` 1/1 |

**The one live halt, read in full** (`6374_rep1.json`, turn 2, step 3 *Identify
specified non-ministerial offices*): 20 rounds, 27 tool calls (7 searches in 8
rounds, 10 section searches with no instrument above 3 rounds, 6 change
lookups, 1 text retrieval), so neither P2.7's nor P3.1's budget fired — the
retrieval-bound shape. `written_up: true`; the write-up is 5,490 chars with 10
provision links, **10 of 10 returned by that delegation's tools and 10 of 10
present in the answer**. The answer opens with P2.1's notice naming the step,
and its BLUF adds, unprompted: *"research into secondary legislation
specifying additional non-ministerial offices did not complete due to an
internal limit on tool-call rounds; therefore, the list of additional offices
provided below is partial"*. Every negative sentence in the write-up names the
limit as the reason (*"the specific contents of this Schedule were not retrieved
because a fixed limit on how much work one research step may do was reached"*).
No header text (`PARTIAL FINDINGS`, `REQUIRED:`) reached the answer. Compare
`wave2_p27/6374 r2 t4 step 3`: the same session's halted step contributed
nothing, and the report's coverage of it was the notice alone.

(`replay_report --dir wave3_p38 halts`; `discovery --before wave2 --only 6374`
and `--only 6383`; `discovery --before wave2_p27 --only 6374`.)

### Every exit-1 subcommand

`halts` 1 halted turn, 0 failing; `negatives` 18 turns asserting a negative,
**0 failing**; `derivations` **0 UNVERIFIED** (the first 6374 sweep without
P2.3's residual — not claimed as a fix); `blanks` invariant holds (1 call not
recovered, 6374 rep 1 turn 1, covered by P4.2's fallback); `scoperecord`
complete; `nosearch` 0/0; `caselaw` 0 TWO_LINES. On the before-column
(`wave3_p38_pre`) all seven exit 0 as well.

### Free observations

- **The `[Research Agent Result]` label reached two answers** (6335 rep 3,
  turns 3 and 5): 7 turns in 1,088 across every directory, 5 of them in
  `baseline`/`wave1`, then 0 in 930 until these. **P4.8.**
- One seam draw wrote "limit of 20 tool calls" where the limit is rounds — the
  model's paraphrase; the lawyer-facing notice says rounds and is code-emitted.
- **Two P4.2 events in six runs, both handled by the existing retry.** 6374
  rep 1 turn 1: three empty completions with `finish_reason=error`, answered
  by the report fallback (an unrecovered call, P4.5's eighth). 6383 rep 1
  turn 3: two completions of ~58K reasoning characters and no content,
  recovered on the third attempt — 768 s and $1.62 for a 1,429-char
  conversational answer. **P4.5's running count: 8 unrecovered provider
  calls in 329 answered turns (95% Wilson 1.2-4.7%)** over the 16 schema-v3
  directories.
- **No fail-open and no write-up failure in live traffic:** the server log
  carries one `Max turns` line, one `partial findings written up` line 21 s
  later, and no `Write-up at the step cap failed` or `no ReAct round` line
  across both sweeps.
- **The section budget fired 2 times in 3 reps of 6335** (reps 2 and 3, a
  fourth search of the Insolvency Act) and its footer clause reached the
  lawyer both times; in `wave3_p38` no run had an instrument above 3
  section rounds (0 of 53), so it never fired there.

### Spend

| | | |
|---|---|---|
| `wave3_p38_pre` (before-column, head `b7f9f96`) | 6335 x3 | $2.52 |
| seam draws (design prototype + seam acceptance) | 6 calls | $0.46 |
| **`wave3_p38`** (acceptance, head `1243cdd`) | 6374 x3, 6383 x3 | **$9.60** |
| **total** | | **$12.58** |

## B10 residual — one subsection cited without its siblings (P3.11)

6348's lawyer: the answer *"did not initially elaborate on the full provision,
only referring to s36(1) and not s36(2)"*. P3.1's prompt rule (*"When you cite
one subsection of a section, say in a line what that section's other
subsections provide"*) moved turn 1 from 0 of 3 to 1 of 3 (`wave3_p31`), and
the row was opened on the premise that a rule is obeyed at a rate, so the
lever is code: a subsection outline appended after each section retrieval.
The row's caveat, written at P3.1, was that *"summaries already keep subsection
numbers, so the outline's value is salience, not information"*.

**Outcome: built, measured at 2 of 3 against a 3-of-3 bar, not booked.** The
outline moves the number and is kept; the one miss is a run where the Worker
was shown s.36(2) twice and wrote s.36(1) alone. What to do with that is the
user's decision (see *The miss*, and the row).

### Where the sibling goes, measured before anything was built

`replay_report depth --seams` (built this session) grades the same requirement
at each seam the depth passes through — the summarised section-search text the
Worker was shown, with its appended blocks removed; the worker report; the
answer — and prints which subsections of s.36 the summaries mention at all.
Over every directory holding a 6348 run:

| turn 1 of 6348, per run | summaries mention s.36 | report | answer |
|---|---|---|---|
| `baseline` (pre-pilot code) | {1, 2} | coarse | coarse |
| `wave1` | {1} | coarse | coarse |
| `wave2` | {1} | coarse | coarse |
| `wave3_p31_pre` reps 1–3 | {1} {1} {1} | coarse ×3 | coarse ×3 |
| `wave3_p31_smoke` | {1} | coarse | coarse |
| `wave3_p31_smoke2` (= `wave3_p31` rep 1, seeded) | {1} | deep | deep |
| `wave3_p31` reps 1–3 | {1} {1} {1} | deep coarse coarse | deep coarse coarse |

**The summariser keeps s.36(2) in 1 of the 11 turn-1 summaries.** The section
search returns s.36 with both subsections in every one of them (P3.1 measured
that). So the row's caveat is true of the subsections a summary mentions and
false of the one it drops: a Worker that was never shown s.36(2) cannot say
what it provides, and the one `wave3_p31` run that did wrote it from a summary
that listed s.36(1) alone — right, but from memory. This is P1.6's situation —
the summariser cannot discard what it never saw — so the outline is
information restored after summarisation, from the RAW result.

(`python -m tools.replay_report --dir <d> depth --seams`, for each of the seven
directories; the `s.36 subsections in the summaries` column. The readout learnt
four ways a summary writes a subsection — `36(1)`, a bare `(1)` under a
`Section 36` heading, a numbered `1.` list, and a bulleted bold heading — three
of them from this row's own runs; the 1-of-11 was checked both ways.)

### The fix, prototyped on the seam

`seam_replay` replays each tool's recorded `final_result`, so a block built in
`run_worker_tool` from the raw result is in a fixture only if it existed when
the run was recorded — the seam could not prototype this row. `--from-raw`
(built first) rebuilds each summarised result's appended blocks from its
recorded `raw_result` through `agent_shared.summarised_result_blocks`, the
product's own builder, and leaves the recorded summary and per-tool notes
alone. The recorded payload is the before-column; `--from-raw` the after.

| fixture, turn 1 | as recorded | `--from-raw` |
|---|---|---|
| `wave3_p31_pre/6348 r1` | SHALLOW, 4 of 4 draws (Session 17; 0 of 3 at depth) | **DELIVERED** (2 of 4 at depth) |
| `wave3_p31/6348 r2` | SHALLOW (1 of 4 at depth) | **DELIVERED** (1 of 4 at depth) |

$0.23 for five draws. **The pinned configuration runs at temperature 0, and
the two `--from-raw` draws on each fixture are byte-identical**, so a payload
gives one sample here: two fixtures, two samples. Every legislation link in
the draws was tool-returned; the block was never echoed. Payload growth:
27.2K → 33.4K chars with one outline, 38.5K → 50.8K with two.

The draw's own sentence: *"(Note: The other subsection, section 36(2),
provides a separate exemption for information obtained from another person
where its disclosure would constitute an actionable breach of confidence)"* —
and the same note for s.29 and s.50, whose subsections the outline listed.

### The block, and what it costs

One line per numbered subsection of each provision with two or more, opening
words with paragraphs folded in, labelled from the URL segment (`s.36`,
`reg. 4`, `art. 2`) and never from the word the text uses (LEX renders a
regulation's text as `Section 4)`, and a label copied from it would make a
wrong pinpoint). No URLs (P1.6's block has them). Left out: Schedules (one
item whose `Section k)` lines are paragraphs — P3.12), provisions with fewer
than two subsections, rows without a provision URL, and the unsummarised path.
Bounded: 300 chars a subsection, 12 subsections a provision, 6,000 chars the
block, provisions in the retrieval's rank order.

Over the graded runs the cap is what bounds it: `wave3_p31_pre`, 36 section
searches, outline median 6,097 chars, p90 6,367, non-empty for 33 of 33
summarised searches; `wave3_p311`, 7 searches, median 6,248 (`depth --seams`,
last line). A summarised section search on an Act with long sections therefore
hands the Worker roughly as much outline as summary. Charged to the context
budget like every other append; nothing measured here says it is too high.

### The acceptance run (`wave3_p311`, head `84b8da5`, n=3, $1.40): 2 of 3

| 6348 | `wave3_p31_pre` (HEAD before P3.1) | `wave3_p31` (P3.1) | **`wave3_p311`** |
|---|---|---|---|
| turn 1 delivers s.36(2) with its substance | 0/3 | 1/3 | **2/3** |
| turn 1 references at depth, per rep | 0, 0, 0 | — | 2 of 5, 1 of 4, 0 of 3 |
| turn 1 summaries mention s.36(2) | 0/3 | 0/3 | 1/3 (rep 3) |
| by turn 2 | 2/3 | 3/3 | 2/3 |

In reps 1 and 2 the summary lists s.36(1) alone, the outline lists both, and
the report and answer carry s.36(2) with its substance — the outline did the
work. Every legislation link in the twelve answers was tool-returned (47 of
47); no block or label leaked into any answer; every exit-1 subcommand exits 0
(`halts` 0, `negatives` 5 turns asserting a negative and 0 failing,
`derivations` 0 UNVERIFIED, `blanks` holds, `scoperecord` 0 leaked,
`nosearch` 0, `caselaw` 0). Reps cost $0.49, $0.53, $0.38 and took 248, 256
and 175 s.

### The miss

**Rep 3, turn 1: the Worker was shown s.36(2) twice and wrote s.36(1) alone.**
Its summary of the FOISA section search kept both subsections (the only
`wave3_p311` summary that did) and the outline listed both beneath it; the
report (6,942 chars, two Acts — that rep also section-searched the Data
Protection Act 2018, an 81K-char raw result, summarised) cites *"Section 36(1)
(Confidentiality)"* and nothing of (2), and the Manager passed it through. So
the residual after this row is not information: it is the Worker not obeying
P3.1's rule with the sibling in front of it. **The same recorded payload,
replayed on the seam as one tool-free composition round, DELIVERED** (3 of 6
references at depth, $0.08): the loss is in how the live ReAct loop's final
write-up round reads its context, not in what the context holds.

Rep 3's turn 2 is a different thing and not this row's: the Manager answered
the lawyer's follow-up (*what is the test for exemption*) with a clarifying
question and no delegation (685 chars, 0 sources), which the grader marks
MISSED; when the lawyer named s.36(2) at turn 3 the run delivered it in full.
That is why `by turn 2` reads 2 of 3 and why `sources_kept` fell in the t2 slot.

**What would close it, not built (a user decision).** Invariant 2's next step
is a code-emitted sibling line at the report seam: where the report pinpoints
s.N(k), the run's outline holds other subsections of s.N, and the report
mentions none of them, append their opening words under the citation — the
P2.1/P2.5 pattern, code writing the disclosure, verbatim statute so Invariant 1
is safe. Design questions for the user first: placement (under the citation or
after the References), how many notes a report may gain (every pinpointed
section with siblings the Worker did not mention — rep 1's draw wrote three
such notes itself), and whether that is clutter. One more acceptance costs
about $1.40 plus seam draws. The alternative is P3.1's precedent: book DONE
with the residual as a new row.

### Invariant 1

- `discovery --before wave3_p31 --only 6348`: `sources_kept` per rep 5.0 →
  4.3; fell in **2 of 4** turn slots (t1 2.0 → 1.7, t2 1.0 → 0.7; noise floor 3
  of 8). Against `wave3_p31_pre`: 4.3 → 4.3, fell in 1 of 4 (t2). The t2 fall
  is rep 3's clarification turn (no delegation, 0 sources) both times.
- `depth --before wave3_p31`: prose fell in 2 of 4 slots, **links in 4 of 4**
  (5.3 → 4.0, 5.3 → 3.0, 6.0 → 5.0, 5.3 → 3.7); against `wave3_p31_pre` prose
  1 of 4, links 4 of 4. Per rep, rep 1 carried 3, 2, 3, 2 links across its four
  turns with four sibling notes in prose at turn 1, where the P3.1 reps carried
  3–8 a turn. **Watch item:** a Worker holding the outline may write a
  subsection's siblings as prose notes in place of further links. n=3 and one
  rep; not a finding.
- Sibling notes (*"(Note: … other subsection …"*) in the answers: 0 in
  `wave3_p31_pre` turn 1, 0 in `wave3_p31`, 4 / 0 / 0 in `wave3_p311`.

### The wrong-pinpoint watch item (P3.1), 6365 smoke, n=1, optional

6365 n=1, $0.92, 7.4 min, one Deep Research turn (run file stamped `7310030`; `git diff 84b8da5 HEAD -- server_py/src` is empty, so the product is the acceptance head's). **DELIVERED**, at the highest depth ratios recorded for the session: references at depth s.45 **7 of 7**, s.57 **19 of 19**, s.21 10 of 11, s.22 11 of 11 (60–95% per anchor at `wave3_p31`, 0–17% at HEAD before P3.1). The four timeline claims Session 16 read against the live text, read by hand here: interim report period → **s.57(3)** (right; `wave3_p31` rep 2 had s.57(1)), 6 months → **s.21(2)**, 9 months → **s.22(5)**, true and fair view → **s.45(1)** — all four correct. 47 pinpoints in the answer, 21 of them in sentences carrying a timeline term; the 17 outside the four watched claims read as plausible and were NOT verified against the text. s.57(1) appears in two step reports and reaches no timeline claim. **n=1 and optional, stated as such: the rate did not rise in this sample** (3 wrong of 34 at `wave3_p31`; 0 of 4 watched claims here). Sibling notes in the answer: the synthesis wrote none — the outline reaches step Workers, and the synthesis has the pinpoint block (P3.1), not the outline.

### Spend

| | | |
|---|---|---|
| seam draws (`--from-raw` A/B on two fixtures, and rep 3's payload) | 6 calls | $0.31 |
| **`wave3_p311`** (acceptance, head `84b8da5`) | 6348 ×3 | **$1.40** |
| `wave3_p311` 6365 smoke (head `84b8da5` for `src/`; file stamped `7310030`, tooling only) | 6365 ×1 | $0.92 |
| **total** | | **$2.63** |

## The chat-mode default (P0.5, found 2026-09-22)

Twelve of the 41 replayed sessions were replayed in Research mode in every
sweep from `baseline` on, because the export's `Session mode` is blank for the
sessions run on 11–13 August (before the field existed), the feedback snapshot
is blank for them too, and `replay_set.py` filled the gap with
`DEFAULT_CHAT_MODE = "research"`. The lawyers ran them in Conversational mode
with the Research flag off. The recorded answers show which Worker wrote them:
the research Worker's report headings (Summary Answer, Detailed Analysis,
Jurisdiction & Status, Statutory Framework, a References heading) pass through
the Manager in Research mode and never appear in a conversational answer.

| Answers | With the research-report headings |
|---|---|
| pre-pilot, the 15 blank-mode sessions | **0 of 38** |
| pre-pilot, the 24 sessions recorded as Conversational | 0 of 64 |
| replay in Research mode (`chat_mode_source: default`), `baseline` | 39 of 48 |
| replay in Research mode, `wave2` | 42 of 48 |
| replay in Conversational mode (`snapshot`), `wave2` | 0 of 87 |
| 6348, pre-pilot, 4 answers | 0 (about 700 chars each) |
| 6348, every replay directory, 4 answers each | 4 of 4 (3,500+ chars each) |

The twelve in scope: 6333, 6334, 6335, 6338, 6340, 6343, 6345, 6346, 6348,
6350 (blank mode), and the non-Deep-Research turns of 6341 and 6347. Which rows
that touches, and what to do, is on P0.5. ~~These counts were a scratch regex
over the export and the run files (recorded on the row); P0.5's first step puts
them behind `replay_report modes`.~~

**Done, Session 20 (2026-09-22). `python -m tools.replay_report modes --dir <D>`
prints both halves of the table above**, and every figure in it was re-measured
with the corrected marker over every directory. Two corrections to the table as
first published, neither of which moves a zero:

* **The 24 conversational-recorded sessions are 0 of 63, not 0 of 64.** One of
  those turns is a blank reply with no text to read (B13/P4.2), so it carries no
  shape. The 0 is unaffected; the denominator was.
* **State the 0 over the non-Deep-Research answers.** The report headings appear
  in **0 of the 152** non-DR pre-pilot answers and in **27 of 27** Deep Research
  ones — `DEEP_RESEARCH_SYNTHESIS_PROMPT` asks for a report structure too. So
  `dr_marker`'s precedence over the report marker is load-bearing, not
  decoration, and "0 research-shaped answers" is a statement about the turns the
  report marker is actually asked to decide.

**The marker was also wrong once, in prose.** The published regex matched its
phrases anywhere in the text, and `Statutory Framework` fired on a Deep Research
planner asking *"would you like to search for the statutory framework discussed
in this case"*. It is now anchored to a heading — and the heading markup is not
one fixed form: the Worker emits at least five (`### 1. Summary Answer (BLUF)`
253 times, `2. **Detailed Analysis:**` 76, `**References:**` 35,
`### Jurisdiction & Status` 18, `### **1. Summary Answer (BLUF)**`), so the
regex requires markup and then consumes a run of it rather than enumerating
them. Both forms were run over all 181 assistant messages in the export and all
1,175 turns in the 29 replay directories: **one disagreement, that one planner
question.** Every count below therefore stands.

### The Conversational-mode replay (`wave0_conv`, P0.5 step 2)

`wave0_conv` is the missing before-column: the twelve sessions replayed in the
mode their lawyers used. Head `223293e`, n=1, 50 turns (48 conversational, 2
Deep Research), **$3.84** against a $6 estimate.

| directory | mode the twelve ran in | research-shaped answers |
|---|---|---|
| `baseline` | Research (a default) | 39 of 48 |
| `wave1` | Research (a default) | 41 of 48 |
| `wave2` | Research (a default) | 42 of 48 |
| `wave0_conv` | **Conversational (evidence)** | **0 of 48** |

Every turn's mode now has a source that is evidence: `conversational_marker`
40, `neighbour` 8 (unanswered turns, taking the nearest answered non-DR turn of
their own session), `dr_marker` 2. `modes` exits 0; every other exit-1
subcommand exits 0 except `caselaw`, which is the pre-P2.4 before-column shape
by design.

**What changed when the mode was right.** Three measurements, each recorded on
its own row:

| | Research mode (wrong) | Conversational (right) |
|---|---|---|
| halted worker runs, 6335 + 6338 + 6340 | 3 of 14 (`baseline`), 1 of 11 (`wave2`) | **0 of 7** |
| 6346 turns deflecting ("switch mode") | 0 of 5 | **5 of 5** |
| delegations with zero tool calls (`nosearch` B) | 7 FAILs, all 6346/6347 (`wave2`) | **0** |
| P4.6's scripted negative, over the twelve | 20 of 50 (`wave2`) | **0 of 50** |
| 6348 turn 1 delivers s.36(2) with substance | 2 of 3 (`wave3_p311`) | **1 of 3** (0 of 3 at `2d9ae11`) |

The middle two rows are the same finding seen twice: **B5's false negative and
B7's deflection are one defect in two modes**, and only the second reached a
lawyer. `negatives` exits 0 on `wave0_conv`, where every full sweep has exited 1
on 6346/6347.

## B7 — the research-mode dead-end, scripted (P4.1, 2026-09-22)

No stored session could show bug (a): the harness sent one research type per
session, so a replayed "I have changed the mode, please proceed" always ran
under the type it started with, and the refusal it drew was correct about the
tool set. P4.1's step 1 made the type per turn and added `replay run --script`,
which builds a sequence from an exported session's turns by index (no question
text in the repo). Two sequences: 6346 — its turn 1 under 'Legislation only',
then its own turn 3 and turn 1 again under 'Legislation & case law' — and 6343
(turn 1, then turn 4 under the new type). Run in Conversational mode on both
sessions and, for 6346, in Deep Research, the mode its lawyer actually used
(all three of her answers are planner clarifications: blank `Message model`,
the planner's signature — see *The chat-mode default* below).

`python -m tools.replay_report --dir <D> deadend --all-reps --before <D>`,
n=3, pinned model, `research_mode_enabled` pinned OFF as on the target:

| | `wave4_p41_pre` (`0a5d813`, pre-fix) | `wave4_p41` (`9aa6d63` / `73ce944`) |
|---|---|---|
| turns from a research-type change onward, Conversational | 9 | 9 |
| …of which answered from case law with no reference to the old scope | **8** | **9** |
| …the exception | 6346 rep 2: P4.5 episode (3 empty completions, 456 s), fallback carrying the Worker's "switch to Research mode" | — |
| mode-change markers the product injected | 0 (it could not see the change) | **6 of 6** |
| turn-1 deflections naming a control the UI does not have | **6 of 6** | **0 of 6** |
| turns from a change onward, Deep Research (6346) | 3 | 3 |
| …answered with a report on the case | 3 | 3 |
| markers recorded | 0 | 3 of 3 (planner JSON) |
| links / `sources_kept` over the 9 post-change conversational turns | 7 / 12 | 8 / 17 |
| spend | $2.68 | $2.54 (+ $0.98 `wave4_p41_dr_v1`, the first DR run, same product) |

**The finding that matters is in the left column: the pre-fix product did not
anchor.** With the type really changed, 11 of 12 post-change turns were
answered from case law before any fix, the refusal still in the history and no
marker present. The row's diagnosis of 6346 — the model anchoring on its own
refusal over a system prompt that already carried the new type — was an
inference, and the replay contradicts it. What the transcript's own words
record is bug (b): the planner called the research type a "mode", the lawyer
said she would "change the research mode", and her turn 4 says "It is in deep
research mode" — the chat-mode control, which does not add case law. The
marker is kept as defence in depth and is verified to fire; the wording fix is
what the session needed.

**The wording metric, same four sessions, Conversational, rep 1, 18 answered
turns each side** (`deadend --dir wave4_p41_conv --session 6343 6346 6347 6350
--before wave0_conv`):

| | `wave2` (Research, wrong mode) | `wave0_conv` (`223293e`) | `wave4_p41_conv` (`9aa6d63`) |
|---|---|---|---|
| turns telling the lawyer to switch or restart | 5 | 14 | **0** |
| turns naming a control the UI does not have | 5 | 15 | **0** |
| turns describing the interface | 2 | 2 | **0** |
| `negatives` exit | 1 | 0 | 0 |

`wave4_p41_conv` cost $0.57 and every exit-1 subcommand exits 0 on it. Note it
still replays 6346 in Conversational mode (the run started before the planner
marker landed); the corrected replay set sends 6346 as Deep Research, where the
scripted DR sequence above is the after-column.

## The conversational Manager seam (P3.13, 2026-09-23)

After P3.11 the quick-lookup Worker states s.36(2) on 6348 turn 1 in 3 of 3
reports, and the conversational Manager deleted it from 2 of those 3 answers
(`wave3_p311_conv`). P3.13 is scoped to that Manager seam alone (Session 20's
tally: 3 of the 21 conversational losses; the Deep Research share belongs to
P4.7 and P3.10).

**Outcome: built, measured at 1 of 3 against a 3-of-3 bar, not ticked.** The
fix is kept and costs no links. The Manager still flattens the sibling at a
rate. What to do next is on the row.

### What the Manager was dropping, measured over every run file first

In each flattened answer, the sibling was the one provision in the report
written without a link: both subsections share the section URL, so the Worker
links s.36(1) and writes s.36(2) in plain words. The Manager's CITATION
PRESERVATION rule protects each provision "with its link".
`python -m tools.replay_report --dir <any> siblings --all-dirs --exclude wave3_p313`:

| 36 directories, 1,060 non-Deep-Research delegations | sibling handed as a link | as plain text |
|---|---|---|
| conversational Manager | **58 of 60 kept** | **70 of 104 kept** |
| research Manager | 94 of 94 | 347 of 347 |

A sibling is a subsection the report cites while the answer keeps another
subsection of the same section. The measure uses section numbers only and is
not instrument-aware, so it is a rate, not a list of defects. `--list` prints
the 34 plain-text drops; they span 6333, 6348, 6359, 6374, 6375, 6409 and
6410, so the shape is not 6348's alone.

### The fix

* **Code:** `citation_links.link_sibling_pinpoints`, applied by
  `agent_core.worker_result_for_manager` to the report the conversational
  Manager is handed. It links an unlinked `s.N(k)` to the `…/section/N` URL
  the same paragraph already carries, and never builds a URL. It requires the
  pinpoint's nearest instrument reference to be that URL's instrument. A plain
  title counts as unknown, unless it directly follows the link it restates.
  **Dry-run over the corpus:** 102 links added to 63 of 777 conversational
  reports. The first draft's 188 distinct edits (research reports included)
  were read in context, and one was wrong: a list of Use Classes Orders where
  the 1963 Order's s.2(2) took the 1950 Order's s.2 URL. It is what the
  instrument rule is for, and a test pins it.
* **Prompt:** one clause in the existing CITATION PRESERVATION bullet of
  `_MANAGER_CONV_BODY`: *"and where the Worker says what a cited section's
  other subsections provide, keep that line too"*. It is a clause and not a
  block, because of P2.4's bullet and case-law-link cost.

### The seam, and what it got wrong

`seam_replay manager` rebuilds the Manager's composition from a run file:
the history, each delegation as the `delegate_research` call and the result
`worker_result_for_manager` returns, then one call. The pinned configuration
runs at temperature 0, so the table counts payloads. Five 6348 turn-1
payloads: the three recorded Manager losses and the two recorded carries.

| variant | tool-free: losses recovered | controls held | links | with tools: losses recovered | controls held | links |
|---|---|---|---|---|---|---|
| before (HEAD `57cfae6`) | 0 of 3 | 2 of 2 | 12 | 0 of 3 | 1 of 2 | 11 |
| link only | 1 of 3 | 2 of 2 | 13 | — | — | — |
| clause only | 2 of 3 | 2 of 2 | 11 | — | — | — |
| **link + clause** | **3 of 3** | 2 of 2 | 15 | **1 of 3** | 2 of 2 | 13 |

Six other sessions' payloads where the conversational Manager dropped a
sibling (6374, 6409, 6375, 6410, 6333, 6359):

| | tool-free before → after | with tools before → after |
|---|---|---|
| sibling kept | 2 → 4 of 6 | 1 → 4 of 6 |
| legislation links | 10 → 14 | 11 → 14 |
| case-law links | 3 → 3 | 3 → 3 |

**The tool-free column was the wrong approximation, and the replay found it.**
The tool-free seam said 3 of 3 on 6348. Rep 1 of the acceptance then
flattened s.36(2). That exact payload DELIVERED in 3 of 3 tool-free draws, and
reproduced the miss in 3 of 3 once the Manager was offered its tools, as the
live call is. The seam now offers them by default. Neither form is exact:
over the six recorded 6348 turn-1 payloads, each matched the live outcome in
5. Temperature 0 is not byte-deterministic on this model either (two draws of
one payload: 1,466 and 1,488 chars).

### The acceptance run (`wave3_p313`, head `778d30a`, n=3, $5.65): 1 of 3

| 6348 turn 1 | summary | report | answer | where lost |
|---|---|---|---|---|
| rep 1 | {1, 2} | deep | coarse | **Manager**: the linker fired (s.36(2), s.45A(2)); the answer is a two-Act bullet list keeping s.36(1) and s.45A(1)(a) |
| rep 2 | {1} | coarse | coarse | upstream: a P4.5 episode; the re-delegated report cites s.36(1) alone, in bold, with nothing to link |
| rep 3 | {1, 2} | deep | deep | carried |

`depth --seams`: carried 2, manager 2, worker 0, summariser 2, identical to
`wave3_p311_conv`. Delivered by turn 2: 1 of 3.

**Invariant 1, against `wave3_p311_conv`:**

* `depth --before`: links fell in 1 of 4 slots (t1 2.0 → 4.0, t2 1.7 → 2.7,
  t3 2.0 → 2.3, t4 1.3 → 0.3); prose fell in 1 of 4.
* `discovery --before`: `sources_kept` 4.0 → 5.0 per rep, and fell in 1 of 4
  slots (t2).

**The exit-1 set:** all 0 except `modes` 1, from rep 2's t1, t3 and t4. Rep 2's
first worker lost its final completion three times, each attempt about 62,912
completion tokens with no content. The Manager was therefore handed a report
with no body, only the search-scope block, which tells the research Worker
what to write "in the Jurisdiction & Status section". It wrote a
`**Jurisdiction & Status**` heading, and the next two turns repeated it. That
heading appeared in 0 of 116 earlier conversational answers. The same
payload on the seam wrote no heading in 4 of 4 draws, with and without the
fix. It is booked on P4.5.

### Spend

| | |
|---|---|
| `wave3_p313` (acceptance, 3 reps; $4.89 of it two P4.5 turns) | $5.65 |
| seam draws, 64 over the session (tool-free and with tools; not every draw's cost was captured, and the printed ones range $0.007–$0.030) | about $1 |

### Option (i): the answer seam (user decision, 2026-09-23). ACCEPTED, 3 of 3

**The code:** `citation_links.restore_dropped_siblings`, run in
`process_user_request` for the conversational Manager on the reports exactly
as it was handed them. It fires where the answer cites s.N(j) and a report
linked s.N(k) that the answer names nowhere. The report's own clause about
s.N(k) then goes after the answer paragraph that cites the section, as "Also
in s.N: …". The words are verbatim Worker text, never generated, with at most
3 notes. Nothing is added when:

* the answer doesn't cite the section at subsection level;
* the clause restates a subsection the answer already has;
* an answer sentence already says it (content-word overlap of 60% or more);
* the clause can't be cut cleanly (unbalanced brackets or quotes; never cut
  at ", and").

A plain-text "section 36(1)" counts as a citation only when every section link
in the reports is to one instrument.

**Dry-run over every recorded conversational answer, read in full:** 15 notes
on 14 of 623 turns (37 directories, before this option's own sweeps). The
first draft's 29 notes included three kinds of fault, and each became a guard:

* broken list cuts (6374: "(the First Minister, Ministers, the Lord
  Advocate.");
* restatements (6348's s.2 notes repeating the answer's own s.2(2)(c)
  sentence);
* near-duplicates (6409's s.27(2) repeating an answer sentence).

**The prompt clause came out again.** Its only reach before any tool result
is the Manager's first delegation brief, so that is where it was measured:

| 6348 turn 1, the Manager's first brief | briefs | the verbatim brief\* | not naming FOI |
|---|---|---|---|
| stored runs before the clause (`wave0_conv`, `wave0_conv_6348`, `_pre`, `wave3_p311_conv`) | 10 | 0 | 2 |
| with the clause (`wave3_p313`, `wave3_p313b`) | 6 | **3** | 3 |
| after it was removed (`wave3_p313c`) | 3 | 0 | 0 |
| seam probe, first round only, with / without the clause | 4 / 4 | 0 / 0 | **2 / 0** |

\* "What is the statutory provision which covers the legal advice privilege
exemption for a disclosure request in Scotland?" In `wave3_p313b` rep 1 it
led the Worker to the Economic Crime and Corporate Transparency Act 2023
(ss.188–190 use "disclosure request" literally), and FOISA was never searched.
That is the only answer without FOISA among the 33 stored 6348 turn-1 runs.

**Seam, tools offered, six 6348 payloads:**

| | delivered | restore fired |
|---|---|---|
| link + clause + restore | 6 of 6 | 3 payloads, 4 notes |
| link + restore, no clause (as shipped) | 6 of 6 | 4 payloads, 5 notes (one on a draw where the Manager dropped every link and cited in words) |

On the six wider payloads (with the clause), the restore fired 0 times.

| directory | head | 6348 t1 delivered | Manager losses | exit-1 set | spend |
|---|---|---|---|---|---|
| `wave3_p313` | `778d30a` (link + clause) | 1 of 3 | 2 | `modes` 1 (P4.5) | $5.65 |
| `wave3_p313b` | `66598f3` (+ restore) | 2 of 3 (miss: ECCTA route) | 0 | all 0 | $1.17 |
| **`wave3_p313c`** | **`ebd3efa`** (link + restore, no clause) | **3 of 3** | **0** | **all 0** | **$1.01** |

In `wave3_p313c` the Manager dropped s.36(2) from all 3 turn-1 answers and
the restore put it back in all 3 (5 notes, s.45A(2) twice beside s.36(2)). The
row's number is therefore the code's, not the Manager's.

**Invariant 1, `wave3_p313c` against `wave3_p311_conv`** (`depth --before`,
`discovery --before`):

* links fell in 1 of 4 slots: t1 2.0 → 5.0, t2 1.7 → 3.7, t3 2.0 → 2.0,
  t4 1.3 → 0.0;
* `sources_kept` fell in 0 of 4, 4.0 → 5.0 per rep;
* prose shrank in 2 of 4.

T4's zero links are three honest "the Act does not define it; that is common
law" answers citing no provision, and the restore only adds text, so it can't
cause a lost link. `wave3_p313b`: links fell in 0 of 4, `sources_kept` 0 of 4.
**Watch:** turn 1 prose roughly doubles (724 → 1,362 chars mean).

**Spend for option (i):** $1.17 + $1.01 for the two sweeps, plus about 25 seam
and probe draws at $0.007–0.04 each.

**Behind a command (added at the handover):** the linker's 102 links on 63 of
777 reports is
`replay_report --dir <any> siblings --all-dirs --exclude wave3_p313 wave3_p313b wave3_p313c --dry-run`.
The restore's 15 notes on 14 of 623 turns is the same with
`--exclude wave3_p313b wave3_p313c`; add `--show` to print every note.

## The research-type default (P0.6, 2026-09-23)

`Filter: Research mode` is blank in the export for the twelve P0.5 sessions,
and for 50 of their turns the harness sent `legislation_only`, labelled
`default`. A human read of the transcripts, committed as
`evidence/research_mode_reads.json`, says that was wrong on **16** of those
turns. On each of them the lawyer had case law in the tool set, and the
replay did not.

| read (50 turns) | turns | sessions and turns |
|---|---|---|
| `legislation_only` | 26 | 6333, 6334, 6335 t1–4, 6343, 6345, 6346, 6347 t1, 6350 t1–2 |
| `legislation_and_case_law` | 10 | 6335 t7, 6338 t1–3, 6340 t1, 6341 t1–5 |
| `case_law_included` (legislation half not settled) | 6 | 6335 t6, 6347 t2–4, 6350 t3–4 |
| `unknown` | 8 | 6335 t5, 6341 t6–8, 6348 t1–4 |

**Why a read is possible at all.** At the pre-pilot the research type was one
saved preference per user (`users.research_mode`, default `legislation_only`,
set through the Research filters modal). It carried across chats and logins,
so a change is an event, and a turn between two equal reads of the same lawyer
is bracketed. Each type also left behaviour in the answers. The legislation-only
Manager declined every case-law question in these sessions. The hybrid Manager
briefed its Worker to ALSO search case law, so its answers report case-law
results nobody asked for, in the case-law tool's own coverage wording. A 2026
judgment can only have come from the tool. A neutral citation alone is not
evidence, because a refusal quotes the case the lawyer named.

**What the default did to the sweeps.**
`python -m tools.replay_report --dir <D> modes` now grades every turn against
the read:

| directories | holding a turn sent without the case-law tool its lawyer had | turn-runs | rep 1 |
|---|---|---|---|
| 39 | 14 | 153 | 16 each in `baseline`, `wave1`, `wave2`, `wave0_conv` |

The scripted P4.1 directories (`wave4_p41`, `wave4_p41_pre`,
`wave4_p41_dr_v1`) are unaffected. The one row whose evidence moves is
**P4.6**. Its acceptance sessions 6340 and 6341 t1–5 ran hybrid, and
`WORKER_SYSTEM_PROMPT_HYBRID` carries none of its three scripted lines.

**What sweeps send from now on.** The reviewer's read, labelled `reviewer`. A
`case_law_included` read goes out as `legislation_and_case_law`, labelled
`reviewer_partial`. A turn nothing settles is labelled `unknown` and sends the
nearest read in its own session, or `legislation_only` in a session with none,
so 6348 is unchanged. `modes` names the unknown turns and exits 1 only on a
`default` label or a type the read rules out.

**What would replace the read:** the target's `request_timings.research_mode`
holds the resolved value of every pre-pilot chat request. It can be joined to
the export on `created_at` and `total_cost_usd` (P0.7, needs the target).
