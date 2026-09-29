# Parallel batch 1, agent D: P3.18 (the Deep Research synthesis asserts a doctrine for a jurisdiction)

Session 33, 2026-09-29. Branch `worktree-agent-ae02e428771fac297`, from `01b66b0`. Seam only, with no
replay. This note gives counts and file, rep and turn locations. It quotes no report text, because
the draws name a matter. The draws are in the gitignored
`evidence/seam/batch1/D/{before,after,after2}/<dir>_r<N>/`.

## The row's acceptance, and whether it is met

**Acceptance (FIX_PLAN P3.18):** P3.3's 6375 criteria, n=3 on a replay, with no alignment assertion
in any rep. **This is not met, and it has not been measured.** Replays were outside this brief, so
it is the integrator's after-column to take. What the seam shows is below. It supports putting the
change into that after-column.

## What I changed, and why

`server_py/src/prompts.py`, Deep Research synthesis only. The Worker prompts are unchanged, so the
first-delegation drift probe does not apply.

1. **A clause in the existing grounding bullet of `_SYNTHESIS_BODY`**, every research type. It is
   Session 32's rule: do not say a general rule (an interpretation Act, a common-law doctrine)
   applies to an instrument or in a jurisdiction, or that one jurisdiction's decisions are binding
   or persuasive in another, unless a step finding cites the source that applies it there. It adds
   the part the synthesis needs: an unsourced step finding saying so is not a finding, so do not
   repeat it and say it was not verified. The clause adds 420 chars.
2. **A sentence in the jurisdiction section, only for the two types that search case law**
   (`_SYNTHESIS_CASE_LAW_REACH`, appended to "Jurisdiction & Status" for `legislation_and_case_law`
   and to "Jurisdiction & Currency" for `case_law_only`). It says: name the courts the cited
   decisions come from, and do not say they are binding or persuasive in, or apply across, another
   jurisdiction unless a step finding cites a source that says so. It adds 213 chars.
   `legislation_only` and the two parliamentary types do not get it.

Why there are two changes: the seam showed that change 1 alone did not work (below). Every draw
that still made the claim made it in the jurisdiction section, carried over from a step finding's
own jurisdiction line.

**Only this text differs.** For every type, the prompt with these two strings removed equals
`_synthesis_prompt_at("20f7b79", type)` (scratch `intact.py`, using seam_replay's own revision
loader). P4.7's headings, the "Key findings" label, citation preservation, the pinpoint rule, the
links rule, P2.5's currency and in-force rules and the gap wording are byte-identical. The
synthesis prompt carries no enabling-power text: that rule is in the Worker prompts and in code,
and none of it was touched. `git diff 20f7b79 01b66b0 -- server_py/src/prompts.py` is empty, as the
brief said, so the before side (`--without-fix --rev 20f7b79`) is HEAD's prompt.

## Where the claim comes from (free, measured first)

I graded the stored turn-2 step findings with the p33 rubric, using the product's
`interpret_grade` in a scratch script. They are the synthesis's input, from `wave4_p33_pre` and
`wave4_p33_post` `6375_rep1..3.json`.

- **11 of the 24 step reports make the alignment claim** (rubric item `scots_alignment`),
  unhedged, and every one of the 6 reps has at least one. By rep: pre r1 2, r2 1, r3 2; post r1 2,
  r2 1, r3 3. Each sits in the Worker's "Jurisdiction & Status" line.
- The stored synthesis answers repeat it in 2 of 6: pre r3 and post r3, the latter being the rep
  the row cites.

So the claim starts with the hybrid research Worker (`WORKER_SYSTEM_PROMPT_HYBRID`, section 4:
"Geographic scope from the metadata"). The synthesis prompt's "ground every statement in the step
findings" then passes it through. This project did not change the Worker. A synthesis-level
refusal is enough for the Deep Research report. A Worker change would also reach Research-mode
answers built from the same report, but it would need the drift probe, which was over budget. That
is for the integrator to decide (below).

## The seam A/B (same day, 2026-09-29, same rubric version)

The six stored 6375 Deep Research payloads were drawn at turn 2, 2 draws a side. The before side
was `--without-fix --rev 20f7b79`; the after side was the working tree. Then there was a probe of
the final build (bullet plus section sentence) on the two payloads that still failed, plus one
other. Graded in one pass at the end, before, after and after2 together, with
`python -m tools.replay_report --dir $PREPILOT_EVIDENCE/seam/batch1/D/<side> interpret --drafts --session 6375 --rubric $PREPILOT_EVIDENCE/rubrics/p33.json`,
and with a scratch `grade.py` for per-draw lines and guards. Every match and every drop was read by
hand. **Rubric version used for every grade: `p33.json` size 10,272 bytes, mtime 1790687956**
(agent B changed it while I worked. It was 10,249 at 1790682319 when I started, and all grading ran
after the change).

**Alignment assertions, draws making one, by slot:**

| payload | before (HEAD) | bullet only | bullet + section (final) |
|---|---|---|---|
| wave4_p33_pre r1 | 0/2 | 0/2 | not drawn |
| wave4_p33_pre r2 | 0/2 | 0/2 | 0/1 |
| wave4_p33_pre r3 | 2/2 | 0/2 | not drawn |
| wave4_p33_post r1 | 1/2 | 2/2 | 0/2 |
| wave4_p33_post r2 | 0/2 | 0/2 | not drawn |
| wave4_p33_post r3 | 2/2 | 2/2 | 0/2 |
| **total** | **5/12** | **4/12** | **0/5** |

- By `interpret --drafts`: before 5 reps with `a1`, bullet only 4, final 0. None of the matches
  was hedged.
- Read by hand, the command's count is right in every draw. No drop is an alignment claim. The
  drops are lists of which courts the cases come from, statements of how the doctrines work between
  the two governments, and gap statements.
- A wider grep of every draw (`persuasive|binding in/on|across the UK/jurisdictions|Scots law`)
  finds the same 5 and 4 files. It also finds 2 more on the bullet-only side (post r2, both draws)
  that state a set of Regulations' territorial extent. That is a retrieval statement, correctly not
  graded. The final build's 5 draws match nothing.
- In all 4 surviving bullet-only assertions, the jurisdiction section repeats the step finding's
  jurisdiction line nearly word for word. With the section sentence, the same section lists the
  courts and stops.
- Temperature 0 was not deterministic: several slots drew two different reports.
  - post r1 and r3 failed 4 of 4 with the bullet alone and 0 of 4 with the final build, so the move
    on those payloads is not noise.
  - The final build was drawn on only 3 of the 6 payloads. The budget ran out.

**Scots-law status statement in the report prose (`scots_status_stated`): 0 of 29 draws on every
side.** The clause's "say instead that this was not verified" was followed in no draw. Every draw
discusses the doctrines, so the requirement fires in all 29, and `interpret --drafts` fails all of
them on it: before 12/12, bullet only 12/12, final 5/5. That is expected at the seam. A seam draw
carries no code-emitted footer, and the rubric counts `CASE_LAW_DOCTRINE_SENTENCE` (user decision,
`0bc4f2c`). The three stored `wave4_p33_post` turn-2 answers all carry that line (scratch
`origin.py`), so the replay should meet the status criterion through the footer, as P3.3's r1 and
r2 did. If the user wants the body itself to state the status (the tighter acceptance Session 32's
addendum item 5 mentions), this change does not deliver it.

## Guards

- **Headings and "Key findings" (P4.7):** all 29 draws carry the hybrid type's five sections
  (`_extract_section_headers` against `REPORT_SECTIONS`) and the bold **Key findings** label. The
  existing tests pass on both sides.
- **No hedge added to a retrieval statement, and no blanket caveat:** `replay_report.hedge_counts`
  over each draw (scratch `grade.py`) gives:

  | side | hedged retrieval statements | provision-citing sentences | blanket caveats | interpretive hedges | words per draw |
  |---|---|---|---|---|---|
  | before | 0 | 268 | 0 | 10 | 1,667 |
  | bullet only | 0 | 271 | 0 | 9 | 1,706 |
  | final | 0 | 93 (5 draws) | 0 | 3 | 1,598 |

- **Links per report (markdown links in each draw):**
  - Totals: before 409 in 12 draws, bullet only 397 in 12.
  - Per slot (sum of 2 draws), before to bullet only: pre r1 70 to 60, pre r2 58 to 48, pre r3 64
    to 68, post r1 60 to 56, post r2 83 to 92, post r3 74 to 73. Lower in 4 of 6 slots, one of
    them by 1.
  - Final build, per draw against before's two draws: post r1 27 and 28 (before 28 and 32); post r3
    36 and 36 (37 and 37); pre r2 27 (31 and 27).
  - Distinct URLs are the same on every side for every payload except pre r1 bullet only: 6 against
    8.
  - One bullet-only draw (pre r2 rep2) wrote its References as bare URLs, 0 links there. That is
    Session 26's failure mode (`test_every_type_keeps_links_as_links`): 1 of 12 draws, against 0 of
    12 before. The one final-build draw on that payload kept them as links (10 in References).
  - **Read:** the final build is within before's rep-to-rep range on the three payloads drawn, but
    at n=1-2 I cannot claim "not lower". The replay's links and `sources_kept` guard should decide.
- **Other synthesis rules intact:** see "Only this text differs" above.

## Tests

- `tests/test_synthesis_prompt.py`: 11 new cases.
  - The grounding-bullet clause on all 5 types.
  - The clause reaches `build_synthesis_messages`' system message.
  - The section sentence in the jurisdiction section of the 2 case-law types.
  - A guard that the other 3 types do not carry the section sentence.
- **Proven to fail with the change reverted:** on a scratch copy of `server_py` with `prompts.py`
  taken from HEAD, 8 of the new cases fail (the 5 clause cases, the builder case and the 2
  section-sentence cases). The 3 negative guards pass there, as a negative guard should.
- The first version of the builder test passed when reverted, because the prompt already says
  "is not a finding" in the halted-step gap rule. It now asserts the clause's own wording.
- **Full suite on `lexchat_test_d`: 1994 passed** (`TEST_DATABASE_URL=postgresql://lexuser:lexpassword@localhost:5432/lexchat_test_d python -m pytest -q`,
  run from `server_py`).

## Spend: $3.93 of $4

These are printed seam costs. Draws cost $0.09 to $0.26 each, above the brief's $0.11 estimate.

- Before and bullet-only A/B, 24 draws: $3.17. The before side was $1.48 and the bullet-only side
  $1.69.
- Final-build probe on post r1 and post r3, 4 draws: $0.65.
- One final-build draw on pre r2, to check the links failure: $0.11.
- No manager, worker or drift draws. No replay, and the server was not started.

## What I did NOT do

- No replay of any kind: pin, run or restore. The acceptance is not measured.
- The final build was not drawn on pre r1, pre r3 or post r2. The budget ran out. On those
  payloads, the only after-side evidence is the bullet-only side, which already had 0 alignment in
  all six of their draws.
- The research Workers were not changed, so there was no drift probe.
- The rubric files were not edited.
- Session 32's clause in the conversational Manager and the quick-lookup Worker was not touched.

## For the integrator to decide

1. **Put the change into the combined after-column?** The seam supports it. The claim went from
   5/12 to 0/5 draws, and to 0 of 4 on the two payloads that failed 4 of 4 without the section
   sentence. No hedge or caveat was added, and headings are unchanged. The one soft guard is links
   (above).
2. **The Worker is the origin** (11 of 24 step reports). This change filters the claim at the
   synthesis. Two consequences follow:
   - A Research-mode (conversational) answer built on a hybrid Worker report is not covered. The
     conversational Manager has Session 32's clause, but it receives the Worker's jurisdiction line.
   - A Worker-side fix to section 4 of `WORKER_SYSTEM_PROMPT_HYBRID` would need the drift probe
     (`seam_replay manager --first-round --date recorded`).

   Whether to book that as a row is the user's call.
3. **The body never states the Scots-law status** (0 of 29 on every side). The 6375 status
   criterion therefore rests on the code line, as it did at P3.3.
