# Parallel batch 3, agent C: P4.17 measured with options

Session 35, 2026-10-01. Branch `worktree-agent-aa6a8c040f1ee7b32`. The worktree came up on `main`
(`a6b4a76`), not on the integrator's head, so before any work I ran `git reset --hard 72dc84e`
(no commits had been made). **Measured against the tree at `72dc84e`**: agent A's grader change
(`NEG_BLAMED_INDEX`) and agent B's case-law footer sentence are not in it. Where B's sentence
matters I simulated it with agent D's wording (`notes/batch2_D.md` 1.6), and say so.

Spend **$0**: no model call, no replay, no server. **No product code and no tool was changed or
added.** This note is the only file committed. Full suite on `lexchat_test_c`: **2077 passed**.

This note gives counts, directories, reps and turns. It quotes no question, answer, search term or
instrument from a session. The scripts are in the gitignored `$C` =
`$PREPILOT_EVIDENCE/seam/batch3/C/` (every one $0, no network); those that print matter text say
so in their docstring. Every command is run from `server_py/` with
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence` and `PYTHONIOENCODING=utf-8`;
`$R` is `$PREPILOT_EVIDENCE/replay`.

## The row's acceptance, and whether it is met

**P4.17's acceptance is "to be booked after the measurement".** This note is that measurement; a
proposed acceptance is in section 8. **Not met and not built.**

## 1. How many turns have the shape

`python $C/p417_shape.py --list` (all 55 directories, 1,814 answered turns).

The brief's shape (research type `legislation_only` or `legislation_and_case_law`, at least one
`search_legislation_sections` and/or `lookup_legislation` run, no `search_legislation`) matches
**88 turns**, all in directories taken since P2.2. They split in two:

- **59 ran a lookup and no section search.** Every one carries a footer (P2.8's carried line 44,
  P3.7's lookup line 15). Not this row's shape.
- **29 ran at least one section search.** That is the row's shape. Footers at the time:
  - **none: 11** (all `legislation_only`, all Conversational);
  - P2.4's standalone case-law line: 13 (all 6370, hybrid: P4.15's 13 turns);
  - P3.7's "for this reply, … looked up" line: 4;
  - P3.7's "no ranked search" line: 1 (`wave4_p37` 6373 r1 t3, the MISATTRIBUTED turn P3.7 fixed
    in `0c91fb6`).

**None of the 29 footers names a section search.** The 11 with no footer at all: 8 since P3.7
(D's count, confirmed: `wave4_b1_post` 1, `wave4_p315_pre` 1, `wave4_p32_pre` 2,
`wave4_p33_post` 1, `wave4_p37` 2, `wave4_p37b` 1) and 3 before it (`wave2_p28` 1,
`wave2_p28_smoke` 1, `wave3_p35` 1; all 6409). Sessions: p32_6406 4, 6409 3, p37_6373 2,
p37_6409 2.

## 2. What each of the 11 answers says, and what the graders say

Read by hand with `python $C/p417_read.py` (prints matter text). "Absent" means the answer states
that something is missing, unretrievable or not made.

| directory | session r t | ran | what the answer says is missing | `negatives` |
|---|---|---|---|---|
| `wave2_p28` | 6409 r3 t4 | 1 section search, 1 change record | nothing (a positive commencement answer) | not enrolled |
| `wave2_p28_smoke` | 6409 r1 t2 | the same | that no further commencement instrument is recorded "in the available sources" (attributed to the sources) | not enrolled |
| `wave3_p35` | 6409 r2 t3 | the same | that the remaining provisions have not been commenced: a negative about the law, unattributed | **FAIL** (terms, index) |
| `wave4_b1_post` | p32_6406 r2 t7 | 2 lookups (held), 2 section searches, 2 change records | that the instrument's "retrieved text" does not specify a provision | not enrolled |
| `wave4_p315_pre` | p37_6373 r1 t3 | 1 lookup (held), 2 section searches | that the instrument does not mention the two subjects asked about, unattributed | not enrolled |
| `wave4_p32_pre` | p32_6406 r3 t3 | 1 lookup, 1 section search | nothing | not enrolled |
| `wave4_p32_pre` | p32_6406 r3 t11 | 1 lookup, 1 section search | nothing (an interpretation) | not enrolled |
| `wave4_p33_post` | p32_6406 r1 t4 | 2 lookups, 5 section searches, 1 full text | that a part of an annex "could not be retrieved from the legislation index" (section 3) | **FAIL** (terms) |
| `wave4_p37` | p37_6373 r3 t3 | 1 lookup (held), 2 section searches | as `wave4_p315_pre` r1 t3, plus an earlier turn's not-held outcome restated in the prose ("not held in this index") | not enrolled |
| `wave4_p37` | p37_6409 r1 t2 | 1 lookup, 1 section search, 1 full text | nothing | not enrolled |
| `wave4_p37b` | p37_6409 r2 t2 | 1 lookup, 1 change record, 1 section search | a limit ("cannot be verified from the available sources"), not a negative | not enrolled |

- **6 of the 11 state that something is absent; `negatives` enrols 2, and both FAIL.** The other
  4 are outside `NEG_ASSERTED`: three claims that an instrument *does not mention / does not
  specify* something, each drawn from the top-ranked results of section searches (the claim
  `section_search_note` tells the Worker not to make), and one "no other … recorded" (the `no`
  limb allows only "relevant" or "specific" between `no` and its noun). Widening `NEG_ASSERTED` to reach the first form
  is P2.2's first-draft trap (it cannot tell them from statements of retrieved law), so the
  acceptance below relies on a hand-read for them.
- **`nosearch` is blind to the shape by construction.** A section search counts as searching
  (`_LEG_SEARCH_TOOLS`), so every one of the 11 has `searched_now` true and the line read as
  `none`, and its only possible verdict there is MISATTRIBUTED for a carried or lookup line. All
  11 read `ok`. (`python -m tools.replay_report --dir $R/<dir> nosearch`.)
- **`scoperecord` never sees the shape.** It examines only delegations that ran
  `search_legislation` (`scope_record_gap` returns None otherwise). Its exit codes on the nine
  directories are unrelated to the shape (only `wave3_p35` exits 1, 21 missing searches, the
  pre-P2.9 memo loss).
- Cross-check by the command: `python -m tools.replay_report --dir $R/wave4_p33_post negatives`
  gives p32_6406 r1 t4 `NO n/a yes - no no FAIL` (5 failing in the directory: this turn and 6370's
  4); `--dir $R/wave3_p35 negatives` gives 6409 r2 t3 `NO n/a NO - no no FAIL` (1 failing).

## 3. The one failing turn D found (`wave4_p33_post` p32_6406 r1 t4)

`python $C/p417_target.py` (prints instrument ids).

- The turn ran 5 section searches over two instruments and one full-text retrieval of the second.
  Two of the section queries name the annex the answer calls unretrievable; **neither returned a
  provision of that annex in its top 10.** The full text was summarised from 49,737 to 1,048
  characters, and the annex is named 12 times in the raw text and 2 times in the summary.
- The Worker's scope block (agent-facing, stripped before rendering) told the Manager it had
  "searched within 2 instrument(s) … (ranked extracts, not the full contents of any of them)".
  The Manager still wrote that the annex could not be retrieved from the index, and named no
  search terms. The lawyer saw no footer.
- That is P3.12's shape (a part of a schedule or annex asked for by name does not rank, though the
  index holds the instrument; D's 1.5 records it as held). **A footer can make this negative
  explained; it cannot make it true.** Correcting it belongs to P3.12.

## 4. What the silence drops besides the scope sentence

`python $C/p417_clauses.py`. Every footer clause after P2.2's (P2.3's enabling power, P3.5's
change records, P2.5's currency, P3.1's section budget, P3.7's lookup, P2.4's case law) rides on
the fresh footer, the carried line, or the lookup and case-law lines. On a section-search turn the
first two never fire, and the lookup line speaks only for a not-held or held-without-text
instrument. So on the 29 turns, HEAD drops clauses the same builders would otherwise state:

- **P2.3's enabling-power clause: 18 turns.**
- **P2.5's currency clause: 9 turns.** That includes the four 6409 commencement answers
  (`wave2_p28`, `wave2_p28_smoke`, `wave3_p35`, `wave4_p37b` r2 t2), which state what is in force.
- **P3.5's change-record clause: 7 turns.**

These are the code's own disclosures, gated on structure. A section-search-only turn loses them
because of a gate, not because of a decision about those clauses.

## 5. The options, dry-run over every stored answer

### 5.1 Method: the product's own builders, validated

D's P4.15 dry run spliced a string into stored footers. A section line has no stored footer to
splice into on 11 of the 29 turns, so I rebuilt each turn's search record from the audit with the
**product's own recorders** (`record_search`, `record_relations`, `record_currency`, … in
`run_worker_tool`'s order, memo path included). Each footer is then rebuilt with the **product's
own chain** (`answer_scope_footer` → `carried_scope_footer` → `lookup_scope_footer` →
`case_law_scope_footer`, with the history the product saw) (`$C/p417_rebuild.py`).

**Validation** (`python $C/p417_rebuild.py`): footer present or absent agrees with the stored
answer on **every answered turn in every directory taken since P2.8**. On the four most recent
directories the rebuilt footer is byte-identical except for the order of quoted terms (parallel
tool calls finish in a different order from the one the audit records):

| directory | answered | exact | exact except term order |
|---|---|---|---|
| `wave4_b1_post` | 78 | 65 | 75 |
| `wave4_p33_post` | 78 | 65 | 72 |
| `wave4_p32_pre` | 45 | 38 | 44 |
| `wave4_p37c` | 30 | 29 | 29 |

The remaining differences were read. Two are P4.14's echoed footers (the stored "footer" is the
model's copy). The others differ in one listed query, or are a footer written by older code.
Older directories differ by design (clauses added later).

The harness was checked against D's result before use: the simulated (a) variant edits **204**
answers and moves exactly **13 `negatives` verdicts FAIL to PASS and nothing else**, as D
recorded (`python $C/p417_diff.py $C/dry a`).

### 5.2 Option (d), the prototype

`$C/p417_option_d.py` (scratch, not product code). It fires when the turn recorded at least one
`search_legislation_sections` and no `search_legislation`, and is slotted after the carried line
and before the lookup line, so it carries the lookup clause itself. On the Deep Research path it
comes after the fresh footer. It is one line:

> *Search scope: for this reply the text of ssi/1901/1 in the legislation index was searched for
> "widget licence", "gadget". A search within an instrument returns the provisions that best
> match its terms, not the whole instrument, so a provision missing from its results may still be
> in the instrument and in this index.<section-budget, enabling, relations, currency, lookup and
> case-law clauses, as the fresh footer carries them>*

**Wording, checked against the detectors** (`python $C/p417_option_d.py`). The new sentence trips
**`NEG_BLAMED_INDEX` only**. With the head, the line also satisfies `_names_search_terms`,
`NEG_TERMS` and the legacy `NEGATIVE_EXPLAINED`, as the fresh footer does. It trips no
`NEG_ASSERTED`, `NOT_FOUND`, `NEG_BLAMED_USER`, `IN_FORCE_CLAIM`, halt detector, `NEG_LIMITS`,
`SCOTS_CASELAW_GAP`, derivation, currency or case-law-gap detector. **My first wording ("a
provision this search did not return …") tripped `NEG_ASSERTED`**, through its "search … did not
return" limb. "Ranked" was avoided because it trips `NEG_LIMITS`. "Not found in this index" was
avoided because it is false in P3.12's case: the provision may be held, and the sentence says so.

**Edits** (`python $C/p417_dryrun.py $C/dry`): **29 answers**, exactly the 29 turns of the shape:
11 gain a line (308 to 915 characters) and 18 have theirs replaced (6370's hybrid line goes from
about 600-700 characters to 1,151-1,248). Every one of the 29 edits was read
(`python $C/p417_lines.py`, prints matter text). **No other turn's footer changes**, including
through the history (`python $C/p417_downstream.py`: 29 changed, 0 outside the shape).

**Couplings, on the 29 real lines** (`python $C/p417_couplings.py`). Each holds on 29 of 29:
- one line, one `*Search scope:` opener;
- P4.14's echo strip removes it whole, and so does an echo followed by the real line;
- `replay_report._without_footer` removes it whole;
- **P2.8's parse (`_earlier_footers`) does not read it**, so it is never carried forward, and a
  later no-search turn's carried line is unchanged by it (except where it restates a lookup);
- P3.7's `_earlier_lookups` reads back exactly the lookup outcomes it states (5 lines carry one),
  as it does for the lookup line today.

### 5.3 What (d) moves: every verdict

`python $C/p417_diff.py $C/dry d` (against the stored base: 14 of 210 outputs change), and
`python $C/p417_diff.py $C/dry ad a` (with (a) already in, which is the tree after agent B's merge:
12 of 441 outputs change). Exit codes: `python $C/p417_rc.py $C/dry d` and `… ad`.

| what moves | (d) alone | (d) after (a) |
|---|---|---|
| `negatives` FAIL to PASS, legislation-only shape | 2: `wave3_p35` 6409 r2 t3, `wave4_p33_post` p32_6406 r1 t4 | the same 2 |
| `negatives` FAIL to PASS, 6370 (case-law negatives) | 9 (`wave4_p33_pre` 3, `wave4_p33_post` 4, `wave4_b1_post` 2) | 0 ((a) already passes them) |
| `negatives` `loose` cell only (no verdict) | 3 PASS rows in `wave4_p37b` | the same |
| `nosearch` MISATTRIBUTED 1 to 0 | `wave4_p37` 6373 r1 t3 | the same |
| `summary`: legacy in-force counter | +1 on 9 turns | the same |
| `summary`: consulted-not-cited | -1 on 4 turns | the same |
| `summary`: turns citing none | -1 on 2 turns | the same |
| `summary`: legacy bare negatives | -1 on 1 turn | the same |
| every other subcommand, every other directory | nothing | nothing |

Exit codes: `negatives` 1 to 0 on `wave3_p35`, `wave4_b1_post`, `wave4_p33_post` and
`wave4_p33_pre`; `nosearch` 1 to 0 on `wave4_p37`. **Nothing exits worse.** After (a) and (d)
together, `negatives` also exits 0 on `wave2_p24_ab`, `wave4_p41_pre` and `wave4_p46_pre` (that is
(a)). `wave4_p33_post` reaches 0 only with both: (a) leaves p32_6406 r1 t4 failing.

Read, each of the moves:
- **The 2 legislation-only passes are what the row asks for**, and each is circular by
  construction, as P2.2's were: the line names the terms and attributes the miss. The model column
  stays `no` on both. One of them (`wave4_p33_post`) is P3.12's false negative (section 3). The
  line tells the lawyer the provision "may still be in the instrument and in this index", which is
  true and is the qualification that turn lacked, but the negative stays false.
- **The 9 6370 passes are a sentence about legislation crediting a negative about case law**:
  D's hazard for (a), in reverse. It is moot once (a) is in (the right column), because (a)'s own
  sentence passes them first. That is one reason to build (d) after (a), not before.
- **The `nosearch` move is not (d)'s.** The stored line on that turn came from P3.7's first code
  (`475ef57`); HEAD (`0c91fb6` onward) already writes the "for this reply," line there, which the
  rebuild reproduces, and (d) then replaces it. It would show as a move in any rebuild at HEAD.
- **The `summary` moves are grader artefacts, and every fresh footer already causes them.**
  P2.5's currency clause opens "Whether legislation is in force is …", which the legacy
  `IN_FORCE_CLAIM` counter (deliberately left alone, `replay_report.py` near line 2181) counts.
  `_source_cited` reads an instrument id in the footer as a citation. In the product the footer is
  appended after the source block is built, so the sources rail is unaffected.

`dbare` (the same line with only the lookup and case-law clauses: `python $C/p417_diff.py $C/dry
dbare`) moves the same `negatives`, `nosearch` and `loose` cells. Of the `summary` moves it keeps
only the citation ones on `wave4_p32_pre` and the bare-negative one on `wave4_p33_post`. It does
not bring the three clauses of section 4.

### 5.4 P2.8's silence, which (d) reverses

The `_SEARCH_TOOLS` comment records why P2.8 left this turn silent: the carried line opens "no
search of the legislation index was run for this reply", which **would be false** after a section
search. Silence was the only safe output of that builder, not a judgement that the turn should say
nothing. (d) states the section searches that did run, so that reason does not apply to it.
`test_a_turn_that_searched_gets_no_carried_line` still holds (the carried line stays empty), but
its docstring ("so it stays silent") would need amending. **The cost P2.8's user decision weighed
does apply:** like the fresh footer and the carried line, (d) fires on positive answers too. On
the 11 turns with no footer, 4 are positive by hand (section 2). The user kept that trade for
P2.8 ("do not reopen without new evidence"). (d) asks for the same trade on a new turn type, so it
is the user's call.

## 6. Option (e): leave the product silent, grade the shape another way

Three ways, none recommended:
- **Drop section-search-only turns from `negatives`' denominator.** That hides `wave4_p33_post`
  r1 t4, which the hand-read says is a real unexplained negative. It moves the grader away from
  the hand-read.
- **Credit the Worker's scope block** ("Searched within N instrument(s) …") as attribution. That
  grades text the lawyer never reads.
- **A report-only listing of the shape for hand-reading.** This is honest, but it changes nothing
  the lawyer reads. Four of the six absence statements in section 2 are invisible to every grader,
  and the three clauses of section 4 stay dropped.

None of the three changes what a lawyer reads, and Invariant 2 points away from all of them.

## 7. Option (f): what else the evidence shows

- **(f1) (d) without the clauses** (`dbare`): the same verdict moves, a shorter line, and the 18,
  9 and 7 dropped disclosures of section 4 stay dropped.
- **(f2) One builder rather than two.** `answer_scope_footer` could take section searches with a
  different head. The output is the same; a separate builder keeps `_FRESH_FOOTER`'s anchored
  parse untouched, which is the safer place to put it.
- **(f3) Do not let P2.8 carry the line.** The carried line says a result not found in "those
  searches" was "not found in this index". For a search within an instrument that is false in
  P3.12's case, so `_FRESH_FOOTER` should stay unable to read it (pinned by a test, as the
  lookup line's non-carry is). Stored cost: no later turn's footer would differ (section 5.2).
- **(f4) Found, not booked: P2.5's currency clause contradicts P3.5's clause on 27 stored
  footers.** When a change record was consulted but held no commencement or repeal relation,
  `_currency_footer_clause` takes its else branch and says "no change record was consulted for
  this answer", while `_relations_footer_clause` on the same line says the records were "consulted
  directly". `python $C/p417_contra.py`: 27 of 455 stored footers carrying the relations clause,
  in 11 directories (most recently `wave4_p37c` 4, `wave4_p37b` 5, `wave4_p315_pre` 3). HEAD's
  code reproduces it (5.1). (d) would put it on one more turn (`wave3_p35` 6409 r2 t3). It is a
  P2.5 wording defect, independent of this row.
- **(f5) The grader cannot enrol "does not mention / does not specify"** (section 2). Not a
  change to make: the acceptance should hand-read every turn of the shape instead.

## 8. Recommendation: (d), built after P4.15 (a)

- It is the only option that changes what a lawyer reads, and Invariant 2 points there.
- It qualifies all six absence statements of section 2, the four no grader sees included. For
  the three "does not mention" claims it states the exact limit `section_search_note` already
  gives the Worker.
- It restores P2.3's, P2.5's and P3.5's disclosures to 18, 9 and 7 turns.
- **Its dry run moves only what it should once (a) is in:** two `negatives` verdicts, both turns
  of the shape. Nothing exits worse; the other moves are artefacts, each read and explained above.

Built as: a builder in `search_scope.py` slotted after the carried line and before the lookup
line on the Manager path, and after the fresh footer on the Deep Research path. It is **not
suppressed by `scope_unknown`** (like the fresh footer: it states only searches this turn
recorded; no stored turn of the shape has a failed delegation or a peer consult). It is not read
by `_FRESH_FOOTER`, and it carries the same clause set as the fresh footer.

**Proposed acceptance for P4.17** (deterministic, then live):
1. **Unit tests at the new builder, each proven to fail with the change reverted** (the note to say
   how many lines the revert removed):
   - it fires if and only if the turn recorded a `search_legislation_sections` and no
     `search_legislation`, on both paths;
   - it names the instruments, and the terms in `_listed_terms`' form;
   - it carries the section-budget, enabling, relations, currency, lookup and case-law clauses;
   - it is one `*Search scope: …*` line, removed whole by `strip_answer_footer` (including P4.14's
     echo-then-real case) and by `replay_report._without_footer`;
   - **P2.8's round trip extended:** `_earlier_footers` does not read it, and a later no-search
     turn's carried line is unchanged by it;
   - `_earlier_lookups` reads its lookup clause;
   - its new sentence trips no detector but `NEG_BLAMED_INDEX` (beside
     `test_footer_trips_no_detector`).
2. **The rebuild dry run over every stored directory** puts the line on exactly the 29 stored turns
   of the shape and changes no other turn's footer. Every verdict it moves is one listed in
   section 5.3: after (a), `negatives` FAIL to PASS on the two turns named there, and otherwise
   only `summary`'s artefacts.
3. **Live, in the first after-column with a turn of the shape** (`wave4_b2_post` carries
   p32_6406 x3, which had 4 such turns in 3 of its 9 stored reps, and 6370 x3, which had 13 over
   9 stored reps):
   - every turn of the shape carries the line and no other turn does. That needs one grader line
     (in `nosearch` or a new subcommand): a section line on a turn that ran `search_legislation`,
     or ran no section search, is MISATTRIBUTED;
   - `negatives` passes every negative on a turn of the shape, **and each is read by hand**. The
     pass is circular by construction, so the model column is printed and the hand-read decides,
     including the "does not mention" claims the grader cannot enrol;
   - no other exit-1 subcommand is worse than in the before-column.

   If no turn of the shape occurs, 1 and 2 stand and 3 carries to the next after-column.
   **Invariant 1:** the line explains a negative and never converts one; P4.17 passing does not
   tick P3.12.

## What I did not do

- Build anything. No product code, no tool, no test, no rubric edit. The (d) builder exists only
  as a scratch prototype in `$C`.
- Run any model, replay, seam draw or server.
- Rebuild against agent B's actual constant. (a) is simulated with D's wording, which the brief
  says B builds; if B's final sentence differs, the right-hand column of 5.3 should be re-run
  (the wording is the `ATTR` constant in `$C/p417_dryrun.py`).
- Count shape turns in the four pre-P2.2 directories (`baseline`, `wave1`, `wave2_p21`,
  `wave2_p22`). They carry no footer of any kind, and their turns record no research type the
  shape test can read.
- Book (f4). It is the integrator's or the user's to book.

## For the integrator and the user to decide

- **Whether to build (d)**: the row was booked "measure first", and (d) reverses P2.8's silence for
  this turn type at P2.8's own cost (a line on positive answers). Recommended, after (a).
- Whether (d) carries the full clause set (recommended) or only the lookup and case-law clauses
  (`dbare`).
- Whether the line names instruments by id (as P3.5's clause does, and as the prototype does) or
  by citation label (as P3.7's clause does).
- Whether to book (f4), P2.5's contradicting else-branch (27 stored footers).
- The proposed acceptance (section 8), including the one grader line it needs.
- Copying: my scratch scripts were written in the worktree's own gitignored `evidence/seam/`
  (an isolated worktree cannot write the shared path directly) and copied to
  `$PREPILOT_EVIDENCE/seam/batch3/C/` before I finished.
