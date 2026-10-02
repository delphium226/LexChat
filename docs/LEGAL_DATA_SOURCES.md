# Legal Data Sources — legislation and case law

Reference for what the legislation bot can and cannot retrieve: the data we hold, the gaps
in it, and where each gap could be filled from. The parliament bot's sources are in
[`parliament/PARLIAMENTARY_DATA.md`](parliament/PARLIAMENTARY_DATA.md); base URLs, auth and
endpoint traps for the APIs we call are in the `external-apis` skill
(`.claude/skills/external-apis/SKILL.md`).

> **Status as of 2026-10-02.** Fix status changes faster than this file. Where a row names a
> FIX_PLAN row, [`prepilot-fixes/FIX_PLAN.md`](prepilot-fixes/FIX_PLAN.md) is authoritative.
> "Potential sources" are leads. The only ones verified live are the LEX endpoints and the
> SCTS judgments API (see §3). Every non-LEX, non-National-Archives source would also need
> adding to the internet-restricted target's whitelist
> ([`NETWORK_AND_DEPENDENCIES.md`](NETWORK_AND_DEPENDENCIES.md)).

---

## 1. What we call today

| Source | What it gives | Called by |
|---|---|---|
| **LEX API** (`lex.lab.i.ai.gov.uk`) | UK legislation: search, section search, full text, amendment/commencement/repeal relations (P3.5), held/absent lookup (P3.7). 6 of its 13 documented endpoints | `search_legislation`, `search_legislation_sections`, `get_legislation_text`, `get_legislation_changes`, `lookup_legislation` |
| **The National Archives — Find Case Law** (`caselaw.nationalarchives.gov.uk`) | England & Wales and UK-wide judgments; Scottish appeals to the UK Supreme Court. 42 court codes, none Scottish or Northern Irish | `search_case_law`, `get_case_law_text` |

One older fix shaped every coverage number below. Until **P1.1** (2026-09-14) the
jurisdiction filter dropped every legislation result whose territorial extent was stated, so
351 of 974 filtered searches returned nothing. Any coverage impression formed before then was
based on an arbitrary subset of the data.

---

## 2. The gaps

"Recent work" says what has landed. Unless marked *branch only*, it is live on `main`
(P3.7 since `v2026.09.3`, the rest since `v2026.09.1`). Most of these fixes make the product
honest about a gap. Only the SCTS lead in §3 would actually fill one.

### 2.1 Data that doesn't exist in anything we call

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **Scottish case law below the UK Supreme Court**: Court of Session, Sheriff Appeal Court, Sheriff Courts, High Court of Justiciary (Northern Irish courts also absent) | Wrong answers, not empty ones. A "Court of Session" search returns 50 English or UK-wide judgments and the model answers from them (6375) | **Disclosure fixed, data still missing.** **P2.4** (17 Sep): when an answer draws on case law, code adds a footer naming exactly which Scottish courts aren't covered, and that UK Supreme Court appeals are. **P4.4** removed the court filter, whose options were all non-Scottish. **Source found 2026-10-02** (§3): **P5.2** is now a question of building a tool and whitelisting it, not of buying data. The build is booked as **P3.20** | **SCTS judgments search API (recommended, §3):** 13,213 Scottish judgments from 1998, full-text search, Open Government Licence. **SCTS RSS feed:** the latest 200 only. **Fallbacks:** BAILII (copies SCTS; its terms restrict automated access), Westlaw / LexisNexis / vLex (licence). **Northern Ireland is not in SCTS:** BAILII or Judiciary NI |
| **Commencement dates and in-force status** | "Was s.X in force on date Y?" can't be answered from data. LEX `status` (renamed `text_version`) is the text version held, not currency, and `/amendment/search` rows carry no date | **Partly fixed.** **P3.5** (16 Sep): `get_legislation_changes` retrieves *which* instrument commenced, amended, repealed or revoked *which* provision, but not *when*. **P2.5** (16 Sep) stops the model reading in-force status from `text_version`. **P1.2** stopped the `current_only` filter pretending to filter. **P4.18** (*branch only*, 2 Oct) fixed a footer that said no change record was consulted when one was. Open: **P3.6** (the dated `description`), **P3.19** (the change tool loses which provision made which change), **P3.21** (fetch the commencing instrument's date in code) | **legislation.gov.uk** "Changes to Legislation" effects data. A second hop into the commencing SSI's text through LEX `/legislation/text`, which works today. LEX `description` (P3.6). The LEX team (question drafted in [`WAVE5_QUESTIONS.md`](prepilot-fixes/WAVE5_QUESTIONS.md)) |
| **Point-in-time versions** of a provision | We seem to get only the one version LEX holds; "as it stood in 2015" can't be answered (not probed in LEX) | **P5.4** booked: probe legislation.gov.uk | **legislation.gov.uk** date-suffixed and `/enacted` URLs. The LEX team |
| **Enabling power** ("made under s.X") | Was the largest error class. LEX recitals exist for 18 of 25 pre-1990 UK SIs and 0 of 28 SSIs (`python -m tools.lex_probe --enabling`) | **Disclosure fixed, data still missing.** **P2.3** (16 Sep): the claim is allowed only where a recital was retrieved, otherwise the product says it couldn't be verified. Turns making an unverified claim fell from 43% to 7%. **P5.4** booked: probe legislation.gov.uk for the recital | **legislation.gov.uk instrument XML**: the full SSI text should carry the "in exercise of the powers conferred by…" recital that LEX's `description` lacks. Not probed; the most promising lead in this group. The LEX team |

### 2.2 Holes in sources we already use

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **2026 secondary legislation** (about 2% of SSI and UK SI 2026 held; SSI 2025 about 87%) and **older Acts missing one by one** (e.g. Education (Scotland) Act 1962; about 60% of 1962 Acts held) | A "not found" is usually our gap, not absence in law; lawyers were asked to recheck correct citations (6409, 6373) | **Fixed for honesty, not coverage.** **P3.7** (24 Sep, `v2026.09.3`): `lookup_legislation` tells, in code, whether each instrument a brief names by number is held, held without text, or not held. **P2.2**: negative answers state what was searched and that 2026 coverage is under 5% | **legislation.gov.uk** new-legislation feeds and direct lookup. The LEX team: why is so little of 2026 held, and is the older patchiness inherited from legislation.gov.uk? If it is, legislation.gov.uk won't fill it |
| **How far back National Archives case law goes is unmeasured** (feed caps at 50, no totals) | Session 6363's recency-bias complaint can be neither confirmed nor ruled out | None | **The National Archives Find Case Law team**: ask for a coverage statement. **BAILII** for older England & Wales material |
| **Schedules and EU Annexes come back as one provision** | Can't fetch a schedule paragraph or Annex chapter by number. 6335 looped 18 times on Sch B1 para 43; an Annex chapter was called "not held" 2 times in 3 | **Open.** **P3.12** is booked (measure first). The P3.1 cap now stops the looping after 3 rounds. Cutting out Annex chapters works in dev tooling (`tools/provision_hints.py`) but isn't in the product. **P5.4** probes legislation.gov.uk's paragraph-level markup | **legislation.gov.uk XML** (paragraph-level markup). **Cutting locally**, building on `provision_hints.py` |

### 2.3 Data we could have but don't use

| Gap | What it costs us | Recent work | Potential sources |
|---|---|---|---|
| **`description` on search results**: commencement and enabling relationships in prose, with dates | Thrown away by `_slim_search_results` | **Open (P3.6).** It must be truncated or filtered, not restored wholesale, because the original stripping is what kept Phase 1 under the summarisation threshold | **LEX**: already in the responses we receive |
| **Explanatory notes for Acts** | Would have settled 6338: which interpretation regime applies to an amended Act | **Not called.** The underlying defect is being worked through prompts: **P3.3** open; **P3.17** measured with options, not yet accepted | **LEX** `/explanatory_note/legislation/lookup`, `/section/lookup`, `/section/search`. Acts only: an SSI returns 404 |
| **Policy and executive notes for SSIs** | No official statement of purpose for secondary legislation | None | **legislation.gov.uk** associated documents |
| **Amendment relations at provision level** | P3.5 queries at instrument level only | None | **LEX** `/amendment/section/search` |

---

## 3. SCTS judgments API — probed 2026-10-02

The Scottish Courts and Tribunals Service runs a JSON search API behind the judgments search
page on scotcourts.gov.uk. It isn't documented or published as an API. It was found by
reading the page's JavaScript (`/apps/NoResults.min.js` holds the AutoRest client,
`azsdk-js-scts-api-client/1.0.0-beta.1`). Everything below was measured live.

### Endpoints

| Call | Purpose |
|---|---|
| `POST https://api.pa.web.scotcourts.gov.uk/web/search` | Search. JSON body `{"query", "filters": [{"field", "value"}], "page", "limit", "indexType": "Judgments", "category": ""}`. Returns `{results: [...], pagination: {count: {total, start, end}, page: {current, total, limit}}}` |
| `GET https://api.pa.web.scotcourts.gov.uk/web/definition/1414` | The search page's definition: filter fields, court values, result columns |
| `GET https://api.pa.web.scotcourts.gov.uk/web/rss/Judgments` | Published RSS feed: the latest 200 judgments as title, date and PDF link. Other index types: `FatalAccidentInquiryDeterminations`, `PracticeNotesAndDirections`, … |
| `GET https://www.scotcourts.gov.uk{documentLink}` | The judgment PDF |

The `api.dv.` host baked into the client as its default is a development environment; the
page passes the production base URL (`api.pa.`) in `data-base-url`.

### Filters

- `Court`: exact values from the definition, e.g. `Court of Session`, `High Court of Justiciary`, `Sheriff Appeal Court Civil`, `Sheriff Court Civil`, `Upper Tribunal - Housing and Property Chamber`.
- `AdditionalDate` (date of opinion/decision) and `Date` (date published): value `YYYY-MM-DD|YYYY-MM-DD`; either side may be empty.

### Result fields

`title`, `documentLink`, `court[]`, `sheriffdom[]`, `judges[]`, `additionalDate`, `date`,
`tags[]`. **No neutral citation field.** It appears in newer PDF filenames (`2026csoh94-…pdf`)
and in the PDF text from 2005 (when Scotland adopted neutral citations).

### Coverage (2026-10-02)

**13,213 judgments in total.**

| Court | Judgments |
|---|---|
| Court of Session | 7,121 |
| High Court of Justiciary | 2,899 |
| Sheriff Court (civil) | 1,986 |
| Sheriff Appeal Court (civil) | 410 |
| Sheriff Appeal Court (criminal) | 157 |
| National Personal Injury Court | 155 |
| Upper Tribunal, Housing and Property Chamber | 269 |
| Upper Tribunal, Social Security Chamber | 96 |
| Sheriff Court (criminal) | 3 |

By decision year: 1997: 2, 1998: 160, 1999: 590, then roughly 330–590 a year through 2026
(2026 to date: 388). Sheriff Court coverage is only what SCTS chooses to publish ("as a
general rule … published unless there is a requirement, or otherwise good reason, not to"),
so it is a fraction of decisions, and criminal sheriff decisions are almost absent.

### Search behaviour

- **Full text, not titles.** `Wednesbury` returns 528 results, and none of the top three has the word in its title.
- **Quoted phrases work.** `"title to sue"` gives 354; `"Wednesbury unreasonable"` 123; `"Interpretation and Legislative Reform (Scotland) Act 2010"` 27.
- **Unquoted multi-word queries behave like OR.** The unquoted ILRA title matched 12,703 of 13,213. A tool must quote phrases.
- **Paging works:** `limit=500` returned 500 rows, and the total is exact.

### Text

Judgment text is only in the PDF. Five PDFs sampled across 1999–2026, covering the Court of
Session, High Court of Justiciary and Sheriff Court, all extracted cleanly with `pypdf`
(4–31 pages, 12,000–81,000 characters). `pdfplumber` is already in
`server_py/requirements.txt` but **not in the offline installer bundle**, so the bundle would
need regenerating before the target could parse PDFs.

### Terms

SCTS's [Crown copyright policy](https://www.scotcourts.gov.uk/scts-crown-copyright-policy)
allows reuse of the site's information "free of charge in any format or medium, under the
terms of the Open Government Licence". It excludes only logos, photographs and third-party
material, and says nothing either way about automated use. `robots.txt` disallows only
`/umbraco/` and `/*?query=*`. That is a much cleaner position than BAILII, which republishes
these judgments and restricts automated access.

### Risks

1. **It is not a published contract.** The client is versioned `1.0.0-beta.1`, and SCTS reworked the judgments system in May 2025, telling RSS users to disable their feeds during the change. Ask SCTS (`enquiries@scotcourts.gov.uk`) before building on it.
2. **Date metadata may be unreliable.** In 2 of 5 samples, a decision-date filter for one year returned a judgment cited from a later year: a 2012 filter returned a `[2015] HCJAC`, a 2020 filter returned a `[2021] SC GLW`. Too small a sample to call a pattern; check before trusting date filters.
3. **Two hosts to whitelist:** `api.pa.web.scotcourts.gov.uk` (search) and `www.scotcourts.gov.uk` (PDFs).
4. **Not Northern Ireland, and not unpublished decisions.**

### Reproduce

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"query":"\"title to sue\"","filters":[{"field":"Court","value":"Court of Session"}],"page":1,"indexType":"Judgments","category":"","limit":5}' \
  https://api.pa.web.scotcourts.gov.uk/web/search
```
