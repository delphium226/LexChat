# Parallel batch 6, agent D: P3.12 and P3.25 measured, with options ($0)

**Base.** The worktree came up on `main` (`a6b4a76`), as in every earlier batch. I had made no
commits, so I ran `git reset --hard 995ef3415ab3b359353fb455b217ab28223e6982` (the integrator's
head, Fix Tracker v36). This note is based on `995ef34`.

**What this is.** Two measurements over the stored evidence, with options for each. There is no
product or tool code; the only commit is this note. Spend **$0**: no model call, no server, no
replay, and no call to LEX, the National Archives or legislation.gov.uk. Every number below comes
from the 57 stored replay directories or the stored copy of LEX's `/openapi.json`
(`evidence/seam/batch4/D/lex/openapi.json`, fetched in batch 4). Every run file used here ran on
the pinned `google/gemini-3.1-pro-preview` (1,935 of 1,951 turns record it; the other 16 record no
model). None of these numbers comes from `glm-5.2:cloud`, the model Thomas tests on.

**Scratch.** The scripts and their outputs are in the gitignored
`docs/prepilot-fixes/evidence/seam/batch6/D/` (`git check-ignore -v` gives `.gitignore:113`), copied
with `cp -r` to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch6/D/`. Each script finds
`server_py/` relative to its own location and asserts that it imports the code it found there. Run
from the main checkout, it therefore reads the main checkout's code, so nothing needs repointing.
Commands below use `D=docs/prepilot-fixes/evidence/seam/batch6/D` and
`E=$PREPILOT_EVIDENCE/replay`, with `PYTHONIOENCODING=utf-8`.

---

## 0. One finding that bears on both rows: `get_legislation_text` never returns a schedule or annex

LEX's `/legislation/text` takes an **`include_schedules`** flag. It defaults to `false`, and the
spec says: *"If False, only sections are returned. If True, sections are returned first, then
schedules."* The executor sends only `{"legislation_id": ...}` (`executor.py`, the
`get_legislation_text` branch), so **every whole-text read the product has ever made was sections
only.** CLAUDE.md's rule ("before concluding the LEX API cannot do something, read `/openapi.json`")
applies here in the other direction: the spec shows a parameter we never send.

Measured over the stored evidence (`python $D/p312_fulltext_schedules.py $E`). Section searches
returned at least one schedule or annex provision for 18 instruments that also have a stored
`get_legislation_text` result. That makes 79 known schedule or annex provisions. **The stored full
text carries 0 of the 79**, whether checked by heading or by opening text. Not one of the 18 full
texts contains an upper-case `SCHEDULE` or `ANNEX` heading. For P3.12's Act the full text is 894,391
characters and ends at the Act's last section; none of the words of the paragraph its row asks about
are in it. Lower bounds on what the flag would add, from the schedule text the corpus happens to
hold:

- P3.2's regulation would go from 47,687 characters to at least 440,035 (×9.2).
- Two SIs have bodies of 1,031 and 1,568 characters, and their schedules hold at least ×7 and ×8
  that. For an instrument like these, a whole-text read is hollow.

**Why it matters.** A Worker that falls back to "the whole text" for a provision that lives in a
schedule or annex gets a document without it. The Worker then reports, accurately as far as it can
see, that the provision is not in the text. That is P3.2's criterion (v) failure (section 1.3).

Per the re-planning protocol, this is a new finding and wants its own row (decision 1).

---

## 1. P3.12: a Schedule paragraph asked for by number

### 1.1 How often a Phase-2 query names a schedule sub-unit, and whether the unit then arrives

Command: `python $D/p312_measure.py $E [--list]`. It covers 5,128 `search_legislation_sections`
calls. The detector is query-only. A **schedule paragraph** query names "Schedule X" anywhere and a
paragraph number anywhere. An **annex chapter** query names "Annex X" and "Chapter Y" (P3.2's
control shape). "Retrieved" means a section-search result on the same `legislation_id` in the same
turn returned the provision whose url ends `/schedule/X` (or `/annex/X`).

| Query names | Calls | Turns | Sessions | Unit in the same call | Unit in the turn, by section search (per turn) |
|---|---|---|---|---|---|
| a schedule **paragraph** | 63 | 10 | 3 (60 of the 63 calls in P3.12's session) | 2 of 63 | 2 of 10 turns |
| a schedule Part / Section / Head | 8 | 4 | 3 | 2 of 8 | 1 of 4 |
| an annex **chapter** | 60 | 39 | 1 (P3.2's session, under two run-file names) | 3 of 60 | 11 of 39 |
| a schedule, with no sub-unit (comparison) | 71 | 42 | 10 | 32 of 71 | 21 of 42 |

- **The two paragraph turns that did get their schedule** are not P3.12's session: they are two
  small instruments, in sessions 6341 and 6367. **P3.12's own Schedule was returned by no stored
  section search, in any directory, for any query.** No query ever named that Schedule without a
  paragraph number, so the comparison row's 32 of 71 says nothing about it.
- **`get_legislation_text` cannot rescue this shape.** For 35 of the 63 paragraph calls, a
  `get_legislation_text` of the same Act followed in the same turn. It reached the Schedule in
  **0**, because the full text carries no schedules (section 0). In every research-mode copy of
  P3.12's turn 7, the Worker fell back to it: 925,155 characters, summarised and then truncated at
  the summary cap (`truncated: true`, 8,054 characters seen).
- **The premise holds: LEX holds a schedule as one provision.** Of the 4,857 section-search rows
  whose `provision_type` is `schedule` (a type that covers annexes), none has a url deeper than
  `/schedule/X` or `/annex/X`.
- **Hand-read** (`python $D/p312_handread.py $E`; output `p312_handread.txt`, gitignored, matter
  text):
  - Draft 1 required "Schedule X" and the paragraph to sit next to each other. It dropped 27
    distinct queries, every one a true match, because the model quotes each term separately or puts
    the paragraph numbers after topical words.
  - Draft 2, the one used above, reads both anywhere in the query. Its drop list is empty, and every
    distinct matched string was read: 44 schedule-paragraph, 7 Part/Section, 17 annex-chapter and 51
    schedule-only.
  - The Part/Section class is adjacency-only on purpose. "Schedule 1, Section 5" in that corpus
    means the Act's s.5, not a part of the Schedule. One of its 7 strings (2 calls) pairs P3.12's
    Schedule with a Part of the Act itself, so it is ambiguous; it moves no conclusion.

### 1.2 Can code cut the sub-unit out once it has the provision?

Command: `python $D/p312_cut_feasibility.py $E`. It runs over every distinct schedule (304) and
annex (19) provision text stored in a section-search result, using the built `tools/provision_hints`
for annexes.

- **Annex chapters: yes.** `provision_hints._cut_annex` cuts 56 of 56 chapter headings cleanly. The
  median chapter is 0.13 of its annex. The chapter P3.2's control turn names comes out of its
  89,133-character annex at **2,494 characters**.
- **Schedule paragraphs: only in one rendering.** LEX marks schedule paragraphs three ways:
  - **`Section N)`** (76 of the 304 schedules): a line-start match is unique for 123 of the 123
    paragraphs tested (paragraphs 1-3).
  - **Bare `N)`** (134 schedules): unique for only 106 of 397, because sub-paragraphs use the same
    marker.
  - **`(N)`** (10 schedules): unique for 17 of 22.
  - **None of these** (84 schedules).

  So a paragraph cut is safe only on the `Section N)` form. Anywhere else, the whole schedule has to
  be handed over, summarised for the query (P1.6's pattern). Stored schedules run from a median of
  5,074 characters to 1,399,168. P3.12's Schedule is not stored, so its marker form is unknown.

### 1.3 P3.2's control turn (export turn 5, run turn 4) in every `p32_6406` directory

Command: `python $D/p312_control_6406.py $E [--queries]`. It grades with the built `stance_grade`
and P3.2's rubric. It covers the 15 reps in `wave4_p32_pre`, `wave4_p33_post`, `wave4_b1_post`,
`wave4_b2_post` and `wave4_b4_post`, all in Conversational mode.

- **What the Worker searched for.** In 15 of 15 reps it searched the regulation for the annex
  chapter the lawyer named: 20 queries name it, usually alongside the article that points to it.
- **What it was given.**
  - **The annex** (one 89K provision) came back from a section search in **2 of 15** reps, never on
    the first call. In 1 of those 2, the summary the Worker saw still carried the chapter's heading.
  - **The whole text.** The Worker called `get_legislation_text` on the regulation in **11 of 15**
    reps. Its text carried **no annex in 11 of 11** (section 0).
- **The control verdict.** The control fails in **9 of 15** by command (by directory: 2, 1, 2, 2
  and 2 of 3). This matches the hand-read counts on P3.2's row except in `wave4_b4_post`, where the
  hand-read records r2 as conditional rather than failing.
  - **7 of the 9** match a "not held / unable to retrieve / cannot verify" pattern. That is P3.12's
    shape, the one criterion (v) forbids.
  - **All 7 of those reps called `get_legislation_text`**, against 4 of the 8 reps that did not
    make the claim.
  - **Neither rep in which the annex arrived** made the not-held claim. Both passed the control.
- **Hand-read:** the 15 control answers' must-not matches, read in
  `$D/p312_control_6406.txt` (gitignored).
- **Reading:** the not-held claim on this turn is what the Worker was handed, a "whole text" with
  no annexes. Section search alone almost never ranks the annex. So criterion (v) needs both:
  - the sub-unit fetched in code (P3.12); and
  - either `get_legislation_text` saying it carries no schedules, or the conversational Worker not
    calling it (P3.25).

### 1.4 Options for P3.12 (what each changes, how it is tested)

- **(a) A code route (Invariant 2), recommended.** In `run_worker_tool`, after a
  `search_legislation_sections` result, code would act when both hold: the query names "Schedule
  X" or "Annex X" with a paragraph, Part or Chapter; and the unit is not in the results. Code then
  fetches that one provision and appends it in a labelled block:
  - annex chapters cut with `_cut_annex`;
  - schedule paragraphs cut only on the `Section N)` form;
  - otherwise the whole schedule, summarised for the query.

  The fetch is either `/legislation/section/search` with the query "Schedule X" at a larger `size`
  (we send 10; the row says 20 ranked P3.12's Schedule for a topical query), or
  `/legislation/section/lookup`, which returns every provision with text. **Which to use needs a
  live LEX probe of payload size first** (the row's probe returned 674 provisions for this Act and
  recorded no size; the stored text record says `number_of_provisions: 1161`; I have not reconciled
  the two). That probe is outside this batch's limits.

  Reach on the stored corpus: 131 calls in 53 turns. In 7 of those calls the unit was already in
  the results, so the route would do nothing there. It would change no other call.

  Tests:
  - a unit test at the `run_worker_tool` seam with a synthetic instrument (`ssi/1901/3`, "Widget
    Order 1901"), proven failing with the route reverted;
  - a dry run over all 5,128 stored section-search calls, listing every call the trigger fires on;
  - the replay below.
- **(b) A per-occurrence line in `section_search_note`.** The line would say that the index holds a
  Schedule as one provision, that a paragraph is reached by retrieving the Schedule, and that
  `get_legislation_text` does not include schedules.
  - It changes the Worker's next call only if the model follows it.
  - Its route is weak. A schedule-only query got the unit in the same call 32 times in 71 for
    other instruments, and P3.12's Schedule was never returned by any query.
  - Unless it also names the whole-text gap, it points the model at `get_legislation_text`, which
    returns no schedule.

  Testable on the seam only as a first-round probe of the next call (Session 22's lesson).
- **(c) Worker prompt phrasing for schedule paragraphs.** Prompt-only (against Invariant 2). It also
  reaches every call the prompt drives, so it needs a first-delegation drift probe (Session 22).
- **(d) Send `include_schedules: true` on `get_legislation_text`.** One field. It removes the
  hollow-text trap for small instruments and EU regulations. For a large Act the schedules sit at
  the tail of a text that already overflows the summary cap: P3.12's 894K of sections were
  truncated before any schedule. So it would not deliver P3.12's paragraphs, and it multiplies
  P3.2's regulation ×9.2.

**Replay figure for the acceptance.**

- **6335, n=3.**
  - Session 18's **$2.52** checks against the stored files: `wave3_p38_pre` reps cost $0.685, $0.944
    and $0.892. Those reps ran in **Research** mode under `legislation_only`.
  - The replay set now records 6335 as Conversational, with turns 6-7 under
    `legislation_and_case_law` (P0.5, P0.6). In that mode the one stored rep (`wave0_conv`, run as
    `legislation_only`) cost **$0.33** for all seven turns, $0.12 of it turn 7.
  - So n=3 in the recorded modes costs about **$1.00-1.50**. $2.52-3.42 is the Research-mode upper
    bound (stored Research reps cost $0.69-1.14).
  - The acceptance also needs a ground truth for paragraphs 42-44 for `replay_report depth`. That
    Schedule's text is in no stored result, so it must be read live first.
- **Criterion (v)** (6406's control turn, n=3).
  - The `p32_6406` script **cut after export turn 5**: median **$0.65** a rep for run turns 1-4, max
    $1.50 (15 stored reps), so about **$2.00**.
  - Or the full script as P3.2's after-column: $5.39-7.50 for n=3 over the five stored directories.
- **Total for P3.12 alone:** about $3.00-3.50, budget $5.

---

## 2. P3.25: the conversational Worker calls `get_legislation_text`, which its prompt forbids

### 2.1 The premise, checked against the code

- **The prompt.** `WORKER_SYSTEM_PROMPT_CONVERSATIONAL` PHASE 2 says *"Do NOT fall back to
  `get_legislation_text`"*. The same prompt then appends `_ENABLING_POWER_RULE` (the recital
  *"arrives in a `get_legislation_text` result"*) and `_IN_FORCE_RULE` (d) (*"the `valid_date` on a
  `get_legislation_text` response"*). So the prompt contradicts itself.
- **The tool list.** `get_worker_tools(research_mode)` takes no chat mode, and returns
  `WORKER_TOOLS` with the tool in it for every legislation Worker. Its only caller is
  `agent_core.py:222`.
- **The census.** `thomas_census.py` re-run: **143 of 1,314** answered conversational turns call it.

### 2.2 What the calls retrieved, whether the answer used it, what it cost, why it was called

Command: `python $D/p325_measure.py $E [--list]`. Built code is imported from the worktree:
`search_scope._recital_in`, `strip_scope_blocks` and `replay_report._without_footer`.

**The calls.** 247 calls in the 143 turns, from 16 sessions. Per turn: 1 call in 95 turns, 2 in 28,
3-9 in 20. By class: 222 on SIs, 20 on EU regulations, 5 on Acts.

- **39 calls failed** with LEX's "Legislation not found". All 39 come from before P3.7 and none
  after: the tool was being used as a held/absent probe, which `lookup_legislation` now does.
- **By era.** Directories run at or after P3.7's build (`475ef57`; each directory's
  `runtime_state.git_head` checked against `git log 475ef57^..995ef34`) give 29 of 483
  conversational turns (6.0%), against 114 of 831 before (13.7%).

**What the 208 successful calls retrieved.**

- **The Worker sees a small text.** Raw median 4,341 characters (max 211,920); the median the Worker
  saw was 2,790. 74 were summarised, 0 truncated and 17 were memo hits.
- **The instruments are small.** `number_of_provisions` has a median of 6, and **115 of 208 calls**
  (55%) were on an instrument with 10 or fewer provisions. A size-10 section search returns every
  provision of such an instrument, schedules included (`python $D/p325_provisions.py $E`).
- **Schedules were missing.** 50 of 208 calls were on an instrument a stored section search shows
  has a schedule or annex (9 instruments). The text carried none of them (section 0).
- **A recital:** in 4 of 208 calls (3 of 183 on SIs).
- **A `valid_date`:** in 92 of 208. It never equals the enactment date.

**Whether the answer used it** (all hand-read in `$D/p325_handread.txt`).

- **The recital.** Its words reached the answer in **1 turn**: P2.3's permitted-branch session
  (6340), in `wave0_conv`, the mode its lawyer used.
- **The valid date.** The answer states it in **2 turns**, both P3.2's control turn, as "the held
  text is up to date to …".
  - My first draft counted 55 calls. On reading them, 55 of 57 hits were the product's own
    code-written currency limb in the Worker report (*"The held text is stated to be up to date to:
    …"*), not the model.
  - The report test now strips scope blocks with the built `strip_scope_blocks`, and the date test
    reads the answer only. The lawyer's footer clause does not name the date.
- **Text only `get_legislation_text` supplied.** I took 8-word runs of the answer that occur in that
  call's text and in no other tool result in the turn, with the instrument's own title removed. They
  occur in **48 turns** (61 calls). By hand:
  - **32 turns use substantive text.** 18 are a commencement instrument's list of commenced
    provisions in 6409, P3.7's evidence session. 9 are an operative list in an SSI in 6374, 3 are
    6383 and 2 are 6406. Ten of the 32 are post-P3.7.
  - **16 turns match only a citation, a title or a URL** that the text happened to contain.

**Why it was called.** The primary reason is what came before the call in the same delegation, by
start time; there are 208 successful calls.

| Primary reason | Calls |
|---|---|
| Straight from `search_legislation`, no section search of the instrument first (against PHASE 2) | 133 |
| After a non-empty section search of the same instrument (16 of these also after a lookup) | 57 |
| The id came from no earlier result (the brief) | 14 |
| After a section search that returned 0 provisions | 3 |
| After a lookup alone | 1 |

- **After P3.7 the reasons shift:** 16 straight from search, 16 after a lookup and a section search,
  2 after a section search, 1 after a lookup.
- **Not-held claims.** Answers saying "not held / not retrieved / unable to retrieve" appear in 28 of
  the 143 turns that call it (20%), against 86 of the other 1,171 conversational turns (7%). This is
  a correlation, not a cause. The case where it is a cause is section 1.3.

**Cost.** A turn that calls it makes a median of 5 tool calls (max 82, pre-P2.7), against 3 for one
that does not. After P3.7 the figures are median 4, max 17. The median recorded turn cost is
$0.092 against $0.076; the 143 turns cost $21.66 together. Thomas's 33-call answer was on GLM. The
pinned model's maximum after P3.7 is 17.

### 2.3 The route a recital and `valid_date` would need without the tool

`python $D/p325_lookup_vs_text.py $E` covers every stored turn, in any mode.

- **The description matches.** In **17 of 17** turns where `lookup_legislation` and
  `get_legislation_text` ran on the same instrument, the lookup's `description` (capped at 600) is
  **identical** to the first 600 characters of `legislation.description` on the text record.
- **Most recitals are in the description.** Of 8 distinct text records carrying a recital, **7**
  carry it in `description`, within its first 600 characters. 1 carries it only in the head of
  `full_text`, which the lookup does not return (P2.3's "1 of 103" again).
- **The lookup tool does not emit `valid_date`.** LEX's `/legislation/lookup` record has it: it is
  in the spec's `Legislation` schema and in the lookup response batch 4 stored. The executor emits
  only title, url, category, enactment_date and description.
- **The gap.** The lookup runs in code only for an instrument the brief names by number
  (`MAX_ROUTED_LOOKUPS = 5`). An instrument met by discovery gets no lookup unless the Worker calls
  the tool. 6340's recital use came that way, straight from search. P3.6 (description on search
  rows) is the other open route.

### 2.4 Options for P3.25

- **(a) Remove the tool from the conversational Worker in code, and re-route the two fields,
  recommended.**
  - **Code.** `get_worker_tools` gains the chat mode, and `run_worker_agent` passes it.
    `lookup_legislation` emits `valid_date`, and for an SI it appends `enabling_power_note` built
    from its record's `description`. `record_currency` and `record_enabling_power` accept the
    lookup.
  - **The prompt.** The conversational prompt's copies of the two shared rules name the lookup, so
    the prompt no longer mentions `get_legislation_text`.
  - **The gap.** For an SI found by discovery, code runs the lookup once for each SI the quick-lookup
    Worker section-searches, bounded like P3.7. Without that, 6340's supported derivation would be
    lost.
  - **What it changes.** 143 of 1,314 turns (29 of 483 after P3.7). The 32 turns with substantive
    text from the tool get it from section search instead, which for 55% of calls returns the whole
    instrument and also returns its schedules. It removes the hollow-text read behind 7 of 7 of P3.2's
    not-held control failures. It loses the 1-in-8 recital that sits only in `full_text`.
- **(b) Keep the tool and cap it in code.** Allow one call per worker run, only on an instrument a
  lookup returned as held, and add a code line on every `get_legislation_text` result saying its
  schedules and annexes are not included.
  - It bounds the 9-call turns and states the gap. It does not remove the contradiction, and the
    133 calls straight from search mostly move to the lookup-first path.
- **(c) Keep the tool and make the prompt consistent.** Replace the prohibition with the conditions
  under which the tool is allowed. This is prompt-only: P2.2 measured this shape at 56%, it is
  against Invariant 2, and it leaves the schedule gap.

**Acceptance for (a), booked after the measurement.**

- **Deterministic tests**, each proven failing with the change reverted (the revert's line count
  stated):
  - the conversational legislation Worker's tool list has no `get_legislation_text`, and the
    research Worker's keeps it;
  - the conversational prompt names no `get_legislation_text`;
  - a synthetic SI's lookup result carries `valid_date` and an `[ENABLING POWER]` block quoting its
    description, screened against every detector (`test_footer_trips_no_detector`).
- **A $0 dry run** of the new lookup block over every stored lookup result, listing every output that
  moves.
- **Replay** (pinned model; a turn's mode is the recorded one):

  | Run | What it must show | Cost, from stored reps |
  |---|---|---|
  | `p37_6409`, n=3 | the commenced-section list still delivered | median $0.42 a rep, about $1.25 |
  | 6340, n=3 | the suppression check: the permitted branch still asserts a supported derivation | $0.07 a rep |
  | `p37r_6374` and `p37r_6383`, n=1 | | $0.22 and $0.30 |
  | `p32_6406` cut after export turn 5, n=3 | shared with P3.12 | about $2 |

  About **$4** in all, or about **$5.50** together with P3.12's 6335 run.

---

## 3. What I did NOT do

- I made no product, tool or test change, and committed only this note.
- No LEX probe:
  - the payload of `/legislation/section/lookup` and of `include_schedules: true` on P3.12's Act and
    P3.2's regulation is unmeasured;
  - the 674-against-1,161 provision count is unreconciled;
  - P3.12's ground truth for paragraphs 42-44 is unread.
- No seam draw or replay. There is no replay figure here beyond prices taken from stored reps.
- I did not edit FIX_PLAN, SESSION_LOG, the tracker, the rubrics or the lawyer pack.
- I did not run `plan_status` or `plan_lint`; nothing they read changed.
- I did not chase the citation-only matches (16 turns, 12 of them 6383 citing its Act's section)
  as a P2.3 matter. They are citations, not derivations.

**Checks.**

- The full suite on `lexchat_test_d` gives **2162 passed** (no code changed). No unit test was
  needed, because nothing was built.
- **The row claims I checked:**
  - P3.12 "a Schedule is ONE provision": holds over 4,857 rows.
  - P3.12 "never ranks the Schedule": holds, 0 of all stored searches.
  - Session 18's $2.52: holds.
  - P3.25's 143 of 1,314: holds.
  - P3.25's premise about the prompt and the tool list: holds (the code at `995ef34`).
  - P2.3's "the recital arrives through `get_legislation_text`": true but not exclusive. 7 of 8
    stored recitals are in the `description` that `lookup_legislation` already returns.

---

## 4. Decisions for the user

1. **Book the `include_schedules` finding (section 0) as its own row?**
   1. **(Recommended) A new row, tracker P1.** A whole-text read silently omits every schedule and
      annex: 0 of 79 known units were carried. On P3.2's control turn this is where the false "not
      held" came from (7 of 7). Its fix is either a code line on every `get_legislation_text` result
      stating the omission, or sending the flag where the text stays small.
   2. **Fold it into P3.12.** P3.12's code route then owns the whole-text gap too.
   3. **Fold it into P3.25.** Removing the tool from the quick-lookup Worker hides the gap there, but
      the research Worker keeps it.
2. **P3.12's lever.**
   1. **(Recommended) The code route (1.4 a).** Fetch the named schedule or annex provision when it is
      missing, cut annex chapters (56 of 56) and `Section N)` paragraphs (123 of 123), otherwise
      hand over the whole schedule summarised. First, a live LEX payload probe, which is free of
      model spend but needs your go-ahead under this batch's limits.
   2. **The `section_search_note` line (1.4 b).** Cheap, but it relies on the model, and the route it
      names did not work for P3.12's Schedule in any stored search.
   3. **Worker prompt phrasing (1.4 c).** Prompt-only. Least preferred.
   4. **`include_schedules: true` (1.4 d).** It fixes the small-instrument and annex case, not P3.12's
      large Act.
3. **P3.25's lever.**
   1. **(Recommended) Remove the tool from the conversational Worker in code** and re-route the
      recital and `valid_date` through `lookup_legislation`. That includes a code lookup for SIs the
      Worker section-searches, so 6340's permitted branch survives.
   2. **Keep it, capped in code** (one per run, only after a lookup), plus the omission line.
   3. **Keep it and make the prompt consistent.** Prompt-only.
4. **The acceptance replays** (about $3-3.50 for P3.12, about $4 for P3.25, about $5.50 together
   with the 6406 control run shared).
   1. **(Recommended) Price them to you after the LEX probe and the build,** run together in one
      sweep with the shared `p32_6406` cut after export turn 5.
   2. **Run P3.12's alone first** (6335 in its recorded Conversational modes, about $1-1.50), because
      P3.2 needs it.
   3. **Read criterion (v) from P3.2's next full after-column** ($5.39-7.50) instead of a cut script.
