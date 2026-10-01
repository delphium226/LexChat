# Parallel batch 3, agent D: a confirmation pack for a lawyer

Agent D, Session 35 batch 3, 2026-10-01. Spend **$0**: no model call of any kind, no server, no
replay. **No code changed**, so the test suite was not run (no product, tool or test file is
touched; this note is the only committed file).

## Base

The worktree came up on `main` (`a6b4a76`), not the integrator's head; with no commits of my
own I ran `git reset --hard 72dc84efdd9a384333287591f8077f42dc3658c1`, as briefed.

## What I did

Wrote the confirmation pack the brief asks for, at
`docs/prepilot-fixes/evidence/lawyer_pack/confirmation_pack.md` (main checkout; see decision 1
below: that directory is **not** in fact gitignored). It holds:

- a one-paragraph cover note in plain language (what is being checked, why it matters, that no
  answer from the tool is attributed to the lawyer), plus two short paragraphs on how to answer
  and what the links are;
- **4 readings**, one section each: the P3.2 reading and the three P3.3 readings;
- **4 yes/no questions**, one per reading, each with space for the answer and a comment. Two
  readings have numbered parts as recorded (two parts and three parts); their question asks
  whether all parts are correct and the comment asks which part, if not;
- **18 legislation.gov.uk links**, every one a URL a stored tool result returned;
- **1 cited source with no link** (a set of explanatory notes our tool does not retrieve; the
  pack says so) and **1 reading that rests on no legislation** (case law; the pack says so and
  gives no link);
- **3 points marked "unclear in our records"**, stated and not resolved (decision 2).

Each reading is quoted from a rubric `_note` field or the FIX_PLAN row, with square-bracketed
insertions only to expand abbreviations or gloss internal terms. Each "question the session
turned on" is my one-sentence summary, not a quotation.

Scratch (gitignored): `docs/prepilot-fixes/evidence/seam/batch3/D/`. The scripts there are
copied from my worktree's ignored scratch and point at the main checkout.

## Numbers and the commands that produce them

All commands from `docs/prepilot-fixes/evidence/seam/batch3/D/` in the main checkout, with
`PYTHONIOENCODING=utf-8`. Read-only over the evidence.

| Number | Command | Output file |
|---|---|---|
| 969 legislation.gov.uk URLs for the pack's instruments in tool results (raw results and `api_calls[].response`) over every stored run file of the four sessions | `python harvest.py` | `harvest.txt`, `harvest.json` |
| Every pack link located as the `id` of a returned item; per-target hit counts (e.g. the decisive P3.2 provision 418 item hits, every one carrying its quoted words) | `python locate.py` | `locate.txt`, `locations.json` |
| Instrument titles as returned, plus 2 extra locations | `python titles.py` | `titles.txt`, `titles.json` |
| One more location (a provision named in an unclear point) | `python locate_extra.py` | stdout |
| **18 of 18 links located** (file, turn, delegation, tool, api_call, JSON path) | `python link_table.py` | `link_locations.md` |
| **18 of 18 links resolve**, HTTP 200 after a redirect (2026-10-01); 2 open at the instrument's made version | `curl -s -o /dev/null -L -w "%{http_code} %{url_effective}" <url>` per link | `link_check.txt` |
| **25 of 25 quoted fragments occur verbatim** in the cited record (rubric `_note`, FIX_PLAN, `classification.json`) or provision text, and in the pack | `python quotes.py ../../../lawyer_pack/confirmation_pack.md` | `quotes_check.txt` |
| Five-word runs shared with lawyer-authored text (user messages, rating comments and the feedback free-text columns of the export, plus the run files' questions): **24** (1, 3, 16, 4 across the four readings), URLs excluded; **0** pack links outside the located set | `python check_pack.py ../../../lawyer_pack/confirmation_pack.md` | `overlap_check.txt` |
| 0 of 13 lawyer usernames in `classification.json` appear in the pack | inline check over `classification.json` `user` fields | (stdout) |

**Every one of the 24 shared runs was read:** all are an instrument's title (22), the wording of
a provision that a lawyer had also quoted (1), or a bare citation form (1). None is a lawyer's
own phrasing. Before that, the check found runs from three of my sentences that followed a
lawyer's word order (a pair of defined terms in the same order; one question's framing, which
reused a provision's wording the lawyer had quoted; two titles joined the same way); I reworded
all three and re-ran.

## What I did NOT do

- No model call, no seam draw, no server, no replay; no rubric, FIX_PLAN, SESSION_LOG or memory
  file edited; nobody contacted (the user sends the pack).
- Did not include the P3.2 stubbornness-guard session: the brief lists four readings, and that
  session's check is a retrieval criterion, not a reading marked for a lawyer.
- Did not give a link for the explanatory notes the P3.3 reading cites: no stored tool result
  carries an address for them, and the brief allows only tool-returned links.
- Did not restate any reading in my own words beyond the one-sentence session summaries and the
  questions, which repeat the recorded reading's terms.
- Did not write a `.gitignore` into the pack directory (the worktree guard refused a command
  naming it, and the brief says commit only this note).

## Acceptance (the brief's requirements)

| Requirement | Met? |
|---|---|
| One short section per reading, for the P3.2 reading and the three P3.3 readings | Yes, 4 sections |
| Question in one neutral sentence | Yes, 4 sentences, none quoted (overlap check above) |
| Reading quoted from the rubric `_note` or FIX_PLAN, not re-derived | Yes, 25 of 25 fragments verbatim |
| Provisions with legislation.gov.uk links, every one tool-returned | Yes, 18 of 18 located; the uncited explanatory notes and the case-law reading say why no link |
| One yes/no question with space for answer and comment | Yes, 4 |
| Cover note in plain language | Yes |
| Quote no lawyer's question or answer; name no lawyer | Yes (checks above) |
| No reading the records do not already record | Yes; the unclear points describe the text and the records, and resolve nothing |
| Unclear sources said to be unclear | Yes, 3 points |
| Pack gitignored | **No: the directory is not covered by `.gitignore`** (decision 1) |

## For the integrator to decide

1. **The pack directory is not gitignored.** `git check-ignore -v
   docs/prepilot-fixes/evidence/lawyer_pack/confirmation_pack.md` returns nothing; `.gitignore`
   covers `evidence/replay/`, `rubrics/`, `seam/` and `replay_set.json` only. The pack names the
   matters, so add `docs/prepilot-fixes/evidence/lawyer_pack/` to `.gitignore` (or move the
   pack under `seam/`) before any broad `git add`. Until then it is an untracked file in the main
   checkout.
2. **Three points the pack marks as unclear, for the user to see before sending:**
   - P3.2 reading: the records do not say which category of material the subject is. The
     provision the reading relies on most speaks of one category; another processing route, for
     other categories, does not obviously name the subject; and the rubric counts as contradicted
     a statement that this other route is closed to it, for which the records cite no provision.
     If the lawyer's answer turns on the category, the rubric's `contradicted` list may need
     re-scoping. This bears directly on why P3.2 is parked.
   - One P3.3 reading: a paragraph of the instrument's interpretation provision says where the
     instrument applies to one kind of application; the records treat it as text and do not
     discuss whether it bears on the undefined phrase.
   - The case-law P3.3 reading: the frozen classification's diagnosis states the doctrine's
     jurisdiction outright; the rubric's reading is narrower and states nothing either way. The
     pack quotes both and resolves neither.
3. **Links are in the `/id/` form the tool returned**, which redirects to the provision; two open
   at the instrument's made version (the pack says so). If the user prefers the redirected form,
   that would no longer be the exact tool-returned URL.
4. **One link is located only in an older directory** (`baseline`), not in the four most recent;
   its text there carries the words the reading relies on.
5. The pack says it is a draft for the sender to review; the cover note's promise (replies used
   only to decide whether each reading stays as the standard) is the user's to confirm.
