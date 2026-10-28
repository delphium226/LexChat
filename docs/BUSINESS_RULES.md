# AILA legislation bot: business rules

**What this document is.** It sets out the rules that govern what the AILA legislation bot does. That covers what it searches, what it reads, what it may and may not say about the law, and what it tells the user about the limits of its research. It describes how the system behaves now. It does not argue for that behaviour or explain how it came about.

**Scope.** This covers the legislation bot only. The Scottish Parliament and Westminster bots share the code but follow different rules, and are not covered.

**Version described.** This describes branch `fix/prepilot-defects` at commit `e671bac` (28 October 2026). The live release is `v2026.10.4`. Rules marked **[not yet live]** are on the branch but are not yet in the live release.

---

## How to read the rules

Each rule has an identifier (BR-n.n), a statement of the rule, and how it is enforced. The enforcement label matters as much as the rule.

| Label | Meaning |
|---|---|
| **System** | Enforced by the software. It holds whatever the language model does. |
| **Instruction** | The language model is instructed to follow it. Capable models usually do, but nothing guarantees it, and compliance can vary with the model in use. |
| **System + Instruction** | Both. The model is instructed, and the software also enforces the rule or backs it up. |

Some of the most important rules are **Instruction** only. Section 15 lists the places where an instruction and the software's behaviour do not agree.

### Terms used

| Term | Meaning |
|---|---|
| **User** | The legal professional using AILA. |
| **Answering agent** | The model that talks to the user. It decides whether research is needed, briefs the research agent and writes the answer. It never searches anything itself. |
| **Research agent** | The model that searches and reads sources, then writes a report for the answering agent. Each piece of research is a separate *research step*. |
| **Round** | One turn of the research agent. In a round it may make several tool calls at once. Limits are counted in rounds, not individual calls. |
| **The index** | The LEX legislation index (i.AI). This is AILA's main source of UK legislation text. It does not hold every instrument, and its coverage is incomplete (BR-12.3). |
| **Change record** | The index's record of amendments, commencements, repeals and revocations, relation by relation. |
| **Made-under record** | AILA's own database of the enabling powers recited in the preambles of SSIs and UK SIs (section 6). |
| **Scope footer** | The italic *Search scope:* line the system appends to an answer (BR-12.2). |
| **Sources rail** | The list of sources shown beside an answer. |

---

## 1. Chat modes and research types

**BR-1.1 Two separate controls.** *System.*
The user sets two independent things:
- the **chat mode**, in the sidebar's *Mode* menu: Conversational, Research or Deep Research;
- the **research type**, under *Filters → Research filters → Research type*: Legislation only, Case law only, or Legislation & case law.

When an instruction names either control, it uses the on-screen name exactly as the user sees it.

**BR-1.2 Defaults.** *System.*
A new user starts in Research mode with Legislation only.

**BR-1.3 Conversational mode.** *System + Instruction.*
Conversational mode gives a short, quick answer.
- The research agent is told to make one discovery search, retrieve each instrument once, read one or two judgments at most, and answer in 2 to 5 sentences. Citations go inline, with no report headings and no References list (Instruction).
- It is **not given** the tool that reads an instrument's full text. It works from section searches and lookups (System).
- It is not told which filters are active. The filters are still applied in code (BR-2.x).
- The search limits in section 4 apply here too. They are wider than the instruction to search once.

**BR-1.4 Research mode.** *System + Instruction.*
Research mode produces a structured report. The research agent's tools and instructions depend on the research type (BR-1.6). The report must have these sections (BR-9.9):

| Research type | Required sections |
|---|---|
| Legislation only | Summary Answer (BLUF), Detailed Analysis, Jurisdiction & Status, References |
| Legislation & case law | Summary Answer (BLUF), Statutory Framework, Key Cases, Jurisdiction & Status, References |
| Case law only | Summary Answer (BLUF), Key Cases, Analysis, Jurisdiction & Currency, References |

**BR-1.5 Deep Research mode.** *System + Instruction.* See section 13.

**BR-1.6 What each research type searches.** *System.*

| Research type | Legislation tools | Case-law tools |
|---|---|---|
| Legislation only | yes | no |
| Case law only | no | yes |
| Legislation & case law | yes | yes |

**BR-1.7 Out-of-scope questions.** *Instruction.*
- **Legislation only, case-law question.** The answering agent must say that case law was not searched. It tells the user they can change the *Research type* to *Legislation & case law* under the *Filters* control, and that this takes effect from their next message in the same chat. It must not call this a "mode", point the user to Research mode, describe where a control sits on the screen, or tell them to start a new chat. It must not answer the case-law point from its own knowledge.
- **Case law only.** The mirror rule applies to legislation questions.

**BR-1.8 Both legislation and case law.** *Instruction.*
Under *Legislation & case law*, the brief to the research agent must contain two tasks. The first is to find the legislation. The second is to search case law using the user's own keywords and party names.

**BR-1.9 A changed setting is acknowledged.** *System.*
Each saved answer records the chat mode and research type it ran under. If the user then changes either one, the system adds a notice to the next request. The notice tells the model that the setting has changed, that it must not repeat earlier statements about its scope, and that it must act on the current setting. One change gets no notice: the automatic return from Deep Research to Conversational after a Deep Research run.

**BR-1.10 Hiding a mode.** *System, interface only.*
An administrator can hide Research mode or Deep Research mode with a feature flag. Both are shown by default. Hiding removes the option from the sidebar. When Research mode is hidden, the Conversational answering agent is also told not to suggest switching to it. The server itself does not refuse a hidden mode (BR-15.10).

---

## 2. Filters

**BR-2.1 The filters available.** *System.*
The filters are:
- Jurisdiction: All, England & Wales, Scotland, Northern Ireland, Wales, UK-wide only.
- Legislation type: All, Acts (primary), SIs & Rules (secondary), Draft instruments. Hidden under *Case law only*.
- Research type (BR-1.1).
- A date range, given as a pair of years. The upper year defaults to the current year.

There is no court filter and no "in force only" filter. The research agent chooses a court for itself on each case-law search (BR-8.3).

**BR-2.2 Jurisdiction means "applies in".** *System.*
A jurisdiction filter keeps legislation that **applies in** the chosen jurisdiction, not only legislation **made for** it. This applies to legislation searches only (BR-2.6). A UK-wide extent therefore counts for each constituent nation, so UK Acts and assimilated EU law survive a Scotland filter.

| Filter | Extents accepted |
|---|---|
| England & Wales | England, Wales, Great Britain, United Kingdom |
| Scotland | Scotland, Great Britain, United Kingdom |
| Northern Ireland | Northern Ireland, United Kingdom |
| Wales | Wales, Great Britain, United Kingdom |
| UK-wide only | United Kingdom only |

The extent "E+W+S+N.I." (all four nations) is read as the United Kingdom. "N.I." is read as Northern Ireland.

**BR-2.3 Unknown extent is kept, unless the instrument's type shows otherwise.** *System.*
About half of all index rows state no extent. Under a nation filter, such a row is kept unless its identifier marks it as belonging to another jurisdiction:

| Identifier prefixes | Belong to |
|---|---|
| asp, ssi | Scotland |
| nia, nisr, nisro, nisi, apni | Northern Ireland |
| asc, anaw, wsi, mwa | Wales |

A Welsh instrument is also kept under an England & Wales filter. If an extent contains a territory the system does not recognise, the extent is treated as unknown.

**BR-2.4 "UK-wide only" is strict.** *System.*
A row is kept only if its stated extent is the United Kingdom. Rows with an unknown extent are dropped.

**BR-2.5 A filtered result does not establish extent.** *Instruction.*
A row kept under a filter has not been shown to apply in that territory. Most rows state no extent. The research agent may give a territorial extent only where the source states one.

**BR-2.6 Where filters are enforced.** *System + Instruction.*

| Filter | Enforced in code on | Instruction only on |
|---|---|---|
| Jurisdiction | legislation searches | section searches, text reads, lookups, the change record, the made-under record, case law |
| Legislation type | legislation searches | everything else |
| Year range | legislation searches. The user's years and the model's own years are intersected: the later start and the earlier end win. | — |
| Date range (case law) | case-law searches. The window is intersected in the same way. An empty window, or a date that is not a date, means no search is run. | — |

The legislation type filter works on the identifier prefix:
- **Acts:** ukpga, ukppa, ukla, asp, nia, apni, anaw, asc, mwa.
- **SIs & Rules:** uksi, ssi, wsi, nisr, nisro, nisi, eur, eudn, eudr.
- **Draft:** ukdsi, sdsi.

**BR-2.7 Search sizes under a filter.** *System.*
- **Unfiltered:** a legislation search asks the index for 5 results.
- **With a jurisdiction or type filter:** it asks for 20, so that enough remain after filtering.
- **Results passed to the model:** at most 5.
- **What the model is told:** separately, how many rows the index matched, how many it was given, and how many the filters removed.

**BR-2.8 Default jurisdiction.** *Instruction.*
- **No jurisdiction named, no filter set:** the answering agent answers for Scotland and says so.
- **"UK" question:** it answers for each of the four parts of the UK.
- **Every brief:** states the jurisdiction.

The planner and the Conversational research agent carry the same rule. The research agents in Research mode are not told it directly.

**BR-2.9 The user is told which filters narrowed the search.** *System.*
The scope footer names only the filters that could have excluded something: a jurisdiction, a type, a lower year, or an upper year that is in the past. The default upper year (the current year) is not mentioned. If no filter narrowed the search, the footer says so.

---

## 3. The answering agent

**BR-3.1 No answers from its own knowledge.** *Instruction.*
The answering agent relies wholly on research. It must not answer from training data.

**BR-3.2 One piece of research per question.** *Instruction.*
The answering agent briefs the research agent once and answers from what comes back. It may brief again only if two things are both true. First, the first research reported an error or found nothing. Second, it can write a materially different and better-scoped brief. The software does not cap this. A request with more than one delegation raises an internal efficiency alert, and Deep Research is exempt from that alert.

**BR-3.3 Self-contained briefs, without speculation.** *Instruction.*
A brief must carry:
- the question;
- every identifier the user gave, verbatim;
- the jurisdiction;
- any earlier context it needs.

A brief must not:
- turn a bare citation into a case name;
- add any fact that did not come from the user or from a tool.

**BR-3.4 The user's own words reach the research agent.** *System.* **[not yet live]**
With a legislation research type in Conversational or Research mode, the user's latest message is passed to the research agent alongside the brief, cut at a word to at most 4,000 characters. Where the two differ, the brief governs. This does not happen in Deep Research, or under *Case law only*.

**BR-3.5 Pass-through in Research mode.** *Instruction.*
In Research mode, the answering agent presents the research report as it was structured. It does not condense it, it never drops References, and it never alters, shortens or removes a citation or link.

**BR-3.6 Shortening in Conversational mode.** *Instruction.*
In Conversational mode, the answering agent may shorten the report. It must keep every cited provision with its link, and must never reduce a provision citation to the bare name of the instrument. Section 9 sets out the repairs the system makes afterwards.

**BR-3.7 Readings, not law.** *Instruction, Conversational mode.*
- **Unsettled points:** where a point is unsettled, the answering agent presents it as a reading.
- **General rules:** it must not say that a general rule (an Interpretation Act provision, a common-law doctrine) applies to an instrument or in a jurisdiction unless a retrieved provision or source applies it there.
- **Application provisions:** before saying such a rule applies, the research agent is told to retrieve the instrument's application provision.

**BR-3.8 Disagreement.** *System + Instruction.*
When the user disputes an answer, the answering agent checks the text again. It changes its position only on text that decides the point, and does not open by agreeing (Instruction). The system removes an agreement opener at the start of an answer, in at most 2 passes. It keeps a scoped agreement, and keeps a plain "Yes, that is correct." (System).

---

## 4. Research limits

**BR-4.1 Searches of the index: 8 rounds per research step.** *System.*
In one research step, the research agent may search the index in at most **8 rounds**. Several searches in the same round count as one. From the 9th round on, every search is refused and is not run. The research agent is told:
- that the search was not run;
- that it must not say anything does not exist;
- that it must say that searching was cut short and name what it was still looking for.

Each step has its own allowance. The limit applies to *Legislation only* and *Legislation & case law*. Case-law searches are not counted. If the system cannot tell which round a search belongs to, the search runs.

**BR-4.2 Searches within one instrument: 3 rounds per instrument per step.** *System + Instruction.*
The research agent may search the sections of any one instrument in at most **3 rounds** per step, counted separately for each instrument. A later search is refused. A provision not reached must be reported as *not retrieved because searching was cut short*, never as absent from the instrument. If the system has already read the instrument's complete list of provisions, the refusal says what that list holds. A provision outside the list is then attributed to the index, not to the limit.

**BR-4.3 Step limit: 20 rounds.** *System.*
A research step stops after **20 rounds**. The same limit applies to the answering agent's own loop.

**BR-4.4 A stopped step writes up what it has.** *System.*
At the step limit, the research agent gets **one** final round with no tools. In it, it must:
- write up only what it has already retrieved;
- say that anything not reached "was not retrieved because this step's limit was reached";
- call the stop a fixed limit, not a time limit or an error.

The report is then labelled **PARTIAL findings**. If that round fails or produces nothing, the report says the step stopped before producing any findings.

**BR-4.5 Material read in one step: 250,000 characters.** *System.*
A research step may take in at most **250,000 characters** of tool output in total. After that, every further result is summarised before the research agent reads it, whatever its size (section 11).

**BR-4.6 Other per-step and per-request caps.** *System.*

| What | Cap |
|---|---|
| Instruments the system looks up automatically from one brief | 5 |
| Automatic lookups after a section search returns nothing | 8 per step |
| Instruments whose full list of provisions the system fetches | 8 per step |
| Instruments read from legislation.gov.uk because the index lacks them | 8 per request |
| Commencement-date reads (made dates) per change-record call | 8, 4 at once |
| Instruments listed from the made-under record | 40 |
| Instruments one Deep Research step hands to the next | 40 |
| Deep Research plan steps | 8 |

**BR-4.7 How a limit is disclosed.** *System.*
- **Search allowance refused (BR-4.1):** the scope footer says searching was limited. It gives the number of searches not run, and says the answer "may not reflect everything a longer search would have found".
- **Within-instrument limit reached (BR-4.2):** the scope footer says searching within an instrument was limited. It names up to 3 instruments whose full list of provisions was read, and for which the limit therefore caused nothing to be missed.
- **Step stopped (BR-4.3):** the answer opens with **"⚠ This answer is incomplete."** (BR-12.4).

---

## 5. In-force status, commencement, amendment and repeal

**BR-5.1 The index does not report in-force status.** *System + Instruction.*
No tool reports whether legislation is in force. A search result's *text version* (`final`, `revised`, `stub`) only says which version of the text the index holds. The bot must never treat a "revised" text as evidence that legislation is in force, and must never put a text version in brackets after an in-force statement.

**BR-5.2 No blanket currency claim.** *System + Instruction.*
The bot must never assert that an instrument, or a body of legislation, is current law. The ban is on the claim, not on particular words. Each of these is the same forbidden claim:
- "is in force"
- "all cited legislation is in force"
- "in operation"
- "remains in force"
- "still good law"
- "current law"
- "active status"
- "continues to apply"

The ban holds even where the claim is true. The research agent is told this (Instruction). The system repeats it in the scope notes it attaches to research results (System).

**BR-5.3 Case law is not evidence of currency.** *System + Instruction.*
A judgment that cites, applies or discusses an Act says nothing about which of its provisions are commenced or repealed today. The bot must never say a case "confirms" an Act's status.

**BR-5.4 What the bot may state about status.** *Instruction, backed by system notes.*
The bot may state only these four things, each citing its source:

| | Basis | What may be said |
|---|---|---|
| (a) | A *coming into force* relation in the change record | That the named provision was commenced by the named instrument. A date is given only where the system has attached one (BR-5.10), with its qualification, as the date that instrument brought the provision into force. It is never given as the provision's status today. |
| (b) | A repeal or revocation relation in the change record | That the named provision is no longer in force. **See BR-15.1:** the system classifies removals more finely than this instruction does. |
| (c) | A repeal or revocation marker in the index's own title, e.g. "(repealed)", "(revoked)", "(expired)", "(spent)" | That the instrument is repealed. An undated marker does not establish a date. A title without a marker is not evidence that the instrument is in force. At most 6 marked titles are listed to the research agent, plus a count of the rest. |
| (d) | The *valid date* on a full-text read | That the text held is stated to be up to date to that date. It is never given as a commencement date. At most 4 are reported to the answering agent. |

**BR-5.5 Commencement Orders of amendments are not commencement.** *System + Instruction.*
A relation of the type *Commencement Order* commences an amendment that some other Act made to the legislation. The provision recorded against it is a placeholder. The bot must never name such an order as having commenced the legislation asked about. The system sorts these relations last, counts them separately and marks them as not commencing this legislation.

**BR-5.6 Self-commencement is not commencement by another instrument.** *System + Instruction.*
Basis (a) is met only by a relation made by **another** instrument. An instrument's own commencement provision says how its provisions come into force, not whether they have. Asked what commenced an instrument, the bot answers from relations made by other instruments.

**BR-5.7 "Not recorded as commenced".** *System + Instruction.*
The bot may say a provision is "not recorded as commenced" only when the change record lists **in full** the commencements made by other instruments. A list cut short does not qualify (BR-5.12).

The bot must not say whether a provision has been commenced in any of these cases:
- the record holds only self-commencement;
- the record holds nothing;
- the list was cut short;
- no change record was consulted.

The system gives the answering agent one line per instrument, up to 12 lines, and names up to 8 more beyond those.

**BR-5.8 A record that was checked must be reported.** *Instruction.*
If the change record was consulted, the answer must first report what it holds: the repeals, the provisions recorded as commenced, and the commencement orders named. Only then may it say that current status is not established.

**BR-5.9 "Not verified".** *System + Instruction.*
Where none of (a) to (d) was retrieved, the research agent says:

> in-force status was not verified — the legislation index does not report it, and no commencement or repeal record was retrieved for this instrument

It then says what would establish the status. The scope footer states, in one of three forms, what was checked:
- the change records consulted, naming up to 3, with the source of any dates;
- that the records consulted list neither a commencement nor a repeal;
- that no change record was consulted.

**BR-5.10 Commencement dates.** *System.*
Commencement dates come from the dated *Changes to Legislation* record on legislation.gov.uk, read through the index's proxy. They are attached only to *coming into force* relations made by another instrument, for changes made **to** the instrument.

| Rule | Detail |
|---|---|
| Reading | One read per change record, memoised for the request. At most 2 pages of 500 changes. 8 seconds per read, no retry. A partial read is disclosed: "read for the first N of the M changes". |
| Qualification | Each date carries the record's own qualification. Provisions brought into force on different dates are dated separately. |
| Date check | A date is kept only if it falls on or after the commencing instrument's own made date. That is read from legislation.gov.uk: at most 8 reads per change-record call, 4 at once. |
| When a date is dropped | If the made date cannot be read, or the cap of 8 is reached, no date is given ("could not be checked"). A date earlier than the made date is refused. Refused instruments are named, up to 6, plus a count. |
| Failure | If the record cannot be read, the change record is returned undated and says so. |
| Prospective and undated changes | These add no date. |

**BR-5.11 Duplicate relations are collapsed.** *System.*
The change record repeats many relations, once under an `http` address and once under `https`. These are collapsed to one relation. Two rows are the same relation when they record the same changed instrument and provision, the same affecting instrument and provision, and the same effect. A relation whose effect is not stated is kept and labelled "not stated". It must not be described as a commencement, amendment or repeal.

**BR-5.12 Size of the change record.** *System.*
The index returns no count of relations and cuts a list off without warning, so:
- the system asks for 2,000 rows;
- if exactly 2,000 come back, it asks once more for 20,000;
- if that limit is also reached, the list is marked **truncated**, and the bot must not present it as complete;
- the read waits up to 120 seconds.

Within each group of relations the system lists:
- at most 60 distinct changed provisions;
- at most 120 relations;
- at most 40 related instruments.

The shortfall is counted.

**BR-5.13 Removals are classified by effect.** *System.*
Each repeal or revocation relation is classified. A removal is any effect that repeals, revokes, omits, removes, deletes or "ceases to have effect". Savings and consequential effects are not removals.

| Class | Test | What may be said |
|---|---|---|
| Provision | the whole provision removed | no longer in force |
| Provision in part | "in part" | the part removed is no longer in force |
| Words only | words or entries removed | the provision stands; its text was amended |
| Qualified | prospective, temporary, conditional, for specified purposes, or for part of the UK only | only with the qualification |

No removal carries a date. The answering agent is given up to 6 instruments for each class.

**BR-5.14 Legislation made before 1963.** *System.* **[not yet live]**
The index's change record holds nothing for an instrument made before 1963, on either side of a relation. This covers an identifier with a year before 1963 and any regnal-year identifier. EU legislation is excluded. For such an instrument an empty record means the position is **unknown**. The bot must not write "no change is recorded" or "not amended". Where the answer relies on such a provision, it says whether it has since been amended or repealed is not known from this research. The scope footer names each such instrument, up to 8, then gives a count, and advises checking the revised text on legislation.gov.uk.

**BR-5.15 The change record carries no enabling power and no dates.** *System + Instruction.*
The change record does not say what an instrument was made under. Its relations carry no date of their own, apart from the dates BR-5.10 adds.

**BR-5.16 Commencement, amendment and repeal questions go to the change record.** *System + Instruction.*
- **Where they come from:** only from the change record. A keyword search, the text of a section or the model's memory cannot establish them, and the research agent must consult the record first.
- **When the record is empty:** it may say "no such change is recorded", never "none was made". The system adds the index's coverage figure (BR-12.3).
- **Pre-1963 exception:** BR-5.14 overrides this for instruments made before 1963.

**BR-5.17 Deep Research reports.** *Instruction.*
The final report states a commencement, repeal or revocation only where a step's findings attribute it to a retrieved change record, and it names that record. It never says all cited legislation is in force. Otherwise it says in-force status was not verified.

---

## 6. Enabling powers and the made-under record

**BR-6.1 Only the preamble establishes what an instrument was made under.** *System + Instruction.*
The bot may say an instrument was made under, cites or relies on a provision only where a system block marked **ENABLING POWER** gives the instrument's own preamble words. Two other kinds of evidence are not enough:
- appearing next to the Act in search results;
- a matching description.

Otherwise it says "the enabling power could not be verified from the available material". It may still describe what a provision does.

The system looks for a preamble recital only in secondary legislation (identifier prefixes ssi, uksi, nisr, wsi, ssr, uksro, nisro, ukci, ukmo). It looks in the instrument's description and in the first 1,200 characters of its text. A recital is quoted up to 600 characters. A section search never returns the preamble, and the research agent is told not to state an enabling power from one.

**BR-6.2 Few instruments carry the recital in the index.** *Fact the rules depend on.*
In a sample of 103 instruments, 18 of 25 pre-1990 UK SIs carried a recital in the index, and none of 28 SSIs did. The made-under record (BR-6.3) fills most of that gap.

**BR-6.3 The made-under record.** *System.*
AILA holds its own record of the enabling powers recited in instrument preambles, harvested from legislation.gov.uk:

| Field | Value |
|---|---|
| Coverage | SSIs 1999 to 2026; UK SIs 1987 to 2026 |
| Size | 86,744 instruments, of which 68,780 recite a power |
| Snapshot | `2026-10-10.1`, harvested 9 October 2026 |
| New instruments | Added by a daily refresh from legislation.gov.uk's new SSI and UK SI lists: 5 pages, 120 reads at most, 20 seconds each, half a second apart |
| Revocation flags | From the snapshot only. An instrument added by the daily refresh reads as revocation *not checked*. |

The record does not cover:
- SIs made before 1987, which are image scans;
- Northern Ireland Statutory Rules;
- instruments published without text;
- instruments made under EU law or under another Order;
- anything published after the last refresh.

**BR-6.4 The forward question: "what was X made under?"** *System.*
A text read, section search or lookup of a secondary instrument may return no recital from the index. Where that happens, the system hands over the record's stored preamble and its reading of it, once per instrument per step, in a block that permits the claim. A recital in text read from legislation.gov.uk (BR-7.5) also permits it.

**BR-6.5 The reverse question: "what was made under section N of Act X?"** *System.*
The research agent consults the made-under record:
- **Listing:** at most **40** instruments are listed, with the total found. If more were found, the agent must say how many there are.
- **Never shortened:** the result is never summarised.
- **What it permits:** the bot may state that each instrument listed was made under that provision. It must not say that nothing else was made under it. It states the record's coverage instead of presenting the total as complete.
- **If none is found:** the record holds none, and search results must not be put in its place.

**BR-6.6 Revocation of instruments in the record.** *System.*
Each instrument in the record carries a revocation status, taken from legislation.gov.uk's *Changes to Legislation*:

| Status | Meaning |
|---|---|
| Revoked in whole | Revoked by a named instrument, with effect from a date on or before today |
| Revoked in whole, undated | No date recorded |
| To be revoked | Every whole revocation is dated in the future |
| Revoked in part | Part revoked |
| Qualified removal only | e.g. temporary or prospective. A temporary omission of words is treated as an amendment of the text, not a revocation. |
| None recorded | No revocation recorded |
| Not checked | Not checked |

A whole revocation requires the removed item to be the instrument itself (the regulations, order, rules, scheme, Act of Sederunt and so on), not a schedule or part of it. Up to 5 revocation relations are kept for each instrument.

What the bot must and must not do:
- It may state a recorded revocation as recorded: which instrument, and from which date, or that no date is recorded.
- It must not say that an instrument revoked from a future date has been revoked.
- It must not treat "none recorded" as in force. It may say only "legislation.gov.uk records no revocation of it as at <checked date>".
- It must give the status of each revoked or partly revoked instrument it lists.

If more than 40 instruments are found, those not revoked in whole are listed first, oldest first. Otherwise the list is oldest first. Counts cover every instrument found.

**BR-6.7 Made-under record after a section search.** *System.* **[not yet live]**
After each section search, the system gives the research agent the record's instruments for each section of an Act the search returned. It covers the section together with its lettered neighbours, so s.33 comes with s.33A.

| Rule | Detail |
|---|---|
| Listing a family | A family with at most 5 instruments not revoked in whole is listed. A larger family is counted, with its earliest and latest. |
| Revoked instruments | Instruments revoked in whole are counted, not listed. Instruments revoked in part, qualified or to be revoked are listed and marked. |
| Size of each block | At most 6 families per block. Each family appears once per step. |
| What it permits | That a listed instrument was made under the section given. Where only a count is shown, the research agent must consult the record before naming any. |
| Reaching the answer | These entries reach the answering agent and the footer only for instruments the report names. |

**BR-6.8 Disclosure.** *System.*
- **Instrument text read:** if the text of a statutory instrument was read, the scope footer names up to 4 instruments whose preamble stated the power. If no preamble was seen, it says that any such derivation given in the answer is unverified.
- **Made-under record consulted:** the footer states the record's coverage and the date its revocations were checked. Where no revocation is recorded, it says that is not confirmation the instrument is in force.

---

## 7. Retrieving text: lookups, schedules and legislation.gov.uk

**BR-7.1 Instrument lookups.** *System.*
A lookup of an instrument by type, year and number returns one of five outcomes:

| Outcome | Meaning |
|---|---|
| Held | The index holds the instrument and its text. |
| Held without text | The index has a record but no text. The bot must never report it as "not found". |
| Not held | The index does not hold it. |
| Lookup failed | Says nothing either way. |
| Invalid | Not a type the index recognises. |

**BR-7.2 When the system looks an instrument up.** *System.*
- **Before research starts:** on every instrument the brief names by number, up to 5. The research agent is then told the result.
  - *Not held:* report "not held in this index", not a citation error, and check the change record for what the instrument changes.
  - *Held:* check that the title is the instrument the question is about.
  - The same year and number under two types are two different instruments.
- **Conversational mode:** before the first section search of each SI, up to 5 per step.
- **After a section search that returns nothing**, up to 8 per step **[not yet live]**. Where the instrument is not held, or held without text, the research agent is told there was nothing to search. It must not report the instrument as lacking what it was searched for.

**BR-7.3 "Not held" is not a wrong citation.** *System + Instruction.*
If an instrument or case the user cited is not found, the bot says the index does not hold it. It must never:
- suggest a typing error;
- ask the user to check the citation;
- offer a different year or number instead.

See BR-15.4 for case law.

**BR-7.4 Search results.** *System.*

| Search | What the research agent sees |
|---|---|
| Legislation search | Each row gives the instrument's identifier, title, address, text version, year, extent and, where held, a description cut at a word to 600 characters. |
| Section search | Up to 10 sections. |
| Totals | A ranking depth, not a count. |

A ranked search cannot establish that something does not exist. After 2 or 3 failed wordings the research agent should stop. When reporting a miss it must:
- quote the 2 or 3 most specific search terms;
- name the filters;
- attribute the miss to the search or the index, never to the user's citation.

A description may be quoted, citing the instrument. It is not the change record, says nothing about status, and does not on its own establish an enabling power.

**BR-7.5 Text from legislation.gov.uk when the index lacks it.** *System.*
Where the index does not hold an instrument, holds it without text, returns an empty text, or reports "Legislation not found", the system reads the text from legislation.gov.uk.

| Rule | Detail |
|---|---|
| Version read | The *made* version (secondary legislation) or *enacted* version (Acts), then the current version |
| Limits | At most 2 reads per instrument and 8 instruments per request. 15 seconds per read, no retry. At most 8 MB. |
| Storage | Never cached or stored |
| What the research agent is told | That the index lacks the instrument; which version was read; to check its title; and to cite it at its legislation.gov.uk address, saying why it was read from there |
| Limit of the made version | It shows no later amendment or revocation, and says nothing about the instrument's status today |
| Disclosure | The scope footer says "The text of X (as made) was read from legislation.gov.uk". The answering agent is told of up to 8 instruments read this way. |

**BR-7.6 Schedules are included in full-text reads.** *System.*
Every full-text read includes the instrument's schedules and annexes. A line names up to 40 of their headings, or says none are held.

**BR-7.7 A schedule named but not returned.** *System.*
- **When it happens:** a section search names a schedule or annex that the results do not include. The system then fetches the instrument's full list of provisions and hands the unit over.
- **Limits on the fetch:** up to 2 units and 4 paragraphs per search, the list of up to 5,000 provisions, and 8 instruments per step.
- **How the unit is handed over:**
  - cut to the named paragraphs;
  - whole, if it fits;
  - for a large schedule with no paragraph named, its paragraph headings plus the paragraphs whose headings share a distinctive word with the question. This allows up to 150 headings of 120 characters each, within the larger of the summarisation threshold and 12,000 characters.
  - otherwise, summarised.
- **When the list is complete:** a unit missing from it is reported as absent from the index, and up to 8 units that are held are named.
- **When the list is incomplete or failed:** the question is left open.

**BR-7.8 Query wording.** *Instruction.*
- **Conversational mode:** the research agent writes legislation searches as plain sentences in the question's own words, not as lists of quoted terms. It also says which kind of power each cited provision is. **[not yet live]**
- **Research mode:** to find a named instrument, the research agent searches by its exact short title, limited to its year.

**BR-7.9 Further research instructions.** *Instruction.*
- Section retrieval is required: an instrument's title and metadata are never enough to answer.
- The full text is a fallback.
- A miss is "the material retrieved does not establish the answer", never "nothing exists".
- A source not searched is "not searched", not "not found".
- **Under *Legislation & case law* only:**
  - give penalty figures exactly as retrieved, never as a current money value or "unlimited";
  - retrieve the operative instruments (designation, exemption, compensation and commencement orders) that give an Act effect;
  - retrieve only the named jurisdiction's legislation;
  - cite an appeal alongside the first-instance decision.

  See BR-15.6.

---

## 8. Case law

**BR-8.1 Source.** *System.*
Case law comes from the National Archives' *Find Case Law*. It holds Scottish appeals to the UK Supreme Court. It does **not** hold decisions of the Court of Session, the Sheriff Appeal Court, the Sheriff Courts or the High Court of Justiciary. The scope footer says so whenever case law was searched. It adds that a search can miss a judgment and is not proof of absence. It also says that whether a common-law rule from a court outside Scotland forms part of Scots law has not been checked.

**BR-8.2 Ordering and counts.** *System.*
- **Ordering:** most relevant first, not by date. Up to 50 results per search.
- **Counts:** the feed's total is only approximate, so what was shown and the approximate total are reported separately, e.g. "the first N of about M". Other matches can lie outside the list.
- **What counts as a hit:** whether anything came back is judged on what was shown, never on the total.

**BR-8.3 Dates and courts.** *System.*
The user's date range and the research agent's own dates are intersected. A year alone covers that whole year, and a year and month cover that whole month. The research agent may choose a court. An invalid court code is refused, and the agent is asked to retry.

**BR-8.4 Reading judgments.** *System + Instruction.*

| | Rule |
|---|---|
| Reading | The research agent must read a judgment before relying on it, not answer from titles (Instruction). After a search with results, it is told to read 1 to 3 judgments, and the first 3 addresses are listed (System). |
| Size | A judgment is passed whole up to **60,000 characters**, or the summarisation threshold if that is higher (BR-11.1). The 250,000-character step allowance still applies. **[not yet live]** |
| Sources | Only Find Case Law addresses, and SCTS documents where enabled (BR-8.8), are fetched. Anything else is refused. 15 seconds per read. |

**BR-8.5 Searches and courts.** *Instruction.*
- **Number of searches:**

  | Research type | Searches |
  |---|---|
  | *Case law only* | at most 3, then stop |
  | *Legislation & case law* | at most 1 retry per track |
  | After a search with no results | the system's note says to stop after 2 or 3 different queries |

- **Courts:** the court that decided each case cited must be named.
- **Deep Research reports:** they must not call a decision binding or persuasive in another jurisdiction unless a finding cites a source that says so.

**BR-8.6 Appeals are flagged.** *System + Instruction.*
Where the results contain a case and a higher court's decision in what appears to be the same case, the research agent is told it must retrieve and cite the higher decision. Up to 3 are listed. Cases are matched on a distinctive party word: at least 4 letters, not boilerplate, and appearing in no more than 3 results.

| Court rank | Courts |
|---|---|
| 4 | UKSC, UKPC |
| 3 | EWCA, CSIH, NICA |
| 2 | EWHC, CSOH, UKUT |

Only a decision of rank 3 or above is flagged as an appeal.

**BR-8.7 A case the question names but the search did not return.** *System.*
If the question names a case (a "X v Y" name or a neutral citation) and the results do not include it, the research agent is told three things:
- this search did not return the case;
- the case may well exist, and its absence is no sign the name or citation is wrong;
- it must not state what the case decided as though it had read it.

The test leans towards treating the case as returned. A law-report citation on its own cannot be matched. See BR-15.4.

**BR-8.8 Scottish judgments (SCTS). Switched off.** *System.*
An administrator can switch on searches of the Scottish Courts and Tribunals Service's published judgments. The *Scottish judgments (SCTS)* feature flag is off by default and stays off until the target network can reach SCTS. With it off, nothing changes. With it on, under a research type that includes case law:

| Rule | Value |
|---|---|
| Searches per request | 60 |
| Judgment texts per request | 20 |
| Requests to SCTS in flight | 2, across the whole server |
| Results per search | 10 |
| Timeouts | 15 seconds (search), 30 seconds (PDF) |
| PDF limits | 15 MB, 300 pages |
| Search terms | Every term is required. A search with more than one term that returns nothing is re-run once with any term matching. Excluded terms are dropped, because a "-" broadens an SCTS search. |
| Dates | The date window filters on the date of decision. A date is never inferred from a citation's year. |
| Citation | The neutral citation comes from the file name, else from the first 4,000 characters of the text. A judgment without one is cited by title, court and date of decision. |

---

## 9. Citations

**BR-9.1 Cite only addresses the tools returned.** *System + Instruction.*
- **Provision citations:** each provision is cited with the address the section search returned, copied exactly. The research agent must not build a provision address itself.
- **No address:** if it has none, it cites the provision in bold with no link.
- **Other sites:** it must not invent addresses on any site other than legislation.gov.uk.

The system then checks this (BR-9.7).

**BR-9.2 Pinpoint citations.** *Instruction.*
The link text names the exact subdivision, e.g. s.110(2), Sch 2 para 3(1) or reg. 4(3). The link itself goes to the section's address. An Act's own address is used only when the Act as a whole is meant.

**BR-9.3 Neighbouring subsections.** *Instruction.*
When it cites one subsection, the research agent says what the section's other subsections provide.

**BR-9.4 Case citations.** *Instruction.*
Cases are cited as *Case Name* plus neutral citation, linked to the address returned. Citations and addresses must never be guessed.

**BR-9.5 References.** *System + Instruction.*
- **Research mode:** reports end with a References section (BR-9.9).
- **Conversational mode:** citations go inline, with no References list unless the user asks.

**BR-9.6 Deep Research.** *System + Instruction.*
The final report passes citations through exactly. It keeps pinpoints, never shortening s.12(3) to s.12, and keeps every link. The system hands the writer the pinpoints the steps attached to each section address, up to 12 addresses with 6 pinpoints each.

**BR-9.7 Provision links no tool returned are cut back.** *System.*
This applies in every mode, to each research report, each answer and each Deep Research report. A legislation.gov.uk provision link whose address no tool returned in this request is changed, and its label marked **†**:
- if the instrument itself was retrieved, the link is cut back to the instrument's address;
- otherwise the link is removed and the label put in bold.

The answer then carries this note, once:

> † No provision-level URL was returned by any search for this citation; where a link is shown it points at the instrument as a whole.

Links to other sites are not changed.

**BR-9.8 Repairs to a Conversational answer.** *System.*
In Conversational mode the answering agent shortens the report, and can drop citations. The system makes four repairs. Each copies the research agent's own words or addresses verbatim. None generates new text.

| Repair | Rule | Limits |
|---|---|---|
| Neighbouring subsections linked | Before the answering agent reads the report, a subsection the research agent mentioned in plain words, e.g. "s.36(2) exempts…", is linked to the section address the same paragraph already cites. | Skipped where the paragraph cites more than one address for the section, the subsection belongs to another instrument, or it is a schedule reference. |
| Dropped subsection restored | If the answer cites one subsection of a section, the report linked another, and the answer mentions the second nowhere, the research agent's own sentence about it is added after the paragraph as "Also in s.N: …". | At most 3 per answer. Each at most 450 characters and at least 4 words. Skipped if 60% of its words already appear in one sentence of the answer. |
| Schedule paragraph restored | For a schedule paragraph the system handed over exactly, a line "Also in Schedule N, paragraph N (heading): "…"" is added, quoting its operative words. This happens where the answer cites a neighbouring paragraph but not this one, or cites only some of its sub-paragraphs, or **[not yet live]** cites it by number only, without its words. | At most 3 per answer, each paragraph once. Each quotation at most 450 characters of whole sub-paragraphs: the rule first, then its conditions of application. A sentence that seems to cite the wrong paragraph is logged, never changed. |
| Instrument linked | An instrument the report linked, which the answer names in words but links nowhere, gets the report's address at its first mention. A provision address is used only where the answer names that provision within 100 characters. | Never inside a quotation, a code span or a bracketed block, or where two instruments claim the same words. |

The Research and Deep Research answers do not get these four repairs. They get only BR-9.7, and Deep Research also gets BR-9.6.

**BR-9.9 Report structure is checked.** *System.*
A research report that has fewer than 2 headed sections, no References section, or no link although sources were retrieved, gets **one** rewrite with no further research. The rewrite is told to add no legal content, and to write "None found" under References if there were no sources. This check is skipped in Conversational mode and for a step that stopped (BR-4.4) or lost its report (BR-12.5).

---

## 10. The sources rail

**BR-10.1 A source that was read is always shown.** *System.*
A source whose text was actually read always appears: a section returned by search, a full text read, or a judgment read.

**BR-10.2 Any other source must be named in the report.** *System.*
A source that was retrieved but not read appears only if the report names it. That includes an instrument met only in a change record. It counts as named if the report gives:
- its identifier or address;
- for a case, its neutral citation;
- its title, at least 8 characters and not just the start of a longer title;
- for an SI, its year and number.

A section heading does not count. Neither does a short form such as "the 1901 Act". A case title closely followed by a different citation does not count, so that an appeal is not credited to the first-instance decision.

**BR-10.3 No fallback.** *System.*
A report that names none of its sources adds none to the rail.

**BR-10.4 Sources named in the answer are restored.** *System.*
A source retrieved during the turn that the answer itself names, by the test in BR-10.2, is added to the rail.

**BR-10.5 Titles.** *System.*
A rail entry shown only by its identifier gets its exact title, if one is known:
- from the turn's own retrievals;
- from a lookup;
- from the made-under record.

The title must name a year, otherwise nothing is substituted. An entry with no address gets its legislation.gov.uk identifier address. Entries are never added, removed or reordered by this step.

---

## 11. Summaries

**BR-11.1 When a result is summarised.** *System.*
A tool result over the **summarisation threshold** is summarised against the question before the research agent reads it.
- **The threshold:** 10% of the model's context window, at 4 characters a token, kept between **10,000** and **200,000** characters.
- **If the model's context window is unknown:** it is **8,000** characters.

Also summarised:
- every result once a step has taken in 250,000 characters (BR-4.5);
- a judgment, over 60,000 characters (BR-8.4).

Results from the made-under record are never summarised.

**BR-11.2 How summaries are made.** *System.*
- **Splitting:** long text is summarised in parts of 150,000 characters, and the parts are combined.
- **Failure:** if a part fails, its first 5,000 characters are used instead. If a single summary fails, the raw text is used, marked as degraded.
- **Size:** a summary still over the threshold is cut and marked "[Content truncated — summary exceeded context limit]".
- **Temperature:** summaries are made at temperature 0.

**BR-11.3 The summariser adds nothing.** *Instruction.*
The summariser is told to summarise only what the text contains. It must add no legislation or rule of its own and draw no conclusions of its own.

**BR-11.4 Invented case citations are removed.** *System.*
- **Citations:** a case citation in a summary that is not in the source text or the question is removed. If the source names the case, only the citation goes. Otherwise the list item, short heading block or sentence goes. Neutral citations, English and Scottish law reports and Find Case Law addresses are all recognised.
- **Bare names [not yet live]:** a bare "X v Y" name with no citation within 40 characters, which neither the source nor the question names, is removed in the same way.
- **What is kept:** a name with no distinctive word, a placeholder, and any passage that also carries a citation the source holds.
- **Nothing is added.**
- **Cached summaries:** this check also runs on summaries taken from the shared cache (BR-14.2).

**BR-11.5 Last-resort size cap.** *System.*
Any tool result, including the research report the answering agent receives, is cut if it exceeds the threshold plus **4,000** characters. It is marked "[Content truncated — result exceeded context limit]". See BR-15.9.

**BR-11.6 Citation addresses survive summarising.** *System.*
When a result is summarised, the system attaches the provision addresses the search returned, up to 12, so that a summary never loses them.

---

## 12. What the user is told

**BR-12.1 The system attaches scope notes to research results.** *System.*
These notes go to the research and answering agents. Each research report ends with a scope note recording the following:
- the searches made, with up to 12 terms;
- the filters in force;
- any limits reached;
- what the change record, the made-under record and lookups held;
- any text read from legislation.gov.uk.

It closes with the rule that none of this can establish that something does not exist. The note is always removed before the user sees the answer.

**BR-12.2 The scope footer.** *System.*
Every answer whose turn searched legislation ends with one italic *Search scope:* line, written by the system, not the model. Its parts, in order and where they apply:

1. The first 2 search terms, and how many further queries are not listed.
2. The filters that narrowed the search (BR-2.9).
3. The index's coverage (BR-12.3).
4. The search limit, if reached (BR-4.7).
5. The within-instrument limit, if reached (BR-4.7).
6. Enabling powers, if an SI's text was read (BR-6.8).
7. The made-under record, if consulted (BR-6.8).
8. The change record, if consulted. It names up to 3 records and says:
   - where any dates come from;
   - that an empty record means no change is recorded;
   - that a cut-short list gives examples, not a complete set;
   - for pre-1963 instruments, BR-5.14.
9. In-force status (BR-5.9).
10. Instruments not held, or held without text, which "does not show whether the number is accurate". Also any text read from legislation.gov.uk.
11. Case law, if searched (BR-8.1).

Other turns get other forms of the footer:

| Turn | Footer |
|---|---|
| Only section searches | A section-search form naming up to 3 instruments |
| Only lookups | Says no ranked search was run |
| Case law only | A case-law form |
| A follow-up that searched nothing | Restates the earlier footer, marked as earlier. Not in Deep Research. |

**BR-12.3 Index coverage.** *System.*
Whenever an empty result is reported, the footer and the system notes state the index's sampled coverage (September 2026):
- Acts of the Scottish Parliament: complete;
- 2025 SSIs: roughly 85% held;
- instruments made in 2026: under 10% held.

They add that not being found in the index is not the same as being absent from the law.

**BR-12.4 A step that stopped.** *System.*
If any research step in the turn reached the step limit, the answer opens with this warning:

> **⚠ This answer is incomplete.** …reached a fixed internal limit of 20 tool-call rounds… **not** a timeout… **not** a finding that the material does not exist. Treat the coverage below as partial…

The warning is added whatever the model wrote. In Deep Research the final report's writer is also told which steps are partial.

**BR-12.5 A step whose report was lost.** *System.*
If the model returned an empty reply on every attempt, the answering agent is told the report was lost. It is told this is not a fault in the index, not the step limit, and not evidence that the material does not exist. It may brief the research agent once more. If no later step that turn succeeded, the answer opens with **"⚠ This answer is incomplete."**. The warning then says either that the coverage is partial or, if nothing completed, that no completed research stands behind the answer.

**BR-12.6 No composed answer.** *System.*
If the answering agent returns nothing after its retries, the user is shown one of these:
- **Research reports exist:** the reports, unedited, under a statement that this is not a composed answer.
- **There are none:** "No answer was returned for this turn … Nothing has been answered from memory. Please send the question again."
- **The Deep Research final report is empty:** the step findings under a statement that they have not been synthesised, reconciled or checked for gaps.

**BR-12.7 A failed research step.** *System.*
If a research step fails, the answering agent is told:
- not to brief again;
- to tell the user plainly that the research could not be completed;
- to suggest narrowing the question;
- not to invent findings or answer from memory.

**BR-12.8 Error messages.** *System.*
A failed request tells the user: "This request could not be completed: <reason>. Please try again, or narrow the question if it was a broad one." The reason is given in plain words, for example "the AI provider did not respond in time". A Deep Research plan the provider refuses produces one of these **[not yet live]**:
- a refusal on account grounds: "trying again will not help. Please tell your administrator";
- a rate limit: "try again in a few minutes";
- other failures: "try again later".

**BR-12.9 Retries.** *System.*
- **Legislation index and case-law calls:** retried up to 3 times when the service is busy or unavailable, after 0.5, 1 and 2 seconds plus a random delay of up to 25%. A service's own requested wait is honoured up to 30 seconds. Once the retries are used up, the research agent is told the call failed.
- **Model calls:** up to 3 attempts, 2 seconds then 4 seconds apart, but only while nothing has yet been shown to the user. A provider that does not start replying within 180 seconds counts as a failure.
- **Research agent:** a model reply that ran away and produced nothing, or stalled at the provider, is not retried. The answering agent is told the report was lost and may brief again (BR-12.5).
- **Answering agent:** where a research report is already in hand, the answering agent gets fewer retries, so that the fallback in BR-12.6 comes sooner.
- **Output cap:** on OpenRouter, each research and answering call may write at most 32,000 tokens.

**BR-12.10 Timeouts on outside services.** *System.*

| Call | Timeout |
|---|---|
| Legislation index, general | 30 seconds |
| Change record | 120 seconds |
| Full list of provisions; full text with schedules | 60 seconds |
| Case law | 15 seconds |
| legislation.gov.uk text | 15 seconds |
| Commencement-date reads | 8 seconds |
| Summarisation | 600 seconds |
| Consulting another bot | 300 seconds |

---

## 13. Deep Research

**BR-13.1 Plan, approve, run.** *System.*
Deep Research works in three stages:
1. A planner drafts a research plan. It has no research tools.
2. The user edits the plan: adds, removes, reorders and rewrites steps, and edits the scope note.
3. On approval, the system runs each step in order as a separate research step. A single final call, with no tools, writes the integrated report.

There is no pausing between steps.

**BR-13.2 Plan limits.** *System + Instruction.*

| Rule | Limit | Enforcement |
|---|---|---|
| Steps the planner is asked for | 2 to 6, framework first and case law last | Instruction |
| Steps accepted | 1 to 8 | System |
| Step title | 1 to 500 characters | System |
| Step detail | up to 4,000 characters | System |
| Scope note | up to 2,000 characters | System |

Steps without a title are dropped. If the planner neither submits a plan nor asks a question, it is asked once more, and then an error is returned.

**BR-13.3 The planner respects the research type.** *Instruction.*
- **Under *Legislation only*:** the plan has no case-law steps. A case-law question goes back to the user as a clarifying question that explains the *Research type* control.
- **Under *Case law only*:** the plan has no legislation steps.

**BR-13.4 The planner's clarifying options.** *System.*
At most 4 options, shown as buttons (BR-14.6). They are omitted when the buttons are switched off.

**BR-13.5 Steps share what they found.** *System.*
- **Instruments:** each step after the first is told which instruments the earlier steps' reports cited, up to 40, with a count of the rest. This is framed as information, not as an instruction to research them.
- **Repeat calls:** an identical call repeated in a later step is answered from memory (BR-14.1).

**BR-13.6 The integrated report.** *Instruction.*
- **What it draws on:** the report is written only from the step findings.
- **Gaps:** described by what happened: not searched, did not complete, or searched and not established.
- **Conflicts:** shown, not silently resolved.
- **Summary Answer:** includes a Key findings list.
- **Status and citations:** BR-5.17 and BR-9.6 apply.

**BR-13.7 Deep Research is not automatic.** *System.*
A Deep Research request without an approved plan is refused. A Deep Research run never consults another bot.

---

## 14. Clarification, suggested questions, other bots, data and privacy

**BR-14.1 Repeat calls within one request.** *System.*
Within one request, an exact repeat of a tool call is answered from memory. Exact means the same tool and the same arguments. A repeat does not call the outside service again and does not count against the search allowance. The memory is discarded when the request ends. Switched on by default.

**BR-14.2 The shared summary cache.** *System.*
A summary of a public document is stored and reused for **any user** who retrieves exactly the same text with a question that has the same significant words, ignoring case, word order, short words and common words. There is no approximate matching. Changed text produces a different key, so a cached summary cannot be stale.

| Rule | Detail |
|---|---|
| Key question | The user's own latest message. In Deep Research, the step's approved text. |
| Tools that may be cached | The legislation searches, full-text reads and change record, and the case-law search and judgment reads. Not lookups, and not the made-under record. |
| Degraded summaries | A summary that fell back to raw text, or was cut short, is never stored. |
| Clean-up | Runs on about 2% of stores, and only once the cache holds more than 20,000 entries. It removes entries never reused after 90 days, and any entry unused for 365 days. |
| Admin controls | Can be switched off. An administrator can clear it. Never backed up. |

**This is the one deliberate way one user's request can shape another user's answer.** Two users who ask the same question of the same text get the same summary. The stored entry includes the first user's question in plain text, and an administrator can see the most reused questions.

**BR-14.3 Rated answers from other users go into the prompt.** *System.*
On every Conversational and Research request, the user's latest question is matched by word overlap against **all users'** past questions. Two kinds of material can go into the answering agent's instructions:
- up to 3 earlier answers rated 4 or 5, with their feedback comments, as examples to emulate. Each answer is cut to 2,000 characters and its question to 300.
- up to 3 comments on answers rated 3 or below, as feedback. Each comment is cut to 500 characters and its question to 50.

There is no switch for this. It does not apply to Deep Research steps. See BR-15.11.

**BR-14.4 What is stored and who sees it.** *System.*

| Who / what | Rule |
|---|---|
| Users | See only their own chats and matters. |
| Saved messages | Each message is saved with the model and provider that produced it, its sources, the chat mode and research type, and any approved Deep Research plan. |
| Retention | None. Deleting a chat deletes its messages. A question may still survive in the shared cache (BR-14.2) and in backups. |
| Ratings | 1 to 5, with an optional comment, changeable by the owner. |
| Administrators | Can see the activity log (each user's messages, cut to 2,000 characters), session transcripts, ratings and feedback. |
| Uploaded documents and matter notes | Sent to the model provider as part of the prompt. Uploads are limited to 50,000 characters a file, 80,000 in total, and 20 MB a file. |
| Logs | Kept for 14 days. At the normal log level, free-text tool arguments are replaced by a length, a fingerprint and the first 24 characters. Some user text is still logged in full (BR-15.12). |
| Backups | Nightly: the last 14 daily runs, 8 weekly and 12 monthly copies kept. |

**BR-14.5 Clarifying questions.** *Instruction.*
The answering agent asks before researching when a question is ambiguous. A clarifying question must never draw on training data to suggest, list or describe particular cases or legislation. The answering agent must ask neutrally and offer only scope choices grounded in the conversation or in tool results, such as the jurisdiction, as enacted versus current, or a section the user named.

**BR-14.6 Suggested-question buttons.** *System + Instruction.*

| | Rule |
|---|---|
| End of an answer | 2 or 3 follow-up questions as buttons (Instruction) |
| A clarifying question | Up to 4 options, which must not also be written out in the answer (Instruction) |
| Grounding | Options follow BR-14.5. A button that offers to change a mode or filter is removed, because a button can only send text (System). |
| Cap | At most 4 buttons, each at most 160 characters. Longer ones are dropped, not cut (System). |
| Display | Shown only under the latest answer. Not saved. |
| Switching off | When the flag is off, the instruction is removed and follow-ups are written as prose. On by default. |

**BR-14.7 Consulting another bot.** *System + Instruction.*
- **The tool:** the answering agent can consult a registered peer bot, such as the Scottish Parliament bot, only if one is enabled.
- **Depth:** a consultation may not itself consult a further bot. A request two levels deep is refused.
- **The consulted bot:** answers the most reasonable reading of the question and states its assumption. It never asks a clarifying question and never offers buttons. It runs in Research mode with no filters.
- **When the peer finds nothing:** the answer says "the Parliament Bot found no records of debate on this topic", not that parliamentary research is unavailable.

**BR-14.8 Feature flags.** *System.*
These flags affect the legislation bot's behaviour:

| Flag | Default | Effect |
|---|---|---|
| Research mode | On | BR-1.10 |
| Deep Research mode | On | BR-1.10 |
| Suggested questions | On | BR-14.6 |
| Tool memo | On | BR-14.1 |
| Local prompt cache | On | BR-14.2 |
| Provider prompt caching | On | Cost only. No effect on content. |
| Scottish judgments (SCTS) | Off | BR-8.8 |
| Matters | On | Named groups of chats, with notes |

---

## 15. Known inconsistencies

These are places where an instruction and the system disagree, or where a rule does less than it appears to. They are listed for review, not resolved here.

**BR-15.1 Repeal versus removal class.** Basis (b) in BR-5.4 tells the research agent that any repeal or revocation relation means the provision is no longer in force. The system's classification (BR-5.13) says otherwise:
- a removal of words leaves the provision standing;
- a prospective, temporary, conditional or territorially limited removal must be stated only with its qualification.

The instruction can therefore license an over-statement. Examples are "repealed" for "words repealed", or for "repealed (prosp.)". The Deep Research rules also treat repeal as a single class. A change to the instruction is pending a test.

**BR-15.2 Pre-1963 legislation is not in the instructions.** The research agent's general instruction says an empty change record means "no such change is recorded". For an instrument made before 1963, the system's note says the opposite: the position is unknown (BR-5.14). Only the system note carries the exception. **[not yet live]**

**BR-15.3 Enabling power: a permission can be followed by a refusal.** This finding comes from reading the code and has not been tested. Suppose an SI's enabling power has already been permitted earlier in a step, from the made-under record or from text read from legislation.gov.uk. A later full-text read of the same SI with no recital in the index can then carry a note forbidding the claim. That note says the record holds no preamble either. The same note appears whenever the made-under record is not loaded, or the SI is outside its coverage.

**BR-15.4 Case law "not held".** The general instruction (BR-7.3) tells the bot to say "this index does not hold it" when a search does not return a case. The system's note (BR-8.7) says only that *this search* did not return it and that it may well exist. The two differ. The note is the more accurate.

**BR-15.5 The dated commencement footer understates the change record.** Where dates are given, the footer says they are "not a check of whether a provision has since been amended or repealed". Yet the change record it names is that check, for repeals.

**BR-15.6 Penalty and operative-instrument rules apply under one research type only.** BR-7.9's rules on penalties verbatim, operative instruments, jurisdiction scope and appeals appear only under *Legislation & case law*. The *Legislation only* and Conversational research agents do not carry them.

**BR-15.7 Conversational instructions versus system limits.** The Conversational research agent is told to search once and retrieve each instrument once. The system allows 8 search rounds and 3 within each instrument. It is also told to use case-law tools that, under *Legislation only*, it does not have, and to use legislation tools that, under *Case law only*, it does not have.

**BR-15.8 Research-mode pass-through names the wrong headings.** BR-3.5's instruction lists the *Legislation & case law* headings: Statutory Framework and Key Cases. A *Legislation only* report uses Detailed Analysis instead.

**BR-15.9 The research report can be cut before the answering agent reads it.** BR-11.5's last-resort cap applies to the research report itself. Where the model's context window is unknown, that is 12,000 characters. A long report can lose its end, including its scope note, before the answering agent reads it.

**BR-15.10 Hidden modes are not refused.** Hiding Research or Deep Research mode (BR-1.10) only removes it from the sidebar. The server still runs it if asked.

**BR-15.11 Cross-user material in the prompt.** BR-14.3 places other users' questions, answers and feedback comments into the instructions. It has no switch. It is not limited to public-source material, unlike the shared cache (BR-14.2).

**BR-15.12 User text in logs.** The redaction in BR-14.4 does not cover these:
- the answering agent's brief to the research agent, which restates the question;
- the keywords taken from each question for BR-14.3;
- Deep Research step titles;
- a new user's email address.

All four are logged in full at the normal log level.

**BR-15.13 Planner wording.** The *Case law only* planner instruction calls the research type a "mode", against BR-1.7. The planner's list of filters to respect still names the court, a filter that no longer exists. The planner's options are not checked for mode-switch offers or length, unlike the answering agent's buttons (BR-14.6).

**BR-15.14 Legislation type names.** The instruction describing the type filter lists fewer prefixes than the filter applies (BR-2.6). For example, it gives "draft" as ukdsi only, but the filter also includes sdsi.

---

## Appendix A. Every numeric limit

| Limit | Value | Rule |
|---|---|---|
| Index search rounds per research step | 8 | BR-4.1 |
| Section-search rounds per instrument per step | 3 | BR-4.2 |
| Rounds per research step (and for the answering agent) | 20 | BR-4.3 |
| Write-up rounds after the step limit | 1 | BR-4.4 |
| Characters of tool output per step | 250,000 | BR-4.5 |
| Summarisation threshold | 10% of context, 10,000 to 200,000 characters; 8,000 if context unknown | BR-11.1 |
| Judgment passed whole up to | 60,000 characters | BR-8.4 |
| Last-resort cap on a result | threshold + 4,000 characters | BR-11.5 |
| Summary part size / failed-part fallback | 150,000 / 5,000 characters | BR-11.2 |
| Legislation search: asked for / passed on | 5 (20 when filtered) / 5 | BR-2.7 |
| Sections per section search | 10 | BR-7.4 |
| Search description | 600 characters | BR-7.4 |
| Preamble recital searched / quoted | first 1,200 / 600 characters | BR-6.1 |
| Automatic lookups from a brief | 5 | BR-7.2 |
| Lookups before section searches (Conversational) | 5 per step | BR-7.2 |
| Lookups after an empty section search | 8 per step | BR-7.2 |
| Full lists of provisions fetched | 8 instruments per step, 5,000 provisions each | BR-7.7 |
| Schedule units / paragraphs read per search | 2 / 4 | BR-7.7 |
| Schedule headings listed | 40 (text read); 150 of 120 characters (large schedule) | BR-7.6, BR-7.7 |
| Large-schedule allowance | larger of threshold and 12,000 characters | BR-7.7 |
| Held units named when one is absent | 8 | BR-7.7 |
| legislation.gov.uk text reads | 2 per instrument, 8 instruments per request, 15 s, 8 MB | BR-7.5 |
| Change record rows | 2,000, then 20,000 | BR-5.12 |
| Change record listing per group | 60 provisions, 120 relations, 40 related instruments | BR-5.12 |
| Commencement lines to the answering agent | 12, plus 8 named | BR-5.7 |
| Removal-class instruments to the answering agent | 6 per class | BR-5.13 |
| Title markers listed | 6 | BR-5.4 |
| Valid dates reported | 4 | BR-5.4 |
| Commencement feed | 2 pages of 500, 8 s, no retry | BR-5.10 |
| Made-date reads | 8 per change-record call, 4 at once | BR-5.10 |
| Refused dates named | 6 | BR-5.10 |
| Pre-1963 instruments named in the footer | 8 | BR-5.14 |
| Made-under record listing | 40 | BR-6.5 |
| Revocation relations kept per instrument | 5 | BR-6.6 |
| Section families: instruments listed / families per block | 5 / 6 | BR-6.7 |
| Made-under daily refresh | 5 pages, 120 reads, 20 s each, 0.5 s apart, once a day | BR-6.3 |
| Enabling-power instruments named in the footer | 4 | BR-6.8 |
| Case-law results per search | 50 | BR-8.2 |
| Judgments the research agent is told to read | 1 to 3 (first 3 listed) | BR-8.4 |
| Case-law searches | 3 (*Case law only*); 1 retry per track (both); stop after 2 to 3 with no results | BR-8.5 |
| Appeals flagged | 3 | BR-8.6 |
| SCTS | 60 searches, 20 texts, 2 in flight, 10 results, 15 s / 30 s, 15 MB / 300 pages, citation from first 4,000 characters | BR-8.8 |
| Pinpoints handed to Deep Research report | 12 addresses, 6 each | BR-9.6 |
| Restored subsection notes | 3, each 450 characters, 4 words minimum, 60% overlap test | BR-9.8 |
| Restored schedule paragraphs | 3, each 450 characters | BR-9.8 |
| Instrument link window | 100 characters | BR-9.8 |
| Citation addresses kept with a summary | 12 | BR-11.6 |
| Bare case name test | 40 characters | BR-11.4 |
| Search terms in the scope note / footer | 12 / 2 | BR-12.1, BR-12.2 |
| Records / instruments named in footer clauses | 3 | BR-12.2 |
| Instruments read from legislation.gov.uk named to the answering agent | 8 | BR-7.5 |
| Index and case-law retries | 3, after 0.5, 1, 2 s (+ up to 25%), max 8 s; requested wait up to 30 s | BR-12.9 |
| Model call attempts | 3, 2 s then 4 s apart; 180 s to first reply | BR-12.9 |
| Output cap per call (OpenRouter) | 32,000 tokens | BR-12.9 |
| Deep Research plan | 2 to 6 asked; 1 to 8 accepted; title 500, detail 4,000, scope note 2,000 characters | BR-13.2 |
| Instruments handed between steps | 40 | BR-13.5 |
| User's own message passed to research | 4,000 characters | BR-3.4 |
| Agreement-opener removal | 2 passes | BR-3.8 |
| Suggested-question buttons | 2 to 3 asked (4 for a clarification); max 4, 160 characters | BR-14.6 |
| Consultation depth | one level | BR-14.7 |
| Shared cache clean-up | above 20,000 entries, 2% of stores, 90 days unused, 365 days idle | BR-14.2 |
| Examples from other users | 3 rated 4+ (answer 2,000, question 300 characters); 3 critiques (500, question 50) | BR-14.3 |
| Uploads | 50,000 characters a file, 80,000 total, 20 MB a file | BR-14.4 |
| Log retention / log preview | 14 days / 24 characters | BR-14.4 |
| Activity log message length | 2,000 characters | BR-14.4 |
| Backups | 14 daily, 8 weekly, 12 monthly | BR-14.4 |
| Timeouts | see BR-12.10 | BR-12.10 |

## Appendix B. Where the rules are implemented

For maintainers. Paths are under `server_py/src/`.

| Section | Main files |
|---|---|
| 1 Modes | `routers/agent_request.py`, `utils/mode_change.py`, `prompts.py`, `agent/tools/schemas.py` |
| 2 Filters | `agent/tools/lex.py` (`_matches_jurisdiction`), `agent/tools/executor.py`, `agent/tools/caselaw.py` |
| 3 Answering agent | `prompts.py`, `agent/agent_core.py`, `utils/openers.py`, `utils/lawyer_words.py` |
| 4 Limits | `utils/discovery_budget.py`, `utils/research_halt.py`, `agent/summarisation.py`, `agent/openrouter_client.py` |
| 5 Status | `prompts.py` (`_IN_FORCE_RULE`, `_COMMENCEMENT_RECORD_RULE`), `utils/search_scope.py`, `utils/removal_effects.py`, `agent/tools/commencement_dates.py` |
| 6 Enabling powers | `utils/made_under.py`, `services/made_under_store.py`, `utils/revocation_record.py`, `agent/agent_shared.py` |
| 7 Retrieval | `utils/instrument_lookup.py`, `utils/schedule_units.py`, `utils/published_text.py`, `agent/tools/published_text.py` |
| 8 Case law | `agent/tools/caselaw.py`, `agent/tools/scts.py` |
| 9 Citations | `utils/citation_links.py`, `utils/paragraph_restore.py` |
| 10 Sources rail | `agent/agent_core.py` (`filter_worker_sources`), `utils/source_naming.py`, `utils/rail_titles.py` |
| 11 Summaries | `agent/summarisation.py`, `utils/summary_citations.py`, `agent/provider_factory.py` |
| 12 Disclosure | `utils/search_scope.py`, `utils/research_halt.py`, `utils/empty_completion.py`, `routers/ai.py`, `routers/research.py` |
| 13 Deep Research | `agent/agent_core.py`, `utils/step_handover.py`, `routers/research.py` |
| 14 Other | `services/local_prompt_cache.py`, `agent/learning.py`, `utils/redact.py`, `utils/suggestions.py`, `routers/federation.py`, `routers/developer.py` |
