# AILA — Overview

*A plain-English guide to what AILA is, what it does, and where its limits are. No technical
knowledge assumed.*

*Last updated 13 October 2026, for release 2026.10.4.*

---

## What it is

AILA (AI Legal Assistant) is a research assistant for legal professionals. You ask a legal question in
plain English; AILA goes and reads the actual source material — Acts of Parliament, statutory
instruments, judgments, parliamentary debates — and comes back with an answer that quotes what it
found and links to every source it used.

Three things make it different from a general-purpose chatbot:

1. **It looks things up rather than recalling them.** For every substantive question, AILA searches
   official databases and retrieves the real text before answering. Answers are built from retrieved
   material, not from the model's memory of what the law probably says.
2. **It is open about what it could not check.** Under each legislation answer it says what was
   searched and the limits of that search. A gap in its database is not presented as proof that the
   law does not exist, and it says a provision is in force only where a record supports it.
3. **It runs in the organisation's own environment.** The application, the databases and all chat
   history sit inside the organisation's environment rather than on a commercial service. (The AI
   model that does the reasoning is a separate service: see *Privacy and data handling*.)

**AILA is a proof of concept.** It is not yet approved for production use, and its answers must be
checked before they are relied on.

## Who it is for

Legal professionals doing real research: finding the provision that applies, checking what has
amended or commenced it, tracing what a Minister said about a clause's purpose, pulling together the
authorities on a point. It assumes a professional reader who will check the sources — it is a
research tool, not a source of legal advice.

---

## A family of assistants, not one bot

AILA is a *set* of assistants built from one shared system. Each one is an expert in a different body
of material, has its own name and look, and keeps its own separate history — but they all behave the
same way and can talk to each other.

| Assistant | Knows about |
|---|---|
| **AILA** (legislation) | UK legislation — Acts and statutory instruments, with the record of how they have been amended, commenced, repealed or revoked, and what each instrument was made under — and UK case law (judgments from the National Archives), including whether a decision was appealed |
| **ParliChat** (Scottish Parliament) | Holyrood proceedings — chamber debates and committee sessions, word for word — plus Scottish bills, MSPs and written answers |
| **HansardChat** (Westminster) | UK Parliament proceedings — Commons, Lords, Westminster Hall and Public Bill Committees, plus written statements and written answers — and MPs, members of the Lords and UK bills |

**They can consult each other.** Where administrators have connected them, if you ask the legislation
assistant what was said in Parliament about a clause, it can put the question to its parliamentary
sibling and fold the answer into its own, rather than telling you it cannot help. If no sibling
assistant is connected, it simply says so — it never pretends to have looked.

---

## How a question gets answered

Behind the scenes each assistant works as a pair:

- A **conversation partner** talks to you. It decides whether your message is a chat, a question it
  needs to clarify first, or a research task. If your question is ambiguous, it asks — and can offer
  the likely readings as buttons you click instead of retyping.
- A **researcher** does the digging. It receives a written brief, searches the relevant databases,
  retrieves the specific provisions, sections or speeches that matter, and writes up what it found
  with citations. It works from the brief alone, which is deliberate: it cannot drift onto something
  it half-remembers from earlier in the conversation.

**Three modes.** The **Mode** menu in the sidebar sets how much work each question gets:

- **Conversational** — a quick back-and-forth. On the legislation assistant, each question gets a
  narrow, focused lookup and a short answer. Always available.
- **Research** — a full research pass and a structured answer that leads with the bottom line, sets
  out the analysis, notes the jurisdiction and what can be said about whether the material is in
  force, and lists its references.
- **Deep Research** — for a substantial piece of work: you approve a research plan first (see below).

The parliamentary assistants answer in the same way in Conversational and Research mode.
Administrators can switch the Research and Deep Research modes on or off.

**Which jurisdiction.** If your question names no jurisdiction, the legislation assistant answers for
Scotland and says so. If you ask about the UK, it answers for each of England, Wales, Scotland and
Northern Ireland, and says where the law differs.

**How long it takes.** A focused question is usually answered in a minute or two. Broad questions
that span several Acts or many debates, and Deep Research, take longer — sometimes several minutes —
because the assistant is genuinely fetching and reading large documents while you wait.

---

## What you can do with it

**Ask and follow up.** Ordinary conversation. Answers can end with suggested next questions you
click, so following a thread does not mean retyping. The buttons only send a question; they never
change your settings.

**See exactly where an answer came from.** Every response has a sources list showing the
legislation, judgments or debates the answer relies on, each by its title, with links straight to the
official source — legislation.gov.uk, the National Archives, parliament.scot,
hansard.parliament.uk. You can check any claim in a couple of clicks.

**Deep Research: approve a plan before it runs.** Instead of answering immediately, the assistant
drafts a **research plan** — a numbered list of the steps it proposes to take. You edit it: reword a
step, drop one, add one you care about, reorder them. Only when you approve does it carry out the plan
step by step, each step building on what the earlier ones found, and write an integrated report,
flagging any gaps it could not close. The plan you approved is stored with the answer, so there is a
record of what was asked for and what was done.

**Narrow the search before it starts.** The **Filters** button sets the scope for your questions:

- on the legislation assistant: the **research type** (legislation only, case law only, or both),
  jurisdiction, type of legislation (Acts, statutory instruments and rules, or draft instruments) and
  a range of years;
- on ParliChat: the type of record (chamber debates, written answers or committee transcripts), the
  parliamentary session (the current session by default) and a date range;
- on HansardChat: the House, the type of record, the Parliament and a date range.

Filters are enforced on the search itself, not merely requested politely of the model. If you need
case law and the legislation assistant is set to legislation only, it tells you where to change it:
Filters, then Research type.

**Get more out of legislation.** On the legislation assistant you can:

- **cite precisely** — answers cite the subsection or schedule paragraph they rely on, and the link
  opens that provision;
- **read schedules** — when an instrument is read in full, its schedules and annexes come with it,
  and a schedule paragraph asked for by number is fetched directly;
- **trace changes** — ask which later legislation amended, brought into force, repealed or revoked a
  provision. Where legislation.gov.uk records the date a provision was brought into force, the answer
  gives it, with any qualification such as "for specified purposes";
- **ask what was made under a section** — "which regulations were made under section 95 of this
  Act?" gets the full list from a record of about 87,000 instruments (Scottish statutory instruments
  from 1999, UK statutory instruments from 1987), with the total, what the record covers, and which
  of them legislation.gov.uk records as revoked.

**Watch the parliamentary moment, not just read it.** Where administrators have switched it on,
ParliChat can attach a video link to a Scottish Parliament citation that starts at the moment the
words were spoken. It depends on the sitting having subtitles: about half of the sittings since 2021
have them, most of the recent ones, and many older ones have none. When it cannot place the moment,
it simply omits the link.

**Keep work together in a matter.** Related chats can be grouped into a *matter* — a workspace for one
piece of work — with notes alongside them. The assistant is told which matter a chat belongs to, and
it can draw up a summary of the research done so far on the matter, or a list of the gaps in it, which
you can save as a note.

**Bring your own documents.** You can attach PDF, Word or plain-text documents to a chat and ask
questions about them alongside the official sources.

**Work on several things at once.** You can start a piece of research, switch to another chat and
carry on working while it runs. Keep the browser tab open until it finishes: refreshing or closing
the tab still loses a run in progress.

**Know what it searches, and what has changed.** In the Settings menu, **Data Sources** describes
exactly what each assistant searches and the limits of each source, and **Release notes** lists what
has changed since the pre-pilot, with the version and build your server runs.

**Tell it when it got it wrong.** You can mark any answer helpful or unhelpful, and say why. Those
ratings are not just reporting: helpful answers are used as examples of what good looks like when
anyone asks a similar question, and the reasons given for unhelpful ones are fed back as warnings.
Where administrators have switched them on, there is also a short end-of-session form and a weekly
user survey, so problems surface as evidence rather than anecdote.

---

## What keeps the answers trustworthy

- **Citations are compulsory.** The research step is instructed to answer only from what it
  retrieved, and to cite it. If it did not find something, the honest answer is that it did not find
  it.
- **Links are checked.** A link to a legislative provision the research did not actually retrieve is
  not passed off as one: it is pointed at the Act and marked, or removed.
- **It says what it searched.** A line under each legislation answer names the searches run and
  their limits, including that the legislation database is incomplete. A gap in the database is not
  presented as proof that the law does not exist.
- **"Nothing found" is never dressed up as "unavailable".** If a search genuinely returns no
  records, that is what you are told — distinct from a source not being connected at all.
- **"Not held" is not "wrong".** If you cite an instrument by number and the database does not hold
  it, the assistant says so, and that this does not show whether your citation is right. Where it
  can, it reads the instrument from legislation.gov.uk instead, and tells you.
- **In force only where a record says so.** The assistant does not infer in-force status from the
  version of the text it holds. It states what the record of changes shows, with its date; a
  commencement date is never presented as proof that a provision is in force today, and "no
  revocation recorded" is never treated as "in force".
- **"Made under" only from the instrument's own words.** What an instrument was made under is stated
  only where the assistant has read the instrument saying so.
- **Interpretation is given as a reading.** Where the text does not settle a point, the answer gives
  it as a reading rather than as settled law, and does not say that a general rule applies unless it
  found the provision that applies it.
- **Summaries keep to their source.** When the assistant condenses a long document, it may not add
  conclusions, legislation or case citations the document does not contain.
- **No invented options.** When the assistant offers you clarifying choices, it may only offer scope
  choices grounded in the conversation or in what it actually retrieved. It is specifically barred
  from suggesting an Act, instrument or case it has not looked up, precisely because a one-click
  button makes a plausible-looking wrong turn too easy to take.
- **Verbatim where verbatim matters.** Parliamentary retrieval returns the actual contributions
  rather than summaries, which is what makes it usable for questions about what a Minister said a
  provision was for.
- **Incomplete work is reported as incomplete.** A research step that stopped early, or whose reply
  was lost, is reported as such — never as having found nothing.
- **It still needs checking.** AILA can misread, retrieve incompletely, or answer a subtly different
  question than the one you meant. It is a fast, well-referenced first pass — not a substitute for
  professional judgement, and not legal advice.

## Privacy and data handling

- **A notice before first use.** Each assistant shows a notice before it is used, listing what must
  not be entered: information classified above OFFICIAL, personal data, details of ongoing
  proceedings not in the public domain, privileged or confidential information, commercially
  sensitive information, and anything bearing a protective marking caveat. Questions should be framed
  in general, hypothetical or anonymised terms.
- **The application and all its data can be hosted on-premise or in the cloud.** Chats, ratings,
  uploaded documents and the parliamentary archive all live in the organisation's own databases.
- **Questions do go to an AI model service.** The reasoning itself is currently done by a large
  language model run by a third-party provider outside the organisation's secure network, so your
  question and the material retrieved for it are sent to whichever model service the administrators
  have configured. This is the main thing to understand about where data travels, and it is why
  sensitivity of input matters. The searches the assistant runs also go to the public databases it
  reads.
- **Queries and answers are recorded.** Every question and answer is kept and may be reviewed for
  security, compliance and quality. Do not assume any query is private.
- **Ratings are shared.** A question and answer you rate, and the reason you give for an unhelpful
  rating, can be shown to the assistant as guidance when another user asks a similar question.
- **Diagnostic logs are only partly redacted.** On the legislation assistant, the searches the
  researcher runs are logged by their *shape* — length and a fingerprint — rather than their text.
  But the research brief handed to the researcher, which restates your question, is logged in full
  on every assistant, as are the parliamentary assistants' searches and the keywords taken from your
  question to find similar rated answers. Diagnostic logs are kept for 14 days.
- **Backups.** AILA includes a nightly backup of every database, verified by reading it back in full,
  and an administrator can restore one part — chats, ratings, users, settings — without disturbing the
  rest. The nightly backup has still to be switched on at the server, and copies are not yet kept off
  the server.

## What administrators can see and control

Administrators have a portal covering:

- **Users** — accounts and roles. There is no public sign-up; accounts are created by an
  administrator.
- **Usage, performance and cost** — how much the service is used, how quickly it responds, and what
  each query costs to run.
- **Quality and efficiency** — automatic monitoring of whether the assistants are researching
  *well*: whether they duplicate work, search in circles, or ignore the required answer structure.
  Each assistant is judged against a baseline appropriate to its own subject matter.
- **The AI model** — which model service and model the assistants use, switchable without a restart.
- **Feature switches** — Matters, the Research and Deep Research modes, suggested-question buttons,
  the session feedback form, the weekly survey and Scottish judgments can each be turned on or off
  without a code change, as can the cost-saving caches.
- **Connected assistants** — which sibling assistants this one may consult.
- **Data coverage** — how much of the Scottish Parliament archive has been gathered and how current
  it is.
- **Service health and feedback** — errors, outages, ratings, comments and survey responses, with
  exports for analysis.
- **Backup and restore** — the state of the backups, and a restore of one part of the data.
- **Cost controls** — repeated work is cached, so identical retrieval and summarising work is not
  paid for twice, either within a single piece of research or across users asking about the same
  provision with the same question. A cached result is reused only where the source text and the
  question are exactly the same.

## Known limits

- **The legislation database is incomplete.** Most secondary legislation made in the current year is
  not yet held, and some older Acts are missing. The text held can lag months — for obscure
  legislation, years — behind the amendments made to it, and neither version of the text says
  whether a provision is in force today.
- **The made-under record has gaps.** It does not cover statutory instruments made before 1987
  (mostly published only as scanned images) or Northern Ireland Statutory Rules.
- **Case law is not complete.** The National Archives collection does not include most lower courts
  or first-tier tribunals, and coverage of older cases is incomplete. Scottish courts are not
  covered until Scottish judgments are switched on (see below), and Northern Irish courts are not
  covered; appeals from either to the UK Supreme Court are. A search can miss a judgment the
  collection holds.
- **Coverage differs by assistant.** Westminster proceedings are searched live, so they are as
  current as Hansard's own publication, but select committee evidence is not covered. Scottish
  Parliament proceedings are searched from a locally gathered archive that is comprehensive in full
  text from 2021 onwards; earlier sessions are only partly gathered and may return short excerpts or
  nothing. Both parliaments publish their reports a little after each sitting, so the last few days
  may not yet be available.
- **Video timestamps are partial** — they depend on subtitles that many sittings do not have, and
  the feature is off unless administrators switch it on.
- **A run is lost if the tab is closed.** Research survives switching chats, but not a refresh or a
  closed tab.
- **Answer quality depends on the model in use.** A capable model researches efficiently and follows
  the required structure; a weaker one is markedly worse on identical infrastructure. Administrators
  choose the model.
- **It is a proof of concept, and not legal advice.** Every answer is a starting point to be
  verified against the sources it cites.

## What is coming

- **Scottish judgments.** The legislation assistant can also search the judgments published by the
  Scottish Courts and Tribunals Service — the Court of Session, the High Court of Justiciary, the
  Sheriff Appeal Court, published sheriff court decisions and Scottish tribunals, from 1998. It is
  built and its use has been agreed; it will be switched on once the server can reach the Scottish
  Courts site. Until then, answers say which Scottish courts are not covered.
- **Further improvements** from the analysis of the pre-pilot continue to arrive in releases, listed
  in Settings, then Release notes.
