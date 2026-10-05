# Parallel batch 7, agent B: P3.27 measured, and the LEX probe P3.12 needs ($0; 156 live LEX calls)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 6011b4fe0ba669cd68e225ac349c35f70f5fc724` (the integrator's
head). This note is based on `6011b4f`.

**What this is.** A measurement of P3.27 over the stored evidence, then a bounded live probe of
LEX for P3.27 and P3.12, with P3.12's ground truth read live. **No product, tool or test code**;
the only commit is this note. Model spend **$0**: no model call, no server, no replay.

**Live calls (the user agreed at launch: up to 300, at least 0.5 s apart, every call logged).**
**156 calls**, 148 status 200 and 8 status 404 (the 8 ids whose stored reads had already failed),
0 transport errors, 24.1 MB received, minimum gap between one call's end and the next call's start
0.600 s. One deviation from the brief's wording: LEX's read endpoints are **POST** (`/openapi.json`
lists `/legislation/text`, `/section/lookup` and `/section/search` as POST); only
`/legislation/proxy` is a GET. All 156 are reads. By endpoint: `/legislation/text` 128,
`/legislation/section/lookup` 16, `/legislation/section/search` 8, `GET /legislation/proxy` 4. No
other host was called. The cap, the pacing and the log are enforced in one module
(`lexcall.py`) that reads its own log back before every call.

**Model.** Every stored run file used here ran on the pinned `google/gemini-3.1-pro-preview`; no
number below comes from `glm-5.2:cloud`.

**Scratch.** Scripts, outputs, the call log (`probe_log.jsonl`), every live response (`raw/`), the
hand-reads and the ground truth are in the gitignored `docs/prepilot-fixes/evidence/seam/batch7/B/`
(`git check-ignore -v` gives `.gitignore:113`), copied to the main checkout's same path. Commands
below run from that folder with `PYTHONIOENCODING=utf-8`; `E=C:/Projects/LexChat/docs/prepilot-fixes/evidence/replay`.
Instruments are named here by the row that names them (P3.12's Act, P3.2's regulation, 6374's
Order), never by id.

---

## 1. P3.27 over the stored evidence ($0)

### 1.1 The reads

`python p327_inventory.py $E --dump calls.json`, then `python p327_measure.py $E --probe probe_summary.json --list --handread handread_raw.txt`.

- **580** stored `get_legislation_text` calls: 531 returned a text, 49 failed. **60** distinct
  instruments returned a text (8 more only ever failed).
- By mode (calls): conversational 247, Deep Research 286, research 47. The conversational count
  matches P3.25's census (247 calls in 143 turns).
- Unit of analysis: a (turn, instrument) pair with a successful read: **419 pairs in 195 turns**
  (conversational 191, Deep Research 184, research 44).

### 1.2 Which reads were of an instrument with a schedule or annex

Two tests. **Known** is batch 6 D's: a stored section search returned a `/schedule/` or `/annex/`
provision of the instrument. **Live** is new: the live text with `include_schedules=true` is longer
than without it (section 2.1).

| Test | Instruments | Pairs | Turns | By mode (pairs) |
|---|---|---|---|---|
| known (D's) | 18 | 91 | 88 | conv 46, DR 31, research 14 |
| **live** | **27** | **126** | **98** | conv 49, DR 35, research 42 |

So **98 of the 195 turns that read a whole text read one whose schedules or annexes were left out.**
D's corpus-only test found 18 of the 27; the other 9 have schedules no stored section search ever
returned.

### 1.3 Which of those turns needed a provision in a schedule or annex

A turn **needed** one when a section-search query on the same instrument in the same turn (D's
`sched_label`, any class) or the brief of the delegation that read the text names a schedule or
annex of it. A query or brief that names only a paragraph or a chapter, with no schedule or annex,
is counted apart: there were **0** such pairs.

- **25 pairs** on a live-schedule instrument (23 by query, 22 by brief), in **23 turns** of **3
  sessions** (6335, 6389, 6406).
- One pair is a detector false positive, found by hand: the brief named the annex of a different
  regulation from the one read. It is excluded below.
- By mode (turns): conversational 16, research 5, Deep Research 2.
- The named unit came back from a section search in the same turn in **2** of the 23.

A first draft of the brief detector matched the plural "Schedules" as "Schedule S" (2 false need
pairs); fixed by making the label case-sensitive. Its drop list was then read: no pair it missed
names a schedule or annex.

### 1.4 What the answer said about that provision (hand-read, every turn)

`python p327_tally.py` holds the verdicts (keys only). I assigned them by reading each need turn's
brief, queries, report and answer (`handread_need_dump.txt`, gitignored). For each verdict I checked
live whether LEX holds the unit.

| What the answer said about the named unit | Turns |
|---|---|
| "not held in this index" (**false**: LEX holds it, as one provision, and the flagged text carries it) | **7** |
| "could not be retrieved from the index / the tool is unable to retrieve it" (reads as unavailable; LEX holds it) | **5** |
| "not retrieved because searching was cut short by a limit" (true of the run) | 2 |
| reasoned on the lawyer's premise about the unread content, with no negative | 3 |
| stated the content of a schedule or annex the turn never retrieved | 2 |
| the named unit not addressed at all | 1 |
| no delivery: a clarifying question (1) or the step-cap halt notice (1) | 2 |
| **delivered**, because a section search returned the annex | 1 |

- **14 of the 23 answers carry a negative about the named unit, and LEX holds the unit in all 14.**
  **0 of the 23 got it from a whole-text read.**
- **The two "stated unread content" turns:**
  - In one, a Deep Research summary of a sections-only text carries a schedule's classification
    words, although the raw text it summarised has none of them. That is the summariser writing
    from training (P3.16's class), and the omitted schedule is what made room for it.
  - In the other, the report adopted the lawyer's premise as fact. The live text happens to agree
    with it.
- **The report was accurate where the answer was not.** On two of P3.2's turns the Worker report
  said, correctly, that the retrieved text "does not contain the Annexes". The answer then said the
  tool was "unable to retrieve" the annex, or reasoned on the premise. A code line in the result
  alone may not stop that paraphrase (see decision 1).

### 1.5 The negatives that are TRUE (Invariant 1)

6374's turns repeatedly say that the text of its Order's Schedule is not held. **Live: LEX holds no
text for that Schedule.**

- `/legislation/section/lookup` returns 3 provisions, none a schedule.
- The flagged text equals the unflagged one (1,827 characters).

**16 turns of 6374 carry a negative about that Schedule, 14 of them in the answer, and every one is
true.** In 5 of the 14 the answer blames a search or step limit rather than the index. That is
true about the run but not about the reason. These are the negatives a P3.27 fix must keep, and it
should correct their attribution (decision 5).

**Other negatives about a schedule or annex, read by hand (`handread_noneed_dump.txt`).**

- One Deep Research claim that two instruments' schedules contain no currency symbol: the schedules
  were returned by a section search, and the live flagged texts confirm it (0 occurrences). It is
  true.
- Two detector false hits on change-record wording (an annex, and a subsection, recorded as "omitted").
- 143 negative sentences in all were written for hand-read. Every one falls in one of the classes
  above.

---

## 2. The live probe

### 2.1 `/legislation/text` with and without `include_schedules` (128 calls)

`python probe1_text.py` (calls), `python probe1_analyse.py` (no calls; `probe1_analysis.txt`).
I probed all 60 instruments a stored whole-text read touched, both ways, and the 8 failed ids once
with the flag (all 404 again).

- **The flagged text is the unflagged text plus the schedules appended, in 60 of 60**, and the live
  unflagged length equals the stored one in 60 of 60. So the stored corpus reflects today's index.
- **27 of 60 grow; 33 do not.** All 18 instruments with known units grow. **All 79 known units are
  in the added text**, found by heading in either order ("SCHEDULE 2", "SECOND SCHEDULE") or by
  their opening text.
  - A heading-only check finds 74. The 5 it misses are an ordinal heading, an unheaded repeal table
    and a malformed provision url.
- **Sizes with the flag** (all 60 instruments): median 10,246 characters (5,988 without), p75 64,516,
  p90 168,950, max 1,178,556 (P3.12's Act; 894,391 without).
  - Where the text grows: median ×1.37, max ×73.1; median 20,632 characters added, max 392,380.
  - 29 of 60 stay at or under 8,000 characters (32 without); 52 of 60 stay at or under 150,000 (55
    without).
- **Hollow texts:** in 9 instruments the schedules are longer than the sections. One SI's body is
  882 characters and its schedule 63,634.
- **P3.27's row figures.** P3.2's regulation grows to **440,067** (row: "at least 440,035"). The two
  SIs grow from 1,031 to 7,241 and from 1,568 to 12,480 characters.

**What sending the flag would have changed on the stored reads** (`python flag_cost.py`, sizes
from the live probe; 419 reads that were not memo hits):

- 4 reads move from verbatim to summarised; 22 grow and stay verbatim.
- Summariser input over the corpus goes from 10,307,667 to 20,207,402 characters (**×1.96**), and
  150K-character chunk calls from 174 to 227.
- 34 reads on 8 instruments exceed one chunk with the flag.
- Every stored replay summarised above **8,000** characters: no summarised read is under 9,263 and
  no verbatim one over 7,795. The context-scaled threshold never applied.

**Where the schedules start, from ONE flagged response** (`python boundary.py`). A paragraph-start
"SCHEDULE / ANNEX / <ordinal> SCHEDULE" finds the boundary exactly in 22 of the 27 that grow. It is
too early in 1 and finds nothing in 4. It finds no heading in any of the 33 that do not grow. So a
code line that must state exactly which schedules a text carries needs the unflagged length as well,
which means a second call or a lookup.

### 2.2 P3.12: how one schedule or annex provision is reached (28 calls)

`python probe2_p312.py`, `python probe3_route.py`, `python probe4_proxy.py`.

- **`/legislation/section/lookup`** (limit above the provision count) returns every provision with
  text. Filtering by `uri` gives the unit **deterministically**.
  - P3.12's Act: **674** provisions in 1,598,880 bytes, 405 ms. Its Schedule is one row of 92,066
    characters at position 123: not last, so the lookup's order is not sections-then-schedules and
    a small `limit` cannot be used.
  - P3.2's regulation: 56 provisions in 476,493 bytes; the annex is one row of 89,133 characters.
  - Over the **16 instruments P3.12's trigger would have fired on** (`python route_ids.py`: 124
    stored calls on 5 instruments for a named sub-unit, 163 on 16 counting schedule-only queries):
    median 242,172 bytes, max 1,598,880; median 148 ms, max 438 ms.
  - **The 674 against 1,161 is now partly reconciled.** The lookup with `limit` 2000 returned 674,
    below the limit, so 674 is complete: 650 sections, 23 schedules and 1 odd row. The text record's
    `number_of_provisions: 1161` counts something else; I have not found what.
- **`/legislation/section/search` does not reach the unit by name.** "Schedule X" on P3.12's Act
  does not return the Schedule at `size` 50. "Schedule X paragraph N" returns it at rank 22 of 50,
  and a topical query at rank 10 of 20. The annex comes back at rank 15 of 20 for "Annex X
  Chapter Y", and not at all in the top 10 for "Annex X". `include_text: false` makes a 50-row
  index 29 KB, but there is no endpoint to fetch one provision's text from LEX's own index.
- **New: `GET /legislation/proxy/<url-encoded provision path>` returns legislation.gov.uk's own page
  for exactly that provision, through LEX's host.**
  - P3.12's paragraph comes back in 68,657 bytes (1.2 s), and P3.2's annex chapter in 46,977 bytes
    (1.4 s). The whole Act's page is 8.9 MB.
  - Its paragraph-level element ids are there (`…-paragraph-N-2-a`).
  - 18 of 20 lines of the paragraph match LEX's text verbatim. The 2 misses are the bold heading and
    one definition line rendered differently.
  - **Caveats:** the spec calls the endpoint a metadata proxy returning HTML; it is a second text
    source, with legislation.gov.uk's own revision notes (`[ F1`); and it depends on
    legislation.gov.uk being up. It needs no new whitelist entry. This is also P5.4 (d)'s question
    (paragraph-level markup), answered through a host we already call.
- **The flagged whole text** carries P3.12's Schedule heading at character 950,791 of 1,178,556.
  That is summariser chunk 7 of 8, and the summary is then capped. Whether the paragraphs survive
  needs a model call, which I did not make (D's 1.4 d stands: the flag alone is not P3.12's fix).

### 2.3 D's cut rules on the live text

`python cut_rules_live.py`. It covers 134 live schedules (from the lookup payloads and the 27
flagged texts split at their headings) and 35 live annexes.

- **Annex chapters: `_cut_annex` cuts 112 of 112** chapter headings (median 0.13 of the annex). P3.2's
  chapter comes out at **2,494** characters of 89,133, exactly D's stored figure.
- **Schedule paragraphs.** By marker form, per schedule: 33 use `Section N)`, 29 of them mixed with
  bare `N)`; 65 bare only; 3 `(N)` only; 33 none.
  - Of 440 `Section N)` lines, 436 are unique.
  - **Where the cut ends is the new finding.** Un-headed paragraphs are rendered bare, like
    sub-paragraphs, so a cut runs to the next `Section M)` line. It holds exactly paragraph N in
    348 (next M = N+1). It runs to the schedule's end in 31 (N last). It **swallows the un-headed
    paragraphs between** in **57** (median 2, max 142).
  - D's rule (a unique `Section N)` line, 123 of 123) tested uniqueness only. It needs a second
    condition: cut cleanly only where the next headed paragraph is N+1. Otherwise label the span
    with the paragraphs it runs through, or hand over the whole schedule summarised.
- **P3.12's three paragraphs are all `Section N)` and consecutive**, so they cut cleanly: 733, 1,450
  and 1,935 characters of a 92,066-character Schedule.

### 2.4 P3.12's ground truth

The three paragraphs P3.12's acceptance names, cut from the live provision, are in the gitignored
`p312_truth.txt`. The third paragraph is checked against the independent proxied
legislation.gov.uk page (18 of 20 lines verbatim). P3.2's annex chapter is in
`p32_control_truth.txt`. Where they go in the repo is decision 4.

---

## 3. What I did NOT do

- No product, tool or test change; the only commit is this note. Nothing was built.
- No model call:
  - whether a flagged 440K or 1.18M text keeps the named unit through summarisation is unmeasured;
  - so is whether a code line changes what the Manager writes (1.4: the report was right and the
    answer was not).
- No probe of `/amendment/*`, the explanatory-note endpoints or legislation.gov.uk directly.
- The proxy was compared with LEX on one paragraph only.
- I did not reconcile `number_of_provisions` beyond showing the lookup is complete.
- I did not edit FIX_PLAN, SESSION_LOG, the tracker, `DEPTH_TRUTH`, a rubric or the lawyer pack.
- I did not run `plan_status` or `plan_lint`, because nothing they read changed.

**Checks.**

- The full suite on `lexchat_test_b` gives **2195 passed** (no code changed).
- **Row claims I checked:**
  - P3.27's "18 instruments, 79 provisions, 0 carried": holds (D's script re-run on `6011b4f`,
    `d_fulltext_rerun.txt`). Live, all 79 are in the flagged texts.
  - P3.27's executor premise: holds at `6011b4f` (`executor.py:533` sends only `legislation_id`).
  - P3.12's "674 provisions, the Schedule is one": holds live.
  - P3.12's "never ranks the Schedule into the top 10 (a topical query at size 20 does)": holds.
  - D's 2,494-character chapter: holds live.
  - D's `Section N)` 123 of 123: holds for uniqueness; the cut's end fails in 57 of 440 (2.3).

---

## 4. Decisions for the user

1. **P3.27's lever.**
   1. **(Recommended) Send `include_schedules: true`, and append a code-written line, built from the
      raw response after summarisation (P2.3's `enabling_power_note` pattern), saying which schedules
      and annexes the text carries, or that the index holds none for this instrument.**
      - The line is exact only with the unflagged length, so the branch makes both calls (each
        59-438 ms against LEX, small beside the model's time). One flagged call finds the boundary
        in 22 of 27.
      - **What it changes:** the 126 reads in 98 turns that left schedules out. 6374's true
        negative becomes a code-stated fact.
      - **Tests:** an executor-seam test that the payload carries the flag and the result passes
        through; line tests on synthetic text ("Widget Order 1901" with a "SCHEDULE 1", an ordinal
        heading, and none); the detector screen (`test_footer_trips_no_detector`); a $0 dry run of
        the line over the 60 saved live payloads, listing every line; then the replay in decision 3.
   2. **The flag and a line from one call.** The line cannot list the schedules (wrong on 5 of 27),
      so it can only say they are appended where the index holds them.
   3. **The line only, no flag.** It states the omission but makes nothing reachable. On P3.2's turns
      the report already said it and the answer still did not.
   4. **The flag only.** Schedules become reachable, but nothing tells the Worker where they are, or
      that none are held.
2. **A size bound on the flag.**
   1. **(Recommended) None at first; count the cost on the after-column.** Summariser input is ×1.96
      over the stored reads, and 34 reads on 8 instruments exceed one 150K chunk.
   2. **Above 150K, keep the sections and replace the schedules with their headings**, pointing to
      P3.12's route. This bounds cost and leaves a named unit to P3.12.
   3. **Only where the flagged text stays verbatim (8K).** That is 22 reads; most of the value is lost.
3. **P3.12's route, and whether to build it with P3.27.**
   1. **(Recommended) One build, two commits, P3.27 first (P1), then P3.12's route.**
      - **The route:** `/legislation/section/lookup` with a limit above the provision count, the row
        picked by `uri`.
      - **Annex chapters** cut by `_cut_annex` (112 of 112 live).
      - **A schedule paragraph** cut only where its `Section N)` line is unique and the next headed
        paragraph is N+1 (348 of 440). Otherwise the span is labelled with what it runs through, or
        the whole schedule is summarised for the query.
      - **On a lookup failure,** the flagged text cut at the heading.
      - The two share the heading and cut helpers and one acceptance sweep with P3.25 (6406's control
        turn, 6335 turn 7, 6374 as the guard).
      - **Tests:** a `run_worker_tool` seam test on a synthetic instrument, proven failing with the
        route reverted; a dry run over all 5,128 stored section searches listing every call it fires
        on (124 on 5 instruments, 163 on 16 with schedule-only queries); the cut over the saved live
        payloads.
   2. **The same, but the paragraph comes from `GET /legislation/proxy`** (exact provision, no cut
      rule, no new whitelist entry). It brings a second text source, HTML parsing and an endpoint
      whose spec says something else. Better kept as a fallback, or for P5.4 (d).
   3. **Build P3.27 alone now and P3.12 next batch.** This is simpler to review. But the conversational
      shape (16 of the 23 need turns) needs P3.12, because P3.25 takes the whole-text tool from that
      Worker.
4. **Where P3.12's ground truth goes.**
   1. **(Recommended) A `DepthReq` for 6335 turn 7 in `DEPTH_TRUTH`**, with `facts` regexes over the
      paragraphs' statutory words, like the existing entries. The statute text is public and holds no
      lawyer's words; the cut text stays in the gitignored scratch.
   2. **Gitignored `evidence/rubrics/`, loaded by `depth` at run time.**
   3. **Grade that turn by hand only.**
5. **Invariant 1 guard for the true negative.**
   1. **(Recommended) Add to P3.27's acceptance:** on 6374's turns naming the Order's Schedule, the
      answer still says the index holds no text for it, and no longer blames a search limit (5 of 14
      answers do now).
   2. **Leave it as a note on the row.**
