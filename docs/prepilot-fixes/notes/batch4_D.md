# Parallel batch 4, agent D: P3.17 measured with options, and the inserting-Act point for the lawyer pack

Session 36, 2026-10-02. Branch `worktree-agent-aa20b622696a1c647`. **The worktree came up on `main`
(`a6b4a76`), not the integrator's HEAD; with no commits of mine I ran
`git reset --hard e5c31ba52567496be4eb4d467e5b8ae621c116e0` before any work.**

**Spend: $0.** No model call, no seam draw, no server, no replay. Sixteen read-only requests to the
public LEX API (one GET of `/openapi.json`; fifteen to search and lookup endpoints, which take a
JSON body by POST and write nothing: the brief said GET, and these endpoints have no GET form).
No product code, no rubric edit, no test added. Full suite on `lexchat_test_d`: **2093 passed**
(`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d python -m pytest -q -x -p no:cacheprovider`, from `server_py/`).

This note names no matter, instrument or reading. Instruments are lettered as in `batch2_C.md`:
**R**, the older interpretation order the booked criteria require; **N**, the newer interpretation
Act; **U**, the UK interpretation Act; **E** and **L**, the earlier and the later of the two Acts that
amended the Act asked about.

**Scratch: the worktree's own gitignored `docs/prepilot-fixes/evidence/seam/batch4/D/`**, because
the harness refused the Write tool on the main checkout's evidence folder. It must be copied to
`$PREPILOT_EVIDENCE/seam/batch4/D/` before the worktree is removed. Its `README.md` indexes every
file. **The pack edit is not applied** (same reason): the edited copy is
`seam/batch4/D/pack/confirmation_pack.md`, for the integrator to copy over
`evidence/lawyer_pack/confirmation_pack.md`.

## The row's acceptance, and whether it is met

**Acceptance (FIX_PLAN P3.17):** P3.3's 6338 criteria, n=3, in the lawyer's configuration. Per rep:
turns 1 and 2 name R; no turn asserts that N governs the Act or the inserted section; turn 3 says
the Act sets no order and does not conclude, hedged or not, that the two must run in sequence.

**Not met** (`wave4_b2_post`, 1 of 3 by hand, as recorded). Nothing here changes a verdict. Part 1
locates the two failure shapes and sets out options; nothing was built.

## Part 1: where the two readings first appear

Method: every stored 6338 rep in the lawyer's configuration (`wave4_p33_pre`, `wave4_p33_post`,
`wave4_b1_post`, `wave4_b2_post`; 3 reps each; 12 turn-2 and 12 turn-3 turns). For each turn, each
stage was read by hand:
- the raw tool results;
- what the Worker saw (the summary, where a result was summarised);
- the Worker's report;
- the Manager's answer.

A regex tagger located candidates first (`scratch/scripts/trace6338.py`). Every turn-2 and turn-3
brief, report and answer was then printed (`scratch/scripts/reports6338.py 2`, `... 3`,
`... 3 summaries`) and read in full.

### Turn 3: the hedged sequence reading

| directory | P3.3 clause in prompts | sequence stated, unhedged | sequence offered as a reading | where it first appears |
|---|---|---|---|---|
| `wave4_p33_pre` | no | **3 of 3** | 0 | summary 2 (r2, r3), Worker report 1 (r1); the Manager kept it in 3 of 3 |
| `wave4_p33_post` | yes | 0 | **1 of 3** (r2) | Manager answer only |
| `wave4_b1_post` | yes | 0 | **1 of 3** (r1) | Manager answer only |
| `wave4_b2_post` | yes (+ PHASE 2c) | 0 | **2 of 3** (r2, r3) | Manager answer only |

- **Since the clause:** the Worker report states the text's silence and offers no reading in 9 of 9.
  The turn-3 summaries carry no sequence framing in 9 of 9. The reading is added by the Manager in
  4 of 9 answers.
- **The phrasing:** all 4 use "on one reading", the clause's own example. All 4 sit beside the right
  statement (the Act does not state an order, or does not prohibit overlap).
- **Correction to the record.** The hand-read, SESSION_LOG Session 35 and the P3.17 row say that no
  stored rep before `wave4_b2_post` offered the sequence as a reading. **Two did:**
  - `wave4_p33_post` r2 turn 3: on one reading, one step would need to finish before the other;
  - `wave4_b1_post` r1 turn 3: on one reading, one step should come before the other.

  Both were graded clean in their hand-reads; under the booked criterion both fail turn 3. **No
  recorded rep verdict moves**: both reps already failed on another turn (`wave4_p33_post` r2 at
  turns 1-2, `wave4_b1_post` r1 at turn 1).
- **Is PHASE 2c the cause? Not shown, and unlikely.**
  - PHASE 2c is a quick-lookup Worker phase, and the turn-3 brief does not trigger it.
  - The turn-3 Worker reports in `wave4_b2_post` are neutral, 3 of 3.
  - The Manager prompt is byte-identical between `wave4_b1_post` and `wave4_b2_post` (batch 2 C's
    18-configuration test).
  - The only route left is the conversation history: turns 1-2 now name R and run longer. Testing it
    needs draws.
  - The rate moved from 2 of 6 (before PHASE 2c) to 2 of 3 (after). With n this small, that cannot
    be told apart from sampling.
- **Is P3.3's clause what turns the structural argument into a hedged reading? The evidence says
  yes.**
  - Before the clause, the argument reached the lawyer as a conclusion in 3 of 3.
  - After it, it never did. When it reached the lawyer at all (4 of 9), it came as "on one reading",
    always in the Manager's answer.
  - The clause did what it was written to do: an interpretation became a reading. The booked
    criterion was written to fail this exact form.
  - The two rules now conflict on this turn. The criterion fails a reading that the clause asks
    for.

### Turn 2: the newer Act offered as governing the inserted section

| directory | brief asks when or by what the section was inserted | change record called | N's application provision retrieved | outcome (R named / N asserted / N as a reading) |
|---|---|---|---|---|
| `wave4_p33_pre` | 1 of 3 | 1 | 0 | N (or U) asserted 3 of 3; first in the **summary** of the Act's own section search (raw text names none), 3 of 3 |
| `wave4_p33_post` | 0 of 3 | 0 | 1 | R 1; N asserted 2: r2 **Manager only** (the report said it was not verified), r3 from the retrieved definitions schedule (report) |
| `wave4_b1_post` | 1 of 3 | 0 | 1 | R 2; R and N side by side 1 (raw text, then report, then answer) |
| `wave4_b2_post` | **3 of 3** | **3** | **3** | R 2 (both say R governs the inserted text); **N as one of two readings 1 (r3)** |

- **Where r3's reading first appears: the Manager's answer.**
  - **Worker report:** gives a premise that is true: L, the Act that inserted the section, is itself
    governed by N. It also states the right conclusion for the Act asked about.
  - **Manager answer:** turns the premise into an "overlap" with two readings.
  - **Tool results:** no tool result or summary at any turn discusses which regime governs inserted
    text.
- **Did PHASE 2c's extra retrieval feed it? In part.**
  - In `wave4_b2_post`, PHASE 2c's "application" query retrieved N's application provision at
    turn 2 in 3 of 3, and that provision is the source of the true premise.
  - The same provision was retrieved in 5 turn-2 turns across the four directories. 3 of the 4 that
    addressed inserted text concluded R; 1 offered both readings. So the provision is an ingredient,
    not the cause.
  - **Its subsection (6) gives the alternative reading a textual footing:** a reference in that Part
    to an Act includes a provision of one. The Manager did not cite it.
  - The reading the rubric relies on to rule the alternative out rests on an explanatory note. No
    tool we call retrieves explanatory notes (`external-apis` skill).
- **The upstream change is turn 1.** The turn-1 answer now names R because of the Act's assent
  date. After that, the turn-2 brief asks when the section was inserted in 3 of 3 (2 of 9 in the
  three earlier directories). That puts the question of inserted text in play for the first time.

### Found: a wrong pinpoint for the insertion, from the change-record tool's grouping

- **In the answers:** all three `wave4_b2_post` Worker reports at turn 2 name the wrong subsection
  of L as the one that inserted the section. 2 of 3 answers repeat it (as does `wave4_p33_pre` r2's
  report).
- **The API rows are right:** they carry the correct subsection (`scratch/lex/03`, `/04`, `/14`,
  `/15`).
- **What the tool keeps (`agent/tools/lex.py`, `_slim_amendment_results`):**
  - it groups relations by (instrument, effect);
  - it keeps `changed_provisions` and `effected_by` as two separately sorted lists, so the pairing
    between them is lost;
  - it caps `effected_by` at `_MAX_EFFECTING_PROVISIONS = 6`.

  L's "inserted" group holds 16 relations and lists 6 effecting provisions. The right one is not
  among them.
- **How the wrong one got in:** the summariser paired the section with one of the six. In 4 of 4
  turn-2 summaries that came from the change record, the tool's output contains the wrong subsection
  and not the right one, and the summary states the wrong one.
- **This is not P3.17.** It is a candidate new row (B4, P3.5's tool) with a deterministic acceptance.
  The user's decision.

### Options for P3.17, with consequences

1. **Wait for the lawyer's answer to the pack (parts 2 and 3), and ask one more thing first.**
   - **Cost:** $0, nothing built. P3.17 stays not met.
   - **What part 3 asks:** whether the Act imposes no order. A Yes does not say whether an answer
     that says so may also offer the other order as one reading. Part 2, similarly, does not ask
     about the alternative given the textual footing above.
   - **So add a supplementary question** before sending: is it acceptable, beside a correct
     statement, to offer the other reading, flagged as one reading? The pack's question is not mine
     to edit; this is the user's decision.
   - **If a lawyer says the readings are acceptable:** `wave4_b2_post` re-grades on the evidence
     already stored. r2 fails only at turn 3 and r3 only at turns 2 and 3, so it could reach 3 of 3
     with no spend. P3.3's acceptance would also still need P3.2.
2. **A sharper clause in the conversational Manager** (not the Worker: the Worker is already neutral
   9 of 9). For example: where the retrieved text is silent on what the user asks (an order, a
   limit, which of two regimes), say it is silent; do not answer the silence with a reading drawn
   from a provision's purpose.
   - **Probes needed:** the first-delegation drift probe, about $0.40. Then a Manager-seam A/B on
     the stored turn-2 and turn-3 payloads of all four directories (`seam_replay manager --turn N`,
     9 slots a turn, 3-5 draws a side, about $1-2).
   - **Risks:**
     - **6370:** its acceptance wants readings given as readings, and the clause could push it to
       silence or to firm statements. So 6370's seam is needed too.
     - **The `hedges` guard.**
     - **The P3.3 counter-pressure:** these users want grounded analysis, and a purposive reading is
       analysis.
   - **A weak test at n=3:** the base rate is 4 of 9, and 0 of 3 has about a 1 in 6 chance even
     with no effect. So the seam evidence has to carry the decision.
   - **Booking:** build only if the lawyer says the readings are wrong to offer.
3. **Retrieve explanatory notes** (a worker tool on the endpoint the skill documents; same host, so
   no whitelist change).
   - **What it buys:** the only route by which the product could state the rubric's turn-2 answer
     from a retrieved source rather than from training (Invariant 1).
   - **Costs:** a new tool, tests, a `CACHEABLE_TOOLS` decision, more calls a turn. And an
     explanatory note is not law; answers would have to say so.
   - **Booking:** its own row; the user's decision, after the lawyer answers part 2.
4. **A code-side check at the Manager seam** that removes or flags a reading which supplies an
   order or a regime. **Not recommended.**
   - There is no generic deterministic trigger.
   - It would put one matter's law into code.
   - It would edit answer text that every grader reads.
5. **Fix the change-record pinpoint** (above). Separate from P3.17, but its error reached 2 of 3
   `wave4_b2_post` answers.

**Recommendation: option 1, and book option 5 as its own row.**
- Build nothing for P3.17 until a lawyer answers. Both failing shapes are readings that the
  product's own P3.3 rule asks for, placed beside the right statement. One of them has a textual
  footing in what was retrieved.
- If the lawyer says they are wrong to offer, option 2 is the lever, with seam evidence before any
  after-column. Option 3 follows only if the user wants turn 2 stated firmly.

**What an after-column would need to measure** (6338 x3 in the lawyer's configuration, about $1.50
at the recorded $0.50 a rep):
- **Turn 1:** R named; guards PHASE 2c's gain.
- **Turn 2:**
  - whether the brief asks about insertion;
  - whether the change record is called, and whether the pinpoint is right;
  - R / N asserted / N as a reading.
- **Turn 3:** the hedged sequence reading counted by hand. `interpret` misses it until agent A's
  rubric fix; check that fix against these 12 stored turn-3 answers, where by hand it is 3
  unhedged, 4 as readings and 5 clean.
- **Per turn, the stage of first appearance**, with `trace6338.py`.
- **If option 2 is built:** 6370 x3 (hedged and unhedged readings) and `hedges`.
- **Before-column:** the 12 stored reps above, with the corrected counts.

## Part 2: the inserting Act

**Evidence, stored tool results first:**
- **Stored change rows.** Over every replay run file (1,212 stored change-record calls), exactly one
  distinct relation touches the section: it was inserted by a subsection of L, type "inserted"
  (whole provision, not words). It is seen in 10 run files (`scratch/rows_target.out`).
- **Stored section text.** The stored text of the section carries no insertion note.
- **Where the earlier year comes from.** The only stored texts that attribute the insertion to E are
  4 summaries, all written before Session 32's summariser source rule: 3 in `baseline` r1 and 1 in
  `wave4_p33_pre` r2, all at turn 2. They name four different sections of E as the inserting one.
  None of the four raw results mentions E, so the summariser added it
  (`python scratch/scripts/e_attrib.py`, output in `scratch/e_attrib.out`).

**Then the API** (each response is in `scratch/lex/`):
- **Change records:**
  - the Act's full change record (562 rows, 281 relations, under the 5,000 cap) has the one relation;
  - L's record of what it changed has it;
  - E's record of what it changed has no row for the section. Its nearest row substitutes a range
    of four sections that does not include it.
- **The insertion itself:** provision-level search on L's inserting subsection returns exactly that
  one row. L's own text of that subsection inserts the whole section after an existing one.
- **E's text:** all 34 of its provisions; the section's number occurs in none.

**Conclusion: L inserted the section, as a whole provision. E did not insert it.** No record shows
any later insertion of text into it.

**Therefore these are wrong**, for the integrator and the user; I edited none of them:
- the rubric `p33.json`'s 6338 `_note`, which says the section was inserted by E (agent A owns the
  rubric; no 6338 pattern depends on the year: a search of the file for E's year finds only the
  note);
- the pack's Reading 2, which quotes that note;
- in the pack, the provisions table's "the inserting Act" row, and the year of insertion given in
  the question's part (2) and in the summary of the session's question;
- the `external-apis` skill, line 80, which repeats it as an example;
- SESSION_LOG Session 33's "change-record id mis-expansions" item: the summary it calls a
  mis-expansion gave the right year. One of the "two change-record id mis-expansions" carried
  forward is therefore not one.

**Whether this changes the reading's conclusion** (that the inserted section follows R) is for the
lawyer. The pack note says so and restates nothing.

**Two API traps found, for the skill:**
- `/amendment/section/search` matches the exact provision URL and nothing coarser: a section id
  returns `[]` where its subsections have rows.
- A relation with `changed_provision_url: null` cannot be reached from the changed side at all. This
  section's insertion is such a row.

## The pack edit

- **Where:** one paragraph, "**A point our records leave unclear.**", in Reading 2, after the
  provisions table and before **Question.** It is the only change: `diff
  pack/confirmation_pack.orig.md pack/confirmation_pack.md` shows 11 added lines and nothing else.
  The original's sha1 `2250272c…` matched the main checkout's copy when I began.
- **What it says:** the records point to a later Act. It cites two URLs: L's inserting subsection,
  and E's provision that substituted the range of sections.
- **Both URLs** are string values inside stored tools' `api_calls`, 12 tool calls each
  (`scratch/scripts/url_stored.py`).
- **Text:** `pack/note_text.md`.
- **Checks on the edited copy**, using the integrator's two scripts with only the pack path changed:
  - links: 20 URLs, 0 not found (`verify_pack_links_D.py`; the pack had 18);
  - quotes: 17 shared 6-word runs, all instrument titles, the same 17 as before
    (`verify_pack_quotes_D.py`).
- **Not edited:** the question, the reading, the key and the table.

## Commands behind the numbers

All run from the worktree root, with `PYTHONIOENCODING=utf-8`; `scratch` =
`docs/prepilot-fixes/evidence/seam/batch4/D`.
- `python scratch/scripts/trace6338.py > scratch/trace6338.out`: the stage locator.
- `python scratch/scripts/reports6338.py 2|3 [summaries]`: every turn-2 and turn-3 brief, report and
  answer (and turn-3 summaries), read by hand for both tables.
- `python scratch/scripts/rows_target.py`: 1,212 stored change-record calls; 1 relation touching the
  section; 10 run files.
- `python scratch/scripts/e_attrib.py`: the 4 summaries attributing the insertion to E.
- `python scratch/scripts/pinpoint.py > scratch/pinpoint.out`: the pinpoint trace.
  - 6 stored change-record calls in the four directories (4 at turn 2, 2 at turn 3).
  - The API rows carry the right subsection in 6 of 6.
  - The tool's output lacks it and carries the wrong one in 6 of 6.
  - Every turn-2 summary states the wrong one (4 of 4), and so does every turn-2 report (4 of 4).
  - 2 of the 3 `wave4_b2_post` answers state it.
- `python scratch/scripts/fetch_lex.py` and `fetch_lex2.py`: the 15 API requests.
  `python scratch/scripts/read_lex.py`: rows, dedupe and the provisions read.
- `python scratch/scripts/url_stored.py`: the stored-URL check.
- `python scratch/scripts/verify_pack_links_D.py`, `verify_pack_quotes_D.py`: the pack checks.

## What I did NOT do

- No model call, seam draw, live Worker, server or replay.
- No rubric edit, no pack question edit, no product or tool code.
- The pack edit is not applied to the main checkout: the harness blocked it.
- The Manager-seam test of whether conversation history drives the turn-3 reading was not drawn.
- The explanatory note for L's inserting section was not fetched; L's own text settled the point.

## For the integrator and the user to decide

1. **Apply the pack edit**, by copying `scratch/pack/confirmation_pack.md` over the pack, and copy
   the scratch folder out before removing the worktree.
2. **Correct "no earlier stored rep offered the sequence as a reading"** in the P3.17 row, the
   SESSION_LOG and the hand-read: 2 earlier reps did. And soften "PHASE 2c ... opened a new failure
   at turn 3": not supported.
3. **The rubric `_note`'s inserting Act** (agent A or the user), the pack table, the pack question's
   part (2) and the skill's line 80.
4. **Whether to add a supplementary pack question** (option 1) before the pack is sent.
5. **Whether to book the change-record pinpoint** (option 5) as a new row.
6. **For the skill:** the two `/amendment/section/search` traps above.
