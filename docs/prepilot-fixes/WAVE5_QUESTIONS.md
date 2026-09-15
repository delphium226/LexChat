# Wave 5 — the external questions, drafted and ready to send

**Status: drafted 2026-09-15 (Session 5), NOT YET SENT.** These need a human to send them;
nothing in the codebase can. They have been idle across five sessions, and the plan says to
open them early precisely because they block nothing and have unknown lead time.

Ledger rows: **P5.1** (LEX relationships), **P5.2** (Scottish case-law corpus), **P5.3**
(corpus currency). Each row's acceptance is *a recorded answer in `SESSION_LOG.md`* — so when
a reply arrives, paste it into the log and tick the row.

Why it matters that these go out now, rather than when the code work reaches them:

- **P5.1 determines whether the largest bucket is buildable at all.** B3 is "AILA asserts a
  relationship between instruments it never retrieved" — what commences what, what amends
  what, what was made under which enabling power. If LEX exposes those relations, B3 gets a
  retrieval fix. If it does not, B3 is **permanently a disclosure**, and P2.3 stops being a
  holding fix and becomes the answer. That is a different piece of work, and the answer
  changes which one gets built.
- **P5.2 is procurement, not engineering.** No amount of code puts the Court of Session in a
  corpus that does not contain it.
- **P5.3 changes what B5's negative is allowed to *say*.** "Not found in the index" is only
  honest if we know what the index covers and how often it refreshes. Invariant 1 requires the
  negative to be true, not merely cautious.

---

## P5.1 — to the LEX team: are instrument relationships retrievable?

> We are building a legal research assistant over the LEX API for Scottish Government lawyers,
> and the single largest class of error we found in our pre-pilot is the model asserting a
> relationship between two instruments that it never actually retrieved — for example that
> an SSI was made under a particular enabling power, or that a commencement order brought a
> section into force.
>
> We currently call three endpoints: `/legislation/search`, `/legislation/section/search` and
> `/legislation/text`. None of them appears to return relationships.
>
> 1. Does the API expose **enabling-power** relations (this instrument was made under
>    s.X of that Act), in any endpoint or any field we may have missed?
> 2. Does it expose **amendment** relations (this provision amends / is amended by), and if
>    so, is the direction recoverable?
> 3. Does it expose **commencement** relations (this order commences s.X of that Act on a
>    date)?
> 4. Does it expose **revocation / repeal** relations?
> 5. If any of these exist but are not in the endpoints above, what is the route to them?
>
> If the answer is "not available", that is genuinely useful to know — we will tell our users
> the system cannot verify those relationships rather than letting the model guess at them.
>
> **A related observation, from the same investigation.** `/legislation/text` returns a record
> for `ssi/2025/119` whose `text` field is **empty**, while `/legislation/section/search`
> returns nothing at all for the same identifier. At the API boundary a stub record like that
> is indistinguishable from an instrument that genuinely has no text — so we cannot tell
> "we hold this but have no text yet" apart from "this does not exist". Is there a field, a
> status value, or a convention that distinguishes them?

## P5.2 — internal/product: the Scottish case-law corpus

> The National Archives *Find Case Law* corpus does not contain the **Court of Session** or
> the **Sheriff Courts**. For a Scottish Government legal audience this is the top substantive
> content gap of the pre-pilot, and in at least one session it stopped being a coverage gap
> and produced a **wrong answer** (6375) rather than a "not found".
>
> Raised independently by three lawyers during the pre-pilot: AlistairC (*Clark* absent,
> 6359), CambeulW (recency bias in what is returned, 6363) and EmmaM.
>
> The engineering half — disclosing the gap in the answer rather than answering around it —
> is P2.4 and is not blocked on this. The question here is a product/procurement decision:
> **is there a licensable source of Court of Session and Sheriff Court decisions we can
> index, and is anyone willing to buy it?** A decision either way should be recorded; "no"
> is an answer that makes P2.4 permanent rather than interim.

## P5.3 — to the LEX team: coverage rules and refresh cadence

> We need to be able to tell a lawyer accurately why something was not found. At the moment
> we can only say "not found in the index", which is vague enough to be unhelpful and, if the
> index is simply behind, misleading.
>
> Verified absent or incomplete as at September 2026:
>
> | identifier | what we see |
> |---|---|
> | `ukpga/1962/47` (Education (Scotland) Act 1962) | 404 |
> | `ssi/2026/170` | 404 |
> | `ssi/2025/119` | record exists, `text` empty |
> | Education (Scotland) Act 1945 | stub-only provisions |
>
> 1. What are the index's **coverage rules** — is there a date floor, a category exclusion,
>    a repealed-instrument policy?
> 2. What is the **refresh cadence** from legislation.gov.uk, and what is the typical lag for
>    a newly-made SSI?
> 3. Is a 404 distinguishable from "not yet ingested"?
>
> The purpose is narrow: so our "we could not find this" message can name the real reason.

---

## When a reply arrives

1. Paste it verbatim into `SESSION_LOG.md` under the session that received it.
2. Tick the row in `FIX_PLAN.md` and record the consequence, not just the answer — P5.1 in
   particular either spawns a new row (retrieval) or makes **P2.3 permanent** (disclosure).
3. If the answer to P5.1 is "no relationships", say so in P2.3's row explicitly. A later
   session must not re-open the question on the assumption that nobody asked.
