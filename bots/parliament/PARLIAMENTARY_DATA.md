# Parliamentary Data Model

Reference for how the parliament bot's data is structured and what is available for each
data type. **The parliament bot is Scotland-only (Scottish Parliament / Holyrood).** All
Westminster (UK Parliament / Hansard) search and retrieval has been removed.

The bot draws on four distinct data sources, each with a different structure, freshness
model, and level of retrievable detail. The single most important distinction:

> **Committee transcripts *and plenary (chamber) debates* are crawled into local databases
> and are fully searchable and retrievable. Written answers, bills, and members are fetched
> live at query time and are excerpt-only / metadata-only.**

---

## 1. The Scottish Parliament session model

Holyrood organises its work into **parliamentary sessions** — the period between two
general elections. Each session contains all the meetings, debates, bills, and members
current during that term. The Scottish Parliament Official Report exposes sessions as
discrete filters:

| Session | Start | End | Notes |
|---|---|---|---|
| Session 1 | 12 May 1999 | 6 May 2003 | |
| Session 2 | 7 May 2003 | 8 May 2007 | |
| Session 3 | 9 May 2007 | 10 May 2011 | |
| Session 4 | 11 May 2011 | 11 May 2016 | |
| Session 5 | 12 May 2016 | 11 May 2021 | |
| **Session 6** | **13 May 2021** | 12 May 2026 | Crawled into the DB (see §3) |
| **Session 7** | **14 May 2026** | *current* | Crawled into the DB (see §3) |

(Dates as published by the SP Official Report session picker.)

### How sessions gate the source data

The SP Official Report search (`search-what-was-said-in-parliament`) **defaults to the
current session** and silently ignores a custom `dtDateFrom`/`dtDateTo` range that falls
outside it. To retrieve older sessions the request **must include `dateSelect=custom`** —
this is a non-obvious requirement discovered during crawler development. Without it, a
2022 date window returns zero meetings even though the data exists. The crawler sets this
param on every backfill window (see `backfill_sessions()` in
`server_py/src/services/parliament_crawler.py`).

The crawler currently backfills from **Session 6 start (13 May 2021)** onward, covering
Session 6 and Session 7. The dissolution gap between sessions simply returns empty
windows. To include earlier sessions, move `_BACKFILL_START` further back.

---

## 2. Data hierarchy

### Committee transcripts & plenary debates (the crawled, DB-backed sources)

Both share the same hierarchy and table shape. Committee transcripts:

```
Session
└── Meeting                     (one committee sitting on one date)
    │   meeting_id   e.g. "13588"
    │   slug         e.g. "SPPAC-10-02-2022"   (committee code + date)
    │   committee    e.g. "Standards, Procedures and Public Appointments Committee"
    │   date         e.g. 2022-02-10
    └── Agenda item              (one item of business within the meeting)
        │   iob_id   e.g. "223940"   ("item of business" ID)
        │   title    e.g. "Subordinate Legislation"
        └── Speeches             (verbatim contributions)
                speaker + text, in order
```

Plenary (chamber) debates:

```
Session
└── Meeting of Parliament       (one plenary sitting on one date)
    │   meeting_id   e.g. "20164"
    │   slug         e.g. "meeting-of-parliament-02-06-2026"
    │   committee    (label only) "Meeting of Parliament"  (committee_code "MOP")
    │   date         e.g. 2026-06-02
    └── Agenda item              (FMQs, General Question Time, named debate, Decision Time)
        │   iob_id   e.g. "223568"   ("item of business" ID)
        │   title    e.g. "Phone-free Classrooms"
        └── Speeches             (verbatim, attributed contributions)
                speaker + text, in order
```

A single row in the `sp_committee_items` / `sp_plenary_items` table = **one agenda item of
one meeting**, uniquely identified by `(meeting_id, iob_id)`. The full speech list for that
item is stored inline (as JSON) plus a flattened `full_text` blob for full-text search.

### Written answers / bills / members (live sources)

These have **no local hierarchy** — they are queried live and return flat result lists
(speech excerpts, bill summaries, or member records). See §4.

---

## 3. The `sp_committee_items` and `sp_plenary_items` tables

Populated by the background crawler; queried via PostgreSQL GIN full-text search. Models:
`SpCommitteeItem` and `SpPlenaryItem` in `server_py/src/models.py`. **The two tables have an
identical schema and mechanism** — the only differences are the table/constraint names
(`uq_sp_meeting_iob` vs `uq_sp_plenary_meeting_iob`) and that plenary rows carry the fixed
label `committee_name = "Meeting of Parliament"` / `committee_code = "MOP"` (plenary has no
committee).

| Column | Type | Description |
|---|---|---|
| `id` | int PK | |
| `meeting_id` | str, indexed | Meeting identifier from the Official Report (`?meeting=ID`) |
| `slug` | str | URL slug — committee code + date, e.g. `SPPAC-10-02-2022` |
| `iob_id` | str | Agenda item ("item of business") ID (`&iob=ID`) |
| `committee_code` | str, indexed | Short code, e.g. `SPPAC`, `FPA`, `PSRC` |
| `committee_name` | str, indexed | Full committee name |
| `meeting_date` | date, indexed | Date of the sitting |
| `agenda_item_title` | str | Title of the agenda item |
| `url` | str, unique | Canonical transcript URL (`slug?meeting=ID&iob=ID`) |
| `speeches` | JSON | Ordered list of `{speaker, text}` objects |
| `full_text` | text | Committee name + agenda title + all speeches, flattened for FTS |
| `fetched_at` | datetime | When the crawler stored the row |

- **Unique constraint** on `(meeting_id, iob_id)` — the crawler inserts with
  `ON CONFLICT DO NOTHING`, so re-crawls are idempotent and resumable.
- **Full-text search** runs `to_tsvector('english', full_text) @@ plainto_tsquery(...)`,
  ranked by `ts_rank`, optionally filtered by committee (committee table only, ILIKE on
  name/code) and date range.

### How the crawler populates them

`server_py/src/services/parliament_crawler.py`, started on app startup **only when
`RESEARCH_MODE=parliamentary_records`**:

1. **`backfill_sessions()`** — one-shot (committee). Iterates two-week windows from
   `_BACKFILL_START` (Session 6 start) to today, requesting the Official Report listing
   with `showCommittee=true&dateSelect=custom&dtDateFrom=X&dtDateTo=Y`. For each meeting
   found it fetches the meeting page (→ committee name + agenda items) and then each
   agenda item's transcript page (→ speeches). Rate-limited to ~1.5 req/s.
2. **`backfill_plenary()`** — one-shot (plenary). Same as above but with `showPlenary=true`
   and `_parse_sp_plenary_meetings` (which *includes* the `meeting-of-parliament-*` slugs the
   committee parser excludes); item pages are parsed with `_parse_sp_plenary_transcript`.
   Runs **after** `backfill_sessions()` so the two don't hit the origin concurrently.
   Transcript fetches use `_fetch_sp_page_with_retry` (retry/backoff, reject <20 KB) because
   the large plenary pages intermittently return a Cloudflare 524 error page.
3. **`background_crawl_loop()`** / **`background_plenary_crawl_loop()`** — run
   `crawl_sp_new_meetings()` / `crawl_sp_new_plenary()` daily against the current listing
   page to pick up new sittings. The plenary loop is self-staggered (first run ~5 min after
   startup) to avoid overlapping the committee crawl.

Written answers, bills, and members are **not** crawled — they are fetched live per query.

---

## 4. Data types and what is available

| Data type | Source | Tool(s) | Keyword search | Full text retrievable | Date filter | Session coverage |
|---|---|---|---|---|---|---|
| **Committee transcripts** | Local DB (crawled from SP Official Report) | `search_scottish_committee_transcripts` → `get_scottish_committee_transcript` | ✅ FTS | ✅ verbatim speeches | ✅ | Session 6 + 7 (whatever is crawled) |
| **Plenary (chamber) debates** | Local DB `sp_plenary_items` (crawled from SP Official Report) | `search_scottish_plenary` → `get_scottish_plenary_debate` | ✅ FTS | ✅ **verbatim speeches** | ✅ | Session 6 + 7 (whatever is crawled) |
| **Plenary debates (fallback)** | TheyWorkForYou `getHansard` (live) | `search_scottish_parliament` | ✅ | ❌ excerpt only | ⚠️ ignored by TWFY | Whatever TWFY indexes (older/breadth fallback) |
| **Written answers** | TheyWorkForYou `getHansard` type=spwrans (live) | `search_scottish_parliament` (`debate_type=written_answers`) | ✅ | ❌ excerpt only | ⚠️ ignored | Whatever TWFY indexes |
| **Bills** | `data.parliament.scot/api/bills` (live) | `search_bills` | ⚠️ client-side keyword filter | n/a (metadata) | ❌ | All Holyrood bills |
| **Members (MSPs)** | TheyWorkForYou `getMSPs` (live) | `get_member_info` | by name | n/a (bio record) | ❌ | Current + historic MSPs |

### Committee transcripts & plenary debates — the fully-retrievable sources

- **Committee search** (`search_scottish_committee_transcripts`): full-text keyword search
  over the DB. Returns up to 10 ranked agenda items with `meeting_id`, `slug`, `iob_id`,
  `committee_name`, `meeting_date`, `agenda_item_title`, `url`, and a 300-char excerpt.
  Optional `committee` and `date_from`/`date_to` filters.
- **Committee retrieve** (`get_scottish_committee_transcript`): pass `meeting_id` + `slug` +
  `iob_id` back to fetch the verbatim transcript — full speeches (minister responses, member
  questions, witness evidence). This is a **live fetch** of the transcript page (not the
  DB), returning `{page_title, committee_name, url, speeches[], total_speeches}`.
- **Plenary search** (`search_scottish_plenary`): full-text keyword search over
  `sp_plenary_items`. Same result shape as committee search (no `committee` filter). Optional
  `date_from`/`date_to`.
- **Plenary retrieve** (`get_scottish_plenary_debate`): pass `meeting_id` + `slug` + `iob_id`
  back to fetch the verbatim chamber speeches for that agenda item (a ministerial statement,
  an FMQs exchange, a named debate). Live fetch parsed by `_parse_sp_plenary_transcript`
  (scoped to the item via its stored `agenda_item_title`), with retry/backoff for Cloudflare
  524s. Returns `{page_title, url, speeches[], total_speeches}`. This is the *Pepper v Hart*
  route — the minister's exact words, verbatim.
- If a DB is empty (crawl not yet finished), the corresponding search returns a graceful note
  telling the model to fall back to `search_scottish_parliament`.

### Plenary (fallback) & written answers — excerpt only

- Backed by TheyWorkForYou's `getHansard`. `search_scottish_parliament` is **excerpt-only**
  (max ~400 chars each, up to 10 results) — for full plenary text use `search_scottish_plenary`
  + `get_scottish_plenary_debate` instead. `search_scottish_parliament` remains useful as an
  older-session / breadth fallback (TWFY may index dates not yet crawled into `sp_plenary_items`)
  and is the route for **written answers**.
- TWFY quirks baked into the code:
  - `type=sp` is **broken** (returns Westminster content) — the caller omits it and
    post-filters results to SP by `/sp/` and `/spwrans/` listurl patterns.
  - Debate titles come from `speech.parent.body` (HTML), not `speech.debate` (always empty).
  - `date_from`/`date_to` are **not supported** by TWFY `getHansard` and are silently ignored.
- Requires `TWFY_API_KEY`; without it `search_scottish_parliament` returns a clear error.

### Bills — metadata only

- The Scottish Parliament Bills API returns the full list; there is no server-side search,
  so `search_bills` fetches everything and filters by keyword client-side (short/long
  title). Returns `billId`, `shortTitle`, `currentStage`, and a link — no bill text.

### Members (MSPs) — biographical record

- `get_member_info` calls TWFY `getMSPs` with a name search (the old `getMSPInfo` endpoint
  was removed). Returns biography, party, constituency, and roles. Scotland/MSPs only.

---

## 5. Filter enforcement

The frontend exposes a **Record type** filter (`debates` / `written_answers` / `committee`)
and a **Date range**. `_apply_parliament_filters` in `parliament.py` maps these onto tools:

- `debates` → redirects `search_scottish_parliament` to `search_scottish_plenary` (the
  full-text plenary route); a `search_scottish_plenary` call is allowed through.
- `written_answers` → sets `debate_type='written_answers'` on `search_scottish_parliament`.
- `committee` → short-circuits `search_scottish_parliament` **and** `search_scottish_plenary`
  with a redirect telling the model to use `search_scottish_committee_transcripts`.
- Date range → merged into `search_scottish_committee_transcripts` and `search_scottish_plenary`
  (honoured, DB queries) and `search_scottish_parliament` (accepted but ignored downstream by
  TWFY).

A `search_budget` of 3 caps the total number of `search_scottish_plenary` +
`search_scottish_parliament` + `search_scottish_committee_transcripts` calls per research run,
forcing weaker models to stop searching and synthesise.

---

## 6. Known gaps — data a researcher may expect but the bot does not (yet) provide

Prioritised by impact for the bot's audience (lawyers doing statutory-interpretation and
scrutiny research). None of these are bugs — they are coverage boundaries.

### Tier 1 — undercuts the core legal use case

- ~~**No full text for plenary (chamber) debates.**~~ **CLOSED.** Plenary chamber debates are
  now crawled into `sp_plenary_items` and exposed via `search_scottish_plenary` (FTS) →
  `get_scottish_plenary_debate` (verbatim speeches), mirroring the committee pipeline. This
  closes the *Pepper v Hart* gap: a minister's full statement of statutory purpose in the
  chamber is now retrievable verbatim. `_parse_sp_plenary_transcript` parses the plenary
  markup (`<p id="orscontributions_...">` contributions, speaker in the first `/msps/` anchor)
  — validated at 30/30 and 41/41 speech attribution on the spike fixtures. `search_scottish_parliament`
  (TWFY, excerpt-only) is retained only as an older-session/breadth fallback. Operational
  handling: transcript fetches retry with backoff and reject <20 KB Cloudflare-524 error pages
  (`_fetch_sp_page_with_retry`); the fetcher forces UTF-8 so mislabelled charset doesn't leave
  replacement chars in `full_text`.
- **Bills are metadata-only.** `search_bills` returns title, current stage, and a link.
  Missing the material lawyers reason from: bill text, how a provision changed
  Stage 1→2→3, amendments/marshalled lists, and — importantly — the **Explanatory Notes,
  Policy Memorandum, and Financial Memorandum** that accompany a bill and are heavily used
  in statutory interpretation. No Royal Assent date either.

### Tier 2 — standard parliamentary research staples, entirely absent

- **Voting / division records** — how MSPs voted on a bill or motion.
- **Motions and amendments** (S6M-xxxxx) — the formal instruments debates hang on.
- **Published committee outputs** — the committee tool covers *meeting transcripts*
  (Official Report) but **not** formal inquiry/Stage 1 reports or **written evidence
  submissions** to inquiries, which are often more citable than the oral session.
- **Public petitions** (PE numbers) and their consideration.

### Tier 3 — coverage boundaries within existing sources

- **Committees & plenary: Session 6–7 only.** Pre-May-2021 work returns nothing from the
  crawled DBs. The TWFY `search_scottish_parliament` fallback may reach further back but
  remains excerpt-only.
- **Plenary date filtering** — now honoured for `search_scottish_plenary` (DB query). It is
  still silently ignored by the TWFY `search_scottish_parliament` fallback (`getHansard`
  drops `date_from`/`date_to`).
- **Transcript truncation** — `get_scottish_committee_transcript` and
  `get_scottish_plenary_debate` cap each speech at 3000 chars (committee also caps at 30
  speeches); very long sessions are cut.
- **MSP data is bio-only** — no Register of Interests, no per-member voting history.

---

## 7. Quick reference — external endpoints

| Source | Base URL | Auth |
|---|---|---|
| SP Official Report (committee + plenary crawl + transcript fetch) | `https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament` | none |
| TheyWorkForYou (`getHansard`, `getMSPs`) | `https://www.theyworkforyou.com/api` | `TWFY_API_KEY` |
| SP Bills | `https://data.parliament.scot/api/bills` | none |
