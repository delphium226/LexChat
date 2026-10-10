# Batch 13, agent C: P3.38 built (read a not-held or text-less instrument from legislation.gov.uk)

Session 45, parallel batch 13, agent C. **Product change, built and unit-tested; not accepted** (the acceptance is
a replay, priced in §7, and the wording goes to the user first, §4). Spend **$0** in model calls. Live calls: **20
GETs to LEX's `/legislation/proxy`** (user-agreed at launch: up to 40), none to any other host.

## 0. Setup, base and what this note does not contain

- **Base.** The worktree came up on `main` (`a6b4a76`), as in every batch. With no commits of my own I ran
  `git reset --hard 1889abb` (the integrator HEAD). This note and every commit are based on `1889abb`.
- **Branch** `worktree-agent-a927f6f481da9ac14`: `4b4b551` (the build), `5cf9ee5` (tests, and the third trigger
  kind), `047233e` (three tests the mutants asked for), `09c12bc` (the limb's number agreement), and this note.
- **Built shape against the brief.** The brief offered "a tool result or a block". **I built a block, run by code,
  appended to the tool result that triggered it** (decision 1). There is **no new Worker tool, so `executor.py` and
  `schemas.py` are untouched**; the read is its own module. The block reuses P3.12's `[PROVISION FETCHED BY CODE — …]`
  markers (decision 2).
- **Live calls: 20**, all `GET https://lex.lab.i.ai.gov.uk/legislation/proxy/<encoded legislation.gov.uk path>`,
  at least 0.6 s apart. The cap (40) was enforced in code by `tools.lgu_probe.PacedClient`, which counts the lines
  already in the log. Every call is logged (method, URL, status, bytes, ms) in the gitignored
  `evidence/seam/batch13/C/calls.jsonl`: 17 × 200, 2 × 404, 1 × 502, 113–1,080 ms. The bodies are saved under
  `raw/` there.
- **Matter text is not here.** Session ids and turn numbers appear, as in batch 12 F's note. Instrument ids, titles
  and statutory words from sessions are only in the gitignored scratch (`dryrun.txt`, `e2e.txt`, `raw/`,
  `rendered/`, `rendered_blocks/`). All the wording in §4 is rendered on synthetic ids.

## 1. What was built, and every function changed

**The trigger** is the outcome decided at Session 44. It is keyed on the API's own outcome, never on prose:
- a `lookup_legislation` result of `not_held`;
- a `lookup_legislation` result of `held_without_text`;
- a `get_legislation_text` read whose `full_text` is empty or is LEX's one-line "No text content available…";
- a `get_legislation_text` read that LEX answered "Legislation not found".

When one fires, code reads the instrument from legislation.gov.uk through LEX's proxy:
- **Routes:** a secondary instrument is read as made (`/<id>/made/data.xml`), primary legislation as enacted (`/enacted/`).
  Either falls back to the current version (`/<id>/data.xml`) where legislation.gov.uk has no such document.
- **Rendering:** the CLML is rendered to plain text (numbered provisions, schedules, footnotes; metadata and
  editorial commentaries dropped).
- **Hand-over:** the text goes to the Worker in a block after the not-held note. It goes verbatim when it fits the
  same threshold and context budget as any tool result. Otherwise it is summarised for the query, never through
  the shared local cache.
- **Records:** the outcome is recorded in the step's scope log, for the Manager's limb and the lawyer's footer.

**Bounds** (in `agent/tools/published_text.py`):
- one document per route, at most 2 routes, so at most **2 calls per instrument**;
- `READ_TIMEOUT_S` = **15 s** per call, one attempt, no retry;
- `MAX_BYTES` = **8,000,000** read from a body;
- `MAX_READS_PER_REQUEST` = **8 instruments per request**. The slot is reserved before the await, so concurrent
  calls share one read;
- per-request memo on the request config (P3.21's pattern). Nothing is kept past the request.

**Where it is said** (§4 has the exact text):
- the block itself, read by the Worker;
- one-line notes for a read that returned no text, read by the Worker;
- the routed-lookup brief, which carries the block after P3.7's lookup block. Its NOT HELD and HELD WITHOUT TEXT
  sentences change only when text follows;
- the quick-lookup Worker's suffix, which carries the block;
- P2.4's not-held note on a text read. Only its last clause changes, and only when text was read;
- a Manager-facing limb in `worker_scope_block`;
- one lawyer-facing footer sentence.

**Functions changed or added** (batch 13's lesson). Every one of these is mine alone in this batch:
- `src/utils/published_text.py` (new): `normalise_id`, `trigger`, `routes`, `page_url`, `parse_published`
  (`_Renderer`, `_xml_root`), `label_for`, `_index_state`, `_currency_sentence`, `published_block`,
  `published_line`, `record_published`, `handed_in_run`, `blocks_in`, `has_published_text`, `published_limb`,
  `published_footer_clause`.
- `src/agent/tools/published_text.py` (new): `proxy_url`, `_client`, `_request_memo`, `_get`, `_read`,
  `read_published_text`.
- `src/agent/agent_shared.py`:
  - new: `published_text_route` and `_published_recital`;
  - **`run_worker_tool`**: the route is called after `record_lookup` and before summarisation. P2.4's note and
    P2.3's enabling block are swapped where the read makes them false, and the block is appended after `not_held`.
    The memo entry stores the read's log entries, and a memo hit re-records them.
- `src/utils/instrument_lookup.py`: `routed_lookup_block` (appends `blocks_in` of each result), `section_search_lookup`
  (suffix carries the block) and `lookup_brief_block` (the two variant sentences).
- `src/utils/search_scope.py`:
  - `not_held_note`: new `text_read` argument, "" by default, which is byte for byte the old note;
  - `worker_scope_block`: one limb added after `_lookup_limb`;
  - `_lookup_footer_clause`: appends `published_footer_clause`. This reaches all four footers through it.
  - **F's functions (`_currency_limb`, the extent rule) are untouched.**
- Tests:
  - `tests/test_published_text.py` (new, 85 tests);
  - `tests/conftest.py`: `_published_text_offline`, which refuses the read's client, as P3.21's fixture does;
  - `tests/test_search_scope.py`: `_published_wording_variants` and `_published_changed_notes` join
    `test_footer_trips_no_detector`;
  - `tests/test_case_law_gap.py`: one assertion. The not-held retrieval now also records the attempted read
    (failed offline).

**Two findings changed the design while building**, both from the dry run and the live probes:
1. **A text read LEX answered "Legislation not found" is its own kind, `read_not_found`.** It is said as "this
   index's text read gave no text for X under that id", never "this index lacks X". The stored text reads LEX
   answered not found name 5 ids:
   - the regnal ids of 2 Acts LEX holds as stub records (batch 12 F's side finding: 2 Acts, 4 reads);
   - a model-built calendar form of one of those Acts;
   - one SSI the index lacks;
   - the model-built `uksi/` id in point 2.

   legislation.gov.uk publishes a document under all 5.
2. **The block asks the Worker to check the title.** One stored text read was of a model-built id: the SSI's year
   and number under `uksi/`. legislation.gov.uk publishes that as an unrelated UK SI, and the read returns it. The
   block names the title legislation.gov.uk gave, straight after the label, and says "Check that its title is the
   instrument the question is about before relying on it." This is P3.7's held-branch rule.

## 2. Measured before and after building (all $0)

**Live shapes** (`probe.py`; `raw/`; 20 calls):
- **legislation.gov.uk's CLML passes through the proxy unchanged.** All 9 of batch 12 F's census SSIs came back
  as made with their text (200; 12–205 KB of XML).
- **All 5 Acts in the dry run read as enacted** (30–882 KB). A calendar id for a pre-1963 Act is answered with its
  regnal document.
- **`/enacted/` on an SSI returns its made document**, and `/made/` behaves the same way the other round. So the
  version label is read from the document's own `DocumentURI`, not from the path asked for.
- **A 1970s UK SI's `/made/data.xml` is a 3 KB metadata stub** with an "Original PDF" alternative and no body.
  That is the `pdf_only` outcome.
- **The proxy has two "no such document" answers:**
  - **404** with `{"detail":"Legislation not found: <path>"}` (a number not yet used);
  - **502** wrapping the upstream error (`"External API error: Client error '400 Bad Request' …"`, a number out of
    range).

  Only these two count as absence. A bare route 404 (`{"detail":"Not Found"}`), any other 502 and any 5xx are a
  failed read (tested), because reading those as absence would state a falsehood about every instrument at once.

**Dry run over every stored input the trigger reads** (`dryrun.py`). It uses the BUILT `trigger`. **It reads all
70 replay directories, none excluded, so the counts include the newest ones.**
- **Stored inputs:** 1,246 calls (679 text reads, 567 lookups).
- **208 calls would trigger a read** (4 of them memo hits), in 178 run-turns across sessions 6341, 6363, 6373,
  6382, 6383, 6409 and 6410, plus their scripted runs.
  - By kind: lookup `not_held` 85, lookup `no_text` 40, text read `no_text` 33, text read `read_not_found` 50.
  - By chat mode: 183 calls conversational, 24 Deep Research, 1 Research.
- **15 distinct ids:**
  - 10 are in P3.31's census, **all 10 present with their as-made text**;
  - 5 are Acts outside the census, **5 of 5 read as enacted live**.
  - So **15 of 15 return text**.
- **The per-request cap:** at most 6 distinct trigger ids in one run-turn (`dryrun_stats.py`: 156 turns with 1, 21
  with 2, 1 with 6), so the cap of 8 binds on no stored request.
- **The pointer back (`earlier`)** would fire twice: 2 delegations met the same id twice through different tools.

**Every triggered id through the built seam, served offline** from the saved documents (`e2e.py`; summariser
stubbed; `run_worker_tool` with a synthetic not-held or text-less result; full table in `e2e.txt`):
- **At the 8,000-character fallback** (every stored replay ran there):
  - **5 of 15 go whole**: the commencement-sized SSIs, 2.6–5.8 K characters of text, each block 3.9–7.3 K;
  - 10 are summarised: 12.9 K–413 K characters of text.
- **At 200,000** (the pinned model with a warm context-length cache): **13 of 15 go whole**. Only the two large
  1920s/1960s Acts (360 K and 413 K) are summarised.

The 6373 instrument (27 K) is summarised at 8,000, and so are four of the six 6382 instruments (13.9 K, 19.2 K,
27 K, 90.8 K).
That bears on the acceptance (§7, decision 3).

**What moves.** Every one of those 208 stored results would carry a block after the result, all 15 ids with text.
For a routed lookup, the brief carries it too. The other changes:
- the lookup brief's two sentences on those turns;
- P2.4's note on 50 text reads;
- the Manager's limb and the lawyer's footer on 178 run-turns;
- and, where the preamble states a power and no other record does, P2.3's forbidding block becomes the permitting
  block. That happens for every triggered SSI read whose recital `recital_window` finds.

Nothing else moves: the 1,038 other lookups and text reads trigger nothing.

**Input forms no stored run contains, tested on synthetic input instead** (all in `test_published_text.py`):
- a PDF-only instrument (its live shape probed);
- every route absent (`not_published`; its live shapes probed);
- the current-version fallback;
- a body over the byte cap;
- a 200 that is not a CLML document, and a DOCTYPE or entity declaration;
- a timeout and a transport error;
- the per-request cap reached;
- a memo hit;
- concurrent reads of one id;
- an id or type this route does not read (`eur/`: no call, no line);
- a regnal id;
- a title with square brackets;
- a recital the index record already states (left as it is);
- a preamble with no recital (permits nothing);
- an Act (never an enabling-power block).

**Not tested anywhere:** a Welsh or Northern Irish instrument, an EU instrument (not read, by design), a revised
document carrying `Commentaries` live (only synthetic), and a schedule-only document.

## 3. Checks behind the claims

- **Suite** (`TEST_DATABASE_URL=…/lexchat_test_c`, `python -m pytest -q`): **3,464 passed** at `09c12bc`. The base
  was 3,379; the 85 added are this row's. The suite ran before my last commit; the note commit changes no code.
- **Revert** (`revert.py`): every changed src file put back to `1889abb` and the two new modules deleted. That
  **removes 1,066 src lines and restores 7**. The P3.38 tests then fail at import (`conftest.py` imports the read
  module): 1 collection error. That proves nothing about behaviour, so:
- **Single-site mutants** (`mutants.py`): one per guard and cleaning step, **61 mutants, 61 caught, 0 survived**.
  The control was run first and passed (411 tests). The first run left 3 survivors, each now caught by a test added
  in `047233e`:
  - a bodiless document with prelims read as text;
  - `handed_in_run` ignoring a failed read;
  - `blocks_in` picking up P3.12's real block, whose header carries a legislation.gov.uk URL.

  `mutants_final.txt` lists each mutant with its failing count.
- **Wording screen** (`screen.py`, and the same assertions in `test_footer_trips_no_detector`). **303 renderings**
  of every block, line, limb and footer clause. They cover 3 ids, 3 kinds, 3 versions, schedules present or absent,
  title present or absent, whole or summary, and every no-text outcome and reason. The screen runs them against:
  - `NEG_ASSERTED`, `NOT_FOUND`, `IN_FORCE_CLAIM`, `_CUR_DISCLOSED`, `NEG_TERMS`, `NEG_LIMITS`;
  - `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `HALT_LITERAL`, `HALT_PARAPHRASE`, `HALT_AS_TIMEOUT`, `OPENER_VOCAB`;
  - `derivation_claims`, `_without_footer`, and per sentence the commencement, currency and `negcurrency` detectors.

  **0 trips: passes.** The first draft tripped 3 of them (`NEG_ASSERTED`, `NEG_BLAMED_INDEX`, `IN_FORCE_CLAIM`):
  - "this index does not hold" tripped `NEG_ASSERTED` and `NEG_BLAMED_INDEX`;
  - "not this index's" tripped `NEG_BLAMED_INDEX`;
  - "whether it is in force today" tripped `IN_FORCE_CLAIM`;
  - "Report it as held in this index" tripped `NEG_BLAMED_INDEX` (through "search … in this index").

  Each was reworded.
- **The two notes the row changes** (P2.4's not-held note, P3.7's brief block) were never clean of the detectors:
  they say "no record" and "NOT HELD" by design. So the screen requires each variant to **trip no detector its
  original did not**: passes, 5 variants.
- **Graders that read what changed** (the batch 7/8 lesson):
  - **`replay_report lookup` (P3.7, exit-1 set)** reads the lookup's `raw_result`, the prose and `LK_FOOTER`.
    `raw_result` is unchanged (the block is appended to `final_result` only). `LK_FOOTER` still matches: the new
    sentence comes after "looked up by its number", tested round trip with `_earlier_lookups`.
  - `_FRESH_FOOTER` is anchored before the clauses, so it is unaffected.
  - **`strip_scope_blocks`** removes an echoed block (`_FETCHED_BLOCK`, `_TOOL_BLOCK`).
  - `CORPUS_LEAK_MARKERS` already lists the markers.
  - **`depth --seams`** strips the block like P3.12's.
  - **`paragraph_restore.handed_paragraphs`** never reads it, because its lead matches neither of P3.12's leads
    (tested).
  - `route_trace.py` prints its header on a quick-lookup section search, distinguishable by its opening.
  - **No grader yet scores P3.38's own bar** (says "read from legislation.gov.uk", answers the need). It is
    hand-read (decision 4).

## 4. The wording, exactly as built (synthetic ids; for the user before merge)

`<text>` stands for the rendered instrument or its summary. Each variant below is printed by `render_wording.py`
(output `wording_rendered.md` in the scratch).

**A. The block (Worker-facing), by index state** (as made, schedules present, whole):

> [PROVISION FETCHED BY CODE — this index lacks SSI 1901/3 (The Widget Order 1901), so code read its text from
> legislation.gov.uk, the official publisher, through the LEX API: the version as made with its schedules, 2,618
> characters. Check that its title is the instrument the question is about before relying on it. Below is the
> whole of it. This text comes from legislation.gov.uk, a different source from the index: cite it as
> https://www.legislation.gov.uk/ssi/1901/3/made, and say in the report that it was read from legislation.gov.uk
> because the index lacks it. The version as made shows no later amendment or revocation and says nothing about the
> instrument's status today.]
> \<text>
> [/PROVISION FETCHED BY CODE]

- **Held without text** (lookup, or an empty text read): the opening is "this index holds the record of SSI 1901/3
  (The Widget Order 1901) but none of its text, so code read …" and the reason is "because the index holds none of
  its text."
- **A text read LEX answered not found:** the opening is "this index's text read gave no text for SSI 1901/3 (The
  Widget Order 1901) under that id, so code read …" and the reason is "because the index's text read gave none."
- **Variable parts:**
  - an Act reads "the version as enacted", and the closing sentence says "The version as enacted shows …";
  - a fallback reads "legislation.gov.uk's current version (it publishes no version as made or enacted of it)", and
    the closing sentence becomes "This text by itself says nothing about the instrument's status today.";
  - with no schedule, "(it has no schedule)" replaces "with its schedules";
  - with no title, the bracketed title is left out;
  - a summary replaces "Below is the whole of it." with "It is longer than one result hands over whole, so below is
    a summary of that retrieved text, condensed for this research question. A provision the summary leaves out is
    still part of the retrieved text. Quote its words only from text shown verbatim."

**B. One-line notes for a read that returned no text** (Worker-facing). Each opens with the same index-state
clause, shown for not held:
- **not published:** "[PROVISION FETCHED BY CODE — this index lacks SSI 1901/3, and code asked legislation.gov.uk for
  its text: legislation.gov.uk returned no document under ssi/1901/3 either, so its text could not be checked here.
  That says nothing about whether the citation is accurate.]"
- **scan only:** "[… — this index lacks SSI 1901/3, and legislation.gov.uk publishes SSI 1901/3 only as a scanned PDF
  (\<pdf url>), which code cannot read, so its text could not be checked here.]"
- **failed:** "[… — this index lacks SSI 1901/3, and code's read of its text from legislation.gov.uk did not complete
  (\<reason>), so its text could not be checked here. That says nothing about the instrument.]". The reason is one
  of:
  - "no reply";
  - "the document was too large to read";
  - "the page was not a legislation document";
  - otherwise "the read did not complete". This doubles up as "did not complete (the read did not complete)"
    (decision 5).
- **cap:** "[… — this index lacks SSI 1901/3, and code did not read its text from legislation.gov.uk: this request has
  already read 8 instruments from there, the most it reads, so its text could not be checked here.]"
- **earlier in the run:** "[… — this index lacks SSI 1901/3; code read its text from legislation.gov.uk earlier in
  this research, and that text was handed over there.]"

**C. The routed brief (P3.7's block; Worker-facing). It changes only when text follows it.**
- **NOT HELD.** Old: "… so a search for its title or number will not find it and its text cannot be read here.
  Report it as not held in this index, not as not found by a search. … What it changes can still be retrieved: …".
  New: "… so a search for its title or number will not find it and its text cannot be read from this index; code
  read its text from legislation.gov.uk instead, and that text follows this block. Report it as not held in this
  index, not as not found by a search, and say that its text was read from legislation.gov.uk. … What it changes
  can also be retrieved: …".
- **HELD WITHOUT TEXT.** Old: "… so a search inside it returns nothing. Report it as held with no text available
  here, never as not found. …". New: "… so a search inside it returns nothing; code read its text from
  legislation.gov.uk instead, and that text follows this block. Report it as a record this index holds without its
  text, never as not found, and say that its text was read from legislation.gov.uk. …". The record's description
  sentence is kept.

**D. P2.4's not-held note on a text read (Worker-facing). Its last instruction only.** Old: "Say plainly that this
index does not hold it and that its contents could not be checked here." New, with text below: "Say plainly that
this index does not hold it, and that its text below was read from legislation.gov.uk instead." New, text handed
earlier in the run: "…, and that its text was read from legislation.gov.uk earlier in this research." The sentence
before ("If you built this id yourself, the id format may be at fault…") is kept.

**E. P2.3, where the read's preamble states the power and no record already does:** the permitting block, with
the source named "legislation.gov.uk's text of ssi/1901/3, read by code" (P3.31's `stored_enabling_note` pattern).

**F. The Manager's limb** (in `worker_scope_block`, straight after P3.7's lookup line):

> Read from legislation.gov.uk by code, because the index lacks the text: SSI 1901/3 (the version as made). The
> report may state and cite what that text provides, attributed to legislation.gov.uk, and the answer must say that
> it was read from there. That changes nothing about what this index holds, and a version as made or enacted shows
> no later amendment or revocation and says nothing about an instrument's status today. Asked legislation.gov.uk for
> the text, and none was read: SSI 1901/4. Its text could not be checked here.

**G. The lawyer's footer** (one sentence, after P3.7's lookup clause, in every footer that carries that clause):

> *Search scope: no ranked search of the legislation index was run for this reply. SSI 1901/3 was looked up by its
> number and is not held in this index, which is incomplete; that does not show whether the number is accurate.
> The text of SSI 1901/3 (as made) was read from legislation.gov.uk.*

- **No lookup ran** (a text read): the footer still carries "The text of SSI 1901/3 (as made) and 1901 asp 1 (as
  enacted) was read from legislation.gov.uk."
- **A failed read** adds nothing to the footer.

**Other code texts about the same instrument, checked against it** (the batch 8 lesson):
- **Changed where they would contradict it:** P3.7's brief (C), P2.4's note (D) and P2.3's forbidding block (E).
- **Left as they are, and true beside it:**
  - P3.7's `_lookup_limb` and footer clause, which say the index does not hold the instrument. That stays true, and
    the row's bar requires it to stay.
  - P3.7's lookup tool description in `schemas.py`.
  - The prompts' "NOT HELD IS NOT A WRONG CITATION".
  - P3.12's lines about an instrument without text in the index ("this index holds no text for …"): these are
    about the index's provision list, and stay true.
- **One tension is left for the user** (decision 6). `_lookup_limb` tells the Manager to "Report one held without
  text as held with no text available here". The new limb follows it and says the text was read from
  legislation.gov.uk. "Here" reads as the index, but the two sit side by side.

## 5. Contradictions found in other agents' territory

None touched. F changes `_currency_limb` and the extent rule in `search_scope.py`. I changed only `not_held_note`,
`worker_scope_block` (one limb) and `_lookup_footer_clause`. The two diffs touch different hunks.

## 6. The regnal-id 404 and P3.12's exact-paragraph route (the row's "Also")

- **The regnal-id 404.** It is not fixed at LEX: its text endpoint still 404s on those ids. But it is now met. The
  404 triggers a read (`read_not_found`), and the 4 stored reads' Acts are all published by legislation.gov.uk
  (live, 2 of 2 distinct regnal ids). Re-asking LEX under the calendar form was not built (decision 7).
- **P3.12's exact-paragraph route** (batch 12 A: 61 of 61 stored schedule-paragraph requests exact through the
  proxy, "booked here") **was not built in this batch**. It needs its own trigger, at P3.12's seam rather than at
  not-held, and P3.12's integration is agent B's file this batch (decision 8).

## 7. The acceptance, priced ($0 spent; nothing run)

**Turns, from the row.**
- **Script `p37_6409`** carries export turns 7–11 and the control turn 2 (a held Act named by number). Its other
  turn, 1, is in the script too.
- **Script `p37_6373`** carries turns 2–3, and turn 1 with them.
- **Session 6410** runs turns 1–2.
- **The 6382/6383 slot:** I recommend **6383 t1 through script `p37r_6383`**. That script also carries turn 2, a
  held SSI named by number, which is **the held-SSI control**.

All five sessions are FAIL in the frozen classification, so **n=3 each** (Invariant 4).

**Price** (`price.py`, from every stored run of the same scripts on the pinned Gemini; `price.txt`):

| Run | Stored cost per rep | n=3 at stored mean | n=3 at stored max +20% |
|---|---|---|---|
| `p37_6409` | $0.30–0.52, mean $0.37 latest | $1.11 | $1.87 |
| `p37_6373` | $0.12–0.35 | $0.78 | $1.26 |
| 6410 | $0.11–0.13 | $0.36 | $0.47 |
| `p37r_6383` | $0.27–0.30 | $0.87 | $1.08 |
| **Total** | | **$3.12** | **$4.68** |

- **My estimate is about $3.60.**
- **The added cost:** each read puts the instrument into the Worker's context (2.6–7 K characters for the
  commencement SSIs), plus one flash summariser call for each summarised text.
- **Up to about $5.40 with one capped runaway** (P4.10: about $0.76 each).
- **Choosing 6382 t1 instead** adds $0.64–1.23 a rep, $1.9–3.7 at n=3: six instruments, four of them summarised at
  8,000.
- **The sweep also makes live legislation.gov.uk reads through LEX's proxy:** free, about 2–4 a run.

**Graders:**
- the exit-1 set, `lookup` among them: P3.7's slots must still PASS;
- P3.38's own bar by hand, as booked on the row: every not-held or stub slot reads the text, says it was read from
  legislation.gov.uk, and answers the need (6409 t11 states the terms; 6373 t2 answers with a provision cited); no
  quoted term is absent from the text read; the P3.7 footer still says the index does not hold it.

**One caution, measured not guessed** (decision 3). Every stored replay ran at the 8,000 fallback. At 8,000 the
6373 instrument (27 K) is **summarised**, so 6373 t2–t3 ("is it mentioned in it") is answered from a summary
condensed for the question. 6409's two instruments (2.6 K and 5.8 K) go whole.

## 8. What I did not do

- **No model call, seam draw or replay; no server.**
- **`seam_replay worker --dry-run` does not rebuild the block.** Its `routed_lookup_block` runs the bare LEX
  executor, not `run_worker_tool`, so a seam rebuild of a routed brief lacks the text. Making it do so would need
  live reads or stored documents in the seam tool. Not built: an integrator drawing a P3.38 seam must know it.
- **Not changed:** the Worker prompts and `schemas.py` (no prompt line names the read), `executor.py`, and
  `CACHEABLE_TOOLS`. The read is not a tool, and its text never reaches the cache.
- **Not built:** a `replay_report` grader for P3.38's bar, the exact-paragraph route, and a LEX retry of a regnal
  id under its calendar form.
- **Not fixed:** the dry run's model-built `uksi/` id for an SSI is read as the unrelated UK SI. The block names
  its title and asks the Worker to check it; it does not refuse it.
- **No FIX_PLAN, SESSION_LOG, tracker or lasting-doc edit.**

## 9. Decisions for the user

1. **How the text reaches the Worker.**
   (a) **Recommended, built:** code reads it and appends a block to the tool result that triggered it. A routed
   lookup's block rides into the brief; the quick-lookup Worker's goes with its section search. The Worker has
   nothing to remember to call (Invariant 2).
   (b) A new Worker tool (`read_published_text`), named by the not-held sentences. The Worker could choose when to
   read, but would read at a rate.
   (c) Make `get_legislation_text` fall back to legislation.gov.uk itself. This misses not-held lookups and the
   quick-lookup Worker, which has no text tool (P3.25).
2. **The block's markers.**
   (a) **Recommended, built:** reuse P3.12's `[PROVISION FETCHED BY CODE — …]`. Every strip, leak marker and seam
   grader already handles it, and its lead never matches P3.12's.
   (b) A new marker (`[TEXT FROM LEGISLATION.GOV.UK — …]`). Clearer to read, but `_TOOL_BLOCK`, `_FETCHED_BLOCK`,
   `_BARE_TAG`, `CORPUS_LEAK_MARKERS` and `depth --seams` would each need widening, and a missed one leaks the block
   to a lawyer.
3. **Size: what goes whole.**
   (a) **Recommended, built:** the same threshold and context budget as any tool result. At a warm cache (200 K)
   13 of 15 stored instruments go whole; at the 8,000 fallback 5 of 15 do, and the rest are summarised for the
   question.
   (b) A fixed allowance for this text (e.g. 40,000 characters) whatever the cold fallback. 6373's instrument and
   all but the largest of 6382's would then go whole in a cold replay too. It costs context per read.
   (c) Over the threshold, the provision headings plus the provisions whose words match the question, instead of a
   summary (P3.12's batch 10 pattern). More code, and the question is a long brief here, not a short query.
4. **A grader for P3.38's bar.**
   (a) **Recommended:** hand-read the acceptance (33 graded slots at n=3, controls included), then decide.
   (b) Build `replay_report published` first: says "legislation.gov.uk", quotes only terms in the text read. It
   needs a careful-reader validation both ways before any rate is quoted.
5. **"did not complete (the read did not complete)".** This is the failed line's wording for an unnamed reason
   (an HTTP error).
   (a) **Recommended:** reword the fallback reason to "an error" ("did not complete (an error)").
   (b) Keep it as built.
6. **The held-without-text tension in `_lookup_limb`** ("Report one held without text as held with no text
   available here", beside a limb saying the text was read from legislation.gov.uk).
   (a) **Recommended:** change "here" to "in this index" in that one sentence. One word, same meaning, removes the
   tension.
   (b) Leave it.
7. **The regnal-id 404 at LEX.**
   (a) **Recommended:** leave it met by the legislation.gov.uk read (built).
   (b) Also re-ask LEX's text endpoint under the calendar form before reading elsewhere. One more LEX call, and it
   does not help the not-held SSIs.
8. **P3.12's exact-paragraph route.**
   (a) **Recommended:** book it as its own build at P3.12's seam, after B's P3.12 changes merge, reusing this read
   module (`proxy_url`, the absence forms, the memo, the cap).
   (b) Drop it from P3.38's row; P3.12's acceptance does not need it (batch 12 A).
9. **The acceptance run.**
   (a) **Recommended:** `p37_6409`, `p37_6373`, 6410 and `p37r_6383`, n=3 each, about $3.60 (up to about $5.40),
   graded by the exit-1 set and by hand against the row's bar.
   (b) Swap `p37r_6383` for 6382 t1: about $2–3 more, and four of its six instruments are summarised at 8,000.

## 10. The user's decisions applied (C5, C6)

The user approved the wording with changes 5 and 6 and took every other recommendation (C1–C4, C7, C8). The
acceptance run is not being run this session.

- **C5, the failed line's fallback reason** (`published_line`, used for an HTTP error):
  - before: "… code's read of its text from legislation.gov.uk did not complete (the read did not complete), so its
    text could not be checked here. That says nothing about the instrument.]"
  - after: "[PROVISION FETCHED BY CODE — this index lacks SSI 1901/3, and code's read of its text from
    legislation.gov.uk did not complete (an error), so its text could not be checked here. That says nothing about
    the instrument.]"
- **C6, one sentence of `_lookup_limb`** (`search_scope.py`):
  - before: "Report one held without text as held with no text available here, never as not found."
  - after: "Report one held without text as held with no text available in this index, never as not found."

**Tests.** Three assertions in `test_published_text.py` now pin "did not complete (an error)". A new assertion
pins the limb sentence (none did before). `_published_changed_notes` gains the limb pair, so the detector screen
covers the change.

**Checks, all with the built code** (`TEST_DATABASE_URL=…/lexchat_test_c`, `PYTHONIOENCODING=utf-8`):
- **Wording screen** (`screen.py`): 303 renderings, **0 trips**.
- **Changed notes:** 6 before/after pairs (the limb now among them), **no detector tripped by a variant that its
  original did not trip**.
- **Mutants** (`mutants.py`, control first: 411 passed): **63 of 63 caught**, 0 survived. That is the 61 before plus:
  - `q06`: the limb says "here" again;
  - `u28`: the old fallback reason.

  Each mutant's failing count is in `mutants_c56.txt`.
- **Suite:** **3,464 passed**.
