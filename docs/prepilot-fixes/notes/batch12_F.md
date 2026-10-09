# Batch 12, agent F: P3.38, P3.39, P3.34 and P3.43 measured ($0, no external call)

Data-improvement batch 1's agents A (P3.38, P3.39) and C (P3.34, P3.43), run as batch 12's agent F
(Session 44, 2026-10-09). **Measurement only: no product code, no test change, no row edited.** This note
is the only tracked file changed.

## 0. Setup, and what this note does not contain

- **Base.** The worktree came up on `main` (`a6b4a76`), as in every batch. With no commits of my own, I
  ran `git reset --hard a99e4d4` (the integrator HEAD). The note is based on `a99e4d4`.
- **Spend $0. Live calls: none, to any host.** No seam, no replay, no server.
- **Inputs counted:** **66** replay directories holding **559** run files (`runall.py` section A; the brief
  said 66). The export holds **196** user turns in **62** sessions from **13** lawyers. Run files are mapped
  back to export turns through `script.turns[].from_turn`, as `replay_report._export_turns` does.
- **Matter text is not in this note.** Session ids and export turn numbers appear, as in the scripts. The
  instrument ids and titles, the defined terms the lawyers asked about, and every quoted sentence are in the
  gitignored hand-read `evidence/seam/batch12/F/handread_F.md`, with one row per counted slot.
- **Scratch:** `docs/prepilot-fixes/evidence/seam/batch12/F/` (gitignored, checked with `git check-ignore -v`).
  Every number below comes from `runall.py` there, after its run order (in its docstring):
  `python export_turns.py && python p338_scan.py && python held_index.py --rebuild && python p338_table.py && python runall.py`,
  run from that folder with `PYTHONIOENCODING=utf-8`. It reads the export at `C:/Temp/...` and
  `$PREPILOT_EVIDENCE/replay` and `/madeunder`.

## 1. Headlines

| Row | Measured | Against the row's rule | Proposal |
|---|---|---|---|
| **P3.38** (recent instruments from legislation.gov.uk) | **20 slots in 8 sessions** where a tool or the answer said an instrument the index lacks is not held or has no text. **9 SSIs are checkable in the census, and 9 of 9 are published by legislation.gov.uk with their as-made text.** A read would change **10 slots** (7 fully, 3 in part) across **5 sessions and 4 lawyers**. One more slot would also have changed, but P3.31's record already meets it. | The row has no drop rule. Its premise is confirmed. | **GO** (P2). Acceptance turns are in §3.5. **The trigger must include held-without-text, not only not-held:** 5 of the 9 instruments are records with no text, and 4 of those 5 were never looked up. |
| **P3.39** (the law as it stood on a date) | **0 turns need a dated version.** 2 user turns (1 session) ask about the "original" historical law. Both are answerable from the old local Acts that LEX already holds as such. 1 borderline turn. | The row has no drop rule. The demand it assumed is absent from the pre-pilot. | **NO-GO now.** Park it with a re-open trigger (decision 2). |
| **P3.34** (definitions index) | Under **the row's own rule (B11)**: **2 turns** (6338 t1-t2). P3.17's built lever already serves both, and an index alone would not have fixed them. Under the **brief's wider count**: **9 export turns in 3 sessions (2 lawyers)** are "find every statutory definition of a term" questions, and each answer misses most of what other runs found. | Under its B11 rule the row drops. The wider count shows a different and larger use case. | **Re-scope, not drop** (decision 3): definition-list questions, a cheaper lever measured first. |
| **P3.43** (statutory guidance, codes) | **0 of 196** user turns ask for guidance, a code of practice, directions or a circular. **2 turns** (1 lawyer) have answers saying the content asked for lives in ministerial directions the product cannot read. | "A negligible count drops the row": 0 explicit asks. | **Drop `[-]`** (decision 4). Record the 2 implicit turns on the row. |

## 2. Method (P3.38 and P3.34 share the evidence index)

- **Held-evidence index** (`held_index.py`): for each legislation id in any stored tool result, how LEX
  answered. This covers the lookup status, a text read's `full_text` length, LEX's "Legislation not found"
  detail, and appearance as a search or section-search row. **Trap found and fixed in my own script:**
  `get_legislation_text` results carry `legislation.text = ""` on every read, and the body is in
  `full_text`. Read `legislation.text` and all 93 text-read ids look empty; read `full_text` and 5 do. Any
  grader that reads a text result should key on `full_text`.
- **Census** (`census.py`): P3.31's `*_snap.jsonl` harvest files (121,132 records). An id is present (with its
  as-made introduction XML and preamble), absent, or not tried. Series outside the census (ukpga, local
  Acts) are reported as **unknown**, as the brief requires. Nothing was called.
- **Slots** (`p338_table.py`): a slot is (session, export turn). It counts when the export answer or any stored
  run says, by tool or in the answer, that an instrument the index really lacks is not held, not found or has
  no text. "Really lacks" means a not-held or held-without-text lookup, LEX's not-found detail, or an empty
  `full_text`, with no successful read anywhere. The export's own claims use wording outside the scan's
  sentence pattern (two phrasings saying the database did not contain or return the instrument). I read those 6 by hand and entered
  them in `MANUAL_EXPORT`.
- **Every counted slot and every exclusion was read**: the export answer, plus the latest stored answers at
  HEAD-era heads (`wave4_p331`, `wave4_b9_sweep2b`, `wave4_b7_p324`, `wave4_p37_reach`, `wave4_p37c`).

## 3. P3.38: instruments the index lacks that legislation.gov.uk publishes

### 3.1 Counts (`p338_table.py`; the census and LEX columns are in `runall.py` section B)

- **18 slots from tools or answers, in 6 sessions** (6409 t1-t11, 6373 t2-t3, 6410 t2, 6382 t1, 6383 t1 and t3,
  6363 t5), over **236 run-turn instances**. There are **2 more answer-only slots** (6371 t1 in the export;
  6387 t3 in 1 of its 5 stored answers), for **20 slots in 8 sessions**.
- **Instruments:** 11 ids. **9 are SSIs, and all 9 are present in the census with an as-made preamble.**
  The other 2 are UK Public General Acts that LEX's lookup says are not held; their legislation.gov.uk status
  is **unknown** (not in the census; no call). The two answer-only slots name a 1940s Act LEX holds only as
  stub provisions (P5.3's row), and a 19th-century local Act. Both are **unknown**.
- **The split:** **4 not held** (no record) and **5 held without text** (a record whose `full_text` is the
  one-line "No text content available for this legislation."). **Only 1 of the 5 stubs was ever surfaced by
  `lookup_legislation`.** The other 4 were met only by a text read in `wave4_p331` (6382 t1), after P3.31's
  record led the Worker to them. The product has no annotation for an empty text read: the Worker inferred
  by itself that the text was unavailable.

### 3.2 What each slot needed, and whether a legislation.gov.uk read would change it at HEAD

Read against the latest stored answers (table in `handread_F.md`):

- **Changed, fully: 7 slots.** 6409 t9, t10, t11 (the not-held commencement SSI: the answer can say which
  section it commences, from the change record, but says it cannot check the purposes for which it does so,
  and at t11 that it cannot give the terms); 6373 t2, t3 (whether something is mentioned in a not-held SSI:
  the answer says it cannot check the text); 6382 t1 (six instruments made under the power, which the answer
  says could not be checked for what the lawyer asked); 6383 t1 (the same check on one not-held SSI).
- **Changed, in part: 3 slots.** 6409 t7, t8 (the stub commencement SSI: sections and date are answered from
  the change record and P3.21, but the answer says it cannot read the saving and transitional provisions its
  title names); 6410 t2 (the not-held commencement SSI: named, but the answer says it cannot confirm the
  instrument's title or the dates it appoints. P3.21's dates were built after those runs and have not been
  re-measured on 6410).
- **Already met by P3.31: 1 slot.** 6383 t3 asks which SSIs were made under a section. A read would have
  changed it before P3.31; at HEAD the record answers it. **So of the 11 slots a read would have changed,
  1 is fully met by P3.31 (the record and its recital), and 2 more (6382 t1, 6383 t1) have their made-under
  half met.** Their text half (the symbol check) is not met.
- **Not changed: 7 slots.** 6409 t1-t6 (in-force questions where the Worker met the two SSIs through the
  change record; at HEAD the change record and P3.21's dates answer them); 6363 t5 (the need is case law, and
  the not-held Act is a side reference).
- **Unknown: 2 slots** (6371 t1, 6387 t3; the series is not in the census).

**Sessions with a changed slot: 6409, 6373, 6410, 6382, 6383** (4 lawyers, `runall.py` B). **In the export
itself, 3 sessions (3 lawyers)** met a not-held recent SSI unprompted (6409, 6373, 6410). 6382 and 6383 reach
their instruments only since P3.31: **6 of the 37 instruments the record lists under that power (the 37 is
P3.31's acceptance figure) have no text in the index (16%)**.

### 3.3 Excluded: "not found" claims about instruments the index holds (22 claims, read)

Counted as slot × instrument. 6409 t1-t2 appear here for the export's claim about the held Act, and above for
the two SSIs.

These are retrieval or filter defects, not P3.38's case: a lookup would have said "held". They were 6357 t1,
t3, t4; 6374 t1-t2; 6381 t1-t3; 6383 t4; 6384 t2-t3; 6396 t1; 6407 t1; 6409 t1-t2 (export); 6341 t6-t7 (two
LEX stub records whose sections *were* retrieved and cited); 6374 t3-t4 (a Schedule: P3.27); 6408 t3 (a
search budget); 6345 t3 (a provision negative); and 6340 t1 (a made-under negative about pre-1987 SIs:
P3.31/P3.35, never a named-instrument claim). Each is listed with its evidence in `handread_F.md`.

### 3.4 Side findings (not P3.38's to fix)

- **`get_legislation_text` 404s on regnal-form ids that LEX's own search and section search return**
  (2 Acts, 4 reads; `runall.py` C prints each id's evidence). Both Acts are LEX "stub" records with
  retrievable sections. A model-built calendar id for one of them 404s too.
- **47 distinct ids appear in search rows with `text_version: "stub"`** (436 rows; `runall.py` C). 46 are in
  regnal-year form and 1 is a 1950s Northern Ireland Act. All are pre-1963 primary legislation, outside the
  census. Their legislation.gov.uk status is unknown.

### 3.5 Proposal

**GO, at P2.** The premise holds: every checkable instrument (9 of 9) is on legislation.gov.uk with text, and
10 slots in 5 sessions (4 lawyers) would change. **Design facts for the build:**
- trigger on `held_without_text` and on an empty `full_text` read, not only on `not_held` (5 of 9; 4 never
  looked up);
- the as-made XML is the right version for commencement and amending SSIs (the census holds it for all 9);
- the route is LEX's `/legislation/proxy` (P5.4: no whitelist entry);
- P3.7's code-written not-held statement must stay true: the index still does not hold the instrument;
  legislation.gov.uk does.

**Acceptance turns (ids only):**
- 6409 export t7-t11 (the existing `p37_6409` script covers them);
- 6373 t2-t3 (`p37_6373`);
- 6410 t2;
- one of 6382 t1 or 6383 t1 (the post-P3.31 shape; `wave4_p331` ran it).

**Controls:** 6409 t2 (a held Act named by number) and a held SSI.

**Bar (to be booked by the integrator, for the user to approve):** every not-held or stub slot reads the
text, says it was read from legislation.gov.uk, and answers the need (6409 t11 states the terms; 6373 t2
answers with a provision cited). No quoted term is absent from the text read (Invariant 1). The P3.7 footer
still says the index does not hold it.

## 4. P3.39: the law as it stood on a date

**Count: 0 user turns need a dated version of a current provision. 2 user turns, in 1 session and from 1
lawyer, ask about historical law (6387 t1, t3). 1 is borderline (6371 t1).** I read all 196 user turns. A
regex sweep (`runall.py` D) matched 19; I read each, and 17 are not temporal asks (a future change, references
back within the conversation, words inside instrument titles, a case-law date window, and wording that means
the current law).

What the answers did:
- **6387 t1/t2** ask which legislation first set a limit. The export's t1 deflected on mode (P4.1's
  shape). Its t2, and all 5 stored answers to t1 and t2, name a 19th-century local Act **from LEX's own copies
  of those Acts**. Which Act they name varies across reps, which is a consistency problem, not a version
  problem.
- **6387 t3** asks what the penalties were. The export has no reply. Of the 5 stored answers, 4 give the regime
  from the held Acts' text and 1 refuses.

No answer used the current text of an amended provision where an earlier text was needed. The borderline
6371 t1 asks the purpose of a section of a 1940s Act that LEX holds only as stub provisions. The export refused
and pointed to Hansard. An `/enacted` read helps only if legislation.gov.uk holds that Act, which is unknown.

**Proposal: NO-GO now** (decision 2). The arXiv evidence on the row is from tax-code questions, a different
population. Re-open on pilot evidence.

## 5. P3.34: definitions

**The row's rule**: count "the stored B11 turns whose failure turns on a definition held in another
instrument that retrieval did not reach". **Count: 2** (6338 t1, t2). The pre-pilot answer asserted a newer
interpretation Act from training, with neither candidate instrument retrieved. P3.17's PHASE 2c (built) now
reaches the right instrument through its *application* provision (turn 1 named it in 3 of 3 in
`wave4_b2_post`, P3.17's row). An index of definitions would put the competing definitions side by side, and
the B11 failure was choosing between them, which only the application provision settles. The other B11 turns
are not definitional: 6338 t3 (concurrency), 6370 (class (b) below) and 6375 (a doctrine). **By its own rule,
the B11 premise is negligible.**

**The brief's count**, covering every turn whose question or failure turns on a defined term. Each was read,
and the classification is in `handread_F.md`:

| Class | Turns | Sessions |
|---|---|---|
| (a) retrieved and used | 11 | 6335, 6337, 6362 x2, 6374 x3, 6389, 6404, 6405, 6413 (a borrowed definition followed into another instrument) |
| (b) retrieved and misread | 7 | 6406 t6, t9, t11, t12 (P3.2's ground); 6370 t3, t5, t6 (P3.3's ground) |
| (c) another instrument never reached, B11 | 2 | 6338 t1-t2 (served by P3.17 at HEAD) |
| (c) another instrument never reached, **definition-list questions** | **9** | 6341 t2-t7, 6384 t1 and t4, 6363 t1 (3 sessions, 2 lawyers) |
| (d) same or named held instrument not retrieved (filter or halt) | 2 | 6357 t3 (0 of 6 answers ever retrieved it), 6384 t2 |
| case-law meaning (outside an instrument index) | 10 | 6335 t3-t6 (t4-t5 had no reply in the export), 6348 t4, 6347 t3-t4, 6363 t2, t4, t5 |

**The definition-list evidence** (`p334_defs.py`, via `runall.py` F), counting instruments cited in a sentence
that gives a definition of the session's term, per answer:

| Turn | Answers | Per answer | Union | Note |
|---|---|---|---|---|
| 6341 t7 (asks for every statutory definition) | 19 | 0 to 14 | 29 | most-cited instrument in 12 of 19 |
| 6341 t6 | 19 | 0 to 8 | 10 | 17 of 19 cite none |
| 6384 t4 | 7 | 1 to 10 | 10 | |
| 6363 t1 | 10 | 0 to 6 | 11 | |

Every instrument in a union was reached by some run, so each answer's misses are held by LEX; that run's
retrieval did not reach them. Two answers say so themselves: they name instruments whose definitions they
could not retrieve because steps halted or a budget bit. The count is a lower bound: the union is only what
some run found. And the detector is loose: a sentence saying an instrument does *not* define the term counts.

**Proposal: re-scope P3.34 to definition-list questions, and measure a cheap lever before any harvest**
(decision 3). The repo's own LEX spec (`docs/api/LexAPISpec.md`, `/legislation/section/search`) marks
`legislation_id` as **optional**, so a corpus-wide definitional search may need no index. **Not verified live
here:** that is the first measure, a few LEX calls in a later batch. **Acceptance turns if go:** 6341 t7 and
6384 t4 (n=3 each), 6363 t1. Controls: 6362 t4 (a definition inside one instrument) and 6413 t1 (a borrowed
definition followed).

## 6. P3.43: statutory guidance and codes of practice

**Count: 0 of 196 user turns ask for guidance, a code of practice, directions or a circular made or issued
under a provision.** A sweep (`runall.py` E) matched 12, and I read each:
- 6 use "scheme" in an unrelated sense;
- 2 use "policy", inside a Regulation's title;
- 2 use "guidance" from a tribunal, which is case law;
- 1 names a procedural direction in another sense;
- 6351 t1 asks whether a court order can enforce a ministerial direction. That is a question about the
  remedy, not about the direction's content.

**Implicit: 2 turns, 1 lawyer** (6365 t1, 6367 t1), from `p343_replay.py` over the replays and the export. 14
of 16 and 11 of 11 stored answers, plus both export answers, say that the content the lawyer asked for is set
by ministerial directions made under the Acts concerned, which no tool holds. 6370 t6's export answer
suggests consulting government circulars. 6338 t3 and 6370 t6 each have 1 stored answer saying no statutory guidance was
found.

**Proposal: drop `[-]`** under the row's rule, recording the 2 implicit turns (decision 4). If it is ever
re-opened:
- **candidate sources:** gov.scot publications (ministerial directions, statutory guidance) and gov.uk guidance
  collections;
- **terms to check:** the Open Government Licence v3.0 those sites state (not checked here, no call);
- **whitelist:** `www.gov.scot` and `www.gov.uk`.

## 7. What I did not do

- No external call of any kind. Nothing was checked live, so these remain unverified:
  - legislation.gov.uk holdings outside the census (the 2 UK Public General Acts, the 1940s Act and the local Act,
    the 47 regnal stubs);
  - the optional `legislation_id` on LEX's section search;
  - the gov.scot and gov.uk terms.
- No model call, seam, replay or server. No product, test or plan file changed. No row was edited.
- I did not re-litigate P3.3's or P3.17's readings (6338, 6370 are cited from their rows).
- I did not measure 6410 t2 after P3.21: no stored 6410 run postdates it.
- I did not grade "completeness" of a definition list against a legal ground truth, only against the union of
  what stored runs found.
- I did not read pilot questions: the pilot has not run, so the pre-pilot export is the only question set.

## 8. Checks behind the claims

- **"9 of 9 published"** is `census.py` on each id: PRESENT, `version=made`, `preamble=ok`, holds for all 9.
  This **passes** for the introduction view. That the body XML is published is inferred from legislation.gov.uk
  publishing made SSIs whole, and was not fetched.
- **"Really lacks"** is the held-evidence index: no `text_ok`, `lookup_held` or `section_row` for any of the
  11. This passes. The one candidate that failed it, the calendar-form id of a held regnal Act, was removed.
- **Stub detection** compares `full_text` under 200 characters against the actual 47-character stub body:
  5 ids, each confirmed as the "No text content available" string. This passes.
- **Turn mapping:** spot-checked on `p37_6409` (run turn 5 maps to export turn 9, the not-held SSI), which
  matches P3.7's graded slots. This passes.
- **Export turn numbering** (the n-th user message) matches P3.7's slot keys (6409 t9, 6373 t2). This passes.

## 9. Decisions for the user

1. **P3.38: go, and on what trigger?**
   (a) **Recommended:** GO at P2, triggered on `not_held`, `held_without_text` **and** an empty `full_text`
   read, through LEX's proxy, as-made XML, live and never cached. Acceptance on 6409 t7-t11, 6373 t2-t3,
   6410 t2 and one of 6382/6383 t1, with the controls above.
   (b) GO on `not_held` only, as the row now reads. This misses 5 of the 9 instruments (all the stubs).
   (c) Defer until the pilot. This leaves 10 measured slots, in 5 sessions and from 4 lawyers, answered with a
   statement that the text cannot be read.
2. **P3.39: what now?**
   (a) **Recommended:** NO-GO now; park `[ ]` with a note "re-open if the pilot shows 2 or more turns needing
   the law at a date". The pre-pilot has 0.
   (b) Drop `[-]`.
   (c) Build anyway as a cheap proxy tool next to P3.21. This builds with no measured user, against the plan's
   measure-first practice.
3. **P3.34: its B11 premise fails its own rule, but definition-list questions are real. Which?**
   (a) **Recommended:** re-scope the row to definition-list questions (9 export turns, 3 sessions, per-answer
   coverage 0 to 14 of a 29-instrument union). Its first step is a few LEX calls testing a corpus-wide
   definitional section search (no `legislation_id`) before any harvest.
   (b) Drop P3.34 `[-]` on its B11 rule and book the definition-list case as a new row.
   (c) Keep the row as written (the heavy body harvest). Its stated motivation (B11) is measured at 2 turns,
   both already served by P3.17.
4. **P3.43: drop?**
   (a) **Recommended:** drop `[-]`, since 0 of 196 turns ask, recording the 2 implicit ministerial-directions
   turns (1 lawyer) on the row.
   (b) Park it with a pilot re-open trigger.
   (c) Narrow it to "ministerial directions under a provision" and keep it measured-first. This rests on
   2 turns from 1 lawyer.
5. **Side findings: book them?**
   (a) **Recommended:** add a one-line note to P3.38's row (the regnal-id 404 on `get_legislation_text` for
   records LEX's search returns), and a lesson that `get_legislation_text`'s body is `full_text`
   (`legislation.text` is always empty).
   (b) Book the regnal 404 as its own row.
   (c) Leave both in this note.
