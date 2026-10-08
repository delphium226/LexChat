# Changelog

AILA releases use **calendar versions, `vYYYY.MM.N`**: the Nth release cut in
that month (`v2026.09.3` is the third release of September 2026). Each release
is an annotated git tag on `main`, and the `VERSION` file at the repo root
names the last release the code contains. How to cut one is in CLAUDE.md,
*Releases*.

To see which version a server is running, look at any of these:
- the **About** box in the app (Settings → About);
- `GET /api/bot-info`: `version`, plus `build` (`git describe`, for example
  `v2026.09.2-3-gabc1234` three commits past the release);
- the first line the server logs at startup: `[Startup] AILA <version> (build <build>)`.

Row references (P1.1 and so on) are to `docs/prepilot-fixes/FIX_PLAN.md`,
where each row carries its evidence and acceptance.

## Unreleased

On `fix/prepilot-defects` since 2026.09.3, waiting for the next cut.

Saying honestly what was and was not found:
- When case law was searched, say that a search can miss a judgment the
  database holds, so one missing from its results may still exist: that is not
  proof of absence (P4.15).
- When a reply searched only within instruments, say so in the scope line:
  which instruments and terms were searched, and that a provision missing
  from such a search may still be in the instrument and in the index
  (P4.17).
- Don't say no change record was consulted when one was: say that the
  records consulted list neither a commencement nor a repeal (P4.18).
- When an instrument cited by number is looked up and is not in the index,
  say that it is not held in this index, which is incomplete, and that this
  does not show whether the number is accurate. It used to say this was "not
  a sign that the citation is wrong", which a lookup cannot establish (P4.21).

Change records:
- Where a change record lists a commencement made by another instrument, give
  the date legislation.gov.uk's Changes to Legislation record gives for it, with
  its qualification ("wholly in force", "for specified purposes"), read
  through the LEX API. A date earlier than the day the commencing instrument
  was made is refused, and the reply says when the record could not be read.
  The date says when the provision was brought into force, never that it is in
  force now (P3.21).
- When listing the changes made to or by an instrument, keep each change with
  the provision that made it, and say how many changes a long list leaves out.
  The changed provisions and the provisions that changed them used to be two
  separate lists, which lost which made which (one lawyer was given the wrong
  provision for an insertion), and the second list was cut at six with no
  count (P3.19).
- Say a provision is "not recorded as commenced" only where the change record
  lists, in full, the commencements made by other instruments. An
  instrument's own commencement provision says how its provisions come into
  force, not whether they have, so it is no longer treated as evidence either
  way; where no record was consulted, say neither (P3.24).

Jurisdiction:
- Where a question names no jurisdiction, answer for Scotland and say so;
  where it asks about the UK, answer for each of England, Wales, Scotland and
  Northern Ireland and say where the law differs. This applies to
  conversational replies and quick lookups (P3.4).
- The jurisdiction filter's notes no longer use letter codes the index never
  sends, and say that most search results carry no stated extent (P3.4).

Search results:
- Keep each legislation search result's own published summary (its
  description, cut to 600 characters), so a commencement date or enabling
  power it states is visible at the first step. The search note says it may be
  quoted with a citation and is not evidence of in-force status (P3.6).

Quick lookups:
- The quick-lookup research step no longer reads an instrument's whole text,
  which its own instructions forbade and which never included schedules or
  annexes. An SI's own recital of its enabling power, and the date its held
  text is up to date to, now come from the index record, looked up before the
  SI is searched. The existing "in-force status is not something this index
  reports" sentence therefore appears on more quick-lookup replies (P3.25).

Schedules and annexes:
- When several searches in one step name schedules of different instruments
  at the same time, fetch each instrument's provision list once and keep to the
  per-step limit, now 8 instruments (P3.12).
- When the research step reads an instrument's whole text, ask the index for
  its schedules and annexes too, and say which ones the text carries, or that
  the index holds none for it. Every whole-text read used to leave them out
  without saying so (P3.27).
- When a search within an instrument names a schedule or annex ("Schedule
  B1, paragraph 43", "Annex XIV, Chapter V") and the results leave it out,
  fetch that schedule or annex from the index and hand over the part named,
  cut at its own heading where it cuts cleanly, or the whole of it summarised
  for the question; where the index holds no schedule for the instrument, say
  so. Both the quick-lookup and the research steps do this (P3.12).
- When a schedule fetched for a search is too large to hand over whole and
  the search names no paragraph, hand over the schedule's paragraph headings
  and the paragraphs whose headings share a word with the search, each cut at
  its own heading, instead of one summary of the whole schedule. Where a
  schedule is still summarised, say that it was retrieved and that the summary
  is a condensed reading of it, so a paragraph the summary leaves out is not
  read as missing (P3.12).
- Read a list of schedule paragraphs separated only by spaces ("paragraphs
  42 43 44") as all of them, not just the first (P3.12).
- Where the index's complete list of an instrument's provisions has been read
  and a search limit within that instrument is then reached, say what that
  list holds, so a schedule the index does not hold is not put down to the
  limit (P3.27, P3.12).

Case law:
- List case-law search results most relevant first, not newest first, and say
  so in the search note. Built; its measured acceptance is not yet met (P3.22).
- Date ranges on a case-law search now apply. They never did: the National
  Archives ignored the form we sent. A start date after the end date is
  refused rather than searched (P3.9).
- Say how many judgments matched a case-law search, not only how many were
  shown, and that they are listed newest first, so a negative drawn from the
  list says what was searched (P3.23).
- Retry a case-law search or judgment fetch that hits the National Archives'
  rate limit, as legislation calls already are (P4.19).

Interpretation. P3.17 and P3.3 stay open: P3.17's change fixed the turn it
aimed at but has not met its acceptance.
- In quick lookups, when an Act does not define a word, look for the general
  interpretation legislation and retrieve the provision saying which Acts it
  applies to before saying it applies (P3.17).
- Also remove the unscoped agreement opener "You are correct to highlight
  this" (P4.16).

Already in 2026.09.3, ticked since: the summariser rule against adding its own
conclusions (P3.16).

Replay harness and measuring tools only, no product change: the negatives
grader reads "a search of the database ... returned no results" as attributing
the miss to the search (P4.15). The interpretation grader reads "As you
suggest, ..." as agreement rather than a hedge (P3.3); the position grader
reads a negated sentence as taking no position (P3.2); a new check reports
whether the section-search scope line appears on exactly the replies that
searched only within instruments (P4.17). The derivation grader no longer
reads an application or appeal "made under section N" as a claim about what
an instrument was made under, and the interpretation grader reads "on a third
reading" (a numbered or contrasted reading) as a hedge (P3.3). A new
`replay_report negcurrency` lists every claim that a provision is not yet
commenced, not in force or remains in force, and grades each against what the
conversation retrieved; footer wording is now screened against it (P3.24).
It now reads the change record's new shape, where on the old reading a
negative the record contradicted was graded supported (P3.24). The seam
tools offer the quick-lookup Worker the same tool list the product does
(P3.25). `python -m tools.lex_probe --caselaw` live-checks the case-law total
and the date filter (P3.23, P3.9), and whether `order=relevance` still
reorders the same 50 results (P3.22). The depth grader has a ground
truth for one schedule-paragraph question, and a new `replay_report
schedules` checks what an answer says about a schedule or annex: a held one
called not held, or one the index does not hold blamed on a search limit
(P3.12, P3.27). A new `python -m tools.lgu_probe` reads legislation.gov.uk's
dated "Changes to Legislation" effects, directly or through LEX (P3.21,
P5.4). New `replay_report` checks: `authorities` grades which case-law authorities a
run retrieved, read and cited against a rubric (P3.22); `cmcdates` lists every
commencement date an answer states and whether a retrieved source states it
(P3.21); `jurisdiction` checks that a reply names its jurisdiction (P3.4); with
two scripted replays of P3.4's opening turns. `lex_probe --caselaw`'s count
and date checks now send the product's own request (P3.22). `authorities`
counts an out-of-corpus authority as named only by its citation or its full
party names, never by one surname, and reads a link whose label holds a
bracketed citation (P3.22); `negcurrency` reads both stored shapes of a
section-search result (P3.24); `commencements` grades scripted replays
(P3.21); `corpus`'s description labels are true before and after P3.6.

Planning tools only, no product change: a new `python -m tools.plan_lint`
checks the fix plan's structure (one table cell per column, every row in the
bucket index once, done marks agreeing with the ticks, dependencies,
the top progress line's counts, balanced bold, UTF-8); `plan_status` now
shares its parsing.

## 2026.09.3 — 2026-09-29

Third cut of the pre-pilot defect fixes (merge `1e30774`), and the first
release tagged when it was cut.

Saying honestly what was and was not found:
- Remove prompt wording that says the whole database lacks something (P4.6).
- Test whether an instrument is held, by its number (P3.7).
- Don't say "no case law found" when case law wasn't searched (P4.7).
- Report a lost research step as lost, not "no results", and name each
  step's outcome in the progress events (P4.5).

Reliability and cost:
- Cap the length of a research step's reply, and re-run a step whose reply
  came back empty after heavy reasoning instead of retrying it (P4.10).
- Re-run a research step whose provider call timed out idle, instead of
  retrying the same request (P4.11).

Interpretation. P3.2 and P3.3 stay open: these changes improved their
measurements but did not meet their acceptance.
- Give an interpretive point as a reading, and don't say that a general rule
  (an interpretation Act, a doctrine) applies unless the provision applying
  it was retrieved (conversational answers and quick lookups; P3.3).
- In Deep Research reports, the same rule, and name the courts the case law
  comes from without saying it binds or persuades in another jurisdiction
  (P3.18).
- When case law was searched, say that a common-law rule taken from a court
  outside Scotland has not been checked against Scots law (P3.3).
- Stop the document summariser adding legislation, or conclusions of its own,
  that the retrieved text does not contain (P3.3, P3.16; P3.16 stays open).
- Remove an unscoped agreement opener ("You are absolutely right to challenge
  this") from the start of an answer (P3.2, widened by P4.13).

Presentation:
- Show one search-scope line, not two, when the model copied the previous
  turn's (P4.14).

For the eval harness: the audit event is **schema v6** (`delegations[].lost`,
P4.5).

On deploy: the local prompt cache version is now **v3**, so no summary cached
before this release is served again. That is intended (older summaries may
carry text the source did not), and the cache hit rate will be low for a while.

Also on `main` since 2026.09.2:
- Release versioning: the `VERSION` file, the version in `/api/bot-info`, the
  About box and the startup log, and this changelog.

Replay harness and measuring tools only, no product change: P0.6, P3.15, and
the graders and probes used to measure the rows above.

## 2026.09.2 — 2026-09-23

Second cut of the pre-pilot defect fixes (merge `c77e779`). Tagged
retroactively.

- Stop the chat reply dropping a subsection the research step had already
  written (P3.13).

## 2026.09.1 — 2026-09-22

First cut of the pre-pilot defect fixes (merge `d8fd73b`), and the first
versioned release. It was tagged retroactively. Everything merged to `main`
before it, including federation, Deep Research, the caching stack and the
Westminster bot, is part of this release and is recorded in the git history
rather than here.

Search and retrieval:
- Make the jurisdiction filter work (P1.1).
- Stop the "current only" filter implying in-force status (P1.2).
- Report the search's true match count (P1.3).
- Verify the enabling power (P2.3).
- Cap how long a step may keep searching (P2.7).
- Retrieve amendment and commencement relations (P3.5).
- Stop a step looping on instruments it already has, and write up findings
  at the cap (P3.8).
- Remove the unused case-law court filter (P4.4).

Saying honestly what was and was not found:
- Disclose a research halt as a limit, not a finding (P2.1).
- Explain every "not found": what was searched, and its limits (P2.2).
- Disclose the Scottish case-law corpus gap (P2.4).
- Stop asserting in-force status (P2.5).
- Don't reformat a halted step into an empty report (P2.6).
- Re-qualify a "not found" repeated from an earlier turn, or given by a turn
  that searched nothing (P2.8, with P2.10).
- Record memo-served searches in the search scope (P2.9).
- Never show a blank or lost reply (P4.2).

Citations:
- Link citations to the provision, not the Act (P1.4).
- Enforce provision links in code (P1.6).
- Cite the provision at the subsection asked for, not the whole section (P3.1).
- Say what a cited subsection's sibling subsections provide (P3.11).

Interaction:
- Fix the research-mode dead-end and the mode-switch wording (P4.1).

For the eval harness: the audit event is **schema v5** (`halted`,
`empty_completions[]`, `halted.written_up`, `mode_change`).

Also in this cut, with no product change: the replay harness and baselines
(P0.1, P0.2, P0.3, P0.5, P1.5), and two enquiries about the LEX corpus
(P5.1, P5.3).
