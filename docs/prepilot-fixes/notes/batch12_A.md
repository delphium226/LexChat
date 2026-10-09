# Parallel batch 12, agent A: P3.12, the seam relay read, the wrong-pinpoint rate, the exact-paragraph route probed, and a jurisdiction candidate ($0)

**Branch:** `worktree-agent-aff4f776be97c42f5`. **Base:** `<INTEGRATOR_HEAD>` = `a99e4d4`. The worktree came up
on `main` (`a6b4a76`) with no commits, so I ran `git reset --hard a99e4d4` before anything else. No other
commit reached my branch while I worked.

**Commits:**

- `9c74183` this note, first version (no product code: section 6 says why);
- `560cf8e` fix(prepilot): P3.12 candidate, a jurisdiction selects the law, not the provisions (quick-lookup
  Worker prompt + tests), built after the integrator's second relay (section 10), **not merged: its wording is
  the user's** (decision 11.2);
- this commit: the note, sections 10 and 11 added.

**Spend:** $0 in model spend. No model call, seam draw, replay or server. The seam draws this note reads were
the integrator's (relayed by message: four composition-seam draws, $0.1866; then eight as-sent draws, $0.3677). **Live calls: 12 of the 20 agreed** (10 through LEX's
`GET /legislation/proxy`, 2 direct to legislation.gov.uk), every one a GET, at least 0.6 s apart (minimum gap
measured 0.600 s), capped at 20 in code (`lgucall.py` refuses the 21st, redirect hops counted; none occurred),
each logged (method, URL, status, bytes, time) in `call_log.jsonl`. Every stored run read here ran on the pinned
`google/gemini-3.1-pro-preview` and was summarised at the 8,000-character fallback; no number comes from
`glm-5.2:cloud`.

**Tests:** full suite **3043 passed** on `lexchat_test_a` with `TEST_DATABASE_URL` set (`pytest_full2.txt`;
3017 at the base, `pytest_full.txt`, plus the candidate's 26).

**Scratch:** my worktree's gitignored `docs/prepilot-fixes/evidence/seam/batch12/A/` (`git check-ignore -v`:
`.gitignore:113`), copied at the end to `C:/Projects/LexChat/docs/prepilot-fixes/evidence/seam/batch12/A/`.
Commands below run from that folder unless they say `server_py/`, with `PYTHONIOENCODING=utf-8` and
`PREPILOT_EVIDENCE=C:/Projects/LexChat/docs/prepilot-fixes/evidence`. Files that print brief, query, answer or
statutory text (`compare_b12.txt`, `dump_pinpoints.txt`, `para_requests.*`, `tally_route.txt`,
`pin_detector.txt`, `raw/`, `schB1_lex.txt`) are scratch only.

**Built shape against the brief.** The first relay's draws did not point at one candidate (section 6), so the
first version built nothing; the second relay's as-sent draws pointed at the brief's jurisdiction phrase and the
integrator asked for a Worker-prompt line, built in `560cf8e` (section 10). The prompt-swapped payloads are
built by a scratch driver (`draw_swap.py`), not by `--at-rev`, because `--at-rev` on the candidate would also
carry P3.31's prompt and tool changes (section 10.3). Also not named by the brief: a $0
prototype of a wrong-pinpoint check (scratch only, section 4.2) and a one-field diagnostic payload for a further
draw (`seam_b12_rep3_noscot.json`, decision 1).

---

## 1. The integrator's four draws, read by hand

Drawn by the integrator at `a99e4d4`, default composition seam (`seam_replay worker --run <file> --turn 7 --reps
1 --print`: every recorded result in one round, no tools offered, a closing "Compose your report now" message,
uncapped), n=1 each. Outputs: gitignored `evidence/seam/batch12/integrator/`. The rule is P3.12's: each of
paragraphs 42, 43 and 44 cited with its facts (`DEPTH_TRUTH`: 42 the winding-up bar; 43 the security and
legal-process limbs and consent or permission; 44 when the interim moratorium runs).

| Payload | `depth` | By hand | 42 | 43 | 44 | Wrong pinpoint |
|---|---|---|---|---|---|---|
| `r2brief` (batch 11 A's brief swap: `wave4_b10_sweep` rep 1's results, r2's narrow brief, no tail lever) | PARTIAL (42 coarse) | **DELIVERED** | 42(2)-(3), 42(4), with its facts | (2)-(3), (4)-(5), (6): every limb | (1)-(5), with its trigger | none |
| `wave4_b11_sweep` rep 1 | PARTIAL | PARTIAL | 42(2)-(3), 42(4) | (5) and (6) only: no security limb | (1)-(2) | none |
| rep 2 | PARTIAL | PARTIAL | named, facts, no sub-paragraph | (5), (6), and "(1)" cited for "restricts legal processes" (loose: (1) is the paragraph's application line) | named, facts | none (one loose) |
| rep 3 | PARTIAL | PARTIAL | **not named** | (5), (6), and a clause naming the other limbs (security among them) | (1)-(5), with an aside on (6)-(7)'s content cited to (1)-(5) (loose) | none (one loose) |

- **The integrator's reading holds, checked against the statutory text** (`p312_truth.txt`, batch 7 B): 4 of 4
  name 43 and 44, 3 of 4 name 42, no draw attaches one paragraph's content to another's number.
- **`depth`'s "42 coarse" on `r2brief` is a grader false negative.** The paragraph-42 fact regex
  (`replay_report._P312_WINDING_UP`) reads "winding up" and not "wind up", and the draw wrote "an order to wind
  up a company". Extending it to `wind(?:ing)?[- ]?up` moves **1 of 48** stored 6335 turn-7 texts (that draw,
  PARTIAL to DELIVERED, which is the hand verdict) and nothing else (`server_py/`: `python
  <scratch>/wind_up_grader.py`, `wind_up_grader.txt`). Not applied: `replay_report.py` is the integrator's
  (decision 4).

## 2. The four payloads compared (the brief, the block, the rounds after it, the output budget)

**Command** (from `server_py/`): `python <scratch>/compare_b12.py > <scratch>/compare_b12.txt`, which builds each
payload with the BUILT `tools.seam_replay.worker_messages` and `worker_as_sent_messages` and groups the
recorded tools into rounds with the product's own `tool_rounds`.

| | `r2brief` | sweep rep 1 | sweep rep 2 | sweep rep 3 |
|---|---|---|---|---|
| Mode | conversational, legislation and case law | the same | the same | the same |
| System prompt | the quick-lookup Worker, sha1 `5f77f22422` | identical | identical | identical |
| Brief | 313 chars, **narrowed to the restriction and enforcement limbs, no jurisdiction** | 250, broad, **"for Scotland"** | 292, broad, **"Jurisdiction: for Scotland"** | 250, broad, **"for Scotland"** (rep 1's brief word for word) |
| Section query | the Schedule + one word (rep 1 of batch 10) | the Schedule + two words, one a jurisdiction | the Schedule + one word, then a second query naming the three paragraphs | the Schedule + one word |
| Block | MATCHED, 42, 43, 44 cut clean; batch 10's tail (names no paragraph); 7,853 chars | MATCHED, 42, 43, 44 and a span from paragraph 112 (the jurisdiction word matched its heading); named tail; 11,546 | MATCHED, named tail, 8,113; **then a CUT block** of 42, 43, 44 (4,629) | MATCHED, named tail, 8,113 |
| Block position | last in result 3, 28 chars before its end | the same | the same, both blocks | the same |
| Rounds after the block | 0 (the block's round is the last) | 0 | **1** (the change record, 5,285 chars) | 0 |
| Composition-seam payload | 8 msgs, 44,476 chars | 9, 52,858 | 10, 69,005 | 8, 44,268 |
| As-sent payload (recorded rounds, tools offered, no closing message) | 8, 44,429 | 9, 52,811 | 12, 68,958 | 8, 44,221 |
| Live report body (before the scope block) | (rep 1's own: 1,003 chars, 4 sentences) | **1,065 chars, 4 sentences** | **1,618, 6** | **866, 3** |
| Seam draw body | 1,487, 6 | 1,666, 6 | 1,637, 6 | 1,892, 8 |
| Live outcome by hand | (rep 1's own: 43(6) alone) | 43(6), 44 | **wrong pinpoints** (43's limbs under "42") | 43(6) alone |
| Seam outcome by hand | DELIVERED | PARTIAL | PARTIAL | PARTIAL |

**What the comparison shows.**

1. **On the same payload, the composition seam writes more than the live Worker did, in all three sweep reps.**
   Live, reps 1 and 3 wrote 3-4 sentences and one or two paragraphs; at the seam the same retrievals gave 6-8
   sentences and all three paragraphs (rep 1) or 43 and 44 (rep 3). Live rep 2 attached 43's content to "42"; at
   the seam it did not. Seam bodies run 1.0 to 2.2 times the live bodies on the same payload (1,666 / 1,065;
   1,637 / 1,618; 1,892 / 866). This is now the third time a P3.12 lever moved the composition seam and not the
   live runs (batch 10's tail: seam 2 of 2, live 0 of 1; batch 11's named tail: seam 1 of 2, live 0 of 3). The
   composition seam differs from the live call in four ways: all results in one flattened round, no tools
   offered, a closing "Compose your report now from the results above" message, and today's date line; the live
   call ends on the last tool result with the Worker's tools offered and `max_tokens` 32,000. **The as-sent seam
   (`--as-sent`) rebuilds the live call** and has never been drawn on P3.12's turn; decision 1 proposes it.
   Fidelity check: the one recorded call with a `sent_chars` on these files (rep 2's round-1 empty completion)
   records 20,652 against 22,323 rebuilt with `--at-rev recorded --date recorded --round 1`, a 1,671-character
   (8%) difference I did not trace; the final calls carry no recorded size.
2. **The brief's jurisdiction phrase goes with a report of 43's Scots limbs alone.** Over every stored Worker-seam
   draw on this turn (13, `dump_pinpoints.txt`), reporting 43's security, hire-purchase or forfeiture limbs:

   | Brief | Draws | 43's other limbs reported | How |
   |---|---|---|---|
   | narrowed, no jurisdiction (r2's brief: batch 10's two payloads, batch 11's `r2_named`, today's `r2brief`) | 6 | **6** | in their own sentence |
   | broad, "for Scotland" (batch 10 rep 1's payload, batch 11's `rep1_named`, today's three sweep payloads) | 7 | **2** | only in the prompt's "what the other subsections provide" clause |

   On one payload (batch 10 rep 1's results) the brief alone flips it: rep 1's own brief 0 of 2 (batch 11's
   draws), r2's brief 1 of 1 (today). The two briefs differ in two ways at once (the jurisdiction phrase and the
   narrowing), and n is 1-2 per payload, so this does not say which; the one-field payload in decision 1
   separates them. Live, every stored turn-7 brief that names Scotland (4: `b10` rep 1, `b11` reps 1-3) gave
   43(6) or 43(5)-(6) as the centre of the answer (4 of 4).
3. **The block is not what differs.** Its position is identical in all four; `r2brief` delivered with batch 10's
   tail, which names no paragraph, and the three sweep payloads, which carry the named tail, did not.
4. **The quick-lookup budget (2-5 sentences, or a short bullet list) is not binding at the seam.** The one
   delivering draw is 6 sentences, 1,487 chars, and fits all three paragraphs; the Scotland-brief draws spent
   their sentences on the Scots limbs and the case law. Live, the reports are shorter still (3-6 sentences), and
   whether the budget binds there is exactly what the composition seam cannot show (point 1).

## 3. What the four draws settle, and what they do not

- **Settled:** the recorded payloads of the three sweep reps are not, at the composition seam, what made the live
  answers narrow or mis-numbered: the same retrievals compose to all three paragraphs (rep 1), 43 and 44 (rep
  3), and correct numbering (rep 2). The block is the same in delivering and failing payloads. A narrow brief
  with no jurisdiction phrase delivered; the three Scotland briefs did not.
- **Not settled:** (a) whether the live narrowness comes from the call's shape (rounds, tools offered, no closing
  message) or from the draw; (b) whether the jurisdiction phrase or the narrowing is the brief's active part; (c)
  whether the wrong pinpoint reproduces at all (0 of 1 seam draws on rep 2's payload). All three are n=1 per
  payload. **So the composition seam is the wrong instrument for the next lever choice on this row**: a Worker-facing
  lever measured on it has twice not transferred.

## 4. The wrong-pinpoint rate, by hand, over every stored 6335 turn 7

**Command:** `python dump_pinpoints.py > dump_pinpoints.txt`: every sentence that cites a schedule paragraph, in
every stored turn-7 answer and Worker report (17 run files over all **66** replay directories: 17 answers, 18
reports) and every stored Worker-seam draw (13). 48 texts, 182 paragraph citations; read by hand against the
statutory text of paragraphs 42-44 and the Schedule's stored LEX text (`schB1_lex.txt`, batch 7 B's
`raw/129.json`).

**Wrong** = a paragraph or sub-paragraph number given to content that is in another paragraph. **Loose** = a
range or the paragraph's application line cited for content in another sub-paragraph of the same paragraph.

| Texts | Citing a schedule paragraph with content | Wrong | Loose |
|---|---|---|---|
| live answers (17) | 14 | **2**: `wave4_b11_sweep` rep 2 (43's legal-process limb, and in its report also the security limb, given to "42"); `wave4_b8_sweep` rep 3 ("para 6", which is the Schedule's qualification-of-administrator paragraph, cited for the moratorium arising on administration) | 1 (`b8` rep 3, "42(1)-(4)" for 42(4)'s exceptions) |
| live answers citing 42, 43 or 44 with content | 13 | **1** (`b11` rep 2) | 1 |
| live Worker reports (18) | the same two reports carry the same two wrong pinpoints (the Manager copied them) | 2 | 1 |
| Worker-seam draws (13) | 13 | **0** | 2 (today's rep 2 "43(1)"; today's rep 3, 44(6)-(7)'s content cited to "44(1)-(5)") |

So: **2 of 14 live answers (14%) carry a wrong schedule pinpoint; 1 of 13 (8%) on paragraphs 42-44; 0 of 13 seam
draws.** Both live cases came from the Worker's report, and the Manager kept them. No answer before the route
existed (`baseline` to `wave3_p38_pre`) carried one, but those answers cited 42-44 mostly as not retrieved.

### 4.1 Paragraphs handed over and then dropped

In the four live answers whose Worker had 42, 43 and 44 verbatim (`b10` rep 1, `b11` reps 1-3), **every one
leaves out at least one paragraph it was handed**: 42 is absent in 3 (`b10` r1, `b11` r1, r3), 44 in 3 (`b10` r1,
`b11` r2, r3), and 43 is reduced to (6) or (5)-(6) in all 4.

### 4.2 A $0 prototype: could code find a wrong pinpoint? (scratch only, not product code)

`python pin_detector.py > pin_detector.txt`: for each sentence citing exactly one of 42, 43, 44, the words it
shares with each paragraph's *distinctive* words (in that paragraph's cut and in no other of the three; five
letters or more, a short stop list). Flagged where it shares 3 or more with another paragraph and none with its
own. **80 single-paragraph sentences over the 48 texts: 2 flagged, both the real case** (`b11` rep 2's answer, 9
words of 43's; its report, 10 words); **0 false positives; the one miss is out of scope** (`b8` rep 3's "para 6"
is outside the three cut paragraphs). Caveat: the threshold of 3 was set on this data (a threshold of 1 flagged
11, 9 of them noise from one shared common word such as "paragraphs"), there is one true case, and it is one
Schedule. It shows the check is possible; it is not evidence that it generalises.

## 5. The exact-paragraph route, probed live (12 calls)

**Commands:** `python probe_paras.py 1` to `4` (each call through `lgucall.get`), then `python parse_para.py
raw/<n>.bin [<paragraph> schB1_lex.txt <server_py>]` (stdlib `xml.etree`, a DTD refused, commentary references
and footnotes left out) and `python tally_route.py > tally_route.txt`. The proxy URL is built exactly as the
product's `commencement_dates.proxy_url` (the whole path URL-encoded into one segment).

| # | Path (legislation.gov.uk, `.../data.xml`) | Via | Status | Bytes | What came back |
|---|---|---|---|---|---|
| 1, 2 | the row's Schedule, paragraph 43 | direct, proxy | 200, 200 | 65,082, 65,082 | **byte-identical** (sha1 `2abc5d69928f` both) |
| 3, 4 | paragraphs 42, 44 | proxy | 200 | 63,290, 70,742 | one paragraph each |
| 5 | paragraph 130 (named by a stored query; see below) | proxy | **404** | 84 | LEX's own JSON: `{"detail":"Legislation not found: ..."}` |
| 6, 12 | P3.22's session's schedule, paragraph 105 | proxy, direct | 200, 200 | 66,366, 66,366 | **byte-identical** (sha1 `019a37d6b573`) |
| 7 | a stored request's Schedule 2, paragraph 2 | proxy | 200 | 19,071 | one paragraph |
| 8 | a stored request's Schedule A1, paragraph 14 | proxy | 200 | 11,426 | one paragraph |
| 9 | the row's Schedule, paragraph 7 (**un-headed**: LEX's cut of 6 swallows it) | proxy | 200 | 46,765 | one paragraph, 203 chars of text |
| 10 | the row's Schedule, paragraph 64A (**lettered**) | proxy | 200 | 59,652 | one paragraph |
| 11 | the row's Schedule, **sub-paragraph 43(6)** (`.../paragraph/43/6/data.xml`) | proxy | 200 | 56,201 | exactly 43(6), with its heading and both numbers |

**Findings (each checked as stated):**

- **legislation.gov.uk serves a schedule paragraph singly, through LEX's proxy, unchanged.** In every 200 (9 of 9)
  the document holds exactly **one** `P1`, whose `Pnumber` is the number asked for, whose `DocumentURI` is the
  paragraph's own URL, with its heading (`P1group/Title`, where the paragraph has one) and its sub-paragraph
  numbers. Proxy against direct: byte-identical **2 of 2**.
- **Word-for-word equal to LEX's cut for 42, 43 and 44 (3 of 3)**, apart from LEX's "Section N)" line
  (`parse_para.py ... 43 schB1_lex.txt`: "word sequences equal: True", 119, 243 and 319 words).
- **It reaches what LEX's cut cannot:** paragraph 7 (built `cut_schedule_paragraph`: NOT_CUT), 64A (built: a
  SPAN_CUT running through 66) and P3.22's session's paragraph 105 (the stored block itself: "no single heading
  of its own in it to cut at", so the 161,434-character schedule went whole to the summariser) each came back
  exactly. A sub-paragraph comes back exactly too, which LEX has no route to at all.
- **An absent paragraph is a clean 404** from the proxy, with a short JSON body: a code-stated negative is
  possible, attributed to legislation.gov.uk.
- **Cost of a read:** 11-71 KB of XML (the metadata dominates) for 0.2-1.9K characters of text; 124-1,090 ms.
- **Version:** the documents are legislation.gov.uk's current revised text (a `RestrictStartDate` on the
  schedule); LEX's own text version may differ in principle. For the three paragraphs compared they agree word
  for word.

**On how many stored schedule-paragraph requests would each route hand over exactly the paragraphs asked for?**
(`para_requests.py` with the BUILT `named_units` and `unit_in_results` over every stored section search in all
66 directories; `tally_route.py` with the BUILT `cut_pieces` on the stored LEX text.)

- **67 stored requests** name a schedule paragraph (62 on this row's session, 5 on three others), 12 distinct
  paragraph lists, **7 distinct paragraphs**.
- **The route fires on 61** (the unit not in the results); 3 more had an errored result (the route does nothing)
  and 3 had the unit in the results (it does not fire).
- **The built LEX route hands over exactly the paragraphs asked for on 58 of 61. The exact-paragraph route would
  on 61 of 61** (every existing paragraph single; the absent one a 404). The 3: P3.22's session's paragraph 105
  (2 calls, whole schedule summarised), and one query on this row that named "paragraph 43, 130" where 130 is a
  *section* of the Act, listed after the paragraph: the built `_paragraphs` reads it as paragraph 130, the cut
  of 130 fails, and **`cut_pieces` then sends the whole Schedule for summary, losing the exact paragraph 43 it
  could cut** (all-or-nothing). That call ran in `wave1`, before the route existed; under today's code it would
  take that path (decision 3).

**Forms no stored request contains, probed:** an un-headed paragraph, a lettered paragraph and a sub-paragraph
(all served exactly). **Not probed:** a paragraph with two territorial versions, a prospective or repealed
paragraph, a paragraph inside a schedule Part on an SI, a Welsh or Northern Irish instrument, and a paragraph
number the instrument uses twice in different schedules (the path names the schedule, so this should not arise).

**What the route would and would not fix on this row:** the row's paragraphs are already cut exactly by LEX's
route (58 of 58 calls on them), so the exact-paragraph route does not touch P3.12's acceptance, which fails on
composition. It would fix retrieval on the other shapes above (P3.22's session's paragraph; un-headed and
lettered paragraphs, about 21% of live paragraphs by batch 7 B's 348 of 440 clean cuts; a named sub-paragraph),
and the all-or-nothing summary. It is P3.38's route and P5.4 (d)'s fallback.

## 6. Which candidate the evidence points at, and why nothing is built (first version; relay 2 in section 10)

| Candidate | What the evidence says |
|---|---|
| **The exact paragraph through the proxy** | Probed and sound (section 5), but **not the failing step here**: the row's three paragraphs already reach the Worker exactly, and the failures are what the Worker writes from them. Worth building for retrieval elsewhere; not for this acceptance. |
| **The concision rule relaxed for a code-fetched unit** (Worker prompt) | Not indicated at the seam: the delivering draw fits in 6 sentences and the failing draws chose the Scots limbs, not ran out of room (section 2, point 4). It is a Worker-facing wording lever, the kind that has twice moved the composition seam and not the live run. Unmeasured on the as-sent seam. |
| **Code-written paragraph lines at the answer seam** (P3.13's pattern) | The only candidate that does not depend on what the Worker composes, which is where every live failure sits: in 4 of 4 live answers with the paragraphs verbatim, at least one was left out (section 4.1), and the one wrong pinpoint a code check found (2 of 2, 0 false, section 4.2). But its design is open and a lawyer reads it (decision 2), and the as-sent draws would say first whether the Worker's composition is really the gap. |
| (not on the list) **the brief's jurisdiction phrase** | The clearest pattern in the draws (section 2, point 2), on the Manager's side or the Worker prompt's Jurisdiction line; confounded with narrowing at n=1-2. |

So the four draws narrow the field (not the block, not the retrieval, probably not the budget) but do not pick one
candidate, and they show that the instrument used for every earlier P3.12 lever choice overstates the live Worker.
**Recommended next:** the as-sent draws (decision 1), then build the answer-seam lines if the as-sent seam
reproduces the live shortfall (decision 2).

## 7. Other code texts that speak of the same Schedule

Nothing built, so nothing new contradicts anything. Two observations for whoever builds next: (i) the
SEARCH SCOPE line ("ranked extracts, not the full contents") sits on the same result as the PROVISION FETCHED BY
CODE block that hands over full paragraphs; neither is wrong, and no stored draw read them as conflicting; (ii)
an answer-seam line would sit beside the Manager's scope footer and P3.13's "Also in s.N" notes, so its wording
must be screened against every answer-reading grader (the batch 10 and 11 screen, `b11_screenA.py`, is the
pattern).

## 8. What I did NOT do

- No model call, seam draw, replay or server; no LEX `POST` (only the 12 GETs above).
- (First version) no product change. Relay 2's candidate (`560cf8e`) changes `prompts.py` and adds one test file;
  no grader, seam tool or other prompt changed. The `wind up` grader fix and the `_paragraphs` /
  all-or-nothing finding are decisions, not edits.
- I did not draw the prompt-swapped payloads or the first-round probe; I built and dry-ran them.
- I did not draw the as-sent payloads; I built and dry-ran them (`--dry-run`).
- I did not edit FIX_PLAN, SESSION_LOG, a rubric, the tracker, CLAUDE.md or a memory file. No push, no merge.

---

## 9. Decisions for the user (first list; decision 1 approved and drawn; superseded by section 11)

1. **The next draw on this row** (the integrator's; priced first; one attempt per draw with the product's
   `max_tokens` 32,000, so a runaway costs at most about $0.41 a draw; expected about $0.04-0.06 a draw, like
   today's).
   1. **(Recommended) The as-sent seam on the three sweep payloads, n=2 each, plus the one-field brief payload,
      n=2: 8 draws, about $0.40 expected, $3.30 at worst.** From `server_py/`:
      `python -m tools.seam_replay worker --run $PREPILOT_EVIDENCE/replay/wave4_b11_sweep/6335_rep1.json --turn 7 --as-sent --at-rev recorded --date recorded --max-tokens 32000 --reps 2 --out <dir>`,
      the same with `6335_rep2.json` and with `6335_rep3.json`, and the same with
      `--run $PREPILOT_EVIDENCE/seam/batch12/A/seam_b12_rep3_noscot.json` (rep 3 with only
      " for Scotland" taken out of the brief; one field differs, asserted by `make_seam_b12.py`). It tells
      whether the live call's shape reproduces the live shortfall (if it does, the composition seam was the
      wrong instrument and levers are measured as-sent from now on), and whether the jurisdiction phrase alone
      moves 43's limbs. A draw that calls a tool instead of composing is itself a result (live, the Worker
      composed at that point).
   2. **Only the three sweep payloads as-sent, n=2** (6 draws, about $0.30, $2.50 at worst). Settles the
      instrument question, not the brief.
   3. **Skip the draws and go to a 6335 n=3 re-run** with whatever lever is chosen. Not recommended: three live
      reps have not moved on two Worker-facing levers, and a rep has cost up to $0.99.
2. **Which lever to build after the draws** (each wording a lawyer or the Worker reads goes to the user before
   merge).
   1. **(Recommended, if the as-sent draws reproduce the shortfall) Code-written lines at the answer seam**, P3.13's
      pattern: after the answer is written, for each paragraph code cut and handed over in that turn whose number
      the answer does not cite, one line with the paragraph's number, its heading and its link, taken from the
      cut (code text, never generated); and a check that flags a sentence citing one handed-over paragraph with
      another's distinctive words (prototype 2 of 2, 0 false). The open design choice is how much statutory text
      a line carries (the heading alone does not meet the row's "cited with its facts"; the operative
      sub-paragraphs verbatim run to 0.7-1.9K characters a paragraph) and what the check does (a note, or
      nothing but a counter).
   2. **The brief's jurisdiction phrase**, if the one-field payload flips 43's limbs: a line in the quick-lookup
      Worker's Jurisdiction rule that "for Scotland" means the law that applies in Scotland, not only the
      provisions specific to it. A prompt change: probe its first-round drift first (FIX_PLAN's P3.13 lesson).
   3. **The concision rule relaxed for a code-fetched unit.** Only if the as-sent draws show the budget binding
      (reports cut short with paragraphs left out for room); today's evidence says it is not.
3. **The all-or-nothing paragraph cut, and the comma-list misread** (a small retrieval fix, found here, not built).
   1. **(Recommended) Hand over the paragraphs that cut and state the ones that do not**, instead of sending the
      whole schedule for summary when any one named paragraph fails; and, once decided, the exact-paragraph
      route as the fallback for the one that failed (a 404 stated in code, a 200 handed over). Measured: 1 stored
      call takes this path; P3.22's session's paragraph 105 is the other shape the fallback reaches.
   2. **Also stop `_paragraphs` reading a number after a comma-separated list as a paragraph when the list mixes
      sections and paragraphs** ("para 43, 130"). Harder to get right than option 1, which makes the misread
      harmless; I would not do it alone.
   3. **Leave both** until P3.38's route is built, which would carry the fallback anyway.
4. **The `depth` grader's paragraph-42 fact regex** (`wind up`).
   1. **(Recommended) Extend it to `wind(?:ing)?[- ]?up`**: moves 1 of 48 stored texts, to the hand verdict.
   2. **Leave it** and hand-read every 42 "coarse" verdict, as this note did.
5. **The exact-paragraph route itself** (P3.38's and P5.4 (d)'s data route, probed sound).
   1. **(Recommended) Book it under P3.38's build, not P3.12's acceptance**, with this note's numbers: 61 of 61
      stored requests exact against 58 of 61, byte-identical through the proxy, a clean 404, un-headed, lettered
      and sub-paragraph forms served.
   2. **Build it into `schedule_route_block` now as the primary route** for a named paragraph. More text a call
      (11-71 KB a read, one read a paragraph) for no gain on this row's acceptance.

## 10. Relay 2: the as-sent draws, and the candidate they point at

The user approved decision 1 of the first list and the integrator drew it: 8 as-sent draws (`seam_replay worker
--run <f> --turn 7 --as-sent --at-rev recorded --date recorded --max-tokens 32000`), $0.3677, outputs gitignored in
`evidence/seam/batch12/integrator/assent/`. The integrator asked me to check its hand-read, build the candidate
the draws point at (unmerged), and prepare the payloads to test it.

### 10.1 The 8 draws, read by hand (the integrator's read checked)

| Payload | Draws | 42 | 43 | 44 | By hand | `depth` |
|---|---|---|---|---|---|---|
| sweep rep 1 | 2, **byte-identical** (1,944 completion tokens, 1,694 chars) | **absent** | (5), (6), and a clause for the other limbs | named, with its trigger, no sub-paragraph | PARTIAL | PARTIAL (42 coarse) |
| sweep rep 2 | 2, distinct | (2)-(3), (4) | (6), (5), and a clause for the other limbs | named with its trigger / (1) and (5) | **DELIVERED 2 of 2** | DELIVERED 2 of 2 |
| sweep rep 3 | 2, **byte-identical** (2,405 tokens, 1,252 chars) | **absent** | "(1)-(4)" for the security, repossession and forfeiture limbs (loose: (1) is the paragraph's application line), (5), (6) | **absent** | PARTIAL | PARTIAL (42, 44 coarse) |
| `seam_b12_rep3_noscot` (rep 3, " for Scotland" removed from the brief) | 1 answered, 1 tool call (`get_legislation_changes`, no text) | (1)-(5), each | (1)-(8), each | (1)-(7), each | **DELIVERED** | DELIVERED |

- **The integrator's read holds**, with three additions. (i) **Rep 2's brief also names Scotland** ("Jurisdiction:
  for Scotland") and delivered 2 of 2, so the phrase is not sufficient on its own: rep 2's payload differs in
  that the Worker's own second section search named the three paragraphs (a CUT block, not only the MATCHED
  one) and a change-record round followed. (ii) As-sent reproduces the live shortfall on reps 1 and 3 (live: 43(6)
  and 44; 43(6) alone), not rep 2's live wrong pinpoint (0 of 2). (iii) No draw has a wrong pinpoint; one is
  loose (rep 3's "(1)-(4)").
- **Effective n:** the two identical pairs make 4 distinct answers on the recorded briefs; the two payloads with
  a Scotland brief and no named-paragraph search (reps 1 and 3) give 2 distinct answers, both without 42; and 1
  answered draw on the one-field payload. **The jurisdiction pointer rests on that one draw**, plus the 6 of 6 against 2 of 7 pattern
  over the composition-seam draws (section 2, point 2). It is a pointer, not a measurement.
- **The as-sent seam is the instrument from here**: it reproduced two of the three live shortfalls, where the
  composition seam reproduced none.

### 10.2 The candidate (`560cf8e`, on this branch, not merged)

**What:** one sentence, `prompts._JURISDICTION_SELECTS_LAW`, joined at the end of the quick-lookup Worker's
existing Jurisdiction bullet (`WORKER_SYSTEM_PROMPT_CONVERSATIONAL`, YOUR MANDATE), after P3.4's three rules,
which are unchanged byte for byte. Nothing else in any prompt moves.

**The built bullet's new tail**, exactly as the Worker reads it:

> ... If the brief names a jurisdiction, answer for that one. **A jurisdiction, whether the brief names it or it is
> the default, selects the law that applies there, not the provisions to report: give each provision on the
> question that applies there, including those that also apply elsewhere in the UK, not only those that name
> that jurisdiction or apply only there.**

**Why each part.** "Whether the brief names it or it is the default": the bullet's own default is Scotland, so
a brief with no jurisdiction is answered for Scotland too; the sentence makes the two cases read the same. "Selects the law ..., not the provisions to
report": the failure is a Worker treating "for Scotland" as a filter on provisions. "Including those that also
apply elsewhere in the UK": the dropped paragraphs are UK-wide provisions that extend to Scotland. "Not only those
that name that jurisdiction or apply only there": names the narrowing seen (43(5) and 43(6) are the limbs that
name Scotland or its procedure). "On the question": keeps the mandate's "Do not broaden the scope" (the sentence
does not license reporting unrelated provisions, such as rep 1's paragraph-112 span).

**Where it reaches (decided for this candidate, open to the user, decision 2.3):** the quick-lookup Worker only,
in every research type, with or without a filter; not the research Workers, the Manager, the planner, the Deep
Research synthesis or the parliamentary bots (`test_the_sentence_reaches_exactly_the_quick_lookup_worker`, 20
dispatch cases x 2 configurations). The evidence is all from the quick-lookup Worker; the research Workers'
reports carry a full Statutory Framework and no stored research-mode turn 7 ran after the route existed.

**Wording options for the user** (each screened, below):

1. **(Recommended, built) W1**, as above.
2. **W2, shorter:** "Answering for a jurisdiction means giving the law that applies there on the question,
   including provisions that also apply elsewhere in the UK, and not only the provisions made for it alone."
   Drops the default clause and the "not the provisions to report" contrast.
3. **W3, an instruction about placement:** "Where a provision on the question applies in that jurisdiction, report
   it whether or not it names the jurisdiction, and give any provision made only for that jurisdiction beside
   it, not in its place." Names the failure most directly; says nothing about the default.

**Screens (BUILT code, all pass):**

- `python <scratch>/screen_b12.py` from `server_py/` (the integrator's `b9_screen.screen`, copied from batch 11 A,
  every answer-reading detector whole and per sentence, "ranked", brackets): **6 texts (W1 sentence, W1 bullet,
  W2, W3, W2 and W3 in the bullet), 0 trips** (`screen_b12.txt`).
- `test_the_sentence_trips_no_detector` (in the product's tests): the sentence and the whole bullet against
  `NEG_ASSERTED`, `NOT_FOUND`, `NEG_TERMS`, `NEG_BLAMED_INDEX`, `NEG_BLAMED_USER`, `NEG_LIMITS`,
  `NEGATIVE_EXPLAINED`, `IN_FORCE_CLAIM`, `_CUR_DISCLOSED`, `_CUR_DATED`, `SCOTS_CASELAW_GAP`, the three halt
  detectors, `OPENER_VOCAB`, `SCHED_LIMIT`, `SCHED_INDEX_NEG`, `_P312_NOT_DELIVERED`, `derivation_claims`,
  `caselaw_gap_statements`, `sched_unit_clauses`, per sentence `_CMC_*`, `_currency_asserted`,
  `negcurrency_claim` and `sched_clause_class`, and `_scripted_counts` (0); no "ranked", "cut short", bracket or
  "retriev".
- P3.4's own screen (`test_the_new_wording_trips_no_detector`, which reads the whole bullet) still passes.

**Other code texts that speak of the same thing** (the lesson), none contradicting it:
- **P3.4's conversational Manager JURISDICTION rule** ("answer it for Scotland (the law that applies in Scotland,
  including UK legislation that extends there)"; "Put the jurisdiction in every `delegate_research` brief"): the
  sentence says on the Worker's side what the Manager's parenthesis already says. The Manager is unchanged.
- **P3.4's bullet itself** ("find the legislation that applies in Scotland (UK legislation that extends there
  included)"): the default case already said it; the sentence extends it to a named jurisdiction.
- **The hybrid research Worker's JURISDICTION SCOPE** ("retrieve sections ONLY for that jurisdiction's
  legislation"): about which instruments to retrieve, in a prompt this candidate does not touch. "That
  jurisdiction's legislation" could be read the same narrow way; decision 2.3.
- **The filter block's extent notes**: never given to the quick-lookup Worker (P3.14); unaffected.
- **The FETCHED block's MATCHED tail** (batch 11 A: "each of those paragraphs that bears on the question gets a
  sentence or bullet of its own"): consistent; the sentence removes a reason the Worker gave for treating the
  general paragraphs as not bearing on a Scotland question.

**What it moves (dry run over every stored input it reads):** the quick-lookup Worker's system prompt, +304
characters, on all **1,585** stored quick-lookup delegations (394 run files, 57 directories); nothing else, by
construction (`test_the_prompt_is_its_parent_plus_the_sentence_alone`, and `draw_swap.py`'s assertion that the
candidate's built prompt is its parent's plus the sentence and nothing else). 140 of those 1,585 briefs name a
jurisdiction (most stored runs predate P3.4, which now has the Manager name one in every brief). **What a prompt
line moves is behaviour, which no dry run shows**: it reaches every quick-lookup Worker call, including its
first round (what it searches), so a first-round probe belongs before any sweep (decision 2.2).

**Tests:** `server_py/tests/test_jurisdiction_selects_law.py`, 26 tests. **Revert** (`mutants_b12.py`, a scratch
copy, the constant, its comment and the join removed): **17 lines** of `prompts.py`, **8 tests fail**. **Single-site
mutants, 10 of 10 caught** (`mutants_b12.txt`): the sentence not joined (6 fail); joined as a block after the
mandate instead of in the bullet (3); also joined into the research legislation Worker (4); also into the
conversational Manager (4); joined twice (2); the default clause dropped (7); "not only those that name" dropped
(7); "also apply elsewhere in the UK" dropped (7); "on the question" dropped (7); a detector-tripping phrase
substituted (9). The two "also joined into" mutants first raised a NameError at import (the constant is defined
below those prompts) and so proved nothing; rewritten to insert the literal sentence, they fail on behaviour.
**Full suite: 3043 passed** on `lexchat_test_a` (3017 + 26; `pytest_full2.txt`).

### 10.3 The payloads to test it (not drawn)

**Why not `--at-rev 560cf8e`:** between the recorded head (`9632b53`) and this candidate's base (`a99e4d4`),
P3.31 changed the quick-lookup Worker's ENABLING POWER rule and added a tool. `seam_replay worker --run
wave4_b11_sweep/6335_rep3.json --turn 7 --as-sent --at-rev 560cf8e --date recorded --max-tokens 32000 --dry-run`
gives sent_chars **44,214** and offers `find_instruments_made_under`, against 43,549 recorded: 665 characters and
a tool more, of which the sentence is 304. Three changes, not one.

**So `draw_swap.py`** (scratch) builds the payload with the product's own builders exactly as `--as-sent --at-rev
recorded --date recorded` does, inserts the candidate sentence (read from `560cf8e` with `git show`) at the end of
the recorded prompt's bullet, and asserts: (1) `560cf8e`'s built prompt is its parent's plus " " + sentence at that
anchor and nothing else; (2) the swapped payload equals the recorded one in every message but the system prompt,
and the system prompt differs only by that insertion; the tools offered are the recorded ones; (3) sent_chars
grows by exactly 304. Each draw is one attempt with `max_tokens` 32,000 through `seam_replay.run_as_sent`, printed
and graded as `--as-sent` prints them. **Dry runs (all assertions pass):**

| Payload | Recorded sent_chars (matches the integrator's draws) | Swapped |
|---|---|---|
| sweep rep 1 | 52,045 | 52,349 |
| sweep rep 2 | 68,100 | 68,404 |
| sweep rep 3 | 43,549 | 43,853 |
| `seam_b12_rep1_noscot.json` (new: rep 1 with " for Scotland" removed, one field asserted, 250 to 237 chars) | 52,032 | 52,336 |
| `seam_b12_rep3_noscot.json` (rebuilt: byte-identical to the one drawn, sha1 `fc0e2240`) | 43,536 | 43,840 |

**Commands** (from `server_py/` of the main checkout; `tools/seam_replay.py` is the same at `a99e4d4` and on this
branch; `S=$PREPILOT_EVIDENCE/seam/batch12/A`):

```
# the candidate, prompt swapped, on the three sweep payloads (n=2 each)
python $S/draw_swap.py --run $PREPILOT_EVIDENCE/replay/wave4_b11_sweep/6335_rep1.json --reps 2 --out <dir>/swap_rep1
python $S/draw_swap.py --run $PREPILOT_EVIDENCE/replay/wave4_b11_sweep/6335_rep2.json --reps 2 --out <dir>/swap_rep2
python $S/draw_swap.py --run $PREPILOT_EVIDENCE/replay/wave4_b11_sweep/6335_rep3.json --reps 2 --out <dir>/swap_rep3
# the brief alone, on rep 1 (recorded prompt, no candidate), n=2
python -m tools.seam_replay worker --run $S/seam_b12_rep1_noscot.json --turn 7 --as-sent --at-rev recorded --date recorded --max-tokens 32000 --reps 2 --print --out <dir>/noscot_rep1
```

8 draws. **Expected about $0.40** (the 8 relay-2 draws cost $0.3677, $0.023-0.063 each); **worst case about $3.30**
(each one attempt, capped at 32,000 output tokens, about $0.41 at the runaway). Two of relay 2's pairs came back
byte-identical, so n=2 may give one distinct answer per payload; a third draw on a payload whose pair is identical
adds nothing.

**What to read:** in the swapped draws, whether 42 and 44 appear with their facts on reps 1 and 3 (the shortfall),
that rep 2 still delivers, that 43(5) and 43(6) are still there (they are what "for Scotland" asks for), and that
nothing outside the question appears (rep 1's block carries a span from paragraph 112, matched on the word
"Scotland"; the sentence must not pull it in). In noscot rep 1, whether the brief alone flips rep 1 as it flipped
rep 3.

## 11. Decisions for the user (revised after relay 2; supersedes section 9)

Section 9's decision 1 was approved and drawn (section 10.1). The others are restated here as they now stand.

1. **The next draws** (the integrator's; priced first).
   1. **(Recommended) The 8 draws of section 10.3**: the candidate prompt-swapped on the three sweep payloads, n=2
      each, and rep 1's brief alone, n=2. About $0.40 expected, $3.30 at worst. Tells whether the sentence
      recovers 42 and 44 on reps 1 and 3 without losing rep 2 or the Scots limbs, and whether the brief alone
      flips rep 1 as it flipped rep 3.
   2. **The three swapped payloads only** (6 draws, about $0.30, $2.50 at worst). Skips the second brief-only
      check, so the pointer would still rest on one answered draw.
   3. **Also draw the candidate on both noscot payloads** (2 more, about $0.10): checks the sentence does not
      hurt the case that already delivers.
2. **The candidate itself** (`560cf8e`, Worker-facing wording; the user's before merge).
   1. **Wording: (Recommended) W1 as built**; or W2 (shorter, no default clause); or W3 (placement instruction).
      All three screened, 0 trips (section 10.2). Choosing W2 or W3 is a one-constant change plus its tests.
   2. **Before any sweep: (Recommended) a first-round probe**, because a Worker-prompt line reaches the Worker's
      first round (what it searches) as well as its write-up (FIX_PLAN's P3.13 lesson). From `server_py/` of
      **this worktree** (whose working tree carries the candidate): `python -m tools.seam_replay worker --run
      $PREPILOT_EVIDENCE/replay/wave4_b11_sweep/6335_rep{1,3}.json --turn 7 --first-round --reps 1`, and the same
      from the main checkout for the before-column: 4 calls, each stopped at the first tool call, about $0.02 each.
      Dry-run checked: the probe uses the working tree's prompt (12,427 characters here, the main checkout's
      12,123 + 304) and today's tools on both sides, so the A/B differs by the sentence alone; this brief names no
      instrument by number, so P3.7's lookup block adds nothing to it.
   3. **Scope: (Recommended) the quick-lookup Worker only**, as built; or **also the research Workers**, as a
      clause in the hybrid Worker's JURISDICTION SCOPE and a bullet in the legislation Worker (no evidence from
      research mode yet: every stored research-mode turn 7 ran before the route).
   4. **If the swapped draws do not recover 42 and 44:** drop the candidate and return to the answer-seam lines
      (section 9's former decision 2.1, unchanged), which do not depend on what the Worker composes.
3. **The all-or-nothing paragraph cut and the comma-list misread** (section 9's decision 3, unchanged): hand over
   the paragraphs that cut and state the ones that do not (recommended); or also fix `_paragraphs`; or leave both
   until P3.38.
4. **The `depth` grader's paragraph-42 fact regex** (section 9's decision 4, unchanged): extend it to
   `wind(?:ing)?[- ]?up` (recommended; 1 of 48 stored texts moves, to the hand verdict); or leave it.
5. **The exact-paragraph route** (section 9's decision 5, unchanged): book it under P3.38 with section 5's numbers
   (recommended); or build it into `schedule_route_block` now.
6. **The instrument for P3.12's lever choices from now on.**
   1. **(Recommended) The as-sent seam** (`--as-sent --at-rev recorded --date recorded --max-tokens 32000`, or
      `draw_swap.py` for a prompt candidate), not the default composition seam: as-sent reproduced 2 of the 3 live
      shortfalls; the composition seam reproduced none, and two earlier levers moved it and not the live runs.
   2. **Keep both**, the composition seam for a cheap first look. It costs the same per draw, so there is little
      to save.

---

**Data handling.** The note names no question, brief, search term, case name or instrument id or title from a
session; it cites P3.12's row and P3.22's session by row. Statutory content is described, not quoted, except the
grader's own pattern (`DEPTH_TRUTH`'s standing exception). Checked with batch 11 A's `matter_grep.py` (copied) and a
Python check for session numbers, instrument ids and matter words (section "Checks" below is in the scratch,
`grep_note.txt`).
