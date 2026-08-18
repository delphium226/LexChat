# AILA — Overview

*A plain-English guide to what AILA is, what it does, and where its limits are. No technical
knowledge assumed.*

---

## What it is

AILA (AI Legal Assistant) is a research assistant for legal professionals. You ask a legal question in
plain English; AILA goes and reads the actual source material — Acts of Parliament, statutory
instruments, judgments, parliamentary debates — and comes back with an answer that quotes what it
found and links to every source it used.

Two things make it different from a general-purpose chatbot:

1. **It looks things up rather than recalling them.** For every substantive question, AILA searches
   official databases and retrieves the real text before answering. Answers are built from retrieved
   material, not from the model's memory of what the law probably says.
2. **It runs on the organisation's own servers.** The application, the databases and all chat history
   sit inside the organisation's environment rather than on a commercial service.

## Who it is for

Legal professionals doing real research: finding the provision that applies, checking whether it is in
force, tracing what a Minister said about a clause's purpose, pulling together the authorities on a
point. It assumes a professional reader who will check the sources — it is a research tool, not a
source of legal advice.

---

## A family of assistants, not one bot

AILA is a *set* of assistants built from one shared system. Each one is an expert in a different body
of material, has its own name and look, and keeps its own separate history — but they all behave the
same way and can talk to each other.

| Assistant | Knows about |
|---|---|
| **AILA** (legislation) | UK legislation — Acts and statutory instruments — and UK case law (judgments from the National Archives), including whether a decision was appealed |
| **ParliChat** (Scottish Parliament) | Holyrood proceedings — chamber debates and committee sessions, word for word — plus Scottish bills, MSPs and written answers |
| **HansardChat** (Westminster) | UK Parliament proceedings — Commons, Lords, Westminster Hall and Public Bill Committees — plus MPs, members of the Lords and UK bills |
| **Drafting assistant** | Legislative drafting guidance and precedent. **Currently in development, not yet released.** |

**They can consult each other.** If you ask the legislation assistant what was said in Parliament
about a clause, it can put the question to its parliamentary sibling and fold the answer into its
own, rather than telling you it cannot help. If no sibling assistant is connected, it simply says so
— it never pretends to have looked.

---

## How a question gets answered

Behind the scenes each assistant works as a pair:

- A **conversation partner** talks to you. It decides whether your message is a chat, a question it
  needs to clarify first, or a research task. If your question is ambiguous, it asks — and offers the
  likely readings as buttons you can click instead of retyping.
- A **researcher** does the digging. It receives a written brief, searches the relevant databases,
  retrieves the specific provisions, sections or speeches that matter, and writes up what it found
  with citations. It works from the brief alone, which is deliberate: it cannot drift onto something
  it half-remembers from earlier in the conversation.

You then get an answer that leads with the bottom line, sets out the analysis, notes the jurisdiction
and whether the material is in force, and lists its references.

**How long it takes.** A focused question is usually answered in a minute or two. Broad questions
that span several Acts or many debates take longer, because the assistant is genuinely fetching and
reading large documents while you wait.

---

## What you can do with it

**Ask and follow up.** Ordinary conversation. Each answer ends with suggested next questions you can
click, so following a thread does not mean retyping.

**See exactly where an answer came from.** Every response has a sources panel listing the
legislation, judgments or debates used, with excerpts and links straight to the official source —
legislation.gov.uk, the National Archives, parliament.scot, hansard.parliament.uk. You can check any
claim in a couple of clicks.

**Deep Research: approve a plan before it runs.** For a substantial piece of work you can switch to
Deep Research mode. Instead of answering immediately, the assistant drafts a **research plan** — a
numbered list of the steps it proposes to take. You edit it: reword a step, drop one, add one you
care about, reorder them. Only when you approve does it carry out the plan step by step and write an
integrated report, flagging any gaps it could not close. The plan you approved is stored with the
answer, so there is a record of what was asked for and what was done.

**Narrow the search before it starts.** Filters let you restrict a question by source type, by date
range, by record type (debates, written answers, committee) and — for Holyrood — by parliamentary
session. These are enforced on the search itself, not merely requested politely of the model.

**Watch the parliamentary moment, not just read it.** For Scottish Parliament citations, the
assistant can attach a video link that starts at the exact moment the words were spoken. This is
optional and depends on subtitles being available: it works for roughly half of the sittings held
recently, and older ones have no subtitle track at all. When it cannot place the moment, it simply
omits the link.

**Keep work together in a matter.** Related chats, uploaded documents and notes can be grouped into
a *matter* — a workspace for one piece of work — so a case's research history stays in one place.

**Bring your own documents.** You can attach PDFs or Word documents to a chat and ask questions
about them alongside the official sources.

**Work on several things at once.** You can start a piece of research, switch to another chat and
carry on working while it runs. 

**Tell it when it got it wrong.** You can rate any answer and leave a comment. Those ratings are not
just reporting: strongly rated answers are used as examples of what good looks like for similar
future questions, and criticisms are fed back as warnings. There is also a short end-of-session form
and an occasional user survey, so problems surface as evidence rather than anecdote.

---

## What keeps the answers trustworthy

- **Citations are compulsory.** The research step is instructed to answer only from what it
  retrieved, and to cite it. If it did not find something, the honest answer is that it did not find
  it.
- **"Nothing found" is never dressed up as "unavailable".** If a search genuinely returns no
  records, that is what you are told — distinct from a source not being connected at all.
- **No invented options.** When the assistant offers you clarifying choices, it may only offer scope
  choices grounded in the conversation or in what it actually retrieved. It is specifically barred
  from suggesting an Act, instrument or case it has not looked up, precisely because a one-click
  button makes a plausible-looking wrong turn too easy to take.
- **Verbatim where verbatim matters.** Parliamentary retrieval returns the actual contributions
  rather than summaries, which is what makes it usable for questions about what a Minister said a
  provision was for.
- **Currency and status are surfaced.** Answers state jurisdiction and whether provisions are in
  force, rather than leaving that for you to infer.
- **It still needs checking.** AILA can misread, retrieve incompletely, or answer a subtly different
  question than the one you meant. It is a fast, well-referenced first pass — not a substitute for
  professional judgement, and not legal advice.

## Privacy and data handling

- **The application and all its data can be hosted on-premise or in the cloud.** Chats, ratings, uploaded documents and
  the parliamentary archive all live in the organisation's own databases.
- **Questions do go to an AI model service.** The reasoning itself is done by a large language model
  reached over the internet or hosted on premises, so your question and the material retrieved for it are sent to whichever
  model service the administrators have configured. This is the main thing to understand about where
  data travels, and it is why sensitivity of input matters.
- **Logs are redacted by default.** The system's own diagnostic logs record the *shape* of a query —
  its length and a fingerprint — rather than its text, so day-to-day operational logging does not
  accumulate the substance of legal questions.
- **Nightly backups.** Every database is backed up each night and the backup is verified by reading
  it back in full. If something is deleted by mistake, an administrator can restore one part —
  chats, ratings, users, settings — without disturbing the rest.

## What administrators can see and control

Administrators have a portal covering:

- **Users** — accounts and roles. There is no public sign-up; accounts are created by an
  administrator.
- **Usage, performance and cost** — how much the service is used, how quickly it responds, and what
  each query costs to run.
- **Quality and efficiency** — automatic monitoring of whether the assistants are researching
  *well*: whether they duplicate work, search in circles, or ignore the required answer structure.
  Each assistant is judged against a baseline appropriate to its own subject matter.
- **Feature switches** — Deep Research, suggested-question buttons, matters, feedback forms and the
  cost-saving caches can each be turned on or off without a code change.
- **Data coverage** — how much of the parliamentary archive has been gathered and how current it is.
- **Service health and feedback** — errors, outages, and everything users have rated or commented on.
- **Cost controls** — repeated work is cached, so identical retrieval and summarising work is not
  paid for twice, either within a single piece of research or across users asking about the same
  provision. Caching never changes an answer's content — only what it cost to produce.

## Known limits

- **Coverage differs by assistant.** Westminster proceedings are searched live and are therefore
  current and complete. Scottish Parliament proceedings are searched from a locally gathered archive
  covering 2021 onwards in full text; older sessions are available only as short excerpts.
- **Video timestamps are partial** — roughly half of recent Scottish sittings, and none of the older
  ones, have the subtitles the feature depends on.
- **The drafting assistant is not released yet.**
- **Answer quality depends on the model in use.** A capable model researches efficiently and follows
  the required structure; a weaker one is markedly worse on identical infrastructure. Administrators
  choose the model.
- **It is not legal advice.** Every answer is a starting point to be verified against the sources it
  cites.

